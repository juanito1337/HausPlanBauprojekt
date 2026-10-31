"""G01b tests use synthetic bindings unless explicitly labelled OCCT in the separate tool."""
import contextlib,copy,io,itertools,json,math,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
B=Path(__file__).absolute().parents[1];E=B/'umgebung'
sys.path[:0]=[str(B),str(E),str(E/'tests'),str(B/'tests')]
from test_r09 import SceneDouble,JOB
from uv_double import install_uv_double
from gesamt import terrain_uv as uv
from gesamt.core import read_json,child_exception_context
from gesamt.terrain_audit import make_audited_adapter,REPORT_NAME,TRACE_ATTR
from gesamt.terrain_only import run_terrain_only
from gesamt.nx_backend import NXBackend
from r09.performance import FastSceneAdapter,RunMonitor,DEFAULTS
SPEC=next(s for s in JOB['parts'] if s['id']=='DGM');SOURCE=E/SPEC['step_file']
REFPATH=B/'data/DGM_REFERENZPUNKTE_G01a.json'

class UVTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.definition=self.root/'step214ug.def'
        self.definition.write_text('TESTDOUBLE_ONLY_NOT_A_NX_DEF')
        self.env=SceneDouble(self.definition);self.control=install_uv_double(self.env)
        self.policy=copy.deepcopy(DEFAULTS)
    def invoke(self,name='run',spec=None):
        out=self.root/name;out.mkdir(exist_ok=True)
        cls=uv.make_uv_audited_adapter(FastSceneAdapter,REFPATH)
        a=cls(lambda t:None,RunMonitor(out),self.policy)
        return a.import_surface_part(out,SOURCE,spec or SPEC,self.definition)
    def read(self,name='run'):return read_json(self.root/name/uv.REPORT)
    def test_01_all_source_indices_checked(self):
        with self.env.active():part,saved,check=self.invoke()
        r=self.read();self.assertEqual(r['checked_samples'],16748)
        self.assertEqual(r['boundary_samples_checked'],748)
        self.assertEqual(self.control.evaluations,16753)
        self.assertEqual(self.control.edge_queries,748)
        self.assertEqual(self.control.body_queries,0)
        self.assertEqual(check['validation_level'],'DGM_UV_G01c')
        self.assertFalse(r['area_check_performed']);self.assertFalse(r['geometry_release'])
        self.assertTrue(Path(part.FullPath).is_file())
    def test_02_problem_points_are_checked_early(self):
        with self.env.active():self.invoke()
        self.assertEqual([r['source_index'] for r in self.read()['focus_points']],list(uv.FOCUS))
    def test_03_shift_at_1089_is_rejected(self):
        def t(p,q):
            if q==[13.,10.]:p[2]+=1.
            return p
        self.control.transform=t
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Punkt 1089') as c:self.invoke()
        self.assertEqual(self.read()['failed_sample']['source_index'],1089)
        self.assertIn('nx_terrain_uv_g01b',child_exception_context(c.exception))
    def test_04_all_eight_axis_mappings(self):
        # Pure fixed-corner logic: every allowed orientation, no per-point refitting.
        src={(0,0):[0.,0.,0.],(1,0):[200.,0.,1.],(0,1):[0.,300.,2.],(1,1):[200.,300.,4.]}
        for flags in itertools.product((False,True),repeat=3):
            m=dict(zip(('swap','reverse_u','reverse_v'),flags))
            nx={tuple(uv.mapped_uv(k,m,[0,1,0,1])):v for k,v in src.items()}
            found,_=uv.determine_mapping(nx,src);self.assertEqual(found,m)
    def test_05_swapped_reversed_actual_parameters(self):
        self.control.swap=True;self.control.rv=True;self.control.limits=[-3.,7.,10.,60.]
        with self.env.active():self.invoke()
        r=self.read();self.assertEqual(r['uv_mapping'],{'swap':True,'reverse_u':False,'reverse_v':True})
        self.assertLess(r['max_position_error_mm'],1e-5)
    def test_06_corner_translation_not_fitted_away(self):
        self.control.transform=lambda p,q:[p[0]+10,p[1],p[2]]
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Eckzuordnung'):self.invoke()
    def test_07_nan_not_accepted(self):
        self.control.transform=lambda p,q:[p[0],p[1],float('nan')]
        with self.env.active(),self.assertRaisesRegex(ValueError,'endlicher'):self.invoke()
    def test_08_missing_SrfPos_fails(self):
        self.env.uf.Modeling.EvaluateFace=lambda *a:NS(unexpected=[0,0,0])
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'SrfPos'):self.invoke()
    def test_09_missing_API_fails_with_saved_checkpoint(self):
        self.env.uf.Modeling.EvaluateFace=None
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'API fehlt'):self.invoke()
        trace=read_json(self.root/'run'/REPORT_NAME)
        self.assertTrue(Path(trace['unverified_snapshot']['path']).is_file())
        self.assertIsNone(trace['final_saved_part'])
    def test_10_no_silent_use_of_legacy_if_evaluation_fails(self):
        self.control.uv_failure='INJECTED_UV_FAILURE'
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'INJECTED_UV_FAILURE'):self.invoke()
        self.assertEqual(self.control.body_queries,0)
        self.assertEqual(self.control.edge_queries,0)
    def test_11_inner_hole_topology_fails(self):
        self.control.edges=5
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Rand'):self.invoke()
    def test_12_three_edges_fail(self):
        self.control.edges=3
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Rand'):self.invoke()
    def test_13_boundary_endpoints_do_not_match(self):
        self.control.vertex_offset=20
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Randkante'):self.invoke()
    def test_14_boundary_deformation_fails_even_if_UV_matches(self):
        self.control.boundary_error=1
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Randabweichung'):self.invoke()
        self.assertEqual(self.read()['checked_samples'],16748)
    def test_15_contradictory_boundary_zero_fails(self):
        self.control.boundary_bad=True
        with self.env.active(),self.assertRaises(Exception):self.invoke()
        self.assertFalse(self.read()['selected_checks_passed'])
    def test_16_numerical_limits_are_not_liberalized(self):
        self.assertEqual(uv.DISTANCE_MM,.25)
        self.control.transform=lambda p,q:[p[0],p[1],p[2]+.251]
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke()
    def test_17_UV_limit_nan_fails(self):
        self.control.limits=[0,float('nan'),0,82]
        with self.env.active(),self.assertRaises(ValueError):self.invoke()
    def test_18_zero_UV_domain_fails(self):
        self.control.limits=[0,0,0,82]
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'entarteter'):self.invoke()
    def test_19_wrong_surface_count_fails(self):
        self.env.extra_sheet=True
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke()
    def test_20_volume_not_accepted(self):
        self.env.step_solids=True
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Volumenkoerper'):self.invoke()
    def test_21_source_data_stay_unchanged(self):
        before=copy.deepcopy(SPEC)
        with self.env.active():self.invoke()
        self.assertEqual(before,SPEC)
    def test_22_changed_grid_centre_rejected(self):
        s=copy.deepcopy(SPEC);s['geometry_reference']['sheets'][0]['samples_mm'][8466][2]+=1
        with self.assertRaisesRegex(ValueError,'Zellmitte'):uv.prepared_reference(s)
    def test_23_historic_failure_reports_as_boundary_distance(self):
        r=read_json(B/'berichte/NX_RANDAUSWERTUNG_G01b.json')
        self.assertEqual(r['record_count'],23)
        for e in r['records']:
            self.assertLess(abs(e['difference_mm']),1e-4)
            self.assertLess(e['NX_target_distance_to_source_boundary_mm'],1e-4)
    def test_24_legacy_body_failure_is_not_used_for_UV(self):
        # Simulated body/face search always fails. Only edge searches return measurements.
        old=self.env.uf.Modeling.AskMinimumDist
        def dist(n,t,g,q,g2,x):
            if t in self.env.objects:raise RuntimeError('LEGACY_BODY_SEARCH_CALLED')
            return old(n,t,g,q,g2,x)
        self.env.uf.Modeling.AskMinimumDist=dist
        with self.env.active():self.invoke()
        self.assertTrue(self.read()['selected_checks_passed'])
    def test_25_output_contains_actual_positions_not_just_counts(self):
        with self.env.active():self.invoke()
        events=[json.loads(l) for l in (self.root/'run'/uv.EVENTS).read_text().splitlines()]
        positions=[e for e in events if e['kind']=='NX_EVALUATE_FACE']
        self.assertEqual(len(positions),16753)
        self.assertEqual(sum(e['kind']=='NX_RANDABSTAND' for e in events),748)
        self.assertIn('actual_position_mm',positions[0]['data'])
    def test_26_no_output_overwrite(self):
        out=self.root/'run';out.mkdir();(out/uv.REPORT).write_text('USER_REPORT')
        with self.env.active(),self.assertRaises(FileExistsError):self.invoke()
        self.assertEqual((out/uv.REPORT).read_text(),'USER_REPORT')
    def test_27_negative_control_is_positive(self):
        with self.env.active():self.invoke()
        c=self.read()['negative_control'];self.assertTrue(c['correctly_not_accepted']);self.assertGreater(c['distance_mm'],1000)
    def test_28_production_standalone_uses_UV_without_manual_import(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'only')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            r=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertEqual(self.env.step_calls,1);self.assertIsNone(r['house'])
        self.assertEqual(r['terrain']['check']['checked_source_points'],16748)
        self.assertGreater(self.control.evaluations,16748)
    def test_29_no_area_integration_in_default(self):
        with self.env.active():self.invoke()
        self.assertEqual(self.env.face_measure_calls,0);self.assertEqual(self.env.mass_calls,0)
    def test_30_INTENSIV_keeps_area_check(self):
        self.policy['surface_validation']='INTENSIV'
        with self.env.active():self.invoke()
        self.assertTrue(self.read()['area_check_performed']);self.assertEqual(self.env.face_measure_calls,2)
    def test_31_stop_checked_between_chunks(self):
        old=self.control.transform
        def stop(p,q):
            if self.control.evaluations==10:(self.root/'run/STOP_R11a.txt').touch()
            return old(p,q)
        self.control.transform=stop
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'STOP_R11a'):self.invoke()
        self.assertLess(self.control.evaluations,150)
    def test_32_two_runs_get_new_files(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'twice')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            r1=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
            r2=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertNotEqual(r1['terrain']['file']['path'],r2['terrain']['file']['path'])
    def test_33_reference_fraction_indexing(self):
        self.assertEqual(uv.sample_fraction(0),(0,0));self.assertEqual(uv.sample_fraction(8465),(1,1))
        self.assertEqual(uv.sample_fraction(1089),(13/101,10/82))
        self.assertEqual(uv.sample_fraction(8466),(.5/101,.5/82))
    def test_34_invalid_fraction_indices(self):
        for i in [-1,16748,True,1.5]:
            with self.assertRaises(ValueError):uv.sample_fraction(i)
    def test_35_numeric_validation(self):
        for x in [True,'1',None,float('inf')]:
            with self.assertRaises(ValueError):uv.number(x)
    def test_36_wrong_owner_fails(self):
        original=uv.prepared_reference
        def corrupt(spec):
            result=original(spec)
            body=list(self.env.session.Parts.Work.Bodies)[0]
            body.OwningPart=NS(Tag=-1)
            return result
        with self.env.active(),patch.object(uv,'prepared_reference',side_effect=corrupt),self.assertRaisesRegex(RuntimeError,'offener Flaechenkoerper'):
            self.invoke()

if __name__=='__main__':unittest.main(verbosity=2)
