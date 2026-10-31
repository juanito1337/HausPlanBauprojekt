"""Offline checks of data, map coordinates and actual STEP round-trip; NOT an NX test.
Run: python werkzeuge/PRUEFE_R08_OFFLINE.py
Requires numpy, scipy, rasterio, shapely, cadquery/OCP.
"""
from pathlib import Path
import unittest,json,hashlib,sys
import numpy as np
import rasterio
from scipy.interpolate import RegularGridInterpolator
from shapely.geometry import Polygon
from shapely import contains_xy
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt

B=Path(__file__).absolute().parents[1]

def bbox(shape):
    bb=shape.BoundingBox();return np.array([bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax])
def xyz_bounds(p):
    q=p.reshape(-1,3);return np.r_[q.min(axis=0),q.max(axis=0)]

class VegetationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a=dict(np.load(B/'data/RASTER_AUSWERTUNG_R08.npz',allow_pickle=False))
        cls.j=json.loads((B/'data/BAUAUFTRAG_VEGETATION_R08.json').read_text())
        cls.i=json.loads((B/'data/AUSWAHL_R08.json').read_text())
        cls.r=np.array(cls.j['transform']['basis_rows_local_xy_in_EN']);cls.o=np.array(cls.j['transform']['origin_EN_m'])
        cls.cads={}
        for name in ['VEGETATION_OBERFLAECHEN_R08.step','GRUENFLAECHEN_NUR_BODENREFERENZ_R08.step','GELAENDE_UND_VEGETATION_R08.step','GELAENDE_R07_UNVERAENDERT.step']:
            cls.cads[name]=cq.importers.importStep(str(B/'CAD'/name)).val()
    def test_01_raster_coverage_and_pixel_alignment(self):
        with rasterio.open(B/'data/DOP_RGBI_2025_AUSSCHNITT.tif') as d,rasterio.open(B/'data/BDOM_2023_AUSSCHNITT.tif') as h:
            self.assertEqual(d.transform,h.transform);self.assertEqual((d.height,d.width),(405,500));self.assertEqual(d.shape,h.shape)
            self.assertEqual(d.crs.to_epsg(),25832);self.assertEqual(h.crs.to_epsg(),25832);self.assertEqual(d.res,(.2,.2))
    def test_02_rgbi_band_layout_and_float_height_data(self):
        with rasterio.open(B/'data/DOP_RGBI_2025_AUSSCHNITT.tif') as d,rasterio.open(B/'data/BDOM_2023_AUSSCHNITT.tif') as h:
            self.assertEqual(d.count,4);self.assertEqual(d.dtypes,('uint8',)*4);self.assertEqual(h.dtypes,('float32',));np.testing.assert_array_equal(h.read(1),self.a['dom'])
    def test_03_no_nodata_in_review_crop(self):
        for key in ['dom','ground','local','h','ndvi']:self.assertTrue(np.isfinite(self.a[key]).all())
    def test_04_metadata_dates_not_conflated(self):
        s=self.j['sources'];self.assertEqual(s['bdom_date'],'2023-04-07');self.assertEqual(s['dop_date'],'2025-05-12');self.assertNotEqual(s['bdom_date'],s['dop_date'])
        self.assertIsNone(s['dgm_date']);self.assertFalse(s['dgm_vertical_verified'])
    def test_05_height_metadata_kept_and_no_house_offset(self):
        self.assertEqual(self.j['sources']['bdom_crs_vertical'],7837);self.assertIsNone(self.j['transform']['H_EG_zero_m']);self.assertFalse(self.j['transform']['house_height_aligned'])
    def test_06_rotation_is_rigid(self):
        np.testing.assert_allclose(self.r@self.r.T,np.eye(2),rtol=0,atol=1e-12);self.assertAlmostEqual(np.linalg.det(self.r),1.)
    def test_07_r07_house_axes_and_boundary_roundtrip(self):
        site=json.loads((B/'quellen/R06_KARTENBEZUG_UNVERAENDERT.json').read_text())
        local=np.array(site['boundary']['points_local_mm'])/1000;expected=local@self.r+self.o
        np.testing.assert_allclose(expected,self.a['boundary'],rtol=0,atol=1e-8)
        h=np.array(site['cadastral_house']['points_local_mm'])/1000
        np.testing.assert_allclose(h@self.r+self.o,self.a['house_en'],rtol=0,atol=1e-8)
    def test_08_all_selected_grid_coordinates_follow_r07(self):
        en=np.stack([self.a['e'],self.a['n']],axis=-1)
        np.testing.assert_allclose((en-self.o)@self.r.T,self.a['local'],rtol=0,atol=1e-10)
        np.testing.assert_allclose(self.a['local']@self.r+self.o,en,rtol=0,atol=1e-8)
    def test_09_dgm_bilinear_sampling_reproduced(self):
        with rasterio.open(B/'data/DGM_R07_AUSSCHNITT.tif') as ds:
            arr=ds.read(1);tf=ds.transform;x=tf.c+tf.a*(np.arange(ds.width)+.5);y=tf.f+tf.e*(np.arange(ds.height)+.5)
            if y[0]>y[-1]:y=y[::-1];arr=arr[::-1]
            q=RegularGridInterpolator((y,x),arr,bounds_error=True)(np.stack([self.a['n'],self.a['e']],axis=-1))
        np.testing.assert_allclose(q,self.a['ground'],rtol=0,atol=1e-9)
    def test_10_height_difference_not_shifted(self):
        np.testing.assert_allclose(self.a['dom']-self.a['ground'],self.a['h'],rtol=0,atol=1e-10)
        for k in self.i['paved_comparisons']:self.assertFalse(k['offset_applied']);self.assertFalse(k['datum_proof'])
    def test_11_spectral_index_reproduced(self):
        with rasterio.open(B/'data/DOP_RGBI_2025_AUSSCHNITT.tif') as ds:
            r=ds.read(1).astype(float);nir=ds.read(4).astype(float)
        np.testing.assert_allclose((nir-r)/(nir+r+1e-6),self.a['ndvi'],rtol=0,atol=1e-10)
    def test_12_selected_vegetation_satisfies_criteria(self):
        sel=self.a['labels']>0;self.assertTrue((self.a['ndvi'][sel]>=.18).all());self.assertTrue((self.a['h'][sel]>=.6).all())
    def test_13_no_canopy_nodes_in_buffered_cadastral_house(self):
        inside=contains_xy(Polygon(self.a['house_en']).buffer(.5),self.a['e'],self.a['n'])
        self.assertFalse(((self.a['labels']>0)&inside).any())
    def test_14_regions_inside_review_roi_and_parcel_buffer(self):
        review=Polygon(self.a['boundary']).buffer(2)
        for k,rec in enumerate(self.i['regions'],1):
            sel=self.a['labels']==k;p=Polygon(rec['review_polygon_utm_m'])
            self.assertTrue(contains_xy(p,self.a['e'][sel],self.a['n'][sel]).all());self.assertTrue(contains_xy(review,self.a['e'][sel],self.a['n'][sel]).all())
    def test_15_boundary_ownership_not_inferred(self):
        for rec in self.i['regions']:self.assertFalse(rec['stem_ownership_verified']);self.assertIsNone(rec['stem_location']);self.assertIsNone(rec['stem_diameter_m']);self.assertIsNone(rec['root_extent']);self.assertFalse(rec['canopy_height_current_verified'])
    def test_16_raster_rectangles_exact_without_overlap_or_extra_cells(self):
        for k,part in enumerate(self.j['parts'],1):
            nodes=(self.a['labels']==k) if k<=8 else self.a['low']
            cells=nodes[:-1,:-1]&nodes[1:,:-1]&nodes[:-1,1:]&nodes[1:,1:]
            covered=np.zeros(cells.shape,np.uint8)
            for r0,r1,c0,c1 in part['rectangles']:
                self.assertGreater(r1,r0);self.assertGreater(c1,c0);covered[r0:r1,c0:c1]+=1
            np.testing.assert_array_equal(covered,cells.astype(np.uint8))
    def test_17_actual_imported_shapes_valid_open_not_solid(self):
        for shape in self.cads.values():self.assertTrue(BRepCheck_Analyzer(shape.wrapped).IsValid());self.assertEqual(len(shape.Solids()),0)
    def test_18_step_face_counts(self):
        veg=sum(len(p['rectangles']) for p in self.j['parts'] if p['z_source']=='bdom');low=sum(len(p['rectangles']) for p in self.j['parts'] if p['z_source']=='dgm')
        self.assertEqual(len(self.cads['VEGETATION_OBERFLAECHEN_R08.step'].Faces()),veg)
        self.assertEqual(len(self.cads['GRUENFLAECHEN_NUR_BODENREFERENZ_R08.step'].Faces()),low)
        self.assertEqual(len(self.cads['GELAENDE_UND_VEGETATION_R08.step'].Faces()),veg+low+1)
    def test_19_roundtrip_all_patch_bounds_and_point_distances(self):
        maxerr=0.;checks=0
        for kind,filename in [('bdom','VEGETATION_OBERFLAECHEN_R08.step'),('dgm','GRUENFLAECHEN_NUR_BODENREFERENZ_R08.step')]:
            faces=self.cads[filename].Faces();bounds=np.array([bbox(f) for f in faces]);used=set()
            for part in self.j['parts']:
                if part['z_source']!=kind:continue
                z=self.a['dom'] if kind=='bdom' else self.a['ground']
                for r0,r1,c0,c1 in part['rectangles']:
                    pts=np.concatenate([self.a['local'][r0:r1+1,c0:c1+1]*1000,z[r0:r1+1,c0:c1+1,None]*1000],axis=-1)
                    distances=np.max(np.abs(bounds-xyz_bounds(pts)),axis=1);index=int(distances.argmin())
                    self.assertLess(distances[index],.002);self.assertNotIn(index,used);used.add(index)
                    # 4 corners, a source node, and an independently interpolated cell-center point.
                    rr=(r1-r0)//2;cc=(c1-c0)//2
                    check_pts=[pts[0,0],pts[0,-1],pts[-1,0],pts[-1,-1],pts[rr,cc],pts[:2,:2].mean(axis=(0,1))]
                    for xyz in check_pts:
                        v=BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,xyz))).Vertex();dist=BRepExtrema_DistShapeShape(v,faces[index].wrapped);dist.Perform()
                        self.assertTrue(dist.IsDone());val=dist.Value();self.assertLess(val,.002);maxerr=max(maxerr,val);checks+=1
            self.assertEqual(len(used),len(faces))
        print('\nActual STEP round-trip: %d point-to-face checks, maximum error %.9f mm'%(checks,maxerr))
    def test_20_all_dates_and_height_unknowns_in_registry(self):
        self.assertEqual(len(self.i['regions']),8)
        for rec in self.i['regions']:
            self.assertEqual(rec['acquisition_image'],'2025-05-12');self.assertEqual(rec['acquisition_surface'],'2023-04-07');self.assertFalse(rec['ground_vertical_datum_verified'])
    def test_21_step_units_are_mm(self):
        for name in self.cads:
            text=(B/'CAD'/name).read_text(errors='strict');self.assertIn('SI_UNIT(.MILLI.,.METRE.)',text)
    def test_22_canopy_shapes_are_not_placed_at_roof_or_house_zero(self):
        bb=bbox(self.cads['VEGETATION_OBERFLAECHEN_R08.step']);self.assertGreater(bb[2],29000);self.assertLess(bb[5],40000)
    def test_23_source_metadata_texts_retained(self):
        dom=(B/'quellen/bdom20nc_32_568_6003_1_sh_2023.pp.txt').read_text();dop=(B/'quellen/dop20rgbi_32_568_6003_1_sh_2025.pp.txt').read_text()
        self.assertIn('07.04.2023',dom);self.assertIn('12.05.2025',dop);self.assertIn('7837',dom);self.assertIn('RGBI',dop)
    def test_24_source_masks_and_incomplete_coverage_disclosed(self):
        self.assertFalse(self.j['is_tree_census']);self.assertFalse(self.j['stems_modelled']);self.assertFalse(self.j['current_2026_geometry_verified'])
        for i,rec in enumerate(self.i['regions'],1):
            self.assertEqual(rec['selected_height_nodes'],int((self.a['labels']==i).sum()))
            self.assertLessEqual(rec['represented_source_nodes'],rec['selected_height_nodes'])

    def test_25_selection_recalculated_from_geotiffs_and_rois(self):
        from REPRODUZIERE_AUSWAHL_OFFLINE import recalculate
        result=recalculate(B)
        for key in ['labels','spectral_labels','low']:np.testing.assert_array_equal(result[key],self.a[key])

if __name__=='__main__':unittest.main(verbosity=2)
