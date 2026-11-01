"""Exact piecewise affine integration and closed conforming surface meshes (mm).

TIN approximation error is separate from numerical topology tolerance. Partitions
are convex, but their union may be nonconvex. No 3D Boolean engine is assumed.
"""
import math
from collections import defaultdict

TOPOLOGY_MM = 1e-6


def finite(*values):
    if any(not math.isfinite(float(v)) for v in values):
        raise ValueError('Nonfinite geometry')


def value(plane, p):
    return plane[0]*p[0] + plane[1]*p[1] + plane[2]


def subtract(a, b):
    return tuple(x-y for x,y in zip(a,b))


def area(poly):
    if len(poly)<3:return 0.0
    a=poly[0]
    return sum((p[0]-a[0])*(q[1]-a[1])-(q[0]-a[0])*(p[1]-a[1])
               for p,q in zip(poly[1:],poly[2:]))/2


def clean(poly):
    out=[]
    for p in poly:
        if not out or math.dist(p,out[-1])>TOPOLOGY_MM:out.append(tuple(p))
    if len(out)>1 and math.dist(out[0],out[-1])<=TOPOLOGY_MM:out.pop()
    if area(out)<0:out.reverse()
    return out if abs(area(out))>1e-10 else []


def clip_polygon(poly, halfspace):
    """Sutherland-Hodgman: retain a*x+b*y+c >= 0; no bounding mask."""
    if not poly:return []
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        fp=value(halfspace,p);fq=value(halfspace,q)
        if fp>=0:out.append(p)
        if (fp<0) != (fq<0):
            t=fp/(fp-fq)
            out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return clean(out)


def plane(triangle):
    a,b,c=triangle;finite(*(v for p in triangle for v in p))
    dx=b[0]-a[0];dy=b[1]-a[1];ex=c[0]-a[0];ey=c[1]-a[1]
    det=dx*ey-dy*ex
    if abs(det)<1e-12:raise ValueError('Degenerate terrain triangle')
    u=((b[2]-a[2])*ey-(c[2]-a[2])*dy)/det
    v=(dx*(c[2]-a[2])-ex*(b[2]-a[2]))/det
    return (u,v,a[2]-u*a[0]-v*a[1])


def integrate_polygon(poly, affine):
    """Exact integral of an affine height over a convex CCW polygon."""
    if len(poly)<3:return 0.0
    a=poly[0];total=0.0
    for b,c in zip(poly[1:],poly[2:]):
        ar=((b[0]-a[0])*(c[1]-a[1])-(c[0]-a[0])*(b[1]-a[1]))/2
        total+=ar*(value(affine,a)+value(affine,b)+value(affine,c))/3
    return total


def partitions(triangles, envelopes, lower=True, domain=(), shift=0):
    """Partition terrain against max lower/min upper envelope; preserve full footprint."""
    out=[]
    for tri in triangles:
        terrain=plane(tri);terrain=(terrain[0],terrain[1],terrain[2]+shift)
        for k,env in enumerate(envelopes):
            poly=clean([tuple(p[:2]) for p in tri])
            for half in domain:poly=clip_polygon(poly,half)
            for j,other in enumerate(envelopes):
                if j!=k:
                    poly=clip_polygon(poly,subtract(env,other) if lower else subtract(other,env))
            bottom,top=(env,terrain) if lower else (terrain,env)
            poly=clip_polygon(poly,subtract(top,bottom))
            if poly and integrate_polygon(poly,subtract(top,bottom))>1e-9:
                out.append((poly,bottom,top))
    return out


def _key(p):
    return tuple(round(x/TOPOLOGY_MM) for x in p)


