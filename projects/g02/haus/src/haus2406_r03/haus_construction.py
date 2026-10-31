# -*- coding: utf-8 -*-
"""R04: belegte Bauteilschichten, offene Tragglieder und Plausibilitaet.

Kein Statikprogramm. Keine Standardquerschnitte, keine abgeleiteten Raster aus
ueblicher Baupraxis. Numerische Modelleigenschaften und Quellen getrennt halten.
"""
import copy
import math
from collections import Counter
from .haus_geometry import Parameters, area, clean, convex_intersection
from .haus_roof import scalar_clip
from .haus_audit import same_plane


def _dot(a,b): return sum(x*y for x,y in zip(a,b))
def _sub(a,b): return [x-y for x,y in zip(a,b)]
def _cross(a,b): return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
def _unit(a):
    length=math.sqrt(_dot(a,a))
    if length<1e-9: raise ValueError('Nullrichtung fuer Tragglied')
    return [x/length for x in a]


def layer_polygons(wall,params):
    """Schichten entlang einseitiger Aussenreferenz, von aussen nach innen.
    Luftschichten geben ein kontrollierbares Leerraum-Polygon, KEIN Material.
    """
    layers=wall.get('construction_layers',[])
    if not layers:return []
    if abs(wall.get('material_left_fraction',.5)-1)>1e-9:
        raise ValueError(wall['id']+': Schichtwand braucht eindeutige Aussenkante links/inwendig.')
    a,b=wall['a'],wall['b'];v=_sub(b,a);length=math.hypot(*v)
    if length<.01:raise ValueError('Leere Schichtwand '+wall['id'])
    n=[-v[1]/length,v[0]/length];depth=0.;result=[];ids=set()
    for layer in layers:
        if layer['id'] in ids:raise ValueError('Doppelte Schicht-ID '+wall['id'])
        ids.add(layer['id']);th=params.number(layer['thickness'])
        if not math.isfinite(th) or th<=0:raise ValueError('Nichtpositive Schichtdicke')
        lo,hi=depth,depth+th
        poly=clean([[a[i]+n[i]*lo for i in range(2)],[b[i]+n[i]*lo for i in range(2)],
                    [b[i]+n[i]*hi for i in range(2)],[a[i]+n[i]*hi for i in range(2)]])
        result.append(dict(layer,polygon=poly,offset_mm=lo,thickness_mm=th));depth=hi
    if abs(depth-params.number(wall['thickness']))>.001:
        raise ValueError(wall['id']+': Schichten passen nicht zur Gesamtdicke; kein stiller Ausgleich.')
    return result


def member_readiness(item):
    """Enabled is explicit; even an approved estimation mode cannot invent beams."""
    if type(item.get('enabled')) is not bool:raise ValueError('Tragglied enabled muss bool sein')
    fields=('start_mm','end_mm','section_mm','width_direction','source_dimension','source_placement')
    missing=[f for f in fields if not item.get(f)]
    if item.get('section_status') not in ('PLANWERT','ABGELEITET'):missing.append('section_status')
    if item.get('placement_status') not in ('PLANWERT','ABGELEITET'):missing.append('placement_status')
    if not item['enabled']:return {'status':'NICHT_MODELLIERT_OFFENE_TRAGGLIEDGRUPPE','missing':missing}
    if missing:raise ValueError(item['id']+': aktiviertes Tragglied ohne belegte Daten: '+', '.join(missing))
    for name in ('start_mm','end_mm','width_direction'):
        if not isinstance(item[name],list) or len(item[name])!=3 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in item[name]):
            raise ValueError(item['id']+': ungueltiger Vektor '+name)
    sec=item['section_mm']
    if not isinstance(sec,list) or len(sec)!=2 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) and x>0 for x in sec):
        raise ValueError(item['id']+': Querschnitt muss [Breite,Hoehe] > 0 sein')
    if math.dist(item['start_mm'],item['end_mm'])<.1:raise ValueError(item['id']+': Traggliedlaenge zu klein')
    # Source provenance must specify document/page/location, not just a filename-like token.
    for field in ('source_dimension','source_placement'):
        if not isinstance(item[field],list) or not item[field]:raise ValueError(item['id']+': Quellenliste fehlt')
        for src in item[field]:
            if not isinstance(src,dict) or not src.get('document') or not isinstance(src.get('page'),int) or src['page']<1 or not src.get('location'):
                raise ValueError(item['id']+': unvollstaendige Quelle '+field)
    return {'status':'BELEGTE_GEOMETRIE_ERZEUGBAR_KEIN_TRAGFAEHIGKEITSNACHWEIS','missing':[]}


