# -*- coding: utf-8 -*-
"""Start flow regression only. FakeNX is NOT an actual NX/Parasolid runtime."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from fake_nx import FakeNX

START='00_HAUS_ERZEUGEN_2406.py'
CHECK='CHECK_HAUS_2406.py'
POINTER='LETZTER_ERFOLGREICHER_LAUF.json'
BUILT='NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT'
CHECKED='DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN'


def load(base,name):
    spec=importlib.util.spec_from_file_location('_test_startfix_'+name.replace('.','_'),str(base/name))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StartSequenceTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.start=load(BASE,START);self.check=load(BASE,CHECK)
        context=contextlib.redirect_stdout(io.StringIO());context.__enter__()
        self.addCleanup(context.__exit__,None,None,None)

    def test_build_is_first_and_no_old_pointer_is_required(self):
        order=[]
        def build(base):
            self.assertFalse((base/POINTER).exists());order.append('build')
            (base/POINTER).write_text('{"generated_by_test":true}')
            return {'status':BUILT}
        def check(base):
            self.assertTrue((base/POINTER).exists());order.append('check')
            return {'status':CHECKED}
        progress={}
        result=self.start._build_then_check(self.base,build,check,progress)
        self.assertEqual(order,['build','check'])
        self.assertEqual(progress['phase'],'ABGESCHLOSSEN')
        self.assertEqual(result['verification']['status'],CHECKED)

    def test_build_exception_prevents_checker_and_pointer(self):
        checker=Mock();progress={}
        with self.assertRaisesRegex(RuntimeError,'MODEL_ERROR'):
            self.start._build_then_check(self.base,Mock(side_effect=RuntimeError('MODEL_ERROR')),checker,progress)
        checker.assert_not_called()
        self.assertFalse((self.base/POINTER).exists())
        self.assertEqual(progress['phase'],'FUNKTIONSTEST_UND_HAUSAUFBAU')

    def test_non_success_build_result_never_invokes_checker(self):
        for state in (None,{}, {'status':'ABGEBROCHEN'},{'status':'NX_FUNKTIONSTEST_BESTANDEN'}):
            with self.subTest(state=state):
                checker=Mock()
                with self.assertRaisesRegex(RuntimeError,'nicht erfolgreich'):
                    self.start._build_then_check(self.base,lambda p:state,checker,{})
                checker.assert_not_called()

    def test_check_failure_has_separate_phase(self):
        progress={}
        with self.assertRaisesRegex(RuntimeError,'HASH_ERROR'):
            self.start._build_then_check(self.base,lambda p:{'status':BUILT},Mock(side_effect=RuntimeError('HASH_ERROR')),progress)
        self.assertEqual(progress['phase'],'AUTOMATISCHE_NACHPRUEFUNG')

    def test_checker_must_actually_report_success(self):
        for state in (None,{}, {'status':'KEIN_GESPEICHERTER_MODELLLAUF'}):
            with self.subTest(state=state):
                with self.assertRaisesRegex(RuntimeError,'Nachpruefung'):
                    self.start._build_then_check(self.base,lambda p:{'status':BUILT},lambda p:state,{})

    def test_no_fabricated_pointer_even_if_build_returns_success(self):
        def checker(base):
            return json.loads((base/POINTER).read_text())
        with self.assertRaises(FileNotFoundError):
            self.start._build_then_check(self.base,lambda p:{'status':BUILT},checker,{})
        self.assertFalse((self.base/POINTER).exists())

    def test_missing_pointer_is_explicit_non_success_without_writing_files(self):
        checker=Mock()
        result=self.check._check_or_explain(self.base,checker)
        self.assertEqual(result['status'],'KEIN_GESPEICHERTER_MODELLLAUF')
        self.assertFalse(result['verification_started']);self.assertFalse(result['model_started'])
        checker.assert_not_called()
        self.assertIn(START,result['message'])
        self.assertEqual(list(self.base.iterdir()),[])

    def test_existing_pointer_delegates_to_original_checker(self):
        (self.base/POINTER).write_text('{}')
        checker=Mock(return_value={'sentinel':'ORIGINAL_CHECKER'})
        result=self.check._check_or_explain(self.base,checker)
        checker.assert_called_once_with(self.base)
        self.assertEqual(result['sentinel'],'ORIGINAL_CHECKER')

    def test_existing_corrupt_pointer_is_not_treated_as_missing(self):
        (self.base/POINTER).write_text('NOT JSON')
        with self.assertRaises(json.JSONDecodeError):
            self.check._check_or_explain(self.base,lambda p:json.loads((p/POINTER).read_text()))
        self.assertEqual((self.base/POINTER).read_text(),'NOT JSON')

    def test_access_denied_is_not_silently_ignored(self):
        with patch.object(Path,'stat',side_effect=PermissionError('ACCESS_DENIED')):
            with self.assertRaisesRegex(PermissionError,'ACCESS_DENIED'):
                self.check._check_or_explain(self.base,Mock())

    def test_new_entry_reports_incomplete_package(self):
        shutil.copy2(BASE/START,self.base/START)
        result=load(self.base,START).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['entry'],START)
        self.assertEqual(result['phase'],'STARTPRUEFUNG')
        self.assertIn('unvollstaendig',result['error'])
        self.assertTrue(Path(result['report_file']).is_file())


class NXSimulatedStartTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        shutil.copytree(BASE/'src',self.base/'src',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(BASE/'data',self.base/'data')
        for name in (START,CHECK):shutil.copy2(BASE/name,self.base/name)
        self.fake=FakeNX();installed=self.fake.install();installed.start();self.addCleanup(installed.stop)
        output=contextlib.redirect_stdout(io.StringIO());output.__enter__();self.addCleanup(output.__exit__,None,None,None)

    def test_full_1165_body_start_includes_checker_without_old_pointer(self):
        self.assertFalse((self.base/POINTER).exists())
        result=load(self.base,START).main()
        self.assertEqual(result['status'],'MODELL_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT')
        self.assertEqual(result['model']['built_solids'],1165)
        self.assertEqual(result['verification']['status'],CHECKED)
        self.assertEqual(result['model']['mode'],'PRUEFMODELL_MIT_NAEHERUNGEN')
        self.assertTrue((self.base/POINTER).is_file())
        self.assertEqual(self.fake.expression_attribute_attempts,0)

    def test_reference_mode_remains_explicit_and_path_resolve_is_never_needed(self):
        self.fake.answer=2
        with patch.object(Path,'resolve',side_effect=OSError(1005,'BLOCKED_RESOLVE')):
            result=load(self.base,START).main()
        self.assertEqual(result['status'],'MODELL_ERZEUGT_DATEI_UND_STRUKTUR_GEPRUEFT')
        self.assertEqual(result['model']['mode'],'REFERENZGERUEST')
        self.assertEqual(result['model']['built_solids'],0)
        self.assertEqual(result['verification']['status'],CHECKED)

    def test_failed_smoke_never_checks_an_old_successful_run(self):
        (self.base/POINTER).write_text('{"old_pointer":"DO_NOT_CHANGE"}')
        old=(self.base/POINTER).read_bytes()
        self.fake.fail_commit_at=1
        result=load(self.base,START).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['phase'],'FUNKTIONSTEST_UND_HAUSAUFBAU')
        self.assertIn('INJECTED_COMMIT_ERROR',result['error'])
        self.assertEqual((self.base/POINTER).read_bytes(),old)
        self.assertFalse(list((self.base/'ausgabe').rglob('pruefung_*.json')))
        report=json.loads(Path(result['report_file']).read_text())
        self.assertEqual(report['entry'],START)

    def test_check_entry_no_success_pointer_has_no_model_side_effects(self):
        result=load(self.base,CHECK).main()
        self.assertEqual(result['status'],'KEIN_GESPEICHERTER_MODELLLAUF')
        self.assertFalse((self.base/'ausgabe').exists())
        self.assertFalse((self.base/'fehlerberichte').exists())
        self.assertFalse(self.fake.session.Parts.items)

    def test_check_entry_existing_invalid_json_still_is_failure(self):
        (self.base/POINTER).write_text('BROKEN')
        result=load(self.base,CHECK).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('nicht lesbar',result['error'])
        self.assertTrue(Path(result['report_file']).exists())
        self.assertFalse(self.fake.session.Parts.items)

    def test_mixed_project_patch_is_rejected_before_creation(self):
        (self.base/'src/haus2406_r03/__init__.py').write_text('__patch__="R03b-EINHEITENFIX"\n')
        result=load(self.base,START).main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('Versionen vermischt',result['error'])
        self.assertFalse(self.fake.session.Parts.items)


if __name__=='__main__':unittest.main(verbosity=2)
