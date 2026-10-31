# -*- coding: utf-8 -*-
"""Automatic DGM import logging. Only standard library + the existing NX adapters.

Measurement signature, query order of the regular checker, source geometry and
0.25 mm acceptance limit remain unchanged. Extra diagnostic queries run AFTER
an error, never select a more favourable answer and never grant a release.
All raw NX results are recorded before numerical validation.
"""
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
from . import PATCH
from .core import absolute, saved_record, write_json
from . import dgm_probe

REPORT_NAME = 'GELAENDE_PROTOKOLL_G01e.json'
EVENT_NAME = 'GELAENDE_PUNKTABFRAGEN_G01e.jsonl'
UNVERIFIED_NAME = 'DGM_UNGEPRUEFTER_IMPORT_G01e.prt'
TRACE_ATTR = 'nx_terrain_audit_g01a'


def json_safe(value):
    """Preserve invalid API returns as text, never replace a failed distance by 0."""
    if value is None or isinstance(value,(str,bool,int)):
        return value
    if isinstance(value,float):
        return value if math.isfinite(value) else {'non_finite_repr':repr(value)}
    if isinstance(value,(list,tuple)):
        return [json_safe(x) for x in value]
    if isinstance(value,dict):
        return {str(k):json_safe(v) for k,v in value.items()}
    return {'type':type(value).__name__,'repr':repr(value)}


def file_info(path):
    p=absolute(path)
    info={'path':str(p),'exists':p.is_file()}
    if info['exists']:
        info.update(saved_record(p))
    return info


class TerrainTrace:
    def __init__(self,out,source,spec,definition):
        self.out=absolute(out)
        self.out.mkdir(parents=True,exist_ok=True)
        self.path=self.out/REPORT_NAME
        self.events=self.out/EVENT_NAME
        # Never overwrite a previous diagnostic, even if called with a reused out.
        for p in (self.path,self.events):
            if p.exists():raise FileExistsError('Diagnoseziel existiert bereits: '+str(p))
        self.events.touch(exist_ok=False)
        self.started=time.perf_counter();self.previous_query=None
        self.data={
            'schema':'G01A_TERRAIN_AUDIT_V1','patch':PATCH,'id':spec['id'],
            'report_file':str(self.path),'events_file':str(self.events),
            'created_at':datetime.datetime.now().isoformat(),
            'source':{'path':str(absolute(source)),'expected_sha256':spec['sha256']},
            'step_definition':{'path':str(absolute(definition))},
            'status':'QUELLDATEIEN_PRUEFEN','geometry_release':False,
            'root_cause_fixed':False,'geometry_changed':False,
            'normal_query_signature':'AskMinimumDist(0, body_tag, 1, fresh_xyz, 0, fresh_zero)',
            'acceptance_limit_mm':0.25,'regular_calls_started':0,'regular_calls_finished':0,
            'recent_regular_queries':[],'unverified_snapshot':None,
            'own_part_checkpoint':None,'final_saved_part':None,
            'source_is_in_package':True,'existing_user_parts_saved_or_closed':False,
            'note':'Protokoll und Diagnose; kein Bestands-/Formnachweis. Keine Auswahl des passendsten Messwerts.'}
        self.write()

    def write(self):
        self.data['updated_at']=datetime.datetime.now().isoformat()
        self.data['elapsed_seconds']=round(time.perf_counter()-self.started,6)
        write_json(self.path,json_safe(self.data))

    def event(self,kind,payload):
        record={'time':datetime.datetime.now().isoformat(),'kind':kind,'data':json_safe(payload)}
        with self.events.open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
            stream.flush()

    def phase(self,name,**fields):
        self.data.update(fields);self.data['status']=name
        self.event('PHASE',{'status':name,**fields});self.write()

    def begin_query(self,body,query,operation):
        self.data['regular_calls_started']+=1
        row={'number':self.data['regular_calls_started'],'operation':str(operation),
             'body_tag':int(body.Tag),'part_file':str(body.OwningPart.FullPath),
             'query_mm':list(query),'previous_query_mm':self.previous_query,
             'guess1_given':1,'guess2_given':0,'guess2_before_mm':[0.,0.,0.],
             'status':'NX_AUFRUF_LAEUFT'}
        self.data['active_query']=row
        self.event('PUNKT_VOR_NX',row)
        # The summary is durable BEFORE each native call. If NX hangs, the last
        # request is still visible. No worker thread and no forced kernel timeout.
        self.write()
        return row

    def finish_query(self,row):
        self.data['regular_calls_finished']+=1
        self.data['last_query']=copy.deepcopy(row)
        self.data['active_query']=None
        self.data['recent_regular_queries'].append(copy.deepcopy(row))
        self.data['recent_regular_queries']=self.data['recent_regular_queries'][-16:]
        self.previous_query=list(row['query_mm'])
        self.event('PUNKT_NACH_NX',row);self.write()

    def fail(self,error):
        self.data.update(status='ABGEBROCHEN_KEINE_GEOMETRIEFREIGABE',
                         error=str(error),exception_type=type(error).__name__,
                         geometry_release=False)
        self.event('ABBRUCH',{'error':str(error),'exception_type':type(error).__name__})
        self.write()
        setattr(error,TRACE_ATTR,copy.deepcopy(self.data))


