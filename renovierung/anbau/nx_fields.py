"""Compact native Anbau field leaves, never snapshots or house copies.

prepare_inputs(plan, new_scratch) is pure transfer preparation. Native callers
use build_field(session, output_path, entry) and inspect_field(session, part,
entry). Four M01 role refsets share each free study leaf. Blocked modeled fields
receive only a separate red diagnostic leaf, never effective sand quantities.

Closed cut-soil components are imported independently: the wall-line height
discontinuity must not be united or bridged. Native cut+exc mass is checked
against the artificial uncut study-soil input, not against earthwork quantities.
NXOpen imports stay inside native functions. No function closes any Part.
"""
import hashlib
import itertools
import json
import math
from pathlib import Path
import re


ROLES = ('cut_soil', 'excavation', 'pile_main', 'pile_reserve')
REFSETS = {role: 'M01_' + role.upper() for role in ROLES}
LAYERS = {'cut_soil': 101, 'excavation': 102, 'pile_main': 103, 'pile_reserve': 104}
COLORS = {'cut_soil': 110, 'excavation': 186, 'pile_main': 75, 'pile_reserve': 36}
CONFLICT_LAYER, CONFLICT_COLOR = 240, 186
CAD_TOLERANCE_MM = 0.25


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _point(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 3
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in value)):
        raise ValueError('Expected finite registered XYZ coordinates')
    return list(value)


def _record(row):
    from renovierung.k02.runner import validate_measurement
    result = {key: row[key] for key in ('body_count', 'volume_m3', 'component_volumes_m3')}
    validate_measurement(result, result['component_volumes_m3'])
    return result


def _geometry(row):
    from renovierung.k02.geometry import validate_mesh
    from renovierung.k02.runner import validate_measurement
    wanted = _record(row)
    measured = validate_mesh(row['mesh'])
    actual = {'body_count': measured['expected_body_count'], 'volume_m3': measured['volume_mm3']/1e9,
              'component_volumes_m3': sorted(v/1e9 for v in measured['component_volumes_mm3'])}
    validate_measurement(actual, wanted['component_volumes_m3'])
    points = row['mesh']['vertices']
    box = [min(p[k] for p in points) for k in range(3)] + [max(p[k] for p in points) for k in range(3)]
    if (not isinstance(row['bbox_mm'], list) or len(row['bbox_mm']) != 6
            or any(type(v) not in (int, float) or not math.isfinite(v) or abs(a-v) > 1e-7
                   for a, v in zip(box, row['bbox_mm']))):
        raise ValueError('Geometry component bounding box differs')
    return dict(wanted, bbox_mm=list(row['bbox_mm']))


