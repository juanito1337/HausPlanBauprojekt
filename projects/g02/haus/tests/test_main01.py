# -*- coding: utf-8 -*-
"""Offline source/geometry/control-flow tests. FakeNX never validates the NX kernel."""
import ast,copy,hashlib,io,json,math,shutil,sys,tempfile,unittest
from contextlib import redirect_stdout
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path[:0]=[str(B/'src'),str(B/'tests')]
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_geometry import Parameters,area,opening_polygon
from haus2406_r03.haus_main_details import main_basis,main_xy,uv_rect,validate_main_data
from haus2406_r03.haus_audit import audit_compiled,vertical_record,intersection_volume
from haus2406_r03.haus_consistency import consistency_report
from haus2406_r03.haus_runtime import read_json,sha256_file,settings_checked
from main01.runtime import Monitor,StopRequested,run_main,verify_package,HouseMainAdapter
from fake_nx import FakeNX
D=read_json(B/'data/haus.json');J=compile_house(D,True);P=Parameters(D['parameters'])
OLD=read_json(B/'archiv/HAUS_R11_UNVERAENDERT.json');OLD_J=compile_house(OLD,True)
A=audit_compiled(D,J);C=consistency_report(D,J,A)
PARTS={p['id']:p for p in J['parts']};SOLIDS=[s for p in J['parts'] for s in p['solids']]
WALLS={w['id']:w for p in D['parts'] for w in p.get('walls',[])}
OPENINGS={o['id']:dict(o,wall=w['id']) for p in D['parts'] for w in p.get('walls',[]) for o in w.get('openings',[])}

