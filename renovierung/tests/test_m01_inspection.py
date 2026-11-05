"""Pure review-index and visibility contract tests; no simulated NX evidence."""
import copy
import importlib
import unittest


def fixture():
    return {'sections': [{'id': 'PS03'}, {'id': 'PS01'}, {'id': 'PS02'}],
            'fields': [{'id': 'PS01-F09', 'sector_id': 'PS01', 'native': True},
                       {'id': 'PS01-F02', 'sector_id': 'PS01', 'native': True},
                       {'id': 'PS02-F01', 'sector_id': 'PS02', 'native': False}]}


class ReviewIndexTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.m01.inspection')
        except ModuleNotFoundError:
            self.fail('The M01 separate review-wrapper module is missing')

    def test_sorted_index_selects_first_real_native_field_or_section_overview(self):
        layout = fixture()
        before = copy.deepcopy(layout)
        self.assertEqual(self.module.build_review_index(layout), [
            {'id': 'PS01', 'file': 'Bauabschnitte/PS01.prt', 'state': 'PS01-F02'},
            {'id': 'PS01-F02', 'file': 'Bauabschnitte/PS01/PS01-F02.prt', 'state': 'PS01-F02'},
            {'id': 'PS01-F09', 'file': 'Bauabschnitte/PS01/PS01-F09.prt', 'state': 'PS01-F09'},
            {'id': 'PS02', 'file': 'Bauabschnitte/PS02.prt', 'state': 'PS02'},
            {'id': 'PS03', 'file': 'Bauabschnitte/PS03.prt', 'state': 'PS03'}])
        self.assertEqual(layout, before)

    def test_no_native_fields_creates_only_section_overviews(self):
        layout = fixture()
        layout['fields'] = []
        self.assertEqual(self.module.build_review_index(layout), [
            {'id': 'PS01', 'file': 'Bauabschnitte/PS01.prt', 'state': 'PS01'},
            {'id': 'PS02', 'file': 'Bauabschnitte/PS02.prt', 'state': 'PS02'},
            {'id': 'PS03', 'file': 'Bauabschnitte/PS03.prt', 'state': 'PS03'}])

    def test_rejects_unknown_section_duplicate_or_unsafe_ids_and_non_boolean_native(self):
        mutations = [lambda d: d['fields'][0].update(sector_id='PS99'),
                     lambda d: d['sections'].append({'id': 'PS01'}),
                     lambda d: d['fields'].append(copy.deepcopy(d['fields'][0])),
                     lambda d: d['sections'][0].update(id='../PS03'),
                     lambda d: d['fields'][0].update(id='PS02-F09'),
                     lambda d: d['fields'][0].update(native=1)]
        for mutation in mutations:
            layout = fixture()
            mutation(layout)
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                self.module.build_review_index(layout)

    def test_review_catalog_cannot_redirect_a_wrapper_to_another_state(self):
        layout = fixture()
        layout['review_masters'] = [
            {'id': 'PS01', 'file': 'Bauabschnitte/PS01.prt', 'state': 'PS01-F02'},
            {'id': 'PS01-F02', 'file': 'Bauabschnitte/PS01/PS01-F02.prt', 'state': 'PS01-F02'},
            {'id': 'PS01-F09', 'file': 'Bauabschnitte/PS01/PS01-F09.prt', 'state': 'PS01-F09'},
            {'id': 'PS02', 'file': 'Bauabschnitte/PS02.prt', 'state': 'PS02'},
            {'id': 'PS03', 'file': 'Bauabschnitte/PS03.prt', 'state': 'PS03'}]
        layout['review_masters'][0]['state'] = 'PS01-F09'
        with self.assertRaises(ValueError):
            self.module._index(layout)

    def test_native_presentation_requires_all_display_layers(self):
        spec = {'origin_mm': [0, 0, 0], 'matrix': [1, 0, 0, 0, 1, 0, 0, 0, 1], 'scale': 0.005}
        record = {'camera': {'absolute_origin_mm': [0, 0, 0], 'matrix': spec['matrix'], 'scale': 0.005},
                  'shaded_with_edges': True, 'layers': {}}
        with self.assertRaises(ValueError):
            self.module._check_presentation(record, spec)


class StandaloneIntentTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.m01.standalone')
        except ModuleNotFoundError:
            self.fail('The M01 isolated subassembly inspector is missing')
        self.layout = fixture()
        self.layout['nodes'] = [
            {'id': 'SECTION_PS01', 'kind': 'assembly', 'file': 'gruppen/SECTION_PS01.prt'},
            {'id': 'SECTION_PS02', 'kind': 'assembly', 'file': 'gruppen/SECTION_PS02.prt'},
            {'id': 'SECTION_PS03', 'kind': 'assembly', 'file': 'gruppen/SECTION_PS03.prt'}]
        for field in self.layout['fields']:
            field['node_id'] = 'FIELD_' + field['id']
            self.layout['nodes'].append({'id': field['node_id'], 'kind': 'field',
                                         'file': 'gruppen/' + field['node_id'] + '.prt'})

    def test_section_selects_first_native_and_retains_blocked_register_markers(self):
        self.layout['fields'].append({'id': 'PS01-F03', 'sector_id': 'PS01',
                                      'node_id': 'FIELD_PS01-F03', 'native': False})
        self.assertEqual(self.module._spec(self.layout, 'SECTION_PS01'), {
            'state': 'SECTION_DEFAULT', 'selected_field': 'PS01-F02',
            'visible_marker_ids': ['PS01-F02', 'PS01-F03']})

    def test_blocked_field_has_a_marker_and_no_selected_study(self):
        self.assertEqual(self.module._spec(self.layout, 'FIELD_PS02-F01'), {
            'state': 'ISOLATED_FIELD', 'selected_field': None,
            'visible_marker_ids': ['PS02-F01']})

    def test_native_isolated_field_selects_its_own_study(self):
        self.assertEqual(self.module._spec(self.layout, 'FIELD_PS01-F09'), {
            'state': 'ISOLATED_FIELD', 'selected_field': 'PS01-F09',
            'visible_marker_ids': ['PS01-F09']})


if __name__ == '__main__':
    unittest.main()
