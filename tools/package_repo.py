"""Package Git-indexed files only. Refuses dirty/untracked non-ignored files.

Run after committing/reviewing changes. The output must be outside this repo.
It is a working-tree export, not a backup of local_data or native NX output.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from tools.repo_support import build_archive


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args=p.parse_args()
    try:
        state=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT)
        if state.strip():
            raise ValueError('Working tree nicht sauber. Änderungen prüfen und committen; nichts automatisch verworfen.')
        raw=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT)
        names=[s.decode('utf-8') for s in raw.split(b'\0') if s]
        if not names:
            raise ValueError('Keine versionierten Dateien. Zuerst Repository initialisieren und committen.')
        result=build_archive(ROOT,names,args.output,'HausPlanBauprojekt')
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print('Verpackung abgebrochen: '+str(error),file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
