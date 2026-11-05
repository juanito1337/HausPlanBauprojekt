"""Small synthetic contracts only; no NX session or simulated native success."""
import copy
import hashlib
import importlib
import tempfile
from pathlib import Path
import unittest


I = [1,0,0,0,1,0,0,0,1]


def fixture():
    from renovierung.m01.inspection import build_review_index
    from renovierung.m01.delivery_paths import make_file_map
    def node(nid,parent,kind,file=None,**kw):
        return dict(id=nid,parent=parent,kind=kind,file=file or nid+'.prt',name=nid,
                    blank=False,reference_set='Entire Part',translation_mm=[0,0,0],rotation=I,**kw)
    nodes=[node('MASTER',None,'master'),node('HOUSE','MASTER','house'),
           node('HOUSE_KG_MAIN','HOUSE','building'),node('TERRAIN','MASTER','terrain'),
           node('ENVIRONMENT','MASTER','environment'),node('UTILITIES','MASTER','utilities'),
           node('SITE_CONTEXT','MASTER','site')]
    fields=[]
    for sid,fid,native in [('PS01','PS01-F01',True),('PS10','PS10-F01',False),('PS11','PS11-F01',False)]:
        nodes.extend([node('SECTION_'+sid,'MASTER','section'),node('FIELD_'+fid,'SECTION_'+sid,'field')])
        measure={r:{'body_count':1,'volume_m3':1.,'component_volumes_m3':[1.]} for r in
                 ('cut_soil','excavation','pile_main','pile_reserve')} if native else {}
        fields.append(dict(id=fid,sector_id=sid,node_id='FIELD_'+fid,native=native,
                           measurements=measure,study_file=fid+'_STUDY.prt'))
        if native:
            for role in measure:
                row=node('OLD_'+role,'FIELD_'+fid,'role',file=fid+'_STUDY.prt',role=role)
                row['blank']=role in ('excavation','pile_reserve');row['reference_set']='M01_'+role.upper()
                nodes.append(row)
    nodes.append(node('CONTEXT_000','MASTER','context'))
    base=dict(nodes=nodes,fields=fields,sections=[{'id':s} for s in ('PS01','PS10','PS11')],
              context={'groups':[dict(id='CONTEXT_000',file='CONTEXT_000.prt',body_count=1,
                                     component_volumes_m3=[.2],exclude_for=['PS01-F01'])]},
              master='MASTER.prt',default_state='PS01-F01',presentation={'scale':.1,'matrix':I,'origin_mm':[0,0,0]})
    base['review_masters']=build_review_index(base)
    layout=copy.deepcopy(base);new=[];prepared={};updates={}
    for fid,mode in [('PS10-F01','CONFLICT_DIAGNOSTIC'),('PS11-F01','STUDY')]:
        geometry={r:{'body_count':1,'volume_m3':1.,'component_volumes_m3':[1.]} for r in
                  ('cut_soil','excavation','pile_main','pile_reserve')}
        leaf={'id':fid,'mode':mode,'file':fid+('_STUDY.prt' if mode=='STUDY' else '_CONFLICT.prt'),
              'geometry':geometry,'construction_release':False,'field_sha256':'a'*64}
        prepared[fid]={'spec':leaf}
        if mode=='STUDY':
            for role in geometry:
                row=node('ANBAU_ROLE_'+fid+'_'+role.upper(),'FIELD_'+fid,'role',file=leaf['file'],role=role)
                row['blank']=role in ('excavation','pile_reserve');row['reference_set']='M01_'+role.upper();new.append(row)
            row=node('ANBAU_SITE_'+fid,'FIELD_'+fid,'annex_site',file='ANBAU_SITE.prt')
            row['reference_set']='ANBAU_SITE_PS11_F01';new.append(row)
        else:
            row=node('ANBAU_CONFLICT_'+fid,'FIELD_'+fid,'diagnostic',file=leaf['file'],role='conflict')
            row['reference_set']='ANBAU_CONFLICT';new.append(row)
        updates[fid]={'container_node_id':'FIELD_'+fid,'container_file':'FIELD_'+fid+'.prt','native':mode=='STUDY',
                      'diagnostic':mode!='STUDY','leaf_file':leaf['file'],'metadata':{},'child_ids':[n['id'] for n in new if n['parent']=='FIELD_'+fid]}
    layout['nodes'].extend(new)
    reviews=copy.deepcopy(base['review_masters'])
    for row in reviews:
        if row['id'] in ('PS10','PS11'):row['state']=row['id']+'-F01'
    reviews.extend({'id':f,'file':'Bauabschnitte/'+f.split('-')[0]+'/'+f+'.prt','state':f} for f in prepared)
    layout['review_masters']=reviews
    site={'file':'ANBAU_SITE.prt','entry_sha256':'b'*64,'body_count':1,'shells':[{'id':'S1'}],
          'reference_sets':{'PS11-F01':{'name':'ANBAU_SITE_PS11_F01','shell_ids':['S1'],'body_count':1}}}
    oldmap=make_file_map(base);filemap=make_file_map(layout)
    mutable={base['master']}|{'FIELD_'+f+'.prt' for f in prepared}|{'SECTION_'+s+'.prt' for s in ('PS10','PS11')}|{r['file'] for r in reviews if r['id'] in ('PS10','PS11')}
    upgrade=dict(schema='ANBAU_M01_UPGRADE_SPEC_V1',base_layout=base,layout=layout,base_file_map=oldmap,
                 file_map=filemap,fields=updates,new_nodes=new,reviews=reviews,mutable_base_files=sorted(mutable),
                 new_leaf_files=sorted([p['spec']['file'] for p in prepared.values()]+['ANBAU_SITE.prt']))
    baseline={name:{'bytes':len(name),'sha256':hashlib.sha256(name.encode()).hexdigest()} for name in oldmap.values()}
    return upgrade,{'fields':prepared},site,baseline


