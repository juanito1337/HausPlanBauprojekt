# -*- coding: utf-8 -*-
"""R03b regression tests; all NX objects here are simulations, not real NX."""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace as ns
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src'))
from haus2406_r03.haus_units import UnitCheckError, verify_millimeters, describe_value
from haus2406_r03.haus_nx import NXAdapter
from fake_nx import FakeNX, PartCreationUnits, BasePartReadUnits

ENTRIES=('RUN_HAUS_2406.py','SMOKE_TEST_2406.py','CHECK_HAUS_2406.py')


def load_entry(path):
    spec=importlib.util.spec_from_file_location('unitfix_'+path.stem,str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnitsContractTests(unittest.TestCase):
    def setUp(self):
        self.n=ns(BasePart=ns(Units=BasePartReadUnits),Part=ns(Units=PartCreationUnits))
        self.part=ns(PartUnits=BasePartReadUnits.Millimeters)

    def test_old_comparison_reproduces_exact_reported_message(self):
        # The R03a code used the creation enum to check a BasePart result.
        # Matching member labels are not matching enum types.
        self.assertEqual(self.part.PartUnits.name,self.n.Part.Units.Millimeters.name)
        def old_r03a_check():
            if self.part.PartUnits != self.n.Part.Units.Millimeters:
                raise RuntimeError('Neues Part ist nicht in Millimetern: FUNKTIONSTEST')
        with self.assertRaisesRegex(RuntimeError,'^Neues Part ist nicht in Millimetern: FUNKTIONSTEST$'):
            old_r03a_check()
        self.assertEqual(verify_millimeters(self.part,self.n,'FUNKTIONSTEST')['status'],
                         'MILLIMETER_BESTAETIGT')

    def test_basepart_millimeters_accepted_with_type_diagnostic(self):
        result=verify_millimeters(self.part,self.n,'TEST')
        self.assertEqual(result['expected_symbol'],'NXOpen.BasePart.Units.Millimeters')
        self.assertIn('BasePartReadUnits',result['actual']['type'])
        self.assertEqual(result['actual']['type'],result['expected']['type'])
        self.assertFalse(result['conversion_performed'])

    def test_inch_part_rejected_and_not_converted(self):
        self.part.PartUnits=BasePartReadUnits.Inches
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(self.part,self.n,'INCH')
        self.assertEqual(caught.exception.nx_unit_check['status'],'NICHT_MILLIMETER')
        self.assertIn('Inches',str(caught.exception))
        self.assertIs(self.part.PartUnits,BasePartReadUnits.Inches)

    def test_creation_enum_as_property_value_is_rejected(self):
        self.part.PartUnits=PartCreationUnits.Millimeters
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(self.part,self.n,'WRONG_TYPE')
        self.assertEqual(caught.exception.nx_unit_check['status'],'UNERWARTETER_RUECKGABETYP')

    def test_no_string_number_none_or_boolean_shortcuts(self):
        for value in (None,True,False,0,1,1.0,'MM','Millimeters','NXOpen.BasePart.Units.Millimeters'):
            with self.subTest(value=value):
                self.part.PartUnits=value
                with self.assertRaises(UnitCheckError) as caught:
                    verify_millimeters(self.part,self.n,'UNKNOWN')
                self.assertEqual(caught.exception.nx_unit_check['status'],'UNERWARTETER_RUECKGABETYP')

    def test_missing_property_reports_query_error(self):
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(ns(),self.n,'MISSING')
        self.assertEqual(caught.exception.nx_unit_check['status'],'ABFRAGE_FEHLGESCHLAGEN')
        self.assertIsInstance(caught.exception.__cause__,AttributeError)

    def test_property_read_failure_preserves_cause(self):
        class Broken:
            @property
            def PartUnits(self):
                raise RuntimeError('INJECTED_NX_UNIT_READ_ERROR')
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(Broken(),self.n,'READ_ERROR')
        self.assertIn('INJECTED_NX_UNIT_READ_ERROR',str(caught.exception))
        self.assertEqual(str(caught.exception.__cause__),'INJECTED_NX_UNIT_READ_ERROR')

    def test_missing_basepart_enum_not_replaced_by_creation_enum(self):
        del self.n.BasePart.Units
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(self.part,self.n,'API_MISSING')
        self.assertEqual(caught.exception.nx_unit_check['status'],'ABFRAGE_FEHLGESCHLAGEN')

    def test_diagnostics_are_json_safe_on_success_and_failure(self):
        result=verify_millimeters(self.part,self.n,'ERGEBNIS')
        self.assertEqual(json.loads(json.dumps(result)),result)
        self.part.PartUnits=BasePartReadUnits.Inches
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(self.part,self.n,'INCH')
        details=caught.exception.nx_unit_check
        self.assertEqual(json.loads(json.dumps(details)),details)

    def test_broken_repr_does_not_mask_unit_problem(self):
        class BrokenRepr:
            def __repr__(self):raise ValueError('INJECTED_REPR_ERROR')
        self.part.PartUnits=BrokenRepr()
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(self.part,self.n,'BAD_REPR')
        self.assertEqual(caught.exception.nx_unit_check['status'],'UNERWARTETER_RUECKGABETYP')
        self.assertIn('repr failed',caught.exception.nx_unit_check['actual']['repr'])

    def test_enum_comparison_exception_not_silently_accepted(self):
        class BrokenComparison:
            def __eq__(self,other):raise RuntimeError('INJECTED_EQUALITY_ERROR')
        unit=BrokenComparison()
        n=ns(BasePart=ns(Units=ns(Millimeters=unit)))
        with self.assertRaises(UnitCheckError) as caught:
            verify_millimeters(ns(PartUnits=unit),n,'BAD_COMPARISON')
        self.assertEqual(caught.exception.nx_unit_check['status'],'VERGLEICH_FEHLGESCHLAGEN')
        self.assertEqual(str(caught.exception.__cause__),'INJECTED_EQUALITY_ERROR')


class UnitsAdapterDoubleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.fake=FakeNX()
        self.ctx=self.fake.install();self.ctx.start();self.addCleanup(self.ctx.stop)
        self.logs=[];self.nx=NXAdapter(self.logs.append)

    def test_newdisplay_still_receives_part_enum(self):
        original=self.fake.session.Parts.NewDisplay
        with patch.object(self.fake.session.Parts,'NewDisplay',wraps=original) as call:
            part=self.nx.new_part(self.root/'MM.prt','MM')
        self.assertIs(call.call_args.args[1],self.fake.N.Part.Units.Millimeters)
        self.assertIs(part.PartUnits,self.fake.N.BasePart.Units.Millimeters)
        self.assertEqual(self.nx.unit_checks[-1]['status'],'MILLIMETER_BESTAETIGT')
        self.assertTrue(any('EINHEITENPRUEFUNG' in line for line in self.logs))

    def test_missing_read_enum_blocks_before_part_creation(self):
        del self.fake.N.BasePart.Units
        with self.assertRaisesRegex(RuntimeError,'BasePart.Units.Millimeters'):
            NXAdapter(self.logs.append)
        self.assertFalse(self.fake.session.Parts.items)

    def test_mock_rejects_basepart_enum_as_newdisplay_argument(self):
        with self.assertRaisesRegex(TypeError,'NewDisplay requires Part.Units'):
            self.fake.session.Parts.NewDisplay(self.root/'BAD.prt',self.fake.N.BasePart.Units.Millimeters)

    def test_inch_new_part_stops_before_geometry_attributes_and_save(self):
        original=self.fake.session.Parts.NewDisplay
        def wrong_units(*args):
            p=original(*args);p.PartUnits=self.fake.N.BasePart.Units.Inches;return p
        with patch.object(self.fake.session.Parts,'NewDisplay',side_effect=wrong_units):
            with self.assertRaisesRegex(RuntimeError,'nicht in Millimetern'):
                self.nx.new_part(self.root/'BAD.prt','FUNKTIONSTEST')
        self.assertEqual(self.fake.commits,0)
        self.assertFalse((self.root/'BAD.prt').exists())
        self.assertFalse(self.nx.created[0].attrs)
        self.assertEqual(self.nx.unit_checks[-1]['status'],'NICHT_MILLIMETER')
        self.assertEqual(self.nx.operation,'PartUnits: FUNKTIONSTEST')

    def test_unit_read_check_does_not_change_foreign_part(self):
        foreign=self.fake.session.Parts.NewDisplay(self.root/'USER.prt',self.fake.N.Part.Units.Millimeters)
        foreign.attrs['USER']='KEEP'
        result=self.nx.check_millimeters(foreign,'READ_ONLY_CHECK')
        self.assertEqual(result['status'],'MILLIMETER_BESTAETIGT')
        self.assertEqual(foreign.attrs,{'USER':'KEEP'})
        self.assertFalse(self.nx.created)
        self.assertFalse(Path(foreign.FullPath).exists())


class UnitsFlowDoubleTests(unittest.TestCase):
    """Bootstrap + safety behaviour, not native NX geometry or bindings."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)/'Projekt';self.base.mkdir()
        shutil.copytree(BASE/'src',self.base/'src',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(BASE/'data',self.base/'data')
        for name in ENTRIES:shutil.copy2(BASE/name,self.base/name)
        self.fake=FakeNX();self.ctx=self.fake.install();self.ctx.start();self.addCleanup(self.ctx.stop)
        self.buf=io.StringIO();self.capture=contextlib.redirect_stdout(self.buf)
        self.capture.__enter__();self.addCleanup(self.capture.__exit__,None,None,None)

    def entry(self,name):return load_entry(self.base/name)
    def reference_build(self):
        self.fake.answer=2
        result=self.entry('RUN_HAUS_2406.py').main()
        self.assertEqual(result['status'],'NX_ERZEUGT_GEOMETRISCH_UNGEPRUEFT',result.get('error'))
        return result
    def force_inches(self):
        original=self.fake.session.Parts.NewDisplay
        def wrong(*args):
            part=original(*args);part.PartUnits=self.fake.N.BasePart.Units.Inches;return part
        return patch.object(self.fake.session.Parts,'NewDisplay',side_effect=wrong)

    def test_reference_model_and_nine_part_checks_accept_read_enum(self):
        state=self.reference_build()
        self.assertEqual(state['built_solids'],0)
        self.assertEqual(state['patch'],'R06-QUELLEN-KONSISTENZ')
        self.assertEqual(len(state['unit_checks']),16)  # 2 smoke + 13 reference-mode subparts + master
        result=self.entry('CHECK_HAUS_2406.py').main()
        self.assertEqual(result['status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN',result.get('error'))
        self.assertEqual(len(result['unit_checks']),14)
        self.assertTrue(all(d['status']=='MILLIMETER_BESTAETIGT' for d in result['unit_checks']))

    def test_main_reports_actual_unit_type_and_blocks_house_on_inch(self):
        with self.force_inches():result=self.entry('RUN_HAUS_2406.py').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['nx_unit_check']['status'],'NICHT_MILLIMETER')
        self.assertEqual(self.fake.commits,0)
        self.assertFalse((self.base/'LETZTER_ERFOLGREICHER_LAUF.json').exists())
        persisted=json.loads(Path(result['report_file']).read_text())
        self.assertEqual(persisted['nx_unit_check'],result['nx_unit_check'])
        reports=list((self.base/'ausgabe').glob('HAUS_*/funktionstest/testergebnis.json'))
        smoke=json.loads(reports[0].read_text())
        self.assertEqual(smoke['unit_checks'][-1]['status'],'NICHT_MILLIMETER')
        self.assertFalse(list(self.base.rglob('HAUS_MASTER.prt')))

    def test_standalone_smoke_reports_unit_failure(self):
        with self.force_inches():result=self.entry('SMOKE_TEST_2406.py').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['nx_unit_check']['context'],'FUNKTIONSTEST')
        self.assertEqual(self.fake.commits,0)

    def test_checker_rejects_inch_master(self):
        self.reference_build();master=self.fake.session.Parts.Display
        master.PartUnits=self.fake.N.BasePart.Units.Inches
        result=self.entry('CHECK_HAUS_2406.py').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertEqual(result['nx_unit_check']['context'],'HAUS_MASTER (Nachpruefung)')
        self.assertEqual(result['nx_unit_check']['status'],'NICHT_MILLIMETER')
        self.assertIs(master.PartUnits,self.fake.N.BasePart.Units.Inches)

    def test_checker_rejects_inch_subcomponent(self):
        self.reference_build();master=self.fake.session.Parts.Display
        part=master.ComponentAssembly.children[0].Prototype
        part.PartUnits=self.fake.N.BasePart.Units.Inches
        result=self.entry('CHECK_HAUS_2406.py').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('Komponente',result['nx_unit_check']['context'])
        self.assertEqual(result['nx_unit_check']['status'],'NICHT_MILLIMETER')
        self.assertIs(part.PartUnits,self.fake.N.BasePart.Units.Inches)

    def test_missing_new_unit_module_is_explicit_for_all_entrypoints(self):
        (self.base/'src/haus2406_r03/haus_units.py').unlink()
        for name in ENTRIES:
            with self.subTest(entry=name):
                result=self.entry(name).main()
                self.assertEqual(result['status'],'ABGEBROCHEN')
                self.assertIn('haus_units.py',result['error'])
        self.assertFalse(self.fake.session.Parts.items)

    def test_mixed_r03a_module_marker_is_rejected(self):
        (self.base/'src/haus2406_r03/__init__.py').write_text(
            '__version__="R03"\n__patch__="R03a-PFADFIX"\n',encoding='utf-8')
        result=self.entry('RUN_HAUS_2406.py').main()
        self.assertEqual(result['status'],'ABGEBROCHEN')
        self.assertIn('Versionen vermischt',result['error'])
        self.assertFalse(self.fake.session.Parts.items)


if __name__=='__main__':unittest.main(verbosity=2)
