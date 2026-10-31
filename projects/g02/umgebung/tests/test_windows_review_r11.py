"""Actual data/geometry tests and malformed-input regressions, NOT NX execution."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).absolute().parents[1];sys.path[:0]=[str(B),str(B/'basis/Haus_R06/src')]
from r09.video import enrich_house,enrich_if_present
from r09.windows_review import apply_review,checked_review
from r09.vegetation_review import selected_job
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_geometry import Parameters
from haus2406_r03.haus_consistency import consistency_report
from haus2406_r03.haus_audit import audit_compiled

class WindowReviewTests(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.raw=json.loads((B/'basis/Haus_R06/data/haus.json').read_text());c.spec=json.loads((B/'abgleich/FENSTER_AENDERUNGEN_R11.json').read_text())
  c.old=enrich_house(c.raw,json.loads((B/'video/VIDEO_DETAILS_R10.json').read_text()));c.new=apply_review(c.old,c.spec);c.job=compile_house(c.new,True)
  c.ops={o['id']:o for p in c.new['parts'] for w in p['walls'] for o in w.get('openings',[])}
  c.env=json.loads((B/'data/IMPORTAUFTRAG_R09.json').read_text());c.selected,c.selection=selected_job(B,c.env)
 def test_01_no_mutation(self):
  old=copy.deepcopy(self.old);apply_review(self.old,self.spec);self.assertEqual(self.old,old)
 def test_02_apply_once(self):
  with self.assertRaisesRegex(ValueError,'doppelt'):apply_review(self.new,self.spec)
 def test_03_baseline_required(self):
  with self.assertRaisesRegex(ValueError,'Videoausgangsstand'):apply_review(self.raw,self.spec)
 def test_04_disable_is_exact_baseline(self):
  s=copy.deepcopy(self.spec);s['enabled']=False;self.assertEqual(apply_review(self.old,s),self.old)
 def test_05_no_metric_claim(self):
  s=copy.deepcopy(self.spec);s['metric_as_built_verified']=True
  with self.assertRaises(ValueError):checked_review(s)
 def test_06_operation_duplicate_rejected(self):
  s=copy.deepcopy(self.spec);s['operations'].append(s['operations'][0])
  with self.assertRaises(ValueError):checked_review(s)
 def test_07_dimension_nan_rejected(self):
  s=copy.deepcopy(self.spec);s['operations'][0]['values']['width']=float('nan')
  with self.assertRaises(ValueError):checked_review(s)
 def test_08_source_page_required(self):
  s=copy.deepcopy(self.spec);s['operations'][0]['evidence_page']=20
  with self.assertRaises(ValueError):checked_review(s)
 def test_09_removed_false_openings(self):
  for name in ('KG_W_F00','KG_W_F01','EG_W_O01'):self.assertNotIn(name,self.ops)
 def test_10_entry_sills_not_zero(self):
  for name in ('EG_W_O02','EG_W_O04','EG_W_O05'):self.assertGreater(self.ops[name]['sill'],0)
 def test_11_plan_entry_sizes(self):
  self.assertEqual((self.ops['EG_W_O02']['width'],self.ops['EG_W_O02']['height']),(1385,1385))
  self.assertEqual((self.ops['EG_W_O04']['width'],self.ops['EG_W_O04']['height']),(1010,1010))
 def test_12_rear_exit_is_door(self):self.assertEqual(self.ops['EG_N_BAD']['kind'],'TUER');self.assertEqual(self.ops['EG_N_BAD']['sill'],0)
 def test_13_plan_disagreement_not_erased(self):self.assertTrue(self.ops['EG_S_F01']['plan_nominal_mm']);self.assertFalse(self.ops['EG_S_F01']['metric_as_built_verified'])
 def test_14_long_dormer_eight_lights_unchanged(self):
  lights=[o.get('video_panes',1) for k,o in self.ops.items() if k.startswith('R10_DG_STRASSE')];self.assertEqual(lights,[1,2,2,2,1])
 def test_15_garage_dormer_four_lights(self):self.assertEqual(sum(self.ops[n]['video_panes'] for n in ('DG_F_GAUBE_W1','DG_F_GAUBE_W2')),4)
 def test_16_courtyard_dormer_not_guessed(self):
  old={o['id']:o for p in self.old['parts'] for w in p['walls'] for o in w.get('openings',[])}
  for k in ('DG_F_GAUBE_O1','DG_F_GAUBE_O2','DG_F_GAUBE_O3'):self.assertEqual(self.ops[k],old[k])
 def test_17_all_changes_have_old_and_new(self):
  for o in self.new['window_review_revision']['operations']:
   self.assertIn('before',o);self.assertIn('after',o);self.assertTrue(o['reason'])
 def test_18_new_roof_windows_count(self):self.assertEqual(len(self.new['video_roof_windows']),9)
 def test_19_new_roof_windows_have_actual_frames_glass(self):
  p=next(p for p in self.job['parts'] if p['id']=='VIDEO_DACHFENSTER');self.assertEqual(len(p['solids']),45)
 def test_20_body_count(self):self.assertEqual(self.job['planned_solids'],1361)
 def test_21_reference_mode_zero_bodies(self):self.assertEqual(compile_house(self.new,False)['planned_solids'],0)
 def test_22_no_new_numerical_collisions(self):self.assertEqual(audit_compiled(self.new,self.job)['collision_count'],10)
 def test_23_no_new_blocked_openings_or_reference_errors(self):
  r=consistency_report(self.new,self.job);self.assertEqual(r['logical_errors'],[]);self.assertEqual(r['opening_clearance']['blocked_count'],2)
 def test_24_runtime_uses_same_overlay(self):self.assertEqual(enrich_if_present(B,self.raw),self.new)
 def test_25_property_and_utility_data_unchanged(self):self.assertEqual(self.new['site'],self.old['site'])
 def test_26_vegetation_only_four_groups_and_dgm(self):self.assertEqual(self.selection['active_ids'],['DGM','V01','V02','V03','V05'])
 def test_27_selected_source_count(self):self.assertEqual(self.selected['total_sheets'],115)
 def test_28_source_geometry_not_modified_by_filter(self):
  for p in self.selected['parts']:self.assertEqual(p,next(q for q in self.env['parts'] if q['id']==p['id']))
 def test_29_unmatched_not_imported_or_called_removed(self):
  self.assertEqual(self.selection['not_automatically_imported'],['V04','V06','V07','V08','F01']);self.assertFalse(self.selection['metric_as_built_verified'])
 def test_30_every_group_has_explicit_review(self):
  p=self.selection['policy'];self.assertEqual(len(p['groups']),8);self.assertTrue(all(x['video'] and x['reason'] for x in p['groups']))
 def test_31_bad_vegetation_policy_rejected(self):
  p=copy.deepcopy(self.selection['policy']);p['groups'][0]['include']='yes'
  with patch('r09.vegetation_review.read_json',return_value=p),self.assertRaises(ValueError):selected_job(B,self.env)
 def test_32_unknown_dgm_height_not_filled(self):
  c=json.loads((B/'data/EINSTELLUNGEN_R09.json').read_text());self.assertIsNone(c['height_connection']['H_EG_zero_in_source_datum_m'])
 def test_33_original_video_provenance(self):self.assertEqual(len(self.spec['video_sha256']),64)

if __name__=='__main__':unittest.main(verbosity=2)
