"""Full project integration with synthetic NX split-DGM responses, NOT NX execution."""
import argparse,contextlib,json,sys,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'umgebung'),str(B/'umgebung/tests'),str(B/'tests')]
from test_r09 import SceneDouble
from fake_nx import Body
from patch_double import PatchAdapter
from gesamt.core import read_json,write_json,run_project,check_records
from gesamt.nx_backend import NXBackend
SPEC=next(s for s in read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if s['id']=='DGM')

def install(env):
    original=env.active;original_faces=[None];old_dist=env.uf.Modeling.AskMinimumDist
    control=NS(cache={},faces={},edges={})
    def faces(body):
        if getattr(body,'_reference',{}).get('grid_shape')!=[102,83]:return original_faces[0](body)
        if body.Tag not in control.cache:
            a=PatchAdapter(SPEC,[(r,r+1,c,c+1) for r in range(101) for c in range(82)],reverse=True)
            for f in a.faces:
                old=f.Tag;f.Tag=body.Tag*1000000+old;f.OwningPart=body.OwningPart
                control.faces[f.Tag]=(a,old)
            for edge in a.edges.values():
                old=edge.Tag;edge.Tag=body.Tag*1000000+old;edge.OwningPart=body.OwningPart
                control.edges[edge.Tag]=(a,old)
            control.cache[body.Tag]=a
        return control.cache[body.Tag].faces
    def evaluate(tag,order,uv):
        a,old=control.faces[tag];return a.evaluate(old,order,uv)
    def limits(tag):a,old=control.faces[tag];return a.limits(old)
    def distance(o1,o2,g1,q,g2,s):
        if o2 not in control.edges:return old_dist(o1,o2,g1,q,g2,s)
        a,old=control.edges[o2];return a.distance(o1,old,g1,q,g2,s)
    env.uf.Modeling.EvaluateFace=evaluate;env.uf.Modeling.AskFaceUvMinmax=limits
    env.uf.Modeling.AskMinimumDist=distance
    @contextlib.contextmanager
    def active():
        with original():
            original_faces[0]=Body.GetFaces
            with patch.object(Body,'GetFaces',faces):yield env
    env.active=active
    return control


def run(report):
    locations=[B,B/'umgebung']; originals={p:{f.name:f.read_bytes() for f in p.glob('LETZT*.json')} for p in locations}
    try:
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);definition=root/'step214ug.def';definition.write_text('SIMULATION_ONLY_NOT_NX_DEF')
            fake=SceneDouble(definition);ctl=install(fake)
            cfg=read_json(B/'data/EINSTELLUNGEN_GESAMT.json');cfg['output_root']=str(root/'output')
            with fake.active():
                result=run_project(B,'ALL',cfg,NXBackend(B,session_provider=lambda:fake.session),verify=False)
            assert result['phase']=='ABGESCHLOSSEN'
            assert result['house']['built_solids']==1418 and result['house']['component_count']==15
            assert result['project']['utility_segments']==45
            assert result['project']['height_connection_confirmed_by_user'] is False
            assert fake.step_calls==6 and fake.mass_calls==0 and fake.face_measure_calls==0
            for key in ['house','environment','project']:check_records(result[key]['files'])
            data={'status':'FULL_PROJECT_WITH_8282_DGM_FACES_SIMULATION_PASSED','NX_tested':False,
                  'house_bodies':1418,'house_components':15,'synthetic_DGM_faces':8282,
                  'saved_components_checked':True,'step_calls':fake.step_calls,
                  'house_not_downgraded':True,'height_offset_not_guessed':True,
                  'physical_utility_depths_confirmed':False,'source_parts_not_resaved':True,
                  'notes':'Synthetic NX calls; temporary placeholder files are NOT native NX files and are deleted.'}
        write_json(report,data);print(json.dumps(data,indent=2))
    finally:
        for loc in locations:
            for f in loc.glob('LETZT*.json'):
                if f.name not in originals[loc]:f.unlink()
            for name,value in originals[loc].items():(loc/name).write_bytes(value)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);a=p.parse_args();run(Path(a.report))
