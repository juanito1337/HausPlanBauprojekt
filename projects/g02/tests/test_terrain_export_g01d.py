"""G01d tests: delivery routing, real NX evidence replay and synthetic workflows.
These are NOT an NX run; independent real CAD tests live in werkzeuge.
"""
import contextlib,copy,hashlib,io,json,math,re,sys,tempfile,unittest
from pathlib import Path
B=Path(__file__).absolute().parents[1];E=B/'umgebung'
sys.path[:0]=[str(B),str(E),str(E/'tests'),str(B/'tests')]
from gesamt import terrain_uv as uv
from gesamt.core import read_json
from gesamt.terrain_boundary import SourceSide,plan_boundary,boundary_probes
from gesamt.nx_backend import NXBackend
from gesamt.terrain_only import run_terrain_only
from test_r09 import SceneDouble,JOB
from r09.performance import FastSceneAdapter,RunMonitor,DEFAULTS
from uv_double import install_uv_double
import test_terrain_boundary_g01c as bc
SPEC=next(p for p in JOB['parts'] if p['id']=='DGM');SOURCE=E/SPEC['step_file']
PROV=read_json(B/'data/DGM_IMPORTDARSTELLUNG_G01d.json')
FIX=read_json(B/'tests/fixtures/NX_G01c_RAND417.json')
_,PTS=uv.prepared_reference(SPEC)
REF=B/'data/DGM_REFERENZPUNKTE_G01a.json'

