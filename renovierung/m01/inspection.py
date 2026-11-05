"""Separate review entry Parts referencing one delivery-local M01 master."""
import hashlib
import math
from pathlib import Path
import re


def build_review_index(layout):
    """Return section and native-field entry files, without inventing studies."""
    try:
        sections = [s['id'] for s in layout['sections']]
        fields = layout['fields']
        if (len(set(sections)) != len(sections)
                or any(not isinstance(s, str) or not re.fullmatch(r'PS[0-9]+', s) for s in sections)):
            raise ValueError('Invalid or duplicate review section IDs')
        seen, native = set(), {}
        for field in fields:
            fid, sid = field['id'], field['sector_id']
            if (not isinstance(fid, str) or not re.fullmatch(r'PS[0-9]+-F[0-9]+', fid)
                    or sid not in sections or fid.split('-')[0] != sid
                    or fid in seen or type(field['native']) is not bool):
                raise ValueError('Invalid or duplicate review field')
            seen.add(fid)
            if field['native']:
                native[fid] = sid
        rows = [{'id': sid, 'file': 'Bauabschnitte/' + sid + '.prt',
                 'state': next(iter(sorted(fid for fid, section in native.items() if section == sid)), sid)}
                for sid in sections]
        rows.extend({'id': fid, 'file': 'Bauabschnitte/' + sid + '/' + fid + '.prt', 'state': fid}
                    for fid, sid in native.items())
        return sorted(rows, key=lambda row: row['id'])
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError('Malformed review layout: ' + str(error)) from error


def _index(layout):
    rows = build_review_index(layout)
    if layout.get('review_masters') != rows:
        raise ValueError('Review entry catalog differs from canonical layout')
    return rows


def _path(root, relative, file_map=None):
    from .delivery_paths import mapfile
    return mapfile(root, relative, file_map)


def _prototype_path(root, logical, actual, file_map=None):
    from .delivery_paths import logicalfile
    if (logicalfile(root, actual, file_map) != logical or
            Path(actual).resolve() != _path(root, logical, file_map)):
        raise ValueError('Loaded prototype FullPath differs from delivery map: '+logical)


def _configure_load(session, method='AsSaved', *, full=True):
    import NXOpen
    if method not in ('AsSaved','FromDirectory'):
        raise ValueError('Fresh entry checks require AsSaved or FromDirectory, without search paths')
    options=session.Parts.LoadOptions
    if full:
        options.SetSearchDirectories([], [])
        options.ComponentLoadMethod=getattr(NXOpen.LoadOptions.LoadMethod,method)
        options.PartLoadOption=NXOpen.LoadOptions.LoadOption.FullyLoad
        options.ComponentsToLoad=NXOpen.LoadOptions.LoadComponents.All
        options.UsePartialLoading=False
        options.UseLightweightRepresentations=False
    elif (options.ComponentLoadMethod!=NXOpen.LoadOptions.LoadMethod.FromDirectory or
          options.PartLoadOption!=NXOpen.LoadOptions.LoadOption.MinimallyLoadLightweightDisplay):
        raise ValueError('The cold default proof requires the unchanged directory/minimal NX profile')
    return {'component_load_method':str(options.ComponentLoadMethod),
            'requested_component_load_method':method,
            'component_load_method_matches_requested':options.ComponentLoadMethod==getattr(NXOpen.LoadOptions.LoadMethod,method),
            'components_to_load':str(options.ComponentsToLoad),
            'use_partial_loading':bool(options.UsePartialLoading),
            'use_lightweight_representations':bool(options.UseLightweightRepresentations),
            'supplementary_search_directories':[]}


