# -*- coding: utf-8 -*-
"""R02: optionale geometrische Einbauteile und Gaubenverschluesse.

Alle Profilquerschnitte sind ausdrueckliche Visualisierungsannahmen. Die acht
neuen Gaubenfenster haben planbeschriftete Breiten/Hoehen, aber ihre Einbaulage
und Bruestung sind weiterhin grafisch bzw. unbestaetigt. KEINE BIM-Objekte.
"""
import math
from .haus_geometry import (area,clean,enabled,convex_intersection,rectangle,opening_polygon)
from .haus_roof import (compile_roofs,dormer,resolve_dormer,scalar_clip,height)
from .haus_quality import plane_z
from .haus_audit import vertical_record,intersection_volume,subtract_vertical


def addz(base,offset):return '('+str(base)+')+('+format(offset,'.12g')+')'


def inserts_for(wall,opening,params,defaults):
    """Ungeteiltes generisches Fenster / geschlossenes Tuerblatt; keine
    unbelegte Fluegelteilung, Anschlagseite oder Beschlagklassifizierung.
    Getrennte Balken ohne doppelt gezahltes Eckvolumen.
    """
    a=wall['a'];b=wall['b'];L=math.dist(a,b);u=[(b[i]-a[i])/L for i in (0,1)];n=[-u[1],u[0]]
    t=params.number(wall['thickness']);off=params.number(opening['offset'])
    W=params.number(opening['width']);H=params.number(opening['height'])
    centre=t*(wall.get('material_left_fraction',0.5)-0.5)
    gap=float(defaults['mounting_gap_mm']);face=float(defaults['frame_face_mm'])
    depth=min(float(defaults['frame_depth_mm']),t-2*gap)
    if min(W,H)<2*(gap+face)+20 or depth<=0:
        raise ValueError('Einbauprofil passt nicht in Oeffnung '+opening['id'])
    base='('+str(opening.get('height_reference',wall['bottom']))+')+('+str(opening['sill'])+')'
    result=[]
    def box(label,x0,x1,d0,d1,z0,z1,category,material):
        if min(x1-x0,d1-d0,z1-z0)<=0:raise ValueError('Ungultiger Einbauquerschnitt '+opening['id']+' '+label)
        xy=lambda x,d:[a[j]+u[j]*(off+x)+n[j]*(centre+d) for j in (0,1)]
        poly=clean([xy(x0,d0),xy(x1,d0),xy(x1,d1),xy(x0,d1)])
        meta=dict(opening,id=opening['id']+'_'+label,status='GESCHAETZT',material=material,host_wall=wall['id'],detail_origin='GENERISCHE_PROFILGEOMETRIE',quantity_excluded=True,note='Querschnitt und Einbauspalt nicht aus Ausfuehrungsdetail; angenommene Visualisierung.')
        result.append({'id':meta['id'],'parent':opening['id'],'kind':category,'polygon':poly,'bottom':addz(base,z0),'top':addz(base,z1),'meta':meta,'host_wall':wall['id']})
    def frame(prefix,x0,x1,z0,z1,d,bar,category,material,bottom=True):
        box(prefix+'_L',x0,x0+bar,-d/2,d/2,z0,z1,category,material)
        box(prefix+'_R',x1-bar,x1,-d/2,d/2,z0,z1,category,material)
        box(prefix+'_O',x0+bar,x1-bar,-d/2,d/2,z1-bar,z1,category,material)
        if bottom:box(prefix+'_U',x0+bar,x1-bar,-d/2,d/2,z0,z0+bar,category,material)
    if opening.get('kind')=='FENSTER':
        frame('RAHMEN',gap,W-gap,gap,H-gap,depth,face,'FENSTERRAHMEN','RAHMENPROXY')
        sg=float(defaults['sash_gap_mm']);sf=float(defaults['sash_face_mm']);sd=min(float(defaults['sash_depth_mm']),depth)
        x0=gap+face+sg;x1=W-gap-face-sg;z0=gap+face+sg;z1=H-gap-face-sg
        if min(x1-x0,z1-z0)<=2*sf:raise ValueError('Fensterfluegel zu klein '+opening['id'])
        panes=opening.get('video_panes',1)
        if type(panes) is not int or panes not in (1,2):
            raise ValueError('Unbelegte/ungueltige Video-Fluegelteilung '+opening['id'])
        gd=min(float(defaults['glazing_thickness_mm']),sd-2)
        if panes == 1:
            frame('FLUEGEL',x0,x1,z0,z1,sd,sf,'FENSTERFLUEGEL','FLUEGELPROXY')
            box('GLAS',x0+sf,x1-sf,-gd/2,gd/2,z0+sf,z1-sf,'GLAS','GLASPAKETPROXY')
        else:
            # Observed pair; mullion/profile dimensions remain visual assumptions.
            mid=(x0+x1)/2;bar=face
            box('PFOSTEN',mid-bar/2,mid+bar/2,-depth/2,depth/2,gap+face,H-gap-face,'FENSTERRAHMEN','PFOSTENPROXY')
            for index,(left,right) in enumerate(((x0,mid-bar/2-sg),(mid+bar/2+sg,x1)),1):
                if right-left <= 2*sf:raise ValueError('Geteilter Fluegel zu klein '+opening['id'])
                frame('FLUEGEL_%d'%index,left,right,z0,z1,sd,sf,'FENSTERFLUEGEL','FLUEGELPROXY')
                box('GLAS_%d'%index,left+sf,right-sf,-gd/2,gd/2,z0+sf,z1-sf,'GLAS','GLASPAKETPROXY')
    else:
        frame('ZARGE',gap,W-gap,gap,H-gap,depth,face,'TUERZARGE','ZARGENPROXY',False)
        leaf=min(float(defaults['door_leaf_mm']),depth)
        box('BLATT_GESCHLOSSEN',gap+face+3,W-gap-face-3,-leaf/2,leaf/2,gap+5,H-gap-face-3,'TUERBLATT','TUERBLATTPROXY')
    return result


