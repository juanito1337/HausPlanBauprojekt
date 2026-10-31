# -*- coding: utf-8 -*-
"""G01a regression tests. All .prt files here are explicitly temporary TESTDOUBLES.
NX point responses are synthetic. They do NOT establish a root cause in NX.
"""
import contextlib
import copy
import importlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

B=Path(__file__).absolute().parents[1]
E=B/'umgebung'
sys.path[:0]=[str(B),str(E),str(E/'tests')]
from test_r09 import SceneDouble,JOB
from uv_double import install_uv_double
from gesamt.core import read_json,write_json,child_exception_context
from gesamt.terrain_audit import (make_audited_adapter,TerrainTrace,REPORT_NAME,EVENT_NAME,
                                 TRACE_ATTR,json_safe)
from gesamt.terrain_only import run_terrain_only
from gesamt.nx_backend import NXBackend
from gesamt import dgm_probe
from r09.performance import FastSceneAdapter,RunMonitor,DEFAULTS
from r09.core import sha256
SPEC=next(x for x in JOB['parts'] if x['id']=='DGM')
SOURCE=E/SPEC['step_file']
REFERENCE=B/'data/DGM_REFERENZPUNKTE_G01a.json'


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.definition=self.root/'step214ug.def'
        self.definition.write_text('TESTDOUBLE_ONLY_NOT_NX_DEF')
        self.env=SceneDouble(self.definition);self.uv_control=install_uv_double(self.env);self.policy=copy.deepcopy(DEFAULTS)
        self.target=make_audited_adapter(FastSceneAdapter,REFERENCE)
    def adapter(self,out):
        out.mkdir(exist_ok=True)
        return self.target(lambda t:None,RunMonitor(out),self.policy)
    def invoke(self,a,out):
        return a.import_surface_part(out,SOURCE,SPEC,self.definition)
    def report(self,out):return read_json(out/REPORT_NAME)
    def replay_bug(self):
        """Synthetic previous-query target; face responses are accurate by construction."""
        prev=[None]
        def query(null,tag,g1,p,g2,guess):
            self.env.distance_calls+=1
            body=tag in self.env.objects and hasattr(self.env.objects[tag],'_reference')
            if body:
                q=list(prev[0]) if prev[0] is not None and p==SPEC['geometry_reference']['sheets'][0]['samples_mm'][1089] else list(p)
                prev[0]=list(p)
            else:q=list(p)
            box=SPEC['face_bounding_boxes_mm'][0]
            if p[2]>box[5]:q[2]=box[5]
            return (math.dist(p,q),list(p),q)
        self.env.uf.Modeling.AskMinimumDist=query
    def test_01_terrain_source_in_package(self):
        self.assertTrue(SOURCE.is_file());self.assertEqual(sha256(SOURCE),SPEC['sha256'])
    def test_02_points_match_delivered_source(self):
        ref=dgm_probe.load_reference(REFERENCE)
        self.assertEqual(ref['source_sha256'],SPEC['sha256'])
        for idx,p in ref['points'].items():self.assertLess(math.dist(p,SPEC['geometry_reference']['sheets'][0]['samples_mm'][int(idx)]),1e-8)
    def test_03_normal_import_is_automatic_and_passes(self):
        out=self.root/'run'
        with self.env.active():
            part,saved,check=self.invoke(self.adapter(out),out)
        self.assertEqual(self.env.step_calls,1)
        self.assertEqual(check['checked_source_points'],147)
        r=self.report(out)
        self.assertTrue(r['selected_checks_passed']);self.assertFalse(r['geometry_release'])
        self.assertEqual(r['regular_calls_finished'],147)
        self.assertTrue(Path(part.FullPath).is_file())
    def test_04_snapshot_exists_before_first_distance_call(self):
        out=self.root/'run';seen=[];original=self.env.uf.Modeling.AskMinimumDist
        def query(*args):
            r=self.report(out);seen.append(r['unverified_snapshot']['exists'])
            self.assertTrue(Path(r['unverified_snapshot']['path']).is_file())
            self.assertEqual(read_json(out/REPORT_NAME)['active_query']['status'],'NX_AUFRUF_LAEUFT')
            return original(*args)
        self.env.uf.Modeling.AskMinimumDist=query
        with self.env.active():self.invoke(self.adapter(out),out)
        self.assertEqual(len(seen),147);self.assertTrue(all(seen))
    def test_05_every_query_has_raw_return_and_endpoints(self):
        out=self.root/'run'
        with self.env.active():self.invoke(self.adapter(out),out)
        events=[json.loads(s) for s in (out/EVENT_NAME).read_text().splitlines()]
        for kind in ['PUNKT_VOR_NX','NX_ROHRUECKGABE','PUNKT_NACH_NX']:
            self.assertEqual(sum(e['kind']==kind for e in events),147)
        last=next(e['data'] for e in reversed(events) if e['kind']=='PUNKT_NACH_NX')
        self.assertIn('returned_target_mm',last);self.assertIn('returned_input_mm',last)
    def test_06_failure_keeps_original_and_automatically_probes(self):
        out=self.root/'run';self.replay_bug()
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'BASIS-Quellpunktabweichung') as caught:
            self.invoke(self.adapter(out),out)
        r=self.report(out)
        self.assertEqual(r['regular_calls_finished'],12)
        self.assertEqual(r['additional_diagnostic']['planned_calls'],31)
        self.assertEqual(r['additional_diagnostic']['completed_calls'],31)
        self.assertFalse(r['geometry_release'])
        self.assertIn(TRACE_ATTR,child_exception_context(caught.exception))
        self.assertTrue(Path(r['unverified_snapshot']['path']).is_file())
        self.assertIsNone(r['final_saved_part'])
    def test_07_original_bad_target_is_preserved(self):
        out=self.root/'run';self.replay_bug()
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke(self.adapter(out),out)
        row=self.report(out)['last_query']
        self.assertAlmostEqual(row['distance_mm'],10003.64433569,places=3)
        self.assertEqual(row['target_distance_to_previous_query_mm'],0.)
        self.assertEqual(row['returned_target_mm'],row['previous_query_mm'])
    def test_08_no_source_coordinates_mutated(self):
        out=self.root/'run';before=copy.deepcopy(SPEC)
        with self.env.active():self.invoke(self.adapter(out),out)
        self.assertEqual(SPEC,before)
    def test_09_production_flags_unchanged_fresh_arrays(self):
        out=self.root/'run';original=self.env.uf.Modeling.AskMinimumDist;args_saved=[]
        def query(n,t,g1,p,g2,q):
            args_saved.append((p,q));self.assertEqual((n,g1,g2),(0,1,0));self.assertEqual(q,[0,0,0])
            return original(n,t,g1,p,g2,q)
        self.env.uf.Modeling.AskMinimumDist=query
        with self.env.active():self.invoke(self.adapter(out),out)
        self.assertEqual(len({id(p) for p,q in args_saved}),147)
    def test_10_wrong_body_count_is_not_accepted(self):
        self.env.extra_sheet=True;out=self.root/'run'
        with self.env.active(),self.assertRaises(ValueError):self.invoke(self.adapter(out),out)
        self.assertFalse(self.report(out)['geometry_release'])
    def test_11_source_missing_no_part_created(self):
        out=self.root/'run'
        with self.env.active(),self.assertRaises(FileNotFoundError):
            self.adapter(out).import_surface_part(out,self.root/'missing.step',SPEC,self.definition)
        self.assertEqual(self.env.step_calls,0)
        self.assertFalse(self.report(out)['source']['exists'])
    def test_12_wrong_source_checksum_rejected(self):
        out=self.root/'run';bad=self.root/'bad.step';bad.write_text('not STEP')
        with self.env.active(),self.assertRaises(ValueError):self.adapter(out).import_surface_part(out,bad,SPEC,self.definition)
        self.assertEqual(self.env.step_calls,0)
    def test_13_import_exception_logged_without_snapshot_claim(self):
        out=self.root/'run';self.env.fail_step_at=1
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'INJECTED_STEP'):
            self.invoke(self.adapter(out),out)
        r=self.report(out);self.assertIsNone(r['unverified_snapshot']);self.assertIn('INJECTED_STEP',r['error'])
    def test_14_zero_distance_with_wrong_input_rejected(self):
        out=self.root/'run'
        self.env.uf.Modeling.AskMinimumDist=lambda n,t,g,p,g2,q:(0.,[0.,0.,0.],[0.,0.,0.])
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Eingangspunkt'):
            self.invoke(self.adapter(out),out)
        self.assertIn('raw_nx_result',self.report(out)['last_query'])
    def test_15_malformed_nx_return_saved_before_error(self):
        out=self.root/'run';self.env.uf.Modeling.AskMinimumDist=lambda *a:(None,)
        with self.env.active(),self.assertRaises(ValueError):self.invoke(self.adapter(out),out)
        self.assertEqual(self.report(out)['last_query']['raw_nx_result'],[None])
    def test_16_probe_error_does_not_hide_original(self):
        out=self.root/'run';self.replay_bug()
        with self.env.active(),patch('gesamt.dgm_probe.run_measurements',side_effect=RuntimeError('PROBE_FAILURE')):
            with self.assertRaisesRegex(RuntimeError,'BASIS-Quellpunktabweichung'):
                self.invoke(self.adapter(out),out)
        self.assertEqual(self.report(out)['additional_diagnostic_error']['error'],'PROBE_FAILURE')
    def test_17_save_failure_has_no_false_snapshot(self):
        out=self.root/'run'
        with self.env.active():
            a=self.adapter(out)
            with patch.object(a,'save',side_effect=RuntimeError('SAVE_FAILURE')),self.assertRaisesRegex(RuntimeError,'SAVE_FAILURE'):
                self.invoke(a,out)
        self.assertIsNone(self.report(out)['unverified_snapshot'])
    def test_18_existing_output_not_overwritten(self):
        out=self.root/'run';out.mkdir();part=out/SPEC['part_file'];part.write_text('USER_FILE')
        with self.env.active(),self.assertRaises(FileExistsError):self.invoke(self.adapter(out),out)
        self.assertEqual(part.read_text(),'USER_FILE')
    def test_19_non_dgm_has_no_checkpoint(self):
        out=self.root/'run';smoke=JOB['smoke_test']
        with self.env.active():a=self.adapter(out);a.import_surface_part(out,E/smoke['step_file'],smoke,self.definition)
        self.assertFalse((out/REPORT_NAME).exists())
    def test_20_reused_diagnostic_path_rejected(self):
        out=self.root/'run';out.mkdir()
        TerrainTrace(out,SOURCE,SPEC,self.definition)
        with self.assertRaises(FileExistsError):TerrainTrace(out,SOURCE,SPEC,self.definition)
    def test_21_tolerance_not_relaxed(self):
        self.assertEqual(dgm_probe.TOLERANCE_MM,.25)
        out=self.root/'run';self.env.distance=.251
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke(self.adapter(out),out)
        self.assertEqual(self.report(out)['acceptance_limit_mm'],.25)
    def test_22_standalone_builds_only_dgm_and_does_not_require_prior_prt(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'only')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            r=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertIsNone(r['house']);self.assertIsNone(r['environment']);self.assertIsNone(r['project'])
        self.assertEqual(self.env.step_calls,1)
        self.assertTrue(r['no_environment_completion_pointer_written'])
        self.assertTrue(Path(r['terrain']['file']['path']).is_file())
    def test_23_standalone_can_run_twice_without_closing_old_dgm(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'twice')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            r1=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
            r2=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertNotEqual(r1['terrain']['file']['path'],r2['terrain']['file']['path'])
        self.assertEqual(self.env.step_calls,2)
    def test_24_standalone_failed_report_embeds_diagnostic(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'fail');self.uv_control.uv_failure='G01b_INJECTED_UV_FAILURE'
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()),self.assertRaises(RuntimeError) as c:
            run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertIn(TRACE_ATTR,child_exception_context(c.exception))
        self.assertTrue(c.exception.gesamt_g01_context['house_not_rebuilt'])
    def test_25_json_safe_preserves_nan_as_diagnostic(self):
        self.assertEqual(json_safe(float('nan')),{'non_finite_repr':'nan'})
    def test_26_snapshot_is_unverified_and_not_final_record(self):
        out=self.root/'run'
        with self.env.active():part,saved,check=self.invoke(self.adapter(out),out)
        r=self.report(out)
        self.assertNotEqual(r['unverified_snapshot']['path'],r['final_saved_part']['path'])
        self.assertFalse(r['unverified_snapshot']['assembly_use_allowed'])
    def test_27_snapshot_stage_does_not_save_foreign_part(self):
        out=self.root/'run'
        with self.env.active():
            a=self.adapter(out)
            foreign=self.env.session.Parts.NewDisplay(str(self.root/'foreign.prt'),self.env.N.Part.Units.Millimeters)
            trace=TerrainTrace(out,SOURCE,SPEC,self.definition)
            with self.assertRaisesRegex(RuntimeError,'nicht in diesem Adapter'):
                a._save_import_checkpoint(foreign,trace)
        self.assertFalse((self.root/'foreign.prt').exists())
    def test_28_pre_nx_event_remains_when_native_call_raises(self):
        out=self.root/'run'
        def bad(*args):raise RuntimeError('SIMULATED_NATIVE_ERROR')
        self.env.uf.Modeling.AskMinimumDist=bad
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'SIMULATED_NATIVE_ERROR'):
            self.invoke(self.adapter(out),out)
        rows=[json.loads(s) for s in (out/EVENT_NAME).read_text().splitlines()]
        self.assertTrue(any(r['kind']=='PUNKT_VOR_NX' for r in rows))
        self.assertEqual(self.report(out)['last_query']['error'],'SIMULATED_NATIVE_ERROR')
    def test_29_checkpoint_hash_identical_copy(self):
        out=self.root/'run'
        with self.env.active():self.invoke(self.adapter(out),out)
        r=self.report(out)
        self.assertEqual(r['unverified_snapshot']['sha256'],r['own_part_checkpoint']['sha256'])
    def test_30_no_more_accurate_result_auto_selected(self):
        out=self.root/'run';self.replay_bug()
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'BASIS-Quellpunktabweichung'):
            self.invoke(self.adapter(out),out)
        r=self.report(out)
        good=[p for p in r['additional_diagnostic']['measurements'] if p['method']=='FACE_MIT_STARTPUNKT' and p['source_index_zero_based']==1089]
        self.assertEqual(good[0]['distance_mm'],0.)
        self.assertFalse(r['geometry_release']);self.assertIsNone(r['final_saved_part'])

    def test_31_stop_request_skips_additional_native_queries(self):
        out=self.root/'run';calls=[]
        def request_stop(n,t,g1,p,g2,q):
            calls.append(True)
            (out/'STOP_R11a.txt').touch()
            return (1.,list(p),[p[0],p[1],p[2]+1.])
        self.env.uf.Modeling.AskMinimumDist=request_stop
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'STOP_R11a'):
            self.invoke(self.adapter(out),out)
        self.assertEqual(len(calls),1)
        self.assertIn('STOP_R11a',self.report(out)['additional_diagnostic_error']['error'])
    def test_32_start_error_json_embeds_raw_terrain_diagnostic(self):
        from gesamt.start import main
        error=RuntimeError('SYNTHETIC_POINT_FAILURE')
        setattr(error,TRACE_ATTR,{'last_query':{'raw_nx_result':[2.,[0,0,0],[0,0,2]]},
                                 'report_file':'TEST_REPORT_NOT_NX','unverified_snapshot':None})
        with patch('gesamt.terrain_only.run_terrain_only',side_effect=error),patch('gesamt.start.message'):
            result=main(self.root,'TERRAIN')
        saved=read_json(Path(result['report_file']))
        self.assertEqual(saved['nested_diagnostics'][TRACE_ATTR]['last_query']['raw_nx_result'][0],2.)
        self.assertIn('STARTFEHLER_G01e_',Path(result['report_file']).name)

if __name__=='__main__':unittest.main(verbosity=2)
