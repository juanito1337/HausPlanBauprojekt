"""One shared, property-clipped display Part for additive annex alternatives.

No NX calls and no new DGM are made here. The registered Grid from
anbau.geometry.load_terrain is consumed unchanged; the established M01 context
partitioner retains its source TIN and 200-mm display-only parallel underside.

Native contract: import write_site_step output once with independent solids;
measure each actual ABS BBox/volume/optional volume centroid; call
match_native_shells; name bodies by shell ID and populate each reference set
from its shell_ids through the returned SID-to-native-tag mapping.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re

from renovierung.k02 import geometry as geom
from renovierung.k02.mesh_step import write_step
from renovierung.k02.terrain import Grid
from renovierung.m01.context import THICKNESS_MM, _boundary, _generate, _tin_z

PART_FILE = 'ANBAU_SITE.prt'
CAD_TOLERANCE_MM = .25


def _number(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite numeric shared-ground coordinate required')
    return value


def _numbers(values, count):
    if not isinstance(values,(list,tuple)) or len(values)!=count:
        raise ValueError('Malformed shared-ground coordinates')
    return [_number(v) for v in values]


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _crop_limits(grid, box):
    """Independently reproduce Grid.triangles' UV floor/ceil/clamp contract."""
    x0,y0,x1,y1=_numbers(box,4)
    if x0>=x1 or y0>=y1:raise ValueError('Empty annex crop bbox')
    uv=[grid.uv(p) for p in ((x0,y0),(x0,y1),(x1,y0),(x1,y1))]
    result=[max(0,math.floor(min(p[0] for p in uv))),
            min(grid.nu-1,math.ceil(max(p[0] for p in uv))),
            max(0,math.floor(min(p[1] for p in uv))),
            min(grid.nv-1,math.ceil(max(p[1] for p in uv)))]
    if result[0]>=result[1] or result[2]>=result[3]:raise ValueError('Empty annex crop cell domain')
    return result


def _cut_domain(grid,n,field,bounds):
    """Read an existing cut mesh; prove the complete XY crop domain, not a hull.

    The cut-soil producer is a piecewise single-height top over two independent
    r<=0/r>=0 halves. Its upward face projections must cover the declared full
    cell parallelogram, whose corners/bounds are independently checked here.
    No field-specific DGM mesh is reconstructed.
    """
    mesh=field['geometry']['cut_soil']['mesh']
    geom.validate_mesh(mesh)
    uv=[grid.uv(p[:2]) for p in mesh['vertices']]
    i0,i1,j0,j1=bounds
    actual=[min(p[0] for p in uv),max(p[0] for p in uv),min(p[1] for p in uv),max(p[1] for p in uv)]
    if any(abs(a-b)>1e-7 for a,b in zip(actual,bounds)):
        raise ValueError('Actual cut-soil UV domain differs: '+field['id'])
    if any(not any(abs(u-i)<1e-7 and abs(v-j)<1e-7 for u,v in uv)
           for i,j in ((i0,j0),(i0,j1),(i1,j0),(i1,j1))):
        raise ValueError('Actual cut-soil crop corner missing: '+field['id'])
    top=[]
    for face in mesh['faces']:
        points=[mesh['vertices'][i] for i in face]
        ar=geom.area([p[:2] for p in points])
        if ar>1e-10:top.append((points,ar))
    area=sum(ar for _,ar in top)
    expected=abs(grid.det)*(i1-i0)*(j1-j0)
    if abs(area-expected)>max(1e-5,expected*1e-9):
        raise ValueError('Actual cut-soil does not cover the full crop: '+field['id'])
    gaps=[_tin_z(grid,n,p[:2])-p[2] for points,_ in top for p in points]
    if not gaps or min(gaps)<-1e-5 or abs(min(gaps))>1e-5:
        raise ValueError('Actual cut-soil height differs from the registered TIN: '+field['id'])
    return {'uv_cell_bounds':list(bounds),'projected_top_area_m2':area/1e6,
            'cut_soil_mesh_sha256':_hash(mesh)}


