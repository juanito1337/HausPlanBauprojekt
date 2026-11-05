"""Own-copy native pile replacement and fresh-open location/history checks."""
import itertools
import math


PILE_ROLES = ('pile_main', 'pile_reserve')
HISTORICAL_LAYER = 251
CAD_TOLERANCE_MM = 0.25


def _volumes(values):
    if not values or any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('Pile component volumes must be finite and positive')
    return list(values)


def _matches(values, expected):
    return len(values) == len(expected) and all(abs(a-b) <= max(1e-10, abs(b)*1e-6)
                                               for a, b in zip(sorted(values), sorted(expected)))


def assign_roles(imported_volumes, expected):
    """Find exactly one volume-based body partition; iterator order has no role."""
    volumes = _volumes(imported_volumes)
    if set(expected) != set(PILE_ROLES):
        raise ValueError('Both pile role component lists are required')
    wanted = {role: _volumes(expected[role]) for role in PILE_ROLES}
    if len(volumes) != sum(len(v) for v in wanted.values()):
        raise ValueError('Imported pile component count differs')
    solutions = []
    for indices in itertools.combinations(range(len(volumes)), len(wanted['pile_main'])):
        rest = [i for i in range(len(volumes)) if i not in indices]
        if (_matches([volumes[i] for i in indices], wanted['pile_main'])
                and _matches([volumes[i] for i in rest], wanted['pile_reserve'])):
            solutions.append({'pile_main': list(indices), 'pile_reserve': rest})
            if len(solutions) > 1:
                raise ValueError('Ambiguous imported pile role/component volumes')
    if not solutions:
        raise ValueError('Imported pile component volumes do not identify both roles')
    return solutions[0]


def vertex_bbox(points):
    if (not points or any(len(p) != 3 or any(type(v) not in (int, float) or not math.isfinite(v)
                                          for v in p) for p in points)):
        raise ValueError('Expected finite B-rep vertex coordinates')
    return [min(p[i] for p in points) for i in range(3)] + [max(p[i] for p in points) for i in range(3)]


def _bbox(bodies):
    """Exact ABS AABB for generated planar, linear-edged B-rep mesh solids."""
    import NXOpen
    points = []
    for body in bodies:
        faces, edges = list(body.GetFaces()), list(body.GetEdges())
        if (not faces or not edges or any(f.SolidFaceType != NXOpen.Face.FaceType.Planar for f in faces)
                or any(e.SolidEdgeType != NXOpen.Edge.EdgeType.Linear for e in edges)):
            raise ValueError('Pile bounding box requires planar faces and linear B-rep edges')
        for edge in edges:
            points.extend([[p.X, p.Y, p.Z] for p in edge.GetVertices()])
    return vertex_bbox(points)


def _history_name(fid, role, index):
    return 'M01_HISTORICAL_CONFLICT_' + fid.replace('-', '_') + '_' + role.upper() + '_%02d' % index


def _relocation_metadata(field):
    return {'field_id': field['id'],
            'active': {role: field['display_stockpile'][role] for role in PILE_ROLES},
            'historical': {role: field['k02_pile_measurements'][role] for role in PILE_ROLES}}


def _nonpile_snapshot(part):
    from renovierung.k02.nx_verify import body_role, measure
    return {b.Tag: {'name': b.Name, 'measurement': measure([b])} for b in part.Bodies
            if body_role(b.Name) in ('cut_soil', 'excavation')}


def check_preserved(before, after):
    """Keep exact body identity; tolerate only tiny repeated mass-property roundoff."""
    if set(before) != set(after):
        raise ValueError('Pile replacement changed original cut-soil/excavation body tags')
    for tag, old in before.items():
        new = after[tag]
        a, b = old['measurement'], new['measurement']
        if (old['name'] != new['name'] or a['body_count'] != b['body_count']
                or len(a['component_volumes_m3']) != len(b['component_volumes_m3'])
                or any(not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12) for x, y in
                       zip(a['component_volumes_m3'] + [a['volume_m3']],
                           b['component_volumes_m3'] + [b['volume_m3']]))):
            raise ValueError('Pile replacement changed original cut-soil/excavation names or volumes')


