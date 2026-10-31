# -*- coding: utf-8 -*-
"""G01e: validate the actual rectangular raster patches in one DGM sheet body.

No NX geometry is edited. Same G01d STEP, same 0.25 mm transfer tolerance.
Face order, edge order, tag values and UV direction are not assumed. Every
face is assigned from actual vertices to an integer-bounded source rectangle.
Rectangles must cover the 101 x 82 cells exactly once. Internal edges must be
shared by the correct pair of faces. Extra trims, missing cells and duplicated
patches are errors. A fixed XY-to-UV mapping is obtained from the actual
carrier of each face; this changes parameter coordinates, NOT geometry.

The new path uses only the NX calls already used in G01d: GetFaces/GetEdges,
GetVertices, AskFaceUvMinmax, EvaluateFace(...,0,...), and AskMinimumDist on
individual edge tags. Native NX execution remains to be confirmed by the user.
"""
import copy
import hashlib
import json
import math
from . import PATCH
from .terrain_uv import (UVLog, prepared_reference, vector, point3d, sides,
                         DISTANCE_MM, BATCH, FOCUS)
from .terrain_boundary import plan_boundary, boundary_probes

NR, NC = 102, 83
CELL_COUNT = (NR-1)*(NC-1)
MAX_FACES = CELL_COUNT
MAX_UNIQUE_EDGES = 4*CELL_COUNT
METHOD = 'RASTER_RECTANGLE_COVERAGE_LOCAL_UV_SHARED_EDGES'


class PatchError(RuntimeError):
    def __init__(self, message, **details):
        super().__init__('DGM-Rasterpruefung: '+message)
        self.patch_details = details


class Grid:
    """Original horizontal affine grid, not a fitted transformation of NX data."""
    def __init__(self, points, nr=NR, nc=NC):
        self.points, self.nr, self.nc = points, nr, nc
        self.origin = points[0]
        self.dr = [points[nc][k]-points[0][k] for k in range(2)]
        self.dc = [points[1][k]-points[0][k] for k in range(2)]
        self.det = self.dr[0]*self.dc[1]-self.dr[1]*self.dc[0]
        if not math.isfinite(self.det) or abs(self.det)<1e-8:
            raise PatchError('Entartetes Quellraster.')
        self.spacing = min(math.hypot(*self.dr),math.hypot(*self.dc))
        self.rc_tolerance = DISTANCE_MM/self.spacing
        for r in range(nr):
            for c in range(nc):
                p=points[r*nc+c]; rc=self.coordinates(p)
                if max(abs(rc[0]-r),abs(rc[1]-c))>1e-6:
                    raise PatchError('Quellraster in XY nicht affin.',node=[r,c],actual_grid=rc)

    def coordinates(self, p):
        x,y=p[0]-self.origin[0],p[1]-self.origin[1]
        return ((x*self.dc[1]-y*self.dc[0])/self.det,
                (self.dr[0]*y-self.dr[1]*x)/self.det)

    def node(self,p):
        r,c=self.coordinates(p); ri,ci=round(r),round(c)
        if not (0<=ri<self.nr and 0<=ci<self.nc):
            raise PatchError('NX-Endpunkt liegt ausserhalb des Originalrasters.',point=p,grid=[r,c])
        error=math.dist(p,self.points[ri*self.nc+ci])
        if error>DISTANCE_MM:
            raise PatchError('NX-Endpunkt passt nicht zu einem Quellknoten.',
                             point=p,grid=[r,c],nearest_node=[ri,ci],error_mm=error)
        return (ri,ci),error

    def at(self,r,c):
        if not (0<=r<=self.nr-1 and 0<=c<=self.nc-1):
            raise PatchError('Referenzabfrage ausserhalb des Originalrasters.',grid=[r,c])
        i=min(self.nr-2,int(r));j=min(self.nc-2,int(c));a,b=r-i,c-j
        p=self.points;n=self.nc
        return [(1-a)*(1-b)*p[i*n+j][k]+a*(1-b)*p[(i+1)*n+j][k]
                +(1-a)*b*p[i*n+j+1][k]+a*b*p[(i+1)*n+j+1][k] for k in range(3)]