def _descriptor(mesh):
    measurement=geom.validate_mesh(mesh)
    if measurement['expected_body_count']!=1:raise ValueError('Expected one independent display shell')
    points=mesh['vertices']
    box=[min(p[k] for p in points) for k in range(3)]+[max(p[k] for p in points) for k in range(3)]
    origin=points[0];moment=[0.,0.,0.];volume=0.
    for face in mesh['faces']:
        a,b,c=[[points[i][k]-origin[k] for k in range(3)] for i in face]
        cross=(b[1]*c[2]-b[2]*c[1],b[2]*c[0]-b[0]*c[2],b[0]*c[1]-b[1]*c[0])
        tetra=sum(a[k]*cross[k] for k in range(3))/6
        volume+=tetra
        for k in range(3):moment[k]+=tetra*(a[k]+b[k]+c[k])/4
    return {'bbox_mm':box,'volume_m3':measurement['volume_mm3']/1e9,
            'centroid_mm':[origin[k]+moment[k]/volume for k in range(3)]}


def _same_volume(a,b):
    return abs(a-b)<=max(1e-10,abs(b)*1e-6)


def _matches(expected,actual,*,centroid=True):
    return (all(abs(a-b)<=CAD_TOLERANCE_MM for a,b in zip(expected['bbox_mm'],actual['bbox_mm']))
            and _same_volume(actual['volume_m3'],expected['volume_m3'])
            and (not centroid or all(abs(a-b)<=CAD_TOLERANCE_MM
                                     for a,b in zip(expected['centroid_mm'],actual['centroid_mm']))))


