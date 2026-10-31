# -*- coding: utf-8 -*-
"""NX-Laufsteuerung mit neuen Ausgabeordnern, Protokoll und Fehlerstatus."""
import csv
import datetime
import hashlib
import json
import math
import os
import platform
import traceback
import uuid
from pathlib import Path
from .haus_geometry import Parameters,validate
from .haus_compile import compile_house
from .haus_roof import height
from .haus_quality import plane_z
from .haus_nx import NXAdapter
from .haus_runtime import (absolute_path,PATCH,PATH_POLICY,read_json,atomic_json,settings_checked,path_key,
    verify_output_paths,verify_saved_files,input_fingerprint,sha256_file)
from .haus_profile import validate_compiled_profiles,profile_check


def dump(path,value):
    atomic_json(path,value)


def write_parameter_report(out,nx):
    """Required build-time provenance sidecar, no claim of NX readback."""
    snapshot=nx.metadata_snapshot()
    path=Path(out)/'parameter_metadaten.json'
    dump(path,snapshot)
    return {'file':path.name,'bytes':path.stat().st_size,'sha256':sha256_file(path),
            'records':len(snapshot['records']),
            'storage':'PART_USER_ATTRIBUTES',
            'scope':'Schreibprotokoll und Quellendaten; keine aktuellen NX-Werte.'}


def check_parameter_report(out,manifest):
    """File integrity only; an existing model's source snapshot is immutable."""
    record=manifest.get('parameter_metadata')
    if record is None:
        if manifest.get('patch') in ('R03c-ATTRIBUTFIX','R06-QUELLEN-KONSISTENZ'):
            raise RuntimeError('R03c-Parameter-Metadaten fehlen im Manifest.')
        return 'ALTER_LAUF_OHNE_R03c_PARAMETERPROTOKOLL'
    if record.get('file')!='parameter_metadaten.json':
        raise RuntimeError('Unerwarteter Parameter-Metadatenpfad.')
    path=Path(out)/record['file']
    if not path.is_file():raise FileNotFoundError('Parameter-Metadaten fehlen: '+str(path))
    if path.stat().st_size!=record['bytes'] or sha256_file(path)!=record['sha256']:
        raise RuntimeError('Parameter-Metadaten veraendert: '+str(path))
    return 'DATEI_PRUEFSUMME_BESTAETIGT_KEIN_NX_ATTRIBUT_LESETEST'


class Log:
    def __init__(self,path):self.path=Path(path);self.nx=None
    def __call__(self,text):
        line=datetime.datetime.now().isoformat(timespec='seconds')+' | '+str(text)
        with self.path.open('a',encoding='utf-8') as f:f.write(line+'\n')
        try:print(line)
        except (OSError,UnicodeError,AttributeError):
            # NX kann ohne beschreibbaren Python-stdout laufen; Dateiprotokoll bleibt.
            self.stdout_unavailable=True
        if self.nx is not None:
            try:self.nx.session.ListingWindow.WriteLine(line)
            except Exception as ex:
                with self.path.open('a',encoding='utf-8') as f:f.write('ListingWindow: '+str(ex)+'\n')


def output_directory(base,settings,prefix):
    settings=settings_checked(settings)
    chosen=settings.get('output_root','').strip()
    root=Path(chosen).expanduser() if chosen else Path(base)/'ausgabe'
    if not root.is_absolute():root=Path(base)/root
    root.mkdir(parents=True,exist_ok=True)
    run=prefix+'_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    out=absolute_path(root/run);out.mkdir(exist_ok=False)
    return out


def sources_text(meta):return ', '.join(s.get('document','?') for s in meta.get('sources',[]))


def reference_objects(nx,part,definitions,params):
    count=0
    for ref in definitions:
        points=ref.get('points3d')
        if points is None:
            polygon=ref.get('polygon',[])
            z=params.number(ref.get('z',0))
            points=[[p[0],p[1],z] for p in polygon]
        if len(points)<2:continue
        count+=len(nx.lines(part,points,ref['id'],ref.get('closed',True),False,ref))
    return count


def control_objects(nx,part,params,review):
    count=0
    for name in ('Z_KG','Z_EG','Z_DG','Z_KG_ANBAU','Z_EG_ANBAU','UK_DG_DECKE','UK_EG_DECKE'):
        z=params.value(name)
        meta=dict(params.items[name],id=name+'_REFERENZ')
        count+=len(nx.lines(part,[[0,0,z],[3000,0,z],[3000,1500,z],[0,1500,z]],name,True,False,meta))
    meta={'id':'Z_BEZUG','status':'ABGELEITET','sources':[{'document':'P13','page':1,'location':'Hoehenbezug'}]}
    count+=len(nx.lines(part,[[0,0,params.value('Z_KG')],[0,0,8000]],'Z_ACHSE',False,False,meta))
    nx.attributes(part,{'id':'STEUERUNG','status':'PRUEFMODELL' if review else 'REFERENZGERUEST','sources':[]})
    return count