class ModelTests(unittest.TestCase):
 def test_no_terrain_or_lines(self):
  self.assertFalse(D['site']['enabled']);self.assertFalse(any(p.get('force_reference_display') for p in J['parts']));self.assertNotIn('GRUNDSTUECK',PARTS)
 def test_one_balcony(self):self.assertEqual(J['main01_review']['modelled_balconies'],1)
 def test_component_count(self):self.assertEqual(len(PARTS),15)
 def test_positive_solid_count(self):self.assertEqual(len(SOLIDS),1418)
 def test_all_unique_solid_ids(self):self.assertEqual(len(SOLIDS),len({s['id'] for s in SOLIDS}))
 def test_removed_false_wall(self):self.assertNotIn('DG_W_BALKON',WALLS)
 def test_old_wall_retained_ledger(self):self.assertEqual(D['main_baseline']['removed_false_model_wall']['id'],'DG_W_BALKON')
 def test_door_on_real_outer_wall(self):self.assertEqual(OPENINGS['DG_T_BALKON_1']['wall'],'DG_W_OST')
 def test_door_floor_reference(self):self.assertEqual(OPENINGS['DG_T_BALKON_1']['height_reference'],'Z_DG')
 def test_no_document_link_errors(self):self.assertEqual(C['logical_errors'],[])
 def test_no_invalid_volume(self):self.assertEqual(A['invalid_solids'],[])
 def test_old_collision_pairs_not_new(self):
  old=audit_compiled(OLD,OLD_J);pairs=lambda x:{tuple(sorted((r['a'],r['b']))) for r in x['collisions']}
  self.assertEqual(pairs(A),pairs(old));self.assertEqual(A['collision_count'],10)
 def test_two_blocked_interior_openings(self):self.assertEqual(C['opening_clearance']['blocked_count'],2)
 def test_balcony_door_not_blocked(self):
  self.assertEqual(next(r for r in C['opening_clearance']['checks'] if r['opening']=='DG_T_BALKON_1')['status'],'NUMERISCH_FREI')
  wall=WALLS['DG_W_OST'];o=next(o for o in wall['openings'] if o['id']=='DG_T_BALKON_1');z=P.value('Z_DG')
  opening={'polygon':opening_polygon(wall,o,P,extra=0),'lo':[0,0,z],'hi':[0,0,z+P.value('BAL_TUER_HOEHE')]}
  for part in [PARTS['DACH'],PARTS['BALKON_ZUGANG']]:
   for solid in part['solids']:self.assertLessEqual(intersection_volume(opening,vertical_record(solid,P,part['id'])),1.0,solid['id'])
 def test_no_structural_approval(self):self.assertFalse(D['main_baseline']['structural_approval']);self.assertFalse(C['structural_design_verified'])
 def test_no_measured_approval(self):self.assertFalse(D['main_baseline']['metric_as_built_verified']);self.assertFalse(C['as_built_verified'])
 def test_sources_M01_fivepages(self):self.assertEqual(D['source_document_pages']['M01'],5)
 def test_balcony_dimension_status(self):
  for k,v in D['parameters'].items():
   if k.startswith(('BAL_','ABGANG_','FALLROHR_')):self.assertEqual(v['status'],'GESCHAETZT',k)
 def test_balcony_reference_area_not_living_area(self):
  self.assertAlmostEqual(J['main01_review']['estimated_balcony_area_m2'],18.5603);self.assertNotEqual(18.5603,8.74)
 def test_no_hidden_foundations(self):self.assertFalse(J['main01_review']['concealed_foundations_or_joist_grid_added'])
 def test_new_parts_quantity_excluded(self):
  for k in ['BALKON_RECHTS','BALKON_ZUGANG','KELLERABGANG_GELAENDER','FALLROHR_SICHTABSCHNITTE']:
   for s in PARTS[k]['solids']:self.assertTrue(s['meta']['quantity_excluded']);self.assertFalse(s['meta']['as_built_verified'])
 def test_basis_orthogonal(self):
  a,t,n=main_basis(D);self.assertAlmostEqual(sum(x*x for x in t),1);self.assertAlmostEqual(sum(x*y for x,y in zip(t,n)),0)
 def test_units_preserved(self):self.assertEqual(D['units'],'mm');self.assertEqual(D['coordinate_system'],OLD['coordinate_system'])
 def test_centred_round_posts_touch_beam(self):
  s={r['id']:r for r in PARTS['BALKON_RECHTS']['solids']};Z=P.value('Z_DG');z=Z-P.value('BAL_BELAG_DICKE')-P.value('BAL_RANDHOEHE')
  _,t,n=main_basis(D);a=D['main_details']['anchor']['a']
  for k,r in s.items():
   if 'STUETZE' in k:
    self.assertAlmostEqual(r['top'],z);xy=[sum(p[i] for p in r['polygon'])/len(r['polygon']) for i in (0,1)]
    v=sum((xy[i]-a[i])*n[i] for i in range(2));self.assertAlmostEqual(v,P.value('BAL_V_START')+P.value('BAL_PROJEKTION')-P.value('BAL_RAND_BREITE')/2,places=5)
 def test_three_sides_seven_display_rows(self):self.assertEqual(sum(s['kind']=='BALKON_BEKLEIDUNG' for s in SOLIDS),21)
 def test_two_downpipe_envelopes(self):self.assertEqual(len(PARTS['FALLROHR_SICHTABSCHNITTE']['solids']),2)
 def test_nine_roof_windows_preserved(self):
  self.assertEqual(len(PARTS['VIDEO_DACHFENSTER']['solids']),len(next(p for p in OLD_J['parts'] if p['id']=='VIDEO_DACHFENSTER')['solids']))
 def test_no_input_mutation(self):
  d=copy.deepcopy(D);before=json.dumps(d,sort_keys=True);compile_house(d,True);self.assertEqual(before,json.dumps(d,sort_keys=True))
 def test_repeat_deterministic(self):self.assertEqual(J,compile_house(D,True))
 def test_reference_mode_no_detail_bodies(self):self.assertEqual(compile_house(D,False)['planned_solids'],0)
 def test_projection_edit_changes_deck_area(self):
  d=copy.deepcopy(D);d['parameters']['BAL_PROJEKTION']['value']+=200;j=compile_house(d,True)
  self.assertAlmostEqual(j['main01_review']['estimated_balcony_area_m2']-J['main01_review']['estimated_balcony_area_m2'],1.034,places=5)
 def test_niche_height_edit_used_in_roof(self):
  d=copy.deepcopy(D);d['parameters']['BAL_NISCHE_DACH_VORN']['value']+=100;j=compile_house(d,True)
  f=lambda j:next(x for x in j['roof_faces'] if x['parent']=='MAIN01_BALKON_ZUGANG_DACH')['plane']
  self.assertNotEqual(f(J),f(j))
 def assert_param_rejected(self,key,value):
  d=copy.deepcopy(D);d['parameters'][key]['value']=value
  with self.assertRaises(ValueError):compile_house(d,True)
 def test_negative_projection_rejected(self):self.assert_param_rejected('BAL_PROJEKTION',-10)
 def test_door_beyond_wall_rejected(self):self.assert_param_rejected('BAL_TUER_OFFSET',9000)
 def test_short_niche_rejected(self):self.assert_param_rejected('BAL_NISCHE_DACH_VORN',4500)
 def test_bad_post_z_rejected(self):self.assert_param_rejected('BAL_STUETZE_FUSS',4000)
 def test_thick_niche_not_silently_desynchronised(self):self.assert_param_rejected('BAL_NISCHE_HUELLE',500)
 def test_mismatched_anchor_rejected(self):
  d=copy.deepcopy(D);d['main_details']['anchor']['a'][0]+=100
  with self.assertRaises(ValueError):compile_house(d,True)
 def test_bad_board_count_rejected(self):
  d=copy.deepcopy(D);d['main_details']['balcony']['horizontal_board_rows']=True
  with self.assertRaises(ValueError):compile_house(d,True)
 def test_unknown_asbuilt_flag_rejected(self):
  d=copy.deepcopy(D);d['main_baseline']['metric_as_built_verified']=True
  with self.assertRaises(ValueError):compile_house(d,True)
 def test_optional_guard_can_be_omitted(self):
  d=copy.deepcopy(D);d['main_details']['cellar_railing']['enabled']=False;j=compile_house(d,True)
  self.assertNotIn('KELLERABGANG_GELAENDER',{p['id'] for p in j['parts']})
 def test_bad_downpipe_rejected(self):
  d=copy.deepcopy(D);d['main_details']['downpipes']['items'][0]['top']=-9000
  with self.assertRaises(ValueError):compile_house(d,True)
 def test_python_310_syntax(self):
  for p in list((B/'src').rglob('*.py'))+[B/'00_HAUS_MAIN01_ERZEUGEN.py']:
   ast.parse(p.read_text(encoding='utf8'),filename=str(p),feature_version=(3,10))
 def test_no_step_import_call_in_house_source(self):
  for p in (B/'src').rglob('*.py'):
   tree=ast.parse(p.read_text())
   for node in ast.walk(tree):
    if isinstance(node,ast.Attribute):self.assertNotIn(node.attr,['CreateStep214Importer','CreateStep242Importer','AskMinimumDist','NewFaceProperties'],str(p))
 def test_only_one_starter(self):self.assertEqual([p.name for p in B.glob('*.py')],['00_HAUS_MAIN01_ERZEUGEN.py'])