def face_rectangle(nodes_by_edge, face_tag):
    """Closed four-sided chain, possibly segmented, bounded by source nodes."""
    if len(nodes_by_edge)<4:
        raise PatchError('Face hat weniger als vier auswertbare Kanten.',face_tag=face_tag)
    vertices=set(n for pair in nodes_by_edge.values() for n in pair)
    r0=min(n[0] for n in vertices);r1=max(n[0] for n in vertices)
    c0=min(n[1] for n in vertices);c1=max(n[1] for n in vertices)
    if r0==r1 or c0==c1:
        raise PatchError('Entartete Face-Ausdehnung.',face_tag=face_tag,bounds=[r0,r1,c0,c1])
    corners={(r0,c0),(r1,c0),(r0,c1),(r1,c1)}
    if not corners.issubset(vertices):
        raise PatchError('Rechteckige Face-Eckpunkte fehlen.',face_tag=face_tag,bounds=[r0,r1,c0,c1])
    chains={k:[] for k in ('R0','R1','C0','C1')}; degree={}
    for tag,(a,b) in nodes_by_edge.items():
        if a==b:raise PatchError('Kante ohne Laenge.',face_tag=face_tag,edge_tag=tag)
        degree[a]=degree.get(a,0)+1;degree[b]=degree.get(b,0)+1
        if a[0]==b[0]==r0:key,lo,hi='R0',min(a[1],b[1]),max(a[1],b[1])
        elif a[0]==b[0]==r1:key,lo,hi='R1',min(a[1],b[1]),max(a[1],b[1])
        elif a[1]==b[1]==c0:key,lo,hi='C0',min(a[0],b[0]),max(a[0],b[0])
        elif a[1]==b[1]==c1:key,lo,hi='C1',min(a[0],b[0]),max(a[0],b[0])
        else:raise PatchError('Innenring, Diagonale oder unbekannte Trimmung in Face.',
                              face_tag=face_tag,edge_tag=tag,edge_nodes=[a,b],bounds=[r0,r1,c0,c1])
        chains[key].append((lo,hi,tag))
    if any(d!=2 for d in degree.values()):
        raise PatchError('Face-Rand ist keine geschlossene Kette.',face_tag=face_tag)
    for key,entries in chains.items():
        start,end=(c0,c1) if key.startswith('R') else (r0,r1)
        cursor=start
        for lo,hi,tag in sorted(entries):
            if lo!=cursor:
                raise PatchError('Luecke oder Ueberlappung im Face-Rand.',face_tag=face_tag,
                                 side=key,edge_tag=tag,expected=cursor,actual=lo)
            cursor=hi
        if cursor!=end:
            raise PatchError('Face-Randseite ist unvollstaendig.',face_tag=face_tag,side=key)
    return (r0,r1,c0,c1)


def covered_cells(rect):
    r0,r1,c0,c1=rect
    return ((r,c) for r in range(r0,r1) for c in range(c0,c1))


def validate_coverage(records, nr=NR, nc=NC):
    owners={}
    for record in records:
        rect=record['rectangle'];tag=record['tag']
        r0,r1,c0,c1=rect
        if not (0<=r0<r1<nr and 0<=c0<c1<nc):
            raise PatchError('Face-Bereich ausserhalb des Rasters.',face_tag=tag,bounds=rect)
        for cell in covered_cells(rect):
            if cell in owners:
                raise PatchError('Rasterzelle doppelt abgedeckt.',cell=cell,
                                 first_face=owners[cell],second_face=tag)
            owners[cell]=tag
    missing=[(r,c) for r in range(nr-1) for c in range(nc-1) if (r,c) not in owners]
    if missing:raise PatchError('Rasterzellen fehlen.',missing_count=len(missing),first_missing=missing[:20])
    return owners


