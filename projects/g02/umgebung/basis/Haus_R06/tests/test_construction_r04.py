# -*- coding: utf-8 -*-
"""R04: source traceability, real layer separation, beam math, explicit gaps.
These are NOT structural calculations or tests in a Siemens kernel.
"""
import copy
import contextlib
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_geometry import Parameters,area,convex_intersection
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_construction import layer_polygons,member_readiness,member_solids,source_plausibility
from haus2406_r03.haus_audit import audit_compiled,vertical_record,intersection_volume
from haus2406_r03.haus_profile import validate_compiled_profiles
from haus2406_r03.haus_metadata import object_attributes
from haus2406_r03.haus_run import check_body_bbox,build_solid,_expected_bbox,run_house
from haus2406_r03.haus_nx import NXAdapter
from fake_nx import FakeNX


def member(**updates):
    # Explicit synthetic TEST geometry only. Never copied into the house dataset.
    m={'id':'TEST_SYNTHETISCH','part':'DACH','kind':'SPARREN','system_id':'TEST_KEIN_HAUSBAUTEIL',
       'enabled':True,'start_mm':[0,0,0],'end_mm':[1000,0,1000],
       'section_mm':[80,160],'width_direction':[0,1,0],
       'section_status':'PLANWERT','placement_status':'PLANWERT',
       'source_dimension':[{'document':'SYNTHETISCHER_TEST','page':1,'location':'Testparameter, kein Bauplan'}],
       'source_placement':[{'document':'SYNTHETISCHER_TEST','page':1,'location':'Testachse, kein Istzustand'}]}
    m.update(updates);return m


class ConstructionDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads((BASE/'data/haus.json').read_text());cls.p=Parameters(cls.d['parameters'])
        cls.c=compile_house(cls.d,True);cls.audit=audit_compiled(cls.d,cls.c)
        cls.w={w['id']:w for p in cls.d['parts'] for w in p['walls']}
        cls.wg=cls.w['EG_AW_06']
    def test_wall_inventory_complete(self):
        r=source_plausibility(self.d,self.c);self.assertEqual(len(r['wall_inventory']),120)
        self.assertTrue(all(not x['as_built_verified'] for x in r['wall_inventory']))
    def test_all_load_bearing_classifications_explicitly_unverified(self):
        self.assertTrue(all(w['load_bearing_status'] in ('UNGEKLAERT','NICHT_NACHGEWIESEN') for w in self.w.values()))
    def test_no_false_wood_floor_solid(self):
        self.assertFalse(any(s['parent']=='AN_EG_TRAGDECKE_PROXY' for p in self.c['parts'] for s in p['solids']))
    def test_wrong_glass_opening_removed(self):
        self.assertFalse(any(o['id']=='EG_WINTERGARTEN_OST' for w in self.w.values() for o in w['openings']))
        self.assertEqual(self.wg['openings'],[])
    def test_layer_sum_410_with_void(self):
        layers=layer_polygons(self.wg,self.p)
        self.assertEqual([x['thickness_mm'] for x in layers],[115,40,80,175]);self.assertEqual(sum(x['thickness_mm'] for x in layers),410)
    def test_air_is_not_solid(self):
        solids=[s for p in self.c['parts'] for s in p['solids'] if s['parent']=='EG_AW_06']
        self.assertTrue(solids);self.assertFalse(any(s['meta']['material']=='LUFT' for s in solids))
        void=self.c['construction_audit']['voids'];self.assertTrue(void)
        for s in solids:
            for v in void:
                self.assertLess(abs(area(convex_intersection(s['polygon'],v['polygon']))),.01)
    def test_exterior_edge_stays_fixed(self):
        layers=layer_polygons(self.wg,self.p)
        self.assertAlmostEqual(max(p[0] for p in layers[0]['polygon']),11355)
        self.assertAlmostEqual(min(p[0] for p in layers[-1]['polygon']),10945)
    def test_layers_have_no_double_volumes(self):
        rs=[vertical_record(s,self.p,p['id']) for p in self.c['parts'] for s in p['solids'] if s['parent']=='EG_AW_06']
        for i,a in enumerate(rs):
            for b in rs[i+1:]:self.assertLess(intersection_volume(a,b),.1)
    def test_bad_layer_sum_rejected(self):
        w=copy.deepcopy(self.wg);w['construction_layers'][0]['thickness']=114
        with self.assertRaisesRegex(ValueError,'Gesamtdicke'):layer_polygons(w,self.p)
    def test_ambiguous_sided_wall_rejected(self):
        w=copy.deepcopy(self.wg);w['material_left_fraction']=.5
        with self.assertRaisesRegex(ValueError,'Aussenkante'):layer_polygons(w,self.p)
    def test_duplicate_layers_rejected(self):
        w=copy.deepcopy(self.wg);w['construction_layers'][1]['id']=w['construction_layers'][0]['id']
        with self.assertRaisesRegex(ValueError,'Doppelte'):layer_polygons(w,self.p)
    def test_410_365_conflict_not_silently_resolved(self):
        self.assertTrue(self.c['construction_audit']['source_conflicts'])
        text=json.dumps(self.d['construction']['variant_conflicts']);self.assertIn('365',text);self.assertIn('410',text)
    def test_stairwall_foot_explicit_and_no_floor_overlap(self):
        solids=next(p['solids'] for p in self.c['parts'] if p['id']=='DG');ids={'DG_W_TREPPEN_E','DG_W_TREPPEN_S'}
        walls=[vertical_record(s,self.p,'DG') for s in solids if s['parent'] in ids]
        floors=[vertical_record(s,self.p,'DG') for s in solids if s['parent']=='DG_FUSSBODEN']
        self.assertEqual(min(r['box'][2] for r in walls),self.p.value('OK_DG_ROH'))
        for a in walls:
            for b in floors:self.assertLess(intersection_volume(a,b),.1)
        self.assertTrue(self.c['construction_audit']['junction_operations'])
    def test_no_new_dg_collision(self):
        self.assertFalse(any(r['part_a']=='DG' or r['part_b']=='DG' for r in self.audit['collisions']))
    def test_remaining_collisions_not_hidden(self):
        self.assertEqual(self.audit['collision_count'],10)
        self.assertTrue(all('ANBAU' in r['part_a'] or 'ANBAU' in r['part_b'] for r in self.audit['collisions']))
    def test_mathematical_profiles_and_positive_volumes(self):
        result=validate_compiled_profiles(self.c,self.p);self.assertEqual(result['profile_count'],1165)
        self.assertFalse(self.audit['invalid_solids'])
    def test_pending_members_stay_absent_even_with_estimate_consent(self):
        self.assertEqual(len(self.d['construction']['pending_members']),5)
        self.assertTrue(all(not x['enabled'] for x in self.d['construction']['pending_members']))
        self.assertFalse(any(s['kind']=='TRAGGLIED' for p in self.c['parts'] for s in p['solids']))
    def test_construction_not_declared_complete(self):
        r=source_plausibility(self.d,self.c);self.assertFalse(r['ready_for_roof_alteration_design'])
        self.assertFalse(r['construction']['structural_calculation_provided'])
    def test_ids_and_coverage(self):
        ids=[s['id'] for p in self.c['parts'] for s in p['solids']]
        self.assertEqual(len(ids),len(set(ids)));self.assertEqual(sum(r['planned_solids'] for r in self.c['coverage']),len(ids))
    def test_metadata_preserves_material_layer_and_unknown_load(self):
        w=next(s for p in self.c['parts'] for s in p['solids'] if s['parent']=='EG_AW_06')
        a=object_attributes(w['meta']);self.assertIn('HAUS_SCHICHT',a);self.assertIn('HAUS_KONSTRUKTIONSSTATUS',a)
        self.assertEqual(a['HAUS_TRAGENDE_FUNKTION'],'UNGEKLAERT');self.assertNotIn('MATERIAL',a)


