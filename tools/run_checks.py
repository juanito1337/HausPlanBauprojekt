"""Repository checks; --full additionally runs the unmodified G02 suite.

Not an NX journal. --cad adds optional Open-CASCADE checks, not an NX test.
No pip installs or source manifest changes are performed.
"""
from __future__ import annotations
import argparse
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).absolute().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--cad', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error('Python >= 3.10 required')
    if args.cad and not args.full:
        parser.error('--cad requires --full')
    out = ROOT / 'reports/local' / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    jobs = [('repository_integrity', [sys.executable, str(ROOT/'tools/verify_repo.py')]),
            ('repository_tests', [sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT/'tests'), '-v'])]
    if args.full:
        command = [sys.executable, str(ROOT/'projects/g02/werkzeuge/PRUEFE_G02_OFFLINE.py'),
                   '--out', str(out/'g02')]
        if args.cad:
            command.append('--cad')
        jobs.append(('g02_offline', command))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    summary = {'checks': [], 'NX_run_performed': False, 'cad_requested': args.cad,
               'full_G02_suite_requested': args.full}
    for name, command in jobs:
        print('RUN ' + name, flush=True)
        log = out/(name+'.txt')
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        summary['checks'].append({'name': name, 'returncode': proc.returncode, 'log': log.name})
        if proc.returncode:
            print(log.read_text(encoding='utf-8', errors='replace')[-12000:])
            break
    summary['status'] = 'PASS' if all(c['returncode'] == 0 for c in summary['checks']) else 'FAIL'
    (out/'RESULT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(summary['status'] + ': ' + str(out))
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
