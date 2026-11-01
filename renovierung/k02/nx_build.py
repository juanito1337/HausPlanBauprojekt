"""Production NX journal for one independent state; invoked in a new process."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def attribute(obj, key, value):
    import NXOpen
    text = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
    # Lists are retained individually, avoiding NX's string attribute length limit.
    if len(text) > 1000:
        for index, start in enumerate(range(0, len(text), 900)):
            obj.SetUserAttribute(key+'_%03d'%index, -1, text[start:start+900], NXOpen.Update.Option.Now)
    else:
        obj.SetUserAttribute(key, -1, text, NXOpen.Update.Option.Now)


def save(part):
    import NXOpen
    part.Save(NXOpen.BasePart.SaveComponents.FalseValue, NXOpen.BasePart.CloseAfterSave.FalseValue).Dispose()


def import_mesh(session, part, path, nx_root):
    import NXOpen
    before = {b.Tag for b in part.Bodies}
    builder = session.DexManager.CreateStep214Importer()
    try:
        builder.SettingsFile = str(Path(nx_root)/'STEP214UG/step214ug.def')
        builder.InputFile = path
        builder.OutputFile = part.FullPath
        builder.ImportTo = NXOpen.Step214Importer.ImportToOption.WorkPart
        builder.ImportToTeamcenter = False
        builder.FileOpenFlag = False
        builder.ProcessHoldFlag = True
        builder.FlattenAssembly = True
        builder.ObjectTypes.Curves = False
        builder.ObjectTypes.Surfaces = True
        builder.ObjectTypes.Solids = True
        builder.SewSurfaces = False
        builder.Optimize = False
        builder.SimplifyGeometry = False
        builder.SmoothBSurfaces = False
        builder.Commit()
    finally:
        builder.Destroy()
    return [b for b in part.Bodies if b.Tag not in before]


def style(bodies, role, layer, color, hidden=False):
    for index, body in enumerate(bodies):
        body.SetName('K02_'+role+'_%02d'%index)
        body.Layer = layer
        body.Color = color
        if hidden: body.Blank()
        else: body.Unblank()


def note(part, lines, point, name, size=130):
    import NXOpen
    import NXOpen.Annotations
    builder = part.Annotations.CreateDraftingNoteBuilder(None)
    try:
        builder.Origin.Plane.PlaneMethod = NXOpen.Annotations.PlaneBuilder.PlaneMethodType.XyPlane
        builder.Origin.SetInferRelativeToGeometry(False)
        builder.Origin.Origin.SetValue(None, None, NXOpen.Point3d(*point))
        builder.Text.TextBlock.SetText(lines)
        builder.Style.LetteringStyle.GeneralTextSize = float(size)
        obj = builder.Commit()
        obj.SetName(name)
        return obj
    finally:
        builder.Destroy()


def register_geometry(part, register):
    import NXOpen
    for row in register:
        a = row['origin_mm']; t = row['tangent']; length = row['length_mm']
        line = part.Curves.CreateLine(NXOpen.Point3d(a[0], a[1], 0.0),
                NXOpen.Point3d(a[0]+length*t[0], a[1]+length*t[1], 0.0))
        line.SetName(row['id']+'_'+row['status']+'_XY_REFERENCE_Z0_NO_DEPTH')
        line.Layer = 200
        line.Color = 186 if not row['native_candidate'] else 36
        attribute(line, 'K02_STATUS', {k: row.get(k) for k in ('id','status','blockers','geometry_conflicts','overbuild_projection_conflicts','geometry_warnings','volume_m3')})
        # Spatially stagger labels outward; Z=0 explicitly remains a reference plane.
        n = row['normal']; p = [a[k]+0.5*length*t[k]+650*n[k] for k in range(2)]
        label = note(part, [row['id'], 'GESPERRT' if not row['native_candidate'] else 'PRUEFEN'], [p[0],p[1],0.0], 'REGISTER_'+row['id'], 95)
        label.Layer = 201
    note(part, ['K02 STUDIE - KEINE BAUFREIGABE',
        'UNABHAENGIGE EINZELFELDVARIANTE / KEINE BAUFOLGE / KEINE NETTOGESAMTMENGE',
        'REGISTER: XY-REFERENZEBENE Z=0; KEINE TIEFEN ODER LEITUNGSLAGEN',
        'STUDIENBODEN: LOKALER TIN-AUSSCHNITT MIT KUENSTLICHER UNTERKANTE'],
        [-9000.0,-11000.0,0.0], 'K02_STUDY_LIMITATIONS', 180)


def main():
    request = json.loads(Path(os.environ['K02_NX_REQUEST']).read_text(encoding='utf-8'))
    sys.path.insert(0, request['repo_root'])
    result = {'status': 'FAIL'}
    try:
        import NXOpen
        import NXOpen.UF
        import NXOpen.Features
        from renovierung.k02.nx_verify import transforms, measure, open_all
        from renovierung.k02.runner import validate_measurement
        session = NXOpen.Session.GetSession()
        uf = NXOpen.UF.UFSession.GetUFSession()
        if list(session.Parts): raise RuntimeError('Fresh NX process required')
        source, root = Path(request['source']).resolve(), Path(request['directory']).resolve()
        original = {r['path']: hashlib.sha256((source/r['path']).read_bytes()).hexdigest() for r in request['source_parts']}
        options = session.Parts.LoadOptions
        options.ComponentLoadMethod = NXOpen.LoadOptions.LoadMethod.SearchDirectories
        dirs = sorted({str((source/r['path']).parent) for r in request['source_parts']})
        options.SetSearchDirectories(dirs, [False]*len(dirs))
        options.ComponentsToLoad = NXOpen.LoadOptions.LoadComponents.All
        options.UsePartialLoading = False
        options.UseLightweightRepresentations = False
        uf.Clone.Initialise(uf.Clone.OperationClass.CLONE_OPERATION)
        try:
            uf.Clone.SetDefAction(uf.Clone.Action.CLONE)
            load, code = uf.Clone.AddAssembly(str(source/request['source_master']))
            if code or load.Failed or load.UserAbort or load.NParts: raise ValueError('Clone source load failed')
            for old, new in request['mapping'].items():
                uf.Clone.SetNaming(str(source/old), uf.Clone.NamingTechnique.USER_NAME, str(root/new))
            failures = uf.Clone.PerformClone(uf.Clone.InitNamingFailures())
            if failures.NFailures: raise ValueError('Clone naming failures: '+str(failures.Statuses))
        finally:
            uf.Clone.Terminate()
        master_name = request['mapping'][request['source_master']]
        master = open_all(session, root, master_name, 'AsSaved')
        source_transforms = [dict(t, part=request['mapping'][t['part']]) for t in request['source_transforms']]
        if transforms(master, root) != source_transforms: raise ValueError('Clone transformed source geometry')
        for part in session.Parts:
            Path(part.FullPath).resolve().relative_to(root)
        session.Parts.SetWork(master)
        for key, value in {'K02_STATE': request['state_id'], 'K02_CONSTRUCTION_RELEASE': False,
                'K02_SOURCE_FINGERPRINT': request['source_fingerprint'],
                'K02_VARIANT': 'INDEPENDENT_SINGLE_FIELD_NO_CUMULATIVE_UNION_OR_NET_TOTAL',
                'K02_REGISTER_PLANE': 'XY_Z0_REFERENCE_ONLY_NO_DEPTH',
                'K02_LOCAL_SOIL': 'LOCAL_TIN_PATCH_ARTIFICIAL_BOTTOM'}.items(): attribute(master, key, value)
        register_geometry(master, request['register'])
        measurements = {}
        field = request['field']
        if field:
            attribute(master, 'K02_FIELD_METADATA', field)
            # Preserve the independent source reference but hide it for a clear local cut.
            terrain_sources = [r for r in request['source_parts'] if Path(r['path']).name.startswith('01_GELAENDE_')]
            if len(terrain_sources) != 1: raise ValueError('Cannot identify original terrain reference')
            terrain_name = request['mapping'][terrain_sources[0]['path']]
            terrain = next(p for p in session.Parts if Path(p.FullPath).name == terrain_name)
            for body in terrain.Bodies: body.Blank()
            attribute(terrain, 'K02_REFERENCE_ONLY', 'PRESERVED_SOURCE_TERRAIN_BLANK_LOCAL_CUT_PATCH_SHOWN')
            save(terrain)
            geometry_name = request['state_id']+'_STUDY.prt'
            geometry = session.Parts.NewDisplay(request['geometry_work_file'], NXOpen.Part.Units.Millimeters)
            session.Parts.SetWork(geometry)
            imported = {}
            for role, path in request['imports'].items():
                imported[role] = import_mesh(session, geometry, path, request['nx_root'])
                if not imported[role]: raise ValueError('STEP import contains no solids: '+role)
                measurements[role] = measure(imported[role])
                if role == 'excavation': expected = [v/1e9 for v in field['component_volumes_mm3']]
                elif role.startswith('pile_'):
                    pile = field['stockpile']['main' if role == 'pile_main' else 'reserve_1_25']
                    expected = [v/1e9 for v in pile['component_volumes_mm3']]
                else: expected = [request['soil_expected_m3']]
                validate_measurement(measurements[role], expected)
            boolean = geometry.Features.CreateBooleanBuilderUsingCollector(NXOpen.Features.BooleanFeature.Null)
            try:
                boolean.Operation = NXOpen.Features.Feature.BooleanType.Subtract
                boolean.TargetBodyCollector = geometry.ScCollectors.CreateCollector()
                boolean.ToolBodyCollector = geometry.ScCollectors.CreateCollector()
                boolean.TargetBodyCollector.ReplaceRules([geometry.ScRuleFactory.CreateRuleBodyDumb(imported['soil'])], False)
                boolean.ToolBodyCollector.ReplaceRules([geometry.ScRuleFactory.CreateRuleBodyDumb(imported['excavation'])], False)
                boolean.RetainTarget = False
                boolean.RetainTool = True
                boolean.Tolerance = 0.001
                feature = boolean.CommitFeature()
                cut = list(feature.GetBodies())
            finally:
                boolean.Destroy()
            measurements['cut_soil'] = measure(cut)
            removed = measurements['soil']['volume_m3']-measurements['cut_soil']['volume_m3']
            if abs(removed-field['volume_m3']) > max(1e-9, field['volume_m3']*1e-6):
                raise ValueError('Boolean removed volume mismatch')
            original_soil_measurement = measurements.pop('soil')
            style(cut, 'cut_soil', 101, 110)
            style(imported['excavation'], 'excavation', 102, 186, True)
            style(imported['pile_main'], 'pile_main', 103, 75)
            style(imported['pile_reserve'], 'pile_reserve', 104, 36, True)
            for key, value in {'K02_CONSTRUCTION_RELEASE': False, 'K02_FIELD': field['id'],
                'K02_SOIL_UNCUT_MEASUREMENT': original_soil_measurement, 'K02_REMOVED_M3': removed,
                'K02_LAYERS': '101 cut soil+slope faces;102 excavation hidden;103 loose pile main;104 alternative1.25 hidden',
                'K02_LOCAL_SOIL': 'LOCAL_TIN_PATCH_ARTIFICIAL_BOTTOM_NOT_FULL_PROPERTY'}.items(): attribute(geometry, key, value)
            save(geometry)
            geometry.SaveAs(str(root/geometry_name)).Dispose()
            _, display_status = session.Parts.SetDisplay(master, False, False)
            if display_status is not None:
                try:
                    if display_status.NumberUnloadedParts:
                        raise ValueError('Master display switch left unloaded parts')
                finally:
                    display_status.Dispose()
            if session.Parts.Display.Tag != master.Tag:
                raise ValueError('Master display root did not switch')
            session.Parts.SetWork(master)
            matrix = NXOpen.Matrix3x3()
            for key, val in zip(('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz'), (1.,0.,0.,0.,1.,0.,0.,0.,1.)): setattr(matrix,key,val)
            component, status = master.ComponentAssembly.AddComponent(str(root/geometry_name), 'Entire Part',
                request['state_id']+'_LOCAL_STUDY', NXOpen.Point3d(0.,0.,0.), matrix, -1)
            try:
                if component is None or status.NumberUnloadedParts: raise ValueError('Study component not loaded')
            finally: status.Dispose()
        save(master)
        if original != {p: hashlib.sha256((source/p).read_bytes()).hexdigest() for p in original}:
            raise ValueError('Original source part changed')
        parts = [{'path': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(root.glob('*.prt'))]
        result = {'status': 'PASS', 'id': request['state_id'], 'master': master_name, 'parts': parts,
                  'transforms': transforms(master, root), 'source_transforms_preserved': True,
                  'measurements': measurements, 'source_hashes_unchanged': True,
                  'construction_release': False, 'register_count': len(request['register']),
                  'original_soil_measurement': original_soil_measurement if field else None,
                  'removed_m3': removed if field else None}
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
    Path(request['report']).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    if result['status'] != 'PASS': raise RuntimeError(result['error'])


if __name__ == '__main__': main()
