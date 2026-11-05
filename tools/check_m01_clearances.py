"""Recalculate horizontal K02 study clearances without NX (standard library).

Fresh plan: python tools/check_m01_clearances.py
Reuse a known fresh plan: add --plan FILE --plan-sha256 SHA256.
Outputs PLAN.json (fresh runs), CLEARANCES.json and CLEARANCES.csv under
reports/local/m01-clearances by default. Input/generator hashes, standard
configuration, native field inventory and expected quantities are checked.
Distances are model geometry only, never a construction/load/access release.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EPS = 1e-7  # mm: numerical contact, not survey accuracy
QUANTITIES = 'renovierung/planung/2026-11-01/K02_MENGEN.json'
CONFIG = 'renovierung/k02/study_config.json'


def default_sources():
    # Importing the pure planner never imports NXOpen.
    from renovierung.k02.planning import DEFAULT_SOURCES
    return dict(DEFAULT_SOURCES)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_pinned_plan(path, expected_sha256):
    raw = Path(path).read_bytes()
    if not expected_sha256 or hashlib.sha256(raw).hexdigest() != expected_sha256.lower():
        raise ValueError('Cached plan SHA-256 differs or was not supplied')
    return json.loads(raw)


def point_segment(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    d2 = dx*dx+dy*dy
    t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/d2)) if d2 else 0.
    q = [a[0]+t*dx, a[1]+t*dy]
    return math.dist(p, q), list(p), q


def _cross(a, b, p):
    return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])


def segment_distance(a, b, c, d):
    """Distance and witness pair for two XY segments, including zero length."""
    u, v = _cross(a, b, c), _cross(a, b, d)
    w, z = _cross(c, d, a), _cross(c, d, b)
    if u*v < 0 and w*z < 0:
        dx, dy = b[0]-a[0], b[1]-a[1]
        ex, ey = d[0]-c[0], d[1]-c[1]
        t = ((c[0]-a[0])*ey-(c[1]-a[1])*ex)/(dx*ey-dy*ex)
        p = [a[0]+t*dx, a[1]+t*dy]
        return 0., p, p
    candidates = [point_segment(a, c, d), point_segment(b, c, d)]
    candidates += [(distance, q, p) for distance, p, q in
                   (point_segment(c, a, b), point_segment(d, a, b))]
    return min(candidates, key=lambda row: row[0])


def _edges(polygons):
    return [(a, b) for poly in polygons for a, b in zip(poly, poly[1:]+poly[:1])]


def inside(p, polygon):
    """Ray crossing on a simple, possibly concave ring; boundary is included."""
    hit = False
    for a, b in _edges([polygon]):
        if point_segment(p, a, b)[0] <= EPS:
            return True
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0]+(p[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if p[0] < x:
                hit = not hit
    return hit


def _box(points):
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def _lower_squared(a, b):
    x = max(0., a[0]-b[2], b[0]-a[2])
    y = max(0., a[1]-b[3], b[1]-a[3])
    return x*x+y*y


def _tree(items):
    bounds = (min(x[0][0] for x in items), min(x[0][1] for x in items),
              max(x[0][2] for x in items), max(x[0][3] for x in items))
    if len(items) <= 8:
        return bounds, items, None
    axis = 0 if bounds[2]-bounds[0] >= bounds[3]-bounds[1] else 1
    items.sort(key=lambda x: x[0][axis]+x[0][axis+2])
    middle = len(items)//2
    return bounds, _tree(items[:middle]), _tree(items[middle:])


def _validate_polygons(polygons):
    if not polygons or any(len(poly) < 3 for poly in polygons):
        raise ValueError('Projection polygons must contain at least three XY points')
    if any(len(p) != 2 or not all(math.isfinite(v) for v in p)
           for poly in polygons for p in poly):
        raise ValueError('Projection coordinates must be finite XY pairs')


def clearance(a_polys, b_polys, filled=True):
    """Exact segment minimum, accelerated only by conservative AABB bounds.

    Filled sets also test containment. For property-line distance use
    filled=False, then separately check outside area against the property.
    Polygon sets are unions of simple rings; no convex-hull substitution.
    """
    _validate_polygons(a_polys)
    _validate_polygons(b_polys)
    a_box = _box([p for poly in a_polys for p in poly])
    b_box = _box([p for poly in b_polys for p in poly])
    if filled and _lower_squared(a_box, b_box) == 0:
        a_rings = [(_box(poly), poly) for poly in a_polys]
        b_rings = [(_box(poly), poly) for poly in b_polys]
        for rings, others in ((a_polys, b_rings), (b_polys, a_rings)):
            for poly in rings:
                p = poly[0]
                for bounds, other in others:
                    if (bounds[0]-EPS <= p[0] <= bounds[2]+EPS and
                            bounds[1]-EPS <= p[1] <= bounds[3]+EPS and inside(p, other)):
                        return {'distance_mm': 0., 'points_mm': [p, p],
                                'overlap_or_containment': True}
    b_tree = _tree([(_box([c, d]), c, d) for c, d in _edges(b_polys)])
    best = (math.inf, None, None)

    def visit(node, a, b, bounds):
        nonlocal best
        if _lower_squared(bounds, node[0]) > best[0]*best[0]:
            return
        if node[2] is None:
            for other, c, d in node[1]:
                if _lower_squared(bounds, other) > best[0]*best[0]:
                    continue
                candidate = segment_distance(a, b, c, d)
                if candidate[0] < best[0]:
                    best = candidate
        else:
            for child in sorted((node[1], node[2]), key=lambda n: _lower_squared(bounds, n[0])):
                visit(child, a, b, bounds)

    for a, b in _edges(a_polys):
        visit(b_tree, a, b, _box([a, b]))
        if best[0] <= EPS:
            return {'distance_mm': 0., 'points_mm': [best[1], best[2]],
                    'overlap_or_containment': bool(filled)}
    return {'distance_mm': best[0], 'points_mm': [best[1], best[2]],
            'overlap_or_containment': False}


def validate_plan(plan, root, config, expected):
    """Refuse stale inputs/generators, nonstandard configuration or quantities."""
    root = Path(root)
    provenance = plan['provenance']
    if plan.get('units') != 'mm' or plan.get('construction_release') is not False:
        raise ValueError('Expected an unreleased mm study')
    if provenance.get('config') != config or config.get('source_paths'):
        raise ValueError('Only the current standard configuration is supported')
    sources = provenance['inputs']
    if len(sources) != len(default_sources()) or {r['role']: r['path'] for r in sources} != default_sources():
        raise ValueError('Incomplete or nonstandard input source inventory')
    generators = provenance['generators']
    actual = {'renovierung/k02/'+p.name for p in (root/'renovierung/k02').glob('*.py')}
    if len(generators) != len(actual) or {r['path'] for r in generators} != actual:
        raise ValueError('Incomplete K02 generator inventory')
    for row in sources+generators:
        if _sha(root/row['path']) != row['sha256']:
            raise ValueError('Stale source/generator hash: '+row['path'])
    native = [f for f in plan['fields'] if f['native_candidate']]
    expected_native = [f for f in expected['fields'] if f['native_candidate']]
    by_id = {f['id']: f for f in expected_native}
    if not native or len(by_id) != len(expected_native) or len(native) != len(by_id) or {f['id'] for f in native} != set(by_id):
        raise ValueError('Native field inventory differs from expected quantities')
    for field in native:
        reference = by_id[field['id']]
        values = [(field['volume_m3'], reference['volume_m3'])]
        values += [(field['stockpile'][key]['volume_mm3']/1e9,
                    reference['stockpile'][key]['volume_mm3']/1e9) for key in ('main', 'reserve_1_25')]
        if any(not math.isfinite(a) or a <= 0 or not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10)
               for a, b in values):
            raise ValueError('Field quantity differs: '+field['id'])


def measure_plan(plan, boundary):
    from renovierung.k02.geometry import outside_area, overlap_area
    native = [f for f in plan['fields'] if f['native_candidate']]
    rows = []
    for field in native:
        row = {'field': field['id'], 'bank_m3': field['volume_m3'],
               'length_m': field['length_mm']/1000,
               'main_loose_m3': field['stockpile']['main']['volume_mm3']/1e9,
               'reserve_loose_m3': field['stockpile']['reserve_1_25']['volume_mm3']/1e9}
        projections = {'excavation': field['projection_polygons'],
                       'pile_main': field['stockpile']['main']['projection_polygons'],
                       'pile_reserve': field['stockpile']['reserve_1_25']['projection_polygons']}
        measures = {}
        for name, polygons in projections.items():
            key = name+'_to_property'
            measures[key] = clearance(polygons, [boundary], filled=False)
            measures[key]['outside_area_mm2'] = outside_area(polygons, boundary)
            row[key+'_m'] = measures[key]['distance_mm']/1000
        for role in ('pile_main', 'pile_reserve'):
            key = 'excavation_to_'+role
            measures[key] = clearance(projections['excavation'], projections[role])
            measures[key]['overlap_area_mm2'] = overlap_area(projections['excavation'], projections[role], convex_b=True)
            row[key+'_m'] = measures[key]['distance_mm']/1000
        row['measurements'] = measures
        rows.append(row)
    pairs = [{'fields': [a['id'], b['id']], **clearance(a['projection_polygons'], b['projection_polygons'])}
             for i, a in enumerate(native) for b in native[i+1:]]
    return {'native_field_count': len(native), 'rows': rows, 'excavation_pairs': pairs}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, help='Reuse a complete previously calculated plan')
    parser.add_argument('--plan-sha256', help='Required known SHA-256 of --plan')
    parser.add_argument('--out-dir', type=Path, default=Path('reports/local/m01-clearances'))
    args = parser.parse_args(argv)
    if bool(args.plan) != bool(args.plan_sha256):
        parser.error('--plan and --plan-sha256 must be supplied together')
    sys.path.insert(0, str(ROOT))
    config_raw = (ROOT/CONFIG).read_bytes()
    expected_raw = (ROOT/QUANTITIES).read_bytes()
    config_sha = hashlib.sha256(config_raw).hexdigest()
    expected_sha = hashlib.sha256(expected_raw).hexdigest()
    config = json.loads(config_raw)
    expected = json.loads(expected_raw)
    output = (ROOT/args.out_dir).resolve()
    if not output.is_relative_to((ROOT/'reports/local').resolve()):
        parser.error('--out-dir must remain inside reports/local')
    if args.plan:
        path = (ROOT/args.plan).resolve()
        plan = read_pinned_plan(path, args.plan_sha256)
        plan_sha = args.plan_sha256.lower()
    else:
        from renovierung.k02.planning import create_plan
        plan = create_plan(ROOT, config)
        raw = json.dumps(plan, ensure_ascii=False, indent=2).encode('utf-8')
        plan_sha = hashlib.sha256(raw).hexdigest()
    validate_plan(plan, ROOT, config, expected)
    house = json.loads((ROOT/default_sources()['house']).read_text(encoding='utf-8'))
    result = measure_plan(plan, house['site']['boundary']['points_local_mm'])
    validate_plan(plan, ROOT, config, expected)  # Detect edits during measurement.
    if _sha(ROOT/CONFIG) != config_sha or _sha(ROOT/QUANTITIES) != expected_sha:
        raise ValueError('Configuration or expected quantity file changed during measurement')
    result.update(schema='M01_CLEARANCES_V1', generated_at_utc=datetime.now(timezone.utc).isoformat(),
                  source_inputs=plan['provenance']['inputs'], generators=plan['provenance']['generators'],
                  config=config, plan_sha256=plan_sha, script_sha256=_sha(__file__),
                  config_sha256=config_sha, expected_quantities_sha256=expected_sha,
                  numerical_contact_epsilon_mm=EPS,
                  construction_release=False,
                  method='Exact XY segment minimum with AABB pruning; containment/contact=0; property boundary distance and outside area separate.')
    output.mkdir(parents=True, exist_ok=True)
    if not args.plan:
        (output/'PLAN.json').write_bytes(raw)
    (output/'CLEARANCES.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    keys = [key for key in result['rows'][0] if key != 'measurements']
    with (output/'CLEARANCES.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({key: row[key] for key in keys} for row in result['rows'])
    minima = {key: min(result['rows'], key=lambda row: row[key])[key] for key in keys if '_to_' in key}
    print(json.dumps({'fields': result['native_field_count'], 'pairs': len(result['excavation_pairs']),
                      'minimum_distances_m': minima, 'output': str(output), 'plan_sha256': plan_sha}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