class DeliveryTests(unittest.TestCase):
    def test_01_new_import_source_exists_and_matches_hash(self):
        self.assertEqual(hashlib.sha256(SOURCE.read_bytes()).hexdigest(),SPEC['sha256'])
        self.assertEqual(SPEC['sha256'],uv.SOURCE_SHA256)
    def test_02_original_file_still_present_unchanged(self):
        self.assertEqual(hashlib.sha256((E/'CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step').read_bytes()).hexdigest(),PROV['original_sha256'])
    def test_03_step_bytes_changed_not_called_byte_identical(self):
        self.assertNotEqual(PROV['original_sha256'],SPEC['sha256'])
        self.assertTrue(PROV['source_topology_changed'])
    def test_04_all_16748_source_points_identical(self):
        self.assertEqual(SPEC['geometry_reference']['sheets'],PROV['old_import_spec']['geometry_reference']['sheets'])
    def test_05_no_box_or_unit_change(self):
        for key in ('face_bounding_boxes_mm','bounding_box_mm','expected_sheets','expected_faces','part_file'):
            if key in SPEC:self.assertEqual(SPEC[key],PROV['old_import_spec'][key])
        self.assertIn('SI_UNIT(.MILLI.,.METRE.)',SOURCE.read_text())
    def test_06_step_has_366_explicit_3d_lines(self):
        self.assertEqual(len(re.findall(r'= LINE\(',SOURCE.read_text())),366)
    def test_07_old_declaration_not_used_as_current_import(self):
        self.assertEqual(SPEC['step_file'],'CAD_IMPORT/GELAENDE_G01d_EXAKTER_SEGMENTRAND.step')
        self.assertIn('G01d',SPEC['source'])
    def test_08_unchanged_limits(self):
        self.assertEqual(uv.DISTANCE_MM,.25)
        self.assertEqual(SPEC['geometry_reference']['distance_tolerance_mm'],.25)
    def test_09_fixture_is_actual_failed_NX_report(self):
        self.assertTrue(FIX['actual_NX_measurement']);self.assertFalse(FIX['selected_checks_passed'])
        self.assertAlmostEqual(FIX['failure']['distance_mm'],.26372681449087754)
    def test_10_evidence_reports_all_carrier_samples_only(self):
        self.assertEqual(FIX['checked_surface_points'],16748)
        self.assertLess(FIX['maximum_surface_deviation_mm'],1e-6)
        self.assertLess(FIX['boundary_samples_completed_including_failure'],FIX['boundary_samples_planned'])
    def test_11_failed_probe_is_original_grid_knot(self):
        self.assertLess(math.dist(PTS[101*83+3],FIX['failure']['query_mm']),1e-7)
    def test_12_raw_returned_point_still_outside_025mm(self):
        f=FIX['failure'];self.assertAlmostEqual(math.dist(f['raw_result'][1],f['raw_result'][2]),f['distance_mm'],places=8)
        self.assertGreater(f['distance_mm'],uv.DISTANCE_MM)
    def test_13_actual_285_endpoint_chains_cover_sides(self):
        _,audit=plan_boundary(FIX['edge_records'],uv.sides(PTS))
        self.assertEqual(sorted(s['edge_count'] for s in audit['sides']),[1,82,101,101])
    def test_14_source_boundary_segments_use_existing_nodes(self):
        r=bc.records(bc.ranges((82,82,101,101)));groups,a=plan_boundary(r,uv.sides(PTS))
        self.assertEqual(a['assigned_edges'],366)
        self.assertEqual(len(list(boundary_probes(groups))),1834)
    def test_15_corrupt_source_identity_rejected(self):
        s=copy.deepcopy(SPEC);s['sha256']='0'*64
        with self.assertRaises(ValueError):uv.prepared_reference(s)
    def test_16_historical_reference_points_match_new_source(self):
        from gesamt.dgm_probe import load_reference
        r=load_reference(REF);self.assertEqual(r['source_sha256'],SPEC['sha256'])
        for i,p in r['points'].items():self.assertLess(math.dist(p,PTS[int(i)]),1e-8)

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.definition=self.root/'step214ug.def'
        self.definition.write_text('SIMULATION_ONLY_NOT_AN_ACTUAL_NX_DEFINITION')
        self.env=SceneDouble(self.definition);self.control=install_uv_double(self.env)
        self.control.edge_ranges=bc.ranges((82,82,101,101));self.policy=copy.deepcopy(DEFAULTS)
    def invoke(self):
        out=self.root/'run';out.mkdir(exist_ok=True)
        cls=uv.make_uv_audited_adapter(FastSceneAdapter,REF)
        return cls(lambda t:None,RunMonitor(out),self.policy).import_surface_part(out,SOURCE,SPEC,self.definition)
    def report(self):return read_json(self.root/'run'/uv.REPORT)
    def test_17_new_full_366_segment_simulation(self):
        with self.env.active():part,saved,check=self.invoke()
        r=self.report();self.assertTrue(r['selected_checks_passed'])
        self.assertEqual(r['boundary_samples_checked'],1834);self.assertEqual(r['checked_samples'],16748)
        self.assertEqual(r['actual_edges_with_distance_checks'],366)
        self.assertEqual(check['input_sha256'],SPEC['sha256'])
    def test_18_actual_0263727_replay_not_silently_accepted(self):
        self.control.edge_ranges=bc.ranges((82,1,101,101))
        previous=self.env.uf.Modeling.AskMinimumDist;f=FIX['failure']
        def query(*args):
            if math.dist(args[3],f['query_mm'])<1e-6:return copy.deepcopy(f['raw_result'])
            return previous(*args)
        self.env.uf.Modeling.AskMinimumDist=query
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'0.263727'):self.invoke()
        self.assertFalse(self.report()['selected_checks_passed'])
        self.assertEqual(self.report()['checked_samples'],16748)
    def test_19_even_0251_mm_still_rejected(self):
        self.control.boundary_error=.251
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke()
    def test_20_true_2mm_internal_deformation_still_rejected(self):
        def warp(p,uv):
            if uv==[13.,10.]:p[2]+=2
            return p
        self.control.transform=warp
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'Punkt 1089'):self.invoke()
    def test_21_missing_boundary_segment_rejected(self):
        self.control.edge_records_transform=lambda r:r[:-1]
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke()
    def test_22_terrain_only_uses_packaged_new_source(self):
        cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(self.root/'only')
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()):
            state=run_terrain_only(B,cfg,NXBackend(B,session_provider=lambda:self.env.session),verify=False)
        self.assertEqual(state['source_sha256'],SPEC['sha256'])
        self.assertTrue(state['source_file'].endswith('GELAENDE_G01d_EXAKTER_SEGMENTRAND.step'))
        self.assertEqual(state['terrain']['check']['actual_boundary_edges'],366)
        self.assertIsNone(state['house']);self.assertIsNone(state['environment'])
    def test_23_no_surface_integration_or_body_distance(self):
        with self.env.active():self.invoke()
        self.assertEqual(self.env.face_measure_calls,0);self.assertEqual(self.control.body_queries,0)
    def test_24_failure_retains_unverified_file(self):
        self.control.boundary_error=.3
        with self.env.active(),self.assertRaises(RuntimeError):self.invoke()
        from gesamt.terrain_audit import REPORT_NAME
        r=read_json(self.root/'run'/REPORT_NAME)
        self.assertTrue(r['unverified_snapshot']['exists']);self.assertIsNone(r['final_saved_part'])

if __name__=='__main__':unittest.main(verbosity=2)
