"""Read-only isolated field/section checks, last operation in an owned batch NX."""
from pathlib import Path


def _spec(layout, node_id):
    from .inspection import build_review_index
    build_review_index(layout)
    fields = layout['fields']
    field = next((f for f in fields if f['node_id'] == node_id), None)
    if field is not None:
        return {'state': 'ISOLATED_FIELD', 'selected_field': field['id'] if field['native'] else None,
                'visible_marker_ids': [field['id']]}
    section = next((s['id'] for s in layout['sections'] if 'SECTION_' + s['id'] == node_id), None)
    if section is None:
        raise ValueError('Unknown standalone field/section node: ' + str(node_id))
    members = [f for f in fields if f['sector_id'] == section]
    candidates = sorted(f['id'] for f in members if f['native'])
    selected = candidates[0] if candidates else None
    return {'state': 'SECTION_DEFAULT', 'selected_field': selected,
            'visible_marker_ids': sorted(f['id'] for f in members if not f['native'] or f['id'] == selected)}


def _close_owned(session, root):
    """Official NX2406 CloseAll API, guarded against GUI or foreign/unsaved Parts."""
    import NXOpen
    if not session.IsBatch:
        raise ValueError('Isolated review may close Parts only in the owned batch NX process')
    for part in session.Parts:
        if not part.FullPath:
            raise ValueError('Refusing to close an unsaved Part')
        path = Path(part.FullPath).resolve()
        path.relative_to(root)
        if not path.is_file() or path.suffix.lower() != '.prt':
            raise ValueError('Refusing to close a Part outside the saved delivery inventory')
    session.Parts.CloseAll(NXOpen.BasePart.CloseModified.CloseModified, None)
    if list(session.Parts):
        raise ValueError('Native CloseAll did not unload every Part')


