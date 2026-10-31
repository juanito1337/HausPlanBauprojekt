# -*- coding: utf-8 -*-
"""Compose the delivered, unchanged MAIN01-A01 and R11a engines.
G01a adds automatic import checkpoints, raw point results and a bounded failure
probe. The production distance query and geometry acceptance stay unchanged.
All new NX interactions reuse the existing adapter methods in the source packages.
"""
import copy
import importlib
import importlib.util
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
from . import PATCH
from .core import (absolute, read_json, write_json, saved_record, relative_file,
                   check_records, environment_offset)

HOUSE_ROOT = 'haus'
ENV_ROOT = 'umgebung'
PROJECT_OPEN = 'PROJEKT_MASTER_G01_HOEHENBEZUG_OFFEN.prt'
PROJECT_ALIGNED = 'PROJEKT_MASTER_G01.prt'
UTILITY_MASTER = 'LEITUNGSPLAN_MASTER_G01.prt'
UTILITY_PARTS = ['07A_GAS_PLANPROJEKTION.prt','07B_STROM_PLANPROJEKTION.prt',
                 '07C_TELEFON_PLANPROJEKTION.prt','07D_BREITBAND_PLANPROJEKTION.prt']


def load_package(name, directory):
    """Resolve one exact package; never accidentally reuse an older extracted version."""
    directory = absolute(directory)
    if not (directory/'__init__.py').is_file():
        raise FileNotFoundError('Python-Paket fehlt: '+str(directory))
    for key in list(sys.modules):
        if key == name or key.startswith(name+'.'):
            del sys.modules[key]
    spec = importlib.util.spec_from_file_location(name,str(directory/'__init__.py'),
                            submodule_search_locations=[str(directory)])
    if spec is None or spec.loader is None:
        raise RuntimeError('Python-Paket nicht ladbar: '+name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class NXBackend:
    def __init__(self, base, session_provider=None):
        self.base = absolute(base)
        self.session_provider = session_provider
        self.flavour = None

    def session(self):
        if self.session_provider is not None:
            return self.session_provider()
        try:
            import NXOpen
            return NXOpen.Session.GetSession()
        except ImportError as error:
            raise RuntimeError('In NX ueber Journal abspielen starten; NXOpen nicht mit pip nachinstallieren.') from error

    def house_modules(self):
        if self.flavour != 'house':
            load_package('haus2406_r03',self.base/HOUSE_ROOT/'src/haus2406_r03')
            load_package('main01',self.base/HOUSE_ROOT/'src/main01')
            self.flavour = 'house'
        return SimpleNamespace(
            runtime=importlib.import_module('main01.runtime'),
            compiler=importlib.import_module('haus2406_r03.haus_compile'))

    def environment_modules(self):
        if self.flavour != 'environment':
            # These legacy helpers support STEP/assembly operations only.
            # The legacy build_house_copy path is NEVER invoked by our environment call.
            load_package('haus2406_r03',self.base/ENV_ROOT/'basis/Haus_R06/src/haus2406_r03')
            load_package('r09',self.base/ENV_ROOT/'r09')
            self.flavour = 'environment'
        return SimpleNamespace(
            core=importlib.import_module('r09.core'),
            perf=importlib.import_module('r09.performance'),
            run=importlib.import_module('r09.run'),
            nx=importlib.import_module('r09.nx_adapter'),
            selection=importlib.import_module('r09.vegetation_review'),
            utilities=importlib.import_module('r09.utilities'),
            site=importlib.import_module('haus2406_r03.haus_site'))

    def preflight(self, mode, config, reuse=None):
        names = set()
        if mode in ('ALL','HOUSE'):
            h = self.house_modules()
            h.runtime.verify_package(self.base/HOUSE_ROOT)
            data = read_json(self.base/HOUSE_ROOT/'data/haus.json')
            names.update(p['file'].casefold() for p in h.compiler.compile_house(data,True)['parts'])
            names.add('haus_master.prt')
        if mode in ('ALL','ENVIRONMENT'):
            e = self.environment_modules(); root = self.base/ENV_ROOT
            e.core.verify_runtime_files(root)
            job = e.core.read_json(root/'data/IMPORTAUFTRAG_R09.json')
            e.core.validate_job(root,job)
            selected,_ = e.selection.selected_job(root,job)
            names.update(p['part_file'].casefold() for p in selected['parts'])
            names.update(['umgebung_master_r09.prt','11_kartenreferenzen_r09.prt'])
        if mode in ('ALL','ASSEMBLE'):
            names.update(p.casefold() for p in UTILITY_PARTS+[UTILITY_MASTER,PROJECT_OPEN,PROJECT_ALIGNED])
        if mode == 'ASSEMBLE':
            if not reuse or set(reuse) != {'house','environment'}:
                raise ValueError('Zusammenstellung braucht beide bestaetigten Teilergebnisse.')
            # Refuse in-memory edited children; no guesses about dirty/stale model state.
            names.update(Path(r['path']).name.casefold() for component in reuse.values()
                         for r in component['files'] if Path(r['path']).suffix.lower()=='.prt')
        conflicts = [str(part.FullPath) for part in self.session().Parts
                     if Path(str(part.FullPath)).name.casefold() in names]
        if conflicts:
            raise RuntimeError('Vorgesehene Projektteile sind bereits geladen. Eigene Arbeit speichern, '
                'die genannten Teile manuell schliessen (nicht nur ausblenden). Keine Dateien loeschen:\n'+'\n'.join(conflicts))

    def build_house(self, out, config):
        h = self.house_modules(); source = self.base/HOUSE_ROOT
        h.runtime.verify_package(source)
        inputs = Path(out)/'eingaben_haus'
        inputs.mkdir(exist_ok=False)
        registry = read_json(source/'PAKETDATEIEN_SHA256.json')
        # Exact, complete source snapshot. Change only allowed output-directory setting.
        for name in list(registry['files'])+['PAKETDATEIEN_SHA256.json']:
            src = relative_file(source,name); dst = relative_file(inputs,name)
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
        options = read_json(inputs/'data/einstellungen.json')
        options['output_root'] = str(absolute(Path(out)/'haus'))
        write_json(inputs/'data/einstellungen.json',options)
        result = h.runtime.run_main(inputs)
        if result.get('status') != 'MAIN01_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT':
            raise RuntimeError('MAIN01-A01 Hauslauf nicht vollstaendig abgeschlossen.')
        directory = absolute(result['output_directory'])
        baseline = read_json(directory/'BASELINE_MAIN01.json')
        if baseline.get('revision') != 'MAIN01-A01':
            raise RuntimeError('Falscher Hausstand im Lauf. MAIN01-A01 erforderlich.')
        # Files + baseline snapshot: later ASSEMBLE rejects edited original files.
        records = [saved_record(relative_file(directory,row['file'])) for row in baseline['saved_files']]
        records.extend(saved_record(directory/name) for name in ['BASELINE_MAIN01.json','manifest_MAIN01.json'])
        return {'kind':'house','revision':'MAIN01-A01','status':'GESPEICHERT_UND_DATEIGEPRUEFT',
                'master':result['saved_house'],'files':records,'as_built_verified':False,
                'mode':result['mode'],'built_solids':result['built_solids'],
                'component_count':result['component_count'],
                'known_collision_pairs':result['numerical_collisions'],
                'blocked_openings':result['blocked_openings'],
                'progress':str(directory/'LAUFSTATUS_MAIN01.json'),
                'baseline':str(directory/'BASELINE_MAIN01.json'),
                'input_snapshot':str(inputs), 'manual_changes_from_previous_models_carried_over':False}

    def build_environment(self, out, config):
        e = self.environment_modules(); root = self.base/ENV_ROOT
        monitor_dir = absolute(Path(out)/'umgebung')
        monitor_dir.mkdir(exist_ok=False)
        cfg = e.core.read_json(root/'data/EINSTELLUNGEN_R09.json')
        cfg['build_house'] = False
        # Call the same engine directly, avoiding three redundant timestamp folders.
        cfg['output_root'] = str(monitor_dir)
        cfg['step_settings_file'] = config['step_settings_file']
        if cfg['step_settings_file'] and not Path(cfg['step_settings_file']).is_absolute():
            cfg['step_settings_file'] = str(absolute(self.base/cfg['step_settings_file']))
        cfg['height_connection'] = {'H_EG_zero_in_source_datum_m':None,'source':'',
                                   'common_vertical_datum_confirmed':False}
        policy = e.core.read_json(root/'data/LAUFZEIT_R11a.json')
        policy['surface_validation'] = config['surface_validation']
        e.perf.policy_checked(policy)
        monitor = e.perf.RunMonitor(monitor_dir)
        def factory(logger):
            from .terrain_uv import make_uv_audited_adapter as make_audited_adapter
            cls = make_audited_adapter(e.perf.FastSceneAdapter,
                                      self.base/'data/DGM_REFERENZPUNKTE_G01a.json')
            return cls(logger,monitor,policy)
        def _reject_legacy_house(*args,**kwargs):
            raise RuntimeError('Alter Umgebungshaus-Erzeuger darf in G01 nicht aufgerufen werden.')
        model = None
        try:
            # Same STEP, adaptive measurement, BASIS and profiling code as R11a.
            model = e.run.run_project(root,config=cfg,adapter_factory=factory,
                                      house_builder=_reject_legacy_house,notify=False)
            allowed = ('R09_ERZEUGT_BEZUGSSYSTEME_GETRENNT','R09_ERZEUGT_MIT_NUTZERHOEHENANSCHLUSS')
            if (model.get('status') not in allowed or model.get('phase') != 'ABGESCHLOSSEN'
                    or model.get('house',{}).get('mode') != 'NICHT_ERZEUGT_LAUT_EINSTELLUNG'
                    or model.get('environment_status') != 'ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT'):
                raise RuntimeError('Umgebungs-Ergebnis unvollstaendig oder alter Hausbuilder wurde aufgerufen.')
            directory = absolute(model['output_directory'])
            monitor.finish('ABGESCHLOSSEN_UMGEBUNG_FACHLICH_OFFEN')
            meta_path = monitor_dir/'manifest_UMGEBUNG_G01.json'
            write_json(meta_path,{'patch':PATCH,'status':'UMGEBUNG_GESPEICHERT_UND_GEPRUEFT',
                       'engine':'R11a_FastSceneAdapter_WITH_EXISTING_R09_IMPORT_ENGINE',
                       'old_house_builder_allowed':False,'policy':policy,
                       'model_manifest':str(directory/'manifest_R09.json'),
                       'model_result':model,'DGM_point85_fixed':False,'NX_tested_here':False})
            records = [saved_record(relative_file(directory,row['relative_file'])) for row in model['files']]
            records.append(saved_record(meta_path))
            return {'kind':'environment','revision':'R11a_MIT_G01e_RASTERFLAECHENPRUEFUNG',
                    'status':'GESPEICHERT_UND_DATEIGEPRUEFT',
                    'master':str(relative_file(directory,model['environment_master'])), 'files':records,
                    'as_built_verified':False,'surface_validation':model['surface_validation'],
                    'new_house_built_by_environment':False,
                    'full_surface_check_performed':model['surface_full_reference_check_performed'],
                    'source_geometry_changed':False,'terrain_source_topology_changed':True,
                    'terrain_boundary_representation':'366_EXACT_LINE_SEGMENTS',
                    'DGM_POINT85_ROOT_CAUSE_FIXED':False,
                    'progress':str(monitor.status_file),
                    'detailed_manifest':str(directory/'manifest_R09.json')}
        except Exception as error:
            error.r11a_context={'output_directory':str(monitor_dir),'progress_file':str(monitor.status_file),
                'last_step':monitor.snapshot(),'phase':'G01_UMGEBUNG_DIREKT',
                'saved_environment_master':str(absolute(model['output_directory'])/model['environment_master'])
                    if model and model.get('environment_status')=='ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT' else None}
            try:
                monitor.finish('ABGEBROCHEN_KEIN_GESAMTERFOLG')
            except Exception as secondary:
                error.r11a_diagnostic_error=str(secondary)
            raise

    def assemble(self, out, house, environment, config):
        e = self.environment_modules(); out = absolute(out)
        log = e.run.Log(out/'projekt_zusammenstellung.log')
        nx = e.nx.SceneAdapter(log); log.nx = nx
        nx._attribute_update_option = getattr(nx.N.Update.Option,'Later',nx.N.Update.Option.Now)
        records = []
        # Re-create only lightweight historical line references, not their house.
        data = read_json(self.base/HOUSE_ROOT/'data/haus.json')
        review,_ = e.utilities.load_review(self.base/ENV_ROOT)
        data = e.utilities.decorate_house_data(data,review)
        source_site = copy.deepcopy(data['site']); source_site['enabled'] = True
        data['site'] = source_site
        refs = {'parts':[],'coverage':[],'warnings':[]}
        e.site.apply_site(data,refs)
        groups = [part for part in refs['parts'] if part['id'] != 'GRUNDSTUECK']
        ref_dir = out/'planreferenzen'; ref_dir.mkdir(exist_ok=False)
        expected_refs = []; segment_count = 0
        for spec in groups:
            path = ref_dir/spec['file']; part = nx.new_part(path,spec['id'])
            for line in spec['references']:
                objects = nx.lines(part,line['points3d'],line['id'],closed=line['closed'],blank=False,meta=line)
                expected_count = len(line['points3d']) if line['closed'] else len(line['points3d'])-1
                if len(objects) != expected_count:
                    raise RuntimeError('Leitungsplansegment fehlt: '+line['id'])
                for obj in objects:
                    obj.Layer = 1; obj.Unblank()
                segment_count += len(objects)
            for title,value in {'HAUS_GEOMETRIEART':'HISTORISCHE_PLANLINIEN_KEIN_LEITUNGSROHR',
                'HAUS_VERLEGETIEFEN':'UNBEKANNT','HAUS_Z_BEZUG':'Z0_NUR_ZEICHENEBENE_KEINE_GELAENDEHOEHE',
                'HAUS_NUTZUNG_ERDARBEITEN':'NICHT_FREIGEGEBEN','HAUS_REVISION':PATCH}.items():
                nx._set_user_attribute(part,title,value,'PLANREFERENZEN')
            nx.save(part); records.append(saved_record(path))
            expected_refs.append((spec['id'],path,(0,0,0)))
        utility_path = ref_dir/UTILITY_MASTER
        utility = nx.new_part(utility_path,'LEITUNGSPLANREFERENZEN_G01')
        for name,path,pos in expected_refs:
            nx.add_at(utility,path,name,pos)
        ref_checks = e.run.check_master(nx,utility,expected_refs)
        nx._set_user_attribute(utility,'HAUS_VERLEGETIEFEN','UNBEKANNT_KEINE_PHYSISCHE_MONTAGE','PLANREFERENZEN')
        nx.save(utility); records.append(saved_record(utility_path))
        offset = environment_offset(config)
        final = out/(PROJECT_OPEN if offset is None else PROJECT_ALIGNED)
        master = nx.new_part(final,'PROJEKT_MAIN01_A01_G01')
        expected = [('HAUS_MAIN01_A01',Path(house['master']),(0,0,0)),
                    ('UMGEBUNG_QUELLHOEHEN' if offset is None else 'UMGEBUNG_Z_BEZUG_NUTZERANGABE',
                       Path(environment['master']),offset or (0,0,0)),
                    ('LEITUNGSPLAN_KEINE_TIEFEN_NICHT_PHYSISCH',utility_path,(0,0,0))]
        for name,path,pos in expected:
            comp = nx.add_at(master,path,name,pos)
            if path == utility_path:
                comp.Blank()  # avoid drawing Z=0 lines as if they were installed underground
        attributes = {'HAUS_REVISION':PATCH,'HAUS_HAUSSTAND':'MAIN01-A01',
            'HAUS_MONTAGESTATUS':('HOEHENBEZUG_OFFEN_QUELLHOEHEN_UNVERAENDERT' if offset is None
                                  else 'Z_VERSATZ_NACH_NUTZERBELEG_KEIN_EIGENER_NACHWEIS'),
            'HAUS_BESTAND_BESTAETIGT':'NEIN','HAUS_STATIK_FREIGEGEBEN':'NEIN',
            'HAUS_DGM_PUNKT85':'URSACHE_WEITER_OFFEN_KEIN_FIX_BEHAUPTET',
            'HAUS_UMGEBUNG_PRUEFUMFANG':environment['surface_validation'],
            'HAUS_PLANLINIEN':'SEPARAT_AUSGEBLENDET_KEINE_BESTAETIGTEN_LEITUNGSTIEFEN'}
        if offset is not None:
            attributes['HAUS_HOEHENQUELLE'] = config['height_connection']['source']
            attributes['HAUS_H_EG_QUELLHOEHE_M'] = config['height_connection']['H_EG_zero_in_source_datum_m']
        for key,value in attributes.items():
            nx._set_user_attribute(master,key,value,'GESAMTPROJEKT')
        checks = e.run.check_master(nx,master,expected)
        nx.prepare_view(master); nx.save(master); records.append(saved_record(final))
        # Saving the project must not rewrite either independently maintained master.
        check_records(house['files']); check_records(environment['files'])
        return {'master':str(final),'files':records,'component_checks':checks,
                'utility_reference_checks':ref_checks,'utility_segments':segment_count,
                'utility_parts':len(groups),'utility_master':str(utility_path),
                'utility_component_hidden':True,'confirmed_utility_depths':0,
                'environment_translation_mm':list(offset or (0,0,0)),
                'height_connection_confirmed_by_user':offset is not None,
                'physical_site_alignment_verified':False,'as_built_verified':False,
                'source_components_not_resaved':True}
