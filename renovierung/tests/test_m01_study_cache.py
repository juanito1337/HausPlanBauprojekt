"""Pure signature tests; no simulated native success."""
import importlib.util
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest


class SignatureTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).resolve().parents[1]/'m01/study_cache.py'
        if not path.is_file():
            self.fail('Temporary study-cache helper is missing')
        spec = importlib.util.spec_from_file_location('m02_study_cache', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)

    def test_boundary_signature_ignores_face_edge_iteration_and_direction(self):
        face = [[[0, 0, 0], [1, 0, 0]], [[1, 0, 0], [0, 1, 0]], [[0, 1, 0], [0, 0, 0]]]
        self.assertEqual(self.module.boundary_signature([face]),
                         self.module.boundary_signature([[list(reversed(edge)) for edge in reversed(face)]]))

    def test_absolute_translation_or_changed_boundary_cannot_share_signature(self):
        a = [[[[0, 0, 0], [1, 0, 0]]]]
        b = [[[[10, 0, 0], [11, 0, 0]]]]
        self.assertNotEqual(self.module.boundary_signature(a), self.module.boundary_signature(b))
        with self.assertRaises(ValueError):
            self.module.boundary_signature([[[[0, 0, float('nan')], [1, 0, 0]]]])


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        SignatureTests.setUp(self)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.old, self.new = '20261104T194735Z_c5086e', '20261104T230000Z_abcdef'
        self.scratch = self.repo / 'reports/local/m01' / self.old
        self.delivery = self.repo / 'cad/nx/m01' / self.old
        self.target = self.repo / 'cad/nx/m01' / self.new
        self.scratch.mkdir(parents=True)
        self.target.mkdir(parents=True)
        fid, file = 'PS01-F01', 'studien/PS01-F01_STUDY.prt'
        self.original = self.repo / 'cad/nx/k02/verified/PS01-F01/PS01-F01_STUDY.prt'
        self.original.parent.mkdir(parents=True)
        self.original.write_bytes(b'synthetic genuine-baseline bytes')
        roles = ('cut_soil', 'excavation', 'pile_main', 'pile_reserve')
        self.layout = {'fields': [{'id': fid, 'native': True, 'node_id': 'FIELD_' + fid, 'study_file': file}],
                       'nodes': [{'id': 'R_' + r, 'parent': 'FIELD_' + fid, 'kind': 'role', 'role': r,
                                  'file': file, 'reference_set': 'M01_' + r.upper()} for r in roles],
                       'sources': [{'file': file, 'source': self.original.relative_to(self.repo).as_posix(),
                                    'bytes': self.original.stat().st_size,
                                    'sha256': hashlib.sha256(self.original.read_bytes()).hexdigest()}],
                       'presentation': {'scale': 0.005}}
        self.part = self.delivery / file
        self.part.parent.mkdir(parents=True)
        self.part.write_bytes(b'synthetic completed A candidate, no native claim')
        oldstep = self.scratch / 'pile_steps/PS01-F01.step'
        self.newstep = self.repo / 'reports/local/m01' / self.new / 'pile_steps/PS01-F01.step'
        for p in (oldstep, self.newstep):
            p.parent.mkdir(parents=True)
            p.write_bytes(b'checked combined STEP bytes')
        request = {'mode': 'build', 'load_method': 'AsSaved', 'repo_root': str(self.repo),
                   'directory': str(self.delivery), 'report': str(self.scratch / 'build_result.json'),
                   'layout': copy.deepcopy(self.layout), 'pile_steps': {fid: str(oldstep)}}
        (self.scratch / 'build_request.json').write_text(json.dumps(request))
        (self.scratch / 'build_result.json').write_text(json.dumps({'status': 'FAIL'}))
        self.inventory = self.module.capture_inventory(self.repo, self.old)

    def prepare(self):
        return self.module.prepare_study_cache(self.repo, self.old, self.target, self.layout,
                                              {'PS01-F01': str(self.newstep)}, self.inventory)

    def test_documented_candidate_copied_with_step_k02_and_contract_provenance(self):
        record = self.prepare()['PS01-F01']
        self.assertEqual((self.target / record['file']).read_bytes(), self.part.read_bytes())
        self.assertEqual(record['sha256'], self.inventory['parts']['PS01-F01']['sha256'])
        self.assertEqual(record['source_run'], self.old)
        self.assertEqual(record['k02_sha256'], hashlib.sha256(self.original.read_bytes()).hexdigest())

    def test_changed_refset_or_presentation_or_step_is_cold(self):
        original = copy.deepcopy(self.layout)
        self.layout['nodes'][0]['reference_set'] = 'M01_WRONG'
        self.assertEqual(self.prepare(), {})
        self.layout = copy.deepcopy(original)
        self.layout['presentation']['scale'] = 0.01
        self.assertEqual(self.prepare(), {})
        self.layout = original
        self.newstep.write_bytes(b'changed STEP')
        self.assertEqual(self.prepare(), {})
        self.assertEqual(list(self.target.rglob('*.prt')), [])

    def test_existing_destination_never_overwritten_and_k02_change_is_hard_error(self):
        target = self.target / 'studien/PS01-F01_STUDY.prt'
        target.parent.mkdir()
        target.write_bytes(b'user-owned bytes')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(target.read_bytes(), b'user-owned bytes')
        self.original.write_bytes(b'changed original')
        with self.assertRaises(ValueError):
            self.prepare()

    def test_running_source_without_terminal_proof_is_rejected(self):
        (self.scratch / 'build_result.json').unlink()
        with self.assertRaises(ValueError):
            self.module.capture_inventory(self.repo, self.old)

    def test_unprocessed_raw_k02_copy_is_not_an_a_study_candidate(self):
        self.part.write_bytes(self.original.read_bytes())
        self.assertEqual(self.module.capture_inventory(self.repo, self.old)['parts'], {})


if __name__ == '__main__':
    unittest.main()