def inspect_subassemblies(session, root, layout, file_map=None, *, load_method='AsSaved'):
    """Freshly load each field/section; discard only owned batch in-memory changes.

    Call last: the master and every previously loaded delivery Part are unloaded.
    No Part save, visibility mutation, or camera mutation is performed.
    """
    import NXOpen
    import NXOpen.Facet
    from .display import read_attribute
    from .inspection import (_check_presentation, _configure_load, _hashes, _loaded,
                             _loaded_inventory, _path, _prototype_path)
    from .presentation import read_presentation
    from .states import ROLES, _visible
    root = Path(root).resolve()
    nodes = {n['id']: n for n in layout['nodes']}
    fields = {f['node_id']: f for f in layout['fields']}
    ids = set(fields) | {'SECTION_' + s['id'] for s in layout['sections']}
    before, result = _hashes(root), {}
    _configure_load(session,load_method,full=True)
    try:
        for node_id in sorted(ids):
            _close_owned(session, root)
            print('M01 fresh subassembly ' + node_id, flush=True)
            row, spec = nodes[node_id], _spec(layout, node_id)
            part, status = session.Parts.OpenDisplay(str(_path(root, row['file'],file_map)))
            _loaded(part, status, row['file'])
            _prototype_path(root,row['file'],part.FullPath,file_map)
            if (read_attribute(part, 'M01_NODE_ID') != node_id
                    or not part.IsFullyLoaded or part.PartUnits != NXOpen.BasePart.Units.Millimeters):
                raise ValueError('Isolated root identity or units differ: ' + node_id)
            local_ids = {node_id}
            while True:
                expanded = local_ids | {nid for nid, node in nodes.items() if node['parent'] in local_ids}
                if expanded == local_ids:
                    break
                local_ids = expanded
            occurrences = {}

            def walk(parent, parent_id):
                for component in parent.GetChildren():
                    ident = read_attribute(component, 'M01_NODE_ID')
                    if ident in occurrences or ident not in local_ids or nodes[ident]['parent'] != parent_id:
                        raise ValueError('Isolated occurrence hierarchy differs: ' + node_id)
                    _prototype_path(root,nodes[ident]['file'],component.Prototype.FullPath,file_map)
                    occurrences[ident] = component
                    walk(component, ident)

            assembly_root = part.ComponentAssembly.RootComponent
            if assembly_root is not None:
                walk(assembly_root, node_id)
            if set(occurrences) != local_ids - {node_id}:
                raise ValueError('Isolated occurrence inventory differs: ' + node_id)
            _loaded_inventory(session,root,{nodes[nid]['file'] for nid in local_ids},file_map)
            counts, marker_nodes = _visible(part, nodes, occurrences)
            markers = {fields[nid]['id'] for nid in marker_nodes}
            for obj in part.ModelingViews.WorkView.AskVisibleObjects():
                if obj.OwningComponent is not None:
                    continue
                if isinstance(obj, (NXOpen.Body, NXOpen.Facet.FacetedBody)):
                    raise ValueError('Unexpected root-owned isolated body: ' + node_id)
                if isinstance(obj, NXOpen.Curve) and obj.Name.startswith('M01_REGISTER_'):
                    markers.add(obj.Name[len('M01_REGISTER_'):])
            roles = {role: 0 for role in ROLES}
            for nid in local_ids:
                node = nodes[nid]
                if node['kind'] != 'role':
                    continue
                field = fields[node['parent']]
                count = (field['measurements'][node['role']]['body_count']
                         if field['id'] == spec['selected_field'] and not node['blank'] else 0)
                if counts.get(nid, 0) != count:
                    raise ValueError('Isolated role B-rep occurrence count differs: ' + node_id + ' ' + nid)
                roles[node['role']] += count
            if sorted(markers) != spec['visible_marker_ids']:
                raise ValueError('Isolated field markers differ: ' + node_id + ' ' + repr(sorted(markers)))
            for nid, component in occurrences.items():
                if nid in fields:
                    field = fields[nid]
                    hidden = bool(field['native'] and field['id'] != spec['selected_field'])
                    if bool(component.IsBlanked) != hidden:
                        raise ValueError('Isolated section field Blank differs: ' + nid)
            presentation = read_presentation(part)
            _check_presentation(presentation, layout['presentation'])
            result[row['file']] = {'state': spec['state'], 'visible_role_bodies': roles,
                                   'visible_marker_ids': sorted(markers), 'presentation': presentation}
    finally:
        try:
            _close_owned(session, root)
        finally:
            if _hashes(root) != before:
                raise ValueError('Read-only isolated inspection changed native Part bytes')
    return result


def _default_entries(layout):
    """Logical Master + review + field/section rows; no metadata mutation."""
    from .inspection import _index
    nodes={n['id']:n for n in layout['nodes']}
    rows=[{'id':'MASTER','kind':'master','file':layout['master'],'state':layout['default_state']}]
    rows.extend(dict(row,kind='review') for row in _index(layout))
    ids={f['node_id'] for f in layout['fields']}|{'SECTION_'+s['id'] for s in layout['sections']}
    for nid in sorted(ids):
        intent=_spec(layout,nid)
        rows.append({'id':nid,'kind':'subassembly','file':nodes[nid]['file'],
                     'state':intent['selected_field'],'marker_ids':intent['visible_marker_ids']})
    return rows


