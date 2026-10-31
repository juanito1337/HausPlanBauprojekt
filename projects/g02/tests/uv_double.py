"""Synthetic NX binding extension for the DGM checker. Not actual NX results."""
import contextlib
import math
from types import SimpleNamespace as NS
from unittest.mock import patch


def install_uv_double(env):
    from fake_nx import Body
    original_active=env.active
    control=NS(limits=[0.,101.,0.,82.],swap=False,ru=False,rv=False,
               evaluations=0,edge_queries=0,body_queries=0,edges=4,
               transform=lambda p,uv:list(p),boundary_error=0.,boundary_bad=False,
               vertex_offset=0.,uv_failure=None,face_type_invalid=False,
               edge_ranges=None,edge_records_transform=lambda r:r,line_transform=lambda line:list(line))
    cache={};edgecache={}
    original_distance=env.uf.Modeling.AskMinimumDist

    def body_of(face):
        body=env.objects[int(face)//10000]
        return body
    def evaluate(face,mode,uv):
        assert mode==0
        control.evaluations+=1
        if control.uv_failure is not None:raise RuntimeError(control.uv_failure)
        b=body_of(face);ref=b._reference;nr,nc=ref['grid_shape'];pts=ref['samples_mm']
        u0,u1,v0,v1=control.limits
        a=(uv[0]-u0)/(u1-u0);c=(uv[1]-v0)/(v1-v0)
        if control.ru:a=1.-a
        if control.rv:c=1.-c
        if control.swap:a,c=c,a
        ar=min(nr-1,max(0.,a*(nr-1)));ac=min(nc-1,max(0.,c*(nc-1)))
        r=min(nr-2,int(ar));col=min(nc-2,int(ac));du=ar-r;dv=ac-col
        q=[(1-du)*(1-dv)*pts[r*nc+col][k]+du*(1-dv)*pts[(r+1)*nc+col][k]+
           (1-du)*dv*pts[r*nc+col+1][k]+du*dv*pts[(r+1)*nc+col+1][k] for k in range(3)]
        return NS(SrfPos=control.transform(q,list(uv)))

    def near(q,line):
        best=(float('inf'),None)
        for a,b in zip(line,line[1:]):
            d=[b[i]-a[i] for i in range(3)]
            t=max(0.,min(1.,sum((q[i]-a[i])*d[i] for i in range(3))/sum(x*x for x in d)))
            p=[a[i]+t*d[i] for i in range(3)];distance=math.dist(p,q)
            if distance<best[0]:best=(distance,p)
        return best

    def distance(n,tag,g1,q,g2,guess):
        if tag not in edgecache:
            control.body_queries+=1
            return original_distance(n,tag,g1,q,g2,guess)
        control.edge_queries+=1
        _,line=edgecache[tag]
        d,p=near(q,line)
        if control.boundary_error:
            p=[p[0],p[1],p[2]+control.boundary_error];d=math.dist(p,q)
        if control.boundary_bad:return (0.,list(q),[0,0,0])
        return (d,list(q),p)

    env.uf.Modeling.AskFaceUvMinmax=lambda tag:list(control.limits)
    env.uf.Modeling.EvaluateFace=evaluate
    env.uf.Modeling.AskMinimumDist=distance

    @contextlib.contextmanager
    def active():
        with original_active():
            old_faces=Body.GetFaces
            def faces(body):
                if getattr(body,'_reference',{}).get('grid_shape')!=[102,83]:return old_faces(body)
                result=old_faces(body)
                for f in result:
                    def get_edges(body=body):
                        from gesamt.terrain_uv import sides
                        nr,nc=body._reference['grid_shape'];pts=body._reference['samples_mm']
                        sl=sides(pts,nr,nc)
                        output=[]
                        records=[]
                        if control.edge_ranges is None:
                            ranges=[(k%4,0.,1.) for k in range(control.edges)]
                        else:ranges=control.edge_ranges
                        from gesamt.terrain_boundary import SourceSide
                        for k,(side_no,ta,tb) in enumerate(ranges):
                            name,source_line=sl[side_no];tag=body.Tag*1000000+100000+k
                            ss=SourceSide(name,source_line)
                            lo,hi=min(ta,tb),max(ta,tb)
                            line=[ss.at(lo)]+[p for t,p in zip(ss.stations,ss.points) if lo<t<hi]+[ss.at(hi)]
                            if ta>tb:line.reverse()
                            records.append(dict(tag=tag,endpoints=[list(line[0]),list(line[-1])],
                                                line=control.line_transform(line)))
                        for rec in control.edge_records_transform(records):
                            tag=rec['tag'];line=rec['line'];ends=rec['endpoints']
                            edgecache[tag]=(body,line)
                            def vertices(ends=ends):
                                return tuple(NS(X=p[0]+control.vertex_offset,Y=p[1],Z=p[2]) for p in ends)
                            output.append(NS(Tag=tag,OwningPart=body.OwningPart,GetVertices=vertices))
                        return output
                    f.GetEdges=get_edges
                return result
            with patch.object(Body,'GetFaces',faces):yield env
    env.active=active
    control.old_distance=original_distance
    control.closest_on_polyline=near
    return control