def field_spec(field):
    """Validate one explicit field and return a small mesh-free native contract."""
    try:
        fid = field['id']
        if (not isinstance(fid, str) or not re.fullmatch(r'PS1[0-3]-F[0-9]{2}', fid)
                or field['sector_id'] != fid.split('-')[0]
                or type(field['native_candidate']) is not bool or type(field['diagnostic_only']) is not bool
                or field['construction_release'] is not False
                or type(field['assumed_slab_underside_z_mm']) not in (int, float)
                or type(field['formation_z_mm']) not in (int, float)
                or not math.isfinite(field['assumed_slab_underside_z_mm'])
                or not math.isfinite(field['formation_z_mm'])
                or not math.isclose(field['assumed_slab_underside_z_mm']-field['formation_z_mm'], 100.0,
                                    rel_tol=0.0, abs_tol=1e-8)
                or not isinstance(field['blockers'], list) or not isinstance(field['conflicts'], list)):
            raise ValueError('Unsafe Anbau field identity/depth/classification')
        native, diagnostic = field['native_candidate'], field['diagnostic_only']
        if (native and (diagnostic or field['blockers'] or field['conflicts'])
                or not native and (field['volume_m3'] is not None or field['measurements'])):
            raise ValueError('Blocked fields must not carry effective quantities')
        marker = field['display_marker']
        line = [_point(p) for p in marker['line']]
        if len(line) != 2 or sum((a-b)**2 for a, b in zip(*line)) <= 1e-12:
            raise ValueError('Registered field marker must be a nonzero line')
        marker = {'line': line, 'label': _point(marker['label'])}
        geometry, measurements = {}, {}
        if native:
            for role in ('soil', *ROLES):
                geometry[role] = _geometry(field['geometry'][role])
            if set(field['measurements']) != set(ROLES):
                raise ValueError('Free field requires all four explicit role measurements')
            from renovierung.k02.runner import validate_measurement
            for role in ROLES:
                measurements[role] = _record(field['measurements'][role])
                validate_measurement(measurements[role], geometry[role]['component_volumes_m3'])
            excavation = geometry['excavation']['volume_m3']
            if (type(field['volume_m3']) not in (int, float)
                    or not math.isfinite(field['volume_m3'])
                    or abs(field['volume_m3']-excavation) > max(1e-9, excavation*1e-6)
                    or abs(geometry['soil']['volume_m3']-geometry['cut_soil']['volume_m3']-excavation)
                    > max(1e-9, excavation*1e-6)):
                raise ValueError('Study cut/excavation/soil mass balance differs')
            for role, pile in field.get('display_stockpile', {}).items():
                if role in ('pile_main', 'pile_reserve'):
                    if pile['bbox_mm'] != geometry[role]['bbox_mm']:
                        raise ValueError('Pile A location differs from role geometry')
            mode, filename, imports, refsets = 'STUDY', fid+'_STUDY.prt', list(ROLES), dict(REFSETS)
        elif diagnostic:
            if not field['blockers'] and not field['conflicts']:
                raise ValueError('Diagnostic field needs an explicit block/conflict')
            if any(role in field['geometry'] for role in ('pile_main', 'pile_reserve')):
                raise ValueError('Blocked field must not invent a native sand pile')
            geometry['excavation'] = _geometry(field['geometry']['excavation'])
            if not math.isclose(field['diagnostic_volume_m3'], geometry['excavation']['volume_m3'],
                                rel_tol=1e-6, abs_tol=1e-10):
                raise ValueError('Diagnostic volume differs from hypothetical geometry')
            mode, filename, imports, refsets = 'CONFLICT_DIAGNOSTIC', fid+'_CONFLICT.prt', ['excavation'], {'conflict': 'ANBAU_CONFLICT'}
        else:
            mode, filename, imports, refsets = 'REGISTER_ONLY', None, [], {}
        metadata = {key: value for key, value in field.items() if key != 'geometry'}
        metadata['geometry'] = geometry
        return {'schema': 'ANBAU_NATIVE_FIELD_V1', 'id': fid, 'sector_id': field['sector_id'],
                'mode': mode, 'file': filename, 'construction_method': 'DIRECT_CUT_COMPONENTS' if native else mode,
                'import_roles': imports, 'refsets': refsets, 'measurements': measurements,
                'geometry': geometry, 'display_marker': marker, 'field_metadata': metadata,
                'field_sha256': _digest(_canonical(field).encode()), 'construction_release': False,
                'effective_excavation_m3': field['volume_m3'] if native else None,
                'effective_sand_m3': {r: geometry[r]['volume_m3'] for r in ('pile_main', 'pile_reserve')} if native else {}}
    except (KeyError, TypeError, AttributeError, OverflowError) as error:
        raise ValueError('Malformed Anbau field: ' + str(error)) from error


