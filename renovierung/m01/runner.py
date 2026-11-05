"""Independent M01 delivery: real NX processes and strict saved evidence."""
from __future__ import annotations
from contextlib import contextmanager
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from tools.repo_support import digest, member_path
from renovierung.k02.runner import read, write, validate_measurement
from .layout import create_layout, validate_layout, part_paths

ROOT = Path(__file__).resolve().parents[2]


def expected_nodes(layout):
    """Layout positions are local; NX occurrence positions are world coordinates."""
    nodes = {n['id']: n for n in layout['nodes']}
    from .states import state_spec
    suppressed = set(state_spec(layout, layout['default_state'])['suppressed_ids']) if 'default_state' in layout else set()
    result = {}
    def visit(nid, active):
        if nid in result: return result[nid]
        if nid in active: raise ValueError('Cyclic assembly')
        node = nodes[nid]
        if node['rotation'] != [1,0,0,0,1,0,0,0,1]:
            raise ValueError('M01 only supports identity local rotations')
        parent = visit(node['parent'], active | {nid}) if node['parent'] else None
        xyz = [float(x) for x in node['translation_mm']]
        if len(xyz)!=3 or not all(math.isfinite(x) for x in xyz): raise ValueError('Invalid position')
        if parent: xyz = [x+y for x,y in zip(xyz,parent['translation_mm'])]
        result[nid] = {k:node[k] for k in ('parent','file','name','blank','reference_set')}
        # NX hiding/showing a parent cascades to its descendants. A hidden
        # study must therefore have every child explicitly hidden as well.
        result[nid]['blank'] = node['blank'] or bool(parent and parent['blank'])
        result[nid].update(translation_mm=xyz,rotation=node['rotation'],
                           suppressed=nid in suppressed or bool(parent and parent['suppressed']))
        return result[nid]
    for nid in nodes: visit(nid,set())
    return result


def validate_result(layout, actual):
    errors=[]
    try:
        if actual.get('status')!='PASS' or actual.get('master')!=layout['master']:
            raise ValueError('Missing native master result')
        for key in ('all_parts_mm','all_parts_fully_loaded','all_paths_internal'):
            if actual.get(key) is not True: raise ValueError('Missing native guarantee: '+key)
        if actual.get('construction_release') is not False: raise ValueError('No construction release permitted')
        expected=expected_nodes(layout)
        if set(actual['nodes'])!=set(expected): raise ValueError('Incomplete/extra assembly nodes')
        for nid,wanted in expected.items():
            found=actual['nodes'][nid]
            for key,value in wanted.items():
                if key in ('translation_mm','rotation'):
                    got=found[key]
                    if len(got)!=len(value) or any(type(x) not in (int,float) or not math.isfinite(x) or
                            abs(x-y)>1e-8 for x,y in zip(got,value)):
                        raise ValueError('Changed position/rotation: '+nid)
                elif key=='name':
                    if not isinstance(found.get(key),str) or found[key].casefold()!=value.casefold():
                        raise ValueError('Changed node '+nid+': '+key)
                elif found.get(key)!=value or (key in ('blank','suppressed') and type(found.get(key)) is not bool):
                    raise ValueError('Changed node '+nid+': '+key)
        paths=part_paths(layout)
        if set(actual['parts'])!=paths or len(actual['parts'])!=len(paths): raise ValueError('Part inventory differs')
        if set(actual['dependencies'])!=paths: raise ValueError('Missing dependency inspection')
        for path,dep in actual['dependencies'].items():
            if dep['expression_references'] or any(p not in paths for p in dep['interpart_parents']):
                raise ValueError('External/unsupported dependency: '+path)
        expected_toggles=set(expected)-{'MASTER'}
        if set(actual['toggle_checks'])!=expected_toggles or len(actual['toggle_checks'])!=len(expected_toggles):
            raise ValueError('Incomplete or duplicated component switching tests')
        fields={f['id']:f for f in layout['fields'] if f['native']}
        states={'BASE',*fields}
        if 'context' in layout: states.update(s['id'] for s in layout['sections'])
        if set(actual['state_checks'])!=states or len(actual['state_checks'])!=len(states):
            raise ValueError('Incomplete or duplicated field display tests')
        if set(actual['measurements'])!=set(fields): raise ValueError('Measured field list differs')
        expected_refs={}
        node_map={n['id']:n for n in layout['nodes']}
        field_by_node={f['node_id']:f for f in fields.values()}
        for nid,node in node_map.items():
            if node['kind']!='role': continue
            field=field_by_node[node['parent']]
            role=node['role']
            wanted=field['measurements'][role]
            names=actual['refsets'][node['file']][node['reference_set']]
            if len(names)!=wanted['body_count'] or len(set(names))!=len(names) or any(
                    not isinstance(n,str) or not n.casefold().startswith(('K02_'+role+'_').casefold()) for n in names):
                raise ValueError('Reference set body membership differs: '+nid)
            expected_refs.setdefault(node['file'],set()).add(node['reference_set'])
        if set(actual['refsets'])!=set(expected_refs): raise ValueError('Reference set parts differ')
        for path,refs in expected_refs.items():
            if set(actual['refsets'][path])!=refs: raise ValueError('Reference set roles differ: '+path)
        for fid,field in fields.items():
            if set(actual['measurements'][fid])!=set(field['measurements']): raise ValueError('Measurement roles differ: '+fid)
            for role,wanted in field['measurements'].items():
                validate_measurement(actual['measurements'][fid][role],wanted['component_volumes_m3'])
        if 'context' in layout:
            from .proof import validate_display_evidence
            errors.extend(validate_display_evidence(layout, actual))
        if 'pile_site' in layout:
            from .pile_transfer import validate_pile_locations
            validate_pile_locations(layout, actual['pile_locations'])
    except (AttributeError,KeyError,TypeError,ValueError,OverflowError) as error:
        errors.append(str(error))
    return errors


