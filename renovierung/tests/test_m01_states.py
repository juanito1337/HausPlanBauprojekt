"""Pure arrangement intent tests; no fake NX or native-success claims."""
import copy
import importlib
import unittest


def fixture():
    nodes = [{'id': key, 'kind': 'assembly', 'parent': 'MASTER'}
             for key in ('HOUSE_EG', 'HOUSE_DG', 'HOUSE_ROOF', 'HOUSE_OUTSIDE', 'ENV_V01')]
    nodes.append({'id': 'TERRAIN', 'kind': 'source', 'parent': 'MASTER'})
    fields = []
    for fid, section, native in [('PS01-F01', 'PS01', True), ('PS01-F02', 'PS01', False),
                                  ('PS02-F01', 'PS02', True)]:
        nid = 'FIELD_' + fid
        nodes.append({'id': nid, 'kind': 'field', 'parent': 'SECTION_' + section})
        fields.append({'id': fid, 'node_id': nid, 'sector_id': section, 'native': native})
        if native:
            for role in ('cut_soil', 'excavation', 'pile_main', 'pile_reserve'):
                nodes.append({'id': 'ROLE_' + fid + '_' + role.upper(), 'kind': 'role',
                              'parent': nid, 'role': role,
                              'blank': role in ('excavation', 'pile_reserve')})
    groups = [{'id': 'CONTEXT_000', 'exclude_for': []},
              {'id': 'CONTEXT_001', 'exclude_for': ['PS01-F01']},
              {'id': 'CONTEXT_002', 'exclude_for': ['PS01-F01', 'PS02-F01']}]
    nodes.extend({'id': g['id'], 'kind': 'context', 'parent': 'CONTEXT'} for g in groups)
    return {'nodes': nodes, 'fields': fields,
            'sections': [{'id': 'PS02'}, {'id': 'PS01'}], 'context': {'groups': groups}}


class StateSpecTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.m01.states')
        except ModuleNotFoundError:
            self.fail('The M01 saved arrangement module is missing')
        self.layout = fixture()

    def test_catalog_is_stable_ascii_and_contains_overviews_and_native_fields(self):
        expected = {'BASE': 'M01_BASE', 'PS01': 'M01_PS01', 'PS02': 'M01_PS02',
                    'PS01-F01': 'M01_PS01_F01', 'PS02-F01': 'M01_PS02_F01'}
        self.assertEqual(self.module.state_catalog(self.layout), expected)
        self.layout['fields'].reverse()
        self.layout['sections'].reverse()
        self.assertEqual(list(self.module.state_catalog(self.layout)), list(expected))

    def test_base_hides_fields_and_shared_context_but_restores_existing_building(self):
        spec = self.module.state_spec(self.layout, 'BASE')
        expected = {f['node_id'] for f in self.layout['fields']} | {'CONTEXT_000', 'CONTEXT_001', 'CONTEXT_002'}
        expected.update(n['id'] for n in self.layout['nodes'] if n['kind']=='role' and n['blank'])
        self.assertEqual(spec, {'id': 'BASE', 'name': 'M01_BASE', 'suppressed_ids': sorted(expected)})

    def test_section_shows_only_selected_registers_and_whole_property_without_excavations(self):
        spec = self.module.state_spec(self.layout, 'PS01')
        hidden = set(spec['suppressed_ids'])
        self.assertIn('FIELD_PS02-F01', hidden)
        self.assertNotIn('FIELD_PS01-F01', hidden)
        self.assertNotIn('FIELD_PS01-F02', hidden)
        self.assertTrue(all(n['id'] in hidden for n in self.layout['nodes'] if n['kind'] == 'role'))
        self.assertFalse(any(g['id'] in hidden for g in self.layout['context']['groups']))
        self.assertTrue({'TERRAIN', 'HOUSE_EG', 'HOUSE_DG', 'HOUSE_ROOF', 'HOUSE_OUTSIDE'} <= hidden)
        self.assertNotIn('ENV_V01', hidden)

    def test_field_suppresses_other_fields_and_only_overlapping_context(self):
        before = copy.deepcopy(self.layout)
        spec = self.module.state_spec(self.layout, 'PS01-F01')
        hidden = set(spec['suppressed_ids'])
        self.assertTrue({'FIELD_PS01-F02', 'FIELD_PS02-F01', 'CONTEXT_001', 'CONTEXT_002'} <= hidden)
        self.assertNotIn('FIELD_PS01-F01', hidden)
        self.assertNotIn('CONTEXT_000', hidden)
        self.assertNotIn('ENV_V01', hidden)
        # A wrapper opening must not reveal the excavation or alternative heap.
        for node in self.layout['nodes']:
            if node['kind']=='role':
                self.assertEqual(node['id'] in hidden,node['blank'])
        self.assertEqual(self.layout, before)
        self.assertEqual(spec['suppressed_ids'], sorted(set(spec['suppressed_ids'])))

    def test_unknown_blocked_and_malformed_states_fail_without_nx(self):
        for state in ('UNKNOWN', 'PS01-F02', None, [], 'PS01;bad'):
            with self.subTest(state=state):
                with self.assertRaises(ValueError):
                    self.module.state_spec(self.layout, state)
        for mutate in (lambda d: d['context']['groups'][0]['exclude_for'].append('UNKNOWN'),
                       lambda d: d['nodes'].append(copy.deepcopy(d['nodes'][0])),
                       lambda d: d['fields'][0].update(node_id='MISSING')):
            layout = copy.deepcopy(self.layout)
            mutate(layout)
            with self.assertRaises(ValueError):
                self.module.state_spec(layout, 'BASE')


if __name__ == '__main__':
    unittest.main()
