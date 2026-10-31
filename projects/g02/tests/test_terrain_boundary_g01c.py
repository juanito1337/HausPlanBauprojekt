"""G01d regression tests. All NX calls below are explicitly synthetic doubles."""
import contextlib
import copy
import io
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

B=Path(__file__).absolute().parents[1];E=B/'umgebung'
sys.path[:0]=[str(B),str(E),str(E/'tests'),str(B/'tests')]
from gesamt import terrain_uv as uv
from gesamt.terrain_boundary import (SourceSide, plan_boundary, boundary_probes,
                                    BoundaryError, MAX_EDGES, edge_for_station)
from gesamt.core import read_json, child_exception_context
from test_r09 import SceneDouble, JOB
from uv_double import install_uv_double
from r09.performance import FastSceneAdapter, RunMonitor, DEFAULTS
from gesamt.nx_backend import NXBackend
from gesamt.terrain_only import run_terrain_only
from gesamt.terrain_audit import REPORT_NAME
SPEC=next(p for p in JOB['parts'] if p['id']=='DGM')
SOURCE=E/SPEC['step_file'];REFPATH=B/'data/DGM_REFERENZPUNKTE_G01a.json'
_,POINTS=uv.prepared_reference(SPEC);SIDES=uv.sides(POINTS)


def ranges(counts=(64,64,79,78), nonlinear=False):
    result=[]
    for side,n in enumerate(counts):
        ts=[(i/n)**1.15 if nonlinear else i/n for i in range(n+1)]
        for a,b in zip(ts,ts[1:]):result.append((side,a,b))
    return result


def records(layout=None):
    result=[]
    for index,(side,a,b) in enumerate(layout or ranges()):
        ss=SourceSide(*SIDES[side])
        result.append({'index':index,'tag':index+100,
                       'endpoints':[ss.at(a),ss.at(b)]})
    return result


