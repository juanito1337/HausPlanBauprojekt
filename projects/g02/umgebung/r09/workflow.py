# -*- coding: utf-8 -*-
"""R11: Haus zuerst, unabhaengig vom STEP-Umgebungsimport.

Kein automatisch angenommener Hoehenanschluss. Keine Unterdrueckung von
Import-/Messfehlern. Erfolg des Hauses wird vor dem Umfeld separat dokumentiert.
Bestehende Nutzermodelle werden weder veraendert noch geschlossen. Die beiden
Erzeuger bleiben verwendbar; .run ist die bestehende, getestete STEP-Engine.
"""
import copy
import datetime
import traceback
import uuid
from pathlib import Path
from .core import (PATCH, absolute, read_json, write_json, settings_checked,
                   verify_runtime_files, check_file_records, placement, within)
from .run import (run_project, build_house_copy, record_saved, Log, check_master)
from .nx_adapter import SceneAdapter
from haus2406_r03.haus_runtime import path_key
from haus2406_r03.haus_run import preflight_filenames


MODES = ('ALL', 'HOUSE', 'ENVIRONMENT')


def _loaded_part(nx, path):
    found = [p for p in nx.session.Parts if path_key(p.FullPath) == path_key(path)]
    if len(found) != 1:
        raise RuntimeError('Erzeugtes Part nicht eindeutig geladen: ' + str(path))
    return found[0]


def display_saved(nx, path):
    """Nur Anzeige eines soeben erzeugten Parts, keine Schreibrechte erweitern.

    Das Teil kann einem anderen Adapter desselben Laufs gehoeren. Deshalb
    ausdruecklich NICHT ensure_work umgehen oder in self.created hineinmogeln.
    Kein Speichern, keine Attribute, keine Geometrieaenderung.
    """
    part = _loaded_part(nx, path)
    display = nx.session.Parts.Display
    if display is None or display.Tag != part.Tag:
        result = nx.session.Parts.SetDisplay(part, False, False)
        if not isinstance(result, tuple) or len(result) != 2:
            raise RuntimeError('SetDisplay-Rueckgabe unerwartet.')
        nx.dispose(result[1])
    display = nx.session.Parts.Display
    if display is None or display.Tag != part.Tag:
        raise RuntimeError('Gespeichertes Modell konnte nicht angezeigt werden.')
    nx.fit(part)
    return part


def checked_house_result(out, house, verification):
    if house.get('status') != 'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT':
        raise RuntimeError('Hauslauf nicht erfolgreich gespeichert.')
    if verification.get('status') != 'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN':
        raise RuntimeError('Haus-Datei-/Strukturpruefung nicht bestanden.')
    directory = absolute(house['output_directory'])
    directory.relative_to(absolute(out))  # Kein fremdes Haus als Ergebnis einsetzen.
    rows = [record_saved(out, within(directory, r['file']), r) for r in house['files']]
    master = directory / 'HAUS_MASTER.prt'
    if not any(path_key(within(out, r['relative_file'])) == path_key(master) for r in rows):
        raise RuntimeError('Haus-Master fehlt im gespeicherten Ergebnisregister.')
    check_file_records(out, rows)
    mode = house['mode']
    if mode not in ('PRUEFMODELL_MIT_NAEHERUNGEN', 'REFERENZGERUEST'):
        raise RuntimeError('Unbekannter Hausmodus.')
    if mode == 'REFERENZGERUEST' and house['built_solids'] != 0:
        raise RuntimeError('Referenzmodus enthaelt unerwartete Koerper.')
    return {'master': master.relative_to(out).as_posix(), 'mode': mode,
            'built_solids': house['built_solids'], 'geometry_revision': 'R11_FENSTERABGLEICH' if (out/'_haus_eingaben/data/FENSTER_AENDERUNGEN_R11.json').is_file() else house.get('geometry_revision', 'R06_UNVERAENDERT'),
            'status': 'ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT',
            'technical_as_built_approval': False,
            'verification_status': verification['status']}, rows


