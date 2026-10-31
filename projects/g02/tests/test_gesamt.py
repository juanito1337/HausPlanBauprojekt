# -*- coding: utf-8 -*-
"""Tests of G01 composition and failure paths. Stub files are NEVER native NX files."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

B=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(B))
from gesamt.core import (config_checked,environment_offset,read_json,write_json,sha256,absolute,
    relative_file,saved_record,check_records,validate_component_result,run_project,
    read_pointer,store_pointer,verify_package,child_exception_context,POINTERS)
from gesamt.nx_backend import NXBackend,load_package
CONFIG=read_json(B/'data/EINSTELLUNGEN_GESAMT.json')


def fake_result(root,kind):
    path=Path(root)/kind;path.mkdir(exist_ok=True)
    master=path/('HAUS_MASTER.prt' if kind=='house' else 'UMGEBUNG_MASTER_R09.prt')
    master.write_text('TESTDOUBLE_NOT_NX_FILE\n'+kind)
    row={'kind':kind,'status':'GESPEICHERT_UND_DATEIGEPRUEFT','master':str(master),
         'files':[saved_record(master)],'as_built_verified':False}
    if kind=='house':row.update(revision='MAIN01-A01',mode='PRUEFMODELL_MIT_NAEHERUNGEN',built_solids=1418)
    else:row.update(surface_validation='BASIS',new_house_built_by_environment=False)
    return row


class StubBackend:
    def __init__(self,fail=None):self.calls=[];self.fail=fail
    def preflight(self,mode,config,reuse):
        self.calls.append(('preflight',mode))
        if self.fail=='preflight':raise RuntimeError('INJECTED_PREFLIGHT')
    def build_house(self,out,cfg):
        self.calls.append(('house',None))
        if self.fail=='house':raise RuntimeError('INJECTED_HOUSE')
        return fake_result(out,'house')
    def build_environment(self,out,cfg):
        self.calls.append(('environment',None))
        if self.fail=='environment':raise RuntimeError('INJECTED_ENVIRONMENT')
        return fake_result(out,'environment')
    def assemble(self,out,house,env,cfg):
        self.calls.append(('assemble',None))
        if self.fail=='assemble':raise RuntimeError('INJECTED_ASSEMBLY')
        path=Path(out)/'PROJECT.prt';path.write_text('TESTDOUBLE_NOT_NX_FILE\nproject')
        return {'master':str(path),'files':[saved_record(path)],
                'height_connection_confirmed_by_user':environment_offset(cfg) is not None}


class ConfigurationTests(unittest.TestCase):
    def test_01_default_no_height(self):self.assertIsNone(environment_offset(CONFIG))
    def test_02_default_basis(self):self.assertEqual(config_checked(CONFIG)['surface_validation'],'BASIS')
    def test_03_explicit_metres_to_mm(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':31.1,'source':'SIMULATED MEASUREMENT','common_vertical_datum_confirmed':True}
        self.assertEqual(environment_offset(c),(0.,0.,-31100.))
    def test_04_missing_elevation(self):
        c=copy.deepcopy(CONFIG);c['height_connection']['common_vertical_datum_confirmed']=True
        with self.assertRaises(ValueError):config_checked(c)
    def test_05_missing_source(self):
        c=copy.deepcopy(CONFIG);c['height_connection'].update(H_EG_zero_in_source_datum_m=31.,common_vertical_datum_confirmed=True)
        with self.assertRaises(ValueError):config_checked(c)
    def test_06_unconfirmed_datum(self):
        c=copy.deepcopy(CONFIG);c['height_connection'].update(H_EG_zero_in_source_datum_m=31.,source='test')
        with self.assertRaises(ValueError):config_checked(c)
    def test_07_invalid_elevations(self):
        for value in (True,'31',float('nan'),float('inf')):
            with self.subTest(value=value):
                c=copy.deepcopy(CONFIG);c['height_connection'].update(H_EG_zero_in_source_datum_m=value,source='test',common_vertical_datum_confirmed=True)
                with self.assertRaises(ValueError):config_checked(c)
    def test_08_unknown_config(self):
        c=copy.deepcopy(CONFIG);c['ignore_errors']=True
        with self.assertRaises(ValueError):config_checked(c)
    def test_09_invalid_surface_policy(self):
        c=copy.deepcopy(CONFIG);c['surface_validation']='IGNORE'
        with self.assertRaises(ValueError):config_checked(c)
    def test_10_config_no_mutation(self):
        c=copy.deepcopy(CONFIG);d=config_checked(c);d['height_connection']['source']='changed';self.assertEqual(c,CONFIG)
    def test_11_path_no_resolve(self):
        with patch.object(Path,'resolve',side_effect=OSError(1005,'simulated')):
            self.assertTrue(absolute('test').is_absolute())
    def test_12_reject_unsafe_relative_paths(self):
        for name in ['../x','/x','C:/x','x\\y','x//y','x/./y','']:
            with self.subTest(name=name),self.assertRaises(ValueError):relative_file(B,name)
    def test_13_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x';p.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):read_json(p)
    def test_14_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x';p.write_text('{"a":NaN}')
            with self.assertRaises(ValueError):read_json(p)
    def test_15_atomic_bom_unicode(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'x';write_json(p,{'a':'Höhe'});self.assertEqual(read_json(p),{'a':'Höhe'});self.assertEqual(len(list(Path(t).iterdir())),1)


class ResultTests(unittest.TestCase):
    def test_01_valid_saved_house(self):
        with tempfile.TemporaryDirectory() as t:validate_component_result(fake_result(t,'house'),'house')
    def test_02_wrong_old_house_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['revision']='R11'
            with self.assertRaises(ValueError):validate_component_result(r,'house')
    def test_03_unverified_result_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['status']='START'
            with self.assertRaises(ValueError):validate_component_result(r,'house')
    def test_04_environment_cannot_build_old_house(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'environment');r['new_house_built_by_environment']=True
            with self.assertRaises(ValueError):validate_component_result(r,'environment')
    def test_05_claimed_as_built_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['as_built_verified']=True
            with self.assertRaises(ValueError):validate_component_result(r,'house')
    def test_06_reference_not_counted_house(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['mode']='REFERENZGERUEST'
            with self.assertRaises(ValueError):validate_component_result(r,'house')
            r['built_solids']=0;validate_component_result(r,'house')
    def test_07_changed_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');Path(r['master']).write_text('modified')
            with self.assertRaises(ValueError):check_records(r['files'])
    def test_08_duplicate_record_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house')
            with self.assertRaises(ValueError):check_records(r['files']*2)
    def test_09_master_must_be_registered(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['master']=str(Path(t)/'fake.prt')
            with self.assertRaises(ValueError):validate_component_result(r,'house')
    def test_10_pointer_requires_success(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');r['status']='FAILED'
            with self.assertRaises(ValueError):store_pointer(Path(t),r)
            self.assertFalse((Path(t)/POINTERS['house']).exists())
    def test_11_missing_pointer_clear_error(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(FileNotFoundError,'Zuerst passenden Erzeuger'):read_pointer(t,'house')
    def test_12_roundtrip_pointer(self):
        with tempfile.TemporaryDirectory() as t:
            r=fake_result(t,'house');store_pointer(t,r);self.assertEqual(read_pointer(t,'house')['master'],r['master'])
    def test_13_cause_diagnostics_preserved(self):
        inner=RuntimeError('inner');inner.nx_surface_check={'point':85}
        outer=RuntimeError('outer');outer.__cause__=inner
        self.assertEqual(child_exception_context(outer)['nx_surface_check']['point'],85)


class WorkflowTests(unittest.TestCase):
    def run_stub(self,t,mode='ALL',backend=None):
        cfg=copy.deepcopy(CONFIG);cfg['output_root']=str(Path(t)/'outputs')
        return run_project(t,mode,cfg,backend or StubBackend(),verify=False)
    def test_01_house_first_environment_then_assembly(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend();r=self.run_stub(t,backend=b)
            self.assertEqual([x[0] for x in b.calls],['preflight','house','environment','assemble'])
            self.assertEqual(r['phase'],'ABGESCHLOSSEN');self.assertFalse(r['DGM_POINT85_ROOT_CAUSE_FIXED'])
    def test_02_only_house_no_environment(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend();r=self.run_stub(t,'HOUSE',b)
            self.assertEqual([x[0] for x in b.calls],['preflight','house']);self.assertIsNone(r['environment'])
    def test_03_only_environment_no_house(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend();r=self.run_stub(t,'ENVIRONMENT',b)
            self.assertEqual([x[0] for x in b.calls],['preflight','environment']);self.assertIsNone(r['house'])
    def test_04_environment_failure_preserves_house(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend('environment')
            with self.assertRaises(RuntimeError) as cm:self.run_stub(t,backend=b)
            ctx=cm.exception.gesamt_g01_context
            self.assertTrue(Path(ctx['saved_house']).is_file())
            self.assertIsNone(ctx['saved_environment']);self.assertEqual(ctx['phase'],'UMGEBUNG_IMPORTIEREN_UND_PRUEFEN')
            self.assertTrue((Path(t)/POINTERS['house']).is_file());self.assertFalse((Path(t)/POINTERS['environment']).exists())
    def test_05_house_failure_no_environment(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend('house')
            with self.assertRaises(RuntimeError):self.run_stub(t,backend=b)
            self.assertNotIn(('environment',None),b.calls)
    def test_06_assembly_failure_keeps_both(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RuntimeError) as cm:self.run_stub(t,backend=StubBackend('assemble'))
            self.assertTrue(Path(cm.exception.gesamt_g01_context['saved_house']).is_file())
            self.assertTrue(Path(cm.exception.gesamt_g01_context['saved_environment']).is_file())
    def test_07_reuse_without_regeneration(self):
        with tempfile.TemporaryDirectory() as t:
            first=self.run_stub(t);b=StubBackend();r=self.run_stub(t,'ASSEMBLE',b)
            self.assertEqual([x[0] for x in b.calls],['preflight','assemble'])
            self.assertEqual(first['house']['master'],r['house']['master'])
    def test_08_edited_reuse_source_fails(self):
        with tempfile.TemporaryDirectory() as t:
            first=self.run_stub(t);Path(first['house']['master']).write_text('manual edit');b=StubBackend()
            with self.assertRaises(ValueError):self.run_stub(t,'ASSEMBLE',b)
            self.assertEqual(b.calls,[])
    def test_09_no_pointer_no_assembly(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend()
            with self.assertRaises(FileNotFoundError):self.run_stub(t,'ASSEMBLE',b)
            self.assertEqual(b.calls,[])
    def test_10_run_folders_unique(self):
        with tempfile.TemporaryDirectory() as t:
            a=self.run_stub(t,'HOUSE');b=self.run_stub(t,'HOUSE');self.assertNotEqual(a['output_directory'],b['output_directory'])
    def test_11_preflight_no_build(self):
        with tempfile.TemporaryDirectory() as t:
            b=StubBackend('preflight')
            with self.assertRaises(RuntimeError):self.run_stub(t,backend=b)
            self.assertEqual(len(b.calls),1)
    def test_12_invalid_mode_no_output(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):run_project(t,'UNKNOWN',CONFIG,StubBackend(),verify=False)
            self.assertEqual(list(Path(t).iterdir()),[])


class BackendTests(unittest.TestCase):
    def test_01_load_current_house_compiler(self):
        b=NXBackend(B);h=b.house_modules();d=read_json(B/'haus/data/haus.json')
        job=h.compiler.compile_house(d,True)
        self.assertEqual(sum(len(p['solids']) for p in job['parts']),1418)
        self.assertEqual(len(job['parts']),15)
        self.assertIn('BAL_TUER_HOEHE',d['parameters'])
    def test_02_environment_selection_preserved(self):
        b=NXBackend(B);e=b.environment_modules();job=read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')
        selected,_=e.selection.selected_job(B/'umgebung',job)
        self.assertEqual([p['id'] for p in selected['parts']],['DGM','V01','V02','V03','V05'])
        self.assertEqual(selected['total_sheets'],115)
    def test_03_house_preflight_never_loads_env(self):
        b=NXBackend(B,lambda:SimpleNamespace(Parts=[]))
        with patch.object(b,'environment_modules',side_effect=AssertionError('env called')):b.preflight('HOUSE',CONFIG)
    def test_04_env_preflight_never_loads_house(self):
        b=NXBackend(B,lambda:SimpleNamespace(Parts=[]))
        with patch.object(b,'house_modules',side_effect=AssertionError('house called')):b.preflight('ENVIRONMENT',CONFIG)
    def test_05_loaded_latest_house_conflict(self):
        b=NXBackend(B,lambda:SimpleNamespace(Parts=[SimpleNamespace(FullPath='/old/HAUS_MASTER.prt')]))
        with self.assertRaisesRegex(RuntimeError,'bereits geladen'):b.preflight('HOUSE',CONFIG)
    def test_06_loaded_environment_conflict(self):
        b=NXBackend(B,lambda:SimpleNamespace(Parts=[SimpleNamespace(FullPath='/old/01_GELAENDE_R09.prt')]))
        with self.assertRaisesRegex(RuntimeError,'bereits geladen'):b.preflight('ENVIRONMENT',CONFIG)
    def test_07_unrelated_part_not_closed(self):
        parts=[SimpleNamespace(FullPath='/users/other.prt')];b=NXBackend(B,lambda:SimpleNamespace(Parts=parts));b.preflight('HOUSE',CONFIG);self.assertEqual(len(parts),1)
    def test_08_module_switch_restores_current_house(self):
        b=NXBackend(B);b.house_modules();b.environment_modules();h=b.house_modules()
        self.assertIn('/haus/src/',str(h.runtime.__file__).replace('\\','/'))
    def test_09_bad_package_load_clear_error(self):
        with self.assertRaises(FileNotFoundError):load_package('should_not_exist',B/'absent')
    def test_10_all_original_utility_routes_no_depth(self):
        b=NXBackend(B);e=b.environment_modules();d=read_json(B/'haus/data/haus.json');review,_=e.utilities.load_review(B/'umgebung')
        d=e.utilities.decorate_house_data(d,review);d['site']['enabled']=True
        comp={'parts':[],'warnings':[],'coverage':[]};e.site.apply_site(d,comp)
        routes=[r for p in comp['parts'] if p['id']!='GRUNDSTUECK' for r in p['references']]
        self.assertEqual(len(routes),25);self.assertEqual(sum(len(r['points3d'])-1 for r in routes),45)
        self.assertTrue(all(r['z_mm'] is None for r in routes))
        self.assertTrue(all(p[2]==0 for r in routes for p in r['points3d']))
    def test_11_latest_house_and_old_env_disagree_is_explicit(self):
        old=read_json(B/'umgebung/basis/Haus_R06/data/haus.json');new=read_json(B/'haus/data/haus.json')
        self.assertNotEqual(new,old)
        source=(B/'gesamt/nx_backend.py').read_text();self.assertIn("house_builder=_reject_legacy_house",source);self.assertIn("cfg['build_house'] = False",source)
    def test_12_step_distance_query_not_silently_changed(self):
        source=(B/'umgebung/r09/nx_adapter.py').read_text()
        self.assertIn('0, body.Tag, 1, list(xyz), 0, [0.0, 0.0, 0.0]',source)
        self.assertIn('DGM_POINT85_ROOT_CAUSE_FIXED', (B/'gesamt/core.py').read_text())



class PackageTests(unittest.TestCase):
    def fixture(self,t):
        root=Path(t)
        content={'gesamt/a.py':'program','haus/data/haus.json':'{}','umgebung/model.step':'source',
                 'data/EINSTELLUNGEN_GESAMT.json':'{}'}
        for name,text in content.items():
            p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        write_json(root/'PAKETDATEIEN_SHA256.json',{'schema':'GESAMT_G01_FILES_V1',
                   'files':{name:sha256(root/name) for name in content}})
        return root
    def test_01_valid_package(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);self.assertEqual(verify_package(root)['checked_files'],4)
    def test_02_program_edit_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);(root/'gesamt/a.py').write_text('modified')
            with self.assertRaises(ValueError):verify_package(root)
    def test_03_house_input_edit_reported(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);(root/'haus/data/haus.json').write_text('{"changed":true}')
            self.assertEqual(len(verify_package(root)['editable_changes']),1)
    def test_04_missing_step_not_house_dependency(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);(root/'umgebung/model.step').unlink()
            self.assertEqual(verify_package(root,'HOUSE')['checked_files'],3)
            with self.assertRaises(FileNotFoundError):verify_package(root,'ALL')
    def test_05_missing_house_not_env_dependency(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);(root/'haus/data/haus.json').unlink()
            self.assertEqual(verify_package(root,'ENVIRONMENT')['checked_files'],3)
    def test_06_config_edit_allowed_but_traced(self):
        with tempfile.TemporaryDirectory() as t:
            root=self.fixture(t);(root/'data/EINSTELLUNGEN_GESAMT.json').write_text('{"surface_validation":"INTENSIV"}')
            r=verify_package(root)
            self.assertEqual(r['editable_changes'][0]['file'],'data/EINSTELLUNGEN_GESAMT.json')

if __name__=='__main__':unittest.main(verbosity=2)