def _default_snapshot(part,layout):
    """One native display query before reference walking; never loads B-reps."""
    import NXOpen
    import NXOpen.Assemblies
    import NXOpen.Facet
    from .display import read_attribute
    fields={f['node_id']:f['id'] for f in layout['fields']}
    kinds={'brep_display_objects':set(),'facet_display_objects':set(),'component_display_proxies':set()}
    node_ids=set();markers=set();marker_proxies=set();component_nodes=set();unclassified=0
    objects=list(part.ModelingViews.WorkView.AskVisibleObjects())
    for obj in objects:
        # Component is itself the visible lightweight proxy. Faces/edges are
        # irrelevant here: do not make an OwningComponent call for each one.
        if isinstance(obj,NXOpen.Assemblies.Component):
            owner=obj;kind='component_display_proxies'
        elif isinstance(obj,NXOpen.Body):owner=obj.OwningComponent;kind='brep_display_objects'
        elif isinstance(obj,NXOpen.Facet.FacetedBody):owner=obj.OwningComponent;kind='facet_display_objects'
        elif isinstance(obj,NXOpen.Curve):owner=obj.OwningComponent;kind='curve'
        else:continue
        nid=None
        if owner is not None:
            try:nid=read_attribute(owner,'M01_NODE_ID')
            except ValueError:pass  # Native display proxies can omit a deep owner.
        if kind=='curve':
            if nid in fields:markers.add(fields[nid])
            elif owner is None and obj.Name.startswith('M01_REGISTER_'):
                markers.add(obj.Name[len('M01_REGISTER_'):])
            continue
        kinds[kind].add((owner.Tag if owner is not None else None,obj.Tag))
        if kind=='component_display_proxies' and nid is not None:
            component_nodes.add(nid)
            if nid in fields:marker_proxies.add(fields[nid])
        if nid is None:unclassified+=1
        else:node_ids.add(nid)
    return {**{kind:len(tags) for kind,tags in kinds.items()},'visible_node_ids':sorted(node_ids),
            'visible_marker_ids':sorted(markers),'visible_marker_proxy_ids':sorted(marker_proxies),
            'component_proxy_node_ids':sorted(component_nodes),'native_visible_object_count':len(objects),
            'unclassified_geometry_objects':unclassified,
            'exact_brep_body_counts_verified':False}


def _default_graph(part,entry,root,layout,file_map):
    """Check directly resolved paths and effective role flags without body loads."""
    from .display import PROJECT,read_attribute
    from .inspection import _prototype_path
    from .states import state_catalog
    nodes={n['id']:n for n in layout['nodes']}
    fields={f['node_id']:f for f in layout['fields']}
    assembly=part.ComponentAssembly.RootComponent
    children=list(assembly.GetChildren()) if assembly is not None else []
    if entry['kind']=='review':
        if len(children)!=1:raise ValueError('Default review must directly resolve one shared master')
        shared=children[0]
        _prototype_path(root,layout['master'],shared.Prototype.FullPath,file_map)
        if (read_attribute(shared.Prototype,'M01_PROJECT')!=PROJECT or
                shared.UsedArrangement.Name!=state_catalog(layout)[entry['state']]):
            raise ValueError('Default review master or used arrangement differs')
        assembly=shared
        children=list(shared.GetChildren())
        parent_id='MASTER'
    else:parent_id=entry['id']
    expected_direct={nid for nid,n in nodes.items() if n['parent']==parent_id}
    roles={};direct={};seen=set()
    def walk(parent,parent_id,inherited=False,depth=0):
        for component in parent.GetChildren():
            nid=read_attribute(component,'M01_NODE_ID')
            if nid in seen or nid not in nodes or nodes[nid]['parent']!=parent_id:
                raise ValueError('Default entry occurrence identity/hierarchy differs: '+str(nid))
            seen.add(nid)
            _prototype_path(root,nodes[nid]['file'],component.Prototype.FullPath,file_map)
            if depth==0:direct[nid]=nodes[nid]['file']
            hidden=inherited or bool(component.IsBlanked) or bool(component.IsSuppressed)
            if nodes[nid]['kind']=='role':
                field=fields[nodes[nid]['parent']]
                wanted=bool(field['id']==entry['state'] and not nodes[nid]['blank'])
                if component.ReferenceSet!=nodes[nid]['reference_set'] or (not hidden)!=wanted:
                    raise ValueError('Default effective role component differs: '+nid)
                roles[nid]={'effective_visible':not hidden,'reference_set':component.ReferenceSet}
            walk(component,nid,hidden,depth+1)
    if assembly is not None:walk(assembly,parent_id)
    if set(direct)!=expected_direct:
        raise ValueError('Default entry direct component references do not resolve completely')
    wanted={nid for nid,n in nodes.items() if n['kind']=='role' and
            fields[n['parent']]['id']==entry['state'] and not n['blank']}
    if not wanted<=set(roles):
        raise ValueError('Default display graph does not offer selected role components')
    return {'direct_references':direct,
            'root_direct_references':{'MASTER':layout['master']} if entry['kind']=='review' else dict(direct),
            'effective_role_components':roles,'selected_role_ids':sorted(wanted)}


