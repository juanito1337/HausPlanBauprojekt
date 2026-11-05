"""Native disk-to-disk packaging only; never generates geometry or saves Parts.

The default uses the already proven full UFClone path. Optional byte-preserving
leaves use documented CLONE Action.REPLACE, not USE_EXISTING (import/export only).
No fallback rewrites a partly created target. A failed optimization must be
retried explicitly in a different empty target with preserve_leaf_bytes=False.
PACKED is not the subsequent native shape/default-opening acceptance.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import traceback


class FlatPackError(RuntimeError):
    def __init__(self, evidence):
        self.evidence = evidence
        super().__init__('%s: %s' % (evidence['stage'], evidence['error']))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def _relative(name, flat=False):
    _require(isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_/-]+\.prt', name),
             'Unsafe canonical/physical Part path: ' + repr(name))
    parts = name.split('/')
    _require(not name.startswith('/') and all(p not in ('', '.', '..') for p in parts)
             and (not flat or len(parts) == 1), 'Physical Part path must be flat: ' + name)
    return name


def _member(root, canonical):
    result = root
    for part in PurePosixPath(_relative(canonical)).parts:
        result = result/part
        _require(not result.is_symlink(), 'Symlink Part path refused: ' + canonical)
    _require(result.resolve().is_relative_to(root), 'Part path escaped its root')
    return result


def _parts(root):
    result = {}
    for path in root.rglob('*'):
        _require(not path.is_symlink(), 'Symlink delivery entry refused: ' + str(path))
        if path.is_file() and path.suffix.lower() == '.prt':
            name = path.relative_to(root).as_posix()
            _relative(name)
            result[name] = {'bytes': path.stat().st_size, 'sha256': _digest(path)}
            _require(result[name]['bytes'] > 0, 'Empty Part: ' + name)
    return result


def plan_flat_pack(source, target, layout, file_map):
    """Pure preflight: snapshot every source and prove bijection without writes."""
    source_arg, target_arg = Path(source), Path(target)
    _require(not source_arg.is_symlink() and not target_arg.is_symlink(), 'Symlink roots refused')
    source, target = source_arg.resolve(), target_arg.resolve()
    _require(source.is_dir(), 'Source Part directory missing')
    _require(source != target and not source.is_relative_to(target) and not target.is_relative_to(source),
             'Source and target must be disjoint directories')
    _require(not target.exists() or target.is_dir() and not any(target.iterdir()),
             'Target must be a new empty directory')
    nodes = layout['nodes']
    by_id = {n['id']: n for n in nodes}
    _require(len(by_id) == len(nodes) and 'MASTER' in by_id, 'Duplicate/missing canonical node IDs')
    _require([n['id'] for n in nodes if n['parent'] is None] == ['MASTER']
             and by_id['MASTER']['file'] == layout['master'], 'One canonical master required')
    for node in nodes:
        current, seen = node['id'], set()
        while current != 'MASTER':
            _require(current in by_id and current not in seen, 'Canonical hierarchy has a cycle/missing parent')
            seen.add(current)
            current = by_id[current]['parent']
    reviews = layout.get('review_masters', [])
    _require(len({r['id'] for r in reviews}) == len(reviews), 'Duplicate review IDs')
    review_files = [_relative(r['file']) for r in reviews]
    node_files = {_relative(n['file']) for n in nodes}
    _require(len(set(review_files)) == len(review_files) and not node_files.intersection(review_files),
             'Review/native paths collide')
    canonical = node_files | set(review_files)
    _require(isinstance(file_map, dict) and set(file_map) == canonical, 'Physical file map inventory differs')
    mapped = [_relative(v, flat=True) for v in file_map.values()]
    _require(len({p.casefold() for p in canonical}) == len(canonical)
             and len({p.casefold() for p in mapped}) == len(mapped), 'Case-insensitive Part names collide')
    source_parts = _parts(source)
    _require(set(source_parts) == canonical, 'Source Part inventory differs from canonical layout')
    parents = {n['parent'] for n in nodes}
    leaf_files = {n['file'] for n in nodes if n['id'] not in parents}
    # Shared study files are terminal role prototypes; wrappers always contain a
    # master reference and cannot be byte-preserved as an independent leaf.
    leaf_files -= {n['file'] for n in nodes if n['id'] in parents}
    return {'source': str(source), 'target': str(target), 'master': layout['master'],
            'file_map': dict(sorted(file_map.items())), 'source_parts': source_parts,
            'review_files': sorted(review_files), 'leaf_candidates': sorted(leaf_files),
            'canonical_layout_sha256': hashlib.sha256(json.dumps(layout, sort_keys=True,
                                        separators=(',', ':'), allow_nan=False).encode()).hexdigest()}


def check_source_unchanged(plan):
    try:
        actual = _parts(Path(plan['source']))
        return [] if actual == plan['source_parts'] else ['Source Part inventory/bytes changed']
    except (OSError, ValueError) as error:
        return ['Source recheck failed: ' + str(error)]


def check_clone_inventory(plan, actual_paths):
    actual = [str(Path(p).resolve()).casefold() for p in actual_paths]
    expected = {str(_member(Path(plan['source']), p).resolve()).casefold() for p in plan['file_map']}
    _require(len(actual) == len(set(actual)) and set(actual) == expected,
             'Clone inventory differs: missing, extra or duplicate source Parts')


def check_pack_outputs(plan, preserved):
    actual = _parts(Path(plan['target']))
    _require(set(actual) == set(plan['file_map'].values()), 'Flat output Part inventory differs')
    _require(set(preserved) <= set(plan['leaf_candidates']), 'Invalid preserved leaf inventory')
    rows = []
    for canonical, physical in plan['file_map'].items():
        before, after = plan['source_parts'][canonical], actual[physical]
        if canonical in preserved:
            _require(after == before, 'Byte-preserved leaf changed: ' + canonical)
        rows.append({'canonical': canonical, 'path': physical, **after,
                     'byte_preserved': canonical in preserved})
    return rows


def _session_guard(session):
    _require(session.IsBatch is True, 'Only an explicitly owned batch NX session is permitted')
    _require(not list(session.Parts), 'Fresh empty NX session required; no existing Parts will be closed')


def _close_source_parts(session, plan, include_output=False):
    import NXOpen
    allowed = {str(_member(Path(plan['source']), name)).casefold() for name in plan['file_map']}
    if include_output:
        allowed.update(str((Path(plan['target'])/name).resolve()).casefold()
                       for name in plan['file_map'].values())
    for part in session.Parts:
        _require(part.FullPath and str(Path(part.FullPath).resolve()).casefold() in allowed,
                 'Refusing to close a foreign or unsaved Part')
    session.Parts.CloseAll(NXOpen.BasePart.CloseModified.CloseModified, None)
    _require(not list(session.Parts), 'Owned source Parts did not unload')


def _inspect_independent_leaves(session, plan):
    """Actual read-only native dependency inspection, optional before byte copies."""
    import NXOpen
    records, accepted = {}, []
    try:
        for canonical in plan['leaf_candidates']:
            _require(not list(session.Parts), 'Source leaf inspection requires an empty session')
            path = _member(Path(plan['source']), canonical)
            part, status = session.Parts.OpenBase(str(path))
            try:
                _require(part is not None and status.NumberUnloadedParts == 0, 'Incomplete source leaf load: ' + canonical)
            finally:
                status.Dispose()
            _require(Path(part.FullPath).resolve() == path, 'NX resolved a different source leaf')
            root = part.ComponentAssembly.RootComponent
            record = {'fully_loaded': bool(part.IsFullyLoaded),
                      'millimeters': part.PartUnits == NXOpen.BasePart.Units.Millimeters,
                      'children': len(list(root.GetChildren())) if root is not None else 0,
                      'interpart_parents': [p.FullPath for p in part.GetInterpartParents()],
                      'expression_reference_count': len(list(part.Expressions.GetInterpartReferences()))}
            record['independent'] = (record['fully_loaded'] and record['millimeters']
                                     and record['children'] == 0 and not record['interpart_parents']
                                     and record['expression_reference_count'] == 0)
            records[canonical] = record
            if record['independent']:
                accepted.append(canonical)
            _close_source_parts(session, plan)
    finally:
        if list(session.Parts):
            _close_source_parts(session, plan)
    return accepted, records


def _clone_inventory(clone, expected_count):
    actual, exhausted = [], False
    clone.StartIteration()
    try:
        while True:
            name = clone.Iterate()
            if name is None or name == '':
                exhausted = True
                break
            _require(isinstance(name, str), 'Unexpected UFClone.Iterate return: ' + repr(name))
            actual.append(name)
            _require(len(actual) <= expected_count, 'Clone inventory has unexpected extra Parts')
    finally:
        # UFClone automatically ends a fully exhausted iteration.
        if not exhausted:
            clone.StopIteration()
    return actual


def build_flat_pack(session, source, target, layout, file_map, *, preserve_leaf_bytes=False):
    """Return PACKED transfer evidence; raise FlatPackError with .evidence on failure.

    A caller must separately verify native geometry, metadata, arrangements and
    normal/default opening of all entry Parts, including after moving the folder.
    No layout/metadata attributes are rewritten. No Part.Save or source mutation.
    """
    evidence = {'schema': 'M01_FLAT_PACK_V1', 'status': 'FAIL', 'stage': 'session_guard',
                'native_geometry_verified': False, 'default_opening_verified': False,
                'construction_release': False, 'preserve_leaf_bytes_requested': preserve_leaf_bytes}
    plan, clone, initialized = None, None, False
    try:
        _session_guard(session)
        _require(type(preserve_leaf_bytes) is bool, 'Explicit boolean leaf-preservation option required')
        evidence['stage'] = 'filesystem_preflight'
        plan = plan_flat_pack(source, target, layout, file_map)
        evidence.update(deepcopy(plan))
        import NXOpen
        import NXOpen.UF
        options = session.Parts.LoadOptions
        options.ComponentLoadMethod = NXOpen.LoadOptions.LoadMethod.SearchDirectories
        directories = sorted({str(_member(Path(plan['source']), name).parent) for name in plan['file_map']})
        options.SetSearchDirectories(directories, [False]*len(directories))
        options.ComponentsToLoad = NXOpen.LoadOptions.LoadComponents.All
        options.UsePartialLoading = False
        options.UseLightweightRepresentations = False
        evidence['source_load_options'] = {'method': 'SearchDirectories', 'all_components': True,
                                            'partial': False, 'lightweight': False}
        preserved, independence = [], {}
        if preserve_leaf_bytes:
            evidence['stage'] = 'native_leaf_independence'
            preserved, independence = _inspect_independent_leaves(session, plan)
        evidence['leaf_independence'] = independence
        evidence['preserved_leaf_files'] = preserved
        _require(not list(session.Parts), 'UFClone must start with no loaded Parts')
        _require(not check_source_unchanged(plan), 'Sources changed before UFClone')
        evidence['stage'] = 'clone_inventory'
        clone = NXOpen.UF.UFSession.GetUFSession().Clone
        clone.Initialise(clone.OperationClass.CLONE_OPERATION)
        initialized = True
        clone.SetDefAction(clone.Action.CLONE)
        load, code = clone.AddAssembly(str(_member(Path(plan['source']), plan['master'])))
        evidence['add_master'] = {'code': code, 'failed': bool(load.Failed),
                                  'user_abort': bool(load.UserAbort), 'part_errors': load.NParts}
        _require(not code and not load.Failed and not load.UserAbort and not load.NParts,
                 'UFClone source master has load errors: ' + repr(evidence['add_master']))
        for canonical in plan['review_files']:
            code = clone.AddPart(str(_member(Path(plan['source']), canonical)))
            _require(code is None or code == 0, 'UFClone.AddPart failed: ' + canonical + ' ' + repr(code))
        check_clone_inventory(plan, _clone_inventory(clone, len(plan['file_map'])))
        evidence['clone_inventory_count'] = len(plan['file_map'])
        evidence['stage'] = 'target_creation'
        target_root = Path(plan['target'])
        target_root.mkdir(parents=True, exist_ok=True)
        _require(not any(target_root.iterdir()), 'Target ceased to be empty before transfer')
        if preserved:
            _require(hasattr(clone.Action, 'REPLACE') and hasattr(clone, 'SetAction'),
                     'UFClone CLONE replacement action is unavailable; use a new full-clone target')
            for canonical in preserved:
                destination = target_root/plan['file_map'][canonical]
                original = _member(Path(plan['source']), canonical)
                with original.open('rb') as incoming, destination.open('xb') as outgoing:
                    for block in iter(lambda: incoming.read(1024*1024), b''):
                        outgoing.write(block)
                _require(_digest(destination) == plan['source_parts'][canonical]['sha256'],
                         'Precopied independent leaf differs: ' + canonical)
        evidence['stage'] = 'clone_naming'
        for canonical in preserved:
            clone.SetAction(str(_member(Path(plan['source']), canonical)), clone.Action.REPLACE,
                            str(target_root/plan['file_map'][canonical]))
        for canonical, physical in plan['file_map'].items():
            if canonical not in preserved:
                clone.SetNaming(str(_member(Path(plan['source']), canonical)),
                                clone.NamingTechnique.USER_NAME, str(target_root/physical))
        evidence['strategy'] = 'BYTECOPY_INDEPENDENT_LEAVES_AND_REPLACE' if preserved else 'FULL_NATIVE_CLONE'
        evidence['stage'] = 'native_clone'
        failures = clone.PerformClone(clone.InitNamingFailures())
        evidence['naming_failures'] = {'count': failures.NFailures,
                                       'statuses': list(failures.Statuses) if failures.NFailures else []}
        _require(not failures.NFailures, 'UFClone naming/clone failures: ' + repr(evidence['naming_failures']))
        evidence['native_clone_completed'] = True
        clone.Terminate()
        initialized = False
        evidence['stage'] = 'owned_session_cleanup'
        evidence['parts_loaded_by_clone'] = [part.FullPath for part in session.Parts]
        if list(session.Parts):
            _close_source_parts(session, plan, include_output=True)
        evidence['stage'] = 'output_inventory_and_source_recheck'
        evidence['parts'] = check_pack_outputs(plan, preserved)
        changes = check_source_unchanged(plan)
        _require(not changes, '; '.join(changes))
        evidence.update(status='PACKED', stage='complete', native_clone_completed=True,
                        source_bytes_unchanged=True, output_part_count=len(evidence['parts']))
        return evidence
    except Exception as error:
        evidence.update(status='FAIL', error=type(error).__name__ + ': ' + str(error),
                        traceback=traceback.format_exc())
        evidence.setdefault('native_clone_completed', False)
        if plan is not None:
            changes = check_source_unchanged(plan)
            evidence['source_recheck_errors'] = changes
            evidence['source_bytes_unchanged'] = not changes
            try:
                evidence['target_parts_after_failure'] = _parts(Path(plan['target']))
            except (OSError, ValueError) as secondary:
                evidence['target_inventory_error'] = str(secondary)
        raise FlatPackError(evidence) from error
    finally:
        if initialized:
            try:
                clone.Terminate()
            except Exception as error:
                evidence['clone_termination_error'] = str(error)
