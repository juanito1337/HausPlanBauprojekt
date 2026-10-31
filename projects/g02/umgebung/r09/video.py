# -*- coding: utf-8 -*-
"""R10 visual observations -> reversible enrichment of a private runtime dataset.

No photogrammetric measurement, no new load-bearing members. Existing house
source data stays immutable. Dimensions/placements of the new objects are
explicit modelling estimates; visibility and pane pattern are separate facts.
No new NX API. Runtime uses existing extrude and assembly paths only.
"""
import copy
import json
import math
from pathlib import Path
from haus2406_r03.haus_geometry import (Parameters, clean, area, convex_intersection,
                                       convex_difference, pieces, validate)
from haus2406_r03.haus_roof import compile_roofs, height


def _rectangle(rect):
    if len(rect)!=4 or not all(type(x) in (int,float) and math.isfinite(x) for x in rect):
        raise ValueError('R10: invalid finite XY rectangle')
    x0,y0,x1,y1=rect
    if x1<=x0 or y1<=y0:raise ValueError('R10: reversed or zero-size rectangle')
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]


def _meta(ident, role, evidence, page, note):
    return {'id':ident,'revision':'R10','status':'GESCHAETZT','phase':'BESTAND',
            'sources':[{'document':'V10','page':page,'location':evidence}],
            'video_evidence':evidence,'video_presence':'IM_BILD_SICHTBAR',
            'video_dimensions':'NICHT_VERMESSEN_MODELLANNAHME',
            'video_role':role,'quantity_excluded':True,'as_built_verified':False,
            'representation':'VIDEOREFERENZ_MIT_GESCHAETZTER_GEOMETRIE',
            'detail_origin':'VIDEO_BEOBACHTUNG_MASSE_UNBESTAETIGT',
            'construction_status':'KEIN_HERSTELLER_ODER_ANSCHLUSSNACHWEIS',
            'material':'NICHT_PHYSIKALISCH_ZUGEWIESEN','note':note}


def _roof_host(faces, polygon, ident, parent):
    # The roof compiler can split one plane into many disjoint XY fragments.
    # A window may span these internal seams, but never a real plane break.
    wanted=abs(area(polygon));groups=[]
    for f in faces:
        if f['parent']!=parent:continue
        overlap=convex_intersection(polygon,f['polygon'])
        if not overlap:continue
        group=next((g for g in groups if max(abs(f['plane'][i]-g['face']['plane'][i]) for i in range(3))<1e-7),None)
        if group is None:
            group={'face':f,'overlap_area':0.};groups.append(group)
        group['overlap_area']+=abs(area(overlap))
    hits=[g['face'] for g in groups if abs(g['overlap_area']-wanted)<.1]
    if len(hits)!=1:
        raise ValueError('R10 '+ident+': expected one complete roof plane, got '+str(len(hits))+'; areas='+str([(g['face']['plane'],g['overlap_area']) for g in groups]))
    return hits[0]


def _prism(ident, polygon, host, offset, thickness, meta):
    if offset<0 or thickness<=0:raise ValueError('R10 invalid surface offset or display thickness')
    return dict(meta,id=ident,points=[[x,y,height(host,[x,y])+offset] for x,y in clean(polygon)],
                vector=[0,0,thickness])


