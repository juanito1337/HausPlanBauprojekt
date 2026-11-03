"""Fail-closed, source-backed layout for the independent M01 delivery."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from tools.repo_support import digest, member_path

IDENTITY = [1, 0, 0, 0, 1, 0, 0, 0, 1]
ROLES = {'cut_soil': 'M01_CUT_SOIL', 'excavation': 'M01_EXCAVATION',
         'pile_main': 'M01_PILE_MAIN', 'pile_reserve': 'M01_PILE_RESERVE'}
HISTORIC_A = {'EG_A_W', 'EG_A_K', 'EG_A_WC', 'KG_A_R', 'KG_A_F', 'KG_A_B', 'KG_A_TREPPENRAUM'}
HISTORIC_B = {'EG_B_W', 'EG_B_K', 'EG_B_B', 'EG_B_A'}
HOUSE_PARTS = {
    '00_STEUERUNG': ('HOUSE_CONTROL', 'HOUSE', 'Steuerungsreferenz'),
    '02_KELLER': ('HOUSE_KG_MAIN', 'HOUSE_KG', 'Keller_Hauptbau'),
    '02B_KELLER_ANBAU': ('HOUSE_KG_ANNEX', 'HOUSE_KG', 'Keller_Anbau'),
    '03_ERDGESCHOSS': ('HOUSE_EG_MAIN', 'HOUSE_EG', 'Erdgeschoss_Hauptbau'),
    '03B_ERDGESCHOSS_ANBAU': ('HOUSE_EG_ANNEX', 'HOUSE_EG', 'Erdgeschoss_Anbau'),
    '03C_GARAGE': ('HOUSE_GARAGE', 'HOUSE', 'Garage'),
    '04_DACHGESCHOSS': ('HOUSE_DG_MAIN', 'HOUSE_DG', 'Dachgeschoss_Bestand'),
    '05_DACH_PRUEFHUELLE': ('HOUSE_ROOF_MAIN', 'HOUSE_ROOF', 'Hauptdach_Pruefhuelle'),
    '05B_FLACHDACH_ANBAU_REFERENZ': ('HOUSE_ROOF_FLAT', 'HOUSE_ROOF', 'Flachdach_Anbau_Referenz'),
    '08_VIDEO_DACHFENSTER_R10': ('HOUSE_ROOF_WINDOWS', 'HOUSE_ROOF', 'Dachfenster'),
    '09_VIDEO_SOLARFELDER_R10': ('HOUSE_ROOF_SOLAR', 'HOUSE_ROOF', 'Solarfeldhuellen'),
    '10_BALKON_RECHTS_MAIN01': ('HOUSE_BALCONY', 'HOUSE_OUTSIDE', 'Balkon'),
    '11_BALKON_ZUGANG_MAIN01': ('HOUSE_BALCONY_ACCESS', 'HOUSE_OUTSIDE', 'Balkonzugang'),
    '12_KELLERABGANG_GELAENDER_MAIN01': ('HOUSE_STAIR_RAIL', 'HOUSE_OUTSIDE', 'Kellerabgang_Gelaender'),
    '13_FALLROHR_REFERENZEN_MAIN01': ('HOUSE_DOWNPIPES', 'HOUSE_OUTSIDE', 'Fallrohrreferenzen')}
ENV_PARTS = {
    '01_GELAENDE_R09': ('TERRAIN', 'Bestandsgelaende'),
    '02_V01_HECKENBEREICH_R09': ('ENV_V01', 'Heckenbereich_V01'),
    '03_V02_HECKENBEREICH_R09': ('ENV_V02', 'Heckenbereich_V02'),
    '04_V03_GEHOELZKRONE_R09': ('ENV_V03', 'Gehoelzkrone_V03'),
    '06_V05_GEHOELZKRONE_R09': ('ENV_V05', 'Gehoelzkrone_V05'),
    '11_KARTENREFERENZEN_R09': ('ENV_MAP', 'Kartenreferenzen')}


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _safe(path):
    if not isinstance(path, str) or not path or '\\' in path or ':' in path:
        raise ValueError('Unsafe relative path')
    p = PurePosixPath(path)
    if p.is_absolute() or any(x in ('', '.', '..') for x in path.split('/')):
        raise ValueError('Unsafe relative path: ' + path)
    return path


def _check_parts(directory, records):
    names = []
    for row in records:
        name = _safe(row['path'])
        path = member_path(directory, name)
        if path.suffix.lower() != '.prt' or not path.is_file():
            raise ValueError('Missing native source: ' + name)
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Changed native source: ' + name)
        names.append(name.casefold())
    if not names or len(names) != len(set(names)):
        raise ValueError('Missing or duplicate native sources')


def _fingerprint(root, paths):
    return hashlib.sha256(json.dumps({p: digest(member_path(root, p)) for p in sorted(paths)}, sort_keys=True).encode()).hexdigest()


def _load_evidence(root):
    """Validate current evidence without opening NX or modifying historical proofs."""
    from tools.nx_project import validate_evidence as validate_base
    from renovierung.k02.runner import validate_evidence as validate_study
    from renovierung.k02.planning import DEFAULT_SOURCES
    pairs = []
    for relative in ('cad/nx', 'cad/nx/k02'):
        base = root/relative
        current, attempt = _read(base/'CURRENT.json'), _read(base/'LAST_ATTEMPT.json')
        if attempt.get('status') != 'PASS' or attempt.get('directory') != current['directory']:
            raise ValueError('Latest source attempt not verified: ' + relative)
        directory = member_path(base, _safe(current['directory']))
        pairs.append((directory, _read(directory/'BUILD.json'), _read(directory/'VERIFY.json'), current))
    gd, gb, gv, gc = pairs[0]
    kd, kb, kv, kc = pairs[1]
    registry = _read(root/'projects/g02/PAKETDATEIEN_SHA256.json')
    paths = {'projects/g02/'+p for p in set(registry['files']) | {'PAKETDATEIEN_SHA256.json'}}
    paths.update('tools/'+p for p in ('nx_project.py', 'nx_build_journal.py', 'nx_verify_journal.py', 'repo_support.py'))
    errors = validate_base(gd, gb, gv, _fingerprint(root, paths))
    _check_parts(gd, gb['parts'])
    if gc['master'] != gc['directory']+'/'+gb['master']:
        errors.append('G02 CURRENT master mismatch')
    paths = set(DEFAULT_SOURCES.values())
    paths.update(p.relative_to(root).as_posix() for p in (root/'renovierung/k02').glob('*.py'))
    paths.update(('renovierung/k02/study_config.json', 'tools/nx_project.py', 'tools/repo_support.py', 'cad/nx/CURRENT.json'))
    paths.update((gd/p).relative_to(root).as_posix() for p in ('BUILD.json', 'VERIFY.json'))
    paths.update((gd/p['path']).relative_to(root).as_posix() for p in gb['parts'])
    errors.extend(validate_study(kd, kb, kv, _fingerprint(root, paths)))
    if kc['masters'] != {s['id']: s['master'] for s in kb['states']}:
        errors.append('K02 CURRENT masters mismatch')
    if kb['source_hashes'] != {r['path']: r['sha256'] for r in gb['parts']}:
        errors.append('K02 baseline sources differ from current G02')
    if kb['baseline_fingerprint'] != gb['source_fingerprint'] or kb.get('baseline_current_scope_valid') is not True:
        errors.append('K02 baseline scope stale')
    plan = kb['plan']
    for row in plan['provenance']['inputs'] + plan['provenance']['generators']:
        path = member_path(root, _safe(row['path']))
        if digest(path) != row['sha256'] or ('bytes' in row and path.stat().st_size != row['bytes']):
            errors.append('K02 plan provenance stale: '+row['path'])
    if plan['provenance']['config'] != _read(root/'renovierung/k02/study_config.json'):
        errors.append('K02 plan config differs')
    if errors:
        raise ValueError('; '.join(errors))
    return gd, gb, kd, kb


def create_layout(root: Path) -> dict:
    """Return a JSON layout backed by complete, current G02/K02 evidence."""
    root = Path(root).resolve()
    gd, gb, kd, kb = _load_evidence(root)
    plan = kb['plan']
    house = _read(root/'projects/g02/haus/data/haus.json')
    layout = {'schema': 'M01_LAYOUT_V1', 'master': 'HAUSPROJEKT_MASTER_M01.prt',
              'nodes': [], 'sources': [], 'fields': [], 'rooms': [], 'construction_release': False,
              'units': 'mm', 'height_registration': deepcopy(plan['height_registration']),
              'sections': deepcopy(plan['sectors']), 'limitations': deepcopy(plan['limitations']),
              'state_basis': 'INDEPENDENT_SINGLE_FIELD_VARIANTS_NO_CUMULATIVE_SEQUENCE',
              'provenance': {'g02_build': (gd/'BUILD.json').relative_to(root).as_posix(),
                             'k02_build': (kd/'BUILD.json').relative_to(root).as_posix(),
                             'plan_provenance': deepcopy(plan['provenance'])}}

    def node(nid, parent, name, kind='assembly', *, file=None, blank=False, **extra):
        value = {'id': nid, 'parent': parent, 'file': file or 'gruppen/'+nid+'.prt',
                 'name': name, 'kind': kind, 'translation_mm': [0, 0, 0],
                 'rotation': list(IDENTITY), 'blank': blank, 'reference_set': 'Entire Part'}
        value.update(extra)
        layout['nodes'].append(value)
        return value

    def source(directory, row, file):
        value = {'source': (directory/row['path']).relative_to(root).as_posix(),
                 'file': file, 'sha256': row['sha256'], 'bytes': row['bytes']}
        layout['sources'].append(value)
        return value

    node('MASTER', None, 'Hausprojekt_Master_M01', file=layout['master'])
    for nid, parent, name in (
        ('HOUSE', 'MASTER', 'Haus_Bestand'), ('HOUSE_KG', 'HOUSE', 'Keller'),
        ('HOUSE_EG', 'HOUSE', 'Erdgeschoss'), ('HOUSE_DG', 'HOUSE', 'Dachgeschoss'),
        ('HOUSE_ROOF', 'HOUSE', 'Dach'), ('HOUSE_OUTSIDE', 'HOUSE', 'Aussenbauteile'),
        ('ENVIRONMENT', 'MASTER', 'Umgebung'), ('UTILITIES', 'MASTER', 'Leitungsreferenzen_Tiefen_unbekannt'),
        ('CONSTRUCTION', 'MASTER', 'Bauzustaende_Einzelfeldstudien')):
        node(nid, parent, name)
    next(n for n in layout['nodes'] if n['id'] == 'ENVIRONMENT')['translation_mm'] = deepcopy(gb['height_translation_mm'])
    selected = []
    for row in gb['parts']:
        stem = Path(row['path']).stem
        if stem in HOUSE_PARTS:
            nid, parent, name = HOUSE_PARTS[stem]
        elif stem in ENV_PARTS:
            nid, name = ENV_PARTS[stem]; parent = 'ENVIRONMENT'
        elif re.fullmatch(r'07[A-D]_(GAS|STROM|TELEFON|BREITBAND)_PLANPROJEKTION_G02_[A-Za-z0-9]+', stem):
            nid = 'UTILITY_'+stem.split('_')[1]; parent = 'UTILITIES'; name = nid+'_Tiefe_unbekannt'
        else:
            continue
        file = 'bestand/'+nid+'.prt'
        source(gd, row, file)
        node(nid, parent, name, 'source', file=file)
        selected.append(nid)
    if len(selected) != 25 or len(set(selected)) != 25:
        raise ValueError('Missing/duplicate confirmed G02 leaf parts')
    states = {s['id']: s for s in kb['states']}
    if len(states) != len(kb['states']): raise ValueError('Duplicate K02 states')
    for sector in plan['sectors']:
        node('SECTION_'+sector['id'], 'CONSTRUCTION', 'Sektion_'+sector['id'], metadata=deepcopy(sector))
    for original in plan['fields']:
        field = deepcopy(original); fid = field['id']; nid = 'FIELD_'+fid
        field.update(node_id=nid, native=bool(field['native_candidate']), measurements={})
        node(nid, 'SECTION_'+field['sector_id'], 'Feld_'+fid, 'field', file='bauzustaende/'+nid+'.prt', blank=True)
        if field['native']:
            state = states[fid]
            studies = [p for p in state['parts'] if Path(p['path']).name == fid+'_STUDY.prt']
            if len(studies) != 1: raise ValueError('Missing/duplicate STUDY source: '+fid)
            study = source(kd, studies[0], 'studien/'+fid+'_STUDY.prt')
            field.update(measurements=deepcopy(state['measurements']), source=study['source'], study_file=study['file'])
            if set(field['measurements']) != set(ROLES): raise ValueError('Incomplete native roles: '+fid)
            for role, refset in ROLES.items():
                node('ROLE_'+fid+'_'+role.upper(), nid, fid+'_'+role, 'role', file=study['file'],
                     blank=role in ('excavation', 'pile_reserve'), reference_set=refset, role=role)
        layout['fields'].append(field)
    for original in house['rooms']:
        room = deepcopy(original); rid = room['id']
        assignment = 'HISTORISCH_WOHNUNG_A' if rid in HISTORIC_A else 'HISTORISCH_WOHNUNG_B' if rid in HISTORIC_B else 'ZUORDNUNG_OFFEN'
        room.update(node_id='ROOM_'+rid, apartment_reference=assignment, current_apartment_assignment_confirmed=False,
                    representation='REGISTER_REFERENCE_ONLY_NO_ROOM_BODY_NO_WALL_ASSIGNMENT')
        floor = {'KG': 'HOUSE_KG', 'EG': 'HOUSE_EG', 'DG': 'HOUSE_DG', 'ANBAU_EG': 'HOUSE_EG'}.get(room['level'])
        if floor is None: raise ValueError('Unknown room level')
        group = 'ROOMS_'+room['level']+'_'+assignment
        if not any(n['id'] == group for n in layout['nodes']):
            node(group, floor, 'Raumregister_'+room['level']+'_'+assignment, blank=True)
        node(room['node_id'], group, 'Raum_'+rid, 'room', file='raeume/'+room['node_id']+'.prt', metadata=deepcopy(room))
        layout['rooms'].append(room)
    validate_layout(layout)
    return layout


def validate_layout(layout) -> None:
    """Reject incomplete, ambiguous or unsafe delivery layouts before any NX work."""
    try:
        _validate_layout(layout)
    except (KeyError, TypeError, AttributeError, IndexError, OverflowError) as error:
        raise ValueError('Malformed M01 layout: '+str(error)) from error


def _validate_layout(d):
    from renovierung.k02.runner import validate_measurement
    if d['schema'] != 'M01_LAYOUT_V1' or d['units'] != 'mm' or d['construction_release'] is not False:
        raise ValueError('Invalid M01 scope')
    nodes = d['nodes']; ids = [n['id'] for n in nodes]; byid = {n['id']: n for n in nodes}
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]+', x) for x in ids):
        raise ValueError('Unsafe or duplicate node IDs')
    if [n['id'] for n in nodes if n['parent'] is None] != ['MASTER']:
        raise ValueError('One master root required')
    if byid['MASTER']['file'] != d['master'] or byid['MASTER']['kind'] != 'assembly':
        raise ValueError('Master differs')
    required_parents = {'HOUSE': 'MASTER', 'HOUSE_KG': 'HOUSE', 'HOUSE_EG': 'HOUSE',
                        'HOUSE_DG': 'HOUSE', 'HOUSE_ROOF': 'HOUSE', 'HOUSE_OUTSIDE': 'HOUSE',
                        'ENVIRONMENT': 'MASTER', 'UTILITIES': 'MASTER', 'CONSTRUCTION': 'MASTER'}
    required_parents.update({v[0]: v[1] for v in HOUSE_PARTS.values()})
    required_parents.update({v[0]: 'ENVIRONMENT' for v in ENV_PARTS.values()})
    required_parents.update({'UTILITY_'+x: 'UTILITIES' for x in ('GAS', 'STROM', 'TELEFON', 'BREITBAND')})
    for nid, parent in required_parents.items():
        if byid[nid]['parent'] != parent: raise ValueError('Confirmed hierarchy differs: '+nid)
    files = {}
    for n in nodes:
        name = _safe(n['file'])
        if not re.fullmatch(r'[A-Za-z0-9_/-]+\.prt', name) or not n['name'].isascii() or not n['name']:
            raise ValueError('Unsafe part/component name')
        if n['kind'] not in ('assembly', 'source', 'role', 'room', 'field') or type(n['blank']) is not bool:
            raise ValueError('Invalid node kind/display')
        if n['rotation'] != IDENTITY or any(type(x) not in (int, float) or not math.isfinite(x) for x in n['rotation']):
            raise ValueError('Invalid rotation')
        transform = n['translation_mm']
        if len(transform) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in transform):
            raise ValueError('Invalid translation')
        expected = d['height_registration']['translation_mm'] if n['id'] == 'ENVIRONMENT' else [0, 0, 0]
        if transform != expected: raise ValueError('Height translation must occur once')
        if n['kind'] != 'role' and n['reference_set'] != 'Entire Part': raise ValueError('Unexpected reference set')
        chain = {n['id']}; parent = n['parent']
        while parent is not None:
            if parent not in byid or parent in chain: raise ValueError('Missing/cyclic parent')
            chain.add(parent); parent = byid[parent]['parent']
        files.setdefault(name.casefold(), []).append(n)
    for occurrences in files.values():
        if len(occurrences) > 1 and (len(occurrences) != 4 or {n['kind'] for n in occurrences} != {'role'} or len({n['parent'] for n in occurrences}) != 1):
            raise ValueError('Repeated physical geometry/assembly')
    sources = d['sources']
    for key in ('source', 'file'):
        values = [_safe(s[key]).casefold() for s in sources]
        if len(values) != len(set(values)): raise ValueError('Duplicate copied source')
    for s in sources:
        if not re.fullmatch(r'[a-f0-9]{64}', s['sha256']) or type(s['bytes']) is not int or s['bytes'] <= 0:
            raise ValueError('Invalid source integrity metadata')
    source_files = {s['file'] for s in sources}
    if source_files != {n['file'] for n in nodes if n['kind'] in ('source', 'role')}:
        raise ValueError('Missing/unreferenced copied source')
    if len(sources) != 47 or sum(n['kind'] == 'source' for n in nodes) != 25:
        raise ValueError('Incomplete confirmed source register')
    if byid['TERRAIN']['parent'] != 'ENVIRONMENT': raise ValueError('Terrain hierarchy differs')
    fields = d['fields']; rooms = d['rooms']
    if len(fields) != 72 or len({f['id'] for f in fields}) != 72 or sum(f['native'] is True for f in fields) != 22:
        raise ValueError('Incomplete field register')
    if len(rooms) != 50 or len({r['id'] for r in rooms}) != 50: raise ValueError('Incomplete room register')
    if len(d['sections']) != 13 or {s['id'] for s in d['sections']} != {f['sector_id'] for f in fields}:
        raise ValueError('Incomplete section register')
    if {n['id'] for n in nodes if n['kind'] == 'field'} != {f['node_id'] for f in fields}:
        raise ValueError('Field nodes differ')
    for f in fields:
        n = byid[f['node_id']]
        if n['id'] != 'FIELD_'+f['id'] or n['parent'] != 'SECTION_'+f['sector_id'] or not n['blank'] or f['construction_release'] is not False:
            raise ValueError('Field display/hierarchy differs')
        roles = [n for n in nodes if n['parent'] == f['node_id']]
        if type(f['native']) is not bool or f['native'] != f['native_candidate']: raise ValueError('Native classification differs')
        if f['native']:
            if len(roles) != 4 or {r['role'] for r in roles} != set(ROLES) or set(f['measurements']) != set(ROLES):
                raise ValueError('Incomplete field roles')
            for r in roles:
                if r['kind'] != 'role' or r['file'] != f['study_file'] or r['reference_set'] != ROLES[r['role']] or r['blank'] != (r['role'] in ('excavation', 'pile_reserve')):
                    raise ValueError('Field role display differs')
                measurement = f['measurements'][r['role']]
                validate_measurement(measurement, measurement['component_volumes_m3'])
        elif roles or f['measurements']: raise ValueError('Invented blocked field geometry')
    if {n['id'] for n in nodes if n['kind'] == 'room'} != {r['node_id'] for r in rooms}: raise ValueError('Room nodes differ')
    for room in rooms:
        n = byid[room['node_id']]
        expected = 'HISTORISCH_WOHNUNG_A' if room['id'] in HISTORIC_A else 'HISTORISCH_WOHNUNG_B' if room['id'] in HISTORIC_B else 'ZUORDNUNG_OFFEN'
        if room['apartment_reference'] != expected or room['current_apartment_assignment_confirmed'] is not False or n['metadata'] != room:
            raise ValueError('Room source metadata differs')
        if not byid[n['parent']]['blank'] or n['blank']: raise ValueError('Room register display differs')
