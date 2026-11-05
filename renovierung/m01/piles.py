"""Opt-in terrain-conforming alternative piles; offline proposal only.

This local helper changes no generator, input, layout, native part or original
K02 study. It intentionally performs no site acceptance: vegetation, buildings,
utilities, property boundary, access and loads need independent site checks.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

from renovierung.k02.geometry import area, bbox, convex_hull, partitions, plane, stockpile, validate_mesh, value
from renovierung.k02.planning import DEFAULT_SOURCES
from renovierung.k02.terrain import Grid, read_json

CONFIG_PATH = 'renovierung/k02/study_config.json'
FACTORS = {'main': 1.05, 'reserve_1_25': 1.25}


def _number(x):
    if type(x) not in (int, float) or not math.isfinite(x):
        raise ValueError('Finite numeric pile parameter required')
    return x


def _tin_z(grid, n, point):
    """Same affine subtriangle as Grid.triangles, not bilinear interpolation."""
    u, v = grid.uv(point)
    if not (0 <= u <= grid.nu-1 and 0 <= v <= grid.nv-1):
        raise ValueError('Pile site outside DGM; no extrapolation')
    i, j = min(int(u), grid.nu-2), min(int(v), grid.nv-2)
    a, b = min(int((u-i)*n), n-1), min(int((v-j)*n), n-1)
    fu, fv = (u-i)*n-a, (v-j)*n-b
    def p(da, db):
        x, y = (a+da)/n, (b+db)/n
        z = ((1-x)*(1-y)*grid.node(i,j)[2]+x*(1-y)*grid.node(i+1,j)[2]+
             x*y*grid.node(i+1,j+1)[2]+(1-x)*y*grid.node(i,j+1)[2])
        return grid.xy(i+x,j+y)+[z]
    tri = [p(0,0),p(1,0),p(1,1)] if fu >= fv else [p(0,0),p(1,1),p(0,1)]
    return value(plane(tri), point)


@lru_cache(maxsize=2)
def _ground(payload):
    d = json.loads(payload)
    grid = Grid(d['grid'])
    cx, cy = d['center']
    radius = d['radius']
    box = [cx-radius, cy-radius, cx+radius, cy+radius]
    return grid, grid.triangles(d['n'], box), box


@lru_cache(maxsize=64)
def _pile(payload, target):
    d = json.loads(payload)
    grid, triangles, _ = _ground(payload)
    result = stockpile(triangles, d['center'], target, roof_slope=0.5, error_mm=d['eps'])
    measurement = validate_mesh(result['mesh'])
    projection = result['projection_polygons']
    ground_z = [_tin_z(grid, d['n'], p) for poly in projection for p in poly]
    xyz = result['mesh']['vertices']
    cx, cy = d['center']; h = result['apex_z_mm']; k = 0.5
    roofs = [(k,0,h-k*cx),(-k,0,h+k*cx),(0,k,h-k*cy),(0,-k,h+k*cy)]
    upper = partitions(triangles, roofs, lower=False, shift=-d['eps'])
    return {'target_volume_m3': target/1e9, 'volume_m3': measurement['volume_mm3']/1e9,
            'body_count': measurement['expected_body_count'],
            'component_volumes_m3': sorted(v/1e9 for v in measurement['component_volumes_mm3']),
            'volume_interval_m3': [v/1e9 for v in result['volume_interval_mm3']],
            'center_xy_mm': list(d['center']), 'apex_z_mm': result['apex_z_mm'],
            'roof_slope': result['roof_slope'], 'form': result['form'],
            'terrain_error_mm': result['terrain_error_mm'],
            'contact_polygons_xy_mm': projection,
            'contact_area_m2': sum(abs(area(p)) for p in projection)/1e6,
            'contact_bbox_mm': list(bbox(projection)),
            'bbox_mm': [min(p[k] for p in xyz) for k in range(3)]+[max(p[k] for p in xyz) for k in range(3)],
            'uncertainty_contact_hull_xy_mm': convex_hull([p for poly,_,_ in upper for p in poly]),
            'contact_ground_z_range_mm': [min(ground_z), max(ground_z)],
            'construction_release': False, 'mesh': result['mesh']}


def _inputs(root, layout, center):
    if not isinstance(center, (list, tuple)) or len(center) != 2:
        raise ValueError('Explicit XY pile center required')
    center = [_number(x) for x in center]
    config = layout['provenance']['plan_provenance']['config']
    if read_json(root/CONFIG_PATH) != config:
        raise ValueError('Pile configuration differs from layout evidence')
    if config.get('loose_factor', 1.05) != 1.05:
        raise ValueError('Expected unchanged K02 loose factor 1.05')
    paths = dict(DEFAULT_SOURCES)
    paths.update(config.get('source_paths', {}))
    hashes = {}
    for path in list(paths.values())+[CONFIG_PATH]:
        relative = Path(path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe pile source path')
        hashes[relative.as_posix()] = hashlib.sha256((root/relative).read_bytes()).hexdigest()
    data, height = read_json(root/paths['grid']), read_json(root/paths['height'])
    source = Grid(data)
    if height['mode'] == 'ABSOLUTE_EG_HOEHE':
        if height.get('common_vertical_datum_confirmed') is not True:
            raise ValueError('Absolute source datum unconfirmed')
        delta = -1000*_number(height['absolute_eg_source_m'])
    elif height['mode'] in ('PLAN_ANNAHME', 'AUFMASSPUNKT'):
        delta = _number(height['ground_z_relative_eg_mm'])-source.sample(height['anchor_xy_mm'])
    else:
        raise ValueError('Unknown height registration mode')
    registration = layout['height_registration']
    if (registration['translation_mm'] != [0,0,delta] or registration['mode'] != height['mode'] or
            registration['applied_once_to_source_grid'] is not True):
        raise ValueError('Pile height registration differs')
    grid = Grid(data, delta)
    n = grid.subdivisions(_number(config.get('terrain_tolerance_mm', 25)))
    if n > 16:
        raise ValueError('K02 TIN budget exceeded')
    eps = grid.error_bound(n)
    radius = _number(config.get('pile_patch_radius_mm', 6000))
    if radius <= 0:
        raise ValueError('Positive pile terrain capture radius required')
    _tin_z(grid, n, center)
    fields = []
    ids = set()
    for field in sorted(layout['fields'], key=lambda f: f['id']):
        if type(field['native']) is not bool:
            raise ValueError('Malformed native classification')
        if not field['native']:
            continue
        fid = field['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', fid) or fid in ids:
            raise ValueError('Duplicate/unsafe native field')
        ids.add(fid)
        volume = _number(field['volume_mm3'])
        if volume <= 0 or abs(_number(field['volume_m3'])-volume/1e9) > max(1e-9, volume/1e9*1e-9):
            raise ValueError('Inconsistent original excavation volume: '+fid)
        if 'measurements' in field:
            native = _number(field['measurements']['excavation']['volume_m3'])
            if abs(native-volume/1e9) > max(1e-7, native*1e-7):
                raise ValueError('Excavation differs from native source: '+fid)
        study = field['study_terrain']
        if (type(study['TIN_subdivisions']) is not int or study['TIN_subdivisions'] != n or
                abs(_number(study['max_vertical_error_mm'])-eps) > 1e-8 or
                study['reference_translation_mm'] != [0,0,delta]):
            raise ValueError('Original study TIN differs: '+fid)
        old = field.get('k02_stockpile', field.get('stockpile'))
        old_center = old['center_mm']
        if len(old_center) != 2:
            raise ValueError('Malformed previous pile center')
        old_center = [_number(x) for x in old_center]
        for role, factor in FACTORS.items():
            if abs(_number(old[role]['target_mm3'])-volume*factor) > max(1e-3,volume*factor*1e-9):
                raise ValueError('Original pile target differs: '+fid+'/'+role)
        fields.append({'id':fid, 'volume_mm3':volume, 'previous':deepcopy(old)})
    if not fields:
        raise ValueError('No native studies available')
    payload = json.dumps({'grid':{'shape':[grid.nu,grid.nv], 'nodes_mm':grid.nodes}, 'n':n, 'eps':eps,
                          'center':center, 'radius':radius}, sort_keys=True, allow_nan=False)
    return payload, fields, hashes, deepcopy(registration)


def create_piles(root, layout, center_xy, include_mesh=False):
    """Recompute main/reserve piles at an explicit site for every native field.

    Returns contact polygons and component-wise mesh volumes without mutating
    the supplied layout. Meshes are included only when explicitly requested.
    Repeated identical DGM/center/volume inputs reuse a bounded geometric cache.
    """
    root = Path(root).resolve()
    try:
        payload, fields, hashes, registration = _inputs(root, layout, center_xy)
        data = json.loads(payload)
        grid, triangles, requested_box = _ground(payload)
        result = {'schema':'M02_LOCAL_PILE_PROPOSAL_V1', 'units':'mm', 'center_xy_mm':data['center'],
                  'construction_release':False, 'site_acceptance':'NOT_ASSESSED',
                  'height_registration':registration, 'source_hashes':hashes,
                  'layout_input_sha256':hashlib.sha256(json.dumps(fields,sort_keys=True,allow_nan=False).encode()).hexdigest(),
                  'ground_capture':{'requested_bbox_mm':requested_box,
                                    'actual_bbox_mm':list(bbox([[p[:2] for p in tri] for tri in triangles])),
                                    'triangle_count':len(triangles), 'TIN_subdivisions':data['n'],
                                    'max_vertical_error_mm':data['eps'],
                                    'center_surface_z_mm':_tin_z(grid,data['n'],data['center']),
                                    'ground_z_range_mm':[min(p[2] for tri in triangles for p in tri),
                                                         max(p[2] for tri in triangles for p in tri)]},
                  'fields':[], 'limitations':['NO_NATIVE_EXECUTION','ALTERNATIVE_SINGLE_FIELD_STUDIES',
                        'SITE_VEGETATION_UTILITIES_PROPERTY_ACCESS_LOADS_NOT_ASSESSED',
                        'NO_CONSTRUCTION_RELEASE','NO_RIGID_TRANSLATION_OF_EXISTING_PILES']}
        for field in fields:
            old = field['previous']
            comparison = {'previous_center_mm':old['center_mm'],
                          'displacement_xy_mm':[data['center'][k]-old['center_mm'][k] for k in range(2)]}
            row = {'id':field['id'], 'excavation_volume_m3':field['volume_mm3']/1e9, 'comparison':comparison}
            for role, factor in FACTORS.items():
                cached = _pile(payload,field['volume_mm3']*factor)
                row[role] = {k:deepcopy(v) for k,v in cached.items() if include_mesh or k != 'mesh'}
                comparison[role] = {'previous_target_volume_m3':old[role]['target_mm3']/1e9,
                                    'previous_volume_m3':old[role]['volume_mm3']/1e9,
                                    'previous_apex_z_mm':old[role]['apex_z_mm'],
                                    'target_delta_m3':cached['target_volume_m3']-old[role]['target_mm3']/1e9,
                                    'mesh_volume_delta_m3':cached['volume_m3']-old[role]['volume_mm3']/1e9,
                                    'apex_delta_mm':cached['apex_z_mm']-old[role]['apex_z_mm']}
            result['fields'].append(row)
        if any(hashlib.sha256((root/path).read_bytes()).hexdigest() != expected for path,expected in hashes.items()):
            raise ValueError('Pile sources changed during calculation')
        return result
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError) as error:
        raise ValueError('Malformed pile proposal inputs: '+str(error)) from error