def _loaded_inventory(session, root, expected, file_map=None, *, full=True, require_all=True, include_physical=False):
    import NXOpen
    from .delivery_paths import logicalfile
    names=set();physical={}
    for part in session.Parts:
        logical=logicalfile(root,part.FullPath,file_map)
        if logical not in expected or logical in names:
            raise ValueError('Unknown/duplicate loaded prototype in fresh entry: '+logical)
        _prototype_path(root,logical,part.FullPath,file_map)
        if part.PartUnits != NXOpen.BasePart.Units.Millimeters or (full and not part.IsFullyLoaded):
            raise ValueError('Fresh entry prototype not fully loaded/mm: '+logical)
        names.add(logical)
        physical[logical]=str(Path(part.FullPath).resolve())
    if require_all and names != set(expected):
        raise ValueError('Missing fresh entry prototype files: '+repr(sorted(set(expected)-names)))
    return physical if include_physical else sorted(names)


def _native_dependencies(part, root, expected, file_map=None):
    from .delivery_paths import logicalfile
    parents=sorted(logicalfile(root,p.FullPath,file_map) for p in part.GetInterpartParents())
    if len(parents)!=len(set(parents)) or set(parents)-set(expected):
        raise ValueError('Review wrapper has foreign/duplicate interpart parents')
    refs=list(part.Expressions.GetInterpartReferences())
    if refs:
        raise ValueError('Unsupported wrapper expression interpart references: '+repr(refs))
    return {'interpart_parents':parents,'expression_references':refs}


def _hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*.prt')}


def _loaded(part, status, context):
    try:
        if part is None or status.NumberUnloadedParts:
            raise ValueError('Incomplete native review load: ' + context)
    finally:
        status.Dispose()


def _restore(session, master, layout):
    from .nx_journal import display_part
    from .states import activate_state
    display_part(session, master)
    activate_state(master, layout['default_state'])


def create_reviews(session, root, layout):
    """Save only new wrapper Parts; never save the referenced master or children."""
    import NXOpen
    from .display import write_attribute
    from .nx_journal import display_part
    from .presentation import apply_presentation
    from .states import state_catalog
    root = Path(root).resolve()
    rows, catalog = _index(layout), state_catalog(layout)
    master = session.Parts.Display
    master_path = _path(root, layout['master'])
    if master is None or Path(master.FullPath).resolve() != master_path:
        raise ValueError('Review creation requires the delivery master displayed')
    for row in rows:
        if _path(root, row['file']).exists():
            raise ValueError('Refusing to overwrite existing review entry: ' + row['file'])
    before, result = _hashes(root), {}
    try:
        for row in rows:
            path = _path(root, row['file'])
            path.parent.mkdir(parents=True, exist_ok=True)
            wrapper = session.Parts.NewDisplay(str(path), NXOpen.Part.Units.Millimeters)
            display_part(session, wrapper)
            matrix = NXOpen.Matrix3x3()
            matrix.Xx = matrix.Yy = matrix.Zz = 1.0
            child, status = wrapper.ComponentAssembly.AddComponent(
                str(master_path), 'Entire Part', 'M01_REVIEW_' + row['id'].replace('-', '_'),
                NXOpen.Point3d(0.0, 0.0, 0.0), matrix, -1)
            _loaded(child, status, row['id'])
            arrangements = {a.Name: a for a in child.Prototype.ComponentAssembly.Arrangements}
            child.SetUsedArrangement(arrangements[catalog[row['state']]])
            for key, value in {'M01_REVIEW_SCOPE': 'M01_REVIEW', 'M01_REVIEW_ID': row['id'],
                               'M01_REVIEW_STATE': row['state']}.items():
                write_attribute(wrapper, key, value)
            presentation = apply_presentation(wrapper, layout['presentation'])
            wrapper.Save(NXOpen.BasePart.SaveComponents.FalseValue,
                         NXOpen.BasePart.CloseAfterSave.FalseValue).Dispose()
            result[row['id']] = dict(row, master=layout['master'], presentation=presentation)
    finally:
        try:
            _restore(session, master, layout)
        finally:
            after = _hashes(root)
            if any(after.get(file) != value for file, value in before.items()):
                raise ValueError('Review creation changed existing native Part bytes')
    return result