def validate_spec(spec):
    if spec.get('schema')!='VIDEO_R10_V1':raise ValueError('R10 video schema')
    if type(spec.get('enabled')) is not bool:raise ValueError('R10 enabled must be bool')
    if spec.get('geometric_as_built_verified') is not False:raise ValueError('R10 no measurement proof available')
    if spec.get('structural_approval') is not False:raise ValueError('R10 cannot infer structural approval')
    if spec.get('video_audio_transcribed') is not False:raise ValueError('R10 audio not transcribed')
    if spec.get('video_duration_s',0)<=0:raise ValueError('R10 video duration missing')
    if len(spec.get('video_sha256',''))!=64:raise ValueError('R10 source hash missing')
    ids=[]
    for item in spec['roof_windows']+spec['pv_fields']:
        ids.append(item['id'])
        if not item.get('evidence') or not 1<=item.get('evidence_page',0)<=spec['evidence_pages']:
            raise ValueError('R10 source page missing '+item['id'])
        if item.get('dimension_status')!='GESCHAETZT':raise ValueError('R10 unsourced dimensions')
        if 'rect_mm' in item:_rectangle(item['rect_mm'])
        for rect in item.get('rectangles_mm',[]):_rectangle(rect)
    if len(set(ids))!=len(ids):raise ValueError('R10 duplicate new element ids')
    w=spec['front_dormer']
    if [a['panes'] for a in w['groups']] != [1,2,2,2,1]:raise ValueError('R10 observed pane grouping changed')
    ends=[]
    for g in w['groups']:
        if g['width_mm']<=0 or g['offset_mm']<0:raise ValueError('R10 bad dormer dimensions')
        ends.append((g['offset_mm'],g['offset_mm']+g['width_mm']))
    if any(a[1]>=b[0] for a,b in zip(ends,ends[1:])):raise ValueError('R10 overlapping dormer openings')
    return True


