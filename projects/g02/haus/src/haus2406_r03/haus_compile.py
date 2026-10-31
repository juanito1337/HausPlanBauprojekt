# -*- coding: utf-8 -*-
"""Vom Plan-Datensatz zum deterministischen, NX-unabhaengigen Bauauftrag.

Oeffnungen entstehen durch Zerlegen von Wandflaechen und Hoehenintervallen.
Innerhalb gleicher Hoehenintervalle eines Parts werden Wandueberlappungen
entfernt. Partuebergreifende Anschluesse bleiben gesondert zu pruefen.
Die Oeffnungsgeometrie ist echt, aber KEIN nativer BIM-Tuer-/Fenster-Feature.
Positionen/Breiten und Topologieaenderungen erfordern einen erneuten Aufbau.
"""
import math
from .haus_geometry import (Parameters,validate,area,clean,pieces,wall_polygon,opening_polygon,
    convex_intersection,convex_difference,remove_overlaps,enabled)
from .haus_roof import compile_roofs,height,scalar_clip
from .haus_details import add_details
from .haus_quality import profile_audit


def fmt(expr):
    return format(expr,'.12g') if isinstance(expr,(int,float)) else str(expr)


def expr_add(a,b):return '('+fmt(a)+')+('+fmt(b)+')'


def expr_sub(a,b):return '('+fmt(a)+')-('+fmt(b)+')'


def split_openings(polygon,wall,params,allow_estimates):
    """Disjunkte XY-Zellen, jede mit der Liste ihrer auszunehmenden Oeffnungen."""
    cells=[(polygon,[])]
    for opening in wall.get('openings',[]):
        if not enabled(opening,params,allow_estimates)[0]:continue
        cutter=opening_polygon(wall,opening,params)
        new=[]
        for cell,active in cells:
            overlap=convex_intersection(cell,cutter)
            if overlap:
                new.extend((piece,active) for piece in convex_difference(cell,cutter))
                new.append((overlap,active+[opening]))
            else:new.append((cell,active))
        cells=new
    return cells


def wall_intervals(wall,openings,params):
    intervals=[(wall['bottom'],wall['top'])]
    for opening in openings:
        ob=expr_add(opening.get('height_reference',wall['bottom']),opening['sill']);ot=expr_add(ob,opening['height'])
        next_items=[]
        for lo,hi in intervals:
            lv,hv,ov,tv=[params.number(v) for v in (lo,hi,ob,ot)]
            if tv<=lv or ov>=hv:next_items.append((lo,hi));continue
            if ov>lv+0.01:next_items.append((lo,ob))
            if tv<hv-0.01:next_items.append((ot,hi))
        intervals=next_items
    return intervals


def roof_pieces(poly,bottom,top,roof_faces,params,thickness):
    """Aufteilen und an die vereinfachte Dach-Unterseite begrenzen.

    Rueckgabe (Grundflaeche, Dachflaeche oder None). Ausschnitte, die vollstaendig
    unterhalb der Unterkante liegen, erzeugen kein sinnloses/nullhohes Solid.
    """
    low=params.number(bottom);high=params.number(top)
    remaining=[poly];result=[]
    for face in roof_faces:
        overlap=convex_intersection(poly,face['polygon'])
        if not overlap:continue
        remaining=remove_overlaps(remaining,[face['polygon']])
        a,b,c=face['plane']
        valid=scalar_clip(overlap,a,b,c-thickness-low-0.1)
        if not valid:continue
        under=scalar_clip(valid,-a,-b,high+thickness-c)
        above=scalar_clip(valid,a,b,c-thickness-high)
        # Bei ebenengleicher horizontaler Decke nicht doppelt ausgeben.
        if abs(a)+abs(b)<1e-10 and abs(c-thickness-high)<1e-8:
            result.append((valid,None));continue
        if under:result.append((under,face))
        if above:result.append((above,None))
    result.extend((r,None) for r in remaining)
    return result