def make_audited_adapter(base_type,reference_path,*,dgm_validator=None):
    """Wrap the existing FastSceneAdapter, without importing an older house builder."""
    reference_path=absolute(reference_path)

    class AuditedSceneAdapter(base_type):
        def import_surface_part(self,out,source,spec,definition,name=None):
            if spec['id']!='DGM':
                return super().import_surface_part(out,source,spec,definition,name)
            trace=TerrainTrace(out,source,spec,definition)
            self._terrain_trace_g01a=trace
            if dgm_validator is not None:
                trace.data.update(normal_query_signature='EvaluateFace(face, UF_MODL_EVAL, UV); Rand separat an Edge-Tags',
                    validation_method='DGM_EINZEL_ODER_RASTERFLAECHEN_G01e',
                    distance_search_replaced=True, geometry_changed=False,
                    note='Direkte Koordinaten der importierten Traegerflaeche und separat gepruefter Rand. Keine Quellwerte als NX-Rueckgabe.')
                trace.write()
            try:
                trace.data['source'].update(file_info(source))
                trace.data['step_definition'].update(file_info(definition))
                trace.write()
                if not trace.data['source']['exists']:
                    raise FileNotFoundError('Mitgelieferte Gelaendequelle fehlt: '+str(absolute(source)))
                if trace.data['source']['sha256']!=spec['sha256']:
                    raise ValueError('Gelaendequelle weicht von ihrer Pruefsumme ab.')
                if not trace.data['step_definition']['exists']:
                    raise FileNotFoundError('Lokale NX-Importdefinition fehlt: '+str(definition))
                trace.phase('NX_IMPORT_STARTET',
                    planned_part_file=str(absolute(Path(out)/(name or spec['part_file']))),
                    staged_step_file=str(absolute(Path(out)/'_step_quellen'/
                        (Path(name or spec['part_file']).stem+'.step'))),
                    intended_import_settings={'ImportTo':'WorkPart','SewSurfaces':False,
                        'Optimize':False,'SimplifyGeometry':False,'SmoothBSurfaces':False,
                        'ProcessHoldFlag':True,'scale_changed':False})
                result=super().import_surface_part(out,source,spec,definition,name)
                part,saved,check=result
                # Parent has now applied metadata and performed the final save.
                trace.phase('ANGEFORDERTE_PRUEFUNG_BESTANDEN_UND_GESPEICHERT',
                    final_saved_part=file_info(part.FullPath),
                    validation_level=getattr(self,'validation_level','UNBEKANNT'),
                    check_result=check,geometry_release=False,
                    selected_checks_passed=True,additional_diagnostic_used_for_acceptance=False)
                check['terrain_audit_report']=str(trace.path)
                check['terrain_point_log']=str(trace.events)
                check['unverified_import_snapshot']=trace.data['unverified_snapshot']
                self.last_terrain_audit_g01a=copy.deepcopy(trace.data)
                return part,saved,check
            except Exception as error:
                # Keep the original NX/check error; a second logging failure cannot replace it.
                try:trace.fail(error)
                except Exception as secondary:
                    trace.data['logging_failure']=str(secondary)
                    setattr(error,TRACE_ATTR,copy.deepcopy(trace.data))
                raise
            finally:
                self._terrain_trace_g01a=None

        def _save_import_checkpoint(self,part,trace):
            if not any(p.Tag==part.Tag for p in self.created):
                raise RuntimeError('Diagnosespeicherung verweigert: Part nicht in diesem Adapter erzeugt.')
            self.ensure_work(part)
            # Only NEW project-owned parts are saved. Mark as unverified inside NX.
            for key,value in {'HAUS_IMPORTSTATUS':'UNGEPRUEFTER_IMPORT_KEINE_FREIGABE',
                              'HAUS_DIAGNOSE_PATCH':PATCH,
                              'HAUS_INPUT_SHA256':trace.data['source']['sha256']}.items():
                self._set_user_attribute(part,key,value,'DGM_DIAGNOSE')
            trace.phase('UNGEPRUEFTEN_IMPORT_SPEICHERN',part_file=str(part.FullPath))
            self.save(part)
            trace.data['own_part_checkpoint']=file_info(part.FullPath)
            if not trace.data['own_part_checkpoint']['exists']:
                raise RuntimeError('Import-Speicherung lieferte keine tatsaechliche Datei.')
            # Preserve the raw stage separately; not registered as a completed environment.
            folder=trace.out/'diagnose_ungeprueft';folder.mkdir(exist_ok=False)
            target=folder/UNVERIFIED_NAME
            with open(part.FullPath,'rb') as source, target.open('xb') as dest:
                shutil.copyfileobj(source,dest)
            snapshot=file_info(target)
            if snapshot.get('sha256')!=trace.data['own_part_checkpoint'].get('sha256'):
                raise RuntimeError('Diagnosekopie stimmt nicht mit dem gespeicherten Importstand ueberein.')
            snapshot.update(verified_geometry=False,assembly_use_allowed=False,
                            label='UNGEPRUEFTER_IMPORT_KEINE_FREIGABE')
            trace.phase('IMPORT_GESICHERT_NOCH_UNGEPRUEFT',unverified_snapshot=snapshot)

        def verify_surface_geometry(self,part,spec,out):
            trace=getattr(self,'_terrain_trace_g01a',None)
            if trace is None or spec['id']!='DGM':
                return super().verify_surface_geometry(part,spec,out)
            bodies=list(part.Bodies)
            trace.phase('IMPORT_IN_NX_VORHANDEN',part_file=str(part.FullPath),
                staged_source=file_info(trace.data['staged_step_file']),
                body_tags=[int(b.Tag) for b in bodies],
                body_count=len(bodies),face_counts=[len(b.GetFaces()) for b in bodies],
                runtime=self.runtime_information())
            self._save_import_checkpoint(part,trace)
            trace.phase('REGULAERE_GEOMETRIEPRUEFUNG_LAEUFT')
            try:
                if dgm_validator is None:
                    # Retained only for regression/diagnosis of the previous algorithm.
                    result=super().verify_surface_geometry(part,spec,out)
                else:
                    result=dgm_validator(self,part,spec,out,trace)
            except Exception as original:
                saved_operation=self.operation
                trace.data['original_validation_failure']={
                    'error':str(original),'operation':str(saved_operation),
                    'surface_check':copy.deepcopy(getattr(original,'nx_surface_check',None))}
                try:
                    # This is observational, AFTER the failed normal test. No retry acceptance.
                    if dgm_validator is None:
                        self._run_automatic_probe(part,spec,trace)
                    else:
                        trace.data['additional_diagnostic']={
                            'status':'KEINE_LEGACY_WIEDERHOLUNG_NACH_UV_FEHLER',
                            'reason':'Direkte UV-Fehler werden nicht durch eine andere Messmethode uebergangen.',
                            'geometry_release':False}
                except Exception as probe_error:
                    trace.data['additional_diagnostic_error']={
                        'error':str(probe_error),'type':type(probe_error).__name__,
                        'traceback':traceback.format_exc()}
                finally:
                    self.operation=saved_operation
                    try:trace.fail(original)
                    except Exception as write_error:
                        trace.data['secondary_logging_error']=str(write_error)
                        setattr(original,TRACE_ATTR,copy.deepcopy(trace.data))
                raise
            self._set_user_attribute(part,'HAUS_IMPORTSTATUS',
                'ANGEFORDERTE_PRUEFUNG_BESTANDEN_KEIN_BESTANDSNACHWEIS','DGM_DIAGNOSE')
            trace.phase('PRUEFUNG_BESTANDEN_ABSCHLUSSSPEICHERN_AUSSTEHEND',check_result=result)
            return result

        def _run_automatic_probe(self,part,spec,trace):
            self.monitor.check_cancel()
            trace.phase('ZUSATZDIAGNOSE_NACH_PRUEFFEHLER')
            ref=dgm_probe.load_reference(reference_path)
            if ref['source_sha256']!=spec['sha256']:
                raise ValueError('Gezielte Diagnose gehoert nicht zur importierten STEP-Datei.')
            samples=spec['geometry_reference']['sheets'][0]['samples_mm']
            for key,point in ref['points'].items():
                if math.dist(point,samples[int(key)])>1e-8:
                    raise ValueError('Diagnosepunkte stimmen nicht mit Importreferenz ueberein.')
            bodies=list(part.Bodies)
            if len(bodies)!=1 or bodies[0].IsSolidBody or bodies[0].OwningPart.Tag!=part.Tag:
                raise RuntimeError('Zusatzdiagnose braucht genau den einen neu importierten DGM-Flächenkoerper.')
            body=bodies[0];faces=list(body.GetFaces())
            if not 1<=len(faces)<=dgm_probe.MAX_FACES:
                raise RuntimeError('Zusatzdiagnose begrenzt auf 1 bis 8 Einzelflaechen.')
            if any(f.OwningPart.Tag!=part.Tag for f in faces):
                raise RuntimeError('Face gehoert nicht zum DGM-Part.')
            box=self.surface_box(body)
            details={'status':'START','source_sha256':ref['source_sha256'],
                     'body_tag':int(body.Tag),'face_tags':[int(f.Tag) for f in faces],
                     'actual_bbox_mm':box,'geometry_release':False,
                     'trigger':'REGULAERE_PRUEFUNG_FEHLGESCHLAGEN',
                     'scope':'Begrenzter Methodenvergleich, kein Ersatz fuer das regulaere Ergebnis.'}
            trace.data['additional_diagnostic']=details
            def checkpoint(data):
                trace.data['additional_diagnostic']=data
                trace.write()
                self.monitor.check_cancel()
            dgm_probe.run_measurements(self.uf.Modeling,ref,int(body.Tag),
                [int(f.Tag) for f in faces],box,details,checkpoint,self.log)

        def surface_distance_mm(self,body,xyz):
            trace=getattr(self,'_terrain_trace_g01a',None)
            if trace is None:
                return super().surface_distance_mm(body,xyz)
            from r09.surface_check import distance_result_checked
            query=dgm_probe.xyz_checked(xyz)
            row=trace.begin_query(body,query,self.operation)
            started=time.perf_counter()
            arg1=list(query);arg2=[0.,0.,0.]
            try:
                with self.monitor.stage('PUNKTABSTAND',self.operation,force=False):
                    # EXACT old production query. No face fallback, no new seed.
                    raw=self.uf.Modeling.AskMinimumDist(0,body.Tag,1,arg1,0,arg2)
                    row['raw_nx_result']=json_safe(raw)
                    row['guess1_after_mm']=json_safe(arg1)
                    row['guess2_after_mm']=json_safe(arg2)
                    # Preserve values even if the numerical return validation then fails.
                    trace.event('NX_ROHRUECKGABE',row)
                    row.update(dgm_probe.result_record(raw,query))
                    if trace.previous_query is not None:
                        row['target_distance_to_previous_query_mm']=math.dist(
                            row['returned_target_mm'],trace.previous_query)
                    distance=distance_result_checked(raw,query)
                self.monitor.count('surface_distance_calls')
                row['status']='NX_RUECKGABE_ERFASST'
                return distance
            except Exception as error:
                row.update(status='NX_ABFRAGE_ODER_RUECKGABEPRUEFUNG_FEHLGESCHLAGEN',
                           error=str(error),exception_type=type(error).__name__)
                code=getattr(error,'ErrorCode',None)
                if code is not None:row['nx_error_code']=json_safe(code)
                raise
            finally:
                row['seconds']=time.perf_counter()-started
                # Logging failure is itself an error; never pretend that diagnostics exist.
                active_error=sys.exc_info()[1]
                try:
                    trace.finish_query(row)
                except Exception as log_error:
                    if active_error is None:
                        raise
                    active_error.g01a_point_log_error=str(log_error)

    return AuditedSceneAdapter
