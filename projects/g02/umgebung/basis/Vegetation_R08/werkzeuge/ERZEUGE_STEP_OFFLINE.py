"""Rebuild the supplied surface STEP files outside NX, from the reviewed R08 job.
Requires numpy, cadquery 2.8 / compatible OCP. Never run as an NX journal.
Outputs go to a NEW directory supplied with --out; existing files are refused.
These are open canopy/ground reference surfaces, never stems or biomass solids.
"""
from pathlib import Path
import argparse,json,time
import numpy as np
import cadquery as cq
from OCP.gp import gp_Pnt
from OCP.TColgp import TColgp_Array2OfPnt
from OCP.TColStd import TColStd_Array1OfReal,TColStd_Array1OfInteger
from OCP.Geom import Geom_BSplineSurface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.BRepCheck import BRepCheck_Analyzer

def spline_face(xyz_mm):
    rows,cols,_=xyz_mm.shape
    if rows<2 or cols<2 or not np.isfinite(xyz_mm).all():
        raise ValueError('Invalid surface support grid')
    poles=TColgp_Array2OfPnt(1,cols,1,rows)
    for r in range(rows):
        for c in range(cols):poles.SetValue(c+1,r+1,gp_Pnt(*map(float,xyz_mm[r,c])))
    def arrays(count):
        knots=TColStd_Array1OfReal(1,count);mults=TColStd_Array1OfInteger(1,count)
        for i in range(count):
            knots.SetValue(i+1,float(i));mults.SetValue(i+1,2 if i in (0,count-1) else 1)
        return knots,mults
    uk,um=arrays(cols);vk,vm=arrays(rows)
    surface=Geom_BSplineSurface(poles,uk,vk,um,vm,1,1,False,False)
    build=BRepBuilderAPI_MakeFace(surface,1e-6)
    if not build.IsDone():raise RuntimeError('Surface generation failed')
    face=build.Face()
    if not BRepCheck_Analyzer(face).IsValid():raise RuntimeError('Invalid generated face')
    return cq.Face(face),surface

def generate(base,out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):raise FileExistsError('Output folder must be empty: '+str(out))
    out.mkdir(parents=True,exist_ok=True)
    arrays=dict(np.load(base/'data/RASTER_AUSWERTUNG_R08.npz',allow_pickle=False))
    job=json.loads((base/'data/BAUAUFTRAG_VEGETATION_R08.json').read_text(encoding='utf-8'))
    vegetation=cq.Assembly(name='VEGETATION_R08_DATUM_MISCHSTAND')
    low=cq.Assembly(name='NIEDRIGER_BEWUCHS_NUR_BODENREFERENZ')
    all_parts=cq.Assembly(name='GELAENDE_UND_VEGETATION_R08_QUELLHOEHEN_MM')
    terrain=cq.importers.importStep(str(base/'CAD/GELAENDE_R07_UNVERAENDERT.step')).val()
    all_parts.add(terrain,name='GELAENDE_R07_UNVERAENDERT')
    build_stats=[];node_max=0.;mid_max=0.;node_count=0;mid_count=0
    for part in job['parts']:
        faces=[];z=arrays['dom'] if part['z_source']=='bdom' else arrays['ground']
        for r0,r1,c0,c1 in part['rectangles']:
            xy=arrays['local'][r0:r1+1,c0:c1+1]*1000
            zz=z[r0:r1+1,c0:c1+1,None]*1000
            pts=np.concatenate([xy,zz],axis=2)
            face,surface=spline_face(pts);faces.append(face)
            for r in range(pts.shape[0]):
                for c in range(pts.shape[1]):
                    actual=np.array(surface.Value(float(c),float(r)).Coord())
                    node_max=max(node_max,float(np.max(np.abs(actual-pts[r,c]))));node_count+=1
            for r in range(pts.shape[0]-1):
                for c in range(pts.shape[1]-1):
                    expected=(pts[r,c]+pts[r+1,c]+pts[r,c+1]+pts[r+1,c+1])*.25
                    actual=np.array(surface.Value(c+.5,r+.5).Coord())
                    mid_max=max(mid_max,float(np.max(np.abs(actual-expected))));mid_count+=1
        if not faces:continue
        compound=cq.Compound.makeCompound(faces)
        name=part['name_ascii']
        target=vegetation if part['z_source']=='bdom' else low
        target.add(compound,name=name);all_parts.add(compound,name=name)
        build_stats.append({'id':part['id'],'faces':len(faces),'source':part['z_source'],'shape_valid':compound.isValid()})
        print(name,len(faces),flush=True)
    for assembly,filename in [(vegetation,'VEGETATION_OBERFLAECHEN_R08.step'),(low,'GRUENFLAECHEN_NUR_BODENREFERENZ_R08.step'),(all_parts,'GELAENDE_UND_VEGETATION_R08.step')]:
        assembly.export(str(out/filename),exportType='STEP',unit='MM',outputUnit='MM')
    result={'node_evaluations':node_count,'midcell_evaluations':mid_count,'max_node_error_mm':node_max,'max_midcell_error_mm':mid_max,'parts':build_stats,'native_NX_tested':False,'model_representation':'Open degree 1x1 B-spline faces. No biomass/stems/roots/closed crown underside.'}
    (out/'ERZEUGUNG.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True)
    args=parser.parse_args();root=Path(__file__).absolute().parents[1]
    print(json.dumps(generate(root,Path(args.out)),indent=2))