class BoundaryPure(unittest.TestCase):
    def test_01_285_segments_not_rejected_by_count(self):
        groups,audit=plan_boundary(records(),SIDES)
        self.assertEqual(audit['actual_edge_count'],285)
        self.assertEqual([len(groups[n]['segments']) for n,_ in SIDES],[64,64,79,78])
        self.assertEqual(audit['assigned_edges'],285)
    def test_02_four_original_edges_still_accepted(self):
        _,audit=plan_boundary(records(ranges((1,1,1,1))),SIDES)
        self.assertEqual(audit['assigned_edges'],4)
    def test_03_all_366_grid_edges_accepted(self):
        _,audit=plan_boundary(records(ranges((82,82,101,101))),SIDES)
        self.assertEqual(audit['assigned_edges'],366)
    def test_04_shuffled_reversed_edges_accepted(self):
        r=records();random.Random(711).shuffle(r)
        for e in r[::2]:e['endpoints'].reverse()
        groups,_=plan_boundary(r,SIDES)
        for g in groups.values():
            self.assertEqual(g['segments'][0]['start_fraction'],0)
            self.assertAlmostEqual(g['segments'][-1]['end_fraction'],1)
    def test_05_nonuniform_splits_accepted(self):
        _,a=plan_boundary(records(ranges(nonlinear=True)),SIDES)
        self.assertEqual(a['assigned_edges'],285)
    def test_06_random_additional_splits(self):
        rng=random.Random(18)
        for _ in range(10):
            layout=[]
            for side in range(4):
                ts=[0.]+sorted(rng.uniform(.01,.99) for j in range(12))+[1.]
                layout.extend((side,a,b) for a,b in zip(ts,ts[1:]))
            _,audit=plan_boundary(records(layout),SIDES)
            self.assertEqual(audit['assigned_edges'],52)
    def test_07_missing_segment_rejected(self):
        r=records();del r[25]
        with self.assertRaises(BoundaryError):plan_boundary(r,SIDES)
    def test_08_missing_side_rejected(self):
        r=[e for e in records() if e['index']>=64]
        with self.assertRaisesRegex(BoundaryError,'fehlt'):plan_boundary(r,SIDES)
    def test_09_duplicate_geometry_with_new_tag_rejected(self):
        r=records();extra=copy.deepcopy(r[10]);extra.update(tag=999999,index=99999);r.append(extra)
        with self.assertRaises(BoundaryError):plan_boundary(r,SIDES)
    def test_10_duplicate_tag_rejected_not_deduplicated(self):
        r=records();r.append(copy.deepcopy(r[1]))
        with self.assertRaisesRegex(BoundaryError,'Doppelte'):plan_boundary(r,SIDES)
    def test_11_duplicate_index_rejected(self):
        r=records();r[1]['index']=0
        with self.assertRaisesRegex(BoundaryError,'Doppelte'):plan_boundary(r,SIDES)
    def test_12_interior_hole_edge_rejected(self):
        r=records();r.append({'tag':9000,'index':9000,'endpoints':[POINTS[1089],POINTS[1099]]})
        with self.assertRaisesRegex(BoundaryError,'Innenkante'):plan_boundary(r,SIDES)
    def test_13_cross_corner_edge_rejected(self):
        r=records();r[0]['endpoints'][0]=list(SIDES[0][1][1]);r[0]['endpoints'][1]=list(SIDES[2][1][10])
        with self.assertRaisesRegex(BoundaryError,'zugeordnet'):plan_boundary(r,SIDES)
    def test_14_wrong_elevation_rejected(self):
        r=records();r[40]['endpoints'][0][2]+=2.
        with self.assertRaises(BoundaryError):plan_boundary(r,SIDES)
    def test_15_equal_endpoints_rejected(self):
        r=records();r[2]['endpoints'][1]=r[2]['endpoints'][0]
        with self.assertRaisesRegex(BoundaryError,'entarteten'):plan_boundary(r,SIDES)
    def test_16_nan_coordinate_rejected(self):
        r=records();r[2]['endpoints'][0][2]=float('nan')
        with self.assertRaises(ValueError):plan_boundary(r,SIDES)
    def test_17_no_tolerance_relaxation_allowed(self):
        for t in [.251,1.,10.,True,float('nan'),0]:
            with self.assertRaises(ValueError):plan_boundary(records(),SIDES,t)
    def test_18_no_silent_edge_limit_truncation(self):
        r=records(ranges((MAX_EDGES,1,1,1)))
        with self.assertRaisesRegex(BoundaryError,'Arbeitslimit'):plan_boundary(r,SIDES)
    def test_19_gap_under_original_sample_spacing_rejected(self):
        s=SourceSide(*SIDES[0]);r=records()
        t=s.project_xy(r[20]['endpoints'][0]);r[20]['endpoints'][0]=s.at(t+.3/s.length_mm)
        with self.assertRaises(BoundaryError):plan_boundary(r,SIDES)
    def test_20_cumulative_small_gaps_rejected(self):
        s=SourceSide(*SIDES[0]);r=records()
        for e in r[2:12]:
            t=s.project_xy(e['endpoints'][0]);e['endpoints'][0]=s.at(t+.04/s.length_mm)
        with self.assertRaisesRegex(BoundaryError,'Abdeckung'):plan_boundary(r,SIDES)
    def test_21_0251_mm_not_tolerated(self):
        r=records();r[2]['endpoints'][0][2]+=.251
        with self.assertRaises(BoundaryError):plan_boundary(r,SIDES)
    def test_22_probe_count_and_all_edges(self):
        groups,_=plan_boundary(records(),SIDES);probes=list(boundary_probes(groups))
        self.assertEqual(len(probes),736+3*285)
        self.assertEqual(sum(p['kind']!='JE_KANTE_ZUSATZPROBE' for p in probes),736)
        extras=[p for p in probes if p['kind']=='JE_KANTE_ZUSATZPROBE']
        self.assertEqual(len({p['edge']['tag'] for p in extras}),285)
    def test_23_original_boundary_knots_unchanged(self):
        groups,_=plan_boundary(records(),SIDES)
        probes=[p for p in boundary_probes(groups) if p['kind']=='ORIGINAL_RANDKNOTEN']
        for p in probes:self.assertEqual(p['query_mm'],groups[p['side']]['source'].points[p['index']])
    def test_24_source_and_input_records_unchanged(self):
        r=records();before=copy.deepcopy(r);points=copy.deepcopy(SIDES)
        groups,_=plan_boundary(r,SIDES);list(boundary_probes(groups))
        self.assertEqual(r,before);self.assertEqual(SIDES,points)
    def test_25_corner_junction_mismatch_rejected(self):
        r=records(ranges((1,1,1,1)))
        r[0]['endpoints'][0][2]+=.2;r[2]['endpoints'][0][2]-=.2
        with self.assertRaisesRegex(BoundaryError,'Ecke'):plan_boundary(r,SIDES)
    def test_26_real_error_never_returns_successful_audit(self):
        r=records();r.pop(200)
        try:plan_boundary(r,SIDES)
        except BoundaryError as e:
            self.assertEqual(e.boundary_details['status'],'RANDPRUEFUNG_ABGEBROCHEN')
        else:self.fail('Error not rejected')
    def test_27_chord_cannot_replace_terrain_end_elevation(self):
        s=SourceSide(*SIDES[0]);q=s.at(.29);q[2]+=1
        self.assertIsNone(s.locate(q,.25))
    def test_28_legacy_count_check_reproduces_reported_285(self):
        with self.assertRaisesRegex(RuntimeError,'285'):
            uv.assign_edges([e['endpoints'] for e in records()],SIDES)
    def test_29_source_x_y_not_rectilinear_rejected(self):
        sides=copy.deepcopy(SIDES);sides[0][1][12][0]+=20
        with self.assertRaisesRegex(ValueError,'geradlinig'):plan_boundary(records(),sides)
    def test_30_three_edges_rejected_with_explicit_message(self):
        with self.assertRaisesRegex(BoundaryError,'Vier Quellseiten'):plan_boundary(records()[:3],SIDES)


class BoundaryIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.definition=self.root/'step214ug.def'
        self.definition.write_text('TESTDOUBLE_NOT_NX_IMPORT_DEFINITION')
        self.env=SceneDouble(self.definition);self.control=install_uv_double(self.env)
        self.control.edge_ranges=ranges();self.policy=copy.deepcopy(DEFAULTS)
    def invoke(self):
        out=self.root/'run';out.mkdir(exist_ok=True)
        cls=uv.make_uv_audited_adapter(FastSceneAdapter,REFPATH)
        return cls(lambda t:None,RunMonitor(out),self.policy).import_surface_part(out,SOURCE,SPEC,self.definition)
    def read(self):return read_json(self.root/'run'/uv.REPORT)
    def test_31_full_285_import_and_save_simulation(self):
        with self.env.active():part,saved,check=self.invoke()
        r=self.read();self.assertEqual(r['checked_samples'],16748)
        self.assertEqual(r['boundary_samples_checked'],1591)
        self.assertEqual(r['actual_edges_with_distance_checks'],285)
        self.assertEqual(self.control.edge_queries,1591);self.assertEqual(self.control.body_queries,0)
        self.assertTrue(Path(part.FullPath).is_file());self.assertTrue(check['boundary_chains_passed'])
    def test_32_changed_interior_still_rejected(self):
        def warp(p,q):
            if q==[13.,10.]:p[2]+=2.
            return p
        self.control.transform=warp
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Punkt 1089'):self.invoke()
    def test_33_wrong_boundary_still_rejected(self):
        self.control.boundary_error=.3
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Randabweichung'):self.invoke()
        self.assertEqual(self.read()['checked_samples'],16748)
    def test_34_subset_missing_no_geometry_success(self):
        self.control.edge_records_transform=lambda rows:rows[:20]+rows[21:]
        with self.env.active(),self.assertRaises(BoundaryError) as c:self.invoke()
        self.assertFalse(self.read()['selected_checks_passed'])
        self.assertIn('nx_terrain_boundary_g01c',child_exception_context(c.exception))
    def test_35_boundary_failure_keeps_saved_unverified_copy(self):
        self.control.edge_records_transform=lambda rows:rows[:-1]
        with self.env.active(),self.assertRaises(BoundaryError):self.invoke()
        trace=read_json(self.root/'run'/REPORT_NAME)
        self.assertTrue(trace['unverified_snapshot']['exists'])
        self.assertIsNone(trace['final_saved_part'])
    def test_36_records_captured_before_assignment_failure(self):
        self.control.edge_records_transform=lambda rows:rows[:-1]
        with self.env.active(),self.assertRaises(BoundaryError):self.invoke()
        r=self.read();self.assertEqual(r['edge_count_returned'],284)
        self.assertEqual(len(r['edge_records']),284)
        self.assertIn('boundary_chains',r)
    def test_37_no_new_NX_methods_required(self):
        self.assertFalse(hasattr(self.env.uf,'Eval'))
        with self.env.active():self.invoke()
        self.assertEqual(self.control.evaluations,16753)
    def test_38_only_terrain_starter_integrates_chain_check(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'single')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            r=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertEqual(r['terrain']['check']['actual_boundary_edges'],285)
        self.assertIsNone(r['house']);self.assertIsNone(r['environment'])
        self.assertEqual(self.env.step_calls,1)
    def test_39_actual_false_distance_is_not_replaced(self):
        self.control.boundary_bad=True
        with self.env.active(),self.assertRaises(Exception):self.invoke()
        self.assertFalse(self.read()['selected_checks_passed'])
    def test_40_shuffled_simulated_API_output(self):
        def shuffle(rows):
            random.Random(18).shuffle(rows)
            for e in rows[::3]:e['endpoints'].reverse();e['line'].reverse()
            return rows
        self.control.edge_records_transform=shuffle
        with self.env.active():self.invoke()
        self.assertTrue(self.read()['selected_checks_passed'])
    def test_41_one_displaced_edge_middle_rejected(self):
        # Ends unchanged; a real geometric query (synthetic here) disagrees in between.
        def bow(line):
            mid=[(line[0][i]+line[-1][i])/2 for i in range(3)]
            mid[2]+=50
            return [line[0],mid,line[-1]]
        self.control.line_transform=bow
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Randabweichung'):self.invoke()
    def test_42_no_area_measurement_in_basis(self):
        with self.env.active():self.invoke()
        self.assertFalse(self.read()['area_check_performed'])
        self.assertEqual(self.env.face_measure_calls,0)


if __name__=='__main__':unittest.main(verbosity=2)
