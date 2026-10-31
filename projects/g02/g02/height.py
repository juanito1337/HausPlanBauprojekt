# -*- coding: utf-8 -*-
"""One height definition for the project assembly. Source geometry stays unchanged."""
from pathlib import Path
import math
from .height_model import Grid, placement, read_json
from gesamt.core import sha256

SETTINGS = 'data/HOEHENANSCHLUSS_G02.json'
GRID = 'data/DGM_STUETZPUNKTE_G02.json'

def height_plan(base, engine_config):
    # There must not be a second simultaneously active vertical definition.
    old = engine_config['height_connection']
    if (old['H_EG_zero_in_source_datum_m'] is not None or old['source'].strip()
            or old['common_vertical_datum_confirmed']):
        raise ValueError('G02: Hoehen nur in data/HOEHENANSCHLUSS_G02.json einstellen; '
                         'zweiter Hoehenansatz in EINSTELLUNGEN_GESAMT.json ist nicht erlaubt.')
    base=Path(base)
    data=read_json(base/GRID)
    grid=Grid(data)
    spec=next(p for p in read_json(base/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if p['id']=='DGM')
    source=base/'umgebung'/spec['step_file']
    if spec['sha256'] != data['step_sha256'] or sha256(source) != data['step_sha256']:
        raise ValueError('Hoehenraster passt nicht zur aktiven Gelaendequelle.')
    # Independently link all height nodes to the import's exact reference grid.
    # Use the full import surface reference, not the small diagnostic point list.
    sheets=spec['geometry_reference']['sheets']
    nodes=sheets[0]['samples_mm'][:len(grid.nodes)]
    if len(sheets)!=1 or len(nodes)!=len(grid.nodes) or any(math.dist(a,b)>1e-6 for a,b in zip(nodes,grid.nodes)):
        raise ValueError('DGM-Hoehenknoten und Importreferenz unterscheiden sich.')
    result=placement(read_json(base/SETTINGS),grid)
    result.update(schema='G02_HEIGHT_PLAN_V1',settings_file=SETTINGS,
                  settings_sha256=sha256(base/SETTINGS),
                  DGM_grid_file=GRID,DGM_grid_file_sha256=sha256(base/GRID),
                  applies_to=['GELAENDE','V01','V02','V03','V05','KARTENREFERENZEN'],
                  excludes=['HAUS','LEITUNGSPLAN_Z0'],
                  applied_exactly_once_at_environment_parent=True,
                  local_source_parts_remain_at_original_source_heights=True)
    return result

def component_placements(house_master, environment_master, utility_master, plan):
    t=list(plan['translation_mm'])
    if len(t)!=3 or any(not math.isfinite(float(x)) for x in t) or t[0]!=0 or t[1]!=0:
        raise ValueError('G02 erlaubt hier nur eine reine Z-Verschiebung.')
    return [('HAUS_MAIN01_A01',str(house_master),[0.,0.,0.]),
            ('UMGEBUNG_'+plan['mode'],str(environment_master),t),
            ('LEITUNGSPLAN_KEINE_TIEFEN',str(utility_master),[0.,0.,0.])]

def verify_placement_rows(rows, plan):
    """rows are actual returned component positions, not their requested inputs."""
    if len(rows)!=3:
        raise ValueError('Drei direkte Projektkomponenten erwartet.')
    wanted=[[0.,0.,0.],list(plan['translation_mm']),[0.,0.,0.]]
    for row,expected in zip(rows,wanted):
        p=row['translation_mm']
        if len(p)!=3 or any(not math.isfinite(float(x)) for x in p):
            raise ValueError('Ungueltige rueckgelesene Komponentenposition.')
        if math.dist(p,expected)>1e-5 or row.get('identity_rotation') is not True:
            raise ValueError('Rueckgelesene Montageposition/Rotation weicht ab.')
    actual=plan['anchor']['source_z_mm']+rows[1]['translation_mm'][2]
    error=abs(actual-plan['target_ground_z_mm'])
    if error>1e-5:
        raise ValueError('Montierter Anker hat nicht die vorgegebene Zielhoehe.')
    return {'status':'MONTAGEPOSITIONEN_UND_ANKER_RECHNERISCH_GEPRUEFT',
            'anchor_height_after_mm':actual,'target_height_mm':plan['target_ground_z_mm'],
            'anchor_error_mm':error,'environment_translation_mm':rows[1]['translation_mm'],
            'site_alignment_surveyed':False,
            'note':'Komponentenpositionen aus NX; Ankerhoehe aus Quellraster + gelesener Position. Kein erneutes Bestandsaufmass.'}
