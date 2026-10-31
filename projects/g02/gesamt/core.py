# -*- coding: utf-8 -*-
"""File and orchestration logic. Standard library only; no NX calls in this file."""
import copy
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import traceback
import uuid
from . import PATCH

MODES = ('ALL', 'HOUSE', 'ENVIRONMENT', 'ASSEMBLE')
POINTERS = {'house': 'LETZTES_HAUS_G01.json', 'environment': 'LETZTE_UMGEBUNG_G01.json'}
CONFIG_FILE = 'data/EINSTELLUNGEN_GESAMT.json'


def absolute(path):
    return Path(os.path.abspath(os.fspath(path)))  # not realpath: retain R03a path fix


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Doppelter JSON-Schluessel: '+key)
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nicht endlicher JSON-Wert: '+value)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=pairs, parse_constant=invalid)


def write_json(path, value):
    path = Path(path)
    temp = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def relative_file(base, name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name or '\x00' in name
            or name.startswith('/') or any(x in ('', '.', '..') for x in name.split('/'))):
        raise ValueError('Ungueltiger relativer Dateipfad: '+repr(name))
    return absolute(Path(base)/name)


def config_checked(config):
    keys = {'schema', 'output_root', 'surface_validation', 'step_settings_file', 'height_connection', 'note'}
    if not isinstance(config, dict) or set(config) != keys or config['schema'] != 'GESAMT_G01_SETTINGS_V1':
        raise ValueError('EINSTELLUNGEN_GESAMT.json: falsches/unvollstaendiges Schema.')
    if config['surface_validation'] not in ('BASIS', 'INTENSIV'):
        raise ValueError('surface_validation muss BASIS oder INTENSIV sein.')
    for key in ('output_root', 'step_settings_file', 'note'):
        if not isinstance(config[key], str):
            raise ValueError(key+': Text erforderlich.')
    h = config['height_connection']
    if not isinstance(h, dict) or set(h) != {'H_EG_zero_in_source_datum_m','source','common_vertical_datum_confirmed'}:
        raise ValueError('height_connection unvollstaendig.')
    if type(h['common_vertical_datum_confirmed']) is not bool or not isinstance(h['source'], str):
        raise ValueError('Hoehenquelle/Bezugsbestaetigung ungueltig.')
    z = h['H_EG_zero_in_source_datum_m']
    if z is None:
        if h['common_vertical_datum_confirmed']:
            raise ValueError('Bestaetigung ohne EG-Quellhoehe.')
    else:
        if type(z) not in (int,float) or not math.isfinite(z):
            raise ValueError('EG-Quellhoehe muss eine endliche Zahl in Metern sein.')
        if not h['source'].strip() or not h['common_vertical_datum_confirmed']:
            raise ValueError('Hoehenanschluss erfordert Quelle und ausdrueckliche Bezugsbestaetigung.')
    return copy.deepcopy(config)


def environment_offset(config):
    z = config_checked(config)['height_connection']['H_EG_zero_in_source_datum_m']
    return None if z is None else (0., 0., -1000.*float(z))


def verify_package(base, mode='ALL'):
    if mode not in MODES:
        raise ValueError('Unbekannter Startmodus: '+str(mode))
    base = absolute(base)
    lock = read_json(base/'PAKETDATEIEN_SHA256.json')
    if lock.get('schema') != 'GESAMT_G01_FILES_V1':
        raise ValueError('Gesamtpaket-Pruefsummen fehlen/ungueltig.')
    editable = {CONFIG_FILE, 'haus/data/haus.json', 'haus/data/einstellungen.json'}
    changes = []; count = 0
    for name, expected in lock['files'].items():
        # HOUSE has no STEP/terrain dependency; ASSEMBLE uses already saved files.
        if mode == 'HOUSE' and (name.startswith(('umgebung/', 'diagnose/'))):
            continue
        if mode == 'ENVIRONMENT' and name.startswith('haus/'):
            continue
        path = relative_file(base, name)
        if not path.is_file():
            raise FileNotFoundError('Paketdatei fehlt: '+name)
        actual = sha256(path)
        if actual != expected:
            if name not in editable:
                raise ValueError('Programm-/Quelldatei geaendert: '+name+'. Pakete nicht mischen.')
            changes.append({'file':name, 'sha256':actual, 'delivery_sha256':expected})
        count += 1
    return {'checked_files':count, 'editable_changes':changes,
            'NX_geometry_test':False, 'scope':mode}


def saved_record(path):
    path = absolute(path)
    if not path.is_file() or path.stat().st_size <= 0:
        raise FileNotFoundError('Gespeicherte Datei fehlt/leer: '+str(path))
    return {'path':str(path), 'bytes':path.stat().st_size, 'sha256':sha256(path)}


