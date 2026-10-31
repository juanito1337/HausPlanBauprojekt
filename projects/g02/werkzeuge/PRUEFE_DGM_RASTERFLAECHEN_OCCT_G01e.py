# -*- coding: utf-8 -*-
"""Actual CAD experiment: 8,282 bilinear faces sharing 16,747 real CAD edges.
Not the user's NX part, not a Parasolid/NX run. Source STEP remains unchanged.
A real 2 mm interior bulge in one cell must be rejected by the same validator.
"""
import argparse,hashlib,json,math,sys,time
from pathlib import Path
from types import SimpleNamespace as NS
B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung')]
import cadquery as cq
from OCP.BRep import BRep_Builder,BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex,BRepBuilderAPI_MakeEdge,BRepBuilderAPI_MakeWire,BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.BRepTools import BRepTools
from OCP.Geom import Geom_BezierSurface
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TopoDS import TopoDS_Shell,TopoDS
from OCP.TopExp import TopExp
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.gp import gp_Pnt
from gesamt.core import read_json,write_json
from gesamt.terrain_uv import verify_dgm_uv,prepared_reference,SOURCE_SHA256,REPORT
from gesamt.terrain_patches import Grid

SPEC=next(s for s in read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if s['id']=='DGM')


def split_surface(source_surface,bulge=False):
    nr,nc=source_surface.NbUPoles(),source_surface.NbVPoles()
    poles=[[source_surface.Pole(r+1,c+1) for c in range(nc)] for r in range(nr)]
    vertices={};edges={}
    def vertex(n):
        if n not in vertices:vertices[n]=BRepBuilderAPI_MakeVertex(poles[n[0]][n[1]]).Vertex()
        return vertices[n]
    def edge(a,b):
        key=tuple(sorted((a,b)))
        if key not in edges:edges[key]=BRepBuilderAPI_MakeEdge(vertex(key[0]),vertex(key[1])).Edge()
        e=edges[key]
        return e if a==key[0] else TopoDS.Edge_s(e.Reversed())
    sewing=BRepBuilderAPI_Sewing(1e-6,True,True,True,False)
    faces=[]
    for r in range(nr-1):
        for c in range(nc-1):
            n=[(r,c),(r+1,c),(r+1,c+1),(r,c+1)]
            if bulge and (r,c)==(13,10):
                arr=TColgp_Array2OfPnt(1,3,1,3)
                for i in range(3):
                    for j in range(3):
                        q=source_surface.Value(r+i/2,c+j/2)
                        dz=8. if (i,j)==(1,1) else 0.
                        arr.SetValue(i+1,j+1,gp_Pnt(q.X(),q.Y(),q.Z()+dz))
            else:
                arr=TColgp_Array2OfPnt(1,2,1,2)
                for i in range(2):
                    for j in range(2):arr.SetValue(i+1,j+1,poles[r+i][c+j])
            surface=Geom_BezierSurface(arr)
            maker=BRepBuilderAPI_MakeFace(surface,1e-7)
            if not maker.IsDone():raise RuntimeError('Face construction failed')
            face=maker.Face();faces.append(face);sewing.Add(face)
    sewing.Perform()
    shape=cq.Shape.cast(sewing.SewedShape())
    if not shape.isValid():raise RuntimeError('Constructed shared-edge CAD shell invalid')
    return shape


class Trace:
    def __init__(self,out):self.path=out/'trace.json';self.data={'NX_tested':False,'backend':'Open CASCADE'}
    def write(self):write_json(self.path,self.data)


