"""Candidate-cache tests use synthetic bytes; they claim no native NX validation."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'm01/context_cache.py'


class CacheTests(unittest.TestCase):
    def setUp(self):
        if not MODULE.is_file():
            self.fail('The optional context-cache proposal is missing')
        spec = importlib.util.spec_from_file_location('context_cache_proposal', MODULE)
        self.cache = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cache)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.old = '20261104T010000Z_abcdef'
        self.new = '20261104T020000Z_123456'
        self.scratch = self.repo / 'reports/local/m01' / self.old
        self.source = self.repo / 'cad/nx/m01' / self.old
        self.target = self.repo / 'cad/nx/m01' / self.new
        self.scratch.mkdir(parents=True)
        self.target.mkdir(parents=True)
        self.source.mkdir(parents=True)
        group = {'id': 'CONTEXT_000', 'file': 'kontext/CONTEXT_000.prt', 'exclude_for': [],
                 'body_count': 1, 'component_volumes_m3': [2.0], 'volume_m3': 2.0}
        node = {'id': 'CONTEXT_000', 'file': group['file'], 'kind': 'context',
                'parent': 'SITE_CONTEXT', 'blank': False, 'metadata': copy.deepcopy(group)}
        self.layout = {'nodes': [node], 'context': {'groups': [group]}, 'presentation': {'scale': 0.005}}
        self.oldstep = self.scratch / 'context_steps/CONTEXT_000.step'
        self.oldstep.parent.mkdir()
        self.oldstep.write_bytes(b'identical STEP')
        self.newstep = self.repo / 'reports/local/m01' / self.new / 'context_steps/CONTEXT_000.step'
        self.newstep.parent.mkdir(parents=True)
        self.newstep.write_bytes(b'identical STEP')
        self.steps = {'CONTEXT_000': str(self.newstep)}
        self.prt = self.source / group['file']
        self.prt.parent.mkdir()
        self.prt.write_bytes(b'synthetic candidate PRT bytes, not native evidence')
        self.request = {'mode': 'build', 'repo_root': str(self.repo), 'directory': str(self.source),
                        'report': str(self.scratch / 'build_result.json'), 'load_method': 'AsSaved',
                        'layout': copy.deepcopy(self.layout), 'context_steps': {'CONTEXT_000': str(self.oldstep)}}
        self.write_request()
        (self.scratch / 'build_result.json').write_text(json.dumps({'status': 'FAIL'}))

    def write_request(self):
        (self.scratch / 'build_request.json').write_text(json.dumps(self.request), encoding='utf-8')

    def prepare(self):
        return self.cache.prepare_context_cache(self.repo, self.old, self.target, self.layout, self.steps)

    def test_explicit_failed_prior_run_yields_candidate_copy_and_exact_provenance(self):
        before = self.prt.read_bytes()
        records = self.prepare()
        self.assertEqual(set(records), {'CONTEXT_000'})
        record = records['CONTEXT_000']
        self.assertEqual(set(record), {'file', 'bytes', 'sha256', 'step_sha256', 'source_run'})
        self.assertEqual(record['source_run'], self.old)
        self.assertEqual(record['file'], 'kontext/CONTEXT_000.prt')
        self.assertEqual((self.target / record['file']).read_bytes(), before)
        self.assertEqual(self.prt.read_bytes(), before)
        self.assertEqual(record['bytes'], len(before))
        self.assertEqual(record['sha256'], '10ea7d0f956789d4096c6ceb12698d94fe86a2bb3d4b25a1f6efc9f2dd11b460')

    def test_missing_part_or_changed_step_or_changed_node_is_a_cold_import(self):
        original = self.prt.read_bytes()
        self.prt.unlink()
        self.assertEqual(self.prepare(), {})
        self.prt.write_bytes(original)
        self.newstep.write_bytes(b'changed STEP')
        self.assertEqual(self.prepare(), {})
        self.newstep.write_bytes(b'identical STEP')
        self.layout['nodes'][0]['name'] = 'changed native node'
        self.assertEqual(self.prepare(), {})
        self.assertFalse((self.target / 'kontext/CONTEXT_000.prt').exists())

    def test_existing_target_is_never_overwritten(self):
        target = self.target / 'kontext/CONTEXT_000.prt'
        target.parent.mkdir()
        target.write_bytes(b'existing user bytes')
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(target.read_bytes(), b'existing user bytes')

    def test_foreign_paths_modes_and_unfinished_sources_fail_before_copying(self):
        for field, value in [('mode', 'verify'), ('repo_root', str(self.repo.parent)),
                             ('directory', str(self.target)), ('report', str(self.repo / 'elsewhere.json')),
                             ('load_method', 'SearchDirectories')]:
            original = copy.deepcopy(self.request)
            self.request[field] = value
            self.write_request()
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepare()
            self.request = original
        self.write_request()
        (self.scratch / 'build_result.json').unlink()
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual(list(self.target.rglob('*.prt')), [])

    def test_unsafe_run_and_new_step_path_are_rejected(self):
        with self.assertRaises(ValueError):
            self.cache.prepare_context_cache(self.repo, '../foreign', self.target, self.layout, self.steps)
        self.steps['CONTEXT_000'] = str(self.oldstep)
        with self.assertRaises(ValueError):
            self.prepare()

    def test_native_candidate_preflight_rechecks_new_step_bytes(self):
        records = self.prepare()
        row = self.layout['nodes'][0]
        self.assertEqual(self.cache._candidate_bytes(self.target, row, self.layout, records['CONTEXT_000']),
                         b'synthetic candidate PRT bytes, not native evidence')
        self.newstep.write_bytes(b'changed after runner preflight')
        with self.assertRaises(ValueError):
            self.cache._candidate_bytes(self.target, row, self.layout, records['CONTEXT_000'])

    def test_native_record_contract_accepts_exact_measured_leaf_and_rejects_changes(self):
        node = self.layout['nodes'][0]
        group = self.layout['context']['groups'][0]
        spec = {'origin_mm': [0, 0, 0], 'matrix': [1, 0, 0, 0, 1, 0, 0, 0, 1], 'scale': 0.005}
        presentation = {'camera': {'absolute_origin_mm': [0, 0, 0], 'matrix': spec['matrix'], 'scale': 0.005},
                        'shaded_with_edges': True,
                        'layers': {str(k): {'visible': True, 'selectable': True, 'hidden': False}
                                   for k in (101, 102, 103, 104, 200, 201, 210)}}
        actual = {'attributes': {'M01_NODE_ID': 'CONTEXT_000', 'M01_KIND': 'context',
                                 'M01_DEFAULT_BLANK': False, 'M01_NODE_METADATA': copy.deepcopy(node)},
                  'fully_loaded': True, 'millimeters': True, 'children': [], 'interpart_parents': [],
                  'expressions': [], 'expression_references': [],
                  'bodies': [{'name': 'CONTEXT_000_000', 'layer': 210, 'blank': False}],
                  'measurement': {'body_count': 1, 'component_volumes_m3': [2.0], 'volume_m3': 2.0},
                  'presentation': presentation}
        self.cache.validate_native_record(node, group, spec, actual)
        mutations = [lambda a: a['attributes'].update(M01_NODE_ID='FOREIGN'),
                     lambda a: a.update(fully_loaded=False), lambda a: a.update(millimeters=False),
                     lambda a: a['children'].append('CHILD'),
                     lambda a: a['interpart_parents'].append('external.prt'),
                     lambda a: a['expressions'].append('p1'),
                     lambda a: a['expression_references'].append('expression'),
                     lambda a: a['bodies'][0].update(name='WRONG'),
                     lambda a: a['bodies'][0].update(layer=1),
                     lambda a: a['bodies'][0].update(blank=True),
                     lambda a: a['measurement'].update(volume_m3=9.0),
                     lambda a: a['presentation']['camera'].update(scale=0.5)]
        for mutate in mutations:
            changed = copy.deepcopy(actual)
            mutate(changed)
            with self.subTest(actual=changed), self.assertRaises(ValueError):
                self.cache.validate_native_record(node, group, spec, changed)


if __name__ == '__main__':
    unittest.main()
