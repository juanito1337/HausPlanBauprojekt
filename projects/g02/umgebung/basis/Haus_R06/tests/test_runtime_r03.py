# -*- coding: utf-8 -*-
"""R03-Regression: echte Dateipruefungen und simulierte NX-Aufrufablaeufe.
Kein NX-/Parasolid-Test. Testdouble-Dateien bleiben in TemporaryDirectory.
"""
import contextlib
import copy
import importlib.util
import io
import json
import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_runtime import (read_json,atomic_json,settings_checked,verify_output_paths,
    checked_part_filenames,verify_saved_files,input_fingerprint,sha256_file)
from haus2406_r03.haus_profile import profile_check,validate_compiled_profiles
from haus2406_r03.haus_geometry import Parameters
from haus2406_r03.haus_compile import compile_house
from haus2406_r03.haus_nx import NXAdapter
from haus2406_r03.haus_run import run_house,smoke_test,check_saved_house,build_solid,preflight_filenames,Log
from fake_nx import FakeNX,Point


class RuntimeFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def test_json_bom_supported(self):
        p=self.root/'x.json';p.write_text('\ufeff{"a":1}',encoding='utf-8');self.assertEqual(read_json(p),{'a':1})
    def test_duplicate_json_keys_rejected(self):
        p=self.root/'x.json';p.write_text('{"a":1,"a":2}')
        with self.assertRaisesRegex(ValueError,'Doppelter'):read_json(p)
    def test_json_nan_rejected(self):
        p=self.root/'x.json';p.write_text('{"a":NaN}')
        with self.assertRaises(ValueError):read_json(p)
    def test_json_infinity_rejected(self):
        p=self.root/'x.json';p.write_text('{"a":Infinity}')
        with self.assertRaises(ValueError):read_json(p)
    def test_json_missing_file_explained(self):
        with self.assertRaisesRegex(ValueError,'nicht lesbar'):read_json(self.root/'absent.json')
    def test_atomic_json_valid(self):
        p=self.root/'x.json';atomic_json(p,{'z':'Höhe'});self.assertEqual(read_json(p),{'z':'Höhe'})
        self.assertEqual([x.name for x in self.root.iterdir()],['x.json'])
    def test_atomic_json_keeps_old_on_serialization_failure(self):
        p=self.root/'x.json';atomic_json(p,{'old':1})
        with self.assertRaises(ValueError):atomic_json(p,{'invalid':math.nan})
        self.assertEqual(read_json(p),{'old':1})
    def test_false_as_string_cannot_enable_estimates(self):
        with self.assertRaisesRegex(ValueError,'kein Text'):settings_checked({'allow_estimates':'false'})
    def test_numbers_not_boolean_settings(self):
        with self.assertRaises(ValueError):settings_checked({'show_review_consent':1})
    def test_smoke_cannot_be_disabled(self):
        with self.assertRaises(ValueError):settings_checked({'automatic_smoke_test':False})
    def test_continue_on_error_rejected(self):
        with self.assertRaises(ValueError):settings_checked({'continue_on_feature_error':True})
    def test_settings_root_must_be_text(self):
        with self.assertRaises(ValueError):settings_checked({'output_root':42})
    def test_settings_array_rejected(self):
        with self.assertRaises(ValueError):settings_checked([])
    def test_part_path_traversal_rejected(self):
        with self.assertRaises(ValueError):checked_part_filenames(['../bad.prt'])
    def test_duplicate_part_case_rejected(self):
        with self.assertRaises(ValueError):checked_part_filenames(['EG.prt','eg.prt'])
    def test_reserved_windows_filename_rejected(self):
        with self.assertRaises(ValueError):checked_part_filenames(['CON.prt'])
    def test_reserved_windows_port_rejected(self):
        with self.assertRaises(ValueError):checked_part_filenames(['com1.prt'])
    def test_existing_part_protected(self):
        p=self.root/'USER.prt';p.write_text('USER_NOT_NX_TEST')
        with self.assertRaises(FileExistsError):verify_output_paths(self.root,['USER.prt'])
        self.assertEqual(p.read_text(),'USER_NOT_NX_TEST')
    def test_writability_probe_cleaned(self):
        verify_output_paths(self.root,['new.prt']);self.assertEqual(list(self.root.iterdir()),[])
    def test_long_path_diagnostic(self):
        p=self.root/('a'*210);p.mkdir()
        with self.assertRaisesRegex(ValueError,'230'):verify_output_paths(p,['HAUS_MASTER.prt'])
    def manifest(self):
        records=[]
        for name in ('EG.prt','HAUS_MASTER.prt'):
            p=self.root/name;p.write_bytes(b'TESTDOUBLE_NOT_A_REAL_NX_PART')
            records.append({'file':name,'bytes':p.stat().st_size,'bodies':0,'sha256':sha256_file(p)})
        return {'status':'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT','files':records,'component_count':1}
    def test_saved_files_valid(self):self.assertEqual(len(verify_saved_files(self.root,self.manifest())),2)
    def test_saved_files_missing(self):
        m=self.manifest();(self.root/'EG.prt').unlink()
        with self.assertRaises(FileNotFoundError):verify_saved_files(self.root,m)
    def test_saved_files_same_size_changed(self):
        m=self.manifest();p=self.root/'EG.prt';p.write_bytes(b'X'*p.stat().st_size)
        with self.assertRaisesRegex(ValueError,'SHA-256'):verify_saved_files(self.root,m)
    def test_saved_files_empty(self):
        m=self.manifest();(self.root/'EG.prt').write_bytes(b'')
        with self.assertRaises(FileNotFoundError):verify_saved_files(self.root,m)
    def test_partial_manifest_rejected(self):
        m=self.manifest();m['status']='ABGEBROCHEN'
        with self.assertRaises(ValueError):verify_saved_files(self.root,m)
    def test_no_master_manifest_rejected(self):
        m=self.manifest();m['files']=m['files'][:1]
        with self.assertRaises(ValueError):verify_saved_files(self.root,m)
    def test_double_manifest_file_rejected(self):
        m=self.manifest();m['files'].append(m['files'][0])
        with self.assertRaises(ValueError):verify_saved_files(self.root,m)
    def test_bootstrap_reports_missing_package(self):
        file=self.root/'RUN_HAUS_2406.py';shutil.copy2(BASE/file.name,file)
        spec=importlib.util.spec_from_file_location('entry_missing_test',str(file));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        with contextlib.redirect_stdout(io.StringIO()):r=mod.main()
        self.assertEqual(r['status'],'ABGEBROCHEN');self.assertIn('unvollstaendig',r['error']);self.assertTrue(Path(r['report_file']).is_file())
    def test_stdout_failure_does_not_stop_file_logger(self):
        logger=Log(self.root/'test.log')
        with patch('builtins.print',side_effect=OSError('NO_STDOUT')):logger('message')
        self.assertIn('message',(self.root/'test.log').read_text())


