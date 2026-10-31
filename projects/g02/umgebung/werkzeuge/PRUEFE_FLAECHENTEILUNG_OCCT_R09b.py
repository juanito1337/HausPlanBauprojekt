"""R09e updated harness. Historical filename kept. OFFLINE ONLY: requires cadquery/OCP; never run as an NX journal.
Real CAD topology experiment; OCCT, not NX. Seven V01 faces split into 14 faces.
49 sheet bodies, 56 faces in total. Verifies unchanged source samples and areas.
"""
import sys, json, tempfile, math
from pathlib import Path
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace,BRepBuilderAPI_Sewing,BRepBuilderAPI_MakeVertex
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepExtrema import BRepExtrema_DistShapeShape
from OCP.gp import gp_Pnt
B=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(B),str(B/'tests')]
from test_r09 import SceneDouble,JOB,Body
from r09.core import compare_boxes,write_json
from r09.nx_adapter import SceneAdapter
s=next(x for x in JOB['parts'] if x['id']=='V01')
orig=cq.importers.importStep(str(B/s['step_file'])).val().Faces()
def box(shape):
 b=shape.BoundingBox();return [b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax]
mp=compare_boxes(s['face_bounding_boxes_mm'],[box(f) for f in orig],.002)['mapping']
shapes=[]
for i,j in mp:
 f=orig[j]
 if i < 7:
  surf=BRep_Tool.Surface_s(f.wrapped);u0,u1,v0,v1=surf.Bounds();uc=u0+0.37*(u1-u0)
  sewer=BRepBuilderAPI_Sewing(1e-7)
  for a,b in [(u0,uc),(uc,u1)]:sewer.Add(BRepBuilderAPI_MakeFace(surf,a,b,v0,v1,1e-7).Face())
  sewer.Perform();result=cq.Shape.cast(sewer.SewedShape())
  assert len(result.Faces())==2 and BRepCheck_Analyzer(result.wrapped).IsValid()
  shapes.append(result)
 else:shapes.append(f)
print('Actual constructed CAD faces',sum(len(f.Faces()) for f in shapes),flush=True)
# Use actual CAD area + distance in the otherwise simulated NX interface.
with tempfile.TemporaryDirectory() as tmp:
 out=Path(tmp);definition=out/'d.def';definition.write_text('NO NX')
 env=SceneDouble(definition)
 def mass(tags,count,kind,units,density,mode,accuracy):
  shape=env.objects[tags[0]]._occt;g=GProp_GProps()
  err=BRepGProp.SurfaceProperties_s(shape.wrapped,g,1e-8)
  return ([g.Mass()/100.0]+[0.]*46,[0.]*13)
 def distance(null,tag,given,p,given2,p2):
  vertex=BRepBuilderAPI_MakeVertex(gp_Pnt(*p)).Vertex()
  d=BRepExtrema_DistShapeShape(vertex,env.objects[tag]._occt.wrapped);d.Perform()
  assert d.IsDone();q=d.PointOnShape2(1)
  return (d.Value(),list(p),[q.X(),q.Y(),q.Z()])
 env.uf.Modeling.AskMassProps3d=mass;env.uf.Modeling.AskMinimumDist=distance
 with env.active():
  a=SceneAdapter(lambda x:None);part=a.new_part(out/'SPLIT_TEST.prt','V01_TEST')
  for shape in reversed(shapes):
   bounds=box(shape);pts=[bounds[:3],bounds[3:]]
   body=Body(part,lambda pts=pts:pts);body.IsSolidBody=False;body.face_count=len(shape.Faces());body._occt=shape
   part.Bodies.append(body)
  # Primary API is a simulated adapter; Area is actually computed by OCCT.
  # Requested NX accuracies are NOT emulated: both OCCT measurements use eps=1e-8.
  def real_area(area_unit,length_unit,accuracy,faces):
   assert area_unit=='SquareMilliMeter' and length_unit=='MilliMeter'
   shape=faces[0].body._occt;g=GProp_GProps()
   BRepGProp.SurfaceProperties_s(shape.wrapped,g,1e-8)
   class Measurement:
    Area=g.Mass()
    def Dispose(self):return None
   return Measurement()
  part.MeasureManager.NewFaceProperties=real_area
  check=a.verify_surface_geometry(part,s,out)
  detail=json.loads((out/'IMPORTPRUEFUNG_V01_R09e.json').read_text())
  result={'test':'OCCT_CREATED_V01_SPLIT_49_SHEETS_56_FACES','status':'BESTANDEN',
          'actual_constructed_sheets':len(shapes),'actual_constructed_faces':sum(len(f.Faces()) for f in shapes),
          'source_points_checked':check['checked_source_points'],
          'max_source_point_distance_mm':check['max_point_distance_mm'],
          'max_area_relative_error':max(r['area_relative_error'] for r in detail['sheets_checked']),
          'NX_tested':False,'NX_accuracy_behavior_emulated':False,'OCCT_integration_eps':1e-8,'not_users_imported_model':True,
          'scope':'Constructed OCCT face splits; production check with CAD-computed measurements via simulated NX boundary. Does NOT verify user NX import.'}
  write_json(B/'berichte/OCCT_FLACHENTEILUNG_R09e.json',result)
  print(json.dumps(result,indent=2))
