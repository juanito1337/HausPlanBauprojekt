"""Native M01 visibility controls. These functions never save a part."""
import json


PROJECT = 'M01'


def attribute_chunks(key, value):
    """Serialize JSON while respecting NX string-attribute length limits."""
    text = json.dumps(value, ensure_ascii=True, separators=(',', ':'))
    if len(text) <= 1000:
        return [(key, text)]
    return [(key+'_%03d' % index, text[start:start+900])
            for index, start in enumerate(range(0, len(text), 900))]


def write_attribute(obj, key, value):
    """Write component instance attributes, never its shared source Part."""
    import NXOpen
    import NXOpen.Assemblies
    if isinstance(obj, NXOpen.Assemblies.Component):
        setter = obj.SetInstanceUserAttribute
    else:
        setter = obj.SetUserAttribute
    for title, text in attribute_chunks(key, value):
        setter(title, -1, text, NXOpen.Update.Option.Now)


def read_attribute(obj, key):
    """Read exact component-instance attributes without prototype fallback."""
    import NXOpen
    import NXOpen.Assemblies
    if isinstance(obj, NXOpen.Assemblies.Component):
        has_attribute = obj.HasInstanceUserAttribute
        get_attribute = obj.GetInstanceStringUserAttribute
    else:
        has_attribute = obj.HasUserAttribute
        get_attribute = obj.GetStringUserAttribute
    kind = NXOpen.NXObject.AttributeType.String
    if has_attribute(key, kind, -1):
        return json.loads(get_attribute(key, -1))
    chunks = []
    index = 0
    while has_attribute(key+'_%03d' % index, kind, -1):
        chunks.append(get_attribute(key+'_%03d' % index, -1))
        index += 1
    if not chunks:
        raise ValueError('Missing M01 attribute: '+key)
    return json.loads(''.join(chunks))


def components(master):
    """Return unique occurrence IDs, refusing another project or duplicates."""
    if read_attribute(master, 'M01_PROJECT') != PROJECT:
        raise ValueError('The displayed part is not an M01 project master')
    root = master.ComponentAssembly.RootComponent
    if root is None:
        raise ValueError('M01 master has no component assembly')
    result = {}

    def walk(parent):
        for component in parent.GetChildren():
            ident = read_attribute(component, 'M01_NODE_ID')
            if ident in result:
                raise ValueError('Duplicate M01 occurrence ID: '+ident)
            result[ident] = component
            walk(component)

    walk(root)
    return result


def set_blank(component, hidden):
    if hidden:
        component.Blank()
    else:
        component.Unblank()
    if bool(component.IsBlanked) != bool(hidden):
        raise ValueError('NX did not apply component visibility: '+component.Name)


def visibility_order(parents, states):
    """Validate a complete state map and put every ancestor before its children.

    Native parent Blank and Unblank both overwrite child flags. Correcting
    descendants last is therefore necessary for exact final states.
    This function has no NX dependency.
    """
    if set(parents) != set(states) or any(type(v) is not bool for v in states.values()):
        raise ValueError('Visibility states must contain exactly all node IDs and boolean values')
    depths = {}
    for ident in parents:
        if ident == 'MASTER':
            raise ValueError('The assembly root is not a visibility occurrence')
        current, chain = ident, set()
        while current != 'MASTER':
            if current not in parents or current in chain:
                raise ValueError('Missing or cyclic visibility parent: '+str(current))
            chain.add(current)
            current = parents[current]
        depths[ident] = len(chain)
    return sorted(states, key=lambda k: (depths[k], k))


def effective_visibility(parents, local_states):
    """Expand the requested hidden-parent intent to all of its descendants.

    The result is the exact physical IsBlanked map to store and verify;
    local_states remains the role/register intent retained in metadata.
    """
    effective = {}
    for ident in visibility_order(parents, local_states):
        effective[ident] = local_states[ident] or effective.get(parents[ident], False)
    return effective


def apply_visibility(nodes, states):
    """Apply exact occurrence states in the current master display context.

    All requests are validated before mutation. Hidden-parent intent is
    expanded explicitly; native parent operations cascade to descendants.
    """
    parents = {ident: read_attribute(component, 'M01_NODE_METADATA')['parent']
               for ident, component in nodes.items()}
    expected = effective_visibility(parents, states)
    order = visibility_order(parents, expected)
    for ident in order:
        component = nodes[ident]
        if bool(component.IsBlanked) != expected[ident]:
            set_blank(component, expected[ident])
    for ident, component in nodes.items():
        if bool(component.IsBlanked) != expected[ident]:
            raise ValueError('Native visibility differs after applying complete state: '+ident)


def select_state(master, field_id='BASE'):
    """Show BASE or exactly one native single-field study without saving.

    field_id is the register ID, e.g. PS01-F01, not an arbitrary tree name.
    Room and house visibility remains under the user's assembly-tree control.
    """
    nodes = components(master)
    fields = {read_attribute(c, 'M01_FIELD_ID'): c for c in nodes.values()
              if read_attribute(c, 'M01_KIND') == 'field'}
    if field_id != 'BASE':
        if field_id not in fields:
            raise ValueError('Unknown M01 field: '+str(field_id))
        if read_attribute(fields[field_id], 'M01_FIELD_NATIVE') is not True:
            raise ValueError('Field has no confirmed native study: '+field_id)
    if 'TERRAIN' not in nodes:
        raise ValueError('M01 terrain occurrence is missing')
    # Validate the complete request before the first visible change.
    states = {ident: bool(component.IsBlanked) for ident, component in nodes.items()}
    for ident, component in nodes.items():
        kind = read_attribute(component, 'M01_KIND')
        if kind == 'role':
            states[ident] = read_attribute(component, 'M01_DEFAULT_BLANK')
        elif kind == 'field':
            states[ident] = field_id == 'BASE' or read_attribute(component, 'M01_FIELD_ID') != field_id
    states['TERRAIN'] = field_id != 'BASE'
    # A manually hidden section must not silently conceal the chosen study.
    current = nodes['TERRAIN'] if field_id == 'BASE' else fields[field_id]
    ancestors, seen = [], set()
    while True:
        parent_id = read_attribute(current, 'M01_NODE_METADATA')['parent']
        if parent_id == 'MASTER':
            break
        if parent_id not in nodes or parent_id in seen:
            raise ValueError('Invalid M01 parent hierarchy')
        seen.add(parent_id)
        current = nodes[parent_id]
        ancestors.append(parent_id)
    for ident in ancestors:
        states[ident] = False
    apply_visibility(nodes, states)
    return field_id
