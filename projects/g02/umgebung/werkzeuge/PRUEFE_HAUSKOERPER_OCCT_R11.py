# -*- coding: utf-8 -*-
"""Offline CAD check of the current numeric house; NOT a NX test or NX journal."""
import json,sys,argparse,math
from pathlib import Path
B=Path(__file__).absolute().parents[1];sys.path[:0]=[str(B),str(B/'basis/Haus_R06/src')]
from haus2406_r03.haus_geometry import Parameters
from haus2406_r03.haus_roof import height
from haus2406_r03.haus_quality import plane_z
from haus2406_r03.haus_audit import vertical_record,integrate
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeSolid
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.TopoDS import TopoDS
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SHELL
from OCP.gp import gp_Pnt

def mesh_for(s,p):
 if 'polygon' in s:
  lo=p.number(s['bottom']);hi=p.number(s['top']);poly=s['polygon']
  lower=[[q[0],q[1],plane_z(s['bottom_plane'],q) if s.get('bottom_plane') else lo] for q in poly]
  upper=[[q[0],q[1],min(hi,height(s['roof_clip'],q)-p.value('DACH_HUELLE_PROXY')) if s.get('roof_clip') else plane_z(s['top_plane'],q) if s.get('top_plane') else hi] for q in poly]
 else:
  lower=s['points'];upper=[[q[i]+s['vector'][i] for i in range(3)] for q in lower]
 return [lower[::-1],upper]+[[lower[i],lower[(i+1)%len(lower)],upper[(i+1)%len(lower)],upper[i]] for i in range(len(lower))]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--report',required=True);args=ap.parse_args()
 d=json.loads((B/'abgleich/HAUS_EINGABEN_R11.json').read_text());j=json.loads((B/'abgleich/BAUAUFTRAG_R11.json').read_text());par=Parameters(d['parameters']);rows=[]
 for part in j['parts']:
  for s in part['solids']:
   sew=BRepBuilderAPI_Sewing(0.00001)
   for face in mesh_for(s,par):
    poly=BRepBuilderAPI_MakePolygon()
    for p in face:poly.Add(gp_Pnt(*p))
    poly.Close();maker=BRepBuilderAPI_MakeFace(poly.Wire(),True)
    if not maker.IsDone():raise RuntimeError('Face failure '+s['id'])
    sew.Add(maker.Face())
   sew.Perform();e=TopExp_Explorer(sew.SewedShape(),TopAbs_SHELL)
   if not e.More():raise RuntimeError('Missing shell '+s['id'])
   shell=TopoDS.Shell_s(e.Current());e.Next()
   if e.More():raise RuntimeError('Multiple shells '+s['id'])
   solid=BRepBuilderAPI_MakeSolid(shell).Solid()
   if not BRepCheck_Analyzer(solid).IsValid():raise RuntimeError('Invalid CAD '+s['id'])
   props=GProp_GProps();BRepGProp.VolumeProperties_s(solid,props);vol=abs(props.Mass())
   if not math.isfinite(vol) or vol<=0:raise RuntimeError('Volume '+s['id'])
   ref=vertical_record(s,par,part['id']);expect=ref['volume_mm3']
   # Full-precision source vertices, no viewport rounding.
   err=abs(vol-expect);limit=max(1.,expect*0.0001)
   if err>limit:raise RuntimeError('CAD volume deviation '+s['id']+': '+str((err,limit)))
   rows.append({'id':s['id'],'valid':True,'volume_mm3':vol,'expected_mm3':expect,'abs_error_mm3':err})
 out={'checked_bodies':len(rows),'status':'BESTANDEN','kernel':'Open CASCADE, NICHT NX/Parasolid','NX_tested':False,'scope':'Bauauftrag als geschlossene planare Polyeder; unveraenderte bestehende Anschlusskonflikte nicht beseitigt. Kein Nachweis von Scan-/Bestandsgenauigkeit.','records':rows}
 Path(args.report).write_text(json.dumps(out,indent=2,ensure_ascii=False));print('CAD BESTANDEN:',len(rows),'Koerper')
if __name__=='__main__':main()
