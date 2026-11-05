"""Declarative upgrade/path protection tests; no NX execution evidence."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


class NodeAttributeTests(unittest.TestCase):
    def test_section_default_fix_only_suppresses_auxiliaries_in_default_arrangement(self):
        from renovierung.anbau import integration as m
        sid='PS12';fid='PS12-F01';field='FIELD_'+fid
        ids=['ANBAU_ROLE_'+fid+'_'+r for r in ('EXCAVATION','PILE_RESERVE')]
        spec={'section_defaults':{sid:{'state':fid}},'fields':{fid:{'native':True,'container_node_id':field}},
              'layout':{'nodes':[{'id':nid,'parent':field} for nid in ids]}}
        master=types.SimpleNamespace(Name='ANBAU_SECTION_MASTER_PS12')
        default=types.SimpleNamespace(Name='ANBAU_SECTION_DEFAULT_PS12');calls=[]
        def suppress(objects,arrangements):
            calls.append((objects,arrangements));return types.SimpleNamespace(Length=0,Dispose=lambda:None)
        assembly=types.SimpleNamespace(Arrangements=[master,default],ActiveArrangement=default,SuppressComponents=suppress)
        part=types.SimpleNamespace(ComponentAssembly=assembly);occurrences={nid:object() for nid in ids}
        self.assertEqual(m._suppress_section_default_auxiliaries(part,sid,spec,occurrences),ids)
        self.assertEqual(calls,[([occurrences[nid] for nid in ids],[default])])
        self.assertIs(assembly.ActiveArrangement,default)

    def test_section_default_evidence_rejects_any_master_node_view_or_unrelated_change(self):
        from renovierung.anbau import integration as m
        nodes=[];fields={};defaults={};sections={}
        for sid in ('PS12','PS13'):
            fid=sid+'-F01';field='FIELD_'+fid;defaults[sid]=fid;fields[fid]={'native':True,'container_node_id':field}
            section='SECTION_'+sid
            rows=[{'id':section,'parent':'CONSTRUCTION','file':section+'.prt','name':section}]
            rows.append({'id':field,'parent':section,'file':field+'.prt','name':field})
            rows.extend({'id':'ANBAU_ROLE_'+fid+'_'+r,'parent':field,'file':fid+'.prt','name':r}
                        for r in ('CUT_SOIL','EXCAVATION','PILE_MAIN','PILE_RESERVE'))
            rows.append({'id':'ANBAU_SITE_'+fid,'parent':field,'file':'ANBAU_SITE.prt','name':'SITE'})
            for row in rows:row.update(reference_set='Entire Part',translation_mm=[0,0,0],rotation=[1,0,0,0,1,0,0,0,1])
            nodes.extend(rows);aux=['ANBAU_ROLE_'+fid+'_'+r for r in ('EXCAVATION','PILE_RESERVE')]
            records={row['id']:{'parent_id':row['parent'],'owner_file':next(p['file'] for p in rows if p['id']==row['parent']),
                     'instance_name':row['name'],'custom_name':row['name'],'reference_set':row['reference_set'],
                     'translation_mm':row['translation_mm'],'rotation':row['rotation'],'used_arrangement':None,
                     'metadata_sha256':m._hash(row)} for row in rows[1:]}
            states={nid:{'native_state':'UnSuppressed','controlled':True,'suppressed':False} for nid in records}
            before={'active_arrangement':'ANBAU_SECTION_DEFAULT_'+sid,'saved_default_arrangement':'ANBAU_SECTION_DEFAULT_'+sid,
                    'presentation':{'camera':'fixed','layers':'fixed'},'nodes':records,
                    'master_states':copy.deepcopy(states),'default_states':states}
            after=copy.deepcopy(before)
            for nid in aux:after['default_states'][nid]={'native_state':'Suppressed','controlled':True,'suppressed':True}
            sections[section]={'auxiliary_ids':aux,'before':before,'after':after}
        names=['SECTION_PS12.prt','SECTION_PS13.prt']+['P%03d.prt'%i for i in range(365)]
        spec={'layout':{'nodes':nodes},'fields':fields,'section_defaults':defaults,
              'file_map':{name:name for name in names},'upgrade_attributes':{'spec_sha256':'a'*64}}
        parts={name:{'bytes':1,'sha256':'b'*64} for name in names}
        record={'status':'SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY','spec_sha256':'a'*64,
                'saved_parts':names[:2],'before_parts':parts,'after_parts':copy.deepcopy(parts),
                'unchanged_parts':365,'source_bytes_unchanged':True,'construction_release':False,'sections':sections}
        m.validate_section_defaults_evidence(spec,record)
        selected='FIELD_PS12-F01';aux=sections['SECTION_PS12']['auxiliary_ids'][0]
        for mutation in ('master','node','view','field_default','aux','other_bytes','missing_used'):
            changed=copy.deepcopy(record);after=changed['sections']['SECTION_PS12']['after']
            if mutation=='master':after['master_states'][selected]['suppressed']=True
            if mutation=='node':after['nodes'][selected]['translation_mm'][0]=1
            if mutation=='view':after['presentation']['camera']='changed'
            if mutation=='field_default':after['default_states'][selected]['controlled']=False
            if mutation=='aux':after['default_states'][aux]['controlled']=False
            if mutation=='other_bytes':changed['after_parts'][names[-1]]['sha256']='c'*64
            if mutation=='missing_used':
                changed['sections']['SECTION_PS12']['before']['nodes'][selected].pop('used_arrangement')
                after['nodes'][selected].pop('used_arrangement')
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):m.validate_section_defaults_evidence(spec,changed)

    def test_naming_record_binds_full_metadata_transform_refset_and_used_arrangement(self):
        from renovierung.anbau import integration as m
        from renovierung.m01 import display
        row={'id':'SECTION_PS10','name':'Sektion_PS10_DIAGNOSE','reference_set':'Entire Part',
             'translation_mm':[0,0,0],'rotation':[1,0,0,0,1,0,0,0,1]}
        matrix=types.SimpleNamespace(**dict(zip(('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz'),row['rotation'])))
        point=types.SimpleNamespace(X=0.,Y=0.,Z=0.)
        child=types.SimpleNamespace(Name=row['name'].upper(),ReferenceSet='Entire Part',
            UsedArrangement=types.SimpleNamespace(Name='ANBAU_SECTION_MASTER_PS10'),GetPosition=lambda:(point,matrix))
        with patch.object(display,'read_attribute',return_value=row), \
                patch.object(m,'_component_instance_name',return_value='OLD_REGISTER'):
            actual=m._instance_name_record(child,row,'CONSTRUCTION','CONSTRUCTION.prt')
            self.assertEqual(actual,{'parent_id':'CONSTRUCTION','owner_file':'CONSTRUCTION.prt',
                'instance_name':'OLD_REGISTER','custom_name':row['name'].upper(),'reference_set':'Entire Part',
                'translation_mm':[0.,0.,0.],'rotation':row['rotation'],
                'used_arrangement':'ANBAU_SECTION_MASTER_PS10','metadata_sha256':m._hash(row)})
            for value in (1.,float('nan')):
                point.X=value
                with self.subTest(position=value),self.assertRaises(ValueError):
                    m._instance_name_record(child,row,'CONSTRUCTION','CONSTRUCTION.prt')
            point.X=0.;child.ReferenceSet='WRONG'
            with self.assertRaises(ValueError):m._instance_name_record(child,row,'CONSTRUCTION','CONSTRUCTION.prt')

    def test_repair_requires_exact_unpublished_candidate_and_only_owner_save_delta(self):
        from renovierung.anbau import integration as m
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary);source=directory/'source';target=directory/'candidate'
            source.mkdir();target.mkdir()
            names=['MASTER.prt','CONSTRUCTION.prt']+['P%03d.prt'%i for i in range(316)]
            base_map={name:name for name in names}
            new_names=['LEAF%02d.prt'%i for i in range(25)]
            wrappers=['VIEW%02d.prt'%i for i in range(24)]
            for name in names:(source/name).write_bytes(b'original');(target/name).write_bytes(b'clone')
            copied=m._inventory(target)
            for name in new_names+wrappers:(target/name).write_bytes(b'new fixture')
            before=m._inventory(target);old_mutable=[names[0]]+names[2:34]
            nodes=[{'id':'MASTER','file':'MASTER.prt'}, {'id':'CONSTRUCTION','file':'CONSTRUCTION.prt'}]
            nodes.extend({'id':'SECTION_'+sid,'parent':'CONSTRUCTION','file':'P%03d.prt'%i}
                         for i,sid in enumerate(('PS10','PS11','PS12','PS13')))
            spec={'schema':m.SCHEMA,'base_layout':{'fixture':True},'layout':{'nodes':nodes},
                  'base_file_map':base_map,'file_map':{name:name for name in names+new_names+wrappers},
                  'section_defaults':{sid:{} for sid in ('PS10','PS11','PS12','PS13')},
                  'mutable_base_files':sorted(old_mutable+['CONSTRUCTION.prt'])}
            spec['base_layout_sha256']=m._hash(spec['base_layout'])
            spec['copy_evidence']={'schema':'ANBAU_M01_INDEPENDENT_COPY_V1','source_root':str(source),
                'destination_root':str(target),'native_clone_completed':True,'native_independent':True,
                'base_layout_sha256':spec['base_layout_sha256'],'source_parts':m._inventory(source),
                'copied_parts':copied,'new_parts':{name:before[name] for name in new_names}}
            spec['spec_sha256']=m._hash({k:v for k,v in spec.items() if k not in ('copy_evidence','spec_sha256')})
            old_upgrade=copy.deepcopy(spec);old_upgrade['mutable_base_files']=sorted(old_mutable)
            old_sha=m._hash({k:v for k,v in old_upgrade.items() if k not in ('copy_evidence','spec_sha256')})
            old={'schema':'ANBAU_END_VERIFICATION_V1','file_map':spec['file_map'],
                 'copy_evidence':spec['copy_evidence'],
                 'immutable_parts':{name:copied[name] for name in names if name not in old_mutable},
                 'upgrade_attributes':{'schema':m.SCHEMA,'spec_sha256':old_sha}}
            old['spec_sha256']=m._hash(old)
            result=m._repair_guard(target,spec,old,before)
            self.assertEqual(result['save_files'],['CONSTRUCTION.prt','MASTER.prt'])
            self.assertEqual(result['old_upgrade_spec_sha256'],old_sha)
            for mutation in ('changed_before','changed_intent','published','missing_owner'):
                changed=copy.deepcopy(spec);manifest=copy.deepcopy(before)
                if mutation=='changed_before':manifest['MASTER.prt']['sha256']='0'*64
                if mutation=='changed_intent':changed['layout']['nodes'][0]['unexpected']='change'
                if mutation=='missing_owner':changed['mutable_base_files'].remove('CONSTRUCTION.prt')
                if mutation=='published':(directory/'CURRENT.json').write_text(json.dumps({'directory':'candidate'}))
                if mutation in ('changed_intent','missing_owner'):
                    changed['spec_sha256']=m._hash({k:v for k,v in changed.items() if k not in ('copy_evidence','spec_sha256')})
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):m._repair_guard(target,changed,old,manifest)
                if mutation=='published':(directory/'CURRENT.json').unlink()
            naming=copy.deepcopy(spec);naming['fields']={}
            for index in range(24):
                sid=('PS10','PS11','PS12','PS13')[index//6];fid=sid+'-F%02d'%(index%6+1)
                nid='FIELD_'+fid;naming['fields'][fid]={'container_node_id':nid}
                naming['layout']['nodes'].append({'id':nid,'parent':'SECTION_'+sid,'file':'P%03d.prt'%(index+4)})
            naming['spec_sha256']=m._hash({k:v for k,v in naming.items() if k not in ('copy_evidence','spec_sha256')})
            proof={'schema':'ANBAU_END_VERIFICATION_V1','layout':naming['layout'],
                   'file_map':naming['file_map'],'copy_evidence':naming['copy_evidence'],
                   'immutable_parts':{name:row for name,row in old['immutable_parts'].items() if name!='CONSTRUCTION.prt'},
                   'upgrade_attributes':{'schema':m.SCHEMA,'spec_sha256':naming['spec_sha256']}}
            proof['spec_sha256']=m._hash(proof)
            targets=m._instance_name_repair_guard(target,naming,proof,before)
            self.assertEqual(targets['save_files'],['CONSTRUCTION.prt','P000.prt','P001.prt','P002.prt','P003.prt'])
            self.assertEqual(len(targets['node_ids']),28)
            changed=copy.deepcopy(naming);changed['layout']['nodes'][0]['unexpected']='change'
            changed['spec_sha256']=m._hash({k:v for k,v in changed.items() if k not in ('copy_evidence','spec_sha256')})
            with self.assertRaises(ValueError):m._instance_name_repair_guard(target,changed,proof,before)

    def test_section_definitions_are_saved_in_their_parent_part_not_only_the_master(self):
        """Definition-owner dispatch only; this does not simulate native saving."""
        from renovierung.anbau import integration
        from renovierung.m01 import display
        class Child:
            def __init__(self,ident):self.ident=ident;self.used=None
            def SetUsedArrangement(self,value):self.used=value
        children=[Child('SECTION_PS01'),Child('SECTION_PS10'),Child('SECTION_PS11')]
        parent=types.SimpleNamespace(ComponentAssembly=types.SimpleNamespace(
            RootComponent=types.SimpleNamespace(GetChildren=lambda:children)))
        nodes={'MASTER':{'file':'MASTER.prt'},'CONSTRUCTION':{'file':'CONSTRUCTION.prt'}}
        nodes.update({child.ident:{'id':child.ident,'parent':'CONSTRUCTION','file':child.ident+'.prt'}
                      for child in children})
        defaults={sid:{'master_arrangement':'ALL_'+sid} for sid in ('PS10','PS11')}
        spec={'section_defaults':defaults,'file_map':{}}
        arrangements={sid:{'ALL_'+sid:object()} for sid in defaults};saved=[]
        with patch.object(integration,'_open',return_value=parent) as opened, \
                patch.object(display,'read_attribute',side_effect=lambda obj,key:obj.ident), \
                patch.object(integration,'_write_node') as write:
            result=integration._persist_section_definitions(None,Path('new'),spec,nodes,arrangements,saved.append)
            opened.assert_called_once_with(None,Path('new'),'CONSTRUCTION.prt',{},True)
            self.assertEqual(result,['CONSTRUCTION.prt'])
            self.assertEqual(saved,[parent])
            self.assertEqual([call.args[1]['id'] for call in write.call_args_list],['SECTION_PS10','SECTION_PS11'])
            self.assertIsNone(children[0].used)
            for child in children[1:]:
                self.assertIs(child.used,arrangements[child.ident.removeprefix('SECTION_')]['ALL_'+child.ident.removeprefix('SECTION_')])
            children.pop();saved.clear()
            with self.assertRaisesRegex(ValueError,'Incomplete SECTION definitions'):
                integration._persist_section_definitions(None,Path('new'),spec,nodes,arrangements,saved.append)
            self.assertEqual(saved,[])

    def test_attribute_replacement_filters_only_none_and_preserves_exact_chunk_deletion(self):
        """Attribute-list fixtures only; no native readback is simulated."""
        from renovierung.anbau import integration
        from renovierung.m01 import display
        class Owner:
            def __init__(self,attributes):self.attributes=attributes;self.deleted=[]
            def GetUserAttributes(self):return self.attributes
            def GetInstanceUserAttributes(self):return self.attributes
            def DeleteUserAttribute(self,*args):self.deleted.append(args)
            def DeleteInstanceUserAttribute(self,*args):self.deleted.append(args)
        class Component(Owner):pass
        nx=types.ModuleType('NXOpen');assemblies=types.ModuleType('NXOpen.Assemblies')
        assemblies.Component=Component;nx.Assemblies=assemblies
        nx.Update=types.SimpleNamespace(Option=types.SimpleNamespace(Now='NOW'))
        key='M01_FIELD_METADATA';value={'id':'PS11-F01'}
        def attribute(title,kind='String'):return types.SimpleNamespace(Title=title,Type=kind)
        direct=attribute(key);chunk=attribute(key+'_000');large=attribute(key+'_1000')
        foreign=attribute(key+'_OTHER');other=attribute('FOREIGN')
        with patch.dict('sys.modules',{'NXOpen':nx,'NXOpen.Assemblies':assemblies}), \
                patch.object(display,'write_attribute') as write:
            for kind in (Owner,Component):
                for rows,wanted in (([None],[]),([None,foreign,chunk,None,direct,large,chunk,other],
                                             [key,key+'_000',key+'_1000'])):
                    with self.subTest(kind=kind.__name__,null_only=len(rows)==1):
                        obj=kind(rows);integration._replace_attribute(obj,key,value)
                        self.assertEqual(obj.deleted, [('String',title,True,'NOW') for title in wanted])
                        write.assert_called_with(obj,key,value)
                write.reset_mock()
                with self.assertRaises(AttributeError):integration._replace_attribute(kind([None,object()]),key,value)
                write.assert_not_called()

    def test_only_component_labels_are_renamed_while_part_metadata_keeps_label(self):
        """Type-dispatch fixture only; it supplies no native NX evidence."""
        from renovierung.anbau import integration
        class Part:
            FullPath='C:/new/PS11_F01.prt'
            def SetName(self,value):
                raise AssertionError('Part filename must not be renamed through NXObject.SetName')
        class Component:
            Tag=41
            def SetName(self,value):self.Name=value
        nx=types.ModuleType('NXOpen');assemblies=types.ModuleType('NXOpen.Assemblies')
        assemblies.Component=Component;nx.Assemblies=assemblies
        uf_module=types.ModuleType('NXOpen.UF');nx.UF=uf_module
        instance={'name':'OLD_REGISTER'};renamed=[]
        def rename(tag,name):renamed.append((tag,name));instance['name']=name.upper()
        uf=types.SimpleNamespace(Assem=types.SimpleNamespace(
            AskComponentData=lambda tag:('FIELD.prt','None',instance['name']),
            AskInstOfPartOcc=lambda tag:tag+100,RenameInstance=rename))
        uf_module.UFSession=types.SimpleNamespace(GetUFSession=lambda:uf)
        row={'id':'FIELD_PS11-F01','name':'PS11_F01_DIAGNOSE','kind':'field','blank':False}
        field={'id':'PS11-F01','native':False,'diagnostic_only':True}
        part,component=Part(),Component()
        with patch.dict('sys.modules',{'NXOpen':nx,'NXOpen.Assemblies':assemblies,'NXOpen.UF':uf_module}), \
                patch.object(integration,'_replace_attribute') as write:
            integration._write_node(part,row,field)
            part_values={call.args[1]:call.args[2] for call in write.call_args_list}
            self.assertEqual(part.FullPath,'C:/new/PS11_F01.prt')
            self.assertEqual(part_values['M01_NODE_METADATA'],row)
            self.assertEqual(part_values['M01_NODE_METADATA']['name'],row['name'])
            self.assertFalse(part_values['M01_FIELD_NATIVE'])
            self.assertTrue(part_values['ANBAU_DIAGNOSTIC'])
            write.reset_mock()
            integration._write_node(component,row,field)
            self.assertEqual(component.Name,row['name'])
            self.assertEqual({call.args[1]:call.args[2] for call in write.call_args_list},part_values)
            self.assertEqual(renamed,[(141,row['name'])])
            self.assertEqual(instance['name'],row['name'].upper())
            integration._write_node(component,row,field)
            self.assertEqual(renamed,[(141,row['name'])])


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=importlib.import_module('renovierung.anbau.integration')
        # Fail on accidental local-artifact dependencies without moving any files.
        text_reader,byte_reader=Path.read_text,Path.read_bytes
        def checked(reader):
            def read(path,*args,**kwargs):
                if path.resolve().is_relative_to((ROOT/'reports/local').resolve()):
                    raise AssertionError('Integration fixtures must not read ignored reports/local inputs')
                return reader(path,*args,**kwargs)
            return read
        with patch.object(Path,'read_text',checked(text_reader)),patch.object(Path,'read_bytes',checked(byte_reader)):
            from renovierung.anbau.geometry import create_plan
            from renovierung.anbau.runner import current_field_inputs,json_contract
            cls.base=json.loads((ROOT/'cad/nx/m01/20261104T222509Z_edc552/BUILD.json').read_text())['layout']
            cls.plan=json_contract(create_plan(ROOT,include_mesh=True))
            cls.inputs=current_field_inputs(cls.plan)
        from renovierung.anbau.site import _entry_hash
        natives=[f for f in cls.plan['fields'] if f['native_candidate']]
        # Synthetic compact shell for declaration tests, not native/geometric evidence.
        cls.site={'schema':'ANBAU_SHARED_SITE_V1','file':'ANBAU_SITE.prt','units':'mm',
                  'construction_release':False,'thickness_mm':200,'body_count':1,
                  'shells':[{'id':'TEST_SHELL','exclude_for':[],'volume_m3':1,'bbox_mm':[0,0,0,1000,1000,1000]}],
                  'groups':[],'field_regions':{f['id']:f['study_terrain']['uv_cell_bounds'] for f in natives},
                  'reference_sets':{f['id']:{'name':'ANBAU_SITE_'+f['id'].replace('-','_'),
                        'shell_ids':['TEST_SHELL'],'body_count':1,'volume_m3':1,'area_m2':5} for f in natives},
                  'height_registration':cls.plan['height_registration'],
                  'source_hashes':{},'input_sha256':'1'*64,'mesh_sha256':'2'*64,'step_sha256':'3'*64,'step_bytes':1}
        cls.site['entry_sha256']=_entry_hash(cls.site)
        cls.spec=cls.module.prepare_upgrade(cls.base,cls.plan,cls.inputs,cls.site)

    def test_existing_tree_houses_and_logical_records_stay_additive(self):
        spec=self.spec
        self.assertEqual(len(spec['base_file_map']),318)
        self.assertEqual(len(spec['file_map']),367)
        self.assertEqual(len(spec['new_nodes']),64)
        self.assertEqual(len(spec['layout']['nodes']),len(self.base['nodes'])+64)
        self.assertEqual(len(spec['mutable_base_files']),34)
        self.assertIn(next(n['file'] for n in self.base['nodes'] if n['id']=='CONSTRUCTION'),spec['mutable_base_files'])
        self.assertEqual(len(set(spec['base_file_map'])-set(spec['mutable_base_files'])),284)
        self.assertEqual(len(spec['new_leaf_files']),25)
        self.assertEqual(len(spec['fields']),24)
        self.assertEqual(spec['base_layout'],self.base)
        self.assertEqual(set(spec['expected_nodes']),{n['id'] for n in spec['layout']['nodes']})
        self.assertEqual(set(spec['expected_world_transforms']),set(spec['expected_nodes']))
        old={n['id']:n for n in self.base['nodes']};new={n['id']:n for n in spec['layout']['nodes']}
        for nid,row in old.items():
            if nid.startswith('FIELD_PS1') or nid in {'SECTION_PS10','SECTION_PS11','SECTION_PS12','SECTION_PS13'}:continue
            self.assertEqual(new[nid],row,nid)
        self.assertEqual(sum(n['id']=='HOUSE' for n in spec['layout']['nodes']),1)
        for node in spec['new_nodes']:
            self.assertEqual(node['translation_mm'],[0,0,0])
            self.assertEqual(node['rotation'],[1,0,0,0,1,0,0,0,1])
            self.assertTrue(node['parent'].startswith('FIELD_PS1'))

    def test_all_original_36_arrangements_hide_every_new_child_and_base_stays_original(self):
        from renovierung.m01.states import state_spec
        spec=self.spec;newids={n['id'] for n in spec['new_nodes']}
        self.assertEqual(len(spec['original_catalog']),36)
        self.assertEqual(len(spec['catalog']),60)
        for sid,name in spec['original_catalog'].items():
            self.assertEqual(spec['catalog'][sid],name)
            self.assertEqual(set(spec['states'][sid]['suppressed_ids']),
                             set(state_spec(self.base,sid)['suppressed_ids'])|newids)
        self.assertTrue(spec['states']['BASE']['terrain_visible'])
        self.assertIsNone(spec['states']['BASE']['site'])

    def test_new_states_are_single_alternatives_and_diagnostics_never_claim_free_native_or_sand(self):
        spec=self.spec;oldcontexts={g['id'] for g in self.base['context']['groups']}
        self.assertEqual(sum(f['native'] for f in spec['fields'].values()),10)
        self.assertEqual(sum(f['diagnostic'] for f in spec['fields'].values()),14)
        fieldids={f['node_id'] for f in self.base['fields']}
        for fid,field in spec['fields'].items():
            state=spec['states'][fid]
            self.assertEqual(state['name'],'M01_'+fid.replace('-','_'))
            self.assertEqual(set(state['visible_field_ids']),{fid})
            hidden=set(state['suppressed_ids'])
            self.assertTrue(oldcontexts<=hidden)
            self.assertIn('TERRAIN',hidden)
            self.assertTrue(fieldids-{field['container_node_id']}<=hidden)
            self.assertFalse(state['terrain_visible'])
            if field['native']:
                self.assertFalse(field['diagnostic'])
                self.assertEqual(state['visible_role_bodies']['cut_soil'],2)
                self.assertEqual(state['visible_role_bodies']['pile_main'],1)
                self.assertEqual(state['visible_role_bodies']['excavation'],0)
                self.assertEqual(state['visible_role_bodies']['pile_reserve'],0)
                self.assertEqual(state['site']['body_count'],1)
            else:
                self.assertTrue(field['diagnostic'])
                self.assertFalse(field['metadata']['native'])
                self.assertIsNone(field['metadata']['volume_m3'])
                self.assertFalse(any(state['visible_role_bodies'].values()))
                self.assertEqual(state['visible_diagnostic_bodies'],1)
                self.assertIsNone(state['site'])

    def test_insufficient_parcel_edge_strips_use_only_existing_red_excavation_source(self):
        expected={'PS11-F01':226.296369,'PS11-F04':6.365958,'PS11-F05':4.389711}
        for fid,distance in expected.items():
            field=self.spec['fields'][fid]
            self.assertFalse(field['native']);self.assertTrue(field['diagnostic'])
            self.assertEqual(field['source_mode'],'STUDY')
            self.assertEqual(field['leaf_file'],fid+'_STUDY.prt')
            self.assertEqual(field['diagnostic_refset'],'M01_EXCAVATION')
            self.assertEqual(field['metadata']['status'],'PARCEL_EDGE_STRIP_CONFLICT_DIAGNOSTIC')
            self.assertAlmostEqual(field['metadata']['parcel_edge_clearance_mm'],distance,places=5)
            self.assertIsNone(field['metadata']['volume_m3'])
            self.assertEqual(len(field['child_ids']),1)
            child=next(n for n in self.spec['new_nodes'] if n['id']==field['child_ids'][0])
            self.assertEqual(child['kind'],'diagnostic');self.assertEqual(child['reference_set'],'M01_EXCAVATION')
            self.assertIn('RANDSTREIFENKONFLIKT',field['metadata']['note'])
        border=self.spec['fields']['PS12-F01']['metadata']
        self.assertTrue(self.spec['fields']['PS12-F01']['native'])
        self.assertIn('0.543',border['note'])

    def test_section_defaults_and_new_wrappers_are_deterministic_and_casefold_unique(self):
        defaults={sid:row['state'] for sid,row in self.spec['section_defaults'].items()}
        self.assertEqual(defaults,{'PS10':'PS10-F01','PS11':'PS11-F01','PS12':'PS12-F01','PS13':'PS13-F01'})
        self.assertEqual(len(self.spec['reviews']),59)
        self.assertEqual(sum(r['action']=='create' for r in self.spec['reviews']),24)
        self.assertEqual(sum(r['action']=='update' for r in self.spec['reviews']),4)
        self.assertEqual(len(set(v.casefold() for v in self.spec['file_map'].values())),367)

    def test_targets_or_native_inputs_cannot_rewrite_original_or_bypass_classification(self):
        for which in ('missing_field','wrong_leaf_mode','wrong_refset','wrong_plan_hash','new_child_collision'):
            base=copy.deepcopy(self.base);plan=copy.deepcopy(self.plan);inputs=copy.deepcopy(self.inputs)
            if which=='missing_field':plan['fields'].pop()
            if which=='wrong_leaf_mode':inputs['fields']['PS10-F01']['spec']['mode']='STUDY'
            if which=='wrong_refset':inputs['fields']['PS11-F01']['spec']['refsets']['cut_soil']='Entire Part'
            if which=='wrong_plan_hash':inputs['plan_sha256']='0'*64
            if which=='new_child_collision':base['nodes'][1]['id']='ANBAU_SITE_PS12-F01'
            with self.subTest(which=which),self.assertRaises(ValueError):
                self.module.prepare_upgrade(base,plan,inputs,self.site)

    def test_attribute_replacement_deletes_only_exact_key_and_own_numeric_chunks(self):
        titles=['M01_FIELD_METADATA','M01_FIELD_METADATA_000','M01_FIELD_METADATA_1000',
                'M01_FIELD_METADATA_OTHER','M01_FIELD_METADATA_000_EXTRA','FOREIGN','M01_FIELD_NATIVE']
        self.assertEqual(self.module.attribute_titles_to_remove(titles,'M01_FIELD_METADATA'),
                         ['M01_FIELD_METADATA','M01_FIELD_METADATA_000','M01_FIELD_METADATA_1000'])

    def test_pinned_edge_review_cannot_be_silently_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory=root/'renovierung/anbau';directory.mkdir(parents=True)
            (directory/'KATALOG.json').write_text('{}',encoding='utf-8')
            review=self.spec['edge_strip_review']
            result=self.module.write_edge_strip_review(root,review)
            path=Path(result['review']);before=path.read_bytes()
            self.module.write_edge_strip_review(root,review)
            self.assertEqual(path.read_bytes(),before)
            changed=copy.deepcopy(review);changed['plan_sha256']='0'*64
            with self.assertRaises(FileExistsError):self.module.write_edge_strip_review(root,changed)
            self.assertEqual(path.read_bytes(),before)

    def test_missing_independent_copy_evidence_is_rejected_before_any_nx_api(self):
        class Session:
            IsBatch=True
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):self.module.upgrade_master(Session(),Path(temp),self.spec)
        spec=copy.deepcopy(self.spec)
        spec['copy_evidence']={'schema':'ANBAU_M01_INDEPENDENT_COPY_V1','native_independent':False}
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):self.module.upgrade_master(Session(),Path(temp),spec)

    def test_copy_guard_requires_exact_disjoint_source_and_target_byte_manifests(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp).resolve();source=directory/'original';target=directory/'new'
            source.mkdir();target.mkdir();spec=copy.deepcopy(self.spec)
            bases={};copied={};added={}
            for name in spec['base_file_map'].values():
                for root,records,content in ((source,bases,b'original fixture, not NX'),(target,copied,b'cloned fixture, not NX')):
                    path=root/name;path.write_bytes(content)
                    records[name]={'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
            for name in spec['new_leaf_files']:
                content=b'new geometry fixture, not NX';(target/name).write_bytes(content)
                added[name]={'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}
            spec['copy_evidence']={'schema':'ANBAU_M01_INDEPENDENT_COPY_V1','source_root':str(source),
                'destination_root':str(target),'native_independent':True,'native_clone_completed':True,
                'base_layout_sha256':spec['base_layout_sha256'],'source_parts':bases,'copied_parts':copied,'new_parts':added}
            self.assertEqual(self.module._copy_guard(target,spec)[0],source)
            for mutation in ('same_root','missing_part','source_changed','target_changed','spec_changed'):
                changed=copy.deepcopy(spec)
                path=None
                if mutation=='same_root':changed['copy_evidence']['source_root']=str(target)
                if mutation=='missing_part':changed['copy_evidence']['copied_parts'].pop(next(iter(copied)))
                if mutation=='source_changed':path=source/next(iter(bases));original=path.read_bytes();path.write_bytes(b'changed')
                if mutation=='target_changed':path=target/next(iter(copied));original=path.read_bytes();path.write_bytes(b'changed')
                if mutation=='spec_changed':changed['catalog']['BASE']='WRONG'
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.module._copy_guard(target,changed)
                if path is not None:path.write_bytes(original)


if __name__=='__main__':unittest.main()
