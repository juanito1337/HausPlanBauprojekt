"""Fresh real NX loading and measurement; never saves the inspected files."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def body_role(name):
    """NX normalizes body names to uppercase on save; role IDs stay canonical."""
    for role in ('excavation', 'pile_main', 'pile_reserve', 'cut_soil'):
        if name.casefold().startswith('k02_'+role+'_'):
            return role
    return None


def transforms(master, directory):
    rows = []
    def walk(parent, indices):
        for index, component in enumerate(parent.GetChildren()):
            origin, rotation = component.GetPosition()
            rows.append({'index_path': indices+[index],
                'part': Path(component.Prototype.FullPath).resolve().relative_to(directory).as_posix(),
                'translation_mm': [origin.X, origin.Y, origin.Z],
                'rotation': [getattr(rotation, k) for k in ('Xx','Xy','Xz','Yx','Yy','Yz','Zx','Zy','Zz')]})
            walk(component, indices+[index])
    walk(master.ComponentAssembly.RootComponent, [])
    return rows


def measure(bodies):
    import NXOpen.UF
    uf = NXOpen.UF.UFSession.GetUFSession()
    values = []
    for body in bodies:
        if not body.IsSolidBody or uf.Modeling.ValidateBody(1, [body.Tag]) != 1:
            raise ValueError('Invalid/non-solid native body: ' + body.Name)
        values.append(uf.Modeling.AskMassProps3d([body.Tag], 1, 1, 4, 1.0, 1, [0.99]+[0.0]*10)[0][1])
    return {'body_count': len(values), 'component_volumes_m3': sorted(values), 'volume_m3': sum(values)}


def open_all(session, directory, master, method):
    import NXOpen
    options = session.Parts.LoadOptions
    options.ComponentLoadMethod = getattr(NXOpen.LoadOptions.LoadMethod, method)
    if method == 'SearchDirectories':
        dirs = sorted({str(p.parent) for p in directory.rglob('*.prt')})
        options.SetSearchDirectories(dirs, [False]*len(dirs))
    options.ComponentsToLoad = NXOpen.LoadOptions.LoadComponents.All
    options.UsePartialLoading = False
    options.UseLightweightRepresentations = False
    part, status = session.Parts.OpenDisplay(str(directory/master))
    try:
        if part is None or status.NumberUnloadedParts:
            raise ValueError('Assembly not fully loaded')
    finally:
        status.Dispose()
    return part


def inspect(session, root, master, expected, expected_measurements):
    import NXOpen
    from renovierung.k02.runner import validate_measurement
    names, dependencies = [], {}
    measurements = {}
    for part in session.Parts:
        path = Path(part.FullPath).resolve()
        name = path.relative_to(root).as_posix()
        if name not in expected or not part.IsFullyLoaded or part.PartUnits != NXOpen.BasePart.Units.Millimeters:
            raise ValueError('Unlisted, partial or non-mm part: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]['sha256']:
            raise ValueError('Native file changed: ' + name)
        parents = [Path(p.FullPath).resolve().relative_to(root).as_posix() for p in part.GetInterpartParents()]
        refs = list(part.Expressions.GetInterpartReferences())
        if refs:
            raise ValueError('Expression interpart references not supported: ' + repr(refs))
        dependencies[name] = {'interpart_parents': parents, 'expression_references': refs}
        names.append(name)
        for role, wanted in expected_measurements.items():
            bodies = [b for b in part.Bodies if body_role(b.Name) == role]
            if bodies:
                if role in measurements: raise ValueError('Duplicate role in different parts')
                # UF body validation requires its owning part to be the work part.
                session.Parts.SetWork(part)
                actual = measure(bodies)
                validate_measurement(actual, wanted['component_volumes_m3'])
                # Keep independent fresh measurements, no copying expected numbers.
                measurements[role] = actual
    if set(names) != set(expected):
        raise ValueError('Missing parts: ' + repr(sorted(set(expected)-set(names))))
    if set(measurements) != set(expected_measurements):
        raise ValueError('Missing measurement roles: ' + repr(sorted(set(expected_measurements)-set(measurements))))
    session.Parts.SetWork(master)
    return {'status': 'PASS', 'parts': sorted(names), 'measurements': measurements,
            'transforms': transforms(master, root), 'dependencies': dependencies,
            'all_parts_mm': True, 'all_parts_fully_loaded': True, 'all_paths_internal': True,
            'files_saved_by_verifier': False}


def main():
    request = json.loads(Path(os.environ['K02_NX_REQUEST']).read_text(encoding='utf-8'))
    sys.path.insert(0, request['repo_root'])
    result = {'status': 'FAIL'}
    try:
        import NXOpen
        session = NXOpen.Session.GetSession()
        if list(session.Parts): raise RuntimeError('Fresh NX process required')
        root = Path(request['directory']).resolve()
        master = open_all(session, root, request['master'], request['load_method'])
        result = inspect(session, root, master, {r['path']: r for r in request['parts']}, request['measurements'])
        result.update(master=request['master'], load_method=request['load_method'])
        if 'transforms' in request and result['transforms'] != request['transforms']:
            raise ValueError('Component transforms changed after save/reopen/move')
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
    Path(request['report']).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    if result['status'] != 'PASS': raise RuntimeError(result['error'])


if __name__ == '__main__': main()
