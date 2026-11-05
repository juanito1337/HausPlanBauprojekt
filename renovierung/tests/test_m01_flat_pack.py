"""Filesystem/contract tests only; sentinel .prt files are not native CAD proof."""
import importlib
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


class FlatPackTests(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module('renovierung.m01.flat_pack')
        except ModuleNotFoundError:
            self.fail('The native flat-pack implementation is missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.target = self.root/'source', self.root/'target'
        self.source.mkdir()
        self.layout = {'master': 'MASTER.prt', 'nodes': [
            {'id': 'MASTER', 'parent': None, 'kind': 'assembly', 'file': 'MASTER.prt'},
            {'id': 'A', 'parent': 'MASTER', 'kind': 'assembly', 'file': 'gruppen/A.prt'},
            {'id': 'L', 'parent': 'A', 'kind': 'source', 'file': 'bestand/L.prt'},
            {'id': 'FIELD_PS01-F01', 'parent': 'MASTER', 'kind': 'field', 'file': 'felder/F.prt'}],
            'review_masters': [{'id': 'PS01', 'file': 'Bauabschnitte/PS01.prt', 'state': 'PS01-F01'}]}
        self.mapping = {'MASTER.prt': 'MASTER.prt', 'gruppen/A.prt': 'A.prt',
                        'bestand/L.prt': 'L.prt', 'felder/F.prt': 'F.prt',
                        'Bauabschnitte/PS01.prt': 'PS01.prt'}
        for name in self.mapping:
            path = self.source/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('SYNTHETIC-NOT-CAD:' + name).encode())

    def plan(self):
        return self.module.plan_flat_pack(self.source, self.target, self.layout, self.mapping)

    def test_plan_keeps_logical_names_and_flat_bijective_paths_without_writes(self):
        before = repr(self.layout)
        plan = self.plan()
        self.assertEqual(plan['file_map'], self.mapping)
        self.assertEqual(plan['review_files'], ['Bauabschnitte/PS01.prt'])
        self.assertEqual(plan['leaf_candidates'], ['bestand/L.prt', 'felder/F.prt'])
        self.assertEqual(set(plan['source_parts']), set(self.mapping))
        self.assertEqual(repr(self.layout), before)
        self.assertFalse(self.target.exists())

    def test_missing_or_extra_native_files_are_rejected(self):
        (self.source/'extra.prt').write_bytes(b'not CAD')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.plan()
        (self.source/'extra.prt').unlink()
        (self.source/'bestand/L.prt').unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.plan()

    def test_invalid_or_colliding_physical_and_canonical_paths_are_rejected(self):
        for bad in ('../L.prt', 'sub/L.prt', 'L.txt', 'C:/L.prt', 'L.PRT'):
            mapping = dict(self.mapping, **{'bestand/L.prt': bad})
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.module.plan_flat_pack(self.source, self.target, self.layout, mapping)
        mapping = dict(self.mapping, **{'bestand/L.prt': 'master.prt'})
        with self.assertRaisesRegex(ValueError, 'collid'):
            self.module.plan_flat_pack(self.source, self.target, self.layout, mapping)
        mapping = dict(self.mapping)
        mapping.pop('bestand/L.prt')
        with self.assertRaisesRegex(ValueError, 'map inventory'):
            self.module.plan_flat_pack(self.source, self.target, self.layout, mapping)

    def test_nonempty_or_nested_destination_is_rejected_without_touching_it(self):
        self.target.mkdir()
        kept = self.target/'keep.txt'
        kept.write_text('user data')
        with self.assertRaisesRegex(ValueError, 'empty'):
            self.plan()
        self.assertEqual(kept.read_text(), 'user data')
        with self.assertRaisesRegex(ValueError, 'disjoint'):
            self.module.plan_flat_pack(self.source, self.source/'flat', self.layout, self.mapping)

    def test_changed_source_bytes_or_inventory_are_detected(self):
        plan = self.plan()
        self.assertEqual(self.module.check_source_unchanged(plan), [])
        (self.source/'bestand/L.prt').write_bytes(b'changed')
        self.assertTrue(self.module.check_source_unchanged(plan))

    def test_output_requires_exact_flat_inventory_and_independent_hashes(self):
        plan = self.plan()
        self.target.mkdir()
        for index, (canonical, physical) in enumerate(self.mapping.items()):
            (self.target/physical).write_bytes(('CLONE-OUTPUT-%d' % index).encode())
        rows = self.module.check_pack_outputs(plan, preserved=[])
        self.assertEqual({r['canonical'] for r in rows}, set(self.mapping))
        self.assertTrue(all(not r['byte_preserved'] for r in rows))
        (self.target/'extra.prt').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            self.module.check_pack_outputs(plan, preserved=[])

    def test_byte_preserved_leaf_has_to_match_actual_source_bytes(self):
        plan = self.plan()
        self.target.mkdir()
        for canonical, physical in self.mapping.items():
            (self.target/physical).write_bytes((self.source/canonical).read_bytes())
        rows = self.module.check_pack_outputs(plan, preserved=['bestand/L.prt'])
        self.assertTrue(next(r for r in rows if r['canonical'] == 'bestand/L.prt')['byte_preserved'])
        (self.target/'L.prt').write_bytes(b'native changed')
        with self.assertRaisesRegex(ValueError, 'preserved'):
            self.module.check_pack_outputs(plan, preserved=['bestand/L.prt'])

    def test_clone_inventory_must_match_all_source_parts_before_output(self):
        plan = self.plan()
        names = [str(self.source/p) for p in self.mapping]
        self.module.check_clone_inventory(plan, names)
        for bad in (names[:-1], names + [names[0]], names + [str(self.root/'foreign.prt')]):
            with self.assertRaisesRegex(ValueError, 'Clone inventory'):
                self.module.check_clone_inventory(plan, bad)

    def test_gui_or_nonempty_sessions_are_refused_before_any_native_api(self):
        for session in (SimpleNamespace(IsBatch=False, Parts=[]),
                        SimpleNamespace(IsBatch=True, Parts=[object()])):
            with self.subTest(session=session):
                with self.assertRaises(self.module.FlatPackError) as error:
                    self.module.build_flat_pack(session, self.source, self.target, self.layout, self.mapping)
                self.assertEqual(error.exception.evidence['status'], 'FAIL')
                self.assertEqual(error.exception.evidence['stage'], 'session_guard')
                self.assertFalse(self.target.exists())


if __name__ == '__main__':
    unittest.main()
