"""Regressionsprüfungen: Original-Regelhinweise niemals als Isttiefen verwenden."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_r09 import (BASE, JOB, CONFIG, SceneDouble, NXSimulationTests,
                      SceneAdapter, ns, Object, Body)
from r09.core import read_json, validate_job, write_json
from r09.utilities import load_review, validate_review, decorate_house_data
from r09.run import preflight_open_parts, run_project
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_metadata import object_attributes

RAW = read_json(BASE/'basis/Haus_R06/data/haus.json')
REVIEW = read_json(BASE/'data/LEITUNGSTIEFEN_PRUEFUNG_R09a.json')


def geometry_signature(data):
    job = compile_house(data, True)
    simple = []
    for p in job['parts']:
        solids = [{k:v for k,v in s.items() if k!='meta'} for s in p['solids']]
        refs = [{'id':r['id'],'points':r.get('points3d',r.get('polygon')), 'closed':r.get('closed')}
                for r in p['references']]
        simple.append({'id':p['id'],'file':p['file'],'solids':solids,'refs':refs})
    return hashlib.sha256(json.dumps(simple,sort_keys=True,allow_nan=False).encode()).hexdigest()


class DepthSourceTests(unittest.TestCase):
    def test_all_nine_original_files_hashed(self):
        review,s=load_review(BASE)
        self.assertEqual(s['documents_reviewed'],9)
        self.assertEqual(s['pages_reviewed'],15)
    def test_every_route_checked_once(self):
        self.assertEqual(validate_review(REVIEW,RAW)['routes_reviewed'],25)
    def test_no_actual_depths_claimed(self):
        self.assertEqual(validate_review(REVIEW,RAW)['confirmed_route_depths'],0)
    def test_explicit_water_range_not_route_depth(self):
        r=next(x for x in REVIEW['rules'] if x['id']=='SWN_WASSER')
        self.assertEqual((r['cover_min_m'],r['cover_max_m']),(1.2,1.6))
        self.assertFalse(r['applied_to_routes'])
    def test_telecom_open_range_exact_source(self):
        r=next(x for x in REVIEW['rules'] if x['id']=='SWN_TK_OFFEN')
        self.assertEqual((r['cover_min_m'],r['cover_max_m']),(0.3,1.5))
        self.assertEqual(r['source']['page'],3)
    def test_bore_upper_information_no_invented_lower_bound(self):
        r=next(x for x in REVIEW['rules'] if x['id']=='SWN_TK_BOHRUNG')
        self.assertIsNone(r['cover_min_m']);self.assertEqual(r['cover_max_m'],5.0)
        self.assertFalse(r['is_safe_depth_envelope'])
    def test_no_numeric_gas_power_rules_in_upload(self):
        r=next(x for x in REVIEW['rules'] if x['id']=='STROM_GAS_VERWEIS')
        self.assertIsNone(r['cover_min_m']);self.assertIsNone(r['cover_max_m'])
    def test_swn_not_telekom_or_vbb(self):
        for r in REVIEW['routes']:
            if r['network']!='BREITBAND':self.assertEqual(r['general_information_ids'],[])
    def test_original_data_not_mutated(self):
        before=copy.deepcopy(RAW);decorate_house_data(RAW,REVIEW);self.assertEqual(RAW,before)
    def test_geometric_payload_bitwise_unchanged(self):
        self.assertEqual(geometry_signature(RAW),geometry_signature(decorate_house_data(RAW,REVIEW)))
    def test_25_unknown_z_lists_stay_unknown(self):
        d=decorate_house_data(RAW,REVIEW)
        self.assertEqual(sum(r['z_mm'] is None for r in d['site']['routes']),25)
    def test_no_synthetic_water_network(self):
        d=decorate_house_data(RAW,REVIEW)
        self.assertEqual([r['network'] for r in d['site']['routes']],[r['network'] for r in RAW['site']['routes']])
    def test_correct_source_page_in_runtime_q42(self):
        f=next(f for f in decorate_house_data(RAW,REVIEW)['source_facts'] if f['id']=='Q42')
        self.assertEqual(f['sources'][0]['page'],3)
        self.assertFalse(f['values']['applied_as_route_depth'])
    def test_attributes_explicitly_disclaim_real_depth(self):
        r=next(r for r in decorate_house_data(RAW,REVIEW)['site']['routes'] if r['network']=='BREITBAND')
        attrs=object_attributes(r)
        self.assertIn('KEIN Bestandswert',attrs['HAUS_TIEFENHINWEIS'])
        self.assertEqual(attrs['HAUS_VERLEGEBAUWEISE'],'UNBEKANNT')
    def test_cannot_promote_rule_to_as_built(self):
        d=copy.deepcopy(REVIEW);d['rules'][0]['as_built_verified']=True
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_cannot_promote_rule_to_safe_envelope(self):
        d=copy.deepcopy(REVIEW);d['rules'][0]['is_safe_depth_envelope']=True
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_cannot_replace_unknown_depth_with_mean(self):
        d=copy.deepcopy(REVIEW);d['routes'][0]['depth_m']=0.9
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_cannot_set_unknown_installation_method(self):
        d=copy.deepcopy(REVIEW);d['routes'][0]['installation_method']='OFFENE_BAUWEISE'
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_cannot_apply_swn_rule_to_gas(self):
        d=copy.deepcopy(REVIEW);r=next(r for r in d['routes'] if r['network']=='GAS');r['general_information_ids']=['SWN_TK_OFFEN']
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_duplicate_route_audit_blocked(self):
        d=copy.deepcopy(REVIEW);d['routes'][1]=d['routes'][0]
        with self.assertRaises(ValueError):validate_review(d,RAW)
    def test_changed_physical_z_requires_re_review(self):
        d=copy.deepcopy(RAW);d['site']['routes'][0]['z_mm']=[-600]*len(d['site']['routes'][0]['points_local_mm'])
        with self.assertRaises(ValueError):validate_review(REVIEW,d)
    def test_no_duplicate_reference_id(self):
        d=copy.deepcopy(JOB);d['reference_lines'][1]['id']=d['reference_lines'][0]['id']
        with self.assertRaises(ValueError):validate_job(BASE,d)
    def test_no_zero_length_reference_line(self):
        d=copy.deepcopy(JOB);d['reference_lines'][0]['points_mm'][1]=d['reference_lines'][0]['points_mm'][0]
        with self.assertRaises(ValueError):validate_job(BASE,d)
    def test_reference_count_checked_before_nx(self):
        d=copy.deepcopy(JOB);d['line_segment_count']+=1
        with self.assertRaises(ValueError):validate_job(BASE,d)
    def test_preflight_checks_orphan_house_parts(self):
        nx=ns(session=ns(Parts=[ns(FullPath='C:/old/03_ERDGESCHOSS.prt')]))
        with self.assertRaises(RuntimeError):preflight_open_parts(nx,JOB,True,['03_ERDGESCHOSS.prt'])
    def test_environment_only_does_not_block_unrelated_house(self):
        nx=ns(session=ns(Parts=[ns(FullPath='C:/old/03_ERDGESCHOSS.prt')]))
        preflight_open_parts(nx,JOB,False,['03_ERDGESCHOSS.prt'])

# Avoid rediscovering imported TestCase classes and counting them a second time.
del NXSimulationTests

class DepthRuntimeTests(unittest.TestCase):
    def test_full_scene_and_house_write_depth_disclaimers_without_changing_z(self):
        from test_r09 import NXSimulationTests as Harness
        h=Harness();h.setUp()
        try:
            state=h.workflow(h.cfg(True))
            self.assertEqual(state['utility_depth_review']['confirmed_route_depths'],0)
            self.assertEqual(state['house']['built_solids'],1361)
            curves=[o for o in h.env.objects.values() if 'HAUS_TIEFENBELEG' in getattr(o,'attrs',{})]
            self.assertEqual(len(curves),45)
            self.assertTrue(all(o.a[2]==0 and o.b[2]==0 for o in curves))
            self.assertTrue(all(o.attrs['HAUS_TIEFENREGEL_ANWENDUNG']=='KEINE_REGELWERTE_ALS_ISTTIEFE' for o in curves))
        finally:h.doCleanups()
    def test_runtime_rejects_orphan_floor_before_step_import(self):
        from test_r09 import NXSimulationTests as Harness
        h=Harness();h.setUp()
        try:
            h.env.session.Parts.NewDisplay(str(h.root/'03_ERDGESCHOSS.prt'),h.env.N.Part.Units.Millimeters)
            with self.assertRaisesRegex(RuntimeError,'bereits geoeffnet'):
                h.workflow(h.cfg(True))
            self.assertEqual(h.env.step_calls,0)
        finally:h.doCleanups()
