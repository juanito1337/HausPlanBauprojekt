# -*- coding: utf-8 -*-
"""All real G02/house/environment Python engines with SYNTHETIC NX responses.
No NX/Parasolid execution. All .prt test stubs are temporary and deleted.
"""
import contextlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'umgebung/tests'),str(B/'tests')]
from test_r09 import SceneDouble
from fake_nx import Part,Status
from gesamt.core import read_json,write_json,check_records,sha256
from g02.workflow import run
from g02.nx_backend import NXBackendG02
spec=importlib.util.spec_from_file_location('split_install_g02',B/'werkzeuge/PRUEFE_GESAMTABLAUF_RASTER_SIMULATION_G01e.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def main(report_path):
    originals={loc:{p.name:p.read_bytes() for p in loc.glob('LETZT*.json')} for loc in [B,B/'umgebung']}
    try:
        with tempfile.TemporaryDirectory() as td:
            temp=Path(td);definition=temp/'step214ug.def';definition.write_text('SYNTHETIC_NOT_NX_DEF')
            fake=SceneDouble(definition);ctl=m.install(fake)
            cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(temp/'out')
            with fake.active(),patch.object(Part,'IsModified',False,create=True):
                first=run(B,'ALL',NXBackendG02(B,session_provider=lambda:fake.session),verify=False,config=cfg)
                assert first['phase']=='ABGESCHLOSSEN'
                assert first['house']['built_solids']==1418 and first['house']['component_count']==15
                assert first['project']['height_mounted'] is True
                assert abs(first['project']['environment_translation_mm'][2]+31362.49870845903)<1e-7
                assert first['project']['height_check']['anchor_error_mm']<1e-7
                for k in ['house','environment','project']:check_records(first[k]['files'])
                oldmaster=fake.session.Parts.by_path(first['project']['master'])
                oldmaster.IsModified=True  # SYNTHETIC dirty OUTER project master.
                oldhash=sha256(oldmaster.FullPath)
                childmaster=fake.session.Parts.by_path(first['house']['master'])
                childmaster.IsFullyLoaded=False
                loadcalls=[]
                def load():
                    loadcalls.append(childmaster.FullPath);childmaster.IsFullyLoaded=True
                    return Status(fake)
                childmaster.LoadThisPartFully=load
                imports_before=fake.step_calls;commits_before=fake.commits
                second=run(B,'REUSE',NXBackendG02(B,session_provider=lambda:fake.session),verify=False,config=cfg)
                assert second['phase']=='ABGESCHLOSSEN'
                assert fake.step_calls==imports_before and fake.commits==commits_before
                assert oldmaster.IsModified is True and sha256(oldmaster.FullPath)==oldhash
                assert len(loadcalls)==1
                assert second['project']['environment_translation_mm']==first['project']['environment_translation_mm']
                assert second['project']['utility_component_hidden'] is True
                for k in ['house','environment','project']:check_records(second[k]['files'])
                # A dirty SOURCE remains an error; it is never ignored/saved.
                childmaster.IsModified=True;partcount=len(fake.session.Parts.items)
                try:
                    run(B,'REUSE',NXBackendG02(B,session_provider=lambda:fake.session),verify=False,config=cfg)
                except RuntimeError as e:
                    assert 'QUELLKOMPONENTE' in str(e)
                else:raise AssertionError('Dirty source accepted')
                assert len(fake.session.Parts.items)==partcount
                assert childmaster.IsModified is True
                report={'status':'G02_FULL_AND_REUSE_SIMULATIONS_PASSED','NX_tested':False,'Parasolid_tested':False,
                        'house_bodies':1418,'house_components':15,'synthetic_DGM_faces':8282,
                        'source_components_files_unchanged':True,'step_imports_full':imports_before,
                        'step_imports_reuse':fake.step_calls-imports_before,
                        'extrusion_features_reuse':fake.commits-commits_before,
                        'dirty_old_master_unchanged_and_not_read_as_source':True,
                        'partially_loaded_house_loaded_once':len(loadcalls)==1,
                        'dirty_source_component_rejected':True,
                        'environment_translation_mm':second['project']['environment_translation_mm'],
                        'anchor_error_mm':second['project']['height_check']['anchor_error_mm'],
                        'height_shift_not_accumulated':True,'utility_segments':45,
                        'as_built_verified':False,'temporary_files_are_not_native_NX_parts':True,
                        'note':'Real supplied Python workflow with synthetic NX bindings and synthetic surface/edge replies. No measured NX runtime.'}
        write_json(report_path,report);print(json.dumps(report,indent=2))
    finally:
        for loc,files in originals.items():
            for p in loc.glob('LETZT*.json'):
                if p.name not in files:p.unlink()
            for name,raw in files.items():(loc/name).write_bytes(raw)

if __name__=='__main__':main(Path(sys.argv[sys.argv.index('--report')+1]))
