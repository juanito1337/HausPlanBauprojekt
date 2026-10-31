# -*- coding: utf-8 -*-
"""R11a execution policy and instrumentation. NX stays on the journal thread.

BASIS is an explicitly limited inspection, NOT a faster equivalent of INTENSIV.
Deferred attributes do not defer feature geometry updates or final Save updates.
No cache, no silent geometry simplification, no automatic edit of old parts.
"""
import copy
import datetime
import json
import os
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path
from .core import absolute, read_json, write_json, settings_checked
from .nx_adapter import SceneAdapter
from .quick_check import verify_basic
from .run import build_house_copy
from .workflow import run_checked_project
from haus2406_r03.haus_nx import NXAdapter

PATCH='R11a-LAUFZEIT'
POLICY_FILE='data/LAUFZEIT_R11a.json'
DEFAULTS={'schema':'R11A_RUNTIME_V1','surface_validation':'BASIS',
          'defer_project_attributes':True,'intermediate_dialogs':False,
          'skip_individual_surface_fit':True}


def policy_checked(policy):
    if not isinstance(policy,dict) or set(policy)!=set(DEFAULTS):
        raise ValueError('LAUFZEIT_R11a.json: unbekannte/fehlende Einstellungen.')
    if policy['schema']!=DEFAULTS['schema'] or policy['surface_validation'] not in ('BASIS','INTENSIV'):
        raise ValueError('LAUFZEIT_R11a.json: schema oder surface_validation ungueltig.')
    for key in ('defer_project_attributes','intermediate_dialogs','skip_individual_surface_fit'):
        if type(policy[key]) is not bool:
            raise ValueError(key+': true/false erforderlich.')
    return copy.deepcopy(policy)


class StopRequested(RuntimeError):
    pass


class RunMonitor:
    """File-backed progress updated BETWEEN NX calls, no unsafe background NX access.
    status JSON is diagnostic (atomic rename, no fsync for every feature).
    Model manifests and saves retain their existing stronger write checks.
    A hung native call cannot be interrupted from this Python check.
    """
    def __init__(self,directory,clock=time.perf_counter):
        self.directory=Path(directory);self.clock=clock;self.started=clock()
        self.stop_file=self.directory/'STOP_R11a.txt'
        self.status_file=self.directory/'LAUFSTATUS_R11a.json'
        self.events_file=self.directory/'LAUFZEITPROFIL_R11a.jsonl'
        self.stack=[];self.sequence=0;self.cancelled=False
        self.last_write=0.0;self.counters={};self.timings={};self.last=None
        self.status='GESTARTET'
        self.write(force=True)

    def check_cancel(self):
        if self.stop_file.exists():
            self.cancelled=True
            raise StopRequested('STOP_R11a.txt gefunden. Kontrollierter Abbruch zwischen NX-Aufrufen; '
                                'bereits gespeicherte Teile bleiben erhalten.')

    def count(self,key,n=1):
        self.counters[key]=self.counters.get(key,0)+n

    def snapshot(self):
        now=self.clock()
        return {'patch':PATCH,'status':self.status,'sequence':self.sequence,
                'updated_at':datetime.datetime.now().isoformat(timespec='seconds'),
                'elapsed_seconds':round(now-self.started,3),'current':copy.deepcopy(self.stack[-1]) if self.stack else None,
                'current_duration_seconds':round(now-self.stack[-1]['clock_start'],3) if self.stack else None,
                'last_completed':self.last,'counters':dict(self.counters),'timings_seconds':copy.deepcopy(self.timings),
                'stop_file':str(self.stop_file),'cancel_requested':self.cancelled,
                'updates_only_between_NX_calls':True,
                'note':'Unveraenderter Zeitstempel kann einen laufenden NX-Kernelaufruf bedeuten; '
                       'kein Timeout-/Hangnachweis. STOP wirkt erst nach Rueckkehr eines Aufrufs.'}

    def write(self,force=False):
        now=self.clock()
        if not force and now-self.last_write<2.0:return
        self.sequence+=1;state=self.snapshot()
        temp=self.status_file.with_name('.'+self.status_file.name+'.tmp')
        try:
            with temp.open('w',encoding='utf-8') as f:
                json.dump(state,f,ensure_ascii=False,indent=2,allow_nan=False)
            os.replace(str(temp),str(self.status_file))
        finally:
            if temp.exists():temp.unlink()
        self.last_write=now

    def event(self,row):
        with self.events_file.open('a',encoding='utf-8') as f:
            f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')

    @contextmanager
    def stage(self,kind,label,detail=None,force=True):
        self.check_cancel()
        entry={'kind':kind,'label':str(label),'detail':detail,
               'clock_start':self.clock(),'started_at':datetime.datetime.now().isoformat(timespec='seconds')}
        self.stack.append(entry);self.status='LAEUFT';self.write(force=force)
        error=None
        try:
            yield
        except BaseException as exc:
            error=exc
            raise
        finally:
            elapsed=max(0.0,self.clock()-entry['clock_start'])
            row={'kind':kind,'label':str(label),'seconds':elapsed,
                 'status':'FEHLER' if error is not None else 'ABGESCHLOSSEN'}
            if error is not None:row['error']=str(error)
            bucket=self.timings.setdefault(kind,{'count':0,'total':0.0,'maximum':0.0})
            bucket['count']+=1;bucket['total']+=elapsed;bucket['maximum']=max(bucket['maximum'],elapsed)
            self.last=row;self.stack.pop()
            self.count('completed_'+kind)
            # Individual point calls only contribute aggregate timings unless failed/slow.
            try:
                if kind!='PUNKTABSTAND' or error is not None or elapsed>=1.0:self.event(row)
                self.write(force=force or error is not None)
            except Exception as diagnostic_error:
                # Never replace the original modeling/API error with a logging error.
                if error is None:raise
                try:error.r11a_diagnostic_error=str(diagnostic_error)
                except (AttributeError,TypeError):pass
        self.check_cancel()

    def finish(self,status):
        self.status=status;self.write(force=True)
        write_json(self.directory/'LAUFZEITZUSAMMENFASSUNG_R11a.json',self.snapshot())


