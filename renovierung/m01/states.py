"""Saved native M01 arrangements and pure suppression intent; never save Parts."""
import re


DETAIL_HIDDEN = {'TERRAIN', 'HOUSE_EG', 'HOUSE_DG', 'HOUSE_ROOF', 'HOUSE_OUTSIDE'}
SITE_VEGETATION = {'ENV_V01', 'ENV_V02', 'ENV_V03', 'ENV_V05'}
ROLES = ('cut_soil', 'excavation', 'pile_main', 'pile_reserve')


def _inventory(layout):
    try:
        nodes = {n['id']: n for n in layout['nodes']}
        fields = {f['id']: f for f in layout['fields']}
        sections = {s['id'] for s in layout['sections']}
        groups = {g['id']: g for g in layout['context']['groups']}
        if (len(nodes) != len(layout['nodes']) or len(fields) != len(layout['fields'])
                or len(sections) != len(layout['sections'])
                or len(groups) != len(layout['context']['groups'])):
            raise ValueError('Duplicate arrangement inventory IDs')
        if any(not re.fullmatch(r'PS[0-9]+', s) for s in sections):
            raise ValueError('Unsafe section state ID')
        for fid, field in fields.items():
            if (not re.fullmatch(r'PS[0-9]+-F[0-9]+', fid)
                    or field['sector_id'] not in sections
                    or type(field['native']) is not bool
                    or nodes[field['node_id']]['kind'] != 'field'):
                raise ValueError('Invalid field arrangement inventory')
        natives = {fid for fid, f in fields.items() if f['native']}
        if not natives:
            raise ValueError('At least one native field is required for the default state')
        if {n['id'] for n in nodes.values() if n['kind'] == 'context'} != set(groups):
            raise ValueError('Context groups and native nodes differ')
        for group in groups.values():
            if (not isinstance(group['exclude_for'], list)
                    or any(fid not in natives for fid in group['exclude_for'])):
                raise ValueError('Context exclusion references an unknown native field')
        field_nodes = {f['node_id'] for f in fields.values() if f['native']}
        for node in nodes.values():
            if node['kind'] == 'role' and (node['parent'] not in field_nodes or node['role'] not in ROLES):
                raise ValueError('Invalid native role arrangement inventory')
        return nodes, fields, sections, groups
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Malformed arrangement layout: ' + str(error)) from error


def state_catalog(layout):
    """Stable register-ID to ASCII arrangement-name mapping in display order."""
    _, fields, sections, _ = _inventory(layout)
    ids = ['BASE'] + sorted(sections) + sorted(fid for fid, f in fields.items() if f['native'])
    return {ident: 'M01_' + ident.replace('-', '_') for ident in ids}


def _controlled(nodes):
    return {nid for nid, n in nodes.items() if n['kind'] in ('field', 'role', 'context')} | (DETAIL_HIDDEN & set(nodes))


def state_spec(layout, state):
    """Return direct suppression intent, independently of inherited Blank flags."""
    nodes, fields, sections, groups = _inventory(layout)
    catalog = state_catalog(layout)
    if not isinstance(state, str) or state not in catalog:
        raise ValueError('Unknown or non-native M01 state: ' + str(state))
    hidden = set()
    for fid, field in fields.items():
        if state == 'BASE' or (field['sector_id'] != state if state in sections else fid != state):
            hidden.add(field['node_id'])
    if state in sections:
        hidden.update(nid for nid, n in nodes.items() if n['kind'] == 'role')
    else:
        # A separately opened parent can reset nested Blank flags. Suppression
        # belongs to the saved arrangement and also applies inside entry parts.
        hidden.update(nid for nid, n in nodes.items()
                      if n['kind'] == 'role' and n['blank'])
    for gid, group in groups.items():
        if state == 'BASE' or state in group['exclude_for']:
            hidden.add(gid)
    if state != 'BASE':
        hidden.update(DETAIL_HIDDEN & set(nodes))
    return {'id': state, 'name': catalog[state], 'suppressed_ids': sorted(hidden)}


def _displayed(master):
    import NXOpen
    display = NXOpen.Session.GetSession().Parts.Display
    if display is None or display.Tag != master.Tag:
        raise ValueError('The intended M01 master must be displayed')


