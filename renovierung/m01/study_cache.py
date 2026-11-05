"""Verify saved field studies against original K02 solids before reuse.

Compare absolute face boundaries, role volumes, references and presentation.
Unusable candidates revert to an independent copy for the ordinary build.
"""
import hashlib
import json
import math
from pathlib import Path

from renovierung.m01.context_cache import RUN, _canonical, _inside, _same_path


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _request(repo, run):
    if not isinstance(run, str) or not RUN.fullmatch(run):
        raise ValueError('Explicit own source run is required')
    scratch, delivery = _inside(repo, 'reports/local/m01', run), _inside(repo, 'cad/nx/m01', run)
    label = 'build' if _inside(scratch,'build_request.json').is_file() else 'generate'
    request = _read(_inside(scratch, label+'_request.json'))
    if request.get('mode') != label or request.get('load_method') != 'AsSaved':
        raise ValueError('Source is not a native build request')
    for key, expected in (('repo_root', repo), ('directory', delivery), ('report', scratch / (label+'_result.json'))):
        _same_path(request.get(key), expected)
    result = _inside(scratch, label+'_result.json')
    interruption = _inside(scratch, 'INTERRUPTED.json')
    stopped = _read(interruption) if interruption.is_file() else {}
    if not ((result.is_file() and _read(result).get('status') in ('PASS', 'FAIL'))
            or (stopped.get('status') == 'INTERRUPTED' and stopped.get('directory') == run
                and stopped.get('process_exited') is True)):
        raise ValueError('Source run is still running or has no terminal evidence')
    return request, scratch, delivery


def _contract(layout, fid):
    fields = [f for f in layout['fields'] if f['id'] == fid and f['native'] is True]
    if len(fields) != 1:
        raise ValueError('Exactly one native field required')
    field = fields[0]
    roles = sorted((n for n in layout['nodes'] if n['parent'] == field['node_id']), key=lambda n: n['id'])
    sources = [s for s in layout['sources'] if s['file'] == field['study_file']]
    if (len(roles) != 4 or {n['role'] for n in roles} != {'cut_soil', 'excavation', 'pile_main', 'pile_reserve'}
            or any(n['kind'] != 'role' or n['file'] != field['study_file'] for n in roles)
            or len(sources) != 1 or field['study_file'] != 'studien/' + fid + '_STUDY.prt'):
        raise ValueError('Native study role/source contract differs')
    return {'field': field, 'roles': roles, 'source': sources[0], 'presentation': layout['presentation']}


def _k02_bytes(repo, source):
    path = _inside(repo, source['source'])
    path.relative_to(repo / 'cad/nx/k02')
    data = path.read_bytes()
    if len(data) != source['bytes'] or _sha(data) != source['sha256']:
        raise ValueError('Genuine K02 source bytes changed')
    return data


def capture_inventory(repo_root, source_run):
    """Explicitly document completed candidate hashes after the source has exited."""
    repo = Path(repo_root).resolve()
    request, _, delivery = _request(repo, source_run)
    result = {'source_run': source_run, 'parts': {}}
    for field in request['layout']['fields']:
        if not field['native']:
            continue
        contract = _contract(request['layout'], field['id'])
        _k02_bytes(repo, contract['source'])
        path = _inside(delivery, field['study_file'])
        if path.is_file():
            stat, data = path.stat(), path.read_bytes()
            if (data and _sha(data) != contract['source']['sha256']
                    and path.stat().st_mtime_ns == stat.st_mtime_ns and len(data) == stat.st_size):
                result['parts'][field['id']] = {'file': field['study_file'], 'bytes': len(data), 'sha256': _sha(data)}
    return result


def prepare_study_cache(repo_root, source_run, destination, layout, pile_steps, inventory):
    """Copy only matching, previously documented candidates into empty new targets."""
    repo, root = Path(repo_root).resolve(), Path(destination).resolve()
    old, old_scratch, delivery = _request(repo, source_run)
    if (not RUN.fullmatch(root.name) or source_run >= root.name
            or root != _inside(repo, 'cad/nx/m01', root.name) or not root.is_dir()
            or inventory.get('source_run') != source_run):
        raise ValueError('Invalid new delivery/source inventory')
    records, copies = {}, []
    for fid, documented in inventory['parts'].items():
        try:
            previous, current = _contract(old['layout'], fid), _contract(layout, fid)
        except ValueError:
            continue
        if _canonical(previous) != _canonical(current):
            continue
        raw = _k02_bytes(repo, current['source'])
        old_step = _inside(old_scratch, 'pile_steps', fid + '.step')
        new_step = _inside(repo, 'reports/local/m01', root.name, 'pile_steps', fid + '.step')
        _same_path(old['pile_steps'][fid], old_step)
        _same_path(pile_steps[fid], new_step)
        if not old_step.is_file() or not new_step.is_file() or old_step.read_bytes() != new_step.read_bytes():
            continue
        origin, target = _inside(delivery, documented['file']), _inside(root, current['field']['study_file'])
        if documented['file'] != current['field']['study_file'] or not origin.is_file():
            continue
        data = origin.read_bytes()
        if len(data) != documented['bytes'] or _sha(data) != documented['sha256']:
            continue
        if target.exists():
            raise ValueError('Refusing to overwrite any existing study target')
        record = dict(documented, source_run=source_run, k02_sha256=_sha(raw),
                      step_sha256=_sha(new_step.read_bytes()), contract_sha256=_sha(_canonical(current).encode()))
        copies.append((fid, origin, target, data, record))
    for fid, origin, target, data, record in copies:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        if origin.read_bytes() != data or target.read_bytes() != data:
            raise ValueError('Candidate changed while copying')
        records[fid] = record
    return records


