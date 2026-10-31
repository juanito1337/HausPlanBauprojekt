# -*- coding: utf-8 -*-
"""One automated terrain-only run. No manual source selection and no house run.
Uses the packaged DGM spec, the standard STEP adapter and the G01e direct surface-coordinate checker.
It never writes a house/environment completion pointer for this isolated part.
"""
import datetime
from pathlib import Path
import traceback
import uuid
from . import PATCH
from .core import (absolute,config_checked,read_json,write_json,verify_package,
                   saved_record,child_exception_context,CONFIG_FILE)
from .terrain_audit import REPORT_NAME
from .terrain_uv import make_uv_audited_adapter as make_audited_adapter


def run_terrain_only(base,config=None,backend=None,verify=True):
    base=absolute(base)
    cfg=config_checked(read_json(base/CONFIG_FILE) if config is None else config)
    root=Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    root=absolute(root if root.is_absolute() else base/root)
    root.mkdir(parents=True,exist_ok=True)
    token=uuid.uuid4().hex[:8]
    out=root/('G01e_GELAENDE_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+token)
    out.mkdir(exist_ok=False)
    state={'patch':PATCH,'mode':'TERRAIN','status':'GESTARTET',
           'output_directory':str(out),'house':None,'environment':None,'project':None,
           'terrain':None,'phase':'QUELLE_UND_PROGRAMM_PRUEFEN',
           'only_new_terrain_part':True,'house_not_rebuilt':True,
           'no_environment_completion_pointer_written':True,
           'no_import_already_existing_prt_needed':True,'physical_site_alignment_verified':False,
           'terrain_log':str(out/REPORT_NAME)}
    monitor=None
    def checkpoint(phase):
        state['phase']=phase
        write_json(out/'manifest_G01.json',state)
        write_json(out/'LAUFSTATUS_G01e.json',{'patch':PATCH,'status':state['status'],
            'phase':phase,'updated_at':datetime.datetime.now().isoformat(),
            'terrain_log':state['terrain_log']})
    checkpoint(state['phase'])
    try:
        if verify:state['package_check']=verify_package(base,'ENVIRONMENT')
        if backend is None:
            from .nx_backend import NXBackend
            backend=NXBackend(base)
        e=backend.environment_modules();source_root=base/'umgebung'
        if verify:e.core.verify_runtime_files(source_root)
        job=read_json(source_root/'data/IMPORTAUFTRAG_R09.json')
        e.core.validate_job(source_root,job)
        specs=[p for p in job['parts'] if p['id']=='DGM']
        if len(specs)!=1:raise ValueError('Genau eine DGM-Quelldefinition im Paket erwartet.')
        spec=specs[0]
        state['source_file']=str(absolute(source_root/spec['step_file']))
        state['source_sha256']=spec['sha256']
        checkpoint('NX_ADAPTER_INITIALISIEREN')
        policy=read_json(source_root/'data/LAUFZEIT_R11a.json')
        policy['surface_validation']=cfg['surface_validation'];e.perf.policy_checked(policy)
        monitor=e.perf.RunMonitor(out)
        logger=e.run.Log(out/'laufprotokoll_G01e.txt')
        cls=make_audited_adapter(e.perf.FastSceneAdapter,base/'data/DGM_REFERENZPUNKTE_G01a.json')
        nx=cls(logger,monitor,policy);logger.nx=nx
        nx.preflight_importer()
        configured=cfg['step_settings_file']
        if configured and not Path(configured).is_absolute():configured=str(absolute(base/configured))
        definition=nx.settings_file(source_root,configured)
        state['step_settings_file']=str(definition)
        # Unique intended part name: no need to close or overwrite an old DGM.
        name='01_GELAENDE_G01e_'+token+'.prt'
        if any(Path(str(p.FullPath).replace('\\','/')).name.casefold()==name.casefold()
               for p in nx.session.Parts):
            raise RuntimeError('Zufaellige neue Diagnosekennung ist bereits geladen; keine Datei ueberschreiben.')
        checkpoint('GELAENDE_IMPORTIEREN_SICHERN_UND_PRUEFEN')
        part,saved,check=nx.import_surface_part(out,source_root/spec['step_file'],spec,definition,name)
        state['terrain']={'file':saved_record(part.FullPath),'check':check,
                          'geometry_release':False,'selected_checks_passed':True}
        # Do not call a full house or vegetation workflow and do not assemble old files.
        e.nx.SceneAdapter.prepare_view(nx,part)
        state['displayed_master']=str(part.FullPath)
        state['status']='ANGEFORDERTER_ABLAUF_ABGESCHLOSSEN_FACHLICH_OFFEN'
        if verify:state['package_check_at_end']=verify_package(base,'ENVIRONMENT')
        monitor.finish('GELAENDE_AUSGEWAEHLTE_PRUEFUNG_ABGESCHLOSSEN')
        checkpoint('ABGESCHLOSSEN')
        return state
    except Exception as error:
        state.update(status='ABGEBROCHEN_KEIN_GESAMTERFOLG',error=str(error),
                     traceback=traceback.format_exc(),nested_diagnostics=child_exception_context(error))
        error.gesamt_g01_context={'output_directory':str(out),'phase':state['phase'],
            'manifest':str(out/'manifest_G01.json'),'saved_house':None,'saved_environment':None,
            'terrain_report':str(out/REPORT_NAME),'house_not_rebuilt':True}
        try:
            checkpoint(state['phase'])
            if monitor is not None:monitor.finish('ABGEBROCHEN_DIAGNOSE_KEINE_FREIGABE')
        except Exception as second:
            error.gesamt_g01_logging_error=str(second)
        raise
