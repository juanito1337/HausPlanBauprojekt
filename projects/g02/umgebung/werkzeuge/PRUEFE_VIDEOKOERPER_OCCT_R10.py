from pathlib import Path
import json,sys,math
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakePolygon,BRepBuilderAPI_MakeFace
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.gp import gp_Pnt,gp_Vec
B=Path(__file__).absolute().parents[1];sys.path[:0]=[str(B),str(B/'basis/Haus_R06/src')]
from haus2406_r03.haus_geometry import Parameters,area
j=json.loads((B/'video/berichte/BAUAUFTRAG_R10.json').read_text());d=json.loads((B/'video/berichte/HAUS_EINGABEN_R10.json').read_text());p=Parameters(d['parameters'])
records=[]
for part in j['parts']:
 for s in part['solids']:
  if not(s['meta'].get('revision')=='R10' or '_V10_' in s['id'] or s['id'].startswith('R10_')):continue
  if 'points' in s:points=s['points'];vec=s['vector']
  elif 'polygon' in s and not(s.get('top_plane') or s.get('bottom_plane') or s.get('roof_clip')):
   z=p.number(s['bottom']);points=[[x,y,z] for x,y in s['polygon']];vec=[0,0,p.number(s['top'])-z]
  else:raise RuntimeError('Unexpected new body construction '+s['id'])
  poly=BRepBuilderAPI_MakePolygon()
  for q in points:poly.Add(gp_Pnt(*q))
  poly.Close();face=BRepBuilderAPI_MakeFace(poly.Wire(),True).Face();shape=BRepPrimAPI_MakePrism(face,gp_Vec(*vec),True).Shape()
  if not BRepCheck_Analyzer(shape).IsValid():raise RuntimeError('Invalid '+s['id'])
  props=GProp_GProps();BRepGProp.VolumeProperties_s(shape,props)
  expected=abs(area([q[:2] for q in points])*vec[2]);got=props.Mass()
  if not(got>0 and abs(got-expected)<=max(.01,expected*1e-9)):raise RuntimeError('Volume '+s['id'])
  records.append({'id':s['id'],'valid':True,'volume_mm3':got,'expected_mm3':expected,'abs_difference_mm3':abs(got-expected)})
out={'status':'BESTANDEN','cad_kernel':'Open CASCADE, nicht NX/Parasolid','checked_new_or_changed_bodies':len(records),'max_volume_difference_mm3':max(r['abs_difference_mm3'] for r in records),'scope':'Neue Detailprismen und geaenderte Dach-/Gaubenkoerper; keine Ausfuehrungsfreigabe. Keine STEP-Dateien erforderlich.','records':records}
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--report',required=True);args=parser.parse_args()
Path(args.report).write_text(json.dumps(out,ensure_ascii=False,indent=2));print(out['status'],out['checked_new_or_changed_bodies'],out['max_volume_difference_mm3'])
