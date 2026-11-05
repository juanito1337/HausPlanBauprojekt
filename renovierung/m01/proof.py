"""Offline validation of native display evidence; never creates an NX success."""
import math

from renovierung.k02.runner import validate_measurement
from .inspection import build_review_index
from .presentation import DISPLAY_LAYERS
from .states import ROLES, state_catalog, state_spec
from .standalone import _spec as standalone_spec


def _ids(actual, expected, label):
    if (not isinstance(actual, list) or any(not isinstance(x, str) for x in actual)
            or len(set(actual)) != len(actual) or set(actual) != set(expected)):
        raise ValueError('Missing, extra or duplicated ' + label)


def _numbers(actual, expected, label, tolerance=1e-8):
    if (not isinstance(actual, list) or len(actual) != len(expected)
            or any(type(a) not in (int, float) or not math.isfinite(a)
                   or not math.isclose(a, b, rel_tol=1e-10, abs_tol=tolerance)
                   for a, b in zip(actual, expected))):
        raise ValueError('Native camera differs: ' + label)


def _presentation(actual, spec):
    camera = actual['camera']
    scale = camera['scale']
    if (type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0
            or not math.isclose(scale, spec['scale'], rel_tol=1e-10, abs_tol=1e-12)):
        raise ValueError('Native camera differs: scale')
    _numbers(camera['matrix'], spec['matrix'], 'matrix')
    _numbers(camera['absolute_origin_mm'], spec['origin_mm'], 'absolute_origin_mm')
    layers = actual['layers']
    if set(layers) != {str(n) for n in DISPLAY_LAYERS}:
        raise ValueError('Native semantic layer inventory differs')
    for number, layer in layers.items():
        if (layer['visible'] is not True or layer['selectable'] is not True
                or layer['hidden'] is not False):
            raise ValueError('Native semantic layer is not visible/selectable: ' + number)
    if actual['shaded_with_edges'] is not True:
        raise ValueError('Native rendering style differs')


def _role_counts(layout, selected_field, actual, label):
    fields = {f['node_id']: f for f in layout['fields']}
    roles = dict.fromkeys(ROLES, 0)
    for node in layout['nodes']:
        if node['kind'] == 'role':
            field, role = fields[node['parent']], node['role']
            if field['id'] == selected_field and node['blank'] is False:
                roles[role] += field['measurements'][role]['body_count']
    if (set(actual) != set(roles) or any(type(actual[r]) is not int or actual[r] != n
                                       for r, n in roles.items())):
        raise ValueError('Visible native role body counts differ: ' + label)


def _visibility(layout, state, actual):
    fields = {f['node_id']: f for f in layout['fields']}
    _role_counts(layout, state, actual['visible_role_bodies'], state)
    hidden = set(state_spec(layout, state)['suppressed_ids'])
    _ids(actual['visible_context_ids'],
         [g['id'] for g in layout['context']['groups'] if g['id'] not in hidden],
         'visible context IDs: ' + state)
    sections = {s['id'] for s in layout['sections']}
    _ids(actual['visible_field_marker_ids'],
         [f['id'] for f in fields.values()
          if state == f['id'] or (state in sections and f['sector_id'] == state)],
         'visible field marker IDs: ' + state)


def validate_display_evidence(layout, actual):
    """Return errors unless context, every saved state and every entry are proven.

    Inventories derive from the canonical layout (36 states and 35 review entries
    plus 85 standalone subassemblies for the complete delivery), so partial or
    duplicated summaries cannot pass.
    View-space Origin is deliberately not compared with the absolute camera point.
    """
    errors = []
    try:
        groups = {g['id']: g for g in layout['context']['groups']}
        measurements = actual['context_measurements']
        if set(measurements) != set(groups):
            raise ValueError('Native context measurement inventory differs')
        for gid, group in groups.items():
            validate_measurement(measurements[gid], group['component_volumes_m3'])
        catalog = state_catalog(layout)
        default = sorted(f['id'] for f in layout['fields'] if f['native'])[0]
        if layout['default_state'] != default:
            raise ValueError('Layout default state differs from first native field')
        arrangements = actual['arrangements']
        if (arrangements['catalog'] != catalog or arrangements['default'] != default
                or arrangements['active'] != default):
            raise ValueError('Native saved arrangement catalog/default differs')
        if set(arrangements['states']) != set(catalog):
            raise ValueError('Native arrangement state inventory differs')
        for sid, record in arrangements['states'].items():
            _ids(record['suppressed_ids'], state_spec(layout, sid)['suppressed_ids'],
                 'suppressed arrangement IDs: ' + sid)
            _visibility(layout, sid, record)
        _presentation(arrangements['presentation'], layout['presentation'])
        reviews = actual['reviews']
        expected_reviews = {r['id']: r for r in build_review_index(layout)}
        if set(reviews) != set(expected_reviews):
            raise ValueError('Native review entry inventory differs')
        for rid, expected in expected_reviews.items():
            record = reviews[rid]
            if (record['file'] != expected['file'] or record['state'] != expected['state']
                    or record['master'] != layout['master']):
                raise ValueError('Native review file/state/master differs: ' + rid)
            _visibility(layout, expected['state'], record)
            _presentation(record['presentation'], layout['presentation'])
        nodes = {n['id']: n for n in layout['nodes']}
        standalone_ids = {f['node_id'] for f in layout['fields']} | {
            'SECTION_' + s['id'] for s in layout['sections']}
        standalone_files = {nodes[nid]['file']: nid for nid in standalone_ids}
        standalone = actual['standalone']
        if len(standalone_files) != len(standalone_ids) or set(standalone) != set(standalone_files):
            raise ValueError('Native standalone field/section inventory differs')
        for file, node_id in standalone_files.items():
            record, expected = standalone[file], standalone_spec(layout, node_id)
            if (set(record) != {'state', 'visible_role_bodies', 'visible_marker_ids', 'presentation'}
                    or record['state'] != expected['state']):
                raise ValueError('Native standalone record/state differs: ' + file)
            _role_counts(layout, expected['selected_field'], record['visible_role_bodies'], file)
            _ids(record['visible_marker_ids'], expected['visible_marker_ids'],
                 'standalone field marker IDs: ' + file)
            _presentation(record['presentation'], layout['presentation'])
    except (AttributeError, KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
        errors.append('Invalid M01 display evidence: ' + str(error))
    return errors
