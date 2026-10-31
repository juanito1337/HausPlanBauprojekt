"""Check the imported source snapshots and Python-3.10 syntax, without NX.

The historical import manifest is immutable evidence. A changed baseline is an
explicit failure, not a reason to rewrite this manifest automatically.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).absolute().parents[1]
sys.path.insert(0, str(ROOT))
from tools.repo_support import check_files, check_python_syntax, member_path, extract_json_assignment


def verify(root: Path = ROOT) -> dict:
    root = Path(root).absolute()
    lock = json.loads((root / 'provenance/IMPORT_MANIFEST.json').read_text(encoding='utf-8'))
    if lock.get('schema') != 'HAUSPLAN_IMPORT_V1':
        raise ValueError('Unbekanntes Importregister')
    sources = []
    errors = []
    for source in lock['sources']:
        target = member_path(root, source['target'])
        issues = check_files(target, source['files'])
        sources.append({'source': source['archive_name'], 'target': source['target'],
                        'checked_files': len(source['files']), 'problems': issues})
        errors.extend(issues)
    additional = json.loads((root/'provenance/ADDITIONAL_FILES_SHA256.json').read_text(encoding='utf-8'))
    extra_errors = check_files(root, additional['files'])
    errors.extend(extra_errors)
    recovered = json.loads((root/'renovierung/recovered/RENOVIERUNGSPLAN_AUS_VORSCHAU.json').read_text(encoding='utf-8'))
    embedded = extract_json_assignment((root/'renovierung/k01_unterlagen/VORSCHAU_BAUABLAUF_K01.html').read_text(encoding='utf-8'))
    if recovered != embedded:
        errors.append({'kind': 'recovered_K01_data_mismatch'})
    names = [p.relative_to(root).as_posix() for p in root.rglob('*.py')
             if not any(part.startswith('.venv') or part in {'.git', '__pycache__', 'venv', 'local_data', 'ausgabe',
                                 'fehlerberichte', 'local'} for part in p.relative_to(root).parts)]
    syntax = check_python_syntax(root, names)
    errors.extend(syntax)
    required = ['README.md', 'AGENTS.md', 'CODEX_START.md', '.gitignore', '.gitattributes',
                'docs/PROJEKTSTAND.md', 'docs/ANFORDERUNGEN_RENOVIERUNG.md',
                'renovierung/README.md']
    missing = [name for name in required if not (root / name).is_file()]
    errors.extend({'file': name, 'kind': 'missing_repo_file'} for name in missing)
    return {'status': 'PASS' if not errors else 'FAIL', 'sources': sources,
            'python_310_syntax_files': len(names), 'syntax_errors': syntax, 'additional_file_errors': extra_errors,
            'K01_recovered_data_matches_preview': recovered == embedded,
            'missing_repo_files': missing, 'NX_run_performed': False,
            'renovation_implementation_available': False,
            'warning': 'K01 ist nur als historische Unterlage erhalten. Keine Ausführungs-/Tragwerksfreigabe.'}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    try:
        result = verify()
    except Exception as error:
        result = {'status': 'FAIL', 'error': str(error), 'NX_run_performed': False}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + '\n', encoding='utf-8')
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
