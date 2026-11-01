"""Conservative study register. Independent states are not a cumulative sequence."""
import hashlib
import math
from pathlib import Path
from . import geometry as geom
from .geometry import finite, overlap_area
from .materials import balance
from .terrain import Grid, closed_terrain, read_json

DEFAULT_SOURCES={
    'catalog':'renovierung/planung/2026-11-01/sektionen.json',
    'scope':'renovierung/planung/2026-11-01/UMFANG_E01.json',
    'grid':'projects/g02/data/DGM_STUETZPUNKTE_G02.json',
    'height':'projects/g02/data/HOEHENANSCHLUSS_G02.json',
    'house':'projects/g02/haus/data/haus.json'}


def field_register(catalog,scope,max_length,width,formation):
    finite(max_length,width,formation)
    if min(max_length,width)<=0:raise ValueError('Invalid provisional field dimensions')
    exclusions={r['sector']:r for r in scope['provisional_exclusions']}
    rows=[]
    for sector in catalog['sectors']:
        sid=sector['id'];count=0;annex=sid in ('PS10','PS11','PS12','PS13')
        for segment in sector['segments']:
            a,b=segment['a'],segment['b'];length=math.dist(a,b)
            t=[(b[k]-a[k])/length for k in range(2)];n=segment['outside_normal']
            pieces=math.ceil(length/max_length)
            for piece in range(pieces):
                count+=1;start=piece*length/pieces;end=(piece+1)*length/pieces
                blockers=[];exclusion=exclusions.get(sid)
                if exclusion and exclusion['boundary'] is None:blockers.append('MASK_BOUNDARY_UNKNOWN')
                if sid in scope['scope_needs_survey']:blockers.append('INTERFACE_UNRESOLVED')
                if annex:blockers.append('UNKNOWN_FORMATION')
                rows.append({'id':sid+'-F%02d'%count,'sector_id':sid,'label':sector['label'],
                             'source_wall':segment['source_wall'],'origin_mm':[a[k]+start*t[k] for k in range(2)],
                             'tangent':t,'normal':n,'station_interval_mm':[start,end],
                             'length_mm':end-start,'width_mm':width,'formation_z_mm':None if annex else formation,
                             'blockers':blockers,'status':'BLOCKED' if blockers else 'UNASSESSED',
                             'whole_sector_excluded':False,'provisional_exclusion':exclusion,
                             'volume_m3':None,'mesh':None,'construction_release':False,
                             'unreachable_remainder':False,'state_basis':'INDEPENDENT_SINGLE_FIELD_VARIANT'})
    return rows


def independent_states(fields):
    overlaps=[]
    for i,a in enumerate(fields):
        for b in fields[i+1:]:
            area=overlap_area(a.get('projection_polygons',[]),b.get('projection_polygons',[]),convex_b=True)
            if area>1e-4:overlaps.append({'fields':[a['id'],b['id']],'projection_overlap_m2':area/1e6,
                                        'shared_excavation_m3':None,'volume_union_computed':False})
    return {'cumulative_sequence_available':False,'net_first_excavation_m3':None,
            'reexcavated_compacted_m3':None,'overlaps':overlaps,
            'limitation':'INDEPENDENT_SINGLE_FIELD_VARIANTS_NO_CUMULATIVE_UNION_OR_NET_TOTAL',
            'open_fields_per_state':1}


def geometry_conflicts(projection,boundary,obstacles):
    conflicts=[]
    if geom.outside_area(projection,boundary)>1e-3:conflicts.append('PROPERTY_BOUNDARY')
    for name,poly in obstacles.items():
        if overlap_area(projection,[poly])>1e-3:conflicts.append('OBSTACLE:'+name)
    return conflicts