def preflight_filenames(nx,filenames):
    """Keine bereits geladenen gleichnamigen Nutzermodelle veraendern."""
    wanted={n.lower() for n in filenames}
    collisions=[]
    for loaded in nx.session.Parts:
        path=loaded.FullPath
        name=str(path).replace('\\','/').rsplit('/',1)[-1] if path else str(getattr(loaded,'Leaf',''))
        if name and name.lower() in wanted:collisions.append(path or name)
    if collisions:
        raise RuntimeError('Gleichnamige Parts sind bereits geladen. Diese Projektteile zuerst manuell schliessen; '
                           'es wird nichts automatisch geschlossen oder ueberschrieben:\n'+'\n'.join(collisions))


def build_solid(nx,part,solid,params):
    ident=solid['id'];meta=dict(solid['meta']);meta['id']=ident;meta['category']=solid['kind'];meta['parent_id']=solid['parent']
    if solid['kind'] in ('DACH','PRISMA'):
        vector=solid['vector'];length=math.sqrt(sum(v*v for v in vector))
        if length<=0:raise ValueError('Prisma ohne Laenge '+ident)
        direction=tuple(v/length for v in vector)
        return nx.extrude(part,solid['points'],0,length,ident,meta,direction=direction)
    bodies=nx.xy_extrude(part,solid['polygon'],solid['bottom'],solid['top'],ident,meta)
    if solid.get('bottom_plane'):
        for label,plane,direction in [('UNTEN',solid['bottom_plane'],(0,0,-1)),('OBEN',solid['top_plane'],(0,0,1))]:
            values=[plane_z(plane,q) for q in solid['polygon']]
            if max(values)-min(values)<1e-6:continue
            pts=[[q[0],q[1],plane_z(plane,q)] for q in solid['polygon']]
            trimmed=[]
            for body in bodies:trimmed.extend(nx.extrude(part,pts,0,20000,ident+'_'+label,meta,target=body,direction=direction))
            bodies=trimmed
    if solid.get('roof_clip'):
        face=solid['roof_clip'];thickness=params.value('DACH_HUELLE_PROXY')
        points=[[p[0],p[1],height(face,p)-thickness] for p in solid['polygon']]
        clipped=[]
        for i,body in enumerate(bodies):
            clipped.extend(nx.extrude(part,points,0,20000,ident+'_DACHABSCHNITT_%02d'%i,meta,target=body))
        bodies=clipped
    return bodies


def write_coverage(path,rows):
    fields=['id','part','kind','status','note','planned_solids']
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter=';');w.writeheader();w.writerows(rows)


