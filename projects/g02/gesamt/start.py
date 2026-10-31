# -*- coding: utf-8 -*-
"""One final message only; nested engines retain the explicit house-estimate consent."""
import builtins
import datetime
import json
from pathlib import Path
import sys
import tempfile
import traceback
import uuid
from . import PATCH
from .core import absolute, run_project, child_exception_context


def message(text,error=False):
    try:
        import NXOpen
        listing = NXOpen.Session.GetSession().ListingWindow
        listing.Open(); listing.WriteLine(text)
        kind = NXOpen.NXMessageBox.DialogType.Error if error else NXOpen.NXMessageBox.DialogType.Information
        NXOpen.UI.GetUI().NXMessageBox.Show('NX Gesamtprojekt G01e',kind,text)
    except Exception:
        print(text)


def main(base,mode):
    base = absolute(base)
    if getattr(builtins,'_NX_GESAMT_G01_RUNNING',False):
        message('Ein G01-Lauf ist bereits aktiv. Keinen zweiten Erzeuger starten.',True)
        return None
    builtins._NX_GESAMT_G01_RUNNING = True
    try:
        if sys.version_info < (3,8):
            raise RuntimeError('Python >= 3.8 innerhalb von NX erforderlich.')
        if mode == 'TERRAIN':
            from .terrain_only import run_terrain_only
            result = run_terrain_only(base)
        else:
            result = run_project(base,mode)
        text = 'G01e: angeforderter Ablauf abgeschlossen.\n'+result['displayed_master']
        if result['house']:
            text += '\nHausstand MAIN01-A01: '+str(result['house']['built_solids'])+' Koerper. Modus: '+result['house']['mode']
        if result['environment']:
            text += '\nUmgebung: '+result['environment']['surface_validation']+'-Modus fuer Vegetation; DGM mit direkter UV-/Randpruefung. Kein Bestandsnachweis.'
        if result['project'] and not result['project']['height_connection_confirmed_by_user']:
            text += '\n\nHoehenbezug OFFEN: Haus und Umgebung im gleichen Projektbaum, aber ca. 30 m vertikal getrennt. Keine physische Montage.'
        if result.get('terrain'):
            text += '\nNur Gelaende erzeugt. Kein Haus-/Vegetationsneuaufbau.\nProtokoll: '+result['terrain_log']
        text += '\n\nArbeitsmodell mit offenen Punkten; keine Statik-/Bestandsfreigabe.\nWeiterarbeit: gespeicherte .prt-Dateien oeffnen, NICHT erneut erzeugen.\nManifest: '+str(Path(result['output_directory'])/'manifest_G01.json')
        message(text)
        return result
    except Exception as error:
        report = {'patch':PATCH,'status':'ABGEBROCHEN_KEIN_GESAMTERFOLG','mode':mode,
                  'base':str(base),'error':str(error),'traceback':traceback.format_exc(),
                  'time':datetime.datetime.now().isoformat(),'python':sys.version,
                  'context':getattr(error,'gesamt_g01_context',{}),
                  'nested_diagnostics':child_exception_context(error)}
        filename = 'STARTFEHLER_G01e_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json'
        target = None
        for directory in (base/'fehlerberichte',Path(tempfile.gettempdir())/'NX_G01_FEHLER'):
            try:
                directory.mkdir(parents=True,exist_ok=True)
                with (directory/filename).open('x',encoding='utf-8') as stream:
                    json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
                target = directory/filename; break
            except (OSError,ValueError,TypeError):
                continue
        text = 'G01e abgebrochen: '+str(error)+'\n\nFehlerbericht: '+str(target or 'nicht schreibbar')
        if report['context'].get('saved_house'):
            text += '\n\nHaus bereits gespeichert und dateigeprueft:\n'+report['context']['saved_house']+'\nKein neuer Hauslauf erforderlich, wenn nur die Umgebung scheitert.'
        audit = report['nested_diagnostics'].get('nx_terrain_audit_g01a',{})
        if audit:
            text += '\n\nGelaendeprotokoll (auch im Fehlerbericht enthalten):\n'+str(audit.get('report_file',''))
            snapshot=audit.get('unverified_snapshot') or {}
            if snapshot.get('exists'):
                text += '\nUngepruefte Importkopie gesichert, KEIN freigegebenes Modell:\n'+snapshot['path']
        text += '\nKeine vorhandenen Dateien loeschen. Keine Gesamterfolgsmeldung.'
        message(text,True)
        report['report_file'] = str(target) if target else None
        return report
    finally:
        builtins._NX_GESAMT_G01_RUNNING = False
