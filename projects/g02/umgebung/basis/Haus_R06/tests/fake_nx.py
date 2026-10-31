# -*- coding: utf-8 -*-
"""Strikte TESTDOUBLES. Kein NX, kein Parasolid und kein API-Signaturnachweis.

Dateien entstehen nur in temporaeren Testordnern und enthalten explizite
TESTDOUBLE-Marker. Sie sind KEINE echten .prt-Dateien und werden nicht geliefert.
Schnittsimulation nur fuer den Kontrollfluss/Boxen; Tueroeffnungsvolumen NICHT simuliert.
"""
import math
import os
import types
from pathlib import Path
from unittest.mock import patch
from haus2406_r03.haus_geometry import Parameters


def ns(**items):return types.SimpleNamespace(**items)


class Status:
    def __init__(self,env,unloaded=0,unsaved=0):
        self.env=env;self.NumberUnloadedParts=unloaded;self.NumberUnsavedParts=unsaved;self.disposed=False
        env.statuses.append(self)
    def Dispose(self):
        self.disposed=True
        if self.env.fail_dispose:raise RuntimeError('INJECTED_DISPOSE_ERROR')


class Point:
    def __init__(self,x=0,y=0,z=0):self.X=float(x);self.Y=float(y);self.Z=float(z)
    def xyz(self):return [self.X,self.Y,self.Z]


class Matrix:
    def __init__(self):
        for key in ('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz'):setattr(self,key,0.)


class Object:
    def __init__(self,env,part=None):
        self.env=env;env.serial+=1;self.Tag=env.serial;env.objects[self.Tag]=self
        self.OwningPart=part;self.Name='';self.attrs={};self.blanked=False;self.Layer=1
    def SetName(self,name):self.Name=name
    def SetUserAttribute(self,title,index,value,option):
        if index!=-1:raise AssertionError('Non scalar attribute index')
        self.env.attribute_attempts.append((self.Tag, title))
        if title in getattr(self,'reserved_attributes',set()):
            self.env.reserved_attribute_attempts.append((self.Tag, title))
            raise FakeNXException('The attribute is reserved by an NX application or the system, so it cannot be set, changed or deleted.',512091)
        self.attrs[title]=value
    def Blank(self):self.blanked=True


class FakeNXException(RuntimeError):
    """Injected OM error, not an actual Siemens exception implementation."""
    def __init__(self,message,code=None):
        super().__init__(message)
        self.ErrorCode=code


class Expression(Object):
    def __init__(self,part,name,rhs,unit):
        super().__init__(part.env,part);self.Name=name;self.RightHandSide=rhs;self.unit=unit
    def SetUserAttribute(self,title,index,value,option):
        # Reproduce exactly the real installation's observed rejection.
        self.env.expression_attribute_attempts+=1
        raise FakeNXException('Functionality attempted not possible in the current version of the OM')


class Expressions:
    def __init__(self,part):self.part=part;self.items={}
    def CreateWithUnits(self,definition,unit):
        name,rhs=definition.split('=',1)
        if name in self.items:raise RuntimeError('Duplicate expression: '+name)
        if unit not in ('MilliMeter','Degrees'):raise ValueError('Unknown unit')
        expr=Expression(self.part,name,rhs,unit);self.items[name]=expr;return expr
    def FindObject(self,name):return self.items[name]
    def number(self,value):
        return Parameters({k:{'formula':e.RightHandSide,'unit':'mm','status':'PLANWERT'} for k,e in self.items.items()}).number(value)


class Curve(Object):
    def __init__(self,part,a,b):super().__init__(part.env,part);self.a=a.xyz();self.b=b.xyz()


class Curves:
    def __init__(self,part):self.part=part;self.items=[]
    def CreateLine(self,a,b):
        curve=Curve(self.part,a,b);self.items.append(curve);return curve


class Section:
    AllowTypes=ns(OnlyCurves='ONLY_CURVES');Mode=ns(Create='CREATE')
    def __init__(self):self.curves=[]
    def SetAllowedEntityTypes(self,allowed):
        if allowed!='ONLY_CURVES':raise ValueError('Expected curves')
    def AddToSection(self,rules,seed,start,end,help_point,mode,chain):
        if start is not None or end is not None or mode!='CREATE' or chain is not False:raise AssertionError('Section contract')
        if len(rules)!=1:raise AssertionError('One dumb rule expected')
        self.curves=list(rules[0]);self.help_point=help_point
        if seed not in self.curves:raise AssertionError('Seed absent')