def checked_environment_result(out, environment):
    allowed = ('R09_ERZEUGT_BEZUGSSYSTEME_GETRENNT', 'R09_ERZEUGT_MIT_NUTZERHOEHENANSCHLUSS')
    if environment.get('status') not in allowed:
        raise RuntimeError('Umgebungslauf ohne vollstaendigen Erzeugungserfolg.')
    if environment.get('environment_status') != 'ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT':
        raise RuntimeError('Umgebung ist nicht import- und strukturgeprueft.')
    directory = absolute(environment['output_directory'])
    directory.relative_to(absolute(out))
    master = within(directory, environment['environment_master'])
    rows = []
    for row in environment['files']:
        p = within(directory, row['relative_file'])
        rows.append(record_saved(out, p, row))
    if not any(path_key(within(out, r['relative_file'])) == path_key(master) for r in rows):
        raise RuntimeError('Umgebungs-Master fehlt im Ergebnisregister.')
    check_file_records(out, rows)
    return {'master': master.relative_to(out).as_posix(),
            'manifest': (directory/'manifest_R09.json').relative_to(out).as_posix(),
            'status': 'ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT',
            'technical_as_built_approval': False,
            'checked_source_points': environment.get('total_checked_source_points'),
            'surface_validation': environment.get('surface_validation','INTENSIV'),
            'surface_area_check_performed': environment.get('surface_area_check_performed',True),
            'surface_full_reference_check_performed': environment.get('surface_full_reference_check_performed',True)}, rows


def phase_pointer(base, out, which, result, records):
    # Diese Zeiger zeigen nur abgeschlossene Einzelphasen, nie einen erfundenen
    # Gesamterfolg. Das Manifest ist schon VOR dem Zeiger dauerhaft geschrieben.
    pointer = {'schema': 'R11_PHASE_POINTER_V1', 'patch': PATCH,
               'phase': which, 'output_directory': str(out),
               'manifest': str(out/'manifest_R11.json'),
               'master': str(within(out, result['master'])),
               'status': result['status'], 'files': records,
               'technical_as_built_approval': False}
    write_json(base/('LETZTER_'+which+'LAUF_R11.json'), pointer)


