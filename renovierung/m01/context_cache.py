"""Reuse identical terrain leaves from a named earlier M01 run.

Both STEP inputs must match byte-for-byte. Every candidate is freshly opened
in NX for identity, dependency, B-rep volume and presentation checks.
"""
import hashlib
import json
import os
from pathlib import Path
import re


RUN = re.compile(r'[0-9]{8}T[0-9]{6}Z_[0-9a-f]{6}')


def _json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _inside(root, *parts):
    path = root.joinpath(*parts).resolve()
    path.relative_to(root)
    return path


def _same_path(actual, expected):
    if not isinstance(actual, str) or Path(actual).resolve() != expected:
        raise ValueError('Cache request path differs: ' + str(expected))


def _inventory(layout):
    nodes = [n for n in layout['nodes'] if n['kind'] == 'context']
    groups = layout['context']['groups']
    by_node = {n['id']: n for n in nodes}
    by_group = {g['id']: g for g in groups}
    if len(by_node) != len(nodes) or len(by_group) != len(groups) or set(by_node) != set(by_group):
        raise ValueError('Context cache inventory differs or contains duplicate IDs')
    for gid, group in by_group.items():
        node = by_node[gid]
        if (not re.fullmatch(r'CONTEXT_[0-9]{3}', gid)
                or group['file'] != 'kontext/' + gid + '.prt'
                or node['file'] != group['file'] or node['parent'] != 'SITE_CONTEXT'
                or node['blank'] is not False or _canonical(node['metadata']) != _canonical(group)
                or any(n.get('parent') == gid for n in layout['nodes'])):
            raise ValueError('Unsafe or non-leaf context node: ' + gid)
    _canonical(layout['presentation'])
    return by_node, by_group


def prepare_context_cache(repo_root, source_run, destination, layout, context_steps):
    """Copy eligible candidates from one explicit finished prior build request.

    This authorizes no native acceptance and never edits source files or any
    existing destination Part. Returns only candidate byte/provenance records.
    """
    repo = Path(repo_root).resolve()
    destination = Path(destination).resolve()
    if (not isinstance(source_run, str) or not RUN.fullmatch(source_run)
            or not RUN.fullmatch(destination.name) or source_run >= destination.name):
        raise ValueError('Cache source must name an earlier own M01 run')
    scratch = _inside(repo, 'reports/local/m01', source_run)
    source = _inside(repo, 'cad/nx/m01', source_run)
    expected_target = _inside(repo, 'cad/nx/m01', destination.name)
    if destination != expected_target or not destination.is_dir() or not source.is_dir():
        raise ValueError('Cache destination/source must be existing own M01 delivery directories')
    label = 'build' if _inside(scratch,'build_request.json').is_file() else 'generate'
    previous = _json(_inside(scratch, label+'_request.json'))
    if previous.get('mode') != label or previous.get('load_method') != 'AsSaved':
        raise ValueError('Cache source is not an own native build request')
    for key, expected in (('repo_root', repo), ('directory', source), ('report', scratch / (label+'_result.json'))):
        _same_path(previous.get(key), expected)
    report_path = _inside(scratch, label+'_result.json')
    interrupted_path = _inside(scratch, 'INTERRUPTED.json')
    interrupted = (_json(interrupted_path) if interrupted_path.is_file() else {})
    recorded_interruption = (interrupted.get('status') == 'INTERRUPTED'
                             and interrupted.get('directory') == source_run
                             and interrupted.get('process_exited') is True)
    if not recorded_interruption and (not report_path.is_file() or _json(report_path).get('status') not in ('PASS', 'FAIL')):
        raise ValueError('Cache source has no terminal build report')
    old_nodes, old_groups = _inventory(previous['layout'])
    new_nodes, new_groups = _inventory(layout)
    if set(previous['context_steps']) != set(old_groups) or set(context_steps) != set(new_groups):
        raise ValueError('Context STEP inventory differs')
    new_scratch = _inside(repo, 'reports/local/m01', destination.name)
    for groups, steps, directory in ((old_groups, previous['context_steps'], scratch),
                                      (new_groups, context_steps, new_scratch)):
        for gid in groups:
            _same_path(steps[gid], _inside(directory, 'context_steps', gid + '.step'))
    same_presentation = _canonical(previous['layout']['presentation']) == _canonical(layout['presentation'])
    candidates = []
    for gid, group in new_groups.items():
        if (not same_presentation or gid not in old_groups
                or _canonical(old_nodes[gid]) != _canonical(new_nodes[gid])
                or _canonical(old_groups[gid]) != _canonical(group)):
            continue
        old_step, new_step = Path(previous['context_steps'][gid]), Path(context_steps[gid])
        if not old_step.is_file() or not new_step.is_file():
            continue
        old_bytes, new_bytes = old_step.read_bytes(), new_step.read_bytes()
        if old_bytes != new_bytes or _hash(old_bytes) != _hash(new_bytes):
            continue
        origin = _inside(source, group['file'])
        if not origin.is_file():
            continue
        target = _inside(destination, group['file'])
        if target.exists():
            raise ValueError('Refusing to overwrite a cached context destination: ' + group['file'])
        stat = origin.stat()
        data = origin.read_bytes()
        if not data or origin.stat().st_mtime_ns != stat.st_mtime_ns or len(data) != stat.st_size:
            raise ValueError('Candidate source is empty or still changing: ' + gid)
        record = {'file': group['file'], 'bytes': len(data), 'sha256': _hash(data),
                  'step_sha256': _hash(new_bytes), 'source_run': source_run}
        candidates.append((gid, origin, target, data, record))
    # Validate all paths/collisions before the first write; exclusive creation
    # still refuses a target that appears between the preflight and this loop.
    records = {}
    for gid, origin, target, data, record in candidates:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if origin.read_bytes() != data or target.read_bytes() != data:
            raise ValueError('Cache source/copy changed during transfer: ' + gid)
        records[gid] = record
    return records


