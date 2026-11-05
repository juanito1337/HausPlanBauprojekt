"""Shared-ground mathematics and transfer contracts; no NX-success simulation."""
import copy
import importlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from renovierung.k02 import geometry as geom
from renovierung.k02.terrain import Grid, closed_terrain


def fixture():
    grid = Grid({'shape':[7,7], 'nodes_mm':[[i*1000,j*1000,300] for i in range(7) for j in range(7)]})
    registration = {'translation_mm':[0,0,-100], 'mode':'PLAN_ANNAHME', 'applied_once_to_source_grid':True}
    terrain = {'grid':grid, 'TIN_subdivisions':4, 'max_vertical_error_mm':0,
               'boundary_xy_mm':[[0,0],[6000,0],[6000,6000],[0,6000]],
               'height_registration':registration, 'source_hashes':{'synthetic_grid':'synthetic-only'}}
    fields = []
    for fid, box, bounds in [('PS11-F01',[1000,1000,3000,3000],[1,3,1,3]),
                              ('PS12-F01',[2000,2000,4000,4000],[2,4,2,4])]:
        fields.append({'id':fid, 'native_candidate':True,
                       'study_terrain':{'crop_bbox_xy_mm':box,'uv_cell_bounds':bounds,
                                        'TIN_subdivisions':4,'max_vertical_error_mm':0,
                                        'reference_translation_mm':[0,0,-100]},
                       'geometry':{'cut_soil':{'mesh':closed_terrain(grid.triangles(4,box),-1000)}}})
    fields.append({'id':'PS10-F01','native_candidate':False})
    return terrain, fields


