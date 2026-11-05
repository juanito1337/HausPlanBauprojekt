"""Source-backed M01 terrain partition checks, without NX execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest

from renovierung.k02.geometry import area, overlap_area, validate_mesh
from renovierung.m01.context import create_context

ROOT = Path(__file__).resolve().parents[2]


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = {'source_paths': {'grid': 'grid.json', 'height': 'height.json', 'house': 'house.json'},
                       'terrain_tolerance_mm': 25, 'main_formation_z_mm': 0,
                       'excavation_slope_ratio': 1}
        self.grid = {'shape': [5, 5], 'nodes_mm': [[i*1000, j*1000, 100] for i in range(5) for j in range(5)]}
        self.height = {'mode': 'PLAN_ANNAHME', 'anchor_xy_mm': [0, 0], 'ground_z_relative_eg_mm': 0}
        self.boundary = {'points_local_mm': [[0, 0], [4000, 0], [4000, 4000], [0, 4000]], 'closed': True}
        self.layout = {'fields': [], 'height_registration': {'translation_mm': [0, 0, -100],
                       'mode': 'PLAN_ANNAHME', 'applied_once_to_source_grid': True},
                       'provenance': {'plan_provenance': {'config': self.config}}}

    def write_sources(self):
        values = {'grid.json': self.grid, 'height.json': self.height,
                  'house.json': {'site': {'boundary': self.boundary}},
                  'renovierung/k02/study_config.json': self.config}
        for path, value in values.items():
            target = self.root/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding='utf-8')

    def field(self, fid, origin, length=2000, width=2000):
        return {'id': fid, 'native': True, 'origin_mm': origin, 'tangent': [1, 0], 'normal': [0, 1],
                'length_mm': length, 'width_mm': width, 'formation_z_mm': 0,
                'study_terrain': {'TIN_subdivisions': 1, 'max_vertical_error_mm': 0,
                                  'reference_translation_mm': [0, 0, -100], 'cutout_applied': True,
                                  'source_is_bilinear': True}}

    @staticmethod
    def top_polygons(mesh):
        out = []
        for face in mesh['faces']:
            p = [mesh['vertices'][i] for i in face]
            if area([v[:2] for v in p]) > 1e-8:
                out.append([v[:2] for v in p])
        return out

    def test_overlapping_crop_masks_cover_property_once_and_leave_far_ground(self):
        self.layout['fields'] = [self.field('A', [0, 0]), self.field('B', [1000, 1000])]
        self.write_sources()
        result = create_context(self.root, self.layout, include_mesh=True)
        self.assertEqual(result['field_regions'], {'A': [0, 2, 0, 2], 'B': [1, 3, 1, 3]})
        groups = {tuple(g['exclude_for']): g for g in result['groups']}
        self.assertEqual({k: g['area_m2'] for k, g in groups.items()}, {(): 9, ('A',): 3, ('B',): 3, ('A', 'B'): 1})
        self.assertEqual(result['area_m2'], 16)
        self.assertEqual(sum(g['volume_m3'] for g in groups.values()), 3.2)
        footprints = [self.top_polygons(g['mesh']) for g in groups.values()]
        for i, polygons in enumerate(footprints):
            self.assertAlmostEqual(sum(area(p) for p in polygons)/1e6, list(groups.values())[i]['area_m2'])
            for others in footprints[i+1:]:
                self.assertAlmostEqual(overlap_area(polygons, others, convex_b=True), 0)
        for fid in ('A', 'B'):
            self.assertEqual(sum(g['area_m2'] for g in groups.values() if fid not in g['exclude_for']), 12)
        for group in groups.values():
            measurement = validate_mesh(group['mesh'])
            self.assertEqual(group['body_count'], measurement['expected_body_count'])
            self.assertAlmostEqual(group['volume_m3'], measurement['volume_mm3']/1e9)
            self.assertEqual(group['component_volumes_m3'], sorted(v/1e9 for v in measurement['component_volumes_mm3']))

    def test_sloped_clipped_concave_boundary_preserves_affine_surface_and_thickness(self):
        self.grid['nodes_mm'] = [[i*1000, j*1000, 100+i*100+j*50] for i in range(5) for j in range(5)]
        self.boundary['points_local_mm'] = [[250, 250], [3750, 250], [3750, 1250], [1250, 1250], [1250, 3750], [250, 3750]]
        self.write_sources()
        result = create_context(self.root, self.layout, include_mesh=True)
        self.assertAlmostEqual(result['area_m2'], 6)
        self.assertAlmostEqual(sum(g['volume_m3'] for g in result['groups']), 1.2)
        for group in result['groups']:
            for x, y, z in group['mesh']['vertices']:
                gap = 0.1*x+0.05*y-z
                self.assertTrue(abs(gap)<1e-7 or abs(gap-200)<1e-7)
        self.assertEqual(result['boundary_xyz_mm'][0], [250, 250, 37.5])

    def test_lightweight_result_deterministic_and_input_edits_invalidate_cache(self):
        self.layout['fields'] = [self.field('B', [1000, 1000]), self.field('A', [0, 0])]
        self.write_sources()
        first = create_context(self.root, self.layout)
        self.assertTrue(all('mesh' not in g for g in first['groups']))
        self.layout['fields'].reverse()
        self.assertEqual(first, create_context(self.root, self.layout))
        for path, expected in first['source_hashes'].items():
            self.assertEqual(expected, hashlib.sha256((self.root/path).read_bytes()).hexdigest())
        self.grid['nodes_mm'][12][2] += 10
        for field in self.layout['fields']:
            field['study_terrain']['max_vertical_error_mm'] = 2.5
        self.write_sources()
        changed = create_context(self.root, self.layout)
        self.assertNotEqual(first['source_hashes'], changed['source_hashes'])
        self.assertNotEqual(first['field_regions'], changed['field_regions'])
        first['groups'][0]['exclude_for'].append('MUTATED')
        self.assertNotIn('MUTATED', create_context(self.root, self.layout)['groups'][0]['exclude_for'])

    def test_rotated_source_grid_uses_cell_domain_not_world_axis_cutout(self):
        self.grid['nodes_mm'] = [[(i-j)*1000, (i+j)*1000, 100] for i in range(5) for j in range(5)]
        self.boundary['points_local_mm'] = [[0, 0], [4000, 4000], [0, 8000], [-4000, 4000]]
        self.layout['fields'] = [self.field('A', [0, 0], 1000, 1000)]
        self.write_sources()
        result = create_context(self.root, self.layout, include_mesh=True)
        self.assertEqual(result['field_regions'], {'A': [0, 1, 0, 1]})
        self.assertEqual({tuple(g['exclude_for']): g['area_m2'] for g in result['groups']}, {(): 30, ('A',): 2})
        self.assertEqual(result['area_m2'], 32)

    def test_clipped_bilinear_source_uses_existing_refined_affine_tin_heights(self):
        self.grid = {'shape': [3, 3], 'nodes_mm': [[i*1000, j*1000, 100+400*i*j] for i in range(3) for j in range(3)]}
        self.boundary['points_local_mm'] = [[100, 200], [400, 200], [400, 450], [100, 450]]
        self.write_sources()
        result = create_context(self.root, self.layout, include_mesh=True)
        self.assertEqual([p[2] for p in result['boundary_xyz_mm']], [20, 40, 80, 20])
        self.assertAlmostEqual(result['area_m2'], 0.075)
        top = [p for g in result['groups'] for p in g['mesh']['vertices'] if p[2] >= 0]
        for x, y, z in top:
            self.assertAlmostEqual(z, 0.2*min(x, y))

    def test_crop_uses_global_grid_maximum_plus_tin_error_and_integer_clamping(self):
        self.grid['nodes_mm'][-1][2] = 1100
        field = self.field('A', [1000, 1000], 500, 500)
        field['study_terrain'].update(TIN_subdivisions=4, max_vertical_error_mm=15.625)
        self.layout['fields'] = [field]
        self.write_sources()
        result = create_context(self.root, self.layout)
        self.assertEqual(result['field_regions'], {'A': [0, 3, 1, 3]})
        self.assertAlmostEqual(next(g['area_m2'] for g in result['groups'] if g['exclude_for'] == ['A']), 6)

    def test_malformed_holes_crossing_or_outside_boundary_and_stale_metadata_fail(self):
        self.layout['fields'] = [self.field('A', [0, 0])]
        original = copy.deepcopy(self.boundary)
        for points in ([], [[0, 0], [4000, 4000], [0, 4000], [4000, 0]],
                       [[-1, 0], [4000, 0], [4000, 4000], [0, 4000]],
                       [[0, 0], [4000, 0], [4000, float('nan')]],
                       [[0, 0, 0], [4000, 0], [4000, 4000]],
                       [[0, 0], [4000, 0], [4000, 4000], [0, 0], [0, 4000]]):
            with self.subTest(points=points):
                self.boundary['points_local_mm'] = points
                self.write_sources()
                with self.assertRaises(ValueError): create_context(self.root, self.layout)
        self.boundary = copy.deepcopy(original)
        self.boundary['holes'] = [[[100, 100], [200, 100], [200, 200]]]
        self.write_sources()
        with self.assertRaises(ValueError): create_context(self.root, self.layout)
        self.boundary = original
        self.write_sources()
        for key, value in (('TIN_subdivisions', 2), ('reference_translation_mm', [0, 0, 0])):
            layout = copy.deepcopy(self.layout)
            layout['fields'][0]['study_terrain'][key] = value
            with self.assertRaises(ValueError): create_context(self.root, layout)
        layout = copy.deepcopy(self.layout)
        layout['fields'].append(copy.deepcopy(layout['fields'][0]))
        with self.assertRaises(ValueError): create_context(self.root, layout)


class RealContextTests(unittest.TestCase):
    def test_real_sources_complete_partition_without_layout_meshes(self):
        current = json.loads((ROOT/'cad/nx/m01/CURRENT.json').read_text())
        layout = json.loads((ROOT/'cad/nx/m01'/current['directory']/'BUILD.json').read_text())['layout']
        start = time.perf_counter()
        result = create_context(ROOT, layout, include_mesh=True)
        elapsed = time.perf_counter()-start
        self.assertAlmostEqual(result['area_m2'], 1829.1091155487732, places=7)
        self.assertEqual(len(result['field_regions']), 22)
        self.assertAlmostEqual(sum(g['area_m2'] for g in result['groups']), result['area_m2'], places=7)
        self.assertAlmostEqual(sum(g['volume_m3'] for g in result['groups']), result['area_m2']*0.2, places=7)
        self.assertLess(elapsed, 120, 'Context generation must remain bounded')
        start = time.perf_counter()
        light = create_context(ROOT, layout)
        self.assertLess(time.perf_counter()-start, 5, 'Repeated layout checks must reuse source-derived geometry')
        self.assertTrue(all('mesh' not in g for g in light['groups']))
        print('M01 context: %.3fs, %d groups, %d vertices, %d faces' %
              (elapsed, len(result['groups']), sum(len(g['mesh']['vertices']) for g in result['groups']),
               sum(len(g['mesh']['faces']) for g in result['groups'])))


if __name__ == '__main__': unittest.main()
