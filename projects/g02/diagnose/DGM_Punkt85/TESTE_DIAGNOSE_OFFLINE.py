import importlib.util, pathlib, unittest, math, tempfile, json
p=pathlib.Path(__file__).parent/'DIAGNOSE_DGM_PUNKT85.py'
s=importlib.util.spec_from_file_location('diag',p);d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
class Fake:
 def __init__(self, mode='same'):
  self.mode=mode; self.calls=[]
 def AskMinimumDist(self, zero, tag, first, xyz, second, guess):
  self.calls.append((zero,tag,first,xyz,second,guess))
  if self.mode=='throws' and tag==11:raise RuntimeError('intentional test error')
  if self.mode=='inconsistent': return (0,list(xyz),[xyz[0]+10,*xyz[1:]])
  delta=0
  if self.mode=='disagreement' and tag==10:delta=1000.049994
  if self.mode=='offset':delta=5
  pt=list(xyz);pt[2]+=delta
  return delta,list(xyz),pt
class Tests(unittest.TestCase):
 def test_01_exact_result(self):
  self.assertTrue(d.result_record((0,[1,2,3],[1,2,3]),[1,2,3])['within_unchanged_point_tolerance'])
 def test_02_true_error_retained(self):
  r=d.result_record((5,[1,2,3],[1,2,8]),[1,2,3]);self.assertEqual(r['distance_mm'],5);self.assertFalse(r['within_unchanged_point_tolerance'])
 def test_03_wrong_input_detected(self):
  self.assertFalse(d.result_record((0,[0,0,0],[0,0,0]),[1,2,3])['result_consistent'])
 def test_04_inconsistent_distance(self):
  self.assertFalse(d.result_record((0,[1,2,3],[1,2,4]),[1,2,3])['result_consistent'])
 def test_05_nonfinite_rejected(self):
  with self.assertRaises(ValueError):d.result_record((float('nan'),[1,2,3],[1,2,3]),[1,2,3])
 def test_06_invalid_result_rejected(self):
  with self.assertRaises(ValueError):d.result_record((0,[1,2,3]),[1,2,3])
 def test_07_negative_rejected(self):
  with self.assertRaises(ValueError):d.result_record((-1,[1,2,3],[1,2,3]),[1,2,3])
 def test_08_coordinates_checked(self):
  for val in [[True,0,0], [float('inf'),0,0], [0,0]]:
   with self.assertRaises(ValueError):d.checked_xyz(val)
 def run_case(self,mode):
  f=Fake(mode);r={};writes=[]
  d.run_measurements(f,10,[11],r,lambda x:writes.append(json.loads(json.dumps(x))),lambda x:None)
  return f,r,writes
 def test_09_bounded_twelve_calls(self):
  f,r,w=self.run_case('same');self.assertEqual(len(f.calls),12);self.assertEqual(r['completed_calls'],12);self.assertFalse(r['geometry_release'])
 def test_10_seed_to_faces_not_body(self):
  f,r,w=self.run_case('same')
  self.assertTrue(all(c[4]==0 for c in f.calls if c[1]==10))
  self.assertEqual(len([c for c in f.calls if c[1]==11 and c[4]==1 and c[3]==c[5]]),4)
 def test_11_meter_disagreement_retained(self):
  f,r,w=self.run_case('disagreement')
  self.assertTrue(all(x['methods_disagree_at_point_tolerance'] for x in r['points']))
  self.assertEqual(r['points'][1]['measurements'][0]['distance_mm'],1000.049994)
  self.assertFalse(r['geometry_release'])
 def test_12_exceptions_not_passed(self):
  f,r,w=self.run_case('throws');self.assertEqual(r['measurement_error_count'],8);self.assertEqual(r['status'],'DIAGNOSE_BEENDET_MIT_MESSFEHLERN')
 def test_13_persistent_offset_not_hidden(self):
  f,r,w=self.run_case('offset');self.assertTrue(all(not m['within_unchanged_point_tolerance'] for p in r['points'] for m in p['measurements']));self.assertFalse(r['geometry_release'])
 def test_14_inconsistent_results_flagged(self):
  f,r,w=self.run_case('inconsistent');self.assertEqual(r['measurement_error_count'],12)
 def test_15_pre_call_status_is_written(self):
  f,r,w=self.run_case('same');self.assertTrue(any(x['points'][-1]['measurements'][-1]['status']=='AUFRUF_LAEUFT' for x in w))
 def test_16_bounded_faces(self):
  for faces in [[],list(range(9))]:
   with self.assertRaises(ValueError):d.run_measurements(Fake(),10,faces,{},lambda x:None,lambda x:None)
 def test_17_output_is_json(self):
  with tempfile.TemporaryDirectory() as directory:
   p=pathlib.Path(directory)/'new.json';d.write_report(p,{'geometry_release':False});self.assertEqual(json.loads(p.read_text()),{'geometry_release':False})
 def test_18_no_part_write_apis(self):
  text=p.read_text();self.assertTrue(all(token not in text for token in ['.Commit(', '.Save(', '.SaveAs(', '.SetWork(', '.SetDisplay(', '.DoUpdate(', '.CreatePoint(', '.CreateStep']))
if __name__=='__main__':unittest.main(verbosity=2)