def hull_xy(points):
    pts=sorted(set((float(p[0]),float(p[1])) for p in points))
    def cross(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[]
    for p in pts:
        while len(lower)>1 and cross(lower[-2],lower[-1],p)<=1e-9:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(pts):
        while len(upper)>1 and cross(upper[-2],upper[-1],p)<=1e-9:upper.pop()
        upper.append(p)
    return clean(lower[:-1]+upper[:-1])


def member_solids(item):
    """Rechteckiges Tragglied von Achspunkt zu Achspunkt, normaler Querschnitt.

    Kein Balken wird geraten. Ein obliquer Quader wird exakt in vertikale
    Prismen zwischen Ebenen zerlegt: vorhandene, getestete Extrusions-/Schnitt-
    wege genuegen auch fuer Sparren, keine erfundenen NX-Tragwerks-Builder.
    Nicht enthalten: Ausklinkungen, Kerven, Bohrungen und Verbindungsmittel.
    """
    ready=member_readiness(item)
    if not item['enabled']:return []
    a,b=item['start_mm'],item['end_mm'];e=_unit(_sub(b,a))
    wr=item['width_direction'];u0=[wr[i]-_dot(wr,e)*e[i] for i in range(3)]
    if math.sqrt(_dot(u0,u0))<1e-8:raise ValueError(item['id']+': Breitenrichtung parallel zur Laengsachse')
    u=_unit(u0);v=_unit(_cross(e,u));width,depth=item['section_mm']
    verts=[]
    for c in (a,b):
        for du,dv in ((-1,-1),(1,-1),(1,1),(-1,1)):
            verts.append([c[i]+du*width/2*u[i]+dv*depth/2*v[i] for i in range(3)])
    center=[(a[i]+b[i])/2 for i in range(3)]
    faces=((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))
    lower=[];upper=[];poly=hull_xy(verts)
    for idx in faces:
        p,q,r=[verts[j] for j in idx[:3]];n=_unit(_cross(_sub(q,p),_sub(r,p)))
        if _dot(n,_sub(center,p))>0:n=[-x for x in n]
        d=_dot(n,p)
        if abs(n[2])<1e-10:poly=scalar_clip(poly,-n[0],-n[1],d);continue
        plane=[-n[0]/n[2],-n[1]/n[2],d/n[2]]
        bank=upper if n[2]>0 else lower
        if not any(same_plane(plane,x) for x in bank):bank.append(plane)
    solids=[]
    def z(plane,p):return plane[0]*p[0]+plane[1]*p[1]+plane[2]
    for hi in upper:
        for lo in lower:
            region=poly
            for other in upper:
                if other is not hi:region=scalar_clip(region,*[other[j]-hi[j] for j in range(3)])
            for other in lower:
                if other is not lo:region=scalar_clip(region,*[lo[j]-other[j] for j in range(3)])
            region=scalar_clip(region,*[hi[j]-lo[j] for j in range(3)])
            if not region or abs(area(region))<.1:continue
            low=min(z(lo,p) for p in region);high=max(z(hi,p) for p in region)
            if high-low<.01:continue
            ident=item['id']+'_SEG_%03d'%(len(solids)+1)
            meta={'id':item['id'],'system_id':item.get('system_id',''),'category':item['kind'],
                  'status':'ABGELEITET','phase':'UNGEKLAERT','material':'HOLZ_ART_GUETE_OFFEN',
                  'construction_status':'BELEGTER_QUERSCHNITT_UND_ACHSE','load_bearing_status':'NICHT_NACHGEWIESEN',
                  'sources':item['source_dimension']+item['source_placement'],
                  'note':'Rechteckquerschnitt normal zur Achse; stirnseitig rechtwinklig. Keine Kerven/Auflagerdetails oder Tragfaehigkeitsfreigabe.'}
            solids.append({'id':ident,'parent':item['id'],'kind':'TRAGGLIED','polygon':region,
                           'bottom':low,'top':high,'bottom_plane':lo,'top_plane':hi,'meta':meta})
    if not solids:raise ValueError(item['id']+': kein Traggliedvolumen')
    return solids


def resolve_stair_wall_feet(compiled,params):
    """Lokale Modellannahme: zwei KS-Treppenhauswaende reichen bis Rohdecke.

    Anschluss ist als GESCHAETZT markiert, kein Auflagernachweis. Nachbarwaende
    behalten die bisherige Geometrie; nur Doppelvolumen der neuen Wandfuesse
    und der Bodenaufbau unter diesen beiden Waenden werden ausgespart.
    Kein globales automatisches Kollisionsbereinigen von Hauptbau/Anbau.
    """
    from .haus_audit import vertical_record, subtract_vertical, intersection_volume, integrate
    from .haus_quality import plane_z
    ids={'DG_W_TREPPEN_E','DG_W_TREPPEN_S'};operations=[]
    def subtract_one(solid,cutters,part_id):
        initial=vertical_record(solid,params,part_id); pieces=[initial];cuts=[]
        for cutter in cutters:
            next_pieces=[];removed=0.
            for piece in pieces:
                overlap=intersection_volume(piece,cutter)
                if overlap>.01:
                    removed+=overlap;next_pieces.extend(subtract_vertical(piece,cutter))
                else:next_pieces.append(piece)
            pieces=next_pieces
            if removed>.01:cuts.append({'cutter':cutter['id'],'removed_mm3':removed})
        if not cuts:return [solid]
        operations.append({'solid':solid['id'],'part':part_id,'cuts':cuts,
          'status':'MODELLANNAHME_WANDFUSS_BIS_ROHDECKE','scope':'Nur lokaler Anschluss; kein Bestands-/Tragfaehigkeitsnachweis'})
        out=[]
        for index,r in enumerate(pieces):
            q=copy.deepcopy(solid);q.pop('roof_clip',None)
            q.update(id=solid['id']+'_J%03d'%(index+1),polygon=r['polygon'],bottom_plane=r['lo'],top_plane=r['hi'],
              bottom=min(plane_z(r['lo'],x) for x in r['polygon']),top=max(plane_z(r['hi'],x) for x in r['polygon']))
            q['meta']['junction_status']='MODELLANNAHME_WANDFUSS_BIS_ROHDECKE'
            q['meta']['junction_note']='Lokale Geometriebereinigung am Treppenhaus: kein gemessenes Auflagerdetail; bei Datenaenderung neu aufbauen.'
            out.append(q)
        return out
    for part in compiled['parts']:
        if part['id']!='DG':continue
        neighbors=[vertical_record(s,params,part['id']) for s in part['solids'] if s['kind']=='WAND' and s['parent'] not in ids]
        first=[]
        for solid in part['solids']:
            first.extend(subtract_one(solid,neighbors,part['id']) if solid['kind']=='WAND' and solid['parent'] in ids else [solid])
        feet=[vertical_record(s,params,part['id']) for s in first if s['kind']=='WAND' and s['parent'] in ids]
        part['solids']=[]
        for solid in first:
            part['solids'].extend(subtract_one(solid,feet,part['id']) if solid['parent']=='DG_FUSSBODEN' else [solid])
    return operations


def apply_construction(data,compiled,params):
    """Apply source-based layers after opening cutting, not a visual skin overlay."""
    definitions={w['id']:w for p in data['parts'] for w in p.get('walls',[])}
    voids=[];layer_counts=Counter();member_rows=[]
    for part in compiled['parts']:
        new=[]
        for solid in part['solids']:
            wall=definitions.get(solid['parent'])
            if solid['kind']!='WAND' or not wall or not wall.get('construction_layers'):
                new.append(solid);continue
            for layer in layer_polygons(wall,params):
                poly=convex_intersection(solid['polygon'],layer['polygon'])
                if not poly or abs(area(poly))<.1:continue
                item=copy.deepcopy(solid);item['polygon']=poly;item['id']+='_'+layer['id']
                item['meta'].update(material=layer['material'],layer_id=layer['id'],layer_thickness_mm=layer['thickness_mm'],
                                    construction_status=wall['construction_status'],system_id=wall['system_id'])
                if not layer['physical']:
                    voids.append({'id':item['id'],'wall':wall['id'],'part':part['id'],'thickness_mm':layer['thickness_mm'],'status':'HOHLRAUM_KEIN_MATERIALKOERPER','polygon':poly})
                else:new.append(item);layer_counts[layer['material']]+=1
        part['solids']=new
    junctions=resolve_stair_wall_feet(compiled,params)
    bypart={p['id']:p for p in compiled['parts']}
    for member in data.get('construction',{}).get('pending_members',[]):
        state=member_readiness(member)
        if member['part'] not in bypart:raise ValueError('Unbekanntes Tragglied-Part '+member['part'])
        shapes=member_solids(member);bypart[member['part']]['solids'].extend(shapes)
        member_rows.append(dict(id=member['id'],system_id=member['system_id'],**state,planned_solids=len(shapes)))
        compiled['coverage'].append({'id':member['id'],'part':member['part'],'kind':member['kind'],'status':state['status'],
                                    'note':'Offene Parameter: '+', '.join(state['missing']),'planned_solids':len(shapes)})
    counts=Counter(s['parent'] for p in compiled['parts'] for s in p['solids'])
    for row in compiled['coverage']:
        if row['id'] in counts and row['kind'] in ('WAND','DECKE'): 
            row['planned_solids']=counts[row['id']]
        if row['id'] in definitions and definitions[row['id']].get('construction_layers'):
            row['planned_solids']=counts[row['id']];row['note']='Getrennte Baustoffschichten; Luftschicht als Hohlraum. Quellenvariante mit offenem Dickenkonflikt.'
    compiled['construction_audit']={'scope':'Quellenmodell, keine Bemessung/keine Bestandsbestaetigung','physical_layer_pieces':dict(layer_counts),
                                    'voids':voids,'junction_operations':junctions,'members':member_rows,'source_conflicts':data.get('construction',{}).get('variant_conflicts',[]),
                                    'structural_calculation_provided':False}
    compiled['warnings'].append('R04: P21-Wintergartenwand 410 mm als offen benannte Quellenvariante; 365-mm-Bezug nicht abschliessend geklaert.')
    compiled['warnings'].append('R04: Keine erfundenen Sparren/Pfetten/Binder/Deckenbalken. Tragsystem bekannt, Einzelgeometrie aus Statik/Aufmass fehlt.')
    compiled['warnings'].append('R04: Anbau-Balkenzone nicht als Vollholzblock dargestellt. Estrich/Daemmschicht besitzen noch kein auskonstruiertes Auflager.')
    return compiled


def source_plausibility(data,compiled):
    """Inventory-level checks, intentionally distinct from volume collision checks."""
    p=Parameters(data['parameters']);wallrows=[]
    for part in data['parts']:
        for w in part.get('walls',[]):
            wallrows.append({'id':w['id'],'part':part['id'],'thickness_mm':p.number(w['thickness']),
              'material':w.get('material','UNGEKLAERT'),'system':w.get('system_id','UNGEKLAERT'),
              'construction_status':w.get('construction_status','UNGEKLAERT'),
              'load_bearing_status':w.get('load_bearing_status','UNGEKLAERT'),
              'as_built_verified':False,'sources':w.get('sources',[])})
    issues=[
      {'id':'K01','severity':'KRITISCH','topic':'TRAGWERK_UNVOLLSTAENDIG','evidence':'P13/P18 verweisen auf Statik; im 31-PDF-Archiv keine Positions-/Bewehrungs-/Holzbauplaene als eigenstaendige Dokumente gefunden.','action':'Statische Berechnung mit Positionsplan, Holzbau-/Binder-/Deckenplan beschaffen. Nicht aus Bauteilhoehen ersetzen.'},
      {'id':'K02','severity':'KRITISCH','topic':'PLANSTAND_ISTZUSTAND','evidence':'Baubeschreibungen 1995/1996 sind Planungsunterlagen; Beschreibung2015 benennt keine Eingriffe in die Konstruktion.','action':'Bauteile am Haus bestaetigen; spaetere Umbauten/Materialzustand nicht bekannt.'},
      {'id':'K03','severity':'KRITISCH','topic':'GESCHOSSREGISTRIERUNG','evidence':'EG/KG/DG wurden aus unterschiedlichen Scans mit unabhaengigen Bezugskonturen abgeleitet.','action':'Gemeinsame Achsen/Hauptmasse aufmessen, keine pauschale Verschiebung oder Skalierung.'},
      {'id':'K04','severity':'KRITISCH','topic':'HAUPTBAU_ANBAU_ANSCHLUSS','evidence':'Numerische Kollisionen im Quellenmodell verbleiben; Materiallagen und Maueranschluss sind nicht zweifelsfrei zugeordnet.','action':'Schnitt/Detail/Bestandsmass am Anschluss; kein blindes Boolesch-Abschneiden fuer scheinbar kollisionsfreie Optik.'},
      {'id':'K05','severity':'OFFEN','topic':'WINTERGARTEN_410_365','evidence':'P21: 175+80+40+115=410 mm; P09 weist 365-mm-Massbezug im Wintergartenbereich aus.','action':'R04 zeigt explizit P21-Variante; tatsaechliche Wanddicke innen/aussen und Zuordnung am Bau pruefen.'},
      {'id':'K06','severity':'OFFEN','topic':'WINTERGARTEN_GLASFRONT','evidence':'Falsch platzierte grosse Glasoeffnung aus rechter massiver Wand entfernt; echte Ostfront nicht vollstaendig bemaesst.','action':'Lage/Teilung/Unterzug/Anschluss und Rahmen aufmessen.'},
      {'id':'K07','severity':'KRITISCH','topic':'DACHHUELLE_IST_KEIN_DACHSTUHL','evidence':'200-mm-Huelle bleibt geometrischer Ersatz; 140 mm Daemmung sind kein Sparrenquerschnitt.','action':'Pfetten/Sparren/Stiele/Kehlbalken/Binder und Gaubenwechsel separat mit Quellen dimensionieren.'},
      {'id':'K08','severity':'OFFEN','topic':'WANDDICKE_IST_KEIN_TRAGFAEHIGKEITSNACHWEIS','evidence':'P22 unterscheidet KS und Leichtbau. 100/115/140/240/365 mm im Modell teils nur grafisch zugeordnet.','action':'Wandarten und Deckenauflager einzeln bestaetigen; nicht aus Dicke automatisch tragend/nichttragend zuweisen.'},
      {'id':'K09','severity':'OFFEN','topic':'TREPPEN_BALKON_SCHORNSTEIN_FUNDAMENTE','evidence':'P22 Stb-Treppe und Stahl/Holz-Balkon; P18 Holztreppe; P21 Schiedel-Schornstein und frostfreies Fundament. Einzelmasse fehlen.','action':'Keine scheingenauen Profile/Bewehrung erfinden. Als fehlende Konstruktion inventarisieren.'},
      {'id':'K10','severity':'OFFEN','topic':'NX_ISTMODELL','evidence':'Kein aktuelles manifest/bauauftrag oder NX-Part des gelungenen Nutzerlaufs vorhanden.','action':'Pruefung hier gilt Datensatz/Code, nicht jede vom Nutzer beobachtete Abweichung. R04 protokolliert jede Koerperbox in NX.'}
    ]
    return {'scope':'Gesamtes Quellenmodell und Konstruktionsvollstaendigkeit; keine Standsicherheitsbemessung',
            'wall_inventory':wallrows,'wall_thickness_distribution':dict(Counter(str(r['thickness_mm']) for r in wallrows)),
            'issues':issues,'construction':compiled.get('construction_audit',{}),'ready_for_roof_alteration_design':False}
