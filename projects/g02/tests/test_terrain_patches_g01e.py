"""G01e regression and geometry-logic tests. No NX runtime available."""
import copy,hashlib,json,math,sys,tempfile,unittest
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'tests')]
from gesamt import terrain_patches as p
from gesamt import terrain_uv as uv
from gesamt.core import read_json
from patch_double import PatchAdapter,Trace
SPEC=next(x for x in read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if x['id']=='DGM')
_,PTS=uv.prepared_reference(SPEC)

def rect_edges(r0,r1,c0,c1):
 return {1:((r0,c0),(r1,c0)),2:((r1,c0),(r1,c1)),3:((r1,c1),(r0,c1)),4:((r0,c1),(r0,c0))}

class Geometry(unittest.TestCase):
 def test_01_report_8282_matches_cells_not_automatic_acceptance(self):
  self.assertEqual(p.CELL_COUNT,101*82); self.assertEqual(p.CELL_COUNT,8282)
 def test_02_grid_nodes_roundtrip(self):
  g=p.Grid(PTS)
  for r,c in [(0,0),(13,10),(101,82)]:self.assertEqual(g.node(PTS[r*83+c])[0],(r,c))
 def test_03_shifted_node_rejected(self):
  g=p.Grid(PTS);q=list(PTS[1089]);q[2]+=.251
  with self.assertRaises(p.PatchError):g.node(q)
 def test_04_invalid_grid(self):
  q=copy.deepcopy(PTS);q[83][:2]=q[0][:2]
  with self.assertRaises(p.PatchError):p.Grid(q)
 def test_05_quad_recognized(self):self.assertEqual(p.face_rectangle(rect_edges(0,1,0,1),10),(0,1,0,1))
 def test_06_shuffled_edges(self):self.assertEqual(p.face_rectangle(dict(reversed(list(rect_edges(2,4,4,8).items()))),10),(2,4,4,8))
 def test_07_missing_edge(self):
  e=rect_edges(0,1,0,1);e.pop(4)
  with self.assertRaises(p.PatchError):p.face_rectangle(e,10)
 def test_08_diagonal_trim(self):
  e=rect_edges(0,2,0,2);e[5]=((0,0),(2,2))
  with self.assertRaises(p.PatchError):p.face_rectangle(e,10)
 def test_09_inner_hole(self):
  e=rect_edges(0,4,0,4);e.update({tag+10:pair for tag,pair in rect_edges(1,2,1,2).items()})
  with self.assertRaises(p.PatchError):p.face_rectangle(e,10)
 def test_10_zero_edge(self):
  e=rect_edges(0,1,0,1);e[5]=((0,0),(0,0))
  with self.assertRaises(p.PatchError):p.face_rectangle(e,10)
 def test_11_segmented_face_boundary(self):
  e=rect_edges(0,2,0,2);e[1]=((0,0),(1,0));e[5]=((1,0),(2,0))
  self.assertEqual(p.face_rectangle(e,10),(0,2,0,2))
 def test_12_complete_small_coverage(self):
  r=[{'tag':1,'rectangle':(0,1,0,2)},{'tag':2,'rectangle':(1,2,0,2)}]
  self.assertEqual(len(p.validate_coverage(r,3,3)),4)
 def test_13_duplicate_coverage(self):
  r=[{'tag':1,'rectangle':(0,2,0,2)},{'tag':2,'rectangle':(1,2,0,2)}]
  with self.assertRaisesRegex(p.PatchError,'doppelt'):p.validate_coverage(r,3,3)
 def test_14_missing_coverage(self):
  with self.assertRaisesRegex(p.PatchError,'fehlen'):p.validate_coverage([{'tag':1,'rectangle':(0,1,0,2)}],3,3)
 def test_15_outside_coverage(self):
  with self.assertRaises(p.PatchError):p.validate_coverage([{'tag':1,'rectangle':(0,3,0,2)}],3,3)
 def test_16_true_shared_edge(self):
  ow={(0,0):1,(1,0):2};e={'tag':4,'nodes':[(1,0),(1,1)],'faces':[1,2]}
  ext,inter=p.edge_incidence([e],ow,3,2);self.assertEqual(len(inter),1)
 def test_17_disconnected_seam(self):
  with self.assertRaisesRegex(p.PatchError,'Naht'):p.edge_incidence([{'tag':4,'nodes':[(1,0),(1,1)],'faces':[1]}],{(0,0):1,(1,0):2},3,2)
 def test_18_wrong_shared_neighbor(self):
  with self.assertRaises(p.PatchError):p.edge_incidence([{'tag':4,'nodes':[(1,0),(1,1)],'faces':[1,7]}],{(0,0):1,(1,0):2},3,2)
 def test_19_exterior_only_one_incidence(self):
  e={'tag':4,'nodes':[(0,0),(0,1)],'faces':[1]}
  self.assertEqual(len(p.edge_incidence([e],{(0,0):1},2,2)[0]),1)
 def test_20_nine_grid_samples_2x2_patch(self):
  s=list(p.face_reference_samples((0,2,0,2)));self.assertEqual(len(s),13)
 def test_21_affine_uv_forward(self):
  g=p.Grid(PTS);cs=[g.at(1,2),g.at(2,2),g.at(1,3),g.at(2,3)]
  m=p.affine_parameter_map(cs,g,[10,20,30,40]);u,v=p.uv_at(1.5,2.5,m,g)
  self.assertAlmostEqual(u,15,places=5);self.assertAlmostEqual(v,35,places=5)
 def test_22_uv_swapped(self):
  g=p.Grid(PTS);cs=[g.at(1,2),g.at(1,3),g.at(2,2),g.at(2,3)]
  m=p.affine_parameter_map(cs,g,[0,1,0,1]);u,v=p.uv_at(1.25,2.75,m,g)
  self.assertAlmostEqual(u,.75,places=5);self.assertAlmostEqual(v,.25,places=5)
 def test_23_skewed_plane_uv_supported(self):
  g=p.Grid(PTS);cs=[g.at(10,10),g.at(12,11),g.at(9,12),g.at(11,13)]
  m=p.affine_parameter_map(cs,g,[0,1,0,1]);u,v=p.uv_at(10.5,11.5,m,g)
  self.assertAlmostEqual(u,.5,places=5);self.assertAlmostEqual(v,.5,places=5)
 def test_24_nonaffine_uv_rejected(self):
  g=p.Grid(PTS);cs=[g.at(1,2),g.at(2,2),g.at(1,3),g.at(2.01,3)]
  with self.assertRaises(p.PatchError):p.affine_parameter_map(cs,g,[0,1,0,1])
 def test_25_singular_uv_rejected(self):
  g=p.Grid(PTS)
  with self.assertRaises(p.PatchError):p.affine_parameter_map([g.at(0,0)]*4,g,[0,1,0,1])
 def test_26_outside_uv_rejected(self):
  g=p.Grid(PTS);m=p.affine_parameter_map([g.at(1,2),g.at(2,2),g.at(1,3),g.at(2,3)],g,[0,1,0,1])
  with self.assertRaises(p.PatchError):p.uv_at(4,4,m,g)
 def test_27_original_step_not_modified(self):
  file=B/'umgebung'/SPEC['step_file'];self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(),uv.SOURCE_SHA256)
 def test_28_limit_remains_025(self):self.assertEqual(p.DISTANCE_MM,.25)

