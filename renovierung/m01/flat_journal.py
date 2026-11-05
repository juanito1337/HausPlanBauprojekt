"""Native packing and verification of a portable single-directory M01 assembly."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def verify_core(session, root, layout, file_map, manifest):
    from renovierung.k02.nx_verify import open_all
    from renovierung.m01.delivery_paths import logicalfile, mapfile
    from renovierung.m01.inspection import inspect_reviews
    from renovierung.m01.nx_journal import display_part, inspect_nodes, inspect_parts, test_visibility
    from renovierung.m01.standalone import inspect_subassemblies
    from renovierung.m01.states import state_catalog, test_arrangements
    master = open_all(session, root, file_map[layout['master']], 'AsSaved')
    if master.ComponentAssembly.ActiveArrangement.Name != state_catalog(layout)[layout['default_state']]:
        raise ValueError('Saved default arrangement differs')
    loaded = {logicalfile(root, p.FullPath, file_map) for p in session.Parts}
    required = {n['file'] for n in layout['nodes']}
    for logical in sorted(required - loaded):
        _, status = session.Parts.OpenBase(str(mapfile(root,logical,file_map)))
        try:
            if status.NumberUnloadedParts:
                raise ValueError('Unloaded core Part: '+logical)
        finally:
            status.Dispose()
    display_part(session, master)
    print('M01 flat: verify complete source and native body measurements', flush=True)
    nodes, occurrences = inspect_nodes(master,root,layout,file_map)
    parts,deps,refs,measurements,facets,context,piles = inspect_parts(
        session,master,root,layout,manifest,file_map,core_only=True)
    toggles = test_visibility(master, layout, occurrences)
    print('M01 flat: verify 36 arrangements',flush=True)
    arrangements = test_arrangements(master,layout)
    print('M01 flat: inspect 35 separate review files',flush=True)
    reviews = inspect_reviews(session,root,layout,file_map=file_map,reuse_master=True)
    for record in reviews.values():
        parts.append(record['file'])
        deps[record['file']] = record['native_dependencies']
    restored,_ = inspect_nodes(session.Parts.Display,root,layout,file_map)
    if restored != nodes:
        raise ValueError('Saved master was not restored after inspecting entry files')
    print('M01 flat: isolated sections and fields',flush=True)
    standalone = inspect_subassemblies(session,root,layout,file_map=file_map)
    return dict(status='PASS',master=layout['master'],mode='verify',load_method='AsSaved',
                nodes=nodes,parts=sorted(parts),dependencies=deps,measurements=measurements,
                refsets=refs,refset_facets=facets,context_measurements=context,
                pile_locations=piles,arrangements=arrangements,reviews=reviews,standalone=standalone,
                toggle_checks=toggles,state_checks=list(arrangements['catalog']),all_parts_mm=True,
                all_parts_fully_loaded=True,all_paths_internal=True,construction_release=False,
                files_saved_by_verifier=False)


def main():
    req=json.loads(Path(os.environ['M01_NX_REQUEST']).read_bytes())
    sys.path.insert(0,req['repo_root'])
    result={'status':'FAIL','construction_release':False}
    try:
        import NXOpen
        from renovierung.m01.delivery_paths import make_file_map
        from renovierung.m01.layout import validate_layout
        session=NXOpen.Session.GetSession()
        if list(session.Parts) or not session.IsBatch:
            raise RuntimeError('Fresh owned batch NX required')
        if req['mode'] in {'flat_pack','flat_core','flat_style'}:
            session.Parts.LoadOptions.PartLoadOption=NXOpen.LoadOptions.LoadOption.FullyLoad
        layout=req['layout']
        validate_layout(layout)
        root=Path(req['directory']).resolve()
        file_map=make_file_map(layout)
        if file_map!=req['file_map']:
            raise ValueError('Delivery filename mapping changed')
        if req['mode']=='flat_pack':
            from renovierung.m01.flat_pack import build_flat_pack
            pack=build_flat_pack(session,Path(req['source_directory']).resolve(),root,layout,file_map,
                                 preserve_leaf_bytes=True)
            result.update(status='PASS',pack=pack)
        elif req['mode']=='flat_style':
            from renovierung.k02.nx_verify import open_all
            from renovierung.m01.display import components
            from renovierung.m01.states import _check_errors, activate_state
            part = open_all(session,root,file_map[layout['master']],'FromDirectory')
            occurrences = components(part)
            ids = [n['id'] for n in layout['nodes'] if n['kind']=='role' and n['blank']]
            assembly = part.ComponentAssembly
            arrangements = list(assembly.Arrangements)
            import NXOpen.Assemblies
            for arrangement in arrangements:
                needed=[]
                for ident in ids:
                    state,controlled=assembly.GetSuppressedState(occurrences[ident],arrangement)
                    if not controlled or state!=NXOpen.Assemblies.ComponentAssembly.SuppressedState.Suppressed:
                        needed.append(occurrences[ident])
                if needed:
                    _check_errors(assembly.SuppressComponents(needed,[arrangement]),'auxiliary roles')
            activate_state(part,layout['default_state'])
            part.Save(NXOpen.BasePart.SaveComponents.FalseValue,NXOpen.BasePart.CloseAfterSave.FalseValue).Dispose()
            result.update(status='PASS',suppressed_auxiliary_ids=sorted(ids),arrangements=len(arrangements))
        else:
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.prt')}
            expected={file_map[p['path']]:p['sha256'] for p in req['parts']}
            if before!=expected:
                raise ValueError('Flat input Parts differ from byte manifest')
            if req['mode']=='flat_core':
                result=verify_core(session,root,layout,file_map,req['parts'])
            elif req['mode']=='flat_default':
                from renovierung.m01.standalone import default_entry_probe
                result.update(entries=default_entry_probe(session,root,layout,file_map=file_map),
                              status='PASS',files_saved_by_verifier=False)
            else:
                raise ValueError('Unsupported flat verification phase')
            after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.prt')}
            if before!=after:
                raise ValueError('Review changed native file bytes')
    except Exception as error:
        result.update(status='FAIL',error=str(error),traceback=traceback.format_exc())
        if hasattr(error,'evidence'):
            result['pack_failure']=error.evidence
    Path(req['report']).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    if result['status']!='PASS':
        raise RuntimeError(result['error'])


if __name__=='__main__':
    main()
