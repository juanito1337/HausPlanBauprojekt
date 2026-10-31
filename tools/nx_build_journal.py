"""Real NX batch entry point; builds an untouched G02 source snapshot."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace


def height_consent(plan, accepted):
    if plan['mode'] != 'PLAN_ANNAHME':
        raise ValueError('Batch consent only covers the documented PLAN_ANNAHME model')
    return accepted is True


def main():
    request = json.loads(Path(os.environ['HAUSPLAN_NX_REQUEST']).read_text(encoding='utf-8'))
    report = Path(request['report'])
    result = {'status': 'FAIL', 'native_NX_run_completed': False}
    try:
        if request.get('accept_model_assumptions') is not True:
            raise ValueError('Explicit acceptance of the existing study-model assumptions required')
        import NXOpen
        session = NXOpen.Session.GetSession()
        if list(session.Parts):
            raise RuntimeError('Build must start in a fresh dedicated NX batch session')
        base = Path(request['source'])
        sys.path.insert(0, str(base))
        from g02.nx_backend import NXBackendG02
        from g02.workflow import run

        class BatchBackend(NXBackendG02):
            def confirm_height(self, plan, reuse=False):
                # Only the consent UI is replaced. Every real NX operation remains intact.
                return height_consent(plan, request['accept_model_assumptions'])

            def house_modules(self):
                modules = super().house_modules()
                runtime = modules.runtime

                class ConsentedHouseAdapter(runtime.HouseMainAdapter):
                    def review_consent(self):
                        return request['accept_model_assumptions']

                def run_main(base):
                    return runtime.run_main(base, adapter_factory=ConsentedHouseAdapter, verify=True)

                return SimpleNamespace(compiler=modules.compiler,
                    runtime=SimpleNamespace(verify_package=runtime.verify_package, run_main=run_main))

        config = json.loads((base / 'data/EINSTELLUNGEN_GESAMT.json').read_text(encoding='utf-8'))
        config['output_root'] = request['output_root']
        state = run(base, 'ALL', backend=BatchBackend(base), verify=True, config=config)
        if state['status'] != 'ANGEFORDERTER_ABLAUF_ABGESCHLOSSEN_FACHLICH_OFFEN':
            raise RuntimeError('G02 build incomplete: ' + state['status'])
        root = Path(state['output_directory']).resolve()
        paths = {Path(record['path']).resolve() for kind in ('house', 'environment', 'project')
                 for record in state[kind]['files'] if Path(record['path']).suffix.lower() == '.prt'}
        parts = []
        for path in sorted(paths):
            parts.append({'path': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
        result = {'schema': 'HAUSPLAN_NX_BUILD_V1', 'status': 'PASS', 'native_NX_run_completed': True,
                  'output_directory': str(root), 'master': Path(state['displayed_master']).relative_to(root).as_posix(),
                  'parts': parts, 'source_fingerprint': request['source_fingerprint'],
                  'nx_version': request['nx_version'], 'completed_at': datetime.datetime.now().astimezone().isoformat(),
                  'house_bodies': state['house']['built_solids'], 'house_components': state['house']['component_count'],
                  'height_translation_mm': state['height_plan']['translation_mm'],
                  'surface_validation': state['environment']['surface_validation']}
    except Exception as error:
        result.update(error=str(error), traceback=traceback.format_exc())
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'status': result['status'], 'report': str(report)}))
    if result['status'] != 'PASS':
        raise RuntimeError(result['error'])


if __name__ == '__main__':
    main()
