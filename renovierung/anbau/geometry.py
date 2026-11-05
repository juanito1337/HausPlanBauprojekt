"""Additive annex display studies from unchanged K02 geometry and source TIN.

Assumed slab underside and formation are display parameters, never verified
as-built slab/foundation levels or a construction release. Original G02/K02/M01
sources and native deliveries are read only.
"""
from __future__ import annotations
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

from renovierung.k02 import geometry as geom
from renovierung.k02.planning import DEFAULT_SOURCES, _corridors, field_register
from renovierung.k02.terrain import Grid, read_json
from tools.check_m01_clearances import clearance
from tools.repo_support import member_path

ASSUMPTIONS_PATH='renovierung/anbau/assumptions.json'
SECTORS=('PS10','PS11','PS12','PS13')


def _number(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError('Finite numeric annex display assumption required')
    return value


def read_assumptions(root,overrides=None):
    result=read_json(Path(root)/ASSUMPTIONS_PATH)
    if overrides is not None:
        if not isinstance(overrides,dict):raise ValueError('Annex assumption overrides must be a dictionary')
        if set(overrides)-set(result)-{'source_paths'}:raise ValueError('Unknown annex display assumption')
        result.update(deepcopy(overrides))
    if result['schema']!='ANBAU_DISPLAY_ASSUMPTIONS_V1' or result['construction_release'] is not False:
        raise ValueError('Annex display assumptions cannot grant construction release')
    for key in ('assumed_slab_underside_z_mm','target_below_assumed_slab_mm','working_width_mm',
                'max_bottom_length_mm','excavation_slope_ratio','terrain_tolerance_mm',
                'utility_corridor_half_width_mm','pile_patch_radius_mm','minimum_pile_excavation_clearance_mm',
                'loose_factor','reserve_factor'):_number(result[key])
    if (result['target_below_assumed_slab_mm']!=100 or result['working_width_mm']!=800 or
            result['max_bottom_length_mm']!=2000 or result['excavation_slope_ratio']!=1 or
            result['loose_factor']!=1.05 or result['reserve_factor']!=1.25 or
            min(result['terrain_tolerance_mm'],result['utility_corridor_half_width_mm'],
                result['pile_patch_radius_mm'],result['minimum_pile_excavation_clearance_mm'])<=0):
        raise ValueError('Annex study must retain the explicit 800/2000/1:1 and material study basis')
    center=result['pile_center_xy_mm']
    if not isinstance(center,list) or len(center)!=2:raise ValueError('Explicit XY pile center required')
    for x in center:_number(x)
    result['formation_z_mm']=result['assumed_slab_underside_z_mm']-result['target_below_assumed_slab_mm']
    return result


def _merge(meshes):
    result={'vertices':[],'faces':[]}
    for mesh in meshes:
        offset=len(result['vertices']);result['vertices'].extend(mesh['vertices'])
        result['faces'].extend([[i+offset for i in face] for face in mesh['faces']])
    geom.validate_mesh(result)
    return result


def soil_meshes(triangles,field,bottom_z):
    """Exact full/cut soil as adjacent nonoverlapping closed r<=0/r>=0 solids.

    The artificial split preserves the discontinuous vertical excavation wall
    at r=0. Joining these solids is unnecessary; their shared interface has zero
    volume. It avoids misusing surface_mesh for discontinuous top surfaces.
    """
    _number(bottom_z)
    a,t,n=field['origin_mm'],field['tangent'],field['normal']
    formation=field['formation_z_mm'];length=field['length_mm'];width=field['width_mm']
    if bottom_z>=min(formation,min(p[2] for tri in triangles for p in tri)):
        raise ValueError('Artificial annex soil bottom intersects study surfaces')
    local=[[[sum((p[k]-a[k])*t[k] for k in (0,1)),
             sum((p[k]-a[k])*n[k] for k in (0,1)),p[2]] for p in tri] for tri in triangles]
    roofs=[(0,0,formation),(0,1,formation-width),(-1,0,formation),(1,0,formation-length)]
    source=[[],[]];cut=[[],[]];low=(0,0,bottom_z)
    for tri in local:
        terrain=geom.plane(tri);xy=geom.clean([p[:2] for p in tri])
        inside=geom.clip_polygon(xy,(0,-1,0))
        outside=geom.clip_polygon(xy,(0,1,0))
        if inside:
            source[0].append((inside,low,terrain));cut[0].append((inside,low,terrain))
        if not outside:continue
        source[1].append((outside,low,terrain))
        for index,roof in enumerate(roofs):
            polygon=list(outside)
            for other_index,other in enumerate(roofs):
                if index!=other_index:polygon=geom.clip_polygon(polygon,geom.subtract(roof,other))
            if not polygon:continue
            difference=geom.subtract(terrain,roof)
            if max(abs(geom.value(difference,p)) for p in polygon)<1e-9:
                cut[1].append((polygon,low,terrain));continue
            removed=geom.clip_polygon(polygon,difference)
            untouched=geom.clip_polygon(polygon,geom.subtract(roof,terrain))
            if removed:cut[1].append((removed,low,roof))
            if untouched:cut[1].append((untouched,low,terrain))
    def world(sets):
        meshes=[geom.surface_mesh(parts) for parts in sets if parts]
        for mesh in meshes:
            for p in mesh['vertices']:
                s,r=p[:2];p[0]=a[0]+s*t[0]+r*n[0];p[1]=a[1]+s*t[1]+r*n[1]
            if t[0]*n[1]-t[1]*n[0]<0:
                for face in mesh['faces']:face.reverse()
        return _merge(meshes)
    return {'soil':world(source),'cut_soil':world(cut)}


def _paths(assumptions):
    paths={**DEFAULT_SOURCES,'vegetation_job':'projects/g02/umgebung/data/IMPORTAUFTRAG_R09.json',
           'vegetation_review':'projects/g02/umgebung/abgleich/VEGETATION_VIDEO_R11.json'}
    overrides=assumptions.get('source_paths',{})
    if set(overrides)-set(paths):raise ValueError('Unknown annex source role')
    paths.update(overrides)
    return paths


def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _inventory(root,assumptions):
    paths=_paths(assumptions)
    files=set(paths.values())|{ASSUMPTIONS_PATH,'renovierung/anbau/geometry.py',
        'renovierung/k02/geometry.py','renovierung/k02/terrain.py','renovierung/k02/planning.py',
        'tools/check_m01_clearances.py','tools/repo_support.py'}
    job=read_json(member_path(root,paths['vegetation_job']))
    base=Path(paths['vegetation_job']).parent.parent
    for row in job['parts']:
        if row['id'] in ('V01','V02','V03','V05'):files.add((base/row['step_file']).as_posix())
    return {path:_sha(member_path(root,path)) for path in sorted(files)}


def _terrain(grid_data,height,house):
    source=Grid(grid_data)
    if height['mode']=='ABSOLUTE_EG_HOEHE':
        if height.get('common_vertical_datum_confirmed') is not True:raise ValueError('Absolute datum unconfirmed')
        delta=-1000*_number(height['absolute_eg_source_m'])
    elif height['mode'] in ('PLAN_ANNAHME','AUFMASSPUNKT'):
        delta=_number(height['ground_z_relative_eg_mm'])-source.sample(height['anchor_xy_mm'])
    else:raise ValueError('Unknown height registration')
    grid=Grid(grid_data,delta)
    boundary=house['site']['boundary']
    if boundary['closed'] is not True or boundary.get('holes'):raise ValueError('One closed parcel polygon required')
    points=boundary['points_local_mm']
    for point in points:
        if len(point)!=2:raise ValueError('Invalid parcel XY coordinate')
        for x in point:_number(x)
    geom.triangulate_polygon(points)
    for point in points:
        u,v=grid.uv(point)
        if not (0<=u<=grid.nu-1 and 0<=v<=grid.nv-1):raise ValueError('Parcel outside source DGM')
    return grid,deepcopy(points),{'translation_mm':[0,0,delta],'mode':height['mode'],'applied_once_to_source_grid':True}


def load_terrain(root,assumptions=None):
    """Warm helper for a separate site generator; Z registration is already applied."""
    root=Path(root).resolve();config=read_assumptions(root,assumptions);paths=_paths(config)
    data={name:read_json(member_path(root,paths[name])) for name in ('grid','height','house')}
    grid,boundary,registration=_terrain(data['grid'],data['height'],data['house'])
    n=grid.subdivisions(config['terrain_tolerance_mm'])
    if n>16:raise ValueError('K02 TIN refinement budget exceeded')
    return {'grid':grid,'TIN_subdivisions':n,'max_vertical_error_mm':grid.error_bound(n),
            'boundary_xy_mm':boundary,'height_registration':registration,
            'source_hashes':{paths[name]:_sha(member_path(root,paths[name])) for name in data}}


def _vegetation(root,paths,data,hashes):
    selected={row['id'] for row in data['vegetation_review']['groups'] if row['include']}
    if selected!={'V01','V02','V03','V05'}:raise ValueError('Active G02 vegetation scope differs')
    result={};base=Path(paths['vegetation_job']).parent.parent
    for row in data['vegetation_job']['parts']:
        if row['id'] not in selected:continue
        relative=(base/row['step_file']).as_posix()
        if hashes[relative]!=row['sha256'] or row['geometry_reference']['source_sha256']!=row['sha256']:
            raise ValueError('Vegetation STEP provenance differs: '+relative)
        patches=[]
        for sheet in row['geometry_reference']['sheets']:
            nr,nc=sheet['grid_shape'];nodes=sheet['samples_mm'][:nr*nc]
            if min(nr,nc)<2 or len(nodes)!=nr*nc:raise ValueError('Invalid vegetation sheet grid')
            corners=[nodes[0][:2],nodes[nc-1][:2],nodes[-1][:2],nodes[-nc][:2]]
            for r in range(nr):
                for c in range(nc):
                    expected=[corners[0][k]+r/(nr-1)*(corners[3][k]-corners[0][k])+c/(nc-1)*(corners[1][k]-corners[0][k]) for k in (0,1)]
                    if math.dist(expected,nodes[r*nc+c][:2])>1e-5:raise ValueError('Nonaffine vegetation projection')
            patches.append(geom.clean(corners))
        if len(patches)!=row['expected_sheets']:raise ValueError('Vegetation sheet count differs')
        result[row['id']]=patches
    if set(result)!=selected:raise ValueError('Missing modeled vegetation group')
    return result


def _record(mesh):
    measure=geom.validate_mesh(mesh);xyz=mesh['vertices']
    return {'mesh':mesh,'body_count':measure['expected_body_count'],
            'volume_m3':measure['volume_mm3']/1e9,
            'component_volumes_m3':sorted(v/1e9 for v in measure['component_volumes_mm3']),
            'bbox_mm':[min(p[k] for p in xyz) for k in range(3)]+[max(p[k] for p in xyz) for k in range(3)]}


def _limits(grid,box):
    x0,y0,x1,y1=box
    uv=[grid.uv(p) for p in ((x0,y0),(x0,y1),(x1,y0),(x1,y1))]
    return [max(0,math.floor(min(p[0] for p in uv))),min(grid.nu-1,math.ceil(max(p[0] for p in uv))),
            max(0,math.floor(min(p[1] for p in uv))),min(grid.nv-1,math.ceil(max(p[1] for p in uv)))]


def _validate_contour(catalog,house):
    part=next(p for p in house['parts'] if p['id']=='ANBAU_KG')
    walls={w['id']:w for w in part['walls']}
    contour=catalog['footprints']['ANBAU_KG']
    if contour!=[w['a'] for w in part['walls'] if w['category']=='AUSSENWAND']:
        raise ValueError('Annex outer test contour differs from G02 outer walls')
    for sector in catalog['sectors']:
        if sector['id'] not in SECTORS:continue
        for segment in sector['segments']:
            wall=walls[segment['source_wall']]
            if segment['a']!=wall['a'] or segment['b']!=wall['b']:
                raise ValueError('Registered annex station geometry differs from G02')


def _access(field,house):
    eg=next(p for p in house['parts'] if p['id']=='ANBAU_EG')
    wall=next(w for w in eg['walls'] if w['id']==field['source_wall'].replace('AN_KG_','AN_EG_'))
    start,end=field['station_interval_mm'];result=[]
    for opening in wall.get('openings',[]):
        if opening.get('kind')!='TUER':continue
        lo,hi=opening['offset'],opening['offset']+opening['width']
        overlap=max(0,min(end,hi)-max(start,lo))
        if overlap>1e-6:
            result.append({'id':opening['id'],'overlap_station_mm':overlap,
                           'opening_station_interval_mm':[lo,hi],
                           'basis':'MODELED_ESTIMATED_DOOR_NO_REPLACEMENT_ACCESS_PROVEN'})
    return result


def _conflicts(projection,hull,boundary,footprints,corridors,vegetation):
    result=[];upper=[hull]
    outside=geom.outside_area(projection,boundary);outside_upper=geom.outside_area(upper,boundary)
    if max(outside,outside_upper)>1e-3:
        result.append({'kind':'PROPERTY_BOUNDARY','nominal_outside_m2':outside/1e6,'upper_error_outside_m2':outside_upper/1e6})
    for name,polygon in footprints.items():
        nominal=geom.overlap_area(projection,[polygon]);uncertain=geom.overlap_area(upper,[polygon])
        if max(nominal,uncertain)>1e-3:
            result.append({'kind':'BUILDING_PROJECTION','object':name,'nominal_overlap_m2':nominal/1e6,
                           'upper_error_overlap_m2':uncertain/1e6,'solid_intersection_volume_m3':None})
    for name,polygon in corridors.items():
        ar=geom.overlap_area(upper,[polygon],convex_b=True)
        if ar>1e-3:result.append({'kind':'UTILITY_CORRIDOR','object':name,'upper_error_overlap_m2':ar/1e6})
    for name,patches in vegetation.items():
        ar=geom.overlap_area(upper,patches,convex_b=True)
        if ar>1e-3:result.append({'kind':'VEGETATION_PROJECTION','object':name,'upper_error_overlap_m2':ar/1e6})
    return result


def _pile_pair(triangles,center,bank_mm3,eps,boundary,obstacles,excavation_hull,minimum):
    geometry={};display={};checks={}
    for role,factor in (('pile_main',1.05),('pile_reserve',1.25)):
        target=bank_mm3*factor
        pile=geom.stockpile(triangles,center,target,error_mm=eps)
        record=_record(pile['mesh']);cx,cy=center;h=pile['apex_z_mm']+eps;k=.5
        roofs=[(k,0,h-k*cx),(-k,0,h+k*cx),(0,k,h-k*cy),(0,-k,h+k*cy)]
        support=[p for p,_,_ in geom.partitions(triangles,roofs,lower=False,shift=-eps)]
        if geom._domain_contact(triangles,support):raise ValueError('Pile upper-error support reaches study DGM edge')
        hull=geom.convex_hull([p for polygon in support for p in polygon])
        groups={**obstacles,'excavation':[excavation_hull]}
        distances={name:clearance([hull],polygons)['distance_mm'] for name,polygons in groups.items() if polygons}
        distances['parcel_boundary']=clearance([hull],[boundary],filled=False)['distance_mm']
        outside=geom.outside_area(support,boundary)/1e6
        overlaps={name:sum(geom.overlap_area(support,[poly])/1e6 for poly in polygons) for name,polygons in groups.items() if polygons}
        passed=(distances['excavation']>=minimum and min(distances.values())>0 and outside<1e-8 and max(overlaps.values(),default=0)<1e-8)
        entry={k:deepcopy(v) for k,v in record.items() if k!='mesh'}
        entry.update(center_xy_mm=list(center),target_volume_m3=target/1e9,apex_z_mm=pile['apex_z_mm'],
                     contact_area_m2=sum(geom.area(p) for p in pile['projection_polygons'])/1e6,
                     contact_polygons_xy_mm=pile['projection_polygons'],uncertainty_contact_hull_xy_mm=hull,
                     volume_interval_m3=[v/1e9 for v in pile['volume_interval_mm3']],
                     clearances_mm=distances,overlap_area_sum_m2=overlaps,parcel_outside_m2=outside,
                     geometric_criterion_passed=passed,construction_release=False,native_verified=False)
        geometry[role]=record;display[role]=entry;checks[role]=passed
    return geometry,display,all(checks.values())


@lru_cache(maxsize=1)
def _compute(root_text,config_text,hash_items):
    root=Path(root_text);config=json.loads(config_text);paths=_paths(config);hashes=dict(hash_items)
    data={name:read_json(member_path(root,path)) for name,path in paths.items()}
    if any(_sha(member_path(root,path))!=expected for path,expected in hashes.items()):
        raise ValueError('Annex input/generator changed before calculation')
    catalog,house,scope=data['catalog'],data['house'],data['scope']
    _validate_contour(catalog,house)
    grid,boundary,registration=_terrain(data['grid'],data['height'],house)
    n=grid.subdivisions(config['terrain_tolerance_mm']);eps=grid.error_bound(n)
    if n>16:raise ValueError('K02 TIN refinement budget exceeded')
    vegetation=_vegetation(root,paths,data,hashes)
    corridors=_corridors(house['site'].get('routes',[]),config['utility_corridor_half_width_mm'])
    footprints=deepcopy(catalog['footprints'])
    obstacles={'building':list(footprints.values()),'utility_corridor':list(corridors.values()),
               'vegetation':[p for patches in vegetation.values() for p in patches]}
    formation=config['formation_z_mm'];center=config['pile_center_xy_mm'];radius=config['pile_patch_radius_mm']
    pile_ground=grid.triangles(n,(center[0]-radius,center[1]-radius,center[0]+radius,center[1]+radius))
    fields=[f for f in field_register(catalog,scope,2000,800,formation) if f['sector_id'] in SECTORS]
    global_depth=max(0,max(p[2] for p in grid.nodes)-formation+eps)
    for index,field in enumerate(fields):
        fid=field['id'];field['formation_z_mm']=formation
        field['assumed_slab_underside_z_mm']=config['assumed_slab_underside_z_mm']
        field['blockers']=[b for b in field['blockers'] if b!='UNKNOWN_FORMATION']
        field.update(native_candidate=False,diagnostic_only=True,construction_release=False,native_verified=False,
                     measurements={},display_stockpile={},geometry={},volume_m3=None)
        a,t,normal,L=field['origin_mm'],field['tangent'],field['normal'],field['length_mm']
        corners=[[a[k]+s*t[k]+r*normal[k] for k in (0,1)]
                 for s in (-global_depth,L+global_depth) for r in (0,800+global_depth)]
        crop=geom.bbox([corners]);triangles=grid.triangles(n,crop)
        result=geom.excavation(triangles,L,800,formation,1,a,t,normal,eps)
        if not result['mesh']['faces']:raise ValueError('No modeled annex excavation at '+fid)
        hull=result['uncertainty_coverage_hull']
        if grid.contact_on_boundary([hull]):field['blockers'].append('DGM_DOMAIN_INCOMPLETE')
        bottom=min(formation-1000,min(p[2] for tri in triangles for p in tri)-1000)
        soil=soil_meshes(triangles,field,bottom)
        field['geometry']={role:_record(mesh) for role,mesh in soil.items()}
        field['geometry']['excavation']=_record(result['mesh'])
        bank=field['geometry']['excavation']['volume_m3']
        residual=field['geometry']['soil']['volume_m3']-field['geometry']['cut_soil']['volume_m3']
        if abs(residual-bank)>max(1e-7,bank*1e-8):raise ValueError('Annex cut-soil/excavation volume balance differs: '+fid)
        field['diagnostic_volume_m3']=bank
        field['excavation_footprint_xy_mm']=result['projection_polygons']
        field['uncertainty_coverage_hull_xy_mm']=hull
        field['volume_interval_m3']=[v/1e9 for v in result['volume_interval_mm3']]
        field['study_terrain']={'crop_bbox_xy_mm':list(crop),'uv_cell_bounds':_limits(grid,crop),
                                'TIN_subdivisions':n,'max_vertical_error_mm':eps,
                                'reference_translation_mm':registration['translation_mm'],
                                'artificial_bottom_z_mm':bottom,'source_is_bilinear':True,
                                'cutout_applied':True,'representation':'TWO_ADJACENT_CLOSED_SOIL_HALVES_NO_VOLUME_OVERLAP'}
        field['conflicts']=_conflicts(result['projection_polygons'],hull,boundary,footprints,corridors,vegetation)
        field['access_conflicts']=_access(field,house)
        if field['access_conflicts']:field['blockers'].append('ACCESS_PROTECTION_UNRESOLVED')
        kinds={c['kind'] for c in field['conflicts']}
        if 'BUILDING_PROJECTION' in kinds:status='RED_BUILDING_PROJECTION_CONFLICT_STUDY'
        elif 'PROPERTY_BOUNDARY' in kinds:status='RED_PROPERTY_CONFLICT_STUDY'
        elif field['blockers']:status='BLOCKED_INTERFACE_OR_ACCESS_STUDY'
        elif field['conflicts']:status='BLOCKED_REGISTERED_OBSTACLE_STUDY'
        else:
            pile_geometry,pile_display,passed=_pile_pair(pile_ground,center,result['volume_mm3'],eps,boundary,
                obstacles,hull,config['minimum_pile_excavation_clearance_mm'])
            if passed:
                field['geometry'].update(pile_geometry);field['display_stockpile']=pile_display
                field['native_candidate']=True;field['diagnostic_only']=False;field['volume_m3']=bank
                field['measurements']={role:{k:deepcopy(field['geometry'][role][k]) for k in
                    ('body_count','component_volumes_m3','volume_m3')} for role in ('excavation','cut_soil','pile_main','pile_reserve')}
                status='GEOMETRICALLY_CLEAR_DISPLAY_STUDY_UNRELEASED'
            else:
                field['blockers'].append('PILE_SITE_GEOMETRIC_CRITERIA_FAILED')
                field['pile_site_checks']=pile_display;status='BLOCKED_PILE_SITE_STUDY'
        field['status']=status
        field['quantity_status']='HYPOTHETICAL_SINGLE_FIELD_DISPLAY_VOLUME_NO_RELEASE' if field['native_candidate'] else 'NO_EFFECTIVE_QUANTITY_DIAGNOSTIC_ONLY'
        field['warnings']=['ASSUMED_SLAB_NOT_SURVEYED_FOUNDATION','ANBAU_FFB_PROXY_MINUS_1860_REMAINS_UNCHANGED',
                           'INDEPENDENT_SINGLE_FIELD_NOT_SIMULTANEOUS','FOUNDATIONS_STABILITY_WATER_ACCESS_LOADS_UTILITIES_UNVERIFIED']
        field['release_requirements']=deepcopy(next(s for s in catalog['sectors'] if s['id']==field['sector_id'])['release_requirements'])
        ends=[[a[k]+s*t[k]+100*normal[k] for k in (0,1)] for s in (0,L)]
        label=[a[k]+L/2*t[k]+(700+index%3*600)*normal[k] for k in (0,1)]
        field['display_marker']={'line':[[*p,grid.sample(p)+100] for p in ends],
                                 'label':[*label,grid.sample(label)+150],
                                 'basis':'SOURCE_REGISTER_STATIONS_HEIGHT_ALREADY_APPLIED'}
        field['slope_study']={'ratio':1,'both_end_slopes':True,'working_width_mm':800,'max_bottom_length_mm':2000}
        field['note']=(fid+'; DARSTELLUNGSANNAHME UK %.0f / Sohle %.0f mm; '%(config['assumed_slab_underside_z_mm'],formation)+
                       ('hypothetische Einzelstudie %.3f m3; '%bank if field['native_candidate'] else 'ROTE/GESPERRTE KONFLIKTSTUDIE, KEINE EFFEKTIVE MENGE; ')+
                       'FFB-Proxy -1860 unveraendert; keine Bau-/Grabfreigabe')
    if len(fields)!=24:raise ValueError('Existing annex register must contain 24 fields')
    if any(_sha(member_path(root,path))!=expected for path,expected in hashes.items()):
        raise ValueError('Annex input/generator changed during calculation')
    return {'schema':'ANBAU_DISPLAY_PLAN_V1','units':'mm','construction_release':False,'native_verified':False,
            'assumptions':config,'height_registration':registration,'boundary_xy_mm':boundary,
            'terrain':{'source':'BILINEAR_DGM_UNCHANGED_K02_TIN','shape':[grid.nu,grid.nv],
                       'TIN_subdivisions':n,'max_vertical_error_mm':eps},
            'annex_outer_test_contour_xy_mm':deepcopy(catalog['footprints']['ANBAU_KG']),
            'fields':fields,'native_candidate_ids':[f['id'] for f in fields if f['native_candidate']],
            'diagnostic_only_ids':[f['id'] for f in fields if f['diagnostic_only']],
            'provenance':{'source_and_generator_hashes':hashes,'coordinate_reference':'EG_MM_HEIGHT_APPLIED_ONCE',
                          'no_original_generator_or_geometry_modified':True},
            'limitations':['DISPLAY_ASSUMPTION_NOT_AS_BUILT_SLAB_OR_FOUNDATION',
                'EXISTING_ANNEX_FFB_PROXY_MINUS_1860_CONTRADICTS_HIGHER_ASSUMED_SLAB_UNDERSIDE',
                'PS10_UNKNOWN_INTERFACE_MASK_NOT_INVENTED','BUILDING_INTERSECTIONS_ARE_XY_PROJECTION_CONFLICTS_NOT_SOLID_BOOLEAN_QUANTITIES',
                'PARCEL_MAP_REFERENCE_NOT_SURVEY','UTILITY_CORRIDORS_ASSUMED_DEPTHS_UNKNOWN',
                'REGISTERED_VEGETATION_PROJECTIONS_NOT_CURRENT_TREE_ROOT_SURVEY',
                'ARTIFICIAL_SOIL_BOTTOM_NOT_EARTHWORK_QUANTITY','NO_CUMULATIVE_SEQUENCE_OR_NET_TOTAL',
                'NO_NX_EXECUTION_NO_CONSTRUCTION_RELEASE']}


def create_plan(root,assumptions=None,include_mesh=True):
    """Return every registered annex field, with optional true closed role meshes.

    Failed geometric/scope/access/logistic gates retain complete diagnostic
    geometry, null effective quantity and no pile. A bounded input-derived cache
    supports repeated native-preparation calls without inflating layout records.
    """
    root=Path(root).resolve();config=read_assumptions(root,assumptions)
    hashes=_inventory(root,config)
    cached=_compute(str(root),json.dumps(config,sort_keys=True,allow_nan=False),tuple(hashes.items()))
    result={k:deepcopy(v) for k,v in cached.items() if k!='fields'}
    result['fields']=[]
    for field in cached['fields']:
        row={k:deepcopy(v) for k,v in field.items() if k!='geometry'}
        row['geometry']={role:{k:deepcopy(v) for k,v in record.items() if include_mesh or k!='mesh'}
                         for role,record in field['geometry'].items()}
        result['fields'].append(row)
    return result


def compact_catalog(plan):
    """Small versioned register; full meshes/contact polygons stay in local PLAN."""
    keys=('id','sector_id','source_wall','origin_mm','tangent','normal','station_interval_mm',
          'length_mm','width_mm','assumed_slab_underside_z_mm','formation_z_mm','status','native_candidate',
          'diagnostic_only','volume_m3','diagnostic_volume_m3','blockers','conflicts','access_conflicts','measurements','note')
    return {'schema':'ANBAU_DISPLAY_CATALOG_V1','units':'mm','construction_release':False,
            'assumptions':deepcopy(plan['assumptions']),'height_registration':deepcopy(plan['height_registration']),
            'terrain':deepcopy(plan['terrain']),'native_candidate_ids':list(plan['native_candidate_ids']),
            'diagnostic_only_ids':list(plan['diagnostic_only_ids']),'provenance':deepcopy(plan['provenance']),
            'limitations':list(plan['limitations']),
            'fields':[{key:deepcopy(f[key]) for key in keys} for f in plan['fields']]}


def write_outputs(root,plan):
    root=Path(root).resolve();target=root/'reports/local/anbau/PLAN.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(plan,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8')
    catalog=root/'renovierung/anbau/KATALOG.json'
    catalog.write_text(json.dumps(compact_catalog(plan),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return {'plan':str(target),'plan_sha256':_sha(target),'catalog':str(catalog),'catalog_sha256':_sha(catalog)}
