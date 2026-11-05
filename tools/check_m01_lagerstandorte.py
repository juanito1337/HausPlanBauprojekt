"""Reproduce the two M01 display-location checks; no search, NX run or release.

Usage: python tools/check_m01_lagerstandorte.py --plan PLAN.json --output RESULT.json
       --candidate A 14500 -9500 --candidate B 10000 -22000 --preferred A
Only the result JSON is written. All geometric coordinates are in local mm.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
from renovierung.k02 import geometry as geom
from renovierung.k02.planning import DEFAULT_SOURCES, _corridors
from renovierung.k02.terrain import Grid
from tools.repo_support import member_path

VEGETATION = ('V01', 'V02', 'V03', 'V05')
KINDS = ('main', 'reserve_1_25')


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Sources:
    """Hash exactly the bytes read; detect changes again before writing results."""
    def __init__(self, root):
        self.root, self.hashes = Path(root).resolve(), {}

    def read(self, name, expected=None, size=None, json_data=True):
        data = member_path(self.root, name).read_bytes()
        actual = hashlib.sha256(data).hexdigest()
        require(expected is None or actual == expected, 'Source/generator hash differs: ' + name)
        require(size is None or len(data) == size, 'Source byte count differs: ' + name)
        require(name not in self.hashes or self.hashes[name] == actual, 'Source changed: ' + name)
        self.hashes[name] = actual
        return json.loads(data.decode('utf-8-sig')) if json_data else data

    def recheck(self):
        for name, expected in self.hashes.items():
            require(hashlib.sha256(member_path(self.root, name).read_bytes()).hexdigest() == expected,
                    'Source changed during calculation: ' + name)


def verify_plan(sources, plan):
    require(plan['schema'] == 'K02_PURE_STUDY_PLAN_V1' and plan['units'] == 'mm'
            and plan['construction_release'] is False, 'Invalid K02 study scope')
    provenance = plan['provenance']
    rows = provenance['inputs'] + provenance['generators']
    require(len({row['path'] for row in rows}) == len(rows), 'Duplicate plan provenance paths')
    generators = {p.relative_to(sources.root).as_posix()
                  for p in (sources.root/'renovierung/k02').glob('*.py')}
    require({r['path'] for r in provenance['generators']} == generators,
            'K02 generator inventory differs')
    for row in rows:
        sources.read(row['path'], row['sha256'], row.get('bytes'), json_data=False)
    paths = dict(DEFAULT_SOURCES)
    paths.update(provenance['config'].get('source_paths', {}))
    require({r['role']: r['path'] for r in provenance['inputs']} == paths,
            'K02 source role/path inventory differs')
    require(sources.read('renovierung/k02/study_config.json') == provenance['config'],
            'K02 configuration differs')
    return {role: sources.read(path) for role, path in paths.items()}


def point_segment(p, a, b):
    delta = [b[i]-a[i] for i in (0, 1)]
    length2 = sum(x*x for x in delta)
    t = max(0., min(1., sum((p[i]-a[i])*delta[i] for i in (0, 1))/length2)) if length2 else 0.
    return math.dist(p, [a[i]+t*delta[i] for i in (0, 1)])


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def convex_inside(p, poly):
    return all(cross(a, b, p) >= -1e-7 for a, b in zip(poly, poly[1:]+poly[:1]))


def polygon_inside(p, poly):
    inside = False
    for a, b in zip(poly, poly[1:]+poly[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]):
            if p[0] < a[0] + (p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1]):
                inside = not inside
    return inside


def segment_distance(a, b, c, d):
    if (max(a[0], b[0]) >= min(c[0], d[0]) and max(c[0], d[0]) >= min(a[0], b[0])
            and max(a[1], b[1]) >= min(c[1], d[1]) and max(c[1], d[1]) >= min(a[1], b[1])
            and cross(a, b, c)*cross(a, b, d) <= 0 and cross(c, d, a)*cross(c, d, b) <= 0):
        return 0.
    return min(point_segment(a, c, d), point_segment(b, c, d),
               point_segment(c, a, b), point_segment(d, a, b))


def edge_distance(a, b):
    return min(segment_distance(p, q, r, s)
               for p, q in zip(a, a[1:]+a[:1]) for r, s in zip(b, b[1:]+b[:1]))


def convex_distance(a, b):
    return 0. if convex_inside(a[0], b) or convex_inside(b[0], a) else edge_distance(a, b)


def route_distance(hull, points):
    if any(convex_inside(p, hull) for p in points):
        return 0.
    return min(segment_distance(a, b, c, d) for a, b in zip(hull, hull[1:]+hull[:1])
               for c, d in zip(points, points[1:]))


def vegetation_projections(sources, job_name, current_name):
    job = sources.read(job_name)
    review = sources.read('projects/g02/umgebung/abgleich/VEGETATION_VIDEO_R11.json')
    require({r['id'] for r in review['groups'] if r['include']} == set(VEGETATION),
            'Active G02 vegetation selection differs')
    polygons, summary = {}, {}
    for row in job['parts']:
        if row['id'] not in VEGETATION:
            continue
        name = 'projects/g02/umgebung/' + row['step_file']
        require(row['sha256'] == row['geometry_reference']['source_sha256'], 'STEP reference hash differs')
        sources.read(name, row['sha256'], json_data=False)
        patches = []
        for sheet in row['geometry_reference']['sheets']:
            nr, nc = sheet['grid_shape']
            nodes = sheet['samples_mm'][:nr*nc]
            require(len(nodes) == nr*nc and min(nr, nc) >= 2, 'Invalid vegetation grid')
            corners = [nodes[0][:2], nodes[nc-1][:2], nodes[-1][:2], nodes[-nc][:2]]
            for r in range(nr):
                for c in range(nc):
                    expected = [corners[0][k] + r/(nr-1)*(corners[3][k]-corners[0][k])
                                + c/(nc-1)*(corners[1][k]-corners[0][k]) for k in (0, 1)]
                    require(math.dist(expected, nodes[r*nc+c][:2]) < 1e-5,
                            'Vegetation patch XY is not affine')
            patches.append(geom.clean(corners))
        require(len(patches) == row['expected_sheets'], 'Vegetation sheet count differs')
        polygons[row['id']] = patches
        summary[row['id']] = {'step': name, 'sheets': len(patches),
                               'projected_area_m2': sum(geom.area(p) for p in patches)/1e6}
    require(set(polygons) == set(VEGETATION), 'Vegetation source inventory differs')
    current = sources.read(current_name)
    base = Path(current_name).parent.as_posix() + '/' + current['directory'] + '/'
    build = sources.read(base+'BUILD.json')
    verify = sources.read(base+'VERIFY.json')
    require(build['status'] == verify['status'] == 'PASS' and build['native_NX_run_completed'] is True,
            'Existing native G02 evidence incomplete')
    require(build['height_translation_mm'][:2] == [0, 0], 'G02 environment has an XY translation')
    for vid in VEGETATION:
        parts = [r for r in build['parts'] if '_' + vid + '_' in r['path']]
        require(len(parts) == 1, 'Missing/duplicate native vegetation part: ' + vid)
        row = parts[0]
        sources.read(base+row['path'], row['sha256'], row['bytes'], json_data=False)
        summary[vid]['existing_native_part'] = base+row['path']
    return polygons, summary


def original_location(fields, vegetation, boundary, footprints, corridors, routes):
    rows = []
    for field in fields:
        for kind in KINDS:
            support = field['stockpile'][kind]['projection_polygons']
            hull = geom.convex_hull([p for poly in support for p in poly])
            distances = {r['id']: route_distance(hull, r['points_local_mm'])/1000 for r in routes}
            nearest = min(distances, key=distances.get)
            rows.append({'field': field['id'], 'kind': kind, 'center_xy_mm': field['stockpile']['center_mm'],
                         'support_m2': sum(geom.area(p) for p in support)/1e6,
                         'vegetation_overlap_m2': {vid: geom.overlap_area(support, patches, convex_b=True)/1e6
                                                    for vid, patches in vegetation.items()},
                         'eg_overlap_m2': geom.overlap_area(support, [footprints['EG']])/1e6,
                         'utility_corridor_overlap_sum_m2': sum(geom.overlap_area(support, [p], convex_b=True)
                                                               for p in corridors)/1e6,
                         'nearest_registered_route': nearest, 'route_clearance_lower_bound_m': distances[nearest],
                         'parcel_outside_m2': geom.outside_area(support, boundary)/1e6})
    return rows


def evaluate_candidate(name, xy, fields, grid, n, eps, boundary, obstacles, radius):
    target = max(f['stockpile'][kind]['target_mm3'] for f in fields for kind in KINDS)
    require({f['stockpile'][kind]['roof_slope'] for f in fields for kind in KINDS} == {.5},
            'Monotone support comparison requires common roof slope 0.5')
    x, y = xy
    triangles = grid.triangles(n, (x-radius, y-radius, x+radius, y+radius))
    pile = geom.stockpile(triangles, xy, target, error_mm=eps)
    h, k = pile['apex_z_mm']+eps, .5
    roofs = [(k, 0, h-k*x), (-k, 0, h+k*x), (0, k, h-k*y), (0, -k, h+k*y)]
    support = [p for p, _, _ in geom.partitions(triangles, roofs, lower=False, shift=-eps)]
    require(not geom._domain_contact(triangles, support), 'Conservative support reaches local DGM domain')
    hull = geom.convex_hull([p for poly in support for p in poly])
    clearances = {category: min(convex_distance(hull, p) for p in patches)/1000
                  for category, patches in obstacles.items()}
    clearances['parcel_boundary'] = edge_distance(hull, boundary)/1000 if all(polygon_inside(p, boundary) for p in hull) else 0.
    overlaps = {category: sum(geom.overlap_area(support, [p], convex_b=True) for p in patches)/1e6
                for category, patches in obstacles.items()}
    outside = geom.outside_area(support, boundary)/1e6
    return {'id': name, 'center_xy_mm': xy, 'largest_reserve_target_m3': target/1e9,
            'largest_nominal_support_m2': sum(geom.area(p) for p in pile['projection_polygons'])/1e6,
            'upper_error_support_m2': sum(geom.area(p) for p in support)/1e6,
            'upper_error_support_bbox_xy_mm': geom.bbox(support),
            'clearance_lower_bounds_m': clearances, 'overlap_area_sum_m2': overlaps,
            'parcel_outside_m2': outside,
            'geometric_criterion_passed': clearances['excavation'] >= .6 and min(clearances.values()) > 0
                                          and outside < 1e-8 and max(overlaps.values()) < 1e-8}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path, help='Complete K02 plan including meshes/projection polygons')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=REPO_ROOT)
    parser.add_argument('--candidate', action='append', nargs=3, metavar=('NAME', 'X_MM', 'Y_MM'), required=True)
    parser.add_argument('--preferred', required=True)
    parser.add_argument('--vegetation-job', default='projects/g02/umgebung/data/IMPORTAUFTRAG_R09.json')
    parser.add_argument('--g02-current', default='cad/nx/CURRENT.json')
    args = parser.parse_args(argv)
    sources = Sources(args.root)
    plan_bytes = args.plan.read_bytes()
    plan = json.loads(plan_bytes.decode('utf-8-sig'))
    data = verify_plan(sources, plan)
    fields = [f for f in plan['fields'] if f['native_candidate']]
    require(len(fields) == 22 and len({f['id'] for f in fields}) == 22, 'Expected 22 unique native field studies')
    boundary = geom.clean(data['house']['site']['boundary']['points_local_mm'])
    vegetation, vegetation_sources = vegetation_projections(sources, args.vegetation_job, args.g02_current)
    footprints = data['catalog']['footprints']
    routes = data['house']['site']['routes']
    config = plan['provenance']['config']
    corridors = list(_corridors(routes, config['utility_corridor_half_width_mm']).values())
    obstacles = {'vegetation': [p for patches in vegetation.values() for p in patches],
                 'building': [tri for p in footprints.values() for tri in geom.triangulate_polygon(p)],
                 'utility_corridor': corridors,
                 'excavation': [geom.clean(f['uncertainty_coverage_hull']) for f in fields]}
    grid = Grid(data['grid'], plan['height_registration']['translation_mm'][2])
    n = grid.subdivisions(config['terrain_tolerance_mm']); eps = grid.error_bound(n)
    require(n == plan['terrain_approximation']['subdivisions'] and
            abs(eps-plan['terrain_approximation']['max_vertical_error_mm']) < 1e-8,
            'K02 TIN evidence differs')
    old = original_location(fields, vegetation, boundary, footprints, corridors, routes)
    candidates = []
    for name, x, y in args.candidate:
        xy = [float(x), float(y)]
        require(all(math.isfinite(v) for v in xy), 'Candidate needs finite coordinates')
        candidates.append(evaluate_candidate(name, xy, fields, grid, n, eps, boundary,
                                             obstacles, config['pile_patch_radius_mm']))
    require(len({r['id'] for r in candidates}) == len(candidates), 'Duplicate candidate IDs')
    require(args.preferred in {r['id'] for r in candidates}, 'Preferred candidate missing')
    require(next(r for r in candidates if r['id'] == args.preferred)['geometric_criterion_passed'],
            'Preferred display candidate fails the geometric criterion')
    sources.read('tools/check_m01_lagerstandorte.py', json_data=False)
    sources.read('tools/repo_support.py', json_data=False)
    sources.recheck()
    require(args.plan.read_bytes() == plan_bytes, 'Plan changed during calculation')
    require(args.output.resolve() != args.plan.resolve() and
            args.output.resolve() not in {member_path(sources.root, p).resolve() for p in sources.hashes},
            'Output would overwrite a source')
    result = {'schema': 'M01_STOCKPILE_DISPLAY_LOCATION_CHECK_V1',
              'scope': 'OFFLINE_XY_ONLY_NO_NX_RUN_NO_CONSTRUCTION_RELEASE', 'construction_release': False,
              'plan_sha256': hashlib.sha256(plan_bytes).hexdigest(),
              'verified_source_generator_hashes': dict(sorted(sources.hashes.items())),
              'vegetation_sources': vegetation_sources, 'vegetation_dates': {'bdom': '2023-04-07', 'mask_image': '2025-05-12'},
              'missing_networks': data['house']['site']['unavailable_networks'],
              'field_count': len(fields), 'original_alternatives': old,
              'TIN_subdivisions': n, 'TIN_vertical_error_mm': eps,
              'utility_corridor_half_width_mm': config['utility_corridor_half_width_mm'],
              'minimum_excavation_clearance_mm': 600, 'preferred_display_candidate': args.preferred,
              'support_bound': 'Largest reserve target bounds all 44 alternatives at common center/TIN/slope. Re-solved fixed-volume roof H<=H_nominal+eps combined with terrain>=TIN-eps. Convex hull of this support gives conservative distance lower bounds.',
              'candidates': candidates}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print('PASS: plan sources/generators, 44 original alternatives and %d candidate checks; no NX run.' % len(candidates))
    for row in candidates:
        print(row['id'], row['center_xy_mm'], row['clearance_lower_bounds_m'])
    print('Result:', args.output.resolve())
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print('FAIL:', error, file=sys.stderr)
        raise SystemExit(1)