def boundary_signature(faces):
    result = []
    for edges in faces:
        face = []
        for edge in edges:
            if len(edge) != 2 or any(len(p) != 3 or any(not math.isfinite(v) for v in p) for p in edge):
                raise ValueError('Invalid finite ABS boundary coordinates')
            face.append(sorted(tuple(round(v, 6) for v in p) for p in edge))
        if not face:
            raise ValueError('Missing face boundary')
        result.append(sorted(face))
    if not result:
        raise ValueError('Missing native faces')
    return _sha(_canonical(sorted(result)).encode())


def _native_signature(body):
    import NXOpen
    faces = []
    for face in body.GetFaces():
        if face.SolidFaceType != NXOpen.Face.FaceType.Planar:
            raise ValueError('Non-planar retained body: clean boundary comparison unavailable')
        edges = []
        for edge in face.GetEdges():
            if edge.SolidEdgeType != NXOpen.Edge.EdgeType.Linear:
                raise ValueError('Nonlinear retained boundary: clean comparison unavailable')
            edges.append([[p.X, p.Y, p.Z] for p in edge.GetVertices()])
        faces.append(edges)
    return boundary_signature(faces)


def verify_study_native(session, candidate, baseline, contract):
    """Fresh real checks; baseline must be a separate own K02 comparison copy."""
    import NXOpen
    import NXOpen.Facet
    from renovierung.k02.nx_verify import body_role, measure
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.nx_journal import display_part, validate_refset_members
    from renovierung.m01.presentation import read_presentation
    from renovierung.m01.inspection import _check_presentation
    from renovierung.m01.pile_native import inspect_piles
    field = contract['field']
    for part in (candidate, baseline):
        root = part.ComponentAssembly.RootComponent
        if (not part.IsFullyLoaded or part.PartUnits != NXOpen.BasePart.Units.Millimeters
                or (root is not None and root.GetChildren()) or list(part.GetInterpartParents())
                or list(part.Expressions.GetInterpartReferences())):
            raise ValueError('Cached study/baseline is not an independent mm leaf')
    signatures = {}
    for role in ('cut_soil', 'excavation'):
        native = [{b.Name: b for b in part.Bodies if body_role(b.Name) == role} for part in (baseline, candidate)]
        if not native[0] or set(native[0]) != set(native[1]):
            raise ValueError('Retained K02 body names differ')
        records = []
        for part, bodies in zip((baseline, candidate), native):
            display_part(session, part)
            validate_measurement(measure(list(bodies.values())), field['measurements'][role]['component_volumes_m3'])
            records.append({name: _native_signature(body) for name, body in bodies.items()})
        if records[0] != records[1]:
            raise ValueError('Retained K02 ABS face boundaries differ')
        signatures[role] = records[0]
    display_part(session, candidate)
    locations = inspect_piles(candidate, field)
    _check_presentation(read_presentation(candidate), contract['presentation'])
    sets = {r.Name: r for r in candidate.GetAllReferenceSets()}
    if {n for n in sets if n.startswith('M01_')} != {r['reference_set'] for r in contract['roles']}:
        raise ValueError('Cached study M01 refset inventory differs')
    for row in contract['roles']:
        bodies = [b for b in candidate.Bodies if body_role(b.Name) == row['role']]
        if any(b.IsBlanked or b.Layer != {'cut_soil': 101, 'excavation': 102, 'pile_main': 103, 'pile_reserve': 104}[row['role']] for b in bodies):
            raise ValueError('Cached active role layer/Blank differs')
        validate_measurement(measure(bodies), field['measurements'][row['role']]['component_volumes_m3'])
        members = []
        for member in sets[row['reference_set']].AskAllDirectMembers():
            record = {'tag': member.Tag, 'kind': 'other'}
            if isinstance(member, NXOpen.Body):
                record['kind'] = 'body'
            elif isinstance(member, NXOpen.Facet.FacetedBody):
                loaded = bool(member.IsAssociatedBodyLoaded)
                record.update(kind='facet', associated_loaded=loaded,
                              associated_tag=member.AssociatedBody.Tag if loaded else None)
            members.append(record)
        validate_refset_members({b.Tag: b.Name for b in bodies}, members)
    return {'retained_absolute_boundary_sha256': signatures, 'pile_locations': locations,
            'presentation': read_presentation(candidate)}