def edge_incidence(edge_records, owners, nr=NR, nc=NC):
    """Check true shared NX edge identities, not only coincident positions."""
    exterior=[];interior=[]
    for edge in edge_records:
        a,b=edge['nodes'];(r0,c0),(r1,c1)=a,b
        if r0==r1:
            lo,hi=sorted((c0,c1)); expected=set()
            for c in range(lo,hi):
                if r0>0:expected.add(owners[(r0-1,c)])
                if r0<nr-1:expected.add(owners[(r0,c)])
            outer=r0 in (0,nr-1)
        elif c0==c1:
            lo,hi=sorted((r0,r1));expected=set()
            for r in range(lo,hi):
                if c0>0:expected.add(owners[(r,c0-1)])
                if c0<nc-1:expected.add(owners[(r,c0)])
            outer=c0 in (0,nc-1)
        else:raise PatchError('Kante verlaeuft diagonal durch Raster.',edge_tag=edge['tag'])
        observed=set(edge['faces'])
        if observed!=expected or len(observed)!=(1 if outer else 2):
            raise PatchError('Nicht verbundene Naht oder falsche Kanten-Nachbarschaft.',
                             edge_tag=edge['tag'],edge_nodes=edge['nodes'],
                             expected_faces=sorted(expected),actual_faces=sorted(observed))
        (exterior if outer else interior).append(edge)
    return exterior,interior


def affine_parameter_map(actual_corners, grid, limits):
    """Map horizontal source coordinates into an actual face's UV coordinates.
    Handles swapped/reversed/skewed plane UVs. Actual XY at all four carrier
    corners must form a parallelogram. No source geometry is used to fit Z.
    """
    p00,p10,p01,p11=[grid.coordinates(p) for p in actual_corners]
    a=[p10[k]-p00[k] for k in range(2)]; b=[p01[k]-p00[k] for k in range(2)]
    det=a[0]*b[1]-a[1]*b[0]
    if not math.isfinite(det) or abs(det)<1e-12:
        raise PatchError('Nicht invertierbare XY/UV-Abbildung.',actual_corners=actual_corners)
    # Compare in mm, not an arbitrary parameter tolerance.
    expected=[actual_corners[1][k]+actual_corners[2][k]-actual_corners[0][k] for k in range(2)]
    err=math.hypot(*(actual_corners[3][k]-expected[k] for k in range(2)))
    if err>DISTANCE_MM:
        raise PatchError('Nicht affine horizontale UV-Abbildung; gesonderte Auswertung erforderlich.',error_mm=err)
    return dict(origin=list(p00),a=a,b=b,det=det,limits=list(limits),
                fourth_xy_error_mm=err,parameter_correspondence_only=True)


def uv_at(r,c,mapping,grid):
    q=[r-mapping['origin'][0],c-mapping['origin'][1]]
    a,b,d=mapping['a'],mapping['b'],mapping['det']
    x=(q[0]*b[1]-q[1]*b[0])/d; y=(a[0]*q[1]-a[1]*q[0])/d
    # Permit at most the existing 0.25 mm correspondence band at UV limits.
    tx=grid.rc_tolerance*(abs(b[0])+abs(b[1]))/abs(d)+1e-10
    ty=grid.rc_tolerance*(abs(a[0])+abs(a[1]))/abs(d)+1e-10
    if not (-tx<=x<=1+tx and -ty<=y<=1+ty):
        raise PatchError('Quellpunkt liegt ausserhalb des zugeordneten UV-Bereichs.',
                         grid_point=[r,c],normalised_uv=[x,y],limits=mapping['limits'])
    u0,u1,v0,v1=mapping['limits']
    return [u0+x*(u1-u0),v0+y*(v1-v0)]


def face_reference_samples(rect,nr=NR,nc=NC):
    r0,r1,c0,c1=rect
    for r in range(r0,r1+1):
        for c in range(c0,c1+1):yield r,c,r*nc+c
    for r in range(r0,r1):
        for c in range(c0,c1):yield r+.5,c+.5,nr*nc+r*(nc-1)+c


