"""R11a bounded work/diagnostics regression tests. No real NX timing claims."""
import contextlib
import copy
import io
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_r09 import BASE,CONFIG,JOB,SceneDouble,FakeNXException,Object
from r09.core import read_json,write_json,sha256
from r09.quick_check import inspection_plan,grid_selection,BASIC_STATUS
from r09.vegetation_review import selected_job
from r09.performance import (DEFAULTS,policy_checked,RunMonitor,StopRequested,
    FastHouseAdapter,FastSceneAdapter,run_optimized_project,QuietLog)
from haus2406_r03.haus_metadata import object_attributes
from haus2406_r03.haus_run import Log as HouseLog


class PolicyAndSamplingTests(unittest.TestCase):
    def test_01_default_is_explicitly_basic(self):
        self.assertEqual(policy_checked(DEFAULTS)['surface_validation'],'BASIS')
    def test_02_unknown_policy_rejected(self):
        p=copy.deepcopy(DEFAULTS);p['ignore_errors']=True
        with self.assertRaises(ValueError):policy_checked(p)
    def test_03_invalid_level_rejected(self):
        p=copy.deepcopy(DEFAULTS);p['surface_validation']='NONE'
        with self.assertRaises(ValueError):policy_checked(p)
    def test_04_no_truthy_strings(self):
        p=copy.deepcopy(DEFAULTS);p['defer_project_attributes']='false'
        with self.assertRaises(ValueError):policy_checked(p)
    def test_05_real_active_source_counts(self):
        job,_=selected_job(BASE,JOB)
        self.assertEqual(sum(p['geometry_reference']['sample_count'] for p in job['parts']),20883)
        self.assertEqual(sum(sum(map(len,inspection_plan(p)[1])) for p in job['parts']),1312)
    def test_06_dgm_147_of_16748_original_points(self):
        p=next(s for s in JOB['parts'] if s['id']=='DGM');ref,indices=inspection_plan(p)
        self.assertEqual(len(indices[0]),147);self.assertEqual(ref['sample_count'],16748)
    def test_07_corners_and_height_extrema_included(self):
        p=next(s for s in JOB['parts'] if s['id']=='DGM');row=p['geometry_reference']['sheets'][0]
        indices=grid_selection(row,9);r,c=row['grid_shape'];points=row['samples_mm']
        for i in (0,c-1,(r-1)*c,r*c-1,min(range(len(points)),key=lambda i:points[i][2]),
                  max(range(len(points)),key=lambda i:points[i][2])):self.assertIn(i,indices)
    def test_08_nodes_and_midpoints_used(self):
        p=next(s for s in JOB['parts'] if s['id']=='DGM');row=p['geometry_reference']['sheets'][0]
        indices=grid_selection(row,9);node_count=math.prod(row['grid_shape'])
        self.assertTrue(any(i>=node_count for i in indices));self.assertTrue(any(i<node_count for i in indices))
    def test_09_all_selected_points_refer_to_original_rows(self):
        original=copy.deepcopy(JOB)
        for p in JOB['parts']+[JOB['smoke_test']]:
            ref,selected=inspection_plan(p)
            for row,indices in zip(ref['sheets'],selected):
                self.assertEqual(indices,sorted(set(indices)))
                self.assertTrue(all(0<=i<len(row['samples_mm']) for i in indices))
        self.assertEqual(JOB,original)
    def test_10_full_small_cell_retained(self):
        row={'grid_shape':[2,2],'samples_mm':[[0,0,0],[1,0,0],[0,1,0],[1,1,0],[.5,.5,0]]}
        self.assertEqual(grid_selection(row,3),list(range(5)))
    def test_11_wrong_reference_hash_is_not_skipped(self):
        s=copy.deepcopy(JOB['smoke_test']);s['sha256']='x'
        with self.assertRaises(ValueError):inspection_plan(s)
    def test_12_tolerance_is_not_relaxed(self):
        s=copy.deepcopy(JOB['smoke_test']);s['geometry_reference']['distance_tolerance_mm']=5
        with self.assertRaises(ValueError):inspection_plan(s)
    def test_13_selection_reproducible(self):
        for p in JOB['parts']:self.assertEqual(inspection_plan(p)[1],inspection_plan(copy.deepcopy(p))[1])


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_14_current_action_written_before_kernel_call(self):
        m=RunMonitor(self.root)
        with m.stage('KERNEL','LANGER_AUFRUF'):
            row=read_json(m.status_file);self.assertEqual(row['current']['label'],'LANGER_AUFRUF')
            self.assertTrue(row['updates_only_between_NX_calls'])
    def test_15_elapsed_timing_not_estimated(self):
        clock=[100.];m=RunMonitor(self.root,clock=lambda:clock[0])
        with m.stage('TEST','ZEIT'):clock[0]+=5
        self.assertEqual(m.timings['TEST']['total'],5.)
    def test_16_cancellation_before_next_call(self):
        m=RunMonitor(self.root);m.stop_file.write_text('stop')
        with self.assertRaises(StopRequested):
            with m.stage('TEST','NO_CALL'):self.fail('must not run')
    def test_17_stop_during_call_waits_until_return(self):
        m=RunMonitor(self.root);returned=[]
        with self.assertRaises(StopRequested):
            with m.stage('TEST','CALL'):
                m.stop_file.write_text('stop');returned.append(True)
        self.assertTrue(returned);self.assertTrue(m.cancelled)
    def test_18_errors_recorded_without_success(self):
        m=RunMonitor(self.root)
        with self.assertRaisesRegex(RuntimeError,'ORIGINAL'):
            with m.stage('TEST','FAIL'):raise RuntimeError('ORIGINAL')
        self.assertEqual(read_json(m.status_file)['last_completed']['status'],'FEHLER')
    def test_19_quiet_log_keeps_details_in_file(self):
        backend=HouseLog(self.root/'full.txt');messages=[]
        backend.nx=type('NX',(),{'session':type('S',(),{'ListingWindow':type('L',(),{'WriteLine':lambda _,s:messages.append(s)})()})()})()
        quiet=QuietLog(backend)
        with contextlib.redirect_stdout(io.StringIO()):
            quiet('  KOERPER_A | P01');quiet('Teil 1/16: EG')
        self.assertIn('KOERPER_A',(self.root/'full.txt').read_text());self.assertEqual(len(messages),1)


class PerformanceNXDoubleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.definition=self.root/'step214ug.def';self.definition.write_text('SIMULATION ONLY')
        self.env=SceneDouble(self.definition)
        self.env.N.Update.Option.Later='LATER_TEST_ENUM'
        self.monitor=RunMonitor(self.root)
    def adapter(self,level='BASIS'):
        p=copy.deepcopy(DEFAULTS);p['surface_validation']=level
        return FastSceneAdapter(lambda s:None,self.monitor,p)
    def imported(self,level='BASIS',spec=None):
        with self.env.active():
            nx=self.adapter(level);out=self.root/'imports';out.mkdir(exist_ok=True)
            source=spec or JOB['smoke_test']
            return nx.import_surface_part(out,BASE/source['step_file'],source,self.definition)
    def test_20_basic_never_calls_area_integration(self):
        self.env.primary_fail=True;self.env.uf_fail=True
        p,s,c=self.imported()
        self.assertEqual(self.env.face_measure_calls,0);self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(c['geometry_validation_status'],BASIC_STATUS)
        self.assertFalse(c['area_check_performed']);self.assertEqual(c['checked_source_points'],23)
    def test_21_intensive_retains_original_area_and_points(self):
        p,s,c=self.imported('INTENSIV')
        self.assertEqual(c['checked_source_points'],58);self.assertEqual(self.env.face_measure_calls,4)
    def test_22_intensive_does_not_swallow_integration_failure(self):
        self.env.primary_fail=True;self.env.uf_fail=True
        with self.assertRaises(RuntimeError):self.imported('INTENSIV')
    def test_23_basic_rejects_missing_body(self):
        self.env.skip_last=True
        with self.assertRaises(ValueError):self.imported()
    def test_24_basic_rejects_extra_body(self):
        self.env.extra_sheet=True
        with self.assertRaises(ValueError):self.imported()
    def test_25_basic_rejects_wrong_scale(self):
        self.env.step_scale=.001
        with self.assertRaises(ValueError):self.imported()
    def test_26_basic_rejects_solid_instead_of_sheet(self):
        self.env.step_solids=True
        with self.assertRaises(RuntimeError):self.imported()
    def test_27_basic_rejects_empty_face_list(self):
        self.env.empty_faces=True
        with self.assertRaises(RuntimeError):self.imported()
    def test_28_basic_rejects_point_deviation(self):
        self.env.distance=.251
        with self.assertRaisesRegex(RuntimeError,'Quellpunktabweichung'):self.imported()
    def test_29_basic_accepts_within_original_tolerance(self):
        self.env.distance=.2
        _,_,c=self.imported();self.assertLessEqual(c['max_point_distance_mm'],.25)
    def test_30_basic_split_faces_are_not_full_verified(self):
        self.env.split_spec={'TEST':1}
        _,_,c=self.imported();self.assertTrue(c['face_count_changed']);self.assertFalse(c['full_reference_check_performed'])
    def test_31_scope_stored_on_part(self):
        part,_,_=self.imported()
        self.assertEqual(part.attrs['HAUS_IMPORTPRUEFUNG'],'BASIS')
        self.assertEqual(part.attrs['HAUS_FLAECHENINHALT_GEPRUEFT'],'False')
    def test_32_deferred_attribute_has_mandatory_save_update(self):
        with self.env.active():
            nx=self.adapter();part=nx.new_part(self.root/'part.prt','X');events=[]
            original=part.SetUserAttribute
            def setter(k,i,v,opt):events.append(('ATTRIBUTE',opt));return original(k,i,v,opt)
            part.SetUserAttribute=setter
            nx._set_user_attribute(part,'HAUS_TEST','value','X')
            update=nx.update
            def tracked(label):events.append(('UPDATE',label));return update(label)
            nx.update=tracked;nx.save(part)
            self.assertEqual(events[0],('ATTRIBUTE','LATER_TEST_ENUM'))
            self.assertTrue(any(x[0]=='UPDATE' for x in events));self.assertEqual(part.attrs['HAUS_TEST'],'value')
    def test_33_missing_later_uses_now(self):
        del self.env.N.Update.Option.Later
        with self.env.active():
            nx=self.adapter();self.assertFalse(nx._deferred_attributes)
            part=nx.new_part(self.root/'part.prt','X')
            self.assertGreater(self.monitor.counters.get('attribute_writes_now',0),0)
    def test_34_deferred_attribute_errors_not_ignored(self):
        with self.env.active():
            nx=self.adapter();part=nx.new_part(self.root/'part.prt','X')
            with patch.object(part,'SetUserAttribute',side_effect=FakeNXException('INJECTED_ATTRIBUTE')):
                with self.assertRaisesRegex(RuntimeError,'INJECTED_ATTRIBUTE'):
                    nx._set_user_attribute(part,'HAUS_TEST','x','X')
    def test_35_intermediate_dialogs_are_logged_not_modal(self):
        with self.env.active():
            nx=self.adapter();before=len(self.env.messages);nx.safe_message('Erzeugt TEST')
            self.assertEqual(len(self.env.messages),before)
    def test_36_estimates_consent_is_not_bypassed(self):
        with self.env.active():
            nx=self.adapter();nx.review_consent();self.assertTrue(self.env.messages)
    def test_37_basic_does_not_change_source_geometry(self):
        sources={p['step_file']:sha256(BASE/p['step_file']) for p in JOB['parts']}
        self.imported()
        self.assertTrue(all(sha256(BASE/p)==h for p,h in sources.items()))
    def test_38_no_source_area_substitution(self):
        part,_,c=self.imported();report=read_json(c['geometry_report'])
        self.assertTrue(all('actual_area_mm2' not in s for s in report['sheets_checked']))
    def test_39_cancel_before_import(self):
        self.monitor.stop_file.write_text('stop')
        with self.assertRaises(StopRequested):self.imported()
        self.assertEqual(self.env.step_calls,0)


class OptimizedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.definition=self.root/'step214ug.def';self.definition.write_text('SIMULATION ONLY')
        self.env=SceneDouble(self.definition);self.env.N.Update.Option.Later='LATER_TEST_ENUM'
    def cfg(self):
        c=copy.deepcopy(CONFIG);c['output_root']=str(self.root/'runs');c['step_settings_file']=str(self.definition);return c
    def writer(self,path,data):
        p=Path(path)
        if p.parent==BASE and p.name.startswith('LETZTER_'):p=self.root/p.name
        return write_json(p,data)
    def run_workflow(self,mode='ALL'):
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()),\
             patch('r09.workflow.write_json',side_effect=self.writer),\
             patch('r09.run.write_json',side_effect=self.writer),\
             patch('r09.performance.write_json',side_effect=self.writer):
            return run_optimized_project(BASE,mode,DEFAULTS,self.cfg(),final_dialog=False)
    def test_40_all_keeps_1361_house_bodies_and_5_source_parts(self):
        state=self.run_workflow()
        result=state['model_result'];self.assertEqual(result['house']['built_solids'],1361)
        self.assertEqual(self.env.step_calls,6)
        self.assertEqual(result['environment']['checked_source_points'],1312)
        self.assertEqual(self.env.distance_calls,1335);self.assertEqual(self.env.face_measure_calls,0)
        self.assertEqual(self.env.mass_calls,0);self.assertEqual(state['status'],'ERZEUGT_BASISPRUEFUNG_VOLLPRUEFUNG_OFFEN')
        self.assertFalse(result['environment']['surface_area_check_performed'])
        self.assertTrue(result['project_reference_master']);self.assertFalse(result.get('physical_site_alignment_verified'))
    def test_41_house_only_no_import_or_area(self):
        state=self.run_workflow('HOUSE');self.assertEqual(self.env.step_calls,0)
        self.assertEqual(state['model_result']['house']['built_solids'],1361)
        self.assertIsNone(state['model_result']['environment'])
    def test_42_environment_only_has_all_selected_sheets(self):
        state=self.run_workflow('ENVIRONMENT');self.assertIsNone(state['model_result']['house'])
        self.assertEqual(self.env.step_calls,6);self.assertEqual(self.env.distance_calls,1335)
    def test_43_import_failure_preserves_house(self):
        self.env.fail_step_at=1
        with self.assertRaisesRegex(RuntimeError,'INJECTED_STEP') as error:self.run_workflow()
        ctx=error.exception.r11a_context;self.assertTrue(Path(ctx['saved_house_master']).is_file())
        self.assertFalse((self.root/'LETZTER_LAUF_R11a.json').exists())
        self.assertEqual(read_json(ctx['manifest'])['status'],'ABBRUCH_KEIN_GESAMTERFOLG')
    def test_44_no_empty_success_after_house_failure(self):
        self.env.fail_commit_at=1
        with self.assertRaises(Exception):self.run_workflow('HOUSE')
        self.assertFalse((self.root/'LETZTER_LAUF_R11a.json').exists());self.assertEqual(self.env.step_calls,0)
    def test_45_new_entry_points_use_performance_wrapper(self):
        for name in ('00_NX_MODELL_ERZEUGEN_2406.py','01_NUR_HAUS_ERZEUGEN_2406.py','02_NUR_UMGEBUNG_ERZEUGEN_2406.py'):
            self.assertIn('from r09.performance import run_optimized_project as run_checked_project',(BASE/name).read_text())
    def test_46_cancel_new_run_never_overwrites_old(self):
        marker=self.root/'existing.prt';marker.write_bytes(b'USER FILE')
        self.run_workflow('ENVIRONMENT');self.assertEqual(marker.read_bytes(),b'USER FILE')