def _check_errors(errors, context):
    records = []
    try:
        for i in range(errors.Length):
            error = errors.GetErrorInfo(i)
            records.append((error.ErrorCode, error.Description))
    finally:
        errors.Dispose()
    if records:
        raise ValueError(context + ': ' + repr(records))


def create_arrangements(master, layout):
    """Create explicit per-arrangement nested suppression; no global overloads."""
    from .display import components, write_attribute
    nodes, fields, _, _ = _inventory(layout)
    catalog = state_catalog(layout)
    specs = {sid: state_spec(layout, sid) for sid in catalog}
    default = sorted(fid for fid, f in fields.items() if f['native'])[0]
    _displayed(master)
    occurrences = components(master)
    if set(occurrences) != set(nodes) - {'MASTER'}:
        raise ValueError('Native arrangement occurrence inventory differs')
    assembly = master.ComponentAssembly
    existing = list(assembly.Arrangements)
    if len(existing) != 1 or assembly.ActiveArrangement is None:
        raise ValueError('Arrangement creation requires one fresh template arrangement')
    controls = sorted(_controlled(nodes))
    template = assembly.ActiveArrangement
    template.SetName(catalog['BASE'])
    arrangements = {'BASE': template}
    for sid in catalog:
        if sid != 'BASE':
            arrangements[sid] = assembly.Arrangements.Create(template, catalog[sid])
    for sid, arrangement in arrangements.items():
        hidden = set(specs[sid]['suppressed_ids'])
        for operation, ids in ((assembly.SuppressComponents, [i for i in controls if i in hidden]),
                               (assembly.UnsuppressComponents, [i for i in controls if i not in hidden])):
            if ids:
                _check_errors(operation([occurrences[i] for i in ids], [arrangement]), sid)
    write_attribute(master, 'M01_STATE_CATALOG', catalog)
    write_attribute(master, 'M01_DEFAULT_STATE', default)
    assembly.SetDefault(arrangements[default])
    assembly.ActiveArrangement = arrangements[default]
    return {'catalog': catalog, 'default': default, 'active': default}


def activate_state(master, state):
    """Activate a saved state after validating its catalog, without saving files."""
    from .display import PROJECT, read_attribute
    _displayed(master)
    if read_attribute(master, 'M01_PROJECT') != PROJECT:
        raise ValueError('Displayed part is not an M01 master')
    catalog = read_attribute(master, 'M01_STATE_CATALOG')
    if not isinstance(catalog, dict) or not isinstance(state, str) or state not in catalog:
        raise ValueError('Unknown M01 saved state: ' + str(state))
    arrangements = {a.Name: a for a in master.ComponentAssembly.Arrangements}
    if (not all(isinstance(name, str) for name in catalog.values())
            or len(set(catalog.values())) != len(catalog)
            or set(arrangements) != set(catalog.values())):
        raise ValueError('Saved arrangement catalog differs from native arrangements')
    master.ComponentAssembly.ActiveArrangement = arrangements[catalog[state]]
    return state


def _visible(master, node_map, occurrences):
    """One view query; B-rep/facet deduplication includes the owning occurrence."""
    import NXOpen
    import NXOpen.Facet
    by_tag = {component.Tag: ident for ident, component in occurrences.items()}
    bodies, markers = {}, set()
    for obj in master.ModelingViews.WorkView.AskVisibleObjects():
        body = None
        if isinstance(obj, NXOpen.Body):
            body = obj
        elif isinstance(obj, NXOpen.Facet.FacetedBody):
            if not obj.IsAssociatedBodyLoaded:
                raise ValueError('Visible facet has no loaded associated B-rep')
            body = obj.AssociatedBody
        elif not isinstance(obj, NXOpen.Curve):
            continue  # Edges and faces do not add a body or a register curve.
        owner = body.OwningComponent if body is not None else obj.OwningComponent
        if owner is None:
            owner = obj.OwningComponent
        if owner is None or owner.Tag not in by_tag:
            # Native root-owned objects are not field/context occurrences.
            continue
        nid = by_tag[owner.Tag]
        if body is not None:
            prototype = body.Prototype if body.IsOccurrence else body
            bodies.setdefault(nid, set()).add((owner.Tag, prototype.Tag))
        elif isinstance(obj, NXOpen.Curve) and node_map[nid]['kind'] == 'field':
            markers.add(nid)
    return {nid: len(tags) for nid, tags in bodies.items()}, markers


