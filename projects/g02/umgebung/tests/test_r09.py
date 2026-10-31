"""Offline-Pruefungen. NX-Doubles sind KEIN echter Translator-/Parasolid-Test."""
import contextlib
import copy
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).absolute().parents[1]
sys.path[:0]=[str(BASE),str(BASE/'basis/Haus_R06/src'),str(BASE/'basis/Haus_R06/tests')]
from r09.core import (read_json,write_json,settings_checked,placement,check_box,compare_boxes,
                      validate_job,verify_runtime_files,check_file_records,sha256,within,absolute)
from r09.nx_adapter import SceneAdapter
from r09.run import run_project,check_master
from fake_nx import FakeNX,Body,Object,ns,FakeNXException

CONFIG=read_json(BASE/'data/EINSTELLUNGEN_R09.json')
JOB=read_json(BASE/'data/IMPORTAUFTRAG_R09.json')


class CoreTests(unittest.TestCase):
    def test_default_no_height_guess(self):self.assertIsNone(placement(CONFIG))
    def test_alignment_sign_m_to_mm(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':31.23,'source':'TEST ONLY','common_vertical_datum_confirmed':True}
        self.assertEqual(placement(c),(0.,0.,-31230.))
    def test_alignment_zero_allowed_only_explicit(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':0,'source':'TEST ONLY','common_vertical_datum_confirmed':True}
        self.assertEqual(placement(c),(0.,0.,0.))
    def test_alignment_missing_source_rejected(self):
        c=copy.deepcopy(CONFIG);c['height_connection']['H_EG_zero_in_source_datum_m']=31
        c['height_connection']['common_vertical_datum_confirmed']=True
        with self.assertRaises(ValueError):placement(c)
    def test_alignment_unconfirmed_datum_rejected(self):
        c=copy.deepcopy(CONFIG);c['height_connection']['H_EG_zero_in_source_datum_m']=31;c['height_connection']['source']='TEST'
        with self.assertRaises(ValueError):placement(c)
    def test_alignment_true_not_number(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':True,'source':'TEST','common_vertical_datum_confirmed':True}
        with self.assertRaises(ValueError):placement(c)
    def test_alignment_no_string_conversion(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':'31.1','source':'TEST','common_vertical_datum_confirmed':True}
        with self.assertRaises(ValueError):placement(c)
    def test_alignment_nan_rejected(self):
        c=copy.deepcopy(CONFIG);c['height_connection']={'H_EG_zero_in_source_datum_m':float('nan'),'source':'TEST','common_vertical_datum_confirmed':True}
        with self.assertRaises(ValueError):placement(c)
    def test_confirmation_without_height_rejected(self):
        c=copy.deepcopy(CONFIG);c['height_connection']['common_vertical_datum_confirmed']=True
        with self.assertRaises(ValueError):placement(c)
    def test_unknown_config_key_rejected(self):
        c=copy.deepcopy(CONFIG);c['allow_automatic_guess']=True
        with self.assertRaises(ValueError):settings_checked(c)
    def test_build_flag_not_text(self):
        c=copy.deepcopy(CONFIG);c['build_house']='false'
        with self.assertRaises(ValueError):settings_checked(c)
    def test_planar_sheet_bbox_accepted(self):self.assertEqual(check_box([0,0,10,100,200,10]),[0,0,10,100,200,10])
    def test_line_bbox_not_surface(self):
        with self.assertRaises(ValueError):check_box([0,0,0,10,0,0])
    def test_infinite_bbox_rejected(self):
        with self.assertRaises(ValueError):check_box([0,0,0,1,2,math.inf])
    def test_bijection_not_import_order(self):
        e=[[0,0,0,10,10,1],[20,0,0,30,10,1]]
        self.assertEqual(compare_boxes(e,e[::-1])['mapping'],[(0,1),(1,0)])
    def test_duplicated_surface_not_missing_other(self):
        e=[[0,0,0,10,10,1],[20,0,0,30,10,1]]
        with self.assertRaises(ValueError):compare_boxes(e,[e[0],e[0]])
    def test_extra_sheet_rejected(self):
        with self.assertRaises(ValueError):compare_boxes([[0,0,0,1,1,1]],[[0,0,0,1,1,1]]*2)
    def test_scale_error_rejected(self):
        with self.assertRaises(ValueError):compare_boxes([[0,0,0,1000,1000,100]],[[0,0,0,1,1,.1]])
    def test_bbox_tolerance_not_faked(self):
        with self.assertRaises(ValueError):compare_boxes([[0,0,0,1000,1000,100]],[[0,0,0,1001,1000,100]])
    def test_path_traversal_rejected(self):
        for path in ('../x','x/../../x','C:/x','/tmp/x','a\\b'):
            with self.subTest(path=path),self.assertRaises(ValueError):within(BASE,path)
    def test_path_fix_does_not_call_resolve(self):
        with patch.object(Path,'resolve',side_effect=OSError(1005,'test')):
            self.assertTrue(absolute(BASE).is_absolute())
    def test_duplicate_json_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):read_json(p)
    def test_json_nan_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bad.json';p.write_text('{"a":NaN}')
            with self.assertRaises(ValueError):read_json(p)
    def test_bom_and_atomic_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';p.write_text('\ufeff{"a":1}')
            self.assertEqual(read_json(p),{'a':1});write_json(p,{'b':2});self.assertEqual(read_json(p),{'b':2})
    def test_output_hash_detects_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'data.txt';p.write_text('old')
            r=[{'relative_file':'data.txt','bytes':3,'sha256':sha256(p)}]
            self.assertEqual(check_file_records(root,r),1);p.write_text('new')
            with self.assertRaises(ValueError):check_file_records(root,r)
    def test_duplicate_output_record_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'x.txt';p.write_text('x');r={'relative_file':'x.txt','bytes':1,'sha256':sha256(p)}
            with self.assertRaises(ValueError):check_file_records(root,[r,r])


class SourceTests(unittest.TestCase):
    def test_source_hashes_and_job(self):self.assertEqual(validate_job(BASE,JOB)['sheets'],585)
    def test_runtime_hashes(self):self.assertGreater(verify_runtime_files(BASE),20)
    def test_ten_surface_components(self):self.assertEqual(len(JOB['parts']),10)
    def test_vegetation_382_and_low_202(self):
        self.assertEqual(sum(x['expected_sheets'] for x in JOB['parts'] if x['id'].startswith('V')),382)
        self.assertEqual(next(x['expected_sheets'] for x in JOB['parts'] if x['id']=='F01'),202)
    def test_mixed_source_dates_preserved(self):
        self.assertEqual(JOB['source_dates']['bdom_date'],'2023-04-07');self.assertEqual(JOB['source_dates']['dop_date'],'2025-05-12')
        self.assertFalse(JOB['source_dates']['dgm_vertical_verified'])
    def test_no_unknown_height_added(self):self.assertIsNone(JOB['coordinate_reference']['H_EG_zero_m'])
    def test_terrain_byte_identical(self):
        self.assertEqual(sha256(BASE/'CAD_IMPORT/GELAENDE_R07_UNVERAENDERT.step'),sha256(BASE/'basis/Vegetation_R08/CAD/GELAENDE_R07_UNVERAENDERT.step'))
    def test_house_json_unchanged(self):
        r=read_json(BASE/'berichte/QUELLENUEBERNAHME_R09.json')
        self.assertEqual(r['R06_haus_sha256'],sha256(BASE/'basis/Haus_R06/data/haus.json'))
    def test_reference_segment_count(self):self.assertEqual(sum(len(x['points_mm'])-1 for x in JOB['reference_lines']),601)
    def test_f01_only_blanked_default(self):self.assertEqual([p['id'] for p in JOB['parts'] if p['blank_by_default']],['F01'])
    def test_no_fake_prt_files_in_package(self):
        self.assertEqual(list((BASE/'CAD_IMPORT').rglob('*.prt')),[])
    def test_geometry_unit_mm(self):self.assertEqual(JOB['unit'],'mm')


class ImporterDouble:
    __slots__=('env','SettingsFile','InputFile','OutputFile','ImportTo','ImportToTeamcenter','FileOpenFlag',
               'ProcessHoldFlag','FlattenAssembly','LayerDefault','ObjectTypes','SewSurfaces','Optimize',
               'SimplifyGeometry','SmoothBSurfaces','destroyed')
    def __init__(self,env):
        self.env=env;self.ObjectTypes=ns(Curves=True,Surfaces=False,Solids=False);self.destroyed=False
        env.importers.append(self)
    def Commit(self):
        e=self.env;e.step_calls+=1
        if e.fail_step_at==e.step_calls:raise RuntimeError('INJECTED_STEP_IMPORT_ERROR')
        assert self.ImportTo=='WORK_PART' and self.ProcessHoldFlag is True
        assert self.FileOpenFlag is False and self.ImportToTeamcenter is False
        assert self.SmoothBSurfaces is False and self.SewSurfaces is False
        assert self.Optimize is False and self.SimplifyGeometry is False
        assert self.LayerDefault==1 and self.ObjectTypes.Surfaces is True
        assert Path(self.SettingsFile).is_file()
        p=e.session.Parts.Work;assert absolute(p.FullPath)==absolute(self.OutputFile)
        assert not p.Bodies
        spec=e.by_hash[sha256(self.InputFile)]
        boxes=spec['face_bounding_boxes_mm']
        if e.skip_last:boxes=boxes[:-1]
        for ref_index in reversed(range(len(boxes))):  # NX order must not matter.
            b=boxes[ref_index]
            pts=[[b[i] for i in range(3)],[b[i+3] for i in range(3)]]
            pts=[[x*e.step_scale for x in pt] for pt in pts]
            body=Body(p,lambda pts=pts:pts);body.IsSolidBody=e.step_solids;body.face_count=1
            body.face_count = 2 if ref_index < e.split_spec.get(spec['id'],0) else 1
            if e.empty_faces:body.face_count=0
            body._reference=spec['geometry_reference']['sheets'][ref_index]
            body._spec_id=spec['id']
            p.Bodies.append(body)
        if e.extra_sheet and p.Bodies:p.Bodies.append(p.Bodies[-1])
        return None  # This is the documented successful import return.
    def Destroy(self):self.destroyed=True


class SceneDouble(FakeNX):
    def __init__(self,definition):
        super().__init__();self.step_calls=0;self.fail_step_at=-1;self.step_scale=1;self.skip_last=False;self.step_solids=False
        self.split_spec={};self.empty_faces=False;self.extra_sheet=False
        self.area_factor=1.;self.area_override=None;self.distance=0.;self.mass_calls=0;self.distance_calls=0
        self.last_measured_body=None;self.last_measured_point=None
        self.face_measure_calls=0;self.disposed_measures=0;self.last_face_inputs=[]
        self.primary_fail=False;self.primary_fail_after_create=False
        self.primary_unavailable=False;self.primary_dispose_fail=False
        self.uf_fail=False;self.legacy_fail_second=False;self.primary_none=False
        self.accuracy_factors={};self.mass_args=[];self.measure_objects=[]
        def mass(tags,count,kind,units,density,accuracy,values):
            assert count==1 and len(tags)==1 and kind==2 and density==1.
            assert len(values)==11
            self.mass_calls+=1;self.mass_args.append((tags,count,kind,units,density,accuracy,values))
            body=self.objects[tags[0]];self.last_measured_body=body
            if accuracy==2:
                assert units==1 and values==[1e-7]+[0.]*10
                if self.legacy_fail_second and body._spec_id=='TEST' and body._reference['source_index']==1:
                    raise FakeNXException('Fehlernummer: 820001',820001)
                factor=25.4*25.4
            else:
                assert accuracy==1 and units==3 and values[0] in (.999,.9999,.99999,.999999,.9999999)
                assert values[1:]==[0.]*10
                factor=100.
            if self.uf_fail:raise FakeNXException('UF_MESSFEHLER 820001',820001)
            area=body._reference['area_mm2']*self.area_factor if self.area_override is None else self.area_override
            area*=self.accuracy_factors.get(values[0],1.)
            return ([area/factor]+[0.]*46,[0.]*13)
        def distance(point_tag,body_tag,given1,point,given2,guess2):
            assert point_tag==0 and given1==1 and given2==0 and guess2==[0.,0.,0.]
            body=self.objects[body_tag];assert hasattr(body,'_reference')
            self.distance_calls+=1;self.last_measured_point=point
            # Simulation only: not a real surface-distance implementation.
            return (self.distance,list(point),[point[0],point[1],point[2]+self.distance])
        self.uf.Modeling=ns(AskMassProps3d=mass,AskMinimumDist=distance)
        self.importers=[];self.by_hash={x['sha256']:x for x in JOB['parts']+[JOB['smoke_test']]}
        self.N.Step214Importer=ns(ImportToOption=ns(WorkPart='WORK_PART'))
        self.N.View=ns(RenderingStyleType=ns(ShadedWithEdges='SHADED'),Canned=ns(Isometric='ISO'),ScaleAdjustment=ns(Fit='FIT'))
        self.session.DexManager=ns(CreateStep214Importer=lambda:ImporterDouble(self))
        self.session.GetEnvironmentVariableValue=lambda key:str(definition.parent) if key=='STEP214UG_DIR' else ''
        original_new=self.session.Parts.NewDisplay
        def new(path,unit):
            p=original_new(path,unit);p.ModelingViews.WorkView.Orient=lambda *args:None
            def measure(area_unit,length_unit,accuracy,faces):
                self.face_measure_calls+=1
                assert area_unit=='SquareMilliMeter' and length_unit=='MilliMeter'
                assert accuracy in (.999,.9999,.99999,.999999,.9999999) and faces
                body=faces[0].body;self.last_measured_body=body
                assert all(f.body is body and f.OwningPart is p for f in faces)
                self.last_face_inputs=[f.Tag for f in faces]
                if self.primary_fail:raise FakeNXException('FACE_MESSFEHLER 820001',820001)
                if self.primary_none:return None
                area=body._reference['area_mm2']*self.area_factor if self.area_override is None else self.area_override
                area*=self.accuracy_factors.get(accuracy,1.)
                env=self
                class Measurement:
                    @property
                    def Area(me):
                        if env.primary_fail_after_create:raise FakeNXException('AREA_READ_FAILED',820001)
                        return area
                    def Dispose(me):
                        env.disposed_measures+=1
                        if env.primary_dispose_fail:raise RuntimeError('MEASURE_DISPOSE_FAILED')
                        me.disposed=True
                obj=Measurement();obj.disposed=False;self.measure_objects.append(obj)
                return obj
            p.MeasureManager=ns(NewFaceProperties=None if self.primary_unavailable else measure)
            return p
        self.session.Parts.NewDisplay=new
    @contextlib.contextmanager
    def active(self):
        with self.install(),patch.object(Object,'Unblank',lambda x:setattr(x,'blanked',False),create=True),\
             patch.object(Body,'GetFaces',lambda x:[ns(Tag=x.Tag*10000+i+1,OwningPart=x.OwningPart,body=x) for i in range(getattr(x,'face_count',1))],create=True):
            yield self


class NXSimulationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.definition=self.root/'step214ug.def';self.definition.write_text('TESTDOUBLE_DEF')
        self.env=SceneDouble(self.definition)
    def adapter(self):return SceneAdapter(lambda s:None)
    def cfg(self,house=False):
        cfg=copy.deepcopy(CONFIG);cfg['build_house']=house;cfg['output_root']=str(self.root/'runs');cfg['step_settings_file']=str(self.definition)
        return cfg
    def workflow(self,cfg=None,house_builder=None):
        opts={} if house_builder is None else {'house_builder':house_builder}
        def test_write(path, value):
            path=Path(path)
            if path == BASE/'LETZTER_R09_LAUF.json':
                path=self.root/'LETZTER_R09_LAUF.json'
            return write_json(path,value)
        with self.env.active(),contextlib.redirect_stdout(io.StringIO()),patch('r09.run.write_json',side_effect=test_write):
            return run_project(BASE,config=cfg or self.cfg(),**opts)
    def test_step_commit_none_is_success(self):
        with self.env.active():
            a=self.adapter();s=JOB['smoke_test'];p,save,check=a.import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
            self.assertEqual(check['sheets'],2);self.assertEqual(save['bodies'],2)
    def test_all_import_options_verified(self):
        self.test_step_commit_none_is_success();self.assertTrue(self.env.importers[-1].destroyed)
    def test_solid_instead_of_sheet_rejected(self):
        self.env.step_solids=True
        with self.env.active():
            s=JOB['smoke_test']
            with self.assertRaisesRegex(RuntimeError,'Volumenkoerper'):
                self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
    def test_missing_sheet_rejected(self):
        self.env.skip_last=True
        with self.env.active():
            s=JOB['smoke_test']
            with self.assertRaisesRegex(ValueError,'Teilkoerperanzahl'):
                self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
    def test_wrong_import_scale_rejected(self):
        self.env.step_scale=.001
        with self.env.active():
            s=JOB['smoke_test']
            with self.assertRaisesRegex(ValueError,'Boxzuordnung'):
                self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
    def test_import_failure_destroys_builder(self):
        self.env.fail_step_at=1
        with self.env.active():
            s=JOB['smoke_test']
            with self.assertRaisesRegex(RuntimeError,'INJECTED'):
                self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
        self.assertTrue(self.env.importers[-1].destroyed)
    def test_existing_prt_not_overwritten(self):
        s=JOB['smoke_test'];p=self.root/s['part_file'];p.write_text('USER DATA')
        with self.env.active(),self.assertRaises(FileExistsError):
            self.adapter().import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
        self.assertEqual(p.read_text(),'USER DATA')
    def test_workpart_made_current_before_import(self):
        self.env.new_display_leaves_work=True;self.test_step_commit_none_is_success()
    def test_def_discovery(self):
        with self.env.active():self.assertEqual(self.adapter().settings_file(BASE,''),self.definition)
    def test_explicit_missing_def_is_error(self):
        with self.env.active(),self.assertRaises(FileNotFoundError):self.adapter().settings_file(BASE,str(self.root/'missing.def'))
    def test_nonzero_component_translation_checked(self):
        with self.env.active():
            a=self.adapter();s=JOB['smoke_test'];p,_,_=a.import_surface_part(self.root,BASE/s['step_file'],s,self.definition)
            m=a.new_part(self.root/'m.prt','MASTER');c=a.add_at(m,Path(p.FullPath),'TEST',(0,0,-31000))
            self.assertEqual(c.GetPosition()[0].Z,-31000)
            with self.assertRaisesRegex(RuntimeError,'Komponentenverschiebung'):a.verify_component(c,p.FullPath,(0,0,0))
    def test_full_environment_default_no_guess(self):
        s=self.workflow();self.assertEqual(s['status'],'R09_ERZEUGT_BEZUGSSYSTEME_GETRENNT')
        self.assertIsNone(s['combined_master']);self.assertEqual(len(s['component_checks']),6)
        self.assertEqual(sum(x['sheets'] for x in s['imports']),115);self.assertEqual(s['reference_segments'],601)
        self.assertEqual(s['checked_file_count'],7)
        self.assertFalse(any(o.Name=='F01' and hasattr(o,'Prototype') for o in self.env.objects.values()))
        self.assertIn('F01',s['vegetation_video_selection']['not_automatically_imported'])
    def test_environment_import_smoke_first(self):
        s=self.workflow();self.assertEqual(self.env.step_calls,6)
        self.assertEqual(s['smoke_test']['status'],'NX_IMPORT_UND_KOMPONENTENTEST_BESTANDEN')
    def test_smoke_failure_does_not_build_house(self):
        self.env.fail_step_at=1;called=[]
        def house(*a):called.append(True)
        with self.assertRaises(RuntimeError):self.workflow(self.cfg(True),house)
        self.assertEqual(called,[])
    def test_import_failure_does_not_build_house(self):
        self.env.fail_step_at=3;called=[]
        with self.assertRaises(RuntimeError):self.workflow(self.cfg(True),lambda *a:called.append(True))
        self.assertEqual(called,[])
        manifests=list((self.root/'runs').rglob('manifest_R09.json'))
        self.assertEqual(read_json(manifests[0])['status'],'R09_ABGEBROCHEN_TEILERGEBNIS')
    def test_house_failure_preserves_environment_only(self):
        def failed(*a):raise RuntimeError('HOUSE_FAILURE')
        with self.assertRaisesRegex(RuntimeError,'HOUSE_FAILURE'):self.workflow(self.cfg(True),failed)
        s=read_json(next((self.root/'runs').rglob('manifest_R09.json')))
        self.assertEqual(s['environment_status'],'ERZEUGT_IMPORT_UND_STRUKTUR_GEPRUEFT')
        self.assertEqual(s['status'],'R09_ABGEBROCHEN_TEILERGEBNIS')
    def test_duplicate_open_part_rejected(self):
        self.workflow()
        with self.assertRaisesRegex(RuntimeError,'bereits geoeffnet'):self.workflow()
    def test_entry_syntax(self):
        import ast
        for p in [BASE/'00_NX_MODELL_ERZEUGEN_2406.py']+list((BASE/'r09').glob('*.py')):
            ast.parse(p.read_text(encoding='utf-8'),feature_version=(3,10))
    def test_real_r06_code_full_simulated_run_separate(self):
        s=self.workflow(self.cfg(True))
        self.assertEqual(s['house']['built_solids'],1361)
        self.assertEqual(s['house']['verification_status'],'DATEI_UND_STRUKTURPRUEFUNG_BESTANDEN')
        self.assertIsNone(s['combined_master']);self.assertEqual(s['checked_file_count'],24)
    def test_real_r06_code_combines_only_with_explicit_height(self):
        cfg=self.cfg(True);cfg['height_connection']={'H_EG_zero_in_source_datum_m':31.2,'source':'SIMULIERTER TESTWERT, KEIN AUFMASS','common_vertical_datum_confirmed':True}
        s=self.workflow(cfg)
        self.assertEqual(s['status'],'R09_ERZEUGT_MIT_NUTZERHOEHENANSCHLUSS')
        comps=s['combined_component_checks']
        self.assertEqual(comps[0]['translation_mm'],[0,0,0])
        self.assertEqual(comps[1]['translation_mm'],[0,0,-31200.0])
        self.assertFalse(s['measured_house_alignment'])
    def test_house_reference_no_full_model_claim(self):
        self.env.answer=2;s=self.workflow(self.cfg(True))
        self.assertEqual(s['house']['mode'],'REFERENZGERUEST')
        self.assertEqual(s['house']['built_solids'],0)
        self.assertIsNone(s['combined_master'])


if __name__=='__main__':unittest.main(verbosity=2)
