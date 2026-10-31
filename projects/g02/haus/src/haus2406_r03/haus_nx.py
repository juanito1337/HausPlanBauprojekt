# -*- coding: utf-8 -*-
"""Isolierte NXOpen-Anbindung. Fuer NX 2406 entworfen, hier NICHT ausgefuehrt.

Siehe berichte/API_PRUEFSTATUS.md. Bewusst keine vermeintlichen BIM-Builder.
Ein realer Lauf des mitgelieferten Funktionstests ist erforderlich.
"""
import json
import math
import os
import platform
import sys
from pathlib import Path
from .haus_runtime import path_key, sha256_file
from .haus_profile import profile_check
from .haus_units import UnitCheckError, verify_millimeters
from .haus_metadata import (AttributeWriteError, attribute_diagnostic,
                            parameter_attributes, SCHEMA, object_attributes,
                            validate_project_attribute_title, OBJECT_ATTRIBUTE_SCHEMA,
                            OBJECT_ATTRIBUTE_TITLES, ATTRIBUTE_NAMESPACE)


class NXAdapter:
    def __init__(self,logger):
        if sys.version_info<(3,8):raise RuntimeError('Dieses Projekt benoetigt Python >= 3.8 in NX.')
        try:
            import NXOpen
            import NXOpen.Features
            import NXOpen.GeometricUtilities
            import NXOpen.Assemblies
            import NXOpen.UF
        except ImportError as ex:
            raise RuntimeError('In NX ueber Journal abspielen ausfuehren; nicht mit normalem Python. NXOpen NICHT ueber pip nachinstallieren.') from ex
        self.N=NXOpen;self.session=NXOpen.Session.GetSession();self.ui=NXOpen.UI.GetUI()
        self.uf=NXOpen.UF.UFSession.GetUFSession();self.log=logger
        self.profile_curves={};self.visibility_records=[]
        self.created=[];self.feature_count=0;self.original_display=self.session.Parts.Display
        self.original_work=self.session.Parts.Work
        self.operation='INITIALISIERUNG'
        self.warnings=[]
        self.unit_checks=[]
        self.attribute_failures=[]
        self.parameter_metadata=[]
        self.api_capabilities=self.check_api_capabilities()
        self.session.ListingWindow.Open()
        self.log('Python '+platform.python_version()+'; NX-Installation: '+os.environ.get('UGII_BASE_DIR','nicht in Umgebung angegeben'))
        # Verhindert einen unbeabsichtigten nativen Speicherlauf im verwalteten Modus.
        # UF.Uf.IsUgmanagerActive wird bewusst nicht durch geratenen Alternativnamen ersetzt.
        managed=self.uf.Uf.IsUgmanagerActive()
        if type(managed) not in (bool,int) or managed not in (0,1):
            raise RuntimeError('IsUgmanagerActive lieferte keinen eindeutigen booleschen Wert: '+repr(managed))
        if managed:
            raise RuntimeError('Teamcenter/Managed Mode aktiv. Paket ist fuer nativen Dateimodus vorgesehen. NX nativ starten.')

    def message(self,text,error=False):
        kind=self.N.NXMessageBox.DialogType.Error if error else self.N.NXMessageBox.DialogType.Information
        self.ui.NXMessageBox.Show('Haus NX2406',kind,str(text))

    def review_consent(self):
        text=('Die Scans enthalten widerspruechliche Masse.\n\n'
              'JA: R06-QUELLENPRUEFMODELL + Grundstueck/Leitungs-Planprojektionen + vorlaeufige Flachdachhaut mit geschaetzten Wandlagen, Oeffnungen und Dachhuellen erzeugen. '
              'Mit generischen Fenster-/Tuerprofilen, Verglasung und Gaubenwangen. Keine Ausfuehrungs- oder Bestandsfreigabe.\n\n'
              'ACHTUNG: Dachstuhl/Balkenlagen mangels Statik nicht ausgefuehrt! Wintergartenwand als 410-mm-Quellenvariante; Anschluss Hauptbau/Anbau offen. Kein nachgewiesener Istzustand.\n\n'
              'NEIN: nur Referenzgeruest mit Hoehen und gekennzeichneten Plankonturen.\n\n'
              'Naehere Annahmen stehen in PRUEFBERICHT_R06.html.\n'
              'Geschaetzte Werte fuer diesen Lauf freigeben?')
        result=self.ui.NXMessageBox.Show('Naeherungen ausdruecklich freigeben',self.N.NXMessageBox.DialogType.Question,text)
        # Dokumentierte NXMessageBox-Rueckgabewerte: 1=Ja, 2=Nein. Keine Freigabe bei anderen Werten.
        return result==1

    def new_part(self,path,ident):
        path=Path(path)
        if path.exists():raise FileExistsError('Vorhandenes Part wird nicht ueberschrieben: '+str(path))
        self.operation='Parts.NewDisplay: '+ident
        part=self.session.Parts.NewDisplay(str(path),self.N.Part.Units.Millimeters)
        if part is None:
            raise RuntimeError('NewDisplay lieferte kein Part: '+ident)
        self.created.append(part)
        self.ensure_work(part)
        self.check_millimeters(part,ident)
        if path_key(part.FullPath)!=path_key(path):
            raise RuntimeError('NX verwendete einen unerwarteten Dateipfad: '+str(part.FullPath))
        if not part.Preferences.Modeling.GetHistoryMode():
            raise RuntimeError('Neues Teil nicht im History Mode: '+ident)
        self.attributes(part,{'id':ident,'status':'PRUEFMODELL','phase':'UNGEKLAERT','sources':[],
                            'construction_status':'UNVOLLSTAENDIGE_QUELLENREKONSTRUKTION','as_built_verified':False})
        self.log('Teil angelegt: '+path.name)
        return part

    def check_millimeters(self,part,ident):
        """Read the BasePart enum, not the Part enum used by NewDisplay."""
        self.operation='PartUnits: '+str(ident)
        try:
            diagnostic=verify_millimeters(part,self.N,ident)
        except UnitCheckError as error:
            self.unit_checks.append(error.nx_unit_check)
            self.log('EINHEITENPRUEFUNG '+json.dumps(error.nx_unit_check,ensure_ascii=False))
            raise
        self.unit_checks.append(diagnostic)
        self.log('EINHEITENPRUEFUNG '+json.dumps(diagnostic,ensure_ascii=False))
        return diagnostic

    def add_parameters(self,part,params):
        self.ensure_work(part)
        created=set();visiting=set()
        def add(name):
            if name in created:return
            if name in visiting:raise ValueError('Zyklische Parameter vor NX-Expression: '+name)
            visiting.add(name)
            item=params.items[name]
            if item.get('unit') not in ('mm','deg'):raise ValueError('Nicht unterstuetzte Einheit: '+name)
            if item.get('value') is None and item.get('formula') is None:
                visiting.remove(name)
                return
            rhs=item.get('formula')
            if rhs is not None:
                for dep in sorted(params.dependencies(rhs)):add(dep)
            else:rhs=format(params.value(name),'.12g')
            params.value(name)  # Endlichkeit/Abhaengigkeiten vor NX pruefen.
            metadata_values,payload=parameter_attributes(name,item)
            unit_name='Degrees' if item['unit']=='deg' else 'MilliMeter'
            unit=part.UnitCollection.FindObject(unit_name)
            self.operation='Expressions.CreateWithUnits: '+name
            expression=part.Expressions.CreateWithUnits(name+'='+str(rhs),unit)
            if expression is None:
                raise RuntimeError('CreateWithUnits lieferte keinen Ausdruck: '+name)
            # R03c: Expressions exist, but this installation rejects their
            # inherited SetUserAttribute call. Use the owning part instead.
            self.parameter_provenance(part,name,metadata_values,payload)
            created.add(name);visiting.remove(name)
        for name in params.items:add(name)
        return len(created)

    def parameter_provenance(self,part,name,values,payload):
        self.ensure_work(part)
        record={'part_file':str(part.FullPath),'expression_name':name,
                'payload':payload,'storage':'PART_USER_ATTRIBUTES',
                'attribute_count':len(values),'written_attributes':0,
                'status':'SCHREIBT'}
        self.parameter_metadata.append(record)
        try:
            for key,value in values.items():
                self._set_user_attribute(part,key,value,'PARAMETER '+name)
                record['written_attributes']+=1
        except Exception:
            record['status']='UNVOLLSTAENDIG_LAUF_ABGEBROCHEN'
            raise
        record['status']='PART_ATTRIBUTE_GESCHRIEBEN'

    def metadata_snapshot(self):
        # Build provenance, NOT a readback of saved NX attributes/current values.
        return {'schema':SCHEMA,'storage':'PART_USER_ATTRIBUTES',
                'object_attribute_schema':OBJECT_ATTRIBUTE_SCHEMA,
                'object_attribute_titles':dict(OBJECT_ATTRIBUTE_TITLES),
                'physical_material_assignment':False,
                'scope':'Schreibprotokoll und Quellen-Snapshot; kein NX-Attribut-Lesetest.',
                'live_expression_values':False,
                'records':list(self.parameter_metadata),
                'attribute_failures':list(self.attribute_failures)}

    def _set_user_attribute(self,obj,key,value,context):
        text=str(value)
        previous=self.operation
        self.operation='SetUserAttribute: '+str(context)+' | '+str(key)
        try:
            validate_project_attribute_title(key)
            # R11a: only the optional performance adapter selects Later.
            # Feature updates and the mandatory pre-save DoUpdate remain active.
            obj.SetUserAttribute(key,-1,text,getattr(self,'_attribute_update_option',self.N.Update.Option.Now))
        except Exception as exception:
            diagnostic=attribute_diagnostic(obj,key,text,exception,self.operation)
            diagnostic['project_attribute_namespace']=ATTRIBUTE_NAMESPACE
            diagnostic['object_attribute_schema']=OBJECT_ATTRIBUTE_SCHEMA
            self.attribute_failures.append(diagnostic)
            error=AttributeWriteError('NX-Attribut konnte nicht geschrieben werden: '+str(key)+
                                      ' an '+diagnostic['object_type']+' '+str(diagnostic['object_name'])+
                                      '\n'+diagnostic['error'],diagnostic)
            # Preserve the originating API error even if a diagnostic log fails.
            try:self.log('ATTRIBUTFEHLER '+json.dumps(diagnostic,ensure_ascii=False))
            except Exception as log_error:
                diagnostic['diagnostic_log_error']=str(log_error)
            raise error from exception
        else:
            self.operation=previous

    def update(self,label):
        mark=self.session.SetUndoMark(self.N.Session.MarkVisibility.Invisible,'R03 Update '+label)
        try:
            count=self.session.UpdateManager.DoUpdate(mark)
            if count:raise RuntimeError('NX-Aktualisierungsfehler bei '+label+': '+str(count))
        finally:self.session.DeleteUndoMark(mark,None)

    def attributes(self,obj,meta):
        # Never call SetUserAttribute on NX expressions. No catch-and-ignore.
        if isinstance(obj,self.N.Expression):
            raise TypeError('Ausdrucksmetadaten auf dem zugehoerigen Part speichern; kein Expression.SetUserAttribute.')
        # R03d: all project metadata uses HAUS_. NX owns the bare MATERIAL
        # title; never overwrite, unlock, delete, or silently omit that field.
        values=object_attributes(meta)
        for key,value in values.items():
            self._set_user_attribute(obj,key,value,meta.get('id','UNBENANNT'))

    def lines(self,part,points,name,closed=True,blank=False,meta=None):
        self.ensure_work(part)
        out=[];pairs=list(zip(points,points[1:]))
        if closed:pairs.append((points[-1],points[0]))
        for i,(a,b) in enumerate(pairs):
            if math.dist(a,b)<1e-5:continue
            curve=part.Curves.CreateLine(self.N.Point3d(*map(float,a)),self.N.Point3d(*map(float,b)))
            curve.SetName(name+'_%03d'%(i+1))
            if meta:self.attributes(curve,meta)
            if blank:curve.Blank()
            out.append(curve)
        return out

    def extrude(self,part,points,start,end,name,meta,target=None,direction=(0,0,1)):
        """Ein geschlossenes konvexes Profil, mit gezielter Ruecknahme bei Fehlern."""
        self.ensure_work(part)
        checked=profile_check(points,direction,name)
        direction=checked['direction']
        if isinstance(start,(int,float)) and isinstance(end,(int,float)) and end<=start:
            raise ValueError(name+': Endgrenze muss groesser als Startgrenze sein.')
        if target is not None:
            if not target.IsSolidBody:
                raise ValueError(name+': Schnittziel ist kein Volumenkoerper.')
            if target.OwningPart.Tag != part.Tag:
                raise ValueError(name+': Schnittziel gehoert zu einem anderen Teil.')
        N=self.N
        mark=self.session.SetUndoMark(N.Session.MarkVisibility.Invisible,name)
        builder=None
        self.operation=name+': PROFIL'
        try:
            curves=self.lines(part,points,name+'_PROFIL')
            if len(curves)!=len(points):raise ValueError('Profilkanten verloren: '+name)
            self.operation=name+': CreateExtrudeBuilder'
            builder=part.Features.CreateExtrudeBuilder(N.Features.Feature.Null)
            if builder is None:raise RuntimeError('CreateExtrudeBuilder lieferte None')
            section=part.Sections.CreateSection(0.00095,0.001,0.5)
            section.SetAllowedEntityTypes(N.Section.AllowTypes.OnlyCurves)
            rule=part.ScRuleFactory.CreateRuleCurveDumb(curves)
            # Mittelpunkt der Startkante statt eines mehrdeutigen Eckpunkts.
            help_point=[(a+b)/2.0 for a,b in zip(points[0],points[1])]
            section.AddToSection([rule],curves[0],N.NXObject.Null,N.NXObject.Null,
                                 N.Point3d(*map(float,help_point)),N.Section.Mode.Create,False)
            builder.Section=section
            builder.DistanceTolerance=0.001
            builder.Direction=part.Directions.CreateDirection(N.Point3d(0.,0.,0.),
                                N.Vector3d(*map(float,direction)),N.SmartObject.UpdateOption.WithinModeling)
            builder.Limits.StartExtend.Value.RightHandSide=str(start)
            builder.Limits.EndExtend.Value.RightHandSide=str(end)
            if target is None:
                builder.BooleanOperation.Type=N.GeometricUtilities.BooleanOperation.BooleanType.Create
            else:
                builder.BooleanOperation.Type=N.GeometricUtilities.BooleanOperation.BooleanType.Subtract
                builder.BooleanOperation.SetTargetBodies([target])
            self.operation=name+': CommitFeature'
            feature=builder.CommitFeature()
            if feature is None:raise RuntimeError('CommitFeature lieferte kein Feature')
            self.operation=name+': DoUpdate'
            errors=self.session.UpdateManager.DoUpdate(mark)
            if errors:raise RuntimeError('NX-Update meldet Fehler: '+str(errors))
            feature.SetName(name);self.attributes(feature,meta)
            bodies=list(feature.GetBodies())
            if len(bodies)!=1:
                raise RuntimeError('Genau ein Ergebniskoerper erwartet, erhalten: '+str(len(bodies)))
            for i,body in enumerate(bodies):
                if not body.IsSolidBody:raise RuntimeError('Flaechenkoerper statt Volumenkoerper')
                if body.OwningPart.Tag != part.Tag:raise RuntimeError('Ergebniskoerper im falschen Part')
                body.SetName(name+'_KOERPER_%02d'%(i+1));self.attributes(body,meta)
                # R05: no invisible category layer inherited from templates.
                # Existing Layer setter only; category remains in HAUS_KATEGORIE.
                body.Layer=1
            self.profile_curves.setdefault(part.Tag,[]).extend(curves)
            for curve in curves:curve.Blank()
            self.operation=name+': DestroyBuilder'
            completed_builder=builder;builder=None
            completed_builder.Destroy()
            self.feature_count+=1
            return bodies
        except Exception as ex:
            failed_operation=self.operation
            if builder is not None:
                try:builder.Destroy()
                except Exception as cleanup:self.log('Zusaetzlicher Builder-Aufraeumfehler: '+str(cleanup))
                builder=None
            try:self.session.UndoToMark(mark,None)
            except Exception as rollback:self.log('Zusaetzlich: Undo fehlgeschlagen: '+str(rollback))
            raise RuntimeError('NX-Schritt fehlgeschlagen: '+failed_operation+'\n'+str(ex)) from ex
        finally:
            try:self.session.DeleteUndoMark(mark,None)
            except Exception as cleanup:self.log('Undo-Marke nicht entfernbar: '+str(cleanup))

    def xy_extrude(self,part,polygon,bottom,top,name,meta,target=None):
        return self.extrude(part,[[p[0],p[1],0] for p in polygon],bottom,top,name,meta,target)

    def finalize_display_objects(self,part):
        """Only objects owned by this run. No new view/reference-set API guesses.
        Body layer 1, profile curves blanked AFTER last update/builder disposal.
        Shading style and assembly layer overrides still need visual checking.
        """
        self.ensure_work(part)
        curves=self.profile_curves.get(part.Tag,[])
        for curve in curves:curve.Blank()
        for body in part.Bodies:body.Layer=1
        self.visibility_records.append({'part':str(part.FullPath),'body_layer':1,
          'profile_curves_blanked':len(curves),'body_count':len(list(part.Bodies)),
          'scope':'Objektlayer/Blank gesetzt; kein Nachweis der tatsaechlichen Bildschirmansicht.'})

    def save(self,part):
        self.ensure_work(part)
        self.operation='Part.Save: '+str(part.FullPath)
        self.update('Speichern '+Path(part.FullPath).name)
        self.finalize_display_objects(part)
        status=part.Save(self.N.BasePart.SaveComponents.FalseValue,self.N.BasePart.CloseAfterSave.FalseValue)
        if status is None:raise RuntimeError('Part.Save lieferte keinen auswertbaren Status.')
        try:
            if status.NumberUnsavedParts>0:
                raise RuntimeError('NX meldet nicht gespeicherte Teile: '+str(status.NumberUnsavedParts))
        finally:self.dispose(status)
        path=Path(part.FullPath)
        if not path.is_file() or path.stat().st_size==0:raise RuntimeError('Gespeicherte Datei fehlt: '+str(path))
        self.log('Gespeichert: '+path.name)
        return {'file':path.name,'bytes':path.stat().st_size,'bodies':len(list(part.Bodies)), 'sha256':sha256_file(path)}

    def add_component(self,master,path,name):
        self.ensure_work(master)
        self.operation='AddComponent: '+name
        if not Path(path).is_file():raise FileNotFoundError('Komponentenpart fehlt: '+str(path))
        matrix=self.N.Matrix3x3()
        matrix.Xx=1.;matrix.Xy=0.;matrix.Xz=0.
        matrix.Yx=0.;matrix.Yy=1.;matrix.Yz=0.
        matrix.Zx=0.;matrix.Zy=0.;matrix.Zz=1.
        component,status=master.ComponentAssembly.AddComponent(str(path),'Entire Part',name,
                             self.N.Point3d(0.,0.,0.),matrix,-1)
        if status is None:raise RuntimeError('AddComponent lieferte keinen Ladestatus.')
        try:
            if component is None:raise RuntimeError('Komponente fehlt: '+name)
            if status.NumberUnloadedParts>0:
                raise RuntimeError('Nicht geladene Komponenten: '+str(status.NumberUnloadedParts))
        finally:self.dispose(status)
        self.attributes(component,{'id':name,'status':'PRUEFMODELL','sources':[]})
        if component.Prototype is None or path_key(component.Prototype.FullPath)!=path_key(path):
            raise RuntimeError('Falscher/fehlender Komponenten-Prototyp: '+name)
        self.check_identity(component)
        return component

    def check_identity(self,component):
        name=component.Name
        origin,rotation=component.GetPosition()
        values=[rotation.Xx,rotation.Xy,rotation.Xz,rotation.Yx,rotation.Yy,rotation.Yz,rotation.Zx,rotation.Zy,rotation.Zz]
        if max(abs(float(a)-b) for a,b in zip(values,[1,0,0,0,1,0,0,0,1]))>1e-8 or max(abs(origin.X),abs(origin.Y),abs(origin.Z))>1e-5:
            raise RuntimeError('Komponente nicht in vereinbarter Identitaetslage: '+name)
        return True

    def fit(self,part):
        try:part.ModelingViews.WorkView.Fit()
        except Exception as ex:self.log('Ansicht nicht automatisch eingepasst: '+str(ex))

    def restore_display_after_failure(self):
        if self.original_display is not None:
            try:
                result=self.session.Parts.SetDisplay(self.original_display,False,False)
                if not isinstance(result,tuple) or len(result)!=2:
                    raise RuntimeError('Unerwarteter SetDisplay-Rueckgabewert: '+repr(result))
                self.dispose(result[1])
            except Exception as ex:self.log('Urspruengliches Anzeigeteil bitte manuell aktivieren: '+str(ex))
        if self.original_work is not None:
            try:self.session.Parts.SetWork(self.original_work)
            except Exception as ex:self.log('Urspruengliches Arbeitsteil bitte manuell aktivieren: '+str(ex))

    def ensure_work(self,part):
        # Keine implizite Bearbeitung bereits geoeffneter Nutzermodelle.
        if all(part.Tag != created.Tag for created in self.created):
            raise RuntimeError('Schreibzugriff auf nicht von diesem Lauf erzeugtes Part verweigert.')
        work=self.session.Parts.Work
        if work is None or work.Tag!=part.Tag:
            self.session.Parts.SetWork(part)
        if self.session.Parts.Work is None or self.session.Parts.Work.Tag!=part.Tag:
            raise RuntimeError('Arbeitsteil konnte nicht aktiviert werden: '+str(part.FullPath))

    def dispose(self,status):
        if status is None:return
        try:status.Dispose()
        except Exception as ex:
            # Ein Aufraeumfehler darf den eigentlichen Speicher-/Ladefehler nicht ersetzen.
            self.warnings.append('Status.Dispose: '+str(ex))
            self.log(self.warnings[-1])

    def safe_message(self,text,error=False):
        try:self.message(text,error)
        except Exception as ex:self.log('Meldungsfenster nicht verfuegbar: '+str(ex)+' | '+str(text))

    def check_api_capabilities(self):
        """Nur konkret benoetigte Attribute, keine Namensraten-Fallbacks."""
        roots={'NXOpen':self.N, 'Session':self.session, 'UFSession':self.uf}
        paths={
          'NXOpen':['Part.Units.Millimeters','BasePart.Units.Millimeters','Expression','Features.Feature.Null','NXObject.Null',
                    'Point3d','Vector3d','Matrix3x3','Section.AllowTypes.OnlyCurves',
                    'Section.Mode.Create','SmartObject.UpdateOption.WithinModeling',
                    'GeometricUtilities.BooleanOperation.BooleanType.Create',
                    'GeometricUtilities.BooleanOperation.BooleanType.Subtract',
                    'Update.Option.Now','Session.MarkVisibility.Invisible',
                    'BasePart.SaveComponents.FalseValue','BasePart.CloseAfterSave.FalseValue'],
          'Session':['Parts.NewDisplay','Parts.SetWork','Parts.OpenDisplay','Parts.SetDisplay',
                     'SetUndoMark','UndoToMark','DeleteUndoMark','UpdateManager.DoUpdate'],
          'UFSession':['Uf.IsUgmanagerActive','ModlGeneral.AskBoundingBox']}
        found=[];missing=[]
        for root,names in paths.items():
            for path in names:
                value=roots[root]
                try:
                    for key in path.split('.'):value=getattr(value,key)
                    found.append(root+'.'+path)
                except AttributeError:missing.append(root+'.'+path)
        if missing:
            raise RuntimeError('Benoetigte NXOpen-API fehlt in dieser Installation:\n'+'\n'.join(missing))
        return {'present':found, 'missing':missing,
                'scope':'Attributverfuegbarkeit, keine Bestaetigung aller Python-Signaturen oder Lizenzen.',
                'python':platform.python_version(),
                'UGII_VERSION':os.environ.get('UGII_VERSION','NICHT_GEMELDET'),
                'UGII_BASE_DIR':os.environ.get('UGII_BASE_DIR','NICHT_GEMELDET')}

    def bounding_box(self,body):
        box=self.uf.ModlGeneral.AskBoundingBox(body.Tag)
        if len(box)!=6 or not all(math.isfinite(float(x)) for x in box):
            raise RuntimeError('Ungueltige Begrenzungsbox: '+repr(box))
        box=[float(x) for x in box]
        if any(box[i+3]<=box[i] for i in range(3)):
            raise RuntimeError('Leere/degenerierte Begrenzungsbox: '+repr(box))
        return box

    def load_fully(self,part):
        if part.IsFullyLoaded:return
        status=part.LoadFully()
        try:
            if status is not None and status.NumberUnloadedParts:
                raise RuntimeError('Komponente konnte nicht vollstaendig geladen werden: '+str(part.FullPath))
        finally:self.dispose(status)
        if not part.IsFullyLoaded:
            raise RuntimeError('Komponente noch teilweise geladen: '+str(part.FullPath))
