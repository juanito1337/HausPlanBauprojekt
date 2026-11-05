"""Native batch entry point for M02 generation and independent verification."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _site_phase(session, root, request):
    from renovierung.anbau.site import build_site_part, inspect_site_part
    path = root / 'ANBAU_SITE.prt'
    building = request['mode'] == 'site_build'
    if building:
        root.mkdir(parents=True, exist_ok=True)
        _, evidence = build_site_part(session, path, request['site_entry'])
    else:
        before = _sha(path)
        part, status = session.Parts.OpenDisplay(str(path))
        try:
            if status.NumberUnloadedParts:
                raise ValueError('Shared-ground Part did not load completely')
        finally:
            status.Dispose()
        evidence = inspect_site_part(session, part, request['site_entry'])
        if _sha(path) != before:
            raise ValueError('Read-only site verification changed Part bytes')
    return {'status': 'PASS', 'evidence': evidence, 'file': path.name,
            'bytes': path.stat().st_size, 'sha256': _sha(path), 'files_saved': building}


def dispatch(session, root, request):
    mode = request['mode']
    if mode in ('site_build', 'site_verify'):
        return _site_phase(session, root, request)
    if mode == 'clone':
        from renovierung.m01.flat_pack import build_flat_pack
        packed = build_flat_pack(session, Path(request['source_directory']).resolve(), root,
                                 request['physical_base_layout'], request['physical_file_map'],
                                 preserve_leaf_bytes=True)
        return {'status': 'PASS', 'pack': packed}
    if mode == 'upgrade':
        from renovierung.anbau.integration import upgrade_master
        return {'status': 'PASS', 'upgrade': upgrade_master(session, root, request['spec'])}
    if mode == 'repair_existing':
        from renovierung.anbau.integration import repair_existing
        repaired = repair_existing(session, root, request['new_upgrade'],
                                   request['old_verification_spec'], request['before_manifest'])
        return {'status': 'PASS', 'repair': repaired}
    if mode == 'repair_instance_names':
        from renovierung.anbau.integration import repair_instance_names
        repaired = repair_instance_names(session, root, request['new_upgrade'],
                                         request['verification_spec'], request['before_manifest'])
        return {'status': 'PASS', 'repair': repaired}
    if mode == 'repair_section_defaults':
        from renovierung.anbau.integration import repair_section_defaults
        repaired = repair_section_defaults(session, root, request['new_upgrade'],
                                           request['verification_spec'], request['before_manifest'])
        return {'status': 'PASS', 'repair': repaired}
    if mode == 'section_smoke':
        from renovierung.anbau.verification import smoke_sections
        return {'status': 'PASS', 'diagnostic': smoke_sections(session, root, request['verification_spec'])}
    if mode == 'full_verify':
        from renovierung.anbau.verification import inspect_full_delivery
        return inspect_full_delivery(session, root, request['verification_spec'])
    if mode == 'default_verify':
        from renovierung.anbau.verification import probe_default_entries
        return probe_default_entries(session, root, request['verification_spec'])
    raise ValueError('Unsupported annex master journal mode: ' + str(mode))


def main():
    request = json.loads(Path(os.environ['ANBAU_MASTER_REQUEST']).read_bytes())
    sys.path.insert(0, request['repo_root'])
    result = {'status': 'FAIL', 'construction_release': False, 'mode': request['mode']}
    try:
        import NXOpen
        session = NXOpen.Session.GetSession()
        if not session.IsBatch or list(session.Parts):
            raise RuntimeError('A fresh owned batch NX process is required')
        result.update(dispatch(session, Path(request['directory']).resolve(), request))
    except Exception as error:
        result.update(status='FAIL', error=str(error), traceback=traceback.format_exc())
        if hasattr(error, 'evidence'):
            result['evidence'] = error.evidence
    Path(request['report']).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