class Body(Object):
    def __init__(self,part,calc):
        super().__init__(part.env,part);self.calc=calc;self.IsSolidBody=not part.env.make_sheet
        self.reserved_attributes=set()
    def vertices(self):return self.calc()


class Feature(Object):
    Null=None
    def __init__(self,part,bodies):super().__init__(part.env,part);self.bodies=bodies
    def GetBodies(self):return list(self.bodies)


class Boolean:
    def __init__(self):self.Type='CREATE';self.targets=[]
    def SetTargetBodies(self,bodies):self.targets=list(bodies)


def clip_vertices(vertices,point,direction,profile):
    """Konvexe Halbraum-Boxsimulation fuer grossflaechige Dach-/Wangenschnitte."""
    u=[profile[1][i]-profile[0][i] for i in range(3)]
    v=[profile[-1][i]-profile[0][i] for i in range(3)]
    n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
    norm=math.sqrt(sum(x*x for x in n))
    if norm<1e-12:return vertices
    sign=1 if sum(a*b for a,b in zip(n,direction))>0 else -1
    n=[x/norm*sign for x in n]
    vals=[sum(n[i]*(p[i]-point[i]) for i in range(3)) for p in vertices]
    result=[p for p,d in zip(vertices,vals) if d<=1e-8]
    for i,a in enumerate(vertices):
        for j in range(i+1,len(vertices)):
            da,db=vals[i],vals[j]
            if da*db<0:
                f=da/(da-db);b=vertices[j];result.append([a[k]+f*(b[k]-a[k]) for k in range(3)])
    unique={tuple(round(x,8) for x in p):p for p in result}
    return list(unique.values())


class ExtrudeBuilder:
    def __init__(self,part):
        self.part=part;self.env=part.env;self.Section=None;self.Direction=None;self.DistanceTolerance=None
        self.Limits=ns(StartExtend=ns(Value=ns(RightHandSide='0')),EndExtend=ns(Value=ns(RightHandSide='1')))
        self.BooleanOperation=Boolean();self.destroyed=False;self.env.builders.append(self)
    def CommitFeature(self):
        self.env.commits+=1
        if self.env.fail_commit_at==self.env.commits:raise RuntimeError('INJECTED_COMMIT_ERROR')
        if self.part.env.session.Parts.Work is not self.part:raise RuntimeError('WRONG_WORK_PART')
        if self.Section is None or self.Direction is None:raise AssertionError('Missing section/direction')
        points=[c.a for c in self.Section.curves];direction=self.Direction
        start=self.Limits.StartExtend.Value.RightHandSide;end=self.Limits.EndExtend.Value.RightHandSide
        self.env.operations.append({'part':self.part.FullPath,'type':self.BooleanOperation.Type,'points':points,'start':start,'end':end,'direction':direction})
        if self.BooleanOperation.Type=='CREATE':
            def vertices():
                lo=self.part.Expressions.number(start);hi=self.part.Expressions.number(end)
                return [[q[i]+d*direction[i] for i in range(3)] for d in (lo,hi) for q in points]
            body=Body(self.part,vertices);self.part.Bodies.append(body)
        else:
            if self.BooleanOperation.Type!='SUBTRACT' or len(self.BooleanOperation.targets)!=1:raise AssertionError('Boolean contract')
            body=self.BooleanOperation.targets[0];old=body.calc
            # Installation log: MATERIAL rejected on the body after door subtraction.
            # This is an injected observation, NOT a complete model of NX attributes.
            body.reserved_attributes.add('MATERIAL')
            def vertices():
                original=old()
                contained=all(min(p[i] for p in points)<=min(p[i] for p in original)+1e-6 and max(p[i] for p in points)>=max(p[i] for p in original)-1e-6 for i in (0,1))
                if not contained:return original  # Door: body-count/control flow only, not volume.
                lo=self.part.Expressions.number(start)
                plane_point=[points[0][i]+lo*direction[i] for i in range(3)]
                return clip_vertices(original,plane_point,direction,points)
            body.calc=vertices
        return Feature(self.part,[body])
    def Destroy(self):
        if self.destroyed:raise RuntimeError('Builder destroyed twice')
        self.destroyed=True
        if self.env.fail_destroy:raise RuntimeError('INJECTED_DESTROY_ERROR')


