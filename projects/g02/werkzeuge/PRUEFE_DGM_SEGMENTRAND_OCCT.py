# -*- coding: utf-8 -*-
"""Real CAD regression, NOT an NX run. Never modifies the shipped STEP source.
Builds a valid one-face boundary with 285 edges on the very same source surface.
It is an artificial split fixture, NOT the user's unseen 285-edge NX part.
Also checks a real inner hole and a displaced internal pole are rejected.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'werkzeuge')]
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace
from OCP.BRepLib import BRepLib
from OCP.Geom2d import Geom2d_Line
from OCP.gp import gp_Pnt2d,gp_Dir2d,gp_Pnt
from gesamt import PATCH
from gesamt.terrain_uv import verify_dgm_uv,SOURCE_SHA256,REPORT
from gesamt.core import read_json,write_json
from PRUEFE_DGM_UV_OCCT import CadAdapter,Trace


def wire_from_segments(surface,configs):
    builder=BRepBuilderAPI_MakeWire()
    for origin,direction,length,n in configs:
        curve=Geom2d_Line(gp_Pnt2d(*origin),gp_Dir2d(*direction))
        stops=[length*(i/n) for i in range(n+1)]
        for a,b in zip(stops,stops[1:]):
            edge=BRepBuilderAPI_MakeEdge(curve,surface,a,b).Edge()
            builder.Add(edge)
    if not builder.IsDone():raise RuntimeError('CAD-Testdraht nicht hergestellt.')
    wire=builder.Wire()
    if not BRepLib.BuildCurves3d_s(wire,1e-7):raise RuntimeError('CAD-Testkurven nicht hergestellt.')
    if not cq.Wire(wire).isValid():raise RuntimeError('CAD-Testdraht ungueltig.')
    return wire


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True)
    args=parser.parse_args();out=Path(args.out).absolute();out.mkdir(parents=True,exist_ok=False)
    job=read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json');spec=next(x for x in job['parts'] if x['id']=='DGM')
    src=B/'umgebung'/spec['step_file'];before=hashlib.sha256(src.read_bytes()).hexdigest()
    assert before==SOURCE_SHA256
    original_src=B/'umgebung/CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step'
    imported=cq.importers.importStep(str(original_src)).val();face=imported.Faces()[0]
    assert imported.isValid() and len(imported.Faces())==1 and len(face.Edges())==4
    surface=BRep_Tool.Surface_s(face.wrapped)
    configs=[((0,0),(0,1),82,64),((0,82),(1,0),101,78),
             ((101,82),(0,-1),82,64),((101,0),(-1,0),101,79)]
    wire=wire_from_segments(surface,configs)
    split=cq.Face(BRepBuilderAPI_MakeFace(surface,wire,True).Face())
    assert split.isValid() and len(split.Edges())==285 and len(split.Wires())==1
    # Output fixture retained for technical reproducibility, not supplied as replacement terrain.
    cq.exporters.export(split,str(out/'TESTKOPIE_285_RANDKANTEN.step'))
    rows=[]
    for name,good_face in [('original_4',face),('synthetic_split_285',split)]:
        folder=out/name;folder.mkdir();adapter=CadAdapter(good_face,folder);trace=Trace(folder/'trace.json')
        check=verify_dgm_uv(adapter,adapter.part,spec,folder,trace)
        report=read_json(folder/REPORT)
        assert check['checked_source_points']==16748
        assert report['original_boundary_samples_checked']==736
        assert report['actual_edges_with_distance_checks']==len(good_face.Edges())
        assert report['max_position_error_mm']<1e-6
        assert report['max_boundary_error_mm']<1e-4
        assert adapter.boundary_calls==736+3*len(good_face.Edges())
        rows.append({'case':name,'valid_CAD_face':True,'actual_edges':len(good_face.Edges()),
                     'face_count':1,'checked_points':16748,'boundary_queries':adapter.boundary_calls,
                     'max_position_error_mm':report['max_position_error_mm'],
                     'max_boundary_error_mm':report['max_boundary_error_mm'],
                     'side_counts':{s['side']:s['edge_count'] for s in report['boundary_chains']['sides']}})
    # Interior hole: exact same underlying surface; coverage check must not accept
    # a merely matching untrimmed carrier surface as the whole original face.
    inner=wire_from_segments(surface,[((20,20),(1,0),1,1),((21,20),(0,1),1,1),
                                      ((21,21),(-1,0),1,1),((20,21),(0,-1),1,1)])
    inner.Reverse()
    maker=BRepBuilderAPI_MakeFace(surface,wire,True);maker.Add(inner)
    hole=cq.Face(maker.Face());assert hole.isValid() and len(hole.Wires())==2
    folder=out/'inner_hole';folder.mkdir();a=CadAdapter(hole,folder)
    try:verify_dgm_uv(a,a.part,spec,folder,Trace(folder/'trace.json'))
    except RuntimeError as e:
        hole_failure={'rejected':True,'actual_edges':len(hole.Edges()),'error':str(e)}
    else:raise AssertionError('Inner hole was not rejected.')
    changed=surface.Copy();p=changed.Pole(14,11)
    changed.SetPole(14,11,gp_Pnt(p.X(),p.Y(),p.Z()+2))
    changed_face=cq.Face(BRepBuilderAPI_MakeFace(changed,1e-7).Face());assert changed_face.isValid()
    folder=out/'changed_pole';folder.mkdir();a=CadAdapter(changed_face,folder)
    try:verify_dgm_uv(a,a.part,spec,folder,Trace(folder/'trace.json'))
    except RuntimeError as e:
        detail=e.nx_terrain_uv_g01b
        assert detail['failed_sample']['source_index']==1089
        assert abs(detail['failed_sample']['position_error_mm']-2)<1e-6
        deform_failure={'rejected':True,'failed_index':1089,'displacement_mm':2.}
    else:raise AssertionError('Actual 2 mm deformation not rejected.')
    after=hashlib.sha256(src.read_bytes()).hexdigest();assert before==after
    summary={'patch':PATCH,'status':'REAL_OCCT_FIXTURES_CHECKED','NX_tested':False,
             'native_prt_created':False,'source_sha256':before,'source_unchanged':True,
             'cases':rows,'negative_tests':{'interior_hole':hole_failure,'changed_pole':deform_failure},
             'limits':'The 285-edge split is an artificial CAD fixture, not the actual NX output. Finite coordinate and edge probes are not a full mathematical surface identity proof.'}
    write_json(out/'ERGEBNIS_DGM_SEGMENTRAND_OCCT.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
