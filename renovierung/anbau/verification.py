"""Independent, read-only acceptance of the flat M01 plus annex delivery.

Pure expectations bind the old layout, prepared annex leaves, shared site and
post-clone/pre-upgrade bytes separately. Native entry points require an empty
owned batch. They never save Parts or regenerate geometry. Full B-rep proof and
cold directory/minimal display proof are intentionally separate observations.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

from renovierung.m01.delivery_paths import make_file_map, mapfile
from renovierung.m01.states import ROLES, DETAIL_HIDDEN, state_catalog, state_spec

SCHEMA='ANBAU_END_VERIFICATION_V1'
LAYERS=(101,102,103,104,200,201,210,240)
I=[1,0,0,0,1,0,0,0,1]
MATRIX_KEYS=('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz')
BODY_KINDS={'role','context','annex_site','diagnostic'}
VISIBILITY_KEYS=('body_counts','visible_role_bodies','visible_context_ids','visible_site_shell_ids',
                 'visible_field_ids','visible_diagnostic_bodies','terrain_visible')


class NativeVerificationFailure(ValueError):
    """Actual observations from a failed run, explicitly never acceptance."""
    def __init__(self,message,evidence):
        super().__init__(message)
        self.evidence=evidence


def failure_evidence(result,spec,phase):
    counts={key:len(result.get(key,{})) for key in ('states','public_selections','reviews','standalone',
        'entries','context_measurements','old_field_measurements','new_fields','sections')}
    return dict(result,status='FAIL',partial_evidence_only=True,complete_release=False,
                verification_spec_sha256=spec['spec_sha256'],failed_phase=deepcopy(phase),completed_scope_counts=counts)


def _failure_snapshot(session,root,spec,result):
    """Failure-only scene observation; no repair and no exact-body promotion."""
    from renovierung.m01.standalone import _default_snapshot
    try:
        part=session.Parts.Display
        if part is not None and part.FullPath and Path(part.FullPath).resolve().parent==root:
            result['failure_display_file']=str(Path(part.FullPath).resolve())
            result['failure_display_snapshot']=_default_snapshot(part,spec['layout'])
    except Exception as error:
        result['failure_display_snapshot_error']=str(error)


def _close_and_guard(session,root,spec,before,source_before,result):
    from renovierung.m01.standalone import _close_owned
    errors=[];guards=result['byte_guards']
    try:_close_owned(session,root)
    except Exception as error:errors.append('Owned-part close: '+str(error))
    try:
        after=inspect_files(root,spec);result['file_manifest_after']=after
        if after!=before:raise ValueError('Read-only verification changed Part bytes')
        guards['target_parts_unchanged']=True
    except Exception as error:
        guards['target_parts_unchanged']=False;errors.append(str(error))
    try:
        if _source_guard(spec)!=source_before:raise ValueError('Read-only verification changed original source bytes')
        guards['original_source_unchanged']=True
    except Exception as error:
        guards['original_source_unchanged']=False;errors.append(str(error))
    if errors:raise NativeVerificationFailure('; '.join(errors),failure_evidence(result,spec,{'operation':'close_and_byte_guards'}))


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                    ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def _ids(values,wanted,label):
    if not isinstance(values,list) or any(not isinstance(x,str) for x in values) or len(set(values))!=len(values) or set(values)!=set(wanted):
        raise ValueError('Missing, extra or duplicate '+label)


def _numbers(values,wanted,label,tol=1e-8):
    if (not isinstance(values,(list,tuple)) or len(values)!=len(wanted) or
            any(type(a) not in (int,float) or not math.isfinite(a) or abs(a-b)>tol for a,b in zip(values,wanted))):
        raise ValueError('Native finite numbers differ: '+label)


def validate_presentation(actual,wanted,*,require_conflict_layer=True):
    """Compare absolute camera and semantic layer states, never numeric enums."""
    from renovierung.m01.proof import _presentation
    legacy=deepcopy(actual)
    if not isinstance(actual.get('layers'),dict) or set(actual['layers'])!={str(n) for n in LAYERS}:
        raise ValueError('Native presentation layer inventory differs')
    layer=actual['layers']['240']
    if not isinstance(layer,dict) or any(type(layer.get(k)) is not bool for k in ('visible','selectable','hidden')):
        raise ValueError('Missing semantic native layer240 state')
    if require_conflict_layer and (layer['visible'] is not True or layer['selectable'] is not True or layer['hidden'] is not False):
        raise ValueError('Native conflict layer240 is not visible/selectable')
    legacy['layers'].pop('240');_presentation(legacy,wanted)
    if 'archive_layer_241' in actual and actual['archive_layer_241'].get('hidden') is not True:
        raise ValueError('Archived old note layer241 is not hidden')


def _descendants(nodes,root):
    result={root}
    while True:
        more=result|{n['id'] for n in nodes.values() if n['parent'] in result}
        if more==result:return result
        result=more


def verification_spec(upgrade,field_inputs,site_entry,baseline_parts):
    """Build independent expectations from canonical inputs, not upgrade.states.

    baseline_parts is the physical basename->{bytes,sha256} inventory captured
    after native independent cloning and before the authorized Part changes
    (34 canonical owner/container/master/review Parts in the current delivery).
    Compact synthetic layouts are accepted for pure contract tests; the real
    counts are returned explicitly for the runner's complete-delivery gate.
    """
    from renovierung.m01.inspection import build_review_index
    from renovierung.m01.standalone import _spec
    if upgrade['schema']!='ANBAU_M01_UPGRADE_SPEC_V1':raise ValueError('Unsupported upgrade schema')
    base=deepcopy(upgrade['base_layout']);layout=deepcopy(upgrade['layout'])
    if 'base_layout_sha256' in upgrade and upgrade['base_layout_sha256']!=_hash(base):raise ValueError('Original layout source hash differs')
    if 'spec_sha256' in upgrade and upgrade['spec_sha256']!=_hash({k:v for k,v in upgrade.items() if k not in ('copy_evidence','spec_sha256')}):
        raise ValueError('Prepared upgrade hash differs')
    nodes={n['id']:n for n in layout['nodes']};old={n['id']:n for n in base['nodes']}
    if len(nodes)!=len(layout['nodes']) or len(old)!=len(base['nodes']):raise ValueError('Duplicate node IDs')
    base_map=make_file_map(base);file_map=make_file_map(layout)
    if upgrade['base_file_map']!=base_map or upgrade['file_map']!=file_map:raise ValueError('Upgrade physical file maps differ')
    if set(baseline_parts)!=set(base_map.values()):raise ValueError('Incomplete post-clone baseline inventory')
    for rec in baseline_parts.values():
        if type(rec.get('bytes')) is not int or rec['bytes']<=0 or not isinstance(rec.get('sha256'),str) or len(rec['sha256'])!=64:
            raise ValueError('Invalid baseline byte/hash certificate')
    prepared=deepcopy(field_inputs['fields']);updates=upgrade['fields'];fids=set(prepared)
    if set(updates)!=fids or not fids or fids-set(f['id'] for f in base['fields']):raise ValueError('Annex field inventory differs')
    fields={f['id']:f for f in base['fields']};new_ids=set(nodes)-set(old)
    if {n['id']:n for n in upgrade['new_nodes']}!={nid:nodes[nid] for nid in new_ids}:raise ValueError('New node declarations differ')
    declined={};boundary=base['context'].get('boundary_xyz_mm')
    if boundary:
        from tools.check_m01_clearances import clearance
        for fid,entry in prepared.items():
            if entry['spec']['mode']!='STUDY':continue
            hull=entry['spec']['field_metadata']['uncertainty_coverage_hull_xy_mm']
            distance=clearance([hull],[[p[:2] for p in boundary]],filled=False)['distance_mm']
            if distance<600:declined[fid]=distance
    def effective_free(fid):return prepared[fid]['spec']['mode']=='STUDY' and fid not in declined
    expected_new=set();sections={fields[f]['sector_id'] for f in fids};selected={}
    for sid in sections:
        members=sorted(f for f in fids if fields[f]['sector_id']==sid)
        free=[f for f in members if effective_free(f)];selected[sid]=(free or members)[0]
    mutable={base['master']}|{old[fields[f]['node_id']]['file'] for f in fids}|{old['SECTION_'+s]['file'] for s in sections}
    # A SECTION occurrence's own name, attributes and UsedArrangement are saved
    # in its direct parent's Part (CONSTRUCTION in the real canonical tree),
    # rather than in the displayed master. Derive that exact owner exemption.
    mutable.update(old[old['SECTION_'+sid]['parent']]['file'] for sid in sections)
    reviews=build_review_index(base)
    for row in reviews:
        if row['id'] in selected:row['state']=selected[row['id']];mutable.add(row['file'])
    reviews.extend({'id':f,'file':'Bauabschnitte/'+fields[f]['sector_id']+'/'+f+'.prt','state':f} for f in sorted(fids))
    if {r['id']:(r['file'],r['state']) for r in upgrade['reviews']}!={r['id']:(r['file'],r['state']) for r in reviews} or len(upgrade['reviews'])!=len(reviews):
        raise ValueError('Review inventory/state differs')
    if set(upgrade['mutable_base_files'])!=mutable or len(upgrade['mutable_base_files'])!=len(mutable):raise ValueError('Unauthorized baseline modification exemption')
    for nid,row in old.items():
        if nid not in nodes:raise ValueError('Original node removed: '+nid)
        for key in ('id','parent','file','kind','translation_mm','rotation','reference_set','blank'):
            if nodes[nid][key]!=row[key]:raise ValueError('Original structural/transform row changed: '+nid+' '+key)
    for fid,entry in prepared.items():
        leaf=entry['spec'];nid=fields[fid]['node_id'];free=effective_free(fid);source_free=leaf['mode']=='STUDY'
        if leaf['id']!=fid or leaf['construction_release'] is not False or leaf['mode'] not in ('STUDY','CONFLICT_DIAGNOSTIC'):
            raise ValueError('Invalid annex native field contract')
        if leaf['file']!=fid+('_STUDY.prt' if source_free else '_CONFLICT.prt'):raise ValueError('Unexpected annex leaf file')
        if updates[fid]['native'] is not free or updates[fid]['diagnostic'] is free:raise ValueError('Effective annex risk classification differs')
        if 'leaf_spec_sha256' in updates[fid] and updates[fid]['leaf_spec_sha256']!=_hash(leaf):raise ValueError('Prepared native leaf hash differs')
        if fid in declined:
            metadata=updates[fid]['metadata']
            if (metadata['status']!='PARCEL_EDGE_STRIP_CONFLICT_DIAGNOSTIC' or metadata['volume_m3'] is not None or
                    metadata['measurements'] or metadata['display_stockpile'] or metadata['construction_release'] is not False):
                raise ValueError('Randstreifen diagnostic retains effective quantities/release')
        diagnostic_refset='M01_EXCAVATION' if fid in declined else 'ANBAU_CONFLICT'
        wanted={('ANBAU_ROLE_'+fid+'_'+r.upper()):(r,'role','M01_'+r.upper()) for r in ROLES} if free else {
            'ANBAU_CONFLICT_'+fid:('conflict','diagnostic',diagnostic_refset)}
        if free:wanted['ANBAU_SITE_'+fid]=(None,'annex_site',site_entry['reference_sets'][fid]['name'])
        for ident,(role,kind,refset) in wanted.items():
            expected_new.add(ident);row=nodes.get(ident,{})
            if (row.get('parent')!=nid or row.get('kind')!=kind or row.get('reference_set')!=refset or
                    row.get('file')!=(site_entry['file'] if kind=='annex_site' else leaf['file']) or
                    row.get('blank')!=(role in ('excavation','pile_reserve')) or
                    role is not None and row.get('role')!=role):raise ValueError('New native component contract differs: '+ident)
            _numbers(row['translation_mm'],[0,0,0],ident);_numbers(row['rotation'],I,ident)
    if new_ids!=expected_new:raise ValueError('Unexpected new node inventory')
    free={fid for fid in prepared if effective_free(fid)}
    source_free={fid for fid,e in prepared.items() if e['spec']['mode']=='STUDY'}
    if set(site_entry['reference_sets'])!=source_free:raise ValueError('Site source reference-set fields differ')
    new_files={e['spec']['file'] for e in prepared.values()}|{site_entry['file']}
    if set(upgrade['new_leaf_files'])!=new_files:raise ValueError('New leaf inventory differs')
    catalog={**state_catalog(base),**{f:'M01_'+f.replace('-','_') for f in sorted(fids)}}
    groups={g['id']:g for g in base['context']['groups']};fieldnodes={f['node_id'] for f in base['fields']}
    oldroles={n['id'] for n in old.values() if n['kind']=='role'}
    controlled={nid for nid,n in nodes.items() if n['kind'] in BODY_KINDS|{'field'}}|(DETAIL_HIDDEN&set(nodes))|({'ENVIRONMENT','UTILITIES'}&set(nodes))
    body_nodes={nid for nid,n in nodes.items() if n['kind'] in BODY_KINDS}
    states={}
    def visibility(sid,hidden,markers,isolated=False):
        counts=dict.fromkeys(body_nodes,0);roles=dict.fromkeys(ROLES,0);shells=[];site=None;diagnostic=0
        for fid,field in fields.items():
            if fid==sid and field['native']:
                for nid in oldroles:
                    row=old[nid]
                    if row['parent']==field['node_id'] and not row['blank']:
                        count=field['measurements'][row['role']]['body_count'];counts[nid]=count;roles[row['role']]+=count
        for gid,g in groups.items():
            if not isolated and gid not in hidden:counts[gid]=g['body_count']
        if sid in prepared:
            leaf=prepared[sid]['spec']
            if effective_free(sid):
                for r in ('cut_soil','pile_main'):
                    count=leaf['geometry'][r]['body_count'];counts['ANBAU_ROLE_'+sid+'_'+r.upper()]=count;roles[r]=count
                ref=site_entry['reference_sets'][sid];counts['ANBAU_SITE_'+sid]=ref['body_count'];shells=list(ref['shell_ids'])
                site=dict(file=site_entry['file'],refset=ref['name'],shell_ids=shells,body_count=ref['body_count'])
            else:diagnostic=leaf['geometry']['excavation']['body_count'];counts['ANBAU_CONFLICT_'+sid]=diagnostic
        return dict(body_counts=counts,visible_role_bodies=roles,visible_context_ids=sorted(g for g in groups if counts[g]),
                    visible_site_shell_ids=sorted(shells),visible_field_ids=sorted(markers),visible_diagnostic_bodies=diagnostic,
                    terrain_visible=not isolated and sid=='BASE',site=site)
    for sid in catalog:
        if sid in state_catalog(base):
            hidden=set(state_spec(base,sid)['suppressed_ids'])|new_ids
            markers=[f['id'] for f in fields.values() if f['node_id'] not in hidden]
        else:
            hidden=(fieldnodes-{fields[sid]['node_id']})|oldroles|set(groups)|new_ids|({'TERRAIN'}&set(nodes));markers=[sid]
            if sid in free:hidden-={'ANBAU_ROLE_'+sid+'_CUT_SOIL','ANBAU_ROLE_'+sid+'_PILE_MAIN','ANBAU_SITE_'+sid}
            else:hidden-={'ANBAU_CONFLICT_'+sid};hidden|={'ENVIRONMENT','UTILITIES'}&set(nodes)
        states[sid]=dict(id=sid,name=catalog[sid],suppressed_ids=sorted(hidden),**visibility(sid,hidden,markers))
    if 'states' in upgrade:
        if set(upgrade['states'])!=set(states):raise ValueError('Builder state inventory differs from independent proof')
        for sid,wanted in states.items():
            row=upgrade['states'][sid]
            for key in ('name','suppressed_ids','visible_role_bodies','visible_context_ids','site','visible_field_ids','terrain_visible','visible_diagnostic_bodies'):
                if row[key]!=wanted[key]:raise ValueError('Builder state differs from independent proof: '+sid+' '+key)
    entries=[dict(id='MASTER',kind='master',file=base['master'],state=base['default_state'],root_node_id='MASTER',visibility=states[base['default_state']])]
    entries.extend(dict(row,kind='review',root_node_id='MASTER',visibility=states[row['state']]) for row in reviews)
    for nid in sorted(fieldnodes|{'SECTION_'+s['id'] for s in base['sections']}):
        fid=next((f for f in fids if fields[f]['node_id']==nid),None)
        sid=nid.removeprefix('SECTION_') if nid.startswith('SECTION_') else None
        if fid:chosen=fid;markers=[fid]
        elif sid in selected:chosen=selected[sid];markers=[chosen]
        else:intent=_spec(base,nid);chosen=intent['selected_field'];markers=intent['visible_marker_ids']
        v=visibility(chosen,set(groups),markers,isolated=True)
        local=_descendants(nodes,nid)
        v['body_counts']={k:value for k,value in v['body_counts'].items() if k in local}
        entries.append(dict(id=nid,kind='subassembly',file=nodes[nid]['file'],state=chosen,root_node_id=nid,visibility=v))
    immutable={base_map[file]:deepcopy(baseline_parts[base_map[file]]) for file in set(base_map)-mutable}
    copy_evidence=upgrade.get('copy_evidence') or {}
    if copy_evidence and copy_evidence.get('copied_parts')!=baseline_parts:raise ValueError('Post-clone baseline differs from copy certificate')
    expected_new_bytes=copy_evidence.get('new_parts',{})
    if expected_new_bytes and set(expected_new_bytes)!=new_files:raise ValueError('New leaf byte certificate differs')
    result=dict(schema=SCHEMA,base_layout=base,layout=layout,file_map=file_map,base_file_map=base_map,
                prepared_fields=prepared,site_entry=deepcopy(site_entry),catalog=catalog,states=states,
                reviews=reviews,entries=entries,controlled_ids=sorted(controlled),immutable_parts=immutable,
                new_leaf_bytes=deepcopy(expected_new_bytes),copy_evidence=deepcopy(copy_evidence),
                presentation=deepcopy(base['presentation']),upgrade_attributes={k:deepcopy(upgrade.get(k)) for k in ('schema','spec_sha256')},
                fields=deepcopy(updates),section_defaults=selected,derived_risk_declines_mm=declined,
                counts=dict(nodes=len(nodes),old_nodes=len(old),parts=len(file_map),states=len(states),reviews=len(reviews),entries=len(entries)))
    result['spec_sha256']=_hash(result)
    return result


def inspect_files(root,spec):
    """Real disk-byte gate independent of native evidence; does not modify files."""
    root=Path(root).resolve();result={}
    for path in root.rglob('*.prt'):
        if path.is_symlink() or path.parent.resolve()!=root:raise ValueError('Delivery is not physically flat/non-symlink')
        result[path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if set(result)!=set(spec['file_map'].values()):raise ValueError('Flat Part inventory differs')
    for name,wanted in {**spec['immutable_parts'],**spec['new_leaf_bytes']}.items():
        if result[name]!=wanted:raise ValueError('Unchanged baseline/new leaf bytes differ: '+name)
    return result


def _source_guard(spec):
    evidence=spec['copy_evidence']
    if not evidence:return None
    if (evidence.get('schema')!='ANBAU_M01_INDEPENDENT_COPY_V1' or evidence.get('native_independent') is not True or
            evidence.get('native_clone_completed') is not True):raise ValueError('Missing completed native independent-copy certificate')
    root=Path(evidence['source_root']).resolve();actual={}
    for path in root.rglob('*.prt'):
        if path.parent.resolve()!=root or path.is_symlink():raise ValueError('Source inventory is not physically flat')
        actual[path.name]={'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    if actual!=evidence['source_parts']:raise ValueError('Original source Part bytes changed')
    return actual


def validate_visibility(expected,actual):
    for key in ('body_counts','visible_role_bodies'):
        if set(actual[key])!=set(expected[key]) or any(type(actual[key][k]) is not int or actual[key][k]!=v for k,v in expected[key].items()):
            raise ValueError('Visible native body counts differ: '+key)
    for key in ('visible_context_ids','visible_site_shell_ids','visible_field_ids'):_ids(actual[key],expected[key],key)
    if type(actual['visible_diagnostic_bodies']) is not int or actual['visible_diagnostic_bodies']!=expected['visible_diagnostic_bodies'] or actual['terrain_visible'] is not expected['terrain_visible']:
        raise ValueError('Visible diagnostic/terrain evidence differs')


def validate_diagnostic_definition_style(node,actual):
    """Stored FIELD definition, not generic nested-component display defaults.

    Native diagnostic_style_probe_02 proves definition186/240/GetLayerOption240
    while the same master-nested component reports generic Color134/Layer1 and
    GetLayerOption-1. Those context properties do not describe its red B-reps.
    """
    for key,wanted in (('color',node['color']),('layer',node['layer']),('layer_option',node['layer'])):
        if type(actual.get(key)) is not int or actual[key]!=wanted:
            raise ValueError('Stored diagnostic definition style differs: '+key)


def validate_instance_name(node,actual,*,definition_required=True):
    """UF instance name is authoritative; custom occurrence aliases can differ.

    uf_assem.h documents AskComponentData's instance_name independently of the
    part occurrence's name. Native wrapper probes demonstrated stale custom
    occurrence aliases and a separate real instance-name defect. Require the
    repaired instance plus saved definition custom name, retaining the existing
    M01 case-insensitive comparison for NX's uppercase name normalization.
    """
    if actual.get('definition_inspection_performed') is not definition_required or actual.get('definition_inspection_scope')!=('full' if definition_required else 'normal_partial'):
        raise ValueError('Native definition inspection scope differs from the actual load profile')
    if not definition_required and ('definition_custom_name' in actual or 'diagnostic_style' in actual):
        raise ValueError('Normal partial loading cannot claim stored full-definition inspection')
    for key in (('instance_name','definition_custom_name') if definition_required else ('instance_name',)):
        if not isinstance(actual.get(key),str) or actual[key].casefold()!=node['name'].casefold():
            raise ValueError('Native authoritative instance/definition name differs: '+key)
    if not isinstance(actual.get('custom_occurrence_name'),str):raise ValueError('Missing custom occurrence name observation')
    if actual.get('reference_set')!=node['reference_set']:raise ValueError('Native occurrence reference set differs')


def component_identity_evidence(node,observed,*,full,read_definition_name):
    """Defer prototype access entirely in normal partial loading."""
    record=dict(observed,definition_inspection_performed=bool(full),definition_inspection_scope='full' if full else 'normal_partial')
    if full:record['definition_custom_name']=read_definition_name()
    validate_instance_name(node,record,definition_required=full)
    return record


def validate_default_definition_binding(spec,record,manifest):
    if (record['definition_inspection_performed'] is not False or record['definition_inspection_scope']!='normal_partial' or
            record['full_definition_evidence_required'] is not True):raise ValueError('Missing explicit normal-partial/full-definition proof separation')
    binding={'verification_spec_sha256':spec['spec_sha256'],'part_manifest_sha256':_hash(manifest)}
    if record['full_definition_binding']!=binding:raise ValueError('Normal entry is not bound to the same complete367-file full-proof inputs')


def validate_diagnostic_display(spec,expected,actual):
    """Require the actual visible red B-reps, exact names and source layers.

    The read-only observation reports native B-rep color/layer properties and
    documented component geometry-layer options. It makes no pixel/screenshot
    claim and does not load another representation or change display settings.
    """
    nodes={n['id']:n for n in spec['layout']['nodes']}
    wanted={nid:n for nid,n in expected['body_counts'].items() if n and nodes[nid]['kind']=='diagnostic'}
    if set(actual)!=set(wanted):raise ValueError('Visible diagnostic style inventory differs')
    for nid,count in wanted.items():
        node=nodes[nid];records=actual[nid]
        prefix='K02_EXCAVATION' if node['reference_set']=='M01_EXCAVATION' else 'ANBAU_CONFLICT_EXCAVATION'
        if not isinstance(records,list) or len(records)!=count:raise ValueError('Visible diagnostic styled-body count differs')
        _ids([r['body_name'] for r in records],[prefix+'_%02d'%i for i in range(count)],'visible diagnostic B-rep names')
        for record in records:
            option=record['component_layer_option']
            if type(option) is not int or option not in (-1,node['layer']):raise ValueError('Unexpected visible diagnostic component geometry-layer option')
            effective=node['source_body_layer'] if option==-1 else option
            for key,value in (('color',node['color']),('prototype_color',node['color']),
                              ('layer',effective),('prototype_layer',node['source_body_layer'])):
                if type(record.get(key)) is not int or record[key]!=value:raise ValueError('Visible diagnostic native body style differs: '+nid+' '+key)
            if type(record['effective_geometry_layer']) is not int or record['effective_geometry_layer']!=effective:
                raise ValueError('Visible diagnostic effective geometry-layer record differs')


def register_only_marker_ids(spec):
    """Unchanged old empty register containers, excluding every annex field."""
    nodes={n['id']:n for n in spec['layout']['nodes']}
    parents={n['parent'] for n in nodes.values()}
    return {f['id'] for f in spec['base_layout']['fields'] if f['native'] is False and
            f['id'] not in spec['prepared_fields'] and not f.get('measurements') and
            f['node_id'] in nodes and nodes[f['node_id']]['kind']=='field' and f['node_id'] not in parents}


def _register_marker_allowance(spec,entry):
    if spec is None:return set()
    if not (entry['kind']=='review' or (entry['kind']=='subassembly' and entry['root_node_id'].startswith('SECTION_'))):return set()
    return register_only_marker_ids(spec)&set(entry['visibility']['visible_field_ids'])


def validate_default_snapshot(entry,actual,*,spec=None):
    """Minimal display evidence is native proxies, not exact B-rep body counts."""
    wanted=entry['visibility'];visible=set(actual['visible_node_ids']);markers=set(actual['visible_marker_ids'])|set(actual['visible_marker_proxy_ids'])
    for key in ('visible_node_ids','visible_marker_ids','visible_marker_proxy_ids'):_ids(actual[key],actual[key],key)
    expected=set(wanted['visible_field_ids']);missing=expected-markers;allowed=_register_marker_allowance(spec,entry)
    if markers-expected or missing-allowed:raise ValueError('Minimal native field-marker/proxy visibility differs')
    count=actual['native_visible_object_count']
    pure_register_section=(entry['kind']=='subassembly' and entry['root_node_id'].startswith('SECTION_') and
        bool(expected) and expected<=allowed and missing==expected and not any(wanted['body_counts'].values()) and not visible)
    if (actual['exact_brep_body_counts_verified'] is not False or type(count) is not int or count<0 or
            (count==0 and not pure_register_section)):
        raise ValueError('Empty or mislabeled native minimal display proof')
    active={nid for nid,n in wanted['body_counts'].items() if n>0}
    selected_fields={'FIELD_'+fid for fid in wanted['visible_field_ids']}
    if active and not visible&(active|selected_fields):raise ValueError('No native selected geometry/proxy visible in minimal display')
    forbidden={nid for nid,n in wanted['body_counts'].items() if not n}
    if visible&forbidden:raise ValueError('Hidden native role/context/site appears in minimal display')
    return sorted(missing)


def register_marker_limitation(spec,entry,snapshot,graph,manifest):
    """Missing register scene observations never become rendered-marker proof.

    Full mode still requires every marker. Native minimal probes found old
    register wires absent from parent scenes while direct FIELD opens showed
    them. Bind each permitted omission to an actual unhidden occurrence and
    to the exact same full-marker proof inputs, without changing the spec.
    """
    missing=validate_default_snapshot(entry,snapshot,spec=spec)
    if not missing:return None
    if set(manifest)!=set(spec['file_map'].values()):raise ValueError('Register marker limitation lacks the complete Part-byte binding')
    fields={f['id']:f for f in spec['base_layout']['fields']};nodes={n['id']:n for n in spec['layout']['nodes']}
    witnesses={}
    for fid in missing:
        nid=fields[fid]['node_id'];node=nodes[nid];actual=graph.get(nid)
        if (actual is None or actual.get('effective_hidden') is not False or
                any(actual.get(k)!=node[k] for k in ('parent','file','reference_set'))):
            raise ValueError('Unobserved register marker has no matching unhidden current occurrence: '+fid)
        witnesses[fid]={'node_id':nid,'parent':node['parent'],'file':node['file'],
                        'reference_set':node['reference_set'],'effective_hidden':False}
    return {'kind':'REGISTER_ONLY_MARKERS_NOT_OBSERVED_IN_NATIVE_MINIMAL_SCENE',
            'missing_marker_ids':missing,'markers_observed_in_minimal_scene':False,
            'present_unhidden_occurrences':witnesses,'full_marker_evidence_required':True,
            'full_marker_binding':{'verification_spec_sha256':spec['spec_sha256'],'part_manifest_sha256':_hash(manifest)}}


def validate_search_directory_isolation(record):
    """Strict empty list after an explicitly owned in-memory batch isolation."""
    for key in ('before_search_directories','after_search_directories'):
        arrays=record[key]
        if (not isinstance(arrays,list) or len(arrays)!=2 or any(not isinstance(a,list) for a in arrays) or
                len(arrays[0])!=len(arrays[1]) or any(not isinstance(p,str) for p in arrays[0]) or
                any(type(flag) is not bool for flag in arrays[1])):raise ValueError('Invalid native search-directory/recursion arrays')
    if record['after_search_directories']!=[[],[]]:raise ValueError('Owned default probe retains supplementary search directories')
    if record['owned_batch_only'] is not True or record['settings_saved'] is not False or record['active_profile_unchanged'] is not True:
        raise ValueError('Search-directory isolation changed/saved settings outside the owned batch')
    before,after=record['before_profile'],record['after_profile']
    if before!=after:raise ValueError('Search-directory isolation changed the active native load profile')
    if (after['requested_component_load_method']!='FromDirectory' or after['component_load_method_matches_requested'] is not True or
            after['minimal_display_profile_verified'] is not True):raise ValueError('Directory/minimal native mode was not preserved')


def _isolate_default_search_directories(session):
    """Observe and clear only the owned batch's directory list; never save it."""
    _batch(session)
    from renovierung.m01.inspection import _configure_load
    options=session.Parts.LoadOptions
    def profile():
        observed=_configure_load(session,'FromDirectory',full=False)
        observed['part_load_option']=str(options.PartLoadOption)
        observed['minimal_display_profile_verified']=True
        return observed
    before=profile();initial=[list(a) for a in options.GetSearchDirectories()]
    # The list is inactive under FromDirectory (LoadOptions.hxx), but clearing
    # it in this private batch additionally excludes a supplementary fallback.
    # No LoadOptions.Save/Restore, preference save, GUI or registry call occurs.
    options.SetSearchDirectories([],[])
    cleared=[list(a) for a in options.GetSearchDirectories()];after=profile()
    isolation={'before_search_directories':initial,'after_search_directories':cleared,
               'before_profile':before,'after_profile':after,'active_profile_unchanged':before==after,
               'owned_batch_only':True,'settings_saved':False}
    validate_search_directory_isolation(isolation)
    return dict(after,search_directory_isolation=isolation)


