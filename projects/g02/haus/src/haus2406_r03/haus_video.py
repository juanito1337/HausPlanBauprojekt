# -*- coding: utf-8 -*-
"""R10 cut only the simplified roof shell around observed skylight proxies.
No structural member is cut or sized. All new placements remain estimates.
"""
import copy
from .haus_geometry import area,convex_intersection,convex_difference
from .haus_roof import height


def cut_video_roof_windows(data,compiled):
    windows=data.get('video_roof_windows',[])
    if not windows:return
    roof=next(p for p in compiled['parts'] if p['id']=='DACH')
    output=[];checks=[]
    old_projection=sum(abs(area([p[:2] for p in s['points']])) for s in roof['solids'])
    for s in roof['solids']:
        fragments=[[p[:2] for p in s['points']]];changed=False
        for w in windows:
            if s['parent']!=w['roof_parent']:continue
            next_pieces=[]
            for p in fragments:
                hit=convex_intersection(p,w['polygon'])
                if hit:
                    changed=True
                    next_pieces.extend(convex_difference(p,w['polygon']))
                else:next_pieces.append(p)
            fragments=next_pieces
        if not changed:output.append(s);continue
        from .haus_roof import plane_for
        face={'plane':plane_for(s['points'])}
        for i,p in enumerate(fragments,1):
            r=copy.deepcopy(s);r['id']=s['id']+'_V10_%03d'%i
            r['points']=[[x,y,height(face,[x,y])] for x,y in p]
            r['meta']['video_cut_note']='Dachfenster-Naeherung: nur Pruefhuelle ausgespart, kein Tragwerksdetail.'
            touched=[w for w in windows if w['roof_parent']==s['parent']
                     and convex_intersection([q[:2] for q in s['points']],w['polygon'])]
            r['meta']['sources']=list(r['meta'].get('sources',[]))+[
                src for w in touched for src in w['meta'].get('sources',[])]
            r['meta']['revision']='R10'
            r['meta']['video_evidence']='; '.join(w['meta']['video_evidence'] for w in touched)
            r['meta']['video_dimensions']='NICHT_VERMESSEN_MODELLANNAHME'
            r['meta']['video_role']='AUSSPARUNG_NUR_IN_DACHPRUEFHUELLE'
            output.append(r)
    new_projection=sum(abs(area([p[:2] for p in s['points']])) for s in output)
    expected_removed=sum(abs(area(w['polygon'])) for w in windows)
    if abs((old_projection-new_projection)-expected_removed)>.5:
        raise ValueError('R10 roof opening area not conserved; possible overlap or wrong host')
    for w in windows:
        remainder=sum(abs(area(hit)) for s in output if s['parent']==w['roof_parent']
                      for hit in [convex_intersection([q[:2] for q in s['points']],w['polygon'])] if hit)
        if remainder>.1:raise ValueError('R10 opening still covered: '+w['id'])
        checks.append({'id':w['id'],'remaining_roof_projection_mm2':remainder,
                       'as_built_verified':False,'scope':'Only simplified roof shell'})
    roof['solids']=output;compiled['video_roof_cut_check']=checks
    for c in compiled['coverage']:
        if c['part']=='DACH':
            c['planned_solids']=sum(s['parent']==c['id'] for s in output)
    compiled['warnings'].append('R10: Video zeigt Bauteile; neue Detailmasse/Lagen bleiben Annahmen. '
                               'Dachfenster nur durch Dach-Pruefhuelle, kein Tragwerksmodell.')