class QuietLog:
    """Keep each original detail on disk; avoid thousands of ListingWindow writes."""
    def __init__(self,backend):self.backend=backend;self.path=getattr(backend,'path',None)
    def __call__(self,text):
        s=str(text)
        if self.path is not None and (s.startswith('  ') or s.startswith('EINHEITENPRUEFUNG ')):
            line=datetime.datetime.now().isoformat(timespec='seconds')+' | '+s
            with Path(self.path).open('a',encoding='utf-8') as f:f.write(line+'\n')
        else:self.backend(text)


class PerformanceMixin:
    def __init__(self,logger,monitor,policy):
        self.monitor=monitor;self.policy=policy_checked(policy)
        self.validation_level=self.policy['surface_validation']
        self._built_here=0;self._last_progress=0.0
        super().__init__(QuietLog(logger))
        # One documented enum, not a guessed method. Missing Later -> original Now.
        later=getattr(self.N.Update.Option,'Later',None)
        if self.policy['defer_project_attributes'] and later is not None:
            self._attribute_update_option=later
            self._deferred_attributes=True
        else:
            self._attribute_update_option=self.N.Update.Option.Now
            self._deferred_attributes=False
            if self.policy['defer_project_attributes']:
                self.log('R11a: Update.Option.Later fehlt; benutze unveraendert Now.')
        if not getattr(self.monitor,'announced',False):
            self.monitor.announced=True
            self.log('R11a Laufstatus: '+str(self.monitor.status_file))
            self.log('R11a Stoppwunsch: leere Datei '+str(self.monitor.stop_file)+
                     ' anlegen; wirkt erst zwischen NX-Aufrufen.')
            self.log('R11a Umgebungspruefung: '+self.validation_level+
                     (' (keine Flaechenintegration, nur verteilte Quellpunkt-Stichproben).'
                      if self.validation_level=='BASIS' else ' (bisheriger umfangreicher Pruefweg).'))
        self.log('R11a: Attributaktualisierung '+('Later; DoUpdate vor Speichern bleibt aktiv.'
                   if self._deferred_attributes else 'Now (Kompatibilitaetsweg).'))

    def _set_user_attribute(self,obj,key,value,context):
        result=super()._set_user_attribute(obj,key,value,context)
        self.monitor.count('attribute_writes_later' if self._deferred_attributes else 'attribute_writes_now')
        return result

    def new_part(self,path,ident):
        with self.monitor.stage('TEIL_ANLEGEN',ident):return super().new_part(path,ident)

    def add_parameters(self,part,params):
        with self.monitor.stage('PARAMETER',Path(part.FullPath).name):return super().add_parameters(part,params)

    def update(self,label):
        with self.monitor.stage('UPDATE',label):return super().update(label)

    def extrude(self,part,points,start,end,name,meta,target=None,direction=(0,0,1)):
        with self.monitor.stage('HAUS_FEATURE',name,{'part':Path(part.FullPath).name}):
            result=super().extrude(part,points,start,end,name,meta,target,direction)
        self._built_here+=1;self.monitor.count('features_created')
        now=time.perf_counter()
        if self._built_here%25==0 or now-self._last_progress>=4.0:
            self.log('R11a Fortschritt: %s | %d Features in diesem Adapter, zuletzt %s' % (
                Path(part.FullPath).name,self._built_here,name))
            self._last_progress=now
        return result

    def save(self,part):
        with self.monitor.stage('SPEICHERN',Path(part.FullPath).name):return super().save(part)

    def review_consent(self):
        with self.monitor.stage('WARTET_AUF_DIALOG','Naeherungen mit Ja/Nein bestaetigen'):
            return super().review_consent()

    def safe_message(self,text,error=False):
        # The wrapper emits one final dialog. Never skip the estimates consent.
        if not self.policy['intermediate_dialogs']:
            self.log('R11a Zwischenmeldung (kein blockierender Dialog): '+str(text))
            return None
        with self.monitor.stage('WARTET_AUF_DIALOG','Zwischenmeldung mit OK schliessen'):
            return super().safe_message(text,error)


