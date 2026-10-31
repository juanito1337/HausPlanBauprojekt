# -*- coding: utf-8 -*-
"""R03c regression against the uploaded Expression.SetUserAttribute OM failure.

NX objects and exception injection are simulated. No NX/Parasolid execution.
The legacy fixture contains the unmodified R03b methods, not invented pseudocode.
"""
import contextlib
import copy
import importlib.util
import io
import json
import math
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_geometry import Parameters
from haus2406_r03.haus_metadata import (parameter_attributes,decode_parameter_attributes,
    attribute_diagnostic,AttributeWriteError,SCHEMA,CHUNK_CHARS)
from haus2406_r03.haus_nx import NXAdapter
from haus2406_r03.haus_run import run_house,smoke_test,check_saved_house,check_parameter_report
from fake_nx import FakeNX,FakeNXException,Expression

OM_ERROR='Functionality attempted not possible in the current version of the OM'


def item(value=240,unit='mm',status='PLANWERT'):
    return {'value':value,'unit':unit,'status':status,
            'sources':[{'document':'P13','page':1,'location':'Quelle mit Höhe und Maß'}],
            'confidence':'hoch','note':'Quellenstand, kein aktueller NX-Istwert'}


def load_entry(base,name):
    spec=importlib.util.spec_from_file_location('_r03c_entry_'+name,str(base/(name+'.py')))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ParameterMetadataTests(unittest.TestCase):
    def test_roundtrip_all_62_current_parameter_definitions(self):
        data=json.loads((BASE/'data/haus.json').read_text())
        for name,value in data['parameters'].items():
            with self.subTest(name=name):
                attrs,payload=parameter_attributes(name,value)
                restored=decode_parameter_attributes(name,attrs)
                self.assertEqual(restored,payload)
                self.assertEqual(restored['definition_at_build'],value)

    def test_long_unicode_source_is_lossless_with_bounded_ascii_chunks(self):
        definition=item();definition['note']='Ä Ö ß 中文\n"Plan"\\ '*600
        attrs,payload=parameter_attributes('LANGE_QUELLE',definition)
        chunks={k:v for k,v in attrs.items() if '__JSON_' in k and not k.endswith('_N')}
        self.assertGreater(len(chunks),100)
        self.assertTrue(all(v.isascii() and 0<len(v)<=CHUNK_CHARS for v in chunks.values()))
        self.assertEqual(decode_parameter_attributes('LANGE_QUELLE',attrs),payload)

    def test_unique_names_do_not_clobber_part_identity_or_each_other(self):
        attrs={'HAUS_ID':'ERDGESCHOSS','QUELLSTATUS':'PRUEFMODELL'}
        for name in ['A','A_B','A__B','A__JSON_0001']:
            values,_=parameter_attributes(name,item());self.assertFalse(set(attrs)&set(values));attrs.update(values)
        self.assertEqual(attrs['HAUS_ID'],'ERDGESCHOSS')
        self.assertEqual(attrs['QUELLSTATUS'],'PRUEFMODELL')
        for name in ['A','A_B','A__B','A__JSON_0001']:
            self.assertEqual(decode_parameter_attributes(name,attrs)['expression_name'],name)

    def test_invalid_names_units_nan_and_metadata_rejected_without_mutation(self):
        definition=item();before=copy.deepcopy(definition)
        for name in ['', 'a b','1X','x'*65,'A/../B']:
            with self.subTest(name=name),self.assertRaises(ValueError):parameter_attributes(name,definition)
        for bad in [item(math.nan),item(unit='inch'),item(status=''),{'value':3,'unit':'mm'}]:
            with self.assertRaises(ValueError):parameter_attributes('A',bad)
        with self.assertRaises(ValueError):parameter_attributes('A',[])
        self.assertEqual(definition,before)

    def test_missing_corrupted_and_mislabelled_chunks_are_not_accepted(self):
        attrs,_=parameter_attributes('A',item())
        for change in ['missing','content','status','unit','format']:
            bad=dict(attrs)
            if change=='missing':del bad['HAUS_PARAM_A__JSON_0001']
            if change=='content':bad['HAUS_PARAM_A__JSON_0001']='!'+bad['HAUS_PARAM_A__JSON_0001'][1:]
            if change=='status':bad['HAUS_PARAM_A__STATUS']='GESCHAETZT'
            if change=='unit':bad['HAUS_PARAM_A__EINHEIT']='deg'
            if change=='format':bad['HAUS_PARAM_A__FORMAT']='WRONG'
            with self.subTest(change=change),self.assertRaises((ValueError,KeyError)):
                decode_parameter_attributes('A',bad)

    def test_record_is_a_deep_build_snapshot_not_a_live_reference(self):
        definition=item();attrs,payload=parameter_attributes('H',definition)
        definition['value']=999;definition['sources'][0]['location']='EDIT'
        self.assertEqual(payload['definition_at_build']['value'],240)
        self.assertNotEqual(payload['definition_at_build']['sources'],definition['sources'])
        self.assertEqual(list(attrs)[-1],'HAUS_PARAM_H__FORMAT')

    def test_diagnostic_survives_unavailable_nx_object_properties(self):
        class Broken:
            @property
            def OwningPart(self):raise RuntimeError('deleted object')
            @property
            def Name(self):raise RuntimeError('deleted name')
            @property
            def Tag(self):raise RuntimeError('deleted tag')
        diagnostic=attribute_diagnostic(Broken(),'KEY','VALUE',FakeNXException(OM_ERROR),'Write')
        self.assertEqual(diagnostic['error'],OM_ERROR)
        self.assertIsNone(diagnostic['nx_error_code'])
        json.dumps(diagnostic,allow_nan=False)


class AttributeAdapterDoubleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.fake=FakeNX();c=self.fake.install();c.start();self.addCleanup(c.stop)
        self.messages=[];self.nx=NXAdapter(self.messages.append)
    def part(self,name='TEST'):
        return self.nx.new_part(self.root/(name+'.prt'),name)

    def test_unmodified_r03b_methods_reproduce_the_uploaded_om_error(self):
        legacy={};exec((BASE/'tests/fixtures/r03b_expression_attributes.txt').read_text(),legacy)
        part=self.part()
        with patch.object(self.nx,'attributes',types.MethodType(legacy['attributes'],self.nx)):
            with self.assertRaises(FakeNXException) as caught:
                legacy['add_parameters'](self.nx,part,Parameters({'A':item()}))
        self.assertEqual(str(caught.exception),OM_ERROR)
        self.assertEqual(self.fake.expression_attribute_attempts,1)
        self.assertIn('A',part.Expressions.items)
        self.assertEqual(part.attrs['HAUS_ID'],'TEST')
        self.assertEqual(self.fake.commits,0)

    def test_all_parameters_use_part_attributes_without_expression_calls(self):
        part=self.part();data=json.loads((BASE/'data/haus.json').read_text())
        count=self.nx.add_parameters(part,Parameters(data['parameters']))
        self.assertEqual(count,67);self.assertEqual(self.fake.expression_attribute_attempts,0)
        self.assertEqual(part.attrs['HAUS_ID'],'TEST')
        for name,definition in data['parameters'].items():
            self.assertFalse(part.Expressions.FindObject(name).attrs)
            self.assertEqual(decode_parameter_attributes(name,part.attrs)['definition_at_build'],definition)
        self.assertEqual(len(self.nx.parameter_metadata),67)

    def test_formula_order_and_angle_units_preserved(self):
        part=self.part();derived=item();derived.pop('value');derived['formula']='H+T'
        params=Parameters({'TOP':derived,'H':item(2650),'T':item(200),'ANGLE':item(45,'deg')})
        self.nx.add_parameters(part,params)
        self.assertEqual(list(part.Expressions.items),['H','T','TOP','ANGLE'])
        self.assertEqual(part.Expressions.FindObject('TOP').RightHandSide,'H+T')
        self.assertEqual(part.Expressions.FindObject('ANGLE').unit,'Degrees')
        self.assertEqual(part.Expressions.number('TOP'),2850)
        part.Expressions.FindObject('H').RightHandSide='2750'
        self.assertEqual(part.Expressions.number('TOP'),2950)
        self.assertEqual(decode_parameter_attributes('H',part.attrs)['definition_at_build']['value'],2650)

    def test_defensive_generic_attributes_guard_prevents_expression_api_call(self):
        part=self.part();expr=part.Expressions.CreateWithUnits('A=1','MilliMeter')
        with self.assertRaisesRegex(TypeError,'Part speichern'):
            self.nx.attributes(expr,{'id':'A','status':'PLANWERT'})
        self.assertEqual(self.fake.expression_attribute_attempts,0)

    def test_failed_part_metadata_write_stops_and_preserves_error_code(self):
        part=self.part();original=part.SetUserAttribute
        def fail(key,index,value,option):
            if key.endswith('__JSON_0001'):raise FakeNXException('INJECTED_PART_ATTRIBUTE_FAILURE',987654)
            return original(key,index,value,option)
        with patch.object(part,'SetUserAttribute',side_effect=fail):
            with self.assertRaises(AttributeWriteError) as caught:
                self.nx.add_parameters(part,Parameters({'A':item()}))
        diag=caught.exception.nx_attribute_check
        self.assertEqual(diag['attribute'],'HAUS_PARAM_A__JSON_0001')
        self.assertEqual(diag['nx_error_code'],987654)
        self.assertEqual(diag['object_name'],'TEST')
        self.assertNotIn('HAUS_PARAM_A__FORMAT',part.attrs)
        self.assertEqual(self.nx.parameter_metadata[0]['status'],'UNVOLLSTAENDIG_LAUF_ABGEBROCHEN')
        self.assertIsInstance(caught.exception.__cause__,FakeNXException)
        self.assertEqual(self.fake.commits,0)

    def test_log_failure_does_not_mask_attribute_failure(self):
        part=self.part()
        with patch.object(part,'SetUserAttribute',side_effect=FakeNXException(OM_ERROR)),\
             patch.object(self.nx,'log',side_effect=OSError('LOG_DISK_FAILURE')):
            with self.assertRaises(AttributeWriteError) as caught:
                self.nx.add_parameters(part,Parameters({'A':item()}))
        self.assertEqual(caught.exception.nx_attribute_check['error'],OM_ERROR)
        self.assertEqual(caught.exception.nx_attribute_check['diagnostic_log_error'],'LOG_DISK_FAILURE')

    def test_none_expression_and_foreign_part_never_receive_parameter_metadata(self):
        part=self.part()
        with patch.object(part.Expressions,'CreateWithUnits',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'keinen Ausdruck'):
                self.nx.add_parameters(part,Parameters({'A':item()}))
        foreign=self.fake.session.Parts.NewDisplay(self.root/'FOREIGN.prt',self.fake.N.Part.Units.Millimeters)
        with self.assertRaisesRegex(RuntimeError,'nicht von diesem Lauf'):
            self.nx.add_parameters(foreign,Parameters({'A':item()}))
        self.assertFalse(self.nx.parameter_metadata);self.assertFalse(foreign.attrs)

    def test_feature_body_curve_and_component_metadata_still_written(self):
        part=self.part();meta={'id':'WALL','status':'GESCHAETZT','sources':[]}
        curves=self.nx.lines(part,[[0,0,0],[10,0,0]],'LINE',False,meta=meta)
        body=self.nx.xy_extrude(part,[[0,0],[100,0],[100,20],[0,20]],0,100,'WALL',meta)[0]
        self.assertEqual(body.attrs['HAUS_ID'],'WALL')
        self.assertEqual(curves[0].attrs['HAUS_ID'],'WALL')
        self.nx.save(part);master=self.part('MASTER');component=self.nx.add_component(master,part.FullPath,'CHILD')
        self.assertEqual(component.attrs['HAUS_ID'],'CHILD')
        self.assertEqual(self.fake.expression_attribute_attempts,0)


class AttributeFlowDoubleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        for name in ('data','src'):
            shutil.copytree(BASE/name,self.base/name,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('RUN_HAUS_2406.py','SMOKE_TEST_2406.py','CHECK_HAUS_2406.py'):
            shutil.copy2(BASE/name,self.base/name)
        self.fake=FakeNX();c=self.fake.install();c.start();self.addCleanup(c.stop)
        cap=contextlib.redirect_stdout(io.StringIO());cap.__enter__();self.addCleanup(cap.__exit__,None,None,None)

    def test_smoke_creates_63_metadata_records_without_expression_attributes(self):
        result=smoke_test(self.base)
        self.assertEqual(result['status'],'NX_FUNKTIONSTEST_BESTANDEN')
        report=json.loads((Path(result['output_directory'])/'parameter_metadaten.json').read_text())
        self.assertEqual(len(report['records']),68);self.assertEqual(self.fake.expression_attribute_attempts,0)
        self.assertFalse(report['live_expression_values'])
        self.assertEqual(result['checks']['expression_z_2650_to_2750'],'BESTANDEN')
        self.assertTrue(all(r['status']=='PART_ATTRIBUTE_GESCHRIEBEN' for r in report['records']))

    def test_full_1165_body_flow_preserves_part_ids_sources_and_checker(self):
        result=run_house(self.base)
        self.assertEqual(result['built_solids'],1165)
        self.assertEqual(result['parameter_metadata']['records'],68+14*67)
        self.assertEqual(self.fake.expression_attribute_attempts,0)
        self.assertFalse(result['attribute_failures'])
        checked=check_saved_house(self.base)
        self.assertEqual(checked['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN')
        self.assertIn('KEIN_NX_ATTRIBUT_LESETEST',checked['parameter_metadata_check'])

    def test_parameter_sidecar_tampering_and_missing_file_block_checker(self):
        self.fake.answer=2;state=run_house(self.base);out=Path(state['output_directory'])
        file=out/'parameter_metadaten.json';original=file.read_bytes()
        file.write_bytes(original+b' ')
        with self.assertRaisesRegex(RuntimeError,'Metadaten veraendert'):check_saved_house(self.base)
        file.unlink()
        with self.assertRaisesRegex(FileNotFoundError,'Metadaten fehlen'):check_saved_house(self.base)
        file.write_bytes(original)
        state.pop('parameter_metadata')
        with self.assertRaisesRegex(RuntimeError,'fehlen im Manifest'):check_parameter_report(out,state)

    def test_parameter_error_propagates_into_entry_json_and_prevents_house(self):
        from fake_nx import Object
        original=Object.SetUserAttribute
        def reject(obj,title,index,value,option):
            if title.startswith('HAUS_PARAM_'):raise FakeNXException('INJECTED_MANDATORY_METADATA_ERROR',12345)
            return original(obj,title,index,value,option)
        with patch.object(Object,'SetUserAttribute',new=reject):
            result=load_entry(self.base,'RUN_HAUS_2406').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['patch'],'R06-QUELLEN-KONSISTENZ')
        self.assertEqual(result['nx_attribute_check']['nx_error_code'],12345)
        saved=json.loads(Path(result['report_file']).read_text())
        self.assertEqual(saved['nx_attribute_check']['attribute'],result['nx_attribute_check']['attribute'])
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
        self.assertEqual(self.fake.commits,0)
        for file in (self.base/'ausgabe').rglob('parameter_metadaten.json'):
            self.assertTrue(json.loads(file.read_text())['attribute_failures'])

    def test_missing_metadata_module_is_explicit_in_all_three_entries(self):
        (self.base/'src/haus2406_r03/haus_metadata.py').unlink()
        for name in ('RUN_HAUS_2406','SMOKE_TEST_2406','CHECK_HAUS_2406'):
            with self.subTest(entry=name):
                result=load_entry(self.base,name).main()
                self.assertEqual(result['status'],'ABGEBROCHEN')
                self.assertIn('haus_metadata.py',result['error'])
        self.assertFalse(self.fake.session.Parts.items)

    def test_nested_error_keeps_original_attribute_diagnostic_in_start_report(self):
        module=load_entry(self.base,'RUN_HAUS_2406')
        detail={'attribute':'HAUS_ID','error':OM_ERROR,'object_type':'Fake.Feature'}
        try:
            try:raise AttributeWriteError('attribute failed',detail)
            except AttributeWriteError as original:raise RuntimeError('NX-Schritt fehlgeschlagen') from original
        except RuntimeError as exception:
            report=module._failure(self.base,exception)
        self.assertEqual(report['nx_attribute_check'],detail)
        self.assertIn('NX-Schritt fehlgeschlagen',report['error'])

    def test_r03b_package_marker_cannot_be_mixed_with_r03c_entries(self):
        (self.base/'src/haus2406_r03/__init__.py').write_text('__version__="R03"\n__patch__="R03b-EINHEITENFIX"\n')
        for name in ('RUN_HAUS_2406','SMOKE_TEST_2406','CHECK_HAUS_2406'):
            with self.subTest(entry=name):
                result=load_entry(self.base,name).main()
                self.assertIn('Versionen vermischt',result['error'])
        self.assertFalse(self.fake.session.Parts.items)


if __name__=='__main__':unittest.main()