def default_entry_probe(session,root,layout,file_map=None,*,load_method='FromDirectory'):
    """121 cold direct opens in a separate fresh owned NX session, no search paths.

    Read camera/layers/display objects immediately after each open, before any
    prototype walk. Preserve the process's native partial/lightweight/component
    defaults; record them instead of claiming factory defaults or exact B-reps.
    Run this as its own fresh journal, separately from the AsSaved/full proof.
    """
    import NXOpen
    from .display import PROJECT,read_attribute
    from .inspection import (_check_presentation,_configure_load,_hashes,_loaded,
                             _loaded_inventory,_path,_prototype_path)
    from .presentation import read_presentation
    if not session.IsBatch or list(session.Parts):
        raise ValueError('Default entry proof requires its own empty owned batch NX session')
    root=Path(root).resolve()
    options=_configure_load(session,load_method,full=False)
    before=_hashes(root);result={};nodes={n['id']:n for n in layout['nodes']}
    core_files={n['file'] for n in nodes.values()}
    try:
        for entry in _default_entries(layout):
            _close_owned(session,root)
            part,status=session.Parts.OpenDisplay(str(_path(root,entry['file'],file_map)))
            _loaded(part,status,entry['file'])
            # Capture the as-opened display before any potentially lazy prototype access.
            presentation=read_presentation(part)
            _check_presentation(presentation,layout['presentation'])
            snapshot=_default_snapshot(part,layout)
            fully_loaded_at_snapshot=all(p.IsFullyLoaded for p in session.Parts)
            _prototype_path(root,entry['file'],part.FullPath,file_map)
            if part.PartUnits!=NXOpen.BasePart.Units.Millimeters:raise ValueError('Default root units differ')
            if entry['kind']=='review':
                if (read_attribute(part,'M01_REVIEW_SCOPE')!='M01_REVIEW' or
                        read_attribute(part,'M01_REVIEW_ID')!=entry['id'] or
                        read_attribute(part,'M01_REVIEW_STATE')!=entry['state']):
                    raise ValueError('Default review root metadata differs')
            elif entry['kind']=='master':
                if read_attribute(part,'M01_PROJECT')!=PROJECT:raise ValueError('Default master identity differs')
            elif read_attribute(part,'M01_NODE_ID')!=entry['id']:
                raise ValueError('Default standalone root identity differs')
            graph=_default_graph(part,entry,root,layout,file_map)
            if graph['selected_role_ids'] and not (snapshot['brep_display_objects']+snapshot['facet_display_objects']+snapshot['component_display_proxies']):
                raise ValueError('Default entry has no actual visible native geometry')
            if not graph['selected_role_ids'] and not (snapshot['visible_marker_ids'] or snapshot['visible_marker_proxy_ids']):
                raise ValueError('Default blocked register entry has no visible native marker')
            role_nodes={nid for nid,n in nodes.items() if n['kind']=='role'}
            observed=set(snapshot['visible_node_ids'])&role_nodes
            if observed-set(graph['selected_role_ids']):raise ValueError('Default view displays an unselected role proxy')
            if set(graph['selected_role_ids'])-observed and not snapshot['unclassified_geometry_objects']:
                raise ValueError('Default native display graph omits an expected selected role proxy')
            expected=core_files|{entry['file']}
            if entry['kind']=='subassembly':
                ids={entry['id']}
                while True:
                    more=ids|{nid for nid,n in nodes.items() if n['parent'] in ids}
                    if more==ids:break
                    ids=more
                expected={nodes[nid]['file'] for nid in ids}
            loaded=_loaded_inventory(session,root,expected,file_map,full=False,require_all=False,include_physical=True)
            result[entry['file']]={'id':entry['id'],'file':entry['file'],'kind':entry['kind'],'state':entry['state'],
                'presentation':presentation,'display_snapshot':snapshot,'load_options':dict(options),
                'snapshot_before_reference_walk':True,'fully_loaded_at_snapshot':fully_loaded_at_snapshot,
                'exact_brep_verified':False,'brep_mass_measurements_performed':False,
                'selected_role_proxy_ids':sorted(observed),'selected_role_proxy_match_complete':observed==set(graph['selected_role_ids']),
                'loaded_files':sorted(loaded),'loaded_full_paths':loaded,'root_directory':str(root),
                'root_full_path':str(Path(part.FullPath).resolve()),'flat_delivery':file_map is not None,
                'all_loaded_paths_internal':True,'all_prototype_paths_match_map':True,'files_saved':False,**graph}
    finally:
        try:_close_owned(session,root)
        finally:
            if _hashes(root)!=before:raise ValueError('Default entry proof changed saved native Part bytes')
    return result