@contextmanager
def exclusive_build(path):
    """Never reclaim a lock automatically: an existing owner must finish first."""
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    token=json.dumps({'pid':os.getpid(),'owner':'HausPlan M01','token':uuid.uuid4().hex})
    try:
        with path.open('x',encoding='utf-8') as stream: stream.write(token)
    except FileExistsError as error:
        raise RuntimeError('Native build already reserved: '+str(path)) from error
    try: yield
    finally:
        if path.is_file() and path.read_text(encoding='utf-8')==token: path.unlink()


def source_fingerprint(layout):
    paths={p.relative_to(ROOT).as_posix() for p in (ROOT/'renovierung/m01').glob('*.py')}
    paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'renovierung/k02').glob('*.py'))
    paths.update(('tools/nx_master.py','tools/nx_project.py','tools/repo_support.py',
                  'projects/g02/haus/data/haus.json','cad/nx/CURRENT.json','cad/nx/k02/CURRENT.json'))
    for base in ('cad/nx','cad/nx/k02'):
        current=read(ROOT/base/'CURRENT.json')
        directory=member_path(ROOT/base,current['directory'])
        paths.update((directory/name).relative_to(ROOT).as_posix() for name in ('BUILD.json','VERIFY.json'))
    paths.update(s['source'] for s in layout['sources'])
    paths.update(layout.get('context', {}).get('source_hashes', {}))
    paths.update(layout.get('pile_site', {}).get('source_hashes', {}))
    values={p:digest(member_path(ROOT,p)) for p in sorted(paths)}
    values['canonical_layout']=hashlib.sha256(json.dumps(layout,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def validate_evidence(directory, layout, build, verify, fingerprint):
    errors=[]
    try:
        validate_layout(layout)
        if build.get('schema')!='M01_BUILD_V1' or verify.get('schema')!='M01_VERIFY_V1': raise ValueError('Invalid M01 proof schema')
        if build.get('status')!='PASS' or verify.get('status')!='PASS' or build.get('native_NX_run_completed') is not True:
            raise ValueError('Missing completed native build')
        if build.get('source_fingerprint')!=fingerprint or verify.get('source_fingerprint')!=fingerprint:
            raise ValueError('M01 source fingerprint stale')
        if build.get('layout')!=layout: raise ValueError('Saved layout differs from current canonical sources')
        expected_paths=part_paths(layout)
        rows=build['parts']
        if len(rows)!=len(expected_paths) or {r['path'] for r in rows}!=expected_paths:
            raise ValueError('Part manifest differs from canonical layout')
        actual_paths={p.relative_to(directory).as_posix() for p in Path(directory).rglob('*.prt')}
        if actual_paths!=expected_paths: raise ValueError('Files differ from native manifest')
        for row in rows:
            path=member_path(directory,row['path'])
            if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:
                raise ValueError('Native file changed: '+row['path'])
        candidates = build.get('study_cache_candidates', {})
        checks = build['result'].get('study_cache_checks', {})
        if set(candidates) != set(checks):
            raise ValueError('Missing native study-cache comparison')
        for fid, record in candidates.items():
            test = checks[fid]
            if test['reused'] is True:
                if digest(member_path(directory, record['file'])) != record['sha256']:
                    raise ValueError('Reused native study bytes changed: '+fid)
                if set(test['evidence']['retained_absolute_boundary_sha256']) != {'cut_soil','excavation'}:
                    raise ValueError('Missing K02 solid boundary comparison: '+fid)
            elif test['reused'] is not False or not test['evidence'].get('cold_fallback_reason'):
                raise ValueError('Unexplained native study-cache outcome: '+fid)
        study_files={n['file'] for n in layout['nodes'] if n['kind']=='role'}
        for source in layout['sources']:
            if source['file'] not in study_files and digest(member_path(directory,source['file']))!=source['sha256']:
                raise ValueError('Original building/environment copy changed: '+source['file'])
        errors.extend(validate_result(layout,build['result']))
        for phase,method in (('reopen','AsSaved'),('relocated','SearchDirectories')):
            result=verify[phase]
            if result.get('load_method')!=method or result.get('files_saved_by_verifier') is not False:
                raise ValueError('Unproven fresh/relocated read-only opening: '+phase)
            errors.extend(phase+': '+e for e in validate_result(layout,result))
    except (AttributeError,KeyError,TypeError,ValueError,OSError) as error:
        errors.append(str(error))
    return errors


def check_master():
    try:
        root=ROOT/'cad/nx/m01'
        current,attempt=read(root/'CURRENT.json'),read(root/'LAST_ATTEMPT.json')
        if attempt.get('status')!='PASS' or attempt.get('directory')!=current['directory']:
            raise ValueError('Latest M01 build not verified')
        directory=member_path(root,current['directory'])
        layout=create_layout(ROOT)
        if current.get('master')!=current['directory']+'/'+layout['master']:
            raise ValueError('M01 CURRENT master mismatch')
        build,verify=read(directory/'BUILD.json'),read(directory/'VERIFY.json')
        if build.get('schema')=='M01_FLAT_BUILD_V2':
            from .flat_release import validate_flat
            return validate_flat(directory,layout,build,verify,source_fingerprint(layout))
        return validate_evidence(directory,layout,build,verify,source_fingerprint(layout))
    except (AttributeError,OSError,KeyError,TypeError,ValueError) as error:
        return ['M01: '+str(error)]


def assert_journal_idle():
    if os.name=='nt':
        proc=subprocess.run(['powershell','-NoProfile','-Command',
            "@(Get-Process -Name run_journal -ErrorAction SilentlyContinue).Count"],capture_output=True,text=True,check=True)
        if int(proc.stdout.strip())!=0:
            raise RuntimeError('Another run_journal process is active; no foreign process was touched')


def wait_for_journal_slot(timeout=1800, poll_seconds=5):
    """Wait before each own journal phase; never terminate another NX process."""
    deadline=time.monotonic()+timeout
    announced=False
    while True:
        try:
            assert_journal_idle()
            return
        except RuntimeError as error:
            if time.monotonic()>=deadline:
                raise TimeoutError('NX journal slot still occupied; no foreign process was touched') from error
            if not announced:
                print('WAIT M01: another NX journal is active',flush=True)
                announced=True
            time.sleep(poll_seconds)


def run_journal(nx_root,request,scratch,label):
    wait_for_journal_slot()
    report=scratch/(label+'_result.json')
    request_path=scratch/(label+'_request.json')
    write(request_path,dict(request,repo_root=str(ROOT),report=str(report)))
    env=dict(os.environ,M01_NX_REQUEST=str(request_path),PYTHONDONTWRITEBYTECODE='1')
    print('NX M01 '+label,flush=True)
    with (scratch/(label+'.log')).open('w',encoding='utf-8') as stream:
        journal='flat_journal.py' if request['mode'].startswith('flat_') else 'nx_journal.py'
        proc=subprocess.run([str(nx_root/'NXBIN/run_journal.exe'),str(ROOT/'renovierung/m01'/journal)],
            env=env,cwd=scratch,stdout=stream,stderr=subprocess.STDOUT)
    if not report.is_file(): raise RuntimeError('NX produced no result: '+str(scratch/(label+'.log')))
    result=read(report)
    if proc.returncode or result.get('status')!='PASS': raise RuntimeError('NX '+label+': '+str(result.get('error',proc.returncode)))
    return result


def build_master(nx_root,accept,context_cache_run=None,study_cache_run=None,pack_run=None):
    if not accept: raise ValueError('Explicit --accept-model-assumptions required')
    nx_root=Path(nx_root)
    if not (nx_root/'NXBIN/run_journal.exe').is_file(): raise ValueError('NX journal executable missing')
    lock=Path(os.environ.get('LOCALAPPDATA',str(ROOT/'reports/local')))/'CodexNX'/'run_journal.lock'
    with exclusive_build(lock):
        wait_for_journal_slot()
        layout=create_layout(ROOT)
        fingerprint=source_fingerprint(layout)
        from .flat_release import publish_generated
        if pack_run:
            return publish_generated(nx_root,pack_run,layout,fingerprint)
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
        root=ROOT/'cad/nx/m01';root.mkdir(parents=True,exist_ok=True)
        scratch=ROOT/'reports/local/m01'/stamp
        destination=root/stamp
        scratch.mkdir(parents=True,exist_ok=False);destination.mkdir(parents=True,exist_ok=False)
        (destination/'.gitignore').write_text('*\n',encoding='ascii')  # structured assembly is an intermediate
        attempt={'status':'RUNNING','directory':stamp,'source_fingerprint':fingerprint}
        write(root/'LAST_ATTEMPT.json',attempt)
        try:
            from .context import create_context
            from renovierung.k02.mesh_step import write_step
            context = create_context(ROOT, layout, include_mesh=True)
            context_steps = {}
            for group in context['groups']:
                path = scratch/'context_steps'/(group['id']+'.step')
                write_step(path, group['mesh'], group['id'])
                context_steps[group['id']] = str(path)
            from .piles import create_piles
            from .context_cache import prepare_context_cache
            from .pile_transfer import pile_pair_mesh
            piles = create_piles(ROOT, layout, layout['pile_site']['center_mm'], include_mesh=True)
            pile_steps = {}
            for field in piles['fields']:
                fid = field['id']
                path = scratch/'pile_steps'/(fid+'.step')
                write_step(path, pile_pair_mesh(field), fid+'_SANDLAGER')
                pile_steps[fid] = str(path)
            cached = (prepare_context_cache(ROOT, context_cache_run, destination, layout, context_steps)
                      if context_cache_run else {})
            studies = {}
            if study_cache_run:
                from .study_cache import capture_inventory, prepare_study_cache
                inventory = capture_inventory(ROOT, study_cache_run)
                write(scratch/'study_candidate_inventory.json', inventory)
                studies = prepare_study_cache(ROOT, study_cache_run, destination, layout, pile_steps, inventory)
            seeded_files = {record['file'] for record in studies.values()}
            for source in layout['sources']:
                src = member_path(ROOT, source['source'])
                if digest(src) != source['sha256']:
                    raise ValueError('Source changed before copy')
                if source['file'] not in seeded_files:
                    dst = member_path(destination, source['file'])
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists():
                        raise ValueError('Unexpected existing source destination: ' + source['file'])
                    shutil.copy2(src, dst)
            request={'mode':'generate','directory':str(destination),'layout':layout,'load_method':'AsSaved',
                     'nx_root':str(nx_root),'context_steps':context_steps,
                     'pile_steps':pile_steps,'context_cache':cached,'study_cache':studies}
            run_journal(nx_root,request,scratch,'generate')
            return publish_generated(nx_root,stamp,layout,fingerprint)
        except Exception as error:
            write(root/'LAST_ATTEMPT.json',dict(attempt,status='FAIL',error=str(error)))
            raise
