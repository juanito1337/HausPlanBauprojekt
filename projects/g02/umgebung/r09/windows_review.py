# -*- coding: utf-8 -*-
"""Reversible R11 window review, no new NX API and no inferred hidden structure.

Raw R06 and R10 evidence remain unchanged. New metric values are marked as
approximations; old values, sources, and removals are retained in a ledger.
"""
import copy
import math
from pathlib import Path
from .core import read_json
from haus2406_r03.haus_geometry import Parameters, validate
from haus2406_r03.haus_roof import compile_roofs


def checked_review(review):
    if review.get('schema') != 'R11_WINDOW_REVIEW_V1':
        raise ValueError('Unbekanntes Fensterabgleich-Schema')
    if type(review.get('enabled')) is not bool or review.get('metric_as_built_verified') is not False:
        raise ValueError('R11: kein metrischer Bestandsnachweis vorhanden')
    if review.get('source_document') != 'V11' or review.get('source_pages') != 8:
        raise ValueError('R11: Quellenbeleg fehlt')
    seen = set()
    for op in review['operations']:
        if op['action'] not in ('update','add','remove') or not op.get('reason') or not op.get('plan'):
            raise ValueError('R11: unvollstaendiger Fensterbefund')
        if op['id'] in seen: raise ValueError('R11: doppelte Operation '+op['id'])
        seen.add(op['id'])
        if type(op.get('evidence_page')) is not int or not 1 <= op['evidence_page'] <= 8: raise ValueError('R11: Belegseite fehlt')
        for key, value in op.get('values',{}).items():
            if key in ('width','height','offset','sill'):
                if type(value) not in (int,float) or not math.isfinite(value):
                    raise ValueError('R11: numerischer Fensterwert fehlt '+op['id'])
                if value < 0 or (key in ('width','height') and value <= 0):
                    raise ValueError('R11: negativer/leerer Fensterwert '+op['id'])
            if key == 'video_panes' and (type(value) is not int or value not in (1,2)):
                raise ValueError('R11: ungesicherte Teilung '+op['id'])
    return review


def apply_review(data, review):
    checked_review(review)
    if not review['enabled']: return copy.deepcopy(data)
    if data.get('window_review_revision'): raise ValueError('R11 doppelt angewandt')
    if not data.get('video_revision'): raise ValueError('R11 benoetigt R10-Videoausgangsstand')
    d=copy.deepcopy(data)
    d['source_document_pages']['V11']=8
    walls={w['id']:w for part in d['parts'] for w in part['walls']}
    ledger=[]
    for op in review['operations']:
        if op['wall_id'] not in walls: raise ValueError('R11: Wirtswand fehlt '+op['wall_id'])
        wall=walls[op['wall_id']]
        hits=[o for o in wall.get('openings',[]) if o['id']==op['id']]
        if op['action']=='add':
            if hits: raise ValueError('R11: neue ID bereits vorhanden '+op['id'])
            old=None
            new={'id':op['id'],'status':'GESCHAETZT','phase':'UNGEKLAERT','present_in_target':True,
                 'sources':[], 'kind':'FENSTER'}
        else:
            if len(hits)!=1: raise ValueError('R11: Ausgangsoeffnung fehlt/doppelt '+op['id'])
            old=copy.deepcopy(hits[0]); new=copy.deepcopy(old)
        if op['action']=='remove':
            wall['openings']=[o for o in wall['openings'] if o['id']!=op['id']]
            ledger.append(dict(op,before=old,after=None))
            continue
        new.update(copy.deepcopy(op['values']))
        new.update(revision='R11',status='GESCHAETZT',metric_as_built_verified=False,
                   window_review_id=op['id'],window_position_verified=False,
                   video_evidence=op['video'],plan_evidence=op['plan'],
                   plan_nominal_mm=copy.deepcopy(op.get('plan_nominal_mm')),
                   window_evidence_status=op['certainty'],note=op['reason'],
                   quantity_excluded=True,
                   detail_origin='R11_PLAN_VIDEO_REFERENZ_KEIN_AUFMASS')
        new['height_reference']=new.get('height_reference',wall['bottom'])
        new['height_reference_status']='FFB_MODELLBEZUG_KEIN_NEUER_HOEHENNACHWEIS'
        new['sources']=new.get('sources',[])+[{'document':'V11','page':op['evidence_page'],
            'location':'Einzelregister '+op['id']+'; '+op['plan']+'; Video '+op['video']}]
        if old is not None:
            wall['openings']=[new if o['id']==op['id'] else o for o in wall['openings']]
        else: wall.setdefault('openings',[]).append(new)
        ledger.append(dict(op,before=old,after=copy.deepcopy(new)))
    # Keep source-derived roof proxies unchanged except three new documented holes.
    from .video import _rectangle,_roof_host,_prism,_meta
    params=Parameters(d['parameters']);faces=compile_roofs(d,params)
    roofpart=next(p for p in d['parts'] if p['id']=='VIDEO_DACHFENSTER')
    existing={x['id'] for x in d['video_roof_windows']}
    for item in review['roof_windows_add']:
        if item['id'] in existing: raise ValueError('Dachfenster bereits vorhanden')
        poly=_rectangle(item['rect_mm']);host=_roof_host(faces,poly,item['id'],item['roof_parent'])
        x0,y0,x1,y1=item['rect_mm'];bar=item['frame_width_xy_mm']
        if bar<=0 or min(x1-x0,y1-y0)<=2*bar+10: raise ValueError('R11: Dachfensterprofil zu breit')
        meta=_meta(item['id'],'DACHFLAECHENFENSTER',item['evidence'],5,
                   'Existenz/ungefaehre Dachseite im Video; Rechteck/Lage/Nennmass nicht vermessen. Aussparung nur in Dach-Pruefhuelle, keine Sparrenwechsel.')
        meta.update(revision='R11',sources=[{'document':'V11','page':5,'location':item['evidence']}])
        tiles=[('L',[x0,y0,x0+bar,y1]),('R',[x1-bar,y0,x1,y1]),
               ('U',[x0+bar,y0,x1-bar,y0+bar]),('O',[x0+bar,y1-bar,x1-bar,y1])]
        for label,rect in tiles:
            roofpart['prisms'].append(_prism(item['id']+'_RAHMEN_'+label,_rectangle(rect),host,10,50,meta))
        roofpart['prisms'].append(_prism(item['id']+'_GLAS',_rectangle([x0+bar,y0+bar,x1-bar,y1-bar]),host,15,10,meta))
        d['video_roof_windows'].append({'id':item['id'],'polygon':poly,'roof_parent':host['parent'],
                                      'roof_plane':host['plane'],'meta':meta})
    d['window_review_revision']={'revision':'R11','operations':ledger,'new_roof_windows':copy.deepcopy(review['roof_windows_add']),
                                'metric_as_built_verified':False,'all_windows_verified':False,'video_audio_reviewed':False}
    errors=validate(d)['errors']
    if errors: raise ValueError('R11-Fensterdaten ungueltig: '+str(errors))
    return d


def apply_if_present(base,data):
    path=Path(base)/'abgleich/FENSTER_AENDERUNGEN_R11.json'
    return apply_review(data,read_json(path)) if path.is_file() else copy.deepcopy(data)
