# -*- coding: utf-8 -*-
"""MAIN01: visible house attachments, explicitly approximate and reversible.

No new NX API. These are convex vertical prisms using the existing build path.
All exterior member profiles are representation envelopes, not structural sizes.
"""
import copy
import math
from .haus_geometry import area, clean, pieces, remove_overlaps, convex_intersection, Parameters
from .haus_roof import plane_for, scalar_clip, height, compile_roofs


def main_basis(data):
    a=data['main_details']['anchor']['a'];b=data['main_details']['anchor']['b']
    length=math.dist(a,b)
    if length<1:raise ValueError('MAIN01 Balkonachse ungueltig')
    t=[(b[i]-a[i])/length for i in range(2)];n=[t[1],-t[0]]
    return a,t,n


def main_xy(data,u,v):
    a,t,n=main_basis(data)
    return [a[i]+t[i]*u+n[i]*v for i in range(2)]


def uv_rect(data,u0,v0,u1,v1):
    if u1<=u0 or v1<=v0:raise ValueError('MAIN01 leeres Rechteck')
    return clean([main_xy(data,u,v) for u,v in [(u0,v0),(u1,v0),(u1,v1),(u0,v1)]])


def metadata(ident,category,note,page=2,material='UNGEKLAERT'):
    return {'id':ident,'category':category,'revision':'MAIN01','status':'GESCHAETZT',
            'phase':'BESTAND','sources':[{'document':'M01','page':page,'location':note}],
            'material':material,'quantity_excluded':True,'as_built_verified':False,
            'representation':'VIDEOREFERENZ_MIT_GESCHAETZTEN_MASSEN',
            'construction_status':'ABMESSUNGEN_AUFLAGER_BEFESTIGUNG_UNBESTAETIGT',
            'load_bearing_status':'KEIN_TRAGFAEHIGKEITSNACHWEIS',
            'note':note+' Keine Werkstatt-/Montagegeometrie; keine statische Freigabe.'}


def _part(ident,filename):
    return {'id':ident,'file':filename,'solids':[],'references':[]}


def _add(part,ident,poly,bottom,top,note,category='MAIN01_DETAIL',page=2,**fields):
    meta=metadata(ident,category,note,page)
    meta.update(fields.pop('meta_fields',{}))
    part['solids'].append(dict(id=ident,parent=ident,kind=category,polygon=clean(poly),
                               bottom=bottom,top=top,meta=meta,**fields))


def _circle(x,y,r,count=16):
    return [[x+r*math.cos(i*2*math.pi/count),y+r*math.sin(i*2*math.pi/count)] for i in range(count)]


def _add_band(part,data,ident,rect,bottom,top,note,**kw):
    _add(part,ident,uv_rect(data,*rect),bottom,top,note,**kw)


def _trim_balcony_roof(compiled,poly):
    changes=[]
    for part in compiled['parts']:
        if part['id']!='DACH':continue
        result=[]
        for s in part['solids']:
            if s.get('parent')!='DACH_QUER' or s.get('kind')!='DACH':
                result.append(s);continue
            oldpoly=[p[:2] for p in s['points']]
            overlap=convex_intersection(oldpoly,poly)
            if not overlap:result.append(s);continue
            plane=plane_for(s['points']);parts=remove_overlaps([oldpoly],[poly])
            for j,p in enumerate(parts,1):
                ns=copy.deepcopy(s);ns['id']=s['id']+'_MAIN01_BALKON_REST_%02d'%j
                ns['points']=[[x,y,plane[0]*x+plane[1]*y+plane[2]] for x,y in p]
                ns['meta']['main_balcony_cut']=True
                result.append(ns)
            changes.append({'old_id':s['id'],'removed_xy_mm2':abs(area(overlap)),'remaining_fragments':len(parts)})
        part['solids']=result
    return changes