def _batch(session):
    if not session.IsBatch or list(session.Parts):raise ValueError('Verification requires a fresh empty owned batch NX process')


def _native_spec(root,spec,*,moved):
    # The source leaf mode is immutable. The independently recomputed parcel
    # edge review can downgrade a source study to one diagnostic occurrence.
    # Each regular study contributes four role nodes plus one shared-site node;
    # each diagnostic contributes exactly one node, for all24 annex fields.
    native_count=sum(entry['spec']['mode']=='STUDY' and fid not in spec['derived_risk_declines_mm']
                     for fid,entry in spec['prepared_fields'].items())
    diagnostic_count=24-native_count
    wanted={'nodes':349+5*native_count+diagnostic_count,'old_nodes':349,'parts':367,'states':60,'reviews':59,'entries':145}
    if spec['counts']!=wanted or len(spec['prepared_fields'])!=24 or len(spec['base_layout']['context']['groups'])!=83:
        raise ValueError('Native acceptance requires349 original nodes plus the independently derived24-field study/diagnostic nodes and367 Parts')
    if spec['spec_sha256']!=_hash({k:v for k,v in spec.items() if k!='spec_sha256'}):raise ValueError('Independent verification specification changed')
    evidence=spec['copy_evidence']
    if not evidence or len(spec['new_leaf_bytes'])!=25:raise ValueError('Native proof requires complete independent-copy/new25-leaf byte certificates')
    source=Path(evidence['source_root']).resolve();destination=Path(evidence['destination_root']).resolve()
    if root==source or root.is_relative_to(source) or source.is_relative_to(root):raise ValueError('Verification target must be independent of original source')
    if (not moved and root!=destination) or (moved and root==destination):raise ValueError('Native proof did not use the required fresh/moved physical directory')


