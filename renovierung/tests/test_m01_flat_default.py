"""Pure recorded-evidence gate tests, no simulated NX-success claim."""
import copy
import importlib
import json
from pathlib import Path
import sys
import types
import unittest

from renovierung.m01 import standalone as module
from renovierung.m01.presentation import camera_spec
from renovierung.tests.test_m01_delivery_paths import archived_register


class DefaultRecordedEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout=archived_register()['layout']
        cls.layout['presentation']=camera_spec([[-1000,-1000,0],[1000,1000,1200]])
        cls.rows=module._default_entries(cls.layout)
        nodes={n['id']:n for n in cls.layout['nodes']};fields={f['node_id']:f for f in cls.layout['fields']}
        spec=cls.layout['presentation']
        presentation={'camera':{'absolute_origin_mm':spec['origin_mm'],'matrix':spec['matrix'],'scale':spec['scale']},
                      'shaded_with_edges':True,'layers':{str(n):{'visible':True,'selectable':True,'hidden':False}
                                                      for n in (101,102,103,104,200,201,210)}}
        cls.actual={}
        for entry in cls.rows:
            parent='MASTER' if entry['kind'] in ('master','review') else entry['id']
            direct={nid:n['file'] for nid,n in nodes.items() if n['parent']==parent}
            expected={nid for nid,n in nodes.items() if n['kind']=='role' and
                      fields[n['parent']]['id']==entry['state'] and not n['blank']}
            markers=entry.get('marker_ids')
            if markers is None:
                markers=[f['id'] for f in cls.layout['fields'] if f['id']==entry['state'] or f['sector_id']==entry['state']]
            loaded={entry['file']}|set(direct.values())
            if entry['kind']=='review':loaded.add(cls.layout['master'])
            root='C:/flat/default_delivery'
            cls.actual[entry['file']]={'id':entry['id'],'file':entry['file'],'kind':entry['kind'],'state':entry['state'],
                'presentation':copy.deepcopy(presentation),'snapshot_before_reference_walk':True,
                'files_saved':False,'exact_brep_verified':False,'brep_mass_measurements_performed':False,
                'all_loaded_paths_internal':True,'all_prototype_paths_match_map':True,'flat_delivery':True,
                'root_directory':root,'root_full_path':root+'/'+Path(entry['file']).name,
                'loaded_files':sorted(loaded),'loaded_full_paths':{f:root+'/'+Path(f).name for f in loaded},
                'load_options':{'requested_component_load_method':'FromDirectory','component_load_method_matches_requested':True,
                                'supplementary_search_directories':[]},
                'direct_references':direct,'root_direct_references':{'MASTER':cls.layout['master']} if entry['kind']=='review' else direct,
                'selected_role_ids':sorted(expected),'selected_role_proxy_ids':sorted(expected),
                'selected_role_proxy_match_complete':True,
                'effective_role_components':{nid:{'effective_visible':True,'reference_set':nodes[nid]['reference_set']} for nid in expected},
                'display_snapshot':{'native_visible_object_count':len(expected)+len(markers),
                    'component_display_proxies':len(expected)+len(markers),'brep_display_objects':0,'facet_display_objects':0,
                    'visible_node_ids':sorted(expected),'component_proxy_node_ids':sorted(expected),
                    'visible_marker_ids':[],'visible_marker_proxy_ids':markers,'unclassified_geometry_objects':0,
                    'exact_brep_body_counts_verified':False}}

    def test_all_121_recorded_entries_accept_visible_component_proxies_without_claiming_breps(self):
        self.assertEqual(len(self.actual),121)
        self.assertEqual(module.validate_default_entries(self.layout,self.actual),[])

    def test_missing_wrong_or_not_immediate_default_evidence_is_rejected(self):
        key=next(r['file'] for r in self.rows if r['id']=='PS01-F02')
        for mutation in ('missing','state','file','camera','snapshot','search','load_method','external',
                         'false_brep','missing_proxy','excavation_proxy','reserve_proxy'):
            actual=copy.deepcopy(self.actual);row=actual[key]
            if mutation=='missing':actual.pop(key)
            if mutation=='state':row['state']='PS01-F01'
            if mutation=='file':row['file']='wrong.prt'
            if mutation=='camera':row['presentation']['camera']['scale']*=2
            if mutation=='snapshot':row['snapshot_before_reference_walk']=False
            if mutation=='search':row['load_options']['supplementary_search_directories']=['C:/old']
            if mutation=='load_method':row['load_options']['requested_component_load_method']='AsSaved'
            if mutation=='external':row['root_full_path']='C:/old/PS01-F02.prt'
            if mutation=='false_brep':row['exact_brep_verified']=True
            if mutation=='missing_proxy':row['display_snapshot']['visible_node_ids'].clear()
            if mutation in ('excavation_proxy','reserve_proxy'):
                suffix='EXCAVATION' if mutation=='excavation_proxy' else 'PILE_RESERVE'
                row['display_snapshot']['visible_node_ids'].append('ROLE_PS01-F02_'+suffix)
            with self.subTest(mutation=mutation):
                self.assertTrue(module.validate_default_entries(self.layout,actual))


if __name__=='__main__':unittest.main()