def compile_inserts(data,result,params):
    source_parts={p['id']:p for p in data['parts']};built=[]
    all_walls=[vertical_record(s,params,p['id']) for p in result['parts'] for s in p['solids'] if s['kind']=='WAND']
    for part in result['parts']:
        source=source_parts.get(part['id'])
        if not source:continue
        wall_records=[vertical_record(s,params,part['id']) for s in part['solids'] if s['kind']=='WAND']
        for w in source.get('walls',[]):
            if not enabled(w,params,True)[0]:continue
            for o in w.get('openings',[]):
                if not enabled(o,params,True)[0]:continue
                # Never add a visible insert for a disabled/unbuilt opening.
                cover=next((c for c in result['coverage'] if c['id']==o['id']),None)
                if not cover or not cover['status'].startswith('GEPLANT'):continue
                # A frame can fit while the declared clear opening is partially blocked.
                # Check the entire opening before creating any visual insert.
                poly=opening_polygon(w,o,params,extra=0)
                z=params.number(o.get('height_reference',w['bottom']))+params.number(o['sill'])
                top=z+params.number(o['height'])
                void={'polygon':poly,'lo':[0,0,z],'hi':[0,0,top]}
                B=[min(q[k] for q in poly) for k in (0,1)]+[z]+[max(q[k] for q in poly) for k in (0,1)]+[top]
                blocked=[]
                for r in all_walls:
                    A=r['box']
                    if any(min(A[k+3],B[k+3])-max(A[k],B[k])<=.001 for k in range(3)):continue
                    if intersection_volume(void,r)>1000:blocked.append(r['id'])
                if blocked:
                    result['coverage'].append({'id':o['id']+'_EINBAUTEIL','part':part['id'],'kind':'EINBAUTEIL_PROXY',
                      'status':'GESPERRT_OEFFNUNG_BLOCKIERT','note':'Volle Oeffnung nicht frei: '+', '.join(sorted(set(blocked)))+'. Keine unbelegte Lage-/Breitenaenderung.',
                      'planned_solids':0})
                    result['warnings'].append('Einbauteil '+o['id']+' gesperrt: deklarierte Oeffnung teilweise durch Wand blockiert.')
                    continue
                inserts=inserts_for(w,o,params,data['visual_defaults'])
                collisions=[]
                for insert in inserts:
                    ri=vertical_record(insert,params,part['id']);B=ri['box']
                    for wall_record in wall_records:
                        A=wall_record['box']
                        if any(min(A[k+3],B[k+3])-max(A[k],B[k])<=.001 for k in range(3)):continue
                        if intersection_volume(ri,wall_record)>1000:collisions.append(wall_record['id'])
                if collisions:
                    result['coverage'].append({'id':o['id']+'_EINBAUTEIL','part':part['id'],'kind':'EINBAUTEIL_PROXY','status':'GESPERRT_KOLLISION','note':'Komplettes Einbauteil nicht erzeugt: ueberschneidet vorhandene Wand '+', '.join(sorted(set(collisions)))+'. Oeffnungsposition/Anschluss zuerst klaeren.','planned_solids':0})
                    result['warnings'].append('Einbauteil '+o['id']+' wegen Wandkollision gesperrt.')
                    continue
                part['solids'].extend(inserts);built.append(o['id'])
                result['coverage'].append({'id':o['id']+'_EINBAUTEIL','part':part['id'],'kind':'EINBAUTEIL_PROXY','status':'GEPLANT_NAEHERUNG','note':'Geschlossenes generisches Einbauteil. Querschnitt, Lichtmassbezug und Einbauspalt sind nicht bestaetigt.','planned_solids':len(inserts)})
    result['detail_counts']={'opening_inserts':len(built),'window_door_solids':sum(s['kind'] in ('FENSTERRAHMEN','FENSTERFLUEGEL','GLAS','TUERZARGE','TUERBLATT') for p in result['parts'] for s in p['solids'])}


