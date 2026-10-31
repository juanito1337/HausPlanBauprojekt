# -*- coding: utf-8 -*-
"""Datei-, Daten- und Lagepruefungen, ohne NX oder Fremdpakete."""
import hashlib
import json
import math
import os
import re
import uuid
from pathlib import Path

PATCH = 'R11-FENSTER-UND-QUELLENBEZUG'


def absolute(path):
    return Path(os.path.abspath(os.fspath(path)))  # kein realpath/resolve (R03a)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError('Doppelter JSON-Schluessel: ' + k)
            out[k] = v
        return out
    def invalid(value):
        raise ValueError('Nicht endlicher JSON-Wert: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=pairs, parse_constant=invalid)


def write_json(path, value):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8', newline='\n') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(str(temp), str(path))
    finally:
        if temp.exists():
            temp.unlink()


def finite_number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ': endliche Zahl erforderlich, keine Zeichenkette/bool.')
    return float(value)


def within(base, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative:
        raise ValueError('Ungueltiger relativer Paketpfad: ' + str(relative))
    p = Path(relative)
    if p.is_absolute() or any(x in ('..', '.') for x in relative.split('/')) or ':' in relative:
        raise ValueError('Pfad verlaesst Paket: ' + relative)
    return absolute(base / p)


def settings_checked(settings):
    if not isinstance(settings, dict) or settings.get('schema') != 'R09_SETTINGS_V1':
        raise ValueError('EINSTELLUNGEN_R09.json hat ein unbekanntes Schema.')
    allowed = {'schema', 'build_house', 'output_root', 'step_settings_file', 'height_connection', 'note'}
    if set(settings) - allowed:
        raise ValueError('Unbekannte Einstellung: ' + ', '.join(sorted(set(settings) - allowed)))
    if type(settings.get('build_house')) is not bool:
        raise ValueError('build_house muss true oder false sein.')
    for name in ('output_root', 'step_settings_file'):
        if not isinstance(settings.get(name), str):
            raise ValueError(name + ' muss ein Pfad als Text sein.')
    h = settings.get('height_connection')
    if not isinstance(h, dict) or set(h) != {'H_EG_zero_in_source_datum_m', 'source', 'common_vertical_datum_confirmed'}:
        raise ValueError('height_connection unvollstaendig/unbekannte Schluessel.')
    if not isinstance(h['source'], str) or type(h['common_vertical_datum_confirmed']) is not bool:
        raise ValueError('Hoehenquelle/Bezugsbestaetigung ungueltig.')
    z = h['H_EG_zero_in_source_datum_m']
    if z is None:
        if h['common_vertical_datum_confirmed']:
            raise ValueError('Hoehenanschluss bestaetigt, aber EG-Hoehe fehlt.')
    else:
        finite_number(z, 'H_EG_zero_in_source_datum_m')
        if not h['source'].strip() or not h['common_vertical_datum_confirmed']:
            raise ValueError('Fuer die Montage: Hoehenquelle und gemeinsamer Bezug fuer Haus, DGM und bDOM erforderlich.')
    return settings


def placement(settings):
    h = settings_checked(settings)['height_connection']
    z = h['H_EG_zero_in_source_datum_m']
    return None if z is None else (0.0, 0.0, -1000.0 * float(z))


def check_box(box):
    if len(box) != 6:
        raise ValueError('Begrenzungsbox braucht sechs Koordinaten.')
    b = [finite_number(x, 'Box') for x in box]
    if any(b[i+3] < b[i] for i in range(3)):
        raise ValueError('Umgekehrte Boxgrenzen.')
    # Offene ebene Flaechen duerfen Dicke 0 haben, aber muessen Flaechenausdehnung besitzen.
    if sum(b[i+3] - b[i] > 1e-7 for i in range(3)) < 2:
        raise ValueError('Keine zweidimensionale Flaechenausdehnung.')
    return b


def compare_boxes(expected, actual, tolerance=0.25):
    """Bijektive Zuordnung der Teilflaechen-Boxen, keine Form-/Bestandsfreigabe."""
    if len(expected) != len(actual):
        raise ValueError('Importierte Teilkoerperanzahl weicht ab: Soll %d / Ist %d. '
                         'Keine stillschweigende Flaechenverschmelzung zulaessig.' % (len(expected), len(actual)))
    exp = [check_box(x) for x in expected]
    act = [check_box(x) for x in actual]
    candidates = []
    for e in exp:
        cs = [(j, max(abs(a-b) for a, b in zip(e, box))) for j, box in enumerate(act)]
        candidates.append(sorted((j, d) for j, d in cs if d <= tolerance))
    # Bipartites Matching statt stiller Indexzuordnung nach Importreihenfolge.
    owner = {}
    def assign(i, seen):
        for j, d in sorted(candidates[i], key=lambda v: v[1]):
            if j in seen:
                continue
            seen.add(j)
            if j not in owner or assign(owner[j], seen):
                owner[j] = i
                return True
        return False
    for i in sorted(range(len(exp)), key=lambda n: len(candidates[n])):
        if not assign(i, set()):
            raise ValueError('Keine eindeutige Boxzuordnung fuer Quellflaeche %d innerhalb %.3f mm. '
                             'Moegliche Skalierung, Lageabweichung oder geaenderte Importgeometrie.' % (i+1, tolerance))
    pairs = sorted((i, j) for j, i in owner.items())
    error = max((max(abs(a-b) for a, b in zip(exp[i], act[j])) for i,j in pairs), default=0.0)
    return {'status': 'TEILFLAECHENBOXEN_BESTANDEN', 'mapping': pairs,
            'count': len(pairs), 'max_error_mm': error, 'numeric_tolerance_mm': tolerance,
            'scope': 'Box- und Anzahlvergleich; kein unabhaengiger Vergleich jedes Flaechenpunkts in NX.'}


def validate_job(base, job):
    if job.get('schema') != 'R09_IMPORT_V1' or job.get('unit') != 'mm':
        raise ValueError('Importauftrag ungueltig.')
    ids = set(); names = set()
    for p in job['parts'] + [job['smoke_test']]:
        if p['id'] in ids or p['part_file'].casefold() in names:
            raise ValueError('Doppelte Bauteil-ID/Datei.')
        ids.add(p['id']); names.add(p['part_file'].casefold())
        if not re.fullmatch('[A-Za-z0-9_]+[.]prt', p['part_file']):
            raise ValueError('Ungeeigneter Part-Dateiname.')
        if type(p['expected_sheets']) is not int or p['expected_sheets'] <= 0:
            raise ValueError('Keine erwarteten Flaechen.')
        if len(p['face_bounding_boxes_mm']) != p['expected_sheets']:
            raise ValueError('Flaechenanzahl widerspricht den Quellboxen.')
        for box in p['face_bounding_boxes_mm']:
            check_box(box)
        from .surface_check import reference_checked
        reference_checked(p)
        source = within(base, p['step_file'])
        if sha256(source) != p['sha256']:
            raise ValueError('STEP-Quelle veraendert: ' + str(source))
    if sum(p['expected_sheets'] for p in job['parts']) != job['total_sheets']:
        raise ValueError('Gesamtzahl widerspruechlich.')
    line_ids = set()
    for line in job['reference_lines']:
        if not isinstance(line.get('id'), str) or not line['id'] or line['id'] in line_ids:
            raise ValueError('Doppelte/leere Kartenlinien-ID.')
        line_ids.add(line['id'])
        if len(line['points_mm']) < 2:
            raise ValueError('Unvollstaendige Kartenlinie.')
        for pt in line['points_mm']:
            if len(pt) != 3:
                raise ValueError('Kartenpunkt ohne XYZ.')
            for value in pt:
                finite_number(value, 'Kartenpunkt')
        if any(math.dist(a,b) <= 1e-6 for a,b in zip(line['points_mm'],line['points_mm'][1:])):
            raise ValueError('Nullsegment in Kartenlinie: '+line['id'])
    segments = sum(len(x['points_mm'])-1 for x in job['reference_lines'])
    if type(job.get('line_segment_count')) is not int or job['line_segment_count'] != segments:
        raise ValueError('Kartenliniensegmentzahl widerspricht den Punkten.')
    return {'parts': len(job['parts']), 'sheets': job['total_sheets'],
            'reference_segments': sum(len(x['points_mm'])-1 for x in job['reference_lines'])}


def verify_runtime_files(base, scope="all"):
    if scope not in ('all', 'house'):
        raise ValueError('Unbekannter Pruefumfang: ' + str(scope))
    records = read_json(base / 'data/PROGRAMM_UND_QUELLEN_SHA256.json')
    if scope == 'house':
        # Haus-Neuaufbau benoetigt weder STEP-Quellgeometrie noch Importauftrag.
        # Gemeinsamer Code und Haus-/Leitungsquellen werden unveraendert geprueft.
        records = {p: h for p, h in records.items()
                   if p != 'data/IMPORTAUFTRAG_R09.json' and not p.startswith('CAD_IMPORT/')}
    for rel, expected in records.items():
        if sha256(within(base, rel)) != expected:
            raise ValueError('Programm-/Quelldatei geaendert oder Paket vermischt: ' + rel)
    return len(records)


def check_file_records(out, records):
    names = set()
    for row in records:
        rel = row['relative_file']
        if rel.casefold() in names:
            raise ValueError('Doppelte Ausgabedatei im Manifest: ' + rel)
        names.add(rel.casefold())
        p = within(out, rel)
        if not p.is_file() or p.stat().st_size != row['bytes'] or sha256(p) != row['sha256']:
            raise ValueError('Gespeicherte Datei fehlt/veraendert: ' + str(p))
    return len(records)
