"""Declarative/additive M02 upgrade of a separately cloned flat M01 master.

No source copy or NX process is started here. Native mutation requires the
explicit independent-copy certificate and a fresh owned batch session. Only
the new target's existing master/annex containers/reviews and new wrappers are
saved; the 25 geometry/site leaves and other 284 baseline files stay unchanged.
"""
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re

from renovierung.m01.delivery_paths import make_file_map,mapfile
from renovierung.m01.states import state_catalog,state_spec
from .nx_fields import REFSETS,ROLES

IDENTITY=[1,0,0,0,1,0,0,0,1]
LAYERS=(101,102,103,104,200,201,210,240)
SCHEMA='ANBAU_M01_UPGRADE_SPEC_V1'


def _canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)


def _hash(value):return hashlib.sha256(_canonical(value).encode()).hexdigest()
def _digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def attribute_titles_to_remove(titles,key):
    """Only own exact JSON key/chunks, including stale chunks after size changes."""
    return sorted({title for title in titles if title==key or re.fullmatch(re.escape(key)+r'_\d{3,}',title)})


def review_edge_strips(plan,minimum_mm=600):
    """Conservative trench error-hull to cadastral boundary, never pile distance."""
    from tools.check_m01_clearances import clearance
    if minimum_mm!=600:raise ValueError('Explicit own unloaded-edge strip criterion is 600 mm')
    records={};regular=[];diagnostic=[]
    for field in plan['fields']:
        fid=field['id'];source_native=field['native_candidate'];row={'id':fid,'source_native_candidate':source_native}
        if source_native:
            result=clearance([field['uncertainty_coverage_hull_xy_mm']],[plan['boundary_xy_mm']],filled=False)
            distance=result['distance_mm'];passed=distance>=minimum_mm
            row.update(parcel_edge_clearance_mm=distance,required_unloaded_edge_strip_mm=minimum_mm,
                       witness_points_xy_mm=result['points_mm'],edge_strip_criterion_passed=passed,
                       reserve_mm=distance-minimum_mm,
                       reason='PARCEL_EDGE_STRIP_LT_600_MM' if not passed else 'GEOMETRY_AND_EDGE_STRIP_DISPLAY_CHECK_ONLY')
        else:passed=False;row['reason']=field['status']
        row['display_mode']='STUDY' if passed else 'CONFLICT_DIAGNOSTIC'
        (regular if passed else diagnostic).append(fid);records[fid]=row
    return {'schema':'ANBAU_PARCEL_EDGE_STRIP_REVIEW_V1','construction_release':False,
            'scope':'CONSERVATIVE_TRENCH_ERROR_HULL_TO_CADASTRAL_BOUNDARY_DISPLAY_ONLY',
            'plan_sha256':_hash(plan),'minimum_unloaded_edge_strip_mm':minimum_mm,
            'regular_study_ids':regular,'diagnostic_ids':diagnostic,'fields':records,
            'limitation':'Map contour is not a surveyed boundary. A numerical surplus is no stability, load, access or construction release.'}


