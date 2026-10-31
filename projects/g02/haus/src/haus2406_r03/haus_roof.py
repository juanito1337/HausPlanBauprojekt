# -*- coding: utf-8 -*-
"""Dach-PRUEFHUELLEN, keine behauptete Rekonstruktion von Sparrenanschluessen.

Stueckweise ebene Walmdachhuellen und optionale Gauben-Ersatzflaechen werden
als obere Einhuellende verschnitten. Geometrie rein numerisch, ohne NX.
Die fuer diese Huellen benoetigten Trauflagen sind ausdruecklich geschaetzt.
"""
import math
from .haus_geometry import clean, area, convex_intersection, convex_difference, transformed, enabled


def height(face, p):
    a,b,c=face['plane']
    return a*p[0]+b*p[1]+c


def scalar_clip(poly,a,b,c):
    """Behalte a*x+b*y+c >= 0."""
    if not poly:return []
    out=[]
    for p,q in zip(poly,poly[1:]+poly[:1]):
        dp=a*p[0]+b*p[1]+c;dq=a*q[0]+b*q[1]+c
        ip=dp>=-1e-7;iq=dq>=-1e-7
        if ip:out.append(p)
        if ip!=iq:
            f=dp/(dp-dq)
            out.append([p[0]+f*(q[0]-p[0]),p[1]+f*(q[1]-p[1])])
    return clean(out)


def plane_for(points):
    p,q,r=points[:3]
    ux,uy,uz=[q[i]-p[i] for i in range(3)]
    vx,vy,vz=[r[i]-p[i] for i in range(3)]
    nx=uy*vz-uz*vy;ny=uz*vx-ux*vz;nz=ux*vy-uy*vx
    if abs(nz)<1e-8:raise ValueError('Dachflaeche nicht ueber XY darstellbar')
    a=-nx/nz;b=-ny/nz;c=p[2]-a*p[0]-b*p[1]
    return [a,b,c]


def hip(definition,params):
    x0,y0,x1,y1=[params.number(v) for v in definition['rect']]
    e=params.number(definition['eave']); slope=math.tan(math.radians(params.number(definition['pitch'])))
    dx=x1-x0;dy=y1-y0;half=min(dx,dy)/2
    if min(dx,dy)<=0 or slope<=0:raise ValueError('Ungueltiges Walmdach')
    # A sourced ridge chain may govern elevation; eave remains derived from the
    # provisional footprint. Changing the span must not silently move that ridge.
    if definition.get('ridge_height') is not None:
        z=params.number(definition['ridge_height'])
        e=z-half*slope
    else:
        z=e+half*slope
    sw=[x0,y0,e];se=[x1,y0,e];ne=[x1,y1,e];nw=[x0,y1,e]
    if dy>=dx:
        rs=[(x0+x1)/2,y0+half,z];rn=[(x0+x1)/2,y1-half,z]
        polygons=[[sw,se,rs],[se,ne,rn,rs],[ne,nw,rn],[nw,sw,rs,rn]]
    else:
        rw=[x0+half,(y0+y1)/2,z];re=[x1-half,(y0+y1)/2,z]
        polygons=[[sw,se,re,rw],[se,ne,re],[ne,nw,rw,re],[nw,sw,rw]]
    result=[]
    for i,points in enumerate(polygons):
        world=[]
        for p in points:
            xy=transformed(p[:2],definition.get('origin',[0,0]),params.number(definition.get('orientation',0)))
            if not world or sum((xy[j]-world[-1][j])**2 for j in (0,1))>1e-8:world.append(xy+[p[2]])
        if len(world)>2:
            poly=clean([p[:2] for p in world])
            if poly:
                result.append({'id':definition['id']+'_%02d'%(i+1),'parent':definition['id'],
                               'polygon':poly,'plane':plane_for(world),'status':'GESCHAETZT',
                               'sources':definition.get('sources',[]),
                               'system_id':definition.get('system_id','UNGEKLAERT'),
                               'representation':'DACH_PRUEFHUELLE_KEIN_TRAGWERK',
                               'construction_status':'NICHT_AUSKONSTRUIERT','quantity_excluded':True})
    return result



def _contains_convex(poly, point, tolerance=1e-5):
    """Point-in-convex-domain in millimetres (distance tolerance, not area)."""
    for p, q in zip(poly, poly[1:] + poly[:1]):
        dx, dy = q[0]-p[0], q[1]-p[1]
        if dx*(point[1]-p[1])-dy*(point[0]-p[0]) < -tolerance*math.hypot(dx, dy):
            return False
    return True


