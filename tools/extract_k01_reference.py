"""Extract data from the retained K01 preview, without executing its JavaScript.

This recovers reference data only, not the missing NX code or CAD assets.
Writes a new target exclusively; never overwrites the original HTML or prior result.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(ROOT))
from tools.repo_support import digest, extract_json_assignment


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    args=p.parse_args()
    source=ROOT/'renovierung/k01_unterlagen/VORSCHAU_BAUABLAUF_K01.html'
    data=extract_json_assignment(source.read_text(encoding='utf-8'))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2)
        stream.write('\n')
    print(json.dumps({'source':str(source.relative_to(ROOT)),'source_sha256':digest(source),
                      'output':str(args.output),'output_sha256':digest(args.output),
                      'javascript_executed':False,'nx_code_recovered':False,'CAD_assets_recovered':False},
                     indent=2,ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())