def check_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError('Keine gespeicherten Dateien nachgewiesen.')
    seen = set()
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get('path'),str):
            raise ValueError('Ungueltiger Dateinachweis.')
        path = Path(row['path'])
        if not path.is_absolute():
            raise ValueError('Dateinachweis erfordert absoluten Pfad.')
        key = os.path.normcase(os.path.normpath(str(path))).casefold()
        if key in seen:
            raise ValueError('Doppelter Dateinachweis: '+str(path))
        seen.add(key)
        if (type(row.get('bytes')) is not int or row['bytes'] <= 0 or not path.is_file()
                or path.stat().st_size != row['bytes'] or sha256(path) != row.get('sha256')):
            raise ValueError('Gespeicherte Datei fehlt oder wurde geaendert: '+str(path))
    return len(seen)


def validate_component_result(result, kind):
    if kind not in POINTERS or not isinstance(result,dict) or result.get('kind') != kind:
        raise ValueError('Falsche Ergebnisart.')
    if result.get('status') != 'GESPEICHERT_UND_DATEIGEPRUEFT':
        raise ValueError('Kein vollstaendig gespeichertes Teilergebnis: '+kind)
    if not isinstance(result.get('master'),str) or not Path(result['master']).is_absolute():
        raise ValueError('Masterpfad fehlt oder ist relativ.')
    if Path(result['master']).suffix.lower() != '.prt':
        raise ValueError('Master ist keine .prt-Datei.')
    check_records(result.get('files'))
    if not any(absolute(r['path']) == absolute(result['master']) for r in result['files']):
        raise ValueError('Master nicht im Dateinachweis.')
    if result.get('as_built_verified') is not False:
        raise ValueError('Kein Bestandnachweis aus diesem Workflow ableitbar.')
    if kind == 'house':
        if result.get('revision') != 'MAIN01-A01':
            raise ValueError('Falscher Hausstand; MAIN01-A01 erforderlich, kein altes R11-Haus.')
        if result.get('mode') not in ('PRUEFMODELL_MIT_NAEHERUNGEN','REFERENZGERUEST'):
            raise ValueError('Unbekannter Hausmodus.')
        if result['mode'] == 'REFERENZGERUEST' and result.get('built_solids') != 0:
            raise ValueError('Referenzmodus widerspricht Koerperzahl.')
    else:
        if result.get('surface_validation') not in ('BASIS','INTENSIV'):
            raise ValueError('Umgebungs-Pruefumfang fehlt.')
        if result.get('new_house_built_by_environment') is not False:
            raise ValueError('Umgebung darf keinen alten Hausstand erzeugen.')
    return result


def store_pointer(base, result):
    validate_component_result(result, result['kind'])
    write_json(Path(base)/POINTERS[result['kind']], {
        'schema':'GESAMT_G01_POINTER_V1', 'patch':PATCH, 'result':result,
        'note':'Nur abgeschlossener Dateistand. Kein Bestands-/Tragwerksnachweis.'})


def read_pointer(base, kind):
    path = Path(base)/POINTERS[kind]
    if not path.is_file():
        raise FileNotFoundError('Kein gespeicherter '+kind+'-Lauf dieses Gesamtpakets. Zuerst passenden Erzeuger starten; keine JSON erfinden/kopieren.')
    pointer = read_json(path)
    if pointer.get('schema') != 'GESAMT_G01_POINTER_V1' or pointer.get('patch') != PATCH:
        raise ValueError('Zeiger gehoert nicht zum aktuellen Gesamtpaket.')
    return validate_component_result(pointer.get('result'),kind)


def child_exception_context(error):
    result = {}; seen = set(); current = error
    names = ('main01_context','r11a_context','r11_context','r09_context','nx_unit_check',
             'nx_attribute_check','nx_surface_check','nx_area_measurement','nx_runtime',
             'nx_terrain_audit_g01a','nx_terrain_uv_g01b','nx_terrain_boundary_g01c')
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        for name in names:
            value = getattr(current,name,None)
            if value is not None and name not in result:
                result[name] = value
        current = current.__cause__ or current.__context__
    return result