def resolve_dormer(definition, params, host_faces):
    """Resolve a straight shed-dormer rear edge against the existing host roof.

    This is a geometric closure of the *model*. It is NOT an as-built survey,
    not a measured pitch, and not a flashing/structural junction design.
    Width, front location, front height and the explicitly estimated pitch stay
    fixed. No best-fit averaging: mixed/sloping rear intersections are rejected.
    Input dictionaries are never modified. Legacy definitions are preserved.
    """
    policy = definition.get('rear_attachment')
    if policy is None:
        return dict(definition)
    if policy != 'INTERSECTION_WITH_HOST':
        raise ValueError('Unbekannte Gaubenanschlussregel: '+str(policy))
    x0,y0,x1,y1 = [params.number(v) for v in definition['rect']]
    front = definition.get('front_axis')
    if front not in ('xmin','xmax','ymin','ymax'):
        raise ValueError('Gaube: ungueltige Vorderkante '+str(front))
    axis = 0 if front[0]=='x' else 1
    if definition.get('axis') != front[0]:
        raise ValueError('Gaube: Achse und Vorderkante widersprechen sich')
    sign = 1 if front.endswith('min') else -1
    fcoord = (x0 if sign>0 else x1) if axis==0 else (y0 if sign>0 else y1)
    low,high = (y0,y1) if axis==0 else (x0,x1)
    pitch = params.number(definition['pitch'])
    front_z = params.number(definition['front_roof_z'])
    maximum = params.number(definition['max_join_distance_mm'])
    if not all(math.isfinite(v) for v in (x0,y0,x1,y1,pitch,front_z,maximum)):
        raise ValueError('Gaube: nicht endlicher Parameter')
    if x1<=x0 or y1<=y0 or not 0 < pitch < 80 or maximum<=0:
        raise ValueError('Gaube: ungueltige Abmessung oder Neigung')
    hosts=set(definition.get('host_parents',[]))
    if not hosts:
        raise ValueError('Gaube: kein Wirtsdach deklariert')
    slope=math.tan(math.radians(pitch))
    roof_plane=[0.,0.,front_z-sign*slope*fcoord]
    roof_plane[axis]=sign*slope
    # Check endpoints and internal stations; all must have the same FIRST
    # intersection with the upper host envelope. A crossing on the opposite
    # roof slope is not a legitimate dormer rear attachment.
    records=[]
    for station in range(9):
        lateral=low+(high-low)*station/8
        start=[fcoord,lateral] if axis==0 else [lateral,fcoord]
        at_front=[h for h in host_faces if h['parent'] in hosts and _contains_convex(h['polygon'],start)]
        if not at_front or front_z<=max(height(h,start) for h in at_front)+0.1:
            raise ValueError('Gaubenvorderkante liegt nicht ueber dem Wirtsdach: '+definition['id'])
        candidates=[]
        for host in host_faces:
            if host['parent'] not in hosts:
                continue
            denominator=sign*(roof_plane[axis]-host['plane'][axis])
            # Only catch-up intersections on an inward-rising host slope.
            if denominator>=-1e-9:
                continue
            depth=(height(host,start)-front_z)/denominator
            if not (0<depth<=maximum):
                continue
            point=list(start);point[axis]+=sign*depth
            if not _contains_convex(host['polygon'],point):
                continue
            z=front_z+slope*depth
            active=[h for h in host_faces if h['parent'] in hosts and _contains_convex(h['polygon'],point)]
            if not active or abs(max(height(h,point) for h in active)-z)>0.001:
                continue
            candidates.append((depth,point,z,host['parent']))
        if not candidates:
            raise ValueError('Kein gueltiger hinterer Gaubendachanschluss: '+definition['id'])
        depth,point,z,parent=min(candidates,key=lambda x:x[0])
        records.append({'station':station,'point':point+[z],'depth_mm':depth,'host_parent':parent})
    depths=[r['depth_mm'] for r in records]
    if max(depths)-min(depths)>0.001:
        raise ValueError('Gaubenanschluss nicht geradlinig; separate Kontur erforderlich: '+definition['id'])
    # One solved station, not an unreported fitted/averaged depth.
    depth=depths[0];back=fcoord+sign*depth;rear_z=front_z+slope*depth
    rect=[x0,y0,x1,y1]
    rect[axis+2 if sign>0 else axis]=back
    # Verify the ENTIRE piecewise-planar rear seam, not only the nine
    # construction stations. Split it at all host-domain intersections.
    edge_a=[back,low] if axis==0 else [low,back]
    edge_b=[back,high] if axis==0 else [high,back]
    delta=[edge_b[k]-edge_a[k] for k in (0,1)]
    breaks={0.0,1.0}
    for host in host_faces:
        if host['parent'] not in hosts:
            continue
        left,right=0.0,1.0;valid=True
        poly=host['polygon']
        for a,b in zip(poly,poly[1:]+poly[:1]):
            ex,ey=b[0]-a[0],b[1]-a[1]
            f0=ex*(edge_a[1]-a[1])-ey*(edge_a[0]-a[0])
            fd=ex*delta[1]-ey*delta[0]
            if abs(fd)<1e-10:
                if f0 < -1e-5*math.hypot(ex,ey):valid=False;break
            elif fd>0:left=max(left,-f0/fd)
            else:right=min(right,-f0/fd)
        if valid and right>=left and right>=0 and left<=1:
            breaks.update((max(0.,left),min(1.,right)))
    checks=[];order=sorted(breaks)
    samples=sorted(set(order+[(a+b)/2 for a,b in zip(order,order[1:])]))
    for fraction in samples:
        point=[edge_a[k]+fraction*delta[k] for k in (0,1)]
        active=[h for h in host_faces if h['parent'] in hosts and _contains_convex(h['polygon'],point)]
        if not active:raise ValueError('Gaubenrueckkante ausserhalb Wirtsdach: '+definition['id'])
        gap=abs(rear_z-max(height(h,point) for h in active))
        if gap>0.001:raise ValueError('Gaubenrueckkante nicht durchgehend geschlossen: '+definition['id'])
        checks.append({'fraction':fraction,'gap_mm':gap})
    out=dict(definition,rect=rect,
             roof_z=[front_z,rear_z] if sign>0 else [rear_z,front_z])
    out['attachment_check']={
        'status':'MODELLFLAECHEN_SCHNEIDEN_SICH_NICHT_BESTANDSBESTAETIGT',
        'pitch_deg':pitch,'pitch_status':definition.get('pitch_status','GESCHAETZT'),
        'front_z_mm':front_z,'rear_z_mm':rear_z,'front_to_rear_mm':depth,
        'original_rect':list(definition['rect']),'resolved_rect':rect,
        'stations':records,'max_depth_spread_mm':max(depths)-min(depths),
        'whole_rear_seam_checks':checks,'max_rear_gap_mm':max(c['gap_mm'] for c in checks),
        'source':'GEOMETRISCHE_ABLEITUNG_AUS_BISHERIGEN_MODELLANNAHMEN',
        'as_built_verified':False,'flashing_or_structure_designed':False}
    return out