def validate_native_record(row, group, presentation_spec, actual):
    """Pure acceptance contract; actual must come from a fresh real NX read."""
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.inspection import _check_presentation
    expected_attributes = {'M01_NODE_ID': row['id'], 'M01_KIND': 'context',
                           'M01_DEFAULT_BLANK': row['blank'], 'M01_NODE_METADATA': row}
    if (_canonical(actual['attributes']) != _canonical(expected_attributes)
            or actual['fully_loaded'] is not True or actual['millimeters'] is not True
            or actual['children'] or actual['interpart_parents'] or actual['expressions']
            or actual['expression_references']):
        raise ValueError('Cached native leaf identity/units/dependencies differ')
    bodies = actual['bodies']
    expected_names = {group['id'] + '_%03d' % index for index in range(group['body_count'])}
    if (len(bodies) != group['body_count'] or {body['name'] for body in bodies} != expected_names
            or any(body['layer'] != 210 or body['blank'] is not False for body in bodies)):
        raise ValueError('Cached native context body names/layers/visibility differ')
    validate_measurement(actual['measurement'], group['component_volumes_m3'])
    _check_presentation(actual['presentation'], presentation_spec)
    return actual


def _candidate_bytes(root, row, layout, record):
    nodes, _ = _inventory(layout)
    if row != nodes.get(row['id']) or record.get('file') != row['file']:
        raise ValueError('Cached context record/node differs')
    if (set(record) != {'file', 'bytes', 'sha256', 'step_sha256', 'source_run'}
            or not isinstance(record['source_run'], str) or not RUN.fullmatch(record['source_run'])
            or not RUN.fullmatch(root.name) or record['source_run'] >= root.name
            or type(record['bytes']) is not int or record['bytes'] <= 0
            or any(not isinstance(record[key], str) or not re.fullmatch(r'[0-9a-f]{64}', record[key])
                   for key in ('sha256', 'step_sha256'))):
        raise ValueError('Malformed cache candidate provenance')
    repo = root.parents[3]
    if root != _inside(repo, 'cad/nx/m01', root.name):
        raise ValueError('Cache native root is not the own M01 delivery')
    step = _inside(repo, 'reports/local/m01', root.name, 'context_steps', row['id'] + '.step')
    if _hash(step.read_bytes()) != record['step_sha256']:
        raise ValueError('Cached context STEP changed after runner preflight')
    data = _inside(root, record['file']).read_bytes()
    if len(data) != record['bytes'] or _hash(data) != record['sha256']:
        raise ValueError('Cached context copy bytes differ')
    return data


def load_cached_context(session, root, row, layout, record):
    """Open and verify the new delivery-local copy; never transform or save it.

    Returns (part, native_evidence). A failure aborts rather than overwriting
    the candidate with a cold import. No source/native-session success inferred.
    """
    import NXOpen
    from renovierung.k02.nx_verify import measure
    from renovierung.m01.display import read_attribute
    from renovierung.m01.presentation import read_presentation
    root = Path(root).resolve()
    _, groups = _inventory(layout)
    data = _candidate_bytes(root, row, layout, record)
    path = _inside(root, record['file'])
    if any(p.FullPath and Path(p.FullPath).resolve() == path for p in session.Parts):
        raise ValueError('Cached context must be freshly opened')
    part, status = session.Parts.OpenDisplay(str(path))
    try:
        if part is None or status.NumberUnloadedParts:
            raise ValueError('Cached native context did not load completely')
    finally:
        status.Dispose()
    try:
        root_component = part.ComponentAssembly.RootComponent
        actual = {'attributes': {key: read_attribute(part, key) for key in
                                 ('M01_NODE_ID', 'M01_KIND', 'M01_DEFAULT_BLANK', 'M01_NODE_METADATA')},
                  'fully_loaded': bool(part.IsFullyLoaded),
                  'millimeters': part.PartUnits == NXOpen.BasePart.Units.Millimeters,
                  'children': [child.Name for child in root_component.GetChildren()] if root_component else [],
                  'interpart_parents': [p.FullPath for p in part.GetInterpartParents()],
                  'expressions': [e.Name for e in part.Expressions],
                  'expression_references': list(part.Expressions.GetInterpartReferences()),
                  'bodies': [{'name': b.Name, 'layer': b.Layer, 'blank': bool(b.IsBlanked)} for b in part.Bodies],
                  'measurement': measure(list(part.Bodies)), 'presentation': read_presentation(part)}
        validate_native_record(row, groups[row['id']], layout['presentation'], actual)
        if Path(part.FullPath).resolve() != path:
            raise ValueError('NX opened a different cached context file')
        return part, actual
    finally:
        if path.read_bytes() != data:
            raise ValueError('Native cache inspection changed saved Part bytes')
