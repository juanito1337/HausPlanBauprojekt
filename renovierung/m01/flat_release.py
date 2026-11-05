"""Publish a self-contained NX folder with one physical file per logical Part."""
import datetime
from pathlib import Path
import shutil
import subprocess
import uuid

from tools.repo_support import digest, member_path
from renovierung.k02.runner import read, write


def validate_flat(directory,layout,build,verify,fingerprint):
    from .delivery_paths import make_file_map
    from .runner import validate_result
    try:
        assert_scope = (build['schema']=='M01_FLAT_BUILD_V2' and verify['schema']=='M01_FLAT_VERIFY_V2'
                        and build['status']==verify['status']=='PASS' and build['layout']==layout
                        and build['source_fingerprint']==verify['source_fingerprint']==fingerprint
                        and build['construction_release'] is False and build['native_NX_run_completed'] is True)
        if not assert_scope:
            raise ValueError('Flat release scope, layout or source hash differs')
        files=make_file_map(layout)
        if (files!=build['delivery_file_map'] or build['pack']['status']!='PASS'
                or build['role_display']['status']!='PASS' or build['role_display']['arrangements']!=36):
            raise ValueError('Invalid native delivery packing evidence')
        packed=build['pack']['pack']
        if (packed['status']!='PACKED' or packed['native_clone_completed'] is not True
                or packed['source_bytes_unchanged'] is not True or packed['output_part_count']!=len(files)):
            raise ValueError('Native packing did not complete the exact local file set')
        actual={p.relative_to(directory).as_posix() for p in directory.rglob('*.prt')}
        records={r['logical']:r for r in build['parts']}
        if (actual!=set(files.values()) or set(records)!=set(files) or len(records)!=len(build['parts'])):
            raise ValueError('Incomplete, nested or duplicate flat delivery')
        for logical,name in files.items():
            row=records[logical]
            path=directory/name
            if row['path']!=name or path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
                raise ValueError('Flat native file changed: '+name)
        for row in layout['sources']:
            if row['file'] not in {f['study_file'] for f in layout['fields'] if f['native']}:
                if records[row['file']]['sha256'] != row['sha256']:
                    raise ValueError('Original house/site leaf copy differs: '+row['file'])
        core=verify['as_saved_full']
        if core.get('load_method')!='AsSaved' or core.get('files_saved_by_verifier') is not False:
            raise ValueError('Missing as-saved full opening')
        errors=validate_result(layout,core)
        default=verify['relocated_default']
        if default['status']!='PASS' or default['files_saved_by_verifier'] is not False:
            raise ValueError('Missing default relocated openings')
        from .standalone import validate_default_entries
        errors.extend(validate_default_entries(layout,default['entries']))
        return errors
    except (KeyError,TypeError,ValueError,OSError,AttributeError) as error:
        return [str(error)]


def publish_generated(nx_root,source_run,layout,fingerprint):
    """Recheck a named completed Part inventory, natively pack and test it."""
    from .context_cache import RUN
    from .delivery_paths import make_file_map
    from .runner import ROOT,run_journal,source_fingerprint
    if not RUN.fullmatch(source_run):
        raise ValueError('Invalid named source run')
    base=ROOT/'cad/nx/m01'
    source=member_path(base,source_run)
    old_scratch=ROOT/'reports/local/m01'/source_run
    reqpath=old_scratch/'build_request.json'
    if not reqpath.is_file():
        reqpath=old_scratch/'generate_request.json'
    req=read(reqpath)
    if (Path(req['repo_root']).resolve()!=ROOT or Path(req['directory']).resolve()!=source
            or req['mode'] not in {'build','generate'} or req['layout']!=layout):
        raise ValueError('Generated input does not match the complete current canonical layout')
    report_path=old_scratch/(req['mode']+'_result.json')
    if Path(req['report']).resolve()!=report_path.resolve():
        raise ValueError('Source generation report path differs')
    terminal=read(report_path)
    if terminal['status'] not in {'PASS','FAIL'}:
        raise ValueError('Source generation has not terminated')
    files=make_file_map(layout)
    if set(files)!={p.relative_to(source).as_posix() for p in source.rglob('*.prt')}:
        raise ValueError('Source generation did not finish writing every native Part')
    source_hashes={logical:digest(member_path(source,logical)) for logical in files}
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
    destination=base/stamp
    scratch=ROOT/'reports/local/m01'/stamp
    destination.mkdir(exist_ok=False)
    scratch.mkdir(parents=True,exist_ok=False)
    attempt=dict(status='RUNNING',directory=stamp,source_fingerprint=fingerprint,source_run=source_run)
    write(base/'LAST_ATTEMPT.json',attempt)
    try:
        common=dict(directory=str(destination),source_directory=str(source),layout=layout,
                    file_map=files,source_hashes=source_hashes)
        packed=run_journal(nx_root,dict(common,mode='flat_pack'),scratch,'flat_pack')
        studies={f['study_file'] for f in layout['fields'] if f['native']}
        for original in layout['sources']:
            if original['file'] not in studies and digest(destination/files[original['file']])!=original['sha256']:
                raise ValueError('Packing changed an original building/site leaf: '+original['file'])
        style=run_journal(nx_root,dict(common,mode='flat_style'),scratch,'flat_style')
        if any(digest(member_path(source,key))!=value for key,value in source_hashes.items()):
            raise ValueError('Packing changed input PRT bytes')
        parts=[dict(logical=logical,path=name,bytes=(destination/name).stat().st_size,
                    sha256=digest(destination/name)) for logical,name in sorted(files.items())]
        build=dict(schema='M01_FLAT_BUILD_V2',status='PASS',native_NX_run_completed=True,
                   construction_release=False,source_fingerprint=fingerprint,source_run=source_run,
                   generation_request_sha256=digest(reqpath),source_part_hashes=source_hashes,
                   delivery_file_map=files,parts=parts,layout=layout,pack=packed,role_display=style)
        build['completed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        build['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        write(destination/'BUILD.json',build)
        manifest=[dict(path=r['logical'],bytes=r['bytes'],sha256=r['sha256']) for r in parts]
        core=run_journal(nx_root,dict(common,mode='flat_core',parts=manifest),scratch,'flat_core')
        from .runner import validate_result
        errors=validate_result(layout,core)
        if errors:
            raise ValueError('; '.join(errors))
        moved=scratch/'relocated';moved.mkdir()
        for row in parts:
            shutil.copy2(destination/row['path'],moved/row['path'])
        default=run_journal(nx_root,dict(common,mode='flat_default',directory=str(moved),parts=manifest),
                            scratch,'flat_relocated_default')
        verify=dict(schema='M01_FLAT_VERIFY_V2',status='PASS',source_fingerprint=fingerprint,
                    as_saved_full=core,relocated_default=default)
        verify['completed_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(destination/'VERIFY.json',verify)
        errors=validate_flat(destination,layout,build,verify,source_fingerprint(layout))
        if errors:
            raise ValueError('; '.join(errors))
        write(base/'CURRENT.json',dict(directory=stamp,master=stamp+'/'+files[layout['master']],revision='M01.2'))
        write(base/'LAST_ATTEMPT.json',dict(attempt,status='PASS'))
        return destination
    except Exception as error:
        write(base/'LAST_ATTEMPT.json',dict(attempt,status='FAIL',error=str(error)))
        raise
