"""Filesystem/provenance tests; no fake NX process or native success claim."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from renovierung.anbau import runner


class RunnerContractTests(unittest.TestCase):
    def naming_fixture(self):
        nodes = [{'id': 'CONSTRUCTION', 'file': 'construction.prt', 'parent': 'MASTER'}]
        fields, records, file_map = {}, {}, {'construction.prt': 'P001.prt'}
        for sector in range(10, 14):
            sid = 'SECTION_PS%02d' % sector
            file = sid+'.prt'
            file_map[file] = 'P%03d.prt' % (sector-8)
            nodes.append({'id': sid, 'parent': 'CONSTRUCTION', 'file': file,
                          'name': sid+'_NEW', 'reference_set': 'Entire Part',
                          'translation_mm': [0, 0, 0], 'rotation': [1, 0, 0, 0, 1, 0, 0, 0, 1],
                          'metadata': {'new': True}})
            for index in range(1, 7):
                fid = 'PS%02d-F%02d' % (sector, index)
                fields[fid] = {}
                nodes.append({'id': 'FIELD_'+fid, 'parent': sid, 'file': fid+'.prt',
                              'name': fid+'_NEW', 'reference_set': 'Entire Part',
                              'translation_mm': [0, 0, 0], 'rotation': [1, 0, 0, 0, 1, 0, 0, 0, 1],
                              'metadata': {'new': True}})
        byid = {n['id']: n for n in nodes}
        for node in nodes[1:]:
            records[node['id']] = {'parent_id': node['parent'], 'owner_file': byid[node['parent']]['file'],
                'instance_name': node['name'], 'custom_name': node['name'], 'reference_set': node['reference_set'],
                'translation_mm': node['translation_mm'][:], 'rotation': node['rotation'][:],
                'used_arrangement': 'SAVED', 'metadata_sha256': runner.canonical_sha(node)}
        before = copy.deepcopy(records)
        for row in before.values():
            row['instance_name'] = 'OLD_NAME'
        return {'layout': {'nodes': nodes}, 'fields': fields, 'file_map': file_map}, {
            'instance_names': records, 'before_instance_names': before}

    def test_naming_phase_proves_exact_names_and_unchanged_geometry_for_all_28(self):
        spec, proof = self.naming_fixture()
        for group in ('instance_names', 'before_instance_names'):
            proof[group]['FIELD_PS10-F01']['custom_name'] = proof[group]['FIELD_PS10-F01']['custom_name'].upper()
        runner.validate_naming_instances(proof, spec)
        self.assertEqual(runner.naming_targets(spec), {'P001.prt', 'P002.prt', 'P003.prt', 'P004.prt', 'P005.prt'})
        for mutation in (lambda p: p['instance_names'].pop('FIELD_PS10-F01'),
                         lambda p: p['instance_names']['FIELD_PS10-F01'].update(instance_name='OLD'),
                         lambda p: p['instance_names']['FIELD_PS10-F01']['translation_mm'].__setitem__(0, 1),
                         lambda p: p['instance_names']['FIELD_PS10-F01'].update(reference_set='WRONG'),
                         lambda p: p['instance_names']['FIELD_PS10-F01'].update(used_arrangement='OTHER'),
                         lambda p: [p[group]['FIELD_PS10-F01'].pop('used_arrangement') for group in
                                    ('instance_names', 'before_instance_names')]):
            changed = copy.deepcopy(proof)
            mutation(changed)
            with self.assertRaises(ValueError):
                runner.validate_naming_instances(changed, spec)

    def test_naming_chain_keeps_original_owner_after_as_its_before_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory, build, _ = self.repair_fixture(Path(temporary))
            spec, proof = self.naming_fixture()
            spec['layout']['nodes'].insert(0, {'id': 'MASTER', 'file': 'master.prt', 'parent': None})
            spec['file_map']['master.prt'] = 'P000.prt'
            spec.update(immutable_parts=copy.deepcopy(build['parts']),
                        upgrade_attributes={'schema': 'UPGRADE', 'spec_sha256': 'old'})
            spec['immutable_parts'].pop('P000.prt')
            spec['spec_sha256'] = runner.canonical_sha(spec)
            runner.write(directory / 'EXPECTATIONS.json', spec)
            def reference():
                path = directory / 'EXPECTATIONS.json'
                return {'file': path.name, 'bytes': path.stat().st_size, 'sha256': runner.digest(path),
                        'spec_sha256': runner.read(path)['spec_sha256']}
            build.update(expectations=reference(), source_fingerprint='original')
            runner.write(directory / 'BUILD.json', build)
            initial = {name: runner.preserve_initial(directory, name)
                       for name in ('BUILD.json', 'EXPECTATIONS.json')}
            for name in ('P000.prt', 'P001.prt'):
                (directory / name).write_bytes(b'owner phase')
            owner_after = runner.inventory(directory)
            new_spec = copy.deepcopy(spec)
            new_spec['immutable_parts'].pop('P001.prt')
            new_spec['upgrade_attributes']['spec_sha256'] = 'new'
            new_spec.pop('spec_sha256')
            new_spec['spec_sha256'] = runner.canonical_sha(new_spec)
            runner.write(directory / 'EXPECTATIONS.json', new_spec)
            owner_native = {'before_parts': build['parts'], 'after_parts': owner_after,
                            'spec_sha256': 'new', 'old_upgrade_spec_sha256': 'old'}
            owner_build = dict(build, parts=owner_after, expectations=reference(), repair={
                'initial_records': initial, 'initial_source_fingerprint': 'original',
                'native': {'repair': owner_native}})
            runner.write(directory / 'BUILD.json', owner_build)
            archive = runner.preserve_initial(directory, 'BUILD.json', 'BUILD_BEFORE_NAMING.json')
            for name in runner.naming_targets(new_spec):
                (directory / name).write_bytes(b'naming phase')
            final_parts = runner.inventory(directory)
            proof.update(before_parts=owner_after, after_parts=final_parts, spec_sha256='new',
                         unchanged_parts=362, source_bytes_unchanged=True,
                         status='INSTANCE_NAMES_REPAIRED_PENDING_FRESH_VERIFY',
                         saved_parts=['construction.prt']+['SECTION_PS%02d.prt' % i for i in range(10, 14)])
            final_build = dict(owner_build, parts=final_parts,
                               naming_repair={'before_build': archive, 'native': {'repair': proof}})
            runner.validate_repair_provenance(directory, final_build, new_spec)
            forged = copy.deepcopy(final_build)
            forged['repair']['native']['repair']['after_parts'] = final_parts
            with self.assertRaises(ValueError):
                runner.validate_repair_provenance(directory, forged, new_spec)
            runner.write(directory / 'BUILD.json', final_build)
            before_defaults = runner.preserve_initial(directory, 'BUILD.json', 'BUILD_BEFORE_DEFAULTS.json')
            for name in runner.defaults_targets(new_spec):
                (directory / name).write_bytes(b'default phase')
            defaults_parts = runner.inventory(directory)
            defaults = {'status': 'SECTION_DEFAULTS_REPAIRED_PENDING_FRESH_VERIFY', 'spec_sha256': 'new',
                        'before_parts': final_parts, 'after_parts': defaults_parts, 'unchanged_parts': 365,
                        'source_bytes_unchanged': True, 'saved_parts': ['SECTION_PS12.prt', 'SECTION_PS13.prt']}
            third = dict(final_build, parts=defaults_parts, defaults_repair={
                'before_build': before_defaults, 'native': {'repair': defaults}})
            # This isolates archive-chain checks; integration tests prove the section-state record.
            with patch('renovierung.anbau.integration.validate_section_defaults_evidence', create=True) as validator:
                runner.validate_repair_provenance(directory, third, new_spec)
                validator.assert_called_once_with(new_spec, defaults)
                forged = copy.deepcopy(third)
                forged['naming_repair']['native']['repair']['after_parts'] = defaults_parts
                with self.assertRaises(ValueError):
                    runner.validate_repair_provenance(directory, forged, new_spec)

    def test_failed_naming_phase_restores_its_five_owners(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, build, _ = self.repair_fixture(root)
            source = root / 'source'
            source.mkdir()
            (source / 'source.prt').write_bytes(b'unchanged')
            scratch = root / 'scratch'
            scratch.mkdir()
            targets = {'P%03d.prt' % i for i in range(1, 6)}
            def failure(*args, **kwargs):
                for name in targets:
                    (directory / name).write_bytes(b'partial naming')
                raise RuntimeError('naming journal failed')
            with patch.object(runner, 'run_native', side_effect=failure):
                with self.assertRaisesRegex(RuntimeError, 'naming journal failed'):
                    runner.run_repair_native(Path('NX'), {'mode': 'repair_instance_names'}, scratch,
                                             directory, build['parts'], source, runner.inventory(source), targets)
            self.assertEqual(runner.inventory(directory), build['parts'])

    def repair_fixture(self, root):
        directory = root / 'cad/nx/m02/20261105T002134Z_6569c2'
        directory.mkdir(parents=True)
        for index in range(367):
            (directory / ('P%03d.prt' % index)).write_bytes(b'original')
        spec = {'layout': {'nodes': [{'id': 'MASTER', 'file': 'master'},
                                      {'id': 'CONSTRUCTION', 'file': 'construction'}]},
                'file_map': {'master': 'P000.prt', 'construction': 'P001.prt'}}
        spec['spec_sha256'] = runner.canonical_sha(spec)
        runner.write(directory / 'EXPECTATIONS.json', spec)
        build = {'schema': 'M02_BUILD_V2', 'status': 'BUILT_PENDING_VERIFICATION',
                 'construction_release': False, 'native_NX_run_completed': True,
                 'parts': runner.inventory(directory), 'expectations': {
                     'file': 'EXPECTATIONS.json', 'bytes': (directory / 'EXPECTATIONS.json').stat().st_size,
                     'sha256': runner.digest(directory / 'EXPECTATIONS.json'),
                     'spec_sha256': spec['spec_sha256']}}
        runner.write(directory / 'BUILD.json', build)
        return directory, build, spec

    def test_repair_rejects_published_or_changed_candidate_before_any_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, build, spec = self.repair_fixture(root)
            runner.validate_repair_candidate(directory, build, spec, root)
            pointer = directory.parent / 'CURRENT.json'
            runner.write(pointer, {'directory': directory.name})
            before = {p.name: p.read_bytes() for p in directory.iterdir()}
            with self.assertRaisesRegex(ValueError, 'published'):
                runner.validate_repair_candidate(directory, build, spec, root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})
            pointer.unlink()
            (directory / 'P200.prt').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, '367'):
                runner.validate_repair_candidate(directory, build, spec, root)
            self.assertFalse((directory / 'BUILD_INITIAL.json').exists())

    def test_failed_repair_restores_only_its_two_parts_and_preserves_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, build, spec = self.repair_fixture(root)
            source = root / 'source'
            source.mkdir()
            (source / 'source.prt').write_bytes(b'unchanged')
            pointer = directory.parent / 'CURRENT.json'
            runner.write(pointer, {'directory': 'older'})
            pointer_before = pointer.read_bytes()
            scratch = root / 'scratch'
            scratch.mkdir()
            def failed_journal(*args, **kwargs):
                (directory / 'P001.prt').write_bytes(b'partial repair')
                raise RuntimeError('native journal failed after process ended')
            with patch.object(runner, 'run_native', side_effect=failed_journal):
                with self.assertRaisesRegex(RuntimeError, 'journal failed'):
                    runner.run_repair_native(Path('NX'), {}, scratch, directory, build['parts'],
                                             source, runner.inventory(source), {'P000.prt', 'P001.prt'})
            self.assertEqual(runner.inventory(directory), build['parts'])
            self.assertEqual(pointer.read_bytes(), pointer_before)

    def test_failed_repair_refuses_rollback_when_an_unrelated_part_changed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, build, spec = self.repair_fixture(root)
            source = root / 'source'
            source.mkdir()
            (source / 'source.prt').write_bytes(b'unchanged')
            scratch = root / 'scratch'
            scratch.mkdir()
            def failed_journal(*args, **kwargs):
                (directory / 'P001.prt').write_bytes(b'partial repair')
                (directory / 'P200.prt').write_bytes(b'unrelated change')
                raise RuntimeError('native journal failed')
            with patch.object(runner, 'run_native', side_effect=failed_journal):
                with self.assertRaisesRegex(RuntimeError, 'rollback refused'):
                    runner.run_repair_native(Path('NX'), {}, scratch, directory, build['parts'],
                                             source, runner.inventory(source), {'P000.prt', 'P001.prt'})
            self.assertEqual((directory / 'P001.prt').read_bytes(), b'partial repair')
            self.assertEqual((directory / 'P200.prt').read_bytes(), b'unrelated change')

    def test_malformed_repair_report_restores_targets_after_the_process_ends(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, build, spec = self.repair_fixture(root)
            source = root / 'source'
            source.mkdir()
            (source / 'source.prt').write_bytes(b'unchanged')
            scratch = root / 'scratch'
            scratch.mkdir()
            def malformed_report(*args, **kwargs):
                (directory / 'P001.prt').write_bytes(b'partial repair')
                return {'repair': {}}
            with patch.object(runner, 'run_native', side_effect=malformed_report):
                with self.assertRaises(KeyError):
                    runner.run_repair_native(Path('NX'), {}, scratch, directory, build['parts'],
                                             source, runner.inventory(source), {'P000.prt', 'P001.prt'})
            self.assertEqual(runner.inventory(directory), build['parts'])

    def test_repair_contract_allows_only_owner_exemption_and_derived_hashes(self):
        old = {'layout': {'nodes': [{'id': 'MASTER', 'file': 'master'},
                                     {'id': 'CONSTRUCTION', 'file': 'construction'}]},
               'file_map': {'master': 'MASTER.prt', 'construction': 'CONSTRUCTION.prt'},
               'immutable_parts': {'CONSTRUCTION.prt': {'sha256': 'original'}, 'LEAF.prt': {'sha256': 'leaf'}},
               'upgrade_attributes': {'schema': 'S', 'spec_sha256': 'old'}, 'spec_sha256': 'old'}
        new = copy.deepcopy(old)
        new['immutable_parts'].pop('CONSTRUCTION.prt')
        new['upgrade_attributes']['spec_sha256'] = 'new'
        new['spec_sha256'] = 'new'
        runner.validate_repair_contract(old, new)
        for change in (lambda s: s['immutable_parts'].pop('LEAF.prt'),
                       lambda s: s['layout']['nodes'][0].update(file='other')):
            changed = copy.deepcopy(new)
            change(changed)
            with self.assertRaises(ValueError):
                runner.validate_repair_contract(old, changed)

    def test_initial_records_are_exact_and_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            original = b'{"status": "BUILT_PENDING_VERIFICATION"}\n'
            (directory / 'BUILD.json').write_bytes(original)
            record = runner.preserve_initial(directory, 'BUILD.json')
            self.assertEqual((directory / record['file']).read_bytes(), original)
            self.assertEqual(record['sha256'], hashlib.sha256(original).hexdigest())
            (directory / 'BUILD.json').write_bytes(b'changed')
            with self.assertRaises(ValueError):
                runner.preserve_initial(directory, 'BUILD.json')
            self.assertEqual((directory / record['file']).read_bytes(), original)

    def test_failed_full_reverification_never_updates_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'candidate'
            directory.mkdir()
            pointer = root / 'CURRENT.json'
            runner.write(pointer, {'directory': 'previous'})
            before = pointer.read_bytes()
            with patch.object(runner, 'run_native', side_effect=RuntimeError('fresh full failed')):
                with self.assertRaisesRegex(RuntimeError, 'fresh full failed'):
                    runner.complete_candidate(Path('NX'), directory, root, {}, {}, root, {},
                                               'fingerprint', {}, {}, {}, {})
            self.assertEqual(pointer.read_bytes(), before)
            self.assertFalse((directory / 'VERIFY.json').exists())

    def test_default_first_still_runs_full_and_never_publishes_when_it_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory, scratch = root / 'candidate', root / 'scratch'
            directory.mkdir()
            scratch.mkdir()
            (directory / 'ONE.prt').write_bytes(b'original')
            pointer = root / 'CURRENT.json'
            runner.write(pointer, {'directory': 'previous'})
            pointer_before, modes = pointer.read_bytes(), []
            def phase(*args):
                modes.append(args[1]['mode'])
                if args[1]['mode'] == 'full_verify':
                    raise RuntimeError('full verification failed')
                return {}  # Scheduling only; this is never accepted as release evidence.
            with patch.object(runner, 'run_native', side_effect=phase):
                with self.assertRaisesRegex(RuntimeError, 'full verification failed'):
                    runner.complete_candidate(Path('NX'), directory, scratch, {},
                                               {'parts': runner.inventory(directory)}, root, {},
                                               'fingerprint', {}, {}, {}, {}, default_first=True)
            self.assertEqual(modes, ['default_verify', 'full_verify'])
            self.assertEqual((scratch / 'relocated/ONE.prt').read_bytes(), b'original')
            self.assertEqual(pointer.read_bytes(), pointer_before)

    def test_section_smoke_is_explicitly_partial_and_bound_to_exact_part_bytes(self):
        spec, parts = {'spec_sha256': 's'}, {'ONE.prt': {'sha256': 'bytes'}}
        smoke = {'schema': 'EXPLICIT_SECTION_DIAGNOSTIC_V1', 'status': 'PARTIAL_DIAGNOSTIC',
                 'scope_only': True, 'complete_release': False, 'construction_release': False,
                 'saved_by_inspector': False,
                 'verification_spec_sha256': 's', 'file_manifest': parts, 'file_manifest_after': parts,
                 'byte_guards': {'target_parts_unchanged': True, 'original_source_unchanged': True},
                 'sections': {nid: {'cold_open': True} for nid in ('SECTION_PS12', 'SECTION_PS13')}}
        runner.validate_section_smoke_record(spec, smoke, parts)
        for change in (lambda s: s.update(status='PASS'), lambda s: s.update(complete_release=True),
                       lambda s: s.update(construction_release=True),
                       lambda s: s.update(saved_by_inspector=True), lambda s: s.update(file_manifest={}),
                       lambda s: s['byte_guards'].update(original_source_unchanged=False),
                       lambda s: s['sections']['SECTION_PS12'].update(cold_open=False)):
            changed = copy.deepcopy(smoke)
            change(changed)
            with self.assertRaises(ValueError):
                runner.validate_section_smoke_record(spec, changed, parts)

    def test_failed_section_smoke_stops_both_long_verification_phases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / 'candidate'
            directory.mkdir()
            pointer = root / 'CURRENT.json'
            runner.write(pointer, {'directory': 'previous'})
            before = pointer.read_bytes()
            with patch.object(runner, 'run_section_smoke', side_effect=RuntimeError('section smoke failed')):
                with patch.object(runner, 'run_native') as long_phase:
                    with self.assertRaisesRegex(RuntimeError, 'section smoke failed'):
                        runner.complete_candidate(Path('NX'), directory, root, {}, {}, root, {},
                            'fingerprint', {}, {}, {}, {}, default_first=True, section_smoke_required=True)
                    long_phase.assert_not_called()
            self.assertEqual(pointer.read_bytes(), before)

    def test_json_contract_preserves_exact_values_across_all_saved_boundaries(self):
        value = {'fields': [{'polygon': [(1.2345678901234567, -0.0), (2, 3)]}],
                 'site': {'centroid_mm': (1e-12, 2, 3)},
                 'expectations': {'transform': (1, 0, 0)}}
        before = copy.deepcopy(value)
        normalized = runner.json_contract(value)
        self.assertEqual(normalized, json.loads(json.dumps(value, allow_nan=False)))
        self.assertEqual(runner.canonical_sha(normalized), runner.canonical_sha(value))
        self.assertEqual(normalized['site']['centroid_mm'][0], 1e-12)
        self.assertEqual(value, before)
        with self.assertRaises(ValueError):
            runner.json_contract({'coordinate': float('nan')})

    def test_fresh_geometry_tuples_match_saved_json_without_numeric_relaxation(self):
        from renovierung.k02.geometry import convex_hull
        from renovierung.tests.test_anbau_nx_fields import fixture
        field = fixture()
        field['uncertainty_coverage_hull_xy_mm'] = convex_hull([[0, 0], [2, 0], [0, 2]])
        self.assertIsInstance(field['uncertainty_coverage_hull_xy_mm'][0], tuple)
        plan = {'fields': [field]}
        current = runner.current_field_inputs(plan)
        saved_plan = json.loads(json.dumps(plan, allow_nan=False))
        saved = runner.current_field_inputs(saved_plan)
        self.assertEqual(current, saved)
        self.assertEqual(runner.compact_prepared(current), json.loads(json.dumps(current)))
        saved_plan['fields'][0]['uncertainty_coverage_hull_xy_mm'][0][0] += 1e-12
        self.assertNotEqual(current, runner.current_field_inputs(saved_plan))

    def test_release_contract_drops_machine_paths_but_keeps_exact_native_specs(self):
        prepared = {'schema': 'ANBAU_FIELD_INPUTS_V1', 'plan_sha256': 'a'*64,
                    'fields': {'PS11-F01': {'spec': {'id': 'PS11-F01', 'file': 'PS11-F01_STUDY.prt'},
                               'presentation': {'scale': 1}, 'imports': [{'path': 'ignored/old.step'}]}},
                    'presentation': {'scale': 1}, 'register_only_ids': []}
        before = copy.deepcopy(prepared)
        compact = runner.compact_prepared(prepared)
        self.assertEqual(compact['fields']['PS11-F01'], {
            'spec': {'id': 'PS11-F01', 'file': 'PS11-F01_STUDY.prt'}, 'presentation': {'scale': 1}})
        self.assertEqual(prepared, before)
        self.assertEqual(runner.compact_site({'entry_sha256': 'b'*64, 'step_path': 'ignored/a.step',
                                             'entry_path': 'ignored/a.json', 'nx_root': 'oldNX'}),
                         {'entry_sha256': 'b'*64})

    def test_source_fingerprint_covers_all_k02_m01_tools_and_ignores_transfer_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ('renovierung/anbau/runner.py', 'renovierung/anbau/assumptions.json',
                             'renovierung/anbau/KATALOG.json', 'renovierung/k02/helper.py',
                             'renovierung/m01/helper.py', 'tools/used.py', 'data/input.json'):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('{}')
            base = root / 'cad/nx/m01/base'
            base.mkdir(parents=True)
            (base / 'BUILD.json').write_text('{}')
            (base / 'part.prt').write_bytes(b'actual synthetic file bytes')
            plan = {'provenance': {'source_and_generator_hashes': {'data/input.json': 'unused'}}}
            prepared = {'schema': 'X', 'plan_sha256': 'p', 'fields': {}, 'presentation': {}, 'register_only_ids': []}
            site = {'step_sha256': 's', 'step_path': 'ignored/one.step'}
            first = runner.source_fingerprint(base, plan, prepared, site, repo_root=root)
            site['step_path'] = 'another/machine/two.step'
            self.assertEqual(first, runner.source_fingerprint(base, plan, prepared, site, repo_root=root))
            for relative in ('renovierung/k02/helper.py', 'renovierung/m01/helper.py', 'tools/used.py'):
                path = root / relative
                original = path.read_bytes()
                path.write_text('changed')
                self.assertNotEqual(first, runner.source_fingerprint(base, plan, prepared, site, repo_root=root))
                path.write_bytes(original)

    def test_completed_318_part_build_candidate_does_not_require_or_claim_m01_release(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for index in range(318):
                name = 'P%03d.prt' % index
                (root / name).write_bytes(b'prt')
                rows.append({'path': name, 'bytes': 3, 'sha256': hashlib.sha256(b'prt').hexdigest()})
            record = {'schema': 'M01_FLAT_BUILD_V2', 'native_NX_run_completed': True,
                      'status': 'BUILT_PENDING_VERIFICATION', 'parts': rows,
                      'delivery_file_map': {row['path']: row['path'] for row in rows}}
            (root / 'BUILD.json').write_text(json.dumps(record))
            self.assertEqual(runner.source_record(root), record)
            (root / rows[0]['path']).write_bytes(b'tampered')
            with self.assertRaises(ValueError):
                runner.source_record(root)

    def test_inventory_refuses_nested_or_symlink_style_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'nested').mkdir()
            (root / 'nested/a.prt').write_bytes(b'prt')
            with self.assertRaises(ValueError):
                runner.inventory(root)

    def test_base_layout_must_match_the_current_generator_exactly(self):
        layout = {'schema': 'M01_LAYOUT_V2', 'nodes': [{'id': 'MASTER'}]}
        baseline = {'layout': copy.deepcopy(layout)}
        runner.validate_base_layout(baseline, layout)
        changed = copy.deepcopy(layout)
        changed['nodes'].append({'id': 'CHANGED'})
        with self.assertRaisesRegex(ValueError, 'matching M01 base'):
            runner.validate_base_layout(baseline, changed)
        self.assertEqual(baseline['layout'], layout)

    def test_pending_build_never_passes_complete_release_gate(self):
        errors = runner.validate_evidence(Path('.'), {'schema': 'M02_BUILD_V2',
                                        'status': 'BUILT_PENDING_VERIFICATION'}, {})
        self.assertTrue(errors)

    def test_atomic_json_write_replaces_only_the_named_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'CURRENT.json'
            sentinel = root / 'other.json'
            sentinel.write_bytes(b'unchanged')
            runner.write(target, {'directory': 'one'})
            runner.write(target, {'directory': 'two'})
            self.assertEqual(runner.read(target), {'directory': 'two'})
            self.assertEqual(sentinel.read_bytes(), b'unchanged')
            self.assertEqual({p.name for p in root.iterdir()}, {'CURRENT.json', 'other.json'})

    def test_changed_assumptions_require_explicit_new_pinned_review(self):
        from renovierung.anbau.integration import review_edge_strips
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = {'fields': [], 'assumed_depth': -1600}
            review = review_edge_strips(plan)
            path = root / 'renovierung/anbau/RANDSTREIFEN_REVIEW.json'
            runner.write(path, review)
            runner.write(path.parent / 'KATALOG.json', {'aktuelleDarstellungsfreigabe': {
                'review': path.relative_to(root).as_posix(), 'review_sha256': runner.digest(path),
                'construction_release': False, 'regular_study_ids': [], 'diagnostic_ids': []}})
            runner.check_pinned_review(plan, root)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                runner.check_pinned_review(dict(plan, assumed_depth=-1500), root)
            self.assertEqual(path.read_bytes(), before)

    def test_node_count_follows_canonical_classification_with_fixed_entry_inventory(self):
        for count in (10, 11):
            fields = {str(i): {'native': i < count, 'diagnostic': i >= count} for i in range(24)}
            spec = {'fields': fields, 'prepared_fields': fields,
                    'counts': dict(runner.EXPECTED_COUNTS, nodes=373+4*count)}
            self.assertEqual(len(runner.assert_counts(spec)['study_ids']), count)
            spec['counts']['parts'] = 366
            with self.assertRaises(ValueError):
                runner.assert_counts(spec)


if __name__ == '__main__':
    unittest.main()