class Component(Object):
    def __init__(self,part,proto,name,origin,matrix):
        super().__init__(part.env,part);self.Prototype=proto;self.Name=name;self.origin=origin;self.matrix=matrix
    def GetPosition(self):return self.origin,self.matrix


class Assembly:
    def __init__(self,part):self.part=part;self.children=[];self.RootComponent=self
    def AddComponent(self,path,refset,name,origin,matrix,layer):
        if refset!='Entire Part' or layer!=-1:raise AssertionError('Assembly contract')
        proto=self.part.env.session.Parts.by_path(path)
        if proto is None:raise RuntimeError('Prototype absent')
        component=Component(self.part,proto,name,origin,matrix);self.children.append(component)
        return component,Status(self.part.env,unloaded=self.part.env.unloaded)
    def GetChildren(self):return list(self.children)


from enum import Enum


class PartCreationUnits(Enum):
    Inches = 'IN'
    Millimeters = 'MM'


class BasePartReadUnits(Enum):
    Inches = 'IN'
    Millimeters = 'MM'


class Part(Object):
    Units=PartCreationUnits
    def __init__(self,env,path,units):
        super().__init__(env);self.OwningPart=self;self.FullPath=os.path.abspath(path)
        if not isinstance(units,PartCreationUnits):
            raise TypeError('NewDisplay requires Part.Units, not BasePart.Units or strings')
        self.PartUnits=(BasePartReadUnits.Millimeters if units==PartCreationUnits.Millimeters
                        else BasePartReadUnits.Inches)
        self.Leaf=Path(path).name;self.Name=Path(path).stem
        self.Preferences=ns(Modeling=ns(GetHistoryMode=lambda:not env.history_free))
        self.Expressions=Expressions(self);self.Curves=Curves(self);self.Bodies=[]
        self.UnitCollection=ns(FindObject=lambda name:name)
        self.Sections=ns(CreateSection=lambda a,b,c:Section())
        self.ScRuleFactory=ns(CreateRuleCurveDumb=lambda curves:list(curves))
        self.Directions=ns(CreateDirection=lambda point,vector,update:vector.xyz())
        self.Features=ns(CreateExtrudeBuilder=lambda null:ExtrudeBuilder(self))
        self.ComponentAssembly=Assembly(self);self.IsFullyLoaded=True
        self.ModelingViews=ns(WorkView=ns(Fit=lambda:None))
    def Save(self,save_components,close):
        if self.env.fail_save:raise RuntimeError('INJECTED_SAVE_ERROR')
        if save_components!='FALSE' or close!='FALSE':raise AssertionError('Save must not close or save foreign components')
        Path(self.FullPath).write_bytes(('TESTDOUBLE_NOT_NX_PART\n'+self.Name+'\n'+str(len(self.Bodies))).encode())
        return None if self.env.none_save_status else Status(self.env,unsaved=self.env.unsaved)
    def LoadFully(self):self.IsFullyLoaded=True;return Status(self.env)


class Parts:
    def __init__(self,env):self.env=env;self.items=[];self.Work=None;self.Display=None
    def __iter__(self):return iter(self.items)
    def by_path(self,path):
        return next((p for p in self.items if os.path.abspath(p.FullPath)==os.path.abspath(path)),None)
    def NewDisplay(self,path,units):
        part=Part(self.env,path,units);self.items.append(part);self.Display=part
        self.Work=part if not self.env.new_display_leaves_work else self.Work
        return part
    def SetWork(self,part):self.Work=part
    def SetDisplay(self,part,maintain,setwork):
        self.Display=part
        if setwork:self.Work=part
        return 0,Status(self.env)
    def OpenDisplay(self,path):
        part=self.by_path(path)
        if part is None:raise RuntimeError('Mock has no disk NX parser')
        self.Display=part;self.Work=part;return part,Status(self.env)


