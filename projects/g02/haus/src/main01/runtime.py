# -*- coding: utf-8 -*-
"""House-only launcher. Never imports the environment integration or STEP importer.
Saved files are a versioned working baseline, NOT a structural/as-built approval.
"""
import datetime
import hashlib
import json
import os
import time
import traceback
import uuid
from contextlib import contextmanager
from pathlib import Path
from . import PATCH
from haus2406_r03.haus_nx import NXAdapter
from haus2406_r03.haus_runtime import absolute_path, atomic_json, read_json, sha256_file
from haus2406_r03.haus_run import run_house, check_saved_house


class StopRequested(RuntimeError):
    pass


class Monitor:
    def __init__(self,directory,clock=time.perf_counter):
        self.directory=Path(directory);self.clock=clock;self.start=clock();self.current=None
        self.status='GESTARTET';self.timings={};self.count=0
        self.stop=self.directory/'STOP_MAIN01.txt'
        self.file=self.directory/'LAUFSTATUS_MAIN01.json'
        self.events=self.directory/'LAUFZEIT_MAIN01.jsonl'
        self.write()
    def write(self):
        # Diagnostic only. No fsync per feature, but atomic rename.
        state={'patch':PATCH,'status':self.status,'updated_at':datetime.datetime.now().isoformat(),
               'elapsed_seconds':self.clock()-self.start,'current':self.current,
               'completed_steps':self.count,'timings':self.timings,
               'stop_file':str(self.stop),'updates_only_between_nx_calls':True}
        temp=self.file.with_suffix('.tmp')
        temp.write_text(json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
        os.replace(str(temp),str(self.file))
    def check(self):
        if self.stop.exists():raise StopRequested('STOP_MAIN01.txt: kontrollierter Stopp zwischen NX-Aufrufen; gespeicherte Dateien bleiben erhalten.')
    @contextmanager
    def step(self,kind,label):
        self.check();previous=self.current;t=self.clock();self.current={'kind':kind,'label':str(label)};self.status='LAEUFT';self.write()
        failure=None
        try:yield
        except BaseException as e:failure=e;raise
        finally:
            elapsed=self.clock()-t;self.count+=1;bucket=self.timings.setdefault(kind,{'count':0,'seconds':0.0})
            bucket['count']+=1;bucket['seconds']+=elapsed
            row={'kind':kind,'label':str(label),'seconds':elapsed,'status':'FEHLER' if failure else 'ABGESCHLOSSEN'}
            if failure:row['error']=str(failure)
            self.current=previous
            try:
                with self.events.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
                self.write()
            except Exception as log_error:
                if failure is None:raise
                try:failure.main01_logging_error=str(log_error)
                except (AttributeError,TypeError):pass
        self.check()
    def finish(self,status):self.status=status;self.current=None;self.write()


class QuietLog:
    def __init__(self,backend):self.backend=backend;self.path=backend.path
    def __call__(self,text):
        if str(text).startswith(('  ','EINHEITENPRUEFUNG ')):
            with self.path.open('a',encoding='utf-8') as f:f.write(datetime.datetime.now().isoformat()+' | '+str(text)+'\n')
        else:self.backend(text)


class HouseMainAdapter(NXAdapter):
    def __init__(self,logger,monitor=None):
        self.monitor=monitor if monitor is not None else Monitor(Path(logger.path).parent)
        self._last_progress=0.;self._features_done=0
        super().__init__(QuietLog(logger))
        # Same supported choice as R11a. Never remove required Save/feature updates.
        self._attribute_update_option=getattr(self.N.Update.Option,'Later',self.N.Update.Option.Now)
        self.log('MAIN01: ausschliesslich Haus; kein STEP, keine DGM-/Vegetationsmessung.')
        self.log('Laufstatus: '+str(self.monitor.file))
    def review_consent(self):
        text=('MAIN01-A01: 45/28 Grad getrennt, berechnete Gaubenanschluesse. Haus mit Balkon rechts aus Strassensicht, Zugangsnische, Kellerabgang-Gelaender und sichtbaren Fallrohrabschnitten.\n\n'
              'JA: Modell mit gekennzeichneten Naeherungen erzeugen.\nNEIN: Nur Referenzgeruest ohne Hauskoerper.\n\n'
              'Balkonmasse, Querschnitte, Befestigungen und Nischengeometrie sind nicht aufgemessen. Keine Statik, keine Baufreigabe. '
              'Bestehende Haus-Anbau-Konflikte bleiben offen.\n\nKein Garten-/Gelaende-/STEP-Aufbau in diesem Paket.')
        with self.monitor.step('DIALOG','Naeherungen bestaetigen'):
            return self.ui.NXMessageBox.Show('MAIN01 – bewusste Freigabe von Naeherungen',self.N.NXMessageBox.DialogType.Question,text)==1
    def new_part(self,path,ident):
        with self.monitor.step('PART',ident):return super().new_part(path,ident)
    def add_parameters(self,part,params):
        with self.monitor.step('PARAMETER',Path(part.FullPath).name):return super().add_parameters(part,params)
    def extrude(self,part,points,start,end,name,meta,target=None,direction=(0,0,1)):
        with self.monitor.step('FEATURE',name):result=super().extrude(part,points,start,end,name,meta,target,direction)
        self._features_done+=1;now=time.perf_counter()
        if self._features_done%25==0 or now-self._last_progress>5:
            self.log('MAIN01 Fortschritt: %d Features; %s'%(self._features_done,name));self._last_progress=now
        return result
    def save(self,part):
        with self.monitor.step('SPEICHERN',Path(part.FullPath).name):
            self._set_user_attribute(part,'HAUS_MAIN_REVISION','MAIN01-A01','Baseline')
            self._set_user_attribute(part,'HAUS_MAIN_STATUS','ARBEITSBASIS_NICHT_BESTANDS_ODER_TRAGWERKSFREIGEGEBEN','Baseline')
            return super().save(part)
    def safe_message(self,text,error=False):
        self.log(('FEHLER: ' if error else 'Zwischenmeldung: ')+str(text))


def verify_package(base):
    base=absolute_path(base);path=base/'PAKETDATEIEN_SHA256.json'
    if not path.is_file():raise FileNotFoundError('Paket unvollstaendig: PAKETDATEIEN_SHA256.json fehlt.')
    registry=read_json(path);changed=[];checked=0
    editable={'data/haus.json','data/einstellungen.json'}
    for name,expected in registry['files'].items():
        p=base/name
        if not p.is_file():raise FileNotFoundError('Paketdatei fehlt: '+name)
        actual=sha256_file(p)
        if actual!=expected:
            if name in editable:changed.append({'file':name,'baseline_sha256':expected,'actual_sha256':actual})
            else:raise ValueError('Programm-/Quelldatei veraendert: '+name+'. Nicht mit anderen Revisionen mischen.')
        checked+=1
    return {'checked_files':checked,'editable_input_changes':changed,
            'baseline_inputs_unchanged':not changed,'scope':'Originaler Hausstand und noetige Dateien, kein NX-Geometrienachweis.'}


def run_main(base,adapter_factory=HouseMainAdapter,verify=True):
    base=absolute_path(base);state={'patch':PATCH,'status':'START','phase':'PAKETPRUEFUNG','saved_house':None,
        'structural_approval':False,'as_built_verified':False,'environment_included':False,'STEP_import':False}
    instances=[]
    def factory(log):
        nx=adapter_factory(log,monitor=instances[0].monitor) if instances and adapter_factory is HouseMainAdapter else adapter_factory(log)
        instances.append(nx);return nx
    try:
        state['package_check']=verify_package(base) if verify else {'test_bypassed_package_hashes':True}
        data=read_json(base/'data/haus.json')
        if data.get('site',{}).get('enabled'):raise ValueError('MAIN01 ist ein Hauslauf. site.enabled muss false bleiben; Umgebung ist spaeter getrennt zu bearbeiten.')
        state['phase']='HAUS_FUNKTIONSTEST_UND_AUFBAU'
        house=run_house(base,_adapter_factory=factory)
        out=absolute_path(house['output_directory']);state['output_directory']=str(out)
        state['saved_house']=str(out/'HAUS_MASTER.prt');state['phase']='DATEI_UND_BAUGRUPPENPRUEFUNG'
        atomic_json(out/'manifest_MAIN01.json',state)
        verification=check_saved_house(base,_adapter_factory=factory)
        if verification['status']!='DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN':raise RuntimeError('MAIN01 Nachpruefung unvollstaendig')
        state.update(status='MAIN01_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT',phase='ABGESCHLOSSEN',
            built_solids=house['built_solids'],component_count=house['component_count'],mode=house['mode'],
            numerical_collisions=house['numeric_collision_pairs'],blocked_openings=house['blocked_clear_openings'],
            verification=verification,finished=datetime.datetime.now().isoformat())
        baseline={'schema':'HAUS_MAIN_BASELINE_V1','revision':'MAIN01-A01',
            'input_file_sha256':sha256_file(base/'data/haus.json'),'package_check':state['package_check'],
            'source_video_sha256':data['main_details']['video_sha256'],
            'model_status':'ARBEITSBASIS_MIT_DOKUMENTIERTEN_ANNAHMEN',
            'mode':house['mode'],'built_solids':house['built_solids'],'component_count':house['component_count'],
            'native_NX_run_completed':True,'as_built_verified':False,'structural_approval':False,
            'main_model_file':'HAUS_MASTER.prt','saved_files':house['files'],
            'known_collision_pairs':house['numeric_collision_pairs'],'blocked_openings':house['blocked_clear_openings'],
            'manual_changes_from_older_models_carried_over':False,
            'instruction':'Gesamten Ausgabeordner als Baseline aufbewahren. Weiterarbeit in Kopie; Erzeuger erstellt neu und uebernimmt keine manuellen Aenderungen.'}
        atomic_json(out/'BASELINE_MAIN01.json',baseline);atomic_json(out/'manifest_MAIN01.json',state)
        atomic_json(base/'LETZTER_MAIN01_LAUF.json',{'directory':str(out),'master':state['saved_house'],'manifest':str(out/'manifest_MAIN01.json'),'status':state['status']})
        for monitor in {id(nx.monitor):nx.monitor for nx in instances if hasattr(nx,'monitor')}.values():
            monitor.finish('ABGESCHLOSSEN')
        return state
    except Exception as exc:
        state.update(status='ABGEBROCHEN_KEINE_GESAMTFREIGABE',error=str(exc),traceback=traceback.format_exc())
        if instances:
            nx=instances[-1];state['nx_operation']=getattr(nx,'operation','UNBEKANNT')
            if hasattr(nx,'monitor'):
                state['output_directory']=str(nx.monitor.directory)
                try:nx.monitor.finish('ABGEBROCHEN')
                except Exception as secondary:state['diagnostic_error']=str(secondary)
        try:
            if state.get('output_directory'):atomic_json(Path(state['output_directory'])/'manifest_MAIN01.json',state)
        except Exception as secondary:state['manifest_error']=str(secondary)
        try:exc.main01_context=state
        except (TypeError,AttributeError):pass
        raise
