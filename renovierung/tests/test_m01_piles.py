"""Source-backed alternative-pile layout tests without NX execution."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from renovierung.m01 import layout as layout_module
from renovierung.m01 import piles as piles_module

ROOT = Path(__file__).resolve().parents[2]


class PileLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, _, build = layout_module._load_evidence(ROOT)
        plan = build['plan']
        states = {s['id']: s for s in build['states']}
        fields = []
        for original in plan['fields']:
            field = copy.deepcopy(original)
            field['native'] = bool(field['native_candidate'])
            field['measurements'] = copy.deepcopy(states[field['id']]['measurements']) if field['native'] else {}
            fields.append(field)
        cls.original = {'fields':fields, 'height_registration':copy.deepcopy(plan['height_registration']),
                        'provenance':{'plan_provenance':copy.deepcopy(plan['provenance'])}}
        cls.proposal = piles_module.create_piles(ROOT, cls.original, [14500,-9500])
        if len(cls.proposal['fields']) != 22:
            raise AssertionError('All 22 native source studies must be recomputed')

    def test_alternative_records_original_source_and_updates_only_pile_measurements(self):
        layout = copy.deepcopy(self.original)
        layout_module._apply_pile_site(ROOT, layout, [14500, -9500], proposal=self.proposal)
        self.assertEqual(layout['pile_site']['center_mm'], [14500, -9500])
        self.assertEqual(layout['pile_site']['previous_centers_mm'], [[13000, -16000]])
        self.assertFalse(layout['pile_site']['construction_release'])
        self.assertEqual(layout['pile_site']['status'], 'EXPLICIT_ALTERNATIVE_SITE_UNRELEASED')
        byid = {f['id']: f for f in self.proposal['fields']}
        for old, field in zip(self.original['fields'], layout['fields']):
            if not field['native']:
                self.assertEqual(field, old)
                continue
            self.assertNotIn('stockpile', field)
            self.assertEqual(field['k02_stockpile'], old['stockpile'])
            self.assertEqual(field['stockpile_reference'], 'HISTORICAL_K02_NOT_CURRENT_DISPLAY_SITE')
            self.assertEqual(field['measurements']['excavation'], old['measurements']['excavation'])
            self.assertEqual(field['measurements']['cut_soil'], old['measurements']['cut_soil'])
            self.assertTrue(field['display_pile_native_verification_required'])
            self.assertIn('ALTERNATIVER_LAGERPLATZ', field['display_pile_note'])
            for role, source_role in (('pile_main', 'main'), ('pile_reserve', 'reserve_1_25')):
                pile = byid[field['id']][source_role]
                self.assertEqual(field['k02_pile_measurements'][role], old['measurements'][role])
                self.assertEqual(field['measurements'][role]['component_volumes_m3'], pile['component_volumes_m3'])
                self.assertEqual(field['display_stockpile'][role]['bbox_mm'], pile['bbox_mm'])
                self.assertEqual(field['display_stockpile'][role]['target_volume_m3'], pile['target_volume_m3'])
        serialized = json.dumps(layout)
        self.assertNotIn('contact_polygons_xy_mm', serialized)
        self.assertNotIn('"mesh":', serialized)

    def test_reapplication_preserves_original_measurements_and_rejects_partial_or_changed_proposal(self):
        layout = copy.deepcopy(self.original)
        layout_module._apply_pile_site(ROOT, layout, [14500, -9500], proposal=self.proposal)
        first = copy.deepcopy(layout)
        layout_module._apply_pile_site(ROOT, layout, [14500, -9500], proposal=self.proposal)
        self.assertEqual(layout, first)
        for mutation in ('partial', 'center', 'excavation', 'quantity', 'hash'):
            proposal = copy.deepcopy(self.proposal)
            if mutation == 'partial': proposal['fields'].pop()
            if mutation == 'center': proposal['center_xy_mm'] = [0, 0]
            if mutation == 'excavation': proposal['fields'][0]['excavation_volume_m3'] += 1
            if mutation == 'quantity': proposal['fields'][0]['main']['target_volume_m3'] += 1
            if mutation == 'hash': proposal['source_hashes'][next(iter(proposal['source_hashes']))] = '0'*64
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                layout_module._apply_pile_site(ROOT, copy.deepcopy(first), [14500, -9500], proposal=proposal)

    def test_create_layout_supplies_compact_alternative_site_and_native_gate(self):
        with patch.object(piles_module, 'create_piles', return_value=self.proposal):
            layout = layout_module.create_layout(ROOT, pile_center_xy=[14500, -9500])
        layout_module.validate_layout(layout)
        self.assertEqual(layout['pile_site']['center_mm'], [14500, -9500])
        bad = copy.deepcopy(layout)
        next(f for f in bad['fields'] if f['native'])['display_stockpile']['pile_main']['bbox_mm'] = [0]*6
        with self.assertRaises(ValueError): layout_module.validate_layout(bad)

    def test_site_a_requires_geometry_gates_and_all_vegetation_source_hashes(self):
        evidence = json.loads((ROOT/layout_module.PILE_SITE_CHECK).read_text())
        for mutation in ('scope','release','clearance','missing_clearance','overlap','outside','vegetation_hash'):
            bad = copy.deepcopy(evidence)
            candidate = next(c for c in bad['candidates'] if c['id'] == 'A')
            if mutation == 'scope': bad['scope'] = 'UNVERIFIED'
            if mutation == 'release': bad['construction_release'] = True
            if mutation == 'clearance': candidate['clearance_lower_bounds_m']['excavation'] = 0.599
            if mutation == 'missing_clearance': candidate['clearance_lower_bounds_m'].pop('vegetation')
            if mutation == 'overlap': candidate['overlap_area_sum_m2']['building'] = 1e-8
            if mutation == 'outside': candidate['parcel_outside_m2'] = 1e-8
            if mutation == 'vegetation_hash': bad['verified_source_generator_hashes'].pop(bad['vegetation_sources']['V01']['step'])
            with self.subTest(mutation=mutation), patch.object(layout_module, '_read', return_value=bad):
                with self.assertRaises(ValueError): layout_module._pile_site_evidence(ROOT, [14500,-9500], 22)


if __name__ == '__main__': unittest.main()
