# -*- coding: utf-8 -*-
"""Offline-Voransicht aus denselben numerischen Bauauftraegen, KEIN NX-Render."""
from .haus_runtime import absolute_path
import html
import json
import math
from pathlib import Path
from .haus_geometry import Parameters
from .haus_compile import compile_house
from .haus_roof import height
from .haus_quality import plane_z
from .haus_audit import audit_compiled


def mesh_for(solid,params):
    if 'polygon' in solid:
        lo=params.number(solid['bottom']);hi=params.number(solid['top']);p=solid['polygon']
        bottom=[[q[0],q[1],plane_z(solid['bottom_plane'],q) if solid.get('bottom_plane') else lo] for q in p]
        top=[[q[0],q[1],min(hi,height(solid['roof_clip'],q)-params.value('DACH_HUELLE_PROXY'))
              if solid.get('roof_clip') else plane_z(solid['top_plane'],q) if solid.get('top_plane') else hi] for q in p]
    else:
        bottom=solid['points'];v=solid['vector']
        top=[[q[i]+v[i] for i in range(3)] for q in bottom]
    faces=[bottom[::-1],top]
    n=len(bottom)
    faces.extend([[bottom[i],bottom[(i+1)%n],top[(i+1)%n],top[i]] for i in range(n)])
    return [[[round(v,3) for v in p] for p in f] for f in faces]


def create_preview(base):
    base=Path(base);data=json.loads((base/'data'/'haus.json').read_text(encoding='utf-8'))
    params=Parameters(data['parameters']);compiled=compile_house(data,True);meshes=[]
    audit=audit_compiled(data,compiled);hits={c[k] for c in audit['collisions'] for k in ('a','b')}
    for part in compiled['parts']:
        for solid in part['solids']:
            meshes.append({'id':solid['id'],'part':part['id'],'kind':solid['kind'],'parent':solid['parent'],'collision':solid['id'] in hits,
                           'sources':solid['meta'].get('sources',[]),'note':solid['meta'].get('note',''),'material':solid['meta'].get('material',''),'quantity_excluded':solid['meta'].get('quantity_excluded',False),'faces':mesh_for(solid,params)})
    references=[dict(r,part=p['id']) for p in compiled['parts'] if p.get('force_reference_display') for r in p['references']]
    ref_payload=json.dumps(references,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    payload=json.dumps(meshes,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    template=(absolute_path(__file__).parent/'preview_template.html').read_text(encoding='utf-8')
    out=base/'VORSCHAU_HAUS.html'
    out.write_text(template.replace('__MESH_DATA__',payload).replace('__BODY_COUNT__',str(len(meshes))).replace('__REFERENCE_DATA__',ref_payload),encoding='utf-8')
    return out
