"""Echter STEP-Rueckimport mit Open CASCADE, kein NX-Lauf.
Benoetigt numpy und cadquery/OCP nur in der Offline-Umgebung.
Die NX-Journaldatei benoetigt diese Pakete NICHT.
"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import cadquery as cq
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
BASE=Path(__file__).absolute().parents[1]
sys.path.insert(0,str(BASE))
from r09.core import compare_boxes,read_json,sha256,write_json

def box(shape):
    b=shape.BoundingBox();return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]

def run():
    job=read_json(BASE/'data/IMPORTAUFTRAG_R09.json')
    old=read_json(BASE/'basis/Vegetation_R08/data/BAUAUFTRAG_VEGETATION_R08.json')
    arrays=dict(np.load(BASE/'basis/Vegetation_R08/data/RASTER_AUSWERTUNG_R08.npz',allow_pickle=False))
    originals={p['id']:p for p in old['parts']}
    rows=[];samples=0;max_distance=0.
    for spec in job['parts']+[job['smoke_test']]:
        path=BASE/spec['step_file'];sh=cq.importers.importStep(str(path)).val()
        assert BRepCheck_Analyzer(sh.wrapped).IsValid() and not sh.Solids()
        faces=sh.Faces();assert len(faces)==spec['expected_faces']
        assert 'SI_UNIT(.MILLI.,.METRE.)' in path.read_text()
        chk=compare_boxes(spec['face_bounding_boxes_mm'],[box(f) for f in faces],tolerance=.002)
        assert sha256(path)==spec['sha256']
        if spec['id']!='DGM':
            p=originals[spec['id']] if spec['id']!='TEST' else dict(originals['V01'],rectangles=originals['V01']['rectangles'][:2])
            z=arrays['dom'] if p['z_source']=='bdom' else arrays['ground']
            for index,face_i in chk['mapping']:
                r0,r1,c0,c1=p['rectangles'][index]
                pts=np.concatenate((arrays['local'][r0:r1+1,c0:c1+1]*1000,z[r0:r1+1,c0:c1+1,None]*1000),axis=-1)
                rr,cc=(r1-r0)//2,(c1-c0)//2
                for xyz in [pts[0,0],pts[0,-1],pts[-1,0],pts[-1,-1],pts[rr,cc],pts[:2,:2].mean(axis=(0,1))]:
                    vert=BRepBuilderAPI_MakeVertex(gp_Pnt(*map(float,xyz))).Vertex()
                    dist=BRepExtrema_DistShapeShape(vert,faces[face_i].wrapped);dist.Perform()
                    assert dist.IsDone() and dist.Value()<.002
                    samples+=1;max_distance=max(max_distance,dist.Value())
        else:
            original=BASE/'basis/Vegetation_R08/CAD/GELAENDE_R07_UNVERAENDERT.step'
            assert (BASE/'CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step').read_bytes()==original.read_bytes()
            assert len(sh.Edges())==366 and all(e.geomType()=='LINE' for e in sh.Edges())
            from OCP.BRep import BRep_Tool
            old_face=cq.importers.importStep(str(original)).val().Faces()[0]
            old_surface=BRep_Tool.Surface_s(old_face.wrapped)
            new_surface=BRep_Tool.Surface_s(faces[0].wrapped)
            assert [old_surface.UDegree(),old_surface.VDegree()]==[new_surface.UDegree(),new_surface.VDegree()]==[1,1]
            assert [new_surface.NbUPoles(),new_surface.NbVPoles()]==[102,83]
            assert list(old_surface.UKnots())==list(new_surface.UKnots())
            assert list(old_surface.VKnots())==list(new_surface.VKnots())
            assert max(old_surface.Pole(i,j).Distance(new_surface.Pole(i,j)) for i in range(1,103) for j in range(1,84))<1e-7
        rows.append({'id':spec['id'],'faces':len(faces),'valid_open_geometry':True,'max_bbox_error_mm':chk['max_error_mm']})
        print(spec['id'],len(faces),'valid open STEP')
    report={'status':'OCCT_STEP_RUECKIMPORT_BESTANDEN','files':len(rows),'model_faces':585,'test_faces':2,
            'point_to_face_samples':samples,'max_point_to_face_distance_mm':max_distance,'parts':rows,
            'NX_tested':False,'scope':'Echte STEP-Dateien, CAD-Pruefung in Open CASCADE; kein NX-Translator und kein Bestandsnachweis.'}
    print(json.dumps(report,indent=2))
    return report
if __name__=='__main__':
    result=run()
    if '--report' in sys.argv:
        p=Path(sys.argv[sys.argv.index('--report')+1]);write_json(p,result)