def create_site_context(terrain,fields,include_mesh=False):
    """Create one shared Part manifest from registered terrain and full field meshes.

    `fields` is the existing annex PLAN['fields']; only native_candidate=True
    contributes a reference set. Full existing cut_soil meshes are required to
    prove the mask domain. `include_mesh=True` adds one combined transfer mesh.
    """
    try:
        source=terrain['grid']
        grid=Grid({'shape':[source.nu,source.nv],'nodes_mm':source.nodes})
        n=terrain['TIN_subdivisions']
        if type(n) is not int or not 1<=n<=16:raise ValueError('Invalid shared-ground TIN subdivision')
        eps=grid.error_bound(n)
        if abs(_number(terrain['max_vertical_error_mm'])-eps)>1e-8:
            raise ValueError('Shared-ground TIN error differs')
        registration=deepcopy(terrain['height_registration'])
        translation=_numbers(registration['translation_mm'],3)
        if translation[:2]!=[0,0] or registration['applied_once_to_source_grid'] is not True:
            raise ValueError('Shared-ground requires an already registered EG grid')
        boundary=_boundary({'closed':True,'points_local_mm':terrain['boundary_xy_mm']},grid)
        seen=set();regions={};checks={};crop_boxes={}
        for field in sorted(fields,key=lambda f:f['id']):
            fid=field['id']
            if (not isinstance(fid,str) or not re.fullmatch(r'PS1[0-3]-F[0-9]+',fid)
                    or fid in seen or type(field['native_candidate']) is not bool):
                raise ValueError('Malformed/duplicate annex shared-ground field')
            seen.add(fid)
            if not field['native_candidate']:continue
            study=field['study_terrain']
            bounds=study['uv_cell_bounds']
            expected=_crop_limits(grid,study['crop_bbox_xy_mm'])
            if (not isinstance(bounds,list) or len(bounds)!=4 or any(type(v) is not int for v in bounds)
                    or bounds!=expected or type(study['TIN_subdivisions']) is not int
                    or study['TIN_subdivisions']!=n
                    or abs(_number(study['max_vertical_error_mm'])-eps)>1e-8
                    or study['reference_translation_mm']!=translation):
                raise ValueError('Annex field study crop/TIN/height differs: '+fid)
            checks[fid]=_cut_domain(grid,n,field,bounds)
            regions[fid]=list(bounds);crop_boxes[fid]=list(study['crop_bbox_xy_mm'])
        if not regions:raise ValueError('No free annex fields need a shared site Part')
        payload=json.dumps({'grid':{'shape':[grid.nu,grid.nv],'nodes_mm':grid.nodes},
                            'n':n,'boundary':boundary,'regions':regions},sort_keys=True,allow_nan=False)
        context=_generate(payload)
        combined={'vertices':[],'faces':[]};groups=[];shells=[]
        for group in context['groups']:
            gid='ANBAU_SITE_GROUP_'+group['id'].split('_')[-1]
            shell_ids=[]
            for component in geom.mesh_components(group['mesh']):
                sid='ANBAU_SITE_SHELL_%05d' % len(shells)
                shells.append({'id':sid,'group_id':gid,'exclude_for':list(group['exclude_for']),**_descriptor(component)})
                shell_ids.append(sid)
                offset=len(combined['vertices'])
                combined['vertices'].extend(deepcopy(component['vertices']))
                combined['faces'].extend([[i+offset for i in face] for face in component['faces']])
            groups.append({'id':gid,'exclude_for':list(group['exclude_for']),
                           'area_m2':group['area_m2'],'volume_m3':group['volume_m3'],
                           'body_count':len(shell_ids),'shell_ids':shell_ids})
        for index,a in enumerate(shells):
            if any(_matches(a,b) for b in shells[index+1:]):
                raise ValueError('Indistinguishable duplicate shared-ground shells')
        measured=geom.validate_mesh(combined)
        if measured['expected_body_count']!=len(shells):raise ValueError('Shared-ground shell indices were fused')
        refs={}
        for fid in regions:
            selected=[g for g in groups if fid not in g['exclude_for']]
            ids=[sid for g in selected for sid in g['shell_ids']]
            refs[fid]={'name':'ANBAU_SITE_'+fid.replace('-','_'),'shell_ids':ids,'body_count':len(ids),
                       'area_m2':sum(g['area_m2'] for g in selected),'volume_m3':sum(g['volume_m3'] for g in selected)}
        result={'schema':'ANBAU_SHARED_SITE_V1','file':PART_FILE,'units':'mm','construction_release':False,
                'representation':'DISPLAY_ONLY_PARALLEL_TIN_SOLIDS_NO_EARTHWORK_QUANTITIES',
                'coordinates':'HOUSE_EG_MM_HEIGHT_ALREADY_APPLIED','thickness_mm':THICKNESS_MM,
                'TIN_subdivisions':n,'max_vertical_error_mm':eps,'height_registration':registration,
                'source_hashes':deepcopy(terrain['source_hashes']),'field_regions':regions,
                'crop_bboxes_xy_mm':crop_boxes,'cut_domain_checks':checks,
                'area_m2':context['area_m2'],'volume_m3':measured['volume_mm3']/1e9,
                'body_count':len(shells),'groups':groups,'shells':shells,'reference_sets':refs,
                'boundary_xyz_mm':deepcopy(context['boundary_xyz_mm']),'mesh_sha256':_hash(combined),
                'input_sha256':_hash({'context_payload':payload,'cut_domain_checks':checks,'registration':registration}),
                'limitation':'Context excludes property intersection with each full UV crop. Existing local cut-soil helpers may extend beyond the map boundary; they remain display soil, not excavation quantities.'}
        if include_mesh:result['mesh']=combined
        return result
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError) as error:
        raise ValueError('Malformed annex shared-ground inputs: '+str(error)) from error


def write_site_step(path,site):
    """One AP214 containing all independent shells; no merging at shared vertices."""
    if ('mesh' not in site or _hash(site['mesh'])!=site['mesh_sha256']
            or site['schema']!='ANBAU_SHARED_SITE_V1' or site['construction_release'] is not False):
        raise ValueError('Full unchanged shared-ground transfer mesh required')
    report=write_step(Path(path),site['mesh'],'ANBAU_SITE')
    if report['expected_body_count']!=len(site['shells']):raise ValueError('Shared-ground AP214 shell count differs')
    return dict(report,site_input_sha256=site['input_sha256'],part_file=site['file'])