class ProfileTests(unittest.TestCase):
    def setUp(self):self.square=[[0,0,0],[10,0,0],[10,10,0],[0,10,0]]
    def test_xy_square(self):self.assertEqual(profile_check(self.square,[0,0,5])['area_mm2'],100)
    def test_sloped_square(self):
        pts=[[x,y,x*.5] for x,y,z in self.square];self.assertLess(profile_check(pts,[0,0,-1])['planarity_mm'],1e-8)
    def test_nonplanar_profile_rejected(self):
        self.square[-1][-1]=1
        with self.assertRaises(ValueError):profile_check(self.square,[0,0,1])
    def test_tangent_direction_rejected(self):
        with self.assertRaises(ValueError):profile_check(self.square,[1,0,0])
    def test_zero_direction_rejected(self):
        with self.assertRaises(ValueError):profile_check(self.square,[0,0,0])
    def test_nan_coordinate_rejected(self):
        self.square[0][0]=math.nan
        with self.assertRaises(ValueError):profile_check(self.square,[0,0,1])
    def test_duplicate_endpoint_rejected(self):
        with self.assertRaises(ValueError):profile_check(self.square+[self.square[0]],[0,0,1])
    def test_self_crossing_rejected(self):
        with self.assertRaises(ValueError):profile_check([self.square[i] for i in (0,2,1,3)],[0,0,1])
    def test_two_dimensional_point_rejected(self):
        with self.assertRaises(ValueError):profile_check([[0,0],[1,0],[0,1]],[0,0,1])
    def test_tiny_edge_rejected(self):
        with self.assertRaises(ValueError):profile_check([[0,0,0],[.001,0,0],[0,5,0]],[0,0,1])
    def test_all_1165_current_profiles(self):
        data=read_json(BASE/'data/haus.json');compiled=compile_house(data,True)
        report=validate_compiled_profiles(compiled,Parameters(data['parameters']))
        self.assertEqual(report['profile_count'],1165);self.assertGreater(report['minimum_edge_mm'],.3)


class AdapterDoubleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.fake=FakeNX();self.context=self.fake.install();self.context.start();self.addCleanup(self.context.stop)
        self.messages=[];self.nx=NXAdapter(self.messages.append)
        self.meta={'id':'T','status':'TEST','sources':[]}
    def part(self):return self.nx.new_part(self.root/'test.prt','TEST')
    def body(self,part):return self.nx.xy_extrude(part,[[0,0],[100,0],[100,20],[0,20]],0,200,'SOLID',self.meta)[0]
    def test_new_part_work_explicit(self):
        self.fake.new_display_leaves_work=True;p=self.part();self.assertIs(self.fake.session.Parts.Work,p)
    def test_foreign_part_cannot_be_written(self):
        foreign=self.fake.session.Parts.NewDisplay(self.root/'FOREIGN.prt',self.fake.N.Part.Units.Millimeters)
        with self.assertRaisesRegex(RuntimeError,'nicht von diesem Lauf'):self.nx.save(foreign)
        self.assertFalse((self.root/'FOREIGN.prt').exists())
    def test_foreign_target_rejected(self):
        p=self.part();q=self.nx.new_part(self.root/'q.prt','Q');b=self.body(q)
        with self.assertRaisesRegex(ValueError,'anderen Teil'):self.nx.xy_extrude(p,[[0,0],[10,0],[10,10],[0,10]],0,10,'CUT',self.meta,target=b)
    def test_wrong_work_part_corrected_before_feature(self):
        p=self.part();self.fake.session.Parts.Work=None;self.body(p);self.assertIs(self.fake.session.Parts.Work,p)
    def test_history_free_blocks(self):
        self.fake.history_free=True
        with self.assertRaisesRegex(RuntimeError,'History'):self.part()
    def test_managed_mode_blocks_before_parts(self):
        self.fake.managed=True
        with self.assertRaisesRegex(RuntimeError,'Teamcenter'):NXAdapter(self.messages.append)
        self.assertEqual(self.fake.session.Parts.items,[])
    def test_ambiguous_managed_mode_not_truthy_guess(self):
        self.fake.managed='False'
        with self.assertRaisesRegex(RuntimeError,'booleschen'):NXAdapter(self.messages.append)
    def test_missing_exact_api_reported(self):
        delattr(self.fake.uf,'ModlGeneral')
        with self.assertRaisesRegex(RuntimeError,'ModlGeneral'):NXAdapter(self.messages.append)
    def test_builder_success_cleanup(self):
        p=self.part();self.body(p);self.assertTrue(all(b.destroyed for b in self.fake.builders));self.assertFalse(self.fake.session.marks)
    def test_commit_failure_rolls_back_profile(self):
        p=self.part();self.fake.fail_commit_at=1
        with self.assertRaisesRegex(RuntimeError,'CommitFeature'):self.body(p)
        self.assertEqual(p.Bodies,[]);self.assertEqual(p.Curves.items,[]);self.assertFalse(self.fake.session.marks)
    def test_cleanup_error_preserves_original_commit_error(self):
        p=self.part();self.fake.fail_commit_at=1;self.fake.fail_destroy=True
        with self.assertRaisesRegex(RuntimeError,'INJECTED_COMMIT_ERROR'):self.body(p)
        self.assertTrue(any('Aufraeumfehler' in line for line in self.messages))
    def test_update_error_stops_and_undoes(self):
        p=self.part();self.fake.fail_update=True
        with self.assertRaisesRegex(RuntimeError,'DoUpdate'):self.body(p)
        self.assertEqual(p.Bodies,[])
    def test_sheet_body_rejected(self):
        p=self.part();self.fake.make_sheet=True
        with self.assertRaisesRegex(RuntimeError,'Flaechenkoerper'):self.body(p)
        self.assertEqual(p.Bodies,[])
    def test_save_status_disposed(self):
        p=self.part();self.body(p);r=self.nx.save(p);self.assertEqual(r['bodies'],1);self.assertTrue(self.fake.statuses[-1].disposed)
    def test_unsaved_status_is_error(self):
        p=self.part();self.fake.unsaved=1
        with self.assertRaisesRegex(RuntimeError,'nicht gespeicherte'):self.nx.save(p)
        self.assertTrue(self.fake.statuses[-1].disposed)
    def test_dispose_error_does_not_replace_save_error(self):
        p=self.part();self.fake.unsaved=1;self.fake.fail_dispose=True
        with self.assertRaisesRegex(RuntimeError,'nicht gespeicherte'):self.nx.save(p)
    def test_no_save_status_blocks(self):
        p=self.part();self.fake.none_save_status=True
        with self.assertRaisesRegex(RuntimeError,'keinen auswertbaren'):self.nx.save(p)
    def test_restore_original_display_and_different_work(self):
        a=self.fake.session.Parts.NewDisplay(self.root/'A.prt',self.fake.N.Part.Units.Millimeters);b=self.fake.session.Parts.NewDisplay(self.root/'B.prt',self.fake.N.Part.Units.Millimeters)
        self.fake.session.Parts.Display=a;self.fake.session.Parts.Work=b
        nx=NXAdapter(self.messages.append);nx.new_part(self.root/'NEW.prt','NEW');nx.restore_display_after_failure()
        self.assertIs(self.fake.session.Parts.Display,a);self.assertIs(self.fake.session.Parts.Work,b)
    def test_component_pose_rechecked(self):
        p=self.part();self.nx.save(p);master=self.nx.new_part(self.root/'master.prt','MASTER')
        child=self.nx.add_component(master,self.root/'test.prt','TEST');child.origin=Point(0,0,20)
        with self.assertRaisesRegex(RuntimeError,'Identitaetslage'):self.nx.check_identity(child)
    def test_unloaded_component_status_blocks(self):
        p=self.part();self.nx.save(p);master=self.nx.new_part(self.root/'master.prt','MASTER');self.fake.unloaded=1
        with self.assertRaisesRegex(RuntimeError,'Nicht geladene'):self.nx.add_component(master,self.root/'test.prt','TEST')
    def test_cycles_not_recursed_into_nx(self):
        p=self.part();params=Parameters({'A':{'formula':'B','unit':'mm'},'B':{'formula':'A','unit':'mm'}})
        with self.assertRaisesRegex(ValueError,'Zyklische'):self.nx.add_parameters(p,params)
    def test_reference_lines_cannot_write_foreign_part(self):
        foreign=self.fake.session.Parts.NewDisplay(self.root/'FOREIGN.prt',self.fake.N.Part.Units.Millimeters)
        with self.assertRaisesRegex(RuntimeError,'Schreibzugriff'):
            self.nx.lines(foreign,[[0,0,0],[10,0,0]],'FORBIDDEN',False)
        self.assertEqual(len(foreign.Curves.items),0)
    def test_unknown_unit_rejected_before_expression(self):
        p=self.part();params=Parameters({'A':{'value':1,'unit':'inch','status':'PLANWERT'}})
        with self.assertRaisesRegex(ValueError,'Einheit'):self.nx.add_parameters(p,params)
    def test_consent_only_explicit_yes(self):
        for answer in (2,-1,None,0):
            self.fake.answer=answer;self.assertFalse(self.nx.review_consent())
        self.fake.answer=1;self.assertTrue(self.nx.review_consent())


