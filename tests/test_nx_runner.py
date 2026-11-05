"""Runner result contracts with subprocess boundary isolated, no fake NX claims."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from tools import run_checks


class NativeRunnerTests(unittest.TestCase):
    def test_annex_scope_requires_integrated_evidence_and_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            marker = root / 'renovierung/anbau/assumptions.json'
            marker.parent.mkdir(parents=True)
            marker.write_text('{}')
            commands = []

            def child(command, **kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0)

            with patch.object(run_checks, 'ROOT', root), patch('sys.argv', ['run_checks.py']), \
                    patch.object(run_checks.subprocess, 'run', side_effect=child):
                self.assertEqual(run_checks.main(), 0)
            self.assertTrue(any(str(root/'tools/nx_anbau.py') in c and 'check' in c for c in commands))
            self.assertTrue(any('test_anbau*.py' in c for c in commands))
            self.assertFalse(any(str(root/'tools/nx_master.py') in c for c in commands))

    def run_checks(self, extra, fail_native=False, fail_master=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def child(command, **kwargs):
                native = any(str(arg).endswith('nx_project.py') for arg in command)
                master = any(str(arg).endswith('nx_master.py') for arg in command)
                return subprocess.CompletedProcess(command, 1 if native and fail_native or master and fail_master else 0)

            with patch.object(run_checks, 'ROOT', root), patch('sys.argv', ['run_checks.py'] + extra), \
                    patch.object(run_checks.subprocess, 'run', side_effect=child):
                result = run_checks.main()
            report = json.loads(next((root / 'reports/local').glob('*/RESULT.json')).read_text())
            return result, report

    def test_default_requires_current_native_evidence(self):
        result, report = self.run_checks([])
        self.assertEqual(result, 0)
        self.assertIn('native_evidence', [row['name'] for row in report['checks']])

    def test_failed_native_evidence_fails_overall(self):
        result, report = self.run_checks([], fail_native=True)
        self.assertEqual(result, 1)
        self.assertEqual(report['status'], 'FAIL')

    def test_explicit_build_runs_before_evidence_validation(self):
        result, report = self.run_checks(['--nx', '--accept-model-assumptions'])
        names = [row['name'] for row in report['checks']]
        self.assertEqual(result, 0)
        self.assertLess(names.index('native_nx_build'), names.index('native_evidence'))

    def test_nx_flag_requires_model_assumption_acceptance(self):
        with self.assertRaises(SystemExit) as error:
            self.run_checks(['--nx'])
        self.assertEqual(error.exception.code, 2)

    def test_master_is_in_default_tests_and_native_evidence(self):
        result,report=self.run_checks([])
        self.assertEqual(result,0)
        names=[r['name'] for r in report['checks']]
        self.assertIn('m01_tests',names)
        self.assertIn('master_evidence',names)

    def test_master_evidence_failure_fails_project(self):
        result,report=self.run_checks([],fail_master=True)
        self.assertEqual(result,1)
        self.assertEqual(report['status'],'FAIL')

    def test_master_build_follows_study_build(self):
        result,report=self.run_checks(['--nx','--accept-model-assumptions'])
        self.assertEqual(result,0)
        names=[r['name'] for r in report['checks']]
        self.assertLess(names.index('native_nx_build'),names.index('master_nx_build'))
        self.assertLess(names.index('master_nx_build'),names.index('m01_tests'))
        self.assertLess(names.index('master_nx_build'),names.index('master_evidence'))


if __name__ == '__main__':
    unittest.main()
