"""Run this journal in NX with the intended M01 master displayed.

Select exactly one field or section component in the assembly tree, then
run this file via Tools > Journal > Play. Clear the selection for BASE.
M01_FIELD_ID may explicitly request BASE, a section, or a saved field state.
Register-only fields select their section overview with visible markers.
No code editing is needed, and this journal never saves a part.
The register-only room entries have no invented position or wall ownership.
"""
import os
from pathlib import Path
import sys


def selected_field(master):
    """Resolve a selection only from occurrences of this displayed master.

    The interactive selection API is documented by NX2406's local stubs;
    automated native evidence tests exercise display.select_state directly.
    """
    import NXOpen
    from renovierung.m01.display import components, read_attribute
    nodes = components(master)
    manager = NXOpen.UI.GetUI().SelectionManager
    count = manager.GetNumSelectedObjects()
    if count == 0:
        return 'BASE'
    if count != 1:
        raise ValueError('Select exactly one M01 field component, or clear selection for BASE')
    selected = manager.GetSelectedTaggedObject(0)
    matched = [c for c in nodes.values() if c.Tag == selected.Tag]
    if len(matched) == 1:
        ident = read_attribute(matched[0], 'M01_NODE_ID')
        if ident.startswith('SECTION_'):
            return ident.removeprefix('SECTION_')
    if len(matched) != 1 or read_attribute(matched[0], 'M01_KIND') != 'field':
        raise ValueError('Selection must be a field component belonging to this M01 master')
    field_id = read_attribute(matched[0], 'M01_FIELD_ID')
    if master.HasUserAttribute('M01_DEFAULT_STATE', NXOpen.NXObject.AttributeType.String, -1):
        if field_id in read_attribute(master, 'M01_STATE_CATALOG'):
            return field_id
    if read_attribute(matched[0], 'M01_FIELD_NATIVE') is not True:
        return read_attribute(matched[0], 'M01_FIELD_METADATA')['sector_id']
    return field_id


def main():
    import NXOpen
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from renovierung.m01.display import select_state
    session = NXOpen.Session.GetSession()
    master = session.Parts.Display
    if master is None:
        raise ValueError('Display the intended HAUSPROJEKT_MASTER_M01.prt first')
    if Path(master.FullPath).name != 'HAUSPROJEKT_MASTER_M01.prt':
        raise ValueError('The intended HAUSPROJEKT_MASTER_M01.prt must be displayed')
    field_id = os.environ.get('M01_FIELD_ID')
    if field_id is None:
        field_id = selected_field(master)
    select_state(master, field_id)


if __name__ == '__main__':
    main()
