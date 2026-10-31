# -*- coding: utf-8 -*-
"""Offline: no NX runtime, no CAD export. python VALIDATE_DATA.py --tests."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest


def main():
    base=Path(os.path.abspath(__file__)).parent
    sys.path.insert(0,str(base/'src'))
    from haus2406_r03.haus_runtime import read_json,atomic_json
    from haus2406_r03.haus_geometry import validate,Parameters
    from haus2406_r03.haus_compile import compile_house
    from haus2406_r03.haus_audit import audit_compiled
    from haus2406_r03.haus_construction import source_plausibility
    from haus2406_r03.haus_consistency import consistency_report
    from haus2406_r03.haus_profile import validate_compiled_profiles
    parser=argparse.ArgumentParser(description='R06-Pruefung ohne NX/Parasolid. Keine Tragwerksbemessung.')
    parser.add_argument('--tests',action='store_true',help='Alle Offline- und Simulationstests ausfuehren.')
    args=parser.parse_args()
    data=read_json(base/'data/haus.json')
    valid=validate(data)
    if valid['errors']:raise ValueError('; '.join(valid['errors']))
    compiled=compile_house(data,True);params=Parameters(data['parameters'])
    audit=audit_compiled(data,compiled);profiles=validate_compiled_profiles(compiled,params)
    construction=source_plausibility(data,compiled)
    consistency=consistency_report(data,compiled,audit)
    reports=base/'berichte';reports.mkdir(exist_ok=True)
    for name,value in [('BAUAUFTRAG_R06.json',compiled),('NUMERISCHE_PRUEFUNG_R06.json',audit),
      ('KONSTRUKTIONSPRUEFUNG_R06.json',construction),('PROFILPRUEFUNG_R06.json',profiles),('KONSISTENZPRUEFUNG_R06.json',consistency)]:
        atomic_json(reports/name,value)
    print('Geplante Koerper:',compiled['planned_solids'])
    print('Ungueltige numerische Volumen:',len(audit['invalid_solids']))
    print('Offene Ueberschneidungspaare:',audit['collision_count'])
    print('Konstruktiv fuer Dachumbauten verifiziert: NEIN')
    print('Kein NX-Lauf. Siehe PRUEFBERICHT_R06.html.')
    print('Blockierte Oeffnungen:',consistency['opening_clearance']['blocked_count'])
    print('Quellen-/Referenzfehler:',len(consistency['logical_errors']))
    if audit['invalid_solids'] or consistency['logical_errors']:return 1
    if args.tests:
        suite=unittest.defaultTestLoader.discover(str(base/'tests'))
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
