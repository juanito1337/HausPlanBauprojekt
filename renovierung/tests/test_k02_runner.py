"""Offline evidence tests; synthetic files never constitute native NX evidence."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
try:
    from renovierung.k02 import runner
except ImportError:
    runner = None


class StudyEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runner, 'K02 runner missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'cad/nx/k02/run'
        self.directory.mkdir(parents=True)
        (self.directory / 'a.prt').write_bytes(b'synthetic')
        self.part = {'path': 'a.prt', 'bytes': 9, 'sha256': hashlib.sha256(b'synthetic').hexdigest()}
        state = {'id': 'BASE', 'master': 'a.prt', 'parts': [self.part], 'measurements': {}, 'transforms': []}
        self.build = {'schema': 'K02_NATIVE_BUILD_V1', 'status': 'PASS', 'native_NX_run_completed': True,
                      'source_fingerprint': 'current', 'states': [state], 'candidate_ids': [],
                      'delivered_field_ids': [], 'complete_study': True, 'construction_release': False}
        phase = {'status': 'PASS', 'parts': ['a.prt'], 'master': 'a.prt', 'transforms': [], 'measurements': {}}
        self.verify = {'schema': 'K02_NATIVE_VERIFY_V1', 'status': 'PASS', 'source_fingerprint': 'current',
                       'states': {'BASE': {'reopen': copy.deepcopy(phase), 'relocated': copy.deepcopy(phase)}}}

    def check(self):
        return runner.validate_evidence(self.directory, self.build, self.verify, 'current')

    def test_intact(self):
        self.assertEqual(self.check(), [])

    def test_stale_inputs(self):
        self.build['source_fingerprint'] = 'old'
        self.assertTrue(self.check())

    def test_missing_or_malformed_parts(self):
        for record in ({'path': '../outside.prt'}, {}, {'path': 'missing.prt', 'sha256': '', 'bytes': 1}):
            with self.subTest(record=record):
                self.build['states'][0]['parts'] = [record]
                self.assertTrue(self.check())

    def test_master_mismatch(self):
        self.verify['states']['BASE']['reopen']['master'] = 'wrong.prt'
        self.assertTrue(self.check())

    def test_transforms_mismatch(self):
        self.verify['states']['BASE']['relocated']['transforms'] = [{'translation': [0, 0, 10]}]
        self.assertTrue(self.check())

    def test_partial_delivery_cannot_pass(self):
        self.build['candidate_ids'] = ['PS01-F01']
        self.assertTrue(self.check())

    def test_simulated_result_cannot_pass(self):
        self.build['native_NX_run_completed'] = False
        self.assertTrue(self.check())

    def test_latest_failed_attempt_blocks_older_success(self):
        runner.write(self.directory / 'BUILD.json', self.build)
        runner.write(self.directory / 'VERIFY.json', self.verify)
        runner.write(self.directory.parent / 'CURRENT.json', {'directory': 'run', 'masters': {'BASE': 'a.prt'}})
        runner.write(self.directory.parent / 'LAST_ATTEMPT.json', {'status': 'FAIL', 'directory': 'new'})
        with patch.object(runner, 'ROOT', self.root):
            self.assertTrue(runner.check_study())

    def test_wrong_pointer_fails(self):
        runner.write(self.directory / 'BUILD.json', self.build)
        runner.write(self.directory / 'VERIFY.json', self.verify)
        runner.write(self.directory.parent / 'CURRENT.json', {'directory': 'run', 'masters': {'BASE': 'wrong.prt'}})
        runner.write(self.directory.parent / 'LAST_ATTEMPT.json', {'status': 'PASS', 'directory': 'run'})
        with patch.object(runner, 'ROOT', self.root), patch.object(runner, 'source_fingerprint', return_value='current'):
            self.assertTrue(runner.check_study())

    def test_measurement_rejects_missing_component(self):
        self.assertTrue(hasattr(runner, 'validate_measurement'))
        with self.assertRaises(ValueError):
            runner.validate_measurement({'body_count': 2, 'component_volumes_m3': [1, 2]}, [1, 2, 3])

    def test_measurement_accepts_three_components_unordered(self):
        self.assertTrue(hasattr(runner, 'validate_measurement'))
        runner.validate_measurement({'body_count': 3, 'component_volumes_m3': [3, 1, 2]}, [1, 2, 3])

    def test_non_object_manifest_fails_closed(self):
        self.assertTrue(runner.validate_evidence(self.directory, [], self.verify, 'current'))

    def test_changed_native_measurement_fails(self):
        self.build['states'][0]['measurements'] = {'excavation': {'body_count': 1, 'component_volumes_m3': [1.0]}}
        self.verify['states']['BASE']['reopen']['measurements'] = {'excavation': {'body_count': 1, 'component_volumes_m3': [2.0]}}
        self.assertTrue(self.check())

    def test_nan_native_measurement_fails(self):
        with self.assertRaises(ValueError):
            runner.validate_measurement({'body_count': 1, 'component_volumes_m3': [float('nan')]}, [1.0])

    def test_unlisted_native_file_fails(self):
        (self.directory/'extra.prt').write_bytes(b'extra')
        self.assertTrue(self.check())

    def test_role_names_survive_nx_uppercase_after_save(self):
        from renovierung.k02 import nx_verify
        self.assertTrue(hasattr(nx_verify, 'body_role'), 'Saved body role normalization missing')
        for name, expected in [('K02_EXCAVATION_00','excavation'), ('K02_CUT_SOIL_00','cut_soil'),
                               ('K02_PILE_MAIN_00','pile_main'), ('K02_PILE_RESERVE_00','pile_reserve'),
                               ('K02_excavation_00','excavation'), ('SOURCE_BODY',None)]:
            with self.subTest(name=name):
                self.assertEqual(nx_verify.body_role(name), expected)


if __name__ == '__main__':
    unittest.main()
