"""Synthetic evidence tests; these do not claim an NX execution."""
import copy
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from renovierung.m01.runner import validate_result, exclusive_build, wait_for_journal_slot


def fixture():
    ident = [1.,0.,0.,0.,1.,0.,0.,0.,1.]
    nodes = []
    for nid, parent, file, kind, xyz, hidden in [
        ('MASTER', None, 'master.prt', 'assembly', [0.,0.,0.], False),
        ('ENVIRONMENT', 'MASTER', 'env.prt', 'assembly', [0.,0.,-10.], False),
        ('TERRAIN', 'ENVIRONMENT', 'terrain.prt', 'source', [0.,0.,0.], False),
        ('FIELD_F01', 'MASTER', 'field.prt', 'field', [0.,0.,0.], True),
        ('ROLE_F01_CUT_SOIL', 'FIELD_F01', 'study.prt', 'role', [0.,0.,0.], False),
    ]:
        nodes.append(dict(id=nid,parent=parent,file=file,kind=kind,name=nid,
            translation_mm=xyz,rotation=ident[:],blank=hidden,reference_set='Entire Part'))
    nodes[-1].update(role='cut_soil',reference_set='M01_CUT_SOIL')
    measurement=dict(body_count=1,component_volumes_m3=[12.],volume_m3=12.)
    layout=dict(master='master.prt',nodes=nodes,fields=[dict(id='F01',node_id='FIELD_F01',native=True,
        measurements={'cut_soil':measurement})],sources=[],construction_release=False)
    actual={n['id']:{k:copy.deepcopy(n[k]) for k in
        ('parent','file','name','translation_mm','rotation','blank','reference_set')} for n in nodes}
    actual['TERRAIN']['translation_mm']=[0.,0.,-10.]
    actual['ROLE_F01_CUT_SOIL']['blank']=True
    for node in actual.values(): node['suppressed']=False
    paths=sorted(n['file'] for n in nodes)
    result=dict(status='PASS',master='master.prt',nodes=actual,parts=paths,
        measurements={'F01':{'cut_soil':copy.deepcopy(measurement)}},
        refsets={'study.prt':{'M01_CUT_SOIL':['K02_cut_soil_00']}},
        toggle_checks=[n['id'] for n in nodes if n['id']!='MASTER'],state_checks=['BASE','F01'],
        dependencies={p:{'interpart_parents':[],'expression_references':[]} for p in paths},
        all_parts_mm=True,all_parts_fully_loaded=True,all_paths_internal=True,construction_release=False)
    return layout,result


class EvidenceTests(unittest.TestCase):
    def test_matching_synthetic_evidence(self):
        layout,result=fixture(); self.assertEqual(validate_result(layout,result),[])

    def test_rejects_display_hierarchy_and_transform_errors(self):
        for node,key,value in [('TERRAIN','translation_mm',[0.,0.,-20.]),
            ('TERRAIN','blank',True),('FIELD_F01','parent','ENVIRONMENT'),
            ('ROLE_F01_CUT_SOIL','reference_set','Entire Part'),('TERRAIN','suppressed',True)]:
            with self.subTest(key=key):
                layout,result=fixture();result['nodes'][node][key]=value
                self.assertTrue(validate_result(layout,result))

    def test_rejects_visible_role_below_hidden_field(self):
        layout,result=fixture()
        result['nodes']['ROLE_F01_CUT_SOIL']['blank']=False
        self.assertTrue(validate_result(layout,result))

    def test_rejects_missing_and_duplicate_toggle_tests(self):
        for key in ('toggle_checks','state_checks'):
            layout,result=fixture(); result[key]=result[key][:-1]
            self.assertTrue(validate_result(layout,result))
            layout,result=fixture(); result[key].append(result[key][0])
            self.assertTrue(validate_result(layout,result))

    def test_rejects_missing_field_and_wrong_volume(self):
        layout,result=fixture(); result['measurements']={}
        self.assertTrue(validate_result(layout,result))
        for value in (float('nan'),-1.,0.,24.):
            layout,result=fixture();m=result['measurements']['F01']['cut_soil']
            m.update(volume_m3=value,component_volumes_m3=[value])
            self.assertTrue(validate_result(layout,result))

    def test_rejects_wrong_refset_members(self):
        for names in ([],['K02_excavation_00'],['K02_cut_soil_00','K02_cut_soil_00']):
            layout,result=fixture();result['refsets']['study.prt']['M01_CUT_SOIL']=names
            self.assertTrue(validate_result(layout,result))

    def test_accepts_native_uppercase_body_names(self):
        layout,result=fixture()
        result['refsets']['study.prt']['M01_CUT_SOIL']=['K02_CUT_SOIL_00']
        self.assertEqual(validate_result(layout,result),[])

    def test_accepts_native_case_normalization_but_not_different_names(self):
        layout,result=fixture()
        layout['nodes'][2]['name']='Bestandsgelaende'
        result['nodes']['TERRAIN']['name']='BESTANDSGELAENDE'
        self.assertEqual(validate_result(layout,result),[])
        result['nodes']['TERRAIN']['name']='ANDERES_GELAENDE'
        self.assertTrue(validate_result(layout,result))

    def test_rejects_external_dependency_and_unknown_part(self):
        layout,result=fixture();result['dependencies']['terrain.prt']['interpart_parents']=['../original.prt']
        self.assertTrue(validate_result(layout,result))
        layout,result=fixture();result['parts'].append('unexpected.prt')
        self.assertTrue(validate_result(layout,result))

    def test_fail_closed_malformed_evidence(self):
        layout,result=fixture()
        for broken in ({},None,dict(result,nodes=None),dict(result,measurements=None)):
            self.assertTrue(validate_result(layout,broken))

    def test_build_lock_never_overwrites_or_removes_foreign_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            lock=Path(directory)/'native.lock'
            with exclusive_build(lock):
                before=lock.read_bytes()
                with self.assertRaises(RuntimeError):
                    with exclusive_build(lock): pass
                self.assertEqual(lock.read_bytes(),before)
            self.assertFalse(lock.exists())

    def test_foreign_journal_slot_is_waited_for_without_process_mutation(self):
        with patch('renovierung.m01.runner.assert_journal_idle',side_effect=[RuntimeError('busy'),None]) as check, \
                patch('renovierung.m01.runner.time.sleep') as sleep:
            wait_for_journal_slot(timeout=60,poll_seconds=1)
        self.assertEqual(check.call_count,2)
        sleep.assert_called_once_with(1)

    def test_foreign_journal_timeout_fails_without_taking_over(self):
        with patch('renovierung.m01.runner.assert_journal_idle',side_effect=RuntimeError('busy')), \
                patch('renovierung.m01.runner.time.sleep') as sleep:
            with self.assertRaises(TimeoutError):wait_for_journal_slot(timeout=0)
        sleep.assert_not_called()


if __name__=='__main__': unittest.main()
