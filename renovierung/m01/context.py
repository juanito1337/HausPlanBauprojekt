"""Shared property TIN for M01 display, never an excavation quantity.

Each source DGM cell has one exclusion mask. Its refined TIN is the unmodified
K02 TIN; a field hides precisely the cells supplied by its own cut-soil part.
The 200 mm parallel underside only makes display solids for STEP transfer.
All coordinates already include the existing height registration exactly once.
Only unmasked CONTEXT_000 uses separate closed 4x4-source-cell solids in its
same Part. Its existing top/bottom TIN triangles and every other group remain
unchanged; this bounds the number of facets in each Siemens STEP-import body.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re

from renovierung.k02 import geometry as geom
from renovierung.k02.planning import DEFAULT_SOURCES
from renovierung.k02.terrain import Grid, read_json

THICKNESS_MM = 200.0
CONFIG_PATH = 'renovierung/k02/study_config.json'


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('Malformed finite context coordinate/parameter')
    return value


def _boundary(record, grid):
    if record.get('closed') is not True or any(record.get(k) for k in ('holes', 'interior_rings', 'rings')):
        raise ValueError('One closed property boundary without holes required')
    points = record['points_local_mm']
    if not isinstance(points, list):
        raise ValueError('Malformed property boundary')
    ring = []
    for p in points:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError('Property boundary requires XY pairs')
        ring.append(tuple(_number(x) for x in p))
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    if len(ring) < 3 or len(set(ring)) != len(ring):
        raise ValueError('Empty/duplicate property boundary')
    for p in ring:
        u, v = grid.uv(p)
        if not (-1e-9 <= u <= grid.nu-1+1e-9 and -1e-9 <= v <= grid.nv-1+1e-9):
            raise ValueError('Property outside DGM; no extrapolation')

    def cross(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

    def intersects(a, b, c, d):
        if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]):
            return False
        if max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
            return False
        return cross(a, b, c)*cross(a, b, d) <= 0 and cross(c, d, a)*cross(c, d, b) <= 0

    for i in range(len(ring)):
        for j in range(i+1, len(ring)):
            if j == i+1 or (i == 0 and j == len(ring)-1):
                continue
            if intersects(ring[i], ring[(i+1) % len(ring)], ring[j], ring[(j+1) % len(ring)]):
                raise ValueError('Property boundary is not simple')
    if abs(geom.area(ring)) < 1e-6:
        raise ValueError('Degenerate property boundary')
    return geom.clean(ring)


def _limits(grid, box):
    """Exactly the floor/ceil/clamp domain of K02 Grid.triangles(bbox)."""
    x0, y0, x1, y1 = box
    uv = [grid.uv(p) for p in ((x0, y0), (x0, y1), (x1, y0), (x1, y1))]
    return [max(0, math.floor(min(p[0] for p in uv))),
            min(grid.nu-1, math.ceil(max(p[0] for p in uv))),
            max(0, math.floor(min(p[1] for p in uv))),
            min(grid.nv-1, math.ceil(max(p[1] for p in uv)))]


def _tin_z(grid, n, p):
    """Affine refined-TIN height, including at clipped boundary vertices."""
    u, v = grid.uv(p)
    u = min(grid.nu-1, max(0, u)); v = min(grid.nv-1, max(0, v))
    i = min(int(u), grid.nu-2); j = min(int(v), grid.nv-2)
    a = min(int((u-i)*n), n-1); b = min(int((v-j)*n), n-1)
    fu = (u-i)*n-a; fv = (v-j)*n-b
    def point(da, db):
        x = (a+da)/n; y = (b+db)/n
        z = ((1-x)*(1-y)*grid.node(i, j)[2]+x*(1-y)*grid.node(i+1, j)[2]+
             x*y*grid.node(i+1, j+1)[2]+(1-x)*y*grid.node(i, j+1)[2])
        return grid.xy(i+x, j+y)+[z]
    tri = [point(0, 0), point(1, 0), point(1, 1)] if fu >= fv else [point(0, 0), point(1, 1), point(0, 1)]
    return geom.value(geom.plane(tri), p)


def _prepare(root, layout):
    config = layout['provenance']['plan_provenance']['config']
    if read_json(root/CONFIG_PATH) != config:
        raise ValueError('Context configuration differs from K02 study evidence')
    paths = dict(DEFAULT_SOURCES)
    paths.update(config.get('source_paths', {}))
    sources = {}
    hashes = {}
    for role in ('grid', 'height', 'house'):
        path = Path(paths[role])
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Unsafe context source path')
        sources[role] = read_json(root/path)
        hashes[path.as_posix()] = hashlib.sha256((root/path).read_bytes()).hexdigest()
    hashes[CONFIG_PATH] = hashlib.sha256((root/CONFIG_PATH).read_bytes()).hexdigest()
    data = sources['grid']
    if (len(data['shape']) != 2 or any(type(x) is not int or x < 2 for x in data['shape']) or
            any(not isinstance(p, list) or len(p) != 3 or any(type(x) not in (int, float) or not math.isfinite(x) for x in p)
                for p in data['nodes_mm'])):
        raise ValueError('Malformed context grid')
    source = Grid(data)
    settings = sources['height']
    if settings['mode'] == 'ABSOLUTE_EG_HOEHE':
        if not settings.get('common_vertical_datum_confirmed'):
            raise ValueError('Absolute datum unconfirmed')
        delta = -1000*_number(settings['absolute_eg_source_m'])
    elif settings['mode'] in ('PLAN_ANNAHME', 'AUFMASSPUNKT'):
        delta = _number(settings['ground_z_relative_eg_mm'])-source.sample(settings['anchor_xy_mm'])
    else:
        raise ValueError('Unknown context height mode')
    registration = layout['height_registration']
    if (registration['translation_mm'] != [0, 0, delta] or registration['mode'] != settings['mode'] or
            registration['applied_once_to_source_grid'] is not True):
        raise ValueError('Context height registration differs')
    grid = Grid(data, delta)
    n = grid.subdivisions(_number(config.get('terrain_tolerance_mm', 25)))
    if n > 16:
        raise ValueError('Context TIN exceeds K02 budget')
    eps = grid.error_bound(n)
    boundary = _boundary(sources['house']['site']['boundary'], grid)
    ratio = _number(config.get('excavation_slope_ratio', 1))
    formation = _number(config.get('main_formation_z_mm', -2605))
    if ratio <= 0:
        raise ValueError('Invalid context study slope')
    regions = {}
    for field in sorted(layout['fields'], key=lambda f: f['id']):
        if type(field['native']) is not bool:
            raise ValueError('Invalid native field flag')
        if not field['native']:
            continue
        fid = field['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', fid) or fid in regions:
            raise ValueError('Unsafe/duplicate native field ID')
        study = field['study_terrain']
        if (study['TIN_subdivisions'] != n or type(study['TIN_subdivisions']) is not int or
                abs(_number(study['max_vertical_error_mm'])-eps) > 1e-8 or
                study['reference_translation_mm'] != [0, 0, delta] or
                study['source_is_bilinear'] is not True or study['cutout_applied'] is not True):
            raise ValueError('Field study TIN differs: '+fid)
        a, t, normal = field['origin_mm'], field['tangent'], field['normal']
        if any(len(p) != 2 for p in (a, t, normal)):
            raise ValueError('Malformed field basis')
        for p in (a, t, normal):
            for x in p:
                _number(x)
        if (abs(math.hypot(*t)-1) > 1e-8 or abs(math.hypot(*normal)-1) > 1e-8 or
                abs(sum(x*y for x, y in zip(t, normal))) > 1e-8):
            raise ValueError('Field basis must be orthonormal')
        length, width = _number(field['length_mm']), _number(field['width_mm'])
        if min(length, width) <= 0 or field['formation_z_mm'] != formation:
            raise ValueError('Field dimensions/formation differ')
        # planning.py uses the maximum over the entire source grid, not a local
        # terrain height and not a buffer around the excavation footprint.
        depth = max(0, max(p[2] for p in grid.nodes)-formation+eps)
        corners = [[a[k]+s*t[k]+r*normal[k] for k in range(2)]
                   for s in (-ratio*depth, length+ratio*depth) for r in (0, width+ratio*depth)]
        limits = _limits(grid, geom.bbox([corners]))
        if limits[0] >= limits[1] or limits[2] >= limits[3]:
            raise ValueError('Empty field study domain')
        regions[fid] = limits
    return grid, n, boundary, regions, hashes


def _tile_context_zero(source, grid):
    """The pilot-proven 4x4 split, preserving source TIN faces and one Part.

    Existing triangles fit wholly between source-cell edges. No terrain point
    is resampled and no second height transform is applied. Only zero-volume
    vertical interfaces between neighboring closed solids are added.
    """
    def surface(mesh, upper):
        out = []
        for face in mesh['faces']:
            tri = [mesh['vertices'][i] for i in face]
            projection = geom.area([p[:2] for p in tri])
            if (upper and projection > 1e-10) or (not upper and projection < -1e-10):
                out.append(tri)
        return out

    def signature(triangles):
        return Counter(tuple(sorted(geom._key(p) for p in tri)) for tri in triangles)

    top_faces = surface(source, True)
    tiles = defaultdict(list)
    for tri in top_faces:
        center = [sum(p[k] for p in tri)/3 for k in range(2)]
        u, v = grid.uv(center)
        tile = (math.floor(u)//4, math.floor(v)//4)
        lo_i, lo_j = tile[0]*4, tile[1]*4
        for point in tri:
            pu, pv = grid.uv(point[:2])
            if not (lo_i-1e-8 <= pu <= lo_i+4+1e-8 and lo_j-1e-8 <= pv <= lo_j+4+1e-8):
                raise ValueError('Existing TIN triangle crosses a context tile boundary')
        top = geom.plane(tri)
        tiles[tile].append((geom.clean([p[:2] for p in tri]),
                            (top[0], top[1], top[2]-THICKNESS_MM), top))
    mesh = {'vertices': [], 'faces': []}
    for _, parts in sorted(tiles.items()):
        tile_mesh = geom.surface_mesh(parts)
        offset = len(mesh['vertices'])
        mesh['vertices'].extend(tile_mesh['vertices'])
        mesh['faces'].extend([[i+offset for i in face] for face in tile_mesh['faces']])
    # Equal triangle multisets also preserve the outer property/mask boundary
    # and prove that each projected terrain interior is retained exactly once.
    if (signature(top_faces) != signature(surface(mesh, True)) or
            signature(surface(source, False)) != signature(surface(mesh, False))):
        raise ValueError('Context tiling changes existing TIN top/bottom faces')
    return mesh


@lru_cache(maxsize=2)
def _generate(payload):
    data = json.loads(payload)
    grid = Grid(data['grid'])
    n, boundary, regions = data['n'], data['boundary'], data['regions']
    boundary_triangles = [(tri, geom.bbox([tri])) for tri in geom.triangulate_polygon(boundary)]
    grouped = defaultdict(list)
    property_box = geom.bbox([boundary])
    for tri in grid.triangles(n, property_box):
        # Centroids are strictly inside one refined source cell, including when
        # the affine grid is rotated/reflected relative to world XY.
        center = [sum(p[k] for p in tri)/3 for k in range(2)]
        u, v = grid.uv(center)
        i, j = math.floor(u), math.floor(v)
        mask = tuple(fid for fid, (i0, i1, j0, j1) in regions.items() if i0 <= i < i1 and j0 <= j < j1)
        top = geom.plane(tri)
        low = (top[0], top[1], top[2]-THICKNESS_MM)
        xy = geom.clean([p[:2] for p in tri])
        x0, y0, x1, y1 = geom.bbox([xy])
        for btri, (bx0, by0, bx1, by1) in boundary_triangles:
            if x0 >= bx1 or x1 <= bx0 or y0 >= by1 or y1 <= by0:
                continue
            clipped = geom._convex_intersection(xy, btri)
            if clipped:
                grouped[mask].append((clipped, low, top))
    groups = []
    for index, mask in enumerate(sorted(grouped)):
        gid = 'CONTEXT_%03d' % index
        parts = grouped[mask]
        area = sum(geom.area(poly) for poly, _, _ in parts)/1e6
        mesh = geom.surface_mesh(parts)
        if gid == 'CONTEXT_000' and not mask:
            mesh = _tile_context_zero(mesh, grid)
        measured = geom.validate_mesh(mesh)
        volume = area*THICKNESS_MM/1000
        if abs(measured['volume_mm3']/1e9-volume) > max(1e-8, volume*1e-9):
            raise ValueError('Context mesh volume differs from display thickness')
        groups.append({'id': gid, 'file': 'kontext/'+gid+'.prt', 'exclude_for': list(mask),
                       'area_m2': area, 'volume_m3': volume,
                       'body_count': measured['expected_body_count'],
                       'component_volumes_m3': sorted(v/1e9 for v in measured['component_volumes_mm3']),
                       'mesh': mesh})
    property_area = abs(geom.area(boundary))/1e6
    if abs(sum(g['area_m2'] for g in groups)-property_area) > max(1e-8, property_area*1e-10):
        raise ValueError('Incomplete/overlapping property context')
    return {'groups': groups, 'boundary_xyz_mm': [[*p, _tin_z(grid, n, p)] for p in boundary],
            'field_regions': regions, 'area_m2': property_area,
            'representation': 'DISPLAY_ONLY_PARALLEL_TIN_SOLIDS_NO_EARTHWORK_QUANTITIES',
            'thickness_mm': THICKNESS_MM, 'coordinates': 'HOUSE_EG_MM_HEIGHT_ALREADY_APPLIED'}


def create_context(root, layout, include_mesh=False):
    """Return deterministic shared terrain groups; omit heavy meshes by default.

    The bounded cache is keyed by complete input-derived geometry. Every call
    rereads and hashes the source files, so edits invalidate it and returned
    dictionaries can be modified without contaminating later layout checks.
    """
    try:
        grid, n, boundary, regions, hashes = _prepare(Path(root).resolve(), layout)
        payload = json.dumps({'grid': {'shape': [grid.nu, grid.nv], 'nodes_mm': grid.nodes},
                              'n': n, 'boundary': boundary, 'regions': regions}, sort_keys=True, allow_nan=False)
        cached = _generate(payload)
        result = {k: deepcopy(v) for k, v in cached.items() if k != 'groups'}
        result['groups'] = [{k: deepcopy(v) for k, v in group.items() if include_mesh or k != 'mesh'}
                            for group in cached['groups']]
        result['source_hashes'] = hashes
        # Detect source changes during an expensive first generation.
        if any(hashlib.sha256((Path(root)/p).read_bytes()).hexdigest() != h for p, h in hashes.items()):
            raise ValueError('Context source changed during generation')
        return result
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError) as error:
        raise ValueError('Malformed M01 context inputs: '+str(error)) from error
