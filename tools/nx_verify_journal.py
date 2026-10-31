"""Open native assembly in a fresh NX process and require all parts inside its root."""
import hashlib
import json
import os
from pathlib import Path
import traceback


def main():
    request = json.loads(Path(os.environ['HAUSPLAN_NX_REQUEST']).read_text(encoding='utf-8'))
    result = {'status': 'FAIL', 'parts': []}
    try:
        import NXOpen
        session = NXOpen.Session.GetSession()
        if list(session.Parts):
            raise RuntimeError('Verification requires a fresh NX process')
        root = Path(request['directory']).resolve()
        expected = {r['path']: r for r in request['parts']}
        directories = sorted({str((root / name).parent) for name in expected})
        options = session.Parts.LoadOptions
        options.ComponentLoadMethod = NXOpen.LoadOptions.LoadMethod.SearchDirectories
        options.SetSearchDirectories(directories, [False] * len(directories))
        options.ComponentsToLoad = NXOpen.LoadOptions.LoadComponents.All
        options.UsePartialLoading = False
        options.UseLightweightRepresentations = False
        master, status = session.Parts.OpenDisplay(str(root / request['master']))
        if status is None:
            raise RuntimeError('No PartLoadStatus returned')
        try:
            if status.NumberUnloadedParts:
                raise RuntimeError('; '.join(status.GetPartName(i) + ': ' + status.GetStatusDescription(i)
                                            for i in range(status.NumberUnloadedParts)))
        finally:
            status.Dispose()
        if master is None:
            raise RuntimeError('No master opened')
        loaded = []
        counts = {}
        for part in session.Parts:
            path = Path(part.FullPath).resolve()
            name = path.relative_to(root).as_posix()  # External/original references fail here.
            if name not in expected:
                raise RuntimeError('Unlisted component: ' + name)
            if not part.IsFullyLoaded:
                raise RuntimeError('Part is not fully loaded: ' + name)
            if part.PartUnits != NXOpen.BasePart.Units.Millimeters:
                raise RuntimeError('Part is not in mm: ' + name)
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]['sha256']:
                raise RuntimeError('Native file changed: ' + name)
            loaded.append(name)
            counts[name] = len(list(part.Bodies))
        if set(loaded) != set(expected):
            raise RuntimeError('Missing components: ' + repr(sorted(set(expected) - set(loaded))))
        result = {'status': 'PASS', 'parts': sorted(loaded), 'body_counts': counts,
                  'all_parts_fully_loaded': True, 'all_parts_within_requested_directory': True,
                  'all_parts_mm': True, 'files_saved_by_verifier': False,
                  'load_method': 'SearchDirectories', 'master': request['master']}
    except Exception as error:
        result.update(error=str(error), traceback=traceback.format_exc())
    Path(request['report']).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'report': request['report']}))
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
