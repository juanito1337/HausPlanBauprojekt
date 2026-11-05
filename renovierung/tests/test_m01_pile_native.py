"""Pure stockpile-role and exact vertex-box checks; no native NX claim."""
import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'm01/pile_native.py'


class PileIntentTests(unittest.TestCase):
    def setUp(self):
        if not MODULE.is_file():
            self.fail('The staging native pile module is missing')
        spec = importlib.util.spec_from_file_location('staging_pile_native', MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_roles_follow_unique_component_volumes_not_import_iterator_order(self):
        expected = {'pile_main': [2.0, 3.0], 'pile_reserve': [8.0]}
        self.assertEqual(self.module.assign_roles([8.0, 3.0, 2.0], expected),
                         {'pile_main': [1, 2], 'pile_reserve': [0]})
        self.assertEqual(self.module.assign_roles([2.0, 8.0, 3.0], expected),
                         {'pile_main': [0, 2], 'pile_reserve': [1]})

    def test_equal_role_candidates_abort_instead_of_arbitrary_assignment(self):
        with self.assertRaises(ValueError):
            self.module.assign_roles([2.0, 2.0], {'pile_main': [2.0], 'pile_reserve': [2.0]})

    def test_component_mismatch_nonfinite_or_missing_bodies_are_rejected(self):
        for values in ([8.0, 6.0], [8.0], [float('nan'), 2.0], [8.0, -2.0]):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.module.assign_roles(values, {'pile_main': [2.0], 'pile_reserve': [8.0]})

    def test_vertex_box_combines_translated_facets_without_axis_assumptions(self):
        self.assertEqual(self.module.vertex_bbox([[7, -2, 30], [10, -5, 32], [8, 1, 29]]),
                         [7, -5, 29, 10, 1, 32])
        for points in ([], [[0, 1]], [[0, float('inf'), 2]]):
            with self.subTest(points=points), self.assertRaises(ValueError):
                self.module.vertex_bbox(points)

    def test_retained_body_tags_and_names_are_exact_but_massprop_ulp_is_allowed(self):
        before = {39562: {'name': 'K02_EXCAVATION_00', 'measurement': {
            'body_count': 1, 'component_volumes_m3': [20.25509838369136], 'volume_m3': 20.25509838369136}}}
        after = {39562: {'name': 'K02_EXCAVATION_00', 'measurement': {
            'body_count': 1, 'component_volumes_m3': [20.255098383691358], 'volume_m3': 20.255098383691358}}}
        self.module.check_preserved(before, after)
        with self.assertRaises(ValueError):
            self.module.check_preserved(before, {999: after[39562]})
        after[39562]['measurement']['component_volumes_m3'] = [20.2551]
        with self.assertRaises(ValueError):
            self.module.check_preserved(before, after)


if __name__ == '__main__':
    unittest.main()
