# -*- coding: utf-8 -*-
"""Datei- und Startpruefungen. Standardbibliothek, keine NX-Abhaengigkeit."""
import hashlib
import json
import math
import os
import re
import tempfile
import uuid
from pathlib import Path

REVISION = 'R06'
PATCH = 'R06-QUELLEN-KONSISTENZ'
PATH_POLICY = 'ABSOLUT_LEXIKALISCH_OHNE_REALPATH'


def read_json(path):
    """BOM-tolerant; doppelte Schluessel und NaN/Infinity sind keine Projektdaten."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Doppelter JSON-Schluessel: ' + str(key))
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nicht endlicher JSON-Wert: ' + value)
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                          object_pairs_hook=pairs, parse_constant=invalid)
    except (OSError, ValueError) as ex:
        raise ValueError('Datei nicht lesbar oder ungueltig: %s\n%s' % (path, ex)) from ex


def atomic_json(path, value):
    """Nur eigene Protokolle: erst komplett schreiben, dann atomar ersetzen."""
    path = Path(path)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def settings_checked(settings):
    if not isinstance(settings, dict):
        raise ValueError('einstellungen.json muss ein JSON-Objekt sein.')
    fields = ('allow_estimates', 'show_review_consent', 'show_reference_curves',
              'continue_on_feature_error', 'automatic_smoke_test')
    for key in fields:
        if key in settings and type(settings[key]) is not bool:
            raise ValueError('%s muss true oder false sein, kein Text und keine Zahl.' % key)
    if settings.get('continue_on_feature_error', False):
        raise ValueError('Fehlerhafte Bauteile duerfen nicht still uebersprungen werden.')
    if settings.get('automatic_smoke_test', True) is not True:
        raise ValueError('R03 setzt automatic_smoke_test=true voraus. Der Test darf nicht umgangen werden.')
    if not isinstance(settings.get('output_root', ''), str):
        raise ValueError('output_root muss ein Pfad als Text sein.')
    return dict(settings)


def absolute_path(path):
    """Absoluter Pfad ohne Aufloesen von Symlinks oder Volume-Handles.

    Der aufrufende Code prueft Dateizugriff/Existenz gesondert. Diese Funktion
    ist KEIN Zugriffs- oder Dateisystemnachweis und verschluckt keine IO-Fehler.
    Laufwerksalias und UNC-Alias werden nicht blind als identisch behandelt.
    """
    value = os.fspath(path)
    if not isinstance(value, str):
        raise TypeError('Projektpfade muessen Text sein, keine Bytes.')
    if not value or '\x00' in value:
        raise ValueError('Leerer Pfad oder NUL-Zeichen im Projektpfad.')
    return Path(os.path.abspath(value))


def path_key(path):
    # NX-Zielumgebung Windows; auch unter Linux gleiche Namenskonflikte testen.
    # Bewusst keine physische Alias-/Symlinkaufloesung. Unterschiedliche Aliase
    # koennen einen konservativen Pfadabbruch erzeugen, aber keine Freigabe.
    return str(absolute_path(path)).replace('\\', '/').casefold()


def checked_part_filenames(filenames):
    seen = set()
    for name in filenames:
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_\-]+\.prt', name):
            raise ValueError('Unsicherer Part-Dateiname: ' + str(name))
        if name.casefold() in seen:
            raise ValueError('Doppelter Part-Dateiname: ' + name)
        if name.split('.')[0].upper() in {'CON','PRN','AUX','NUL'} or re.fullmatch(r'(COM|LPT)[1-9]', name.split('.')[0], re.I):
            raise ValueError('Reservierter Windows-Dateiname: ' + name)
        seen.add(name.casefold())
    return list(filenames)


def verify_output_paths(out, filenames):
    out = absolute_path(out)
    checked_part_filenames(filenames)
    for name in filenames:
        path = out / name
        if path.exists():
            raise FileExistsError('Vorhandenes Part wird nicht ueberschrieben: ' + str(path))
        # Eigene konservative Schutzgrenze, keine behauptete Siemens-Spezifikation.
        if len(str(path)) > 230:
            raise ValueError('Projektpfad zu lang fuer die konservative R03-Schutzgrenze (230 Zeichen). '
                             'Kurzen lokalen Ausgabeordner in output_root waehlen: ' + str(path))
    with tempfile.NamedTemporaryFile(prefix='.haus_write_probe_', dir=str(out), delete=True) as handle:
        handle.write(b'HAUS_R03_WRITE_TEST')
        handle.flush()
    return True


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def input_fingerprint(base):
    base = Path(base)
    files = list((base / 'src' / 'haus2406_r03').glob('*.py'))
    files += [base / 'data' / 'haus.json', base / 'data' / 'einstellungen.json']
    result = {}
    for file in sorted(files):
        result[str(file.relative_to(base)).replace('\\', '/')] = sha256_file(file)
    return result


def verify_saved_files(out, manifest):
    """Alle protokollierten Dateien pruefen, bevor NX sie oeffnet."""
    out = absolute_path(out)
    if manifest.get('status') != 'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT':
        raise ValueError('Kein erfolgreich abgeschlossener Hauslauf im Manifest.')
    files = manifest.get('files', [])
    if not files:
        raise ValueError('Manifest enthaelt keine gespeicherten Parts.')
    names = checked_part_filenames([f['file'] for f in files])
    if names.count('HAUS_MASTER.prt') != 1:
        raise ValueError('Masterdatei im Manifest fehlt oder ist doppelt.')
    if len(files) != manifest.get('component_count', -1) + 1:
        raise ValueError('Dateianzahl und Komponentenanzahl im Manifest widersprechen sich.')
    for record in files:
        path = out / record['file']
        if not path.is_file() or path.stat().st_size <= 0:
            raise FileNotFoundError('Gespeichertes Part fehlt oder ist leer: ' + str(path))
        if path.stat().st_size != record['bytes']:
            raise ValueError('Datei seit Modelllauf veraendert (Groesse): ' + str(path))
        if not record.get('sha256') or sha256_file(path) != record['sha256']:
            raise ValueError('Datei seit Modelllauf veraendert (SHA-256): ' + str(path))
    return files
