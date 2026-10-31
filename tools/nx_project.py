"""Build in real NX and validate versioned native evidence. No simulated NX."""
from __future__ import annotations
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.repo_support import digest, member_path


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def source_fingerprint() -> str:
    base = ROOT / 'projects/g02'
    registry = read(base / 'PAKETDATEIEN_SHA256.json')
    files = {f'projects/g02/{name}': digest(member_path(base, name))
             for name in sorted(set(registry['files']) | {'PAKETDATEIEN_SHA256.json'})}
    for name in ('nx_project.py', 'nx_build_journal.py', 'nx_verify_journal.py', 'repo_support.py'):
        files['tools/' + name] = digest(ROOT / 'tools' / name)
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode('utf-8')).hexdigest()


def validate_evidence(directory: Path, build: dict, verify: dict, fingerprint: str) -> list[str]:
    errors = []
    if build.get('schema') != 'HAUSPLAN_NX_BUILD_V1' or build.get('status') != 'PASS':
        errors.append('Build is not complete')
    if build.get('native_NX_run_completed') is not True:
        errors.append('Real NX build evidence missing')
    if verify.get('schema') != 'HAUSPLAN_NX_VERIFY_V1' or verify.get('status') != 'PASS':
        errors.append('NX verification is not complete')
    if any(report.get('source_fingerprint') != fingerprint for report in (build, verify)):
        errors.append('Evidence is stale: source/generator fingerprint changed')
    names = []
    for record in build.get('parts', []):
        try:
            name = record['path']
            path = member_path(directory, name)
            if path.suffix.lower() != '.prt' or not path.is_file():
                raise ValueError('Missing native part: ' + name)
            if digest(path) != record['sha256'] or path.stat().st_size != record['bytes']:
                raise ValueError('Changed native part: ' + name)
            names.append(name)
        except (KeyError, TypeError, ValueError, OSError) as error:
            errors.append(str(error))
    if not names or len(set(n.casefold() for n in names)) != len(names):
        errors.append('Empty or case-colliding native manifest')
    if build.get('master') not in names:
        errors.append('Master is not in native manifest')
    actual = {p.relative_to(directory).as_posix() for p in directory.rglob('*')
              if p.is_file() and p.suffix.lower() == '.prt'}
    if actual != set(names):
        errors.append('Native files differ from manifest')
    for phase in ('reopen', 'relocated'):
        result = verify.get(phase, {})
        if result.get('status') != 'PASS' or set(result.get('parts', [])) != set(names):
            errors.append('Missing/incomplete NX verification: ' + phase)
    return errors


def run_journal(nx_root: Path, journal: str, request: dict, scratch: Path, label: str) -> dict:
    request_path = scratch / (label + '_request.json')
    report_path = scratch / (label + '_result.json')
    write(request_path, dict(request, report=str(report_path)))
    env = dict(os.environ, HAUSPLAN_NX_REQUEST=str(request_path), PYTHONDONTWRITEBYTECODE='1')
    print('NX ' + label + ': ' + str(scratch / (label + '.log')), flush=True)
    with (scratch / (label + '.log')).open('w', encoding='utf-8') as stream:
        proc = subprocess.run([str(nx_root / 'NXBIN/run_journal.exe'), str(ROOT / 'tools' / journal)],
                              cwd=scratch, env=env, stdout=stream, stderr=subprocess.STDOUT)
    if not report_path.is_file():
        raise RuntimeError(f'NX {label} returned {proc.returncode}, no result; see log')
    result = read(report_path)
    if proc.returncode != 0 or result.get('status') != 'PASS':
        raise RuntimeError(f'NX {label} failed: {result.get("error", proc.returncode)}; see {report_path}')
    return result


def generation_root(temp_root: Path) -> Path:
    target = temp_root.resolve() / ('HPNX_' + uuid.uuid4().hex[:8])
    if len(str(target)) > 95:
        raise ValueError('Temporary NX root too long; choose a shorter TEMP directory')
    target.mkdir(exist_ok=False)
    return target