def _read_presentation(part,*,archive=False):
    import NXOpen.Layer
    from renovierung.m01.presentation import read_presentation
    result=read_presentation(part)
    def semantic(number):
        state=part.Layers.GetState(number)
        return dict(state=str(state),visible=state in (NXOpen.Layer.State.WorkLayer,NXOpen.Layer.State.Selectable,NXOpen.Layer.State.Visible),
                    selectable=state in (NXOpen.Layer.State.WorkLayer,NXOpen.Layer.State.Selectable),hidden=state==NXOpen.Layer.State.Hidden)
    result['layers']['240']=semantic(240)
    if archive:result['archive_layer_241']=semantic(241)
    return result


def _position(component):
    point,matrix=component.GetPosition()
    return [point.X,point.Y,point.Z],[getattr(matrix,k) for k in MATRIX_KEYS]


def _default_arrangement_name(part):
    # NX2406 Assemblies_ComponentAssembly.hxx exposes SetDefault only.
    # UFAssem AskDefaultArrangement/AskNameOfArrangement are documented getters.
    import NXOpen.UF
    uf=NXOpen.UF.UFSession.GetUFSession()
    return uf.Assem.AskNameOfArrangement(uf.Assem.AskDefaultArrangement(part.Tag))


def _entry_presentation(part,entry,spec):
    archive=entry['id'] in {r['container_node_id'] for r in spec['fields'].values()}
    actual=_read_presentation(part,archive=archive)
    mutable=spec['file_map'][entry['file']] not in spec['immutable_parts']
    validate_presentation(actual,spec['presentation'],require_conflict_layer=mutable)
    return actual


