"""Analytic distances and reuse gates for the independent M01 study checker."""
import copy
import hashlib
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


class ClearanceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('tools.check_m01_clearances'),
                             'The repeatable clearance checker is not implemented')
        self.tool = importlib.import_module('tools.check_m01_clearances')

    def test_separated_squares_have_three_mm_gap_and_consistent_witnesses(self):
        a = [[0, 0], [10, 0], [10, 10], [0, 10]]
        b = [[13, 2], [15, 2], [15, 8], [13, 8]]
        result = self.tool.clearance([a], [b])
        self.assertAlmostEqual(result['distance_mm'], 3)
        self.assertAlmostEqual(self.tool.math.dist(*result['points_mm']), 3)

    def test_filled_polygon_containment_is_zero_without_edge_crossing(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
        inner = [[1, 1], [2, 1], [2, 2], [1, 2]]
        self.assertEqual(self.tool.clearance([outer], [inner])['distance_mm'], 0)
        self.assertEqual(self.tool.clearance([inner], [outer])['distance_mm'], 0)

    def test_crossing_segments_intersect_at_the_reported_midpoint(self):
        distance, a, b = self.tool.segment_distance([0, 0], [2, 2], [0, 2], [2, 0])
        self.assertEqual((distance, a, b), (0, [1, 1], [1, 1]))

    def test_collinear_overlapping_segments_have_zero_gap(self):
        self.assertEqual(self.tool.segment_distance([0, 0], [2, 0], [1, 0], [3, 0])[0], 0)

    def test_degenerate_segments_remain_valid_points(self):
        self.assertEqual(self.tool.segment_distance([0, 0], [0, 0], [3, 4], [3, 4])[0], 5)

    def test_property_boundary_mode_keeps_the_two_mm_inner_clearance(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
        inner = [[2, 2], [8, 2], [8, 8], [2, 8]]
        self.assertEqual(self.tool.clearance([inner], [outer], filled=False)['distance_mm'], 2)
        self.assertEqual(self.tool.clearance([inner], [outer])['distance_mm'], 0)

    def test_concave_notch_is_not_filled_by_a_convex_hull(self):
        concave = [[0, 0], [10, 0], [10, 10], [6, 10], [6, 4], [4, 4], [4, 10], [0, 10]]
        self.assertTrue(self.tool.inside([2, 8], concave))
        self.assertFalse(self.tool.inside([5, 8], concave))
        notch = [[4.5, 7], [5.5, 7], [5.5, 8], [4.5, 8]]
        self.assertAlmostEqual(self.tool.clearance([concave], [notch])['distance_mm'], .5)

    def test_invalid_projection_is_rejected_instead_of_reporting_infinity(self):
        square = [[0, 0], [1, 0], [1, 1], [0, 1]]
        for polygons in ([], [[[0, 0], [1, 0]]], [[[0, 0], [1, 0], [float('nan'), 1]]]):
            with self.subTest(polygons=polygons), self.assertRaises(ValueError):
                self.tool.clearance(polygons, [square])

    def test_spatial_search_preserves_nearest_of_many_disconnected_rings(self):
        square = [[0, 0], [1, 0], [1, 1], [0, 1]]
        others = [[[100+10*i, 100], [101+10*i, 100], [101+10*i, 101], [100+10*i, 101]]
                  for i in range(18)]
        others.append([[-3, 4], [-2, 4], [-2, 5], [-3, 5]])
        self.assertAlmostEqual(self.tool.clearance([square], others)['distance_mm'], 13**.5)

    def test_cached_plan_requires_the_pinned_file_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'plan.json'
            path.write_text('{"units":"mm"}', encoding='utf-8')
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(self.tool.read_pinned_plan(path, sha)['units'], 'mm')
            path.write_text('{"units":"m"}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                self.tool.read_pinned_plan(path, sha)

    def test_source_mutation_and_wrong_expected_quantity_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {}
            for role, relative in self.tool.default_sources().items():
                path = root/relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}', encoding='utf-8')
                sources[role] = {'role': role, 'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            generator = root/'renovierung/k02/example.py'
            generator.parent.mkdir(parents=True, exist_ok=True)
            generator.write_text('# example', encoding='utf-8')
            record = {'path': 'renovierung/k02/example.py', 'sha256': hashlib.sha256(generator.read_bytes()).hexdigest()}
            field = {'id': 'F1', 'native_candidate': True, 'volume_m3': 1,
                     'stockpile': {'main': {'volume_mm3': 1.05e9}, 'reserve_1_25': {'volume_mm3': 1.25e9}}}
            plan = {'units': 'mm', 'construction_release': False, 'fields': [field],
                    'provenance': {'config': {}, 'inputs': list(sources.values()), 'generators': [record]}}
            expected = {'fields': [copy.deepcopy(field)]}
            self.tool.validate_plan(plan, root, {}, expected)
            wrong = copy.deepcopy(plan)
            wrong['fields'][0]['stockpile']['main']['volume_mm3'] *= 2
            with self.assertRaisesRegex(ValueError, 'quantity'):
                self.tool.validate_plan(wrong, root, {}, expected)
            (root/next(iter(sources.values()))['path']).write_text('{"changed":true}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.tool.validate_plan(plan, root, {}, expected)


if __name__ == '__main__':
    unittest.main()
