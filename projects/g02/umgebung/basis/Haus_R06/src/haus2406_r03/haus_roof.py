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


def dormer(definition,params):
    x0,y0,x1,y1=[params.number(v) for v in definition['rect']];z0,z1=[params.number(t) for t in definition['roof_z']]
    if definition['axis']=='x':
        points=[[x0,y0,z0],[x1,y0,z1],[x1,y1,z1],[x0,y1,z0]]
    else:
        points=[[x0,y0,z0],[x1,y0,z0],[x1,y1,z1],[x0,y1,z1]]
    return {'id':definition['id'],'parent':definition['id'],'polygon':clean([p[:2] for p in points]),
            'plane':plane_for(points),'status':'GESCHAETZT','sources':definition.get('sources',[]),
            'system_id':'GAUBE_TRAGWERK_OFFEN','representation':'DACH_PRUEFHUELLE_KEIN_TRAGWERK',
            'construction_status':'NICHT_AUSKONSTRUIERT','quantity_excluded':True}


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
        for item in data.get('dormers',[]):
            if enabled(item,params,True)[0]:raw.append(dormer(item,params))
    return upper_envelope(raw)