def dormer(definition,params):
    x0,y0,x1,y1=[params.number(v) for v in definition['rect']];z0,z1=[params.number(t) for t in definition['roof_z']]
    if definition['axis']=='x':
        points=[[x0,y0,z0],[x1,y0,z1],[x1,y1,z1],[x0,y1,z0]]
    else:
        points=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z1],[x0,y1,z1]]
    return {'id':definition['id'],'parent':definition['id'],'polygon':clean([p[:2] for p in points]),
            'plane':plane_for(points),'status':'GESCHAETZT','sources':definition.get('sources',[]),
            'system_id':'GAUBE_TRAGWERK_OFFEN','representation':'DACH_PRUEFHUELLE_KEIN_TRAGWERK',
            'construction_status':'NICHT_AUSKONSTRUIERT','quantity_excluded':True,
            'attachment_check':definition.get('attachment_check'),
            'note':definition.get('note',''),
            'pitch_status':definition.get('pitch_status','GESCHAETZT')}


def upper_envelope(faces):
    """Nicht ueberlappende XY-Facetten der jeweils hoechsten Dachflaeche."""
    output=[]
    for i,f in enumerate(faces):
        fragments=[f['polygon']]
        for j,g in enumerate(faces):
            if i==j:continue
            difference=[f['plane'][k]-g['plane'][k] for k in range(3)]
            next_pieces=[]
            for piece in fragments:
                overlap=convex_intersection(piece,g['polygon'])
                if not overlap:
                    next_pieces.append(piece);continue
                if max(abs(v) for v in difference)<1e-8:
                    if i<j:next_pieces.append(piece)
                    else:next_pieces.extend(convex_difference(piece,g['polygon']))
                    continue
                next_pieces.extend(convex_difference(piece,g['polygon']))
                kept=scalar_clip(overlap,*difference)
                if kept:next_pieces.append(kept)
            fragments=[p for p in next_pieces if abs(area(p))>0.1]
            if not fragments:break
        for n,p in enumerate(fragments):
            item=dict(f);item['polygon']=p;item['id']=f['id']+'_F%02d'%(n+1);output.append(item)
    return output


def compile_roofs(data,params,include_dormers=True):
    raw=[]
    for item in data.get('roof_definitions',[]):
        if enabled(item,params,True)[0]:raw.extend(hip(item,params))
    if include_dormers:
        host_faces=upper_envelope(raw)
        for item in data.get('dormers',[]):
            if enabled(item,params,True)[0]:
                raw.append(dormer(resolve_dormer(item,params,host_faces),params))
    for item in data.get('main_roof_faces', []):
        pts=item['points']
        if item.get('main_parameter_control'):
            anchor=data['main_details']['anchor'];a=anchor['a'];b=anchor['b'];length=math.dist(a,b)
            t=[(b[k]-a[k])/length for k in range(2)];n=[t[1],-t[0]]
            lo=params.value('BAL_TUER_OFFSET')-150;hi=params.value('BAL_TUER_OFFSET')+params.value('BAL_TUER_BREITE')+150
            zback=params.value('BAL_NISCHE_DACH_HINTEN');zfront=params.value('BAL_NISCHE_DACH_VORN')
            pts=[]
            for u,v in [(lo,-1500),(hi,-1500),(hi,100),(lo,100)]:
                z=zback+(v+1500)*(zfront-zback)/1600
                pts.append([a[k]+t[k]*u+n[k]*v for k in range(2)]+[z])
        raw.append(dict(item,points=pts,polygon=clean([p[:2] for p in pts]),plane=plane_for(pts)))
    return upper_envelope(raw)
