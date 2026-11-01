"""Affine bilinear grid reader; conforming uniform local TIN approximation."""
import json
import math
from .geometry import finite, plane, surface_mesh


class Grid:
    def __init__(self, data, z_offset=0):
        self.nu,self.nv=data['shape'];self.nodes=[list(p) for p in data['nodes_mm']]
        if min(self.nu,self.nv)<2 or len(self.nodes)!=self.nu*self.nv:raise ValueError('Invalid grid shape')
        finite(z_offset)
        for p in self.nodes:finite(*p);p[2]+=z_offset
        self.origin=self.nodes[0];self.du=[self.nodes[self.nv][k]-self.origin[k] for k in range(2)]
        self.dv=[self.nodes[1][k]-self.origin[k] for k in range(2)]
        self.det=self.du[0]*self.dv[1]-self.du[1]*self.dv[0]
        if abs(self.det)<1e-6:raise ValueError('Degenerate grid')
        for i in range(self.nu):
            for j in range(self.nv):
                if math.dist(self.node(i,j)[:2],self.xy(i,j))>0.001:raise ValueError('Nonaffine grid')

    def node(self,i,j):return self.nodes[i*self.nv+j]

    def xy(self,u,v):return [self.origin[k]+u*self.du[k]+v*self.dv[k] for k in range(2)]

    def uv(self,p):
        finite(*p);x=p[0]-self.origin[0];y=p[1]-self.origin[1]
        return ((x*self.dv[1]-y*self.dv[0])/self.det,(self.du[0]*y-self.du[1]*x)/self.det)

    def sample(self,p):
        u,v=self.uv(p)
        if not (0<=u<=self.nu-1 and 0<=v<=self.nv-1):raise ValueError('Outside DGM; no extrapolation')
        i=min(int(u),self.nu-2);j=min(int(v),self.nv-2);a=u-i;b=v-j
        return ((1-a)*(1-b)*self.node(i,j)[2]+a*(1-b)*self.node(i+1,j)[2]+
                a*b*self.node(i+1,j+1)[2]+(1-a)*b*self.node(i,j+1)[2])

    def cross_term(self,i,j):
        return self.node(i,j)[2]-self.node(i+1,j)[2]-self.node(i,j+1)[2]+self.node(i+1,j+1)[2]

    def error_bound(self,n):
        if type(n)!=int or n<1:raise ValueError('Invalid subdivision')
        return max(abs(self.cross_term(i,j)) for i in range(self.nu-1) for j in range(self.nv-1))/(4*n*n)

    def subdivisions(self,target_mm):
        finite(target_mm)
        if target_mm<=0:raise ValueError('Invalid TIN tolerance')
        return max(1,math.ceil(math.sqrt(self.error_bound(1)/target_mm)))

    def triangles(self, subdivisions=1, bbox=None):
        n=subdivisions
        if type(n)!=int or n<1:raise ValueError('Invalid subdivision')
        imin=jmin=0;imax=self.nu-1;jmax=self.nv-1
        if bbox is not None:
            x0,y0,x1,y1=bbox;uv=[self.uv(p) for p in [(x0,y0),(x0,y1),(x1,y0),(x1,y1)]]
            imin=max(0,math.floor(min(p[0] for p in uv)));imax=min(imax,math.ceil(max(p[0] for p in uv)))
            jmin=max(0,math.floor(min(p[1] for p in uv)));jmax=min(jmax,math.ceil(max(p[1] for p in uv)))
        out=[]
        def point(i,j,a,b):
            z=((1-a)*(1-b)*self.node(i,j)[2]+a*(1-b)*self.node(i+1,j)[2]+
               a*b*self.node(i+1,j+1)[2]+(1-a)*b*self.node(i,j+1)[2])
            return self.xy(i+a,j+b)+[z]
        for i in range(imin,imax):
            for j in range(jmin,jmax):
                for a in range(n):
                    for b in range(n):
                        p,q,r,s=[point(i,j,u/n,v/n) for u,v in [(a,b),(a+1,b),(a+1,b+1),(a,b+1)]]
                        out.extend([[p,q,r],[p,r,s]])
        return out

    def contact_on_boundary(self,polygons):
        return any(min(u,v,self.nu-1-u,self.nv-1-v)<1e-7
                   for poly in polygons for u,v in (self.uv(p) for p in poly))


def closed_terrain(triangles, bottom_z):
    """Artificial closed study soil, not geological strata or the source Sheet."""
    finite(bottom_z)
    if any(p[2]<=bottom_z for tri in triangles for p in tri):raise ValueError('Soil bottom intersects terrain')
    return surface_mesh([([p[:2] for p in tri],(0,0,bottom_z),plane(tri)) for tri in triangles])


def read_json(path):
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('Duplicate JSON key '+k)
            out[k]=v
        return out
    def invalid(v):raise ValueError('Nonfinite JSON '+v)
    return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=invalid)