def run_house(base, _adapter_factory=None):
    base=absolute_path(base)
    data=read_json(base/'data'/'haus.json')
    settings=settings_checked(read_json(base/'data'/'einstellungen.json'))
    check=validate(data)
    if check['errors']:raise ValueError('Datensatz nicht verwendbar: '+'; '.join(check['errors']))
    if settings.get('continue_on_feature_error'):
        raise ValueError('continue_on_feature_error wird bewusst nicht unterstuetzt. Fehler stoppen den Lauf.')
    out=output_directory(base,settings,'HAUS');log=Log(out/'laufprotokoll.txt');nx=None
    state={'project':data['project_id'],'revision':'MAIN01','patch':PATCH,'path_policy':PATH_POLICY,'status':'START','nx_runtime_test':'LAUF_GESTARTET',
           'started':datetime.datetime.now().isoformat(),'python':platform.python_version(),
           'files':[],'built_solids':0,'warnings':[], 'output_directory':str(out)}
    dump(out/'manifest.json',state)
    try:
        nx=(_adapter_factory or NXAdapter)(log);log.nx=nx
        dump(out/'api_umgebung.json',nx.api_capabilities)
        state['input_fingerprint']=input_fingerprint(base)
        review=bool(settings.get('allow_estimates',False))
        if not review and settings.get('show_review_consent',True):review=nx.review_consent()
        state['mode']='PRUEFMODELL_MIT_NAEHERUNGEN' if review else 'REFERENZGERUEST'
        state['estimates_explicitly_allowed']=review
        log('Modus: '+state['mode'])
        compiled=compile_house(data,review);params=Parameters(data['parameters'])
        profiles=validate_compiled_profiles(compiled,params)
        dump(out/'profil_vorpruefung.json',profiles)
        state['planned_solids']=compiled['planned_solids'];state['warnings']=compiled['warnings']
        state['geometry_revision']='MAIN01_HAUSBASIS' if data.get('main_baseline') else 'R10_VIDEO_NAEHERUNG' if data.get('video_revision') else 'R06_UNVERAENDERT'
        if data.get('video_revision'):
            dump(out/'video_aenderungen_R10.json',data['video_revision'])
            state['video_review']=data['video_revision']
            state['video_roof_cut_check']=compiled.get('video_roof_cut_check',[])
        state['site_audit']=compiled.get('site_audit',{})
        state['flat_roof_audit']=compiled.get('flat_roof_audit',{})
        dump(out/'grundstueck_leitungspruefung.json',state['site_audit'])
        state['detail_counts']=compiled.get('detail_counts',{});state['profile_audit']=compiled['profile_audit']
        from .haus_audit import audit_compiled
        numerical=audit_compiled(data,compiled)
        dump(out/'numerische_pruefung.json',numerical)
        state['numeric_collision_pairs']=numerical['collision_count']
        from .haus_construction import source_plausibility
        construction_review=source_plausibility(data,compiled)
        dump(out/'konstruktionspruefung.json',construction_review)
        state['construction_complete']=False
        state['as_built_verified']=False
        state['structural_design_verified']=False
        from .haus_consistency import consistency_report
        consistency=consistency_report(data,compiled,numerical)
        dump(out/'quellen_konsistenzpruefung.json',consistency)
        state['technical_consistency_confirmed']=False
        state['document_coverage_complete']=False
        state['consistency_status']=consistency['status']
        state['blocked_clear_openings']=consistency['opening_clearance']['blocked_count']
        state['proxy_solids_excluded_from_quantities']=consistency['proxy_excluded_from_quantities']
        if consistency['logical_errors']:
            raise ValueError('Quellen-/Datenverknuepfung inkonsistent: '+str(consistency['logical_errors']))
        if state['blocked_clear_openings']:
            log('FACHLICH OFFEN: %s deklarierte Oeffnungen nicht vollstaendig frei; siehe quellen_konsistenzpruefung.json.'%state['blocked_clear_openings'])
        facts_file=base/'data'/'QUELLENFAKTEN_R06.json'
        if facts_file.is_file():dump(out/'quellenfakten_verwendet.json',read_json(facts_file))
        state['body_geometry_checks']=[]
        if numerical['invalid_solids']:raise ValueError('Numerisch ungueltige Koerper: '+str(numerical['invalid_solids']))
        if numerical['collision_count']:log('WARNUNG: '+str(numerical['collision_count'])+' numerische Ueberschneidungspaare; siehe numerische_pruefung.json. Keine geometrische Freigabe.')
        filenames=[p['file'] for p in compiled['parts']]+['HAUS_MASTER.prt']
        verify_output_paths(out,filenames)
        preflight_filenames(nx,filenames)
        state['status']='NX_FUNKTIONSTEST';dump(out/'manifest.json',state)
        test=smoke_test(base,_nx=nx,_settings=settings,_parent=out,_silent=True,
                        _compiled=compiled,_params=params)
        if test.get('status')!='NX_FUNKTIONSTEST_BESTANDEN':
            raise RuntimeError('Vorgeschalteter Funktionstest nicht bestanden; Hausbau gesperrt.')
        state['smoke_test_directory']=test['output_directory']
        if input_fingerprint(base)!=state['input_fingerprint']:
            raise RuntimeError('Projektdateien wurden waehrend der Vorpruefung veraendert. Neu starten.')
        dump(out/'haus_verwendet.json',data)
        dump(out/'einstellungen_verwendet.json',dict(settings,allow_estimates=review))
        dump(out/'bauauftrag.json',compiled)
        write_coverage(out/'abdeckung_geplant.csv',compiled['coverage'])
        state['source_data_sha256']=hashlib.sha256((base/'data'/'haus.json').read_bytes()).hexdigest()
        state['status']='BAUT';dump(out/'manifest.json',state)
        for index,definition in enumerate(compiled['parts']):
            log('Teil %d/%d: %s; %d Koerper-Auftraege'%(index+1,len(compiled['parts']),definition['file'],len(definition['solids'])))
            part=nx.new_part(out/definition['file'],definition['id']);nx.add_parameters(part,params)
            source_ids=definition.get('source_fact_ids',[])
            nx.attributes(part,{'id':definition['id'],'status':state['mode'],'sources':[],
                'source_fact_ids':';'.join(source_ids),'technical_consistency_confirmed':False,
                'document_coverage_complete':False,'as_built_verified':False})
            state['parameter_metadata']=write_parameter_report(out,nx)
            if definition['id']=='STEUERUNG':control_objects(nx,part,params,review)
            if definition.get('force_reference_display') or not review or settings.get('show_reference_curves',False):
                drawn=reference_objects(nx,part,definition['references'],params)
                if definition.get('force_reference_display'):
                    expected=sum(len(r['points3d'])-(0 if r.get('closed') else 1) for r in definition['references'])
                    if drawn!=expected:raise RuntimeError('Anzahl Grundstuecks-/Leitungssegmente falsch: '+definition['id'])
                    state.setdefault('site_reference_counts',{})[definition['id']]=drawn
            done_ids=[]
            for i,solid in enumerate(definition['solids']):
                state['current_object']=solid['id']
                log('  '+solid['id']+' | '+sources_text(solid['meta']))
                bodies=build_solid(nx,part,solid,params)
                if len(bodies)!=1:raise RuntimeError('Bauteilauftrag erzeugte nicht genau einen Koerper: '+solid['id'])
                expectation=_expected_bbox(solid,params)
                actual=nx.bounding_box(bodies[0])
                checked=check_body_bbox(solid['id'],definition['id'],expectation,actual)
                state['body_geometry_checks'].append(checked)
                # Write before raising, so the failing shape is identifiable.
                if checked['status']!='BOX_VERGLEICH_BESTANDEN':
                    dump(out/'koerper_boxpruefung.json',state['body_geometry_checks'])
                    raise RuntimeError('Koerperbox weicht vom Bauauftrag ab: '+solid['id']+'; maximal '+str(checked['max_difference_mm'])+' mm. Siehe koerper_boxpruefung.json.')
                state['built_solids']+=1;done_ids.append(solid['id'])
                if (i+1)%25==0:dump(out/'manifest.json',state)
            actual_count=len(list(part.Bodies))
            if actual_count!=len(definition['solids']):
                raise RuntimeError('Koerperanzahl weicht vom Bauauftrag ab: '+definition['id']+' Soll='+str(len(definition['solids']))+' Ist='+str(actual_count))
            dump(out/'koerper_boxpruefung.json',state['body_geometry_checks'])
            saved=nx.save(part);saved['part_id']=definition['id'];saved['completed_ids']=done_ids
            state['files'].append(saved);dump(out/'manifest.json',state)
        master=nx.new_part(out/'HAUS_MASTER.prt','HAUS_MASTER')
        for definition in compiled['parts']:nx.add_component(master,out/definition['file'],definition['id'])
        count=len(master.ComponentAssembly.RootComponent.GetChildren())
        if count!=len(compiled['parts']):raise RuntimeError('Baugruppenanzahl weicht ab: '+str(count))
        state['component_count']=count
        nx.attributes(master,{'id':'HAUS_MASTER','status':state['mode'],'sources':[],
          'construction_status':'UNVOLLSTAENDIG_KEINE_DACHUMBAU_FREIGABE','as_built_verified':False,
          'load_bearing_status':'NICHT_NACHGEWIESEN','technical_consistency_confirmed':False,
          'document_coverage_complete':False})
        nx.fit(master);state['files'].append(nx.save(master))
        if state['built_solids']!=state['planned_solids']:
            raise RuntimeError('Nicht alle geplanten Bauteilauftraege abgeschlossen.')
        state['status']='NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT'
        state['nx_runtime_test']='MODELLLAUF_UND_SPEICHERN_ERFOLGREICH; WIEDEROEFFNUNG_SEPARAT_PRUEFEN'
        state['features_including_smoke']=nx.feature_count
        state['display_object_setup']=list(nx.visibility_records)
        state['adapter_warnings']=list(nx.warnings)
        state['parameter_metadata']=write_parameter_report(out,nx)
        state['attribute_failures']=list(nx.attribute_failures)
        state['unit_checks']=list(nx.unit_checks)
        state['body_box_check_count']=len(state['body_geometry_checks'])
        dump(out/'koerper_boxpruefung.json',state.pop('body_geometry_checks'))
        state['finished']=datetime.datetime.now().isoformat()
        state.pop('current_object',None)
        for row in compiled['coverage']:
            if row['status']=='GEPLANT_NAEHERUNG':row['status']='ERZEUGT_NAEHERUNG'
        write_coverage(out/'abdeckung_erzeugt.csv',compiled['coverage'])
        verify_saved_files(out,state)
        dump(out/'manifest.json',state)
        # Nur eigener Ergebniszeiger, keine vorhandenen Modelle.
        dump(base/'LETZTER_ERFOLGREICHER_LAUF.json',{'directory':str(out),'master':str(out/'HAUS_MASTER.prt')})
        log('Modelllauf beendet. Keine Baufreigabe und keine bestaetigte Planuebereinstimmung.')
        nx.safe_message('Erzeugt: '+state['mode']+'\n'+str(out/'HAUS_MASTER.prt')+
                   '\n\n'+str(state['built_solids'])+' Koerper-Auftraege, '+str(count)+' Komponenten.\n'
                   'MAIN01: Die Datei-/Strukturpruefung folgt automatisch; kein zweites Journal starten.\n'
                   'Fachliche Sperrpunkte bleiben: '+str(state['blocked_clear_openings'])+' blockierte Oeffnungen und '+str(numerical['collision_count'])+' Ueberschneidungspaare.\n'
                   'Kein vollstaendiges oder statisch bestaetigtes Bestandsmodell.')
        return state
    except Exception as ex:
        state['status']='ABGEBROCHEN_TEILMODELL_NICHT_FREIGEGEBEN'
        state['error']=str(ex);state['traceback']=traceback.format_exc()
        state['nx_operation']=nx.operation if nx is not None else 'VOR_NX_INITIALISIERUNG'
        state['unit_checks']=list(nx.unit_checks) if nx is not None else []
        state['attribute_failures']=list(nx.attribute_failures) if nx is not None else []
        if nx is not None:
            try:state['parameter_metadata']=write_parameter_report(out,nx)
            except Exception as report_error:state['parameter_metadata_report_error']=str(report_error)
        if 'body_geometry_checks' in state:dump(out/'koerper_boxpruefung.json',state.pop('body_geometry_checks'))
        dump(out/'manifest.json',state);log(state['traceback'])
        if nx is not None:
            nx.restore_display_after_failure()
            nx.safe_message('Lauf abgebrochen. Keine Vollstaendigkeitsmeldung.\n'+str(ex)+'\n\nProtokoll:\n'+str(out/'laufprotokoll.txt'),True)
        raise