def register_fixture(section='PS02'):
    from renovierung.m01.delivery_paths import make_file_map
    from renovierung.m01.inspection import build_review_index
    args=fixture();upgrade=args[0];fid=section+('-F02' if section=='PS01' else '-F01')
    def node(nid,parent,kind):return dict(id=nid,parent=parent,kind=kind,file=nid+'.prt',name=nid,
        blank=False,reference_set='Entire Part',translation_mm=[0,0,0],rotation=I)
    is_new=section not in {s['id'] for s in upgrade['base_layout']['sections']}
    field=dict(id=fid,sector_id=section,node_id='FIELD_'+fid,native=False,measurements={})
    for layout in (upgrade['base_layout'],upgrade['layout']):
        if is_new:
            layout['sections'].append({'id':section});layout['nodes'].append(node('SECTION_'+section,'MASTER','section'))
        layout['fields'].append(copy.deepcopy(field));layout['nodes'].append(node(field['node_id'],'SECTION_'+section,'field'))
    upgrade['base_layout']['review_masters']=build_review_index(upgrade['base_layout'])
    if is_new:
        row=next(r for r in upgrade['base_layout']['review_masters'] if r['id']==section)
        upgrade['reviews'].append(copy.deepcopy(row))
        if upgrade['layout']['review_masters'] is not upgrade['reviews']:upgrade['layout']['review_masters'].append(copy.deepcopy(row))
    upgrade['base_file_map']=make_file_map(upgrade['base_layout']);upgrade['file_map']=make_file_map(upgrade['layout'])
    for name in upgrade['base_file_map'].values():args[3].setdefault(name,{'bytes':len(name),'sha256':hashlib.sha256(name.encode()).hexdigest()})
    return args


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.m=importlib.import_module('renovierung.anbau.verification')
        self.args=fixture();self.spec=self.m.verification_spec(*self.args)

    def test_independent_old_new_state_and_entry_coverage(self):
        s=self.spec
        self.assertEqual(len(s['states']),7)
        self.assertEqual(len(s['reviews']),6)
        self.assertEqual(len(s['entries']),13)
        self.assertEqual(s['states']['PS11-F01']['body_counts']['ANBAU_SITE_PS11-F01'],1)
        self.assertEqual(s['states']['PS11-F01']['visible_field_ids'],['PS11-F01'])
        self.assertEqual(s['states']['PS10-F01']['body_counts']['ANBAU_CONFLICT_PS10-F01'],1)
        self.assertIsNone(s['states']['PS10-F01']['site'])
        for sid in ('BASE','PS01','PS01-F01','PS10','PS11'):
            self.assertTrue(set(n['id'] for n in self.args[0]['new_nodes'])<=set(s['states'][sid]['suppressed_ids']))

    def test_builder_state_table_cannot_replace_independent_expectations(self):
        args=copy.deepcopy(self.args);args[0]['states']={'BASE':{'suppressed_ids':[]}}
        with self.assertRaises(ValueError):self.m.verification_spec(*args)

    def test_immutable_house_and_transform_exemptions_are_rejected(self):
        for mutation in ('mutable_house','move_house','remove_baseline','changed_node_id','wrong_refset'):
            args=copy.deepcopy(self.args)
            if mutation=='mutable_house':args[0]['mutable_base_files'].append('HOUSE.prt')
            if mutation=='move_house':next(n for n in args[0]['layout']['nodes'] if n['id']=='HOUSE')['translation_mm'][2]=1
            if mutation=='remove_baseline':args[3].pop('HOUSE.prt')
            if mutation=='changed_node_id':args[0]['new_nodes'][0]['id']='UNEXPECTED'
            if mutation=='wrong_refset':next(n for n in args[0]['layout']['nodes'] if n['kind']=='annex_site')['reference_set']='Entire Part'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.m.verification_spec(*args)

    def test_section_default_is_single_selected_annex_and_diagnostic_has_no_site(self):
        rows={r['id']:r for r in self.spec['entries']}
        self.assertEqual(rows['SECTION_PS11']['visibility']['visible_field_ids'],['PS11-F01'])
        self.assertEqual(rows['FIELD_PS10-F01']['visibility']['visible_field_ids'],['PS10-F01'])
        self.assertFalse(any(rows['FIELD_PS10-F01']['visibility']['visible_role_bodies'].values()))
        self.assertIsNone(rows['FIELD_PS10-F01']['visibility']['site'])

    def test_visibility_rejects_wrong_shells_markers_counts_and_duplicate_ids(self):
        expected=self.spec['states']['PS11-F01']
        actual={k:copy.deepcopy(expected[k]) for k in self.m.VISIBILITY_KEYS}
        self.m.validate_visibility(expected,actual)
        for key,value in [('body_counts',{**actual['body_counts'],'ANBAU_SITE_PS11-F01':0}),
                          ('visible_site_shell_ids',['WRONG']),('visible_field_ids',[]),
                          ('visible_context_ids',['CONTEXT_000','CONTEXT_000'])]:
            bad=copy.deepcopy(actual);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.m.validate_visibility(expected,bad)

    def test_camera_and_semantic_layer_240_are_required(self):
        from renovierung.m01.presentation import DISPLAY_LAYERS
        p={'camera':{'scale':.1,'matrix':I,'absolute_origin_mm':[0,0,0]},'shaded_with_edges':True,
           'layers':{str(i):{'visible':True,'selectable':True,'hidden':False} for i in (*DISPLAY_LAYERS,240)}}
        self.m.validate_presentation(p,self.spec['presentation'])
        for key in ('camera','240','rawenum'):
            bad=copy.deepcopy(p)
            if key=='camera':bad['camera']['absolute_origin_mm'][2]=1
            elif key=='240':bad['layers']['240']['hidden']=True
            else:bad['layers']['240']=1
            with self.subTest(key=key),self.assertRaises((ValueError,TypeError)):
                self.m.validate_presentation(bad,self.spec['presentation'])

    def test_file_gate_detects_missing_extra_changed_bytes_without_nx(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in self.spec['file_map'].values():(root/name).write_text(name)
            before=self.m.inspect_files(root,self.spec)
            self.assertEqual(len(before),len(self.spec['file_map']))
            (root/'HOUSE.prt').write_text('changed')
            with self.assertRaises(ValueError):self.m.inspect_files(root,self.spec)
            (root/'HOUSE.prt').write_text('HOUSE.prt');(root/'FOREIGN.prt').write_text('x')
            with self.assertRaises(ValueError):self.m.inspect_files(root,self.spec)

    def test_default_display_proxy_is_not_promoted_to_exact_brep_success(self):
        row=next(r for r in self.spec['entries'] if r['id']=='PS11-F01')
        snapshot={'native_visible_object_count':2,'visible_node_ids':['FIELD_PS11-F01'],
                  'visible_marker_ids':[],'visible_marker_proxy_ids':['PS11-F01'],
                  'unclassified_geometry_objects':0,'exact_brep_body_counts_verified':False}
        self.m.validate_default_snapshot(row,snapshot)
        for key,value in [('visible_node_ids',['HOUSE']),('native_visible_object_count',0),
                          ('exact_brep_body_counts_verified',True)]:
            bad=copy.deepcopy(snapshot);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.m.validate_default_snapshot(row,bad)


    def test_source_study_cannot_remain_free_inside_required_parcel_edge_strip(self):
        args=copy.deepcopy(self.args)
        args[0]['base_layout']['context']['boundary_xyz_mm']=[[0,0,0],[1000,0,0],[1000,1000,0],[0,1000,0]]
        args[1]['fields']['PS11-F01']['spec']['field_metadata']={
            'uncertainty_coverage_hull_xy_mm':[[100,100],[200,100],[200,200],[100,200]]}
        with self.assertRaises(ValueError):self.m.verification_spec(*args)

    def test_incomplete_full_or_default_summaries_fail_closed(self):
        self.assertTrue(self.m.validate_full_evidence(self.spec,{}))
        self.assertTrue(self.m.validate_default_evidence(self.spec,{}))

    def test_native_scope_node_count_follows_independently_derived_study_diagnostic_ratio(self):
        with tempfile.TemporaryDirectory() as folder:
            destination=Path(folder)/'delivery';source=Path(folder)/'source'
            for native_count in (9,10,13):
                # Pure guard input, never a claim that native cloning occurred.
                specs={f'PS11-F{i:02}':{'spec':{'mode':'STUDY' if i<=13 else 'CONFLICT_DIAGNOSTIC'}} for i in range(1,25)}
                declines={f'PS11-F{i:02}':100. for i in range(native_count+1,14)}
                spec={'counts':dict(nodes=349+5*native_count+(24-native_count),old_nodes=349,
                                    parts=367,states=60,reviews=59,entries=145),
                      'prepared_fields':specs,'derived_risk_declines_mm':declines,
                      'base_layout':{'context':{'groups':[{} for _ in range(83)]}},
                      'copy_evidence':{'source_root':str(source),'destination_root':str(destination)},
                      'new_leaf_bytes':{f'LEAF_{i}.prt':{} for i in range(25)}}
                spec['spec_sha256']=self.m._hash(spec)
                with self.subTest(native_count=native_count):
                    self.m._native_spec(destination.resolve(),spec,moved=False)
                    bad=copy.deepcopy(spec);bad['counts']['nodes']+=4
                    bad['spec_sha256']=self.m._hash({k:v for k,v in bad.items() if k!='spec_sha256'})
                    with self.assertRaises(ValueError):self.m._native_spec(destination.resolve(),bad,moved=False)

    def test_section_instance_definition_owner_is_the_only_additional_mutable_part(self):
        from renovierung.m01.delivery_paths import make_file_map
        args=copy.deepcopy(self.args);upgrade=args[0]
        construction=dict(id='CONSTRUCTION',parent='MASTER',kind='assembly',file='CONSTRUCTION.prt',name='CONSTRUCTION',
                          blank=False,reference_set='Entire Part',translation_mm=[0,0,0],rotation=I)
        for layout in (upgrade['base_layout'],upgrade['layout']):
            layout['nodes'].append(copy.deepcopy(construction))
            for node in layout['nodes']:
                if node['id'].startswith('SECTION_'):node['parent']='CONSTRUCTION'
        upgrade['base_file_map']=make_file_map(upgrade['base_layout']);upgrade['file_map']=make_file_map(upgrade['layout'])
        args[3]['CONSTRUCTION.prt']={'bytes':16,'sha256':'c'*64}
        upgrade['mutable_base_files'].append('CONSTRUCTION.prt')
        accepted=self.m.verification_spec(*args)
        self.assertNotIn('CONSTRUCTION.prt',accepted['immutable_parts'])
        upgrade['mutable_base_files'].remove('CONSTRUCTION.prt')
        with self.assertRaises(ValueError):self.m.verification_spec(*args)

    def test_diagnostic_definition_style_is_distinct_from_nested_context_properties(self):
        node={'layer':240,'color':186,'source_body_layer':102}
        definition={'layer':240,'color':186,'layer_option':240}
        self.m.validate_diagnostic_definition_style(node,definition)
        for key,value in [('layer',1),('color',134),('layer_option',-1)]:
            wrong={**definition,key:value}
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.m.validate_diagnostic_definition_style(node,wrong)

    def test_visible_diagnostic_brep_colors_source_layers_and_exact_body_ids_are_required(self):
        spec=copy.deepcopy(self.spec);fid='PS10-F01';nid='ANBAU_CONFLICT_'+fid
        node=next(n for n in spec['layout']['nodes'] if n['id']==nid)
        node.update(layer=240,color=186,source_body_layer=240)
        record={'body_name':'ANBAU_CONFLICT_EXCAVATION_00','color':186,'layer':240,
                'prototype_color':186,'prototype_layer':240,'component_layer_option':-1,'effective_geometry_layer':240}
        self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[record]})
        for key,value in [('color',134),('layer',1),('prototype_layer',102),('body_name','K02_PILE_MAIN_00'),
                          ('component_layer_option',17),('effective_geometry_layer',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[{**record,key:value}]})
        with self.assertRaises(ValueError):self.m.validate_diagnostic_display(spec,spec['states'][fid],{})
        with self.assertRaises(ValueError):self.m.validate_diagnostic_display(spec,spec['states']['BASE'],{nid:[record]})
        # Native probe2: downgraded STUDY source uses102; stored definition240,
        # nested option-1 and visible Body186/102 are simultaneously correct.
        node['source_body_layer']=102;node['reference_set']='M01_EXCAVATION'
        record.update(body_name='K02_EXCAVATION_00',layer=102,prototype_layer=102,effective_geometry_layer=102)
        self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[record]})
        # Native standalone probe: the very same source102 has visible layer240
        # when the FIELD definition's component geometry override240 applies.
        record.update(component_layer_option=240,layer=240,effective_geometry_layer=240)
        self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[record]})
        for key,value in [('layer',102),('prototype_layer',240),('effective_geometry_layer',102)]:
            with self.subTest(standalone_wrong=key),self.assertRaises(ValueError):
                self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[{**record,key:value}]})
        record.update(component_layer_option=-1,effective_geometry_layer=102)
        with self.assertRaises(ValueError):
            self.m.validate_diagnostic_display(spec,spec['states'][fid],{nid:[record]})

    def test_authoritative_instance_name_cannot_be_replaced_by_context_or_display_alias(self):
        node={'name':'PS12-F01_ANBAU_STUDIE','reference_set':'Entire Part'}
        actual={'instance_name':node['name'],'custom_occurrence_name':'FELD_PS12-F01_GESPERRT_REGISTER',
                'definition_custom_name':node['name'],'reference_set':'Entire Part',
                'definition_inspection_performed':True,'definition_inspection_scope':'full'}
        self.m.validate_instance_name(node,actual)
        # Existing M01 names compare case-insensitively; NX can uppercase them.
        self.m.validate_instance_name(node,{**actual,'instance_name':node['name'].lower()})
        for key,value in [('instance_name','FELD_PS12-F01_GESPERRT_REGISTER'),('instance_name',None),
                          ('reference_set','Empty'),('definition_custom_name','FELD_PS12-F01_GESPERRT_REGISTER')]:
            wrong={**actual,key:value,'custom_occurrence_name':node['name'],'display_name':node['name']}
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                self.m.validate_instance_name(node,wrong)

    def test_failure_evidence_retains_completed_observations_without_becoming_acceptance(self):
        observed={'states':{'BASE':{'native_observation':'retained'}},'public_selections':{},
                  'reviews':{'PS01':{'file':'PS01.prt'}},'standalone':{},
                  'context_measurements':{'CONTEXT_000':{'body_count':1}},
                  'byte_guards':{'target_parts_unchanged':None,'original_source_unchanged':None}}
        phase={'kind':'subassembly','id':'SECTION_PS12','operation':'native_graph'}
        evidence=self.m.failure_evidence(observed,self.spec,phase)
        error=self.m.NativeVerificationFailure('wrong auxiliary visibility',evidence)
        self.assertIs(error.evidence['states'],observed['states'])
        self.assertEqual(error.evidence['failed_phase'],phase)
        self.assertEqual(error.evidence['completed_scope_counts']['states'],1)
        self.assertEqual(error.evidence['completed_scope_counts']['reviews'],1)
        self.assertEqual(error.evidence['completed_scope_counts']['context_measurements'],1)
        self.assertEqual(error.evidence['status'],'FAIL')
        self.assertTrue(error.evidence['partial_evidence_only'])
        self.assertEqual(error.evidence['verification_spec_sha256'],self.spec['spec_sha256'])
        observed['byte_guards']['target_parts_unchanged']=True
        self.assertTrue(error.evidence['byte_guards']['target_parts_unchanged'])
        # Even all scopes being present later could never turn this failure
        # envelope into a successful delivery through either pure final gate.
        with self.assertRaisesRegex(ValueError,'Partial'):
            self.m._recorded_manifest(self.spec,error.evidence)
        self.assertTrue(self.m.validate_full_evidence(self.spec,error.evidence))
        self.assertTrue(self.m.validate_default_evidence(self.spec,error.evidence))

    def test_section_smoke_scope_is_exactly_two_named_cold_entries_and_never_release(self):
        def rename(value):
            if isinstance(value,str):return value.replace('PS10','PS12').replace('PS11','PS13')
            if isinstance(value,dict):return {rename(k):rename(v) for k,v in value.items()}
            if isinstance(value,(list,tuple)):return [rename(v) for v in value]
            return value
        spec=self.m.verification_spec(*rename(self.args))
        entries=self.m.section_smoke_entries(spec)
        self.assertEqual([r['id'] for r in entries],['SECTION_PS12','SECTION_PS13'])
        broken=copy.deepcopy(spec);broken['entries'].append(copy.deepcopy(entries[0]))
        with self.assertRaises(ValueError):self.m.section_smoke_entries(broken)
        self.assertTrue(self.m.validate_section_smoke_evidence(spec,{}))
        with self.assertRaises(ValueError):
            self.m.smoke_sections(type('NonBatch',(),{'IsBatch':False,'Parts':[]})(),Path('.'),spec)

    def test_owned_batch_search_isolation_requires_empty_readback_and_unchanged_active_profile(self):
        profile={'requested_component_load_method':'FromDirectory','component_load_method_matches_requested':True,
                 'component_load_method':'native-enum-string','part_load_option':'native-minimal-enum-string',
                 'minimal_display_profile_verified':True,'components_to_load':'native-component-option',
                 'use_partial_loading':True,'use_lightweight_representations':True}
        record={'before_search_directories':[['C:/inactive/configured/path'],[True]],
                'after_search_directories':[[],[]],'before_profile':profile,'after_profile':copy.deepcopy(profile),
                'active_profile_unchanged':True,'owned_batch_only':True,'settings_saved':False}
        self.m.validate_search_directory_isolation(record)
        for key,value in [('after_search_directories',[['C:/still/configured'],[False]]),
                          ('active_profile_unchanged',False),('owned_batch_only',False),('settings_saved',True)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.m.validate_search_directory_isolation({**record,key:value})
        changed=copy.deepcopy(record);changed['after_profile']['component_load_method_matches_requested']=False
        with self.assertRaises(ValueError):self.m.validate_search_directory_isolation(changed)
        changed=copy.deepcopy(record);changed['before_search_directories'][1]=[]
        with self.assertRaises(ValueError):self.m.validate_search_directory_isolation(changed)

    def test_partial_profile_never_calls_prototype_definition_reader_or_claims_full_proof(self):
        node={'name':'PS12-F01_ANBAU_STUDIE','reference_set':'Entire Part'}
        raw={'instance_name':node['name'],'custom_occurrence_name':'old context alias','reference_set':'Entire Part'}
        def forbidden_reader():raise AssertionError('A normal partial inspection must not read the prototype definition')
        partial=self.m.component_identity_evidence(node,raw,full=False,read_definition_name=forbidden_reader)
        self.assertFalse(partial['definition_inspection_performed'])
        self.assertEqual(partial['definition_inspection_scope'],'normal_partial')
        self.assertNotIn('definition_custom_name',partial)
        self.m.validate_instance_name(node,partial,definition_required=False)
        with self.assertRaises(ValueError):self.m.validate_instance_name(node,partial)
        for extra in ({'definition_custom_name':node['name']},{'diagnostic_style':{}},
                      {'definition_inspection_performed':True}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                self.m.validate_instance_name(node,{**partial,**extra},definition_required=False)
        calls=[]
        full=self.m.component_identity_evidence(node,raw,full=True,read_definition_name=lambda:(calls.append(True) or node['name']))
        self.assertEqual(calls,[True]);self.m.validate_instance_name(node,full)

    def test_normal_definition_evidence_is_bound_to_same_spec_and_part_bytes(self):
        manifest={name:{'bytes':1,'sha256':'a'*64} for name in self.spec['file_map'].values()}
        record={'definition_inspection_performed':False,'definition_inspection_scope':'normal_partial',
                'full_definition_evidence_required':True,
                'full_definition_binding':{'verification_spec_sha256':self.spec['spec_sha256'],
                                           'part_manifest_sha256':self.m._hash(manifest)}}
        self.m.validate_default_definition_binding(self.spec,record,manifest)
        for key,value in [('definition_inspection_performed',True),('full_definition_evidence_required',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                self.m.validate_default_definition_binding(self.spec,{**record,key:value},manifest)
        bad=copy.deepcopy(record);bad['full_definition_binding']['part_manifest_sha256']='0'*64
        with self.assertRaises(ValueError):self.m.validate_default_definition_binding(self.spec,bad,manifest)

    def test_register_only_classification_excludes_annex_studies_diagnostics_and_any_children(self):
        spec=self.m.verification_spec(*register_fixture())
        self.assertEqual(self.m.register_only_marker_ids(spec),{'PS02-F01'})
        spec['layout']['nodes'].append({'id':'UNEXPECTED_CHILD','parent':'FIELD_PS02-F01','kind':'curve'})
        self.assertEqual(self.m.register_only_marker_ids(spec),set())

    def test_old_register_marker_limit_requires_current_unhidden_graph_and_full_marker_binding(self):
        spec=self.m.verification_spec(*register_fixture());entry=next(e for e in spec['entries'] if e['id']=='PS02')
        scene={'native_visible_object_count':2,'exact_brep_body_counts_verified':False,
               'visible_node_ids':['HOUSE','CONTEXT_000'],'visible_marker_ids':[],'visible_marker_proxy_ids':[]}
        graph={'FIELD_PS02-F01':{'parent':'SECTION_PS02','file':'FIELD_PS02-F01.prt','reference_set':'Entire Part','effective_hidden':False}}
        manifest={name:{'bytes':1,'sha256':'a'*64} for name in spec['file_map'].values()}
        limit=self.m.register_marker_limitation(spec,entry,scene,graph,manifest)
        self.assertEqual(limit['missing_marker_ids'],['PS02-F01'])
        self.assertFalse(limit['markers_observed_in_minimal_scene'])
        self.assertTrue(limit['full_marker_evidence_required'])
        self.assertEqual(limit['full_marker_binding']['part_manifest_sha256'],self.m._hash(manifest))
        for bad in ({},{'FIELD_PS02-F01':{**graph['FIELD_PS02-F01'],'effective_hidden':True}}):
            with self.subTest(graph=bad),self.assertRaises(ValueError):self.m.register_marker_limitation(spec,entry,scene,bad,manifest)
        with self.assertRaises(ValueError):self.m.validate_default_snapshot(entry,{**scene,'visible_marker_ids':['PS02-F99']},spec=spec)
        strict={k:copy.deepcopy(entry['visibility'][k]) for k in self.m.VISIBILITY_KEYS};strict['visible_field_ids']=[]
        with self.assertRaises(ValueError):self.m.validate_visibility(entry['visibility'],strict)

    def test_empty_scene_limit_is_only_pure_old_register_section_and_direct_field_stays_strict(self):
        spec=self.m.verification_spec(*register_fixture());entries={e['id']:e for e in spec['entries']}
        empty={'native_visible_object_count':0,'exact_brep_body_counts_verified':False,'visible_node_ids':[],
               'visible_marker_ids':[],'visible_marker_proxy_ids':[]}
        self.m.validate_default_snapshot(entries['SECTION_PS02'],empty,spec=spec)
        for eid in ('PS02','FIELD_PS02-F01','PS11-F01','PS10-F01'):
            with self.subTest(eid=eid),self.assertRaises(ValueError):self.m.validate_default_snapshot(entries[eid],empty,spec=spec)

    def test_mixed_section_can_omit_only_its_old_register_companion_never_the_native_study_marker(self):
        spec=self.m.verification_spec(*register_fixture('PS01'));entry=next(e for e in spec['entries'] if e['id']=='SECTION_PS01')
        scene={'native_visible_object_count':3,'exact_brep_body_counts_verified':False,
               'visible_node_ids':['OLD_cut_soil','OLD_pile_main','FIELD_PS01-F01'],
               'visible_marker_ids':[],'visible_marker_proxy_ids':['PS01-F01']}
        self.m.validate_default_snapshot(entry,scene,spec=spec)
        with self.assertRaises(ValueError):self.m.validate_default_snapshot(entry,{**scene,'visible_marker_proxy_ids':[]},spec=spec)
        self.assertEqual(entry['visibility']['visible_field_ids'],['PS01-F01','PS01-F02'])


if __name__=='__main__':unittest.main()
