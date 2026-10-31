# -*- coding: utf-8 -*-
"""H01: height registration only. No NX and no inferred surveying approval."""
import hashlib
import json
import math
import os
from pathlib import Path
import uuid

REVISION = 'G02-INTEGRIERTER-HOEHENBEZUG'
IDENTITY = (1.,0.,0.,0.,1.,0.,0.,0.,1.)


def read_json(path):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('Doppelter JSON-Schluessel: '+key)
            out[key] = value
        return out
    def invalid(value):
        raise ValueError('Nicht endlicher JSON-Wert: '+value)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=pairs,
                      parse_constant=invalid)


def write_json(path, data):
    path = Path(path)
    tmp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with tmp.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(str(tmp),str(path))
    finally:
        if tmp.exists(): tmp.unlink()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def number(value, name):
    if type(value) not in (float,int) or not math.isfinite(value):
        raise ValueError(name+': endliche Zahl erforderlich.')
    return float(value)


def vector(value, size, name):
    if not isinstance(value,(list,tuple)) or len(value)!=size:
        raise ValueError(name+': '+str(size)+' Werte erforderlich.')
    return [number(v,name) for v in value]


def file_record(path):
    p = Path(os.path.abspath(os.fspath(path)))
    if not p.is_file() or p.stat().st_size <= 0:
        raise ValueError('Datei fehlt/leer: '+str(p))
    return {'path':str(p),'bytes':p.stat().st_size,'sha256':digest(p)}


def verify_records(records):
    for row in records:
        now=file_record(row['path'])
        if now['bytes']!=row['bytes'] or now['sha256']!=row['sha256']:
            raise RuntimeError('Quelldatei wurde waehrend der Montage geaendert: '+row['path'])


def verify_package(base):
    base=Path(base); lock=read_json(base/'PAKETDATEIEN_SHA256.json')
    if lock.get('schema')!='H01_FILES_V1': raise ValueError('Falsches H01-Paket.')
    edits=[]
    for name,sha in lock['files'].items():
        if name.startswith('/') or '\\' in name or '..' in Path(name).parts:
            raise ValueError('Ungueltiger Paketpfad.')
        p=base/name
        if not p.is_file(): raise FileNotFoundError('Paketdatei fehlt: '+name)
        actual=digest(p)
        if actual!=sha:
            if name!='data/HOEHENANSCHLUSS_H01.json':
                raise ValueError('H01-Programm-/Quelldatei geaendert: '+name)
            edits.append({'file':name,'actual':actual,'delivery':sha})
    return {'checked_files':len(lock['files']),'settings_changes':edits}


class Grid:
    """Original local X/Y in mm, original DGM source Z in mm. Bilinear cells."""
    def __init__(self,data):
        if data.get('schema')!='H01_ORIGINAL_DGM_GRID_V1':raise ValueError('Falsches DGM-Schema.')
        self.shape=data['shape']; self.nodes=data['nodes_mm']; self.source=data
        if (not isinstance(self.shape,list) or len(self.shape)!=2 or
            any(type(k)!=int or k<2 for k in self.shape)):
            raise ValueError('Ungueltige Rastergroesse.')
        self.nu,self.nv=self.shape
        if len(self.nodes)!=self.nu*self.nv:raise ValueError('Raster unvollstaendig.')
        self.nodes=[vector(p,3,'DGM-Stuetzpunkt') for p in self.nodes]
        self.origin=self.nodes[0]
        self.du=[self.nodes[self.nv][k]-self.origin[k] for k in range(2)]
        self.dv=[self.nodes[1][k]-self.origin[k] for k in range(2)]
        self.det=self.du[0]*self.dv[1]-self.du[1]*self.dv[0]
        if abs(self.det)<1e-6:raise ValueError('Degeneriertes DGM-Raster.')
        for i in range(self.nu):
            for j in range(self.nv):
                p=self.nodes[i*self.nv+j]
                predicted=[self.origin[k]+i*self.du[k]+j*self.dv[k] for k in range(2)]
                if math.dist(p[:2],predicted)>0.001:
                    raise ValueError('DGM-Raster nicht affin/ursprungsgleich.')

    def sample(self,xy):
        x,y=vector(xy,2,'Anker XY'); a=x-self.origin[0]; b=y-self.origin[1]
        u=(a*self.dv[1]-b*self.dv[0])/self.det
        v=(self.du[0]*b-self.du[1]*a)/self.det
        if u < -1e-6 or v < -1e-6 or u > self.nu-1+1e-6 or v > self.nv-1+1e-6:
            raise ValueError('Anker liegt ausserhalb des DGM. Keine Extrapolation.')
        u=min(max(u,0.),self.nu-1.);v=min(max(v,0.),self.nv-1.)
        i=min(int(math.floor(u)),self.nu-2);j=min(int(math.floor(v)),self.nv-2)
        a=u-i;b=v-j
        indices=[i*self.nv+j,(i+1)*self.nv+j,(i+1)*self.nv+j+1,i*self.nv+j+1]
        weights=[(1-a)*(1-b),a*(1-b),a*b,(1-a)*b]
        z=sum(self.nodes[idx][2]*w for idx,w in zip(indices,weights))
        return {'xy_mm':[x,y],'source_z_mm':z,'grid_uv':[u,v],
                'indices':indices,'weights':weights,
                'support_points_mm':[self.nodes[k] for k in indices]}


