"""Real NX study orchestration. Offline checks validate evidence, never emulate NX."""
from __future__ import annotations
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from tools.repo_support import digest, member_path
from .planning import DEFAULT_SOURCES, create_plan
from .mesh_step import write_step

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def source_fingerprint():
    paths = set(DEFAULT_SOURCES.values())
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'renovierung/k02').glob('*.py'))
    paths.update(('renovierung/k02/study_config.json', 'tools/nx_project.py', 'tools/repo_support.py',
                  'cad/nx/CURRENT.json'))
    baseline = read(ROOT / 'cad/nx/CURRENT.json')
    directory = member_path(ROOT / 'cad/nx', baseline['directory'])
    paths.update((directory / name).relative_to(ROOT).as_posix() for name in ('BUILD.json', 'VERIFY.json'))
    build = read(directory / 'BUILD.json')
    paths.update((directory / row['path']).relative_to(ROOT).as_posix() for row in build['parts'])
    return hashlib.sha256(json.dumps({p: digest(member_path(ROOT, p)) for p in sorted(paths)}, sort_keys=True).encode()).hexdigest()


def _positive_volume(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _component_total(values):
    if not isinstance(values, list) or not values or not all(_positive_volume(v) for v in values):
        raise ValueError('Native components must be nonempty, finite and positive')
    try:
        total = math.fsum(values)
    except OverflowError as error:
        raise ValueError('Native component total overflow') from error
    if not _positive_volume(total):
        raise ValueError('Native component total must be finite and positive')
    return total


def _measurement_values(record):
    values = record['component_volumes_m3']
    total = _component_total(values)
    if type(record['body_count']) is not int or record['body_count'] != len(values):
        raise ValueError('Native component count mismatch')
    saved_total = record.get('volume_m3')
    # Internal record coherence uses relative rounding tolerance, not CAD tolerance.
    if not _positive_volume(saved_total) or not math.isclose(saved_total, total, rel_tol=1e-12, abs_tol=0.0):
        raise ValueError('Native stored total must match its finite positive component sum')
    return values


def validate_measurement(actual, expected):
    values = _measurement_values(actual)
    _component_total(expected)
    if len(values) != len(expected):
        raise ValueError('Native component count mismatch')
    for a, b in zip(sorted(values), sorted(expected)):
        if abs(a-b) > max(1e-10, abs(b)*1e-6):
            raise ValueError('Native volume mismatch')


def validate_evidence(directory, build, verify, fingerprint, require_complete=True):
    errors = []
    try:
        if build.get('schema') != 'K02_NATIVE_BUILD_V1' or build.get('status') != 'PASS' or build.get('native_NX_run_completed') is not True:
            errors.append('Missing real K02 build evidence')
        if verify.get('schema') != 'K02_NATIVE_VERIFY_V1' or verify.get('status') != 'PASS':
            errors.append('Missing native K02 verification')
        if any(r.get('source_fingerprint') != fingerprint for r in (build, verify)):
            errors.append('K02 source/generator evidence stale')
        if build.get('construction_release') is not False:
            errors.append('Study cannot carry construction release')
        if require_complete and (build.get('complete_study') is not True or
                set(build['candidate_ids']) != set(build['delivered_field_ids'])):
            errors.append('K02 study incomplete')
        all_names = []
        state_ids = []
        for state in build['states']:
            state_ids.append(state['id'])
            names = []
            for row in state['parts']:
                path = member_path(directory, row['path'])
                if path.suffix.lower() != '.prt' or not path.is_file() or digest(path) != row['sha256'] or path.stat().st_size != row['bytes']:
                    raise ValueError('Missing/changed native part: ' + row['path'])
                names.append(row['path'])
            if not names or state['master'] not in names:
                errors.append('Missing state master: ' + state['id'])
            all_names.extend(names)
            for phase in ('reopen', 'relocated'):
                result = verify['states'][state['id']][phase]
                if result.get('status') != 'PASS' or result.get('master') != state['master'] or set(result['parts']) != set(names):
                    errors.append('Incomplete state verification: ' + state['id'] + '/' + phase)
                if result.get('transforms') != state['transforms']:
                    errors.append('Native transforms differ: ' + state['id'])
                actual_measurements = result.get('measurements', {})
                if set(actual_measurements) != set(state['measurements']):
                    errors.append('Native measurement roles differ: ' + state['id'])
                for role, expected in state['measurements'].items():
                    validate_measurement(actual_measurements[role], _measurement_values(expected))
        if len(set(state_ids)) != len(state_ids) or 'BASE' not in state_ids:
            errors.append('Missing/duplicate base state')
        if set(state_ids) != {'BASE', *build['delivered_field_ids']}:
            errors.append('Delivered state register mismatch')
        if len(set(n.casefold() for n in all_names)) != len(all_names):
            errors.append('Cross-state duplicate part path')
        actual = {p.relative_to(directory).as_posix() for p in Path(directory).rglob('*.prt')}
        if actual != set(all_names):
            errors.append('Native files differ from manifest')
    except (AttributeError, KeyError, TypeError, ValueError, OSError) as error:
        errors.append('Malformed K02 evidence: ' + str(error))
    return errors


def check_study():
    try:
        root = ROOT / 'cad/nx/k02'
        current, attempt = read(root/'CURRENT.json'), read(root/'LAST_ATTEMPT.json')
        if attempt.get('status') != 'PASS' or attempt.get('directory') != current['directory']:
            return ['Latest K02 attempt not verified']
        directory = member_path(root, current['directory'])
        build = read(directory/'BUILD.json')
        if current.get('masters') != {s['id']: s['master'] for s in build['states']}:
            return ['K02 CURRENT masters mismatch']
        return validate_evidence(directory, build, read(directory/'VERIFY.json'), source_fingerprint())
    except (AttributeError, OSError, KeyError, TypeError, ValueError) as error:
        return ['K02 evidence missing/malformed: ' + str(error)]


def journal(nx_root, module, request, scratch, label):
    req, report = scratch/(label+'_request.json'), scratch/(label+'_result.json')
    write(req, dict(request, report=str(report), repo_root=str(ROOT)))
    env = dict(os.environ, K02_NX_REQUEST=str(req), PYTHONDONTWRITEBYTECODE='1')
    print('NX K02 ' + label, flush=True)
    with (scratch/(label+'.log')).open('w', encoding='utf-8') as stream:
        process = subprocess.run([str(nx_root/'NXBIN/run_journal.exe'), str(ROOT/'renovierung/k02'/module)],
                                 cwd=scratch, env=env, stdout=stream, stderr=subprocess.STDOUT)
    result = read(report)
    if process.returncode or result.get('status') != 'PASS':
        raise RuntimeError('NX K02 failed: ' + str(result.get('error', process.returncode)) + '; ' + str(report))
    return result


def compact(value):
    """Keep quantities, warnings and provenance; exclude bulky interchange meshes."""
    if isinstance(value, dict):
        return {k: compact(v) for k, v in value.items() if k not in ('mesh', 'mesh_components', 'projection_polygons', 'uncertainty_coverage_hull')}
    if isinstance(value, list):
        return [compact(v) for v in value]
    return value


def build_study(nx_root: Path, accept: bool, *, prototype_field=None, plan=None) -> Path:
    """Build all states, or a local pilot which can never advance CURRENT.

    A supplied plan is accepted only with byte-valid input/generator provenance.
    Normal project builds generate a fresh plan. Prototype evidence is separate.
    """
    if not accept:
        raise ValueError('Explicit acceptance of documented study assumptions required')
    nx_root = Path(nx_root)
    stamp = datetime.datetime.now().strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:6]
    pilot = prototype_field is not None
    scratch = ROOT/'reports/local/k02'/stamp
    destination = scratch/'native' if pilot else ROOT/'cad/nx/k02'/stamp
    attempt = scratch/'ATTEMPT.json' if pilot else ROOT/'cad/nx/k02/LAST_ATTEMPT.json'
    write(attempt, {'status': 'RUNNING', 'directory': stamp})
    try:
        if not (nx_root/'NXBIN/run_journal.exe').is_file():
            raise FileNotFoundError('NX run_journal missing')
        fingerprint = source_fingerprint()
        from tools import nx_project
        current = read(ROOT/'cad/nx/CURRENT.json')
        source = member_path(ROOT/'cad/nx', current['directory'])
        baseline = read(source/'BUILD.json')
        # Pilot may prove APIs against the untouched historical source, explicitly
        # recording its old scope. Full delivery requires current baseline evidence.
        baseline_errors = nx_project.validate_evidence(source, baseline, read(source/'VERIFY.json'),
            baseline['source_fingerprint'] if pilot else nx_project.source_fingerprint())
        if baseline_errors:
            raise ValueError('; '.join(baseline_errors))
        config = read(ROOT/'renovierung/k02/study_config.json')
        if plan is None:
            plan = create_plan(ROOT, config)
        write(scratch/'PLAN.json', plan)
        for row in plan['provenance']['inputs'] + plan['provenance']['generators']:
            if digest(member_path(ROOT, row['path'])) != row['sha256']:
                raise ValueError('Supplied plan provenance stale: ' + row['path'])
        if plan['provenance']['config'] != config:
            raise ValueError('Plan configuration differs from active configuration')
        candidates = [f for f in plan['fields'] if f['native_candidate']]
        selected = [f for f in candidates if not pilot or f['id'] == prototype_field]
        if pilot and len(selected) != 1:
            raise ValueError('Prototype must select one native candidate')
        scratch.mkdir(parents=True, exist_ok=True)
        destination.mkdir(parents=True, exist_ok=False)
        work = Path(tempfile.mkdtemp(prefix='K02_'))
        original_hashes = {r['path']: digest(source/r['path']) for r in baseline['parts']}
        baseline_check = journal(nx_root, 'nx_verify.py', {'directory': str(source), 'master': baseline['master'],
            'parts': baseline['parts'], 'load_method': 'SearchDirectories', 'measurements': {}}, scratch, 'source')
        states, verifications = [], {}
        register = compact(plan['fields'])
        for index, field in enumerate([None] + selected):
            sid = 'BASE' if field is None else field['id']
            state_root = destination/sid
            state_root.mkdir()
            mapping = {r['path']: f'{sid}_{i:02d}.prt' for i, r in enumerate(baseline['parts'])}
            request = {'source': str(source), 'source_parts': baseline['parts'], 'source_master': baseline['master'],
                'source_transforms': baseline_check['transforms'], 'mapping': mapping, 'directory': str(state_root),
                'field': compact(field) if field else None, 'register': register,
                'nx_root': str(nx_root), 'state_id': sid, 'source_fingerprint': fingerprint,
                'geometry_work_file': str(work/(sid+'_g.prt'))}
            if field:
                request['imports'] = {}
                geometry = {'soil': field['study_terrain']['mesh'], 'excavation': field['mesh'],
                            'pile_main': field['stockpile']['main']['mesh'],
                            'pile_reserve': field['stockpile']['reserve_1_25']['mesh']}
                for role, mesh in geometry.items():
                    path = work/(sid+'_'+role+'.step')
                    write_step(path, mesh, sid+'_'+role)
                    request['imports'][role] = str(path)
                from .geometry import validate_mesh
                request['soil_expected_m3'] = validate_mesh(geometry['soil'])['volume_mm3']/1e9
            state = journal(nx_root, 'nx_build.py', request, scratch, 'build_'+sid)
            # Every assembly gets its own directory and globally unique leaf names.
            persisted = state_root
            verify_request = {'directory': str(persisted), 'master': state['master'], 'parts': state['parts'],
                              'measurements': state['measurements'], 'transforms': state['transforms'],
                              'load_method': 'AsSaved'}
            reopen = journal(nx_root, 'nx_verify.py', verify_request, scratch, 'reopen_'+sid)
            moved = scratch/('moved_'+sid)
            shutil.copytree(persisted, moved)
            relocated = journal(nx_root, 'nx_verify.py', dict(verify_request, directory=str(moved), load_method='SearchDirectories'), scratch, 'relocated_'+sid)
            for report in (state, reopen, relocated):
                report['master'] = sid+'/'+report['master']
                if isinstance(report['parts'][0], dict):
                    for row in report['parts']: row['path'] = sid+'/'+row['path']
                else: report['parts'] = [sid+'/'+p for p in report['parts']]
            states.append(state)
            verifications[sid] = {'reopen': reopen, 'relocated': relocated}
            if field:
                field['native_measured_volume_m3'] = state['measurements']['excavation']['volume_m3']
                field['native_minus_mathematical_m3'] = field['native_measured_volume_m3']-field['volume_m3']
                field['native_status'] = 'NATIVE_BUILD_FRESH_REOPEN_RELOCATED_PASS'
                field['study_terrain']['cutout_applied'] = True
        plan['provenance']['native_verified_field_ids'] = [f['id'] for f in selected]
        plan['provenance']['native_verified'] = not pilot
        plan['limitations'] = [s for s in plan['limitations'] if s != 'NO_NX_EXECUTION_OR_VERIFICATION']
        if pilot: plan['limitations'].append('PROTOTYPE_ONLY_NOT_COMPLETE_NATIVE_STUDY')
        if original_hashes != {name: digest(source/name) for name in original_hashes}:
            raise ValueError('Original native source modified')
        if source_fingerprint() != fingerprint:
            raise ValueError('K02 inputs changed during native build')
        build = {'schema': 'K02_NATIVE_BUILD_V1', 'status': 'PASS', 'native_NX_run_completed': True,
                 'source_fingerprint': fingerprint, 'states': states, 'construction_release': False,
                 'candidate_ids': [f['id'] for f in candidates], 'delivered_field_ids': [f['id'] for f in selected],
                 'complete_study': not pilot, 'prototype_only': pilot, 'source_hashes': original_hashes,
                 'baseline_source_directory': str(source), 'baseline_fingerprint': baseline['source_fingerprint'],
                 'baseline_current_scope_valid': not baseline_errors and not pilot,
                 'baseline_native_check': baseline_check, 'plan': compact(plan)}
        verify = {'schema': 'K02_NATIVE_VERIFY_V1', 'status': 'PASS', 'source_fingerprint': fingerprint, 'states': verifications}
        write(destination/'BUILD.json', build)
        write(destination/'VERIFY.json', verify)
        errors = validate_evidence(destination, build, verify, fingerprint, require_complete=not pilot)
        if errors: raise ValueError('; '.join(errors))
        if not pilot:
            write(ROOT/'cad/nx/k02/CURRENT.json', {'directory': stamp, 'masters': {s['id']: s['master'] for s in states}})
        write(attempt, {'status': 'PASS', 'directory': stamp, 'source_fingerprint': fingerprint})
        return destination
    except Exception as error:
        write(attempt, {'status': 'FAIL', 'directory': stamp, 'error': str(error)})
        raise
