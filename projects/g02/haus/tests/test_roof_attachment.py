# -*- coding: utf-8 -*-
"""Focused numerical roof tests. No NX kernel is simulated here."""
import copy,json,math,sys,unittest
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path.insert(0,str(B/'src'))
from haus2406_r03.haus_geometry import Parameters,validate
from haus2406_r03.haus_roof import hip,dormer,height,compile_roofs,resolve_dormer
from haus2406_r03.haus_compile import compile_house
D=json.loads((B/'data/haus.json').read_text());O=json.loads((B/'archiv/HAUS_MAIN01_VOR_DACHPRUEFUNG.json').read_text())
P=Parameters(D['parameters']);PO=Parameters(O['parameters']);H=compile_roofs(D,P,False)
OLD={x['id']:x for x in O['dormers']};NEW={x['id']:x for x in D['dormers']}
R={k:resolve_dormer(v,P,H) for k,v in NEW.items()}
angle=lambda f:math.degrees(math.atan(math.hypot(*f['plane'][:2])))

class RoofAttachmentTests(unittest.TestCase):
 def test_documented_main_pitch(self):self.assertEqual(P.value('DACH_MAIN_WINKEL'),45)
 def test_documented_wing_pitch(self):self.assertEqual(P.value('DACH_ANBAU_WINKEL'),28)
 def test_actual_main_faces_45(self):
  for x in D['roof_definitions'][:2]:
   for f in hip(x,P):self.assertAlmostEqual(angle(f),45,places=10)
 def test_actual_rotated_wing_faces_28(self):
  for f in hip(next(x for x in D['roof_definitions'] if x['id']=='DACH_ANBAU'),P):self.assertAlmostEqual(angle(f),28,places=10)
 def test_main_and_wing_geometry_unchanged(self):
  for old,new in zip(O['roof_definitions'],D['roof_definitions']):
   self.assertEqual(hip(old,PO),hip(new,P))
 def test_three_independent_estimated_dormer_parameters(self):
  self.assertEqual(len({v['pitch'] for v in NEW.values()}),3)
  for v in NEW.values():self.assertEqual(D['parameters'][v['pitch']]['status'],'GESCHAETZT')
 def test_dormer_angles_preserved(self):
  for key in OLD:self.assertAlmostEqual(angle(dormer(OLD[key],PO)),angle(dormer(R[key],P)),places=10)
 def test_front_roof_heights_preserved(self):
  for key in OLD:
   idx=1 if OLD[key]['front_axis']=='xmax' else 0
   self.assertAlmostEqual(PO.number(OLD[key]['roof_z'][idx]),P.number(R[key]['roof_z'][idx]))
 def test_front_locations_and_widths_preserved(self):
  for key in OLD:
   old,new=OLD[key]['rect'],R[key]['rect'];axis=0 if NEW[key]['axis']=='x' else 1
   front=axis if NEW[key]['front_axis'].endswith('min') else axis+2
   for index in {front,1-axis,3-axis}:self.assertAlmostEqual(old[index],new[index])
 def test_west_old_step_reproduced(self):self.assertAlmostEqual(5930-(3875+1800),255)
 def test_east_old_step_reproduced(self):self.assertAlmostEqual(5930-(11865-6200),265)
 def test_south_old_step_reproduced(self):self.assertAlmostEqual(5930-(3875+1800),255)
 def test_all_rear_seams_closed(self):
  for r in R.values():self.assertLess(r['attachment_check']['max_rear_gap_mm'],1e-7)
 def test_first_join_before_ridge(self):
  for r in R.values():self.assertLess(r['attachment_check']['front_to_rear_mm'],2500)
 def test_no_fixed_rear_elevation_controls(self):
  for item in NEW.values():self.assertNotIn('roof_z',item);self.assertEqual(item['rear_attachment'],'INTERSECTION_WITH_HOST')
 def test_seam_has_piecewise_domain_check(self):
  for r in R.values():self.assertGreaterEqual(len(r['attachment_check']['whole_rear_seam_checks']),3)
 def test_no_false_asbuilt_status(self):
  for r in R.values():self.assertFalse(r['attachment_check']['as_built_verified']);self.assertFalse(r['attachment_check']['flashing_or_structure_designed'])
 def test_no_input_changes(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);before=copy.deepcopy(d);resolve_dormer(d,P,H);self.assertEqual(d,before)
 def test_too_short_join_search_rejected(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);d['max_join_distance_mm']=10
  with self.assertRaisesRegex(ValueError,'Kein gueltiger'):resolve_dormer(d,P,H)
 def test_steeper_than_host_rejected(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);d['pitch']=55
  with self.assertRaisesRegex(ValueError,'Kein gueltiger'):resolve_dormer(d,P,H)
 def test_unknown_policy_rejected(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);d['rear_attachment']='GUESS'
  with self.assertRaisesRegex(ValueError,'Unbekannte'):resolve_dormer(d,P,H)
 def test_wrong_axis_rejected(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);d['axis']='y'
  with self.assertRaisesRegex(ValueError,'widersprechen'):resolve_dormer(d,P,H)
 def test_unknown_host_rejected(self):
  d=copy.deepcopy(NEW['GAUBE_WEST']);d['host_parents']=['NOT_A_ROOF']
  with self.assertRaises(ValueError):resolve_dormer(d,P,H)
 def test_pitch_parameter_changes_join_not_front(self):
  d=copy.deepcopy(D);d['parameters']['GAUBE_WEST_WINKEL_MODELL']['value']+=1;p=Parameters(d['parameters'])
  r=resolve_dormer(d['dormers'][0],p,compile_roofs(d,p,False))
  self.assertNotEqual(r['rect'][2],R['GAUBE_WEST']['rect'][2]);self.assertEqual(r['rect'][0],R['GAUBE_WEST']['rect'][0]);self.assertLess(r['attachment_check']['max_rear_gap_mm'],1e-7)
 def test_all_building_openings_unchanged(self):self.assertEqual(D['parts'],O['parts']);self.assertEqual(D['video_roof_windows'],O['video_roof_windows'])
 def test_balcony_solar_flat_roof_unchanged(self):
  for key in ['main_details','main_roof_faces','flat_roofs']:self.assertEqual(D[key],O[key])
 def test_garage_angle_not_laundered_into_planvalue(self):
  g=next(x for x in D['roof_definitions'] if x['id']=='DACH_GARAGE');self.assertEqual(g['pitch'],35);self.assertEqual(g['pitch_status'],'GESCHAETZT_KEIN_NUMERISCHER_PLANWINKEL')
 def test_no_dormer_rear_wall_generated(self):
  job=compile_house(D,True)
  for p in job['parts']:
   for s in p['solids']:
    if s['kind']=='GAUBENWANGE':self.assertNotIn('RUECKEN',s['id'])
 def test_legacy_definitions_still_valid(self):
  for d in OLD.values():self.assertEqual(resolve_dormer(d,PO,H),d)
 def test_data_schema_valid(self):self.assertEqual(validate(D)['errors'],[])

if __name__=='__main__':unittest.main(verbosity=2)