def compile_cheeks(data,result,params):
    """Seiten- und Rueckverschluesse zwischen Hauptdach und Gaubenunterseite.
    Ein vorhandener DG-Fassadenstreifen bildet die Front, nicht eine zweite
    ueberlagerte Wand. Ebene Unter- und Obergrenzen werden spaeter in NX getrimmt.
    """
    base=compile_roofs(data,params,include_dormers=False)
    part=next(p for p in result['parts'] if p['id']=='DG');count=0
    for item in data.get('dormers',[]):
        if not enabled(item,params,True)[0]:continue
        item=resolve_dormer(item,params,base)
        x0,y0,x1,y1=[params.number(v) for v in item['rect']]
        f=dormer(item,params);t=float(data['visual_defaults']['cheek_thickness_mm'])
        h=params.value('DACH_HUELLE_PROXY');axis=item['front_axis']
        # The existing facade owns the front 140 mm: no duplicate corner volume.
        if axis=='xmin':x0+=t
        elif axis=='xmax':x1-=t
        else:y0+=t
        # Inner-side strips; subtract the front and avoid double-counted rear corners.
        if axis=='xmin':
            strips=[('SEITE_A',[[x0,y0],[x1,y0],[x1,y0+t],[x0,y0+t]]),('SEITE_B',[[x0,y1-t],[x1,y1-t],[x1,y1],[x0,y1]]),('RUECKEN',[[x1-t,y0+t],[x1,y0+t],[x1,y1-t],[x1-t,y1-t]])]
        elif axis=='xmax':
            strips=[('SEITE_A',[[x0,y0],[x1,y0],[x1,y0+t],[x0,y0+t]]),('SEITE_B',[[x0,y1-t],[x1,y1-t],[x1,y1],[x0,y1]]),('RUECKEN',[[x0,y0+t],[x0+t,y0+t],[x0+t,y1-t],[x0,y1-t]])]
        else:
            strips=[('SEITE_A',[[x0,y0],[x0+t,y0],[x0+t,y1],[x0,y1]]),('SEITE_B',[[x1-t,y0],[x1,y0],[x1,y1],[x1-t,y1]]),('RUECKEN',[[x0+t,y1-t],[x1-t,y1-t],[x1-t,y1],[x0+t,y1]])]
        if item.get('rear_attachment')=='INTERSECTION_WITH_HOST':
            # The roof rear meets the host; do not invent a vertical rear wall.
            strips=[entry for entry in strips if entry[0]!='RUECKEN']
        added=0
        for label,poly in strips:
            for g in base:
                if g['parent'] not in ('DACH_HAUPT','DACH_QUER'):continue
                overlap=convex_intersection(poly,g['polygon'])
                if not overlap:continue
                difference=[f['plane'][i]-g['plane'][i] for i in range(3)];difference[2]-=0.1
                valid=scalar_clip(overlap,*difference)
                if not valid or area(valid)<1:continue
                lower=list(g['plane']);upper=list(f['plane']);lower[2]-=h;upper[2]-=h
                ident=item['id']+'_'+label+'_%02d'%(added+1)
                meta={'id':ident,'status':'GESCHAETZT','phase':'UNGEKLAERT','sources':item['sources'],'material':'GAUBENWANGENPROXY','quantity_excluded':True,'note':'140-mm-Ersatzwand zwischen zwei vorlaeufigen Dachflaechen; keine nachgewiesene Holzrahmenkonstruktion.'}
                part['solids'].append({'id':ident,'parent':item['id'],'kind':'GAUBENWANGE','polygon':valid,'bottom':min(plane_z(lower,q) for q in valid),'top':max(plane_z(upper,q) for q in valid),'bottom_plane':lower,'top_plane':upper,'meta':meta})
                added+=1;count+=1
        result['coverage'].append({'id':item['id']+'_WANGEN','part':'DG','kind':'GAUBENWANGEN_PROXY','status':'GEPLANT_NAEHERUNG','note':('Zwei Seiten bis zum berechneten Dachanschluss; keine kuenstliche Rueckwand. Front ist bestehende DG-Wand.' if item.get('rear_attachment') else 'Zwei Seiten und Anschlussseite, zugeschnitten zwischen vorlaeufigen Dachflaechen. Front ist bestehende DG-Wand.'),'planned_solids':added})
    result.setdefault('detail_counts',{})['dormer_cheek_solids_before_junction_trim']=count
    trim_cheek_junctions(result,params)


