# -*- coding: utf-8 -*-
import copy
import json
import math
import sys
import unittest
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_geometry import (Parameters,area,clean,convex_intersection,convex_difference,
    triangulate,rectangle,affine_source,remove_overlaps,transformed,validate,enabled,wall_polygon)
from haus2406_r03.haus_compile import compile_house,split_openings,wall_intervals
from haus2406_r03.haus_roof import scalar_clip,plane_for,height,upper_envelope,compile_roofs


def parameters(**values):
    return Parameters({k:{'value':v,'unit':'mm','status':'PLANWERT'} for k,v in values.items()})


class GeometryTests(unittest.TestCase):
    def test_area(self):self.assertEqual(area([[0,0],[10,0],[10,20],[0,20]]),200)
    def test_clean_orientation(self):self.assertGreater(area(clean([[0,0],[0,20],[10,20],[10,0],[0,0]])),0)
    def test_rectangle_width(self):self.assertAlmostEqual(area(rectangle([0,0],[1000,0],240)),240000)
    def test_wall_outside_edge(self):
        poly=rectangle([0,0],[1000,0],240,1)
        self.assertEqual(min(p[1] for p in poly),0)
        self.assertEqual(max(p[1] for p in poly),240)
    def test_degenerate_wall(self):
        with self.assertRaises(ValueError):rectangle([0,0],[0,0],240)
    def test_intersection_area(self):
        a=[[0,0],[10,0],[10,10],[0,10]];b=[[5,5],[15,5],[15,15],[5,15]]
        self.assertAlmostEqual(area(convex_intersection(a,b)),25)
    def test_difference_area(self):
        a=[[0,0],[10,0],[10,10],[0,10]];b=[[5,5],[15,5],[15,15],[5,15]]
        self.assertAlmostEqual(sum(area(p) for p in convex_difference(a,b)),75)
    def test_difference_disjoint(self):
        a=[[0,0],[10,0],[10,10],[0,10]];b=[[2,2],[8,2],[8,8],[2,8]]
        pieces=convex_difference(a,b)
        for i,p in enumerate(pieces):
            for q in pieces[i+1:]:self.assertLess(abs(area(convex_intersection(p,q))),1e-6)
    def test_concave_triangulation(self):
        p=[[0,0],[10,0],[10,4],[4,4],[4,10],[0,10]]
        self.assertAlmostEqual(sum(area(t) for t in triangulate(p)),64)
    def test_rotation(self):
        x,y=transformed([100,0],[20,30],90)
        self.assertAlmostEqual(x,20);self.assertAlmostEqual(y,130)
    def test_affine(self):
        cal={'pixels':[[10,90],[110,90],[10,10]],'dimensions_mm':[1000,800]}
        self.assertEqual(affine_source([60,50],cal),[500,400])
    def test_affine_degenerate(self):
        with self.assertRaises(ValueError):affine_source([0,0],{'pixels':[[0,0],[1,0],[2,0]],'dimensions_mm':[1,1]})
    def test_expression_math(self):self.assertEqual(parameters(Z_DG=2870).number('Z_DG-60-160'),2650)
    def test_expression_injection(self):
        with self.assertRaises(ValueError):parameters().number('__import__("os").system("echo bad")')
    def test_expression_attribute(self):
        with self.assertRaises(ValueError):parameters().number('(1).__class__')
    def test_expression_unknown(self):
        with self.assertRaises(ValueError):parameters().number('MISSING+1')
    def test_expression_missing_not_zero(self):
        with self.assertRaises(ValueError):parameters(X=None).value('X')
    def test_expression_cycle(self):
        p=Parameters({'X':{'formula':'Y','status':'ABGELEITET'},'Y':{'formula':'X','status':'ABGELEITET'}})
        with self.assertRaises(ValueError):p.value('X')
    def test_nonfinite(self):
        with self.assertRaises(ValueError):parameters(X=float('inf')).value('X')
    def test_uncertainty_propagates(self):
        p=Parameters({'A':{'value':100,'status':'GESCHAETZT'},'B':{'formula':'A+2','status':'ABGELEITET'}})
        self.assertIn('A',p.uncertain('B'))
        self.assertFalse(enabled({'status':'ABGELEITET','height':'B'},p)[0])
    def test_no_estimates_by_default(self):self.assertFalse(enabled({'status':'GESCHAETZT'},parameters())[0])
    def test_roof_plane(self):
        p=plane_for([[0,0,100],[100,0,200],[100,100,200]])
        self.assertAlmostEqual(height({'plane':p},[50,50]),150)
    def test_scalar_clipping(self):
        p=scalar_clip([[0,0],[10,0],[10,10],[0,10]],1,0,-5)
        self.assertAlmostEqual(area(p),50)
    def test_upper_envelope(self):
        faces=[{'id':'A','polygon':[[0,0],[10,0],[10,10],[0,10]],'plane':[1,0,0]},
               {'id':'B','polygon':[[0,0],[10,0],[10,10],[0,10]],'plane':[-1,0,10]}]
        out=upper_envelope(faces)
        self.assertAlmostEqual(sum(area(p['polygon']) for p in out),100)
        self.assertEqual(len(out),2)
    def test_opening_volume(self):
        p=parameters();w={'a':[0,0],'b':[3000,0],'thickness':240,'bottom':0,'top':2650,
          'openings':[{'id':'D','offset':1000,'width':1000,'sill':0,'height':2010,'status':'PLANWERT'}]}
        volume=0
        for poly,opens in split_openings(wall_polygon(w,p),w,p,False):
            for lo,hi in wall_intervals(w,opens,p):volume+=area(poly)*(p.number(hi)-p.number(lo))
        self.assertAlmostEqual(volume,3000*240*2650-1000*240*2010)


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((BASE/'data'/'haus.json').read_text(encoding='utf-8'))
        cls.params=Parameters(cls.data['parameters']);cls.compiled=compile_house(cls.data,True)
    def test_source_data_valid(self):self.assertEqual(validate(self.data)['errors'],[])
    def test_wrong_units_rejected(self):
        d=copy.deepcopy(self.data);d['units']='m';self.assertTrue(validate(d)['errors'])
    def test_duplicate_id_rejected(self):
        d=copy.deepcopy(self.data);d['parts'][1]['walls'].append(d['parts'][1]['walls'][0]);self.assertTrue(validate(d)['errors'])
    def test_opening_outside_rejected(self):
        d=copy.deepcopy(self.data)
        w=next(w for p in d['parts'] for w in p['walls'] if w.get('openings'))
        w['openings'][0]['offset']=1e8;self.assertTrue(validate(d)['errors'])
    def test_strict_no_unconfirmed_solids(self):self.assertEqual(compile_house(self.data,False)['planned_solids'],0)
    def test_counts(self):
        self.assertEqual(sum(len(p['walls']) for p in self.data['parts']),120)
        self.assertEqual(sum(len(w['openings']) for p in self.data['parts'] for w in p['walls']),79)
    def test_level_corrections(self):
        self.assertEqual(self.params.value('Z_DG'),2870)
        self.assertEqual(self.params.value('Z_KG'),-2325)
        self.assertEqual(self.params.value('UK_DG_DECKE'),2650)
        self.assertEqual(self.params.value('UK_EG_DECKE'),-220)
    def test_partnames_unique(self):
        names=[p['file'] for p in self.data['parts']];self.assertEqual(len(names),len(set(names)))
        self.assertTrue(all('/' not in n and '\\' not in n for n in names))
    def test_planned_shapes_positive(self):
        for part in self.compiled['parts']:
            for s in part['solids']:
                if 'polygon' in s:
                    self.assertGreater(area(s['polygon']),0)
                    self.assertGreater(self.params.number(s['top']),self.params.number(s['bottom']))
                    triangulate(s['polygon'])
    def test_roof_projections_nonoverlapping(self):
        faces=self.compiled['roof_faces']
        for i,f in enumerate(faces):
            for g in faces[i+1:]:self.assertLess(abs(area(convex_intersection(f['polygon'],g['polygon']))),0.1)
    def test_no_double_floor_offset(self):
        kg=next(p for p in self.compiled['parts'] if p['id']=='KG')
        self.assertTrue(any(self.params.number(s['bottom'])==-2325 for s in kg['solids'] if s['kind']=='WAND'))
    def test_roof_wall_remaining_height(self):
        for part in self.compiled['parts']:
            for s in part['solids']:
                if s.get('roof_clip'):
                    low=self.params.number(s['bottom']);t=self.params.value('DACH_HUELLE_PROXY')
                    self.assertGreaterEqual(min(height(s['roof_clip'],p)-t-low for p in s['polygon']),0.099)
    def test_compiler_deterministic(self):
        a=json.dumps(self.compiled,sort_keys=True)
        b=json.dumps(compile_house(self.data,True),sort_keys=True)
        self.assertEqual(a,b)


if __name__=='__main__':unittest.main(verbosity=2)
