"""Offline tests of evidence validation; these are never an NX-run claim."""
from pathlib import Path
import hashlib
import tempfile
import unittest
import json
from unittest.mock import patch

try:
    from tools import nx_project as nx
except ImportError:
    nx = None


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(nx, 'Native evidence validator is not implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'master.prt').write_bytes(b'synthetic-test-only')
        self.record = {'path': 'master.prt', 'sha256': hashlib.sha256(b'synthetic-test-only').hexdigest(), 'bytes': 19}
        self.build = {'schema': 'HAUSPLAN_NX_BUILD_V1', 'status': 'PASS',
                      'source_fingerprint': 'a' * 64, 'master': 'master.prt',
                      'parts': [self.record], 'native_NX_run_completed': True}
        self.verify = {'schema': 'HAUSPLAN_NX_VERIFY_V1', 'status': 'PASS',
                       'source_fingerprint': 'a' * 64,
                       'reopen': {'status': 'PASS', 'parts': ['master.prt']},
                       'relocated': {'status': 'PASS', 'parts': ['master.prt']}}

    def check(self):
        return nx.validate_evidence(self.root, self.build, self.verify, 'a' * 64)

    def test_intact_evidence(self):
        self.assertEqual(self.check(), [])

    def test_changed_part_fails(self):
        (self.root / 'master.prt').write_bytes(b'changed')
        self.assertTrue(self.check())

    def test_missing_part_fails(self):
        (self.root / 'master.prt').unlink()
        self.assertTrue(self.check())

    def test_outside_path_fails(self):
        self.record['path'] = '../master.prt'
        self.assertTrue(self.check())

    def test_stale_source_fails(self):
        self.build['source_fingerprint'] = 'b' * 64
        self.assertTrue(self.check())

    def test_simulation_cannot_pass(self):
        self.build['native_NX_run_completed'] = False
        self.assertTrue(self.check())

    def test_missing_reopen_cannot_pass(self):
        self.verify['reopen'] = {'status': 'FAIL', 'parts': []}
        self.assertTrue(self.check())

    def test_relocation_must_load_all_parts(self):
        self.verify['relocated']['parts'] = []
        self.assertTrue(self.check())

    def test_master_must_be_listed(self):
        self.build['master'] = 'other.prt'
        self.assertTrue(self.check())

    def test_empty_build_fails(self):
        self.build['parts'] = []
        self.assertTrue(self.check())

    def test_case_collisions_fail(self):
        self.build['parts'].append(dict(self.record, path='MASTER.prt'))
        self.assertTrue(self.check())

    def test_unlisted_native_file_fails(self):
        (self.root / 'other.prt').write_bytes(b'untracked')
        self.assertTrue(self.check())

    def test_wrong_current_master_fails(self):
        repo = self.root / 'repo'
        target = repo / 'cad/nx/current'
        target.mkdir(parents=True)
        (target / 'master.prt').write_bytes(b'synthetic-test-only')
        nx.write(target / 'BUILD.json', self.build)
        nx.write(target / 'VERIFY.json', self.verify)
        nx.write(target.parent / 'CURRENT.json', {'directory': 'current', 'master': 'wrong.prt'})
        nx.write(target.parent / 'LAST_ATTEMPT.json', {'directory': 'current', 'status': 'PASS'})
        with patch.object(nx, 'ROOT', repo), patch.object(nx, 'source_fingerprint', return_value='a' * 64), \
                patch('sys.argv', ['nx_project.py', 'check']):
            self.assertEqual(nx.main(), 1)


class HeightConsentTests(unittest.TestCase):
    def test_real_g02_plan_uses_mode_not_descriptive_status(self):
        from tools.nx_build_journal import height_consent
        plan = {'mode': 'PLAN_ANNAHME', 'status': 'PLANANNAHME_KEIN_VERMESSENER_BESTAND'}
        self.assertTrue(height_consent(plan, True))
        self.assertFalse(height_consent(plan, False))

    def test_consent_does_not_cover_other_modes(self):
        from tools.nx_build_journal import height_consent
        with self.assertRaises(ValueError):
            height_consent({'mode': 'AUFMASSPUNKT', 'status': 'NUTZERANGABE'}, True)


class BuildPathTests(unittest.TestCase):
    def test_short_unique_native_workspace(self):
        self.assertTrue(hasattr(nx, 'generation_root'), 'Short native build workspace is missing')
        with tempfile.TemporaryDirectory() as temp:
            first = nx.generation_root(Path(temp))
            second = nx.generation_root(Path(temp))
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir())
            tail = 'G02_20261031_134526_a32354bc/umgebung/R09_20261031_134646_8ffa9c/funktionstest/.IMPORTPRUEFUNG_TEST_R11a_BASIS.json.e86a75a592e0422cad9890c38ec87ea6.tmp'
            self.assertLess(len(str(first / tail)), 250)

    def test_long_temporary_root_rejected_before_build(self):
        self.assertTrue(hasattr(nx, 'generation_root'), 'Short native build workspace is missing')
        with tempfile.TemporaryDirectory() as temp:
            long_root = Path(temp) / ('x' * 120)
            long_root.mkdir()
            with self.assertRaises(ValueError):
                nx.generation_root(long_root)
            self.assertEqual(list(long_root.iterdir()), [])


class AttemptTests(unittest.TestCase):
    def test_missing_nx_replaces_previous_success_with_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / 'cad/nx'
            directory.mkdir(parents=True)
            (directory / 'LAST_ATTEMPT.json').write_text(json.dumps({'status': 'PASS', 'directory': 'old'}))
            with patch.object(nx, 'ROOT', root):
                with self.assertRaises(FileNotFoundError):
                    nx.build_native(root / 'missing_nx', True)
            result = json.loads((directory / 'LAST_ATTEMPT.json').read_text())
            self.assertEqual(result['status'], 'FAIL')
            self.assertNotEqual(result['directory'], 'old')

    def test_transitive_generator_dependency_invalidates_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'projects/g02').mkdir(parents=True)
            (root / 'projects/g02/PAKETDATEIEN_SHA256.json').write_text('{"files": {}}')
            (root / 'tools').mkdir()
            for name in ('nx_project.py', 'nx_build_journal.py', 'nx_verify_journal.py', 'repo_support.py'):
                (root / 'tools' / name).write_text('first')
            with patch.object(nx, 'ROOT', root):
                before = nx.source_fingerprint()
                (root / 'tools/repo_support.py').write_text('changed')
                self.assertNotEqual(nx.source_fingerprint(), before)


if __name__ == '__main__':
    unittest.main()