def check_body_bbox(ident,part_id,expected,actual,tolerance_mm=1.0):
    """UF axis-aligned boxes: gross location/extent check, not full shape match.
    1 mm is an API/computation comparison tolerance, NOT source accuracy.
    """
    if len(expected)!=6 or len(actual)!=6 or not all(math.isfinite(float(x)) for x in expected+actual):
        raise ValueError('Ungueltige Boxdaten fuer '+ident)
    if not math.isfinite(tolerance_mm) or tolerance_mm<=0:raise ValueError('Ungueltige Boxtoleranz')
    delta=max(abs(float(a)-float(e)) for a,e in zip(actual,expected))
    return {'id':ident,'part':part_id,'expected_mm':expected,'nx_box_mm':actual,
      'max_difference_mm':delta,'tolerance_mm':tolerance_mm,
      'status':'BOX_VERGLEICH_BESTANDEN' if delta<=tolerance_mm else 'BOX_ABWEICHUNG',
      'scope':'Lage/Ausdehnung zur berechneten Geometrie; keine Form-, Plan-, Material- oder Tragwerksfreigabe.'}


def _expected_bbox(solid,params):
    if 'points' in solid:
        pts=list(solid['points'])+[[q[i]+solid['vector'][i] for i in range(3)] for q in solid['points']]
    else:
        lo=params.number(solid['bottom']);hi=params.number(solid['top']);pts=[]
        for q in solid['polygon']:
            bottom=plane_z(solid['bottom_plane'],q) if solid.get('bottom_plane') else lo
            top=plane_z(solid['top_plane'],q) if solid.get('top_plane') else hi
            if solid.get('roof_clip'):top=min(top,height(solid['roof_clip'],q)-params.value('DACH_HUELLE_PROXY'))
            pts.extend([[q[0],q[1],bottom],[q[0],q[1],top]])
    return [min(q[i] for q in pts) for i in range(3)]+[max(q[i] for q in pts) for i in range(3)]


