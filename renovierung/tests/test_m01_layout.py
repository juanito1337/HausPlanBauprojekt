"""Offline layout tests; these do not claim an NX execution."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from renovierung.m01.layout import create_layout, validate_layout, _check_parts
from renovierung.m01 import layout as implementation

ROOT = Path(__file__).resolve().parents[2]


class LayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = create_layout(ROOT)

    def test_real_register_complete_and_source_data_preserved(self):
        layout = self.layout
        self.assertIsNone(validate_layout(layout))
        self.assertEqual(len(layout['fields']), 72)
        self.assertEqual(sum(f['native'] for f in layout['fields']), 22)
        self.assertEqual(len(layout['rooms']), 50)
        self.assertEqual(len([n for n in layout['nodes'] if n['id'].startswith('SECTION_')]), 13)
        self.assertEqual(len(layout['sources']), 47)
        current = json.loads((ROOT/'cad/nx/k02/CURRENT.json').read_text())
        build = json.loads((ROOT/'cad/nx/k02'/current['directory']/'BUILD.json').read_text())
        for actual, original in zip(layout['fields'], build['plan']['fields']):
            for key, value in original.items():
                self.assertEqual(actual[key], value, (original['id'], key))
        house = json.loads((ROOT/'projects/g02/haus/data/haus.json').read_text())
        for actual, original in zip(layout['rooms'], house['rooms']):
            for key, value in original.items():
                self.assertEqual(actual[key], value)
            if 'point' not in original:
                self.assertNotIn('point', actual)
        self.assertFalse(layout['construction_release'])

    def test_unique_leaf_geometry_and_single_height_translation(self):
        layout = self.layout
        sources = layout['sources']
        self.assertEqual(len({r['source'] for r in sources}), len(sources))
        self.assertFalse(any('MASTER' in Path(r['source']).name for r in sources))
        nodes = layout['nodes']
        shifted = [n for n in nodes if n['translation_mm'] != [0, 0, 0]]
        self.assertEqual([n['id'] for n in shifted], ['ENVIRONMENT'])
        self.assertEqual(shifted[0]['translation_mm'], [0, 0, -31362.49870845903])
        self.assertEqual(len([n for n in nodes if n['id'] == 'TERRAIN']), 1)
        for field in layout['fields']:
            node = next(n for n in nodes if n['id'] == field['node_id'])
            self.assertTrue(node['blank'])
            roles = [n for n in nodes if n['parent'] == node['id']]
            self.assertEqual(len(roles), 4 if field['native'] else 0)
            if roles:
                self.assertEqual(len({n['file'] for n in roles}), 1)
                self.assertEqual({n['reference_set'] for n in roles}, {
                    'M01_CUT_SOIL', 'M01_EXCAVATION', 'M01_PILE_MAIN', 'M01_PILE_RESERVE'})

    def test_conservative_room_assignment_and_coordinates(self):
        for room in self.layout['rooms']:
            rid = room['id']
            expected = ('HISTORISCH_WOHNUNG_A' if rid in {
                'EG_A_W', 'EG_A_K', 'EG_A_WC', 'KG_A_R', 'KG_A_F', 'KG_A_B', 'KG_A_TREPPENRAUM'}
                else 'HISTORISCH_WOHNUNG_B' if rid in {'EG_B_W', 'EG_B_K', 'EG_B_B', 'EG_B_A'}
                else 'ZUORDNUNG_OFFEN')
            self.assertEqual(room['apartment_reference'], expected)
            self.assertFalse(room['current_apartment_assignment_confirmed'])
            node = next(n for n in self.layout['nodes'] if n['id'] == room['node_id'])
            self.assertEqual(node['translation_mm'], [0, 0, 0])
            self.assertEqual(node['metadata'], room)

    def test_rejects_invalid_layouts(self):
        def duplicate_id(d): d['nodes'][1]['id'] = d['nodes'][0]['id']
        def missing_parent(d): d['nodes'][1]['parent'] = 'MISSING'
        def unsafe_file(d): d['nodes'][1]['file'] = '../bad.prt'
        def duplicate_source(d): d['sources'].append(copy.deepcopy(d['sources'][0]))
        def missing_source(d): d['sources'].pop()
        def missing_field(d): d['fields'].pop()
        def missing_room(d): d['rooms'].pop()
        def wrong_transform(d): d['nodes'][1]['rotation'][0] = float('nan')
        def doubled_height(d): next(n for n in d['nodes'] if n['id'] == 'TERRAIN')['translation_mm'][2] = -31362.49870845903
        def release(d): d['construction_release'] = True
        def visible_field(d): next(n for n in d['nodes'] if n['kind'] == 'field')['blank'] = False
        def shared_assembly(d): d['nodes'][1]['file'] = d['nodes'][0]['file']
        def house_under_environment(d): next(n for n in d['nodes'] if n['id'] == 'HOUSE')['parent'] = 'ENVIRONMENT'
        def leaf_under_wrong_floor(d): next(n for n in d['nodes'] if n['id'] == 'HOUSE_KG_MAIN')['parent'] = 'HOUSE_EG'
        def bad_measurement(d): d['fields'][0]['measurements']['cut_soil']['body_count'] = 0
        def unregistered_role(d):
            n = copy.deepcopy(next(n for n in d['nodes'] if n['kind'] == 'role'))
            n.update(id='UNREGISTERED_ROLE', parent='MASTER', file='studien/unregistered.prt')
            d['nodes'].append(n)
            d['sources'].append(dict(d['sources'][-1], file=n['file'], source='cad/nx/unregistered.prt'))
        for mutate in (duplicate_id, missing_parent, unsafe_file, duplicate_source, missing_source,
                       missing_field, missing_room, wrong_transform, doubled_height, release,
                       visible_field, shared_assembly, house_under_environment, leaf_under_wrong_floor,
                       bad_measurement, unregistered_role):
            with self.subTest(mutate=mutate.__name__):
                value = copy.deepcopy(self.layout)
                mutate(value)
                with self.assertRaises(ValueError): validate_layout(value)

    def test_rejects_stale_and_cross_mismatched_source_evidence(self):
        original_read = implementation._read
        for mode in ('stale_fingerprint', 'cross_baseline', 'duplicate_manifest'):
            def fixture_read(path):
                value = original_read(path)
                if Path(path).name == 'BUILD.json':
                    if mode == 'stale_fingerprint': value['source_fingerprint'] = '0'*64
                    if mode == 'cross_baseline' and value.get('schema') == 'K02_NATIVE_BUILD_V1':
                        value['source_hashes'][next(iter(value['source_hashes']))] = '0'*64
                    if mode == 'duplicate_manifest' and 'parts' in value:
                        value['parts'].append(copy.deepcopy(value['parts'][0]))
                return value
            with self.subTest(mode=mode), patch.object(implementation, '_read', fixture_read):
                with self.assertRaises(ValueError): create_layout(ROOT)

    def test_native_source_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            part = root/'leaf.prt'
            part.write_bytes(b'fixture - not an NX part')
            row = {'path': 'leaf.prt', 'sha256': hashlib.sha256(part.read_bytes()).hexdigest(), 'bytes': part.stat().st_size}
            _check_parts(root, [row])
            with self.assertRaises(ValueError): _check_parts(root, [row, row])
            with self.assertRaises(ValueError): _check_parts(root, [dict(row, path='../leaf.prt')])
            part.write_bytes(b'changed')
            with self.assertRaises(ValueError): _check_parts(root, [row])
            part.unlink()
            with self.assertRaises(ValueError): _check_parts(root, [row])


if __name__ == '__main__': unittest.main()