def _corridors(routes,half_width):
    out={}
    for route in routes:
        pts=route.get('points_local_mm',[])
        for i,(a,b) in enumerate(zip(pts,pts[1:])):
            length=math.dist(a,b)
            if length<=1e-6:continue
            nx=-(b[1]-a[1])*half_width/length;ny=(b[0]-a[0])*half_width/length
            out['UTILITY_'+route['id']+'_'+str(i)]=[[a[0]+nx,a[1]+ny],[a[0]-nx,a[1]-ny],
                                                                [b[0]-nx,b[1]-ny],[b[0]+nx,b[1]+ny]]
    return out


def _sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def create_plan(repo_root:Path, config:dict)->dict:
    """Read immutable sources and return a JSON-serializable mm study plan.

    Geometrical conflicts retain the complete hypothetical field; unknown masks
    or depths receive no mesh/quantity. No native or cumulative success inferred.
    """
    root=Path(repo_root);paths=dict(DEFAULT_SOURCES);paths.update(config.get('source_paths',{}))
    inputs=[{'role':name,'path':path,'sha256':_sha(root/path),'bytes':(root/path).stat().st_size}
            for name,path in paths.items()]
    generators=[{'path':'renovierung/k02/'+p.name,'sha256':_sha(p)} for p in sorted(Path(__file__).parent.glob('*.py'))]
    sources={name:read_json(root/path) for name,path in paths.items()}
    settings=sources['height'];source_grid=Grid(sources['grid']);anchor=settings['anchor_xy_mm']
    if settings['mode']=='ABSOLUTE_EG_HOEHE':
        if not settings.get('common_vertical_datum_confirmed'):raise ValueError('Absolute datum unconfirmed')
        delta=-1000*settings['absolute_eg_source_m']
    elif settings['mode'] in ('PLAN_ANNAHME','AUFMASSPUNKT'):
        delta=settings['ground_z_relative_eg_mm']-source_grid.sample(anchor)
    else:raise ValueError('Unknown height mode')
    grid=Grid(sources['grid'],delta)
    width=config.get('working_width_mm',800);length=config.get('max_bottom_length_mm',2000)
    formation=config.get('main_formation_z_mm',-2605);ratio=config.get('excavation_slope_ratio',1)
    target=config.get('terrain_tolerance_mm',25);n=grid.subdivisions(target);eps=grid.error_bound(n)
    if n>16:raise ValueError('TIN refinement exceeds bounded study budget; revise tolerance explicitly')
    fields=field_register(sources['catalog'],sources['scope'],length,width,formation)
    boundary=sources['house']['site']['boundary']['points_local_mm']
    obstacles={name:poly for name,poly in sources['catalog']['footprints'].items() if name!='EG'}
    eg_projection=sources['catalog']['footprints'].get('EG')
    for row in sources['scope']['provisional_exclusions']:
        if row['boundary'] is not None:obstacles['EXCLUSION_'+row['sector']]=row['boundary']
    # Utility width is a conspicuous display corridor assumption, never a safety clearance.
    utility_width=config.get('utility_corridor_half_width_mm',1000)
    finite(utility_width)
    if utility_width<=0:raise ValueError('Utility corridor width must be explicit and positive')
    utility_corridors=_corridors(sources['house']['site'].get('routes',[]),utility_width)
    pile_candidates=config.get('pile_candidates_mm',[])
    pile_radius=config.get('pile_patch_radius_mm',6000);finite(pile_radius)
    if pile_radius<=0:raise ValueError('Invalid pile terrain patch')
    loose=config.get('loose_factor',1.05);compacted=config.get('compacted_factor',0.89)
    prepared_piles=[]
    for center in pile_candidates:
        finite(*center);x,y=center
        prepared_piles.append((center,grid.triangles(n,(x-pile_radius,y-pile_radius,x+pile_radius,y+pile_radius))))
    for field in fields:
        field['native_candidate']=False;field['stockpile']=None
        field['fach_status']='UNVERIFIED_FOUNDATIONS_SOIL_WATER_UTILITIES_LOADS_ACCESS'
        field['geometry_conflicts']=[]
        field['overbuild_projection_conflicts']=[]
        if field['blockers']:continue
        a=field['origin_mm'];t=field['tangent'];normal=field['normal'];L=field['length_mm']
        depth=max(0,max(p[2] for p in grid.nodes)-formation+eps)
        corners=[[a[k]+s*t[k]+r*normal[k] for k in range(2)]
                 for s in (-ratio*depth,L+ratio*depth) for r in (0,width+ratio*depth)]
        box=geom.bbox([corners]);triangles=grid.triangles(n,box)
        result=geom.excavation(triangles,L,width,formation,ratio,a,t,normal,eps)
        field.update(result);field['volume_m3']=result['volume_mm3']/1e9
        field['volume_interval_m3']=[v/1e9 for v in result['volume_interval_mm3']]
        field['native_measured_volume_m3']=None;field['native_minus_mathematical_m3']=None
        if grid.contact_on_boundary([result['uncertainty_coverage_hull']]):
            field['diagnostic_truncated_volume_m3']=field['volume_m3']
            field.update(status='INCOMPLETE_DGM_DOMAIN',quantity_status='UNKNOWN_OUTSIDE_DGM',
                         mesh=None,mesh_components=None,expected_body_count=None,component_volumes_mm3=None,
                         volume_m3=None,volume_mm3=None,volume_interval_m3=None,volume_interval_mm3=None,
                         projection_polygons=[],geometry_conflicts=['DGM_BOUNDARY'],unreachable_remainder=True)
            field['blockers'].append('DGM_DOMAIN_INCOMPLETE')
            continue
        field['geometry_conflicts']=geometry_conflicts(result['projection_polygons'],boundary,obstacles)
        if eg_projection and overlap_area(result['projection_polygons'],[eg_projection])>1e-3:
            field['overbuild_projection_conflicts']=['OVERBUILD_PROJECTION_UNRESOLVED']
        if grid.contact_on_boundary(result['projection_polygons']):field['geometry_conflicts'].append('DGM_BOUNDARY')
        field['utility_projection_conflicts']=geometry_conflicts(result['projection_polygons'],boundary,utility_corridors)
        field['quantity_status']='HYPOTHETICAL_FULL_FIELD_CONFLICT' if field['geometry_conflicts'] else 'INDEPENDENT_FIELD_TIN_ESTIMATE'
        field['status']='GEOMETRY_CONFLICT' if field['geometry_conflicts'] else 'GEOMETRY_CANDIDATE_UNVERIFIED'
        if not field['geometry_conflicts'] and field['overbuild_projection_conflicts']:
            field['status']='OVERBUILD_PROJECTION_UNRESOLVED'
        field['native_candidate']=not field['geometry_conflicts'] and result['volume_mm3']>0
        field['unreachable_remainder']=bool(field['geometry_conflicts'])
        # Fill equals excavated void only as a transparent scenario; insulation unknown.
        field['material']=balance(field['volume_m3'],field['volume_m3'],loose,compacted)
        field['material']['fill_scenario']='FULL_VOID_NO_CONFIRMED_INSULATION_DISPLACEMENT'
        field['material']['reexcavated_compacted_m3']=None
        soil_bottom=min(formation-1000,min(p[2] for tri in triangles for p in tri)-1000)
        field['study_terrain']={'mesh':closed_terrain(triangles,soil_bottom),
                                'artificial_bottom_z_mm':soil_bottom,'source_is_bilinear':True,
                                'TIN_subdivisions':n,'max_vertical_error_mm':eps,
                                'cutout_applied':False,'reference_translation_mm':[0,0,delta]}
        field['stockpile_attempts']=[]
        if not field['native_candidate']:continue
        for center,pile_ground in prepared_piles:
            attempt={'center_mm':center,'conflicts':[]}
            try:
                pile=geom.stockpile(pile_ground,center,result['volume_mm3']*loose,error_mm=eps)
                reserve=geom.stockpile(pile_ground,center,result['volume_mm3']*1.25,error_mm=eps)
                for candidate in (pile,reserve):
                    projection=candidate['projection_polygons']
                    pile_obstacles={**obstacles,**utility_corridors}
                    if eg_projection:pile_obstacles['EG_PROJECTION']=eg_projection
                    attempt['conflicts'].extend(geometry_conflicts(projection,boundary,pile_obstacles))
                    if overlap_area(projection,result['projection_polygons'],convex_b=True)>1e-3:attempt['conflicts'].append('EXCAVATION_FOOTPRINT')
                    if grid.contact_on_boundary(projection):attempt['conflicts'].append('DGM_BOUNDARY')
                attempt['conflicts']=sorted(set(attempt['conflicts']))
                if not attempt['conflicts']:
                    field['stockpile']={'main':pile,'reserve_1_25':reserve,'center_mm':center,
                                        'terrain_error_mm':eps,'status':'GEOMETRY_CANDIDATE_LOADS_ACCESS_UNVERIFIED',
                                        'load_clearance_mm':None,'access_corridors_confirmed':False}
            except ValueError as exc:attempt['conflicts'].append(str(exc))
            field['stockpile_attempts'].append(attempt)
            if field['stockpile']:break
        field['logistics_status']='CANDIDATE_UNVERIFIED' if field['stockpile'] else 'NO_GEOMETRICALLY_CLEAR_PILE_FOUND'
    result={'schema':'K02_PURE_STUDY_PLAN_V1','units':'mm','construction_release':False,
            'fields':fields,'sectors':[{'id':s['id'],'label':s['label'],'field_ids':[f['id'] for f in fields if f['sector_id']==s['id']]} for s in sources['catalog']['sectors']],
            'independent_states':independent_states(fields),
            'height_registration':{'translation_mm':[0,0,delta],'mode':settings['mode'],'applied_once_to_source_grid':True},
            'terrain_approximation':{'source':'BILINEAR_GRID','model':'CONFORMING_LOCAL_UNIFORM_TIN','subdivisions':n,'max_vertical_error_mm':eps,'target_mm':target},
            'assumptions':{'working_width_mm':width,'max_bottom_length_mm':length,
                           'user_confirmed_study_dimensions':config.get('user_confirmed_study_dimensions',False),
                           'provisional_assistant_dimensions':not config.get('user_confirmed_study_dimensions',False),
                           'excavation_slope_ratio':ratio,'main_formation_z_mm':formation,'formation_is_check_target_only':True,
                           'utility_corridor_half_width_mm':utility_width,'utility_width_is_safety_clearance':False,
                           'loose_factor':loose,'compacted_factor':compacted,'loose_sensitivity':[1.15,1.25],
                           'material_reference':'WSDOT M46-03.08 Ch10 Table10-1 p10-12 (2013-10), sand example; not site measurements',
                           'pile_form':'SQUARE_PYRAMID_ROOF_1_TO_2','load_clearances_and_access_confirmed':False},
            'provenance':{'inputs':inputs,'generators':generators,
                          'config':config,'native_verified':False},
            'limitations':['INDEPENDENT_STATES_NO_CUMULATIVE_UNION_OR_NET_TOTAL',
                           'UNKNOWN_SCOPE_AND_DEPTH_BLOCKED_NULL_QUANTITIES','FULL_CONFLICT_GEOMETRY_NEVER_TRIMMED_TO_FIT',
                           'STUDY_SOIL_ARTIFICIAL_BOTTOM_NOT_SOURCE_DGM_SOLID','NO_NX_EXECUTION_OR_VERIFICATION',
                           'GEOMETRY_CLEAR_DOES_NOT_CONFIRM_FOUNDATIONS_UTILITIES_LOADS_OR_ACCESS']}
    # Detect a source edit during a long study generation, rather than bless mixed inputs.
    for record in inputs:
        if _sha(root/record['path'])!=record['sha256']:raise RuntimeError('Source changed during planning')
    return result
