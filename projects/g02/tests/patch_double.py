"""Synthetic split-face test data, NOT an NX run or measured NX geometry."""
import math
from types import SimpleNamespace as NS
from gesamt.terrain_patches import Grid
from gesamt.terrain_uv import prepared_reference
from gesamt.core import write_json

class Trace:
    def __init__(self,path):self.path=path;self.data={}
    def write(self):write_json(self.path,self.data)

class PatchAdapter:
    def __init__(self,spec,rectangles,reverse=False):
        _,points=prepared_reference(spec);self.grid=Grid(points);self.spec=spec
        self.part=NS(Tag=1,FullPath='SYNTHETIC_ONLY_NOT_AN_NX_PART')
        self.records=[];self.faces=[];self.edges={};self.nodes={};self.rectangles={}
        self.transforms={}; self.deformation=lambda p,r,c,tag:list(p)
        self.bad_edge_distance=0.;self.bad_uv=False;self.swap=False;self.reverse=False
        self.bad_point=False;self.minimum_body_calls=0;self.eval_calls=0;self.edge_calls=0
        self.attrs={};self.logs=[];self.operation='SIMULATION_ONLY';self.validation_level='BASIS'
        def edge(a,b):
            key=tuple(sorted((a,b)))
            if key not in self.edges:
                tag=100000+len(self.edges);v=[self.grid.at(*a),self.grid.at(*b)]
                obj=NS(Tag=tag,OwningPart=self.part,GetVertices=lambda v=v:tuple(NS(X=p[0],Y=p[1],Z=p[2]) for p in v))
                self.edges[key]=obj;self.nodes[tag]=key
            return self.edges[key]
        for n,rect in enumerate(rectangles):
            tag=10+n;r0,r1,c0,c1=rect;self.rectangles[tag]=rect
            es=[]
            for r in range(r0,r1):
                es.append(edge((r,c0),(r+1,c0)));es.append(edge((r,c1),(r+1,c1)))
            for c in range(c0,c1):
                es.append(edge((r0,c),(r0,c+1)));es.append(edge((r1,c),(r1,c+1)))
            self.faces.append(NS(Tag=tag,OwningPart=self.part,GetEdges=lambda es=es:list(reversed(es)) if reverse else list(es)))
        if reverse:self.faces.reverse()
        self.body=NS(Tag=2,IsSolidBody=False,OwningPart=self.part,GetFaces=lambda:list(self.faces))
        self.part.Bodies=[self.body]
        self.uf=NS(Modeling=NS(AskFaceUvMinmax=self.limits,EvaluateFace=self.evaluate,AskMinimumDist=self.distance))
        self.monitor=NS(check_cancel=lambda:None)
    def ensure_work(self,p):assert p is self.part
    def check_millimeters(self,p,why):self.ensure_work(p)
    def surface_box(self,b):return list(self.spec['face_bounding_boxes_mm'][0])
    def _set_user_attribute(self,p,k,v,label):self.attrs[k]=v
    def log(self,t):self.logs.append(t)
    def limits(self,tag):return [0,float('nan'),0,1] if self.bad_uv else [0.,1.,0.,1.]
    def evaluate(self,tag,order,uv):
        assert order==0;self.eval_calls+=1
        r0,r1,c0,c1=self.rectangles[tag];a,b=uv
        if self.swap:a,b=b,a
        if self.reverse:a=1-a;b=1-b
        r=r0+a*(r1-r0);c=c0+b*(c1-c0)
        # UV extrapolation beyond 1e-10 only reflects floating point rounding.
        r=max(0,min(101,r));c=max(0,min(82,c))
        p=self.deformation(self.grid.at(r,c),r,c,tag)
        if self.bad_point:p=[float('nan'),0,0]
        return NS(SrfPos=p)
    def distance(self,obj1,tag,flag1,q,flag2,guess):
        if tag not in self.nodes:self.minimum_body_calls+=1;raise AssertionError('BODY/FACE distance forbidden')
        self.edge_calls+=1;a,b=(self.grid.at(*n) for n in self.nodes[tag]);d=[b[k]-a[k] for k in range(3)]
        t=min(1,max(0,sum((q[k]-a[k])*d[k] for k in range(3))/sum(x*x for x in d)))
        p=[a[k]+t*d[k] for k in range(3)];p[2]+=self.bad_edge_distance
        return math.dist(q,p),list(q),p
    def surface_area_mm2(self,b):raise AssertionError('Unexpected area integration')
