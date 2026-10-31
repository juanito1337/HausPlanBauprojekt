# -*- coding: utf-8 -*-
"""Offline: genuine source STEP loading and rigid translation in Open CASCADE.
This does not test the NX translator, NX load state, or a survey datum.
"""
import math,sys,json
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path.insert(0,str(B))
from g02.height import height_plan
from g02.height_model import Grid
from gesamt.core import read_json,write_json,sha256

def check(out):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool
    from OCP.BRepTools import BRepTools
    from OCP.gp import gp_Trsf,gp_Vec
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    p=height_plan(B,read_json(B/'data/EINSTELLUNGEN_GESAMT.json'))
    grid=Grid(read_json(B/'data/DGM_STUETZPUNKTE_G02.json'))
    specs=[s for s in read_json(B/'umgebung/data/IMPORTAUFTRAG_R09.json')['parts'] if s['id'] in ['DGM','V01','V02','V03','V05']]
    tr=gp_Trsf();tr.SetTranslation(gp_Vec(*p['translation_mm']))
    rows=[];anchor_error=None
    for spec in specs:
        path=B/'umgebung'/spec['step_file'];original_hash=sha256(path)
        rd=STEPControl_Reader()
        if rd.ReadFile(str(path))!=IFSelect_RetDone:raise RuntimeError('STEP source read failed')
        rd.TransferRoots();shape=rd.OneShape()
        exp=TopExp_Explorer(shape,TopAbs_FACE);faces=[]
        while exp.More():faces.append(TopoDS.Face_s(exp.Current()));exp.Next()
        if len(faces)!=spec['expected_faces']:raise RuntimeError('Unexpected SOURCE face count')
        maximum=0.;count=0;all_valid=True
        for face in faces:
            uv=BRepTools.UVBounds_s(face);surface=BRep_Tool.Surface_s(face)
            movedface=TopoDS.Face_s(BRepBuilderAPI_Transform(face,tr,True).Shape())
            moved=BRep_Tool.Surface_s(movedface)
            all_valid=all_valid and BRepCheck_Analyzer(movedface).IsValid()
            fractions=[(0,0),(0,1),(1,0),(1,1),(.5,.5),(.25,.75),(.75,.25)]
            for a,b in fractions:
                u=uv[0]+a*(uv[1]-uv[0]);v=uv[2]+b*(uv[3]-uv[2])
                x=surface.Value(u,v);y=moved.Value(u,v)
                error=math.dist([x.X(),x.Y(),x.Z()+p['translation_mm'][2]],[y.X(),y.Y(),y.Z()])
                maximum=max(maximum,error);count+=1
            if spec['id']=='DGM':
                if len(faces)!=1 or max(abs(a-b) for a,b in zip(uv,(0.,101.,0.,82.)))>1e-6:
                    raise RuntimeError('DGM source parametrization unexpected')
                for i in range(grid.nu):
                    for j in range(grid.nv):
                        expected=grid.nodes[i*grid.nv+j];x=moved.Value(i,j)
                        error=math.dist([expected[0],expected[1],expected[2]+p['translation_mm'][2]],[x.X(),x.Y(),x.Z()])
                        maximum=max(maximum,error);count+=1
                anchor=moved.Value(*p['anchor']['grid_uv'])
                anchor_error=abs(anchor.Z()-p['target_ground_z_mm'])
        if not all_valid or maximum>1e-5 or sha256(path)!=original_hash:raise RuntimeError('Invalid transformed reference')
        rows.append({'id':spec['id'],'actual_source_faces':len(faces),'source_sha256':original_hash,
                     'transformed_faces_valid':all_valid,'position_comparisons':count,'max_translation_error_mm':maximum})
    result={'status':'G02_HOEHEN_TRANSFORMATION_OCCT_BESTANDEN','NX_tested':False,'Parasolid_tested':False,
            'translation_mm':p['translation_mm'],'grid_nodes_checked':8466,'groups':rows,
            'all_selected_surface_faces':sum(r['actual_source_faces'] for r in rows),
            'comparisons':sum(r['position_comparisons'] for r in rows),'anchor_target_mm':p['target_ground_z_mm'],
            'anchor_error_mm':anchor_error,'original_files_unchanged':True,
            'site_alignment_surveyed':False,
            'scope':'Actual STEP/Open-CASCADE rigid translation; independent of NX runtime. Same translation for all selected vegetation and ground; no terrain reshaping.'}
    if anchor_error>1e-5:raise RuntimeError('Translated anchor inconsistent')
    write_json(out,result);print(json.dumps(result,indent=2));return result
if __name__=='__main__':check(Path(sys.argv[sys.argv.index('--report')+1]))