def validate_default_entries(layout,actual):
    """Pure gate for recorded 121-entry cold/default evidence, never NX calls.

    Component display proxies are actual scene evidence, distinct from loaded
    B-rep bodies. This gate requires the selected cut-soil/main-pile scene and
    excludes excavation/reserve proxies; it never promotes minimal-load data
    into an exact B-rep measurement proof.
    """
    from pathlib import PurePosixPath,PureWindowsPath
    from .delivery_paths import make_file_map
    from .inspection import _check_presentation
    errors=[]
    try:
        rows={r['file']:r for r in _default_entries(layout)}
        if not isinstance(actual,dict) or set(actual)!=set(rows):
            return ['Default entry inventory differs from the exact logical Master/review/subassembly matrix']
        nodes={n['id']:n for n in layout['nodes']}
        fields={f['node_id']:f for f in layout['fields']}
        role_ids={nid for nid,n in nodes.items() if n['kind']=='role'}
        file_map=make_file_map(layout)
        roots=set()
        for logical,entry in rows.items():
            try:
                record=actual[logical]
                if any(record[k]!=entry[k] for k in ('id','file','kind','state')):
                    raise ValueError('Logical entry identity/file/state differs')
                if (record['snapshot_before_reference_walk'] is not True or record['files_saved'] is not False or
                        record['exact_brep_verified'] is not False or record['brep_mass_measurements_performed'] is not False or
                        record['all_loaded_paths_internal'] is not True or record['all_prototype_paths_match_map'] is not True):
                    raise ValueError('Missing immediate read-only display/path evidence or false exact-B-rep claim')
                _check_presentation(record['presentation'],layout['presentation'])
                options=record['load_options']
                if (options['requested_component_load_method']!='FromDirectory' or
                        options['component_load_method_matches_requested'] is not True or
                        options['supplementary_search_directories']!=[]):
                    raise ValueError('Default entry must use FromDirectory without supplementary search paths')
                root_text=record['root_directory']
                path_type=PureWindowsPath if PureWindowsPath(root_text).drive else PurePosixPath
                root=path_type(root_text)
                if not root.is_absolute() or '..' in root.parts:
                    raise ValueError('Invalid physical delivery root')
                roots.add(str(root).casefold())
                flat=record['flat_delivery']
                if type(flat) is not bool:raise ValueError('Missing physical delivery mapping mode')
                def physical(path_text,logical_file):
                    path=path_type(path_text)
                    if not path.is_absolute():raise ValueError('Native FullPath is not absolute')
                    relative=path.relative_to(root)
                    expected=file_map[logical_file] if flat else logical_file
                    if '..' in relative.parts or relative.as_posix().casefold()!=expected.casefold():
                        raise ValueError('Native FullPath differs from the root-relative logical mapping')
                physical(record['root_full_path'],logical)
                parent='MASTER' if entry['kind'] in ('master','review') else entry['id']
                direct={nid:n['file'] for nid,n in nodes.items() if n['parent']==parent}
                root_direct={'MASTER':layout['master']} if entry['kind']=='review' else direct
                if record['direct_references']!=direct or record['root_direct_references']!=root_direct:
                    raise ValueError('Direct logical component references differ')
                allowed={n['file'] for n in nodes.values()}|{logical}
                if entry['kind']=='subassembly':
                    ids={entry['id']}
                    while True:
                        more=ids|{nid for nid,n in nodes.items() if n['parent'] in ids}
                        if more==ids:break
                        ids=more
                    allowed={nodes[nid]['file'] for nid in ids}
                loaded=record['loaded_files'];paths=record['loaded_full_paths']
                if len(loaded)!=len(set(loaded)) or set(loaded)!=set(paths) or set(loaded)-allowed:
                    raise ValueError('Unlisted/duplicate loaded prototype files')
                if not ({logical}|set(root_direct.values()))<=set(loaded):
                    raise ValueError('Default root/direct referenced prototypes were not resolved')
                for name,path in paths.items():physical(path,name)
                wanted={nid for nid in role_ids if fields[nodes[nid]['parent']]['id']==entry['state'] and not nodes[nid]['blank']}
                effective=record['effective_role_components']
                if not wanted<=set(effective):raise ValueError('Missing selected role component metadata')
                for nid,value in effective.items():
                    if (nid not in role_ids or type(value['effective_visible']) is not bool or
                            value['effective_visible']!=(nid in wanted) or value['reference_set']!=nodes[nid]['reference_set']):
                        raise ValueError('Effective role flags/reference sets differ')
                scene=record['display_snapshot']
                counts=[scene[k] for k in ('component_display_proxies','brep_display_objects','facet_display_objects')]
                if (any(type(v) is not int or v<0 for v in counts) or
                        type(scene['native_visible_object_count']) is not int or scene['native_visible_object_count']<=0 or
                        scene['exact_brep_body_counts_verified'] is not False):
                    raise ValueError('Missing real native display representations or false body-count claim')
                visible=set(scene['visible_node_ids']);components=set(scene['component_proxy_node_ids'])
                if not visible<=set(nodes) or not components<=visible or len(components)>scene['component_display_proxies']:
                    raise ValueError('Unlisted visible native node/component proxies')
                observed=visible&role_ids
                if (observed!=wanted or set(record['selected_role_ids'])!=wanted or
                        set(record['selected_role_proxy_ids'])!=wanted or record['selected_role_proxy_match_complete'] is not True):
                    raise ValueError('Selected cut-soil/main scene missing or excavation/reserve/unselected proxy visible')
                if wanted and not sum(counts):raise ValueError('No visible geometry or Component proxies for native field')
                markers=set(scene['visible_marker_ids'])|set(scene['visible_marker_proxy_ids'])
                marker_wanted=entry.get('marker_ids')
                if marker_wanted is None:
                    marker_wanted=[f['id'] for f in layout['fields'] if f['id']==entry['state'] or f['sector_id']==entry['state']]
                if markers!=set(marker_wanted):raise ValueError('Default visible marker/marker-component proxies differ')
            except (KeyError,TypeError,ValueError,AttributeError,OverflowError) as error:
                errors.append(logical+': '+str(error))
        if len(roots)!=1:errors.append('Default entries do not share one physical delivery root')
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError) as error:
        errors.append('Malformed default-entry evidence: '+str(error))
    return errors