def _native_graph(session,part,entry,root,spec,*,full):
    """Resolve real native paths/transforms/attributes; never ask a Body to load."""
    import NXOpen
    import NXOpen.UF
    from renovierung.m01.display import read_attribute,PROJECT
    from renovierung.m01.inspection import _prototype_path,_native_dependencies
    from renovierung.m01.nx_journal import world_transforms
    nodes={n['id']:n for n in spec['layout']['nodes']};world=world_transforms(spec['layout'])
    assembly=part.ComponentAssembly.RootComponent;children=list(assembly.GetChildren()) if assembly is not None else []
    shared=None
    if entry['kind']=='review':
        for key,wanted in {'M01_REVIEW_SCOPE':'M01_REVIEW','M01_REVIEW_ID':entry['id'],'M01_REVIEW_STATE':entry['state']}.items():
            if read_attribute(part,key)!=wanted:raise ValueError('Fresh wrapper attribute differs: '+entry['id']+' '+key)
        if len(children)!=1:raise ValueError('Wrapper must contain exactly one shared master occurrence')
        shared=children[0];_prototype_path(root,spec['layout']['master'],shared.Prototype.FullPath,spec['file_map'])
        _numbers(_position(shared)[0],[0,0,0],'wrapper master position');_numbers(_position(shared)[1],I,'wrapper master rotation')
        if shared.UsedArrangement.Name!=spec['catalog'][entry['state']]:raise ValueError('Wrapper saved used arrangement differs')
        assembly=shared
    root_id=entry['root_node_id'];local=_descendants(nodes,root_id)
    root_part=shared.Prototype if shared is not None else part
    if read_attribute(root_part,'M01_NODE_ID')!=root_id:raise ValueError('Opened root node identity differs')
    if root_id=='MASTER':
        if read_attribute(root_part,'M01_PROJECT')!=PROJECT or read_attribute(root_part,'M01_STATE_CATALOG')!=spec['catalog']:
            raise ValueError('Master project/catalog differs')
        default=spec['base_layout']['default_state']
        if read_attribute(root_part,'M01_DEFAULT_STATE')!=default or (full and _default_arrangement_name(root_part)!=spec['catalog'][default]):
            raise ValueError('Master saved default differs')
        for key,wanted in {'ANBAU_UPGRADE_SCHEMA':spec['upgrade_attributes']['schema'],
                           'ANBAU_UPGRADE_SPEC_SHA256':spec['upgrade_attributes']['spec_sha256'],
                           'ANBAU_CONSTRUCTION_RELEASE':False,'M01_PRESENTATION':spec['presentation']}.items():
            if wanted is not None and read_attribute(root_part,key)!=wanted:raise ValueError('Master annex attribute differs: '+key)
        if full:
            names=[a.Name for a in root_part.ComponentAssembly.Arrangements]
            _ids(names,spec['catalog'].values(),'native master arrangements')
    elif root_id.startswith('SECTION_') and root_id.removeprefix('SECTION_') in spec['section_defaults']:
        sid=root_id.removeprefix('SECTION_');active=root_part.ComponentAssembly.ActiveArrangement
        if active is None or active.Name!='ANBAU_SECTION_DEFAULT_'+sid or (full and _default_arrangement_name(root_part)!='ANBAU_SECTION_DEFAULT_'+sid):
            raise ValueError('Standalone annex section saved default differs')
    rows={};occurrences={};fields={f['node_id']:f for f in spec['layout']['fields']};definition_cache={}
    uf_assem=NXOpen.UF.UFSession.GetUFSession().Assem
    def direct_definition(component,parent_id,nid):
        parent_part=component.Parent.Prototype
        if parent_part is None:
            parent_path=mapfile(root,nodes[parent_id]['file'],spec['file_map'])
            parent_part=next((p for p in session.Parts if Path(p.FullPath).resolve()==parent_path),None)
        if parent_part is None:raise ValueError('Canonical component definition Part is unresolved')
        _prototype_path(root,nodes[parent_id]['file'],parent_part.FullPath,spec['file_map'])
        if parent_part.Tag not in definition_cache:
            children=list(parent_part.ComponentAssembly.RootComponent.GetChildren());indexed={}
            for child in children:
                ident=read_attribute(child,'M01_NODE_ID')
                if ident in indexed:raise ValueError('Canonical component definition identity is duplicated')
                indexed[ident]=child
            definition_cache[parent_part.Tag]=indexed
        if nid not in definition_cache[parent_part.Tag]:raise ValueError('Canonical direct component definition is missing: '+nid)
        return definition_cache[parent_part.Tag][nid]
    def attrs(obj,nid):
        row=nodes[nid]
        for key,wanted in {'M01_NODE_ID':nid,'M01_KIND':row['kind'],'M01_DEFAULT_BLANK':row['blank'],'M01_NODE_METADATA':row}.items():
            if read_attribute(obj,key)!=wanted:raise ValueError('Native occurrence metadata differs: '+nid+' '+key)
    attrs(root_part,root_id)
    for nid,f in fields.items():
        if nid!=root_id:continue
        for key,wanted in {'M01_FIELD_ID':f['id'],'M01_FIELD_NATIVE':f['native'],'M01_FIELD_METADATA':f}.items():
            if read_attribute(root_part,key)!=wanted:raise ValueError('Standalone FIELD metadata differs: '+nid)
    def walk(parent,parent_id,inherited=False):
        if parent is None:return
        for component in parent.GetChildren():
            nid=read_attribute(component,'M01_NODE_ID')
            if nid not in local or nid in rows or nodes[nid]['parent']!=parent_id:raise ValueError('Native component hierarchy/ID differs: '+str(nid))
            row=nodes[nid];attrs(component,nid)
            identity=component_identity_evidence(row,{'instance_name':uf_assem.AskComponentData(component.Tag)[2],
                'custom_occurrence_name':component.Name,'reference_set':component.ReferenceSet},full=full,
                read_definition_name=lambda:direct_definition(component,parent_id,nid).Name)
            if nid in fields:
                field=fields[nid]
                for key,wanted in {'M01_FIELD_ID':field['id'],'M01_FIELD_NATIVE':field['native'],'M01_FIELD_METADATA':field}.items():
                    if read_attribute(component,key)!=wanted:raise ValueError('FIELD instance metadata differs: '+nid+' '+key)
                if field['id'] in spec['fields']:
                    for key,wanted in {'ANBAU_DIAGNOSTIC':spec['fields'][field['id']]['diagnostic'],'ANBAU_CONSTRUCTION_RELEASE':False}.items():
                        if read_attribute(component,key)!=wanted or (full and read_attribute(component.Prototype,key)!=wanted):
                            raise ValueError('Annex FIELD diagnostic/release attribute differs: '+nid)
            diagnostic_style=None
            if row['kind']=='diagnostic' and full:
                # Resolve the saved direct definition in its canonical FIELD
                # Part. A master-nested Component exposes different generic
                # Color/Layer defaults, as demonstrated by the native probes.
                definition=direct_definition(component,parent_id,nid)
                if read_attribute(definition,'M01_NODE_METADATA')!=row or definition.ReferenceSet!=row['reference_set']:
                    raise ValueError('Stored diagnostic direct definition metadata/refset differs: '+nid)
                stored={'color':definition.Color,'layer':definition.Layer,'layer_option':definition.GetLayerOption()}
                validate_diagnostic_definition_style(row,stored)
                diagnostic_style={'definition_file':nodes[parent_id]['file'],'definition':stored,
                                  'nested_context':{'color':component.Color,'layer':component.Layer,'layer_option':component.GetLayerOption()}}
            _prototype_path(root,row['file'],component.Prototype.FullPath,spec['file_map'])
            p,r=_position(component);origin,rot=world[root_id]
            # Positions in a standalone display are relative to that root's ABS.
            wanted_p=[sum(rot[j*3+i]*(world[nid][0][j]-origin[j]) for j in range(3)) for i in range(3)]
            wanted_r=[sum(rot[k*3+i]*world[nid][1][k*3+j] for k in range(3)) for i in range(3) for j in range(3)]
            _numbers(p,wanted_p,nid+' position');_numbers(r,wanted_r,nid+' rotation')
            hidden=inherited or bool(component.IsBlanked) or bool(component.IsSuppressed)
            if nid.startswith('SECTION_') and root_id=='MASTER' and nid.removeprefix('SECTION_') in spec['section_defaults']:
                if component.UsedArrangement.Name!='ANBAU_SECTION_MASTER_'+nid.removeprefix('SECTION_'):
                    raise ValueError('Master must use annex section all-fields arrangement: '+nid)
            rows[nid]=dict(parent=parent_id,file=row['file'],full_path=str(Path(component.Prototype.FullPath).resolve()),
                           **identity,translation_mm=p,rotation=r,effective_hidden=hidden)
            if diagnostic_style is not None:rows[nid]['diagnostic_style']=diagnostic_style
            occurrences[nid]=component;walk(component,nid,hidden)
    walk(assembly,root_id)
    if set(rows)!=local-{root_id}:raise ValueError('Missing native graph nodes')
    for nid,count in entry['visibility']['body_counts'].items():
        if nid in rows and rows[nid]['effective_hidden']!=(count==0):raise ValueError('Native effective role/context/site flags differ: '+entry['id']+' '+nid)
    deps={}
    expected_files=set(spec['file_map'])
    for native in session.Parts:
        from renovierung.m01.delivery_paths import logicalfile
        logical=logicalfile(root,native.FullPath,spec['file_map'])
        if native.PartUnits!=NXOpen.BasePart.Units.Millimeters or full and not native.IsFullyLoaded:raise ValueError('Loaded Part units/load state differ: '+logical)
        _prototype_path(root,logical,native.FullPath,spec['file_map'])
        if full and (entry['kind']=='master' or native.Tag==part.Tag):deps[logical]=_native_dependencies(native,root,expected_files,spec['file_map'])
    return rows,occurrences,deps