def replace_piles(session, part, field, step_path, nx_root):
    """Mutate only the supplied new own-copy study; caller creates refs and saves."""
    import NXOpen.Layer
    from renovierung.k02.nx_build import import_mesh
    from renovierung.k02.nx_verify import body_role, measure
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.display import write_attribute
    preserved = _nonpile_snapshot(part)
    if not preserved or any(ref.Name.startswith('M01_') for ref in part.GetAllReferenceSets()):
        raise ValueError('Pile replacement requires fresh own-copy study before M01 reference sets')
    historical = {}
    for role in PILE_ROLES:
        bodies = sorted((b for b in part.Bodies if body_role(b.Name) == role), key=lambda b: b.Name)
        wanted = field['k02_pile_measurements'][role]
        if len(bodies) != wanted['body_count']:
            raise ValueError('Original K02 pile body count differs: ' + field['id'] + ' ' + role)
        validate_measurement(measure(bodies), wanted['component_volumes_m3'])
        historical[role] = bodies
    for role, bodies in historical.items():
        for index, body in enumerate(bodies):
            body.SetName(_history_name(field['id'], role, index))
            body.Layer = HISTORICAL_LAYER
            body.Blank()
    part.Layers.SetState(HISTORICAL_LAYER, NXOpen.Layer.State.Hidden)
    imported = import_mesh(session, part, str(step_path), nx_root)
    values = [measure([body])['volume_m3'] for body in imported]
    assigned = assign_roles(values, {role: field['measurements'][role]['component_volumes_m3']
                                    for role in PILE_ROLES})
    for role in PILE_ROLES:
        for index, imported_index in enumerate(assigned[role]):
            body = imported[imported_index]
            body.SetName('K02_' + role.upper() + '_%02d' % index)
            body.Layer, body.Color = (103, 75) if role == 'pile_main' else (104, 36)
            # Prototype geometry is available in both role reference sets;
            # reserve visibility is controlled by its role occurrence.
            body.Unblank()
    after = _nonpile_snapshot(part)
    check_preserved(preserved, after)
    write_attribute(part, 'M01_PILE_RELOCATION', _relocation_metadata(field))
    return inspect_piles(part, field, check_reference_sets=False)


def inspect_piles(part, field, check_reference_sets=True):
    """Read active ABS B-rep boxes and exact hidden historical groups after reopen."""
    import NXOpen
    import NXOpen.Facet
    import NXOpen.Layer
    from renovierung.k02.nx_verify import body_role, measure
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.display import read_attribute
    if read_attribute(part, 'M01_PILE_RELOCATION') != _relocation_metadata(field):
        raise ValueError('Saved pile relocation metadata differs: ' + field['id'])
    all_bodies = list(part.Bodies)
    record, historical_tags, recognized = {}, set(), set()
    for role in PILE_ROLES:
        active = [body for body in all_bodies if body_role(body.Name) == role]
        wanted = field['measurements'][role]
        expected_names = {'K02_' + role.upper() + '_%02d' % index for index in range(wanted['body_count'])}
        layer = 103 if role == 'pile_main' else 104
        if (len(active) != wanted['body_count'] or {b.Name for b in active} != expected_names
                or any(b.Layer != layer or b.IsBlanked for b in active)):
            raise ValueError('Active pile names/layer/Blank differ: ' + field['id'] + ' ' + role)
        validate_measurement(measure(active), wanted['component_volumes_m3'])
        box = _bbox(active)
        expected_box = field['display_stockpile'][role]['bbox_mm']
        if (not isinstance(expected_box, list) or len(expected_box) != 6
                or any(type(b) not in (int, float) or not math.isfinite(b)
                       or abs(a-b) > CAD_TOLERANCE_MM for a, b in zip(box, expected_box))):
            raise ValueError('Active pile ABS bounding box differs: ' + field['id'] + ' ' + role)
        record[role] = {'bbox_mm': box, 'body_count': len(active)}
        recognized.update(b.Tag for b in active)
        old = field['k02_pile_measurements'][role]
        names = {_history_name(field['id'], role, index) for index in range(old['body_count'])}
        hidden = [body for body in all_bodies if body.Name in names]
        if (len(hidden) != old['body_count'] or {b.Name for b in hidden} != names
                or any(b.Layer != HISTORICAL_LAYER or not b.IsBlanked for b in hidden)):
            raise ValueError('Historical conflict pile names/layer/Blank differ: ' + field['id'] + ' ' + role)
        validate_measurement(measure(hidden), old['component_volumes_m3'])
        historical_tags.update(b.Tag for b in hidden)
        recognized.update(b.Tag for b in hidden)
    recognized.update(b.Tag for b in all_bodies if body_role(b.Name) in ('cut_soil', 'excavation'))
    if recognized != {b.Tag for b in all_bodies}:
        raise ValueError('Unexpected extra study bodies outside active/history roles: ' + field['id'])
    if part.Layers.GetState(HISTORICAL_LAYER) != NXOpen.Layer.State.Hidden:
        raise ValueError('Historical conflict layer is not hidden: ' + field['id'])
    if check_reference_sets:
        for reference_set in part.GetAllReferenceSets():
            if not reference_set.Name.startswith('M01_'):
                continue
            for member in reference_set.AskAllDirectMembers():
                associated = (member.AssociatedBody if isinstance(member, NXOpen.Facet.FacetedBody)
                              and member.IsAssociatedBodyLoaded else None)
                if member.Tag in historical_tags or (associated is not None and associated.Tag in historical_tags):
                    raise ValueError('Historical conflict body belongs to an active M01 reference set')
    record['historical_hidden'] = {role: field['k02_pile_measurements'][role]['body_count'] for role in PILE_ROLES}
    return record