def apply_main_details(data,compiled,params):
    cfg=data.get('main_details')
    if not cfg or not cfg.get('enabled'):return
    if cfg.get('schema')!='MAIN01_HOUSE_DETAIL_V1':raise ValueError('MAIN01 Detailschema')
    # The compiler only invokes this hook in the explicitly allowed estimate mode.
    P=lambda k:params.value(k)
    Z=P('Z_DG');u0=P('BAL_U_START');u1=u0+P('BAL_LAENGE');v0=P('BAL_V_START');v1=v0+P('BAL_PROJEKTION')
    deck_t=P('BAL_BELAG_DICKE');edge_h=P('BAL_RANDHOEHE');edge_b=P('BAL_RAND_BREITE')
    note='Video 01:30-01:42 + P05 Balkon 3.4.9 + P22 Stahl/Holz; lokale Konturzuordnung und Details nicht aufgemessen.'
    compiled['main01_review']={'technical_approval':False,'modelled_balconies':1,
       'estimated_balcony_area_m2':abs(area(uv_rect(data,u0,v0,u1,v1)))/1e6,
       'plan_area_label_m2':8.74,'plan_area_label_not_equated_to_footprint':True,
       'roof_cut':_trim_balcony_roof(compiled,uv_rect(data,u0,v0,u1,v1)),
       'concealed_foundations_or_joist_grid_added':False,'metric_as_built_verified':False}
    bal=_part('BALKON_RECHTS','10_BALKON_RECHTS_MAIN01.prt')
    _add_band(bal,data,'M01_BAL_BELAG_EINHUELLENDE',[u0,v0,u1,v1],Z-deck_t,Z,note,category='BALKON_BELAG')
    # Three edge envelopes with butt joints, no invented transverse joist grid.
    for label,rect in [
        ('VORN',[u0,v0,u0+edge_b,v1]),
        ('HINTEN',[u1-edge_b,v0,u1,v1]),
        ('AUSSEN',[u0+edge_b,v1-edge_b,u1-edge_b,v1])]:
        _add_band(bal,data,'M01_BAL_RAND_'+label,rect,Z-deck_t-edge_h,Z-deck_t,
                  note+' Nur sichtbarer Rand als Einhuellende; kein tatsaechlich bestimmtes Stahlprofil.',category='BALKON_RAND')
    # The two visible posts are not given fictitious buried footings or tube thickness.
    r=P('BAL_STUETZE_D')/2
    for i,(u,v) in enumerate([(u0+170,v1-edge_b/2),(u1-170,v1-edge_b/2)],1):
        x,y=main_xy(data,u,v)
        _add(bal,'M01_BAL_STUETZE_%02d_EINHUELLENDE'%i,_circle(x,y,r),P('BAL_STUETZE_FUSS'),Z-deck_t-edge_h,
             note+' Rundprofil nur 16-seitige Aussenhuelle. Unteres Ende provisorisch; kein Vollstahl-/Fundamentkoerper.',category='BALKON_STUETZE')
    # Slatted screen seen in the video; row count is an illustrative segmentation.
    rows=cfg['balcony']['horizontal_board_rows'];bh=P('BAL_BRETT_H');bt=P('BAL_BRETT_T');rh=P('BAL_GELAENDER_H');base=100
    gap=(rh-base-rows*bh)/(rows-1)
    if gap<0:raise ValueError('MAIN01 Balkonbekleidung passt nicht in ihre Hoehe')
    for i in range(rows):
        bot=Z+base+i*(bh+gap)
        for label,rect in [('VORN',[u0,v0,u0+bt,v1]),('HINTEN',[u1-bt,v0,u1,v1]),
                           ('AUSSEN',[u0+bt,v1-bt,u1-bt,v1])]:
            _add_band(bal,data,'M01_BAL_LAMELLE_%s_%02d'%(label,i+1),rect,bot,bot+bh,
                      note+' Horizontale Bekleidung sichtbar; sieben Anzeigezeilen sind keine vermessene Brettzahl.',category='BALKON_BEKLEIDUNG')
    # Inner posts do not interpenetrate the outer boards. Profiles remain proxies.
    post=40
    for i,(u,v) in enumerate([(u0+bt,v0),(u0+bt,v1-bt-post),(u1-bt-post,v0),(u1-bt-post,v1-bt-post)],1):
        _add_band(bal,data,'M01_BAL_GELAENDERSTIEL_%02d'%i,[u,v,u+post,v+post],Z,Z+rh,
                  note+' Gelaenderunterkonstruktion grob modelliert, Befestigung und Staenderzahl nicht bestaetigt.',category='BALKON_GELAENDER')
    compiled['parts'].append(bal)
    # Side cheeks close the raised access roof envelope, not a load-bearing dormer.
    niche=_part('BALKON_ZUGANG','11_BALKON_ZUGANG_MAIN01.prt')
    roof=next(f for f in compiled['roof_faces'] if f['parent']=='MAIN01_BALKON_ZUGANG_DACH');newplane=roof['plane'];thick=P('BAL_NISCHE_HUELLE')
    original=copy.deepcopy(data);original['main_roof_faces']=[]
    rawfaces=compile_roofs(original,params)
    us=[P('BAL_TUER_OFFSET')-150,P('BAL_TUER_OFFSET')+P('BAL_TUER_BREITE')+150]
    upper=list(newplane);upper[2]-=thick
    for i,u in enumerate(us,1):
        strip=uv_rect(data,u if i==1 else u-30,-1500,u+30 if i==1 else u,-75)
        idx=0
        for face in rawfaces:
            if face['parent']!='DACH_QUER':continue
            hit=convex_intersection(strip,face['polygon'])
            if not hit:continue
            lo=list(face['plane'])
            diff=[upper[j]-lo[j] for j in range(3)];diff[2]-=.01
            hit=scalar_clip(hit,*diff)
            if not hit:continue
            idx+=1;bottom=min(lo[0]*x+lo[1]*y+lo[2] for x,y in hit);top=max(upper[0]*x+upper[1]*y+upper[2] for x,y in hit)
            _add(niche,'M01_BAL_NISCHENWANGE_%d_%02d'%(i,idx),hit,bottom,top,
                'P05/P19 und Video 01:30/01:36: Zugangsnische. Geschätzte Anschlussflaechen, keine ausgefuehrte Dachkonstruktion.',
                category='BALKON_NISCHE',bottom_plane=lo,top_plane=upper)
    compiled['parts'].append(niche)
    # Guard at the visible cellar descent; not a guessed flight or basement excavation.
    if cfg['cellar_railing']['enabled']:
        guard=_part('KELLERABGANG_GELAENDER','12_KELLERABGANG_GELAENDER_MAIN01.prt')
        ku0,ku1=cfg['cellar_railing']['u_range'];kv0,kv1=cfg['cellar_railing']['v_range'];kv0=max(kv0,850)
        z0=P('ABGANG_BEZUG_Z');z1=z0+P('ABGANG_GELAENDER_H');bar=30
        gn='Video 01:38-01:42: sichtbares Schutzgelaender am Kellerabgang. Lage und Abmessungen grob, kein Schutz-/Normnachweis; Stufen/Unterbau nicht ergaenzt.'
        edges=[('LANG',ku0,kv1,ku1,kv1),('VORN',ku0,kv0,ku0,kv1),('ENDE',ku1,kv1-550,ku1,kv1)]
        for label,ua,va,ub,vb in edges:
            # Crossbar as an orthogonal local rectangle.
            horizontal=abs(ub-ua)>0
            rect=[min(ua,ub),va-bar/2,max(ua,ub),va+bar/2] if horizontal else [ua-bar/2,min(va,vb),ua+bar/2,max(va,vb)]
            # Shorten long rail near end returns to avoid false intersections.
            if horizontal:rect[0]+=bar/2;rect[2]-=bar/2
            _add_band(guard,data,'M01_KG_HANDLAUF_'+label,rect,z1-bar,z1,gn,category='ABGANG_GELAENDER',page=3)
            length=math.hypot(ub-ua,vb-va);num=max(2,int(length/cfg['cellar_railing']['vertical_spacing_mm']))
            for k in range(num):
                f=(k+.5)/num;u=ua+(ub-ua)*f;v=va+(vb-va)*f
                x,y=main_xy(data,u,v)
                _add(guard,'M01_KG_STAB_%s_%02d'%(label,k+1),_circle(x,y,10,12),z0,z1-bar,gn,category='ABGANG_GELAENDER',page=3)
        compiled['parts'].append(guard)
    if cfg['downpipes']['enabled']:
        drain=_part('FALLROHR_SICHTABSCHNITTE','13_FALLROHR_REFERENZEN_MAIN01.prt')
        for item in cfg['downpipes']['items']:
            x,y=item['xy']
            _add(drain,item['id'],_circle(x,y,P('FALLROHR_PROXY_D')/2),item['bottom'],item['top'],
                 item['evidence']+' Nur oberirdischer sichtbarer Abschnitt; keine Wandstaerke, unterirdische Fortsetzung oder Entwaesserungsbemessung.',category='FALLROHR_EINHUELLENDE',page=3)
        compiled['parts'].append(drain)
    for part in [p for p in compiled['parts'] if p['id'] in {'BALKON_RECHTS','BALKON_ZUGANG','KELLERABGANG_GELAENDER','FALLROHR_SICHTABSCHNITTE'}]:
        compiled['coverage'].append({'id':part['id'],'part':part['id'],'kind':'MAIN01_VIDEOANBAUTEIL',
            'status':'GEPLANT_NAEHERUNG','note':'Sichtbare Existenz belegt; Maße/Anschlüsse unbestätigt. Kein Tragwerksnachweis.', 'planned_solids':len(part['solids'])})
    compiled['warnings'].append('MAIN01: Balkon, Nische, Geländer und Fallrohre enthalten ausdrücklich geschätzte Anzeigequerschnitte; keine statische/ausführungsreife Konstruktion.')