def _volumes(values):
    if not isinstance(values, list) or not values or any(type(v) not in (int, float)
                       or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Expected positive finite component volumes')
    return values


def _match(values, expected):
    return len(values) == len(expected) and all(abs(a-b) <= max(1e-10, abs(b)*1e-6)
                                               for a, b in zip(sorted(values), sorted(expected)))


def assign_import_roles(values, expected):
    """Require a unique component-volume partition; never infer iterator roles."""
    _volumes(values)
    if not expected or any(role not in ('soil', *ROLES) for role in expected):
        raise ValueError('Unknown imported role inventory')
    for components in expected.values():
        _volumes(components)
    if len(values) != sum(len(v) for v in expected.values()):
        raise ValueError('Imported component count differs')
    roles, solutions = list(expected), []
    def visit(index, remaining, selected):
        if len(solutions) > 1:
            return
        role = roles[index]
        for group in itertools.combinations(remaining, len(expected[role])):
            if not _match([values[i] for i in group], expected[role]):
                continue
            rest = [i for i in remaining if i not in group]
            assignment = dict(selected, **{role: list(group)})
            if index+1 == len(roles):
                if not rest:
                    solutions.append(assignment)
            else:
                visit(index+1, rest, assignment)
    visit(0, list(range(len(values))), {})
    if len(solutions) != 1:
        raise ValueError('Imported role/component volumes are missing or ambiguous')
    return solutions[0]


def _joined(meshes):
    result = {'vertices': [], 'faces': []}
    for mesh in meshes:
        offset = len(result['vertices'])
        result['vertices'].extend(list(p) for p in mesh['vertices'])
        result['faces'].extend([[offset+i for i in face] for face in mesh['faces']])
    return result


def prepare_inputs(plan, scratch):
    """Write only new local STEP inputs; no NX execution or native success claim."""
    from renovierung.k02.mesh_step import write_step
    from renovierung.m01.presentation import camera_spec
    scratch = Path(scratch).resolve()
    fields = plan['fields']
    if len({f['id'] for f in fields}) != len(fields):
        raise ValueError('Duplicate Anbau field IDs')
    specs = {f['id']: field_spec(f) for f in fields}
    if scratch.exists():
        raise ValueError('Refusing to overwrite prepared field inputs')
    scratch.mkdir(parents=True)
    corners = []
    for spec in specs.values():
        for row in spec['geometry'].values():
            box = row['bbox_mm']
            corners.extend([box[:3], box[3:]])
    presentation = plan.get('presentation') or (camera_spec(corners) if corners else None)
    result = {'schema': 'ANBAU_FIELD_INPUTS_V1', 'plan_sha256': _digest(_canonical(plan).encode()),
              'fields': {}, 'register_only_ids': [], 'presentation': presentation}
    for field in sorted(fields, key=lambda f: f['id']):
        fid, spec = field['id'], specs[field['id']]
        if spec['file'] is None:
            result['register_only_ids'].append(fid)
            continue
        roles = spec['import_roles']
        expected = {role: spec['geometry'][role]['component_volumes_m3'] for role in roles}
        try:
            assign_import_roles([v for role in roles for v in expected[role]], expected)
            batches = [roles]
            transfer = 'COMBINED_ROLE_STEP'
        except ValueError:
            batches = [[role] for role in roles]
            transfer = 'SEPARATE_ROLE_STEPS'
        imports = []
        for batch in batches:
            name = fid + '_' + ('COMBINED' if len(batch) > 1 else batch[0].upper())
            path = scratch / (name + '.step')
            transfer_record = write_step(path, _joined([field['geometry'][role]['mesh'] for role in batch]), name)
            imports.append({'path': str(path), 'roles': list(batch),
                            'bytes': transfer_record['bytes'], 'sha256': transfer_record['sha256']})
        result['fields'][fid] = {'spec': spec, 'transfer_mode': transfer, 'imports': imports,
                                  'presentation': presentation}
    return result


def validate_native_result(spec, actual):
    """Validate measured records; only native inspection may establish them."""
    from renovierung.k02.runner import validate_measurement
    for key in ('id', 'file', 'mode', 'field_sha256'):
        if actual.get(key) != spec[key]:
            raise ValueError('Native Anbau field identity differs: ' + key)
    if (actual.get('construction_release') is not False or actual.get('all_parts_mm') is not True
            or actual.get('no_external_dependencies') is not True):
        raise ValueError('Native field units/dependencies/release differ')
    free = spec['mode'] == 'STUDY'
    roles = list(ROLES) if free else ['conflict']
    if set(actual['bodies']) != set(roles) or set(actual['native_bbox_mm']) != set(roles):
        raise ValueError('Native field role inventory differs')
    expected_sets = {}
    for role in roles:
        expected = spec['geometry'][role if free else 'excavation']
        bodies = actual['bodies'][role]
        prefix = 'K02_' + role.upper() if free else 'ANBAU_CONFLICT_EXCAVATION'
        names = {prefix+'_%02d' % i for i in range(expected['body_count'])}
        layer, color = (LAYERS[role], COLORS[role]) if free else (CONFLICT_LAYER, CONFLICT_COLOR)
        if (len(bodies) != expected['body_count'] or {b['name'] for b in bodies} != names
                or any(b['layer'] != layer or b['color'] != color or b['blank'] is not False for b in bodies)):
            raise ValueError('Native field names/layer/color/Blank differ: ' + role)
        box = actual['native_bbox_mm'][role]
        if (len(box) != 6 or any(type(a) not in (int, float) or not math.isfinite(a)
                or abs(a-b) > CAD_TOLERANCE_MM for a, b in zip(box, expected['bbox_mm']))):
            raise ValueError('Native field ABS bounding box differs: ' + role)
        expected_sets[spec['refsets'][role]] = sorted(names)
    if actual['refsets'] != expected_sets:
        raise ValueError('Native field reference-set body membership differs')
    if free:
        if set(actual['measurements']) != set(ROLES) or actual['diagnostic_measurement'] is not None:
            raise ValueError('Native free field needs four effective role measurements')
        for role in ROLES:
            validate_measurement(actual['measurements'][role], spec['geometry'][role]['component_volumes_m3'])
        excavation = actual['measurements']['excavation']['volume_m3']
        cut = actual['measurements']['cut_soil']['volume_m3']
        if (abs(spec['geometry']['soil']['volume_m3']-cut-excavation) > max(1e-9, excavation*1e-6)
                or actual['effective_excavation_m3'] != excavation
                or actual['effective_sand_m3'] != {r: actual['measurements'][r]['volume_m3']
                                                 for r in ('pile_main', 'pile_reserve')}):
            raise ValueError('Native effective quantities or study-soil balance differ')
    else:
        if actual['measurements'] or actual['effective_excavation_m3'] is not None or actual['effective_sand_m3']:
            raise ValueError('Blocked diagnostic must have no effective quantities')
        validate_measurement(actual['diagnostic_measurement'], spec['geometry']['excavation']['component_volumes_m3'])
    return actual


def _native_box(bodies):
    import NXOpen
    points = []
    for body in bodies:
        faces, edges = list(body.GetFaces()), list(body.GetEdges())
        if (not faces or not edges or any(f.SolidFaceType != NXOpen.Face.FaceType.Planar for f in faces)
                or any(e.SolidEdgeType != NXOpen.Edge.EdgeType.Linear for e in edges)):
            raise ValueError('Anbau mesh body needs planar faces and linear B-rep edges')
        points.extend([[p.X, p.Y, p.Z] for edge in edges for p in edge.GetVertices()])
    if not points:
        raise ValueError('Missing positive native field bodies')
    return [min(p[k] for p in points) for k in range(3)] + [max(p[k] for p in points) for k in range(3)]


def inspect_field(session, part, entry):
    """Read a displayed leaf's genuine B-reps, refsets, style and saved camera.

    The leaf is a role prototype: all four source roles remain unblanked for
    reference-set integration. The FIELD parent/master suppresses auxiliary
    excavation/reserve occurrences. This function never changes or saves them.
    """
    import NXOpen
    import NXOpen.Facet
    from renovierung.k02.nx_verify import measure
    from renovierung.m01.display import read_attribute
    from renovierung.m01.nx_journal import validate_refset_members
    from renovierung.m01.presentation import read_presentation
    from renovierung.m01.inspection import _check_presentation
    spec = entry['spec']
    if session.Parts.Display is None or session.Parts.Display.Tag != part.Tag:
        raise ValueError('Native Anbau inspection requires this Part displayed')
    session.Parts.SetWork(part)
    if read_attribute(part, 'ANBAU_FIELD_SPEC') != spec:
        raise ValueError('Saved Anbau field specification differs')
    root = part.ComponentAssembly.RootComponent
    independent = (not (root is not None and root.GetChildren()) and not list(part.GetInterpartParents())
                   and not list(part.Expressions.GetInterpartReferences()))
    free = spec['mode'] == 'STUDY'
    groups = {role: [] for role in (ROLES if free else ('conflict',))}
    all_bodies = list(part.Bodies)
    for body in all_bodies:
        matches = [role for role in groups if body.Name.startswith(
                    'K02_' + role.upper() + '_' if free else 'ANBAU_CONFLICT_EXCAVATION_')]
        if len(matches) != 1:
            raise ValueError('Unexpected native Anbau body: ' + body.Name)
        groups[matches[0]].append(body)
    measured = {role: measure(bodies) for role, bodies in groups.items()}
    sets = {r.Name: r for r in part.GetAllReferenceSets()}
    relevant = {name for name in sets if name.startswith(('M01_', 'ANBAU_'))}
    if relevant != set(spec['refsets'].values()):
        raise ValueError('Native Anbau reference-set inventory differs')
    refsets = {}
    for role, name in spec['refsets'].items():
        members = []
        for member in sets[name].AskAllDirectMembers():
            record = {'tag': member.Tag, 'kind': 'other'}
            if isinstance(member, NXOpen.Body):
                record['kind'] = 'body'
            elif isinstance(member, NXOpen.Facet.FacetedBody):
                loaded = bool(member.IsAssociatedBodyLoaded)
                record.update(kind='facet', associated_loaded=loaded,
                              associated_tag=member.AssociatedBody.Tag if loaded else None)
            members.append(record)
        validate_refset_members({b.Tag: b.Name for b in groups[role]}, members)
        refsets[name] = sorted(b.Name for b in groups[role])
    marker = [curve for curve in part.Curves if curve.Name == 'M01_REGISTER_' + spec['id']]
    if len(marker) != 1 or marker[0].Layer != 200 or marker[0].IsBlanked:
        raise ValueError('Native Anbau register marker is missing/hidden')
    actual_line = [[p.X, p.Y, p.Z] for p in (marker[0].StartPoint, marker[0].EndPoint)]
    if any(abs(a-b) > 1e-8 for p, q in zip(actual_line, spec['display_marker']['line']) for a, b in zip(p, q)):
        raise ValueError('Native Anbau marker moved away from registered field')
    presentation = read_presentation(part)
    _check_presentation(presentation, entry['presentation'])
    result = {'id': spec['id'], 'file': spec['file'], 'mode': spec['mode'],
              'construction_method': spec['construction_method'], 'construction_release': False,
              'field_sha256': spec['field_sha256'], 'all_parts_mm': part.PartUnits == NXOpen.BasePart.Units.Millimeters,
              'no_external_dependencies': independent, 'measurements': measured if free else {},
              'diagnostic_measurement': None if free else measured['conflict'],
              'effective_excavation_m3': measured['excavation']['volume_m3'] if free else None,
              'effective_sand_m3': {r: measured[r]['volume_m3'] for r in ('pile_main', 'pile_reserve')} if free else {},
              'bodies': {r: [{'name': b.Name, 'layer': b.Layer, 'color': b.Color, 'blank': bool(b.IsBlanked)}
                              for b in bodies] for r, bodies in groups.items()},
              'native_bbox_mm': {r: _native_box(bodies) for r, bodies in groups.items()},
              'refsets': refsets, 'presentation': presentation, 'display_marker': spec['display_marker']}
    return validate_native_result(spec, result)


def field_note_lines(spec):
    free = spec['mode'] == 'STUDY'
    field = spec['field_metadata']
    lines = [spec['id'] + (' ANBAU / STUDIE' if free else ' GESPERRT / ROTE KONFLIKTDIAGNOSE'),
             'UK %.2f m / Pruefsohle %.2f m rel. EG' %
             (field['assumed_slab_underside_z_mm']/1000, field['formation_z_mm']/1000),
             'Vorplanung - keine Ausfuehrungsfreigabe']
    if free:
        lines.append('Lager A - Bewuchsabstand oertlich pruefen')
    else:
        lines.append('Hypothetischer Konfliktkoerper - keine wirksame Sandmenge')
    return lines


def build_field(session, output_path, entry):
    """Create one new mm leaf; never save any pre-existing Part or source model."""
    import NXOpen
    import NXOpen.Layer
    from renovierung.k02.nx_build import import_mesh, note, save
    from renovierung.k02.nx_verify import measure
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.display import write_attribute
    from renovierung.m01.presentation import apply_presentation
    spec = entry['spec']
    path = Path(output_path).resolve()
    if not session.IsBatch or spec['mode'] == 'REGISTER_ONLY' or path.name != spec['file'] or path.exists():
        raise ValueError('Anbau generator needs an owned batch and a new exact field filename')
    planned_roles = [role for row in entry['imports'] for role in row['roles']]
    if len(planned_roles) != len(set(planned_roles)) or set(planned_roles) != set(spec['import_roles']):
        raise ValueError('Anbau transfer role inventory differs')
    for row in entry['imports']:
        data = Path(row['path']).read_bytes()
        if len(data) != row['bytes'] or _digest(data) != row['sha256']:
            raise ValueError('Prepared Anbau STEP input changed')
    path.parent.mkdir(parents=True, exist_ok=True)
    part = session.Parts.NewDisplay(str(path), NXOpen.Part.Units.Millimeters)
    session.Parts.SetWork(part)
    imported_roles = {}
    for row in entry['imports']:
        imported = import_mesh(session, part, row['path'], entry['nx_root'])
        values = [measure([body])['volume_m3'] for body in imported]
        expected = {r: spec['geometry'][r]['component_volumes_m3'] for r in row['roles']}
        assigned = assign_import_roles(values, expected)
        for role, indices in assigned.items():
            bodies = [imported[i] for i in indices]
            validate_measurement(measure(bodies), expected[role])
            imported_roles[role] = bodies
    free = spec['mode'] == 'STUDY'
    groups = imported_roles if free else {'conflict': imported_roles['excavation']}
    for role, bodies in groups.items():
        prefix = 'K02_' + role.upper() if free else 'ANBAU_CONFLICT_EXCAVATION'
        for index, body in enumerate(bodies):
            body.SetName(prefix+'_%02d' % index)
            body.Layer, body.Color = (LAYERS[role], COLORS[role]) if free else (CONFLICT_LAYER, CONFLICT_COLOR)
            body.Unblank()
        refset = part.CreateReferenceSet()
        refset.SetName(spec['refsets'][role])
        refset.AddObjectsToReferenceSet(bodies)
    marker = spec['display_marker']
    line = part.Curves.CreateLine(*(NXOpen.Point3d(*(float(v) for v in p)) for p in marker['line']))
    line.SetName('M01_REGISTER_' + spec['id'])
    line.Layer, line.Color = 200, (36 if free else CONFLICT_COLOR)
    lines = field_note_lines(spec)
    label = note(part, lines, [float(v) for v in marker['label']], 'ANBAU_NOTE_' + spec['id'], 200)
    label.Layer = 201
    write_attribute(part, 'ANBAU_FIELD_SPEC', spec)
    write_attribute(part, 'ANBAU_CONSTRUCTION_RELEASE', False)
    apply_presentation(part, entry['presentation'])
    if not free:
        part.Layers.SetState(CONFLICT_LAYER, NXOpen.Layer.State.Selectable)
    # Run genuine geometry checks before the first save and again on saved data.
    inspect_field(session, part, entry)
    save(part)
    result = inspect_field(session, part, entry)
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError('Native Anbau field was not saved')
    result.update(status='PASS', bytes=path.stat().st_size, sha256=_digest(path.read_bytes()))
    return part, result


def main():
    """Batch journal entry: ANBAU_NX_REQUEST points to explicit prepared inputs."""
    import os
    import sys
    import traceback
    request = json.loads(Path(os.environ['ANBAU_NX_REQUEST']).read_text(encoding='utf-8'))
    sys.path.insert(0, request['repo_root'])
    result = {'status': 'FAIL', 'construction_release': False, 'mode': request['mode']}
    try:
        import NXOpen
        session = NXOpen.Session.GetSession()
        if not session.IsBatch or list(session.Parts):
            raise ValueError('A fresh owned batch NX process is required')
        root = Path(request['directory']).resolve()
        entries = request['prepared']['fields']
        selected = request.get('field_ids', sorted(entries))
        if len(selected) != len(set(selected)) or set(selected)-set(entries):
            raise ValueError('Unknown/duplicate native Anbau pilot fields')
        results = {}
        for fid in selected:
            entry = dict(entries[fid], nx_root=request['nx_root'])
            path = root / entry['spec']['file']
            if request['mode'] == 'build':
                _, results[fid] = build_field(session, path, entry)
            elif request['mode'] == 'verify':
                before = path.read_bytes()
                part, status = session.Parts.OpenDisplay(str(path))
                try:
                    if status.NumberUnloadedParts:
                        raise ValueError('Saved Anbau leaf failed fresh loading')
                finally:
                    status.Dispose()
                results[fid] = inspect_field(session, part, entry)
                if path.read_bytes() != before:
                    raise ValueError('Read-only Anbau verification changed file bytes')
            else:
                raise ValueError('Unknown Anbau journal mode')
        result.update(status='PASS', fields=results, native_NX_run_completed=True,
                      files_saved=request['mode'] == 'build', plan_sha256=request['prepared']['plan_sha256'])
    except Exception as error:
        result.update(error=str(error), traceback=traceback.format_exc())
    Path(request['report']).write_text(json.dumps(result, indent=2), encoding='utf-8')
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
