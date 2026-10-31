# -*- coding: utf-8 -*-
"""Focused G02 tests. Any temporary .prt here is explicitly a TESTDOUBLE, not NX."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
B=Path(__file__).absolute().parents[1];sys.path.insert(0,str(B))
from gesamt.core import read_json,write_json,saved_record
from g02 import PATCH
from g02.height import height_plan,component_placements,verify_placement_rows
from g02.height_model import Grid,placement
from g02.workflow import run,prior_results,verify_delivery,read_result,store_result
from g02.nx_backend import modified_flag,displayed_manifest,NXBackendG02
CFG=read_json(B/'data/EINSTELLUNGEN_GESAMT.json')
SETTINGS=read_json(B/'data/HOEHENANSCHLUSS_G02.json')
GRID=Grid(read_json(B/'data/DGM_STUETZPUNKTE_G02.json'))
PLAN=height_plan(B,CFG)

def result(root,kind):
    p=Path(root)/kind;p.mkdir(exist_ok=True)
    f=p/('HAUS_MASTER.prt' if kind=='house' else 'UMGEBUNG_MASTER_R09.prt')
    f.write_text('TESTDOUBLE_NOT_NX_PART\n'+kind)
    r={'kind':kind,'master':str(f),'files':[saved_record(f)],'status':'GESPEICHERT_UND_DATEIGEPRUEFT',
       'as_built_verified':False}
    if kind=='house':r.update(revision='MAIN01-A01',mode='PRUEFMODELL_MIT_NAEHERUNGEN',built_solids=1418)
    else:r.update(surface_validation='BASIS',new_house_built_by_environment=False)
    return r

class Stub:
    def __init__(self,fail=None,accept=True,manifest=None):
        self.calls=[];self.fail=fail;self.accept=accept;self.manifest=manifest;self.audit={}
    def preflight(self,*a):self.calls.append('preflight')
    def confirm_height(self,*a):self.calls.append('confirm');return self.accept
    def build_house(self,out,cfg):self.calls.append('house');return result(out,'house')
    def build_environment(self,out,cfg):
        self.calls.append('environment')
        if self.fail=='environment':raise RuntimeError('INJECTED_ENVIRONMENT_FAILURE')
        return result(out,'environment')
    def assemble_aligned(self,out,h,e,p):
        self.calls.append('assemble')
        if self.fail=='assemble':raise RuntimeError('INJECTED_MONTAGE_FAILURE')
        f=Path(out)/'PROJECT.prt';f.write_text('TESTDOUBLE_NOT_NX_PART')
        return {'master':str(f),'files':[saved_record(f)],'height_mounted':True,'height_plan':p,
                'environment_translation_mm':list(p['translation_mm'])}
    def select_previous_manifest(self):return self.manifest,str(Path(self.manifest).parent/'OLD_MASTER.prt')
    def check_open_reuse_sources(self,*a):self.calls.append('source_states')

class HeightTests(unittest.TestCase):
    def test_01_default_offset(self):self.assertAlmostEqual(PLAN['translation_mm'][2],-31362.49870845903,8)
    def test_02_anchor_target(self):self.assertAlmostEqual(PLAN['anchor']['source_z_mm']+PLAN['translation_mm'][2],-300.,8)
    def test_03_not_surveyed(self):self.assertFalse(PLAN['site_alignment_surveyed']);self.assertFalse(PLAN['absolute_height_independently_verified'])
    def test_04_plan_no_datum_claim(self):self.assertFalse(PLAN['datum_confirmation_is_user_claim'])
    def test_05_weight_sum(self):self.assertAlmostEqual(sum(PLAN['anchor']['weights']),1,12)
    def test_06_all_four_supports(self):self.assertEqual(len(PLAN['anchor']['support_points_mm']),4)
    def test_07_source_nodes_count(self):self.assertEqual(len(GRID.nodes),8466)
    def test_08_no_xy_offset(self):self.assertEqual(PLAN['translation_mm'][:2],[0.,0.])
    def test_09_vegetation_follows_parent(self):self.assertTrue(set(['V01','V02','V03','V05']).issubset(PLAN['applies_to']))
    def test_10_utility_excluded(self):self.assertIn('LEITUNGSPLAN_Z0',PLAN['excludes'])
    def test_11_second_height_rejected(self):
        cfg=copy.deepcopy(CFG);cfg['height_connection']['H_EG_zero_in_source_datum_m']=31.
        with self.assertRaises(ValueError):height_plan(B,cfg)
    def test_12_actual_absolute_mode(self):
        s=copy.deepcopy(SETTINGS);s.update(mode='ABSOLUTE_EG_HOEHE',ground_z_relative_eg_mm=None,absolute_eg_source_m=31.4,
             common_vertical_datum_confirmed=True,source='SYNTHETIC TEST NOT A SURVEY')
        p=placement(s,GRID);self.assertEqual(p['translation_mm'][2],-31400.);self.assertFalse(p['absolute_height_independently_verified'])
    def test_13_absolute_without_datum(self):
        s=copy.deepcopy(SETTINGS);s.update(mode='ABSOLUTE_EG_HOEHE',ground_z_relative_eg_mm=None,absolute_eg_source_m=31.4)
        with self.assertRaises(ValueError):placement(s,GRID)
    def test_14_no_fake_datum_on_plan(self):
        s=copy.deepcopy(SETTINGS);s['common_vertical_datum_confirmed']=True
        with self.assertRaises(ValueError):placement(s,GRID)
    def test_15_outside_grid(self):
        s=copy.deepcopy(SETTINGS);s['anchor_xy_mm']=[1e9,1e9]
        with self.assertRaises(ValueError):placement(s,GRID)
    def test_16_nonfinite_or_bool_target(self):
        for v in [True,float('nan'),float('inf'),'300']:
            s=copy.deepcopy(SETTINGS);s['ground_z_relative_eg_mm']=v
            with self.subTest(v=v),self.assertRaises(ValueError):placement(s,GRID)
    def test_17_measured_anchor_remains_dgm_dependent(self):
        s=copy.deepcopy(SETTINGS);s.update(mode='AUFMASSPUNKT',ground_z_relative_eg_mm=-420,source='TEST ONLY')
        p=placement(s,GRID);self.assertAlmostEqual(p['translation_mm'][2]+p['anchor']['source_z_mm'],-420)
        self.assertFalse(p['site_alignment_surveyed'])
    def test_18_source_description_required(self):
        s=copy.deepcopy(SETTINGS);s['source']=' '
        with self.assertRaises(ValueError):placement(s,GRID)
    def test_19_height_not_rounded_before_assembly(self):self.assertNotEqual(PLAN['translation_mm'][2],round(PLAN['translation_mm'][2],0))
    def test_20_settings_no_mutation(self):
        s=copy.deepcopy(SETTINGS);placement(s,GRID);self.assertEqual(s,SETTINGS)

class PlacementTests(unittest.TestCase):
    def rows(self):return [{'translation_mm':list(x),'identity_rotation':True} for x in ([0,0,0],PLAN['translation_mm'],[0,0,0])]
    def test_01_readback_pass(self):self.assertLess(verify_placement_rows(self.rows(),PLAN)['anchor_error_mm'],1e-7)
    def test_02_wrong_sign(self):
        rows=self.rows();rows[1]['translation_mm'][2]*=-1
        with self.assertRaises(ValueError):verify_placement_rows(rows,PLAN)
    def test_03_double_shift(self):
        rows=self.rows();rows[1]['translation_mm'][2]*=2
        with self.assertRaises(ValueError):verify_placement_rows(rows,PLAN)
    def test_04_house_not_moved(self):
        rows=self.rows();rows[0]['translation_mm'][2]=100
        with self.assertRaises(ValueError):verify_placement_rows(rows,PLAN)
    def test_05_leitungen_not_given_fake_depth(self):
        rows=self.rows();rows[2]['translation_mm'][2]=-800
        with self.assertRaises(ValueError):verify_placement_rows(rows,PLAN)
    def test_06_rotation_rejected(self):
        rows=self.rows();rows[1]['identity_rotation']=False
        with self.assertRaises(ValueError):verify_placement_rows(rows,PLAN)
    def test_07_missing_child(self):
        with self.assertRaises(ValueError):verify_placement_rows(self.rows()[:2],PLAN)
    def test_08_repeat_absolute(self):
        a=component_placements('h','e','u',PLAN);b=component_placements('h','e','u',PLAN)
        self.assertEqual(a,b);self.assertEqual(a[1][2],PLAN['translation_mm'])

class WorkflowTests(unittest.TestCase):
    def call(self,t,mode='ALL',stub=None):
        cfg=copy.deepcopy(CFG);cfg['output_root']=str(Path(t)/'out')
        return run(t,mode,stub or Stub(),verify=False,config=cfg,plan_override=copy.deepcopy(PLAN))
    def test_01_order_and_integrated_height(self):
        with tempfile.TemporaryDirectory() as t:
            stub=Stub();s=self.call(t,stub=stub)
            self.assertEqual(stub.calls,['preflight','confirm','house','environment','assemble'])
            self.assertTrue(s['project']['height_mounted']);self.assertFalse(s['old_H01_montage_invoked'])
    def test_02_no_height_confirmation_no_build(self):
        with tempfile.TemporaryDirectory() as t:
            stub=Stub(accept=False);s=self.call(t,stub=stub)
            self.assertEqual(stub.calls,['preflight','confirm']);self.assertIsNone(s['house'])
    def test_03_env_failure_preserves_house(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RuntimeError):self.call(t,stub=Stub(fail='environment'))
            self.assertTrue(Path(read_result(t,'house')['master']).is_file())
            self.assertFalse((Path(t)/'LETZTE_UMGEBUNG_G02.json').exists())
    def test_04_montage_failure_preserves_both(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RuntimeError):self.call(t,stub=Stub(fail='assemble'))
            for k in ('house','environment'):self.assertTrue(Path(read_result(t,k)['master']).is_file())
    def test_05_house_only_no_env(self):
        with tempfile.TemporaryDirectory() as t:
            stub=Stub();self.call(t,'HOUSE',stub);self.assertEqual(stub.calls,['preflight','house'])
    def test_06_env_only_no_house(self):
        with tempfile.TemporaryDirectory() as t:
            stub=Stub();self.call(t,'ENVIRONMENT',stub);self.assertEqual(stub.calls,['preflight','environment'])
    def test_07_assemble_no_rebuild(self):
        with tempfile.TemporaryDirectory() as t:
            self.call(t,'HOUSE');self.call(t,'ENVIRONMENT');stub=Stub();s=self.call(t,'ASSEMBLE',stub)
            self.assertEqual(stub.calls,['preflight','confirm','assemble']);self.assertTrue(s['project']['height_mounted'])
    def test_08_reuse_no_project_geometry_read(self):
        with tempfile.TemporaryDirectory() as t:
            first=self.call(t);stub=Stub(manifest=Path(first['output_directory'])/'manifest_G02.json')
            s=self.call(t,'REUSE',stub)
            self.assertEqual(stub.calls,['source_states','confirm','assemble'])
            self.assertTrue(s['old_project_master_changes_not_carried_over'])
    def test_09_reject_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'m.json';write_json(p,{'patch':PATCH,'status':'ABGEBROCHEN'})
            with self.assertRaises(ValueError):prior_results(p)
    def test_10_reject_modified_source(self):
        with tempfile.TemporaryDirectory() as t:
            s=self.call(t);Path(s['house']['master']).write_text('CHANGED')
            with self.assertRaises(ValueError):prior_results(Path(s['output_directory'])/'manifest_G02.json')
    def test_11_patch_no_old_R11(self):
        with tempfile.TemporaryDirectory() as t:
            s=self.call(t);p=Path(s['output_directory'])/'manifest_G02.json';d=read_json(p);d['patch']='R11';write_json(p,d)
            with self.assertRaises(ValueError):prior_results(p)
    def test_12_unique_output_dirs(self):
        with tempfile.TemporaryDirectory() as t:self.assertNotEqual(self.call(t,'HOUSE')['output_directory'],self.call(t,'HOUSE')['output_directory'])
    def test_13_invalid_mode(self):
        with self.assertRaises(ValueError):run(B,'UNKNOWN')
    def test_14_no_fake_success_from_project(self):
        class Bad(Stub):
            def assemble_aligned(self,*args):
                r=super().assemble_aligned(*args);r['height_mounted']=False;return r
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(RuntimeError):self.call(t,stub=Bad())

class SourceStateTests(unittest.TestCase):
    def test_01_clean_property(self):self.assertFalse(modified_flag(NS(IsModified=False,FullPath='p')))
    def test_02_dirty_property(self):self.assertTrue(modified_flag(NS(IsModified=True,FullPath='p')))
    def test_03_method_called(self):self.assertFalse(modified_flag(NS(IsModified=lambda:False,FullPath='p')))
    def test_04_integer_only_zero_one(self):
        self.assertFalse(modified_flag(NS(IsModified=0,FullPath='p')))
        with self.assertRaises(RuntimeError):modified_flag(NS(IsModified=2,FullPath='p'))
    def test_05_missing_rejected(self):
        with self.assertRaises(RuntimeError):modified_flag(NS(FullPath='p'))
    def test_06_display_lookup_does_not_read_dirty_flag(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'manifest_G01.json';p.write_text('{}')
            class Old:
                FullPath=str(Path(t)/'PROJEKT_MASTER_G01_HOEHENBEZUG_OFFEN.prt')
                @property
                def IsModified(self):raise AssertionError('Old dirty flag must not be read')
                @property
                def ComponentAssembly(self):raise AssertionError('Old tree must not be read')
            got,_=displayed_manifest(NS(Parts=NS(Display=Old())))
            self.assertEqual(got,p)
    def test_07_dirty_source_still_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            h=result(t,'house');e=result(t,'environment')
            backend=NXBackendG02(B,lambda:NS(Parts=[NS(FullPath=h['master'],IsModified=True)]))
            with self.assertRaisesRegex(RuntimeError,'QUELLKOMPONENTE'):backend.check_open_reuse_sources(h,e)
    def test_08_dirty_old_master_not_source(self):
        with tempfile.TemporaryDirectory() as t:
            h=result(t,'house');e=result(t,'environment')
            parts=[NS(FullPath=str(Path(t)/'OLD_MASTER.prt'),IsModified=True),NS(FullPath=h['master'],IsModified=False)]
            backend=NXBackendG02(B,lambda:NS(Parts=parts));backend.check_open_reuse_sources(h,e)
            self.assertEqual(len(backend.audit['source_state_checks']),1)

if __name__=='__main__':unittest.main(verbosity=2)