def match_native_shells(site,records):
    """Return shell ID→native tag only when each real body is uniquely identified.

    Records require tag (positive integer), bbox_mm (six ABS coordinates),
    volume_m3 and optionally centroid_mm (true mass centroid, not vertex mean).
    Missing centroids are accepted only if BBox+volume already identify bodies.
    """
    try:
        shells=site['shells']
        if len({s['id'] for s in shells})!=len(shells) or len(records)!=len(shells):
            raise ValueError('Missing/duplicate shared-ground shell inventory')
        actual=[];tags=set()
        for record in records:
            tag=record['tag'];box=_numbers(record['bbox_mm'],6);volume=_number(record['volume_m3'])
            if (type(tag) is not int or tag<=0 or tag in tags or volume<=0
                    or any(box[k]>=box[k+3] for k in range(3))):
                raise ValueError('Invalid/duplicate native shared-ground body')
            tags.add(tag)
            row={'tag':tag,'bbox_mm':box,'volume_m3':volume}
            if 'centroid_mm' in record:row['centroid_mm']=_numbers(record['centroid_mm'],3)
            actual.append(row)
        mapping={}
        for row in actual:
            candidates=[s for s in shells if _matches(s,row,centroid='centroid_mm' in row)]
            if len(candidates)!=1:
                raise ValueError('Native shared-ground shell missing or ambiguous: '+str(row['tag']))
            sid=candidates[0]['id']
            if sid in mapping:raise ValueError('Duplicate native body for shared-ground shell: '+sid)
            mapping[sid]=row['tag']
        if set(mapping)!={s['id'] for s in shells}:raise ValueError('Incomplete native shared-ground association')
        return mapping
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError) as error:
        raise ValueError('Malformed native shared-ground records: '+str(error)) from error


def _entry_hash(entry):
    return _hash({k:v for k,v in entry.items()
                  if k not in ('entry_sha256','step_path','entry_path','nx_root')})


def _mask_hash(site):
    return _hash({key:site[key] for key in ('field_regions','groups','shells','reference_sets')})


def validate_site_entry(entry):
    """Validate compact input before any native mutation, including exact refsets."""
    try:
        if ('mesh' in entry or entry['schema']!='ANBAU_SHARED_SITE_V1' or entry['file']!=PART_FILE
                or entry['units']!='mm' or entry['construction_release'] is not False
                or entry['thickness_mm']!=200 or entry['entry_sha256']!=_entry_hash(entry)
                or not re.fullmatch(r'[a-f0-9]{64}',entry['step_sha256'])
                or type(entry['step_bytes']) is not int or entry['step_bytes']<=0):
            raise ValueError('Invalid compact shared-ground entry/hash')
        shells={s['id']:s for s in entry['shells']}
        if len(shells)!=len(entry['shells']) or type(entry['body_count']) is not int or len(shells)!=entry['body_count']:
            raise ValueError('Invalid compact shared-ground shell inventory')
        for fid,ref in entry['reference_sets'].items():
            expected=[s['id'] for s in entry['shells'] if fid not in s['exclude_for']]
            ids=ref['shell_ids']
            if (ref['name']!='ANBAU_SITE_'+fid.replace('-','_') or len(ids)!=len(set(ids))
                    or set(ids)!=set(expected) or type(ref['body_count']) is not int or ref['body_count']!=len(ids)
                    or not _same_volume(_number(ref['volume_m3']),sum(shells[s]['volume_m3'] for s in ids))):
                raise ValueError('Invalid compact shared-ground reference set: '+fid)
        if set(entry['reference_sets'])!=set(entry['field_regions']):
            raise ValueError('Compact shared-ground field/refset inventory differs')
        return entry
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError) as error:
        raise ValueError('Malformed compact shared-ground entry: '+str(error)) from error