def load_cached_study(session, repo_root, root, layout, fid, record):
    """Validate candidate or restore ONLY this generated target for a cold rebuild."""
    import NXOpen
    from renovierung.m01.nx_journal import display_part, load_leaf
    repo, root = Path(repo_root).resolve(), Path(root).resolve()
    contract = _contract(layout, fid)
    if root != _inside(repo, 'cad/nx/m01', root.name) or not RUN.fullmatch(root.name):
        raise ValueError('Wrong cache destination root')
    if (not isinstance(record.get('source_run'), str) or not RUN.fullmatch(record['source_run'])
            or record['source_run'] >= root.name):
        raise ValueError('Cache source run provenance differs')
    previous, old_scratch, old_delivery = _request(repo, record['source_run'])
    if _canonical(_contract(previous['layout'], fid)) != _canonical(contract):
        raise ValueError('Prior/new field contract changed after preparation')
    old_part = _inside(old_delivery, contract['field']['study_file'])
    old_step = _inside(old_scratch, 'pile_steps', fid + '.step')
    _same_path(previous['pile_steps'][fid], old_step)
    if _sha(old_part.read_bytes()) != record['sha256'] or _sha(old_step.read_bytes()) != record['step_sha256']:
        raise ValueError('Prior study/STEP bytes changed after preparation')
    raw = _k02_bytes(repo, contract['source'])
    step = _inside(repo, 'reports/local/m01', root.name, 'pile_steps', fid + '.step')
    path = _inside(root, contract['field']['study_file'])
    data = path.read_bytes()
    if (record['file'] != contract['field']['study_file'] or len(data) != record['bytes']
            or _sha(data) != record['sha256'] or _sha(raw) != record['k02_sha256']
            or _sha(step.read_bytes()) != record['step_sha256']
            or _sha(_canonical(contract).encode()) != record['contract_sha256']):
        raise ValueError('Study cache provenance/bytes changed')
    if any(p.FullPath and Path(p.FullPath).resolve() == path for p in session.Parts):
        raise ValueError('Cached study requires fresh loading before assembly insertion')
    compare_path = _inside(repo, 'reports/local/m01', root.name, 'study_compare',
                           'K02_COMPARE_' + fid.replace('-', '_') + '.prt')
    compare_path.parent.mkdir(parents=True, exist_ok=True)
    if compare_path.exists():
        raise ValueError('Refusing to overwrite an existing K02 comparison Part')
    with compare_path.open('xb') as stream:
        stream.write(raw)
    candidate, baseline, rejected, baseline_owned = None, None, None, False
    try:
        candidate = load_leaf(session, path)
        if Path(candidate.FullPath).resolve() != path:
            raise ValueError('NX opened a different candidate Part; refusing comparison/close')
        baseline = load_leaf(session, compare_path)
        if Path(baseline.FullPath).resolve() != compare_path:
            raise ValueError('NX opened a different comparison Part; refusing close')
        baseline_owned = True
        try:
            evidence = verify_study_native(session, candidate, baseline, contract)
        except (ValueError, NXOpen.NXException) as error:
            rejected = str(error)
        display_part(session, candidate)
    finally:
        if baseline_owned:
            baseline.Close(NXOpen.BasePart.CloseWholeTree.FalseValue, NXOpen.BasePart.CloseModified.CloseModified, None)
        if compare_path.read_bytes() != raw or path.read_bytes() != data:
            raise ValueError('Read-only cached-study comparison changed native bytes')
    if rejected is None:
        return candidate, evidence
    # No assembly references it yet; exact hash guard proves this is still our
    # untouched generated candidate, never an existing user-owned target.
    candidate.Close(NXOpen.BasePart.CloseWholeTree.FalseValue, NXOpen.BasePart.CloseModified.CloseModified, None)
    if path.read_bytes() != data:
        raise ValueError('Refusing to replace a changed candidate after rejection')
    path.unlink()
    with path.open('xb') as stream:
        stream.write(raw)
    return None, {'cold_fallback_reason': rejected}