def surface_mesh(parts):
    """Weld XY, split T-junctions, omit internal walls, then orient a closed shell.

    All partition vertices lying on an edge are inserted before face fans. This
    is required at clipping/envelope intersections and is not just vertex welding.
    """
    if not parts:return {'vertices':[],'faces':[]}
    xy={_key(p):tuple(p) for poly,_,_ in parts for p in poly}
    points=list(xy.values());vertices=[];faces=[];lookup={};edges=defaultdict(list)
    def vertex(p):
        key=_key(p)
        if key not in lookup:lookup[key]=len(vertices);vertices.append(list(p))
        return lookup[key]
    def face(a,b,c):
        if len({a,b,c})==3:
            u=subtract(vertices[b],vertices[a]);v=subtract(vertices[c],vertices[a])
            cross=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
            if sum(x*x for x in cross)>1e-18:faces.append([a,b,c])
    # Spatial buckets reduce the conforming-edge search on local refined TINs.
    bucket=250.0;bins=defaultdict(list)
    for p in points:bins[(math.floor(p[0]/bucket),math.floor(p[1]/bucket))].append(p)
    for poly,lo,hi in parts:
        ring=[]
        for a,b in zip(poly,poly[1:]+poly[:1]):
            dx=b[0]-a[0];dy=b[1]-a[1];d2=dx*dx+dy*dy
            # Quantized representatives may differ by tiny roundoff from a/b.
            # Never infer endpoint membership from a dimensionless t threshold:
            # on a short edge that can omit a real corner altogether.
            akey,bkey=_key(a),_key(b)
            ring.append(xy[akey])
            candidates=[]
            for ix in range(math.floor((min(a[0],b[0])-TOPOLOGY_MM)/bucket),math.floor((max(a[0],b[0])+TOPOLOGY_MM)/bucket)+1):
                for iy in range(math.floor((min(a[1],b[1])-TOPOLOGY_MM)/bucket),math.floor((max(a[1],b[1])+TOPOLOGY_MM)/bucket)+1):
                    for p in bins[(ix,iy)]:
                        pkey=_key(p)
                        if pkey in (akey,bkey):continue
                        t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d2
                        if 0<t<1 and abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)<=TOPOLOGY_MM*math.sqrt(d2):
                            candidates.append((t,pkey))
            ring.extend(xy[key] for _,key in sorted(candidates))
        # Already conforming triangles need no centroid or extra planar facets.
        # Longer rings retain the center fan so every collinear edge split stays.
        low=[vertex((*p,value(lo,p))) for p in ring]
        high=[vertex((*p,value(hi,p))) for p in ring]
        if len(ring)==3:
            face(high[0],high[1],high[2]);face(low[0],low[2],low[1])
        else:
            center=(sum(p[0] for p in poly)/len(poly),sum(p[1] for p in poly)/len(poly))
            lc=vertex((*center,value(lo,center)));hc=vertex((*center,value(hi,center)))
            for i in range(len(ring)):
                j=(i+1)%len(ring);face(hc,high[i],high[j]);face(lc,low[j],low[i])
        for i,p in enumerate(ring):
            j=(i+1)%len(ring)
            key=tuple(sorted((_key(p),_key(ring[j]))))
            edges[key].append((low[i],low[j],high[i],high[j]))
    for rows in edges.values():
        if len(rows)>2:raise ValueError('Overlapping surface partition')
        if len(rows)==1:
            a,b,c,d=rows[0];face(a,b,d);face(a,d,c)
    mesh={'vertices':vertices,'faces':faces}
    validate_mesh(mesh)
    return mesh


