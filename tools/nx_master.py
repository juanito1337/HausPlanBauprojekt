"""Build/check the integrated M01 main assembly with actual NX evidence."""
import argparse
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from renovierung.m01.runner import build_master,check_master


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('build','check'))
    parser.add_argument('--nx-root',type=Path,default=Path('C:/Siemens/NX2406'))
    parser.add_argument('--accept-model-assumptions',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='build':
            print('PASS M01: '+str(build_master(args.nx_root,args.accept_model_assumptions)))
        else:
            errors=check_master()
            if errors: raise ValueError('; '.join(errors))
            print('PASS M01: native main assembly evidence matches current sources (no new NX run)')
        return 0
    except Exception as error:
        print('FAIL M01: '+str(error));return 1


if __name__=='__main__': raise SystemExit(main())