def test_arrangements(master, layout):
    """Check every direct control and visible field/context occurrence, then restore default.

    Requires the final presentation and field-owned marker geometry to be applied
    already. AskVisibleObjects is native visibility evidence, not a screenshot.
    """
    import NXOpen.Assemblies
    from .display import components, read_attribute
    from .presentation import read_presentation
    nodes, fields, sections, groups = _inventory(layout)
    catalog = state_catalog(layout)
    default = sorted(fid for fid, f in fields.items() if f['native'])[0]
    _displayed(master)
    if (read_attribute(master, 'M01_STATE_CATALOG') != catalog
            or read_attribute(master, 'M01_DEFAULT_STATE') != default):
        raise ValueError('Native state attributes differ from canonical layout')
    occurrences = components(master)
    controls = sorted(_controlled(nodes))
    assembly = master.ComponentAssembly
    enum = NXOpen.Assemblies.ComponentAssembly.SuppressedState
    states = {}
    try:
        for sid in catalog:
            activate_state(master, sid)
            spec = state_spec(layout, sid)
            expected = set(spec['suppressed_ids'])
            direct_hidden = []
            for nid in controls:
                status, controlled = assembly.GetSuppressedState(occurrences[nid], assembly.ActiveArrangement)
                wanted = enum.Suppressed if nid in expected else enum.Unsuppressed
                if not controlled or status != wanted:
                    raise ValueError('Direct arrangement suppression differs: ' + sid + ' ' + nid)
                if status == enum.Suppressed:
                    direct_hidden.append(nid)
            visible_counts, markers = _visible(master, nodes, occurrences)
            for nid in SITE_VEGETATION & set(occurrences):
                if occurrences[nid].IsSuppressed:
                    raise ValueError('Mapped site vegetation suppressed in '+sid+': '+nid)
            if sid == 'BASE':
                for nid in ('HOUSE_KG_MAIN', 'HOUSE_EG_MAIN', 'TERRAIN'):
                    if nid in nodes and visible_counts.get(nid, 0) == 0:
                        raise ValueError('No visible building/site geometry in BASE: ' + nid)
            role_counts = {role: 0 for role in ROLES}
            for nid, node in nodes.items():
                if node['kind'] != 'role':
                    continue
                field = next(f for f in fields.values() if f['node_id'] == node['parent'])
                count = (field['measurements'][node['role']]['body_count']
                         if sid == field['id'] and not node['blank'] else 0)
                if visible_counts.get(nid, 0) != count:
                    raise ValueError('Visible role B-rep occurrence count differs: ' + sid + ' ' + nid)
                role_counts[node['role']] += count
            visible_context = []
            for gid, group in groups.items():
                count = 0 if gid in expected else group['body_count']
                if visible_counts.get(gid, 0) != count:
                    raise ValueError('Visible context B-rep occurrence count differs: ' + sid + ' ' + gid)
                if count:
                    visible_context.append(gid)
            wanted_markers = {f['node_id'] for fid, f in fields.items()
                              if sid == fid or (sid in sections and f['sector_id'] == sid)}
            if markers != wanted_markers:
                raise ValueError('Visible field markers differ: ' + sid + ' ' + repr(sorted(markers)))
            field_ids = {f['node_id']: fid for fid, f in fields.items()}
            states[sid] = {'suppressed_ids': direct_hidden, 'visible_role_bodies': role_counts,
                           'visible_context_ids': sorted(visible_context),
                           'visible_field_marker_ids': sorted(field_ids[nid] for nid in markers)}
            states[sid]['visible_site_bodies'] = {nid: visible_counts.get(nid, 0) for nid in
                ('HOUSE_KG_MAIN', 'HOUSE_EG_MAIN', 'TERRAIN', 'ENV_V01', 'ENV_V02', 'ENV_V03', 'ENV_V05') if nid in nodes}
    finally:
        activate_state(master, default)
    return {'catalog': catalog, 'default': default, 'active': default, 'states': states,
            'presentation': read_presentation(master)}
