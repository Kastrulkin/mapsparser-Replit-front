"""Verify standalone integrity script without heredoc temporary-file dependency."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path('/private/tmp/localos-current-full-v10.BYwJr6')
SPEC = importlib.util.spec_from_file_location('frozen_v10', ROOT / 'run_current_full_v10.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
sys.path[:0] = [str(ROOT), str(RUN.PSUTIL)]
PREP = ROOT / 'writable/dist-fix'
OUTPUT = ROOT / 'evidence/dist-fix-v1.json'
EXPECTED = {
    'clean/scripts/verify_frontend_dist_integrity.sh': 'a351b5cc083697d4953d6d1e9d59b88e0b8c8e5353077912f3dd767e3e059741',
    'clean/tests/test_frontend_dist_integrity.py': '1e965bcafe9e1e974f68ce47c6601b2fa30dcf7c1b5a4e934241f6b79a5c5817',
    'patched/scripts/verify_frontend_dist_integrity.sh': 'd2c7af2e0ae6792c90ed8f03c87a332985e4de0a54ed27f2743dea9ecca63a1c',
    'patched/tests/test_frontend_dist_integrity.py': '54406cd59ee744ec7f260b9fb50257cd2f163455eb93580369b41cbd39729f8f',
}
CHILD = '''import json,pytest
result={'nodes':[],'reports':[],'errors':[]}
class H:
 def pytest_collection_finish(self,session):result['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed:result['errors'].append(report.nodeid)
 @pytest.hookimpl(hookwrapper=True)
 def pytest_runtest_makereport(self,item,call):
  outcome=yield;report=outcome.get_result()
  if report.failed and call.excinfo is not None:
   report.safe_failure={'type':type(call.excinfo.value).__name__,'here_document_denial':'cannot create temp file for here document: Operation not permitted' in str(call.excinfo.value)}
 def pytest_runtest_logreport(self,report):result['reports'].append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'xfail':bool(getattr(report,'wasxfail',False)),'failure':getattr(report,'safe_failure',None)})
r=pytest.main(%r,plugins=[H()]);result['return_code']=r
print('DIST_FIX_RESULT='+json.dumps(result,sort_keys=True));raise SystemExit(r)
'''


def hashes():
    return {name: RUN.sha(PREP / name) for name in EXPECTED}


def execute(name, result):
    args = [str(PREP / name / 'tests/test_frontend_dist_integrity.py'), '-c', str(RUN.SOURCE / 'pytest.ini'), '-q', '-p', 'no:cacheprovider', '--tb=no', '--show-capture=no', '--basetemp', str(PREP / ('basetemp-' + name))]
    capture, output = RUN.invoke(CHILD % args, 60)
    item = {'capture': capture}
    result['runs'][name] = item
    rows = [line[len('DIST_FIX_RESULT='):] for line in output.splitlines() if line.startswith('DIST_FIX_RESULT=')]
    RUN.require(len(rows) == 1, 'callback')
    data = json.loads(rows[0]); item['data'] = data
    RUN.require(capture['exit_code'] == data['return_code'] and capture['stopped_reason'] is None, 'exit')
    RUN.require(not any(row['truncated'] for row in capture['streams'].values()), 'truncation')
    RUN.require(not data['errors'] and len(data['nodes']) == len(set(data['nodes'])) == 2, 'collection')
    expected = Counter((node, stage) for node in data['nodes'] for stage in ('setup', 'call', 'teardown'))
    RUN.require(Counter((row['nodeid'], row['when']) for row in data['reports']) == expected, 'stages')
    RUN.require(not any(row['xfail'] for row in data['reports']), 'xfail')
    return data


result = {'status': 'failed', 'source_ref': RUN.SOURCE_REF, 'runs': {}, 'input_hashes': EXPECTED}
RUN.require(not OUTPUT.exists(), 'exclusive_output')
try:
    RUN.require(RUN.sha(ROOT / 'run_current_full_v10.py') == '93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4', 'runner_drift')
    RUN.require(RUN.sha(RUN.POLICY) == RUN.POLICY_SHA and RUN.sha(ROOT / 'owned_processes.py') == RUN.HELPER_SHA, 'policy_helper_drift')
    RUN.require(hashes() == EXPECTED, 'input_drift')
    before = RUN.manifest()
    controls, output = RUN.invoke(RUN.CONTROL, 30)
    result['controls'] = {'capture': controls, 'checks': json.loads(output)}
    RUN.require(controls['exit_code'] == 0 and controls['stopped_reason'] is None, 'controls')
    red = execute('clean', result)
    failed = [row for row in red['reports'] if row['outcome'] != 'passed']
    RUN.require(red['return_code'] == 1 and len(failed) == 1, 'red_shape')
    RUN.require(failed[0]['when'] == 'call' and failed[0]['nodeid'].endswith('::test_integrity_check_accepts_complete_dynamic_import') and failed[0]['failure'] == {'type':'AssertionError','here_document_denial':True}, 'red_cause')
    green = execute('patched', result)
    RUN.require(green['return_code'] == 0 and all(row['outcome'] == 'passed' for row in green['reports']), 'green_nonpass')
    RUN.require(hashes() == EXPECTED and RUN.manifest() == before, 'source_drift')
    result['source_inputs_unchanged'] = True
    result['status'] = 'passed'
except BaseException:
    result['error_type'] = type(sys.exception()).__name__
finally:
    RUN.put(OUTPUT, result)
print(json.dumps({'status': result['status']}))
raise SystemExit(0 if result['status'] == 'passed' else 1)