def _full_snapshot(part,spec,expected,occurrences,*,root_node_id='MASTER'):
    """Actual visible B-rep occurrence counts, deduplicated across facets."""
    import NXOpen
    import NXOpen.Facet
    nodes={n['id']:n for n in spec['layout']['nodes']};owner_ids={c.Tag:nid for nid,c in occurrences.items()}
    fieldnodes={f['node_id']:f['id'] for f in spec['layout']['fields']}
    bodies={};markers=set();shells=set();diagnostic_styles={}
    for obj in part.ModelingViews.WorkView.AskVisibleObjects():
        body=None
        if isinstance(obj,NXOpen.Body):body=obj
        elif isinstance(obj,NXOpen.Facet.FacetedBody):
            if not obj.IsAssociatedBodyLoaded:raise ValueError('Full proof contains a visible facet without loaded B-rep')
            body=obj.AssociatedBody
        elif not isinstance(obj,NXOpen.Curve):continue  # Skip faces/edges before owner access.
        owner=body.OwningComponent if body is not None else obj.OwningComponent
        if owner is None:owner=obj.OwningComponent
        nid=owner_ids.get(owner.Tag) if owner is not None else root_node_id
        if body is not None:
            if nid not in nodes:raise ValueError('Unclassified native visible body owner')
            prototype=body.Prototype if body.IsOccurrence else body
            bodies.setdefault(nid,set()).add((owner.Tag if owner is not None else None,prototype.Tag))
            if nodes[nid]['kind']=='annex_site':shells.add(prototype.Name)
            if nodes[nid]['kind']=='diagnostic':
                option=occurrences[nid].GetLayerOption()
                record={'body_name':prototype.Name,'color':body.Color,'layer':body.Layer,
                        'prototype_color':prototype.Color,'prototype_layer':prototype.Layer,'component_layer_option':option,
                        'effective_geometry_layer':prototype.Layer if option==-1 else option}
                key=(nid,prototype.Tag)
                if key in diagnostic_styles and diagnostic_styles[key]!=record:raise ValueError('Visible diagnostic B-rep/facet body style observations disagree')
                diagnostic_styles[key]=record
        elif nid in fieldnodes:markers.add(fieldnodes[nid])
        elif owner is None and obj.Name.startswith('M01_REGISTER_'):markers.add(obj.Name[len('M01_REGISTER_'):])
    counts={nid:len(bodies.get(nid,set())) for nid in expected['body_counts']}
    roles=dict.fromkeys(ROLES,0);diag=0
    for nid,n in counts.items():
        if nodes[nid]['kind']=='role':roles[nodes[nid]['role']]+=n
        elif nodes[nid]['kind']=='diagnostic':diag+=n
    result=dict(body_counts=counts,visible_role_bodies=roles,visible_context_ids=sorted(nid for nid,n in counts.items() if n and nodes[nid]['kind']=='context'),
                visible_site_shell_ids=sorted(shells),visible_field_ids=sorted(markers),visible_diagnostic_bodies=diag,
                terrain_visible=bool(bodies.get('TERRAIN')))
    validate_visibility(expected,result)
    styled={}
    for (nid,tag),record in diagnostic_styles.items():styled.setdefault(nid,[]).append(record)
    validate_diagnostic_display(spec,expected,styled)
    result['visible_diagnostic_styles']=styled
    if root_node_id=='MASTER':
        # Building remains present in every state; upper-house visibility follows
        # the canonical arrangement rather than being inferred from role totals.
        required={'HOUSE_KG_MAIN'}&set(nodes)
        for nid in required:
            if not bodies.get(nid):raise ValueError('No actual house B-rep visible: '+nid)
    result['exact_brep_body_counts_verified']=True
    return result


def _refset(part,name,bodies):
    import NXOpen
    import NXOpen.Facet
    from renovierung.m01.nx_journal import validate_refset_members
    sets={r.Name:r for r in part.GetAllReferenceSets()}
    if name not in sets:raise ValueError('Missing native reference set: '+name)
    records=[]
    for member in sets[name].AskAllDirectMembers():
        row={'tag':member.Tag,'kind':'other'}
        if isinstance(member,NXOpen.Body):row['kind']='body'
        elif isinstance(member,NXOpen.Facet.FacetedBody):
            loaded=bool(member.IsAssociatedBodyLoaded);associated=member.AssociatedBody if loaded else None
            row.update(kind='facet',associated_loaded=loaded,associated_tag=associated.Tag if associated is not None else None)
        records.append(row)
    facets=validate_refset_members({b.Tag:b.Name for b in bodies},records)
    return dict(body_names=sorted(b.Name for b in bodies),associated_facets=facets)


def _measure_core(session,master,root,spec,*,evidence=None):
    import NXOpen.Layer
    from renovierung.k02.nx_verify import measure,body_role
    from renovierung.k02.runner import validate_measurement
    from renovierung.m01.nx_journal import display_part
    from renovierung.m01.delivery_paths import logicalfile
    from .nx_fields import inspect_field
    from .site import inspect_site_part
    parts={logicalfile(root,p.FullPath,spec['file_map']):p for p in session.Parts}
    from renovierung.m01.display import read_attribute
    from renovierung.m01.pile_native import _bbox,_relocation_metadata,_history_name,HISTORICAL_LAYER,PILE_ROLES
    contexts={};old_fields={};refsets={};pile_locations={};history_measurements={}
    if evidence is not None:evidence.update(context_measurements=contexts,old_field_measurements=old_fields,
        old_refsets=refsets,old_pile_locations=pile_locations,old_historical_measurements=history_measurements)
    base=spec['base_layout']
    for group in base['context']['groups']:
        part=parts[group['file']];display_part(session,part);bodies=list(part.Bodies)
        if any(b.IsBlanked or b.Layer!=210 for b in bodies):raise ValueError('Old context body hidden/wrong layer: '+group['id'])
        actual=measure(bodies);validate_measurement(actual,group['component_volumes_m3']);contexts[group['id']]=actual
        # Entire Part contexts need no custom set; explicitly named context
        # reference sets are verified against all their intended B-reps.
        for row in base['nodes']:
            if row['id']==group['id'] and row['reference_set'] not in ('Entire Part','ENTIRE PART'):
                refsets[group['id']]=_refset(part,row['reference_set'],bodies)
    for field in base['fields']:
        if not field['native']:continue
        roles=[n for n in base['nodes'] if n['parent']==field['node_id'] and n['kind']=='role']
        if {n['role'] for n in roles}!=set(ROLES):raise ValueError('Incomplete old native role graph')
        measurements={};refsets[field['id']]={}
        study=parts[field['study_file']];display_part(session,study)
        if read_attribute(study,'M01_PILE_RELOCATION')!=_relocation_metadata(field):raise ValueError('Original moved-pile source metadata differs')
        expected_sets={n['reference_set'] for n in roles}
        if {r.Name for r in study.GetAllReferenceSets() if r.Name.startswith('M01_')}!=expected_sets:raise ValueError('Old study refset inventory differs')
        if study.Layers.GetState(HISTORICAL_LAYER)!=NXOpen.Layer.State.Hidden:raise ValueError('Old conflict-pile archive layer251 is not hidden')
        locations={};history={};all_bodies=list(study.Bodies);recognized=set()
        for row in roles:
            role=row['role'];part=parts[row['file']];display_part(session,part)
            bodies=[b for b in part.Bodies if body_role(b.Name)==role]
            if any(b.IsBlanked or b.Layer!={'cut_soil':101,'excavation':102,'pile_main':103,'pile_reserve':104}[role] for b in bodies):raise ValueError('Old role body hidden/wrong layer')
            measurements[role]=measure(bodies);validate_measurement(measurements[role],field['measurements'][role]['component_volumes_m3'])
            refsets[field['id']][role]=_refset(part,row['reference_set'],bodies)
            recognized.update(b.Tag for b in bodies)
            if role in PILE_ROLES:
                expected_names={'K02_'+role.upper()+'_%02d'%i for i in range(field['measurements'][role]['body_count'])}
                if {b.Name for b in bodies}!=expected_names:raise ValueError('Old active pile names differ')
                box=_bbox(bodies);_numbers(box,field['display_stockpile'][role]['bbox_mm'],'old moved pile '+field['id']+' '+role,tol=.25)
                locations[role]={'bbox_mm':box,'body_count':len(bodies)}
                old=field['k02_pile_measurements'][role]
                names={_history_name(field['id'],role,i) for i in range(old['body_count'])}
                hidden=[b for b in all_bodies if b.Name in names]
                if len(hidden)!=old['body_count'] or any(not b.IsBlanked or b.Layer!=HISTORICAL_LAYER for b in hidden):raise ValueError('Old historical conflict bodies missing/visible')
                history[role]=measure(hidden);validate_measurement(history[role],old['component_volumes_m3'])
                recognized.update(b.Tag for b in hidden)
        if recognized!={b.Tag for b in all_bodies}:raise ValueError('Unknown extra original study bodies')
        locations['historical_hidden']={r:history[r]['body_count'] for r in PILE_ROLES}
        pile_locations[field['id']]=locations;history_measurements[field['id']]=history
        old_fields[field['id']]=measurements
    new_fields={};integrated={}
    if evidence is not None:evidence.update(new_fields=new_fields,integrated_fields=integrated)
    for fid,entry in spec['prepared_fields'].items():
        part=parts[entry['spec']['file']];display_part(session,part)
        new_fields[fid]=inspect_field(session,part,entry)
        update=spec['fields'][fid];native=update['native']
        measurement=new_fields[fid]['measurements']
        integrated[fid]=dict(mode='STUDY' if native else 'CONFLICT_DIAGNOSTIC',
            source_mode=entry['spec']['mode'],construction_release=False,
            effective_excavation_m3=measurement['excavation']['volume_m3'] if native else None,
            effective_sand_m3={r:measurement[r]['volume_m3'] for r in ('pile_main','pile_reserve')} if native else {})
    site=inspect_site_part(session,parts[spec['site_entry']['file']],spec['site_entry'])
    display_part(session,master)
    return dict(old_field_measurements=old_fields,context_measurements=contexts,old_refsets=refsets,
                old_pile_locations=pile_locations,old_historical_measurements=history_measurements,
                new_fields=new_fields,integrated_fields=integrated,site=site)


