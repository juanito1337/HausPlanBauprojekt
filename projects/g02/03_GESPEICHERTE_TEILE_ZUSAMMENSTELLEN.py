# -*- coding: utf-8 -*-
"""G02: gesamtes Paket entpacken; in NX ueber Journal abspielen starten."""
import os
from pathlib import Path
import sys
import importlib.util
import traceback
import datetime
import json
import tempfile
import uuid
MODE = 'ASSEMBLE'

def main():
    base=Path(os.path.abspath(__file__)).parent
    try:
        for package in ('gesamt','g02'):
            for name in list(sys.modules):
                if name==package or name.startswith(package+'.'):
                    del sys.modules[name]
            path=base/package/'__init__.py'
            spec=importlib.util.spec_from_file_location(package,str(path),submodule_search_locations=[str(path.parent)])
            if spec is None or spec.loader is None:raise RuntimeError('Paket nicht lesbar: '+package)
            module=importlib.util.module_from_spec(spec);sys.modules[package]=module;spec.loader.exec_module(module)
        from g02.start import main as run
        return run(base,MODE)
    except Exception as error:
        report={'revision':'G02-BOOTSTRAP','mode':MODE,'error':str(error),'traceback':traceback.format_exc(),'base':str(base)}
        filename='STARTFEHLER_G02_BOOTSTRAP_'+uuid.uuid4().hex[:8]+'.json'
        saved=None
        for folder in (base/'fehlerberichte',Path(tempfile.gettempdir())/'NX_G02_FEHLER'):
            try:
                folder.mkdir(parents=True,exist_ok=True)
                with (folder/filename).open('x',encoding='utf-8') as stream:
                    json.dump(report,stream,ensure_ascii=False,indent=2)
                saved=folder/filename;break
            except OSError:continue
        text='G02 Startfehler: '+str(error)+'\nGesamtes Paket entpacken.\nProtokoll: '+str(saved)
        try:
            import NXOpen
            NXOpen.UI.GetUI().NXMessageBox.Show('G02 Startfehler',NXOpen.NXMessageBox.DialogType.Error,text)
        except Exception:print(text)
        return report

if __name__=='__main__':main()