class FastHouseAdapter(PerformanceMixin,NXAdapter):
    pass


class FastSceneAdapter(PerformanceMixin,SceneAdapter):
    def prepare_view(self,part):
        if self.policy['skip_individual_surface_fit'] and 'MASTER' not in Path(part.FullPath).stem:
            self.ensure_work(part)
            self.monitor.count('intermediate_view_fits_omitted')
            return
        return super().prepare_view(part)

    def import_surface_part(self,out,source,spec,definition,name=None):
        self.log('R11a START IMPORT: '+spec['id']+' ('+self.validation_level+')')
        with self.monitor.stage('UMGEBUNG_IMPORT_UND_PRUEFUNG',spec['id'],{'file':str(source)}):
            result=super().import_surface_part(out,source,spec,definition,name)
        self.log('R11a IMPORT GESPEICHERT: '+spec['id'])
        return result

    def verify_surface_geometry(self,part,spec,out):
        with self.monitor.stage('UMGEBUNG_PRUEFUNG',spec['id'],{'level':self.validation_level}):
            if self.validation_level=='BASIS':result=verify_basic(self,part,spec,out)
            else:result=super().verify_surface_geometry(part,spec,out)
        # Persist inspection scope on the new NX part, not merely in an external note.
        for key,value in {'HAUS_IMPORTPRUEFUNG':self.validation_level,
                'HAUS_FLAECHENINHALT_GEPRUEFT':str(self.validation_level=='INTENSIV'),
                'HAUS_ALLE_QUELLPUNKTE_GEPRUEFT':str(self.validation_level=='INTENSIV'),
                'HAUS_IMPORTPRUEFUNG_HINWEIS':('BASIS: Umfang/Boxen/Stichproben; keine Flaechenintegration.'
                    if self.validation_level=='BASIS' else 'INTENSIV: Flaecheninhalt und alle definierten Quellpunkte.')}.items():
            self._set_user_attribute(part,key,value,spec['id'])
        return result

    def surface_area_mm2(self,body):
        # Never invoked by BASIS. Accurate old path remains available explicitly.
        with self.monitor.stage('FLAECHENINTEGRATION',getattr(body,'Name',''),
                                {'part':Path(body.OwningPart.FullPath).name}):
            self.monitor.count('surface_area_evaluations')
            return super().surface_area_mm2(body)

    def surface_distance_mm(self,body,xyz):
        with self.monitor.stage('PUNKTABSTAND',self.operation,force=False):
            distance=super().surface_distance_mm(body,xyz)
        self.monitor.count('surface_distance_calls')
        count=self.monitor.counters['surface_distance_calls']
        if count%100==0:self.log('R11a: %d Quellpunktabstaende geprueft; %s'%(count,self.operation))
        return distance