def smoke_test(base,_nx=None,_settings=None,_parent=None,_silent=False,_compiled=None,_params=None):
    """Tatsaechlicher NX-Test erst beim Nutzer. Eindeutige Testdateinamen pro Lauf."""
    base=Path(base)
    settings=settings_checked(read_json(base/'data'/'einstellungen.json')) if _settings is None else _settings
    if _parent is None:
        out=output_directory(base,settings,'FUNKTIONSTEST')
    else:
        out=Path(_parent)/'funktionstest';out.mkdir(exist_ok=False)
    log=Log(out/'laufprotokoll.txt');nx=_nx
    result={'status':'LAEUFT','revision':'MAIN01','patch':PATCH,'path_policy':PATH_POLICY,'output_directory':str(out),'checks':{},'nx_execution':True}
    dump(out/'testergebnis.json',result)
    token=uuid.uuid4().hex[:8]
    geometry_name='TEST_GEOMETRIE_'+token+'.prt';master_name='TEST_MASTER_'+token+'.prt'
    try:
        if nx is None:nx=NXAdapter(log)
        log.nx=nx
        dump(out/'api_umgebung.json',nx.api_capabilities)
        result['checks']['api_attributes']='VORHANDEN; SIGNATUREN_WERDEN_DURCH_AUFRUFE_GETESTET'
        verify_output_paths(out,[geometry_name,master_name])
        preflight_filenames(nx,[geometry_name,master_name])
        part=nx.new_part(out/geometry_name,'FUNKTIONSTEST')
        data=read_json(base/'data'/'haus.json')
        # Alle 54 Hausparameter samt Winkel- und Abhaengigkeitsausdruecken testen.
        items=dict(data['parameters']);items['TEST_H']={'value':2650,'unit':'mm','status':'PLANWERT','sources':[]}
        params=Parameters(items);nx.add_parameters(part,params)
        result['parameter_metadata']=write_parameter_report(out,nx)
        result['checks']['expression_provenance']='AUF_PART_GESCHRIEBEN_KEIN_EXPRESSION_ATTRIBUTZUGRIFF'
        result['checks']['all_house_expressions']='ERZEUGT'
        meta={'id':'TESTWAND','status':'TESTGEOMETRIE_KEIN_HAUSBAUTEIL','sources':[]}
        wall=nx.xy_extrude(part,[[0,0],[3000,0],[3000,240],[0,240]],0,'TEST_H','TESTWAND',meta)[0]
        cut=nx.xy_extrude(part,[[1000,-1],[2000,-1],[2000,241],[1000,241]],-1,2010,'TEST_TUEROEFFNUNG',meta,target=wall)
        if len(cut)!=1:raise RuntimeError('Testwand nach Schnitt nicht genau ein Koerper')
        before=nx.bounding_box(cut[0])
        if abs(before[5]-2650)>0.1:raise RuntimeError('Falsche Ausgangshoehe '+str(before))
        # Marke VOR der Aenderung: kontrolliertes Ruecksetzen bei Updatefehlern.
        mark=nx.session.SetUndoMark(nx.N.Session.MarkVisibility.Invisible,'Hoehentest_R03')
        try:
            part.Expressions.FindObject('TEST_H').RightHandSide='2750'
            errors=nx.session.UpdateManager.DoUpdate(mark)
            if errors:raise RuntimeError('Updatefehler im Hoehentest: '+str(errors))
            after=nx.bounding_box(cut[0])
            if abs(after[5]-2750)>0.1:raise RuntimeError('Hoehenexpression steuert Modell nicht: '+str(after))
        except Exception:
            nx.session.UndoToMark(mark,None)
            raise
        finally:nx.session.DeleteUndoMark(mark,None)
        result['checks']['expression_z_2650_to_2750']='BESTANDEN'
        result['checks']['wall_boolean_opening']='COMMIT_UND_KOERPERANZAHL_BESTANDEN; VOLUMEN_NICHT_GEMESSEN'
        roof=nx.extrude(part,[[0,1000,3000],[1000,1000,3500],[1000,2000,3500],[0,2000,3000]],0,200,
                       'TEST_DACH',meta,direction=(0,0,-1))[0]
        bb=nx.bounding_box(roof)
        if abs(bb[2]-2800)>0.1 or abs(bb[5]-3500)>0.1:raise RuntimeError('Schraege negative Extrusion falsch: '+str(bb))
        result['checks']['sloped_negative_z_extrusion']='BESTANDEN'
        wedge={'id':'TEST_GAUBENWANGE','parent':'TEST','kind':'GAUBENWANGE',
               'polygon':[[4000,0],[5000,0],[5000,200],[4000,200]],
               'bottom':1000,'top':2600,'bottom_plane':[.4,0,-600],
               'top_plane':[.6,0,-400],'meta':meta}
        wedge_bodies=build_solid(nx,part,wedge,params)
        bb=nx.bounding_box(wedge_bodies[0])
        if abs(bb[2]-1000)>.1 or abs(bb[5]-2600)>.1:raise RuntimeError('Wangen-Test: Begrenzung falsch '+str(bb))
        result['checks']['sloped_wedge_two_plane_trims']='COMMIT_UND_BEGRENZUNGSBOX_BESTANDEN'
        from .haus_details import inserts_for
        wall_def={'id':'TESTFASSADE','a':[6000,0],'b':[9000,0],'thickness':365,'bottom':0}
        opening={'id':'TESTFENSTER','kind':'FENSTER','offset':750,'width':1500,'height':1500,'sill':800,'status':'GESCHAETZT','sources':[]}
        detail_bodies=0
        for solid in inserts_for(wall_def,opening,params,data['visual_defaults']):
            detail_bodies+=len(build_solid(nx,part,solid,params))
        if detail_bodies!=9:raise RuntimeError('Fenster-Test: neun getrennte Koerper erwartet')
        result['checks']['generic_window_nine_bodies']='BESTANDEN'
        # Zusaetzlich tatsaechliche Profile des aktuellen Hausdatensatzes pruefen.
        compiled=compile_house(data,True) if _compiled is None else _compiled
        solids=[s for p in compiled['parts'] for s in p['solids']]
        if solids:
            def shortest(s):
                pts=s.get('points',s.get('polygon'))
                return min(math.dist(a,b) for a,b in zip(pts,pts[1:]+pts[:1]))
            candidates=[min(solids,key=shortest),max(solids,key=lambda s:len(s.get('points',s.get('polygon'))))]
            for criterion in (lambda s:bool(s.get('roof_clip')),lambda s:bool(s.get('bottom_plane')),
                              lambda s:s['kind']=='DACH',lambda s:s['kind']=='GLAS'):
                selection=next((s for s in solids if criterion(s)),None)
                if selection is not None:candidates.append(selection)
            seen=set();sample_checks=[]
            for original in candidates:
                if original['id'] in seen:continue
                seen.add(original['id'])
                solid=dict(original,id='PROBE_'+original['id'])
                bodies=build_solid(nx,part,solid,params)
                actual=nx.bounding_box(bodies[0]);expected=_expected_bbox(solid,params)
                # UF-Box ist nur eine Boxpruefung, kein Volumennachweis.
                if max(abs(a-b) for a,b in zip(actual,expected))>0.2:
                    raise RuntimeError('Hausprofil-Probe mit abweichender Box: '+original['id']+' Ist='+str(actual)+' Soll='+str(expected))
                sample_checks.append({'source_id':original['id'],'box_check':'BESTANDEN'})
            result['checks']['actual_house_profile_samples']=sample_checks
        result['geometry']=nx.save(part)
        master=nx.new_part(out/master_name,'TEST_MASTER')
        nx.add_component(master,out/geometry_name,'TEST_GEOMETRIE')
        if len(master.ComponentAssembly.RootComponent.GetChildren())!=1:raise RuntimeError('Komponententest fehlgeschlagen')
        result['checks']['assembly_identity_placement']='ERZEUGT_UND_IDENTITAET_NUMERISCH_GEPRUEFT'
        nx.fit(master);result['master']=nx.save(master)
        for record in (result['geometry'],result['master']):
            if sha256_file(out/record['file'])!=record['sha256']:raise RuntimeError('Datei nach Speicherung veraendert')
        result['parameter_metadata']=write_parameter_report(out,nx)
        result['unit_checks']=list(nx.unit_checks)
        result['checks']['part_units']='BASEPART_UNITS_MILLIMETERS_BESTAETIGT'
        result['status']='NX_FUNKTIONSTEST_BESTANDEN'
        result['reopen']='NICHT_GETESTET; KEINE_TEILE_AUTOMATISCH_GESCHLOSSEN'
        dump(out/'testergebnis.json',result)
        if not _silent:
            nx.safe_message('NX-Funktionstest bestanden.\n'+str(out)+'\n\nJetzt 00_HAUS_ERZEUGEN_2406.py starten. '
                            'Der Hauptlauf prueft in seiner aktuellen Sitzung erneut. Testdateien sind keine Hausbauteile.')
    except Exception as ex:
        result['status']='NX_FUNKTIONSTEST_FEHLGESCHLAGEN';result['error']=str(ex);result['traceback']=traceback.format_exc()
        result['nx_operation']=nx.operation if nx is not None else 'INITIALISIERUNG'
        result['unit_checks']=list(nx.unit_checks) if nx is not None else []
        result['attribute_failures']=list(nx.attribute_failures) if nx is not None else []
        if nx is not None and 'checks' in result and isinstance(result['checks'],dict):
            try:result['parameter_metadata']=write_parameter_report(out,nx)
            except Exception as report_error:result['parameter_metadata_report_error']=str(report_error)
        dump(out/'testergebnis.json',result);log(result['traceback'])
        if nx is not None:
            nx.restore_display_after_failure()
            if not _silent:nx.safe_message(str(ex)+'\n\n'+str(out/'laufprotokoll.txt'),True)
        raise
    return result