class Session:
    MarkVisibility=ns(Invisible='INVISIBLE')
    def __init__(self,env):
        self.env=env;self.Parts=Parts(env);self.marks={};self.next_mark=0;self.undo_calls=0
        self.UpdateManager=ns(DoUpdate=lambda mark:1 if env.fail_update else 0)
        self.ListingWindow=ns(Open=lambda:None,WriteLine=lambda line:env.lines.append(line))
    def SetUndoMark(self,visibility,name):
        self.next_mark+=1
        self.marks[self.next_mark]=[(p,list(p.Bodies),list(p.Curves.items),[(b,b.calc) for b in p.Bodies],
                                    {k:e.RightHandSide for k,e in p.Expressions.items.items()}) for p in self.Parts]
        return self.next_mark
    def UndoToMark(self,mark,name):
        self.undo_calls+=1
        for part,bodies,curves,calcs,expressions in self.marks[mark]:
            part.Bodies[:]=bodies;part.Curves.items[:]=curves
            for b,fn in calcs:b.calc=fn
            for k,rhs in expressions.items():part.Expressions.items[k].RightHandSide=rhs
    def DeleteUndoMark(self,mark,name):self.marks.pop(mark,None)


class FakeNX:
    def __init__(self):
        self.serial=0;self.objects={};self.statuses=[];self.builders=[];self.operations=[];self.lines=[];self.messages=[]
        self.expression_attribute_attempts=0
        self.attribute_attempts=[];self.reserved_attribute_attempts=[]
        self.managed=False;self.history_free=False;self.make_sheet=False;self.commits=0
        self.fail_commit_at=-1;self.fail_update=False;self.fail_save=False;self.fail_destroy=False;self.fail_dispose=False
        self.none_save_status=False;self.unsaved=0;self.unloaded=0;self.new_display_leaves_work=False;self.answer=1
        self.session=Session(self)
        N=types.ModuleType('NXOpen');N.__path__=[]
        N.Session=ns(GetSession=lambda:self.session,MarkVisibility=Session.MarkVisibility)
        N.Point3d=Point;N.Vector3d=Point;N.Matrix3x3=Matrix;N.Part=Part
        N.NXObject=ns(Null=None);N.Body=Body;N.Section=Section
        N.Expression=Expression;N.NXException=FakeNXException
        N.SmartObject=ns(UpdateOption=ns(WithinModeling='WITHIN'))
        N.Update=ns(Option=ns(Now='NOW'))
        N.BasePart=ns(Units=BasePartReadUnits,SaveComponents=ns(FalseValue='FALSE'),CloseAfterSave=ns(FalseValue='FALSE'))
        N.NXMessageBox=ns(DialogType=ns(Information='INFO',Error='ERROR',Question='QUESTION'))
        def show(title,kind,text):
            self.messages.append((title,kind,text));return self.answer if kind=='QUESTION' else -2
        N.UI=ns(GetUI=lambda:ns(NXMessageBox=ns(Show=show)))
        feature=types.ModuleType('NXOpen.Features');feature.Feature=Feature
        geo=types.ModuleType('NXOpen.GeometricUtilities')
        geo.BooleanOperation=ns(BooleanType=ns(Create='CREATE',Subtract='SUBTRACT'))
        assembly=types.ModuleType('NXOpen.Assemblies')
        ufmod=types.ModuleType('NXOpen.UF')
        def bbox(tag):
            pts=self.objects[tag].vertices()
            if not pts:raise RuntimeError('Mock clipping erased solid')
            return [min(p[i] for p in pts) for i in range(3)]+[max(p[i] for p in pts) for i in range(3)]
        self.uf=ns(Uf=ns(IsUgmanagerActive=lambda:self.managed),ModlGeneral=ns(AskBoundingBox=bbox))
        ufmod.UFSession=ns(GetUFSession=lambda:self.uf)
        self.modules={'NXOpen':N,'NXOpen.Features':feature,'NXOpen.GeometricUtilities':geo,'NXOpen.Assemblies':assembly,'NXOpen.UF':ufmod}
        for key,value in [('Features',feature),('GeometricUtilities',geo),('Assemblies',assembly),('UF',ufmod)]:setattr(N,key,value)
        self.N=N
    def install(self):return patch.dict('sys.modules',self.modules)
