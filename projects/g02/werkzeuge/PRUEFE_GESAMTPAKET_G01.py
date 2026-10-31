# -*- coding: utf-8 -*-
"""Offline only, not an NX journal. --cad requires local OCP/cadquery/numpy.
Executes genuine Python tests, simulated NX bindings, optional independent CAD checks.
"""
import argparse
import ast
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

B=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(B))
from gesamt.core import read_json,write_json,verify_package


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True,help='New output folder; must not exist yet.')
    parser.add_argument('--cad',action='store_true')
    args=parser.parse_args();out=Path(args.out).absolute();out.mkdir(parents=True,exist_ok=False)
    result={'patch':'MAIN01-A01-G01e-RASTERFLAECHENPRUEFUNG','tested_at':datetime.datetime.now().isoformat(),
            'NX_tested':False,'Parasolid_tested':False,'all_model_defects_fixed':False,
            'package_check':verify_package(B),'syntax_files':0,'checks':[]}
    for p in B.rglob('*.py'):
        if '__pycache__' not in p.parts and 'ausgabe' not in p.parts:
            ast.parse(p.read_text(encoding='utf-8-sig'),filename=str(p));result['syntax_files']+=1
    jobs=[('haus_main01_a01',[sys.executable,str(B/'haus/werkzeuge/PRUEFE_MAIN01_OFFLINE.py')]),
          ('umgebung_r11a',[sys.executable,str(B/'umgebung/werkzeuge/PRUEFE_PROGRAMM_OFFLINE_R09.py')]),
          ('gesamt_g01',[sys.executable,str(B/'tests/test_gesamt.py')]),
          ('g01a_terrain_audit',[sys.executable,str(B/'tests/test_terrain_audit_g01a.py')]),
          ('g01b_uv_pruefung',[sys.executable,str(B/'tests/test_terrain_uv_g01b.py')]),
          ('g01c_boundary_chains',[sys.executable,str(B/'tests/test_terrain_boundary_g01c.py')]),
          ('g01d_exact_boundary_delivery',[sys.executable,str(B/'tests/test_terrain_export_g01d.py')]),
          ('g01e_raster_patches',[sys.executable,str(B/'tests/test_terrain_patches_g01e.py')]),
          ('dgm_diagnose',[sys.executable,str(B/'diagnose/DGM_Punkt85/TESTE_DIAGNOSE_OFFLINE.py')]),
          ('gesamt_simulation',[sys.executable,str(B/'werkzeuge/PRUEFE_GESAMTABLAUF_SIMULATION.py'),'--report',str(out/'SIMULATION_G01.json')]),
          ('gesamt_raster_simulation',[sys.executable,str(B/'werkzeuge/PRUEFE_GESAMTABLAUF_RASTER_SIMULATION_G01e.py'),'--report',str(out/'SIMULATION_RASTER_G01e.json')])]
    if args.cad:
        jobs.extend([
            ('cad_dgm_raster_patches',[sys.executable,str(B/'werkzeuge/PRUEFE_DGM_RASTERFLAECHEN_OCCT_G01e.py'),'--out',str(out/'CAD_DGM_RASTERFLAECHEN')]),
            ('cad_haus',[sys.executable,str(B/'haus/werkzeuge/PRUEFE_HAUS_OCCT_OFFLINE.py'),'--report',str(out/'CAD_HAUS_G01.json')]),
            ('cad_umgebung',[sys.executable,str(B/'umgebung/werkzeuge/PRUEFE_STEP_OFFLINE_R09.py'),'--report',str(out/'CAD_UMGEBUNG_G01.json')]),
            ('cad_dgm_uv',[sys.executable,str(B/'werkzeuge/PRUEFE_DGM_UV_OCCT.py'),'--out',str(out/'CAD_DGM_UV')]),
            ('cad_dgm_exact_line_boundary',[sys.executable,str(B/'werkzeuge/PRUEFE_DGM_LINIENRAND_G01d.py'),'--out',str(out/'CAD_DGM_LINIENRAND')]),
            ('cad_dgm_segmented_boundary',[sys.executable,str(B/'werkzeuge/PRUEFE_DGM_SEGMENTRAND_OCCT.py'),'--out',str(out/'CAD_DGM_SEGMENTRAND')])])
    for label,command in jobs:
        print('PRUEFE '+label,flush=True)
        log=out/(label+'.txt')
        with log.open('w',encoding='utf-8') as stream:
            completed=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
        txt=log.read_text(encoding='utf-8',errors='replace')
        counts=[int(n) for n in re.findall(r'Ran (\d+) tests?',txt)]
        result['checks'].append({'name':label,'returncode':completed.returncode,
                                'unittest_count':sum(counts),'log':log.name})
        print(label,'PASS' if completed.returncode==0 else 'FAIL',flush=True)
    result['package_check_at_end']=verify_package(B)
    result['test_count']=sum(r['unittest_count'] for r in result['checks'])
    result['all_requested_checks_passed']=all(r['returncode']==0 for r in result['checks'])
    result['limits']=['No NX execution; simulated bindings do not validate translator, kernel or actual run time.',
                     'G01e adds split-raster-face verification. The G01d STEP is unchanged. Existing 0.25 mm limits remain. No NX execution of the new verifier.',
                     'House/terrain vertical connection, structural calculations and utility depths still open.']
    write_json(out/'ERGEBNIS_G01.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['all_requested_checks_passed'] else 1

if __name__=='__main__':raise SystemExit(main())
