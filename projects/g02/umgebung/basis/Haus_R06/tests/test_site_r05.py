# -*- coding: utf-8 -*-
"""R05: data geometry, no invented elevations, separated flat-roof reference.
NX calls in this test use explicitly simulated responses, not NX/Parasolid.
"""
import contextlib, copy, io, json, math, os, shutil, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_site import audit_site, validate_line, line_definition
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_geometry import Parameters,area,convex_intersection
from haus2406_r03.haus_run import reference_objects,run_house,check_saved_house
from haus2406_r03.haus_metadata import object_attributes
from haus2406_r03.haus_nx import NXAdapter
from fake_nx import FakeNX

class SiteDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=json.loads((BASE/'data/haus.json').read_text());cls.s=cls.d['site'];cls.p=Parameters(cls.d['parameters']);cls.c=compile_house(cls.d,True)
    def test_parcel_date_and_no_survey_claim(self):
        self.assertEqual(self.s['parcel'],'74/34');self.assertEqual(self.s['boundary_date'],'2026-01-23');self.assertFalse(self.s['survey_verified'])
    def test_25_sourced_routes(self):
        self.assertEqual(len(self.s['routes']),25);self.assertTrue(all(r['sources'] for r in self.s['routes']))
    def test_45_open_route_segments_and_23_closed_control_edges(self):
        a=audit_site(self.s);self.assertEqual((a['route_segments'],a['boundary_segments'],a['cadastral_house_segments'],a['curve_segments']),(45,9,14,68))
    def test_unknown_depths_stay_null(self):
        self.assertTrue(all(r['z_mm'] is None for r in self.s['routes']));self.assertIsNone(self.s['physical_z_mm'])
    def test_projection_plane_not_depth(self):
        r=line_definition(self.s['routes'][0],self.s,'TEST');self.assertTrue(all(p[2]==0 for p in r['points3d']));self.assertIsNone(r['z_mm']);self.assertIn('KEINE_PHYSISCHE_HOEHE',r['representation'])
    def test_no_fake_outer_diameters(self):
        self.assertTrue(all(r['diameter_outer_mm'] is None for r in self.s['routes']))
        g=next(r for r in self.s['routes'] if r['id']=='GAS_HAUSANSCHLUSS');self.assertEqual(g['nominal_size_dn'],40)
    def test_no_assumed_broadband_connection(self):
        b=[r for r in self.s['routes'] if r['network']=='BREITBAND'];self.assertEqual(len(b),5);self.assertTrue(all(r['role']=='STRASSENTRASSE' for r in b))
    def test_telekom_two_drawn_entries_not_merged(self):
        t=[r for r in self.s['routes'] if r['network']=='TELEFON' and r['role']=='HAUSANSCHLUSS'];self.assertEqual(len(t),2);self.assertNotEqual(t[0]['points_local_mm'][-1],t[1]['points_local_mm'][-1])
    def test_electric_connection_label_preserved(self):
        r=next(r for r in self.s['routes'] if r['id']=='STROM_HAUSANSCHLUSS');self.assertEqual(r['source_label'],'NAYY 4x35')
    def test_operator_validity_does_not_become_current(self):
        self.assertTrue(all(r['valid_until']<'2026-10-07' for r in self.s['routes']));self.assertFalse(self.s['use_for_excavation'])
    def test_no_water_sewage_from_legend(self):
        self.assertFalse(any(r['network'] in ('WASSER','ABWASSER','REGENWASSER') for r in self.s['routes']));self.assertIn('SCHMUTZWASSER',self.s['unavailable_networks'])
    def test_registration_residuals_retained(self):
        self.assertGreater(self.s['coordinate_reference']['max_house_control_residual_mm'],250)
        self.assertGreater(next(r for r in self.s['registrations'] if r['id'].startswith('TELEFON'))['max_control_residual_mm'],400)
    def test_orthogonal_local_basis_without_house_scaling(self):
        g=self.s['coordinate_reference'];a=g['local_x_in_east_north'];b=g['local_y_in_east_north'];self.assertAlmostEqual(sum(x*y for x,y in zip(a,b)),0);self.assertAlmostEqual(math.hypot(*a),1);self.assertAlmostEqual(math.hypot(*b),1)
    def test_closed_boundary_area_is_only_graphic(self):
        b=self.s['boundary'];self.assertTrue(1800<b['graphic_area_m2']<1850);self.assertIn('KEINE_AMTLICHE_PUNKTDATEI',b['geometry_quality'])
    def test_duplicate_id_is_blocked(self):
        s=copy.deepcopy(self.s);s['routes'][1]['id']=s['routes'][0]['id']
        with self.assertRaisesRegex(ValueError,'Doppelte'):audit_site(s)
    def test_nan_coordinate_is_blocked(self):
        s=copy.deepcopy(self.s);s['routes'][0]['points_local_mm'][0][0]=float('nan')
        with self.assertRaisesRegex(ValueError,'endliche'):audit_site(s)
    def test_zero_length_is_blocked(self):
        s=copy.deepcopy(self.s);s['routes'][0]['points_local_mm'][1]=s['routes'][0]['points_local_mm'][0]
        with self.assertRaisesRegex(ValueError,'Nullsegment'):audit_site(s)
    def test_singular_registration_is_blocked(self):
        s=copy.deepcopy(self.s);s['registrations'][0]['matrix_2x3']=[[0,0,0],[0,0,0]]
        with self.assertRaisesRegex(ValueError,'Singulaere'):audit_site(s)
    def test_3d_requires_complete_height_count(self):
        r=copy.deepcopy(self.s['routes'][0]);r['z_mm']=[-800]
        with self.assertRaisesRegex(ValueError,'Z-Wert pro'):validate_line(r)
    def test_3d_requires_height_datum_and_source(self):
        r=copy.deepcopy(self.s['routes'][0]);r['z_mm']=[-800]*len(r['points_local_mm'])
        with self.assertRaisesRegex(ValueError,'Hoehenbezug'):validate_line(r)
    def test_sourced_3d_polyline_uses_its_own_heights(self):
        r=copy.deepcopy(self.s['routes'][0]);r['z_mm']=[-900-i*10 for i in range(len(r['points_local_mm']))];r['height_sources']=[{'document':'SYNTHETISCHER_TEST'}];r['height_datum']='SYNTHETISCHER_TEST_NICHT_HAUS';r['z_coordinate_system']='MODELL_Z_MM_EG0'
        x=line_definition(r,self.s,'TEST');self.assertEqual([p[2] for p in x['points3d']],r['z_mm']);self.assertEqual(x['representation'],'3D_TRASSENACHSE')
    def test_nhn_heights_not_automatically_used_as_local_z(self):
        r=copy.deepcopy(self.s['routes'][0]);r['z_mm']=[40000]*len(r['points_local_mm']);r['height_sources']=[{'document':'TEST'}];r['height_datum']='NHN_UNKORRIGIERT'
        with self.assertRaisesRegex(ValueError,'umgerechnet'):validate_line(r)
    def test_polyline_cannot_claim_pipe_body(self):
        r=copy.deepcopy(self.s['routes'][0]);r['physical_pipe_model']=True
        with self.assertRaisesRegex(ValueError,'Rohrkoerper'):validate_line(r)
    def test_all_new_components_in_build_and_source_coverage(self):
        self.assertEqual(len(self.c['parts']),14);self.assertEqual(self.c['planned_solids'],1165)
        new=[p for p in self.c['parts'] if p.get('force_reference_display')];self.assertEqual(len(new),5);self.assertTrue(all(not p['solids'] for p in new))
    def test_references_not_silently_hidden_in_3d_mode(self):
        refs=[r for p in self.c['parts'] if p.get('force_reference_display') for r in p['references']];self.assertEqual(len(refs),27);self.assertTrue(all('points3d' in r for r in refs))
    def test_flat_roof_one_reference_body_no_building_material(self):
        p=next(p for p in self.c['parts'] if p['id']=='FLACHDACH');self.assertEqual(len(p['solids']),1);self.assertTrue(p['solids'][0]['meta']['quantity_excluded']);self.assertEqual(self.c['flat_roof_audit']['physical_roof_materials'],0)
    def test_flat_roof_slope_and_layers_remain_unknown(self):
        r=self.d['flat_roofs'][0];self.assertIsNone(r['slope_percent']);self.assertIsNone(r['drainage_direction']);self.assertEqual(r['physical_layers'],[])
    def test_flat_roof_does_not_duplicate_sloped_roof_projection(self):
        f=next(p for p in self.c['parts'] if p['id']=='FLACHDACH')['solids'][0]
        for roof in self.c['roof_faces']:self.assertLess(abs(area(convex_intersection(f['polygon'],roof['polygon']))),0.1)
    def test_reference_mode_keeps_site_but_no_flat_roof_solid(self):
        c=compile_house(self.d,False);self.assertEqual(c['planned_solids'],0);self.assertEqual(len(c['parts']),13);self.assertEqual(c['site_audit']['curve_segments'],68)
    def test_old_roof_and_walls_not_rewritten_for_flat_annex(self):
        # R06 source corrections are intentional; adding/removing ONLY the flat
        # reference must still leave building solids and roof faces unchanged.
        other=copy.deepcopy(self.d);other['flat_roofs']=[];other['site']['enabled']=False
        without=compile_house(other,True)
        for part in without['parts']:
            current=next(p for p in self.c['parts'] if p['id']==part['id'])
            self.assertEqual(part['solids'],current['solids'])
        self.assertEqual(without['roof_faces'],self.c['roof_faces'])
    def test_metadata_discloses_projection_and_network(self):
        r=line_definition(self.s['routes'][0],self.s,'LEITUNG_PLANREFERENZ');m=object_attributes(r)
        self.assertEqual(m['HAUS_NETZ'],'STROM');self.assertIn('KEINE_VERLEGETIEFE',m['HAUS_HOEHENSTATUS']);self.assertTrue(all(k.startswith('HAUS_') for k in m))

