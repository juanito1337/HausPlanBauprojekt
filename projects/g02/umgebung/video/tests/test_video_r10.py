import copy, hashlib, json, math, sys, unittest
from pathlib import Path
BASE=Path(__file__).parents[2]
sys.path[:0]=[str(BASE),str(BASE/'basis/Haus_R06/src')]
from r09.video import enrich_house, validate_spec, _roof_host, _rectangle
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_geometry import Parameters, validate, convex_intersection, area
from haus2406_r03.haus_profile import validate_compiled_profiles
from haus2406_r03.haus_audit import audit_compiled
from haus2406_r03.haus_consistency import consistency_report
from haus2406_r03.haus_metadata import object_attributes
from haus2406_r03.haus_roof import compile_roofs

class VideoChecks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads((BASE/'basis/Haus_R06/data/haus.json').read_text())
  cls.spec=json.loads((BASE/'video/VIDEO_DETAILS_R10.json').read_text())
  cls.enriched=enrich_house(cls.data,cls.spec)
  cls.job=compile_house(cls.enriched,True);cls.params=Parameters(cls.data['parameters'])
  cls.before=compile_house(cls.data,True)
  cls.audit=audit_compiled(cls.enriched,cls.job)
  cls.consistency=consistency_report(cls.enriched,cls.job,cls.audit)
 def newwall(self):return next(w for p in self.enriched['parts'] for w in p['walls'] if w['id']=='DG_W_SUED')
 def test_01_schema(self):self.assertTrue(validate_spec(self.spec))
 def test_02_original_unchanged(self):self.assertEqual(self.data,json.loads((BASE/'basis/Haus_R06/data/haus.json').read_text()))
 def test_03_disabled_exact_baseline(self):
  s=copy.deepcopy(self.spec);s['enabled']=False;self.assertEqual(enrich_house(self.data,s),self.data)
 def test_04_no_double_application(self):
  with self.assertRaises(ValueError):enrich_house(self.enriched,self.spec)
 def test_05_16_components(self):self.assertEqual(len(self.job['parts']),16)
 def test_06_five_dormer_groups(self):self.assertEqual(len(self.newwall()['openings']),5)
 def test_07_eight_panes(self):self.assertEqual([o['video_panes'] for o in self.newwall()['openings']],[1,2,2,2,1])
 def test_08_old_three_removed(self):self.assertFalse(set(self.spec['front_dormer']['replace_ids']) & {o['id'] for o in self.newwall()['openings']})
 def test_09_three_existing_widths_retained(self):self.assertEqual([o['width'] for o in self.newwall()['openings'] if o['video_panes']==2],[1500]*3)
 def test_10_existing_heights_retained(self):self.assertTrue(all(o['height']==1500 and o['sill']==800 for o in self.newwall()['openings']))
 def test_11_dimensions_are_not_surveyed(self):self.assertTrue(all(o['status']=='GESCHAETZT' and not o['as_built_verified'] for o in self.newwall()['openings']))
 def test_12_six_roof_windows(self):self.assertEqual(len(self.enriched['video_roof_windows']),6)
 def test_13_thirty_roof_window_bodies(self):self.assertEqual(len(next(p for p in self.job['parts'] if p['id']=='VIDEO_DACHFENSTER')['solids']),30)
 def test_14_six_clear_roof_holes(self):self.assertEqual(len(self.job['video_roof_cut_check']),6);self.assertTrue(all(x['remaining_roof_projection_mm2']<=.1 for x in self.job['video_roof_cut_check']))
 def test_15_pv_not_individual_modules(self):self.assertTrue(all(f['module_count'] is None for f in self.spec['pv_fields']))
 def test_16_pv_does_not_cover_windows(self):
  pv=next(p for p in self.job['parts'] if p['id']=='VIDEO_SOLARFELDER')
  for s in pv['solids']:
   for w in self.enriched['video_roof_windows']:
    hit=convex_intersection([p[:2] for p in s['points']],w['polygon']);self.assertLessEqual(abs(area(hit)) if hit else 0,.1)
 def test_17_profiles(self):self.assertEqual(validate_compiled_profiles(self.job,self.params)['profile_count'],self.job['planned_solids'])
 def test_18_no_invalid_solids(self):self.assertEqual(self.audit['invalid_solids'],[])
 def test_19_no_new_collisions(self):
  a=audit_compiled(self.data,self.before);self.assertEqual(self.audit['collisions'],a['collisions'])
 def test_20_two_existing_blocked_openings(self):self.assertEqual(self.consistency['opening_clearance']['blocked_count'],2)
 def test_21_logical_source_integrity(self):self.assertEqual(self.consistency['logical_errors'],[])
 def test_22_reference_mode_has_no_proxy_bodies(self):self.assertEqual(compile_house(self.enriched,False)['planned_solids'],0)
 def test_23_unique_ids(self):
  ids=[s['id'] for p in self.job['parts'] for s in p['solids']];self.assertEqual(len(ids),len(set(ids)))
 def test_24_no_site_change(self):self.assertEqual(self.data['site'],self.enriched['site'])
 def test_25_no_roof_pitch_or_span_change(self):self.assertEqual(self.data['roof_definitions'],self.enriched['roof_definitions'])
 def test_26_no_structural_members_invented(self):self.assertEqual(self.data['construction'],self.enriched['construction'])
 def test_27_no_height_datum_change(self):self.assertEqual(self.data['parameters'],self.enriched['parameters'])
 def test_28_other_parts_equal(self):
  for old,new in zip(self.data['parts'],self.enriched['parts']):
   if old['id']!='DG':self.assertEqual(old,new)
 def test_29_quantity_exclusion(self):
  for p in self.enriched['parts']:
   for q in p['prisms']:
    if q['id'].startswith('R10_'):self.assertTrue(q['quantity_excluded'])
 def test_30_attributes(self):
  a=object_attributes(self.newwall()['openings'][0]);self.assertEqual(a['HAUS_REVISION'],'R10');self.assertEqual(a['HAUS_VIDEO_SICHTBAR'],'IM_BILD_SICHTBAR');self.assertTrue(all(k.startswith('HAUS_') for k in a))
 def test_31_no_fake_metric_approval(self):
  s=copy.deepcopy(self.spec);s['geometric_as_built_verified']=True
  with self.assertRaises(ValueError):validate_spec(s)
 def test_32_no_fake_structural_approval(self):
  s=copy.deepcopy(self.spec);s['structural_approval']=True
  with self.assertRaises(ValueError):validate_spec(s)
 def test_33_no_fake_audio_evaluation(self):
  s=copy.deepcopy(self.spec);s['video_audio_transcribed']=True
  with self.assertRaises(ValueError):validate_spec(s)
 def test_34_no_unknown_source_pages(self):
  s=copy.deepcopy(self.spec);s['roof_windows'][0]['evidence_page']=99
  with self.assertRaises(ValueError):validate_spec(s)
 def test_35_degenerate_profile_rejected(self):
  with self.assertRaises(ValueError):_rectangle([1,2,1,5])
 def test_36_roof_plane_break_rejected(self):
  faces=compile_roofs(self.data,self.params)
  with self.assertRaises(ValueError):_roof_host(faces,_rectangle([16000,3000,20000,5000]),'TEST','DACH_QUER')
 def test_37_disabled_input_not_mutated(self):
  s=copy.deepcopy(self.spec);s['enabled']=False;before=copy.deepcopy(s);enrich_house(self.data,s);self.assertEqual(s,before)
 def test_38_validated_house(self):self.assertEqual(validate(self.enriched)['errors'],[])
 def test_39_observation_register(self):self.assertEqual(len(self.spec['observations']),18);self.assertTrue(all(not x['metric_verified'] for x in self.spec['observations']))
 def test_40_frame_glass_counts(self):
  d=next(p for p in self.job['parts'] if p['id']=='DG');glass=[x for x in d['solids'] if x['id'].startswith('R10_DG_STRASSE') and x['kind']=='GLAS'];self.assertEqual(len(glass),8)
if __name__=='__main__':unittest.main(verbosity=2)