def validate_main_data(data,params):
    cfg=data['main_details']
    if cfg.get('schema')!='MAIN01_HOUSE_DETAIL_V1' or type(cfg.get('enabled')) is not bool:
        raise ValueError('MAIN01 falsches Detailschema oder enabled-Typ')
    if not cfg['enabled']:raise ValueError('MAIN01 ist ein abgestimmter Stand; Details nicht teilweise deaktivieren. Referenzmodus im Startdialog verwenden.')
    if data.get('main_baseline',{}).get('metric_as_built_verified') is not False:
        raise ValueError('MAIN01 hat keinen metrischen Bestandsnachweis')
    if data.get('main_baseline',{}).get('structural_approval') is not False:
        raise ValueError('MAIN01 hat keinen Tragwerksnachweis')
    anchor=cfg['anchor'];walls=[w for p in data['parts'] for w in p.get('walls',[]) if w['id']==anchor['wall_id']]
    if len(walls)!=1 or any(math.dist(anchor[k],walls[0][k])>.001 for k in ('a','b')):
        raise ValueError('MAIN01 Balkonanker stimmt nicht mit Wirtswand ueberein')
    L=math.dist(anchor['a'],anchor['b']);p=params.value
    for key in ['BAL_PROJEKTION','BAL_LAENGE','BAL_BELAG_DICKE','BAL_RANDHOEHE','BAL_RAND_BREITE','BAL_STUETZE_D',
                'BAL_GELAENDER_H','BAL_BRETT_H','BAL_BRETT_T','BAL_TUER_BREITE','BAL_TUER_HOEHE','BAL_NISCHE_HUELLE','ABGANG_GELAENDER_H','FALLROHR_PROXY_D']:
        if not math.isfinite(p(key)) or p(key)<=0:raise ValueError('MAIN01 ungueltiger Parameter '+key)
    if p('BAL_PROJEKTION')<300 or p('BAL_LAENGE')<600:raise ValueError('MAIN01 Balkon fuer Darstellung zu klein')
    if p('BAL_TUER_OFFSET')<0 or p('BAL_TUER_OFFSET')+p('BAL_TUER_BREITE')>L:
        raise ValueError('MAIN01 Balkontuer ausserhalb der Wirtswand')
    if p('BAL_STUETZE_FUSS')>=p('Z_DG')-p('BAL_BELAG_DICKE')-p('BAL_RANDHOEHE'):
        raise ValueError('MAIN01 Stuetzenfuss oberhalb Randunterkante')
    if abs(p('BAL_NISCHE_HUELLE')-p('DACH_HUELLE_PROXY'))>.001:
        raise ValueError('MAIN01 Nische verwendet gemeinsame Dach-Pruefhuellendicke; keine unabhaengige Schichtannahme')
    if p('BAL_NISCHE_DACH_VORN')-p('BAL_NISCHE_HUELLE')<p('Z_DG')+p('BAL_TUER_HOEHE')+20:
        raise ValueError('MAIN01 Nischenhoehe laesst Balkontuer nicht frei')
    rows=cfg['balcony']['horizontal_board_rows']
    if type(rows) is not int or not 2<=rows<=30:raise ValueError('MAIN01 ungueltige Anzeige-Lamellenzahl')
    if rows*p('BAL_BRETT_H')>p('BAL_GELAENDER_H')-100:raise ValueError('MAIN01 Lamellenhoehen passen nicht')
    for k in ['balcony','cellar_railing','downpipes']:
        if type(cfg[k]['enabled']) is not bool:raise ValueError('MAIN01 Detail-Schalter muss bool sein')
    if cfg['balcony']['enabled'] is not True:
        raise ValueError('MAIN01 aktueller Nischenabgleich setzt Balkon aktiviert voraus; keine halbe Teilkonfiguration')
    for item in cfg['downpipes']['items']:
        if item['top']<=item['bottom'] or not all(math.isfinite(v) for v in item['xy']+[item['top'],item['bottom']]):
            raise ValueError('MAIN01 ungueltiges Fallrohrsegment')
    return True