class Integration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.out=Path(self.tmp.name)
  self.a=PatchAdapter(SPEC,[(0,51,0,82),(51,101,0,82)],reverse=True)
 def invoke(self):return uv.verify_dgm_uv(self.a,self.a.part,SPEC,self.out,Trace(self.out/'trace.json'))
 def report(self):return read_json(self.out/uv.REPORT)
 def test_29_two_rectangles_full_coverage(self):
  r=self.invoke();self.assertEqual(r['faces'],2);self.assertEqual(r['checked_source_points'],16748)
  self.assertTrue(self.report()['coverage_passed']);self.assertEqual(self.a.minimum_body_calls,0)
 def test_30_uv_axes_reversed_and_swapped(self):
  self.a.reverse=True;self.a.swap=True
  self.assertEqual(self.invoke()['verified_raster_cells'],8282)
 def test_31_duplicate_rectangle_rejected(self):
  self.a=PatchAdapter(SPEC,[(0,101,0,82),(0,101,0,82)])
  with self.assertRaisesRegex(p.PatchError,'doppelt'):self.invoke()
  self.assertFalse(self.report()['selected_checks_passed'])
 def test_32_missing_cell_rejected(self):
  self.a=PatchAdapter(SPEC,[(0,51,0,82),(51,100,0,82)])
  with self.assertRaisesRegex(p.PatchError,'fehlen'):self.invoke()
 def test_33_foreign_face_owner(self):
  self.a.faces[0].OwningPart=type('P',(),{'Tag':999})()
  with self.assertRaisesRegex(p.PatchError,'Part'):self.invoke()
 def test_34_deformed_node_rejected(self):
  self.a.deformation=lambda pt,r,c,tag:[pt[0],pt[1],pt[2]+(2 if abs(r-13)<1e-5 and abs(c-10)<1e-5 else 0)]
  with self.assertRaises(p.PatchError):self.invoke()
  self.assertEqual(self.report()['failed_sample']['source_index'],1089)
 def test_35_deformed_cell_centre_rejected(self):
  self.a.deformation=lambda pt,r,c,tag:[pt[0],pt[1],pt[2]+(2 if abs(r-13.5)<1e-5 and abs(c-10.5)<1e-5 else 0)]
  with self.assertRaises(p.PatchError):self.invoke()
 def test_36_bad_edge_result_still_rejected(self):
  self.a.bad_edge_distance=.26372681449087754
  with self.assertRaisesRegex(p.PatchError,'Kante'):self.invoke()
  self.assertTrue(self.report()['all_carrier_reference_points_passed'])
 def test_37_nonfinite_uv_rejected(self):
  self.a.bad_uv=True
  with self.assertRaises(ValueError):self.invoke()
 def test_38_nonfinite_surface_rejected(self):
  self.a.bad_point=True
  with self.assertRaises(ValueError):self.invoke()
 def test_39_data_not_mutated(self):
  before=copy.deepcopy(SPEC);self.invoke();self.assertEqual(before,SPEC)
 def test_40_cancel_is_not_ignored(self):
  def stop():raise RuntimeError('STOP_BY_TEST')
  self.a.monitor.check_cancel=stop
  with self.assertRaisesRegex(RuntimeError,'STOP_BY_TEST'):self.invoke()
 def test_41_full_8282_cell_subdivision(self):
  self.a=PatchAdapter(SPEC,[(r,r+1,c,c+1) for r in range(101) for c in range(82)],reverse=True)
  r=self.invoke();s=self.report()
  self.assertEqual(r['faces'],8282);self.assertEqual(r['checked_source_points'],16748)
  self.assertEqual(s['face_point_comparisons'],41410)
  self.assertEqual(s['unique_edges'],16747);self.assertEqual(s['interior_edges'],16381)
  self.assertEqual(s['boundary_samples_checked'],1834);self.assertEqual(s['shared_edge_samples_checked'],49143)
  self.assertEqual(s['edge_distance_calls'],50977);self.assertTrue(s['selected_checks_passed'])
 def test_42_failure_json_has_actual_counts(self):
  self.a.bad_uv=True
  with self.assertRaises(ValueError):self.invoke()
  r=self.report();self.assertEqual(r['nx_faces'],2);self.assertIn('active_face',r)

if __name__=='__main__':unittest.main(verbosity=2)
