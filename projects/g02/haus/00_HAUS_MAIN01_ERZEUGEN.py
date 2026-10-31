# -*- coding: utf-8 -*-
"""Start this ONE journal in NX 2406. House only; does not import any STEP file."""
import datetime
import json
import os
import sys
import tempfile
import traceback
import uuid
from pathlib import Path


def main():
    base=Path(os.path.abspath(__file__)).parent
    root=str(base/'src')
    # A previous imported Python module from another extraction must not be reused.
    for name in list(sys.modules):
        if name=='main01' or name.startswith('main01.') or name=='haus2406_r03' or name.startswith('haus2406_r03.'):
            del sys.modules[name]
    if root not in sys.path:sys.path.insert(0,root)
    try:
        from main01.runtime import run_main
        result=run_main(base)
        import NXOpen
        NXOpen.UI.GetUI().NXMessageBox.Show('HAUS MAIN01-A01',NXOpen.NXMessageBox.DialogType.Information,
            'Haus gespeichert und datei-/strukturgeprueft:\n'+result['saved_house']+'\n\n'
            +str(result['built_solids'])+' Koerper, '+str(result['component_count'])+' Komponenten.\n'
            'Versionierte ARBEITSBASIS MAIN01-A01, keine Baufreigabe.\n'
            'Weiterarbeiten: HAUS_MASTER.prt direkt oeffnen, nicht erneut generieren.\n'
            'Kein Garten, Gelaende oder STEP-Import in diesem Lauf.')
        return result
    except Exception as exc:
        state={'patch':'MAIN01-A01-DACHANSCHLUSS','entry':Path(__file__).name,'error':str(exc),
               'traceback':traceback.format_exc(),'time':datetime.datetime.now().isoformat(),
               'project_base':str(base),'status':'ABGEBROCHEN'}
        if hasattr(exc,'main01_context'):state['main01_context']=exc.main01_context
        report=None
        for destination in [base/'fehlerberichte',Path(tempfile.gettempdir())/'HAUS_MAIN01_FEHLER']:
            try:
                destination.mkdir(parents=True,exist_ok=True)
                report=destination/('STARTFEHLER_MAIN01_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json')
                report.write_text(json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');break
            except Exception:report=None
        message='MAIN01 abgebrochen: '+str(exc)+'\n\nFehlerbericht: '+str(report or 'nicht schreibbar')
        try:
            import NXOpen
            NXOpen.UI.GetUI().NXMessageBox.Show('HAUS MAIN01-A01',NXOpen.NXMessageBox.DialogType.Error,message)
        except Exception:print(message)
        return None

if __name__=='__main__':main()