def build_native(nx_root: Path, accept: bool) -> Path:
    if not accept:
        raise ValueError('Explicit --accept-model-assumptions required for the documented G02 study model')
    stamp = datetime.datetime.now().astimezone().strftime('%Y%m%dT%H%M%S') + '_' + uuid.uuid4().hex[:6]
    scratch = ROOT / 'reports/local/nx' / stamp
    destination = ROOT / 'cad/nx' / stamp
    current = ROOT / 'cad/nx/CURRENT.json'
    attempt = ROOT / 'cad/nx/LAST_ATTEMPT.json'
    attempt.parent.mkdir(parents=True, exist_ok=True)
    fingerprint = None
    write(attempt, {'status': 'RUNNING', 'directory': stamp, 'source_fingerprint': fingerprint})
    try:
        if not (nx_root / 'NXBIN/run_journal.exe').is_file():
            raise FileNotFoundError('NX run_journal.exe missing: ' + str(nx_root))
        scratch.mkdir(parents=True, exist_ok=False)
        destination.mkdir(parents=True, exist_ok=False)
        fingerprint = source_fingerprint()
        native_output = generation_root(Path(tempfile.gettempdir()))
        source = ROOT / 'projects/g02'
        snapshot = scratch / 'source'
        registry = read(source / 'PAKETDATEIEN_SHA256.json')
        for name in sorted(set(registry['files']) | {'PAKETDATEIEN_SHA256.json'}):
            target = member_path(snapshot, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member_path(source, name), target)
        version_env = dict(os.environ, HAUSPLAN_NX_EXE=str(nx_root / 'NXBIN/ugraf.exe'))
        version = subprocess.check_output(['powershell', '-NoProfile', '-Command',
            '(Get-Item -LiteralPath $env:HAUSPLAN_NX_EXE).VersionInfo.ProductVersion'],
            env=version_env, text=True).strip()
        request = {'source': str(snapshot), 'output_root': str(native_output),
                   'accept_model_assumptions': accept, 'nx_version': version,
                   'source_fingerprint': fingerprint}
        result = run_journal(nx_root, 'nx_build_journal.py', request, scratch, 'build')
        run_root = Path(result['output_directory'])
        parts = []
        for record in result['parts']:
            src = member_path(run_root, record['path'])
            if digest(src) != record['sha256']:
                raise ValueError('Generated native file changed: ' + record['path'])
            dst = member_path(destination, record['path'])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            parts.append(record)
        build = {k: result[k] for k in ('schema', 'status', 'native_NX_run_completed', 'source_fingerprint',
                  'nx_version', 'completed_at', 'master', 'parts', 'house_bodies', 'house_components',
                  'height_translation_mm', 'surface_validation')}
        build['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        build['source_commit_is_context_fingerprint_is_authoritative'] = True
        write(destination / 'BUILD.json', build)
        reopen_request = {'directory': str(destination), 'master': build['master'], 'parts': parts}
        reopen = run_journal(nx_root, 'nx_verify_journal.py', reopen_request, scratch, 'reopen')
        relocated = scratch / 'relocated'
        for record in parts:
            target = member_path(relocated, record['path'])
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(member_path(destination, record['path']), target)
        moved = run_journal(nx_root, 'nx_verify_journal.py', dict(reopen_request, directory=str(relocated)), scratch, 'relocated')
        verification = {'schema': 'HAUSPLAN_NX_VERIFY_V1', 'status': 'PASS',
                        'source_fingerprint': fingerprint, 'nx_version': version,
                        'completed_at': datetime.datetime.now().astimezone().isoformat(),
                        'reopen': reopen, 'relocated': moved}
        write(destination / 'VERIFY.json', verification)
        errors = validate_evidence(destination, build, verification, source_fingerprint())
        if errors:
            raise ValueError('; '.join(errors))
        write(current, {'directory': stamp, 'master': stamp + '/' + build['master']})
        write(attempt, {'status': 'PASS', 'directory': stamp, 'source_fingerprint': fingerprint})
        return destination
    except Exception as error:
        write(attempt, {'status': 'FAIL', 'directory': stamp, 'source_fingerprint': fingerprint, 'error': str(error)})
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('build', 'check'))
    parser.add_argument('--nx-root', type=Path, default=Path(os.environ.get('UGII_BASE_DIR', 'C:/Siemens/NX2406')))
    parser.add_argument('--accept-model-assumptions', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            print('PASS: ' + str(build_native(args.nx_root, args.accept_model_assumptions)))
        else:
            current = read(ROOT / 'cad/nx/CURRENT.json')
            attempt = read(ROOT / 'cad/nx/LAST_ATTEMPT.json')
            if attempt.get('status') != 'PASS' or attempt.get('directory') != current['directory']:
                raise ValueError('Latest NX attempt is not verified')
            directory = member_path(ROOT / 'cad/nx', current['directory'])
            build = read(directory / 'BUILD.json')
            if current.get('master') != current['directory'] + '/' + build.get('master', ''):
                raise ValueError('CURRENT master pointer does not match the verified build')
            errors = validate_evidence(directory, build, read(directory / 'VERIFY.json'), source_fingerprint())
            if errors:
                raise ValueError('; '.join(errors))
            print('PASS: saved NX evidence and native files match current sources (no new NX run)')
        return 0
    except Exception as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