class DeferredQueueTests(unittest.TestCase):
    def test_47_later_queue_is_flushed_before_save_and_matches_now(self):
        """Unlike the old double, this test really delays setting the attributes."""
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);definition=root/'step214ug.def';definition.write_text('TEST')
            env=SceneDouble(definition);env.N.Update.Option.Later='LATER_QUEUE'
            monitor=RunMonitor(root);pending=[];original_set=Object.SetUserAttribute
            original_update=env.session.UpdateManager.DoUpdate
            def deferred(obj,key,index,value,option):
                if option=='LATER_QUEUE':pending.append((obj,key,index,value));return
                return original_set(obj,key,index,value,option)
            def flush(mark):
                count=original_update(mark)
                if count==0:
                    for obj,key,index,value in pending:original_set(obj,key,index,value,env.N.Update.Option.Now)
                    pending.clear()
                return count
            with env.active(),patch.object(Object,'SetUserAttribute',new=deferred):
                env.session.UpdateManager.DoUpdate=flush
                nx=FastHouseAdapter(lambda t:None,monitor,DEFAULTS)
                part=nx.new_part(root/'fast.prt','FAST');self.assertTrue(pending);self.assertNotIn('HAUS_ID',part.attrs)
                nx._set_user_attribute(part,'HAUS_TEST','keep complete source','TEST')
                nx.save(part)
                self.assertFalse(pending);self.assertEqual(part.attrs['HAUS_ID'],'FAST')
                self.assertEqual(part.attrs['HAUS_TEST'],'keep complete source')
                expected=object_attributes({'id':'FAST','status':'PRUEFMODELL','phase':'UNGEKLAERT','sources':[],
                    'construction_status':'UNVOLLSTAENDIGE_QUELLENREKONSTRUKTION','as_built_verified':False})
                self.assertTrue(all(part.attrs[k]==v for k,v in expected.items()))
    def test_48_diagnostic_io_failure_does_not_hide_geometry_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            monitor=RunMonitor(tmp)
            with self.assertRaisesRegex(RuntimeError,'REAL_GEOMETRY_ERROR') as caught:
                with monitor.stage('TEST','FAIL'):
                    monitor.event=lambda *a:(_ for _ in ()).throw(OSError('LOG_IO_ERROR'))
                    raise RuntimeError('REAL_GEOMETRY_ERROR')
            self.assertIn('LOG_IO_ERROR',caught.exception.r11a_diagnostic_error)
