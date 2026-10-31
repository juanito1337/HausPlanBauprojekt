# -*- coding: utf-8 -*-
"""Regression fuer den gemeldeten WinError 1005 im Projektpfad.

Fehler werden injiziert. Kein Windows-Laufwerk, keine NX-/Parasolid-Laufzeit.
Windows-Pfadformen werden rein lexikalisch mit ntpath/PureWindowsPath geprueft.
"""
import ast
import contextlib
import importlib.util
import io
import ntpath
import os
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

BASE=Path(os.path.abspath(__file__)).parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_runtime import (absolute_path,path_key,verify_output_paths,
    verify_saved_files,sha256_file,read_json,atomic_json)
from haus2406_r03.haus_run import output_directory
from fake_nx import FakeNX

ENTRIES=('RUN_HAUS_2406.py','SMOKE_TEST_2406.py','CHECK_HAUS_2406.py')


def volume_error():
    error=OSError(1005,'INJECTED: Auf dem Datentraeger befindet sich kein erkanntes Dateisystem.')
    error.winerror=1005
    return error


def load_entry(path):
    spec=importlib.util.spec_from_file_location('pathfix_'+Path(path).stem,str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def blocked_resolvers():
    """Jeder verbliebene Resolveraufruf wuerde den Originalfehler ausloesen."""
    with patch.object(Path,'resolve',side_effect=volume_error()), \
         patch('os.path.realpath',side_effect=volume_error()):
        yield


class PathFixLexicalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_old_expression_reproduces_injected_1005(self):
        with blocked_resolvers(), self.assertRaises(OSError) as raised:
            Path(__file__).resolve().parent
        self.assertEqual(raised.exception.winerror,1005)

    def test_absolute_path_does_not_query_final_path(self):
        target=self.root/'Plan Haus'/'Datei.prt'
        with blocked_resolvers():
            self.assertEqual(absolute_path(target),target)

    def test_relative_path_is_absolutized_without_resolve(self):
        with blocked_resolvers():
            result=absolute_path('Projekt/data/../src')
        self.assertEqual(result,Path(os.path.abspath('Projekt/src')))

    def test_nonexistent_path_remains_path_not_success_claim(self):
        with blocked_resolvers():
            result=absolute_path(self.root/'NICHT_VORHANDEN')
        self.assertFalse(result.exists())

    def test_empty_path_is_rejected(self):
        with self.assertRaises(ValueError):absolute_path('')

    def test_nul_path_is_rejected(self):
        with self.assertRaises(ValueError):absolute_path('abc\0def')

    def test_bytes_path_is_rejected(self):
        with self.assertRaises(TypeError):absolute_path(b'abc')

    def test_path_key_spaces_and_case_without_filesystem(self):
        with blocked_resolvers(),patch.object(Path,'stat',side_effect=AssertionError('NO_STAT')):
            self.assertEqual(path_key(self.root/'Plan Haus'/'HAUS.PRT'),
                             path_key(self.root/'plan haus'/'haus.prt'))

    def test_path_key_different_folders_are_not_equated(self):
        with blocked_resolvers():
            self.assertNotEqual(path_key(self.root/'A'/'EG.prt'),path_key(self.root/'B'/'EG.prt'))

    def test_existing_part_still_protected_when_resolve_fails(self):
        file=self.root/'USER.prt';file.write_bytes(b'USER_BYTES')
        with blocked_resolvers(),self.assertRaises(FileExistsError):
            verify_output_paths(self.root,['USER.prt'])
        self.assertEqual(file.read_bytes(),b'USER_BYTES')

    def test_write_probe_works_and_is_removed_when_resolve_fails(self):
        with blocked_resolvers():self.assertTrue(verify_output_paths(self.root,['NEU.prt']))
        self.assertEqual(list(self.root.iterdir()),[])

    def test_write_probe_failure_is_not_hidden(self):
        with blocked_resolvers(),patch('haus2406_r03.haus_runtime.tempfile.NamedTemporaryFile',
                    side_effect=PermissionError('WRITE_DENIED')), self.assertRaises(PermissionError):
            verify_output_paths(self.root,['NEU.prt'])

    def test_hash_verification_still_runs_when_resolve_fails(self):
        records=[]
        for name in ('EG.prt','HAUS_MASTER.prt'):
            file=self.root/name;file.write_bytes(b'TESTDOUBLE_NOT_A_REAL_NX_PART')
            records.append({'file':name,'bytes':file.stat().st_size,'sha256':sha256_file(file)})
        manifest={'status':'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT','files':records,'component_count':1}
        with blocked_resolvers():self.assertEqual(len(verify_saved_files(self.root,manifest)),2)
        (self.root/'EG.prt').write_bytes(b'X'*records[0]['bytes'])
        with blocked_resolvers(),self.assertRaisesRegex(ValueError,'SHA-256'):
            verify_saved_files(self.root,manifest)

    def test_output_directory_is_unique_absolute_without_resolve(self):
        base=self.root/'Plan Haus';base.mkdir()
        with blocked_resolvers():
            one=output_directory(base,{},'TEST');two=output_directory(base,{},'TEST')
        self.assertNotEqual(one,two);self.assertTrue(one.is_absolute())
        self.assertEqual(one.parent,base/'ausgabe')

    def test_active_source_has_no_resolve_or_realpath_call(self):
        files=list((BASE/'src').rglob('*.py'))+list(BASE.glob('*.py'))
        found=[]
        for file in files:
            tree=ast.parse(file.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                    if node.func.attr in ('resolve','realpath','_getfinalpathname'):
                        found.append(str(file.relative_to(BASE))+':'+str(node.lineno))
        self.assertEqual(found,[])


class PathFixBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def _windows_base(self,name,filename):
        entry=load_entry(BASE/name)
        with patch.object(entry,'__file__',filename),patch.object(entry,'Path',PureWindowsPath),\
             patch.object(entry,'os',types.SimpleNamespace(path=ntpath)),\
             patch.object(ntpath,'realpath',side_effect=volume_error()):
            return entry._project_base()

    def test_reported_mapped_drive_with_spaces_all_entries(self):
        for name in ENTRIES:
            with self.subTest(entry=name):
                self.assertEqual(self._windows_base(name,'W:\\Plan Haus\\Haus_NX2406_Projekt_R03a\\'+name),
                                 PureWindowsPath('W:/Plan Haus/Haus_NX2406_Projekt_R03a'))

    def test_unc_path_is_preserved(self):
        self.assertEqual(self._windows_base(ENTRIES[0],'\\\\server\\share\\Plan Haus\\'+ENTRIES[0]),
                         PureWindowsPath('//server/share/Plan Haus'))

    def test_local_unicode_path_is_preserved(self):
        self.assertEqual(self._windows_base(ENTRIES[0],'C:\\Benutzer\\Jörg\\Haus\\'+ENTRIES[0]),
                         PureWindowsPath('C:/Benutzer/Jörg/Haus'))

    def test_windows_forward_slashes_are_accepted(self):
        self.assertEqual(self._windows_base(ENTRIES[0],'W:/Plan Haus/Projekt/'+ENTRIES[0]),
                         PureWindowsPath('W:/Plan Haus/Projekt'))

    def test_missing_package_report_survives_original_path_error_all_entries(self):
        for name in ENTRIES:
            with self.subTest(entry=name):
                path=self.root/name;shutil.copy2(BASE/name,path);entry=load_entry(path)
                with blocked_resolvers(),contextlib.redirect_stdout(io.StringIO()):result=entry.main()
                self.assertEqual(result['status'],'ABGEBROCHEN')
                self.assertIn('unvollstaendig',result['error'])
                self.assertEqual(result['patch'],'R06-QUELLEN-KONSISTENZ')
                self.assertEqual(Path(result['report_file']).parent,self.root/'fehlerberichte')


class PathFixFlowDoubleTests(unittest.TestCase):
    """Simulierte NX-Antworten. Keine Aussagen ueber echte NX-API-Signaturen."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'Plan Haus';self.base.mkdir()
        shutil.copytree(BASE/'data',self.base/'data')
        shutil.copytree(BASE/'src',self.base/'src',ignore=shutil.ignore_patterns('__pycache__'))
        for name in ENTRIES:shutil.copy2(BASE/name,self.base/name)
        self.fake=FakeNX();self.context=self.fake.install();self.context.start();self.addCleanup(self.context.stop)
        self.buffer=io.StringIO();self.output=contextlib.redirect_stdout(self.buffer)
        self.output.__enter__();self.addCleanup(self.output.__exit__,None,None,None)

    def test_all_three_entrypoints_and_1165_workflow_with_resolvers_blocked(self):
        smoke=load_entry(self.base/'SMOKE_TEST_2406.py')
        main=load_entry(self.base/'RUN_HAUS_2406.py')
        check=load_entry(self.base/'CHECK_HAUS_2406.py')
        with blocked_resolvers():
            result=smoke.main()
            self.assertEqual(result['status'],'NX_FUNKTIONSTEST_BESTANDEN',result.get('error'))
            state=main.main()
            self.assertEqual(state['status'],'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT',state.get('error'))
            self.assertEqual(state['built_solids'],1165)
            self.assertEqual(state['component_count'],14)
            self.assertEqual(state['patch'],'R06-QUELLEN-KONSISTENZ')
            checked=check.main()
            self.assertEqual(checked['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN',checked.get('error'))
        self.assertFalse((self.base/'fehlerberichte').exists())

    def test_actual_read_error_1005_remains_an_abort_not_success(self):
        entry=load_entry(self.base/'RUN_HAUS_2406.py')
        original=Path.read_text
        def broken(path,*args,**kwargs):
            if path==self.base/'data/haus.json':raise volume_error()
            return original(path,*args,**kwargs)
        with blocked_resolvers(),patch.object(Path,'read_text',broken):result=entry.main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('nicht lesbar',result['error'])
        self.assertIn('1005',result['error'])
        self.assertTrue(Path(result['report_file']).is_file())
        self.assertFalse(self.fake.session.Parts.items)

    def test_mixed_original_package_is_rejected(self):
        (self.base/'src/haus2406_r03/__init__.py').write_text('__version__ = "R03"\n',encoding='utf-8')
        entry=load_entry(self.base/'RUN_HAUS_2406.py')
        with blocked_resolvers():result=entry.main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('Versionen vermischt',result['error'])
        self.assertFalse(self.fake.session.Parts.items)


if __name__=='__main__':unittest.main(verbosity=2)