def _occurrences(child):
    from .display import read_attribute
    result = {}

    def walk(parent):
        for component in parent.GetChildren():
            ident = read_attribute(component, 'M01_NODE_ID')
            if ident in result:
                raise ValueError('Duplicate review occurrence ID: ' + ident)
            result[ident] = component
            walk(component)

    walk(child)
    return result


def _visible_record(layout, state, counts, markers):
    from .states import ROLES, state_spec
    nodes = {node['id']: node for node in layout['nodes']}
    fields = {field['node_id']: field for field in layout['fields']}
    hidden = set(state_spec(layout, state)['suppressed_ids'])
    role_counts = {role: 0 for role in ROLES}
    for nid, node in nodes.items():
        if node['kind'] != 'role':
            continue
        field = fields[node['parent']]
        expected = (field['measurements'][node['role']]['body_count']
                    if field['id'] == state and not node['blank'] else 0)
        if counts.get(nid, 0) != expected:
            raise ValueError('Review visible role B-rep occurrence count differs: ' + state + ' ' + nid)
        role_counts[node['role']] += expected
    contexts = []
    for group in layout['context']['groups']:
        gid = group['id']
        expected = 0 if gid in hidden else group['body_count']
        if counts.get(gid, 0) != expected:
            raise ValueError('Review visible context B-rep occurrence count differs: ' + state + ' ' + gid)
        if expected:
            contexts.append(gid)
    sections = {section['id'] for section in layout['sections']}
    expected = {nid for nid, field in fields.items()
                if field['id'] == state or (state in sections and field['sector_id'] == state)}
    if markers != expected:
        raise ValueError('Review visible field markers differ: ' + state)
    return {'visible_role_bodies': role_counts, 'visible_context_ids': sorted(contexts),
            'visible_field_marker_ids': sorted(fields[nid]['id'] for nid in markers)}


def _check_presentation(record, spec):
    from .presentation import DISPLAY_LAYERS
    camera = record['camera']
    for key, expected in (('absolute_origin_mm', spec['origin_mm']), ('matrix', spec['matrix'])):
        actual = camera[key]
        if len(actual) != len(expected) or any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-8)
                                                for a, b in zip(actual, expected)):
            raise ValueError('Review native camera differs: ' + key)
    if (not math.isclose(camera['scale'], spec['scale'], rel_tol=1e-10, abs_tol=1e-12)
            or not record['shaded_with_edges']
            or set(record['layers']) != {str(number) for number in DISPLAY_LAYERS}
            or not all(v['visible'] and v['selectable'] and not v['hidden'] for v in record['layers'].values())):
        raise ValueError('Review native presentation differs')