def inspect_full_delivery(session,root,spec):
    """Fresh AsSaved/full: core once, 60 states, 59 fresh wrappers,85 cold roots.

    Every geometric prototype is measured once. Reusing the loaded full core
    avoids repeating 22 field and 83 context measurements for each wrapper.
    Standalone root B-rep visibility is checked separately without mass calls.
    Caller must use a dedicated batch process; no Part save is performed.
    """
    _batch(session)
    import NXOpen
    import NXOpen.Assemblies
    from renovierung.m01.inspection import _configure_load,_loaded,_loaded_inventory
    from renovierung.m01.standalone import _close_owned
    from renovierung.m01.nx_journal import display_part
    from renovierung.m01.display import read_attribute
    root=Path(root).resolve();_native_spec(root,spec,moved=False)
    before=inspect_files(root,spec);source_before=_source_guard(spec);options=_configure_load(session,'AsSaved',full=True)
    options['full_load_profile_verified']=True
    options['part_load_option']=str(session.Parts.LoadOptions.PartLoadOption)
    result=dict(schema=SCHEMA,mode='AS_SAVED_FULL',root=str(root),file_manifest=before,load_options=options,
                saved_by_inspector=False,construction_release=False,states={},public_selections={},reviews={},standalone={},
                byte_guards={'target_parts_unchanged':None,'original_source_unchanged':None})
    core_files={n['file'] for n in spec['layout']['nodes']};master=None;wrapper=None
    phase={'kind':'master','id':'MASTER','operation':'open_and_graph'}
    try:
        entry=next(r for r in spec['entries'] if r['kind']=='master')
        master,status=session.Parts.OpenDisplay(str(mapfile(root,entry['file'],spec['file_map'])));_loaded(master,status,'master')
        _loaded_inventory(session,root,core_files,spec['file_map'])
        if master.ComponentAssembly.ActiveArrangement.Name!=spec['catalog'][entry['state']]:raise ValueError('Saved master active arrangement differs')
        graph,occurrences,deps=_native_graph(session,master,entry,root,spec,full=True)
        result['nodes']=graph;result['dependencies']=deps
        phase={'operation':'core_geometry_measurements'}
        result.update(_measure_core(session,master,root,spec,evidence=result))
        assembly=master.ComponentAssembly;arrangements={a.Name:a for a in assembly.Arrangements}
        enum=NXOpen.Assemblies.ComponentAssembly.SuppressedState
        house={nid:_position(c) for nid,c in occurrences.items() if nid=='HOUSE' or nid.startswith('HOUSE_')}
        for sid,expected in spec['states'].items():
            phase={'kind':'saved_state','id':sid}
            print('ANBAU full saved state '+sid,flush=True)
            assembly.ActiveArrangement=arrangements[spec['catalog'][sid]]
            hidden=[]
            for nid in spec['controlled_ids']:
                status,controlled=assembly.GetSuppressedState(occurrences[nid],assembly.ActiveArrangement)
                wanted=enum.Suppressed if nid in expected['suppressed_ids'] else enum.Unsuppressed
                if not controlled or status!=wanted:raise ValueError('Native direct suppression differs: '+sid+' '+nid)
                if status==enum.Suppressed:hidden.append(nid)
            for nid,(p,r) in house.items():
                now=_position(occurrences[nid]);_numbers(now[0],p,'house state '+sid);_numbers(now[1],r,'house state '+sid)
            visible=_full_snapshot(master,spec,expected,occurrences)
            presentation=_read_presentation(master);validate_presentation(presentation,spec['presentation'])
            result['states'][sid]=dict(suppressed_ids=hidden,**visible,presentation=presentation,house_transforms_unchanged=True)
        from renovierung.m01.display import select_state
        for fid in sorted(spec['prepared_fields']):
            phase={'kind':'public_select_state','id':fid}
            print('ANBAU public native select_state '+fid,flush=True)
            if select_state(master,fid)!=fid or assembly.ActiveArrangement.Name!=spec['catalog'][fid]:
                raise ValueError('Public native field selection routed to another state: '+fid)
            expected=spec['states'][fid]
            for nid in spec['controlled_ids']:
                status,controlled=assembly.GetSuppressedState(occurrences[nid],assembly.ActiveArrangement)
                if not controlled or status!=(enum.Suppressed if nid in expected['suppressed_ids'] else enum.Unsuppressed):
                    raise ValueError('Public selection suppression differs: '+fid+' '+nid)
            for nid,(p,r) in house.items():
                now=_position(occurrences[nid]);_numbers(now[0],p,'public selection house '+fid);_numbers(now[1],r,'public selection house '+fid)
            visible=_full_snapshot(master,spec,expected,occurrences)
            presentation=_read_presentation(master);validate_presentation(presentation,spec['presentation'])
            result['public_selections'][fid]=dict(**visible,presentation=presentation,
                selected_state=fid,house_transforms_unchanged=True,public_api='renovierung.m01.display.select_state',ui_automation_performed=False)
        assembly.ActiveArrangement=arrangements[spec['catalog'][entry['state']]]
        result['master_presentation']=_read_presentation(master);validate_presentation(result['master_presentation'],spec['presentation'])
        for row in spec['reviews']:
            phase={'kind':'review','id':row['id'],'file':row['file']}
            print('ANBAU fresh full wrapper '+row['id'],flush=True)
            wrapper,status=session.Parts.OpenDisplay(str(mapfile(root,row['file'],spec['file_map'])));_loaded(wrapper,status,row['id'])
            review_entry=next(r for r in spec['entries'] if r['kind']=='review' and r['id']==row['id'])
            graph,occs,deps=_native_graph(session,wrapper,review_entry,root,spec,full=True)
            _loaded_inventory(session,root,core_files|{row['file']},spec['file_map'])
            visible=_full_snapshot(wrapper,spec,review_entry['visibility'],occs)
            presentation=_entry_presentation(wrapper,review_entry,spec)
            result['reviews'][row['id']]=dict(file=row['file'],state=row['state'],master=spec['layout']['master'],
                **visible,presentation=presentation,nodes=graph,fresh_wrapper_from_disk=True,core_reused=True)
            wrapper.Close(NXOpen.BasePart.CloseWholeTree.FalseValue,NXOpen.BasePart.CloseModified.CloseModified,None);wrapper=None
            display_part(session,master);assembly.ActiveArrangement=arrangements[spec['catalog'][entry['state']]]
            _loaded_inventory(session,root,core_files,spec['file_map'])
        _close_owned(session,root);master=None
        for sub in (r for r in spec['entries'] if r['kind']=='subassembly'):
            phase={'kind':'subassembly','id':sub['id'],'file':sub['file']}
            print('ANBAU cold full subassembly '+sub['id'],flush=True)
            part,status=session.Parts.OpenDisplay(str(mapfile(root,sub['file'],spec['file_map'])));_loaded(part,status,sub['id'])
            graph,occs,deps=_native_graph(session,part,sub,root,spec,full=True)
            visible=_full_snapshot(part,spec,sub['visibility'],occs,root_node_id=sub['root_node_id'])
            presentation=_entry_presentation(part,sub,spec)
            result['standalone'][sub['file']]=dict(state=sub['state'],**visible,presentation=presentation,nodes=graph,cold_open=True)
            _close_owned(session,root)
        result['catalog']=deepcopy(spec['catalog']);result['default']=spec['base_layout']['default_state']
        result['all_parts_mm']=True;result['all_full_paths_internal']=True;result['source_bytes_unchanged']=_source_guard(spec)==source_before
        phase={'operation':'full_final_gate'}
        errors=validate_full_evidence(spec,result)
        if errors:raise ValueError('; '.join(errors))
        result['status']='PASS';return result
    except Exception as error:
        _failure_snapshot(session,root,spec,result)
        raise NativeVerificationFailure(str(error),failure_evidence(result,spec,phase)) from error
    finally:
        _close_and_guard(session,root,spec,before,source_before,result)


def probe_default_entries(session,root,spec):
    """Cold FromDirectory/minimal openings of all145 ordinary user entry Parts.

    The caller supplies the MOVED copy in a fresh owned NX process whose actual
    active load profile is directory/minimal. Its initially configured search
    list is recorded and cleared only in the private batch, with strict empty
    readback and unchanged active-profile evidence. No options file is saved.
    Visibility, arrangements, layers and camera are observed as opened. The scene query
    precedes reference walking; no B-rep association or mass method is called.
    """
    _batch(session)
    from renovierung.m01.inspection import _configure_load,_loaded,_loaded_inventory
    from renovierung.m01.standalone import _close_owned,_default_snapshot
    root=Path(root).resolve();_native_spec(root,spec,moved=True)
    before=inspect_files(root,spec);source_before=_source_guard(spec)
    options=_isolate_default_search_directories(session)
    result=dict(schema=SCHEMA,mode='MOVED_FROM_DIRECTORY_DEFAULT',root=str(root),file_manifest=before,
                load_options=options,saved_by_inspector=False,construction_release=False,entries={},
                byte_guards={'target_parts_unchanged':None,'original_source_unchanged':None},register_only_marker_limitations={})
    phase={'operation':'start_cold_default_entries'}
    try:
        for entry in spec['entries']:
            phase={'kind':entry['kind'],'id':entry['id'],'file':entry['file']}
            if list(session.Parts):raise ValueError('Default probe did not start from an empty owned session')
            print('ANBAU cold default entry '+entry['id'],flush=True)
            part,status=session.Parts.OpenDisplay(str(mapfile(root,entry['file'],spec['file_map'])));_loaded(part,status,entry['id'])
            # This ordering is part of the proof. Never move graph walking above.
            presentation=_entry_presentation(part,entry,spec)
            snapshot=_default_snapshot(part,spec['layout'])
            validate_default_snapshot(entry,snapshot,spec=spec)
            graph,occs,deps=_native_graph(session,part,entry,root,spec,full=False)
            limitation=register_marker_limitation(spec,entry,snapshot,graph,before)
            if entry['kind']=='master' and part.ComponentAssembly.ActiveArrangement.Name!=spec['catalog'][entry['state']]:
                raise ValueError('Cold master did not open its saved active state')
            loaded=_loaded_inventory(session,root,set(spec['file_map']),spec['file_map'],full=False,require_all=False,include_physical=True)
            result['entries'][entry['file']]=dict(id=entry['id'],kind=entry['kind'],file=entry['file'],state=entry['state'],
                root_full_path=str(Path(part.FullPath).resolve()),loaded_full_paths=loaded,nodes=graph,
                presentation=presentation,display_snapshot=snapshot,snapshot_before_reference_walk=True,
                cold_open=True,all_parts_mm=True,all_full_paths_internal=True,files_saved=False,
                brep_mass_measurements_performed=False,exact_brep_body_counts_verified=False,
                definition_inspection_performed=False,definition_inspection_scope='normal_partial',full_definition_evidence_required=True,
                full_definition_binding={'verification_spec_sha256':spec['spec_sha256'],'part_manifest_sha256':_hash(before)},
                register_only_marker_limitation=limitation)
            if limitation is not None:result['register_only_marker_limitations'][entry['file']]=limitation
            _close_owned(session,root)
        result['source_bytes_unchanged']=_source_guard(spec)==source_before
        phase={'operation':'default_final_gate'}
        errors=validate_default_evidence(spec,result)
        if errors:raise ValueError('; '.join(errors))
        result['status']='PASS';return result
    except Exception as error:
        _failure_snapshot(session,root,spec,result)
        raise NativeVerificationFailure(str(error),failure_evidence(result,spec,phase)) from error
    finally:
        _close_and_guard(session,root,spec,before,source_before,result)


