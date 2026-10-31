# -*- coding: utf-8 -*-
"""Filter only after the complete source job was hash/geometry-definition checked."""
import copy
from pathlib import Path
from .core import read_json


def selected_job(base, job):
    path=Path(base)/'abgleich/VEGETATION_VIDEO_R11.json'
    if not path.is_file(): return copy.deepcopy(job), {'applied':False}
    r=read_json(path)
    if r.get('schema')!='R11_VEGETATION_REVIEW_V1' or r.get('review_is_metric_survey') is not False:
        raise ValueError('Vegetationsabgleich ist kein metrischer Nachweis')
    rows=r.get('groups',[])
    if len(rows)!=8 or {x['id'] for x in rows}!={'V%02d'%n for n in range(1,9)}:
        raise ValueError('Vegetationsabgleich unvollstaendig/doppelt')
    if any(type(x.get('include')) is not bool or not x.get('reason') or not x.get('video') for x in rows):
        raise ValueError('Vegetationsbefund ohne ausdrueckliche Entscheidung/Quelle')
    if type(r.get('ground_cover_F01_include')) is not bool: raise ValueError('F01-Status fehlt')
    active={'DGM'}|{x['id'] for x in rows if x['include']}
    if r['ground_cover_F01_include']:active.add('F01')
    ids={p['id'] for p in job['parts']}
    if not active.issubset(ids) or 'DGM' not in ids:raise ValueError('Bestaetigte Referenz fehlt im Importauftrag')
    out=copy.deepcopy(job)
    out['parts']=[p for p in out['parts'] if p['id'] in active]
    out['total_sheets']=sum(p['expected_sheets'] for p in out['parts'])
    report={'applied':True,'policy':r,'active_ids':[p['id'] for p in out['parts']],
            'not_automatically_imported':[p['id'] for p in job['parts'] if p['id'] not in active],
            'geometry_unchanged':True,'metric_as_built_verified':False,'active_source_sheets':out['total_sheets']}
    return out,report