def placement(settings,grid):
    required={'schema','mode','anchor_xy_mm','ground_z_relative_eg_mm','source',
              'absolute_eg_source_m','common_vertical_datum_confirmed','note'}
    if not isinstance(settings,dict) or set(settings)!=required or settings['schema']!='H01_HEIGHT_SETTINGS_V1':
        raise ValueError('Hoeheneinstellungen unvollstaendig oder unbekannte Felder.')
    mode=settings['mode']
    if mode not in ('PLAN_ANNAHME','AUFMASSPUNKT','ABSOLUTE_EG_HOEHE'):
        raise ValueError('Unbekannter Hoehenmodus.')
    if not isinstance(settings['source'],str) or not settings['source'].strip():
        raise ValueError('Hoehenquelle/Beschreibung fehlt.')
    if type(settings['common_vertical_datum_confirmed']) is not bool:
        raise ValueError('Bezugsbestaetigung muss true/false sein.')
    anchor=grid.sample(settings['anchor_xy_mm'])
    if mode=='ABSOLUTE_EG_HOEHE':
        h=number(settings['absolute_eg_source_m'],'Absolute EG-Hoehe')
        if not settings['common_vertical_datum_confirmed']:
            raise ValueError('Absoluter Anschluss erfordert ausdrueckliche Bezugsbestaetigung.')
        if settings['ground_z_relative_eg_mm'] is not None:
            raise ValueError('Absoluter Modus: keine zusaetzliche Anker-Zielhoehe einsetzen.')
        delta=-1000*h
        label='ABSOLUTE_HOEHE_NACH_NUTZERANGABE_NICHT_UNABHAENGIG_VERIFIZIERT'
        target=anchor['source_z_mm']+delta
    else:
        if settings['absolute_eg_source_m'] is not None or settings['common_vertical_datum_confirmed']:
            raise ValueError('Plan-/Aufmassanker darf keine bestaetigte absolute EG-Hoehe vortaeuschen.')
        target=number(settings['ground_z_relative_eg_mm'],'Ankerhoehe relativ EG')
        if abs(target)>5000:raise ValueError('Anker-Zielhoehe groesser als 5 m: Einheiten/Bezug klaeren.')
        delta=target-anchor['source_z_mm']
        label=('PLANANNAHME_KEIN_VERMESSENER_BESTAND' if mode=='PLAN_ANNAHME'
               else 'LOKALER_AUFMASSPUNKT_PLUS_DGM_KEIN_AMTLICHER_HOEHENANSCHLUSS')
    if abs(delta)>100000:raise ValueError('Versatz groesser als 100 m: falsches Gebiet/Einheit?')
    return {'schema':'H01_PLACEMENT_V1','mode':mode,'status':label,'source':settings['source'],
            'anchor':anchor,'target_ground_z_mm':target,'translation_mm':[0.,0.,delta],
            'effective_EG_zero_in_source_m':-delta/1000,
            'absolute_height_independently_verified':False,'site_alignment_surveyed':False,
            'geometry_deformed':False,'xy_changed':False,'rotation_changed':False,
            'source_grid_sha256':grid.source['source_grid_record_sha256'],
            'source_step_sha256':grid.source['step_sha256'],
            'datum_confirmation_is_user_claim':settings['common_vertical_datum_confirmed']}


def check_pose(position,rotation,context,allow_z=False):
    p=vector(position,3,context);r=vector(rotation,9,context)
    if max(abs(x-y) for x,y in zip(r,IDENTITY))>1e-8:
        raise ValueError(context+': gedrehte Komponente; keine automatische Neuausrichtung.')
    if max(abs(p[0]),abs(p[1]))>0.001 or (not allow_z and abs(p[2])>0.001):
        raise ValueError(context+': vorhandene lokale Verschiebung; Montage nicht eindeutig.')
    return p


def part_role(path):
    name=Path(str(path)).name.casefold()
    if name=='haus_master.prt':return 'house'
    if name=='umgebung_master_r09.prt':return 'environment'
    if name.startswith('01_gelaende_') and name.endswith('.prt'):return 'terrain'
    if name=='leitungsplan_master_g01.prt':return 'utilities'
    return None


def planned_children(children,offset):
    roles=[row['role'] for row in children]
    if roles.count('house')!=1 or roles.count('environment')+roles.count('terrain')!=1:
        raise ValueError('Gesamtbaugruppe mit genau einem Haus und einer Umgebung/Gelaendekomponente anzeigen.')
    if any(role not in ('house','environment','terrain','utilities') for role in roles):
        raise ValueError('Unbekannte direkte Komponente: wird nicht stillschweigend weggelassen.')
    if roles.count('utilities')>1:raise ValueError('Doppelte Leitungsplanbaugruppe.')
    seen=set();out=[]
    for row in children:
        key=os.path.normcase(os.path.abspath(row['path'])).casefold()
        if key in seen:raise ValueError('Doppelte Komponentenprototypen.')
        seen.add(key)
        env=row['role'] in ('environment','terrain')
        check_pose(row['position_mm'],row['rotation'],row['name'],allow_z=env)
        changed=dict(row)
        # Absolute placement relative to ORIGINAL prototype; never add the offset twice.
        changed['new_position_mm']=list(offset if env else row['position_mm'])
        changed['delta_from_current_mm']=[changed['new_position_mm'][k]-row['position_mm'][k] for k in range(3)]
        changed['hidden']=bool(row.get('hidden',False)) or row['role']=='utilities'
        out.append(changed)
    return out
