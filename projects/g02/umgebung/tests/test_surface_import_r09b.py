"""Gezielte R09b-Regressionen. Mocks pruefen Logik, NICHT NX-Geometrie."""
import ast
import copy
import io
import contextlib
import math
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from test_r09 import BASE,JOB
import test_r09 as simulation
from r09.core import read_json,write_json
from r09.surface_check import reference_checked,area_checked,distance_result_checked
from r09.nx_adapter import SceneAdapter

class SurfaceImportTests(unittest.TestCase):
    setUp=simulation.NXSimulationTests.setUp
    adapter=simulation.NXSimulationTests.adapter
    cfg=simulation.NXSimulationTests.cfg
    workflow=simulation.NXSimulationTests.workflow
    def v01(self):return copy.deepcopy(next(s for s in JOB['parts'] if s['id']=='V01'))
    def imported(self,spec=None):
        s=spec or self.v01()
        with self.env.active():return self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
    def test_01_original_r09a_reproduces_49_56_abort(self):
        self.env.split_spec={'V01':7}
        module=types.ModuleType('r09._historic');module.__package__='r09'
        original=(BASE/'tests/fixtures/nx_adapter_R09a_historisch.txt').read_text()
        exec(compile(original,'nx_adapter_R09a_historisch.py','exec'),module.__dict__)
        s=self.v01()
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'V01 Soll=49 Ist=56'):
            module.SceneAdapter(lambda text:None).import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
    def test_02_split_49_sheets_56_faces_with_geometry_passes(self):
        self.env.split_spec={'V01':7};p,s,c=self.imported()
        self.assertEqual(c['sheets'],49);self.assertEqual(c['faces'],56)
        self.assertEqual(c['checked_source_points'],1920);self.assertTrue(c['face_count_changed'])
        self.assertEqual(self.env.distance_calls,1920);self.assertEqual(self.env.mass_calls,0);self.assertEqual(self.env.face_measure_calls,98)
    def test_03_split_reordered_body_mapping_preserved(self):
        self.env.split_spec={'V01':7};p,s,c=self.imported()
        self.assertEqual(c['mapping'][0],(0,48))
        self.assertEqual(p.Bodies[48].Name,'V01_QUELLFLAECHE_0001')
    def test_04_same_face_count_wrong_area_rejected(self):
        self.env.area_factor=1.02
        with self.assertRaisesRegex(RuntimeError,'Flaecheninhalt abweichend'):self.imported()
    def test_05_split_wrong_area_is_not_ignored(self):
        self.env.split_spec={'V01':7};self.env.area_factor=2.
        with self.assertRaisesRegex(RuntimeError,'Flaecheninhalt abweichend'):self.imported()
    def test_06_zero_area_rejected(self):
        self.env.area_override=0.
        with self.assertRaisesRegex(RuntimeError,'positiv'):self.imported()
    def test_07_nan_area_rejected(self):
        self.env.area_override=math.nan
        with self.assertRaisesRegex(RuntimeError,'endliche'):self.imported()
    def test_08_split_surface_point_mismatch_rejected(self):
        self.env.split_spec={'V01':7};self.env.distance=2.
        with self.assertRaisesRegex(RuntimeError,'Quellpunkt'):self.imported()
    def test_09_same_count_point_mismatch_rejected(self):
        self.env.distance=0.3
        with self.assertRaisesRegex(RuntimeError,'Quellpunkt'):self.imported()
    def test_10_inside_numeric_distance_tolerance_passes(self):
        self.env.distance=.1;p,s,c=self.imported(JOB['smoke_test'])
        self.assertAlmostEqual(c['max_point_distance_mm'],.1)
    def test_11_empty_faces_rejected(self):
        self.env.empty_faces=True
        with self.assertRaisesRegex(RuntimeError,'ohne Faces'):self.imported()
    def test_12_more_bodies_not_accepted_as_split_faces(self):
        self.env.extra_sheet=True
        with self.assertRaisesRegex(ValueError,'Teilkoerperanzahl'):self.imported()
    def test_13_failure_diagnostic_retains_actual_counts(self):
        self.env.split_spec={'V01':7};self.env.area_factor=1.2
        with self.assertRaises(RuntimeError) as cm:self.imported()
        report=read_json(self.root/'IMPORTPRUEFUNG_V01_R09e.json')
        self.assertEqual(report['nx_faces'],56);self.assertEqual(report['nx_sheets'],49)
        self.assertEqual(report['status'],'IMPORTGEOMETRIE_ABGEBROCHEN')
        self.assertEqual(cm.exception.nx_surface_check['last_sheet']['area_passed'],False)
    def test_14_missing_reference_rejected(self):
        s=self.v01();s.pop('geometry_reference')
        with self.assertRaisesRegex(ValueError,'Pruefreferenz'):reference_checked(s)
    def test_15_foreign_reference_hash_rejected(self):
        s=self.v01();s['geometry_reference']['source_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'STEP-Quelle'):reference_checked(s)
    def test_16_missing_grid_point_rejected(self):
        s=self.v01();s['geometry_reference']['sheets'][0]['samples_mm'].pop()
        with self.assertRaisesRegex(ValueError,'unvollstaendig'):reference_checked(s)
    def test_17_changed_tolerance_rejected(self):
        s=self.v01();s['geometry_reference']['distance_tolerance_mm']=10
        with self.assertRaisesRegex(ValueError,'Prueftoleranz'):reference_checked(s)
    def test_18_reference_indices_must_match(self):
        s=self.v01();s['geometry_reference']['sheets'][0]['source_index']=1
        with self.assertRaisesRegex(ValueError,'index'):reference_checked(s)
    def test_19_nan_reference_point_rejected(self):
        s=self.v01();s['geometry_reference']['sheets'][0]['samples_mm'][0][0]=math.nan
        with self.assertRaisesRegex(ValueError,'endliche'):reference_checked(s)
    def test_20_reference_total_count_checked(self):
        s=self.v01();s['geometry_reference']['sample_count']+=1
        with self.assertRaisesRegex(ValueError,'Gesamtzahl'):reference_checked(s)
    def test_21_reference_point_outside_source_rejected(self):
        s=self.v01();s['geometry_reference']['sheets'][0]['samples_mm'][0][0]+=1e6
        with self.assertRaisesRegex(ValueError,'ausserhalb'):reference_checked(s)
    def test_22_full_workflow_reports_actual_topology_not_585(self):
        self.env.split_spec={'V01':7};s=self.workflow()
        self.assertEqual(s['total_imported_nx_faces'],122)
        self.assertEqual(s['total_checked_source_points'],20883)
        self.assertTrue(any('56 NX-Faces' in w for w in s['warnings']))
    def test_23_bad_distance_api_return_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'drei Ergebnisfelder'):distance_result_checked(0.,[0,0,0])
    def test_24_negative_distance_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'Negativer'):distance_result_checked((-1,[0,0,0],[0,0,0]),[0,0,0])
    def test_25_distance_endpoints_must_agree(self):
        with self.assertRaisesRegex(RuntimeError,'widersprechen'):distance_result_checked((0.,[0,0,0],[0,0,1]),[0,0,0])
    def test_26_distance_input_point_must_agree(self):
        with self.assertRaisesRegex(RuntimeError,'Eingangspunkt'):distance_result_checked((0.,[0,0,1],[0,0,1]),[0,0,0])
    def test_27_api_errors_not_swallowed(self):
        def fail(*a):raise RuntimeError('INJECTED_MASS_API_FAILURE')
        self.env.primary_unavailable=True
        self.env.uf.Modeling.AskMassProps3d=fail
        with self.assertRaisesRegex(RuntimeError,'INJECTED_MASS_API_FAILURE'):self.imported()
    def test_28_primary_area_already_in_square_mm(self):
        p,s,c=self.imported(JOB['smoke_test'])
        report=read_json(self.root/'IMPORTPRUEFUNG_TEST_R09e.json')
        self.assertTrue(all(r['area_relative_error']<1e-12 for r in report['sheets_checked']))
    def test_29_all_original_knots_and_cell_centres_present(self):
        total=0
        for s in JOB['parts']+[JOB['smoke_test']]:total+=reference_checked(s)['sample_count']
        self.assertEqual(total,35661)
        self.assertEqual(JOB['parts'][0]['geometry_reference']['sample_count'],16748)
    def test_30_area_comparison_not_total_cancellation(self):
        self.assertFalse(area_checked(100000,101000)['area_passed'])
        self.assertFalse(area_checked(100000,99000)['area_passed'])
    def test_31_import_settings_not_relaxed(self):
        self.imported(JOB['smoke_test']);builder=self.env.importers[-1]
        self.assertFalse(builder.SewSurfaces);self.assertFalse(builder.Optimize)
        self.assertFalse(builder.SimplifyGeometry);self.assertFalse(builder.SmoothBSurfaces)
    def test_32_starter_reports_surface_diagnosis(self):
        entry=(BASE/'00_NX_MODELL_ERZEUGEN_2406.py').read_text()
        ast.parse(entry,feature_version=(3,10))
        self.assertIn("'nx_surface_check'",entry)
        self.assertIn('R11a-LAUFZEIT',entry)
    def test_33_nonexistent_measurement_api_blocks_before_import(self):
        self.env.uf.Modeling.AskMinimumDist=None
        with self.env.active(),self.assertRaisesRegex(RuntimeError,'AskMinimumDist'):self.adapter().preflight_importer()
        self.assertEqual(self.env.step_calls,0)
    def test_34_diagnostic_logs_failed_point(self):
        self.env.distance=1.
        with self.assertRaises(RuntimeError):self.imported()
        r=read_json(self.root/'IMPORTPRUEFUNG_V01_R09e.json')['sheets_checked'][0]
        self.assertEqual(r['failed_sample_index'],0);self.assertEqual(r['failed_distance_mm'],1.)
    def test_35_zero_or_negative_reference_area_rejected(self):
        s=self.v01();s['geometry_reference']['sheets'][0]['area_mm2']=-1
        with self.assertRaisesRegex(ValueError,'positiv'):reference_checked(s)
    def test_36_distance_nan_rejected(self):
        with self.assertRaisesRegex(ValueError,'endliche'):distance_result_checked((math.nan,[0,0,0],[0,0,0]),[0,0,0])

    def test_37_null_tag_uses_python_integer_without_nxopen_tag_namespace(self):
        self.assertFalse(hasattr(self.env.N, 'Tag'))
        p,s,c=self.imported(JOB['smoke_test'])
        self.assertEqual(c['checked_source_points'],58)
