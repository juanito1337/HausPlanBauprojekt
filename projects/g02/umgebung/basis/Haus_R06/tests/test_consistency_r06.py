# -*- coding: utf-8 -*-
"""R06 regression tests: actual source/data issues, not NX certification."""
import copy,json,math,os,sys,unittest
from pathlib import Path
BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_geometry import Parameters,validate,enabled
from haus2406_r03.haus_compile import compile_house,wall_intervals
from haus2406_r03.haus_roof import hip,height
from haus2406_r03.haus_details import inserts_for
from haus2406_r03.haus_consistency import source_integrity,system_integrity,opening_clearance,roof_height_checks,registration_checks,consistency_report
from haus2406_r03.haus_metadata import object_attributes

class ConsistencyR06Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads((BASE/'data/haus.json').read_text());cls.p=Parameters(cls.d['parameters'])
        cls.c=compile_house(cls.d,True);cls.r=consistency_report(cls.d,cls.c)
        cls.w={w['id']:w for p in cls.d['parts'] for w in p.get('walls',[])}
        cls.old=json.loads((BASE/'historie/haus_R05_unveraendert.json').read_text())
    def test_fifty_files_ninety_two_pages_in_inventory(self):
        inv=json.loads((BASE/'data/DOKUMENTABDECKUNG_R06.json').read_text())
        self.assertEqual((len(inv['documents']),sum(d['pages'] for d in inv['documents'])),(50,92))
        self.assertTrue(inv['all_files_hash_verified']);self.assertFalse(inv['semantic_full_coverage_confirmed'])
    def test_fact_ledger_matches_canonical_data(self):
        f=json.loads((BASE/'data/QUELLENFAKTEN_R06.json').read_text());self.assertEqual(f['facts'],self.d['source_facts']);self.assertEqual(len(f['facts']),44)
    def test_references_all_resolve_but_not_semantic_proof(self):
        r=source_integrity(self.d);self.assertFalse(r['errors']);self.assertGreater(r['checked_references'],400);self.assertIn('KEIN semantischer',r['meaning'])
    def test_missing_doc_in_nested_fact_detected(self):
        d=copy.deepcopy(self.d);d['source_facts'][0]['sources'][0]['document']='NICHT_VORHANDEN'
        self.assertTrue(source_integrity(d)['errors'])
    def test_impossible_page_detected_outside_primary_walls(self):
        d=copy.deepcopy(self.d);d['site']['routes'][0]['sources'][0]['page']=500
        self.assertTrue(source_integrity(d)['errors'])
    def test_boolean_page_not_valid(self):
        d=copy.deepcopy(self.d);d['source_facts'][0]['sources'][0]['page']=True
        self.assertTrue(source_integrity(d)['errors'])
    def test_old_missing_system_links_reproduced(self):
        r=system_integrity(self.old);self.assertGreaterEqual(len(r['dangling']),100)
    def test_current_system_links_resolve(self):
        self.assertFalse(system_integrity(self.d)['dangling']);self.assertFalse(system_integrity(self.d)['duplicate_systems'])
    def test_new_dangling_link_detected(self):
        d=copy.deepcopy(self.d);d['parts'][1]['walls'][0]['system_id']='MISSING'
        self.assertTrue(system_integrity(d)['dangling'])
    def test_duplicate_system_detected(self):
        d=copy.deepcopy(self.d);d['construction']['systems'].append(copy.deepcopy(d['construction']['systems'][0]))
        self.assertTrue(system_integrity(d)['duplicate_systems'])
    def test_wintergarten_register_not_unassigned(self):
        a=next(a for a in self.d['material_assemblies'] if a['id']=='WINTERGARTEN_SUED_P21')
        self.assertEqual(a['assigned_wall'],'EG_AW_06');self.assertIn('NICHT_AM_BAU',a['assignment_status'])
        self.assertEqual(sum(l['thickness_mm'] for l in a['layers_inside_out']),410)
    def test_floor_register_no_solid_timber_proxy_claim(self):
        a=next(a for a in self.d['material_assemblies'] if a['id']=='ANBAU_FUSSBODEN_P18')
        self.assertEqual(a['assignment_status'],'ZWEI_BODENSCHICHTEN_OHNE_TRAGGLIEDER')
        self.assertEqual(sum(l['thickness_mm'] for l in a['layers']),80)
    def test_79_full_openings_are_checked(self):
        self.assertEqual(self.r['opening_clearance']['checked_openings'],79)
    def test_two_partial_obstructions_not_hidden(self):
        ids={r['opening'] for r in self.r['opening_clearance']['checks'] if r['status']=='BLOCKIERT'}
        self.assertEqual(ids,{'KG_T_A_FLUR_BAD_1','EG_T_B_ABST_S'})
    def test_blocked_door_inserts_not_drawn_as_complete(self):
        blocked={r['id'] for r in self.c['coverage'] if r['status']=='GESPERRT_OEFFNUNG_BLOCKIERT'}
        self.assertEqual(blocked,{'KG_T_A_FLUR_BAD_1_EINBAUTEIL','EG_T_B_ABST_S_EINBAUTEIL'})
        self.assertFalse(any(s['parent'] in {'KG_T_A_FLUR_BAD_1','EG_T_B_ABST_S'} for p in self.c['parts'] for s in p['solids']))
    def test_no_unsupported_door_shift_or_shrink(self):
        old=next(o for p in self.old['parts'] for w in p.get('walls',[]) for o in w.get('openings',[]) if o['id']=='EG_T_B_ABST_S')
        new=self.w['EG_IW_B_ABST_S']['openings'][0]
        self.assertEqual((old['offset'],old['width']),(new['offset'],new['width']))
    def test_clear_opening_threshold_must_be_positive(self):
        with self.assertRaises(ValueError):opening_clearance(self.d,self.c,0)
    def test_opening_heights_not_bound_to_wall_foot(self):
        w={'bottom':-60,'top':2700};o={'sill':0,'height':2000,'height_reference':0}
        lohi=wall_intervals(w,[o],Parameters({}));self.assertEqual([(self.p.number(a),self.p.number(b)) for a,b in lohi],[(-60,0),(2000,2700)])
    def test_legacy_opening_reference_retained_when_not_given(self):
        w={'bottom':-60,'top':2700};o={'sill':0,'height':2000}
        vals=wall_intervals(w,[o],Parameters({}));self.assertEqual([(self.p.number(a),self.p.number(b)) for a,b in vals],[(1940,2700)])
    def test_insert_heights_use_same_explicit_floor_reference(self):
        w=copy.deepcopy(self.w['EG_IW_B_ABST_S']);w['bottom']=-60;o=w['openings'][0]
        a=inserts_for(w,o,self.p,self.d['visual_defaults']);w['bottom']=-160
        b=inserts_for(w,o,self.p,self.d['visual_defaults'])
        self.assertEqual([(s['bottom'],s['top']) for s in a],[(s['bottom'],s['top']) for s in b])
    def test_invalid_explicit_reference_rejected(self):
        d=copy.deepcopy(self.d);w=next(w for p in d['parts'] for w in p.get('walls',[]) if w['openings']);w['openings'][0]['height_reference']='DOES_NOT_EXIST'
        self.assertTrue(validate(d)['errors'])
    def test_explicit_height_above_wall_rejected(self):
        d=copy.deepcopy(self.d);w=next(w for p in d['parts'] for w in p.get('walls',[]) if w['openings']);w['openings'][0]['height_reference']=100000
        self.assertTrue(any('Oeffnung ueber Wand' in x for x in validate(d)['errors']))
    def test_anbau_source_height_chain_5360(self):
        self.assertEqual(self.p.value('FIRST_ANBAU_P18'),5360)
        r=next(r for r in self.r['roof_heights'] if r['roof']=='DACH_ANBAU');self.assertAlmostEqual(r['maximum_height_mm'],5360)
    def test_old_anbau_ridge_chain_deviation_reproduced(self):
        p=Parameters(self.old['parameters']);r=next(x for x in self.old['roof_definitions'] if x['id']=='DACH_ANBAU')
        z=max(height(f,q) for f in hip(r,p) for q in f['polygon']);self.assertAlmostEqual(5360-z,73.2336149669)
    def test_ridge_reference_survives_changed_proxy_span(self):
        r=copy.deepcopy(next(x for x in self.d['roof_definitions'] if x['id']=='DACH_ANBAU'));r['rect'][2]+=250
        z=max(height(f,q) for f in hip(r,self.p) for q in f['polygon']);self.assertAlmostEqual(z,5360)
    def test_angle_28_not_modified_to_fit(self):
        r=next(x for x in self.d['roof_definitions'] if x['id']=='DACH_ANBAU');self.assertEqual(self.p.number(r['pitch']),28)
    def test_16cm_zone_not_declared_reinforced_concrete(self):
        a=self.d['parameters']['D_ANBAU_DECKENZONE_P18'];self.assertIn('KEIN Nachweis',a['note'])
    def test_no_guessed_members_enabled(self):
        self.assertTrue(all(not x['enabled'] for x in self.d['construction']['pending_members']))
    def test_roof_and_visual_inserts_excluded_from_real_quantities(self):
        for p in self.c['parts']:
            for s in p['solids']:
                if s['kind'] in ('DACH','FENSTERRAHMEN','TUERBLATT','GLAS','GAUBENWANGE','FLACHDACH_REFERENZ'):
                    self.assertTrue(s['meta'].get('quantity_excluded'),s['id'])
    def test_unknown_members_not_counted_as_material(self):
        self.assertFalse(any(s['kind']=='TRAGGLIED' for p in self.c['parts'] for s in p['solids']))
    def test_map_source_recalculation_all_25_paths(self):
        r=registration_checks(self.d['site']);self.assertEqual(len(r['checks']),25);self.assertFalse(r['errors'])
    def test_shifted_utility_point_detected(self):
        s=copy.deepcopy(self.d['site']);s['routes'][0]['points_local_mm'][0][0]+=100
        self.assertTrue(registration_checks(s)['errors'])
    def test_wrong_map_matrix_detected(self):
        s=copy.deepcopy(self.d['site']);s['registrations'][0]['matrix_2x3'][0][2]+=5
        self.assertTrue(registration_checks(s)['errors'])
    def test_missing_registration_detected(self):
        s=copy.deepcopy(self.d['site']);s['routes'][0]['registration_id']='unknown'
        self.assertTrue(registration_checks(s)['errors'])
    def test_unknown_heights_not_filled_from_leaflet(self):
        self.assertEqual(self.r['map_registration']['unknown_route_heights'],25)
        self.assertEqual(self.r['map_registration']['unknown_outer_diameters'],25)
    def test_room_register_fifty_not_spatial_claim(self):
        self.assertEqual(len(self.d['rooms']),50);new=[r for r in self.d['rooms'] if r.get('geometry_status')=='KEIN_RAUMPOLYGON_ERGAENZT']
        self.assertEqual(len(new),10);self.assertTrue(all(r['point'] is None for r in new))
    def test_room_area_uncertainty_not_silently_corrected(self):
        r=next(r for r in self.d['rooms'] if r['id']=='EG_N_W');self.assertFalse(r['area_use_for_validation']);self.assertIn('22_32',r['reading_status'])
    def test_source_area_sums_not_whole_house_volume(self):
        for ident in ('Q32','Q33'):
            f=next(f for f in self.d['source_facts'] if f['id']==ident)
            self.assertAlmostEqual(sum(f['values']['areas_m2']),f['values']['total_m2'])
    def test_no_technical_completion_flag_from_unit_test_success(self):
        self.assertFalse(self.r['technical_consistency_confirmed']);self.assertFalse(self.r['document_coverage_complete']);self.assertFalse(self.r['structural_design_verified'])
    def test_namespace_safe_current_master_metadata(self):
        a=object_attributes({'technical_consistency_confirmed':False,'document_coverage_complete':False,'source_fact_ids':'Q01;Q02'})
        self.assertEqual(a['HAUS_REVISION'],'R06');self.assertEqual(a['HAUS_DOKUMENTINHALTE_VOLLSTAENDIG'],'False')
    def test_existing_ten_cross_part_collisions_remain_visible(self):
        self.assertEqual(self.r['numerical_collisions'],10)
    def test_review_mode_has_1165_bodies_not_failed_inserts(self):
        self.assertEqual(self.c['planned_solids'],1165)
    def test_current_report_has_no_reference_integrity_errors(self):
        self.assertFalse(self.r['logical_errors']);self.assertEqual(self.r['status'],'DATEN_KONSISTENTER_ABER_TECHNISCH_UNVOLLSTAENDIG')

if __name__=='__main__':unittest.main()
