"""Analytical/real-source annex display geometry, never a construction release."""
import copy
import importlib
import math
from pathlib import Path
import unittest

from renovierung.k02 import geometry as geom

ROOT=Path(__file__).resolve().parents[2]


class SoilTests(unittest.TestCase):
    def setUp(self):
        self.module=importlib.import_module('renovierung.anbau.geometry')
        self.triangles=[[[-5000,-5000,2300],[7000,-5000,2300],[7000,7000,2300]],
                        [[-5000,-5000,2300],[7000,7000,2300],[-5000,7000,2300]]]
        self.field={'origin_mm':[0,0],'tangent':[1,0],'normal':[0,1],
                    'length_mm':2000,'width_mm':800,'formation_z_mm':0}

    def test_cut_soil_exactly_removes_analytical_field_with_closed_nonoverlapping_halves(self):
        soils=self.module.soil_meshes(self.triangles,self.field,-1000)
        source=geom.validate_mesh(soils['soil']);cut=geom.validate_mesh(soils['cut_soil'])
        self.assertEqual(source['expected_body_count'],2)
        self.assertEqual(cut['expected_body_count'],2)
        self.assertAlmostEqual(source['volume_mm3']/1e9,475.2)
        self.assertAlmostEqual((source['volume_mm3']-cut['volume_mm3'])/1e9,21.31333333333333)
        self.assertAlmostEqual(sorted(cut['component_volumes_mm3'])[0]/1e9,198)

    def test_rotated_clockwise_basis_and_sloping_surface_preserve_volume_subtraction(self):
        angle=.3;c=math.cos(angle);s=math.sin(angle)
        triangles=[[[p[0]*c+p[1]*s+15000,p[0]*s-p[1]*c-7000,p[2]+p[0]*.01] for p in tri] for tri in self.triangles]
        field=dict(self.field,origin_mm=[15000,-7000],tangent=[c,s],normal=[s,-c])
        soils=self.module.soil_meshes(triangles,field,-1000)
        excavation=geom.excavation(triangles,2000,800,0,1,field['origin_mm'],field['tangent'],field['normal'])
        actual=geom.mesh_volume(soils['soil'])-geom.mesh_volume(soils['cut_soil'])
        self.assertAlmostEqual(actual/1e9,excavation['volume_mm3']/1e9,places=8)

    def test_modifiable_slab_display_assumption_and_invalid_depth_are_explicit(self):
        base=self.module.read_assumptions(ROOT)
        changed=self.module.read_assumptions(ROOT,{'assumed_slab_underside_z_mm':-1400})
        self.assertEqual(base['formation_z_mm'],-1600)
        self.assertEqual(changed['formation_z_mm'],-1500)
        self.assertFalse(base['construction_release'])
        for value in (None,math.nan,True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.module.read_assumptions(ROOT,{'assumed_slab_underside_z_mm':value})


class RealPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=importlib.import_module('renovierung.anbau.geometry')
        cls.plan=cls.module.create_plan(ROOT)

    def test_real_existing_24_ids_preserved_and_unknown_interface_not_invented(self):
        fields=self.plan['fields']
        self.assertEqual(len(fields),24)
        self.assertEqual({s:sum(f['sector_id']==s for f in fields) for s in ('PS10','PS11','PS12','PS13')},
                         {'PS10':5,'PS11':7,'PS12':5,'PS13':7})
        for field in fields:
            self.assertEqual(field['formation_z_mm'],-1600)
            self.assertEqual(field['assumed_slab_underside_z_mm'],-1500)
            self.assertLessEqual(field['length_mm'],2000)
            self.assertEqual(field['width_mm'],800)
            self.assertFalse(field['construction_release'])
            self.assertIsNotNone(field['geometry']['excavation']['mesh'])
            if field['sector_id']=='PS10':
                self.assertIn('INTERFACE_UNRESOLVED',field['blockers'])
                self.assertFalse(field['native_candidate'])
                self.assertIsNone(field['volume_m3'])
        self.assertFalse(self.plan['construction_release'])

    def test_free_candidates_have_mesh_measured_roles_and_safe_new_site_piles(self):
        candidates=[f for f in self.plan['fields'] if f['native_candidate']]
        self.assertEqual([f['id'] for f in candidates],
                         ['PS11-F01','PS11-F04','PS11-F05']+
                         ['PS12-F%02d'%i for i in range(1,6)]+['PS13-F%02d'%i for i in range(1,6)])
        for field in candidates:
            self.assertEqual(set(field['measurements']),{'excavation','cut_soil','pile_main','pile_reserve'})
            for role,measurement in field['measurements'].items():
                measured=geom.validate_mesh(field['geometry'][role]['mesh'])
                self.assertEqual(measurement['body_count'],measured['expected_body_count'])
                self.assertEqual(measurement['component_volumes_m3'],sorted(v/1e9 for v in measured['component_volumes_mm3']))
            self.assertAlmostEqual(field['volume_m3'],field['measurements']['excavation']['volume_m3'])
            for role,factor in (('pile_main',1.05),('pile_reserve',1.25)):
                pile=field['display_stockpile'][role]
                self.assertEqual(pile['center_xy_mm'],[14500,-9500])
                self.assertAlmostEqual(pile['target_volume_m3'],field['volume_m3']*factor)
                self.assertGreaterEqual(pile['clearances_mm']['excavation'],600)
                self.assertGreater(min(pile['clearances_mm'].values()),0)

    def test_conflicts_keep_complete_red_mesh_but_no_effective_quantity_or_pile(self):
        byid={f['id']:f for f in self.plan['fields']}
        for fid in ('PS10-F01','PS10-F05','PS13-F06','PS13-F07'):
            field=byid[fid]
            self.assertIn('BUILDING',field['status'])
            self.assertFalse(field['native_candidate'])
            self.assertTrue(field['diagnostic_only'])
            self.assertIsNone(field['volume_m3'])
            self.assertEqual(field['measurements'],{})
            self.assertFalse(field['display_stockpile'])
            self.assertGreater(field['diagnostic_volume_m3'],0)
        self.assertFalse(byid['PS11-F07']['native_candidate'])
        self.assertFalse(byid['PS11-F06']['native_candidate'])
        edge=next(c for c in byid['PS11-F06']['conflicts'] if c['kind']=='PROPERTY_BOUNDARY')
        self.assertAlmostEqual(edge['nominal_outside_m2'],0,places=9)
        self.assertAlmostEqual(edge['upper_error_outside_m2'],0.016796632999420167,places=9)
        for fid in ('PS11-F02','PS11-F03'):
            self.assertIn('ACCESS_PROTECTION_UNRESOLVED',byid[fid]['blockers'])

    def test_warm_light_api_is_independent_and_carries_no_meshes(self):
        light=self.module.create_plan(ROOT,include_mesh=False)
        self.assertEqual([f['id'] for f in light['fields']],[f['id'] for f in self.plan['fields']])
        for field in light['fields']:
            self.assertTrue(all('mesh' not in g for g in field['geometry'].values()))
        light['fields'][0]['blockers'].append('MUTATED')
        self.assertNotIn('MUTATED',self.module.create_plan(ROOT,include_mesh=False)['fields'][0]['blockers'])

    def test_compact_catalog_preserves_status_and_hashes_without_large_geometry(self):
        import hashlib
        import json
        catalog=self.module.compact_catalog(self.plan)
        self.assertLess(len(json.dumps(catalog)),100000)
        self.assertNotIn('"mesh"',json.dumps(catalog))
        self.assertNotIn('contact_polygons',json.dumps(catalog))
        self.assertEqual(catalog['native_candidate_ids'],self.plan['native_candidate_ids'])
        for path,expected in self.plan['provenance']['source_and_generator_hashes'].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected)


if __name__=='__main__':unittest.main()
