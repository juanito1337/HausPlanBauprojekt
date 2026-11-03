"""Build or independently inspect one M01 delivery in a fresh native NX process."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import traceback


MATRIX_KEYS = ('Xx', 'Xy', 'Xz', 'Yx', 'Yy', 'Yz', 'Zx', 'Zy', 'Zz')
IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]


def internal(root, path):
    value = Path(path).resolve()
    return value.relative_to(root).as_posix()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sorted_nodes(layout):
    """Topological order, independently refusing unknown parents and cycles."""
    wanted = {row['id']: row for row in layout['nodes']}
    if len(wanted) != len(layout['nodes']):
        raise ValueError('Duplicate layout node IDs')
    pending, result, seen = list(layout['nodes']), [], set()
    while pending:
        ready = [r for r in pending if r['parent'] is None or r['parent'] in seen]
        if not ready:
            raise ValueError('Layout cycle or unknown parent')
        for row in ready:
            result.append(row)
            seen.add(row['id'])
            pending.remove(row)
    if [r['id'] for r in result if r['parent'] is None] != ['MASTER']:
        raise ValueError('Exactly one MASTER root required')
    return result


def metadata(obj, row, fields, rooms):
    from renovierung.m01.display import write_attribute as attribute
    for key, value in {'M01_NODE_ID': row['id'], 'M01_KIND': row['kind'],
                       'M01_DEFAULT_BLANK': row['blank'], 'M01_NODE_METADATA': row}.items():
        attribute(obj, key, value)
    if row['kind'] == 'field':
        field = fields[row['id']]
        attribute(obj, 'M01_FIELD_ID', field['id'])
        attribute(obj, 'M01_FIELD_NATIVE', field['native'])
        attribute(obj, 'M01_FIELD_METADATA', field)
    if row['kind'] == 'room':
        attribute(obj, 'M01_ROOM_METADATA', rooms[row['id']])


def associated_rows(layout, key):
    return {row['node_id']: row for row in layout[key]}


def display_part(session, part):
    _, status = session.Parts.SetDisplay(part, False, False)
    if status is not None:
        try:
            if status.NumberUnloadedParts:
                raise ValueError('Display switch left unloaded parts')
        finally:
            status.Dispose()
    if session.Parts.Display.Tag != part.Tag:
        raise ValueError('NX did not display intended part')
    session.Parts.SetWork(part)


def load_leaf(session, path):
    part, status = session.Parts.OpenDisplay(str(path))
    try:
        if part is None or status.NumberUnloadedParts:
            raise ValueError('Source leaf not fully loaded: '+str(path))
    finally:
        status.Dispose()
    if part.ComponentAssembly.RootComponent is not None and part.ComponentAssembly.RootComponent.GetChildren():
        raise ValueError('M01 sources must be leaf parts: '+str(path))
    return part


def build(session, root, layout):
    import NXOpen
    from renovierung.k02.nx_build import save
    from renovierung.k02.nx_verify import body_role
    from renovierung.m01.display import (PROJECT, apply_visibility, components,
                                         set_blank, write_attribute as attribute)
    rows = sorted_nodes(layout)
    fields, rooms = associated_rows(layout, 'fields'), associated_rows(layout, 'rooms')
    source_rows = {r['file']: r for r in layout['sources']}
    expected_files = {r['file'] for r in rows}
    if set(source_rows) - expected_files:
        raise ValueError('Unused source in layout')
    sources = {}
    for filename, item in source_rows.items():
        path = root/filename
        internal(root, path)
        if not path.is_file() or path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            raise ValueError('Copied source bytes differ: '+filename)
        sources[filename] = load_leaf(session, path)
    # Four occurrences use each unique study part, without duplicating geometry.
    study_roles = {}
    for row in rows:
        if row['kind'] == 'role':
            study_roles.setdefault(row['file'], {})[row['role']] = row['reference_set']
    for filename, roles in study_roles.items():
        part = sources[filename]
        # Independent source leaves are not descendants of the last opened leaf.
        display_part(session, part)
        existing = {r.Name for r in part.GetAllReferenceSets()}
        for role, ref_name in roles.items():
            bodies = [b for b in part.Bodies if body_role(b.Name) == role]
            if not bodies or ref_name in existing:
                raise ValueError('Missing role bodies or existing M01 reference set: '+filename+' '+role)
            for body in bodies:
                body.Unblank()
            refset = part.CreateReferenceSet()
            refset.SetName(ref_name)
            refset.AddObjectsToReferenceSet(bodies)
        save(part)
    parts = dict(sources)
    # Build children before parents. Source leaves are never saved here.
    for row in reversed(rows):
        filename = row['file']
        if filename in parts:
            continue
        path = root/filename
        internal(root, path)
        if path.exists():
            raise ValueError('Generated part already exists: '+filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        part = session.Parts.NewDisplay(str(path), NXOpen.Part.Units.Millimeters)
        display_part(session, part)
        metadata(part, row, fields, rooms)
        if row['id'] == 'MASTER':
            attribute(part, 'M01_PROJECT', PROJECT)
            attribute(part, 'M01_CONSTRUCTION_RELEASE', False)
            attribute(part, 'M01_LAYOUT_SCHEMA', layout['schema'])
        for child in rows:
            if child['parent'] != row['id']:
                continue
            matrix = NXOpen.Matrix3x3()
            for key, value in zip(MATRIX_KEYS, child['rotation']):
                setattr(matrix, key, float(value))
            component, status = part.ComponentAssembly.AddComponent(
                str(root/child['file']), child['reference_set'], child['name'],
                NXOpen.Point3d(*(float(v) for v in child['translation_mm'])), matrix, -1)
            try:
                if component is None or status.NumberUnloadedParts:
                    raise ValueError('Native component not fully loaded: '+child['id'])
            finally:
                status.Dispose()
            metadata(component, child, fields, rooms)
            set_blank(component, child['blank'])
        save(part)
        parts[filename] = part
    master = parts[layout['master']]
    display_part(session, master)
    # NX does not inherit all saved subassembly blank states into a new root.
    # Persist the exact defaults on occurrences of the completed master itself.
    occurrences = components(master)
    defaults = {row['id']: row['blank'] for row in rows if row['id'] != 'MASTER'}
    if set(occurrences) != set(defaults):
        raise ValueError('Incomplete master occurrence tree before default visibility')
    apply_visibility(occurrences, defaults)
    save(master)
    for filename, item in source_rows.items():
        if filename not in study_roles and digest(root/filename) != item['sha256']:
            raise ValueError('Copied source leaf was modified: '+filename)
    return master


def world_transforms(layout):
    result = {}
    for row in sorted_nodes(layout):
        p, r = list(row['translation_mm']), list(row['rotation'])
        if row['parent'] is not None:
            parent_p, parent_r = result[row['parent']]
            p = [parent_p[i]+sum(parent_r[i*3+j]*p[j] for j in range(3)) for i in range(3)]
            r = [sum(parent_r[i*3+k]*r[k*3+j] for k in range(3))
                 for i in range(3) for j in range(3)]
        result[row['id']] = (p, r)
    return result


def same_numbers(actual, wanted, context):
    if len(actual) != len(wanted) or any(not math.isfinite(float(a)) or abs(a-b) > 1e-8
                                        for a, b in zip(actual, wanted)):
        raise ValueError('Native transform mismatch: '+context)


def inspect_nodes(master, root, layout):
    from renovierung.m01.display import PROJECT, effective_visibility, read_attribute
    if read_attribute(master, 'M01_PROJECT') != PROJECT:
        raise ValueError('Missing M01 master identity')
    if read_attribute(master, 'M01_CONSTRUCTION_RELEASE') is not False:
        raise ValueError('Incorrect construction release attribute')
    if read_attribute(master, 'M01_LAYOUT_SCHEMA') != layout['schema']:
        raise ValueError('Layout schema attribute mismatch')
    wanted = {r['id']: r for r in layout['nodes']}
    fields, rooms = associated_rows(layout, 'fields'), associated_rows(layout, 'rooms')
    world = world_transforms(layout)
    local_states = {ident: row['blank'] for ident, row in wanted.items() if ident != 'MASTER'}
    effective = effective_visibility({ident: wanted[ident]['parent'] for ident in local_states}, local_states)
    rows, occurrences = {}, {}

    def check_attrs(obj, ident):
        row = wanted[ident]
        for key, expected in {'M01_NODE_ID': ident, 'M01_KIND': row['kind'],
                              'M01_DEFAULT_BLANK': row['blank'], 'M01_NODE_METADATA': row}.items():
            if read_attribute(obj, key) != expected:
                raise ValueError('Native attribute mismatch: '+ident+' '+key)
        if ident in fields:
            for key, expected in {'M01_FIELD_ID': fields[ident]['id'],
                                  'M01_FIELD_NATIVE': fields[ident]['native'],
                                  'M01_FIELD_METADATA': fields[ident]}.items():
                if read_attribute(obj, key) != expected:
                    raise ValueError('Field metadata mismatch: '+ident)
        if ident in rooms and read_attribute(obj, 'M01_ROOM_METADATA') != rooms[ident]:
            raise ValueError('Room register metadata mismatch: '+ident)

    check_attrs(master, 'MASTER')
    root_row = wanted['MASTER']
    rows['MASTER'] = {'parent': None, 'file': internal(root, master.FullPath),
                      'name': root_row['name'], 'translation_mm': [0., 0., 0.],
                      'rotation': IDENTITY, 'blank': False, 'reference_set': 'Entire Part',
                      'suppressed': False}
    if rows['MASTER']['file'] != root_row['file']:
        raise ValueError('Incorrect master filename')

    def walk(parent, parent_id):
        for component in parent.GetChildren():
            ident = read_attribute(component, 'M01_NODE_ID')
            if ident not in wanted or ident in rows:
                raise ValueError('Unknown or duplicate occurrence: '+str(ident))
            check_attrs(component, ident)
            row = wanted[ident]
            point, matrix = component.GetPosition()
            actual = {'parent': parent_id, 'file': internal(root, component.Prototype.FullPath),
                      'name': component.Name, 'translation_mm': [point.X, point.Y, point.Z],
                      'rotation': [getattr(matrix, k) for k in MATRIX_KEYS],
                      'blank': bool(component.IsBlanked), 'reference_set': component.ReferenceSet,
                      'suppressed': bool(component.IsSuppressed)}
            for key in ('parent', 'file', 'name', 'blank', 'reference_set'):
                expected = effective[ident] if key == 'blank' else row[key]
                matches = (actual[key].casefold() == row[key].casefold()
                           if key == 'name' else actual[key] == expected)
                if not matches:
                    raise ValueError('Native node mismatch: '+ident+' '+key+' '+repr(actual[key]))
            if component.IsSuppressed:
                raise ValueError('Suppressed occurrence: '+ident)
            same_numbers(actual['translation_mm'], world[ident][0], ident+' translation')
            same_numbers(actual['rotation'], world[ident][1], ident+' rotation')
            rows[ident], occurrences[ident] = actual, component
            walk(component, ident)

    walk(master.ComponentAssembly.RootComponent, 'MASTER')
    if set(rows) != set(wanted):
        raise ValueError('Missing native occurrences: '+repr(sorted(set(wanted)-set(rows))))
    return rows, occurrences


def validate_refset_members(body_names_by_tag, members):
    """Require exact B-reps, allowing only facets associated with those B-reps.

    This record-only validation has no NX dependency. Facets are display
    representations and never contribute additional measured body volumes.
    """
    body_members = [m['tag'] for m in members if m['kind'] == 'body']
    tags = [m['tag'] for m in members]
    if (not body_names_by_tag or len(tags) != len(set(tags))
            or len(body_members) != len(body_names_by_tag)
            or set(body_members) != set(body_names_by_tag)):
        raise ValueError('Reference set has wrong or duplicate B-rep members')
    facets = []
    for member in members:
        if member['kind'] == 'body':
            continue
        if (member['kind'] != 'facet' or member.get('associated_loaded') is not True
                or member.get('associated_tag') not in body_names_by_tag):
            raise ValueError('Reference set has foreign, orphan or unknown display members')
        facets.append(body_names_by_tag[member['associated_tag']])
    return sorted(facets)


def inspect_parts(session, master, root, layout, expected_parts=None):
    import NXOpen
    import NXOpen.Facet
    from renovierung.k02.nx_verify import body_role, measure
    from renovierung.k02.runner import validate_measurement
    expected_files = {r['file'] for r in layout['nodes']}
    disk_files = {p.relative_to(root).as_posix() for p in root.rglob('*.prt')}
    if disk_files != expected_files:
        raise ValueError('Delivery part inventory differs from layout')
    expected_hashes = {r['path']: r for r in expected_parts} if expected_parts is not None else None
    if expected_hashes is not None and set(expected_hashes) != expected_files:
        raise ValueError('Verifier part manifest differs from layout')
    parts, dependencies = {}, {}
    for part in session.Parts:
        filename = internal(root, part.FullPath)
        if filename not in expected_files or filename in parts:
            raise ValueError('Unlisted or duplicate native part: '+filename)
        if not part.IsFullyLoaded or part.PartUnits != NXOpen.BasePart.Units.Millimeters:
            raise ValueError('Part not fully loaded in millimeters: '+filename)
        path = root/filename
        if expected_hashes is not None:
            item = expected_hashes[filename]
            if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
                raise ValueError('Native file bytes differ: '+filename)
        parents = [internal(root, p.FullPath) for p in part.GetInterpartParents()]
        if set(parents)-expected_files:
            raise ValueError('Unknown internal interpart parent: '+filename)
        refs = list(part.Expressions.GetInterpartReferences())
        if refs:
            raise ValueError('Unsupported expression interpart reference: '+filename)
        dependencies[filename] = {'interpart_parents': sorted(parents), 'expression_references': refs}
        parts[filename] = part
    if set(parts) != expected_files:
        raise ValueError('Missing loaded parts: '+repr(sorted(expected_files-set(parts))))
    refsets, refset_facets, measurements = {}, {}, {}
    for field in layout['fields']:
        if not field['native']:
            continue
        roles = [r for r in layout['nodes'] if r['parent'] == field['node_id'] and r['kind'] == 'role']
        if {r['role'] for r in roles} != set(field['measurements']):
            raise ValueError('Field role inventory mismatch: '+field['id'])
        measurements[field['id']] = {}
        for row in roles:
            filename, role = row['file'], row['role']
            part = parts[filename]
            session.Parts.SetWork(part)
            bodies = [b for b in part.Bodies if body_role(b.Name) == role]
            if not bodies or any(b.IsBlanked for b in bodies):
                raise ValueError('Missing or hidden role prototype bodies: '+field['id']+' '+role)
            sets = {ref.Name: ref for ref in part.GetAllReferenceSets()}
            wanted_names = {r['reference_set'] for r in roles if r['file'] == filename}
            if {name for name in sets if name.startswith('M01_')} != wanted_names:
                raise ValueError('Study reference set inventory mismatch: '+filename)
            members = list(sets[row['reference_set']].AskAllDirectMembers())
            records = []
            for member in members:
                record = {'tag': member.Tag, 'kind': 'other'}
                if isinstance(member, NXOpen.Body):
                    record['kind'] = 'body'
                elif isinstance(member, NXOpen.Facet.FacetedBody):
                    loaded = bool(member.IsAssociatedBodyLoaded)
                    associated = member.AssociatedBody if loaded else None
                    record.update(kind='facet', associated_loaded=loaded,
                                  associated_tag=associated.Tag if associated is not None else None)
                records.append(record)
            try:
                facet_names = validate_refset_members({b.Tag: b.Name for b in bodies}, records)
            except ValueError as error:
                raise ValueError('Reference set has wrong role members: '+field['id']+' '+role+'; '+str(error)) from error
            refsets.setdefault(filename, {})[row['reference_set']] = sorted(b.Name for b in bodies)
            refset_facets.setdefault(filename, {})[row['reference_set']] = facet_names
            actual = measure(bodies)
            wanted = field['measurements'][role]
            validate_measurement(actual, wanted['component_volumes_m3'])
            measurements[field['id']][role] = actual
    session.Parts.SetWork(master)
    return sorted(parts), dependencies, refsets, measurements, refset_facets


def test_visibility(master, layout, occurrences):
    from renovierung.m01.display import (apply_visibility, effective_visibility,
                                         select_state, set_blank)
    wanted = {r['id']: r for r in layout['nodes']}
    baseline = {ident: wanted[ident]['blank'] for ident in occurrences}
    parents = {ident: wanted[ident]['parent'] for ident in occurrences}
    toggles, states = [], []
    try:
        for ident, component in occurrences.items():
            visible = dict(baseline)
            current = ident
            while current != 'MASTER':
                visible[current] = False
                current = parents[current]
            apply_visibility(occurrences, visible)
            set_blank(component, True)
            set_blank(component, False)
            # Parent operations overwrite descendant flags. Restore the
            # complete canonical local intent, expanded to physical flags.
            apply_visibility(occurrences, baseline)
            toggles.append(ident)
        for state in ['BASE']+[f['id'] for f in layout['fields'] if f['native']]:
            select_state(master, state)
            for field in layout['fields']:
                expected = state == 'BASE' or field['id'] != state
                if bool(occurrences[field['node_id']].IsBlanked) != expected:
                    raise ValueError('Field state switch mismatch: '+state)
            if bool(occurrences['TERRAIN'].IsBlanked) != (state != 'BASE'):
                raise ValueError('Terrain state switch mismatch: '+state)
            for ident, component in occurrences.items():
                if wanted[ident]['kind'] == 'role':
                    hidden_field = bool(occurrences[parents[ident]].IsBlanked)
                    expected = hidden_field or wanted[ident]['blank']
                    if bool(component.IsBlanked) != expected:
                        raise ValueError('Role state visibility mismatch: '+state+' '+ident)
            states.append(state)
    finally:
        apply_visibility(occurrences, baseline)
    expected = effective_visibility(parents, baseline)
    if any(bool(c.IsBlanked) != expected[ident] for ident, c in occurrences.items()):
        raise ValueError('Native default visibility was not restored')
    return sorted(toggles), states


def main():
    result = {'status': 'FAIL', 'construction_release': False}
    request = json.loads(Path(os.environ['M01_NX_REQUEST']).read_text(encoding='utf-8'))
    sys.path.insert(0, request['repo_root'])
    try:
        import NXOpen
        from renovierung.k02.nx_verify import open_all
        from renovierung.m01.layout import validate_layout
        session = NXOpen.Session.GetSession()
        if list(session.Parts):
            raise RuntimeError('A fresh NX process is required')
        root, layout = Path(request['directory']).resolve(), request['layout']
        validate_layout(layout)
        sorted_nodes(layout)
        if request['mode'] == 'build':
            master = build(session, root, layout)
        elif request['mode'] == 'verify':
            master = open_all(session, root, layout['master'], request['load_method'])
        else:
            raise ValueError('Unsupported M01 journal mode')
        before = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*.prt')}
        nodes, occurrences = inspect_nodes(master, root, layout)
        parts, dependencies, refsets, measurements, refset_facets = inspect_parts(
            session, master, root, layout, request.get('parts') if request['mode'] == 'verify' else None)
        toggles, states = test_visibility(master, layout, occurrences)
        # Check attributes and exact baseline again after the unsaved switches.
        restored, _ = inspect_nodes(master, root, layout)
        if nodes != restored:
            raise ValueError('Native state testing changed the baseline')
        after = {p.relative_to(root).as_posix(): digest(p) for p in root.rglob('*.prt')}
        if before != after:
            raise ValueError('Inspection modified saved part files')
        result.update(status='PASS', master=layout['master'], mode=request['mode'],
                      load_method=request['load_method'], nodes=nodes, parts=parts,
                      dependencies=dependencies, measurements=measurements, refsets=refsets,
                      refset_facets=refset_facets,
                      toggle_checks=toggles, state_checks=states, all_parts_mm=True,
                      all_parts_fully_loaded=True, all_paths_internal=True,
                      files_saved_by_verifier=False)
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
    Path(request['report']).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
