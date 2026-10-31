"""R09e: observed coarse/fine DGM discrepancy, bounded refinement and failure paths.

Only the FIRST TWO DGM numbers below come from the uploaded NX log. Later values
in all tests are deliberately synthetic, not NX measurements or proof of NX success.
The source-area value is never passed into the runtime measurement function.
"""
import ast
import contextlib
import io
import math
import types
import unittest
from unittest.mock import patch
import test_r09 as sim
from test_r09 import BASE, JOB, Body, ns, FakeNXException
from r09.core import read_json, write_json, sha256
from r09.area_measure import (measure_surface_area, SurfaceAreaMeasurementError,
    ACCURACY_VALUES, ACCURACY_SCHEDULE, REFINEMENT_ACCURACIES,
    REFINED_WINDOW_SIZE, STABILITY_RELATIVE, STABILITY_ABSOLUTE_MM2,
    PRIMARY, FALLBACK)
from r09.surface_check import area_checked, DISTANCE_TOLERANCE_MM, AREA_RELATIVE_TOLERANCE

DGM = next(p for p in JOB['parts'] if p['id']=='DGM')
SOURCE = DGM['geometry_reference']['sheets'][0]['area_mm2']
OBSERVED = (8358381179.944885, 8361523002.046139)
# These are hypothetical later measurements for testing program logic ONLY.
HYPOTHETICAL_CONVERGED = OBSERVED + (SOURCE-100000., SOURCE-10000., SOURCE-1000.)


