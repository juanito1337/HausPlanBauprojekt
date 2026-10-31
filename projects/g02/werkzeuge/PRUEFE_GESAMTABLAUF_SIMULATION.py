# -*- coding: utf-8 -*-
"""Integration using the real Python engines with simulated NX responses.
No native NX geometry is created. Temporary stub .prt files are deleted afterwards.
"""
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'umgebung/tests'),str(B/'tests')]
from test_r09 import SceneDouble
from uv_double import install_uv_double
from gesamt.core import read_json,write_json,run_project,check_records
from gesamt.nx_backend import NXBackend


def run(report_path):
    originals={}
    locations=[B,B/'umgebung']
    for location in locations:
        originals[location]={p.name:p.read_bytes() for p in location.glob('LETZT*.json')}
    try:
        with tempfile.TemporaryDirectory() as t:
            temp=Path(t);definition=temp/'step214ug.def';definition.write_text('TESTDOUBLE_ONLY_NOT_NX_DEF')
            fake=SceneDouble(definition)
            uv_control=install_uv_double(fake)
            uv_control.edge_ranges=[(side,i/n,(i+1)/n) for side,n in enumerate((64,64,79,78)) for i in range(n)]
            cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(temp/'output')
            backend=NXBackend(B,session_provider=lambda:fake.session)
            with fake.active():
                result=run_project(B,'ALL',cfg,backend,verify=False)
            assert result['phase']=='ABGESCHLOSSEN'
            assert result['house']['revision']=='MAIN01-A01'
            assert result['house']['built_solids']==1418 and result['house']['component_count']==15
            assert result['environment']['surface_validation']=='BASIS'
            assert result['environment']['new_house_built_by_environment'] is False
            assert result['environment']['DGM_POINT85_ROOT_CAUSE_FIXED'] is False
            assert result['project']['utility_segments']==45 and result['project']['utility_parts']==4
            assert result['project']['confirmed_utility_depths']==0
            assert result['project']['environment_translation_mm']==[0,0,0]
            assert result['project']['height_connection_confirmed_by_user'] is False
            assert len(result['project']['component_checks'])==3
            assert len(result['project']['utility_reference_checks'])==4
            assert check_records(result['house']['files'])>15
            assert check_records(result['environment']['files'])>6
            assert check_records(result['project']['files'])==6
            assert fake.step_calls==6  # smoke + DGM/V01/V02/V03/V05; not ten groups
            assert fake.mass_calls==0 and fake.face_measure_calls==0
            assert uv_control.evaluations==16753 and uv_control.edge_queries==1591
            master=fake.session.Parts.by_path(result['project']['master'])
            children=master.ComponentAssembly.RootComponent.GetChildren()
            assert children[-1].blanked is True
            assert children[0].Prototype.FullPath==result['house']['master']
            assert children[1].Prototype.FullPath==result['environment']['master']
            report={'status':'PYTHON_GESAMTABLAUF_MIT_NX_TESTDOUBLE_BESTANDEN','NX_tested':False,
                'house_revision':'MAIN01-A01','house_bodies':1418,'house_components':15,
                'environment_groups':['DGM','V01','V02','V03','V05'],'simulated_step_imports':fake.step_calls,
                'simulated_DGM_boundary_edges':285,'simulated_uv_evaluations':uv_control.evaluations,'simulated_boundary_queries':uv_control.edge_queries,'simulated_point_distance_calls':fake.distance_calls,'real_surface_measurements':0,
                'project_children':3,'utility_groups':4,'utility_line_segments':45,
                'utility_parent_hidden':True,'height_offset_not_guessed':True,'DGM_point85_fixed':False,
                'source_files_not_resaved':True,'temporary_stub_files_deleted_after_run':True,
                'note':'Real delivered Python engines + simulated NX bindings, synthetic bilinear UV evaluator and edge distances. No STEP translator/Parasolid execution. No as-built approval.'}
        write_json(report_path,report)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return report
    finally:
        # Restore existing test/user pointers; do not leave pointers to deleted stub parts.
        for location in locations:
            for p in location.glob('LETZT*.json'):
                if p.name not in originals[location]:p.unlink()
            for name,content in originals[location].items():
                (location/name).write_bytes(content)

if __name__=='__main__':
    out=Path(sys.argv[sys.argv.index('--report')+1]) if '--report' in sys.argv else B/'berichte/SIMULATION_G01.json'
    run(out)