def write_edge_strip_review(root,review):
    """Publish only additive review data; geometry PLAN and STEP inputs stay intact."""
    root=Path(root).resolve();directory=root/'renovierung/anbau'
    path=directory/'RANDSTREIFEN_REVIEW.json'
    content=(json.dumps(review,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')
    if path.exists() and path.read_bytes()!=content:
        raise FileExistsError('Pinned parcel-edge review differs; use an explicit new review revision')
    if not path.exists():path.write_bytes(content)
    catalog=directory/'KATALOG.json';data=json.loads(catalog.read_text(encoding='utf-8'))
    data['aktuelleDarstellungsfreigabe']={'scope':'DISPLAY_ONLY_NO_CONSTRUCTION_RELEASE','construction_release':False,
        'review':'renovierung/anbau/RANDSTREIFEN_REVIEW.json','review_sha256':_digest(path),
        'regular_study_ids':review['regular_study_ids'],'diagnostic_ids':review['diagnostic_ids'],
        'regular_study_count':len(review['regular_study_ids']),'diagnostic_count':len(review['diagnostic_ids'])}
    catalog.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return {'review':str(path),'sha256':_digest(path),'catalog':str(catalog)}


def _metadata(previous,field,leaf):
    result=deepcopy(previous)
    keys=('status','blockers','conflicts','access_conflicts','volume_m3','diagnostic_volume_m3','note',
          'assumed_slab_underside_z_mm','formation_z_mm','length_mm','width_mm','measurements','display_marker')
    for key in keys:result[key]=deepcopy(field[key])
    result.update(native=leaf['mode']=='STUDY',native_candidate=field['native_candidate'],
                  diagnostic_only=field['diagnostic_only'],construction_release=False,
                  native_verified=False,anbau_source_field_sha256=leaf['field_sha256'],
                  anbau_native_mode=leaf['mode'],anbau_previous_field_sha256=_hash(previous))
    result['display_stockpile']={role:{k:deepcopy(v) for k,v in row.items() if k in
        ('target_volume_m3','volume_m3','component_volumes_m3','body_count','bbox_mm','apex_z_mm','center_xy_mm')}
        for role,row in field['display_stockpile'].items()}
    return result


def _node(nid,parent,file,name,kind,*,refset='Entire Part',blank=False,role=None):
    result={'id':nid,'parent':parent,'file':file,'name':name,'kind':kind,'reference_set':refset,
            'blank':bool(blank),'translation_mm':[0,0,0],'rotation':list(IDENTITY)}
    if role is not None:result['role']=role
    return result


def prepare_upgrade(base_layout,anbau_plan,field_native_inputs,site_entry):
    """Return mesh-free expectations; never change input records or native files."""
    from .site import validate_site_entry,_native_attributes
    try:
        if (anbau_plan['schema']!='ANBAU_DISPLAY_PLAN_V1' or anbau_plan['construction_release'] is not False or
                field_native_inputs['schema']!='ANBAU_FIELD_INPUTS_V1' or
                field_native_inputs['plan_sha256']!=_hash(anbau_plan)):
            raise ValueError('Annex plan/prepared native input hashes differ')
        validate_site_entry(site_entry)
        base_map=make_file_map(base_layout)
        if len(base_map)!=318:raise ValueError('Expected complete unchanged 318-Part flat M01.2 basis')
        original_catalog=state_catalog(base_layout)
        if len(original_catalog)!=36:raise ValueError('Expected the original 36 saved M01 states')
        source_fields={f['id']:f for f in anbau_plan['fields']}
        expected={f['id'] for f in base_layout['fields'] if f['sector_id'] in ('PS10','PS11','PS12','PS13')}
        prepared=field_native_inputs['fields']
        if len(source_fields)!=24 or set(source_fields)!=expected or set(prepared)!=expected:
            raise ValueError('Upgrade must cover exactly all 24 existing annex FIELD nodes')
        source_free={fid for fid,f in source_fields.items() if f['native_candidate']}
        edge_review=review_edge_strips(anbau_plan);free=set(edge_review['regular_study_ids'])
        if set(site_entry['reference_sets'])!=source_free:
            raise ValueError('Shared site reference sets differ from free annex candidates')
        layout=deepcopy(base_layout);nodes={n['id']:n for n in layout['nodes']};base_nodes={n['id']:n for n in base_layout['nodes']}
        if len(nodes)!=len(layout['nodes']):raise ValueError('Duplicate original node IDs')
        fields={f['id']:f for f in layout['fields']}
        updates={};new_nodes=[];leaf_files=set();mutable={layout['master']}
        for fid,field in sorted(source_fields.items()):
            previous=fields[fid];nid=previous['node_id'];leaf=prepared[fid]['spec']
            source_native=fid in source_free;native=fid in free;mode='STUDY' if native else 'CONFLICT_DIAGNOSTIC'
            source_mode='STUDY' if source_native else 'CONFLICT_DIAGNOSTIC'
            filename=fid+('_STUDY.prt' if source_native else '_CONFLICT.prt')
            if (leaf['id']!=fid or leaf['mode']!=source_mode or leaf['file']!=filename or
                    leaf['field_sha256']!=_hash(field) or leaf['construction_release'] is not False or
                    leaf['refsets']!=(REFSETS if source_native else {'conflict':'ANBAU_CONFLICT'}) or
                    source_native and (field['blockers'] or field['conflicts']) or
                    not source_native and (field['volume_m3'] is not None or field['measurements'])):
                raise ValueError('Annex native field declaration/classification differs: '+fid)
            if any(n['parent']==nid for n in base_layout['nodes']):
                raise ValueError('Annex original FIELD must be the existing empty register container')
            metadata=_metadata(previous,field,leaf)
            metadata.update(native=native,native_candidate=native,diagnostic_only=not native,
                            anbau_source_native_mode=source_mode,anbau_native_mode=mode)
            if source_native:
                edge=edge_review['fields'][fid]
                metadata.update(parcel_edge_clearance_mm=edge['parcel_edge_clearance_mm'],
                    required_unloaded_edge_strip_mm=600,edge_strip_criterion_passed=edge['edge_strip_criterion_passed'])
                if not native:
                    metadata.update(status='PARCEL_EDGE_STRIP_CONFLICT_DIAGNOSTIC',volume_m3=None,
                                    measurements={},display_stockpile={})
                    metadata['blockers'].append('PARCEL_EDGE_STRIP_LT_600_MM')
                    metadata['conflicts'].append({'kind':'PARCEL_EDGE_STRIP','distance_mm':edge['parcel_edge_clearance_mm'],
                                                  'required_mm':600,'solid_intersection_volume_m3':None})
                    metadata['note']=(fid+' RANDSTREIFENKONFLIKT: %.3f mm statt600mm; '%edge['parcel_edge_clearance_mm']+
                                      'nur rote Konfliktgeometrie, keine effektive Aushub-/Sandmenge, keine Bau-/Grabfreigabe')
                elif edge['reserve_mm']<1:
                    metadata['note']+='; KARTENRAND-GRENZFALL: nur %.3f mm Reserve ueber600mm, keine belastbare Freigrenze'%edge['reserve_mm']
            fields[fid].clear();fields[fid].update(metadata)
            nodes[nid]['name']=fid+('_ANBAU_STUDIE' if native else '_RANDSTREIFENKONFLIKT' if source_native else '_ROTE_KONFLIKTDIAGNOSE')
            children=[]
            if native:
                if site_entry['field_regions'][fid]!=field['study_terrain']['uv_cell_bounds']:
                    raise ValueError('Annex site/cut-soil crop mask differs')
                for role in ROLES:
                    child=_node('ANBAU_ROLE_'+fid+'_'+role.upper(),nid,filename,fid+'_ANBAU_'+role,
                                'role',refset=REFSETS[role],blank=role in ('excavation','pile_reserve'),role=role)
                    children.append(child)
                children.append(_node('ANBAU_SITE_'+fid,nid,site_entry['file'],fid+'_GRUNDSTUECK',
                                      'annex_site',refset=site_entry['reference_sets'][fid]['name']))
            else:
                diagnostic_refset=leaf['refsets']['excavation'] if source_native else leaf['refsets']['conflict']
                children.append(_node('ANBAU_CONFLICT_'+fid,nid,filename,fid+'_ROTE_KONFLIKTDIAGNOSE',
                                      'diagnostic',refset=diagnostic_refset,role='conflict'))
                children[-1].update(layer=240,color=186,source_body_layer=102 if source_native else 240)
            if any(c['id'] in nodes for c in children):raise ValueError('New annex node ID collides with basis')
            for child in children:nodes[child['id']]=child
            new_nodes.extend(children);leaf_files.add(filename);mutable.add(base_nodes[nid]['file'])
            updates[fid]={'container_node_id':nid,'container_file':base_nodes[nid]['file'],
                          'container_name':nodes[nid]['name'],'metadata':deepcopy(metadata),
                          'native':native,'diagnostic':not native,'mode':mode,'source_mode':source_mode,
                          'diagnostic_refset':None if native else diagnostic_refset,
                          'diagnostic_body_count':0 if native else leaf['geometry']['excavation']['body_count'],
                          'child_ids':[c['id'] for c in children],
                          'leaf_file':filename,'leaf_spec_sha256':_hash(leaf),'leaf_field_sha256':leaf['field_sha256'],
                          'leaf_refsets':deepcopy(leaf['refsets']),
                          'leaf_body_counts':{r:leaf['geometry'][r if source_native else 'excavation']['body_count']
                                              for r in (ROLES if source_native else ('conflict',))}}
        layout['nodes'].extend(deepcopy(new_nodes));leaf_files.add(site_entry['file'])
        section_defaults={};reviews=[]
        for sid in ('PS10','PS11','PS12','PS13'):
            members=sorted(fid for fid,f in source_fields.items() if f['sector_id']==sid)
            candidates=[fid for fid in members if fid in free];selected=(candidates or members)[0]
            section_defaults[sid]={'state':selected,'selected_field_node_id':updates[selected]['container_node_id'],
                                   'field_node_ids':[updates[fid]['container_node_id'] for fid in members],
                                   'master_arrangement':'ANBAU_SECTION_MASTER_'+sid,
                                   'default_arrangement':'ANBAU_SECTION_DEFAULT_'+sid}
            section='SECTION_'+sid;mutable.add(nodes[section]['file'])
            mutable.add(nodes[nodes[section]['parent']]['file'])
            nodes[section]['name']='Sektion_'+sid+'_%02d_STUDIEN_%02d_KONFLIKTE'%(len(candidates),len(members)-len(candidates))
        for row in layout['review_masters']:
            result=deepcopy(row);result['action']='update' if row['id'] in section_defaults else 'keep'
            if result['action']=='update':
                result['state']=section_defaults[row['id']]['state'];mutable.add(row['file']);row['state']=result['state']
            reviews.append(result)
        for fid,field in sorted(source_fields.items()):
            row={'id':fid,'file':'Bauabschnitte/'+field['sector_id']+'/'+fid+'.prt','state':fid}
            layout['review_masters'].append(deepcopy(row));reviews.append(dict(row,action='create'))
        catalog={**original_catalog,**{fid:'M01_'+fid.replace('-','_') for fid in sorted(source_fields)}}
        new_ids={n['id'] for n in new_nodes};old_context={g['id'] for g in base_layout['context']['groups']}
        old_roles={n['id'] for n in base_layout['nodes'] if n['kind']=='role'}
        field_nodes={f['node_id'] for f in base_layout['fields']};states={}
        for sid,name in catalog.items():
            role_counts={r:0 for r in ROLES};visible_context=[];site=None;diagnostic=0
            if sid in original_catalog:
                hidden=set(state_spec(base_layout,sid)['suppressed_ids'])|new_ids
                visible_fields=[f['id'] for f in base_layout['fields'] if f['node_id'] not in hidden]
                for f in base_layout['fields']:
                    if f['id']==sid and f['native']:
                        for r in ROLES:
                            if r not in ('excavation','pile_reserve'):role_counts[r]=f['measurements'][r]['body_count']
                visible_context=[g['id'] for g in base_layout['context']['groups'] if g['id'] not in hidden]
            else:
                update=updates[sid];hidden=(field_nodes-{update['container_node_id']})|old_roles|old_context|new_ids|{'TERRAIN'}
                visible_fields=[sid]
                if update['native']:
                    for r in ('cut_soil','pile_main'):
                        hidden.remove('ANBAU_ROLE_'+sid+'_'+r.upper());role_counts[r]=source_fields[sid]['measurements'][r]['body_count']
                    hidden.remove('ANBAU_SITE_'+sid)
                    site={'file':site_entry['file'],'refset':site_entry['reference_sets'][sid]['name'],
                          'shell_ids':deepcopy(site_entry['reference_sets'][sid]['shell_ids']),
                          'body_count':site_entry['reference_sets'][sid]['body_count']}
                else:
                    hidden.remove('ANBAU_CONFLICT_'+sid)
                    hidden.update({'ENVIRONMENT','UTILITIES'}&set(nodes))
                    diagnostic=updates[sid]['diagnostic_body_count']
            states[sid]={'id':sid,'name':name,'suppressed_ids':sorted(hidden),'visible_role_bodies':role_counts,
                         'visible_diagnostic_bodies':diagnostic,'visible_context_ids':visible_context,
                         'original_context_body_count':sum(g['body_count'] for g in base_layout['context']['groups'] if g['id'] in visible_context),
                         'site':site,'visible_field_ids':sorted(visible_fields),'terrain_visible':sid=='BASE'}
        file_map=make_file_map(layout)
        if len(file_map)!=367 or len(mutable)!=34:raise ValueError('Unexpected additive part/save inventory')
        result={'schema':SCHEMA,'construction_release':False,'base_layout_sha256':_hash(base_layout),
                'plan_sha256':_hash(anbau_plan),'base_layout':deepcopy(base_layout),'layout':layout,
                'base_file_map':base_map,'file_map':file_map,'fields':updates,'new_nodes':new_nodes,
                'catalog':catalog,'original_catalog':original_catalog,'states':states,'section_defaults':section_defaults,
                'reviews':reviews,'mutable_base_files':sorted(mutable),'new_leaf_files':sorted(leaf_files),
                'site_contract':{'file':site_entry['file'],'entry_sha256':site_entry['entry_sha256'],
                    'attributes':_native_attributes(site_entry),'reference_sets':deepcopy(site_entry['reference_sets']),
                    'body_count':site_entry['body_count'],'shell_ids':[s['id'] for s in site_entry['shells']]},
                'presentation':deepcopy(base_layout['presentation']),'display_layers':list(LAYERS),'archive_layer':241,
                'edge_strip_review':edge_review,'copy_evidence':None}
        from renovierung.m01.nx_journal import world_transforms
        result['expected_nodes']={row['id']:deepcopy(row) for row in layout['nodes']}
        result['expected_world_transforms']={nid:{'translation_mm':p,'rotation':r}
                                             for nid,(p,r) in world_transforms(layout).items()}
        result['spec_sha256']=_hash({k:v for k,v in result.items() if k not in ('copy_evidence','spec_sha256')})
        return result
    except (KeyError,TypeError,AttributeError,IndexError,OverflowError) as error:
        raise ValueError('Malformed additive master upgrade inputs: '+str(error)) from error


def _inventory(root):
    result={}
    for path in root.rglob('*.prt'):
        if path.is_symlink() or path.parent.resolve()!=root:raise ValueError('Upgrade requires physically flat nonsymlink Parts')
        result[path.name]={'bytes':path.stat().st_size,'sha256':_digest(path)}
    return result


def _copy_guard(root,spec):
    evidence=spec.get('copy_evidence')
    if (not isinstance(evidence,dict) or evidence.get('schema')!='ANBAU_M01_INDEPENDENT_COPY_V1' or
            evidence.get('native_independent') is not True or evidence.get('native_clone_completed') is not True or
            evidence.get('base_layout_sha256')!=spec['base_layout_sha256']):
        raise ValueError('Explicit completed native independent-copy evidence is required before mutation')
    source=Path(evidence['source_root']).resolve();target=Path(evidence['destination_root']).resolve()
    if source==target or source.is_relative_to(target) or target.is_relative_to(source) or target!=root:
        raise ValueError('Original and new upgrade target roots must be disjoint')
    bases=set(spec['base_file_map'].values());new=set(spec['new_leaf_files'])
    if (set(evidence['source_parts'])!=bases or set(evidence['copied_parts'])!=bases or
            set(evidence['new_parts'])!=new or _inventory(source)!=evidence['source_parts'] or
            _inventory(root)!={**evidence['copied_parts'],**evidence['new_parts']}):
        raise ValueError('Independent source/copied/new Part bytes or flat inventories differ')
    if spec['spec_sha256']!=_hash({k:v for k,v in spec.items() if k not in ('copy_evidence','spec_sha256')}):
        raise ValueError('Prepared upgrade specification changed')
    return source,evidence


def _replace_attribute(obj,key,value):
    """Remove stale own direct/chunk attributes before the standard M01 writer."""
    import NXOpen
    import NXOpen.Assemblies
    from renovierung.m01.display import write_attribute
    instance=isinstance(obj,NXOpen.Assemblies.Component)
    attributes=obj.GetInstanceUserAttributes() if instance else obj.GetUserAttributes()
    attributes=[attribute for attribute in attributes if attribute is not None]
    selected=set(attribute_titles_to_remove([a.Title for a in attributes],key))
    delete=obj.DeleteInstanceUserAttribute if instance else obj.DeleteUserAttribute
    seen=set()
    for attribute in sorted(attributes,key=lambda a:a.Title):
        key_type=(attribute.Title,str(attribute.Type))
        if attribute.Title in selected and key_type not in seen:
            delete(attribute.Type,attribute.Title,True,NXOpen.Update.Option.Now);seen.add(key_type)
    write_attribute(obj,key,value)


def _component_instance_name(component):
    import NXOpen.UF
    name=NXOpen.UF.UFSession.GetUFSession().Assem.AskComponentData(component.Tag)[2]
    if not isinstance(name,str) or not name:raise ValueError('Missing authoritative component instance name')
    return name


def _rename_component_instance(component,name):
    """Rename the assembly instance, distinct from its contextual custom name."""
    import NXOpen.UF
    if _component_instance_name(component).casefold()!=name.casefold():
        assem=NXOpen.UF.UFSession.GetUFSession().Assem
        instance=assem.AskInstOfPartOcc(component.Tag)
        if not instance:raise ValueError('Component has no authoritative instance tag')
        assem.RenameInstance(instance,name)
    actual=_component_instance_name(component)
    if actual.casefold()!=name.casefold():raise ValueError('NX did not retain the requested instance name')
    return actual


def _write_node(obj,row,field=None):
    import NXOpen.Assemblies
    # A Part keeps its mapped filename; NXObject.SetName is unsuitable for it.
    # Only assembly occurrences receive the visible component label.
    if isinstance(obj,NXOpen.Assemblies.Component):
        _rename_component_instance(obj,row['name']);obj.SetName(row['name'])
    values={'M01_NODE_ID':row['id'],'M01_KIND':row['kind'],'M01_DEFAULT_BLANK':row['blank'],'M01_NODE_METADATA':row}
    if field is not None:
        values.update(M01_FIELD_ID=field['id'],M01_FIELD_NATIVE=field['native'],M01_FIELD_METADATA=field,
                      ANBAU_DIAGNOSTIC=field['diagnostic_only'],ANBAU_CONSTRUCTION_RELEASE=False)
    for key,value in values.items():_replace_attribute(obj,key,value)


def _presentation(part,spec):
    import NXOpen.Layer
    from renovierung.m01.presentation import apply_presentation
    result=apply_presentation(part,spec['presentation'])
    part.Layers.SetState(240,NXOpen.Layer.State.Selectable)
    part.Layers.SetState(spec['archive_layer'],NXOpen.Layer.State.Hidden)
    return result


def _status(status,what):
    try:
        if status.NumberUnloadedParts:raise ValueError('Incomplete native upgrade load: '+what)
    finally:status.Dispose()


def _identity(component):
    p,r=component.GetPosition()
    values=[p.X,p.Y,p.Z]+[getattr(r,k) for k in ('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz')]
    if any(abs(a-b)>1e-8 for a,b in zip(values,[0,0,0]+IDENTITY)):
        raise ValueError('New annex component transform is not exact identity')


def _owned_parts(session,root):
    import NXOpen
    result={}
    for part in session.Parts:
        path=Path(part.FullPath).resolve()
        if (not part.FullPath or path.parent!=root or not path.is_file() or path.name in result or
                not part.IsFullyLoaded or part.PartUnits!=NXOpen.BasePart.Units.Millimeters):
            raise ValueError('Upgrade refuses foreign, duplicate, partial or non-mm native Parts')
        result[path.name]=part
    return result


def _open(session,root,logical,file_map,display=False):
    from renovierung.m01.nx_journal import display_part
    path=mapfile(root,logical,file_map);parts=_owned_parts(session,root)
    if path.name in parts:
        part=parts[path.name]
        if display:display_part(session,part)
    else:
        part,status=(session.Parts.OpenDisplay if display else session.Parts.OpenBase)(str(path))
        _status(status,logical)
    if Path(part.FullPath).resolve()!=path:raise ValueError('Native opened a different physical Part: '+logical)
    _owned_parts(session,root)
    return part


def _refsets(part,expected):
    """Only membership cardinality/ownership, no repeated mass measurement."""
    import NXOpen
    import NXOpen.Facet
    sets={r.Name:r for r in part.GetAllReferenceSets()}
    for name,count in expected.items():
        if name not in sets:raise ValueError('Required native reference set missing: '+name)
        bodies=set()
        for member in sets[name].AskAllDirectMembers():
            if isinstance(member,NXOpen.Body):body=member
            elif isinstance(member,NXOpen.Facet.FacetedBody) and member.IsAssociatedBodyLoaded:body=member.AssociatedBody
            else:raise ValueError('Unknown/orphan object in new body reference set: '+name)
            if body.OwningPart.Tag!=part.Tag:raise ValueError('Reference set has foreign body ownership')
            bodies.add(body.Tag)
        if len(bodies)!=count:raise ValueError('New body reference-set cardinality differs: '+name)


def _add_child(session,part,root,row,file_map):
    import NXOpen
    from renovierung.m01.display import set_blank
    matrix=NXOpen.Matrix3x3()
    for key,value in zip(('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz'),IDENTITY):setattr(matrix,key,float(value))
    child,status=part.ComponentAssembly.AddComponent(str(mapfile(root,row['file'],file_map)),row['reference_set'],row['name'],
        NXOpen.Point3d(0.,0.,0.),matrix,-1)
    _status(status,row['id'])
    if child is None:raise ValueError('Missing added annex occurrence')
    _identity(child);_write_node(child,row);set_blank(child,row['blank'])
    if row.get('layer') is not None:child.Layer=row['layer'];child.Color=row['color']
    return child


def _field_note(part,field,spec):
    from renovierung.k02.nx_build import note
    from renovierung.m01.display import read_attribute
    fid=field['id'];old=[n for n in part.Notes if n.Name=='M01_NOTE_'+fid]
    if len(old)!=1:raise ValueError('Expected one own historical FIELD note: '+fid)
    markers=[c for c in part.Curves if c.Name=='M01_REGISTER_'+fid]
    if len(markers)!=1:raise ValueError('Expected one own FIELD register marker: '+fid)
    markers[0].Color=36 if field['native'] else 186;markers[0].Layer=200;markers[0].Unblank()
    archive=[{'name':n.Name,'text':list(n.GetText()),'layer':n.Layer} for n in old]
    _replace_attribute(part,'ANBAU_PREVIOUS_FIELD_NOTES',archive)
    for n in old:
        n.SetName('ANBAU_ARCHIVE_M01_NOTE_'+fid);n.Blank();n.Layer=spec['archive_layer']
    lines=[fid+(' ANBAU STUDIE / VORPLANUNG' if field['native'] else ' ROTE / GESPERRTE KONFLIKTDIAGNOSE'),
           'DARSTELLUNGSANNAHME UK %.2f m / Pruefsohle %.2f m' %
           (field['assumed_slab_underside_z_mm']/1000,field['formation_z_mm']/1000)]
    if field['native']:
        lines.append('Aushub %.3f m3 / Lager A %.3f m3 (Einzelalternative)' %
            (field['measurements']['excavation']['volume_m3'],field['measurements']['pile_main']['volume_m3']))
    else:lines.append('KEIN AUSGEFUEHRTER SCHACHT / KEINE EFFEKTIVE MENGE / KEIN SANDLAGER')
    if 'parcel_edge_clearance_mm' in field:
        distance=field['parcel_edge_clearance_mm']
        if distance<600:lines.append('RANDSTREIFENKONFLIKT: %.3f mm statt600mm - gesperrt'%distance)
        elif distance-600<1:lines.append('KARTENRAND-GRENZFALL: nur %.3f mm rechnerische Reserve'%(distance-600))
    lines.append('FFB-Proxy -1.86 m bleibt unveraendert; keine Bau-/Grabfreigabe')
    current=note(part,lines,[float(v) for v in field['display_marker']['label']],'M01_NOTE_'+fid,130)
    current.Layer=201


def _arrangements(part,name_to_hidden,occurrences,*,default,template_name=None):
    """Create/update explicit nested suppression, without changing prototype geometry."""
    from renovierung.m01.states import _check_errors
    assembly=part.ComponentAssembly
    existing={a.Name:a for a in assembly.Arrangements}
    if template_name is not None:
        if len(existing)!=1:raise ValueError('Unmodified standalone section must have one template arrangement')
        template=assembly.ActiveArrangement;template.SetName(template_name);existing={template_name:template}
    else:
        template=existing['M01_BASE']
    for name in name_to_hidden:
        if name not in existing:existing[name]=assembly.Arrangements.Create(template,name)
    for name,hidden in name_to_hidden.items():
        unknown=set(hidden)-set(occurrences)
        if unknown:raise ValueError('Arrangement has unknown control IDs: '+repr(sorted(unknown)))
        for method,ids in ((assembly.SuppressComponents,[n for n in occurrences if n in hidden]),
                           (assembly.UnsuppressComponents,[n for n in occurrences if n not in hidden])):
            if ids:_check_errors(method([occurrences[n] for n in ids],[existing[name]]),name)
    assembly.SetDefault(existing[default]);assembly.ActiveArrangement=existing[default]
    return existing


def _section_auxiliary_ids(spec,sid):
    default=spec['section_defaults'][sid]
    fid=default['state'] if isinstance(default,dict) else default
    if not spec['fields'][fid]['native']:return []
    ids=['ANBAU_ROLE_'+fid+'_'+r for r in ('EXCAVATION','PILE_RESERVE')]
    nodes={n['id']:n for n in spec['layout']['nodes']}
    if any(nodes[nid]['parent']!=spec['fields'][fid]['container_node_id'] for nid in ids):
        raise ValueError('SECTION auxiliary role parent differs')
    return ids


def _section_occurrences(part):
    from renovierung.m01.display import read_attribute
    result={}
    def walk(parent):
        for child in parent.GetChildren():
            nid=read_attribute(child,'M01_NODE_ID')
            if nid in result:raise ValueError('Duplicate SECTION occurrence ID: '+nid)
            result[nid]=child;walk(child)
    walk(part.ComponentAssembly.RootComponent)
    return result


def _suppress_section_default_auxiliaries(part,sid,spec,occurrences=None):
    """Change only the DEFAULT arrangement's selected excavation/reserve controls."""
    from renovierung.m01.states import _check_errors
    ids=_section_auxiliary_ids(spec,sid)
    if ids:
        occurrences=_section_occurrences(part) if occurrences is None else occurrences
        name='ANBAU_SECTION_DEFAULT_'+sid
        arrangement=next(a for a in part.ComponentAssembly.Arrangements if a.Name==name)
        _check_errors(part.ComponentAssembly.SuppressComponents([occurrences[nid] for nid in ids],[arrangement]),name)
    return ids


def _section_default_snapshot(part,sid,spec,occurrences):
    import NXOpen.Assemblies
    import NXOpen.UF
    from renovierung.m01.presentation import read_presentation
    nodes={n['id']:n for n in spec['layout']['nodes']};assembly=part.ComponentAssembly
    arrangements={a.Name:a for a in assembly.Arrangements}
    def states(name):
        result={}
        for nid,component in occurrences.items():
            state,controlled=assembly.GetSuppressedState(component,arrangements[name])
            result[nid]={'native_state':str(state),'controlled':bool(controlled),
                         'suppressed':state==NXOpen.Assemblies.ComponentAssembly.SuppressedState.Suppressed}
        return result
    presentation=read_presentation(part)
    presentation['extra_layers']={str(n):str(part.Layers.GetState(n)) for n in (240,241)}
    uf=NXOpen.UF.UFSession.GetUFSession()
    return {'active_arrangement':assembly.ActiveArrangement.Name,
            'saved_default_arrangement':uf.Assem.AskNameOfArrangement(uf.Assem.AskDefaultArrangement(part.Tag)),
            'presentation':presentation,
            'nodes':{nid:_instance_name_record(c,nodes[nid],nodes[nid]['parent'],nodes[nodes[nid]['parent']]['file'])
                     for nid,c in occurrences.items()},
            'master_states':states('ANBAU_SECTION_MASTER_'+sid),'default_states':states('ANBAU_SECTION_DEFAULT_'+sid)}


def validate_section_defaults_evidence(spec,record):
    """Pure strict two-Part DEFAULT-only proof; raises on any unrelated change."""
    nodes={n['id']:n for n in spec['layout']['nodes']}
    sections={'SECTION_PS12','SECTION_PS13'};files={nodes[nid]['file'] for nid in sections}
    sha=spec['upgrade_attributes']['spec_sha256'] if 'upgrade_attributes' in spec else spec['spec_sha256']
    if (record['status']!='SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY' or record['spec_sha256']!=sha
            or set(record['saved_parts'])!=files or len(record['saved_parts'])!=2
            or record['unchanged_parts']!=365 or record['source_bytes_unchanged'] is not True
            or record['construction_release'] is not False or set(record['sections'])!=sections):
        raise ValueError('Incomplete SECTION DEFAULT repair scope')
    before,after=record['before_parts'],record['after_parts'];allowed={spec['file_map'][f] for f in files}
    if (len(before)!=367 or set(before)!=set(spec['file_map'].values()) or set(before)!=set(after)
            or any(after[n]!=r for n,r in before.items() if n not in allowed)):
        raise ValueError('SECTION DEFAULT repair changed an unrelated Part')
    keys={'active_arrangement','saved_default_arrangement','presentation','nodes','master_states','default_states'}
    for section,proof in record['sections'].items():
        sid=section.removeprefix('SECTION_');aux=_section_auxiliary_ids(spec,sid)
        if len(aux)!=2 or proof['auxiliary_ids']!=aux:raise ValueError('Unexpected SECTION auxiliary repair controls')
        before,after=proof['before'],proof['after'];local={section}
        while True:
            expanded=local|{nid for nid,row in nodes.items() if row['parent'] in local}
            if expanded==local:break
            local=expanded
        local.remove(section)
        if (set(before)!=keys or set(after)!=keys or any(before[k]!=after[k] for k in keys-{'default_states'})
                or before['active_arrangement']!='ANBAU_SECTION_DEFAULT_'+sid
                or before['saved_default_arrangement']!='ANBAU_SECTION_DEFAULT_'+sid
                or any(set(snapshot[k])!=local for snapshot in (before,after) for k in ('nodes','master_states','default_states'))):
            raise ValueError('SECTION MASTER/node/view/default identity changed')
        for nid,row in before['nodes'].items():
            wanted=nodes[nid]
            node_keys={'parent_id','owner_file','instance_name','custom_name','reference_set','translation_mm','rotation',
                       'used_arrangement','metadata_sha256'}
            if (set(row)!=node_keys or row['instance_name'].casefold()!=wanted['name'].casefold() or row['custom_name'].casefold()!=wanted['name'].casefold()
                    or row['parent_id']!=wanted['parent'] or row['owner_file']!=nodes[wanted['parent']]['file']
                    or row['reference_set']!=wanted['reference_set'] or row['translation_mm']!=wanted['translation_mm']
                    or row['rotation']!=wanted['rotation'] or row['metadata_sha256']!=_hash(wanted)):
                raise ValueError('SECTION instance name/transform/refset/metadata differs: '+nid)
        for snapshot in (before,after):
            for states in (snapshot['master_states'],snapshot['default_states']):
                for state in states.values():
                    if (set(state)!={'native_state','controlled','suppressed'} or not isinstance(state['native_state'],str)
                            or not state['native_state'] or type(state['controlled']) is not bool or type(state['suppressed']) is not bool):
                        raise ValueError('Incomplete SECTION suppression observation')
        for nid,state in after['default_states'].items():
            if nid in aux:
                if state['controlled'] is not True or state['suppressed'] is not True:
                    raise ValueError('SECTION DEFAULT auxiliary is not explicitly suppressed: '+nid)
            elif state!=before['default_states'][nid]:raise ValueError('SECTION DEFAULT changed a non-auxiliary control: '+nid)
        default=spec['section_defaults'][sid];fid=default['state'] if isinstance(default,dict) else default
        selected=spec['fields'][fid]['container_node_id']
        for field in spec['fields'].values():
            nid=field['container_node_id']
            if nid in local and nodes[nid]['parent']==section:
                state=after['default_states'][nid]
                if state['controlled'] is not True or state['suppressed'] is not (nid!=selected):
                    raise ValueError('SECTION DEFAULT direct FIELD selection differs: '+nid)


def _persist_section_definitions(session,root,spec,nodes,arrangements,save_part):
    """Write SECTION instance definitions in their actual parent prototype Part."""
    from renovierung.m01.display import read_attribute
    owners={}
    for sid in spec['section_defaults']:
        ident='SECTION_'+sid;owners.setdefault(nodes[ident]['parent'],set()).add(ident)
    saved=[]
    for owner,expected in sorted(owners.items()):
        filename=nodes[owner]['file'];part=_open(session,root,filename,spec['file_map'],True)
        found=set()
        for child in part.ComponentAssembly.RootComponent.GetChildren():
            ident=read_attribute(child,'M01_NODE_ID')
            if ident not in expected:continue
            if ident in found:raise ValueError('Duplicate SECTION definition in parent Part: '+ident)
            _write_node(child,nodes[ident]);sid=ident.removeprefix('SECTION_')
            child.SetUsedArrangement(arrangements[sid][spec['section_defaults'][sid]['master_arrangement']])
            found.add(ident)
        if found!=expected:raise ValueError('Incomplete SECTION definitions in parent Part: '+owner)
        save_part(part);saved.append(filename)
    return saved


def _repair_guard(root,spec,old,before):
    """Allow only the reviewed owner-save correction of an unpublished candidate."""
    root=Path(root).resolve();evidence=spec['copy_evidence']
    source=Path(evidence['source_root']).resolve()
    if (spec['schema']!=SCHEMA or old['schema']!='ANBAU_END_VERIFICATION_V1'
            or spec['spec_sha256']!=_hash({k:v for k,v in spec.items() if k not in ('copy_evidence','spec_sha256')})
            or old['spec_sha256']!=_hash({k:v for k,v in old.items() if k!='spec_sha256'})):
        raise ValueError('Repair specification hashes differ')
    if (evidence['schema']!='ANBAU_M01_INDEPENDENT_COPY_V1' or evidence['native_clone_completed'] is not True
            or evidence['native_independent'] is not True or old['copy_evidence']!=evidence
            or Path(evidence['destination_root']).resolve()!=root or source==root
            or source.is_relative_to(root) or root.is_relative_to(source)
            or evidence['base_layout_sha256']!=spec['base_layout_sha256']
            or spec['base_layout_sha256']!=_hash(spec['base_layout'])):
        raise ValueError('Repair requires the original independent-copy certificate')
    pointer=root.parent/'CURRENT.json'
    if pointer.is_file() and json.loads(pointer.read_bytes()).get('directory')==root.name:
        raise ValueError('Refusing to repair a published CURRENT delivery')
    if (len(before)!=367 or set(before)!=set(spec['file_map'].values()) or _inventory(root)!=before
            or old['file_map']!=spec['file_map'] or len(evidence['copied_parts'])!=318
            or len(evidence['new_parts'])!=25 or _inventory(source)!=evidence['source_parts']):
        raise ValueError('Repair candidate/source byte inventories differ')
    for name,record in {**old['immutable_parts'],**evidence['new_parts']}.items():
        if before[name]!=record:raise ValueError('Repair protected input bytes changed: '+name)
    nodes={n['id']:n for n in spec['layout']['nodes']}
    owners={nodes['SECTION_'+sid]['parent'] for sid in spec['section_defaults']}
    if owners!={'CONSTRUCTION'}:raise ValueError('Repair is limited to the reviewed CONSTRUCTION owner')
    owner_files={nodes[nid]['file'] for nid in owners}
    old_mutable=sorted(logical for logical,actual in spec['base_file_map'].items() if actual not in old['immutable_parts'])
    if (len(old_mutable)!=33 or len(spec['mutable_base_files'])!=34
            or set(spec['mutable_base_files'])!=set(old_mutable)|owner_files):
        raise ValueError('Repair changes more than the exact missing owner-save exemption')
    reconstructed=dict(spec,mutable_base_files=old_mutable)
    old_sha=old['upgrade_attributes']['spec_sha256']
    if (old['upgrade_attributes']['schema']!=SCHEMA
            or _hash({k:v for k,v in reconstructed.items() if k not in ('copy_evidence','spec_sha256')})!=old_sha):
        raise ValueError('Repair would change the original layout/geometry/arrangement intent')
    return {'source':source,'save_files':sorted(owner_files|{nodes['MASTER']['file']}),
            'old_upgrade_spec_sha256':old_sha}


def repair_existing(session,root,new_upgrade,old_verification_spec,before_manifest):
    """Repair exactly CONSTRUCTION plus Master; fresh full/default proof is mandatory."""
    root=Path(root).resolve();spec=new_upgrade
    guard=_repair_guard(root,spec,old_verification_spec,before_manifest)
    if session.IsBatch is not True or list(session.Parts):
        raise ValueError('Repair requires its own fresh empty batch session')
    from renovierung.k02.nx_build import save
    from renovierung.m01.display import read_attribute
    from renovierung.m01.nx_journal import display_part
    from renovierung.m01.inspection import _configure_load
    nodes={n['id']:n for n in spec['layout']['nodes']};saved=[]
    try:
        _configure_load(session,'FromDirectory',full=True)
        master=_open(session,root,nodes['MASTER']['file'],spec['file_map'],True)
        if (read_attribute(master,'ANBAU_UPGRADE_SPEC_SHA256')!=guard['old_upgrade_spec_sha256']
                or read_attribute(master,'M01_STATE_CATALOG')!=spec['catalog']):
            raise ValueError('Repair candidate master identity/catalog differs')
        arrangements={}
        for sid,default in spec['section_defaults'].items():
            node=nodes['SECTION_'+sid];part=_open(session,root,node['file'],spec['file_map'])
            if read_attribute(part,'M01_NODE_METADATA')!=node:
                raise ValueError('Repair candidate SECTION prototype metadata differs: '+sid)
            arrangements[sid]={a.Name:a for a in part.ComponentAssembly.Arrangements}
            if set(arrangements[sid])!={default['master_arrangement'],default['default_arrangement']}:
                raise ValueError('Repair candidate SECTION arrangements differ: '+sid)
        _owned_parts(session,root)
        saved.extend(_persist_section_definitions(session,root,spec,nodes,arrangements,save))
        display_part(session,master)
        _replace_attribute(master,'ANBAU_UPGRADE_SPEC_SHA256',spec['spec_sha256'])
        save(master);saved.append(nodes['MASTER']['file'])
        after=_inventory(root);allowed={spec['file_map'][logical] for logical in guard['save_files']}
        if set(saved)!=set(guard['save_files']) or set(after)!=set(before_manifest):
            raise ValueError('Repair save/file inventory differs')
        if any(after[name]!=record for name,record in before_manifest.items() if name not in allowed):
            raise ValueError('Repair changed a Part outside the exact two-Part save set')
        _owned_parts(session,root)
        return {'status':'REPAIRED_PENDING_FRESH_VERIFY','old_upgrade_spec_sha256':guard['old_upgrade_spec_sha256'],
                'spec_sha256':spec['spec_sha256'],'saved_parts':sorted(saved),
                'before_parts':deepcopy(before_manifest),'after_parts':after,'unchanged_parts':len(after)-len(allowed),
                'source_bytes_unchanged':True,'construction_release':False}
    finally:
        if _inventory(guard['source'])!=spec['copy_evidence']['source_parts']:
            raise ValueError('Read-only original M01.2 source bytes changed during repair')


def _instance_name_repair_guard(root,spec,verification,before):
    """Bind naming-only repair to an identical saved model expectation contract."""
    root=Path(root).resolve();copy=spec['copy_evidence'];source=Path(copy['source_root']).resolve()
    if (spec['schema']!=SCHEMA or verification['schema']!='ANBAU_END_VERIFICATION_V1'
            or spec['spec_sha256']!=_hash({k:v for k,v in spec.items() if k not in ('copy_evidence','spec_sha256')})
            or verification['spec_sha256']!=_hash({k:v for k,v in verification.items() if k!='spec_sha256'})
            or verification['upgrade_attributes']!={'schema':SCHEMA,'spec_sha256':spec['spec_sha256']}
            or verification['layout']!=spec['layout'] or verification['file_map']!=spec['file_map']
            or verification['copy_evidence']!=copy):
        raise ValueError('Naming repair would change the saved expectation contract')
    if (copy['schema']!='ANBAU_M01_INDEPENDENT_COPY_V1' or copy['native_clone_completed'] is not True
            or copy['native_independent'] is not True or Path(copy['destination_root']).resolve()!=root
            or source==root or source.is_relative_to(root) or root.is_relative_to(source)
            or copy['base_layout_sha256']!=spec['base_layout_sha256']
            or spec['base_layout_sha256']!=_hash(spec['base_layout'])):
        raise ValueError('Naming repair requires the original independent-copy certificate')
    pointer=root.parent/'CURRENT.json'
    if pointer.is_file() and json.loads(pointer.read_bytes()).get('directory')==root.name:
        raise ValueError('Refusing to rename instances in a published CURRENT delivery')
    if (len(before)!=367 or set(before)!=set(spec['file_map'].values()) or _inventory(root)!=before
            or len(copy['copied_parts'])!=318 or len(copy['new_parts'])!=25
            or _inventory(source)!=copy['source_parts']):
        raise ValueError('Naming repair candidate/source byte inventories differ')
    for name,record in {**verification['immutable_parts'],**copy['new_parts']}.items():
        if before[name]!=record:raise ValueError('Naming repair protected input bytes changed: '+name)
    nodes={n['id']:n for n in spec['layout']['nodes']}
    ids={'SECTION_'+sid for sid in spec['section_defaults']}|{f['container_node_id'] for f in spec['fields'].values()}
    owners={nodes[nid]['parent'] for nid in ids}
    expected_owners={'CONSTRUCTION'}|{'SECTION_'+sid for sid in ('PS10','PS11','PS12','PS13')}
    files={nodes[nid]['file'] for nid in owners}
    if (len(ids)!=28 or len(spec['fields'])!=24 or owners!=expected_owners or len(files)!=5
            or not files.issubset(spec['mutable_base_files'])):
        raise ValueError('Naming repair requires exactly28 instances in the five reviewed mutable owners')
    return {'source':source,'save_files':sorted(files),'node_ids':sorted(ids)}


def _instance_name_record(component,row,parent_id,owner_file):
    from renovierung.m01.display import read_attribute
    metadata=read_attribute(component,'M01_NODE_METADATA')
    p,r=component.GetPosition();translation=[p.X,p.Y,p.Z]
    rotation=[getattr(r,k) for k in ('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz')]
    if (metadata!=row or component.ReferenceSet!=row['reference_set']
            or component.Name.casefold()!=row['name'].casefold()
            or any(not math.isfinite(a) or abs(a-b)>1e-8 for a,b in
                   zip(translation+rotation,row['translation_mm']+row['rotation']))):
        raise ValueError('Naming repair instance metadata/custom name/refset/transform differs: '+row['id'])
    arrangement=component.UsedArrangement
    return {'parent_id':parent_id,'owner_file':owner_file,'instance_name':_component_instance_name(component),
            'custom_name':component.Name,'reference_set':component.ReferenceSet,
            'translation_mm':translation,'rotation':rotation,
            'used_arrangement':arrangement.Name if arrangement is not None else None,
            'metadata_sha256':_hash(metadata)}


def repair_instance_names(session,root,upgrade,verification_spec,before_manifest):
    """Rename28 existing instances in five owners; do not save geometry or Master."""
    root=Path(root).resolve();guard=_instance_name_repair_guard(root,upgrade,verification_spec,before_manifest)
    if session.IsBatch is not True or list(session.Parts):
        raise ValueError('Naming repair requires its own fresh empty batch session')
    from renovierung.k02.nx_build import save
    from renovierung.m01.display import read_attribute
    from renovierung.m01.inspection import _configure_load
    nodes={n['id']:n for n in upgrade['layout']['nodes']};owners={}
    for nid in guard['node_ids']:owners.setdefault(nodes[nid]['parent'],set()).add(nid)
    saved=[];before_names={};after_names={}
    try:
        _configure_load(session,'FromDirectory',full=True)
        for parent,expected in sorted(owners.items()):
            filename=nodes[parent]['file'];part=_open(session,root,filename,upgrade['file_map'],True)
            selected={}
            for child in part.ComponentAssembly.RootComponent.GetChildren():
                nid=read_attribute(child,'M01_NODE_ID')
                if nid not in expected:continue
                if nid in selected:raise ValueError('Duplicate direct naming repair instance: '+nid)
                selected[nid]=child
            if set(selected)!=expected:raise ValueError('Missing direct naming repair instances: '+parent)
            for nid,child in sorted(selected.items()):
                before_names[nid]=_instance_name_record(child,nodes[nid],parent,filename)
                _rename_component_instance(child,nodes[nid]['name'])
                after_names[nid]=_instance_name_record(child,nodes[nid],parent,filename)
                if {k:v for k,v in before_names[nid].items() if k!='instance_name'}!={k:v for k,v in after_names[nid].items() if k!='instance_name'}:
                    raise ValueError('Naming repair changed instance data beyond its authoritative name: '+nid)
            save(part);saved.append(filename)
        _owned_parts(session,root)
        after=_inventory(root);allowed={upgrade['file_map'][p] for p in guard['save_files']}
        if set(saved)!=set(guard['save_files']) or set(after)!=set(before_manifest) or set(after_names)!=set(guard['node_ids']):
            raise ValueError('Naming repair save/instance inventory differs')
        if any(after[name]!=record for name,record in before_manifest.items() if name not in allowed):
            raise ValueError('Naming repair changed a Part outside its five definition owners')
        return {'status':'INSTANCE_NAMES_REPAIRED_PENDING_FRESH_VERIFY','spec_sha256':upgrade['spec_sha256'],
                'saved_parts':sorted(saved),'before_parts':deepcopy(before_manifest),'after_parts':after,
                'unchanged_parts':len(after)-len(allowed),'before_instance_names':before_names,'instance_names':after_names,
                'source_bytes_unchanged':True,'construction_release':False}
    finally:
        if _inventory(guard['source'])!=upgrade['copy_evidence']['source_parts']:
            raise ValueError('Read-only original M01.2 source bytes changed during naming repair')


def repair_section_defaults(session,root,upgrade,verification_spec,before_manifest):
    """Suppress exactly four auxiliary occurrences in two SECTION DEFAULTs."""
    root=Path(root).resolve();guard=_instance_name_repair_guard(root,upgrade,verification_spec,before_manifest)
    if session.IsBatch is not True or list(session.Parts):
        raise ValueError('SECTION DEFAULT repair requires its own fresh empty batch session')
    from renovierung.k02.nx_build import save
    from renovierung.m01.inspection import _configure_load
    nodes={n['id']:n for n in upgrade['layout']['nodes']};saved=[];sections={}
    try:
        _configure_load(session,'FromDirectory',full=True)
        for sid in ('PS12','PS13'):
            section='SECTION_'+sid;filename=nodes[section]['file']
            part=_open(session,root,filename,upgrade['file_map'],True);occurrences=_section_occurrences(part)
            before=_section_default_snapshot(part,sid,upgrade,occurrences)
            aux=_suppress_section_default_auxiliaries(part,sid,upgrade,occurrences)
            if len(aux)!=2:raise ValueError('SECTION DEFAULT repair requires a selected regular study')
            save(part);saved.append(filename)
            sections[section]={'auxiliary_ids':aux,'before':before,
                               'after':_section_default_snapshot(part,sid,upgrade,occurrences)}
        _owned_parts(session,root);after=_inventory(root)
        result={'status':'SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY','spec_sha256':upgrade['spec_sha256'],
                'saved_parts':sorted(saved),'before_parts':deepcopy(before_manifest),'after_parts':after,
                'unchanged_parts':365,'sections':sections,'source_bytes_unchanged':True,'construction_release':False}
        validate_section_defaults_evidence(upgrade,result)
        return result
    finally:
        if _inventory(guard['source'])!=upgrade['copy_evidence']['source_parts']:
            raise ValueError('Read-only original M01.2 source bytes changed during SECTION DEFAULT repair')


def upgrade_master(session,new_flat_dir,spec):
    """Upgrade only a proven independent NEW flat copy; no source/leaf save.

    A successful return is mutation evidence, not fresh-open/model acceptance.
    The separate verifier must inspect all 60 states and the extended tree.
    """
    root=Path(new_flat_dir).resolve();source,copy=_copy_guard(root,spec)
    if session.IsBatch is not True or list(session.Parts):
        raise ValueError('Upgrade requires its own fresh empty batch session')
    import NXOpen
    from renovierung.k02.nx_build import save
    from renovierung.m01.display import components,read_attribute,set_blank
    from renovierung.m01.nx_journal import display_part
    from renovierung.m01.inspection import _configure_load
    layout=spec['layout'];base=spec['base_layout'];file_map=spec['file_map'];nodes={n['id']:n for n in layout['nodes']}
    _configure_load(session,'FromDirectory',full=True)
    saved=[];created=[]
    immutable={name:row for name,row in copy['copied_parts'].items() if name not in
               {spec['base_file_map'][p] for p in spec['mutable_base_files']}}
    immutable.update(copy['new_parts'])
    try:
        master=_open(session,root,layout['master'],file_map,True)
        if (read_attribute(master,'M01_PROJECT')!='M01' or
                read_attribute(master,'M01_STATE_CATALOG')!=spec['original_catalog']):
            raise ValueError('Copied original master identity/36-state catalog differs')
        field_parts={}
        for fid,update in spec['fields'].items():
            part=_open(session,root,update['container_file'],file_map)
            old=next(f for f in base['fields'] if f['id']==fid)
            if (read_attribute(part,'M01_NODE_ID')!=update['container_node_id'] or
                    read_attribute(part,'M01_FIELD_METADATA')!=old):
                raise ValueError('Copied original FIELD identity/metadata differs: '+fid)
            assembly=part.ComponentAssembly.RootComponent
            if assembly is not None and assembly.GetChildren():raise ValueError('Original annex FIELD is not empty')
            field_parts[fid]=part
            leaf=_open(session,root,update['leaf_file'],file_map)
            if (_hash(read_attribute(leaf,'ANBAU_FIELD_SPEC'))!=update['leaf_spec_sha256'] or
                    read_attribute(leaf,'ANBAU_CONSTRUCTION_RELEASE') is not False):
                raise ValueError('Prepared native annex leaf identity differs: '+fid)
            _refsets(leaf,{ref:update['leaf_body_counts'][role] for role,ref in update['leaf_refsets'].items()})
        site=_open(session,root,spec['site_contract']['file'],file_map)
        for key,value in spec['site_contract']['attributes'].items():
            if read_attribute(site,key)!=value:raise ValueError('Native annex site metadata differs: '+key)
        _refsets(site,{r['name']:r['body_count'] for r in spec['site_contract']['reference_sets'].values()})
        # No mutation above this point: all copied containers and new leaves are verified.
        for fid,update in spec['fields'].items():
            part=field_parts[fid];display_part(session,part)
            old=read_attribute(part,'M01_FIELD_METADATA')
            _replace_attribute(part,'ANBAU_PREVIOUS_FIELD_METADATA',old)
            _write_node(part,nodes[update['container_node_id']],update['metadata'])
            _field_note(part,update['metadata'],spec)
            for child in spec['new_nodes']:
                if child['parent']==update['container_node_id']:_add_child(session,part,root,child,file_map)
            _presentation(part,spec);save(part);saved.append(update['container_file'])
        section_arrangements={}
        for sid,default in spec['section_defaults'].items():
            section_node='SECTION_'+sid;part=_open(session,root,nodes[section_node]['file'],file_map,True)
            _write_node(part,nodes[section_node]);direct={}
            for child in part.ComponentAssembly.RootComponent.GetChildren():
                nid=read_attribute(child,'M01_NODE_ID')
                if nid not in default['field_node_ids']:raise ValueError('Unexpected annex section child')
                fid=read_attribute(child,'M01_FIELD_ID');_write_node(child,nodes[nid],spec['fields'][fid]['metadata'])
                set_blank(child,False);direct[nid]=child
            if set(direct)!=set(default['field_node_ids']):raise ValueError('Incomplete annex section FIELD inventory')
            section_arrangements[sid]=_arrangements(part,
                {default['master_arrangement']:set(),default['default_arrangement']:set(direct)-{default['selected_field_node_id']}},
                direct,default=default['default_arrangement'],template_name=default['master_arrangement'])
            _suppress_section_default_auxiliaries(part,sid,spec)
            _presentation(part,spec);save(part);saved.append(nodes[section_node]['file'])
        saved.extend(_persist_section_definitions(session,root,spec,nodes,section_arrangements,save))
        display_part(session,master)
        occurrences=components(master)
        if set(occurrences)!=set(nodes)-{'MASTER'}:raise ValueError('Extended master occurrence inventory differs')
        for nid,component in occurrences.items():
            row=nodes[nid]
            if nid.startswith('SECTION_PS1') and nid in {'SECTION_'+s for s in spec['section_defaults']}:
                sid=nid.removeprefix('SECTION_')
                if (read_attribute(component,'M01_NODE_METADATA')!=row or component.Name.casefold()!=row['name'].casefold()
                        or component.UsedArrangement.Name!=spec['section_defaults'][sid]['master_arrangement']):
                    raise ValueError('Saved SECTION parent definition differs in master: '+nid)
            if nid in {u['container_node_id'] for u in spec['fields'].values()}:
                fid=read_attribute(component,'M01_FIELD_ID');_write_node(component,row,spec['fields'][fid]['metadata'])
            elif nid in {n['id'] for n in spec['new_nodes']}:
                _write_node(component,row);_identity(component)
            set_blank(component,row['blank'])
        # Only controlled IDs are changed. Other old nodes retain their saved state.
        controlled=set().union(*(set(r['suppressed_ids']) for r in spec['states'].values()))
        controlled.update(n['id'] for n in nodes.values() if n['kind'] in ('field','role','context','annex_site','diagnostic'))
        controls={nid:occurrences[nid] for nid in sorted(controlled)}
        native_arrangements=_arrangements(master,{r['name']:set(r['suppressed_ids']) for r in spec['states'].values()},
                                           controls,default=spec['catalog'][base['default_state']])
        for key,value in {'M01_STATE_CATALOG':spec['catalog'],'M01_DEFAULT_STATE':base['default_state'],
                          'M01_PRESENTATION':spec['presentation'],'ANBAU_UPGRADE_SCHEMA':SCHEMA,
                          'ANBAU_UPGRADE_SPEC_SHA256':spec['spec_sha256'],'ANBAU_CONSTRUCTION_RELEASE':False}.items():
            _replace_attribute(master,key,value)
        _presentation(master,spec);save(master);saved.append(layout['master'])
        for row in spec['reviews']:
            if row['action']=='keep':continue
            path=mapfile(root,row['file'],file_map)
            if row['action']=='create':
                if path.exists():raise ValueError('New annex review wrapper already exists')
                wrapper=session.Parts.NewDisplay(str(path),NXOpen.Part.Units.Millimeters)
                matrix=NXOpen.Matrix3x3();matrix.Xx=matrix.Yy=matrix.Zz=1.
                child,status=wrapper.ComponentAssembly.AddComponent(str(mapfile(root,layout['master'],file_map)),
                    'Entire Part','M01_REVIEW_'+row['id'].replace('-','_'),NXOpen.Point3d(0.,0.,0.),matrix,-1)
                _status(status,row['id']);created.append(row['file'])
            else:
                wrapper=_open(session,root,row['file'],file_map,True)
                children=list(wrapper.ComponentAssembly.RootComponent.GetChildren())
                if len(children)!=1:raise ValueError('Existing section review must reference one master')
                child=children[0]
            _identity(child)
            if Path(child.Prototype.FullPath).resolve()!=mapfile(root,layout['master'],file_map):
                raise ValueError('Review wrapper references a foreign master')
            child.SetUsedArrangement(native_arrangements[spec['catalog'][row['state']]])
            for key,value in {'M01_REVIEW_SCOPE':'M01_REVIEW','M01_REVIEW_ID':row['id'],
                              'M01_REVIEW_STATE':row['state'],'ANBAU_CONSTRUCTION_RELEASE':False}.items():
                _replace_attribute(wrapper,key,value)
            _presentation(wrapper,spec);save(wrapper);saved.append(row['file'])
            # Avoid retaining 24 additional full master instances in memory.
            wrapper.Close(NXOpen.BasePart.CloseWholeTree.FalseValue,NXOpen.BasePart.CloseModified.CloseModified,None)
            display_part(session,master)
        master.ComponentAssembly.ActiveArrangement=native_arrangements[spec['catalog'][base['default_state']]]
        _owned_parts(session,root)
        after=_inventory(root)
        if set(after)!=set(file_map.values()):raise ValueError('Final extended flat inventory differs')
        if any(after[name]!=record for name,record in immutable.items()):
            raise ValueError('Upgrade changed an immutable copied basis/annex leaf')
        if set(saved)!=set(spec['mutable_base_files'])|{r['file'] for r in spec['reviews'] if r['action']=='create'}:
            raise ValueError('Unexpected target save set')
        return {'status':'UPGRADED_PENDING_FRESH_VERIFY','schema':SCHEMA,'spec_sha256':spec['spec_sha256'],
                'master':layout['master'],'saved_parts':sorted(saved),'created_wrappers':sorted(created),
                'catalog':spec['catalog'],'source_bytes_unchanged':True,'immutable_base_and_leaf_bytes_unchanged':True,
                'part_count':len(after),'construction_release':False}
    finally:
        if _inventory(source)!=copy['source_parts']:
            raise ValueError('Read-only original M01.2 source bytes changed during target upgrade')
