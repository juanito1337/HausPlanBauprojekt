# -*- coding: utf-8 -*-
"""Ein Einstieg fuer Umgebung R09 und Hausgeometrie R06 mit R09a-Quellenmetadaten."""
import datetime
import os
import shutil
import traceback
import uuid
from pathlib import Path
from .core import (PATCH, absolute, read_json, write_json, sha256, settings_checked,
                   placement, validate_job, verify_runtime_files, check_file_records, compare_boxes)
from .nx_adapter import SceneAdapter
from .utilities import load_review, decorate_house_data
from haus2406_r03.haus_runtime import verify_output_paths, path_key


class Log:
    def __init__(self,path):
        self.path=Path(path); self.nx=None
    def __call__(self,text):
        line=datetime.datetime.now().isoformat(timespec='seconds')+' | '+str(text)
        with self.path.open('a',encoding='utf-8') as f:
            f.write(line+'\n')
        try:
            print(line)
        except (OSError,UnicodeError,AttributeError):
            pass  # NX kann ohne stdout laufen. Das Dateiprotokoll ist verpflichtend.
        if self.nx is not None:
            try:
                self.nx.session.ListingWindow.WriteLine(line)
            except Exception:
                pass  # Nur optionaler zweiter Ausgabekanal, keine Geometrieausnahme.


def record_saved(out,path,saved):
    p=absolute(path)
    return dict(saved,relative_file=p.relative_to(absolute(out)).as_posix())