def run_project(base, mode='ALL', config=None, backend=None, verify=True):
    """Latest house first; environment failure never reverts a completed house.
    ASSEMBLE only references checked prior G01 files, without regeneration/import.
    """
    if mode not in MODES:
        raise ValueError('Unbekannter Startmodus: '+str(mode))
    base = absolute(base)
    cfg = config_checked(read_json(base/CONFIG_FILE) if config is None else config)
    package_check = verify_package(base,mode) if verify else {'test_only_hash_bypass':True}
    if backend is None:
        from .nx_backend import NXBackend
        backend = NXBackend(base)
    root = Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    root = absolute(root if root.is_absolute() else base/root)
    root.mkdir(parents=True,exist_ok=True)
    out = root/('G01_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    out.mkdir(exist_ok=False)
    state = {'schema':'GESAMT_G01_RUN_V1', 'patch':PATCH, 'mode':mode,
             'output_directory':str(out), 'status':'GESTARTET', 'phase':'VORPRUEFUNG',
             'started':datetime.datetime.now().isoformat(), 'house':None, 'environment':None,
             'project':None, 'configuration':cfg, 'package_check':package_check,
             'physical_site_alignment_verified':False, 'as_built_verified':False,
             'structural_approval':False, 'DGM_POINT85_ROOT_CAUSE_FIXED':False,
             'house_geometry_revision':'MAIN01-A01', 'source_geometry_changed_by_consolidation':False}
    def checkpoint(phase):
        state['phase'] = phase
        write_json(out/'manifest_G01.json',state)
        write_json(out/'LAUFSTATUS_G01.json',{
            'patch':PATCH,'phase':phase,'status':state['status'],
            'updated_at':datetime.datetime.now().isoformat(),
            'saved_house':(state['house'] or {}).get('master'),
            'saved_environment':(state['environment'] or {}).get('master'),
            'house_detail':(state['house'] or {}).get('progress'),
            'environment_detail':(state['environment'] or {}).get('progress'),
            'note':'Grobphase. Feinfortschritt: HAUS-Unterordner/LAUFSTATUS_MAIN01.json bzw. Umgebung/LAUFSTATUS_R11a.json. Kein NX-Timeout.'})
    checkpoint('VORPRUEFUNG')
    try:
        reuse = None
        if mode == 'ASSEMBLE':
            reuse = {k:read_pointer(base,k) for k in POINTERS}
        backend.preflight(mode, cfg, reuse)
        if mode in ('ALL','HOUSE'):
            checkpoint('HAUS_MAIN01_A01_ERZEUGEN')
            state['house'] = validate_component_result(backend.build_house(out,cfg),'house')
            checkpoint('HAUS_GESPEICHERT')
            store_pointer(base,state['house'])
        if mode in ('ALL','ENVIRONMENT'):
            checkpoint('UMGEBUNG_IMPORTIEREN_UND_PRUEFEN')
            state['environment'] = validate_component_result(backend.build_environment(out,cfg),'environment')
            checkpoint('UMGEBUNG_GESPEICHERT')
            store_pointer(base,state['environment'])
        if mode == 'ASSEMBLE':
            state.update(house=reuse['house'],environment=reuse['environment'])
        if state['house'] and state['environment']:
            checkpoint('PROJEKT_ZUSAMMENSTELLEN')
            state['project'] = backend.assemble(out,state['house'],state['environment'],cfg)
            check_records(state['project']['files'])
            state['height_connection_mode'] = ('NUTZERBELEGTER_Z_VERSATZ_KEIN_EIGENER_VERIFICATION'
                         if environment_offset(cfg) is not None else 'BEIDE_QUELLHOEHEN_UNVERAENDERT_NICHT_PHYSISCH_MONTIERT')
        checkpoint('ABSCHLUSSPRUEFUNG')
        for key in POINTERS:
            if state[key]:
                validate_component_result(state[key],key)
        if verify:
            state['package_check_at_end'] = verify_package(base,mode)
        state['displayed_master'] = (state['project'] or state['house'] or state['environment'])['master']
        state['status'] = 'ANGEFORDERTER_ABLAUF_ABGESCHLOSSEN_FACHLICH_OFFEN'
        state['finished'] = datetime.datetime.now().isoformat()
        checkpoint('ABGESCHLOSSEN')
        write_json(base/'LETZTER_GESAMTLAUF_G01.json',{
            'schema':'GESAMT_G01_RESULT_V1', 'patch':PATCH,'directory':str(out),
            'manifest':str(out/'manifest_G01.json'),'master':state['displayed_master'],
            'mode':mode,'status':state['status']})
        return state
    except Exception as error:
        state.update(status='ABGEBROCHEN_KEIN_GESAMTERFOLG',error=str(error),
                     traceback=traceback.format_exc(),nested_diagnostics=child_exception_context(error))
        context = {'output_directory':str(out),'phase':state['phase'],
                   'manifest':str(out/'manifest_G01.json'),
                   'saved_house':(state['house'] or {}).get('master'),
                   'saved_environment':(state['environment'] or {}).get('master')}
        error.gesamt_g01_context = context
        try:
            checkpoint(state['phase'])
        except Exception as logging_error:
            error.gesamt_g01_logging_error = str(logging_error)
        raise