def prepare_site_inputs(site,scratch,*,nx_root=None):
    """Write exactly one STEP and its compact JSON once; re-use only exact matches.

    Returns the mesh-free site_entry consumed by build/inspect. A changed site
    requires a new scratch directory; existing inputs are never overwritten.
    nx_root may be supplied here, in the returned entry, or through UGII_BASE_DIR.
    """
    scratch=Path(scratch).resolve()
    step=scratch/'ANBAU_SITE.step';record=scratch/'ANBAU_SITE_ENTRY.json'
    if step.exists() or record.exists():
        if not (step.is_file() and record.is_file()):raise FileExistsError('Incomplete existing shared-ground inputs')
        entry=json.loads(record.read_text(encoding='utf-8'))
        validate_site_entry(entry)
        expected={k:v for k,v in site.items() if k!='mesh'}
        for key,value in expected.items():
            if entry.get(key)!=value:raise FileExistsError('Existing STEP belongs to a different shared-ground site')
        if hashlib.sha256(step.read_bytes()).hexdigest()!=entry['step_sha256']:
            raise ValueError('Existing shared-ground STEP bytes changed')
        if nx_root is not None:entry['nx_root']=str(Path(nx_root).resolve())
        return entry
    scratch.mkdir(parents=True,exist_ok=True)
    report=write_site_step(step,site)
    entry={k:deepcopy(v) for k,v in site.items() if k!='mesh'}
    entry.update(step_path=str(step),step_sha256=report['sha256'],step_bytes=report['bytes'],entry_path=str(record))
    if nx_root is not None:entry['nx_root']=str(Path(nx_root).resolve())
    entry['entry_sha256']=_entry_hash(entry)
    validate_site_entry(entry)
    with record.open('x',encoding='utf-8') as stream:
        json.dump(entry,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    return entry


def uf_mass_values(values):
    """UF_MODL units=4: volume m³, WCS center metres; return the latter in mm.

    Zero physical mass can make a mass centroid unavailable; unique BBox/volume
    matching remains allowed then. Mapping WCS mm to ABS is a native next step.
    """
    values=_numbers(values,47)
    if values[1]<=0 or values[2]<0:raise ValueError('Invalid native solid mass properties')
    result={'volume_m3':values[1]}
    if values[2]>0:result['centroid_wcs_mm']=[v*1000 for v in values[3:6]]
    return result


def _require_batch(session):
    if session.IsBatch is not True:raise ValueError('Shared-ground native operations require an owned batch NX session')


def _native_attributes(entry):
    return {'ANBAU_SITE_SCHEMA':entry['schema'],'ANBAU_SITE_ENTRY_SHA256':entry['entry_sha256'],
            'ANBAU_SITE_INPUT_SHA256':entry['input_sha256'],'ANBAU_SITE_MESH_SHA256':entry['mesh_sha256'],
            'ANBAU_SITE_MASK_SHA256':_mask_hash(entry),'ANBAU_SITE_SOURCES_SHA256':_hash(entry['source_hashes']),
            'ANBAU_SITE_SOURCE_HASHES':entry['source_hashes'],'ANBAU_SITE_CONSTRUCTION_RELEASE':False}


def _native_records(session,part):
    import NXOpen.UF
    from renovierung.m01.pile_native import _bbox
    session.Parts.SetWork(part)
    uf=NXOpen.UF.UFSession.GetUFSession()
    records=[]
    for body in part.Bodies:
        if not body.IsSolidBody or uf.Modeling.ValidateBody(1,[body.Tag])!=1:
            raise ValueError('Invalid shared-ground B-rep: '+body.Name)
        # Siemens uf_modl.h: units 4=kg/m; COFM[3:6] is in the displayed WCS.
        props=uf.Modeling.AskMassProps3d([body.Tag],1,1,4,1.,1,[.99]+[0.]*10)[0]
        values=uf_mass_values(list(props))
        record={'tag':body.Tag,'bbox_mm':_bbox([body]),'volume_m3':values['volume_m3']}
        if 'centroid_wcs_mm' in values:
            # uf_csys.h: 3=ROOT_WCS_COORDS, 1=ROOT_COORDS (displayed ABS).
            record['centroid_mm']=list(uf.Csys.MapPoint(3,values['centroid_wcs_mm'],1))
        records.append(record)
    return records


def validate_import_model_refset(body_names_by_tag,reference_sets,*,custom_names=()):
    """Accept only the observed STEP MODEL set with exact own B-rep membership.

    Native probes default_refsets_result.json/import_refsets_result.json showed
    an empty NewDisplay template, then MODEL containing the imported B-reps and
    their associated facets. MODEL is retained, never treated as an annex mask.
    """
    from renovierung.m01.nx_journal import validate_refset_members
    implicit={'Entire Part','Empty','ENTIRE PART','EMPTY'}
    if set(reference_sets)-implicit!={'MODEL'}|set(custom_names):
        raise ValueError('Unexpected STEP/reference-set inventory; exact MODEL and declared annex sets required')
    facets=validate_refset_members(body_names_by_tag,reference_sets['MODEL'])
    return {'name':'MODEL','body_names':sorted(body_names_by_tag.values()),'associated_facets':facets}


def _reference_set_records(part):
    import NXOpen
    import NXOpen.Facet
    result={}
    for ref in part.GetAllReferenceSets():
        if ref.Name in result:raise ValueError('Duplicate native shared-ground reference-set names')
        members=[]
        for member in ref.AskAllDirectMembers():
            row={'tag':member.Tag,'kind':'other'}
            if isinstance(member,NXOpen.Body):row['kind']='body'
            elif isinstance(member,NXOpen.Facet.FacetedBody):
                loaded=bool(member.IsAssociatedBodyLoaded)
                associated=member.AssociatedBody if loaded else None
                row.update(kind='facet',associated_loaded=loaded,associated_tag=associated.Tag if associated is not None else None)
            members.append(row)
        result[ref.Name]=members
    return result


def build_site_part(session,output_path,site_entry):
    """Create/save only a new ANBAU_SITE.prt; return (part, native_evidence).

    The caller's owned batch may already contain its new assembly. No existing
    Part is saved or closed. The imported STEP's native iterator order is unused.
    """
    _require_batch(session)
    validate_site_entry(site_entry)
    output=Path(output_path).resolve()
    if output.name!=PART_FILE or output.exists() or any(p.FullPath and Path(p.FullPath).resolve()==output for p in session.Parts):
        raise ValueError('Shared-ground output must be an explicit new ANBAU_SITE.prt target')
    step=Path(site_entry['step_path'])
    if (not step.is_file() or step.stat().st_size!=site_entry['step_bytes']
            or hashlib.sha256(step.read_bytes()).hexdigest()!=site_entry['step_sha256']):
        raise ValueError('Shared-ground transfer STEP missing or changed')
    root=site_entry.get('nx_root') or os.environ.get('UGII_BASE_DIR')
    if not root or not (Path(root)/'STEP214UG/step214ug.def').is_file():
        raise ValueError('Explicit NX installation root or UGII_BASE_DIR required for shared-ground import')
    import NXOpen
    import NXOpen.Layer
    from renovierung.k02.nx_build import import_mesh,save
    from renovierung.m01.nx_journal import display_part
    from renovierung.m01.display import write_attribute
    output.parent.mkdir(parents=True,exist_ok=True)
    part=session.Parts.NewDisplay(str(output),NXOpen.Part.Units.Millimeters)
    display_part(session,part)
    imported=import_mesh(session,part,str(step.resolve()),str(Path(root).resolve()))
    if len(imported)!=site_entry['body_count'] or len(list(part.Bodies))!=len(imported):
        raise ValueError('Shared-ground native import body count differs')
    records=_native_records(session,part)
    mapping=match_native_shells(site_entry,records)
    bytag={b.Tag:b for b in imported}
    for sid,tag in mapping.items():
        body=bytag[tag];body.SetName(sid);body.Layer,body.Color=210,95;body.Unblank()
    part.Layers.SetState(210,NXOpen.Layer.State.Selectable)
    validate_import_model_refset({body.Tag:body.Name for body in imported},_reference_set_records(part))
    for ref in site_entry['reference_sets'].values():
        native=part.CreateReferenceSet();native.SetName(ref['name'])
        if ref['shell_ids']:native.AddObjectsToReferenceSet([bytag[mapping[sid]] for sid in ref['shell_ids']])
    for key,value in _native_attributes(site_entry).items():write_attribute(part,key,value)
    save(part)
    evidence=inspect_site_part(session,part,site_entry)
    evidence['saved_new_part']=str(output)
    return part,evidence


def inspect_site_part(session,part,site_entry):
    """Read exact shared-ground identity/geometry/refsets; never save a Part.

    Display/work switch is temporary so native mass-centroid WCS→ABS conversion
    cannot accidentally use the containing assembly's coordinate system.
    """
    _require_batch(session)
    validate_site_entry(site_entry)
    import NXOpen
    import NXOpen.Facet
    import NXOpen.Layer
    from renovierung.m01.display import read_attribute
    from renovierung.m01.nx_journal import display_part,validate_refset_members
    if (part is None or not part.FullPath or not part.IsFullyLoaded
            or part.PartUnits!=NXOpen.BasePart.Units.Millimeters):
        raise ValueError('Shared-ground Part must be fully loaded in mm')
    path=Path(part.FullPath).resolve()
    if path.name!=PART_FILE or not path.is_file():raise ValueError('Unexpected shared-ground Part path')
    before=hashlib.sha256(path.read_bytes()).hexdigest()
    previous_display,previous_work=session.Parts.Display,session.Parts.Work
    try:
        display_part(session,part)
        attributes={key:read_attribute(part,key) for key in _native_attributes(site_entry)}
        for key,expected in _native_attributes(site_entry).items():
            if attributes[key]!=expected:raise ValueError('Shared-ground native attribute differs: '+key)
        root=part.ComponentAssembly.RootComponent
        if ((root is not None and list(root.GetChildren())) or list(part.GetInterpartParents())
                or list(part.Expressions.GetInterpartReferences())):
            raise ValueError('Shared-ground Part contains components or external dependencies')
        layer=part.Layers.GetState(210)
        if layer not in (NXOpen.Layer.State.WorkLayer,NXOpen.Layer.State.Selectable):
            raise ValueError('Shared-ground layer 210 is not visible/selectable')
        bodies=list(part.Bodies)
        if any(body.Layer!=210 or body.IsBlanked for body in bodies):
            raise ValueError('Hidden/wrong-layer shared-ground body')
        records=_native_records(session,part)
        mapping=match_native_shells(site_entry,records)
        bytag={b.Tag:b for b in bodies};measured={r['tag']:r for r in records}
        for sid,tag in mapping.items():
            if bytag[tag].Name!=sid:raise ValueError('Shared-ground body name differs: '+sid)
        refsets={ref.Name:ref for ref in part.GetAllReferenceSets()}
        names={r['name'] for r in site_entry['reference_sets'].values()}
        native_refsets=_reference_set_records(part)
        import_model=validate_import_model_refset({body.Tag:body.Name for body in bodies},native_refsets,custom_names=names)
        evidence={}
        for fid,wanted in site_entry['reference_sets'].items():
            expected={mapping[sid]:sid for sid in wanted['shell_ids']}
            members=native_refsets[wanted['name']]
            facets=validate_refset_members(expected,members) if expected else []
            if not expected and members:raise ValueError('Expected empty shared-ground refset contains objects')
            volume=sum(measured[tag]['volume_m3'] for tag in expected)
            if not _same_volume(volume,wanted['volume_m3']):raise ValueError('Shared-ground refset volume differs: '+fid)
            evidence[fid]={'name':wanted['name'],'shell_ids':list(wanted['shell_ids']),
                           'body_count':len(expected),'volume_m3':volume,'associated_facets':facets}
        return {'status':'PASS','file':path.name,'entry_sha256':site_entry['entry_sha256'],
                'source_mask_attributes':attributes,'body_count':len(bodies),
                'shell_measurements':{sid:measured[tag] for sid,tag in mapping.items()},
                'reference_sets':evidence,'import_model_refset':import_model,'layer_210_visible_selectable':True,
                'no_external_dependencies':True,'saved_by_inspector':False,'construction_release':False}
    finally:
        if previous_display is not None and session.Parts.Display.Tag!=previous_display.Tag:
            display_part(session,previous_display)
        if previous_work is not None and session.Parts.Work.Tag!=previous_work.Tag:session.Parts.SetWork(previous_work)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=before:
            raise ValueError('Shared-ground inspection changed native Part bytes')