class BeamGeometryTests(unittest.TestCase):
    def volume(self,m):
        s=member_solids(m);p=Parameters({});r=[vertical_record(x,p,'TEST') for x in s]
        for i,a in enumerate(r):
            self.assertGreater(a['volume_mm3'],0)
            for b in r[i+1:]:self.assertLess(intersection_volume(a,b),1.)
        result=sum(x['volume_mm3'] for x in r)
        expected=math.dist(m['start_mm'],m['end_mm'])*math.prod(m['section_mm'])
        self.assertAlmostEqual(result/expected,1,places=8)
        return s
    def test_vertical_beam_normal_section(self):self.volume(member(end_mm=[0,0,1000],width_direction=[1,0,0]))
    def test_horizontal_beam(self):self.volume(member(end_mm=[1000,0,0]))
    def test_45_degree_rafter(self):self.volume(member())
    def test_slanted_and_translated_axis(self):self.volume(member(start_mm=[1100,-2300,2775],end_mm=[4530,3412,5200],width_direction=[1,-1,.2]))
    def test_reversed_axis(self):self.volume(member(start_mm=[1000,0,1000],end_mm=[0,0,0]))
    def test_normalized_width_direction(self):
        a=self.volume(member(width_direction=[0,30,0]));b=self.volume(member())
        self.assertEqual(a,b)
    def test_dormant_unknown_member_yields_no_geometry(self):
        m=member(enabled=False,section_mm=None,end_mm=None);self.assertEqual(member_solids(m),[])
    def test_missing_size_stops_not_standard_size(self):
        with self.assertRaisesRegex(ValueError,'belegte Daten'):member_solids(member(section_mm=None))
    def test_missing_placement_source_stops(self):
        with self.assertRaisesRegex(ValueError,'belegte Daten'):member_solids(member(source_placement=[]))
    def test_guessed_size_stops(self):
        with self.assertRaisesRegex(ValueError,'belegte Daten'):member_solids(member(section_status='GESCHAETZT'))
    def test_parallel_width_direction_rejected(self):
        with self.assertRaisesRegex(ValueError,'parallel'):member_solids(member(width_direction=[1,0,1]))
    def test_zero_axis_rejected(self):
        with self.assertRaises(ValueError):member_solids(member(end_mm=[0,0,0]))
    def test_zero_or_nan_section_rejected(self):
        for x in [0,-1,float('nan'),True]:
            with self.subTest(x=x),self.assertRaises(ValueError):member_solids(member(section_mm=[80,x]))
    def test_incomplete_source_locator_rejected(self):
        with self.assertRaisesRegex(ValueError,'Quelle'):member_solids(member(source_dimension=[{'document':'P13'}]))
    def test_estimation_mode_cannot_override_member_source_requirement(self):
        d=json.loads((BASE/'data/haus.json').read_text());d['construction']['pending_members'][0]['enabled']=True
        with self.assertRaisesRegex(ValueError,'belegte Daten'):compile_house(d,True)


class RuntimeConstructionTests(unittest.TestCase):
    def test_bbox_exact(self):
        r=check_body_bbox('A','B',[0,0,0,1,1,1],[0,0,0,1,1,1]);self.assertEqual(r['status'],'BOX_VERGLEICH_BESTANDEN')
    def test_bbox_error_is_not_count_success(self):
        r=check_body_bbox('A','B',[0,0,0,1,1,1],[0,0,2000,1,1,2001]);self.assertEqual(r['status'],'BOX_ABWEICHUNG')
    def test_bbox_finite_required(self):
        with self.assertRaises(ValueError):check_body_bbox('A','B',[0]*6,[float('nan')]*6)
    def test_beam_through_existing_nx_adapter_simulation(self):
        fake=FakeNX()
        with tempfile.TemporaryDirectory() as td,fake.install():
            nx=NXAdapter(lambda _:None);p=nx.new_part(Path(td)/'TEST_MEMBER.prt','TEST')
            shapes=member_solids(member());params=Parameters({})
            for shape in shapes:
                result=build_solid(nx,p,shape,params);self.assertEqual(len(result),1)
                check=check_body_bbox(shape['id'],'TEST',_expected_bbox(shape,params),nx.bounding_box(result[0]))
                self.assertEqual(check['status'],'BOX_VERGLEICH_BESTANDEN')
            nx.save(p);self.assertTrue(all(b.Layer==1 for b in p.Bodies))
            self.assertTrue(all(curve.blanked for curve in nx.profile_curves[p.Tag]))
    def test_full_run_writes_each_bbox_and_construction_limits(self):
        fake=FakeNX()
        with tempfile.TemporaryDirectory() as td,fake.install(),contextlib.redirect_stdout(io.StringIO()):
            b=Path(td)
            for name in ('data','src'):shutil.copytree(BASE/name,b/name,ignore=shutil.ignore_patterns('__pycache__'))
            state=run_house(b);out=Path(state['output_directory'])
            rows=json.loads((out/'koerper_boxpruefung.json').read_text())
            self.assertEqual(len(rows),1165);self.assertTrue(all(r['status']=='BOX_VERGLEICH_BESTANDEN' for r in rows))
            self.assertFalse(state['construction_complete']);self.assertFalse(state['as_built_verified']);self.assertFalse(state['structural_design_verified'])
            self.assertEqual(state['body_box_check_count'],1165);self.assertTrue((out/'konstruktionspruefung.json').is_file())
            self.assertTrue(state['display_object_setup'])
            self.assertTrue(all(body.Layer==1 for part in fake.session.Parts for body in part.Bodies))

if __name__=='__main__':unittest.main()