def mesh_volume(mesh):
    if not mesh['vertices']:return 0.0
    origin=mesh['vertices'][0];total=0.0
    for face in mesh['faces']:
        a,b,c=[subtract(mesh['vertices'][i],origin) for i in face]
        total+=(a[0]*(b[1]*c[2]-b[2]*c[1])+a[1]*(b[2]*c[0]-b[0]*c[2])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
    return total


def mesh_components(mesh):
    """Deterministic connected shells with compact, independent vertex indices."""
    neighbors=defaultdict(set)
    for face in mesh['faces']:
        for a,b in zip(face,face[1:]+face[:1]):neighbors[a].add(b);neighbors[b].add(a)
    todo=set(neighbors);groups=[]
    while todo:
        seen=set();pending=[min(todo)]
        while pending:
            v=pending.pop()
            if v not in seen:seen.add(v);pending.extend(neighbors[v]-seen)
        todo-=seen;indices=sorted(seen);mapping={old:new for new,old in enumerate(indices)}
        groups.append({'vertices':[list(mesh['vertices'][i]) for i in indices],
                       'faces':[[mapping[i] for i in face] for face in mesh['faces'] if face[0] in seen]})
    return groups


def validate_mesh(mesh):
    vertices=mesh['vertices'];faces=mesh['faces'];edges=defaultdict(list)
    for p in vertices:
        if len(p)!=3:raise ValueError('Invalid vertex')
        finite(*p)
    if not faces:raise ValueError('Empty solid')
    for face in faces:
        if len(face)!=3 or len(set(face))!=3:raise ValueError('Degenerate face')
        if any(type(i)!=int or not 0<=i<len(vertices) for i in face):raise ValueError('Invalid index')
        a,b,c=[vertices[i] for i in face];u=subtract(b,a);v=subtract(c,a)
        if sum(x*x for x in (u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]))<=1e-18:
            raise ValueError('Zero area face')
        for a,b in zip(face,face[1:]+face[:1]):edges[tuple(sorted((a,b)))].append((a,b))
    if any(len(rows)!=2 or rows[0]!=rows[1][::-1] for rows in edges.values()):
        raise ValueError('Mesh is not closed with opposite edge incidence')
    # Each vertex link must be a single cycle, rejecting shells touching at a point.
    links=defaultdict(lambda:defaultdict(set))
    for f in faces:
        for i in range(3):
            v,a,b=f[i],f[(i+1)%3],f[(i+2)%3]
            links[v][a].add(b);links[v][b].add(a)
    for link in links.values():
        if any(len(neighbors)!=2 for neighbors in link.values()):raise ValueError('Nonmanifold vertex')
        seen=set();pending=[next(iter(link))]
        while pending:
            v=pending.pop()
            if v not in seen:seen.add(v);pending.extend(link[v]-seen)
        if len(seen)!=len(link):raise ValueError('Disconnected vertex link')
    volume=mesh_volume(mesh)
    if volume<=0 or not math.isfinite(volume):raise ValueError('Nonpositive oriented volume')
    components=mesh_components(mesh);volumes=[mesh_volume(part) for part in components]
    if any(v<=0 for v in volumes):raise ValueError('Nonpositive oriented component')
    if abs(sum(volumes)-volume)>max(1e-3,volume*1e-9):raise ValueError('Component volume mismatch')
    return {'closed':True,'volume_mm3':volume,'edge_count':len(edges),
            'expected_body_count':len(components),'component_volumes_mm3':volumes}


def excavation(triangles, length, width, formation, ratio=1, origin=(0,0),
               tangent=(1,0), normal=(0,1), error_mm=0):
    finite(length,width,formation,ratio,error_mm,*origin,*tangent,*normal)
    if min(length,width,ratio)<=0 or error_mm<0:raise ValueError('Invalid field dimensions')
    if abs(math.hypot(*tangent)-1)>1e-8 or abs(math.hypot(*normal)-1)>1e-8 or abs(sum(a*b for a,b in zip(tangent,normal)))>1e-8:
        raise ValueError('Field basis must be orthonormal')
    local=[]
    for tri in triangles:
        local.append([((p[0]-origin[0])*tangent[0]+(p[1]-origin[1])*tangent[1],
                       (p[0]-origin[0])*normal[0]+(p[1]-origin[1])*normal[1],p[2]) for p in tri])
    roofs=[(0,0,formation),(0,1/ratio,formation-width/ratio),
           (-1/ratio,0,formation),(1/ratio,0,formation-length/ratio)]
    def get(shift):return partitions(local,roofs,domain=[(0,1,0)],shift=shift)
    parts=get(0)
    def vol(ps):return sum(integrate_polygon(p,subtract(hi,lo)) for p,lo,hi in ps)
    volume=vol(parts);mesh=surface_mesh(parts)
    for p in mesh['vertices']:
        s,r=p[:2];p[0]=origin[0]+s*tangent[0]+r*normal[0];p[1]=origin[1]+s*tangent[1]+r*normal[1]
    if tangent[0]*normal[1]-tangent[1]*normal[0]<0:
        for f in mesh['faces']:f.reverse()
    if volume and abs(mesh_volume(mesh)-volume)>max(1e-3,volume*1e-9):raise ValueError('Mesh/integral volume mismatch')
    footprints=[[[origin[0]+p[0]*tangent[0]+p[1]*normal[0],origin[1]+p[0]*tangent[1]+p[1]*normal[1]] for p in poly] for poly,_,_ in parts]
    components=mesh_components(mesh)
    low_parts=get(-error_mm);upper_parts=get(error_mm)
    upper_points=[[origin[0]+p[0]*tangent[0]+p[1]*normal[0],origin[1]+p[0]*tangent[1]+p[1]*normal[1]]
                  for poly,_,_ in upper_parts for p in poly]
    return {'mesh':mesh,'mesh_components':components,'expected_body_count':len(components),
            'component_volumes_mm3':[mesh_volume(part) for part in components],
            'geometry_warnings':['DISCONNECTED_EXCAVATION_COMPONENTS'] if len(components)>1 else [],
            'volume_mm3':volume,'volume_interval_mm3':[vol(low_parts),vol(upper_parts)],
            'uncertainty_coverage_hull':convex_hull(upper_points),
            'projection_polygons':footprints,'terrain_error_mm':error_mm}


