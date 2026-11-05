"""Transfer alternative heaps as distinct unmerged STEP shells in one import."""
import math
from renovierung.k02.geometry import validate_mesh


def pile_pair_mesh(field):
    result = {'vertices': [], 'faces': []}
    for key in ('main', 'reserve_1_25'):
        row = field[key]
        mesh = row['mesh']
        measurement = validate_mesh(mesh)
        if measurement['expected_body_count'] != row['body_count']:
            raise ValueError('Pile component count differs: '+key)
        offset = len(result['vertices'])
        result['vertices'].extend(list(point) for point in mesh['vertices'])
        result['faces'].extend([offset+i for i in face] for face in mesh['faces'])
    # Equal ground points of the two alternatives retain independent vertex IDs.
    # Fusing here would merge two mutually exclusive excavation scenarios.
    return result


def validate_pile_locations(layout, actual):
    """Equal volume at the historical hedge site must never pass as a moved pile."""
    fields = {f['id']: f for f in layout['fields'] if f['native']}
    if set(actual) != set(fields):
        raise ValueError('Incomplete measured pile location inventory')
    roles = ('pile_main', 'pile_reserve')
    for fid, field in fields.items():
        found = actual[fid]
        if set(found) != {*roles, 'historical_hidden'} or set(found['historical_hidden']) != set(roles):
            raise ValueError('Incomplete locations or legacy flags: '+fid)
        for role in roles:
            old = found['historical_hidden'][role]
            count = found[role]['body_count']
            if (type(old) is not int or old != field['k02_pile_measurements'][role]['body_count']
                    or type(count) is not int or count != field['measurements'][role]['body_count']):
                raise ValueError('Current or archived native pile count differs: '+fid+' '+role)
            box, expected = found[role]['bbox_mm'], field['display_stockpile'][role]['bbox_mm']
            if (len(box) != 6 or len(expected) != 6 or any(type(v) not in (float, int)
                    or not math.isfinite(v) or abs(v-w)>0.25 for v,w in zip(box,expected))):
                raise ValueError('Native pile location differs: '+fid+' '+role)