def section_smoke_entries(spec):
    ids=('SECTION_PS12','SECTION_PS13')
    result=[]
    for nid in ids:
        rows=[r for r in spec['entries'] if r['id']==nid and r['kind']=='subassembly']
        if len(rows)!=1 or rows[0]['root_node_id']!=nid:raise ValueError('Section smoke requires exactly one canonical entry: '+nid)
        result.append(rows[0])
    return result


def smoke_sections(session,root,spec):
    """Two cold full SECTION12/13 diagnoses, no mass calls or delivery release.

    The journal may wrap a successful PARTIAL_DIAGNOSTIC in its technical PASS.
    This schema can never substitute for either complete acceptance mode.
    """
    _batch(session)
    from renovierung.m01.inspection import _configure_load,_loaded
    from renovierung.m01.standalone import _close_owned
    root=Path(root).resolve();_native_spec(root,spec,moved=False)
    before=inspect_files(root,spec);source_before=_source_guard(spec)
    entries=section_smoke_entries(spec);options=_configure_load(session,'AsSaved',full=True)
    options.update(full_load_profile_verified=True,part_load_option=str(session.Parts.LoadOptions.PartLoadOption))
    result=dict(schema='EXPLICIT_SECTION_DIAGNOSTIC_V1',status='PARTIAL_DIAGNOSTIC',scope_only=True,
                complete_release=False,construction_release=False,saved_by_inspector=False,
                verification_spec_sha256=spec['spec_sha256'],root=str(root),file_manifest=before,
                load_options=options,sections={},byte_guards={'target_parts_unchanged':None,'original_source_unchanged':None})
    phase={'operation':'start_section_smoke'}
    try:
        for entry in entries:
            phase={'kind':'section_smoke','id':entry['id'],'file':entry['file']}
            if list(session.Parts):raise ValueError('Section smoke must start every entry from an empty owned session')
            print('ANBAU cold full section smoke '+entry['id'],flush=True)
            part,status=session.Parts.OpenDisplay(str(mapfile(root,entry['file'],spec['file_map'])));_loaded(part,status,entry['id'])
            graph,occurrences,deps=_native_graph(session,part,entry,root,spec,full=True)
            visible=_full_snapshot(part,spec,entry['visibility'],occurrences,root_node_id=entry['root_node_id'])
            presentation=_entry_presentation(part,entry,spec)
            result['sections'][entry['id']]=dict(id=entry['id'],file=entry['file'],state=entry['state'],
                **visible,nodes=graph,presentation=presentation,native_dependencies=deps,cold_open=True,
                all_parts_mm=True,files_saved=False,mass_measurements_performed=False)
            _close_owned(session,root)
    except Exception as error:
        _failure_snapshot(session,root,spec,result)
        raise NativeVerificationFailure(str(error),failure_evidence(result,spec,phase)) from error
    finally:
        _close_and_guard(session,root,spec,before,source_before,result)
    issues=validate_section_smoke_evidence(spec,result)
    if issues:raise NativeVerificationFailure('; '.join(issues),failure_evidence(result,spec,{'operation':'section_smoke_final_gate'}))
    return result


def validate_section_smoke_evidence(spec,actual):
    """Pure exact-two-entry diagnostic gate, explicitly no delivery acceptance."""
    errors=[]
    try:
        if (actual['schema']!='EXPLICIT_SECTION_DIAGNOSTIC_V1' or actual['status']!='PARTIAL_DIAGNOSTIC' or
                actual['scope_only'] is not True or actual['complete_release'] is not False or
                actual['construction_release'] is not False or actual['saved_by_inspector'] is not False or
                actual['verification_spec_sha256']!=spec['spec_sha256']):raise ValueError('Wrong named-section diagnostic identity/release scope')
        if actual.get('partial_evidence_only') is True:raise ValueError('Failed partial observations are not a successful named-section diagnosis')
        manifest=actual['file_manifest']
        if set(manifest)!=set(spec['file_map'].values()) or actual['file_manifest_after']!=manifest:raise ValueError('Section smoke flat inventory/read-only bytes differ')
        for name,wanted in {**spec['immutable_parts'],**spec['new_leaf_bytes']}.items():
            if manifest[name]!=wanted:raise ValueError('Section smoke protected native bytes differ: '+name)
        if actual['byte_guards']!={'target_parts_unchanged':True,'original_source_unchanged':True}:raise ValueError('Section smoke byte/source guards incomplete')
        options=actual['load_options']
        if (options['requested_component_load_method']!='AsSaved' or options['component_load_method_matches_requested'] is not True or
                options['full_load_profile_verified'] is not True or options['supplementary_search_directories']!=[]):raise ValueError('Section smoke native load profile differs')
        entries={e['id']:e for e in section_smoke_entries(spec)}
        if set(actual['sections'])!=set(entries):raise ValueError('Named section smoke inventory differs')
        for nid,entry in entries.items():
            row=actual['sections'][nid]
            if any(row[key]!=entry[key] for key in ('id','file','state')):raise ValueError('Section smoke entry identity/state differs')
            if row['cold_open'] is not True or row['all_parts_mm'] is not True or row['files_saved'] is not False or row['mass_measurements_performed'] is not False or row['exact_brep_body_counts_verified'] is not True:
                raise ValueError('Section smoke native observation/read-only flags differ')
            _recorded_graph(spec,entry,row['nodes'],actual['root']);validate_visibility(entry['visibility'],row)
            validate_diagnostic_display(spec,entry['visibility'],row['visible_diagnostic_styles'])
            _recorded_presentation(spec,entry,row['presentation'])
    except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError) as error:
        errors.append('Invalid explicit section diagnostic evidence: '+str(error))
    return errors


def _recorded_graph(spec,entry,rows,root,*,full=True):
    """Pure graph/FullPath gate; POSIX tests and Windows native records supported."""
    from pathlib import PureWindowsPath,PurePosixPath
    from renovierung.m01.nx_journal import world_transforms
    nodes={n['id']:n for n in spec['layout']['nodes']};world=world_transforms(spec['layout'])
    local=_descendants(nodes,entry['root_node_id'])-{entry['root_node_id']}
    if set(rows)!=local:raise ValueError('Recorded native graph node inventory differs')
    path_type=PureWindowsPath if PureWindowsPath(root).drive else PurePosixPath
    directory=path_type(root)
    if not directory.is_absolute() or '..' in directory.parts:raise ValueError('Invalid recorded delivery directory')
    origin,rot=world[entry['root_node_id']]
    for nid,actual in rows.items():
        node=nodes[nid]
        validate_instance_name(node,actual,definition_required=full)
        if any(actual[k]!=node[k] for k in ('parent','file','reference_set')):raise ValueError('Recorded native structural row differs: '+nid)
        expected_p=[sum(rot[j*3+i]*(world[nid][0][j]-origin[j]) for j in range(3)) for i in range(3)]
        expected_r=[sum(rot[k*3+i]*world[nid][1][k*3+j] for k in range(3)) for i in range(3) for j in range(3)]
        _numbers(actual['translation_mm'],expected_p,nid);_numbers(actual['rotation'],expected_r,nid)
        path=path_type(actual['full_path'])
        if not path.is_absolute() or path.parent!=directory or path.name.casefold()!=spec['file_map'][node['file']].casefold():
            raise ValueError('Recorded native FullPath leaves flat delivery mapping: '+nid)
        if nid in entry['visibility']['body_counts'] and actual['effective_hidden'] is not (entry['visibility']['body_counts'][nid]==0):
            raise ValueError('Recorded native role/context flags differ: '+nid)
        if node['kind']=='diagnostic' and full:
            style=actual['diagnostic_style']
            if style['definition_file']!=nodes[node['parent']]['file']:raise ValueError('Recorded diagnostic definition owner differs')
            validate_diagnostic_definition_style(node,style['definition'])
            context=style['nested_context']
            if any(type(context[k]) is not int for k in ('color','layer','layer_option')) or context['layer_option'] not in (-1,node['layer']):
                raise ValueError('Invalid recorded diagnostic nested-context style properties')


def _recorded_presentation(spec,entry,actual):
    mutable=spec['file_map'][entry['file']] not in spec['immutable_parts']
    validate_presentation(actual,spec['presentation'],require_conflict_layer=mutable)
    if entry['id'] in {r['container_node_id'] for r in spec['fields'].values()}:
        if actual.get('archive_layer_241',{}).get('hidden') is not True:raise ValueError('Missing archived FIELD note layer241 evidence')


def _recorded_manifest(spec,actual):
    if actual.get('partial_evidence_only') is True:raise ValueError('Partial failure evidence cannot establish delivery acceptance')
    manifest=actual['file_manifest']
    if set(manifest)!=set(spec['file_map'].values()):raise ValueError('Recorded file manifest incomplete')
    for name,wanted in {**spec['immutable_parts'],**spec['new_leaf_bytes']}.items():
        if manifest[name]!=wanted:raise ValueError('Recorded protected native bytes differ: '+name)
    if actual['saved_by_inspector'] is not False or actual['construction_release'] is not False:raise ValueError('Wrong save/release claim')
    if spec['copy_evidence'] and actual['source_bytes_unchanged'] is not True:raise ValueError('Missing original source-byte proof')


