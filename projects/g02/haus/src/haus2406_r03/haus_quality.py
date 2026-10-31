# -*- coding: utf-8 -*-
"""Numerische Endkontrolle. Keine CAD-Laufzeit, keine behauptete Planfreigabe."""
import math
from .haus_geometry import clean, area, cross

PROFILE_TOLERANCE_MM = 0.01


def sanitize_polygon(poly, tolerance=PROFILE_TOLERANCE_MM):
    """Entfernt nur Punkte innerhalb der Modelliertoleranz einer Nachbarkante.

    Die Polygonzerlegung selbst verwendet weiterhin die engere Rechentoleranz.
    Eine Flaechenkontrolle verhindert das unbemerkte Entfernen echter Details.
    """
    p=clean(poly)
    if not p:raise ValueError('Leeres Endprofil')
    before=abs(area(p)); initial=list(p); changed=True
    while changed and len(p)>3:
        changed=False;candidates=[]
        for i,b in enumerate(p):
            a=p[i-1];c=p[(i+1)%len(p)];length=math.dist(a,c)
            if length<=1e-10:continue
            dist=abs(cross(a,c,b))/length
            dot=((b[0]-a[0])*(c[0]-a[0])+(b[1]-a[1])*(c[1]-a[1]))/(length*length)
            if dist<=tolerance and -1e-8<=dot<=1+1e-8:
                candidates.append((dist,i))
        if candidates:
            _,index=min(candidates);p.pop(index);changed=True
    if min(math.dist(a,b) for a,b in zip(p,p[1:]+p[:1]))<tolerance:
        raise ValueError('Endprofil hat eine Kante unter %.4f mm'%tolerance)
    difference=abs(abs(area(p))-before)
    perimeter=sum(math.dist(a,b) for a,b in zip(initial,initial[1:]+initial[:1]))
    if difference>perimeter*tolerance+1e-5:
        raise ValueError('Profilbereinigung hat Flaeche unzulaessig veraendert')
    return p,{'removed_vertices':len(initial)-len(p),'area_change_mm2':difference}


def plane_z(plane,p):return plane[0]*p[0]+plane[1]*p[1]+plane[2]


def profile_audit(compiled):
    result={'status':'BESTANDEN','checked_profiles':0,'removed_vertices':0,'max_area_change_mm2':0.0,'changes':[],'discarded_numerical_slivers':[]}
    ids=set()
    for part in compiled['parts']:
        kept=[]
        for solid in part['solids']:
            if solid['id'] in ids:raise ValueError('Doppelte Bauauftrag-ID '+solid['id'])
            ids.add(solid['id'])
            if 'polygon' not in solid:
                kept.append(solid);continue
            poly=clean(solid['polygon'])
            max_edge=max(math.dist(a,b) for a,b in zip(poly,poly[1:]+poly[:1]))
            # Degenerate overlap residue narrower than the NX profile tolerance.
            # Its exact ID and lost projected area remain in the audit trail.
            minimum_width=min(max(abs(cross(a,b,q))/math.dist(a,b) for q in poly) for a,b in zip(poly,poly[1:]+poly[:1]) if math.dist(a,b)>1e-8)
            if minimum_width<PROFILE_TOLERANCE_MM:
                result['discarded_numerical_slivers'].append({'id':solid['id'],'parent':solid['parent'],'area_mm2':abs(area(poly)),'min_width_mm':minimum_width})
                continue
            try:new,change=sanitize_polygon(poly)
            except ValueError as ex:raise ValueError(solid['id']+': '+str(ex)) from ex
            solid['polygon']=new;result['checked_profiles']+=1;kept.append(solid)
            if change['removed_vertices']:
                result['changes'].append(dict(change,id=solid['id']))
                result['removed_vertices']+=change['removed_vertices']
                result['max_area_change_mm2']=max(result['max_area_change_mm2'],change['area_change_mm2'])
        part['solids']=kept
    for r in result['discarded_numerical_slivers']:
        for c in compiled['coverage']:
            if c['id']==r['parent']:
                c['planned_solids']-=1
                c['note']+=' Numerischer Splitter unter 0.01 mm entfernt: '+r['id']+'.'
    return result
