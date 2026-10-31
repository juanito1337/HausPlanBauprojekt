"""Independent real CAD roundtrip and equivalence checks for G01d. NOT NX."""
import argparse,hashlib,json,math,sys
from pathlib import Path
B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'werkzeuge')]
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCP.gp import gp_Pnt
from gesamt import PATCH
from gesamt.core import read_json,write_json
from gesamt.terrain_uv import verify_dgm_uv,REPORT
from gesamt.terrain_boundary import SourceSide,plan_boundary
from PRUEFE_DGM_UV_OCCT import CadAdapter,Trace


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',required=True)
    out=Path(p.parse_args().out).absolute();out.mkdir(parents=True,exist_ok=False)
    spec=next(p for p in read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if p['id']=='DGM')
    old_path=B/'umgebung/CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step'
    new_path=B/'umgebung'/spec['step_file']
    old=cq.importers.importStep(str(old_path)).val().Faces()[0]
    new=cq.importers.importStep(str(new_path)).val().Faces()[0]
    assert old.isValid() and new.isValid()
    assert len(old.Edges())==4 and len(new.Edges())==366 and len(new.Wires())==1
    assert all(e.geomType()=='LINE' for e in new.Edges())
    a=BRep_Tool.Surface_s(old.wrapped);b=BRep_Tool.Surface_s(new.wrapped)
    attrs=['UDegree','VDegree','NbUPoles','NbVPoles','NbUKnots','NbVKnots','IsURational','IsVRational']
    assert all(getattr(a,k)()==getattr(b,k)() for k in attrs)
    for func in ['UKnots','VKnots','UMultiplicities','VMultiplicities']:
        assert list(getattr(a,func)())==list(getattr(b,func)())
    assert list(a.Bounds())==list(b.Bounds())==[0.,101.,0.,82.]
    poles=[a.Pole(i,j).Distance(b.Pole(i,j)) for i in range(1,103) for j in range(1,84)]
    weights=[abs(a.Weight(i,j)-b.Weight(i,j)) for i in range(1,103) for j in range(1,84)]
    assert max(poles)<1e-7 and max(weights)==0
    # Both faces have the same bounded rectangle; the new wire's parameter curves
    # and 3D LINEs must agree with the same original linear cell intervals.
    from gesamt.terrain_uv import prepared_reference,sides
    _,points=prepared_reference(spec);ss=sides(points)
    edges=new.Edges()
    records=[dict(index=i,tag=i+100,endpoints=[list(e.startPoint().toTuple()),list(e.endPoint().toTuple())]) for i,e in enumerate(edges)]
    groups,topology=plan_boundary(records,ss)
    samples=0;max_line_error=0
    for row in topology['edges']:
        source=groups[row['side']]['source'];e=edges[row['index']];curve=BRepAdaptor_Curve(e.wrapped)
        lo,hi=curve.FirstParameter(),curve.LastParameter()
        cp=curve.Value(lo);start=[cp.X(),cp.Y(),cp.Z()]
        forward=math.dist(start,row['start_mm'])<1e-6
        assert forward or math.dist(start,row['end_mm'])<1e-6
        for t in [0,.125,.25,.5,.75,.875,1]:
            xyz=curve.Value(lo+t*(hi-lo));pt=[xyz.X(),xyz.Y(),xyz.Z()]
            f=row['start_fraction']+(row['end_fraction']-row['start_fraction'])*(t if forward else 1-t)
            delta=math.dist(pt,source.at(f));max_line_error=max(max_line_error,delta);samples+=1
            assert delta<1e-6, (row,lo,hi,t,pt,source.at(f),delta,e.startPoint().toTuple(),e.endPoint().toTuple())
    run=out/'production';run.mkdir()
    adapter=CadAdapter(new,run);trace=Trace(run/'trace.json')
    r=verify_dgm_uv(adapter,adapter.part,spec,run,trace);detail=read_json(run/REPORT)
    assert r['checked_source_points']==16748 and r['boundary_samples_checked']==1834
    assert detail['max_position_error_mm']<1e-6 and detail['max_boundary_error_mm']<1e-6
    # The reported target is NOT on the original exact piecewise-linear edge.
    fix=read_json(B/'tests/fixtures/NX_G01c_RAND417.json');q=fix['failure']['query_mm'];target=fix['failure']['raw_result'][2]
    old_r1=min(old.Edges(),key=lambda e:min(math.dist(e.startPoint().toTuple(),q),math.dist(e.endPoint().toTuple(),q)))
    cv=BRepAdaptor_Curve(old_r1.wrapped);spline=cv.BSpline()
    # identify the long R1 curve by the source-side end points (not by residual choice)
    ends=[points[101*83],points[8465]]
    candidates=[e for e in old.Edges() if min(max(math.dist(e.startPoint().toTuple(),ends[0]),math.dist(e.endPoint().toTuple(),ends[1])),max(math.dist(e.startPoint().toTuple(),ends[1]),math.dist(e.endPoint().toTuple(),ends[0])))<1e-5]
    assert len(candidates)==1;cv=BRepAdaptor_Curve(candidates[0].wrapped);spline=cv.BSpline()
    q_dist=GeomAPI_ProjectPointOnCurve(gp_Pnt(*q),spline,cv.FirstParameter(),cv.LastParameter()).LowerDistance()
    target_dist=GeomAPI_ProjectPointOnCurve(gp_Pnt(*target),spline,cv.FirstParameter(),cv.LastParameter()).LowerDistance()
    assert q_dist<1e-6 and target_dist>.25
    # A true coordinate change remains rejected under the same fixed tolerance.
    changed=b.Copy();pole=changed.Pole(14,11)
    changed.SetPole(14,11,gp_Pnt(pole.X(),pole.Y(),pole.Z()+2))
    badface=cq.Face(BRepBuilderAPI_MakeFace(changed,1e-7).Face());folder=out/'changed_pole';folder.mkdir()
    bad=CadAdapter(badface,folder)
    try:verify_dgm_uv(bad,bad.part,spec,folder,Trace(folder/'trace.json'))
    except RuntimeError as error:
        fail=error.nx_terrain_uv_g01b
        assert fail['failed_sample']['source_index']==1089
        assert abs(fail['failed_sample']['position_error_mm']-2)<1e-6
    else:raise AssertionError('True changed surface passed incorrectly')
    summary={'patch':PATCH,'status':'REAL_CAD_ROUNDTRIP_AND_EQUIVALENCE_CHECKS_PASSED',
      'NX_tested':False,'Parasolid_tested':False,'native_prt_created':False,
      'original_sha256':hashlib.sha256(old_path.read_bytes()).hexdigest(),
      'new_sha256':hashlib.sha256(new_path.read_bytes()).hexdigest(),
      'source_original_preserved':True,'old_edges':4,'new_LINE_edges':366,'faces':1,'boundary_loops':1,
      'same_degrees_knots_multiplicities_and_weights':True,'poles_compared':len(poles),
      'maximum_pole_difference_mm':max(poles),'surface_is_not_reconstructed_by_fit':True,
      'independent_edge_position_comparisons':samples,'maximum_edge_comparison_mm':max_line_error,
      'production_reference_points':r['checked_source_points'],'production_edge_probes':r['boundary_samples_checked'],
      'maximum_production_surface_error_mm':detail['max_position_error_mm'],
      'maximum_production_boundary_error_mm':detail['max_boundary_error_mm'],
      'NX_report_comparison':{'queried_point_distance_to_original_exact_boundary_mm':q_dist,
        'NX_returned_target_distance_to_original_exact_boundary_mm':target_dist,
        'NX_reported_distance_mm':fix['failure']['distance_mm'],
        'does_not_determine_whether_NX_curve_or_distance_solver_caused_difference':True},
      'negative_test_true_2mm_deformation_rejected_at_index':1089,
      'tolerance_mm':.25,'scope':'Source representations and comparison code tested in Open CASCADE. No test of the new source in NX. No terrain-to-house height datum confirmation.'}
    write_json(out/'ERGEBNIS_DGM_LINIENRAND_G01d.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