class SiteRuntimeDoubleTests(unittest.TestCase):
    def test_open_reference_lines_do_not_close_connections(self):
        d=json.loads((BASE/'data/haus.json').read_text());r=line_definition(d['site']['routes'][0],d['site'],'TEST');calls=[]
        class Dummy:
            def lines(self,part,points,name,closed,blank,meta):
                calls.append((closed,points));return [object()]*(len(points)-(0 if closed else 1))
        count=reference_objects(Dummy(),None,[r],Parameters(d['parameters']));self.assertFalse(calls[0][0]);self.assertEqual(count,len(r['points3d'])-1)
    def test_closed_cadastral_lines_keep_final_segment(self):
        d=json.loads((BASE/'data/haus.json').read_text());r=line_definition(d['site']['boundary'],d['site'],'TEST')
        class Dummy:
            def lines(self,part,points,name,closed,blank,meta):return [object()]*(len(points)-(0 if closed else 1))
        self.assertEqual(reference_objects(Dummy(),None,[r],Parameters(d['parameters'])),9)
    def test_simulated_full_run_saves_all_68_site_segments(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);shutil.copytree(BASE/'data',root/'data');shutil.copytree(BASE/'src',root/'src',ignore=shutil.ignore_patterns('__pycache__'));f=FakeNX()
            with f.install(),contextlib.redirect_stdout(io.StringIO()):
                state=run_house(root);checked=check_saved_house(root)
            self.assertEqual(sum(state['site_reference_counts'].values()),68);self.assertEqual(state['built_solids'],1165);self.assertEqual(state['component_count'],14)
            self.assertEqual(checked['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN');self.assertTrue((Path(state['output_directory'])/'grundstueck_leitungspruefung.json').is_file())

if __name__=='__main__':unittest.main(verbosity=2)
