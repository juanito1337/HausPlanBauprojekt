"""Reproducible native M02 build, complete acceptance and offline freshness."""
from copy import deepcopy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

from tools.repo_support import digest, member_path
from renovierung.m01.runner import exclusive_build, wait_for_journal_slot

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = 'cad/nx/m01/20261104T222509Z_edc552'
EXPECTED_COUNTS = {'old_nodes': 349, 'parts': 367, 'states': 60,
                   'reviews': 59, 'entries': 145}


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    """Replace only the named JSON record, atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write((json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def canonical_sha(value):
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def json_contract(value):
    """Use the exact persisted array representation, without numerical rounding."""
    return json.loads(json.dumps(value, ensure_ascii=True, allow_nan=False))


def inventory(root):
    root = Path(root).resolve()
    result = {}
    names = set()
    for path in sorted(root.rglob('*.prt')):
        if path.is_symlink() or path.parent.resolve() != root or path.name.casefold() in names:
            raise ValueError('Native delivery must contain unique flat nonsymlink Parts')
        names.add(path.name.casefold())
        result[path.name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return result


def compact_prepared(prepared):
    """Preserve exact native attribute specifications without ignored STEP paths."""
    result = {'schema': prepared['schema'], 'plan_sha256': prepared['plan_sha256'],
            'fields': {fid: {'spec': deepcopy(row['spec']), 'presentation': deepcopy(row['presentation'])}
                       for fid, row in prepared['fields'].items()},
            'presentation': deepcopy(prepared.get('presentation')),
            'register_only_ids': list(prepared.get('register_only_ids', []))}
    # Geometry helpers return tuples; persisted native contracts contain JSON arrays.
    # Round-trip the exact values, without rounding or changing the numerical gate.
    return json_contract(result)


def compact_site(entry):
    return json_contract({key: value for key, value in entry.items()
                          if key not in ('step_path', 'entry_path', 'nx_root')})


def physical_layout(layout, mapping):
    result = deepcopy(layout)
    for node in result['nodes']:
        node['file'] = mapping[node['file']]
    for entry in result['review_masters']:
        entry['file'] = mapping[entry['file']]
    result['master'] = mapping[result['master']]
    return result


def run_native(nx_root, request, scratch, label, journal='journal.py'):
    wait_for_journal_slot()
    scratch = Path(scratch)
    request = dict(request, repo_root=str(ROOT), report=str(scratch / (label + '_result.json')))
    request_path = scratch / (label + '_request.json')
    write(request_path, request)
    variable = 'ANBAU_NX_REQUEST' if journal == 'nx_fields.py' else 'ANBAU_MASTER_REQUEST'
    environment = dict(os.environ, **{variable: str(request_path), 'PYTHONDONTWRITEBYTECODE': '1'})
    print('NX M02 ' + label, flush=True)
    with (scratch / (label + '.log')).open('w', encoding='utf-8') as log:
        process = subprocess.run([str(Path(nx_root) / 'NXBIN/run_journal.exe'),
                                  str(ROOT / 'renovierung/anbau' / journal)],
                                 cwd=scratch, env=environment, stdout=log, stderr=subprocess.STDOUT)
    report = Path(request['report'])
    if not report.is_file():
        raise RuntimeError('Native phase produced no report: ' + label)
    result = read(report)
    if process.returncode or result.get('status') != 'PASS':
        raise RuntimeError('Native ' + label + ': ' + str(result.get('error', process.returncode)))
    return result


def source_fingerprint(base, plan, prepared, site_entry, *, repo_root=None):
    repo = Path(repo_root or ROOT).resolve()
    paths = set(plan['provenance']['source_and_generator_hashes'])
    for directory in ('renovierung/anbau', 'renovierung/k02', 'renovierung/m01', 'tools'):
        paths.update(path.relative_to(repo).as_posix() for path in (repo / directory).glob('*.py'))
    paths.update(('renovierung/anbau/assumptions.json', 'renovierung/anbau/KATALOG.json'))
    review = repo / 'renovierung/anbau/RANDSTREIFEN_REVIEW.json'
    if review.is_file():
        paths.add(review.relative_to(repo).as_posix())
    catalog = read(repo / 'renovierung/anbau/KATALOG.json')
    declared_review = catalog.get('aktuelleDarstellungsfreigabe', {}).get('review')
    if declared_review:
        paths.add(declared_review)
    sources = {path: digest(member_path(repo, path)) for path in sorted(paths)}
    sources.update(base_build=digest(Path(base) / 'BUILD.json'),
                   base_parts=canonical_sha(inventory(base)), plan=canonical_sha(plan),
                   prepared=canonical_sha(compact_prepared(prepared)),
                   site_entry=canonical_sha(compact_site(site_entry)))
    return canonical_sha(sources)


def source_record(base):
    """Accept complete build bytes; do not assert an unproven full M01 release."""
    base = Path(base).resolve()
    build = read(base / 'BUILD.json')
    if build.get('schema') != 'M01_FLAT_BUILD_V2' or build.get('native_NX_run_completed') is not True:
        raise ValueError('Explicit complete native flat M01 build candidate is required')
    mapping = build['delivery_file_map']
    rows = build['parts']
    expected = {row['path']: {'bytes': row['bytes'], 'sha256': row['sha256']} for row in rows}
    if (len(mapping) != 318 or len({name.casefold() for name in mapping.values()}) != 318
            or len(rows) != 318 or set(expected) != set(mapping.values()) or inventory(base) != expected):
        raise ValueError('Incomplete or changed 318-Part source build candidate')
    return build


def validate_base_layout(baseline, current_layout):
    """Bind native baseline bytes to the current canonical M01 specification."""
    if baseline['layout'] != current_layout:
        raise ValueError('Current M01 layout differs; first generate a matching M01 base')


def check_pinned_review(plan, repo_root=None):
    """Parameter changes need an explicit review revision, never an automatic overwrite."""
    from .integration import review_edge_strips
    repo = Path(repo_root or ROOT).resolve()
    catalog = read(repo / 'renovierung/anbau/KATALOG.json')
    declared = catalog['aktuelleDarstellungsfreigabe']
    path = member_path(repo, declared['review'])
    review = read(path)
    if (digest(path) != declared['review_sha256'] or review != review_edge_strips(plan)
            or declared['construction_release'] is not False
            or declared['regular_study_ids'] != review['regular_study_ids']
            or declared['diagnostic_ids'] != review['diagnostic_ids']):
        raise ValueError('Current assumptions require an explicit matching edge-strip review revision')
    return review


def current_field_inputs(plan):
    from .nx_fields import field_spec
    from renovierung.m01.presentation import camera_spec
    specs = {field['id']: field_spec(field) for field in plan['fields']}
    points = [point for spec in specs.values() for row in spec['geometry'].values()
              for point in (row['bbox_mm'][:3], row['bbox_mm'][3:])]
    presentation = plan.get('presentation') or camera_spec(points)
    return compact_prepared({'schema': 'ANBAU_FIELD_INPUTS_V1', 'plan_sha256': canonical_sha(plan),
            'fields': {fid: {'spec': spec, 'presentation': presentation}
                       for fid, spec in specs.items() if spec['file'] is not None},
            'presentation': presentation,
            'register_only_ids': sorted(fid for fid, spec in specs.items() if spec['file'] is None)})


def assert_counts(spec):
    studies = sorted(fid for fid, field in spec['fields'].items() if field['native'])
    diagnostics = sorted(fid for fid, field in spec['fields'].items() if field['diagnostic'])
    expected = dict(EXPECTED_COUNTS, nodes=349+5*len(studies)+len(diagnostics))
    if (spec['counts'] != expected or len(studies)+len(diagnostics) != 24
            or set(studies) & set(diagnostics) or set(studies+diagnostics) != set(spec['prepared_fields'])):
        raise ValueError('Incomplete M02 inventory or canonical risk classification')
    return {'study_ids': studies, 'diagnostic_ids': diagnostics, 'construction_release': False}


def _asset_path(manifest_path, value):
    path = Path(value)
    return (path if path.is_absolute() else Path(manifest_path).parent / path).resolve()


def _verify_field_asset_reports(prepared, build, verify):
    from .nx_fields import validate_native_result
    for report in (build, verify):
        if (report.get('status') != 'PASS' or report.get('native_NX_run_completed') is not True
                or report.get('plan_sha256') != prepared['plan_sha256']
                or set(report['fields']) != set(prepared['fields'])):
            raise ValueError('Missing complete native 24-field build/fresh-reopen evidence')
        for fid, entry in prepared['fields'].items():
            validate_native_result(entry['spec'], report['fields'][fid])


def _current_site(plan):
    from .geometry import load_terrain
    from .site import create_site_context
    return json_contract(create_site_context(load_terrain(ROOT), plan['fields'], include_mesh=False))


def _reuse_assets(manifest_path, plan):
    """Explicit reuse is never a substitute for final independent M02 acceptance."""
    manifest_path = Path(manifest_path).resolve()
    manifest = read(manifest_path)
    if manifest.get('schema') != 'M02_NATIVE_ASSETS_V1':
        raise ValueError('Unsupported explicit native asset manifest')
    prepared = read(_asset_path(manifest_path, manifest['field_inputs']))
    if compact_prepared(prepared) != current_field_inputs(plan):
        raise ValueError('Reused field inputs differ from current canonical planning')
    site_entry = read(_asset_path(manifest_path, manifest['site_entry']))
    from .site import validate_site_entry
    validate_site_entry(site_entry)
    if any(site_entry.get(key) != value for key, value in _current_site(plan).items() if key != 'mesh'):
        raise ValueError('Reused shared-ground inputs differ from current terrain/masks')
    reports = {name: read(_asset_path(manifest_path, manifest[name])) for name in
               ('field_build', 'field_verify', 'site_build', 'site_verify')}
    _verify_field_asset_reports(prepared, reports['field_build'], reports['field_verify'])
    for name in ('site_build', 'site_verify'):
        report = reports[name]
        if report.get('status') != 'PASS' or report['evidence'].get('entry_sha256') != site_entry['entry_sha256']:
            raise ValueError('Reused site needs matching native build and fresh-reopen proofs')
    field_root = _asset_path(manifest_path, manifest['field_directory'])
    site_root = _asset_path(manifest_path, manifest['site_directory'])
    sources = {}
    for fid, row in reports['field_build']['fields'].items():
        path = field_root / prepared['fields'][fid]['spec']['file']
        if path.is_symlink() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise ValueError('Reused native field bytes changed: ' + path.name)
        sources[path.name] = path
    site_path = site_root / site_entry['file']
    built = reports['site_build']
    if site_path.is_symlink() or site_path.stat().st_size != built['bytes'] or digest(site_path) != built['sha256']:
        raise ValueError('Reused native shared-ground bytes changed')
    sources[site_path.name] = site_path
    provenance = {'mode': 'EXPLICIT_REUSE', 'manifest_sha256': digest(manifest_path),
                  'reports': {name: digest(_asset_path(manifest_path, manifest[name])) for name in reports}}
    return compact_prepared(prepared), compact_site(site_entry), sources, provenance


def _build_assets(nx_root, plan, scratch):
    from .nx_fields import prepare_inputs
    from .site import create_site_context, prepare_site_inputs
    from .geometry import load_terrain
    prepared = prepare_inputs(plan, scratch / 'field_inputs')
    field_root = scratch / 'field_parts'
    request = {'mode': 'build', 'directory': str(field_root), 'prepared': prepared, 'nx_root': str(nx_root)}
    build = run_native(nx_root, request, scratch, 'field_build', 'nx_fields.py')
    verify = run_native(nx_root, dict(request, mode='verify'), scratch, 'field_verify', 'nx_fields.py')
    _verify_field_asset_reports(prepared, build, verify)
    site = create_site_context(load_terrain(ROOT), plan['fields'], include_mesh=True)
    entry = prepare_site_inputs(site, scratch / 'site_inputs', nx_root=nx_root)
    site_root = scratch / 'site_parts'
    request = {'directory': str(site_root), 'site_entry': entry}
    run_native(nx_root, dict(request, mode='site_build'), scratch, 'site_build')
    run_native(nx_root, dict(request, mode='site_verify'), scratch, 'site_verify')
    sources = {row['spec']['file']: field_root / row['spec']['file'] for row in prepared['fields'].values()}
    sources[entry['file']] = site_root / entry['file']
    return compact_prepared(prepared), compact_site(entry), sources, {'mode': 'GENERATED_FROM_VERSIONED_INPUTS'}


def validate_evidence(directory, build, verify, fingerprint=None):
    """Complete release gate, independent of any ignored scratch artifacts."""
    errors = []
    try:
        from .verification import inspect_files, validate_full_evidence, validate_default_evidence
        if (build.get('schema') != 'M02_BUILD_V2' or build.get('status') != 'PASS'
                or build.get('native_NX_run_completed') is not True or build.get('construction_release') is not False):
            raise ValueError('M02 build is pending or has no complete native release proof')
        if verify.get('schema') != 'M02_VERIFY_V2' or verify.get('status') != 'PASS':
            raise ValueError('Missing complete M02 VERIFY')
        for record in (build, verify):
            if fingerprint is not None and record['source_fingerprint'] != fingerprint:
                raise ValueError('M02 source/generator fingerprint is stale')
        if build['source_fingerprint'] != verify['source_fingerprint']:
            raise ValueError('M02 build and verification fingerprints differ')
        reference = build['expectations']
        path = member_path(Path(directory), reference['file'])
        if path.stat().st_size != reference['bytes'] or digest(path) != reference['sha256']:
            raise ValueError('Independent expectation bytes changed')
        spec = read(path)
        if (spec['spec_sha256'] != reference['spec_sha256']
                or canonical_sha({k: v for k, v in spec.items() if k != 'spec_sha256'}) != spec['spec_sha256']):
            raise ValueError('Independent expectation contract changed')
        if build['classification'] != assert_counts(spec) or build['parts'] != inspect_files(directory, spec):
            raise ValueError('Current Part bytes or integrated classification differ')
        if build.get('repair') or build.get('naming_repair') or build.get('defaults_repair'):
            validate_repair_provenance(directory, build, spec)
        if build.get('defaults_repair'):
            validate_section_smoke_record(spec, build['defaults_repair']['smoke'], build['parts'])
        if verify.get('source_bytes_unchanged') is not True or verify.get('delivery_bytes_unchanged') is not True:
            raise ValueError('Missing source/delivery byte guards')
        errors.extend(validate_full_evidence(spec, verify['full']))
        errors.extend(validate_default_evidence(spec, verify['relocated_default']))
        if verify['full']['file_manifest'] != build['parts'] or verify['relocated_default']['file_manifest'] != build['parts']:
            raise ValueError('Native phases did not inspect exactly the final 367 Part bytes')
    except (AttributeError, KeyError, TypeError, ValueError, OSError, IndexError) as error:
        errors.append('M02: ' + str(error))
    return errors


def validate_repair_candidate(directory, build, spec, repo_root=None, *, naming=False, defaults=False):
    """Reject published, historical, incomplete or changed candidates before writes."""
    repo = Path(repo_root or ROOT).resolve()
    directory = Path(directory)
    if directory.is_symlink() or directory.resolve().parent != repo / 'cad/nx/m02':
        raise ValueError('Repair requires an explicit direct M02 candidate directory')
    current = directory.parent / 'CURRENT.json'
    if current.exists() and read(current).get('directory') == directory.name:
        raise ValueError('Refusing to repair a published CURRENT delivery')
    if (build.get('schema') != 'M02_BUILD_V2' or build.get('status') != 'BUILT_PENDING_VERIFICATION'
            or build.get('native_NX_run_completed') is not True
            or build.get('construction_release') is not False
            or (naming and defaults) or bool(build.get('repair')) != (naming or defaults)
            or bool(build.get('naming_repair')) != defaults or build.get('defaults_repair')):
        raise ValueError('Repair requires an unpublished, unrepaired pending build')
    if (directory / 'VERIFY.json').exists() and read(directory / 'VERIFY.json').get('status') == 'PASS':
        raise ValueError('Refusing to repair a previously published/verified delivery')
    if len(build['parts']) != 367 or inventory(directory) != build['parts']:
        raise ValueError('Repair requires the exact original 367-Part manifest')
    reference = build['expectations']
    path = member_path(directory, reference['file'])
    if (reference['file'] != 'EXPECTATIONS.json' or path.stat().st_size != reference['bytes']
            or digest(path) != reference['sha256'] or read(path) != spec
            or spec['spec_sha256'] != reference['spec_sha256']
            or canonical_sha({k: v for k, v in spec.items() if k != 'spec_sha256'}) != spec['spec_sha256']
            or read(directory / 'BUILD.json') != build):
        raise ValueError('Original pending build/expectation evidence changed')
    if naming or defaults:
        validate_repair_provenance(directory, build, spec)


def repair_targets(spec):
    files = {node['id']: node['file'] for node in spec['layout']['nodes']}
    names = {spec['file_map'][files[nid]] for nid in ('MASTER', 'CONSTRUCTION')}
    if len(names) != 2 or any(Path(name).name != name for name in names):
        raise ValueError('Repair must save exactly the two internal owner Parts')
    return names


def naming_targets(spec):
    ids = {'CONSTRUCTION'} | {'SECTION_PS%02d' % i for i in range(10, 14)}
    files = {node['id']: node['file'] for node in spec['layout']['nodes']}
    names = {spec['file_map'][files[nid]] for nid in ids}
    if len(names) != 5 or any(Path(name).name != name for name in names):
        raise ValueError('Naming repair must save exactly the five internal owner Parts')
    return names


def defaults_targets(spec):
    files = {node['id']: node['file'] for node in spec['layout']['nodes']}
    names = {spec['file_map'][files[nid]] for nid in ('SECTION_PS12', 'SECTION_PS13')}
    if len(names) != 2 or any(Path(name).name != name for name in names):
        raise ValueError('Default repair must save exactly SECTION_PS12 and SECTION_PS13')
    return names


def validate_naming_instances(repaired, spec):
    nodes = {node['id']: node for node in spec['layout']['nodes']}
    expected = {'SECTION_PS%02d' % i for i in range(10, 14)} | {'FIELD_'+fid for fid in spec['fields']}
    before, after = repaired['before_instance_names'], repaired['instance_names']
    if len(expected) != 28 or set(before) != expected or set(after) != expected:
        raise ValueError('Naming repair must prove exactly the 28 canonical native instances')
    keys = {'parent_id', 'owner_file', 'instance_name', 'custom_name', 'reference_set',
            'translation_mm', 'rotation', 'used_arrangement', 'metadata_sha256'}
    for nid in expected:
        row, previous, actual = nodes[nid], before[nid], after[nid]
        if set(previous) != keys or set(actual) != keys:
            raise ValueError('Incomplete native naming/transform evidence: ' + nid)
        unchanged_before = {k: v for k, v in previous.items() if k != 'instance_name'}
        unchanged_after = {k: v for k, v in actual.items() if k != 'instance_name'}
        if (unchanged_before != unchanged_after or actual['instance_name'].casefold() != row['name'].casefold()
                or actual['parent_id'] != row['parent'] or actual['owner_file'] != nodes[row['parent']]['file']
                or actual['custom_name'].casefold() != row['name'].casefold()
                or actual['reference_set'] != row['reference_set']
                or actual['translation_mm'] != row['translation_mm'] or actual['rotation'] != row['rotation']
                or actual['metadata_sha256'] != canonical_sha(row)):
            raise ValueError('Naming repair changed instance geometry/metadata or left an old name: ' + nid)


def validate_repair_contract(old, new):
    """Only the owner-save exemption and derived specification hashes may change."""
    construction = next(n['file'] for n in old['layout']['nodes'] if n['id'] == 'CONSTRUCTION')
    name = old['file_map'][construction]
    expected = deepcopy(old)
    if name not in expected['immutable_parts']:
        raise ValueError('Candidate does not have the known missing owner-save contract')
    expected['immutable_parts'].pop(name)
    expected['upgrade_attributes']['spec_sha256'] = new['upgrade_attributes']['spec_sha256']
    expected['spec_sha256'] = new['spec_sha256']
    if expected != new or repair_targets(old) != repair_targets(new):
        raise ValueError('Repair would change geometry, source or an unrelated delivery contract')


def run_repair_native(nx_root, request, scratch, directory, before, source_root, source_before, targets):
    """Restore only phase-owned bytes after a terminated failing journal and guards."""
    if inventory(directory) != before or inventory(source_root) != source_before:
        raise ValueError('Candidate/source bytes changed before the repair journal')
    backups = Path(scratch) / 'repair_backups'
    backups.mkdir(exist_ok=False)
    for name in sorted(targets):
        shutil.copyfile(Path(directory) / name, backups / name)
        if digest(backups / name) != before[name]['sha256']:
            raise ValueError('Repair backup differs: ' + name)
    try:
        mode = request.get('mode', 'repair_existing')
        naming = mode == 'repair_instance_names'
        defaults = mode == 'repair_section_defaults'
        result = run_native(nx_root, request, scratch, mode)
        after = inventory(directory)
        if (set(after) != set(before) or inventory(source_root) != source_before
                or any(after[name] != row for name, row in before.items() if name not in targets)):
            raise ValueError('Repair changed source or Parts outside the authorized owners')
        repaired = result['repair']
        if defaults:
            owner_ids = {'SECTION_PS12', 'SECTION_PS13'}
            expected_status = 'SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY'
        elif naming:
            owner_ids = {'CONSTRUCTION'} | {'SECTION_PS%02d' % i for i in range(10, 14)}
            expected_status = 'INSTANCE_NAMES_REPAIRED_PENDING_FRESH_VERIFY'
        else:
            owner_ids = {'MASTER', 'CONSTRUCTION'}
            expected_status = 'REPAIRED_PENDING_FRESH_VERIFY'
        logical_targets = {node['file'] for node in request['new_upgrade']['base_layout']['nodes']
                           if node['id'] in owner_ids}
        if (repaired['status'] != expected_status
                or repaired['before_parts'] != before or repaired['after_parts'] != after
                or repaired['unchanged_parts'] != 367-len(targets) or repaired['source_bytes_unchanged'] is not True
                or set(repaired['saved_parts']) != logical_targets or len(repaired['saved_parts']) != len(targets)
                or repaired['spec_sha256'] != request['new_upgrade']['spec_sha256']):
            raise ValueError('Incomplete native owner-repair evidence')
        if defaults:
            from .integration import validate_section_defaults_evidence
            validate_section_defaults_evidence(request['verification_spec'], repaired)
        elif naming:
            validate_naming_instances(repaired, request['verification_spec'])
        elif repaired['old_upgrade_spec_sha256'] != request['old_verification_spec']['upgrade_attributes']['spec_sha256']:
            raise ValueError('Original owner-repair specification differs')
        return result
    except Exception as error:
        # run_native is synchronous: the journal process has ended before this path.
        after = inventory(directory)
        if (set(after) != set(before) or inventory(source_root) != source_before
                or any(after[name] != row for name, row in before.items() if name not in targets)):
            raise RuntimeError('Repair failed; rollback refused because source/other Part bytes changed') from error
        for name in sorted(targets):
            if digest(backups / name) != before[name]['sha256']:
                raise RuntimeError('Repair failed; original backup changed, rollback refused') from error
        for name in sorted(targets):
            shutil.copyfile(backups / name, Path(directory) / name)
        if inventory(directory) != before:
            raise RuntimeError('Repair failed and original-byte rollback could not be confirmed') from error
        raise


def validate_repair_provenance(directory, build, spec):
    records = build['repair']['initial_records']
    if set(records) != {'BUILD.json', 'EXPECTATIONS.json'}:
        raise ValueError('Incomplete initial repair evidence')
    initial = {}
    for name, record in records.items():
        expected_name = Path(name).stem + '_INITIAL.json'
        path = member_path(directory, record['file'])
        if (record['file'] != expected_name or path.stat().st_size != record['bytes']
                or digest(path) != record['sha256']):
            raise ValueError('Initial repair evidence bytes changed')
        initial[name] = read(path)
    old_build, old_spec = initial['BUILD.json'], initial['EXPECTATIONS.json']
    if (old_build['status'] != 'BUILT_PENDING_VERIFICATION' or old_build.get('repair')
            or old_build['source_fingerprint'] != build['repair']['initial_source_fingerprint']
            or old_build['expectations']['sha256'] != records['EXPECTATIONS.json']['sha256']
            or old_build['expectations']['spec_sha256'] != old_spec['spec_sha256']
            or canonical_sha({k: v for k, v in old_spec.items() if k != 'spec_sha256'}) != old_spec['spec_sha256']):
        raise ValueError('Initial pending build/spec provenance differs')
    validate_repair_contract(old_spec, spec)
    repaired = build['repair']['native']['repair']
    targets = repair_targets(spec)
    owner_after = (build['naming_repair']['native']['repair']['before_parts']
                   if build.get('naming_repair') else build['parts'])
    if (repaired['before_parts'] != old_build['parts'] or repaired['after_parts'] != owner_after
            or repaired['spec_sha256'] != spec['upgrade_attributes']['spec_sha256']
            or repaired['old_upgrade_spec_sha256'] != old_spec['upgrade_attributes']['spec_sha256']
            or set(old_build['parts']) != set(owner_after)
            or any(owner_after[name] != row for name, row in old_build['parts'].items() if name not in targets)):
        raise ValueError('Repair provenance changed outside the authorized owner bytes')
    if build.get('naming_repair'):
        phase = build['naming_repair']
        record = phase['before_build']
        path = member_path(directory, record['file'])
        if (record['file'] != 'BUILD_BEFORE_NAMING.json' or path.stat().st_size != record['bytes']
                or digest(path) != record['sha256']):
            raise ValueError('Before-naming build evidence changed')
        previous = read(path)
        names = phase['native']['repair']
        targets = naming_targets(spec)
        naming_after = (build['defaults_repair']['native']['repair']['before_parts']
                        if build.get('defaults_repair') else build['parts'])
        logical_targets = {node['file'] for node in spec['layout']['nodes']
                           if node['id'] == 'CONSTRUCTION' or node['id'] in
                           {'SECTION_PS%02d' % i for i in range(10, 14)}}
        if (previous['status'] != 'BUILT_PENDING_VERIFICATION' or previous.get('naming_repair')
                or previous['repair'] != build['repair'] or previous['parts'] != owner_after
                or previous['expectations'] != build['expectations']
                or names['before_parts'] != previous['parts'] or names['after_parts'] != naming_after
                or names['spec_sha256'] != spec['upgrade_attributes']['spec_sha256']
                or names['status'] != 'INSTANCE_NAMES_REPAIRED_PENDING_FRESH_VERIFY'
                or set(names['saved_parts']) != logical_targets or len(names['saved_parts']) != 5
                or names['unchanged_parts'] != 362 or len(names['instance_names']) != 28
                or names['source_bytes_unchanged'] is not True
                or set(owner_after) != set(naming_after)
                or any(naming_after[name] != row for name, row in owner_after.items() if name not in targets)):
            raise ValueError('Naming repair chain differs or changed an unauthorized Part')
        validate_naming_instances(names, spec)
    if build.get('defaults_repair'):
        from .integration import validate_section_defaults_evidence
        phase = build['defaults_repair']
        record = phase['before_build']
        path = member_path(directory, record['file'])
        if (not build.get('naming_repair') or record['file'] != 'BUILD_BEFORE_DEFAULTS.json'
                or path.stat().st_size != record['bytes'] or digest(path) != record['sha256']):
            raise ValueError('Before-defaults build evidence changed')
        previous = read(path)
        repaired = phase['native']['repair']
        before = build['naming_repair']['native']['repair']['after_parts']
        targets = defaults_targets(spec)
        logical_targets = {node['file'] for node in spec['layout']['nodes']
                           if node['id'] in ('SECTION_PS12', 'SECTION_PS13')}
        if (previous['status'] != 'BUILT_PENDING_VERIFICATION' or previous.get('defaults_repair')
                or previous['repair'] != build['repair'] or previous['naming_repair'] != build['naming_repair']
                or previous['parts'] != before or previous['expectations'] != build['expectations']
                or repaired['before_parts'] != before or repaired['after_parts'] != build['parts']
                or repaired['status'] != 'SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY'
                or repaired['spec_sha256'] != spec['upgrade_attributes']['spec_sha256']
                or set(repaired['saved_parts']) != logical_targets or len(repaired['saved_parts']) != 2
                or repaired['unchanged_parts'] != 365 or repaired['source_bytes_unchanged'] is not True
                or set(before) != set(build['parts'])
                or any(build['parts'][name] != row for name, row in before.items() if name not in targets)):
            raise ValueError('Section-default repair chain differs or changed an unauthorized Part')
        validate_section_defaults_evidence(spec, repaired)


def preserve_initial(directory, filename, archive_name=None):
    """Keep the exact previous evidence; never overwrite an initial record."""
    source = Path(directory) / filename
    target = source.with_name(archive_name or source.stem + '_INITIAL.json')
    original = source.read_bytes()
    if target.exists():
        if target.read_bytes() != original:
            raise ValueError('An initial evidence record already exists with different bytes')
    else:
        with target.open('xb') as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    return {'file': target.name, 'bytes': len(original), 'sha256': digest(target)}


def validate_section_smoke_record(spec, smoke, parts):
    if (smoke['schema'] != 'EXPLICIT_SECTION_DIAGNOSTIC_V1' or smoke['status'] != 'PARTIAL_DIAGNOSTIC'
            or smoke['scope_only'] is not True or smoke['complete_release'] is not False
            or smoke['construction_release'] is not False
            or smoke['saved_by_inspector'] is not False or smoke['verification_spec_sha256'] != spec['spec_sha256']
            or smoke['file_manifest'] != parts or smoke['file_manifest_after'] != parts
            or smoke['byte_guards'] != {'target_parts_unchanged': True, 'original_source_unchanged': True}
            or set(smoke['sections']) != {'SECTION_PS12', 'SECTION_PS13'}
            or any(row['cold_open'] is not True for row in smoke['sections'].values())):
        raise ValueError('Missing exact read-only two-section diagnostic proof')


def run_section_smoke(nx_root, directory, scratch, spec, build):
    result = run_native(nx_root, {'mode': 'section_smoke', 'directory': str(directory),
                                 'verification_spec': spec}, scratch, 'section_smoke')
    smoke = result['diagnostic']
    validate_section_smoke_record(spec, smoke, build['parts'])
    return smoke


def complete_candidate(nx_root, directory, scratch, spec, build, base, source_before,
                       fingerprint, plan, prepared, site_entry, attempt, *, default_first=False,
                       section_smoke_required=False):
    """The same full and relocated native release gate for builds and repairs."""
    def full_phase():
        return run_native(nx_root, {'mode': 'full_verify', 'directory': str(directory),
                                   'verification_spec': spec}, scratch, 'full_verify')
    def default_phase():
        relocated = scratch / 'relocated'
        relocated.mkdir()
        for name, row in build['parts'].items():
            target = relocated / name
            shutil.copyfile(directory / name, target)
            if target.stat().st_size != row['bytes'] or digest(target) != row['sha256']:
                raise ValueError('Moved native Part bytes changed: ' + name)
        return run_native(nx_root, {'mode': 'default_verify', 'directory': str(relocated),
                                    'verification_spec': spec}, scratch, 'relocated_default')
    if section_smoke_required:
        smoke = run_section_smoke(nx_root, directory, scratch, spec, build)
        build['defaults_repair']['smoke'] = smoke
        build['defaults_repair']['smoke_report_sha256'] = digest(scratch / 'section_smoke_result.json')
        write(directory / 'BUILD.json', build)
    if default_first:
        moved = default_phase()
        full = full_phase()
    else:
        full = full_phase()
        moved = default_phase()
    if inventory(base) != source_before or inventory(directory) != build['parts']:
        raise ValueError('Source or delivery bytes changed during native verification')
    if source_fingerprint(base, plan, prepared, site_entry) != fingerprint:
        raise ValueError('Source/code changed during the native run')
    verify = {'schema': 'M02_VERIFY_V2', 'status': 'PASS', 'source_fingerprint': fingerprint,
              'construction_release': False, 'full': full, 'relocated_default': moved,
              'source_bytes_unchanged': True, 'delivery_bytes_unchanged': True}
    released = dict(build, status='PASS')
    errors = validate_evidence(directory, released, verify, fingerprint)
    if errors:
        raise ValueError('; '.join(errors))
    write(directory / 'BUILD.json', released)
    write(directory / 'VERIFY.json', verify)
    write(directory.parent / 'LAST_ATTEMPT.json', dict(attempt, status='PASS'))
    write(directory.parent / 'CURRENT.json', {'directory': directory.name,
          'master': directory.name + '/' + spec['file_map'][spec['layout']['master']], 'revision': 'M02',
          'source_fingerprint': fingerprint})
    return directory


def repair_extension(nx_root, accept, candidate_path, *, naming=False, defaults=False):
    """Repair owner metadata or native instance names in one unpublished candidate."""
    if not accept:
        raise ValueError('Explicit display assumptions acceptance is required')
    nx_root = Path(nx_root).resolve()
    if not (nx_root / 'NXBIN/run_journal.exe').is_file():
        raise ValueError('NX journal executable is missing')
    from .geometry import create_plan
    from .integration import prepare_upgrade
    from .verification import verification_spec
    from renovierung.m01.layout import create_layout
    directory = member_path(ROOT, candidate_path)
    lock = Path(os.environ['LOCALAPPDATA']) / 'CodexNX/run_journal.lock'
    with exclusive_build(lock):
        build = read(directory / 'BUILD.json')
        old_spec = read(directory / 'EXPECTATIONS.json')
        validate_repair_candidate(directory, build, old_spec, naming=naming, defaults=defaults)
        base = member_path(ROOT, build['base_source'])
        baseline = source_record(base)
        validate_base_layout(baseline, create_layout(ROOT))
        source_before = inventory(base)
        if digest(base / 'BUILD.json') != build['base_build_sha256'] or source_before != build['base_source_parts']:
            raise ValueError('Original baseline build or source bytes changed')
        plan = json_contract(create_plan(ROOT, include_mesh=True))
        check_pinned_review(plan)
        prepared = current_field_inputs(plan)
        site_entry = compact_site(old_spec['site_entry'])
        if (canonical_sha(plan) != build['plan_sha256'] or prepared['fields'] != old_spec['prepared_fields']
                or any(site_entry.get(k) != v for k, v in _current_site(plan).items() if k != 'mesh')):
            raise ValueError('Candidate planning, native leaves or shared-ground sources changed')
        upgrade = prepare_upgrade(baseline['layout'], plan, prepared, site_entry)
        upgrade['copy_evidence'] = old_spec['copy_evidence']
        spec = json_contract(verification_spec(upgrade, prepared, site_entry,
                                              old_spec['copy_evidence']['copied_parts']))
        if naming or defaults:
            if spec != old_spec:
                raise ValueError('Naming/default repair requires the unchanged complete verification contract')
        else:
            validate_repair_contract(old_spec, spec)
        classification = assert_counts(spec)
        fingerprint = source_fingerprint(base, plan, prepared, site_entry)
        # Recheck all initial bytes after the lengthy canonical source calculation.
        validate_repair_candidate(directory, build, old_spec, naming=naming, defaults=defaults)
        if defaults:
            initial = preserve_initial(directory, 'BUILD.json', 'BUILD_BEFORE_DEFAULTS.json')
            mode, targets = 'repair_section_defaults', defaults_targets(spec)
        elif naming:
            initial = preserve_initial(directory, 'BUILD.json', 'BUILD_BEFORE_NAMING.json')
            mode, targets = 'repair_instance_names', naming_targets(spec)
        else:
            initial = {name: preserve_initial(directory, name) for name in ('BUILD.json', 'EXPECTATIONS.json')}
            mode, targets = 'repair_existing', repair_targets(spec)
        scratch = ROOT / 'reports/local/m02_extension' / (directory.name + '_repair_' + uuid.uuid4().hex[:6])
        scratch.mkdir(parents=True, exist_ok=False)
        attempt = {'status': 'RUNNING', 'mode': mode, 'directory': directory.name,
                   'source_fingerprint': fingerprint, 'base_source': build['base_source']}
        write(directory.parent / 'LAST_ATTEMPT.json', attempt)
        try:
            repaired = run_repair_native(nx_root, {'mode': mode, 'directory': str(directory),
                        'new_upgrade': upgrade, 'old_verification_spec': old_spec, 'verification_spec': old_spec,
                        'before_manifest': build['parts']}, scratch, directory, build['parts'], base,
                        source_before, targets)
            if not naming and not defaults:
                write(directory / 'EXPECTATIONS.json', spec)
            expectation_path = directory / 'EXPECTATIONS.json'
            updated = dict(build, status='BUILT_PENDING_VERIFICATION', source_fingerprint=fingerprint,
                           classification=classification, counts=spec['counts'], parts=inventory(directory),
                           expectations={'file': expectation_path.name, 'bytes': expectation_path.stat().st_size,
                             'sha256': digest(expectation_path), 'spec_sha256': spec['spec_sha256']})
            report_hash = digest(scratch / (mode + '_result.json'))
            if defaults:
                updated['defaults_repair'] = {'before_build': initial, 'native': repaired, 'report_sha256': report_hash}
            elif naming:
                updated['naming_repair'] = {'before_build': initial, 'native': repaired, 'report_sha256': report_hash}
            else:
                updated['repair'] = {'initial_records': initial, 'initial_source_fingerprint': build['source_fingerprint'],
                                     'native': repaired, 'report_sha256': report_hash}
            write(directory / 'BUILD.json', updated)
            return complete_candidate(nx_root, directory, scratch, spec, updated, base, source_before,
                                      fingerprint, plan, prepared, site_entry, attempt, default_first=defaults,
                                      section_smoke_required=defaults)
        except Exception as error:
            write(directory.parent / 'LAST_ATTEMPT.json', dict(attempt, status='FAIL', error=str(error)))
            raise


def build_extension(nx_root, accept, base_path=DEFAULT_BASE, reuse_assets=None):
    if not accept:
        raise ValueError('Explicit display assumptions acceptance is required')
    nx_root = Path(nx_root).resolve()
    if not (nx_root / 'NXBIN/run_journal.exe').is_file():
        raise ValueError('NX journal executable is missing')
    from .geometry import create_plan
    from .integration import prepare_upgrade
    from .verification import verification_spec
    from renovierung.m01.layout import create_layout
    base = member_path(ROOT, base_path).resolve()
    baseline = source_record(base)
    validate_base_layout(baseline, create_layout(ROOT))
    source_before = inventory(base)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:6]
    directory = ROOT / 'cad/nx/m02' / stamp
    scratch = ROOT / 'reports/local/m02_extension' / stamp
    pointer = directory.parent
    lock = Path(os.environ['LOCALAPPDATA']) / 'CodexNX/run_journal.lock'
    with exclusive_build(lock):
        scratch.mkdir(parents=True, exist_ok=False)
        attempt = {'status': 'RUNNING', 'directory': stamp, 'base_source': base.relative_to(ROOT).as_posix()}
        write(pointer / 'LAST_ATTEMPT.json', attempt)
        try:
            plan = json_contract(create_plan(ROOT, include_mesh=True))
            check_pinned_review(plan)
            if reuse_assets is None:
                prepared, site_entry, assets, provenance = _build_assets(nx_root, plan, scratch)
            else:
                prepared, site_entry, assets, provenance = _reuse_assets(reuse_assets, plan)
            upgrade = prepare_upgrade(baseline['layout'], plan, prepared, site_entry)
            fingerprint = source_fingerprint(base, plan, prepared, site_entry)
            attempt['source_fingerprint'] = fingerprint
            write(pointer / 'LAST_ATTEMPT.json', attempt)
            identity = {name: name for name in baseline['delivery_file_map'].values()}
            clone = run_native(nx_root, {'mode': 'clone', 'directory': str(directory),
                               'source_directory': str(base),
                               'physical_base_layout': physical_layout(baseline['layout'], baseline['delivery_file_map']),
                               'physical_file_map': identity}, scratch, 'clone')
            copied = inventory(directory)
            if len(copied) != 318 or set(assets) != set(upgrade['new_leaf_files']):
                raise ValueError('Independent clone or new asset inventory differs')
            for name, source in assets.items():
                target = directory / name
                if target.exists():
                    raise ValueError('Refusing to overwrite a native asset: ' + name)
                shutil.copyfile(source, target)
                if digest(source) != digest(target):
                    raise ValueError('Native asset changed while copying: ' + name)
            new_parts = {name: {'bytes': (directory / name).stat().st_size, 'sha256': digest(directory / name)}
                         for name in assets}
            upgrade['copy_evidence'] = {
                'schema': 'ANBAU_M01_INDEPENDENT_COPY_V1', 'source_root': str(base),
                'destination_root': str(directory), 'native_clone_completed': True, 'native_independent': True,
                'base_layout_sha256': upgrade['base_layout_sha256'], 'source_parts': source_before,
                'copied_parts': copied, 'new_parts': new_parts,
                'clone_report_path': str(scratch / 'clone_result.json'),
                'clone_report_sha256': digest(scratch / 'clone_result.json')}
            spec = json_contract(verification_spec(upgrade, prepared, site_entry, copied))
            classification = assert_counts(spec)
            expectation_path = directory / 'EXPECTATIONS.json'
            write(expectation_path, spec)
            expectation = {'file': expectation_path.name, 'bytes': expectation_path.stat().st_size,
                           'sha256': digest(expectation_path), 'spec_sha256': spec['spec_sha256']}
            upgraded = run_native(nx_root, {'mode': 'upgrade', 'directory': str(directory), 'spec': upgrade},
                                  scratch, 'upgrade')
            build = {'schema': 'M02_BUILD_V2', 'status': 'BUILT_PENDING_VERIFICATION',
                     'construction_release': False, 'native_NX_run_completed': True,
                     'source_fingerprint': fingerprint, 'base_source': base.relative_to(ROOT).as_posix(),
                     'base_build_sha256': digest(base / 'BUILD.json'), 'base_source_parts': source_before,
                     'base_claim': 'COMPLETE_318_PART_BUILD_CANDIDATE_NOT_FULL_M01_RELEASE',
                     'plan_sha256': canonical_sha(plan), 'expectations': expectation,
                     'classification': classification, 'counts': spec['counts'], 'asset_provenance': provenance,
                     'clone': clone, 'upgrade': upgraded, 'parts': inventory(directory)}
            write(directory / 'BUILD.json', build)
            return complete_candidate(nx_root, directory, scratch, spec, build, base, source_before,
                                      fingerprint, plan, prepared, site_entry, attempt)
        except Exception as error:
            write(pointer / 'LAST_ATTEMPT.json', dict(attempt, status='FAIL', error=str(error)))
            raise


def check_extension():
    """Regenerate current expectations without requiring ignored local inputs."""
    try:
        from .geometry import create_plan
        from .integration import prepare_upgrade
        from .verification import verification_spec
        from renovierung.m01.layout import create_layout
        pointer = ROOT / 'cad/nx/m02'
        current = read(pointer / 'CURRENT.json')
        attempt = read(pointer / 'LAST_ATTEMPT.json')
        if attempt.get('status') != 'PASS' or attempt.get('directory') != current['directory']:
            raise ValueError('Latest M02 attempt is not the verified CURRENT revision')
        directory = member_path(pointer, current['directory'])
        build, verify = read(directory / 'BUILD.json'), read(directory / 'VERIFY.json')
        saved = read(member_path(directory, build['expectations']['file']))
        base = member_path(ROOT, build['base_source'])
        baseline = source_record(base)
        validate_base_layout(baseline, create_layout(ROOT))
        if digest(base / 'BUILD.json') != build['base_build_sha256'] or inventory(base) != build['base_source_parts']:
            raise ValueError('Original build-candidate provenance/bytes changed')
        plan = json_contract(create_plan(ROOT, include_mesh=True))
        check_pinned_review(plan)
        prepared = current_field_inputs(plan)
        if prepared['fields'] != saved['prepared_fields']:
            raise ValueError('Current canonical field specifications changed')
        site_entry = saved['site_entry']
        if any(site_entry.get(key) != value for key, value in _current_site(plan).items() if key != 'mesh'):
            raise ValueError('Current shared-ground geometry/masks changed')
        upgrade = prepare_upgrade(baseline['layout'], plan, prepared, site_entry)
        upgrade['copy_evidence'] = saved['copy_evidence']
        rebuilt = json_contract(verification_spec(upgrade, prepared, site_entry,
                                                  saved['copy_evidence']['copied_parts']))
        if rebuilt != saved:
            raise ValueError('Independent expectations no longer match current inputs/generators')
        fingerprint = source_fingerprint(base, plan, prepared, site_entry)
        master = saved['file_map'][saved['layout']['master']]
        if current.get('master') != current['directory'] + '/' + master:
            raise ValueError('M02 CURRENT master differs')
        return validate_evidence(directory, build, verify, fingerprint)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as error:
        return ['M02: ' + str(error)]
