"""Independent analytical fixtures; no NX or third party packages required."""
import importlib
import json
import math
import re
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CoreTests(unittest.TestCase):
    def module(self, name):
        try:
            return importlib.import_module('renovierung.k02.' + name)
        except ModuleNotFoundError as exc:
            self.fail('Required pure core is missing: ' + str(exc))

    @staticmethod
    def flat(z=2300):
        return [[[-5000, -5000, z], [7000, -5000, z], [7000, 7000, z]],
                [[-5000, -5000, z], [7000, 7000, z], [-5000, 7000, z]]]

    def field(self, **kw):
        return self.module('geometry').excavation(self.flat(), length=2000, width=800,
                                                   formation=0, **kw)

    def test_flat_field_has_both_end_slopes_and_analytical_volume(self):
        g = self.module('geometry')
        result = self.field()
        self.assertAlmostEqual(result['volume_mm3'] / 1e9, 21.31333333333333, places=8)
        self.assertAlmostEqual(g.mesh_volume(result['mesh']) / 1e9, 21.31333333333333, places=8)
        xs = [p[0] for p in result['mesh']['vertices']]
        ys = [p[1] for p in result['mesh']['vertices']]
        self.assertAlmostEqual(min(xs), -2300)
        self.assertAlmostEqual(max(xs), 4300)
        self.assertAlmostEqual(max(ys), 3100)
        g.validate_mesh(result['mesh'])

    def test_slope_width_and_length_each_change_volume(self):
        g = self.module('geometry')
        for length, width, ratio, want in [(1000, 800, 1, 16.8283333333333),
                                           (2000, 400, 1, 17.3573333333333),
                                           (2000, 800, 2, 55.1693333333333)]:
            r = g.excavation(self.flat(), length=length, width=width, formation=0, ratio=ratio)
            # ratio=2 extends beyond this fixture; use an adequately large ground patch.
            if ratio == 2:
                ground = [[[-10000,-10000,2300],[15000,-10000,2300],[15000,15000,2300]],
                          [[-10000,-10000,2300],[15000,15000,2300],[-10000,15000,2300]]]
                r = g.excavation(ground, length=length,width=width,formation=0,ratio=ratio)
            self.assertAlmostEqual(r['volume_mm3']/1e9, want, places=8)

    def test_affine_thickness_positive_clipping(self):
        g = self.module('geometry')
        tri = [(0,0),(1,0),(0,1)]
        self.assertAlmostEqual(g.integrate_polygon(tri, (1,2,1)), 1.0)
        clipped = g.clip_polygon(tri, (1,0,-0.5))
        self.assertAlmostEqual(g.integrate_polygon(clipped, (1,0,-0.5)), 1/48)

    def test_rotated_translated_field_keeps_volume(self):
        g = self.module('geometry')
        angle=0.3; c=math.cos(angle); s=math.sin(angle)
        ground = [[[p[0]*c-p[1]*s+12000,p[0]*s+p[1]*c-3500,p[2]+650] for p in t]
                  for t in self.flat()]
        r=g.excavation(ground, origin=(12000,-3500), tangent=(c,s), normal=(-s,c),
                       length=2000,width=800,formation=650)
        self.assertAlmostEqual(r['volume_mm3']/1e9,21.3133333333333,places=8)
        g.validate_mesh(r['mesh'])

    def test_no_material_and_nonfinite_geometry(self):
        g=self.module('geometry')
        for z in (0,-100):
            r=g.excavation(self.flat(z),length=2000,width=800,formation=0)
            self.assertEqual(r['volume_mm3'],0)
            self.assertEqual(r['mesh']['faces'],[])
        with self.assertRaises(ValueError):
            g.excavation(self.flat(),length=math.nan,width=800,formation=0)

    def test_outward_clockwise_basis_preserves_positive_orientation(self):
        g=self.module('geometry')
        ground=[[[p[0],-p[1],p[2]] for p in tri] for tri in self.flat()]
        result=g.excavation(ground,length=2000,width=800,formation=0,normal=(0,-1))
        self.assertAlmostEqual(g.mesh_volume(result['mesh'])/1e9,21.3133333333333)
        g.validate_mesh(result['mesh'])

    def test_square_pile_contacts_sloping_ground_and_matches_volume(self):
        g=self.module('geometry')
        ground=[[[-10000,-10000,-2000],[10000,-10000,2000],[10000,10000,2000]],
                [[-10000,-10000,-2000],[10000,10000,2000],[-10000,10000,-2000]]]
        result=g.stockpile(ground,(0,0),10e9,error_mm=10)
        self.assertAlmostEqual(result['volume_mm3']/1e9,10,places=6)
        g.validate_mesh(result['mesh'])
        base=[p for p in result['mesh']['vertices'] if abs(p[2]-.2*p[0])<1e-5]
        self.assertGreater(len(base),4)
        self.assertGreater(abs(min(p[0] for p in base)), max(p[0] for p in base))
        self.assertLess(result['volume_interval_mm3'][0],10e9)
        self.assertGreater(result['volume_interval_mm3'][1],10e9)

    def test_pile_cannot_be_closed_by_cutting_ground_domain(self):
        g=self.module('geometry')
        steep=[[[p[0],p[1],p[0]] for p in tri] for tri in self.flat(0)]
        with self.assertRaises(ValueError):g.stockpile(steep,(0,0),1e9)

    def test_polygon_conflicts_include_end_slopes_and_nonconvex_property(self):
        g=self.module('geometry');foot=self.field()['projection_polygons']
        property_poly=[[-2000,-100],[5000,-100],[5000,4000],[-2000,4000]]
        self.assertGreater(g.outside_area(foot,property_poly),0)
        garage=[[-1500,100],[-1000,100],[-1000,500],[-1500,500]]
        self.assertAlmostEqual(g.overlap_area(foot,[garage]),200000)
        concave=[[-3000,-100],[5000,-100],[5000,4000],[1000,4000],[1000,3500],[-3000,3500]]
        self.assertAlmostEqual(g.outside_area(foot,concave),0,places=4)

    def test_independent_overlapping_fields_do_not_have_net_total(self):
        p=self.module('planning')
        fields=[{'id':'A',**self.field()}, {'id':'B',**self.field()}]
        result=p.independent_states(fields)
        self.assertIsNone(result['net_first_excavation_m3'])
        self.assertFalse(result['cumulative_sequence_available'])
        self.assertGreater(result['overlaps'][0]['projection_overlap_m2'],0)

    def test_overlap_is_independent_of_polygon_ring_orientation(self):
        g=self.module('geometry');foot=self.field()['projection_polygons']
        clockwise=[list(reversed(poly)) for poly in foot]
        self.assertAlmostEqual(g.overlap_area(clockwise,clockwise,convex_b=True)/1e6,20.46)

    def test_catalog_retains_unknown_excluded_and_annex_rows(self):
        p=self.module('planning');t=self.module('terrain')
        catalog=t.read_json(ROOT/'renovierung/planung/2026-11-01/sektionen.json')
        scope=t.read_json(ROOT/'renovierung/planung/2026-11-01/UMFANG_E01.json')
        rows=p.field_register(catalog,scope,2000,800,-2605)
        self.assertEqual({r['sector_id'] for r in rows},{'PS%02d'%i for i in range(1,14)})
        self.assertTrue(all(r['volume_m3'] is None for r in rows))
        self.assertTrue(all('MASK_BOUNDARY_UNKNOWN' in r['blockers'] for r in rows if r['sector_id'] in ('PS02','PS05','PS08')))
        self.assertTrue(all(not r['whole_sector_excluded'] for r in rows if r['sector_id']=='PS02'))
        self.assertTrue(all('UNKNOWN_FORMATION' in r['blockers'] and r['formation_z_mm'] is None for r in rows if r['sector_id'] in ('PS10','PS11','PS12','PS13')))
        self.assertTrue(all(not r['blockers'] for r in rows if r['sector_id']=='PS07'))

    def test_artificial_study_soil_is_closed_and_does_not_move_source(self):
        t=self.module('terrain');g=self.module('geometry');ground=self.flat(2300)
        mesh=t.closed_terrain(ground,-1000)
        self.assertAlmostEqual(g.mesh_volume(mesh),475200000000)
        self.assertEqual(ground[0][0][2],2300)

    def test_plan_reads_sources_once_and_records_unknowns_without_fake_totals(self):
        p=self.module('planning');t=self.module('terrain');g=self.module('geometry')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={
                'catalog.json':{'sectors':[{'id':'PS01','label':'wall','segments':[
                    {'a':[0,0],'b':[2000,0],'outside_normal':[0,-1],'source_wall':'W1'}]},
                    {'id':'PS11','label':'annex','segments':[{'a':[3000,0],'b':[4000,0],
                    'outside_normal':[0,-1],'source_wall':'W2'}]}],
                    'footprints':{'KG':[[0,0],[2000,0],[2000,2000],[0,2000]],
                                  'EG':[[0,-60],[2000,-60],[2000,2000],[0,2000]]}},
                'scope.json':{'provisional_exclusions':[],'scope_needs_survey':[]},
                'height.json':{'anchor_xy_mm':[0,-500],'ground_z_relative_eg_mm':-300,'mode':'PLAN_ANNAHME'},
                'grid.json':{'shape':[21,21],'nodes_mm':[[i*1000,j*1000,2300] for i in range(-10,11) for j in range(-10,11)]},
                'house.json':{'site':{'boundary':{'points_local_mm':[[-9000,-9000],[9000,-9000],[9000,9000],[-9000,9000]]},'routes':[]}}}
            for name,data in files.items():(root/name).write_text(json.dumps(data),encoding='utf-8')
            cfg={'source_paths':{'catalog':'catalog.json','scope':'scope.json','height':'height.json','grid':'grid.json','house':'house.json'},
                 'working_width_mm':800,'max_bottom_length_mm':2000,'main_formation_z_mm':-2605,
                 'terrain_tolerance_mm':25,'pile_candidates_mm':[[5000,-5000]],'pile_patch_radius_mm':4000}
            result=p.create_plan(root,cfg)
            self.assertEqual(result['units'],'mm')
            self.assertEqual(result['height_registration']['translation_mm'],[0,0,-2600])
            self.assertEqual(len(result['provenance']['inputs']),5)
            field=result['fields'][0]
            self.assertIsNotNone(field['volume_m3']);g.validate_mesh(field['mesh'])
            g.validate_mesh(field['study_terrain']['mesh'])
            self.assertFalse(field['construction_release'])
            self.assertTrue(field['native_candidate'])
            self.assertIn('OVERBUILD_PROJECTION_UNRESOLVED',field['overbuild_projection_conflicts'])
            self.assertEqual(field['geometry_conflicts'],[])
            self.assertEqual(result['fields'][1]['volume_m3'],None)
            self.assertIsNone(result['independent_states']['net_first_excavation_m3'])
            json.dumps(result,allow_nan=False)

    def test_plan_marks_property_conflict_without_shrinking_full_field(self):
        p=self.module('planning')
        field=self.field()
        conflicts=p.geometry_conflicts(field['projection_polygons'],
            [[0,-100],[5000,-100],[5000,5000],[0,5000]],
            {'GARAGE':[[-1500,0],[-1000,0],[-1000,500],[-1500,500]]})
        self.assertIn('PROPERTY_BOUNDARY',conflicts)
        self.assertIn('OBSTACLE:GARAGE',conflicts)
        self.assertAlmostEqual(field['volume_mm3']/1e9,21.3133333333333)

    def test_dgm_boundary_does_not_produce_fake_complete_quantity_or_solid(self):
        p=self.module('planning')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            files={
                'catalog':{'sectors':[{'id':'PS01','label':'wall','segments':[{'a':[0,0],'b':[2000,0],
                    'outside_normal':[0,-1],'source_wall':'W'}]}],'footprints':{}},
                'scope':{'provisional_exclusions':[],'scope_needs_survey':[]},
                'height':{'anchor_xy_mm':[0,-500],'ground_z_relative_eg_mm':-300,'mode':'PLAN_ANNAHME'},
                'grid':{'shape':[5,3],'nodes_mm':[[i*1000,j*1000,2300] for i in range(-1,4) for j in range(-1,2)]},
                'house':{'site':{'boundary':{'points_local_mm':[[-9000,-9000],[9000,-9000],[9000,9000],[-9000,9000]]},'routes':[]}}}
            for name,data in files.items():(root/(name+'.json')).write_text(json.dumps(data))
            plan=p.create_plan(root,{'source_paths':{k:k+'.json' for k in files}})
            field=plan['fields'][0]
            self.assertEqual(field['status'],'INCOMPLETE_DGM_DOMAIN')
            self.assertIsNone(field['volume_m3']);self.assertIsNone(field['mesh'])
            self.assertFalse(field['native_candidate'])
            self.assertGreater(field['diagnostic_truncated_volume_m3'],0)

    def test_mesh_validator_rejects_open_and_wrong_orientation(self):
        g=self.module('geometry'); mesh=self.field()['mesh']
        with self.assertRaises(ValueError):
            g.validate_mesh(dict(mesh,faces=mesh['faces'][:-1]))
        faces=[list(f) for f in mesh['faces']];faces[0].reverse()
        with self.assertRaises(ValueError):
            g.validate_mesh(dict(mesh,faces=faces))

    def test_two_separate_cubes_export_two_closed_solids_and_total_volume(self):
        g=self.module('geometry');s=self.module('mesh_step')
        mesh=g.surface_mesh([([(0,0),(10,0),(10,10)],(0,0,0),(0,0,10)),
                             ([(0,0),(10,10),(0,10)],(0,0,0),(0,0,10))]);count=len(mesh['vertices'])
        disconnected={'vertices':mesh['vertices']+[[x+20000,y,z] for x,y,z in mesh['vertices']],
                      'faces':mesh['faces']+[[i+count for i in f] for f in mesh['faces']]}
        info=g.validate_mesh(disconnected)
        self.assertEqual(info['expected_body_count'],2)
        self.assertAlmostEqual(info['volume_mm3'],2000)
        components=g.mesh_components(disconnected)
        self.assertEqual(len(components),2)
        for part in components:self.assertAlmostEqual(g.mesh_volume(part),1000)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'two.step';record=s.write_step(path,disconnected)
            self.assertEqual(record['expected_body_count'],2)
            self.assertEqual(path.read_text().count('FACETED_BREP('),2)
            self.assertEqual(path.read_text().count('CLOSED_SHELL('),2)

    def test_quantized_edge_endpoints_are_always_kept_in_small_sliver(self):
        g=self.module('geometry')
        mesh=g.surface_mesh([
            ([(0,0),(.01,0),(.01,.01)],(0,0,0),(0,0,10)),
            ([(1e-9,1e-9),(.010000001,.010000001),(0,.01)],(0,0,0),(0,0,10))])
        g.validate_mesh(mesh)
        self.assertAlmostEqual(g.mesh_volume(mesh),.001,places=7)

    def test_conforming_triangles_do_not_gain_redundant_centroid_facets(self):
        g=self.module('geometry')
        mesh=g.surface_mesh([([(0,0),(10,0),(10,10)],(0,0,0),(0,0,10)),
                             ([(0,0),(10,10),(0,10)],(0,0,0),(0,0,10))])
        self.assertEqual(len(mesh['faces']),12)
        self.assertEqual(len(mesh['vertices']),8)
        self.assertAlmostEqual(g.mesh_volume(mesh),1000)

    def test_terrain_saddle_refinement_and_volume_band(self):
        t=self.module('terrain'); g=self.module('geometry')
        grid=t.Grid({'shape':[2,2], 'nodes_mm':[[0,0,1000],[0,1000,1000],
                                                   [1000,0,1000],[1000,1000,2000]]})
        for n in (1,2,4):
            triangles=grid.triangles(subdivisions=n)
            integral=sum(g.integrate_polygon([p[:2] for p in tri],g.plane(tri)) for tri in triangles)
            self.assertAlmostEqual(integral/1e9,1.25+1/(12*n*n))
            eps=grid.error_bound(n)
            self.assertLessEqual(abs(integral-1.25e9),eps*1e6+1e-6)
        self.assertEqual(grid.subdivisions(25),4)
        self.assertAlmostEqual(grid.sample((500,500)),1250)
        with self.assertRaises(ValueError):grid.sample((-1,0))

    def test_refined_terrain_produces_closed_field_and_error_band(self):
        t=self.module('terrain');g=self.module('geometry')
        nodes=[[i*1000,j*1000,2300+((i+j)%2)*80] for i in range(-5,8) for j in range(-5,8)]
        grid=t.Grid({'shape':[13,13],'nodes_mm':nodes})
        result=g.excavation(grid.triangles(subdivisions=2),length=2000,width=800,
                            formation=0,error_mm=grid.error_bound(2))
        self.assertLess(result['volume_interval_mm3'][0],result['volume_mm3'])
        self.assertGreater(result['volume_interval_mm3'][1],result['volume_mm3'])
        g.validate_mesh(result['mesh'])

    def test_material_factors_preserve_equivalents_and_show_refill_deficit(self):
        m=self.module('materials')
        r=m.balance(10,10)
        self.assertAlmostEqual(r['stockpiled_loose_m3'],10.5)
        self.assertAlmostEqual(r['compacted_available_m3'],8.9)
        self.assertAlmostEqual(r['loose_needed_m3'],10.5/.89)
        self.assertAlmostEqual(r['import_bank_equivalent_m3'],10/.89-10)
        self.assertEqual(r['remaining_loose_m3'],0)
        self.assertIsNone(r['mass_kg'])
        with self.assertRaises(ValueError):m.balance(-1,10)

    def test_step_fixture_is_closed_mm_faceted_brep(self):
        g=self.module('geometry'); s=self.module('mesh_step')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'field.step'
            meta=s.write_step(path,self.field()['mesh'],'FIELD')
            text=path.read_text(encoding='ascii')
            self.assertIn('FACETED_BREP',text)
            self.assertIn('CLOSED_SHELL',text)
            self.assertIn('SI_UNIT(.MILLI.,.METRE.)',text)
            self.assertEqual(text.count('FACE_SURFACE('),len(self.field()['mesh']['faces']))
            self.assertEqual(text.count('PLANE('),len(self.field()['mesh']['faces']))
            for triple in re.findall(r"CARTESIAN_POINT\('',\(([^)]+)\)\)",text):
                for number in triple.split(','):
                    self.assertRegex(number,r'^[+-]?[0-9]+\.[0-9]*(?:E[+-]?[0-9]+)?$')
            self.assertGreater(path.stat().st_size,500)
            self.assertAlmostEqual(meta['volume_mm3']/1e9,21.3133333333333)
            with self.assertRaises(ValueError):
                s.write_step(path,{'vertices':[[math.nan,0,0]],'faces':[]})


if __name__ == '__main__':
    unittest.main()
