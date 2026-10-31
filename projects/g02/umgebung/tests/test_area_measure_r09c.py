"""R09c regression of the *observed* measurement failure. No actual NX engine.

The test double returns supplied numbers, not measured geometry. Deliberate bad
returns check failure handling. Original R09b is executed from an unchanged copy.
"""
import ast
import copy
import math
import types
import unittest
from unittest.mock import patch
import test_r09 as simulation
from test_r09 import BASE, JOB
from fake_nx import FakeNXException, Body, ns
from r09.area_measure import (measure_surface_area, _stable_pair, runtime_information,
                             SurfaceAreaMeasurementError, PRIMARY, FALLBACK)
from r09.core import read_json
from r09.nx_adapter import SceneAdapter


class AreaMeasureTests(unittest.TestCase):
    setUp = simulation.NXSimulationTests.setUp
    adapter = simulation.NXSimulationTests.adapter
    cfg = simulation.NXSimulationTests.cfg
    workflow = simulation.NXSimulationTests.workflow

    def imported(self, spec=None):
        spec = spec or JOB['smoke_test']
        with self.env.active():
            return self.adapter().import_surface_part(self.root, BASE/spec['step_file'], spec, self.definition)

    def report(self, ident='TEST'):
        return read_json(self.root/('IMPORTPRUEFUNG_'+ident+'_R09e.json'))

    def test_01_original_r09b_reproduces_820001_on_second_test_sheet(self):
        self.env.legacy_fail_second = True
        module = types.ModuleType('r09._historic_r09b'); module.__package__ = 'r09'
        text = (BASE/'tests/fixtures/nx_adapter_R09b_historisch.txt').read_text()
        exec(compile(text, 'nx_adapter_R09b_historisch.py', 'exec'), module.__dict__)
        spec = JOB['smoke_test']
        with self.env.active(), self.assertRaises(FakeNXException) as cm:
            module.SceneAdapter(lambda text: None).import_surface_part(self.root, BASE/spec['step_file'], spec, self.definition)
        self.assertEqual(cm.exception.ErrorCode, 820001)
        r = read_json(self.root/'IMPORTPRUEFUNG_TEST_R09b.json')
        self.assertEqual((r['nx_sheets'],r['nx_faces']), (2,2))
        self.assertEqual(r['sheets_checked'][-1]['source_index'], 1)
        self.assertEqual(r['sheets_checked'][0]['checked_samples'], 20)
        self.assertEqual(r['sheets_checked'][-1]['checked_samples'], 0)

    def test_02_new_code_does_not_call_failing_relative_mass_mode(self):
        self.env.legacy_fail_second=True
        p,s,c=self.imported()
        self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(self.env.face_measure_calls,4)
        self.assertEqual(c['checked_source_points'],58)
        self.assertEqual(self.env.disposed_measures,4)

    def test_03_primary_has_explicit_mm_units_no_inch_factor(self):
        self.imported()
        for r in self.report()['sheets_checked']:
            d=r['area_measurement'];self.assertEqual(d['selected_method'],PRIMARY)
            self.assertAlmostEqual(d['area_mm2'],r['expected_area_mm2'])
            self.assertEqual([a['area_unit'] for a in d['attempts'][0]['measurements']],['mm2','mm2'])

    def test_04_fixed_mode_fallback_on_nx_error_is_recorded(self):
        self.env.primary_fail=True
        self.imported()
        self.assertEqual(self.env.mass_calls,4)
        for r in self.report()['sheets_checked']:
            d=r['area_measurement'];self.assertTrue(d['fallback_used'])
            self.assertEqual(d['selected_method'],FALLBACK)
            self.assertEqual(d['attempts'][0]['nx_error_code'],820001)
            self.assertTrue(r['area_passed'])
        self.assertTrue(all(a[5]==1 and a[3]==3 for a in self.env.mass_args))

    def test_05_missing_primary_has_bounded_documented_fallback(self):
        self.env.primary_unavailable=True;self.imported()
        self.assertEqual(self.env.face_measure_calls,0);self.assertEqual(self.env.mass_calls,4)
        d=self.report()['sheets_checked'][0]['area_measurement']
        self.assertEqual(d['attempts'][0]['status'],'API_NICHT_VERFUEGBAR')

    def test_06_both_nx_methods_fail_stops_with_both_attempts(self):
        self.env.primary_fail=True;self.env.uf_fail=True
        with self.assertRaises(SurfaceAreaMeasurementError) as cm:self.imported()
        d=cm.exception.nx_area_measurement
        self.assertEqual(d['status'],'FLAECHENMESSUNG_ABGEBROCHEN')
        self.assertEqual(len(d['attempts']),2)
        self.assertTrue(all(a['nx_error_code']==820001 for a in d['attempts']))
        self.assertEqual(self.env.distance_calls,0)

    def test_07_zero_result_is_error_not_fallback_trigger(self):
        self.env.area_override=0
        with self.assertRaisesRegex(RuntimeError,'positiv'):self.imported()
        self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(self.env.disposed_measures,1)

    def test_08_nonfinite_result_not_accepted(self):
        self.env.area_override=math.inf
        with self.assertRaisesRegex(RuntimeError,'endliche'):self.imported()
        self.assertEqual(self.env.mass_calls,0)

    def test_09_null_measurement_does_not_hide_binding_problem(self):
        self.env.primary_none=True
        with self.assertRaisesRegex(RuntimeError,'kein Messobjekt'):self.imported()
        self.assertEqual(self.env.mass_calls,0)

    def test_10_type_error_not_masked_by_alternate_api(self):
        with self.env.active():
            spec=JOB['smoke_test'];a=self.adapter();p=a.new_part(self.root/'direct.prt','DIRECT')
            b=Body(p,lambda:[[0,0,0],[1,1,1]]);b.IsSolidBody=False
            def bad(*args):raise TypeError('SIGNATURE_ERROR')
            p.MeasureManager.NewFaceProperties=bad
            with self.assertRaisesRegex(RuntimeError,'SIGNATURE_ERROR'):a.surface_area_mm2(b)
        self.assertEqual(self.env.mass_calls,0)

    def test_11_two_accuracy_results_must_be_stable(self):
        self.env.accuracy_factors={.999:1.,.9999:1.02,.99999:1.,.999999:1.02,.9999999:1.}
        with self.assertRaisesRegex(RuntimeError,'nicht stabil'):self.imported()
        self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(self.env.disposed_measures,5)

    def test_12_stable_but_wrong_result_fails_source_comparison(self):
        self.env.area_factor=1.04
        with self.assertRaisesRegex(RuntimeError,'Flaecheninhalt abweichend'):self.imported()
        self.assertEqual(self.env.mass_calls,0)

    def test_13_wrong_fallback_value_also_fails_source_comparison(self):
        self.env.primary_fail=True;self.env.area_factor=1.04
        with self.assertRaisesRegex(RuntimeError,'Flaecheninhalt abweichend'):self.imported()
        self.assertEqual(self.env.mass_calls,2)

    def test_14_cleanup_failure_stops_not_fallback(self):
        self.env.primary_dispose_fail=True
        with self.assertRaisesRegex(RuntimeError,'MEASURE_DISPOSE_FAILED') as cm:self.imported()
        self.assertEqual(self.env.mass_calls,0)
        self.assertFalse(cm.exception.nx_area_measurement['attempts'][0]['measurements'][0]['disposed'])

    def test_15_area_read_exception_releases_measure_then_fallback(self):
        self.env.primary_fail_after_create=True
        self.imported()
        self.assertEqual(self.env.disposed_measures,2)
        self.assertEqual(self.env.mass_calls,4)

    def test_16_read_and_cleanup_fail_preserve_both_errors(self):
        self.env.primary_fail_after_create=True;self.env.primary_dispose_fail=True
        with self.assertRaisesRegex(RuntimeError,'AREA_READ_FAILED') as cm:self.imported()
        self.assertEqual(self.env.mass_calls,0)
        row=cm.exception.nx_area_measurement['attempts'][0]['measurements'][0]
        self.assertIn('MEASURE_DISPOSE_FAILED',row['cleanup_error']['error'])
        self.assertEqual(row['nx_error_code'],820001)

    def test_17_split_faces_all_counted_once(self):
        self.env.split_spec={'V01':7}
        spec=next(p for p in JOB['parts'] if p['id']=='V01')
        p,s,c=self.imported(spec)
        self.assertEqual(c['faces'],56);self.assertEqual(c['sheets'],49)
        self.assertEqual(self.env.face_measure_calls,98)
        r=self.report('V01')
        self.assertEqual(sum(row['area_measurement']['nx_faces'] for row in r['sheets_checked']),56)

    def test_18_primary_success_requires_no_mass_api(self):
        self.env.uf.Modeling.AskMassProps3d=None
        self.imported()
        self.assertEqual(self.env.face_measure_calls,4)

    def test_19_no_available_method_is_fatal(self):
        self.env.primary_unavailable=True;self.env.uf.Modeling.AskMassProps3d=None
        with self.assertRaisesRegex(RuntimeError,'Keine verfuegbare'):self.imported()
        self.assertEqual(self.env.distance_calls,0)

    def test_20_invalid_uf_return_is_fatal(self):
        self.env.primary_fail=True;self.env.uf.Modeling.AskMassProps3d=lambda *a: ([],[])
        with self.assertRaisesRegex(RuntimeError,'Rueckgabefelder unvollstaendig'):self.imported()

    def test_21_import_point_check_still_blocks_wrong_shape(self):
        self.env.distance=1
        with self.assertRaisesRegex(RuntimeError,'Quellpunkt'):self.imported()
        self.assertEqual(self.env.face_measure_calls,2)

    def test_22_faulty_smoke_test_never_starts_house(self):
        self.env.primary_fail=True;self.env.uf_fail=True;calls=[]
        with self.assertRaisesRegex(RuntimeError,'FLAECHEN|Flaechen'):
            self.workflow(self.cfg(True),lambda *a:calls.append(True))
        self.assertEqual(calls,[])
        manifest=read_json(next((self.root/'runs').rglob('manifest_R09.json')))
        self.assertEqual(manifest['phase'],'NX_STEP_IMPORT_FUNKTIONSTEST')
        self.assertEqual(manifest['status'],'R09_ABGEBROCHEN_TEILERGEBNIS')
        self.assertIn('python',manifest['nx_runtime'])

    def test_23_whole_house_and_environment_use_new_measurements(self):
        self.env.legacy_fail_second=True;self.env.split_spec={'V01':7}
        s=self.workflow(self.cfg(True))
        self.assertEqual(s['house']['built_solids'],1361)
        self.assertEqual(s['total_imported_nx_faces'],122)
        self.assertEqual(s['total_checked_source_points'],20883)
        self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(self.env.face_measure_calls,2*(115+2))
        self.assertEqual(self.env.disposed_measures,self.env.face_measure_calls)

    def test_24_runtime_does_not_guess_nx_release_from_python(self):
        with self.env.active():r=runtime_information(self.adapter())
        self.assertFalse(r['nx_version_inferred_from_python'])
        self.assertIn('python',r);self.assertIsNone(r['UGII_FULL_VERSION'])

    def test_25_optional_version_read_error_not_cad_error(self):
        def fail(name):raise RuntimeError('OPTIONAL_VERSION_UNAVAILABLE')
        self.env.session.GetEnvironmentVariableValue=fail
        with self.env.active():r=runtime_information(self.adapter())
        self.assertEqual(r['UGII_VERSION_read_error'],'OPTIONAL_VERSION_UNAVAILABLE')

    def test_26_start_report_includes_measurement_and_runtime_diagnostics(self):
        s=(BASE/'00_NX_MODELL_ERZEUGEN_2406.py').read_text()
        self.assertIn("'nx_area_measurement'",s);self.assertIn("'nx_runtime'",s)
        self.assertIn('R11a-LAUFZEIT',s)
        ast.parse(s,feature_version=(3,10));ast.parse(s,feature_version=(3,12))

    def test_27_area_module_no_source_values_or_shape_modifications(self):
        import inspect
        self.assertEqual(tuple(inspect.signature(measure_surface_area).parameters),('adapter','body'))
        tree=ast.parse((BASE/'r09/area_measure.py').read_text())
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        for name in ('CreateFeature','CreateEmbeddedObject','SetUserAttribute','Commit','SmoothBSurfaces'):
            self.assertNotIn(name,calls)

    def test_28_stability_absolute_and_relative_limits(self):
        self.assertAlmostEqual(_stable_pair([10000,10000.5])['area_mm2'],10000.5)
        self.assertAlmostEqual(_stable_pair([1,1.09])['repeat_limit_mm2'],.1)
        with self.assertRaises(RuntimeError):_stable_pair([10000,10002])

    def test_29_uf_fallback_unstable_pair_not_accepted(self):
        self.env.primary_fail=True;self.env.accuracy_factors={.999:1.,.9999:1.02,.99999:1.,.999999:1.02,.9999999:1.}
        with self.assertRaisesRegex(RuntimeError,'nicht stabil'):self.imported()
        self.assertEqual(self.env.mass_calls,5)

    def test_30_unexpected_sheet_count_is_not_measurement_fallback(self):
        self.env.extra_sheet=True
        with self.assertRaisesRegex(ValueError,'Teilkoerperanzahl'):self.imported()
        self.assertEqual(self.env.face_measure_calls,0)

    def test_31_fallback_workflow_still_checks_all_points(self):
        self.env.primary_fail=True
        s=self.workflow()
        self.assertEqual(s['total_checked_source_points'],20883)
        self.assertEqual(self.env.mass_calls,2*(115+2))
        self.assertEqual(self.env.distance_calls,20941)

    def test_32_duplicate_faces_are_not_double_counted(self):
        with self.env.active():
            a=self.adapter();p=a.new_part(self.root/'direct.prt','DUP')
            b=Body(p,lambda:[[0,0,0],[1,1,1]]);b.IsSolidBody=False
            f=ns(Tag=4321,OwningPart=p,body=b)
            with patch.object(Body,'GetFaces',lambda obj:[f,f]), self.assertRaisesRegex(RuntimeError,'Doppelte Face'):
                a.surface_area_mm2(b)

    def test_33_primary_unit_lookup_problem_is_not_hidden(self):
        with self.env.active():
            a=self.adapter();p=a.new_part(self.root/'direct.prt','UNITS')
            b=Body(p,lambda:[[0,0,0],[1,1,1]]);b.IsSolidBody=False
            p.UnitCollection.FindObject=lambda name:None
            with self.assertRaisesRegex(RuntimeError,'Einheiten'):a.surface_area_mm2(b)
        self.assertEqual(self.env.mass_calls,0)

    def test_34_measured_area_failure_report_has_runtime_snapshot(self):
        self.env.primary_fail=True;self.env.uf_fail=True
        with self.assertRaises(SurfaceAreaMeasurementError) as cm:self.imported()
        self.assertIn('python',cm.exception.nx_runtime)
        row=cm.exception.nx_surface_check['last_sheet']
        self.assertEqual(row['checked_samples'],0)
        self.assertEqual(row['area_measurement']['status'],'FLAECHENMESSUNG_ABGEBROCHEN')


if __name__=='__main__':unittest.main(verbosity=2)