def convex_hull(points):
    points=sorted(set(tuple(p) for p in points))
    if len(points)<3:return points
    def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lower=[];upper=[]
    for p in points:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=0:lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=0:upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def triangulate_polygon(poly):
    """Ear clipping for simple nonconvex map/house polygons; rejects invalid rings."""
    poly=clean(poly)
    if not poly:raise ValueError('Empty polygon')
    # Collinear source vertices can obstruct ear tests; remove them first.
    changed=True
    while changed and len(poly)>3:
        changed=False
        for i in range(len(poly)):
            a,b,c=poly[i-1],poly[i],poly[(i+1)%len(poly)]
            if abs(area([a,b,c]))<1e-8:
                poly.pop(i);changed=True;break
    out=[]
    while len(poly)>3:
        for i,b in enumerate(poly):
            a,c=poly[i-1],poly[(i+1)%len(poly)]
            tri=[a,b,c]
            if area(tri)<=1e-9:continue
            def inside(p):
                return all((q[0]-r[0])*(p[1]-r[1])-(q[1]-r[1])*(p[0]-r[0])>=-1e-8
                           for r,q in zip(tri,tri[1:]+tri[:1]))
            if any(inside(p) for j,p in enumerate(poly) if j not in (i,(i-1)%len(poly),(i+1)%len(poly))):continue
            out.append(tri);poly.pop(i);break
        else:raise ValueError('Polygon is not simple or numerically valid')
    out.append(poly)
    return out


def _convex_intersection(a,b):
    poly=list(a)
    for p,q in zip(b,b[1:]+b[:1]):
        dx=q[0]-p[0];dy=q[1]-p[1]
        poly=clip_polygon(poly,(-dy,dx,dy*p[0]-dx*p[1]))
        if not poly:break
    return poly


def bbox(polygons):
    points=[p for poly in polygons for p in poly]
    if not points:return (0,0,0,0)
    return (min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points))


def overlap_area(polygons_a,polygons_b, convex_a=True, convex_b=False):
    """Intersection area of disjoint interiors, in mm². No envelope-only tests."""
    a=[clean(p) for p in polygons_a] if convex_a else [t for p in polygons_a for t in triangulate_polygon(p)]
    b=[clean(p) for p in polygons_b] if convex_b else [t for p in polygons_b for t in triangulate_polygon(p)]
    a=[p for p in a if p];b=[p for p in b if p]
    # Spatial bins avoid O(TIN²) when comparing two refined field footprints.
    size=1000.0;index=defaultdict(list);bounds=[]
    for i,poly in enumerate(b):
        x0,y0,x1,y1=bbox([poly]);bounds.append((x0,y0,x1,y1))
        for x in range(math.floor(x0/size),math.floor(x1/size)+1):
            for y in range(math.floor(y0/size),math.floor(y1/size)+1):index[(x,y)].append(i)
    total=0.0
    for poly in a:
        x0,y0,x1,y1=bbox([poly]);candidates=set()
        for x in range(math.floor(x0/size),math.floor(x1/size)+1):
            for y in range(math.floor(y0/size),math.floor(y1/size)+1):candidates.update(index[(x,y)])
        for i in candidates:
            u0,v0,u1,v1=bounds[i]
            if x0<u1 and x1>u0 and y0<v1 and y1>v0:total+=abs(area(_convex_intersection(poly,b[i])))
    return total