class OrchestrationDoubleTests(unittest.TestCase):
    """Alle NX-Interaktionen hier sind Testdoubles, KEINE realen NX-Laeufe."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
        shutil.copytree(BASE/'data',self.base/'data');shutil.copytree(BASE/'src',self.base/'src',ignore=shutil.ignore_patterns('__pycache__'))
        self.fake=FakeNX();self.context=self.fake.install();self.context.start();self.addCleanup(self.context.stop)
        self.output=io.StringIO();self.capture=contextlib.redirect_stdout(self.output);self.capture.__enter__();self.addCleanup(self.capture.__exit__,None,None,None)
    def test_full_1165_call_flow_with_smoke_and_checker(self):
        state=run_house(self.base)
        self.assertEqual(state['built_solids'],1165);self.assertEqual(state['component_count'],14)
        self.assertEqual(state['status'],'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT')
        self.assertEqual(sum(r['bodies'] for r in state['files']),1165)
        self.assertTrue(Path(state['smoke_test_directory']).is_dir())
        checked=check_saved_house(self.base)
        self.assertEqual(checked['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN')
        self.assertIn('WIEDEROEFFNUNG_NICHT_GETESTET',checked['reopen'])
        self.assertTrue(all(b.destroyed for b in self.fake.builders));self.assertFalse(self.fake.session.marks)
    def test_reference_mode_no_house_solids(self):
        self.fake.answer=2;state=run_house(self.base)
        self.assertEqual(state['built_solids'],0);self.assertEqual(sum(r['bodies'] for r in state['files']),0)
        self.assertEqual(state['mode'],'REFERENZGERUEST')
    def test_failed_smoke_prevents_house_and_success_pointer(self):
        self.fake.fail_commit_at=1
        with self.assertRaisesRegex(RuntimeError,'INJECTED_COMMIT_ERROR'):run_house(self.base)
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
        self.assertFalse(any(Path(p.FullPath).name=='HAUS_MASTER.prt' for p in self.fake.session.Parts))
        report=next((self.base/'ausgabe').glob('HAUS_*/manifest.json'))
        self.assertEqual(read_json(report)['status'],'ABGEBROCHEN_TEILMODELL_NICHT_FREIGEGEBEN')
    def test_smoke_repeat_does_not_clash_by_filename(self):
        first=smoke_test(self.base);second=smoke_test(self.base)
        self.assertNotEqual(first['geometry']['file'],second['geometry']['file'])
    def test_smoke_respects_configured_output_directory(self):
        settings=read_json(self.base/'data/einstellungen.json');settings['output_root']='custom_output'
        atomic_json(self.base/'data/einstellungen.json',settings)
        result=smoke_test(self.base);self.assertEqual(Path(result['output_directory']).parent,self.base/'custom_output')
    def test_smoke_all_house_parameters_and_actual_profiles(self):
        result=smoke_test(self.base)
        self.assertEqual(result['checks']['all_house_expressions'],'ERZEUGT')
        self.assertGreaterEqual(len(result['checks']['actual_house_profile_samples']),4)
    def test_existing_master_is_not_modified(self):
        original=self.fake.session.Parts.NewDisplay(self.base/'HAUS_MASTER.prt',self.fake.N.Part.Units.Millimeters)
        original.attrs['USER']='PRESERVE'
        with self.assertRaisesRegex(RuntimeError,'Gleichnamige'):run_house(self.base)
        self.assertEqual(original.attrs,{'USER':'PRESERVE'})
        self.assertFalse(Path(original.FullPath).exists())
    def test_checker_detects_missing_disk_part_even_when_loaded(self):
        state=run_house(self.base);out=Path(state['output_directory']);(out/state['files'][0]['file']).unlink()
        with self.assertRaises(FileNotFoundError):check_saved_house(self.base)
    def test_checker_detects_shifted_component(self):
        run_house(self.base);master=self.fake.session.Parts.Display;master.ComponentAssembly.children[0].origin.X=5
        with self.assertRaisesRegex(RuntimeError,'Identitaetslage'):check_saved_house(self.base)
    def test_checker_detects_duplicate_component_replacing_other(self):
        run_house(self.base);master=self.fake.session.Parts.Display
        master.ComponentAssembly.children[-1]=master.ComponentAssembly.children[0]
        with self.assertRaisesRegex(RuntimeError,'Doppelte Komponente'):check_saved_house(self.base)
    def test_checker_forces_full_load(self):
        run_house(self.base);master=self.fake.session.Parts.Display
        master.ComponentAssembly.children[1].Prototype.IsFullyLoaded=False
        self.assertEqual(check_saved_house(self.base)['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN')
        self.assertTrue(master.ComponentAssembly.children[1].Prototype.IsFullyLoaded)
    def test_second_house_run_safely_blocks_without_overwrite(self):
        first=run_house(self.base);out=Path(first['output_directory']);before=sha256_file(out/'HAUS_MASTER.prt')
        with self.assertRaisesRegex(RuntimeError,'Gleichnamige'):run_house(self.base)
        self.assertEqual(sha256_file(out/'HAUS_MASTER.prt'),before)

    def test_mid_house_failure_records_partial_and_no_success(self):
        original=build_solid;counter=[0]
        def failing(nx,part,solid,params):
            if Path(part.FullPath).name=='02_KELLER.prt':
                counter[0]+=1
                if counter[0]==5:raise RuntimeError('INJECTED_MID_HOUSE_ERROR')
            return original(nx,part,solid,params)
        with patch('haus2406_r03.haus_run.build_solid',side_effect=failing):
            with self.assertRaisesRegex(RuntimeError,'INJECTED_MID_HOUSE_ERROR'):run_house(self.base)
        report=read_json(next((self.base/'ausgabe').glob('HAUS_*/manifest.json')))
        self.assertEqual(report['built_solids'],4)
        self.assertTrue(report['current_object'])
        self.assertEqual(report['status'],'ABGEBROCHEN_TEILMODELL_NICHT_FREIGEGEBEN')
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
        self.assertFalse(any(Path(p.FullPath).name=='HAUS_MASTER.prt' for p in self.fake.session.Parts))
    def test_house_save_failure_not_reported_as_success(self):
        original=NXAdapter.save
        def failing(nx,part):
            if Path(part.FullPath).name=='02_KELLER.prt':raise RuntimeError('INJECTED_HOUSE_SAVE_ERROR')
            return original(nx,part)
        with patch.object(NXAdapter,'save',failing):
            with self.assertRaisesRegex(RuntimeError,'INJECTED_HOUSE_SAVE_ERROR'):run_house(self.base)
        report=read_json(next((self.base/'ausgabe').glob('HAUS_*/manifest.json')))
        self.assertEqual(report['status'],'ABGEBROCHEN_TEILMODELL_NICHT_FREIGEGEBEN')
        self.assertEqual([x['file'] for x in report['files']],['00_STEUERUNG.prt'])
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
    def test_input_change_during_smoke_prevents_build(self):
        original=smoke_test
        def changing(*args,**kwargs):
            result=original(*args,**kwargs)
            settings=read_json(self.base/'data/einstellungen.json');settings['note']='ALTERED_DURING_TEST'
            atomic_json(self.base/'data/einstellungen.json',settings)
            return result
        with patch('haus2406_r03.haus_run.smoke_test',side_effect=changing):
            with self.assertRaisesRegex(RuntimeError,'waehrend der Vorpruefung'):run_house(self.base)
        self.assertFalse(any(Path(p.FullPath).name=='00_STEUERUNG.prt' for p in self.fake.session.Parts))
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
    def test_runtime_revision_marker(self):
        import haus2406_r03
        self.assertEqual(haus2406_r03.__version__,'R03')
        self.assertEqual(read_json(self.base/'data/haus.json')['revision'],'R06')

if __name__=='__main__':unittest.main(verbosity=2)
