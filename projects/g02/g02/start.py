# -*- coding: utf-8 -*-
import builtins
import datetime
import json
from pathlib import Path
import tempfile
import traceback
import uuid
from . import PATCH
from .workflow import run
from gesamt.core import absolute, child_exception_context

def message(text,error=False):
    try:
        import NXOpen
        listing=NXOpen.Session.GetSession().ListingWindow
        listing.Open();listing.WriteLine(text)
        kind=NXOpen.NXMessageBox.DialogType.Error if error else NXOpen.NXMessageBox.DialogType.Information
        NXOpen.UI.GetUI().NXMessageBox.Show('NX Gesamtprojekt G02',kind,text)
    except Exception:print(text)

def main(base,mode):
    base=absolute(base)
    if getattr(builtins,'_NX_GESAMT_G01_RUNNING',False):
        message('Ein Projektlauf ist bereits aktiv. Keinen zweiten Starter starten.',True);return
    builtins._NX_GESAMT_G01_RUNNING=True
    try:
        result=run(base,mode)
        if result['status']=='ABGEBROCHEN_DURCH_NUTZER_KEINE_NEUE_MONTAGE':
            message('G02: auf Wunsch abgebrochen. Keine neue Montage erzeugt.');return result
        text='G02: angeforderter Ablauf abgeschlossen.\n'+result['displayed_master']
        if result.get('project'):
            p=result['height_plan']
            text+='\n\nGesamte Umgebung montiert: Z = %.3f mm\nAnker relativ EG: %.3f mm\n%s' % (
                        p['translation_mm'][2],p['target_ground_z_mm'],p['status'])
            text+='\nHoehenbezogene Arbeitsmontage, KEIN vermessener Bestandsnachweis.'
        else:
            text+='\nEinzelbereich erzeugt. Fuer gemeinsame Hoehenmontage 03 oder 05 verwenden.'
        text+='\n\nProtokoll: '+str(Path(result['output_directory'])/'manifest_G02.json')
        text+='\nZum Weiterarbeiten die erzeugte .prt-Masterdatei oeffnen, nicht erneut erzeugen.'
        message(text);return result
    except Exception as error:
        report={'patch':PATCH,'mode':mode,'error':str(error),'traceback':traceback.format_exc(),
                'context':getattr(error,'g02_context',{}),'nested_diagnostics':child_exception_context(error),
                'montage_diagnostics':getattr(error,'g02_montage_diagnostics',{}),
                'NX_runtime_test_by_author':False}
        filename='STARTFEHLER_G02_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json'
        target=None
        for directory in (base/'fehlerberichte',Path(tempfile.gettempdir())/'NX_G02_FEHLER'):
            try:
                directory.mkdir(parents=True,exist_ok=True)
                with (directory/filename).open('x',encoding='utf-8') as f:
                    json.dump(report,f,ensure_ascii=False,indent=2,allow_nan=False)
                target=directory/filename;break
            except (OSError,ValueError,TypeError):continue
        text='G02 abgebrochen: '+str(error)+'\n\nFehlerbericht: '+str(target)
        ctx=report['context']
        for key,label in [('saved_house','Haus bereits gespeichert'),('saved_environment','Umgebung bereits gespeichert')]:
            if ctx.get(key):text+='\n\n'+label+':\n'+ctx[key]
        text+='\nKeine vorhandenen Dateien loeschen. Keine Gesamterfolgsmeldung.'
        message(text,True);return report
    finally:builtins._NX_GESAMT_G01_RUNNING=False