def compile_house(data,allow_estimates=False):
    check=validate(data)
    if check['errors']:raise ValueError('Datensatzfehler: '+'; '.join(check['errors']))
    params=Parameters(data['parameters'])
    if data.get('main_details'):
        from .haus_main_details import validate_main_data
        validate_main_data(data,params)
    roofs=compile_roofs(data,params) if allow_estimates else []
    # Das niedrige Anbaudach ist kein Dachabschluss fuer das Haupt-DG.
    dg_roofs=[r for r in roofs if r['parent'] not in ('DACH_ANBAU','DACH_GARAGE')]
    roof_t=params.value('DACH_HUELLE_PROXY') if allow_estimates else 0
    result={'mode':'PRUEFMODELL_MIT_NAEHERUNGEN' if allow_estimates else 'REFERENZGERUEST',
            'parts':[],'coverage':[],'warnings':[], 'roof_faces':roofs}
    def coverage(ident,part,kind,status,note='',count=0):
        result['coverage'].append({'id':ident,'part':part,'kind':kind,'status':status,'note':note,'planned_solids':count})
    for source_part in data['parts']:
        part={'id':source_part['id'],'file':source_part['file'],'solids':[],'references':source_part.get('references',[])}
        part['source_fact_ids']=source_part.get('source_fact_ids',[])
        result['parts'].append(part);previous={}
        for wall in source_part.get('walls',[]):
            ok,reason=enabled(wall,params,allow_estimates)
            if not ok:
                coverage(wall['id'],part['id'],'WAND',reason)
                for o in wall.get('openings',[]):coverage(o['id'],part['id'],'OEFFNUNG','WIRTSWAND_NICHT_GEBAUT')
                continue
            count_before=len(part['solids'])
            key=(params.number(wall['bottom']),params.number(wall['top']))
            old=previous.setdefault(key,[])
            fragments=remove_overlaps(pieces(wall_polygon(wall,params)),old)
            old.extend(fragments)
            for fragment in fragments:
                for cell,openings in split_openings(fragment,wall,params,allow_estimates):
                    for lo,hi in wall_intervals(wall,openings,params):
                        roof_parts=roof_pieces(cell,lo,hi,dg_roofs if part['id']=='DG' else roofs,params,roof_t) if part['id']=='DG' or wall.get('trim_to_roof',False) else [(cell,None)]
                        for poly,roof in roof_parts:
                            if abs(area(poly))<0.1:continue
                            serial=len(part['solids'])-count_before+1
                            part['solids'].append({'id':wall['id']+'_S%03d'%serial,'parent':wall['id'],
                              'kind':'WAND','polygon':poly,'bottom':lo,'top':hi,'roof_clip':roof,
                              'meta':wall,'opening_neighbors':[o['id'] for o in openings]})
            count=len(part['solids'])-count_before
            coverage(wall['id'],part['id'],'WAND','GEPLANT_NAEHERUNG' if count else 'DURCH_VERSCHNITT_ENTFALLEN',
                     'Wand in disjunkte Koerper aufgeteilt; Oeffnungen durch ausgelassene Volumenbereiche.',count)
            for o in wall.get('openings',[]):
                ok,reason=enabled(o,params,allow_estimates)
                hit=any(convex_intersection(f,opening_polygon(wall,o,params)) for f in fragments)
                coverage(o['id'],part['id'],'OEFFNUNG','GEPLANT_NAEHERUNG' if ok and hit else reason if not ok else 'KEIN_WANDREST_AM_ORT',
                         'Hohlraum in Wand; optionale generische Einbauteile separat in Abdeckung aufgefuehrt.')
        for slab in source_part.get('slabs',[]):
            ok,reason=enabled(slab,params,allow_estimates)
            if not ok:coverage(slab['id'],part['id'],'DECKE',reason);continue
            fragments=pieces(slab['polygon'])
            for hole in slab.get('holes',[]):
                hp=hole['polygon'] if isinstance(hole,dict) else hole
                for cutter in pieces(hp):fragments=remove_overlaps(fragments,[cutter])
            for i,poly in enumerate(fragments):
                part['solids'].append({'id':slab['id']+'_S%03d'%(i+1),'parent':slab['id'],'kind':'DECKE',
                                      'polygon':poly,'bottom':slab['bottom'],'top':slab['top'],'meta':slab})
            coverage(slab['id'],part['id'],'DECKE','GEPLANT_NAEHERUNG','Polygonzerlegung mit ausgesparten Deckenoeffnungen.',len(fragments))
        for prism in source_part.get('prisms',[]):
            ok,reason=enabled(prism,params,allow_estimates)
            if ok:part['solids'].append(dict(prism,kind='PRISMA',parent=prism['id'],meta=prism))
            coverage(prism['id'],part['id'],'PRISMA','GEPLANT_NAEHERUNG' if ok else reason,count=1 if ok else 0)
        for ref in source_part.get('references',[]):coverage(ref['id'],part['id'],'REFERENZ','REFERENZ_KEIN_BAUTEIL')
        if part['id']=='DACH':
            for face in roofs:
                points=[[p[0],p[1],height(face,p)] for p in face['polygon']]
                part['solids'].append({'id':face['id'],'parent':face['parent'],'kind':'DACH',
                    'points':points,'vector':[0,0,-roof_t],'meta':face})
            for roof in data.get('roof_definitions',[])+data.get('dormers',[]):
                n=sum(1 for f in roofs if f['parent']==roof['id'])
                coverage(roof['id'],part['id'],'DACH_PRUEFHUELLE','GEPLANT_NAEHERUNG' if allow_estimates else 'NAEHERUNG_GESPERRT',
                         'Vereinfachte Dachhuelle; Gaubendachflaechen mit optionalen geometrischen Wangen; Anschluesse nicht konstruktiv freigegeben.',n)
    for room in data.get('rooms',[]):coverage(room['id'],room['level'],'RAUM','NUR_REGISTER','Keine geschlossene Raumvolumen- oder Wohnflaechenberechnung.')
    if allow_estimates:
        add_details(data,result,params)
        from .haus_construction import apply_construction
        apply_construction(data,result,params)
    from .haus_site import apply_site, apply_flat_roofs
    apply_flat_roofs(data,result,params,allow_estimates)
    apply_site(data,result)
    for part in result['parts']:
        part['source_fact_ids']=[f['id'] for f in data.get('source_facts',[]) if part['id'] in f.get('part_ids',[])]
    if allow_estimates and data.get('video_roof_windows'):
        from .haus_video import cut_video_roof_windows
        cut_video_roof_windows(data,result)
    if allow_estimates and data.get('main_details'):
        from .haus_main_details import apply_main_details
        apply_main_details(data,result,params)
    result['profile_audit']=profile_audit(result)
    result['planned_solids']=sum(len(p['solids']) for p in result['parts'])
    result['warnings'].extend([
        'Geometrie aus grafisch uebertragenen Scans; keine zugesicherte Massgenauigkeit.',
        'Kein vollstaendiges Bestands-, Tragwerks-, Genehmigungs- oder natives BIM-Modell.',
        'Dachhuellen vereinfacht, Anschluesse Hauptbau/Anbau und DG-Decke nicht konstruktiv geloest.',
        'Einbauteile haben generische angenommene Profile; keine Hersteller-/Anschlagdaten. Treppen bleiben Referenzkonturen.',
        'XY-Lagen/Topologie/Dachgeometrie erfordern Neuaufbau; keine globale Interpart-Assoziativitaet.'
    ])
    return result