class AdaptiveAreaTests(unittest.TestCase):
    setUp = sim.NXSimulationTests.setUp
    adapter = sim.NXSimulationTests.adapter
    cfg = sim.NXSimulationTests.cfg
    workflow = sim.NXSimulationTests.workflow

    def factors(self, values):
        self.env.accuracy_factors = dict(zip(ACCURACY_SCHEDULE, [v/SOURCE for v in values]))

    def direct(self, values, old=False):
        self.factors(values)
        with self.env.active():
            a=self.adapter();p=a.new_part(self.root/'direct.prt','DGM_TEST')
            b=Body(p,lambda:[[0,0,0],[1,1,1]])
            b.IsSolidBody=False;b._reference=DGM['geometry_reference']['sheets'][0];b._spec_id='DGM'
            if old:
                module=types.ModuleType('r09._original_d');module.__package__='r09'
                text=(BASE/'tests/fixtures/area_measure_R09d_historisch.txt').read_text()
                exec(compile(text,'area_measure_R09d_historisch.py','exec'),module.__dict__)
                return module.measure_surface_area(a,b)
            return measure_surface_area(a,b)

    def imported(self, values, spec=DGM):
        self.factors(values)
        with self.env.active():
            return self.adapter().import_surface_part(self.root, BASE/spec['step_file'],spec,self.definition)

    def test_01_actual_old_function_reproduces_observed_abort(self):
        with self.assertRaisesRegex(RuntimeError,'3141822.1 mm2') as cm:
            self.direct(OBSERVED,old=True)
        d=cm.exception.nx_area_measurement
        self.assertEqual(d['requested_accuracies'],[.999,.9999])
        self.assertEqual(self.env.face_measure_calls,2)
        for got,wanted in zip(d['attempts'][0]['measurements'],OBSERVED):
            self.assertAlmostEqual(got['area_mm2'],wanted,places=4)

    def test_02_same_first_two_values_can_continue_to_finer_evaluations(self):
        value,d=self.direct(HYPOTHETICAL_CONVERGED)
        self.assertTrue(d['refinement_used']);self.assertEqual(d['measurement_count'],4)
        self.assertEqual(d['requested_accuracies'],list(ACCURACY_SCHEDULE[:4]))
        self.assertAlmostEqual(value,HYPOTHETICAL_CONVERGED[3],places=3)
        self.assertEqual(d['convergence_window_size'],3)
        self.assertLessEqual(d['convergence_span_mm2'],d['convergence_limit_mm2'])
        self.assertEqual(self.env.disposed_measures,4);self.assertEqual(self.env.mass_calls,0)

    def test_03_stable_initial_pair_retains_fast_two_call_path(self):
        value,d=self.direct([SOURCE-1000,SOURCE])
        self.assertFalse(d['refinement_used']);self.assertEqual(d['measurement_count'],2)
        self.assertEqual(self.env.face_measure_calls,2)

    def test_04_one_stable_fine_pair_is_not_enough_after_initial_mismatch(self):
        self.direct(HYPOTHETICAL_CONVERGED)
        self.assertEqual(self.env.face_measure_calls,4)

    def test_05_small_pairwise_drift_but_excessive_three_value_range_stops(self):
        v=[SOURCE*x for x in (1.,.998,.99806,.99812,.99818)]
        with self.assertRaisesRegex(RuntimeError,'nach 5 Auswertungen') as cm:self.direct(v)
        a=cm.exception.nx_area_measurement['attempts'][0]
        self.assertTrue(a['comparisons'][-1]['stable'])
        self.assertFalse(a['refined_windows'][-1]['passed'])
        self.assertEqual(self.env.mass_calls,0)

    def test_06_fifth_level_available_without_unbounded_loop(self):
        v=OBSERVED+(SOURCE+1000000.,SOURCE+1050000.,SOURCE+1080000.)
        value,d=self.direct(v)
        self.assertEqual(d['measurement_count'],5)
        self.assertAlmostEqual(value,v[-1],places=3)
        self.assertFalse(d['attempts'][0]['refined_windows'][0]['passed'])
        self.assertTrue(d['attempts'][0]['refined_windows'][1]['passed'])

    def test_07_oscillation_never_falls_back_to_nicer_api(self):
        v=[SOURCE*x for x in (1.,1.01,1.,1.01,1.)]
        with self.assertRaisesRegex(RuntimeError,'nicht stabil') as cm:self.direct(v)
        self.assertEqual(self.env.face_measure_calls,5);self.assertEqual(self.env.mass_calls,0)
        self.assertEqual(len(cm.exception.nx_area_measurement['attempts']),1)

    def test_08_all_original_acceptance_tolerances_unchanged(self):
        self.assertEqual(STABILITY_RELATIVE,.0001)
        self.assertEqual(STABILITY_ABSOLUTE_MM2,.1)
        self.assertEqual(AREA_RELATIVE_TOLERANCE,.001)
        self.assertEqual(DISTANCE_TOLERANCE_MM,.25)

    def test_09_latest_value_not_average_or_closest_to_source(self):
        v=OBSERVED+(SOURCE-200000.,SOURCE-350000.,SOURCE-300000.)
        value,d=self.direct(v)
        self.assertEqual(d['measurement_count'],4)
        self.assertAlmostEqual(value,v[3],places=3)
        self.assertGreater(abs(value-SOURCE),abs(v[2]-SOURCE))

    def test_10_invalid_refined_value_does_not_trigger_fallback(self):
        with self.assertRaisesRegex(RuntimeError,'endliche'):self.direct(OBSERVED+(math.nan,))
        self.assertEqual(self.env.mass_calls,0);self.assertEqual(self.env.disposed_measures,3)

    def test_11_cleanup_failure_on_refinement_stops(self):
        self.factors(HYPOTHETICAL_CONVERGED)
        original=self.env.session.Parts.NewDisplay
        def new(path,unit):
            p=original(path,unit);inner=p.MeasureManager.NewFaceProperties
            def measure(au,lu,acc,faces):
                obj=inner(au,lu,acc,faces)
                if acc==.99999:
                    def bad():raise RuntimeError('REFINED_DISPOSE_FAILED')
                    obj.Dispose=bad
                return obj
            p.MeasureManager.NewFaceProperties=measure
            return p
        self.env.session.Parts.NewDisplay=new
        with self.assertRaisesRegex(RuntimeError,'REFINED_DISPOSE_FAILED'):self.imported(HYPOTHETICAL_CONVERGED)
        self.assertEqual(self.env.mass_calls,0)

    def test_12_fixed_mode_fallback_uses_same_bounded_refinement(self):
        self.env.primary_fail=True
        value,d=self.direct(HYPOTHETICAL_CONVERGED)
        self.assertEqual(d['selected_method'],FALLBACK)
        self.assertTrue(d['fallback_used']);self.assertTrue(d['refinement_used'])
        self.assertEqual(self.env.mass_calls,4)
        self.assertTrue(all(a[5]==1 for a in self.env.mass_args))

    def test_13_fixed_mode_nonconvergence_remains_error(self):
        self.env.primary_fail=True
        v=[SOURCE*x for x in (1.,1.01,1.,1.01,1.)]
        with self.assertRaisesRegex(RuntimeError,'nicht stabil'):self.direct(v)
        self.assertEqual(self.env.mass_calls,5)

    def test_14_source_comparison_still_rejects_stable_wrong_result(self):
        v=[SOURCE*x for x in (.97,.98,.98001,.98002,.98003)]
        with self.assertRaisesRegex(RuntimeError,'Flaecheninhalt abweichend'):self.imported(v)
        self.assertEqual(self.env.distance_calls,0)

    def test_15_all_dgm_samples_checked_after_successful_refinement(self):
        p,s,c=self.imported(HYPOTHETICAL_CONVERGED)
        self.assertEqual(c['checked_source_points'],16748)
        self.assertEqual(self.env.distance_calls,16748)
        report=read_json(self.root/'IMPORTPRUEFUNG_DGM_R09e.json')
        self.assertEqual(report['sheets_checked'][0]['area_measurement']['measurement_count'],4)

    def test_16_shape_error_not_masked_by_successful_area_refinement(self):
        self.env.distance=1.
        with self.assertRaisesRegex(RuntimeError,'Quellpunkt'):self.imported(HYPOTHETICAL_CONVERGED)
        r=read_json(self.root/'IMPORTPRUEFUNG_DGM_R09e.json')
        self.assertEqual(r['status'],'IMPORTGEOMETRIE_ABGEBROCHEN')
        self.assertEqual(r['sheets_checked'][0]['checked_samples'],1)

    def test_17_only_observed_pair_alone_does_not_prove_geometry(self):
        self.assertTrue(area_checked(SOURCE,OBSERVED[-1])['area_passed'])
        self.assertGreater(abs(OBSERVED[-1]-OBSERVED[0]),STABILITY_RELATIVE*OBSERVED[-1])
        self.assertAlmostEqual((OBSERVED[-1]-OBSERVED[0])/1e6,3.1418221012535095)

    def test_18_bounded_schedule_uses_unique_increasing_values_below_one(self):
        self.assertEqual(len(ACCURACY_SCHEDULE),5)
        self.assertEqual(len(set(ACCURACY_SCHEDULE)),5)
        self.assertEqual(tuple(sorted(ACCURACY_SCHEDULE)),ACCURACY_SCHEDULE)
        self.assertTrue(all(0<a<1 for a in ACCURACY_SCHEDULE))

    def test_19_no_source_dependency_and_no_geometry_write_in_measurement(self):
        import inspect
        self.assertEqual(list(inspect.signature(measure_surface_area).parameters),['adapter','body'])
        tree=ast.parse((BASE/'r09/area_measure.py').read_text())
        calls=[n.func.attr for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)]
        for forbidden in ('Commit','CreateFeature','SetUserAttribute','SurfaceProperties_s','importStep'):
            self.assertNotIn(forbidden,calls)

    def test_20_full_environment_simulated_with_refinement_checks_all_sources(self):
        self.factors(HYPOTHETICAL_CONVERGED)
        s=self.workflow()
        self.assertEqual(s['total_checked_source_points'],20883)
        self.assertEqual(self.env.face_measure_calls,4*(115+2))

    def test_21_error_keeps_all_evaluations_and_attempt_status(self):
        v=[SOURCE*x for x in (1.,1.01,1.,1.01,1.)]
        with self.assertRaises(SurfaceAreaMeasurementError) as cm:self.direct(v)
        d=cm.exception.nx_area_measurement
        self.assertEqual(d['attempts'][0]['status'],'KONVERGENZ_NICHT_ERREICHT')
        self.assertEqual(len(d['attempts'][0]['measurements']),5)
        self.assertEqual(d['requested_accuracies'],list(ACCURACY_SCHEDULE))
        self.assertFalse(d['source_value_as_fallback_allowed'])

    def test_22_real_observed_fixture_identifies_no_fine_results_as_user_data(self):
        f=read_json(BASE/'tests/fixtures/DGM_MESSWERTE_NX_R09d.json')
        self.assertEqual(tuple(x['area_mm2'] for x in f['measurements']),OBSERVED)
        self.assertEqual(len(f['measurements']),2)
        self.assertFalse(f['later_refinement_results_available'])

if __name__=='__main__':unittest.main(verbosity=2)
