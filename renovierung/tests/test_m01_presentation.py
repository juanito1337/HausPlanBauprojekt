"""Pure camera geometry tests; no NX mocks and no claim of native rendering."""
import importlib
import itertools
import math
import unittest


class CameraSpecTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.m01.presentation')
        except ModuleNotFoundError:
            self.fail('The M01 presentation module is missing')

    def test_house_and_property_fit_inside_virtual_view(self):
        # A translated, sloping property tens of metres across, with a tall house.
        points = [[-22000, -31000, -4400], [41000, -31000, -3200],
                  [37000, 26000, 1700], [-16000, 23000, 900], [5000, 4000, 14500]]
        spec = self.module.camera_spec(points)
        self.assertEqual(spec['origin_mm'], [9500, -2500, 5050])
        matrix = spec['matrix']
        self.assertEqual(len(matrix), 9)
        self.assertTrue(0 < spec['scale'] < 0.01)
        # Include every BBox corner: fitting the boundary alone can clip the house.
        limits = [(min(p[i] for p in points), max(p[i] for p in points)) for i in range(3)]
        for point in points + list(itertools.product(*limits)):
            delta = [point[i] - spec['origin_mm'][i] for i in range(3)]
            for axis in range(3):
                screen_mm = sum(matrix[axis * 3 + i] * delta[i] for i in range(3)) * spec['scale']
                self.assertLessEqual(abs(screen_mm), 70 + 1e-10)

    def test_isometry_is_orthonormal_right_handed_and_has_equal_axis_foreshortening(self):
        spec = self.module.camera_spec([[0, 0, 0], [40000, 25000, 12000]])
        rows = [spec['matrix'][i:i + 3] for i in (0, 3, 6)]
        for i, a in enumerate(rows):
            for j, b in enumerate(rows):
                self.assertAlmostEqual(sum(x * y for x, y in zip(a, b)), float(i == j))
        cross = [rows[0][1] * rows[1][2] - rows[0][2] * rows[1][1],
                 rows[0][2] * rows[1][0] - rows[0][0] * rows[1][2],
                 rows[0][0] * rows[1][1] - rows[0][1] * rows[1][0]]
        self.assertAlmostEqual(sum(a * b for a, b in zip(cross, rows[2])), 1.0)
        projections = [math.hypot(rows[0][i], rows[1][i]) for i in range(3)]
        self.assertAlmostEqual(projections[0], projections[1])
        self.assertAlmostEqual(projections[1], projections[2])

    def test_translation_changes_only_center_and_uniform_scaling_preserves_framing(self):
        points = [[-13000, 0, -3500], [28000, 19000, 12000], [5000, -21000, 500]]
        original = self.module.camera_spec(points)
        delta = [250000, -800000, 100000]
        translated = self.module.camera_spec([[p[i] + delta[i] for i in range(3)] for p in points])
        self.assertEqual(translated['matrix'], original['matrix'])
        self.assertEqual(translated['scale'], original['scale'])
        self.assertEqual(translated['origin_mm'], [original['origin_mm'][i] + delta[i] for i in range(3)])
        enlarged = self.module.camera_spec([[v * 3 for v in p] for p in points])
        self.assertAlmostEqual(enlarged['scale'] * 3, original['scale'])
        self.assertEqual(enlarged['origin_mm'], [v * 3 for v in original['origin_mm']])
        self.assertEqual(self.module.camera_spec(list(reversed(points))), original)

    def test_vertical_and_planar_inputs_fit_without_artificial_depth(self):
        for points in ([[0, 0, -10000], [0, 0, 50000]],
                       [[-40000, -20000, 0], [40000, 20000, 0]]):
            with self.subTest(points=points):
                spec = self.module.camera_spec(points)
                self.assertTrue(math.isfinite(spec['scale']) and spec['scale'] > 0)
                self.assertGreater(spec['matrix'][5], 0, 'World Z must point upward in the view')

    def test_invalid_nonfinite_and_degenerate_inputs_are_rejected(self):
        cases = [None, [], [[0, 0, 0]], [[1, 2, 3], [1, 2, 3]],
                 [[0, 0], [1, 2]], [[0, 0, 0, 0], [1, 2, 3, 4]],
                 [[0, 0, 0], [1, True, 3]], [[0, 0, 0], [1, '2', 3]],
                 [[0, 0, 0], [1, float('nan'), 3]], [[0, 0, 0], [float('inf'), 2, 3]],
                 [[-1e308, 0, 0], [1e308, 1, 1]]]
        for points in cases:
            with self.subTest(points=points):
                with self.assertRaises(ValueError):
                    self.module.camera_spec(points)


if __name__ == '__main__':
    unittest.main()
