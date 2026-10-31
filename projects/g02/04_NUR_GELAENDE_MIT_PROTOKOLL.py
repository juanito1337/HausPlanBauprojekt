# -*- coding: utf-8 -*-
"""In NX als Journal starten. Nur Gelaende samt automatischem Protokoll. Gesamtes G01e-Paket entpacken."""
import importlib.util
import datetime
import json
import tempfile
import traceback
import uuid
import os
from pathlib import Path
import sys

MODE = 'TERRAIN'

def main():
    base = Path(os.path.abspath(__file__)).parent
    for name in list(sys.modules):
        if name == 'gesamt' or name.startswith('gesamt.'):
            del sys.modules[name]
    path = base/'gesamt/__init__.py'
    try:
        spec = importlib.util.spec_from_file_location('gesamt',str(path),submodule_search_locations=[str(path.parent)])
        if spec is None or spec.loader is None:
            raise RuntimeError('Gesamtpaket kann nicht geladen werden.')
        module = importlib.util.module_from_spec(spec); sys.modules['gesamt'] = module
        spec.loader.exec_module(module)
        from gesamt.start import main as run
        return run(base,MODE)
    except Exception as error:
        report = {'patch':'MAIN01-A01-G01e-BOOTSTRAP','mode':MODE,'error':str(error),
                  'base':str(base),'entry':Path(__file__).name,'traceback':traceback.format_exc()}
        saved = None
        name = 'STARTFEHLER_G01e_BOOTSTRAP_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json'
        for folder in (base/'fehlerberichte',Path(tempfile.gettempdir())/'NX_G01_FEHLER'):
            try:
                folder.mkdir(parents=True,exist_ok=True)
                with (folder/name).open('x',encoding='utf-8') as stream:
                    json.dump(report,stream,ensure_ascii=False,indent=2)
                saved = folder/name; break
            except OSError:
                continue
        text = 'G01-Startpaket unvollstaendig/unlesbar: '+str(error)+'\nGesamtes ZIP entpacken, nicht nur die Starterdatei kopieren.\nProjektordner: '+str(base)+'\nFehlerbericht: '+str(saved)
        try:
            import NXOpen
            NXOpen.UI.GetUI().NXMessageBox.Show('NX G01 Startfehler',NXOpen.NXMessageBox.DialogType.Error,text)
        except Exception:
            print(text)
        return None

if __name__ == '__main__':
    main()
