# -*- coding: utf-8 -*-
"""Offline aggregate verification; NOT an NX journal.
--cad runs real Open-CASCADE source checks in addition to Python simulations.
No NX runtime is used or claimed by this tool. Use a new output directory.
"""
import argparse
import ast
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys

BASE = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(BASE))
from g02 import PATCH
from g02.workflow import verify_delivery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--cad', action='store_true')
    args = parser.parse_args()
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    result = {'patch': PATCH, 'started_at': datetime.datetime.now().isoformat(),
              'NX_tested': False, 'Parasolid_tested': False,
              'as_built_verified': False, 'site_alignment_surveyed': False,
              'package_check': verify_delivery(BASE), 'checks': [],
              'python_310_syntax_files': 0,
              'legacy_suite_vertical_notes_describe_old_source_workflow': True}
    # Parsing targets the Python 3.10 grammar used by the supplied NX reports.
    for path in BASE.rglob('*.py'):
        if '__pycache__' not in path.parts and 'ausgabe' not in path.parts:
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path), feature_version=(3, 10))
            result['python_310_syntax_files'] += 1
    baseline_cmd = [sys.executable, str(BASE / 'werkzeuge/PRUEFE_GESAMTPAKET_G01.py'),
                    '--out', str(out / 'basis')]
    if args.cad:
        baseline_cmd.append('--cad')
    jobs = [('bisherige_630_pruefungen', baseline_cmd),
            ('g02_hoehen_und_speicherzustand', [sys.executable, '-m', 'unittest', 'discover',
                 '-s', str(BASE / 'tests_g02'), '-p', 'test_*.py', '-v']),
            ('g02_vollstaendiger_workflow_simulation', [sys.executable,
                 str(BASE / 'werkzeuge/PRUEFE_G02_ABLAUF_SIMULATION.py'),
                 '--report', str(out / 'SIMULATION_G02.json')])]
    if args.cad:
        jobs.append(('g02_reale_cad_hoehenpruefung', [sys.executable,
            str(BASE / 'werkzeuge/PRUEFE_HOEHEN_G02_OCCT.py'),
            '--report', str(out / 'CAD_HOEHEN_G02.json')]))
    env = os.environ.copy()
    env.setdefault('OPENBLAS_NUM_THREADS', '1')
    env.setdefault('OMP_NUM_THREADS', '1')
    for name, cmd in jobs:
        print('PRUEFE ' + name, flush=True)
        log = out / (name + '.txt')
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT, cwd=str(BASE), env=env)
        text = log.read_text(encoding='utf-8', errors='replace')
        count = sum(int(x) for x in re.findall(r'Ran (\d+) tests?', text))
        if name == 'bisherige_630_pruefungen':
            bfile = out / 'basis/ERGEBNIS_G01.json'
            if bfile.is_file():
                bresult = json.loads(bfile.read_text(encoding='utf-8'))
                count = bresult.get('test_count', 0)
                result['baseline_all_checks_passed'] = bresult.get('all_requested_checks_passed')
        row = {'name': name, 'returncode': proc.returncode, 'unittest_count': count, 'log': log.name}
        result['checks'].append(row)
        print(name + (' PASS' if proc.returncode == 0 else ' FAIL'), flush=True)
    result['package_check_at_end'] = verify_delivery(BASE)
    result['test_count'] = sum(row['unittest_count'] for row in result['checks'])
    result['all_requested_checks_passed'] = all(row['returncode'] == 0 for row in result['checks'])
    result['finished_at'] = datetime.datetime.now().isoformat()
    result['limits'] = [
        'Kein NX-/Parasolid-Lauf: Simulationen pruefen nicht die reale NX-Schnittstelle oder Laufzeit.',
        'Der Liefer-Hoehenanschluss ist eine unvermessenene Planannahme, keine bestaetigte NHN-Hoehe.',
        'Quellkoerper bleiben unveraendert; nur die neue uebergeordnete Baugruppe traegt den Hoehenversatz.',
        'Zehn bekannte Hausueberschneidungen, zwei teilweise blockierte Oeffnungen, Statik und Leitungstiefen bleiben offen.'
    ]
    (out / 'ERGEBNIS_G02.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result['all_requested_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
