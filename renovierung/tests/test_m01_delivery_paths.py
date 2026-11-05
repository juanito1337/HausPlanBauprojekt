"""Pure delivery-path contracts; these tests provide no NX evidence."""
import copy
import importlib.util
import importlib
import json
from pathlib import Path
import tempfile
import sys
import types
import unittest

from renovierung.m01 import delivery_paths as paths, inspection, standalone
ROOT=Path(__file__).resolve().parents[2]


def archived_register():
    layout=json.loads((ROOT/'cad/nx/m01/20261103T005043Z_07d05f/BUILD.json').read_bytes())['layout']
    layout['review_masters']=inspection.build_review_index(layout)
    layout['default_state']='PS01-F01'
    return {'layout':layout}

class DeliveryPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.layout={'master':'MASTER.prt','nodes':[{'file':'MASTER.prt'}, {'file':'gruppen/SECTION_PS01.prt'},
                      {'file':'studien/PS01-F01_STUDY.prt'},{'file':'studien/PS01-F01_STUDY.prt'}],
                     'review_masters':[{'file':'Bauabschnitte/PS01/PS01-F01.prt'}]}

    def test_flat_bijection_roundtrips_and_preserves_logical_metadata(self):
        before=copy.deepcopy(self.layout)
        mapping=paths.make_file_map(self.layout)
        self.assertEqual(mapping,{'MASTER.prt':'MASTER.prt','gruppen/SECTION_PS01.prt':'SECTION_PS01.prt',
                                 'studien/PS01-F01_STUDY.prt':'PS01-F01_STUDY.prt',
                                 'Bauabschnitte/PS01/PS01-F01.prt':'PS01-F01.prt'})
        self.assertEqual(self.layout,before)
        for logical,basename in mapping.items():
            physical=paths.mapfile(self.root,logical,mapping)
            self.assertEqual(physical,self.root/basename)
            self.assertEqual(paths.logicalfile(self.root,physical,mapping),logical)
        self.assertEqual(paths.mapfile(self.root,'gruppen/SECTION_PS01.prt'),self.root/'gruppen/SECTION_PS01.prt')
        self.assertEqual(paths.logicalfile(self.root,self.root/'gruppen/SECTION_PS01.prt'),'gruppen/SECTION_PS01.prt')

    def test_collisions_casefold_duplicates_unsafe_roots_and_escape_fail_closed(self):
        for extra in ('other/PS01-F01_STUDY.prt','other/ps01-f01_study.PRT','GRUPPEN/section_ps01.prt'):
            layout=copy.deepcopy(self.layout);layout['nodes'].append({'file':extra})
            with self.subTest(extra=extra),self.assertRaises(ValueError):paths.make_file_map(layout)
        bad_paths=('../x.prt','/x.prt','C:/x.prt','C:x.prt','\\\\server\\x.prt',
                   'gruppen\\x.prt','gruppen/../x.prt','gruppen//x.prt','./x.prt','x.prt ','.prt','CON.prt')
        mapping=paths.make_file_map(self.layout)
        for logical in bad_paths:
            with self.subTest(logical=logical),self.assertRaises(ValueError):paths.mapfile(self.root,logical,mapping)
        for mapping in ({'gruppen/A.prt':'nested/A.prt'}, {'gruppen/A.prt':'B.prt'},
                        {'gruppen/A.prt':'A.prt','other/a.prt':'a.prt'}, {'../A.prt':'A.prt'}, {}):
            with self.subTest(mapping=mapping),self.assertRaises(ValueError):paths.mapfile(self.root,'gruppen/A.prt',mapping)
        for actual in (self.root.parent/'outside.prt',self.root/'nested/SECTION_PS01.prt',self.root/'UNKNOWN.prt',Path('MASTER.prt')):
            with self.subTest(actual=actual),self.assertRaises(ValueError):paths.logicalfile(self.root,actual,paths.make_file_map(self.layout))

    def test_archived_project_and_entries_have_unique_casefold_basenames(self):
        request=archived_register()
        mapping=paths.make_file_map(request['layout'])
        self.assertEqual(len(mapping),234)
        self.assertEqual(len({v.casefold() for v in mapping.values()}),234)
        for logical in mapping:
            self.assertEqual(paths.logicalfile(self.root,paths.mapfile(self.root,logical,mapping),mapping),logical)

    def test_inspector_prototype_checks_use_the_bijection_not_just_root_containment(self):
        mapping=paths.make_file_map(self.layout)
        correct=self.root/'SECTION_PS01.prt'
        self.assertIsNone(inspection._prototype_path(self.root,'gruppen/SECTION_PS01.prt',correct,mapping))
        for wrong in (self.root/'MASTER.prt',self.root/'gruppen/SECTION_PS01.prt',self.root.parent/'SECTION_PS01.prt'):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):
                inspection._prototype_path(self.root,'gruppen/SECTION_PS01.prt',wrong,mapping)

    def test_default_probe_matrix_has_one_master_35_reviews_and_85_isolated_entries(self):
        request=archived_register()
        layout=request['layout'];before=copy.deepcopy(layout)
        rows=standalone._default_entries(layout)
        self.assertEqual(len(rows),121)
        self.assertEqual({kind:sum(r['kind']==kind for r in rows) for kind in ('master','review','subassembly')},
                         {'master':1,'review':35,'subassembly':85})
        self.assertEqual(len({r['file'] for r in rows}),121)
        self.assertEqual(layout,before)


if __name__=='__main__':unittest.main()