class ControlTests(unittest.TestCase):
 def test_monitor_event_and_file(self):
  with tempfile.TemporaryDirectory() as t:
   m=Monitor(t)
   with m.step('FEATURE','x'):pass
   self.assertEqual(read_json(Path(t)/'LAUFSTATUS_MAIN01.json')['completed_steps'],1)
 def test_monitor_stop_prevents_next_step(self):
  with tempfile.TemporaryDirectory() as t:
   m=Monitor(t);m.stop.touch()
   with self.assertRaises(StopRequested):
    with m.step('FEATURE','never'):self.fail('must not run')
 def test_original_error_preserved(self):
  with tempfile.TemporaryDirectory() as t:
   m=Monitor(t)
   with self.assertRaisesRegex(RuntimeError,'original'):
    with m.step('FEATURE','x'):raise RuntimeError('original')
 def test_strict_settings(self):
  with self.assertRaises(ValueError):settings_checked({'allow_estimates':'yes'})
 def test_duplicate_json_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'x.json';p.write_text('{"a":1,"a":2}')
   with self.assertRaises(ValueError):read_json(p)
 def test_registry_missing_file(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'PAKETDATEIEN_SHA256.json').write_text('{"files":{"x":"x"}}')
   with self.assertRaises(FileNotFoundError):verify_package(b)
 def test_code_tamper_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'x.py').write_text('changed');(b/'PAKETDATEIEN_SHA256.json').write_text('{"files":{"x.py":"x"}}')
   with self.assertRaises(ValueError):verify_package(b)
 def test_editable_input_recorded(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);(b/'data').mkdir();(b/'data/haus.json').write_text('{}');(b/'PAKETDATEIEN_SHA256.json').write_text('{"files":{"data/haus.json":"old"}}')
   self.assertFalse(verify_package(b)['baseline_inputs_unchanged'])
 def test_no_actual_nx_dependency_for_compilation(self):self.assertIsInstance(compile_house(D,True),dict)
 def test_fake_complete_house_and_baseline(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);shutil.copytree(B/'data',b/'data');shutil.copytree(B/'src',b/'src');env=FakeNX();env.N.Update.Option.Later='LATER'
   with env.install(),redirect_stdout(io.StringIO()):result=run_main(b,verify=False)
   self.assertEqual(result['built_solids'],1418);self.assertEqual(result['component_count'],15)
   self.assertFalse(result['as_built_verified']);self.assertFalse(result['environment_included']);self.assertFalse(result['STEP_import'])
   self.assertEqual(env.expression_attribute_attempts,0);self.assertEqual(env.reserved_attribute_attempts,[])
   out=Path(result['output_directory']);self.assertTrue((out/'BASELINE_MAIN01.json').is_file())
   self.assertGreater(read_json(out/'LAUFSTATUS_MAIN01.json')['completed_steps'],1400)
   self.assertTrue(all(Path(p.FullPath).read_bytes().startswith(b'TESTDOUBLE_NOT_NX_PART') for p in env.session.Parts))
 def test_fake_feature_failure_no_baseline(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);shutil.copytree(B/'data',b/'data');shutil.copytree(B/'src',b/'src');env=FakeNX();env.fail_commit_at=3
   with env.install(),redirect_stdout(io.StringIO()),self.assertRaises(Exception):run_main(b,verify=False)
   self.assertFalse((b/'LETZTER_MAIN01_LAUF.json').exists());self.assertEqual(list(b.rglob('BASELINE_MAIN01.json')),[])
 def test_fake_save_failure_no_baseline(self):
  with tempfile.TemporaryDirectory() as t:
   b=Path(t);shutil.copytree(B/'data',b/'data');shutil.copytree(B/'src',b/'src');env=FakeNX();env.fail_save=True
   with env.install(),redirect_stdout(io.StringIO()),self.assertRaises(Exception):run_main(b,verify=False)
   self.assertFalse((b/'LETZTER_MAIN01_LAUF.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
