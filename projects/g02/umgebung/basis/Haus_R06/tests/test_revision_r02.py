# -*- coding: utf-8 -*-
"""R02 numerical/data regression tests; no NX execution is simulated as success."""
import ast
import copy
import json
import math
import sys
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_geometry import Parameters,area,convex_intersection,validate
from haus2406_r03.haus_audit import (intersection_volume,subtract_vertical,integrate,vertical_record,audit_compiled)
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_quality import sanitize_polygon,PROFILE_TOLERANCE_MM
from haus2406_r03.haus_details import inserts_for
from haus2406_r03.haus_preview import mesh_for


def box(x0=0,x1=10,y0=0,y1=10,z0=0,z1=10):
    return {'polygon':[[x0,y0],[x1,y0],[x1,y1],[x0,y1]],'lo':[0,0,z0],'hi':[0,0,z1]}

def volume(r):return integrate(r['polygon'],[r['hi'][i]-r['lo'][i] for i in range(3)])


class NumericalAuditTests(unittest.TestCase):
    def test_empty_clip_is_empty(self):self.assertEqual(convex_intersection(box()['polygon'],[]),[])
    def test_identical_cubes(self):self.assertAlmostEqual(intersection_volume(box(),box()),1000)
    def test_touching_no_volume(self):self.assertEqual(intersection_volume(box(),box(x0=10,x1=20)),0)
    def test_disjoint_vertical(self):self.assertEqual(intersection_volume(box(),box(z0=20,z1=30)),0)
    def test_half_cube_overlap(self):self.assertAlmostEqual(intersection_volume(box(),box(x0=5,x1=15)),500)
    def test_overlapping_wedges(self):
        a=box();b=box();a['hi']=[1,0,0];b['hi']=[-1,0,10]
        self.assertAlmostEqual(intersection_volume(a,b),250)
    def test_lower_plane_max(self):
        a=box();b=box();a['lo']=[1,0,0];b['lo']=[-1,0,10]
        self.assertAlmostEqual(intersection_volume(a,b),250)
    def test_symmetry(self):
        a=box();b=box(x0=2,x1=12,z0=3,z1=8);a['hi']=[.5,0,7]
        self.assertAlmostEqual(intersection_volume(a,b),intersection_volume(b,a))
    def test_subtract_internal_cube(self):
        a=box(0,100,0,100,0,100);b=box(25,75,25,75,25,75)
        self.assertAlmostEqual(sum(volume(r) for r in subtract_vertical(a,b)),875000)
    def test_subtract_disjoint_keeps_subject(self):self.assertAlmostEqual(sum(volume(r) for r in subtract_vertical(box(),box(z0=20,z1=30))),1000)
    def test_subtract_identical_empty(self):self.assertEqual(subtract_vertical(box(),box()),[])
    def test_subtract_conserves_sloped_volume(self):
        a=box(0,100,0,100,0,200);b=box(20,80,0,100,0,200);b['lo']=[.5,0,20];b['hi']=[1,0,50]
        self.assertAlmostEqual(sum(volume(r) for r in subtract_vertical(a,b))+intersection_volume(a,b),volume(a),places=3)
    def test_subtraction_fragments_disjoint(self):
        a=box(0,100,0,100,0,200);b=box(20,80,0,100,0,200);b['lo']=[.5,0,20];b['hi']=[1,0,50]
        rs=subtract_vertical(a,b)
        for i,r in enumerate(rs):
            for q in rs[i+1:]:self.assertAlmostEqual(intersection_volume(r,q),0,places=3)
    def test_sanitize_short_vertex(self):
        poly,change=sanitize_polygon([[0,0],[.001,0],[100,0],[100,100],[0,100]])
        self.assertEqual(len(poly),4);self.assertEqual(area(poly),10000)
    def test_sanitize_preserves_actual_detail(self):
        poly,change=sanitize_polygon([[0,0],[100,0],[100,100],[60,100],[60,90],[40,90],[40,100],[0,100]])
        self.assertEqual(len(poly),8);self.assertEqual(change['removed_vertices'],0)
    def test_sanitize_tiny_triangle_rejected(self):
        with self.assertRaises(ValueError):sanitize_polygon([[0,0],[.001,0],[0,.001]])


class RevisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((BASE/'data/haus.json').read_text(encoding='utf-8'))
        cls.params=Parameters(cls.data['parameters']);cls.compiled=compile_house(cls.data,True)
        cls.audit=audit_compiled(cls.data,cls.compiled)
        cls.solids=[s for p in cls.compiled['parts'] for s in p['solids']]
    def test_revision(self):self.assertEqual(self.data['revision'],'R06')
    def test_plan_register(self):
        docs=json.loads((BASE/'data/planregister.json').read_text(encoding='utf-8'))
        self.assertEqual(len(docs),31)
        self.assertEqual(sum(self.data['source_document_pages'].values()),92)
    def test_corrected_keller_chain(self):self.assertEqual(self.params.value('KG_NORDBREITE'),365+2480+115+4605+365)
    def test_corrected_keller_divider(self):
        w=next(w for p in self.data['parts'] for w in p['walls'] if w['id']=='KG_IW_N_TRENN')
        self.assertEqual(w['a'][0],2902.5);self.assertEqual(w['b'][0],2902.5)
    def test_wintergarden_not_assigned_to_east(self):
        m=next(m for m in self.data['material_assemblies'] if m['id']=='WINTERGARTEN_SUED_P21')
        self.assertEqual(m['assigned_wall'],'EG_AW_06');self.assertEqual(sum(s['thickness_mm'] for s in m['layers_inside_out']),410)
    def test_eight_labelled_dormer_windows(self):
        o=[o for p in self.data['parts'] for w in p['walls'] for o in w['openings'] if o['id'].startswith('DG_F_GAUBE_')]
        self.assertEqual(len(o),8)
        for x in o:self.assertEqual((x['width'],x['height']),(1500,1500));self.assertEqual(x['status'],'GESCHAETZT')
    def test_annex_floor_thicknesses(self):
        p=next(p for p in self.data['parts'] if p['id']=='ANBAU_EG')
        for ident in ('AN_EG_TRITTSCHALL','AN_EG_ESTRICH'):
            sl=next(s for s in p['slabs'] if s['id']==ident)
            self.assertEqual(self.params.number(sl['top'])-self.params.number(sl['bottom']),40)
    def test_77_insert_sets(self):self.assertEqual(self.compiled['detail_counts']['opening_inserts'],77)
    def test_488_insert_solids(self):self.assertEqual(self.compiled['detail_counts']['window_door_solids'],488)
    def test_blocked_insert_explicit(self):
        cov=next(c for c in self.compiled['coverage'] if c['id']=='KG_T_A_FLUR_BAD_1_EINBAUTEIL')
        self.assertEqual(cov['status'],'GESPERRT_OEFFNUNG_BLOCKIERT');self.assertEqual(cov['planned_solids'],0)
    def test_no_bad_solids(self):self.assertEqual(self.audit['invalid_solids'],[])
    def test_remaining_collisions_are_not_details(self):
        self.assertGreater(self.audit['collision_count'],0)
        for c in self.audit['collisions']:
            self.assertIn(c['kind_a'],('WAND','DECKE'));self.assertIn(c['kind_b'],('WAND','DECKE'))
            self.assertNotEqual(c['part_a'],c['part_b'])
    def test_coverage_sum_matches_solids(self):self.assertEqual(sum(c['planned_solids'] for c in self.compiled['coverage']),len(self.solids))
    def test_unique_compiled_ids(self):self.assertEqual(len(self.solids),len({s['id'] for s in self.solids}))
    def test_all_profile_edges_above_tolerance(self):
        for s in self.solids:
            points=s.get('polygon',s.get('points'))
            for a,b in zip(points,points[1:]+points[:1]):self.assertGreaterEqual(math.dist(a,b),PROFILE_TOLERANCE_MM,s['id'])
    def test_slivers_recorded(self):self.assertEqual(len(self.compiled['profile_audit']['discarded_numerical_slivers']),7)
    def test_preview_finite_and_closed_prisms(self):
        for s in self.solids:
            faces=mesh_for(s,self.params)
            self.assertGreaterEqual(len(faces),5)
            self.assertTrue(all(math.isfinite(v) for f in faces for q in f for v in q))
    def test_review_required(self):
        settings=json.loads((BASE/'data/einstellungen.json').read_text(encoding='utf-8'))
        self.assertFalse(settings['allow_estimates']);self.assertTrue(settings['show_review_consent'])
    def test_details_can_be_disabled(self):
        d=copy.deepcopy(self.data);d['detail_options']['opening_inserts']=False;d['detail_options']['dormer_cheeks']=False
        c=compile_house(d,True)
        self.assertFalse(any(s['kind'] in ('GLAS','TUERBLATT','GAUBENWANGE') for p in c['parts'] for s in p['solids']))
    def test_roof_parameter_changes_geometry(self):
        d=copy.deepcopy(self.data);d['parameters']['DACH_MAIN_WINKEL']['value']=40
        c=compile_house(d,True)
        self.assertNotEqual(c['roof_faces'],self.compiled['roof_faces'])
    def test_opening_kind_missing_rejected(self):
        d=copy.deepcopy(self.data);o=next(o for p in d['parts'] for w in p['walls'] for o in w['openings']);o['kind']='OTHER'
        self.assertTrue(validate(d)['errors'])
    def test_opening_source_missing_rejected(self):
        d=copy.deepcopy(self.data);o=next(o for p in d['parts'] for w in p['walls'] for o in w['openings']);o['sources']=[]
        self.assertTrue(validate(d)['errors'])
    def test_negative_visual_dimension_rejected(self):
        d=copy.deepcopy(self.data);d['visual_defaults']['frame_face_mm']=-1;self.assertTrue(validate(d)['errors'])
    def test_degenerate_roof_rejected(self):
        d=copy.deepcopy(self.data);d['roof_definitions'][0]['rect']=[0,0,0,10];self.assertTrue(validate(d)['errors'])
    def test_roof_ninety_degrees_rejected(self):
        d=copy.deepcopy(self.data);d['roof_definitions'][0]['pitch']=90;self.assertTrue(validate(d)['errors'])
    def test_duplicate_part_id_rejected(self):
        d=copy.deepcopy(self.data);d['parts'][1]['id']=d['parts'][0]['id'];self.assertTrue(validate(d)['errors'])
    def test_python38_syntax(self):
        for f in BASE.rglob('*.py'):ast.parse(f.read_text(encoding='utf-8'),filename=str(f),feature_version=(3,8))
    def test_window_generic_parts_nonoverlap(self):
        w={'id':'W','a':[0,0],'b':[3000,0],'thickness':365,'bottom':0}
        o={'id':'O','kind':'FENSTER','offset':750,'width':1500,'height':1500,'sill':800,'sources':[]}
        ss=inserts_for(w,o,self.params,self.data['visual_defaults']);self.assertEqual(len(ss),9)
        rec=[vertical_record(s,self.params,'T') for s in ss]
        for i,a in enumerate(rec):
            for b in rec[i+1:]:self.assertAlmostEqual(intersection_volume(a,b),0,places=3)

if __name__=='__main__':unittest.main(verbosity=2)