def check_saved_house(base, _adapter_factory=None):
    base=Path(base)
    pointer=read_json(base/'LETZTER_ERFOLGREICHER_LAUF.json')
    out=absolute_path(pointer['directory']);manifest=read_json(out/'manifest.json')
    check_name='pruefung_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
    log=Log(out/(check_name+'.log'));nx=None
    result={'status':'LAEUFT','revision':'MAIN01','patch':PATCH,'path_policy':PATH_POLICY,'checks':[],
            'scope':'Datei-Hashes, Prototyppfade, Identitaetslage, Vollstaendigladen, Koerperanzahl. KEINE Planfreigabe.'}
    try:
        verify_saved_files(out,manifest)
        result['parameter_metadata_check']=check_parameter_report(out,manifest)
        master_path=out/'HAUS_MASTER.prt'
        if path_key(pointer['master'])!=path_key(master_path):raise ValueError('Ergebniszeiger passt nicht zum Manifest.')
        nx=(_adapter_factory or NXAdapter)(log);log.nx=nx
        master=None
        for loaded in nx.session.Parts:
            if loaded.FullPath and path_key(loaded.FullPath)==path_key(master_path):master=loaded;break
        if master is None:
            filenames=[f['file'] for f in manifest['files']]
            # Gleichnamige Teile aus einem anderen Lauf nicht versehentlich binden.
            for loaded in nx.session.Parts:
                if loaded.FullPath and Path(loaded.FullPath).name.casefold() in {x.casefold() for x in filenames}:
                    if path_key(Path(loaded.FullPath).parent)!=path_key(out):
                        raise RuntimeError('Gleichnamiges Teil aus anderem Ordner geladen: '+loaded.FullPath)
            master,status=nx.session.Parts.OpenDisplay(str(master_path))
            try:
                if master is None:raise RuntimeError('Master konnte nicht geoeffnet werden')
                if status is None:raise RuntimeError('OpenDisplay lieferte keinen Ladestatus')
                if status.NumberUnloadedParts:raise RuntimeError('Nicht alle Dateien geladen')
            finally:nx.dispose(status)
            result['reopen']='AUS_DATEI_GEOEFFNET'
        else:result['reopen']='BEREITS_GELADEN; WIEDEROEFFNUNG_NICHT_GETESTET'
        nx.load_fully(master)
        nx.check_millimeters(master,'HAUS_MASTER (Nachpruefung)')
        root=master.ComponentAssembly.RootComponent
        if root is None:raise RuntimeError('Master enthaelt keine Baugruppe')
        children=list(root.GetChildren())
        if len(children)!=manifest['component_count']:raise RuntimeError('Falsche Komponentenanzahl')
        expected={f['file']:f for f in manifest['files'] if f['file']!='HAUS_MASTER.prt'}
        visited=set()
        for child in children:
            proto=child.Prototype
            if proto is None:raise RuntimeError('Komponenten-Prototyp fehlt: '+child.Name)
            path=absolute_path(proto.FullPath);name=path.name
            if name not in expected or path_key(path.parent)!=path_key(out):raise RuntimeError('Falscher Komponentenpfad '+str(path))
            if name in visited:raise RuntimeError('Doppelte Komponente statt fehlendem Geschoss: '+name)
            visited.add(name)
            nx.load_fully(proto);nx.check_identity(child)
            nx.check_millimeters(proto,'Komponente '+name)
            bodies=list(proto.Bodies)
            if len(bodies)!=expected[name]['bodies']:raise RuntimeError('Koerperanzahl abweichend '+name)
            if any(not b.IsSolidBody for b in bodies):raise RuntimeError('Flaechenkoerper in '+name)
            result['checks'].append({'file':name,'bodies':len(bodies),'status':'BESTANDEN'})
        if visited!=set(expected):raise RuntimeError('Mindestens eine erwartete Komponente fehlt')
        result['unit_checks']=list(nx.unit_checks)
        result['status']='DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN'
        dump(out/(check_name+'.json'),result)
        nx.safe_message('Datei-/Strukturpruefung bestanden.\n'+result['reopen']+'\n\nBauteillage, Dachanschluesse und Masse weiterhin anhand der Plaene pruefen.')
    except Exception as ex:
        result['status']='PRUEFUNG_FEHLGESCHLAGEN';result['error']=str(ex);result['traceback']=traceback.format_exc()
        result['unit_checks']=list(nx.unit_checks) if nx is not None else []
        result['attribute_failures']=list(nx.attribute_failures) if nx is not None else []
        if nx is not None and 'checks' in result and isinstance(result['checks'],dict):
            try:result['parameter_metadata']=write_parameter_report(out,nx)
            except Exception as report_error:result['parameter_metadata_report_error']=str(report_error)
        dump(out/(check_name+'.json'),result);log(result['traceback'])
        if nx is not None:nx.safe_message(str(ex),True)
        raise
    return result
