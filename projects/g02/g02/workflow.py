# -*- coding: utf-8 -*-
"""Consolidated orchestration with an explicit, non-surveyed height plan.
No old H01/H01a montage is invoked; old project masters are never inputs for
geometry/positions. REUSE references hash-checked components from a saved run.
"""
import datetime
from pathlib import Path
import traceback
import uuid
from . import PATCH
from .height import height_plan
from gesamt.core import (absolute,read_json,write_json,sha256,relative_file,saved_record,
                         check_records,validate_component_result,config_checked,
                         child_exception_context)

MODES=('ALL','HOUSE','ENVIRONMENT','ASSEMBLE','REUSE')
POINTERS={'house':'LETZTES_HAUS_G02.json','environment':'LETZTE_UMGEBUNG_G02.json'}
ALLOWED_OLD_PATCHES={'MAIN01-A01-G01e-RASTERFLAECHENPRUEFUNG',PATCH}

def verify_delivery(base,mode='ALL'):
    base=absolute(base);lock=read_json(base/'PAKETDATEIEN_SHA256.json')
    if lock.get('schema')!='GESAMT_G01_FILES_V1':raise ValueError('Unbekanntes Paketregister.')
    changes=[];count=0
    editable={'data/EINSTELLUNGEN_GESAMT.json','data/HOEHENANSCHLUSS_G02.json',
              'haus/data/haus.json','haus/data/einstellungen.json'}
    for name,wanted in lock['files'].items():
        if mode=='HOUSE' and name.startswith(('umgebung/','diagnose/')):continue
        if mode=='ENVIRONMENT' and name.startswith('haus/'):continue
        p=relative_file(base,name)
        if not p.is_file():raise FileNotFoundError('Lieferdatei fehlt: '+name)
        actual=sha256(p)
        if actual!=wanted:
            if name not in editable:raise ValueError('Programm-/Quelldatei veraendert: '+name+'. Nicht mit anderen Paketen mischen.')
            changes.append({'file':name,'delivery_sha256':wanted,'actual_sha256':actual})
        count+=1
    return {'count':count,'settings_changes':changes,'NX_test':False}

def prior_results(manifest_path):
    state=read_json(manifest_path)
    if (state.get('patch') not in ALLOWED_OLD_PATCHES or
        state.get('status')!='ANGEFORDERTER_ABLAUF_ABGESCHLOSSEN_FACHLICH_OFFEN' or
        state.get('phase')!='ABGESCHLOSSEN'):
        raise ValueError('Nur ein vollstaendig abgeschlossener G01e-/G02-Lauf darf wiederverwendet werden.')
    results={key:validate_component_result(state.get(key),key) for key in POINTERS}
    if results['house']['mode']!='PRUEFMODELL_MIT_NAEHERUNGEN':
        raise ValueError('Gespeicherter Hausstand ist nur ein Referenzgeruest.')
    return results, saved_record(manifest_path)

def store_result(base,result):
    validate_component_result(result,result['kind'])
    write_json(Path(base)/POINTERS[result['kind']],{'schema':'G02_POINTER_V1','patch':PATCH,'result':result})

def read_result(base,kind):
    p=Path(base)/POINTERS[kind]
    if not p.is_file():raise FileNotFoundError('Noch kein abgeschlossener G02-'+kind+'-Lauf. Fuer bestehendes G01e stattdessen 05 verwenden.')
    data=read_json(p)
    if data.get('schema')!='G02_POINTER_V1' or data.get('patch')!=PATCH:raise ValueError('Falscher Ergebnisverweis.')
    return validate_component_result(data['result'],kind)

