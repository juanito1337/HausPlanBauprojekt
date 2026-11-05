"""Real pure transfer/quantity contracts; these tests do not simulate NX."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import unittest

from renovierung.k02.geometry import surface_mesh


def box(x0, x1, z0, z1):
    return surface_mesh([([[x0, 0], [x1, 0], [x1, 1000], [x0, 1000]],
                          (0, 0, z0), (0, 0, z1))])


def join(*meshes):
    result = {'vertices': [], 'faces': []}
    for mesh in meshes:
        offset = len(result['vertices'])
        result['vertices'].extend(mesh['vertices'])
        result['faces'].extend([[offset + i for i in face] for face in mesh['faces']])
    return result


def fixture():
    geometry = {
        'soil': {'mesh': join(box(-500, 0, -6000, 4000), box(0, 500, -6000, 4000)),
                 'body_count': 2, 'volume_m3': 10.0, 'component_volumes_m3': [5.0, 5.0],
                 'bbox_mm': [-500, 0, -6000, 500, 1000, 4000]},
        'cut_soil': {'mesh': join(box(-500, 0, -6000, 4000), box(0, 500, -6000, -1600)),
                     'body_count': 2, 'volume_m3': 7.2, 'component_volumes_m3': [2.2, 5.0],
                     'bbox_mm': [-500, 0, -6000, 500, 1000, 4000]},
        'excavation': {'mesh': box(0, 500, -1600, 4000), 'body_count': 1, 'volume_m3': 2.8,
                       'component_volumes_m3': [2.8], 'bbox_mm': [0, 0, -1600, 500, 1000, 4000]},
        'pile_main': {'mesh': box(10000, 11000, 0, 3000), 'body_count': 1, 'volume_m3': 3.0,
                      'component_volumes_m3': [3.0], 'bbox_mm': [10000, 0, 0, 11000, 1000, 3000]},
        'pile_reserve': {'mesh': box(10000, 11000, 0, 3500), 'body_count': 1, 'volume_m3': 3.5,
                         'component_volumes_m3': [3.5], 'bbox_mm': [10000, 0, 0, 11000, 1000, 3500]}}
    return {'id': 'PS11-F01', 'sector_id': 'PS11', 'native_candidate': True, 'diagnostic_only': False,
            'assumed_slab_underside_z_mm': -1500, 'formation_z_mm': -1600,
            'construction_release': False, 'blockers': [], 'conflicts': [], 'warnings': ['FOUNDATION_UNVERIFIED'],
            'status': 'GEOMETRY_CANDIDATE_UNVERIFIED', 'volume_m3': 2.8, 'diagnostic_volume_m3': 2.8,
            'display_marker': {'line': [[0, 100, 4200], [0, 900, 4200]], 'label': [0, 500, 4250]},
            'geometry': geometry,
            'measurements': {role: {k: geometry[role][k] for k in
                                    ('body_count', 'volume_m3', 'component_volumes_m3')}
                             for role in ('cut_soil', 'excavation', 'pile_main', 'pile_reserve')}}


class NativeFieldContractTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.anbau.nx_fields')
        except ModuleNotFoundError:
            self.fail('The separate Anbau native field generator is missing')

    def test_free_field_retains_two_cut_soil_bodies_and_four_compatible_roles(self):
        spec = self.module.field_spec(fixture())
        self.assertEqual(spec['file'], 'PS11-F01_STUDY.prt')
        self.assertEqual(spec['construction_method'], 'DIRECT_CUT_COMPONENTS')
        self.assertEqual(spec['measurements']['cut_soil']['body_count'], 2)
        self.assertEqual(spec['effective_excavation_m3'], 2.8)
        self.assertEqual(spec['effective_sand_m3'], {'pile_main': 3.0, 'pile_reserve': 3.5})
        self.assertEqual(set(spec['refsets'].values()),
                         {'M01_CUT_SOIL', 'M01_EXCAVATION', 'M01_PILE_MAIN', 'M01_PILE_RESERVE'})
        self.assertFalse(spec['construction_release'])

    def test_blocked_diagnostic_has_only_red_excavation_and_no_effective_quantities(self):
        field = fixture()
        field.update(native_candidate=False, diagnostic_only=True, volume_m3=None, measurements={},
                     blockers=['BUILDING_CONFLICT'], conflicts=['MAIN_HOUSE_OVERLAP'])
        for role in ('pile_main', 'pile_reserve'):
            field['geometry'].pop(role)
        spec = self.module.field_spec(field)
        self.assertEqual(spec['file'], 'PS11-F01_CONFLICT.prt')
        self.assertEqual(spec['import_roles'], ['excavation'])
        self.assertEqual(spec['effective_sand_m3'], {})
        self.assertIsNone(spec['effective_excavation_m3'])
        self.assertEqual(spec['measurements'], {})
        self.assertEqual(spec['refsets'], {'conflict': 'ANBAU_CONFLICT'})

    def test_source_depth_release_blockers_bad_quantity_or_mesh_mismatch_fail(self):
        changes = [lambda f: f.update(formation_z_mm=-2605), lambda f: f.update(construction_release=True),
                   lambda f: f.update(id='../PS11-F01'), lambda f: f.update(sector_id='PS12'),
                   lambda f: f['blockers'].append('UNKNOWN_SCOPE'),
                   lambda f: f.update(volume_m3=9),
                   lambda f: f['geometry']['cut_soil'].update(component_volumes_m3=[3.2, 4.0]),
                   lambda f: f['geometry']['excavation']['mesh']['vertices'][0].__setitem__(2, float('nan'))]
        for change in changes:
            field = fixture()
            change(field)
            with self.subTest(field=field['id']), self.assertRaises(ValueError):
                self.module.field_spec(field)

    def test_volume_partition_assigns_multi_body_roles_independently_of_import_order(self):
        expected = {'cut_soil': [2.2, 5.0], 'excavation': [2.8], 'pile_main': [3.0], 'pile_reserve': [3.5]}
        self.assertEqual(self.module.assign_import_roles([3.5, 2.2, 3.0, 2.8, 5.0], expected),
                         {'cut_soil': [1, 4], 'excavation': [3], 'pile_main': [2], 'pile_reserve': [0]})
        with self.assertRaises(ValueError):
            self.module.assign_import_roles([2.8, 2.8], {'excavation': [2.8], 'pile_main': [2.8]})

    def test_combined_transfer_keeps_independent_shells_and_never_overwrites_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'new'
            result = self.module.prepare_inputs({'fields': [fixture()]}, target)
            entry = result['fields']['PS11-F01']
            self.assertEqual(entry['transfer_mode'], 'COMBINED_ROLE_STEP')
            self.assertEqual(len(entry['imports']), 1)
            self.assertEqual(entry['imports'][0]['roles'], ['cut_soil', 'excavation', 'pile_main', 'pile_reserve'])
            self.assertTrue(Path(entry['imports'][0]['path']).is_file())
            with self.assertRaises(ValueError):
                self.module.prepare_inputs({'fields': [fixture()]}, target)

    def test_equal_role_volumes_use_separate_imports_without_arbitrary_roles(self):
        field = fixture()
        field['geometry']['pile_main'] = copy.deepcopy(field['geometry']['excavation'])
        field['measurements']['pile_main'] = copy.deepcopy(field['measurements']['excavation'])
        with tempfile.TemporaryDirectory() as directory:
            result = self.module.prepare_inputs({'fields': [field]}, Path(directory) / 'new')
            entry = result['fields']['PS11-F01']
            self.assertEqual(entry['transfer_mode'], 'SEPARATE_ROLE_STEPS')
            self.assertEqual(len(entry['imports']), 4)

    def test_native_result_gate_rejects_wrong_pose_layer_or_effective_mass(self):
        spec = self.module.field_spec(fixture())
        actual = {'id': 'PS11-F01', 'file': 'PS11-F01_STUDY.prt', 'mode': 'STUDY',
                  'construction_release': False, 'field_sha256': spec['field_sha256'],
                  'all_parts_mm': True, 'no_external_dependencies': True,
                  'measurements': {
                      'cut_soil': {'body_count': 2, 'volume_m3': 7.2, 'component_volumes_m3': [2.2, 5.0]},
                      'excavation': {'body_count': 1, 'volume_m3': 2.8, 'component_volumes_m3': [2.8]},
                      'pile_main': {'body_count': 1, 'volume_m3': 3.0, 'component_volumes_m3': [3.0]},
                      'pile_reserve': {'body_count': 1, 'volume_m3': 3.5, 'component_volumes_m3': [3.5]}},
                  'native_bbox_mm': {'cut_soil': [-500, 0, -6000, 500, 1000, 4000],
                                     'excavation': [0, 0, -1600, 500, 1000, 4000],
                                     'pile_main': [10000, 0, 0, 11000, 1000, 3000],
                                     'pile_reserve': [10000, 0, 0, 11000, 1000, 3500]},
                  'effective_excavation_m3': 2.8, 'effective_sand_m3': {'pile_main': 3.0, 'pile_reserve': 3.5},
                  'bodies': {}, 'refsets': {}, 'diagnostic_measurement': None}
        for role, count, layer, color in [('cut_soil', 2, 101, 110), ('excavation', 1, 102, 186),
                                           ('pile_main', 1, 103, 75), ('pile_reserve', 1, 104, 36)]:
            names = ['K02_' + role + '_%02d' % i for i in range(count)]
            actual['bodies'][role] = [{'name': name.upper(), 'layer': layer, 'color': color, 'blank': False}
                                      for name in names]
            actual['refsets']['M01_' + role.upper()] = [name.upper() for name in names]
        self.module.validate_native_result(spec, actual)
        changes = [lambda a: a['native_bbox_mm']['pile_main'].__setitem__(0, 9000),
                   lambda a: a['bodies']['cut_soil'][0].update(layer=251),
                   lambda a: a.update(effective_excavation_m3=None),
                   lambda a: a['refsets']['M01_PILE_MAIN'].append('CONFLICT_BODY'),
                   lambda a: a.update(construction_release=True)]
        for change in changes:
            altered = copy.deepcopy(actual)
            change(altered)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.module.validate_native_result(spec, altered)

    def test_changed_explicit_underside_and_note_keep_the_100_mm_target(self):
        field = fixture()
        field.update(assumed_slab_underside_z_mm=-1400, formation_z_mm=-1500, volume_m3=2.75,
                     diagnostic_volume_m3=2.75)
        field['geometry']['excavation'].update(mesh=box(0, 500, -1500, 4000), volume_m3=2.75,
                                               component_volumes_m3=[2.75], bbox_mm=[0, 0, -1500, 500, 1000, 4000])
        field['geometry']['cut_soil'].update(mesh=join(box(-500, 0, -6000, 4000), box(0, 500, -6000, -1500)),
                                            volume_m3=7.25, component_volumes_m3=[2.25, 5.0])
        for role in ('cut_soil', 'excavation'):
            field['measurements'][role] = {k: field['geometry'][role][k] for k in
                                           ('body_count', 'volume_m3', 'component_volumes_m3')}
        spec = self.module.field_spec(field)
        self.assertEqual(self.module.field_note_lines(spec)[1], 'UK -1.40 m / Pruefsohle -1.50 m rel. EG')
        self.assertEqual(spec['effective_excavation_m3'], 2.75)

    def test_current_depth_note_and_native_spec_remain_unchanged(self):
        spec = self.module.field_spec(fixture())
        self.assertEqual(self.module.field_note_lines(spec)[1], 'UK -1.50 m / Pruefsohle -1.60 m rel. EG')
        encoded = json.dumps(spec, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         'f8e8dca7d81021594d2e0ebe5131245e9cf2b4f9d2c88aa08ea2f4ce431f8e55')


if __name__ == '__main__':
    unittest.main()