def enrich_house(data,spec):
    validate_spec(spec)
    if not spec['enabled']:return copy.deepcopy(data)
    if data.get('video_revision'):raise ValueError('R10 must not be applied twice')
    d=copy.deepcopy(data);params=Parameters(d['parameters']);faces=compile_roofs(d,params)
    d['source_document_pages']['V10']=spec['evidence_pages']
    change={'revision':'R10','base_geometry':'R06','video_file':spec['video_file'],
            'video_sha256':spec['video_sha256'],'observations':copy.deepcopy(spec['observations']),
            'metric_reconstruction':False,'hidden_construction_reconstructed':False,
            'audio_transcribed':False,'as_built_approved':False,'changes':[],
            'display_values_are_not_material_dimensions':True}
    f=spec['front_dormer']
    wall=next(w for p in d['parts'] for w in p['walls'] if w['id']==f['wall_id'])
    old=copy.deepcopy(wall['openings'])
    keep=[w for w in old if w['id'] not in f['replace_ids']]
    if len(old)-len(keep)!=len(f['replace_ids']):raise ValueError('R10 expected dormer openings not found')
    template=next(w for w in old if w['id']==f['replace_ids'][0])
    for i,g in enumerate(f['groups'],1):
        ident='R10_DG_STRASSE_F%02d'%i
        o=copy.deepcopy(template);o.update(_meta(ident,'GAUBENFENSTER',f['evidence'],1,
          'Sichtbare Gruppen 1+2+2+2+1; drei Doppelbreiten aus bisherigem Modell, '
          'zwei Randbreiten und neue Positionen geschaetzt. Kein Aufmass, kein Eingriffsvorschlag.'))
        o.update(offset=g['offset_mm'],width=g['width_mm'],video_panes=g['panes'],
                 phase='BESTAND',height_reference_status='VORHERIGER_MODELLHOEHENBEZUG_UNVERAENDERT')
        keep.append(o)
    wall['openings']=keep
    change['changes'].append({'kind':'GAUBENFENSTER','wall':wall['id'],
                             'before':old,'after':copy.deepcopy(keep),
                             'what_is_observed':'5 Gruppen / 8 sichtbare Felder',
                             'what_is_estimated':'Positionen, Randbreiten, Profilquerschnitte'})
    newparts={
      'VIDEO_DACHFENSTER':{'id':'VIDEO_DACHFENSTER','file':'08_VIDEO_DACHFENSTER_R10.prt','walls':[],'slabs':[],'prisms':[],'references':[]},
      'VIDEO_SOLARFELDER':{'id':'VIDEO_SOLARFELDER','file':'09_VIDEO_SOLARFELDER_R10.prt','walls':[],'slabs':[],'prisms':[],'references':[]}}
    cuts=[]
    for item in spec['roof_windows']:
        rect=item['rect_mm'];poly=_rectangle(rect);host=_roof_host(faces,poly,item['id'],item['roof_parent'])
        x0,y0,x1,y1=rect;bar=item['frame_width_xy_mm']
        if min(x1-x0,y1-y0)<=2*bar+10:raise ValueError('R10 skylight frame too wide')
        note='Im Video erkennbares Dachfenster; XY aus Bild-/Modellzuordnung geschaetzt. '
        note+='Nennmass, Einbauhoehe, Eindeckrahmen und Wechselkonstruktion unbekannt. '
        note+='Aussparung nur in der vereinfachten Dachhuelle, nicht in einem Dachtragwerk.'
        meta=_meta(item['id'],'DACHFLAECHENFENSTER',item['evidence'],item['evidence_page'],note)
        tiles=[('L',[x0,y0,x0+bar,y1]),('R',[x1-bar,y0,x1,y1]),
               ('U',[x0+bar,y0,x1-bar,y0+bar]),('O',[x0+bar,y1-bar,x1-bar,y1])]
        for label,r in tiles:
            newparts['VIDEO_DACHFENSTER']['prisms'].append(_prism(item['id']+'_RAHMEN_'+label,_rectangle(r),host,10,50,meta))
        newparts['VIDEO_DACHFENSTER']['prisms'].append(_prism(item['id']+'_GLAS',_rectangle([x0+bar,y0+bar,x1-bar,y1-bar]),host,15,10,meta))
        cuts.append({'id':item['id'],'polygon':poly,'roof_parent':host['parent'],
                     'roof_plane':host['plane'],'meta':meta})
    d['video_roof_windows']=cuts
    # Solar fields are estimated footprint envelopes, NOT individual module counts.
    # Every rectangle must remain on one plane; no invented bent modules across hips.
    for item in spec['pv_fields']:
        meta=_meta(item['id'],'SOLARFELD_UMRISS',item['evidence'],item['evidence_page'],
            'Existenz im Video; Umriss/Lage aus Bildverhaeltnissen geschaetzt. '
            'Keine Modulzahl, Leistung, Last, Halterung oder Dachanschlusskonstruktion. '
            '60 mm Abstand und 30 mm Dicke sind rein vertikale Anzeigeparameter.')
        count=0
        for ri,rect in enumerate(item['rectangles_mm'],1):
            poly=_rectangle(rect);host=_roof_host(faces,poly,item['id'],item['roof_parent'])
            fragments=[poly]
            for window in spec['roof_windows']:
                if window['roof_parent']!=item['roof_parent']:continue
                x0,y0,x1,y1=window['rect_mm'];pad=item['window_clearance_xy_mm']
                cutter=_rectangle([x0-pad,y0-pad,x1+pad,y1+pad])
                fragments=[s for p in fragments for s in convex_difference(p,cutter)]
            for fi,p in enumerate(fragments,1):
                count+=1;ident=item['id']+'_R%d_S%02d'%(ri,fi)
                newparts['VIDEO_SOLARFELDER']['prisms'].append(_prism(ident,p,host,60,30,meta))
        change['changes'].append({'kind':'SOLARFELD_UMRISS','id':item['id'],'display_bodies':count,
                                 'module_count':None,'dimensions_verified':False})
    d['parts'].extend(newparts.values())
    change['changes'].append({'kind':'DACHFENSTER','new_windows':len(cuts),
                             'display_bodies':len(newparts['VIDEO_DACHFENSTER']['prisms']),
                             'openings_only_in_roof_proxy':True})
    d['video_revision']=change
    errors=validate(d)['errors']
    if errors:raise ValueError('R10 enriched data invalid: '+str(errors))
    return d


def enrich_if_present(base,data):
    path=Path(base)/'video/VIDEO_DETAILS_R10.json'
    if not path.is_file():return copy.deepcopy(data)
    spec=json.loads(path.read_text(encoding='utf-8-sig'))
    from .windows_review import apply_if_present
    return apply_if_present(base,enrich_house(data,spec))