class SharedSiteTests(unittest.TestCase):
    def setUp(self):
        try:
            self.site = importlib.import_module('renovierung.anbau.site')
        except ModuleNotFoundError:
            self.fail('The annex shared-ground module is missing')
        self.terrain, self.fields = fixture()

    def create(self, mesh=True):
        return self.site.create_site_context(self.terrain,self.fields,include_mesh=mesh)

    def test_one_shared_part_covers_property_once_and_each_state_excludes_only_its_crop(self):
        result = self.create()
        self.assertEqual(result['file'],'ANBAU_SITE.prt')
        self.assertEqual(result['area_m2'],36)
        self.assertAlmostEqual(result['volume_m3'],7.2)
        self.assertEqual(set(result['reference_sets']),{'PS11-F01','PS12-F01'})
        for fid in ('PS11-F01','PS12-F01'):
            selected=result['reference_sets'][fid]
            self.assertEqual(selected['area_m2'],32)
            self.assertEqual(selected['body_count'],len(selected['shell_ids']))
            byid={s['id']:s for s in result['shells']}
            self.assertTrue(all(fid not in byid[s]['exclude_for'] for s in selected['shell_ids']))
            self.assertAlmostEqual(selected['volume_m3'],6.4)
        measured=geom.validate_mesh(result['mesh'])
        self.assertEqual(measured['expected_body_count'],len(result['shells']))
        self.assertAlmostEqual(measured['volume_mm3']/1e9,7.2)
        self.assertTrue(all(100-1e-8<=p[2]<=300+1e-8 for p in result['mesh']['vertices']))
        self.assertFalse(result['construction_release'])

    def test_concave_property_is_clipped_without_removing_the_whole_context(self):
        self.terrain['boundary_xy_mm']=[[0,0],[6000,0],[6000,3500],[3500,3500],[3500,6000],[0,6000]]
        result=self.create()
        self.assertEqual(result['area_m2'],29.75)
        self.assertEqual(result['reference_sets']['PS11-F01']['area_m2'],25.75)
        self.assertEqual(result['reference_sets']['PS12-F01']['area_m2'],26)

    def test_point_touching_mask_shells_fail_closed_in_the_unchanged_partition_helper(self):
        # This puts B-only top-left and bottom-right pieces in contact at one
        # vertical edge. The inherited helper refuses that nonmanifold weld.
        self.terrain['boundary_xy_mm']=[[0,0],[6000,0],[6000,3000],[3000,3000],[3000,6000],[0,6000]]
        with self.assertRaises(ValueError):self.create()

    def test_already_registered_heights_are_not_transformed_again_and_results_are_independent(self):
        original=self.create()
        self.fields.reverse()
        self.assertEqual(original,self.create())
        self.terrain['grid']=Grid({'shape':[7,7],'nodes_mm':[[i*1000,j*1000,800] for i in range(7) for j in range(7)]})
        self.terrain['height_registration']['translation_mm'][2]=400
        for field in self.fields:
            if field['native_candidate']:
                field['study_terrain']['reference_translation_mm'][2]=400
                for p in field['geometry']['cut_soil']['mesh']['vertices']:p[2]+=500
        shifted=self.create()
        self.assertEqual([p[2]+500 for p in original['mesh']['vertices']],[p[2] for p in shifted['mesh']['vertices']])
        self.assertEqual(original['volume_m3'],shifted['volume_m3'])
        shifted['groups'][0]['exclude_for'].append('MUTATED')
        self.assertNotIn('MUTATED',self.create()['groups'][0]['exclude_for'])

    def test_stale_uv_crop_height_or_actual_cut_soil_domain_are_rejected(self):
        for change in ('bounds','subdivisions','height','mesh_domain','missing_mesh'):
            with self.subTest(change=change):
                fields=copy.deepcopy(self.fields)
                field=fields[0]
                if change=='bounds':field['study_terrain']['uv_cell_bounds']=[0,3,1,3]
                elif change=='subdivisions':field['study_terrain']['TIN_subdivisions']=2
                elif change=='height':field['study_terrain']['reference_translation_mm']=[0,0,0]
                elif change=='mesh_domain':
                    for p in field['geometry']['cut_soil']['mesh']['vertices']:p[0]+=1000
                else:field['geometry']['cut_soil'].pop('mesh')
                with self.assertRaises(ValueError):
                    self.site.create_site_context(self.terrain,fields)

    def test_step_has_all_independent_closed_shells_in_one_ap214(self):
        result=self.create()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ONE_SITE.step'
            report=self.site.write_site_step(path,result)
            data=path.read_text()
            self.assertIn("FILE_SCHEMA(('AUTOMOTIVE_DESIGN'))",data)
            self.assertEqual(data.count('=FACETED_BREP('),len(result['shells']))
            self.assertEqual(report['expected_body_count'],len(result['shells']))
        light=self.create(mesh=False)
        self.assertNotIn('mesh',light)
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(ValueError):
            self.site.write_site_step(Path(folder)/'missing.step',light)

    def test_native_shell_assignment_uses_geometry_not_import_order(self):
        result=self.create()
        expected={s['id']:1000+i for i,s in enumerate(result['shells'])}
        native=[{'tag':expected[s['id']],'bbox_mm':s['bbox_mm'][:],
                 'volume_m3':s['volume_m3'],'centroid_mm':s['centroid_mm'][:]}
                for s in reversed(result['shells'])]
        self.assertEqual(self.site.match_native_shells(result,native),expected)
        for change in ('duplicate_tag','wrong_bbox','wrong_volume','missing'):
            with self.subTest(change=change):
                bad=copy.deepcopy(native)
                if change=='duplicate_tag':bad[1]['tag']=bad[0]['tag']
                elif change=='wrong_bbox':bad[0]['bbox_mm'][0]+=2
                elif change=='wrong_volume':bad[0]['volume_m3']*=1.1
                else:bad.pop()
                with self.assertRaises(ValueError):self.site.match_native_shells(result,bad)

    def test_centroid_disambiguates_equal_bbox_volume_and_remaining_duplicates_fail(self):
        a={'id':'A','bbox_mm':[0,0,0,1000,1000,1000],'volume_m3':.5,'centroid_mm':[200,500,500]}
        b=dict(a,id='B',centroid_mm=[800,500,500])
        site={'shells':[a,b]}
        records=[{'tag':2,'bbox_mm':a['bbox_mm'],'volume_m3':.5,'centroid_mm':b['centroid_mm']},
                 {'tag':1,'bbox_mm':a['bbox_mm'],'volume_m3':.5,'centroid_mm':a['centroid_mm']}]
        self.assertEqual(self.site.match_native_shells(site,records),{'A':1,'B':2})
        for row in records:row.pop('centroid_mm')
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            self.site.match_native_shells(site,records)

    def test_one_step_preparation_returns_compact_hashed_reusable_native_entry(self):
        site=self.create()
        with tempfile.TemporaryDirectory() as folder:
            entry=self.site.prepare_site_inputs(site,folder)
            self.assertNotIn('mesh',entry)
            self.assertTrue(Path(entry['step_path']).is_file())
            self.assertTrue(Path(entry['entry_path']).is_file())
            self.assertEqual(entry['file'],'ANBAU_SITE.prt')
            self.assertEqual(entry['reference_sets']['PS11-F01']['name'],'ANBAU_SITE_PS11_F01')
            self.assertEqual(entry,self.site.prepare_site_inputs(site,folder))
            self.site.validate_site_entry(entry)
            bad=copy.deepcopy(entry)
            bad['reference_sets']['PS11-F01']['body_count']+=1
            with self.assertRaises(ValueError):self.site.validate_site_entry(bad)

    def test_uf_mass_units_four_preserve_cubic_metres_and_convert_centroid_metres_to_mm(self):
        values=[0.]*47
        values[1]=.375;values[2]=250.;values[3:6]=[15.5,-2.25,.125]
        actual=self.site.uf_mass_values(values)
        self.assertEqual(actual['volume_m3'],.375)
        self.assertEqual(actual['centroid_wcs_mm'],[15500,-2250,125])
        values[1]=float('nan')
        with self.assertRaises(ValueError):self.site.uf_mass_values(values)

    def test_native_entry_points_refuse_gui_before_any_native_api_or_file_mutation(self):
        session=SimpleNamespace(IsBatch=False)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'ANBAU_SITE.prt'
            with self.assertRaisesRegex(ValueError,'batch'):
                self.site.build_site_part(session,path,{})
            self.assertFalse(path.exists())
        with self.assertRaisesRegex(ValueError,'batch'):
            self.site.inspect_site_part(session,None,{})

    def test_rotated_source_grid_proves_uv_crop_instead_of_world_axis_bbox(self):
        grid=Grid({'shape':[7,7],'nodes_mm':[[(i-j)*1000,(i+j)*1000,300] for i in range(7) for j in range(7)]})
        self.terrain['grid']=grid
        self.terrain['boundary_xy_mm']=[[0,0],[6000,6000],[0,12000],[-6000,6000]]
        for field,bounds in zip(self.fields,([1,3,0,1],[2,4,0,1])):
            field['study_terrain']['uv_cell_bounds']=bounds
            field['geometry']['cut_soil']['mesh']=closed_terrain(grid.triangles(4,field['study_terrain']['crop_bbox_xy_mm']),-1000)
        result=self.create()
        self.assertEqual(result['area_m2'],72)
        self.assertEqual(result['reference_sets']['PS11-F01']['area_m2'],68)
        self.assertEqual(result['reference_sets']['PS12-F01']['area_m2'],68)

    def test_shell_volume_centroid_matches_sloped_parallel_layer(self):
        grid=Grid({'shape':[7,7],'nodes_mm':[[i*1000,j*1000,300+i*100+j*50] for i in range(7) for j in range(7)]})
        self.terrain['grid']=grid
        for field in self.fields:
            if field['native_candidate']:
                field['geometry']['cut_soil']['mesh']=closed_terrain(grid.triangles(4,field['study_terrain']['crop_bbox_xy_mm']),-1000)
        result=self.create()
        for shell in result['shells']:
            x,y,z=shell['centroid_mm']
            self.assertAlmostEqual(z,200+.1*x+.05*y,places=7)


    def test_step_import_model_refset_requires_exact_own_bodies_and_associated_facets(self):
        bodies={11:'SHELL_A',12:'SHELL_B'}
        members=[{'tag':11,'kind':'body'},{'tag':12,'kind':'body'},
                 {'tag':21,'kind':'facet','associated_loaded':True,'associated_tag':11}]
        good={'MODEL':members}
        result=self.site.validate_import_model_refset(bodies,good)
        self.assertEqual(result['body_names'],['SHELL_A','SHELL_B'])
        for which in ('missing_model','extra_set','missing_body','extra_body','orphan_facet','wrong_facet','duplicate'):
            bad=copy.deepcopy(good)
            if which=='missing_model':bad={}
            elif which=='extra_set':bad['FOREIGN']=[]
            elif which=='missing_body':bad['MODEL'].pop(1)
            elif which=='extra_body':bad['MODEL'].append({'tag':13,'kind':'body'})
            elif which=='orphan_facet':bad['MODEL'][2]['associated_loaded']=False
            elif which=='wrong_facet':bad['MODEL'][2]['associated_tag']=13
            else:bad['MODEL'].append(copy.deepcopy(bad['MODEL'][0]))
            with self.subTest(which=which),self.assertRaises(ValueError):
                self.site.validate_import_model_refset(bodies,bad)
        self.site.validate_import_model_refset(bodies,{**good,'ANBAU_SITE_TEST':[]},custom_names=['ANBAU_SITE_TEST'])


if __name__=='__main__':unittest.main()
