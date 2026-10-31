# -*- coding: utf-8 -*-
"""Independent CAD check using actual Open CASCADE geometry, not NX.

Runs the production G01c validator against a thin adapter over the imported
STEP face. Every evaluated position and boundary distance comes from OCCT.
A second real CAD surface with one deliberately displaced pole must fail.
No native NX .prt files are produced, no user files are changed.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS

BASE = Path(__file__).absolute().parents[1]
sys.path[:0] = [str(BASE), str(BASE/'umgebung')]
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
from gesamt.terrain_uv import verify_dgm_uv, SOURCE_SHA256
from gesamt.core import read_json, write_json


def xyz(p):
    return [p.X(), p.Y(), p.Z()]


class Trace:
    def __init__(self, path):
        self.path = path
        self.data = {'backend':'Open CASCADE, not NX', 'NX_tested':False}
    def write(self):
        write_json(self.path, self.data)


class CadAdapter:
    def __init__(self, face, out):
        self.face = face
        self.surface = BRep_Tool.Surface_s(face.wrapped)
        self.part = NS(Tag=1, FullPath='OCCT_TEST_ONLY_NOT_A_NATIVE_PRT')
        self.edges = face.Edges()
        self.edge_by_tag = {}
        edge_objects = []
        for i, edge in enumerate(self.edges):
            tag = 100+i
            self.edge_by_tag[tag] = edge
            ends = [edge.startPoint().toTuple(), edge.endPoint().toTuple()]
            vertices = tuple(NS(X=p[0],Y=p[1],Z=p[2]) for p in ends)
            edge_objects.append(NS(Tag=tag,OwningPart=self.part,GetVertices=lambda v=vertices:v))
        f = NS(Tag=10,OwningPart=self.part,GetEdges=lambda:edge_objects)
        self.body = NS(Tag=2,IsSolidBody=False,OwningPart=self.part,GetFaces=lambda:[f])
        self.part.Bodies = [self.body]
        self.uf = NS(Modeling=NS(AskFaceUvMinmax=self.limits,
                                EvaluateFace=self.evaluate,
                                AskMinimumDist=self.minimum_edge_distance))
        self.monitor = NS(check_cancel=lambda:None)
        self.validation_level = 'BASIS'
        self.operation = 'OCCT_ACTUAL_GEOMETRY'
        self.evaluations = 0
        self.boundary_calls = 0
        self.attributes = {}
        self.messages = []

    def ensure_work(self, part):
        if part is not self.part:raise AssertionError('Wrong harness part')

    def check_millimeters(self, part, context):
        # Harness: source STEP is the unchanged known millimetre export.
        self.ensure_work(part)

    def surface_box(self, body):
        b = self.face.BoundingBox()
        return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]

    def limits(self, tag):
        if tag != 10:raise AssertionError('Not the imported face')
        return self.surface.Bounds()

    def evaluate(self, tag, request, uv):
        if tag != 10 or request != 0:raise AssertionError('Not a position-only face evaluation')
        self.evaluations += 1
        return NS(SrfPos=xyz(self.surface.Value(*uv)))

    def minimum_edge_distance(self, obj1, obj2, flag1, q, flag2, seed):
        if obj1 != 0 or obj2 not in self.edge_by_tag or flag1 != 1 or flag2 != 0:
            raise AssertionError('Only the assigned real edge may be queried')
        self.boundary_calls += 1
        vertex = BRepBuilderAPI_MakeVertex(gp_Pnt(*q)).Vertex()
        measure = BRepExtrema_DistShapeShape(vertex,self.edge_by_tag[obj2].wrapped)
        measure.Perform()
        if not measure.IsDone() or measure.NbSolution()<1:
            raise RuntimeError('Actual OCCT edge distance failed')
        return measure.Value(), xyz(measure.PointOnShape1(1)), xyz(measure.PointOnShape2(1))

    def log(self, message):self.messages.append(message)
    def _set_user_attribute(self, part, key, value, label):
        self.ensure_work(part);self.attributes[key]=value
    def surface_area_mm2(self, body):
        raise AssertionError('BASIS must not invoke area integration')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    args = parser.parse_args()
    out = Path(args.out).absolute();out.mkdir(parents=True,exist_ok=False)
    job=read_json(BASE/'umgebung/data/IMPORTAUFTRAG_R09.json')
    spec=next(p for p in job['parts'] if p['id']=='DGM')
    source=BASE/'umgebung'/spec['step_file']
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    assert before==SOURCE_SHA256
    imported=cq.importers.importStep(str(source)).val()
    assert imported.isValid() and len(imported.Faces())==1
    face=imported.Faces()[0]
    surface=BRep_Tool.Surface_s(face.wrapped)
    assert [surface.UDegree(),surface.VDegree()]==[1,1]
    assert [surface.NbUPoles(),surface.NbVPoles()]==[102,83]
    assert list(surface.UKnots())==list(range(102))
    assert list(surface.VKnots())==list(range(83))
    good=out/'original';good.mkdir()
    adapter=CadAdapter(face,good);trace=Trace(good/'trace.json')
    result=verify_dgm_uv(adapter,adapter.part,spec,good,trace)
    assert result['checked_source_points']==16748
    assert result['boundary_samples_checked']==736+3*len(face.Edges())
    assert adapter.evaluations==16753 and adapter.boundary_calls==736+3*len(face.Edges())
    check=read_json(good/'DGM_FLAECHENPRUEFUNG_G01e.json')
    assert check['max_position_error_mm']<1e-6
    assert check['max_boundary_error_mm']<1e-6
    assert check['negative_control']['correctly_not_accepted']

    # Deform a real interior pole of a copy. Corners, boundary and original file
    # stay unchanged. The production checker must reject index 1089.
    changed=surface.Copy()
    original_pole=changed.Pole(14,11)
    changed.SetPole(14,11,gp_Pnt(original_pole.X(),original_pole.Y(),original_pole.Z()+2.0))
    changed_face=cq.Face(BRepBuilderAPI_MakeFace(changed,1e-7).Face())
    assert changed_face.isValid()
    bad=out/'displaced_pole';bad.mkdir()
    other=CadAdapter(changed_face,bad);bad_trace=Trace(bad/'trace.json')
    try:
        verify_dgm_uv(other,other.part,spec,bad,bad_trace)
    except RuntimeError as error:
        failure=error.nx_terrain_uv_g01b
        assert failure['failed_sample']['source_index']==1089
        assert math.isclose(failure['failed_sample']['position_error_mm'],2.,abs_tol=1e-6)
    else:
        raise AssertionError('Changed actual surface was not rejected')
    after=hashlib.sha256(source.read_bytes()).hexdigest();assert after==before
    summary={'status':'OCCT_ORIGINAL_PASSED_AND_REAL_DEFORMATION_REJECTED',
        'NX_tested':False,'Parasolid_tested':False,'native_prt_created':False,
        'source':str(source.relative_to(BASE)),'source_sha256':before,
        'source_unchanged':before==after,
        'surface_type':surface.DynamicType().Name(),
        'source_degree':[surface.UDegree(),surface.VDegree()],
        'source_poles':[surface.NbUPoles(),surface.NbVPoles()],
        'source_parameter_limits':list(surface.Bounds()),'actual_edges':len(face.Edges()),
        'reference_points_checked':16748,'actual_surface_evaluations':adapter.evaluations,
        'actual_edge_distance_queries':adapter.boundary_calls,
        'maximum_position_error_mm':check['max_position_error_mm'],
        'maximum_edge_error_mm':check['max_boundary_error_mm'],
        'negative_control':check['negative_control'],
        'real_modified_surface_test':{'changed_pole':[14,11],'delta_z_mm':2.,
            'detected_index':failure['failed_sample']['source_index'],
            'detected_error_mm':failure['failed_sample']['position_error_mm'],
            'rejected':True},
        'limitations':'Validates the actual exported source and production Python comparison using OCCT positions/edges; does not test NX bindings, STEP importer, or the saved user NX part.'}
    write_json(out/'ERGEBNIS_DGM_UV_OCCT.json',summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
