# -*- coding: utf-8 -*-
"""G02 creates a new height-aligned project, never edits the old project master.
Build methods and terrain checks are inherited unchanged from G01e.
"""
import copy
import datetime
import json
from pathlib import Path
import os
from . import PATCH
from .loading import PartLoader
from .height import component_placements, verify_placement_rows
from gesamt.nx_backend import NXBackend
from gesamt.core import absolute, read_json, write_json, saved_record, check_records

FIELDS=('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz')

def path_key(path):
    return os.path.normcase(os.path.abspath(os.fspath(path))).casefold()

def modified_flag(part):
    """Never mistake a bound method for a Boolean; never reset the NX dirty flag."""
    flag=getattr(part,'IsModified',None)
    if callable(flag):flag=flag()
    if type(flag) is bool:return flag
    if type(flag) is int and flag in (0,1):return bool(flag)
    raise RuntimeError('NX-Aenderungsstatus nicht eindeutig lesbar: '+str(part.FullPath))

def displayed_manifest(session):
    # Only FullPath is needed. We intentionally do NOT read/save the old tree,
    # its geometry, its positions or its IsModified flag. It is not a source part.
    part=session.Parts.Display
    if part is None:
        raise RuntimeError('Fuer 05 die bisherige Gesamtbaugruppe anzeigen; alternativ 00 fuer einen Neuaufbau.')
    path=absolute(part.FullPath)
    for name in ('manifest_G02.json','manifest_G01.json'):
        manifest=path.parent/name
        if manifest.is_file():return manifest, str(path)
    raise FileNotFoundError('Kein gespeichertes G01e/G02-Laufmanifest neben der angezeigten Gesamtbaugruppe. '
                            'Die urspruengliche Projekt-Masterdatei des erfolgreichen Laufs anzeigen.')

