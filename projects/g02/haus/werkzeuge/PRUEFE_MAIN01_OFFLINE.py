# -*- coding: utf-8 -*-
"""Offline only: sources, program logic and optional independent CAD. Not a NX journal."""
import argparse,json,subprocess,sys,tempfile
from pathlib import Path
B=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(B/'src'))
from haus2406_r03.haus_runtime import read_json
from main01.runtime import verify_package

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--cad',action='store_true');args=parser.parse_args()
 print('MAIN01-A01 OFFLINE: KEIN NX-LAUF / KEINE STATIK / KEINE BESTANDSFREIGABE',flush=True)
 registry=B/'PAKETDATEIEN_SHA256.json'
 if registry.exists():print('PAKETPRUEFUNG:',json.dumps(verify_package(B),ensure_ascii=False),flush=True)
 else:raise FileNotFoundError('PAKETDATEIEN_SHA256.json fehlt; gesamtes Paket verwenden.')
 subprocess.run([sys.executable,str(B/'tests/test_main01.py')],check=True)
 subprocess.run([sys.executable,str(B/'tests/test_roof_attachment.py')],check=True)
 if args.cad:
  with tempfile.TemporaryDirectory() as t:
   report=Path(t)/'CAD.json'
   subprocess.run([sys.executable,str(B/'werkzeuge/PRUEFE_HAUS_OCCT_OFFLINE.py'),'--report',str(report)],check=True)
   r=read_json(report);print('CAD:',r['status'],r['checked_bodies'],'Koerper; nur Rechenmodell. Keine echte .prt-Datei erzeugt.',flush=True)
 print('MAIN01 OFFLINEPRUEFUNG BESTANDEN. 10 bekannte Kollisionen und 2 blockierte Oeffnungen bleiben offen.',flush=True)
if __name__=='__main__':main()