def internal_edge_probes(edge, grid):
    a,b=edge['nodes']; span=max(abs(a[0]-b[0]),abs(a[1]-b[1]))
    # Endpoints were already compared to original nodes; compare all intervening
    # source nodes and segment middles, plus quarter points of every segment.
    for step in range(span):
        for delta in (.25,.5,.75):
            t=(step+delta)/span
            r=a[0]+t*(b[0]-a[0]);c=a[1]+t*(b[1]-a[1])
            yield grid.at(r,c),'INNERE_NAHT_ZWISCHENPUNKT',[r,c]
        if step+1<span:
            t=(step+1)/span;r=a[0]+t*(b[0]-a[0]);c=a[1]+t*(b[1]-a[1])
            yield grid.at(r,c),'INNERE_NAHT_KNOTEN',[r,c]


def verify_dgm_patches(adapter,part,spec,out,trace):
    from r09.core import compare_boxes
    from r09.surface_check import distance_result_checked,area_checked
    from .terrain_audit import json_safe
    log=UVLog(out,trace,adapter); m=adapter.uf.Modeling
    log.data.update(method=METHOD,scope='Vollstaendige diskrete Rasterabdeckung; lokale Flaechenpunkte, echte geteilte Kanten und Aussenrand. Kein universeller Formgleichheits- oder Bestandsnachweis.',
        nx_faces=None,faces_mapped=0,faces_checked=0,face_point_comparisons=0,
        surface_evaluation_calls=0,edge_distance_calls=0,shared_edge_samples_checked=0,
        covered_cells=0,checked_samples=0,actual_edges_read=0,
        edge_parameters_preserved=True,carrier_is_single_face=False,
        all_carrier_reference_points_passed=False)
    try:
        adapter.ensure_work(part);adapter.check_millimeters(part,'DGM Rasterflaechenpruefung')
        for method in ('AskFaceUvMinmax','EvaluateFace','AskMinimumDist'):
            if not callable(getattr(m,method,None)):
                raise PatchError('NX-API fehlt: Modeling.'+method)
        ref,points=prepared_reference(spec);grid=Grid(points)
        bodies=list(part.Bodies)
        if len(bodies)!=1 or bodies[0].IsSolidBody or bodies[0].OwningPart.Tag!=part.Tag:
            raise PatchError('Genau ein offener Koerper im neuen Part erforderlich.')
        body=bodies[0];faces=list(body.GetFaces())
        log.data.update(nx_sheets=1,nx_faces=len(faces),body_tag=int(body.Tag),
                        expected_raster_cells=CELL_COUNT,source_grid_shape=[NR,NC],available_samples=len(points))
        log.checkpoint('TATSAECHLICHE_RASTERTOPOLOGIE_LESEN')
        if not 1<len(faces)<=MAX_FACES:
            raise PatchError('Flaechenanzahl ausserhalb des unterstuetzten Rasterumfangs.',actual_faces=len(faces),maximum=MAX_FACES)
        boxes=compare_boxes(spec['face_bounding_boxes_mm'],[adapter.surface_box(body)])
        log.data['bounds_check']=boxes
        edge_objects={};edges={};records=[];face_objects={}
        for i,face in enumerate(faces):
            tag=int(face.Tag);adapter.operation='G01e DGM Face-Rand %d/%d (Tag %d)'%(i+1,len(faces),tag)
            log.data['active_face']={'index':i,'tag':tag,'stage':'ENDPUNKTE_UND_RAND'}
            if face.OwningPart.Tag!=part.Tag:raise PatchError('Face gehoert nicht zum neuen Part.',face_tag=tag)
            if tag in face_objects:raise PatchError('Doppelte Face-Kennung.',face_tag=tag)
            face_objects[tag]=face;entries=list(face.GetEdges()); seen=set();nodes={}
            for edge in entries:
                et=int(edge.Tag)
                if et in seen:raise PatchError('Kante innerhalb einer Face mehrfach verwendet.',face_tag=tag,edge_tag=et)
                seen.add(et)
                if edge.OwningPart.Tag!=part.Tag:raise PatchError('Kante gehoert nicht zum neuen Part.',edge_tag=et)
                if et not in edges:
                    if len(edges)>=MAX_UNIQUE_EDGES:raise PatchError('Arbeitslimit fuer Kanten erreicht.')
                    pair=edge.GetVertices()
                    if len(pair)!=2:raise PatchError('Kante ohne zwei Endpunkte.',edge_tag=et)
                    ends=[point3d(p) for p in pair]; located=[grid.node(p) for p in ends]
                    if located[0][0]==located[1][0]:raise PatchError('Kante ohne Rasterlaenge.',edge_tag=et)
                    row={'tag':et,'endpoints':ends,'nodes':[n[0] for n in located],
                         'max_endpoint_error_mm':max(n[1] for n in located),'faces':[]}
                    edges[et]=row;edge_objects[et]=edge
                    log.data['actual_edges_read']=len(edges)
                    log.event('NX_RASTERKANTE',row)
                edges[et]['faces'].append(tag);nodes[et]=edges[et]['nodes']
            rect=face_rectangle(nodes,tag)
            record={'tag':tag,'index':i,'rectangle':rect,'edge_tags':list(nodes)}
            records.append(record);log.event('NX_FACE_RASTERZUORDNUNG',record)
            log.data['faces_mapped']=i+1;log.data['last_mapped_face']=record
            if (i+1)%BATCH==0 or i+1==len(faces):
                log.checkpoint('TATSAECHLICHE_RASTERTOPOLOGIE_LESEN')
                if (i+1)%(BATCH*8)==0 or i+1==len(faces):
                    adapter.log('G01e DGM: %d/%d Face-Raender erfasst.'%(i+1,len(faces)))
        log.checkpoint('RASTERABDECKUNG_UND_NACHSCHAFT')
        owners=validate_coverage(records); exterior,interior=edge_incidence(list(edges.values()),owners)
        log.data.update(covered_cells=len(owners),unique_edges=len(edges),interior_edges=len(interior),
                        exterior_edges=len(exterior),coverage_passed=True,shared_edge_topology_passed=True,
                        coverage_map_sha256=hashlib.sha256(json.dumps(sorted(owners.items())).encode()).hexdigest())
        # Reuse the existing perimeter proof, only on edges that are truly exterior.
        exterior_records=[dict(e,index=i) for i,e in enumerate(exterior)]
        groups,boundary_audit=plan_boundary(exterior_records,sides(points),DISTANCE_MM)
        log.data['boundary_chains']=boundary_audit
        outer_probes=list(boundary_probes(groups))
        log.data['expected_boundary_samples']=len(outer_probes)
        if len(outer_probes)!=736+3*len(exterior):raise PatchError('Interner Fehler im Aussenrand-Pruefumfang.')
        # Prioritise patches incident to historical failed source points, never omit
        # other patches. All source nodes are also checked on every incident face.
        wanted={(int(idx)//NC,int(idx)%NC) for idx in FOCUS if idx<NR*NC}
        def priority(rec):
            a,b,c,d=rec['rectangle']
            return (0 if any(a<=r<=b and c<=s<=d for r,s in wanted) else 1,rec['rectangle'])
        checked=set(); records.sort(key=priority); max_error=0.
        for i,rec in enumerate(records):
            tag=rec['tag'];face=face_objects[tag]
            adapter.operation='G01e DGM Face-Koordinaten %d/%d Tag %d'%(i+1,len(records),tag)
            log.data['active_face']={'index':i,'tag':tag,'rectangle':rec['rectangle'],'stage':'UV_KOORDINATEN'}
            if i%BATCH==0:log.checkpoint('LOKALE_FLAECHENKOORDINATEN')
            limits=vector(m.AskFaceUvMinmax(tag),4)
            if not (limits[0]<limits[1] and limits[2]<limits[3]):
                raise PatchError('Entarteter UV-Bereich.',face_tag=tag,uv_limits=limits)
            cache={}
            def evaluate(uv,kind):
                key=tuple(uv)
                if key in cache:return cache[key]
                adapter.operation='G01e DGM Face %d %s'%(tag,kind)
                log.data['last_evaluation']={'face_tag':tag,'uv':list(uv),'kind':kind}
                value=m.EvaluateFace(tag,0,list(uv))
                if not hasattr(value,'SrfPos'):raise PatchError('EvaluateFace ohne SrfPos.',face_tag=tag)
                actual=vector(value.SrfPos);cache[key]=actual
                log.data['surface_evaluation_calls']+=1
                log.event('NX_FACE_POSITION',dict(face_tag=tag,uv=list(uv),kind=kind,actual_mm=actual))
                return actual
            u0,u1,v0,v1=limits
            corners=[evaluate(uv,'UV_BEREICHSECKE') for uv in ([u0,v0],[u1,v0],[u0,v1],[u1,v1])]
            mapping=affine_parameter_map(corners,grid,limits)
            log.event('NX_FACE_FESTE_PARAMETERZUORDNUNG',dict(face_tag=tag,rectangle=rec['rectangle'],mapping=mapping))
            for r,c,idx in face_reference_samples(rec['rectangle']):
                uv=uv_at(r,c,mapping,grid);actual=evaluate(uv,'QUELLREFERENZ_%d'%idx)
                deviation=math.dist(points[idx],actual); max_error=max(max_error,deviation)
                row={'face_tag':tag,'source_index':idx,'source_mm':points[idx],
                     'uv':uv,'NX_position_mm':actual,'position_error_mm':deviation}
                log.event('RASTER_FLAECHENVERGLEICH',row)
                log.data['face_point_comparisons']+=1;log.data['max_position_error_mm']=max_error
                log.data['last_sample']=row
                if idx in FOCUS and idx not in checked:log.data['focus_points'].append(row)
                if deviation>DISTANCE_MM:
                    log.data['failed_sample']=row
                    raise PatchError('Flaechenpunkt %d weicht um %.6f mm ab (Grenze %.3f mm).'%(idx,deviation,DISTANCE_MM),**row)
                checked.add(idx);log.data['checked_samples']=len(checked)
            log.data['faces_checked']=i+1
            if (i+1)%(BATCH*8)==0 or i+1==len(records):
                adapter.log('G01e DGM: %d/%d Faces geprueft; %d/16748 unterschiedliche Quellpunkte.'%(i+1,len(records),len(checked)))
        if len(checked)!=16748:raise PatchError('Nicht alle Originalpunkte geprueft.',checked=len(checked))
        log.data['all_carrier_reference_points_passed']=True
        log.data['active_face']=None
        log.checkpoint('ECHTE_INNERE_UND_AEUSSERE_KANTEN')
        touched=set()
        def edge_distance(edge,q,kind,detail):
            et=edge['tag'];adapter.operation='G01e DGM Kante %d %s'%(et,kind)
            data={'edge_tag':et,'query_mm':q,'kind':kind,**detail}
            log.data['active_edge_probe']=data
            raw=m.AskMinimumDist(0,et,1,list(q),0,[0.,0.,0.]);data['raw_result']=json_safe(raw)
            log.event('NX_RASTERKANTENABSTAND',data)
            distance=distance_result_checked(raw,q)
            log.data['edge_distance_calls']+=1;touched.add(et)
            log.data['max_boundary_error_mm']=max(log.data['max_boundary_error_mm'],distance)
            if distance>DISTANCE_MM:
                data['distance_mm']=distance;log.data['failed_boundary']=data
                raise PatchError('Kante %d weicht um %.6f mm ab (Grenze %.3f mm).'%(et,distance,DISTANCE_MM),**data)
            if log.data['edge_distance_calls']%(BATCH*4)==0:log.checkpoint('ECHTE_INNERE_UND_AEUSSERE_KANTEN')
        for i,edge in enumerate(interior):
            for q,kind,rc in internal_edge_probes(edge,grid):
                edge_distance(edge,q,kind,{'source_grid':rc})
                log.data['shared_edge_samples_checked']+=1
            if (i+1)%4096==0:adapter.log('G01e DGM: %d/%d innere Kanten geprueft.'%(i+1,len(interior)))
        for probe in outer_probes:
            edge=edges[probe['edge']['tag']]
            edge_distance(edge,probe['query_mm'],probe['kind'],{'side':probe['side'],'source_fraction':probe['fraction']})
            log.data['boundary_samples_checked']+=1
            key='per_edge_extra_samples_checked' if probe['kind']=='JE_KANTE_ZUSATZPROBE' else 'original_boundary_samples_checked'
            log.data[key]+=1
        if (len(touched)!=len(edges) or log.data['boundary_samples_checked']!=len(outer_probes)
            or log.data['original_boundary_samples_checked']!=736):
            raise PatchError('Kantenpruefung nicht vollstaendig.')
        log.data.update(active_edge_probe=None,actual_edges_with_distance_checks=len(touched),
                        full_reference_check_performed=True)
        # A scalar comparison guard, not a physical off-surface NX query.
        above=list(points[1089]);above[2]=max(p[2] for p in points)+1000.
        log.data['negative_reference_control']={'distance_to_source_mm':math.dist(above,points[1089]),
                                               'above_source_rejected':math.dist(above,points[1089])>999.}
        if adapter.validation_level=='INTENSIV':
            log.checkpoint('OPTIONALE_FLAECHENINTEGRATION')
            area=area_checked(ref['area_mm2'],adapter.surface_area_mm2(body))
            log.data.update(area_check_performed=True,area_result=area)
            if not area['area_passed']:raise PatchError('Flaecheninhalt im Intensivmodus abweichend.')
        for key,value in {
            'HAUS_IMPORTPRUEFUNG':'G01e_RASTERFLAECHEN_UND_KANTEN',
            'HAUS_NX_EINZELFLAECHEN':str(len(faces)),
            'HAUS_GEPRUEFTE_RASTERZELLEN':str(CELL_COUNT),
            'HAUS_ALLE_QUELLPUNKTE_GEPRUEFT':'True',
            'HAUS_FLAECHENINHALT_GEPRUEFT':str(log.data['area_check_performed']),
            'HAUS_IMPORTPRUEFUNG_HINWEIS':'Einmalige Rasterabdeckung, geteilte Kanten und 16.748 Quellpunkte; endliche Pruefung, kein Bestandsnachweis.'}.items():
            adapter._set_user_attribute(part,key,value,'DGM')
        log.data.update(status='RASTERFLAECHEN_UND_KANTEN_BESTANDEN_KEIN_BESTANDSNACHWEIS',
                        selected_checks_passed=True,geometry_release=False)
        log.checkpoint('PRUEFUNG_BESTANDEN_SPEICHERN_AUSSTEHEND')
        return dict(boxes,faces=len(faces),source_faces=1,face_count_changed=True,
            faces_per_sheet_import_order=[len(faces)],checked_source_points=len(checked),
            available_source_points=16748,max_point_distance_mm=max_error,
            geometry_validation_status=log.data['status'],validation_level='DGM_RASTER_G01e',
            requested_environment_level=adapter.validation_level,geometry_report=str(log.path),
            area_check_performed=log.data['area_check_performed'],full_reference_check_performed=True,
            boundary_samples_checked=log.data['boundary_samples_checked'],original_boundary_samples_checked=736,
            actual_boundary_edges=len(exterior),boundary_chains_passed=True,normal_distance_search_used=False,
            verified_raster_cells=CELL_COUNT,actual_internal_edges=len(interior),
            shared_edge_samples_checked=log.data['shared_edge_samples_checked'])
    except Exception as error:
        log.data.update(status='DGM_RASTERFLAECHEN_ABGEBROCHEN',error=str(error),
            exception_type=type(error).__name__,nx_error_code=getattr(error,'ErrorCode',None),
            operation=adapter.operation,selected_checks_passed=False,geometry_release=False)
        if hasattr(error,'patch_details'):log.data['patch_failure']=error.patch_details
        if hasattr(error,'boundary_details'):log.data['boundary_chains']=error.boundary_details
        try:log.checkpoint('ABGEBROCHEN')
        except Exception as secondary:log.data['secondary_logging_error']=str(secondary)
        error.nx_terrain_uv_g01b=copy.deepcopy(log.data)
        error.nx_surface_check={'id':'DGM','status':log.data['status'],'report_file':str(log.path),
            'error':str(error),'operation':adapter.operation,'method':METHOD,
            'nx_faces':log.data['nx_faces'],'checked_samples':log.data['checked_samples'],
            'failed_sample':log.data.get('failed_sample')}
        raise
    finally:log.close()