class NXBackendG02(NXBackend):
    def __init__(self,base,session_provider=None):
        super().__init__(base,session_provider)
        self.reusing=False
        self.audit={'source_parts_resaved':False,'old_project_master_read_for_geometry':False,
                    'old_project_master_modified_or_saved':False,'dirty_source_parts_ignored':False,
                    'status':'START','loads':[],'source_state_checks':[]}

    def select_previous_manifest(self):
        return displayed_manifest(self.session())

    def confirm_height(self,plan,reuse=False):
        import NXOpen
        text=('G02: Haus und gesamte Umgebung auf EINEM Hoehenbezug montieren.\n\n'
              'Modus: '+plan['status']+'\n'
              'Anker X/Y: %.1f / %.1f mm\nDGM am Anker: %.4f m\n'
              'Ziel relativ EG: %.3f m\nUmgebung: Z-Versatz %.3f mm\n\n' %
              (*plan['anchor']['xy_mm'],plan['anchor']['source_z_mm']/1000,
               plan['target_ground_z_mm']/1000,plan['translation_mm'][2]))
        if plan['mode']=='PLAN_ANNAHME':
            text+=('Die -0,30-m-Kote aus Schnitt A-A wird auf einen gewaehlten Punkt uebertragen. '
                   'Das ist eine UNVERMESSENE PLANANNAHME, keine bestaetigte heutige Anschlusskote.\n\n')
        else:
            text+='Nutzerangaben und gemeinsamer Hoehenbezug werden nicht unabhaengig vermessen.\n\n'
        if reuse:
            text+=('Nur gespeicherte, dateigepruefte Haus-/Umgebungskomponenten des vorhandenen Laufmanifests '
                   'werden referenziert. Aenderungen an der alten PROJEKT-Masterdatei werden NICHT uebernommen. '
                   'Die alte Projektdatei wird weder gespeichert noch geschlossen oder ueberschrieben.\n\n')
        else:
            text+='Neuer Gesamtaufbau. Manuelle Aenderungen aus aelteren Parts werden nicht uebernommen.\n\n'
        text+='Diesen dokumentierten Arbeitsstand erstellen?'
        return NXOpen.UI.GetUI().NXMessageBox.Show('G02 - Hoehenbezug bestaetigen',
                    NXOpen.NXMessageBox.DialogType.Question,text)==1

    def check_open_reuse_sources(self, house, environment):
        self.reusing=True
        records=house['files']+environment['files']
        check_records(house['files']);check_records(environment['files'])
        allowed={path_key(r['path']) for r in records if Path(r['path']).suffix.lower()=='.prt'}
        # A dirty outer master is NOT ignored as if it were clean. It is excluded
        # because the new tree is reconstructed from the saved manifest instead.
        for part in self.session().Parts:
            if path_key(part.FullPath) in allowed:
                # Read first when possible, before any later load operation.
                try: flag=modified_flag(part)
                except Exception as error:
                    self.audit['source_state_checks'].append({'path':str(part.FullPath),
                        'when':'BEFORE_LOAD','flag':None,'read_error':str(error)})
                    continue # mandatory full-load check follows when referencing
                self.audit['source_state_checks'].append({'path':str(part.FullPath),
                    'when':'BEFORE_LOAD','flag':flag})
                if flag:
                    raise RuntimeError('Ungespeicherte Aenderung an einer QUELLKOMPONENTE: '+str(part.FullPath)+
                        '. Keine automatische Speicherung/Verwerfung. Die alte Projekt-Masterdatei allein blockiert G02 nicht.')

    def assemble_aligned(self,out,house,environment,plan):
        e=self.environment_modules();out=absolute(out)
        token=out.name.split('_')[-1]
        log=e.run.Log(out/'PROJEKT_MONTAGE_G02.log')
        eventpath=out/'LADEVORGAENGE_G02.jsonl'
        auditpath=out/'MONTAGEPRUEFUNG_G02.json'
        def event(value):
            record=dict(value,time=datetime.datetime.now().isoformat())
            with eventpath.open('a',encoding='utf-8') as f:
                json.dump(record,f,ensure_ascii=False,allow_nan=False);f.write('\n')
            self.audit['last_load_event']=record
            write_json(auditpath,self.audit)
        loader=PartLoader(self.session(),self.audit,event)
        backend=self
        class ReadyAdapter(e.nx.SceneAdapter):
            def verify_component(self,comp,path,translation):
                loader.ensure_part(comp.Prototype,'G02 Referenz vor Einheiten-/Positionslesung')
                super().verify_component(comp,path,translation)
                pos,rot=comp.GetPosition()
                return {'component':comp.Name,'file':str(path),
                        'translation_mm':[float(pos.X),float(pos.Y),float(pos.Z)],
                        'rotation':[float(getattr(rot,k)) for k in FIELDS],
                        'identity_rotation':True,'values_read_back_from_NX':True}
        nx=ReadyAdapter(log);log.nx=nx
        nx._attribute_update_option=getattr(nx.N.Update.Option,'Later',nx.N.Update.Option.Now)
        records=[]
        # Existing utility source lines retain their own explicit drawing plane.
        data=read_json(self.base/'haus/data/haus.json')
        review,_=e.utilities.load_review(self.base/'umgebung')
        data=e.utilities.decorate_house_data(data,review)
        data['site']=copy.deepcopy(data['site']);data['site']['enabled']=True
        refs={'parts':[],'coverage':[],'warnings':[]};e.site.apply_site(data,refs)
        groups=[p for p in refs['parts'] if p['id']!='GRUNDSTUECK']
        refdir=out/'planreferenzen';refdir.mkdir(exist_ok=False)
        expected_refs=[];segment_count=0
        for spec in groups:
            path=refdir/(Path(spec['file']).stem+'_G02_'+token+'.prt')
            part=nx.new_part(path,spec['id'])
            for line in spec['references']:
                objs=nx.lines(part,line['points3d'],line['id'],closed=line['closed'],blank=False,meta=line)
                expected_count=len(line['points3d']) if line['closed'] else len(line['points3d'])-1
                if len(objs)!=expected_count:raise RuntimeError('Leitungsreferenz unvollstaendig: '+line['id'])
                for obj in objs:obj.Layer=1;obj.Unblank()
                segment_count+=len(objs)
            for k,v in {'HAUS_GEOMETRIEART':'HISTORISCHE_PLANLINIEN_KEIN_LEITUNGSROHR',
                'HAUS_VERLEGETIEFEN':'UNBEKANNT','HAUS_Z_BEZUG':'Z0_NUR_ZEICHENEBENE_KEINE_GELAENDEHOEHE',
                'HAUS_NUTZUNG_ERDARBEITEN':'NICHT_FREIGEGEBEN','HAUS_REVISION':PATCH}.items():
                nx._set_user_attribute(part,k,v,'PLANREFERENZEN')
            nx.save(part);records.append(saved_record(path));expected_refs.append((spec['id'],path,(0,0,0)))
        utility_path=refdir/('LEITUNGSPLAN_MASTER_G02_'+token+'.prt')
        utility=nx.new_part(utility_path,'LEITUNGSPLANREFERENZEN_G02')
        for name,path,pos in expected_refs:nx.add_at(utility,path,name,pos)
        refchecks=e.run.check_master(nx,utility,expected_refs)
        nx._set_user_attribute(utility,'HAUS_VERLEGETIEFEN','UNBEKANNT_KEINE_PHYSISCHE_MONTAGE','PLANREFERENZEN')
        nx.save(utility);records.append(saved_record(utility_path))
        label='PLANBEZUG' if plan['mode']=='PLAN_ANNAHME' else 'NUTZERBEZUG'
        final=out/('PROJEKT_MASTER_G02_'+label+'_'+token+'.prt')
        master=nx.new_part(final,'PROJEKT_MAIN01_A01_G02')
        expected=component_placements(house['master'],environment['master'],utility_path,plan)
        comps=[]
        for name,path,pos in expected:
            comp=nx.add_at(master,Path(path),name,pos);comps.append(comp)
            if path_key(path)==path_key(utility_path):comp.Blank()
            else:comp.Unblank()
        # Load/check the existing source trees after they have been referenced,
        # but before saving the NEW master. Never save a source through it.
        if self.reusing:
            self._check_source_trees(loader,comps[:2],house,environment)
        attributes={'HAUS_REVISION':PATCH,'HAUS_HAUSSTAND':'MAIN01-A01',
            'HAUS_MONTAGESTATUS':plan['status'],'HAUS_HOEHENQUELLE':plan['source'],
            'HAUS_UMGEBUNG_DZ_MM':format(plan['translation_mm'][2],'.12g'),
            'HAUS_ANCHOR_XY_MM':str(plan['anchor']['xy_mm']),
            'HAUS_ANCHOR_Z_REL_EG_MM':str(plan['target_ground_z_mm']),
            'HAUS_HOEHENANSCHLUSS_VERMESSEN':'NEIN',
            'HAUS_BESTAND_BESTAETIGT':'NEIN','HAUS_STATIK_FREIGEGEBEN':'NEIN',
            'HAUS_UMGEBUNG_PRUEFUMFANG':environment['surface_validation'],
            'HAUS_PLANLINIEN':'SEPARAT_AUSGEBLENDET_KEINE_BESTAETIGTEN_LEITUNGSTIEFEN'}
        for k,v in attributes.items():nx._set_user_attribute(master,k,v,'GESAMTPROJEKT_G02')
        checked=e.run.check_master(nx,master,expected)
        # Component enumeration order is not guaranteed; map by full source path.
        bypath={path_key(row['file']):row for row in checked}
        actual=[bypath[path_key(path)] for _,path,_ in expected]
        heightcheck=verify_placement_rows(actual,plan)
        self.audit.update(status='MONTAGE_GEPRUEFT_VOR_SPEICHERN',actual_components=actual,
                          height_check=heightcheck,source_data_verified_by_saved_hashes=True,
                          source_tree_reused_without_reading_old_master=True)
        write_json(auditpath,self.audit)
        nx.prepare_view(master);nx.save(master)
        # Read back again after the update/save, not just prior to it.
        checked_after=e.run.check_master(nx,master,expected)
        bypath={path_key(row['file']):row for row in checked_after}
        after=[bypath[path_key(path)] for _,path,_ in expected]
        height_after=verify_placement_rows(after,plan)
        check_records(house['files']);check_records(environment['files'])
        self.audit.update(status='NEUE_MONTAGE_GESPEICHERT_POSITIONEN_RUECKGELESEN',
                          actual_components_after_save=after,height_check_after_save=height_after,
                          output_master=str(final),source_files_unchanged=True)
        write_json(auditpath,self.audit)
        records.extend([saved_record(final),saved_record(auditpath)])
        return {'master':str(final),'files':records,'component_checks':after,
                'utility_reference_checks':refchecks,'utility_segments':segment_count,
                'utility_parts':len(groups),'utility_master':str(utility_path),
                'utility_component_hidden':True,'confirmed_utility_depths':0,
                'environment_translation_mm':list(plan['translation_mm']),
                'height_plan':plan,'height_check':height_after,'height_mounted':True,
                'physical_site_alignment_verified':False,'as_built_verified':False,
                'source_components_not_resaved':True,'old_project_master_not_used':True,
                'audit':str(auditpath)}

    def _check_source_trees(self,loader,components,house,environment):
        allowed={path_key(r['path']) for result in (house,environment) for r in result['files']
                 if Path(r['path']).suffix.lower()=='.prt'}
        seen=set()
        def walk(part,stack=()):
            loader.ensure_part(part,'G02 gespeicherte Quellkomponente')
            key=path_key(part.FullPath)
            if key in stack:raise RuntimeError('Zyklische Quellbaugruppe.')
            if key not in allowed:raise RuntimeError('Nicht im gespeicherten Laufmanifest erfasste Komponente: '+str(part.FullPath))
            if key in seen:return
            if len(seen)>2000:raise RuntimeError('Unerwartet grosse Quellbaugruppe.')
            flag=modified_flag(part)
            self.audit['source_state_checks'].append({'path':str(part.FullPath),'when':'AFTER_FULL_LOAD','flag':flag})
            if flag:raise RuntimeError('Quellkomponente nach Volladen ungespeichert geaendert: '+str(part.FullPath)+
                                       '. Keine automatische Speicherung/Verwerfung; Details im Ladeprotokoll.')
            seen.add(key)
            for child in loader.children(part,'G02 gespeicherte Unterkomponenten'):
                walk(child.Prototype,stack+(key,))
        for comp in components:walk(comp.Prototype)
        self.audit['source_parts_fully_loaded_and_clean']=len(seen)
