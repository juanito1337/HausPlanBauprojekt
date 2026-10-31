# -*- coding: utf-8 -*-
"""Unabhaengige numerische Volumen-/Kollisionspruefung von Bauauftraegen.

Exakt fuer die hier verwendeten konvexen XY-Polygone zwischen linearen Hoehen-
ebenen. Keine Pruefung im Parasolid-Kernel, kein Nachweis des Plan-Istzustands.
"""
import math
from .haus_geometry import Parameters,area,convex_intersection
from .haus_roof import plane_for,scalar_clip
from .haus_quality import plane_z


def centroid(poly):
    a=area(poly)
    if abs(a)<1e-10:raise ValueError('Kein Schwerpunkt fuer leeres Polygon')
    x=y=0.0
    for p,q in zip(poly,poly[1:]+poly[:1]):
        c=p[0]*q[1]-q[0]*p[1];x+=(p[0]+q[0])*c;y+=(p[1]+q[1])*c
    return [x/(6*a),y/(6*a)]


def integrate(poly,plane):
    if not poly:return 0.0
    return abs(area(poly))*plane_z(plane,centroid(poly))


def vertical_record(solid,params,part_id):
    if 'polygon' in solid:
        poly=solid['polygon'];lo=solid.get('bottom_plane',[0,0,params.number(solid['bottom'])]);hi=solid.get('top_plane',[0,0,params.number(solid['top'])])
        if solid.get('roof_clip'):
            hi=list(solid['roof_clip']['plane']);hi[2]-=params.value('DACH_HUELLE_PROXY')
    else:
        if abs(solid['vector'][0])+abs(solid['vector'][1])>1e-7:raise ValueError('Pruefer erwartet vertikale Extrusion: '+solid['id'])
        poly=[p[:2] for p in solid['points']];one=plane_for(solid['points']);two=list(one);two[2]+=solid['vector'][2]
        lo,hi=(one,two) if solid['vector'][2]>0 else (two,one)
    minimum=min(plane_z(hi,p)-plane_z(lo,p) for p in poly)
    volume=integrate(poly,[hi[i]-lo[i] for i in range(3)])
    return {'id':solid['id'],'parent':solid['parent'],'part':part_id,'kind':solid['kind'],'polygon':poly,'lo':lo,'hi':hi,'volume_mm3':volume,'min_thickness_mm':minimum,
            'box':[min(p[0] for p in poly),min(p[1] for p in poly),min(plane_z(lo,p) for p in poly),max(p[0] for p in poly),max(p[1] for p in poly),max(plane_z(hi,p) for p in poly)]}


def same_plane(a,b):return max(abs(a[i]-b[i]) for i in range(3))<1e-8


def intersection_volume(a,b):
    xy=convex_intersection(a['polygon'],b['polygon'])
    if not xy:return 0.0
    upper=[a['hi']] if same_plane(a['hi'],b['hi']) else [a['hi'],b['hi']]
    lower=[a['lo']] if same_plane(a['lo'],b['lo']) else [a['lo'],b['lo']]
    volume=0.0
    for u in upper:
        for l in lower:
            poly=xy
            for other in upper:
                if other is not u:poly=scalar_clip(poly,*[other[i]-u[i] for i in range(3)])
            for other in lower:
                if other is not l:poly=scalar_clip(poly,*[l[i]-other[i] for i in range(3)])
            diff=[u[i]-l[i] for i in range(3)];poly=scalar_clip(poly,*diff)
            if poly:volume+=max(0,integrate(poly,diff))
    return volume


def audit_compiled(data,compiled,collision_threshold_mm3=1000.0):
    params=Parameters(data['parameters']);records=[vertical_record(s,params,p['id']) for p in compiled['parts'] for s in p['solids']]
    bad=[r['id'] for r in records if r['volume_mm3']<=0 or r['min_thickness_mm']<-.001 or not all(math.isfinite(v) for v in r['box'])]
    collisions=[];candidates=0
    ordered=sorted(records,key=lambda r:r['box'][0])
    for i,a in enumerate(ordered):
        A=a['box']
        for b in ordered[i+1:]:
            B=b['box']
            if B[0]>=A[3]-1e-5:break
            if any(min(A[k+3],B[k+3])-max(A[k],B[k])<=1e-5 for k in (1,2)):continue
            candidates+=1;v=intersection_volume(a,b)
            if v>collision_threshold_mm3:
                collisions.append({'a':a['id'],'b':b['id'],'part_a':a['part'],'part_b':b['part'],'parent_a':a['parent'],'parent_b':b['parent'],'kind_a':a['kind'],'kind_b':b['kind'],'volume_cm3':round(v/1000,4)})
    return {'scope':'Numerischer Bauauftrag, vertikale Prismen zwischen Ebenen; KEIN NX-Test, KEIN Planaufmass.',
            'checked_solids':len(records),'invalid_solids':bad,'collision_threshold_cm3':collision_threshold_mm3/1000,
            'candidate_pairs':candidates,'collisions':collisions,'collision_count':len(collisions),
            'status':'NICHT_KOLLISIONSFREI' if not bad and collisions else 'NUMERISCH_BESTANDEN' if not bad else 'FEHLER',
            'records':[{'id':r['id'],'parent':r['parent'],'part':r['part'],'kind':r['kind'],'volume_cm3':r['volume_mm3']/1000,'minimum_thickness_mm':r['min_thickness_mm'],'bbox_mm':r['box']} for r in records]}


def subtract_vertical(subject,cutter):
    """Disjunkte Volumenreste eines konvexen XY-Prismas zwischen Ebenen.
    Alle Resultate bleiben numerisch definierte Prismen zwischen Ebenen.
    """
    from .haus_geometry import convex_difference
    hit=convex_intersection(subject['polygon'],cutter['polygon'])
    if not hit:return [subject]
    result=[]
    for poly in convex_difference(subject['polygon'],cutter['polygon']):
        item=dict(subject,polygon=poly);result.append(item)
    # Below the cutter: lower stays, upper=min(subject.upper, cutter.lower).
    def emit(poly,lo,hi):
        valid=scalar_clip(poly,*[hi[i]-lo[i]-(.001 if i==2 else 0) for i in range(3)])
        if valid and abs(area(valid))>.1:result.append(dict(subject,polygon=valid,lo=lo,hi=hi))
    for i,u in enumerate([subject['hi'],cutter['lo']]):
        other=[subject['hi'],cutter['lo']][1-i]
        if i and same_plane(u,other):continue
        poly=hit if same_plane(u,other) else scalar_clip(hit,*[other[j]-u[j] for j in range(3)])
        emit(poly,subject['lo'],u)
    # Above the cutter: upper stays, lower=max(subject.lower, cutter.upper).
    for i,l in enumerate([subject['lo'],cutter['hi']]):
        other=[subject['lo'],cutter['hi']][1-i]
        if i and same_plane(l,other):continue
        poly=hit if same_plane(l,other) else scalar_clip(hit,*[l[j]-other[j] for j in range(3)])
        emit(poly,l,subject['hi'])
    return result
