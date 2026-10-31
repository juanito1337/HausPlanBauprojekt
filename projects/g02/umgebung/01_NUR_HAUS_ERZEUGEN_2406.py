# -*- coding: utf-8 -*-
"""In NX 2406 als Journal abspielen. Gesamtes R11a-ZIP vorher entpacken.
Eindeutiger Einstieg fuer die gewaehlte Erzeugungsart. Kein normales Python.
"""
import datetime
import importlib.util
import json
import os
import sys
import tempfile
import traceback
import uuid
from pathlib import Path


def load_package(name, directory):
    for key in list(sys.modules):
        if key == name or key.startswith(name + '.'):
            del sys.modules[key]
    spec = importlib.util.spec_from_file_location(name, str(directory/'__init__.py'),
                                                submodule_search_locations=[str(directory)])
    if spec is None or spec.loader is None:
        raise RuntimeError('Python-Paket nicht ladbar: '+str(directory))
    mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod)
    return mod


MODE = 'HOUSE'


def main():
    base=Path(os.path.abspath(__file__)).parent
    try:
        if sys.version_info < (3,8):
            raise RuntimeError('Python >= 3.8 innerhalb von NX erforderlich.')
        import NXOpen
        load_package('haus2406_r03',base/'basis/Haus_R06/src/haus2406_r03')
        load_package('r09',base/'r09')
        from r09.performance import run_optimized_project as run_checked_project
        return run_checked_project(base, mode=MODE)
    except Exception as ex:
        report={'status':'ABGEBROCHEN','patch':'R11a-LAUFZEIT',
                'entry':Path(__file__).name,'project_base':str(base),
                'error':str(ex),'traceback':traceback.format_exc(),'python':sys.version,
                'time':datetime.datetime.now().isoformat(),
                'note':'Kein vollstaendiger Erfolg; ggf. gespeicherte Teilergebnisse im Manifest gekennzeichnet.'}
        cause=ex;seen=set()
        while cause is not None and id(cause) not in seen:
            seen.add(id(cause))
            for key in ('r11a_context','r11_context','r09_context','nx_unit_check','nx_attribute_check','r09_log_failure','nx_surface_check','nx_area_measurement','nx_runtime'):
                value=getattr(cause,key,None)
                if value is not None and key not in report:
                    report[key]=value
            cause=cause.__cause__ or cause.__context__
        name='STARTFEHLER_R09_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:8]+'.json'
        result=None
        for dest in (base/'fehlerberichte',Path(tempfile.gettempdir())/'NX_R09_Fehler'):
            try:
                dest.mkdir(parents=True,exist_ok=True)
                with (dest/name).open('x',encoding='utf-8') as f:
                    json.dump(report,f,ensure_ascii=False,indent=2)
                result=dest/name;break
            except OSError:
                continue
        message='R11a abgebrochen: '+str(ex)+'\n\nFehlerbericht: '+str(result)
        ctx=report.get('r11a_context') or report.get('r11_context', {})
        if ctx.get('saved_house_master'):
            message+='\n\nHaus bereits gespeichert und dateigeprueft:\n'+ctx['saved_house_master']
            message+='\nKein Gesamterfolg. Haus fachlich weiterhin ein Pruefmodell.'
        try:
            print(message)
        except Exception:
            pass
        try:
            import NXOpen
            listing=NXOpen.Session.GetSession().ListingWindow;listing.Open();listing.WriteLine(message)
            NXOpen.UI.GetUI().NXMessageBox.Show('NX-Projekt R11a',NXOpen.NXMessageBox.DialogType.Error,message)
        except Exception:
            pass
        report['report_file']=str(result) if result else None
        return report


if __name__=='__main__':
    main()
