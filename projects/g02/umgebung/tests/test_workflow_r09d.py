"""R11: Reihenfolge, Teilerfolg und getrennte Erzeugung. Keine echte NX-Laufzeit."""
import ast
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_r09 import BASE, CONFIG, JOB, SceneDouble, SceneAdapter
from r09.core import read_json, write_json, sha256, verify_runtime_files
from r09.workflow import (run_checked_project, checked_house_result,
                          checked_environment_result, display_saved)
from r09.run import run_project, build_house_copy


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.definition = self.root/'step214ug.def'; self.definition.write_text('SIMULATION ONLY')
        self.env = SceneDouble(self.definition)
        self.events = []
    def cfg(self):
        c = copy.deepcopy(CONFIG); c['output_root'] = str(self.root/'runs')
        c['step_settings_file'] = str(self.definition)
        return c
    def writer(self, path, data):
        p = Path(path)
        if p.parent == BASE and p.name.startswith('LETZTER_'):
            p = self.root/p.name
        return write_json(p, data)
    def workflow(self, mode='ALL', house=None, environment=None, config=None):
        def hb(base, out):
            self.events.append('HOUSE')
            return (house or build_house_copy)(base, out)
        def eb(base, **kw):
            self.events.append('ENVIRONMENT')
            return (environment or run_project)(base, **kw)
        with self.env.active(), contextlib.redirect_stdout(io.StringIO()), \
             patch('r09.workflow.write_json', side_effect=self.writer), \
             patch('r09.run.write_json', side_effect=self.writer):
            return run_checked_project(BASE, mode, config or self.cfg(),
                                       house_builder=hb, environment_runner=eb)
    def manifest(self):
        return read_json(next((self.root/'runs').rglob('manifest_R11.json')))
    def test_01_full_run_house_precedes_environment(self):
        s = self.workflow()
        self.assertEqual(self.events, ['HOUSE', 'ENVIRONMENT'])
        self.assertEqual(s['house']['built_solids'], 1361)
        self.assertEqual(s['checked_file_count'], 25)
        self.assertEqual(s['environment']['checked_source_points'], 20883)
        self.assertEqual(self.env.step_calls, 6)
    def test_02_house_only_never_calls_step_importer(self):
        self.env.session.DexManager.CreateStep214Importer = None
        self.definition.unlink()
        s = self.workflow('HOUSE')
        self.assertEqual(self.events, ['HOUSE']); self.assertEqual(self.env.step_calls, 0)
        self.assertEqual(s['checked_file_count'], 17); self.assertIsNone(s['environment'])
    def test_03_environment_only_never_builds_house(self):
        s = self.workflow('ENVIRONMENT')
        self.assertEqual(self.events, ['ENVIRONMENT']); self.assertIsNone(s['house'])
        self.assertEqual(s['checked_file_count'], 7)
    def test_04_environment_failure_preserves_house(self):
        self.env.fail_step_at = 1
        with self.assertRaisesRegex(RuntimeError, 'INJECTED') as ctx:
            self.workflow()
        s = self.manifest()
        self.assertEqual(s['status'], 'R11_ABGEBROCHEN_KEIN_GESAMTERFOLG')
        self.assertIsNotNone(s['house']); self.assertIsNone(s['environment'])
        p = Path(ctx.exception.r11_context['saved_house_master'])
        self.assertTrue(p.is_file())
        self.assertTrue((self.root/'LETZTER_HAUSLAUF_R11.json').is_file())
        self.assertFalse((self.root/'LETZTER_GESAMTLAUF_R11.json').exists())
    def test_05_house_failure_never_imports_environment(self):
        def failed(*args): raise RuntimeError('HOUSE_INJECTED')
        with self.assertRaisesRegex(RuntimeError, 'HOUSE_INJECTED'): self.workflow(house=failed)
        self.assertEqual(self.events, ['HOUSE']); self.assertEqual(self.env.step_calls, 0)
        self.assertIsNone(self.manifest()['house'])
    def test_06_no_height_means_two_separate_masters(self):
        s = self.workflow(); self.assertIsNone(s['combined_master'])
        self.assertTrue(s['displayed_master'].endswith('PROJEKT_MASTER_R11_HOEHENBEZUG_OFFEN.prt'))
        self.assertTrue(s['project_reference_master']); self.assertFalse(s['physical_site_alignment_verified'])
        self.assertTrue(all(c['translation_mm']==[0,0,0] for c in s['project_reference_checks']))
        self.assertFalse(s['technical_as_built_approval'])
    def test_07_confirmed_height_applies_to_whole_environment_once(self):
        c = self.cfg(); c['height_connection'] = {'H_EG_zero_in_source_datum_m': 31.2,
            'source': 'NUR SIMULATION KEIN ECHTER HOEHENWERT', 'common_vertical_datum_confirmed': True}
        s = self.workflow(config=c)
        self.assertEqual(s['combined_master'], 'GESAMTMODELL_R11.prt')
        self.assertEqual(s['checked_file_count'], 25)
        self.assertEqual(s['combined_component_checks'][1]['translation_mm'], [0,0,-31200.])
        self.assertEqual(s['combined_component_checks'][0]['translation_mm'], [0,0,0])
    def test_08_reference_house_does_not_become_full_model(self):
        self.env.answer = 2
        s = self.workflow('HOUSE')
        self.assertEqual(s['house']['mode'], 'REFERENZGERUEST')
        self.assertEqual(s['house']['built_solids'], 0)
        self.assertIsNone(s['combined_master'])
    def test_09_explicit_house_start_overrides_build_house_false(self):
        c = self.cfg(); c['build_house'] = False
        s = self.workflow('HOUSE', config=c)
        self.assertEqual(s['house']['built_solids'], 1361)
    def test_10_all_start_respects_build_house_false(self):
        c = self.cfg(); c['build_house'] = False
        s = self.workflow(config=c)
        self.assertEqual(self.events, ['ENVIRONMENT']); self.assertIsNone(s['house'])
    def test_11_house_does_not_parse_environment_job(self):
        # Fail explicitly on environment-job access, not on all reads.
        def read(path):
            if Path(path).name == 'IMPORTAUFTRAG_R09.json':
                raise AssertionError('STEP-Auftrag in Hausmodus gelesen')
            return read_json(path)
        with patch('r09.workflow.read_json', side_effect=read):
            self.workflow('HOUSE')
        self.assertEqual(self.env.step_calls, 0)
    def test_12_invalid_mode_before_creating_outputs(self):
        with self.assertRaises(ValueError): self.workflow('INVALID')
        self.assertFalse((self.root/'runs').exists())
    def test_13_open_old_house_component_is_never_closed(self):
        with self.env.active():
            p = self.env.session.Parts.NewDisplay(str(self.root/'03_ERDGESCHOSS.prt'), self.env.N.Part.Units.Millimeters)
        with self.assertRaisesRegex(RuntimeError, 'bereits geladen'): self.workflow('HOUSE')
        self.assertEqual(self.events, []); self.assertEqual(self.env.step_calls, 0)
        self.assertIn(p, list(self.env.session.Parts))
    def test_14_existing_environment_does_not_prevent_house_only(self):
        with self.env.active():
            p = self.env.session.Parts.NewDisplay(str(self.root/'01_GELAENDE_R09.prt'), self.env.N.Part.Units.Millimeters)
        self.workflow('HOUSE'); self.assertIn(p, list(self.env.session.Parts))
    def test_15_existing_house_does_not_prevent_environment_only(self):
        with self.env.active():
            p = self.env.session.Parts.NewDisplay(str(self.root/'HAUS_MASTER.prt'), self.env.N.Part.Units.Millimeters)
        self.workflow('ENVIRONMENT'); self.assertIn(p, list(self.env.session.Parts))
    def test_16_house_file_tampering_during_environment_is_rejected(self):
        def tamper(base, **kw):
            pointer = read_json(self.root/'LETZTER_HAUSLAUF_R11.json')
            Path(pointer['master']).write_text('MODIFIED - SIMULATION')
            return run_project(base, **kw)
        with self.assertRaisesRegex(ValueError, 'Datei fehlt/veraendert'): self.workflow(environment=tamper)
        self.assertEqual(self.manifest()['status'], 'R11_ABGEBROCHEN_KEIN_GESAMTERFOLG')
    def test_17_partial_house_status_cannot_be_success(self):
        with self.assertRaises(RuntimeError): checked_house_result(self.root, {'status':'PARTIAL'}, {})
    def test_18_wrong_house_verification_cannot_be_success(self):
        with self.assertRaises(RuntimeError): checked_house_result(self.root, {'status':'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT'}, {'status':'FAILED'})
    def test_19_partial_environment_status_cannot_be_success(self):
        with self.assertRaises(RuntimeError): checked_environment_result(self.root, {'status':'R09_ABGEBROCHEN_TEILERGEBNIS'})
    def test_20_foreign_environment_directory_rejected(self):
        e = {'status':'R09_ERZEUGT_BEZUGSSYSTEME_GETRENNT', 'environment_status':'ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT', 'output_directory':str(self.root.parent)}
        with self.assertRaises(ValueError): checked_environment_result(self.root, e)
    def test_21_display_does_not_grant_write_ownership(self):
        with self.env.active():
            a = SceneAdapter(lambda text: None)
            p = self.env.session.Parts.NewDisplay(str(self.root/'readonly.prt'), self.env.N.Part.Units.Millimeters)
            before = len(a.created)
            display_saved(a, p.FullPath)
            self.assertEqual(len(a.created), before)
            with self.assertRaisesRegex(RuntimeError,'Schreibzugriff'): a.ensure_work(p)
    def test_22_display_missing_part_not_assumed_open(self):
        with self.env.active():
            a = SceneAdapter(lambda text: None)
            with self.assertRaises(RuntimeError): display_saved(a, self.root/'missing.prt')
    def test_23_phase_pointers_reference_checked_results(self):
        s = self.workflow()
        for k in ('HAUS','UMGEBUNG'):
            p = read_json(self.root/('LETZTER_'+k+'LAUF_R11.json'))
            self.assertTrue(Path(p['master']).is_file()); self.assertEqual(p['patch'], 'R11-FENSTER-UND-QUELLENBEZUG')
            self.assertFalse(p['technical_as_built_approval'])
    def test_24_import_measurements_not_disabled(self):
        s = self.workflow('ENVIRONMENT')
        self.assertGreater(self.env.face_measure_calls, 230)
        self.assertEqual(s['environment']['checked_source_points'], 20883)
    def test_25_invalid_geometry_environment_preserves_house(self):
        self.env.area_factor = 1.2
        with self.assertRaisesRegex(RuntimeError, 'Flaecheninhalt abweichend'): self.workflow()
        self.assertIsNotNone(self.manifest()['house'])
        self.assertIsNone(self.manifest()['environment'])
    def test_26_step_split_keeps_same_sheet_requirements(self):
        self.env.split_spec = {'V01':7}
        s = self.workflow('ENVIRONMENT')
        e = read_json(Path(s['output_directory'])/s['environment']['manifest'])
        check = next(x for x in e['imports'] if x['id']=='V01')
        self.assertEqual(check['sheets'],49); self.assertEqual(check['faces'],56)
    def test_27_entry_modes_and_diagnostics_are_explicit(self):
        for name, mode in [('00_NX_MODELL_ERZEUGEN_2406.py','ALL'), ('01_NUR_HAUS_ERZEUGEN_2406.py','HOUSE'), ('02_NUR_UMGEBUNG_ERZEUGEN_2406.py','ENVIRONMENT')]:
            text = (BASE/name).read_text()
            ast.parse(text, feature_version=(3,10))
            self.assertIn("MODE = %r" % mode,text)
            self.assertIn('run_checked_project(base, mode=MODE)',text)
            self.assertIn('saved_house_master',text); self.assertIn("'r11_context'",text)
    def test_28_scope_does_not_require_environment_import_job(self):
        records = read_json(BASE/'data/PROGRAMM_UND_QUELLEN_SHA256.json')
        records['data/IMPORTAUFTRAG_R09.json'] = '0'*64
        with patch('r09.core.read_json', return_value=records):
            self.assertGreater(verify_runtime_files(BASE,'house'),20)
            with self.assertRaises(ValueError): verify_runtime_files(BASE,'all')
    def test_29_unknown_verification_scope_rejected(self):
        with self.assertRaises(ValueError): verify_runtime_files(BASE,'ignore_everything')
    def test_30_no_automatic_terrain_alignment_default(self):
        self.assertIsNone(CONFIG['height_connection']['H_EG_zero_in_source_datum_m'])
        self.assertFalse(CONFIG['height_connection']['common_vertical_datum_confirmed'])


if __name__ == '__main__': unittest.main(verbosity=2)
