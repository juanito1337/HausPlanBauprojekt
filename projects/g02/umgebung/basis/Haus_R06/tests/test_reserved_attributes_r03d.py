# -*- coding: utf-8 -*-
"""Regression for NX error 512091 in the user's 2026-10-07 body-attribute log.

All NX objects here are test doubles. The injected reservation reproduces the
observed rejection after Boolean subtraction, NOT a complete NX material model.
"""
import ast
import contextlib
import copy
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_metadata import (object_attributes,OBJECT_ATTRIBUTE_TITLES,
    OBJECT_ATTRIBUTE_SCHEMA,validate_project_attribute_title,parameter_attributes,AttributeWriteError)
from haus2406_r03.haus_nx import NXAdapter
from fake_nx import FakeNX,FakeNXException,Object,Body,Feature

RESERVED_ERROR='The attribute is reserved by an NX application or the system, so it cannot be set, changed or deleted.'
START='00_HAUS_ERZEUGEN_2406.py'
POINTER='LETZTER_ERFOLGREICHER_LAUF.json'


def legacy_methods():
    values={}
    exec((BASE/'tests/fixtures/r03c_reserved_attributes.txt').read_text(encoding='utf-8'),values)
    return values


def load_entry(base):
    spec=importlib.util.spec_from_file_location('_r03d_starter',str(base/START))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class AttributeNamespaceTests(unittest.TestCase):
    def test_all_twelve_titles_are_unique_and_project_namespaced(self):
        values=object_attributes({})
        self.assertEqual(len(values),12)
        self.assertEqual(set(values),set(OBJECT_ATTRIBUTE_TITLES.values()))
        self.assertEqual(len(set(OBJECT_ATTRIBUTE_TITLES.values())),12)
        self.assertEqual(OBJECT_ATTRIBUTE_TITLES['HAUS_ID'],'HAUS_ID')
        self.assertEqual(OBJECT_ATTRIBUTE_TITLES['MATERIAL'],'HAUS_MATERIAL')
        self.assertEqual(OBJECT_ATTRIBUTE_TITLES['REVISION'],'HAUS_REVISION')
        for key in values:self.assertEqual(validate_project_attribute_title(key),key)

    def test_base_values_preserved_except_revision_and_new_construction_fields(self):
        data=json.loads((BASE/'data/haus.json').read_text())
        examples=[{}, {'id':'TESTWAND','material':'Mauerwerk ÄÖß', 'category':'WAND',
                         'status':'GESCHAETZT','phase':'BESTAND','parent_id':'W01',
                         'host_wall':'AW01','detail_origin':'PLANWERT',
                         'sources':[{'document':'P13','page':1,'location':'Quelle mit Maß'}]}]
        # Every metadata dictionary compiled for the actual house is checked.
        from haus2406_r03.haus_compile import compile_house
        compiled=compile_house(data,True)
        examples.extend(s['meta'] for part in compiled['parts'] for s in part.get('solids',[]))
        legacy=legacy_methods()['attributes']
        for meta in examples:
            with self.subTest(id=meta.get('id')):
                old={}
                capture=types.SimpleNamespace(N=types.SimpleNamespace(Expression=type('UnusedExpression',(),{})),
                      _set_user_attribute=lambda obj,key,value,context:old.__setitem__(key,value))
                before=copy.deepcopy(meta);legacy(capture,object(),meta)
                new=object_attributes(meta)
                expected={OBJECT_ATTRIBUTE_TITLES[k]:v for k,v in old.items()}
                expected['HAUS_REVISION']='R06'
                self.assertEqual({k:new[k] for k in expected},expected)
                self.assertTrue(all(k.startswith('HAUS_') for k in new))
                self.assertEqual(meta,before)

    def test_empty_material_is_not_invented_or_written_under_system_name(self):
        for meta in ({},{'material':''},{'material':'Holz / C24 – Näherung'}):
            values=object_attributes(meta)
            self.assertNotIn('MATERIAL',values)
            self.assertEqual(values['HAUS_MATERIAL'],meta.get('material',''))

    def test_invalid_or_nonproject_titles_are_rejected(self):
        for title in ('MATERIAL','REVISION','QUELLE','KATEGORIE','HAUS_','XHAUS_ID','haus_ID','HAUS_ID\n','HAUS_ID;X',None,4):
            with self.subTest(title=title),self.assertRaises(ValueError):validate_project_attribute_title(title)
        self.assertEqual(validate_project_attribute_title('HAUS_PARAM_Hoehe__STATUS'),'HAUS_PARAM_Hoehe__STATUS')

    def test_existing_54_parameter_attribute_names_remain_valid_and_separate(self):
        data=json.loads((BASE/'data/haus.json').read_text())
        object_keys=set(object_attributes({}))
        for name,item in data['parameters'].items():
            values,_=parameter_attributes(name,item)
            self.assertFalse(set(values)&object_keys)
            for key in values:validate_project_attribute_title(key)

    def test_source_has_one_guarded_nx_attribute_write_and_no_unlock_or_delete(self):
        calls=[]
        for path in (BASE/'src').rglob('*.py'):
            tree=ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    if node.func.attr=='SetUserAttribute':calls.append((path,node.lineno))
                    self.assertNotIn(node.func.attr,('DeleteUserAttribute','DeleteAllAttributesByType','SetUserAttributeLock'))
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0].name,'haus_nx.py')
        tree=ast.parse(calls[0][0].read_text())
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_set_user_attribute')
        guards=[n.lineno for n in ast.walk(method) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='validate_project_attribute_title']
        self.assertEqual(len(guards),1);self.assertLess(guards[0],calls[0][1])


class ReservedAttributeAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
        self.fake=FakeNX();installed=self.fake.install();installed.start();self.addCleanup(installed.stop)
        self.nx=NXAdapter(lambda s:None)
        self.meta={'id':'TESTWAND','status':'GESCHAETZT','sources':[],'category':'WAND'}
    def part(self,name='TEST'):
        return self.nx.new_part(self.base/(name+'.prt'),name)
    def wall(self,part):
        return self.nx.xy_extrude(part,[[0,0],[4000,0],[4000,240],[0,240]],0,2650,'TEST_WAND',self.meta)[0]
    def door(self,part,body):
        return self.nx.xy_extrude(part,[[1000,-1],[2000,-1],[2000,241],[1000,241]],-1,2010,'TEST_TUEROEFFNUNG',self.meta,target=body)[0]

    def test_unmodified_r03c_code_reproduces_error_512091_after_subtraction(self):
        old=legacy_methods()
        with patch.object(self.nx,'attributes',types.MethodType(old['attributes'],self.nx)),\
             patch.object(self.nx,'_set_user_attribute',types.MethodType(old['_set_user_attribute'],self.nx)):
            part=self.part();wall=self.wall(part)
            self.assertIn('MATERIAL',wall.attrs)
            with self.assertRaisesRegex(RuntimeError,'SetUserAttribute: TESTWAND \\| MATERIAL'):
                self.door(part,wall)
        diag=self.nx.attribute_failures[-1]
        self.assertEqual(diag['nx_error_code'],512091)
        self.assertEqual(diag['attribute'],'MATERIAL')
        self.assertEqual(diag['object_name'],'TEST_TUEROEFFNUNG_KOERPER_01')
        self.assertEqual(diag['value_chars'],0)
        self.assertEqual(diag['error'],RESERVED_ERROR)
        self.assertEqual(self.fake.commits,2)
        self.assertEqual(len(self.fake.reserved_attribute_attempts),1)

    def test_corrected_subtraction_does_not_touch_preexisting_system_material(self):
        part=self.part();wall=self.wall(part)
        wall.attrs['MATERIAL']='SYSTEM_OWNED_DO_NOT_TOUCH'
        result=self.door(part,wall)
        self.assertIs(result,wall)
        self.assertEqual(wall.attrs['MATERIAL'],'SYSTEM_OWNED_DO_NOT_TOUCH')
        self.assertEqual(wall.attrs['HAUS_MATERIAL'],'')
        self.assertEqual(wall.attrs['HAUS_ID'],'TESTWAND')
        self.assertFalse(self.fake.reserved_attribute_attempts)
        self.assertFalse(self.nx.attribute_failures)
        self.assertTrue(all(key.startswith('HAUS_') for _,key in self.fake.attribute_attempts))

    def test_all_object_kinds_keep_source_text_and_never_touch_bare_titles(self):
        part=self.part();body=self.wall(part)
        curve=self.nx.lines(part,[[0,0,0],[10,0,0]],'REFERENCE',False,meta=self.meta)[0]
        feature=next(obj for obj in self.fake.objects.values() if isinstance(obj,Feature))
        self.nx.save(part);master=self.part('MASTER')
        component=self.nx.add_component(master,part.FullPath,'CHILD')
        material=dict(self.meta,material='Ziegel – laut Plan')
        for obj in (part,body,curve,feature,component):
            obj.attrs['MATERIAL']='SYSTEM'
            obj.reserved_attributes=set(OBJECT_ATTRIBUTE_TITLES)-{'HAUS_ID'}
            self.nx.attributes(obj,material)
            self.assertEqual(obj.attrs['MATERIAL'],'SYSTEM')
            self.assertEqual(obj.attrs['HAUS_MATERIAL'],material['material'])
            self.assertEqual(obj.attrs['HAUS_KATEGORIE'],'WAND')
        self.assertFalse(self.fake.reserved_attribute_attempts)

    def test_lowlevel_guard_stops_unprefixed_write_before_api(self):
        part=self.part();attempts=len(self.fake.attribute_attempts)
        for key in ('MATERIAL','REVISION','QUELLSTATUS'):
            with self.subTest(key=key),self.assertRaises(AttributeWriteError) as caught:
                self.nx._set_user_attribute(part,key,'x','INVALID_CALLER')
            self.assertEqual(caught.exception.nx_attribute_check['project_attribute_namespace'],'HAUS_')
        self.assertEqual(len(self.fake.attribute_attempts),attempts)
        self.assertEqual(len(self.nx.attribute_failures),3)

    def test_even_prefixed_attribute_rejection_is_not_swallowed(self):
        part=self.part();body=self.wall(part)
        body.reserved_attributes.add('HAUS_MATERIAL')  # Deliberately injected custom conflict.
        with self.assertRaisesRegex(RuntimeError,'HAUS_MATERIAL'):self.door(part,body)
        diag=self.nx.attribute_failures[-1]
        self.assertEqual(diag['nx_error_code'],512091)
        self.assertEqual(diag['attribute'],'HAUS_MATERIAL')
        self.assertEqual(diag['object_attribute_schema'],OBJECT_ATTRIBUTE_SCHEMA)
        self.assertGreater(self.fake.session.undo_calls,0)

    def test_snapshot_states_material_is_only_metadata(self):
        snapshot=self.nx.metadata_snapshot()
        self.assertEqual(snapshot['object_attribute_titles']['MATERIAL'],'HAUS_MATERIAL')
        self.assertFalse(snapshot['physical_material_assignment'])
        self.assertFalse(snapshot['live_expression_values'])


class ReservedAttributeFlowTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.base=Path(tmp.name)
        for name in ('src','data'):shutil.copytree(BASE/name,self.base/name,ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(BASE/START,self.base/START)
        self.fake=FakeNX();installed=self.fake.install();installed.start();self.addCleanup(installed.stop)
        output=contextlib.redirect_stdout(io.StringIO());output.__enter__();self.addCleanup(output.__exit__,None,None,None)

    def test_full_1165_body_launcher_and_check_never_write_unprefixed_attributes(self):
        self.assertFalse((self.base/POINTER).exists())
        state=load_entry(self.base).main()
        self.assertEqual(state['status'],'MODELL_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT')
        self.assertEqual(state['model']['patch'],'R06-QUELLEN-KONSISTENZ')
        self.assertEqual(state['model']['built_solids'],1165)
        self.assertFalse(self.fake.reserved_attribute_attempts)
        self.assertEqual(self.fake.expression_attribute_attempts,0)
        self.assertGreater(len(self.fake.attribute_attempts),1000)
        self.assertTrue(all(key.startswith('HAUS_') for _,key in self.fake.attribute_attempts))
        self.assertTrue((self.base/POINTER).is_file())
        cuts=[body for body in self.fake.objects.values() if isinstance(body,Body) and body.reserved_attributes]
        self.assertGreater(len(cuts),1)
        self.assertTrue(all('HAUS_MATERIAL' in body.attrs for body in cuts))
        out=Path(state['model']['output_directory'])
        snapshot=json.loads((out/'parameter_metadaten.json').read_text())
        self.assertEqual(snapshot['object_attribute_schema'],OBJECT_ATTRIBUTE_SCHEMA)

    def test_real_prefixed_write_failure_keeps_original_code_and_stops_before_house(self):
        original=Object.SetUserAttribute
        def reject(obj,title,index,value,option):
            if isinstance(obj,Body) and obj.reserved_attributes and title=='HAUS_MATERIAL':
                raise FakeNXException(RESERVED_ERROR,512091)
            return original(obj,title,index,value,option)
        with patch.object(Object,'SetUserAttribute',new=reject):result=load_entry(self.base).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['phase'],'FUNKTIONSTEST_UND_HAUSAUFBAU')
        self.assertEqual(result['nx_attribute_check']['attribute'],'HAUS_MATERIAL')
        self.assertEqual(result['nx_attribute_check']['nx_error_code'],512091)
        self.assertFalse((self.base/POINTER).exists())
        self.assertFalse(list((self.base/'ausgabe').rglob('HAUS_MASTER.prt')))
        self.assertFalse(list((self.base/'ausgabe').rglob('pruefung_*.json')))
        report=json.loads(Path(result['report_file']).read_text())
        self.assertEqual(report['patch'],'R06-QUELLEN-KONSISTENZ')
        self.assertIn('project_attribute_namespace',report['nx_attribute_check'])

    def test_reference_mode_keeps_same_namespace_policy(self):
        self.fake.answer=2;result=load_entry(self.base).main()
        self.assertEqual(result['status'],'MODELL_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT')
        self.assertEqual(result['model']['mode'],'REFERENZGERUEST')
        self.assertEqual(result['model']['built_solids'],0)
        self.assertFalse(self.fake.reserved_attribute_attempts)
        self.assertTrue(all(key.startswith('HAUS_') for _,key in self.fake.attribute_attempts))

    def test_r03c_core_is_rejected_by_r03d_launcher(self):
        (self.base/'src/haus2406_r03/__init__.py').write_text('__patch__="R03c-ATTRIBUTFIX"\n')
        result=load_entry(self.base).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('Versionen vermischt',result['error'])
        self.assertFalse(self.fake.attribute_attempts)


if __name__=='__main__':unittest.main(verbosity=2)
