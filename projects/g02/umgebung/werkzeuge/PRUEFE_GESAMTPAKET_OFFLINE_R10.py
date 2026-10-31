# -*- coding: utf-8 -*-
"""Offline-Gesamtpruefung, NICHT als NX-Journal starten.
Ohne --cad: Python-Standardbibliothek. --cad: zusaetzlich cadquery/OCP und numpy.
Tests erzeugen nur temporaere simulierte Parts, keine echten NX-Dateien.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

BASE = Path(os.path.abspath(__file__)).parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cad', action='store_true', help='Echte STEP-Dateien mit Open CASCADE nachpruefen.')
    parser.add_argument('--out', default='', help='Neuer Protokollordner; darf noch nicht existieren.')
    args = parser.parse_args()
    out = Path(args.out) if args.out else BASE/'berichte'/('OFFLINE_R10_'+uuid.uuid4().hex[:8])
    out.mkdir(parents=True, exist_ok=False)
    jobs = [('haus', [sys.executable, str(BASE/'basis/Haus_R06/VALIDATE_DATA.py'), '--tests']),
            ('integration', [sys.executable, str(BASE/'werkzeuge/PRUEFE_PROGRAMM_OFFLINE_R09.py')]),
            ('video', [sys.executable, str(BASE/'video/tests/test_video_r10.py')])]
    if args.cad:
        jobs += [('videokoerper', [sys.executable, str(BASE/'werkzeuge/PRUEFE_VIDEOKOERPER_OCCT_R10.py'), '--report', str(out/'CAD_VIDEO_R10.json')])]
        jobs += [('step', [sys.executable, str(BASE/'werkzeuge/PRUEFE_STEP_OFFLINE_R09.py'), '--report', str(out/'STEP_RUECKIMPORT.json')]),
                 ('flaechenteilung', [sys.executable, str(BASE/'werkzeuge/PRUEFE_FLAECHENTEILUNG_OCCT_R09b.py')]),
                 ('dgm_integration', [sys.executable, str(BASE/'werkzeuge/PRUEFE_DGM_INTEGRATION_OFFLINE_R09e.py'), '--report', str(out/'DGM_QUELLINTEGRATION.json')])]
    result = {'patch':'R10-VIDEO-BESTANDSABGLEICH', 'NX_tested':False, 'checks':[],
              'date':datetime.datetime.now().isoformat(), 'cad_requested':args.cad}
    for label, cmd in jobs:
        print('Pruefe '+label, flush=True)
        log = out/(label+'.txt')
        with log.open('w', encoding='utf-8') as stream:
            proc = subprocess.run(cmd, stdout=stream, stderr=subprocess.STDOUT)
        txt = log.read_text(encoding='utf-8', errors='replace')
        match = re.search(r'Ran (\d+) tests?', txt)
        result['checks'].append({'name':label,'exit_code':proc.returncode,'test_count':int(match[1]) if match else None,'log':log.name})
    result['all_requested_checks_passed'] = all(r['exit_code']==0 for r in result['checks'])
    result['test_count'] = sum(r['test_count'] or 0 for r in result['checks'])
    (out/'ERGEBNIS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2), encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if result['all_requested_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