def run_checked_project(base, mode='ALL', config=None, adapter_factory=SceneAdapter,
                        house_builder=build_house_copy, environment_runner=run_project):
    """Standard: erst Haus, dann STEP-Umfeld. Fehler stoppen nur den weiteren Ablauf.

    HOUSE beruehrt weder den STEP-Importer noch dessen Definition oder Auftrag.
    ENVIRONMENT beruehrt keine bereits gespeicherte Hausdatei.
    """
    if mode not in MODES:
        raise ValueError('Unbekannter Startmodus: '+str(mode))
    base = absolute(base)
    cfg = settings_checked(copy.deepcopy(read_json(base/'data/EINSTELLUNGEN_R09.json')
                                        if config is None else config))
    build_house = mode == 'HOUSE' or (mode == 'ALL' and cfg['build_house'])
    build_environment = mode != 'HOUSE'
    # Absichtlich KEIN STEP-Auftrag/Importerzugriff vor einem reinen Hauslauf.
    verified = verify_runtime_files(base, scope='house')
    root = Path(cfg['output_root']).expanduser() if cfg['output_root'].strip() else base/'ausgabe'
    root = absolute(root if root.is_absolute() else base/root)
    root.mkdir(parents=True, exist_ok=True)
    out = root/('R11_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8])
    out.mkdir(exist_ok=False)
    log = Log(out/'laufprotokoll_R11.txt')
    nx = None
    state = {'schema': 'R11_RUN_V1', 'patch': PATCH, 'mode': mode,
             'output_directory': str(out), 'started': datetime.datetime.now().isoformat(),
             'status': 'GESTARTET', 'phase': 'VORPRUEFUNG', 'files': [],
             'house': None, 'environment': None, 'combined_master': None, 'project_reference_master': None,
             'verified_runtime_files_house_scope': verified,
             'technical_as_built_approval': False, 'own_NX_release_test': False,
             'settings': cfg,
             'limits': ['Haus: zehn Ueberschneidungspaare und zwei teilweise blockierte Oeffnungen offen.',
                        'Leitungen: Planlinien, keine bestaetigte Verlegetiefe.',
                        'Dachtragwerk, Flachdachaufbau und Bestandsgenauigkeit nicht vollstaendig belegt.',
                        'Haushoehenanschluss an DGM/bDOM fehlt bis zur belegten Nutzerangabe.',
                        'Vegetation: offene Referenzflaechen aus unterschiedlichen Datenstaenden.']}
    write_json(out/'manifest_R11.json', state)
    try:
        nx = adapter_factory(log); log.nx = nx
        state['nx_runtime'] = nx.runtime_information()
        log('AKTION R11: '+mode+'; Haus unabhaengig vom STEP-Import.')
        if build_house:
            from haus2406_r03.haus_compile import compile_house
            house_data = read_json(base/'basis/Haus_R06/data/haus.json')
            from .video import enrich_if_present
            house_data = enrich_if_present(base, house_data)
            names = [p['file'] for p in compile_house(house_data, True)['parts']] + ['HAUS_MASTER.prt','PROJEKT_MASTER_R11_HOEHENBEZUG_OFFEN.prt','GESAMTMODELL_R11.prt']
            preflight_filenames(nx, names)
            state['phase'] = 'HAUS_ERZEUGEN_UND_PRUEFEN'
            write_json(out/'manifest_R11.json', state)
            house, verification = house_builder(base, out)
            result, rows = checked_house_result(out, house, verification)
            state['house'] = result; state['files'].extend(rows)
            state['phase'] = 'HAUS_GESPEICHERT'
            write_json(out/'manifest_R11.json', state)
            phase_pointer(base, out, 'HAUS', result, rows)
            log('HAUS GESPEICHERT UND DATEIGEPRUEFT: '+str(within(out, result['master'])))
            log('Fachliche offene Punkte bleiben bestehen. Kein Tragwerks-/Bestandsnachweis.')
        if build_environment:
            state['phase'] = 'UMGEBUNG_IMPORTIEREN_UND_PRUEFEN'
            write_json(out/'manifest_R11.json', state)
            env_config = copy.deepcopy(cfg)
            env_config['build_house'] = False
            env_config['output_root'] = str(out/'umgebung_lauf')
            environment = environment_runner(base, config=env_config,
                                             adapter_factory=adapter_factory, notify=False)
            result, rows = checked_environment_result(out, environment)
            state['environment'] = result; state['files'].extend(rows)
            state['phase'] = 'UMGEBUNG_GESPEICHERT'
            write_json(out/'manifest_R11.json', state)
            phase_pointer(base, out, 'UMGEBUNG', result, rows)
            log('UMGEBUNG GESPEICHERT: '+str(within(out, result['master'])))
        state['phase'] = 'ABSCHLUSSPRUEFUNG'
        write_json(out/'manifest_R11.json', state)
        # Haus zuerst bzw. allein betrachten; keine 30-m-Abstandsmontage vortaeuschen.
        final = within(out, (state['house'] or state['environment'])['master'])
        offset = placement(cfg)
        if (state['house'] and state['environment'] and offset is not None and
                state['house']['mode'] == 'PRUEFMODELL_MIT_NAEHERUNGEN'):
            final = out/'GESAMTMODELL_R11.prt'
            master = nx.new_part(final, 'GESAMTMODELL_R11')
            expected = [('HAUS_R06', within(out, state['house']['master']), (0,0,0)),
                        ('UMGEBUNG_R09', within(out, state['environment']['master']), offset)]
            for name, path, pos in expected:
                nx.add_at(master, path, name, pos)
            nx._set_user_attribute(master, 'HAUS_HOEHENQUELLE', cfg['height_connection']['source'], 'MONTAGE')
            nx._set_user_attribute(master, 'HAUS_H_EG_QUELLHOEHE_M', cfg['height_connection']['H_EG_zero_in_source_datum_m'], 'MONTAGE')
            nx._set_user_attribute(master, 'HAUS_REVISION', PATCH, 'MONTAGE')
            nx._set_user_attribute(master, 'HAUS_TRANSFORMATION', 'UMGEBUNG_NUR_Z_TRANSLATION', 'MONTAGE')
            nx._set_user_attribute(master, 'HAUS_BESTAND_BESTAETIGT', 'NEIN', 'MONTAGE')
            nx.prepare_view(master)
            state['combined_component_checks'] = check_master(nx, master, expected)
            state['files'].append(record_saved(out, final, nx.save(master)))
            state['combined_master'] = final.relative_to(out).as_posix()
        if state['house'] and state['environment'] and state['combined_master'] is None:
            # Both datasets are present in one project tree. Keep BOTH original Z systems.
            # The 30 m separation is intentional and explicitly NOT a site placement.
            final = out/'PROJEKT_MASTER_R11_HOEHENBEZUG_OFFEN.prt'
            master = nx.new_part(final, 'PROJEKT_R11_BEZUG_OFFEN')
            expected = [('HAUS_FFB_NULL', within(out,state['house']['master']),(0,0,0)),
                        ('UMGEBUNG_QUELLHOEHEN_NICHT_MONTIERT',within(out,state['environment']['master']),(0,0,0))]
            for name,path,pos in expected:
                nx.add_at(master,path,name,pos)
            for key,value in {'HAUS_REVISION':PATCH,'HAUS_MONTAGESTATUS':'NUR_PROJEKTREFERENZ_HOEHENBEZUG_OFFEN',
                              'HAUS_BESTAND_BESTAETIGT':'NEIN','HAUS_TRANSFORMATION':'KEIN_Z_OFFSET_KEINE_SKALIERUNG',
                              'HAUS_HINWEIS':'Umgebung ca. 30 m oberhalb Haus wegen verschiedener Nullhoehen. Keine physische Montage.'}.items():
                nx._set_user_attribute(master,key,value,'PROJEKTREFERENZ')
            nx.prepare_view(master)
            state['project_reference_checks']=check_master(nx,master,expected)
            state['files'].append(record_saved(out,final,nx.save(master)))
            state['project_reference_master']=final.relative_to(out).as_posix()
            state['physical_site_alignment_verified']=False
        state['checked_file_count'] = check_file_records(out, state['files'])
        verify_runtime_files(base, scope='all' if build_environment else 'house')
        display_saved(nx, final)
        state['status'] = 'R11_ERZEUGT_GEPRUEFT_FACHLICH_OFFEN'
        state['phase'] = 'ABGESCHLOSSEN'
        state['finished'] = datetime.datetime.now().isoformat()
        state['displayed_master'] = final.relative_to(out).as_posix()
        write_json(out/'manifest_R11.json', state)
        write_json(base/'LETZTER_GESAMTLAUF_R11.json', {
            'output_directory': str(out), 'manifest': str(out/'manifest_R11.json'),
            'status': state['status'], 'mode': mode,
            'displayed_master': str(final), 'combined_master': state['combined_master']})
        text = 'R11: angeforderter Ablauf abgeschlossen.\n'+str(final)
        if state['house'] and state['environment'] and not state['combined_master']:
            text += '\n\nHaus und Umgebung im gemeinsamen Projektbaum, aber NICHT hoehenrichtig montiert. Umgebungs-Quellhoehen bleiben ca. 30 m ueber Haus. Zur Hauskontrolle HAUS_MASTER.prt separat anzeigen.'
        if state['house']:
            text += '\nHausmodus: '+state['house']['mode']+'; Koerper: '+str(state['house']['built_solids'])
        text += '\n\nZum Weiterarbeiten die gespeicherten .prt-Dateien oeffnen; NICHT erneut erzeugen.\nFachliche offene Punkte bleiben.\nPruefbericht: '+str(out/'manifest_R11.json')
        log(text); nx.safe_message(text)
        return state
    except Exception as error:
        state['status'] = 'R11_ABGEBROCHEN_KEIN_GESAMTERFOLG'
        state['error'] = str(error); state['traceback'] = traceback.format_exc()
        context = {'output_directory': str(out), 'phase': state['phase'],
                   'saved_house_master': str(within(out, state['house']['master'])) if state['house'] else None,
                   'saved_environment_master': str(within(out, state['environment']['master'])) if state['environment'] else None}
        error.r11_context = context
        try:
            write_json(out/'manifest_R11.json', state)
            log('ABBRUCH: '+str(error))
            if context['saved_house_master']:
                log('Haus bereits separat gespeichert: '+context['saved_house_master'])
        except Exception as log_error:
            error.r09_log_failure = str(log_error)
        # Nie einen Fehler durch Anzeige-Wiederherstellung verdecken.
        if nx is not None:
            try:
                nx.restore_display_after_failure()
            except Exception as display_error:
                context['restore_display_error'] = str(display_error)
        raise