def build_house_copy(base,out,_adapter_factory=None):
    """Eigene Laufkopie: gleiche R06-Geometrie, R09a-Tiefenhinweise als Metadaten."""
    original=base/'basis/Haus_R06'
    runtime=out/'_haus_eingaben'
    runtime.mkdir(exist_ok=False)
    for folder in ('src','data'):
        shutil.copytree(original/folder,runtime/folder,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    review, depth_summary = load_review(base)
    raw_house=read_json(runtime/'data/haus.json')
    raw_house = decorate_house_data(raw_house, review)
    from .video import enrich_if_present
    raw_house = enrich_if_present(base, raw_house)
    write_json(runtime/'data/haus.json', raw_house)
    if raw_house.get('video_revision'):
        write_json(runtime/'data/VIDEO_AENDERUNGEN_R10.json', raw_house['video_revision'])
    if raw_house.get('window_review_revision'):
        write_json(runtime/'data/FENSTER_AENDERUNGEN_R11.json', raw_house['window_review_revision'])
    write_json(runtime/'data/LEITUNGSTIEFEN_PRUEFUNG_R09a.json',review)
    cfg=read_json(runtime/'data/einstellungen.json')
    cfg['output_root']=str(out/'haus')
    # Den bisherigen expliziten Naeherungsdialog NICHT umgehen.
    write_json(runtime/'data/einstellungen.json',cfg)
    from haus2406_r03.haus_run import run_house,check_saved_house
    state=run_house(runtime, _adapter_factory=_adapter_factory)
    if state.get('status')!='NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT':
        raise RuntimeError('Haus R06 nicht erfolgreich gespeichert; keine Nachpruefung.')
    verified=check_saved_house(runtime, _adapter_factory=_adapter_factory)
    if verified.get('status')!='DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN':
        raise RuntimeError('Haus-Nachpruefung fehlgeschlagen.')
    return state,verified


def check_master(nx,master,expected):
    children=list(master.ComponentAssembly.RootComponent.GetChildren())
    if len(children)!=len(expected):
        raise RuntimeError('Baugruppenstruktur unvollstaendig/ueberzaehlig: '+master.FullPath)
    paths={path_key(path):(name,path,offset) for name,path,offset in expected}
    seen=set(); checks=[]
    for child in children:
        key=path_key(child.Prototype.FullPath) if child.Prototype is not None else ''
        if key not in paths or key in seen:
            raise RuntimeError('Doppelte/falsche Komponente in '+master.FullPath)
        seen.add(key)
        name,path,offset=paths[key]
        if child.Name!=name:
            raise RuntimeError('Komponentenname stimmt nicht: '+child.Name)
        checks.append(nx.verify_component(child,path,offset))
    return checks


def preflight_open_parts(nx,job,build_house,house_part_files=()):
    names={p['part_file'].casefold() for p in job['parts']}
    names.update({'11_KARTENREFERENZEN_R09.prt'.casefold(),'UMGEBUNG_MASTER_R09.prt'.casefold(),
                  'GESAMTMODELL_R09.prt'.casefold()})
    if build_house:
        names.add('haus_master.prt')
        names.update(n.casefold() for n in house_part_files)
    conflicts=[str(p.FullPath) for p in nx.session.Parts if Path(str(p.FullPath)).name.casefold() in names]
    if conflicts:
        raise RuntimeError('Gleichnamige Projektteile sind bereits geoeffnet. Eigene Arbeit speichern, '
                           'diese Teile manuell schliessen und neu starten:\n'+'\n'.join(conflicts))


def run_project(base,config=None,adapter_factory=SceneAdapter,house_builder=build_house_copy,notify=True):
    base=absolute(base)
    cfg=settings_checked(read_json(base/'data/EINSTELLUNGEN_R09.json') if config is None else config)
    job=read_json(base/'data/IMPORTAUFTRAG_R09.json')
    counts=validate_job(base,job)
    from .vegetation_review import selected_job
    job, selection = selected_job(base, job)
    counts = dict(counts, parts=len(job['parts']), sheets=job['total_sheets'])
    fingerprint_count=verify_runtime_files(base)
    review, depth_summary=load_review(base)
    house_part_files=[]
    if cfg['build_house']:
        from haus2406_r03.haus_compile import compile_house
        house_data=read_json(base/'basis/Haus_R06/data/haus.json')
        house_part_files=[p['file'] for p in compile_house(house_data,True)['parts']]
    root=Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    root=absolute(root if root.is_absolute() else base/root)
    root.mkdir(parents=True,exist_ok=True)
    out=root/('R09_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    out.mkdir(exist_ok=False)
    env_dir=out/'umgebung'; env_dir.mkdir()
    log=Log(out/'laufprotokoll_R09.txt'); nx=None
    state={'schema':'R09_RUN_V1','patch':PATCH,'status':'START','phase':'VORPRUEFUNG',
           'output_directory':str(out),'started':datetime.datetime.now().isoformat(),
           'files':[],'imports':[],'counts':counts,'verified_runtime_files':fingerprint_count,
           'house_geometry_changed':False,'measured_house_alignment':False,
           'technical_as_built_approval':False,'settings':cfg,
           'limits':['Keine komplette Bestandsvermessung.',
                     'Leitungstiefen weiterhin unbekannt.',
                     'Haus R06: zehn Ueberschneidungspaare und zwei blockierte Oeffnungen bleiben offen.',
                     'Offene Vegetationsoberflaechen, keine Staemme oder Wurzeln.',
                     'bDOM 2023 / Luftbild 2025, DGM-Bezugsnachweis noch offen.']}
    state['vegetation_video_selection'] = selection
    state['utility_depth_review']=depth_summary
    write_json(out/'LEITUNGSTIEFEN_PRUEFUNG_R09a.json',review)
    write_json(out/'manifest_R09.json',state)
    write_json(out/'EINSTELLUNGEN_VERWENDET_R09.json',cfg)
    try:
        nx=adapter_factory(log); log.nx=nx
        state['nx_runtime'] = nx.runtime_information()
        write_json(out/'manifest_R09.json', state)
        preflight_open_parts(nx,job,cfg['build_house'],house_part_files)
        nx.preflight_importer()
        definition=nx.settings_file(base,cfg['step_settings_file'])
        state['step_settings_file']=str(definition)
        state['step_settings_sha256']=sha256(definition)
        names=[p['part_file'] for p in job['parts']]+['11_KARTENREFERENZEN_R09.prt','UMGEBUNG_MASTER_R09.prt']
        verify_output_paths(env_dir,names)
        state['phase']='NX_STEP_IMPORT_FUNKTIONSTEST'; write_json(out/'manifest_R09.json',state)
        log('R09: realer STEP-Importtest in dieser NX-Sitzung, vor dem Hauptlauf.')
        smoke_dir=out/'funktionstest'; smoke_dir.mkdir()
        smoke=job['smoke_test']; unique='TEST_IMPORT_R09_'+uuid.uuid4().hex[:8]+'.prt'
        sm_part,sm_save,sm_check=nx.import_surface_part(smoke_dir,base/smoke['step_file'],smoke,definition,name=unique)
        sm_master=nx.new_part(smoke_dir/('TEST_MASTER_R09_'+uuid.uuid4().hex[:8]+'.prt'),'R09_TEST_MASTER')
        # Nicht-null-Verschiebung testen; veraendert NIE die Quellkoerper.
        sm_comp=nx.add_at(sm_master,smoke_dir/unique,'TEST_IMPORT_TRANSLATION',(0,0,-1234.5))
        sm_check['placement_test']=nx.verify_component(sm_comp,smoke_dir/unique,(0,0,-1234.5))
        nx.save(sm_master)
        sm_check['status']='NX_IMPORT_UND_KOMPONENTENTEST_BESTANDEN'
        state['smoke_test']=sm_check; write_json(out/'funktionstest_R09.json',sm_check)
        state['phase']='UMGEBUNG'; write_json(out/'manifest_R09.json',state)
        parts={}; expected=[]
        for spec in job['parts']:
            state['current_object']=spec['id']; write_json(out/'manifest_R09.json',state)
            log('Importiere %s: %d offene Flaechen' % (spec['id'],spec['expected_sheets']))
            part,saved,check=nx.import_surface_part(env_dir,base/spec['step_file'],spec,definition)
            parts[spec['id']]=part
            state['files'].append(record_saved(out,env_dir/spec['part_file'],saved));state['imports'].append(check)
            expected.append((spec['id'],env_dir/spec['part_file'],(0,0,0)))
        refs=nx.new_part(env_dir/'11_KARTENREFERENZEN_R09.prt','R09_KARTENREFERENZEN')
        segment_count=0
        for ref in job['reference_lines']:
            lines=nx.lines(refs,ref['points_mm'],'R09_'+ref['id'],closed=False,blank=False)
            for line in lines:
                line.Layer=1; line.Unblank()
            segment_count+=len(lines)
        if segment_count!=job['line_segment_count']:
            raise RuntimeError('Kartenliniensegmente fehlen.')
        nx._set_user_attribute(refs,'HAUS_Z_BEZUG','DARSTELLUNG_UEBER_DGM_KEINE_GRENZPUNKTHOEHEN','KARTENREFERENZEN')
        state['files'].append(record_saved(out,env_dir/'11_KARTENREFERENZEN_R09.prt',nx.save(refs)))
        state['reference_segments']=segment_count
        expected.append(('KARTENREFERENZEN',env_dir/'11_KARTENREFERENZEN_R09.prt',(0,0,0)))
        master=nx.new_part(env_dir/'UMGEBUNG_MASTER_R09.prt','UMGEBUNG_R09')
        for ident,path,offset in expected:
            component=nx.add_at(master,path,ident,offset)
            if ident=='F01':
                component.Blank()  # deckungsgleiche Bodenreferenz, sonst Z-Fighting
        for k,v in {'HAUS_REVISION':PATCH,'HAUS_Z_BEZUG':'QUELLHOEHEN_MM_KEIN_EG_OFFSET',
                    'HAUS_HOEHENANSCHLUSS':'OFFEN_BIS_QUELLE_BESTAETIGT',
                    'HAUS_F01_ANZEIGE':'AUSGEBLENDET_WEGEN_UEBERLAGERUNG_MIT_GELAENDE'}.items():
            nx._set_user_attribute(master,k,v,'UMGEBUNG')
        nx.prepare_view(master)
        state['environment_master']=(env_dir/'UMGEBUNG_MASTER_R09.prt').relative_to(out).as_posix()
        state['component_checks']=check_master(nx,master,expected)
        state['files'].append(record_saved(out,env_dir/'UMGEBUNG_MASTER_R09.prt',nx.save(master)))
        state['environment_status']='ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT'
        state['surface_validation']=getattr(nx,'validation_level','INTENSIV')
        state['surface_area_check_performed']=state['surface_validation']=='INTENSIV'
        state['surface_full_reference_check_performed']=state['surface_validation']=='INTENSIV'
        state['status']='UMGEBUNG_ERZEUGT';state.pop('current_object',None)
        write_json(out/'manifest_R09.json',state)
        if cfg['build_house']:
            state['phase']='HAUS_R06_NEUAUFBAU';write_json(out/'manifest_R09.json',state)
            log('Umgebung gespeichert. Jetzt Hausbasis R06 mit optionalem R10-Videoabgleich und eigenem Naeherungsdialog.')
            house,verification=house_builder(base,out)
            house_out=absolute(house['output_directory'])
            house_path=house_out/'HAUS_MASTER.prt'
            state['house']={'master':house_path.relative_to(out).as_posix(),
                            'mode':house['mode'],'verification_status':verification['status'],
                            'built_solids':house['built_solids'],
                            'geometry_revision':house.get('geometry_revision','R06_UNVERAENDERT'),'as_built_verified':False,
                            'metadata_revision':'R09a_TIEFENHINWEISE_KEINE_TIEFENZUWEISUNG'}
            for saved in house['files']:
                state['files'].append(record_saved(out,house_out/saved['file'],saved))
            offset=placement(cfg)
            if offset is not None and house['mode']=='PRUEFMODELL_MIT_NAEHERUNGEN':
                state['phase']='HOEHENANSCHLUSS_NACH_NUTZERANGABE';write_json(out/'manifest_R09.json',state)
                combined=nx.new_part(out/'GESAMTMODELL_R09.prt','GESAMTMODELL_R09')
                assembly=[('HAUS_R06',house_path,(0,0,0)),('UMGEBUNG_R09',env_dir/'UMGEBUNG_MASTER_R09.prt',offset)]
                for name,path,pos in assembly:
                    nx.add_at(combined,path,name,pos)
                nx._set_user_attribute(combined,'HAUS_HOEHENQUELLE',cfg['height_connection']['source'],'HOEHENANSCHLUSS')
                nx._set_user_attribute(combined,'HAUS_H_EG_QUELLHOEHE_M',cfg['height_connection']['H_EG_zero_in_source_datum_m'],'HOEHENANSCHLUSS')
                nx._set_user_attribute(combined,'HAUS_TRANSFORMATION','UMGEBUNG_NUR_Z_TRANSLATION_KEINE_SKALIERUNG','HOEHENANSCHLUSS')
                nx.prepare_view(combined)
                state['combined_component_checks']=check_master(nx,combined,assembly)
                state['files'].append(record_saved(out,out/'GESAMTMODELL_R09.prt',nx.save(combined)))
                state['combined_master']='GESAMTMODELL_R09.prt'
                state['combined_height_connection']='NUTZERANGABE_KEIN_EIGENER_VERMESSUNGSNACHWEIS'
                final_display=combined
            else:
                state['combined_master']=None
                state['combined_height_connection']='OFFEN_KEINE_UNBELEGTE_MONTAGE'
                final_display=master
        else:
            state['house']={'mode':'NICHT_ERZEUGT_LAUT_EINSTELLUNG'}
            state['combined_master']=None
            final_display=master
        state['phase']='ABSCHLUSSPRUEFUNG'
        verify_runtime_files(base)  # Veraenderungen waehrend des Laufs nicht uebergehen.
        for spec in job['parts']:
            old_check=next(x for x in state['imports'] if x['id']==spec['id'])
            actual_faces=sum(len(b.GetFaces()) for b in parts[spec['id']].Bodies)
            if actual_faces != old_check['faces']:
                raise RuntimeError('Face-Anzahl nach Importpruefung veraendert: '+spec['id'])
            actual=[nx.surface_box(b) for b in parts[spec['id']].Bodies]
            compare_boxes(spec['face_bounding_boxes_mm'],actual)
        state['total_imported_nx_faces']=sum(x['faces'] for x in state['imports'])
        state['total_checked_source_points']=sum(x['checked_source_points'] for x in state['imports'])
        state['checked_file_count']=check_file_records(out,state['files'])
        state['warnings']=list(nx.warnings)
        state['status']='R09_ERZEUGT_MIT_NUTZERHOEHENANSCHLUSS' if state.get('combined_master') else 'R09_ERZEUGT_BEZUGSSYSTEME_GETRENNT'
        state['phase']='ABGESCHLOSSEN'
        state['finished']=datetime.datetime.now().isoformat()
        state['nx_runtime_status']='DIESER_NX_LAUF_ABGESCHLOSSEN; KEIN_KALTER_WIEDEROEFFNUNGSTEST'
        nx.set_display(final_display);nx.fit(final_display)
        # Kein Speichern nach den Datei-Pruefsummen; Ansichtsaenderung ggf. spaeter manuell speichern.
        write_json(out/'manifest_R09.json',state)
        write_json(base/'LETZTER_R09_LAUF.json',{'directory':str(out),'environment_master':str(env_dir/'UMGEBUNG_MASTER_R09.prt'),
                   'combined_master':str(out/state['combined_master']) if state.get('combined_master') else None})
        log('R09 abgeschlossen: '+state['status'])
        text=('R11: %d Quell-Flaechenkoerper in %d Quelldaten-Komponenten + Kartenreferenzen gespeichert.\n' % (job['total_sheets'],len(job['parts'])))+str(final_display.FullPath)
        if not state.get('combined_master'):
            text+='\n\nKein bestaetigter Hoehenanschluss: Haus und Umgebung bleiben getrennte Master. Nicht blind gemeinsam am Ursprung einfuegen.'
        if cfg['build_house']:
            text+='\nHausmodus: '+state['house']['mode']
        text+='\n\nLeitungstiefen/Tragwerksluecken bleiben offen. Pruefprotokoll: '+str(out/'manifest_R09.json')
        if notify:
            nx.safe_message(text)
        return state
    except Exception as ex:
        state['status']='R09_ABGEBROCHEN_TEILERGEBNIS';state['error']=str(ex);state['traceback']=traceback.format_exc()
        state['nx_operation']=nx.operation if nx is not None else 'VOR_NX'
        try:
            write_json(out/'manifest_R09.json',state)
        except Exception as log_ex:
            ex.r09_log_failure=str(log_ex)
        if nx is not None:
            ex.nx_runtime = state.get('nx_runtime', {})
        ex.r09_context={'output_directory':str(out),'phase':state['phase'],'operation':state['nx_operation']}
        if nx is not None:
            nx.restore_display_after_failure()
        raise