def run_optimized_project(base,mode='ALL',policy=None,config=None,*,monitor_factory=RunMonitor,
                          final_dialog=True):
    base=absolute(base)
    policy=policy_checked(read_json(base/POLICY_FILE) if policy is None else policy)
    cfg=settings_checked(copy.deepcopy(read_json(base/'data/EINSTELLUNGEN_R09.json') if config is None else config))
    if mode not in ('ALL','HOUSE','ENVIRONMENT'):raise ValueError('Unbekannter Startmodus.')
    root=Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    root=absolute(root if root.is_absolute() else base/root)
    root.mkdir(parents=True,exist_ok=True)
    run=root/('R11a_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    run.mkdir(exist_ok=False)
    monitor=monitor_factory(run)
    cfg['output_root']=str(run/'modelllauf')
    state={'schema':'R11A_RUN_V1','patch':PATCH,'mode':mode,'policy':policy,
           'output_directory':str(run),'status':'GESTARTET','model_result':None,
           'geometry_revision':'R11_UNVERAENDERT','full_surface_validation_performed':False,
           'NX_performance_benchmarked_here':False,'as_built_approved':False}
    write_json(run/'manifest_R11a.json',state)
    def factory(logger):return FastSceneAdapter(logger,monitor,policy)
    def house_factory(logger):return FastHouseAdapter(logger,monitor,policy)
    def house_builder(directory,out):
        with monitor.stage('HAUS_GESAMT','Haus R11 aufbauen und nachpruefen'):
            return build_house_copy(directory,out,_adapter_factory=house_factory)
    try:
        # Common code/data hash checks still run in the underlying workflow.
        result=run_checked_project(base,mode,cfg,adapter_factory=factory,house_builder=house_builder)
        monitor.check_cancel()
        state['model_result']=result
        state['full_surface_validation_performed']=bool(result.get('environment') and policy['surface_validation']=='INTENSIV')
        state['status']=('ERZEUGT_BASISPRUEFUNG_VOLLPRUEFUNG_OFFEN' if result.get('environment') and
                         policy['surface_validation']=='BASIS' else 'ERZEUGT_FACHLICH_OFFEN')
        state['diagnostics']=monitor.snapshot()
        write_json(run/'manifest_R11a.json',state)
        write_json(base/'LETZTER_LAUF_R11a.json',{'output_directory':str(run),
                   'manifest':str(run/'manifest_R11a.json'),'status':state['status']})
        monitor.finish('ABGESCHLOSSEN_'+state['status'])
        text=('R11a: Modelllauf abgeschlossen.\n\n'+str(Path(result['output_directory'])/result['displayed_master'])+
              '\n\nHausgeometrie unveraendert R11. '+
              ('Umgebung nur BASIS-geprueft: Koerper/Boxen/Stichproben, KEINE Flaechenintegration. '
               if result.get('environment') and policy['surface_validation']=='BASIS' else '')+
              '\nHohenanschluss/Leitungstiefen und konstruktive offene Punkte bleiben.\n'
              'Weiterarbeiten: gespeicherte .prt oeffnen, nicht erneut erzeugen.\n'
              'Laufstatus und Zeiten: '+str(run))
        if final_dialog:
            import NXOpen
            try:
                NXOpen.UI.GetUI().NXMessageBox.Show('NX-Projekt R11a',NXOpen.NXMessageBox.DialogType.Information,text)
            except Exception as display_error:
                # A failed optional final notification does not undo a completed saved build.
                state['final_notification_warning']=str(display_error)
                write_json(run/'manifest_R11a.json',state)
        return state
    except Exception as error:
        state.update(status='ABBRUCH_KEIN_GESAMTERFOLG',error=str(error),traceback=traceback.format_exc(),
                     diagnostics=monitor.snapshot())
        context=getattr(error,'r11_context',{})
        state['saved_house_master']=context.get('saved_house_master')
        state['saved_environment_master']=context.get('saved_environment_master')
        if state.get('model_result'):
            completed=state['model_result']
            for key,part in (('saved_house_master','house'),('saved_environment_master','environment')):
                if completed.get(part):state[key]=str(Path(completed['output_directory'])/completed[part]['master'])
        error.r11a_context={'output_directory':str(run),'manifest':str(run/'manifest_R11a.json'),
                           'progress_file':str(monitor.status_file),'last_step':monitor.snapshot(),
                           'saved_house_master':state['saved_house_master'],
                           'saved_environment_master':state['saved_environment_master']}
        try:
            write_json(run/'manifest_R11a.json',state)
            monitor.finish('ABBRUCH_AUF_ANFORDERUNG' if monitor.cancelled else 'ABGEBROCHEN')
        except Exception as report_error:error.r11a_diagnostic_error=str(report_error)
        raise
