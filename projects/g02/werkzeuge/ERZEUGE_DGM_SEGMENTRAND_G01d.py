# -*- coding: utf-8 -*-
"""Offline export only, NOT an NX journal.

Keep the complete original bilinear surface. Represent each original 1-m
boundary interval as an exact 3D LINE with its own matching degree-1 pcurve.
No fitting, smoothing, downsampling, relocation or tolerance expansion.
Requires cadquery/OCP only in the offline generator, never in the NX journal.
"""
import argparse
import hashlib
from pathlib import Path
import json

ORIGINAL_SHA256='25a972e13beecdd9ebcf2a3420124803c78805263c806162a9785b84e167fd61'
BASE=Path(__file__).absolute().parents[1]


def make_segmented_face(surface):
    import cadquery as cq
    from OCP.BRep import BRep_Builder
    from OCP.BRepBuilderAPI import (BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,
                                    BRepBuilderAPI_MakeFace)
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.Geom2d import Geom2d_BSplineCurve
    from OCP.TColgp import TColgp_Array1OfPnt2d
    from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
    from OCP.TopLoc import TopLoc_Location
    from OCP.gp import gp_Pnt2d
    if (surface.UDegree(),surface.VDegree(),surface.NbUPoles(),surface.NbVPoles()) != (1,1,102,83):
        raise ValueError('Only the original 102 x 83 bilinear source is supported.')
    if list(surface.UKnots()) != list(range(102)) or list(surface.VKnots()) != list(range(83)):
        raise ValueError('Unexpected parameter knots: no source fitting permitted.')
    builder=BRep_Builder();wire=BRepBuilderAPI_MakeWire()
    # Closed boundary, exactly one edge per existing grid cell along the perimeter.
    sides=[((0,0),(0,1),82),((0,82),(1,0),101),
           ((101,82),(0,-1),82),((101,0),(-1,0),101)]
    for origin,direction,count in sides:
        for i in range(count):
            a=[origin[j]+i*direction[j] for j in range(2)]
            b=[origin[j]+(i+1)*direction[j] for j in range(2)]
            p0=surface.Value(*a);p1=surface.Value(*b)
            length=p0.Distance(p1)
            if length<=0:raise ValueError('Degenerate source boundary interval.')
            mk=BRepBuilderAPI_MakeEdge(p0,p1)
            if not mk.IsDone():raise RuntimeError('3D line construction failed.')
            edge=mk.Edge();curve=BRepAdaptor_Curve(edge)
            if abs(curve.FirstParameter())>1e-10 or abs(curve.LastParameter()-length)>1e-8:
                raise RuntimeError('Unexpected 3D line parameter range.')
            # A 2-pole linear pcurve uses the same physical-length parameter as
            # the 3D LINE. A unit-speed 2D line would use a different range.
            poles=TColgp_Array1OfPnt2d(1,2)
            poles.SetValue(1,gp_Pnt2d(*a));poles.SetValue(2,gp_Pnt2d(*b))
            knots=TColStd_Array1OfReal(1,2)
            knots.SetValue(1,0.0);knots.SetValue(2,length)
            mults=TColStd_Array1OfInteger(1,2)
            mults.SetValue(1,2);mults.SetValue(2,2)
            pc=Geom2d_BSplineCurve(poles,knots,mults,1,False)
            builder.UpdateEdge(edge,pc,surface,TopLoc_Location(),1e-7)
            wire.Add(edge)
            if not wire.IsDone():raise RuntimeError('Boundary wire construction failed.')
    mk=BRepBuilderAPI_MakeFace(surface,wire.Wire(),True)
    if not mk.IsDone():raise RuntimeError('Face with exact line boundary failed.')
    face=cq.Face(mk.Face())
    if not face.isValid() or len(face.Wires())!=1 or len(face.Edges())!=366:
        raise RuntimeError('Unexpected or invalid boundary representation.')
    if any(e.geomType()!='LINE' for e in face.Edges()):
        raise RuntimeError('Boundary is not exclusively made of exact lines.')
    return face


def export_new(path):
    import cadquery as cq
    from OCP.BRep import BRep_Tool
    source=BASE/'umgebung/CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step'
    if hashlib.sha256(source.read_bytes()).hexdigest()!=ORIGINAL_SHA256:
        raise ValueError('Original source hash differs.')
    path=Path(path).absolute()
    if path.exists():raise FileExistsError('No overwrite: '+str(path))
    path.parent.mkdir(parents=True,exist_ok=True)
    old=cq.importers.importStep(str(source)).val().Faces()[0]
    new=make_segmented_face(BRep_Tool.Surface_s(old.wrapped))
    cq.exporters.export(new,str(path))
    back=cq.importers.importStep(str(path)).val()
    if not back.isValid() or len(back.Faces())!=1 or len(back.Edges())!=366:
        raise RuntimeError('STEP roundtrip failed.')
    if any(e.geomType()!='LINE' for e in back.Edges()):
        raise RuntimeError('STEP roundtrip changed a boundary line type.')
    return {'original_sha256':ORIGINAL_SHA256,'new_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'file':path.name,'bytes':path.stat().st_size,'surface_faces':1,'closed_boundary_loops':1,
            'line_edges':366,'surface_fitted':False,'elevation_points_changed':False,'NX_tested':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True)
    args=parser.parse_args();print(json.dumps(export_new(args.out),indent=2))