def run(base,mode='ALL',backend=None,verify=True,config=None,plan_override=None):
    if mode not in MODES:raise ValueError('Unbekannter G02-Modus: '+str(mode))
    base=absolute(base)
    cfg=config_checked(read_json(base/'data/EINSTELLUNGEN_GESAMT.json') if config is None else config)
    delivery=verify_delivery(base,mode) if verify else {'testing_only':True}
    plan=None
    if mode in ('ALL','ASSEMBLE','REUSE'):
        plan=height_plan(base,cfg) if plan_override is None else plan_override
    if backend is None:
        from .nx_backend import NXBackendG02
        backend=NXBackendG02(base)
    root=Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    if not root.is_absolute():root=base/root
    root=absolute(root);root.mkdir(parents=True,exist_ok=True)
    out=root/('G02_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]);out.mkdir()
    state={'schema':'G02_RUN_V1','patch':PATCH,'mode':mode,'status':'GESTARTET','phase':'VORPRUEFUNG',
           'output_directory':str(out),'house':None,'environment':None,'project':None,
           'height_plan':plan,'configuration':cfg,'delivery_check':delivery,
           'site_alignment_surveyed':False,'structural_approval':False,'as_built_verified':False,
           'old_H01_montage_invoked':False,'user_sources_overwritten':False,
           'all_existing_house_conflicts_fixed':False}
    def checkpoint(phase):
        state['phase']=phase;state['updated_at']=datetime.datetime.now().isoformat()
        write_json(out/'manifest_G02.json',state)
        write_json(out/'LAUFSTATUS_G02.json',{'patch':PATCH,'status':state['status'],'phase':phase,
                'updated_at':state['updated_at'],'saved_house':(state['house'] or {}).get('master'),
                'saved_environment':(state['environment'] or {}).get('master'),
                'saved_project':(state['project'] or {}).get('master')})
    checkpoint('VORPRUEFUNG')
    try:
        previous=None
        if mode=='REUSE':
            checkpoint('GESPEICHERTES_LAUFMANIFEST_LESEN')
            manifest,displayed=backend.select_previous_manifest()
            previous,record=prior_results(manifest)
            state['previous_run_manifest']=record
            state['old_project_path_for_manifest_lookup_only']=displayed
            state['old_project_master_changes_not_carried_over']=True
            backend.check_open_reuse_sources(previous['house'],previous['environment'])
        elif mode=='ASSEMBLE':
            previous={key:read_result(base,key) for key in POINTERS}
            backend.preflight(mode,cfg,previous)
            backend.reusing=True
        else:
            backend.preflight(mode,cfg,None)
        if plan is not None:
            checkpoint('HOEHENANSATZ_BESTAETIGEN')
            accepted=backend.confirm_height(plan,mode in ('REUSE','ASSEMBLE'))
            state['height_plan_explicitly_accepted']=accepted
            if not accepted:
                state['status']='ABGEBROCHEN_DURCH_NUTZER_KEINE_NEUE_MONTAGE'
                checkpoint('ABGEBROCHEN_DURCH_NUTZER')
                return state
            write_json(out/'HOEHENANSCHLUSS_G02.json',plan)
        if previous is not None:state.update(previous)
        if mode in ('ALL','HOUSE'):
            checkpoint('HAUS_MAIN01_A01_ERZEUGEN')
            state['house']=validate_component_result(backend.build_house(out,cfg),'house')
            checkpoint('HAUS_GESPEICHERT');store_result(base,state['house'])
        if mode in ('ALL','ENVIRONMENT'):
            checkpoint('UMGEBUNG_ERZEUGEN_UND_PRUEFEN')
            state['environment']=validate_component_result(backend.build_environment(out,cfg),'environment')
            checkpoint('UMGEBUNG_GESPEICHERT');store_result(base,state['environment'])
        if state['house'] and state['environment']:
            checkpoint('HOEHENBEZOGENE_PROJEKTBAUGRUPPE_ERZEUGEN')
            state['project']=backend.assemble_aligned(out,state['house'],state['environment'],plan)
            check_records(state['project']['files'])
            if state['project'].get('height_mounted') is not True:
                raise RuntimeError('Neue Projektmontage hat keinen geprueften Hoehenversatz.')
            state['height_connection_mode']=plan['status']
        checkpoint('ABSCHLUSSPRUEFUNG')
        for key in POINTERS:
            if state[key]:validate_component_result(state[key],key)
        if state.get('previous_run_manifest'):check_records([state['previous_run_manifest']])
        if verify:state['delivery_check_at_end']=verify_delivery(base,mode)
        result=state['project'] or state['house'] or state['environment']
        state['displayed_master']=result['master']
        state['status']='ANGEFORDERTER_ABLAUF_ABGESCHLOSSEN_FACHLICH_OFFEN'
        checkpoint('ABGESCHLOSSEN')
        write_json(base/'LETZTER_G02_LAUF.json',{'patch':PATCH,'manifest':str(out/'manifest_G02.json'),
                'master':state['displayed_master'],'mode':mode,'height_plan':plan})
        return state
    except Exception as error:
        state.update(status='ABGEBROCHEN_KEIN_GESAMTERFOLG',error=str(error),traceback=traceback.format_exc(),
                     nested_diagnostics=child_exception_context(error),montage_diagnostics=getattr(backend,'audit',{}))
        error.g02_context={'directory':str(out),'manifest':str(out/'manifest_G02.json'),
            'phase':state['phase'],'saved_house':(state['house'] or {}).get('master'),
            'saved_environment':(state['environment'] or {}).get('master')}
        error.g02_montage_diagnostics=state['montage_diagnostics']
        checkpoint(state['phase'])
        raise