def add_details(data,result,params):
    options=data.get('detail_options',{})
    if options.get('opening_inserts',False):compile_inserts(data,result,params)
    if options.get('dormer_cheeks',False):compile_cheeks(data,result,params)


def trim_cheek_junctions(result,params):
    part=next(p for p in result['parts'] if p['id']=='DG')
    cutters=[vertical_record(s,params,'DG') for s in part['solids'] if s['kind'] in ('WAND','FENSTERRAHMEN','FENSTERFLUEGEL','GLAS','TUERZARGE','TUERBLATT')]
    fixed=[];changes=[]
    for solid in part['solids']:
        if solid['kind']!='GAUBENWANGE':fixed.append(solid);continue
        record=vertical_record(solid,params,'DG');parts=[record];hits=[]
        for cutter in cutters:
            if intersection_volume(record,cutter)<=1:continue
            parts=[r for fragment in parts for r in subtract_vertical(fragment,cutter)]
            hits.append(cutter['id'])
        for i,piece in enumerate(parts):
            poly=piece['polygon'];lo=piece['lo'];hi=piece['hi']
            item=dict(solid,polygon=poly,bottom_plane=lo,top_plane=hi,bottom=min(plane_z(lo,q) for q in poly),top=max(plane_z(hi,q) for q in poly))
            if len(parts)>1:item['id']=solid['id']+'_J%02d'%(i+1)
            fixed.append(item)
        if hits:changes.append({'id':solid['id'],'cutters':hits,'result_pieces':len(parts)})
    part['solids']=fixed
    counts={}
    for s in fixed:
        if s['kind']=='GAUBENWANGE':counts[s['parent']]=counts.get(s['parent'],0)+1
    for c in result['coverage']:
        if c['kind']=='GAUBENWANGEN_PROXY':c['planned_solids']=counts.get(c['id'].replace('_WANGEN',''),0)
    result['detail_counts']['dormer_cheek_solids']=sum(counts.values())
    result['detail_junction_trim']=changes