def inspect_reviews(session, root, layout, file_map=None, *, load_method='AsSaved', reuse_master=False):
    """Read fresh wrapper files and native visibility, preserving every Part byte."""
    import NXOpen
    from .display import PROJECT, read_attribute
    from .presentation import read_presentation
    from .states import _visible, state_catalog
    from .standalone import _close_owned
    root = Path(root).resolve()
    rows, catalog = _index(layout), state_catalog(layout)
    master = session.Parts.Display
    master_path = _path(root, layout['master'], file_map)
    if master is None or Path(master.FullPath).resolve() != master_path:
        raise ValueError('Review inspection requires the delivery master displayed')
    before, result = _hashes(root), {}
    nodes = {node['id']: node for node in layout['nodes']}
    core_files={node['file'] for node in nodes.values()}
    _configure_load(session,load_method,full=True)
    if reuse_master:
        if load_method!='AsSaved' or not session.IsBatch:
            raise ValueError('Core reuse requires the owned AsSaved/full batch inspection')
        _loaded_inventory(session,root,core_files,file_map)
    wrapper=None
    try:
        for row in rows:
            path = _path(root, row['file'], file_map)
            if reuse_master:
                _loaded_inventory(session,root,core_files,file_map)
            else:
                _close_owned(session, root)
                master = None
            print('M01 fresh review ' + row['id'], flush=True)
            wrapper, status = session.Parts.OpenDisplay(str(path))
            _loaded(wrapper, status, row['id'])
            _prototype_path(root,row['file'],wrapper.FullPath,file_map)
            if not wrapper.IsFullyLoaded or wrapper.PartUnits != NXOpen.BasePart.Units.Millimeters:
                raise ValueError('Review wrapper units differ')
            for key, expected in {'M01_REVIEW_SCOPE': 'M01_REVIEW', 'M01_REVIEW_ID': row['id'],
                                   'M01_REVIEW_STATE': row['state']}.items():
                if read_attribute(wrapper, key) != expected:
                    raise ValueError('Review wrapper identity differs: ' + row['id'])
            assembly_root = wrapper.ComponentAssembly.RootComponent
            children = list(assembly_root.GetChildren()) if assembly_root is not None else []
            if len(children) != 1:
                raise ValueError('Review must contain exactly one shared master occurrence')
            child = children[0]
            master = child.Prototype
            if (Path(child.Prototype.FullPath).resolve() != master_path
                    or read_attribute(child.Prototype, 'M01_PROJECT') != PROJECT
                    or child.UsedArrangement.Name != catalog[row['state']]):
                raise ValueError('Review shared master or used arrangement differs: ' + row['id'])
            position, rotation = child.GetPosition()
            if (any(abs(value) > 1e-8 for value in (position.X, position.Y, position.Z))
                    or any(abs(getattr(rotation, key) - expected) > 1e-10
                           for key, expected in zip(('Xx', 'Xy', 'Xz', 'Yx', 'Yy', 'Yz', 'Zx', 'Zy', 'Zz'),
                                                    (1, 0, 0, 0, 1, 0, 0, 0, 1)))):
                raise ValueError('Review master occurrence is not at identity')
            occurrences = _occurrences(child)
            if set(occurrences) != set(nodes) - {'MASTER'}:
                raise ValueError('Review nested occurrence inventory differs: ' + row['id'])
            for nid,component in occurrences.items():
                _prototype_path(root,nodes[nid]['file'],component.Prototype.FullPath,file_map)
            _loaded_inventory(session,root,core_files|{row['file']},file_map)
            dependencies=_native_dependencies(wrapper,root,core_files|{row['file']},file_map)
            counts, markers = _visible(wrapper, nodes, occurrences)
            visible = _visible_record(layout, row['state'], counts, markers)
            presentation = read_presentation(wrapper)
            _check_presentation(presentation, layout['presentation'])
            result[row['id']] = {'file': row['file'], 'state': row['state'], 'master': layout['master'],
                                 **visible, 'presentation': presentation, 'fully_loaded':True,'units':'mm',
                                 'native_dependencies':dependencies,'fresh_wrapper_from_disk':True,
                                 'core_reused':bool(reuse_master),
                                 'open_scope':'FRESH_WRAPPER_REUSED_FULL_CORE' if reuse_master else 'COLD_FULL_ENTRY_TREE'}
            if reuse_master:
                wrapper.Close(NXOpen.BasePart.CloseWholeTree.FalseValue,
                              NXOpen.BasePart.CloseModified.CloseModified,None)
                wrapper=None
                _restore(session,master,layout)
                _loaded_inventory(session,root,core_files,file_map)
    finally:
        try:
            if reuse_master and wrapper is not None:
                _prototype_path(root,row['file'],wrapper.FullPath,file_map)
                wrapper.Close(NXOpen.BasePart.CloseWholeTree.FalseValue,
                              NXOpen.BasePart.CloseModified.CloseModified,None)
            if master is not None:
                _restore(session, master, layout)
        finally:
            if _hashes(root) != before:
                raise ValueError('Read-only review inspection changed native Part bytes')
    return result
