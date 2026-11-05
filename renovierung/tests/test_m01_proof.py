"""Synthetic evidence validation only; these fixtures are no native NX proof."""
import copy
import importlib
import unittest


def fixture():
    roles = ('cut_soil', 'excavation', 'pile_main', 'pile_reserve')
    nodes = [{'id': 'MASTER', 'kind': 'assembly', 'file': 'MASTER.prt'},
             {'id': 'TERRAIN', 'kind': 'source', 'parent': 'MASTER'},
             {'id': 'SECTION_PS01', 'kind': 'assembly', 'parent': 'MASTER', 'file': 'sections/PS01.prt'},
             {'id': 'SECTION_PS02', 'kind': 'assembly', 'parent': 'MASTER', 'file': 'sections/PS02.prt'},
             {'id': 'FIELD_PS01-F01', 'kind': 'field', 'parent': 'SECTION_PS01', 'file': 'fields/PS01-F01.prt'},
             {'id': 'FIELD_PS02-F01', 'kind': 'field', 'parent': 'SECTION_PS02', 'file': 'fields/PS02-F01.prt'}]
    nodes += [{'id': 'ROLE_PS01-F01_' + role.upper(), 'kind': 'role',
               'parent': 'FIELD_PS01-F01', 'role': role,
               'blank': role in ('excavation', 'pile_reserve')} for role in roles]
    groups = [{'id': 'CONTEXT_000', 'exclude_for': [], 'body_count': 2,
               'component_volumes_m3': [1., 2.], 'volume_m3': 3.},
              {'id': 'CONTEXT_001', 'exclude_for': ['PS01-F01'], 'body_count': 1,
               'component_volumes_m3': [4.], 'volume_m3': 4.}]
    nodes += [{'id': g['id'], 'kind': 'context', 'parent': 'SITE_CONTEXT'} for g in groups]
    measurements = {r: {'body_count': 2 if r == 'cut_soil' else 1} for r in roles}
    layout = {'master': 'MASTER.prt', 'default_state': 'PS01-F01', 'nodes': nodes,
              'fields': [{'id': 'PS01-F01', 'node_id': 'FIELD_PS01-F01', 'sector_id': 'PS01',
                          'native': True, 'measurements': measurements},
                         {'id': 'PS02-F01', 'node_id': 'FIELD_PS02-F01', 'sector_id': 'PS02', 'native': False}],
              'sections': [{'id': 'PS01'}, {'id': 'PS02'}], 'context': {'groups': groups},
              'presentation': {'scale': .002, 'matrix': [1., 0., 0., 0., 1., 0., 0., 0., 1.],
                               'origin_mm': [1000., 2000., 3000.]}}
    presentation = {'camera': {'scale': .002, 'matrix': layout['presentation']['matrix'][:],
                               'absolute_origin_mm': [1000., 2000., 3000.],
                               'origin_view_mm': [-1000., -2000., -3000.]},
                    'layers': {str(n): {'visible': True, 'selectable': True, 'hidden': False}
                               for n in (101, 102, 103, 104, 200, 201, 210)},
                    'shaded_with_edges': True}
    zero = dict.fromkeys(roles, 0)
    states = {
        'BASE': {'suppressed_ids': ['FIELD_PS01-F01', 'FIELD_PS02-F01', 'CONTEXT_000', 'CONTEXT_001',
                                   'ROLE_PS01-F01_EXCAVATION','ROLE_PS01-F01_PILE_RESERVE'],
                 'visible_role_bodies': zero.copy(), 'visible_context_ids': [], 'visible_field_marker_ids': []},
        'PS01': {'suppressed_ids': ['FIELD_PS02-F01', 'TERRAIN'] + ['ROLE_PS01-F01_' + r.upper() for r in roles],
                 'visible_role_bodies': zero.copy(), 'visible_context_ids': ['CONTEXT_000', 'CONTEXT_001'],
                 'visible_field_marker_ids': ['PS01-F01']},
        'PS02': {'suppressed_ids': ['FIELD_PS01-F01', 'TERRAIN'] + ['ROLE_PS01-F01_' + r.upper() for r in roles],
                 'visible_role_bodies': zero.copy(), 'visible_context_ids': ['CONTEXT_000', 'CONTEXT_001'],
                 'visible_field_marker_ids': ['PS02-F01']},
        'PS01-F01': {'suppressed_ids': ['FIELD_PS02-F01', 'CONTEXT_001', 'TERRAIN',
                                        'ROLE_PS01-F01_EXCAVATION','ROLE_PS01-F01_PILE_RESERVE'],
                     'visible_role_bodies': dict(zero, cut_soil=2, pile_main=1),
                     'visible_context_ids': ['CONTEXT_000'], 'visible_field_marker_ids': ['PS01-F01']}}
    catalog = {'BASE': 'M01_BASE', 'PS01': 'M01_PS01', 'PS02': 'M01_PS02', 'PS01-F01': 'M01_PS01_F01'}
    actual = {'context_measurements': {g['id']: {k: copy.deepcopy(g[k]) for k in
               ('body_count', 'component_volumes_m3', 'volume_m3')} for g in groups},
              'arrangements': {'catalog': catalog, 'default': 'PS01-F01', 'active': 'PS01-F01',
                               'states': states, 'presentation': copy.deepcopy(presentation)}}
    actual['standalone'] = {}
    for file, state, markers, counts in (
            ('fields/PS01-F01.prt', 'ISOLATED_FIELD', ['PS01-F01'], dict(zero, cut_soil=2, pile_main=1)),
            ('fields/PS02-F01.prt', 'ISOLATED_FIELD', ['PS02-F01'], zero),
            ('sections/PS01.prt', 'SECTION_DEFAULT', ['PS01-F01'], dict(zero, cut_soil=2, pile_main=1)),
            ('sections/PS02.prt', 'SECTION_DEFAULT', ['PS02-F01'], zero)):
        actual['standalone'][file] = {'state': state, 'visible_role_bodies': counts.copy(),
                                      'visible_marker_ids': markers[:], 'presentation': copy.deepcopy(presentation)}
    return layout, actual, presentation


class DisplayEvidenceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.validate = importlib.import_module('renovierung.m01.proof').validate_display_evidence
        except ModuleNotFoundError:
            self.fail('The M01 display evidence validator is missing')
        self.layout, self.actual, self.presentation = fixture()

    def test_complete_synthetic_display_evidence_is_accepted(self):
        self.add_reviews()
        self.assertEqual(self.validate(self.layout, self.actual), [])

    def add_reviews(self):
        self.actual['reviews'] = {}
        records = [{'id': 'PS01', 'file': 'Bauabschnitte/PS01.prt', 'state': 'PS01-F01'},
                   {'id': 'PS01-F01', 'file': 'Bauabschnitte/PS01/PS01-F01.prt', 'state': 'PS01-F01'},
                   {'id': 'PS02', 'file': 'Bauabschnitte/PS02.prt', 'state': 'PS02'}]
        for record in records:
            sid = record['state']
            state = self.actual['arrangements']['states'][sid]
            self.actual['reviews'][record['id']] = dict(file=record['file'], state=sid,
                master=self.layout['master'], visible_role_bodies=copy.deepcopy(state['visible_role_bodies']),
                visible_context_ids=state['visible_context_ids'][:], visible_field_marker_ids=state['visible_field_marker_ids'][:],
                presentation=copy.deepcopy(self.presentation))

    def assert_rejected(self, mutate):
        self.add_reviews()
        mutate(self.actual)
        self.assertTrue(self.validate(self.layout, self.actual))

    def test_missing_or_incoherent_context_measurements_are_rejected(self):
        for mutate in (lambda a: a.pop('context_measurements'),
                       lambda a: a['context_measurements'].pop('CONTEXT_001'),
                       lambda a: a['context_measurements']['CONTEXT_000'].update(component_volumes_m3=[1.5, 1.5]),
                       lambda a: a['context_measurements']['CONTEXT_000'].update(volume_m3=4.),
                       lambda a: a['context_measurements']['CONTEXT_000'].update(body_count=True)):
            with self.subTest(mutate=mutate):
                self.actual = fixture()[1]
                self.assert_rejected(mutate)

    def test_wrong_native_layer_semantics_or_shading_are_rejected(self):
        for key, value in (('visible', False), ('selectable', False), ('hidden', True), ('visible', 1)):
            with self.subTest(key=key, value=value):
                self.actual = fixture()[1]
                self.assert_rejected(lambda a: a['arrangements']['presentation']['layers']['101'].update({key: value}))
        self.actual = fixture()[1]
        self.assert_rejected(lambda a: a['arrangements']['presentation'].update(shaded_with_edges=False))

    def test_state_inventory_defaults_and_visibility_are_exact(self):
        for mutate in (lambda a: a['arrangements']['states'].pop('BASE'),
                       lambda a: a['arrangements'].update(active='PS02'),
                       lambda a: a['arrangements']['catalog'].update(PS01='WRONG'),
                       lambda a: a['arrangements']['states']['PS01-F01']['visible_role_bodies'].update(cut_soil=1),
                       lambda a: a['arrangements']['states']['PS01']['visible_role_bodies'].update(pile_main=1),
                       lambda a: a['arrangements']['states']['PS01-F01']['visible_context_ids'].append('CONTEXT_001'),
                       lambda a: a['arrangements']['states']['PS02'].update(visible_field_marker_ids=[])):
            with self.subTest(mutate=mutate):
                self.actual = fixture()[1]
                self.assert_rejected(mutate)

    def test_duplicate_summary_ids_are_rejected(self):
        for key in ('suppressed_ids', 'visible_context_ids', 'visible_field_marker_ids'):
            with self.subTest(key=key):
                self.actual = fixture()[1]
                self.assert_rejected(lambda a: a['arrangements']['states']['PS01-F01'][key].append(
                    a['arrangements']['states']['PS01-F01'][key][0]))

    def test_missing_review_wrong_state_master_or_camera_are_rejected(self):
        for change in ('missing', 'extra', 'state', 'master', 'file', 'camera', 'context',
                       'roles', 'markers', 'duplicate_markers', 'layer'):
            with self.subTest(change=change):
                self.actual = fixture()[1]
                self.add_reviews()
                rid = next(iter(self.actual['reviews']))
                record = self.actual['reviews'][rid]
                if change == 'missing': self.actual['reviews'].pop(rid)
                elif change == 'extra': self.actual['reviews']['PS99'] = copy.deepcopy(record)
                elif change in ('state', 'master', 'file'): record[change] = 'WRONG'
                elif change == 'camera': record['presentation']['camera']['scale'] = .004
                elif change == 'context': record['visible_context_ids'].append('CONTEXT_000')
                elif change == 'roles': record['visible_role_bodies']['cut_soil'] = 99
                elif change == 'duplicate_markers': record['visible_field_marker_ids'] *= 2
                elif change == 'layer': record['presentation']['layers'].pop('210')
                else: record['visible_field_marker_ids'].append('PS99-F99')
                self.assertTrue(self.validate(self.layout, self.actual))

    def test_nonfinite_or_changed_camera_values_are_rejected(self):
        for key, value in (('scale', float('nan')), ('scale', True), ('matrix', [0.]*9),
                           ('absolute_origin_mm', [1000., 2000., 3001.])):
            with self.subTest(key=key):
                self.actual = fixture()[1]
                self.assert_rejected(lambda a: a['arrangements']['presentation']['camera'].update({key: value}))

    def test_malformed_records_return_errors_without_raising(self):
        for key in ('context_measurements', 'arrangements', 'reviews'):
            for value in (None, [], True):
                with self.subTest(key=key, value=value):
                    self.actual = fixture()[1]
                    self.assert_rejected(lambda a: a.update({key: value}))

    def test_standalone_inventory_is_mandatory_and_complete(self):
        for mutate in (lambda a: a.pop('standalone'), lambda a: a.update(standalone={}),
                       lambda a: a['standalone'].pop('fields/PS02-F01.prt'),
                       lambda a: a['standalone'].update({'EXTRA.prt': {}})):
            with self.subTest(mutate=mutate):
                self.actual = fixture()[1]
                self.assert_rejected(mutate)

    def test_standalone_wrong_state_markers_role_count_or_layer_are_rejected(self):
        for file, change in (('fields/PS01-F01.prt', 'state'), ('fields/PS01-F01.prt', 'markers'),
                             ('fields/PS01-F01.prt', 'roles'), ('fields/PS02-F01.prt', 'roles'),
                             ('sections/PS01.prt', 'layer'), ('sections/PS02.prt', 'camera')):
            with self.subTest(file=file, change=change):
                self.actual = fixture()[1]
                self.add_reviews()
                record = self.actual['standalone'][file]
                if change == 'state': record['state'] = 'WRONG'
                elif change == 'markers': record['visible_marker_ids'].append('PS02-F01')
                elif change == 'roles': record['visible_role_bodies']['cut_soil'] = 99
                elif change == 'layer': record['presentation']['layers']['101']['hidden'] = True
                else: record['presentation']['camera']['scale'] = 1.
                self.assertTrue(self.validate(self.layout, self.actual))


if __name__ == '__main__':
    unittest.main()