class CadGridAdapter:
    def __init__(self,shape):
        self.shape=shape;self.part=NS(Tag=1,FullPath='OCCT_TEST_NOT_A_NATIVE_NX_PART')
        self.emap=TopTools_IndexedMapOfShape();TopExp.MapShapes_s(shape.wrapped,TopAbs_EDGE,self.emap)
        self.edge_shapes={};self.edge_objects={};self.surface={};self.face_shapes={};self.faces=[]
        for i in range(1,self.emap.Extent()+1):
            e=cq.Edge(TopoDS.Edge_s(self.emap.FindKey(i)));tag=100000+i
            ends=(e.startPoint().toTuple(),e.endPoint().toTuple())
            self.edge_shapes[tag]=e
            self.edge_objects[tag]=NS(Tag=tag,OwningPart=self.part,
                GetVertices=lambda v=ends:tuple(NS(X=p[0],Y=p[1],Z=p[2]) for p in v))
        for i,f in enumerate(shape.Faces()):
            tag=10+i;self.face_shapes[tag]=f;self.surface[tag]=BRep_Tool.Surface_s(f.wrapped)
            es=[self.edge_objects[100000+self.emap.FindIndex(e.wrapped)] for e in f.Edges()]
            self.faces.append(NS(Tag=tag,OwningPart=self.part,GetEdges=lambda es=es:list(reversed(es))))
        self.faces.reverse()  # Deliberately not original row-major order.
        self.body=NS(Tag=2,OwningPart=self.part,IsSolidBody=False,GetFaces=lambda:self.faces)
        self.part.Bodies=[self.body];self.validation_level='BASIS';self.operation='OCCT_EXPERIMENT'
        self.uf=NS(Modeling=NS(AskFaceUvMinmax=self.limits,EvaluateFace=self.evaluate,AskMinimumDist=self.distance))
        self.monitor=NS(check_cancel=lambda:None);self.evaluations=0;self.edge_calls=0;self.attributes={}
    def ensure_work(self,p):assert p is self.part
    def check_millimeters(self,p,context):self.ensure_work(p)
    def surface_box(self,b):
        q=self.shape.BoundingBox();return [q.xmin,q.ymin,q.zmin,q.xmax,q.ymax,q.zmax]
    def limits(self,tag):return BRepTools.UVBounds_s(self.face_shapes[tag].wrapped)
    def evaluate(self,tag,order,uv):
        assert order==0;self.evaluations+=1;p=self.surface[tag].Value(*uv)
        return NS(SrfPos=[p.X(),p.Y(),p.Z()])
    def distance(self,o1,o2,f1,q,f2,guess):
        assert o1==0 and f1==1 and f2==0 and o2 in self.edge_shapes
        self.edge_calls+=1;v=BRepBuilderAPI_MakeVertex(gp_Pnt(*q)).Vertex()
        d=BRepExtrema_DistShapeShape(v,self.edge_shapes[o2].wrapped);d.Perform()
        if not d.IsDone() or d.NbSolution()<1:raise RuntimeError('OCCT edge distance failed')
        def xyz(p):return [p.X(),p.Y(),p.Z()]
        return d.Value(),xyz(d.PointOnShape1(1)),xyz(d.PointOnShape2(1))
    def log(self,t):print(t,flush=True)
    def _set_user_attribute(self,p,k,v,label):self.attributes[k]=v
    def surface_area_mm2(self,b):raise AssertionError('BASIS must not integrate area')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True);args=parser.parse_args()
    out=Path(args.out);out.mkdir(parents=True,exist_ok=False)
    source=B/'umgebung'/SPEC['step_file'];before=hashlib.sha256(source.read_bytes()).hexdigest();assert before==SOURCE_SHA256
    real=cq.importers.importStep(str(source)).val();assert real.isValid() and len(real.Faces())==1
    surface=BRep_Tool.Surface_s(real.Faces()[0].wrapped)
    start=time.perf_counter();good_shape=split_surface(surface);adapter=CadGridAdapter(good_shape)
    good=out/'good';good.mkdir();result=verify_dgm_uv(adapter,adapter.part,SPEC,good,Trace(good))
    report=read_json(good/REPORT)
    assert result['faces']==8282 and result['checked_source_points']==16748
    assert adapter.edge_calls==50977
    assert report['max_position_error_mm']<1e-4 and report['max_boundary_error_mm']<1e-5
    good_summary={k:report[k] for k in ['nx_faces','covered_cells','unique_edges','interior_edges','exterior_edges',
        'checked_samples','face_point_comparisons','surface_evaluation_calls','edge_distance_calls',
        'boundary_samples_checked','shared_edge_samples_checked','max_position_error_mm','max_boundary_error_mm']}
    del adapter,good_shape
    bad=out/'real_interior_bulge';bad.mkdir();bad_shape=split_surface(surface,bulge=True);a=CadGridAdapter(bad_shape)
    try:verify_dgm_uv(a,a.part,SPEC,bad,Trace(bad))
    except RuntimeError as e:
        fail=e.nx_terrain_uv_g01b;sample=fail['failed_sample']
        assert sample['source_index']==8466+13*82+10
        assert math.isclose(sample['position_error_mm'],2.,abs_tol=1e-4)
    else:raise AssertionError('Real interior CAD deformation not rejected')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    summary={'status':'ACTUAL_OCCT_8282_FACES_PASS_REAL_2MM_BULGE_REJECTED','NX_tested':False,'Parasolid_tested':False,
        'user_imported_NX_part_tested':False,'source_sha256':before,'source_STEP_unchanged':True,
        'actual_CAD_model':'Constructed from actual imported STEP carrier as 8282 bilinear Bezier faces with shared edges',
        'counts':good_summary,'deformation_test':{'cell':[13,10],'actual_displacement_at_centre_mm':2.,
            'source_index':sample['source_index'],'measured_deviation_mm':sample['position_error_mm'],'rejected':True},
        'elapsed_seconds_OCCT_only':round(time.perf_counter()-start,3)}
    write_json(out/'ERGEBNIS_RASTERFLAECHEN_OCCT_G01e.json',summary);print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