def validate_full_evidence(spec,actual):
    """Fail closed on incomplete/altered full native evidence. Never invokes NX."""
    from renovierung.k02.runner import validate_measurement
    from .nx_fields import validate_native_result
    from .site import match_native_shells,_native_attributes
    from renovierung.m01.pile_transfer import validate_pile_locations
    errors=[]
    try:
        if actual['schema']!=SCHEMA or actual['mode']!='AS_SAVED_FULL':raise ValueError('Wrong full evidence mode/schema')
        _recorded_manifest(spec,actual)
        if actual['all_parts_mm'] is not True or actual['all_full_paths_internal'] is not True:raise ValueError('Missing native units/path proof')
        options=actual['load_options']
        if options['requested_component_load_method']!='AsSaved' or options['component_load_method_matches_requested'] is not True or options['supplementary_search_directories']!=[] or options['full_load_profile_verified'] is not True:
            raise ValueError('Wrong fresh full native load profile')
        if actual['catalog']!=spec['catalog'] or actual['default']!=spec['base_layout']['default_state']:raise ValueError('Native catalog/default differs')
        master_entry=next(r for r in spec['entries'] if r['kind']=='master')
        _recorded_graph(spec,master_entry,actual['nodes'],actual['root'])
        validate_presentation(actual['master_presentation'],spec['presentation'])
        if set(actual['states'])!=set(spec['states']):raise ValueError('Missing/extra saved state evidence')
        for sid,wanted in spec['states'].items():
            row=actual['states'][sid];_ids(row['suppressed_ids'],wanted['suppressed_ids'],'native suppressed IDs '+sid)
            validate_visibility(wanted,row);validate_presentation(row['presentation'],spec['presentation'])
            validate_diagnostic_display(spec,wanted,row['visible_diagnostic_styles'])
            if row['exact_brep_body_counts_verified'] is not True or row['house_transforms_unchanged'] is not True:raise ValueError('Missing full state geometry/house proof')
        if set(actual['public_selections'])!=set(spec['prepared_fields']):raise ValueError('Missing public native selection proof for all24 annex fields')
        for fid,row in actual['public_selections'].items():
            if (row['selected_state']!=fid or row['public_api']!='renovierung.m01.display.select_state' or
                    row['ui_automation_performed'] is not False or row['house_transforms_unchanged'] is not True):
                raise ValueError('Public field API routing/house/UI claim differs')
            validate_visibility(spec['states'][fid],row);validate_presentation(row['presentation'],spec['presentation'])
            validate_diagnostic_display(spec,spec['states'][fid],row['visible_diagnostic_styles'])
        reviews={r['id']:r for r in spec['reviews']}
        if set(actual['reviews'])!=set(reviews):raise ValueError('Missing/extra old/new wrapper evidence')
        for rid,wanted in reviews.items():
            row=actual['reviews'][rid];entry=next(r for r in spec['entries'] if r['kind']=='review' and r['id']==rid)
            if row['file']!=wanted['file'] or row['state']!=wanted['state'] or row['master']!=spec['layout']['master'] or row['fresh_wrapper_from_disk'] is not True:
                raise ValueError('Fresh saved wrapper identity/state differs: '+rid)
            validate_visibility(entry['visibility'],row);_recorded_presentation(spec,entry,row['presentation']);_recorded_graph(spec,entry,row['nodes'],actual['root'])
            validate_diagnostic_display(spec,entry['visibility'],row['visible_diagnostic_styles'])
        subs={r['file']:r for r in spec['entries'] if r['kind']=='subassembly'}
        if set(actual['standalone'])!=set(subs):raise ValueError('Missing/extra field/section full evidence')
        for file,entry in subs.items():
            row=actual['standalone'][file]
            if row['cold_open'] is not True or row['state']!=entry['state']:raise ValueError('Standalone saved root state differs')
            validate_visibility(entry['visibility'],row);_recorded_presentation(spec,entry,row['presentation']);_recorded_graph(spec,entry,row['nodes'],actual['root'])
            validate_diagnostic_display(spec,entry['visibility'],row['visible_diagnostic_styles'])
        groups={g['id']:g for g in spec['base_layout']['context']['groups']}
        if set(actual['context_measurements'])!=set(groups):raise ValueError('Incomplete old83 context measurements')
        for gid,g in groups.items():validate_measurement(actual['context_measurements'][gid],g['component_volumes_m3'])
        oldfields={f['id']:f for f in spec['base_layout']['fields'] if f['native']}
        if set(actual['old_field_measurements'])!=set(oldfields):raise ValueError('Incomplete old22 field measurements')
        validate_pile_locations(spec['base_layout'],actual['old_pile_locations'])
        if set(actual['old_historical_measurements'])!=set(oldfields):raise ValueError('Missing archived conflict-pile measurements')
        for fid,field in oldfields.items():
            if set(actual['old_field_measurements'][fid])!=set(ROLES) or set(actual['old_refsets'][fid])!=set(ROLES):raise ValueError('Incomplete old native role/refset proof')
            for role,wanted in field['measurements'].items():
                validate_measurement(actual['old_field_measurements'][fid][role],wanted['component_volumes_m3'])
                names=actual['old_refsets'][fid][role]['body_names'];_ids(names,names,'old role body names')
                if len(names)!=wanted['body_count']:raise ValueError('Old native refset body count differs')
            if set(actual['old_historical_measurements'][fid])!={'pile_main','pile_reserve'}:raise ValueError('Incomplete historical native roles')
            for role in ('pile_main','pile_reserve'):
                validate_measurement(actual['old_historical_measurements'][fid][role],field['k02_pile_measurements'][role]['component_volumes_m3'])
        if set(actual['new_fields'])!=set(spec['prepared_fields']):raise ValueError('Incomplete new24 field leaf proof')
        if set(actual['integrated_fields'])!=set(spec['prepared_fields']):raise ValueError('Incomplete integrated10/14 classification proof')
        for fid,entry in spec['prepared_fields'].items():
            validate_native_result(entry['spec'],actual['new_fields'][fid])
            row=actual['integrated_fields'][fid];native=spec['fields'][fid]['native']
            if row['mode']!=('STUDY' if native else 'CONFLICT_DIAGNOSTIC') or row['source_mode']!=entry['spec']['mode'] or row['construction_release'] is not False:
                raise ValueError('Integrated study/diagnostic classification differs')
            wanted=actual['new_fields'][fid]['measurements']
            if row['effective_excavation_m3']!=(wanted['excavation']['volume_m3'] if native else None) or row['effective_sand_m3']!=({r:wanted[r]['volume_m3'] for r in ('pile_main','pile_reserve')} if native else {}):
                raise ValueError('Integrated diagnostic has effective sand/excavation quantities')
        site=actual['site'];wanted=spec['site_entry']
        if site['entry_sha256']!=wanted['entry_sha256'] or site['source_mask_attributes']!=_native_attributes(wanted) or site['body_count']!=wanted['body_count']:
            raise ValueError('Native shared site identity/source/mask differs')
        if site['import_model_refset']['name']!='MODEL':raise ValueError('Missing native STEP MODEL reference-set proof')
        _ids(site['import_model_refset']['body_names'],[s['id'] for s in wanted['shells']],'native MODEL body members')
        if set(site['shell_measurements'])!={s['id'] for s in wanted['shells']}:raise ValueError('Native site shell inventory differs')
        mapping=match_native_shells(wanted,list(site['shell_measurements'].values()))
        if any(site['shell_measurements'][sid]['tag']!=tag for sid,tag in mapping.items()):raise ValueError('Native named site shell geometry differs')
        if set(site['reference_sets'])!=set(wanted['reference_sets']):raise ValueError('Native shared site refset inventory differs')
        for fid,ref in wanted['reference_sets'].items():
            row=site['reference_sets'][fid]
            if row['name']!=ref['name'] or row['body_count']!=ref['body_count']:raise ValueError('Native site refset identity/count differs')
            _ids(row['shell_ids'],ref['shell_ids'],'native site refset shells')
            if not math.isclose(row['volume_m3'],ref['volume_m3'],rel_tol=1e-6,abs_tol=1e-10):raise ValueError('Native site refset volume differs')
        if site['no_external_dependencies'] is not True or site['saved_by_inspector'] is not False:raise ValueError('Native site isolation/save proof differs')
    except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError) as error:
        errors.append('Invalid full annex delivery evidence: '+str(error))
    return errors


def validate_default_evidence(spec,actual):
    """Pure exact145-entry gate for a moved flat directory/minimal native run."""
    errors=[]
    try:
        if actual['schema']!=SCHEMA or actual['mode']!='MOVED_FROM_DIRECTORY_DEFAULT':raise ValueError('Wrong cold default evidence mode/schema')
        _recorded_manifest(spec,actual)
        options=actual['load_options']
        if options['requested_component_load_method']!='FromDirectory' or options['component_load_method_matches_requested'] is not True or options['supplementary_search_directories']!=[] or options['minimal_display_profile_verified'] is not True:
            raise ValueError('Wrong native cold default load profile/search paths')
        validate_search_directory_isolation(options['search_directory_isolation'])
        entries={r['file']:r for r in spec['entries']}
        if set(actual['entries'])!=set(entries):raise ValueError('Missing/extra cold default user entry evidence')
        limits={}
        for file,entry in entries.items():
            row=actual['entries'][file]
            if any(row[k]!=entry[k] for k in ('id','kind','file','state')):raise ValueError('Cold default entry identity/state differs')
            for key in ('snapshot_before_reference_walk','cold_open','all_parts_mm','all_full_paths_internal'):
                if row[key] is not True:raise ValueError('Missing native cold/default evidence flag: '+key)
            for key in ('files_saved','brep_mass_measurements_performed','exact_brep_body_counts_verified'):
                if row[key] is not False:raise ValueError('Unsupported minimal-load save/mass/B-rep claim')
            validate_default_snapshot(entry,row['display_snapshot'],spec=spec)
            _recorded_presentation(spec,entry,row['presentation']);_recorded_graph(spec,entry,row['nodes'],actual['root'],full=False)
            validate_default_definition_binding(spec,row,actual['file_manifest'])
            limitation=register_marker_limitation(spec,entry,row['display_snapshot'],row['nodes'],actual['file_manifest'])
            if row['register_only_marker_limitation']!=limitation:raise ValueError('Register-only scene limitation evidence differs')
            if limitation is not None:limits[file]=limitation
            from pathlib import PureWindowsPath,PurePosixPath
            path_type=PureWindowsPath if PureWindowsPath(actual['root']).drive else PurePosixPath
            root=path_type(actual['root'])
            if path_type(row['root_full_path'])!=root/spec['file_map'][file]:raise ValueError('Cold opened root FullPath differs')
            loaded=row['loaded_full_paths']
            if file not in loaded or set(loaded)-set(spec['file_map']):raise ValueError('Cold loaded file inventory differs')
            for logical,path in loaded.items():
                if path_type(path)!=root/spec['file_map'][logical]:raise ValueError('Cold loaded native FullPath differs')
        if actual['register_only_marker_limitations']!=limits:raise ValueError('Register-only marker limitation summary differs')
    except (ValueError,KeyError,TypeError,AttributeError,IndexError,OverflowError) as error:
        errors.append('Invalid moved directory/default annex evidence: '+str(error))
    return errors