def outside_area(polygons,boundary):
    return max(0,sum(abs(area(p)) for p in polygons)-overlap_area(polygons,[boundary]))


def _domain_contact(triangles, polygons):
    """Positive-support vertices at a TIN boundary imply a potentially cut-off body."""
    edges=defaultdict(int)
    for tri in triangles:
        for a,b in zip(tri,tri[1:]+tri[:1]):edges[tuple(sorted((_key(a[:2]),_key(b[:2]))))]+=1
    boundary=[(tuple(v*TOPOLOGY_MM for v in a),tuple(v*TOPOLOGY_MM for v in b)) for (a,b),n in edges.items() if n==1]
    points={_key(p):p for poly in polygons for p in poly}
    for a,b in boundary:
        dx=b[0]-a[0];dy=b[1]-a[1];d2=dx*dx+dy*dy
        for p in points.values():
            t=((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d2
            if -1e-9<=t<=1+1e-9 and abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)<TOPOLOGY_MM*math.sqrt(d2):return True
    return False


def stockpile(triangles, center, target_mm3, roof_slope=0.5, relative_tolerance=1e-8, error_mm=0):
    """Square pyramid roof min(H±k*x,H±k*y), exact contact on the supplied TIN.

    Solver never hides a truncated pile by adding a wall at the TIN domain edge.
    The supplied patch must include the full contact footprint and some margin.
    """
    finite(*center,target_mm3,roof_slope,relative_tolerance,error_mm)
    if target_mm3<=0 or roof_slope<=0 or error_mm<0 or not 0<relative_tolerance<0.01:raise ValueError('Invalid pile target')
    cx,cy=center;k=roof_slope
    roofs=[(k,0,-k*cx),(-k,0,k*cx),(0,k,-k*cy),(0,-k,k*cy)]
    prepared=[]
    for tri in triangles:
        terrain=plane(tri)
        for i,roof in enumerate(roofs):
            poly=clean([p[:2] for p in tri])
            for j,other in enumerate(roofs):
                if i!=j:poly=clip_polygon(poly,subtract(other,roof))
            if poly:prepared.append((poly,terrain,roof))
    def get(h,terrain_shift=0):
        out=[]
        for poly,terrain,roof in prepared:
            terrain=(terrain[0],terrain[1],terrain[2]+terrain_shift)
            top=(roof[0],roof[1],roof[2]+h)
            clipped=clip_polygon(poly,subtract(top,terrain))
            if clipped and integrate_polygon(clipped,subtract(top,terrain))>1e-9:
                out.append((clipped,terrain,top))
        return out
    def vol(parts):return sum(integrate_polygon(p,subtract(hi,lo)) for p,lo,hi in parts)
    low=min(p[2] for tri in triangles for p in tri);high=low+1000
    for _ in range(30):
        parts=get(high);v=vol(parts)
        if v>=target_mm3:break
        high=low+(high-low)*2
    else:raise ValueError('Pile target cannot be bracketed')
    for _ in range(60):
        h=(low+high)/2;parts=get(h);v=vol(parts)
        if abs(v-target_mm3)<=target_mm3*relative_tolerance:break
        if v<target_mm3:low=h
        else:high=h
    footprints=[p for p,_,_ in parts]
    upper_parts=get(h,-error_mm)
    if _domain_contact(triangles,[p for p,_,_ in upper_parts]):raise ValueError('Pile uncertainty hull reaches terrain domain; no artificial closing wall permitted')
    mesh=surface_mesh(parts)
    if abs(mesh_volume(mesh)-v)>max(1e-3,v*1e-9):raise ValueError('Pile mesh/integral mismatch')
    components=mesh_components(mesh)
    return {'mesh':mesh,'mesh_components':components,'expected_body_count':len(components),
            'component_volumes_mm3':[mesh_volume(part) for part in components],
            'volume_mm3':v,'target_mm3':target_mm3,'apex_z_mm':h,
            'volume_interval_mm3':[vol(get(h,error_mm)),vol(upper_parts)],
            'terrain_error_mm':error_mm,
            'projection_polygons':footprints,'roof_slope':k,'form':'SQUARE_PYRAMID_1_TO_2_STUDY',
            'relative_volume_tolerance':relative_tolerance,'construction_release':False}
