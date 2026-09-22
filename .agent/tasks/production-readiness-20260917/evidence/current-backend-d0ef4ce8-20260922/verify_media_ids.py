"""Bounded collection-ID regression under the reviewed offline runner policy."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path('/private/tmp/localos-current-full-v10.BYwJr6')
RUNNER = ROOT / 'run_current_full_v10.py'
SPEC = importlib.util.spec_from_file_location('frozen_full_v10', RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
RUN.require(RUN.sha(RUNNER) == '93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4', 'runner_drift')
RUN.require(RUN.sha(RUN.POLICY) == RUN.POLICY_SHA, 'policy_drift')
RUN.require(RUN.sha(ROOT / 'owned_processes.py') == RUN.HELPER_SHA, 'helper_drift')
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUN.PSUTIL))
FILES = [ROOT / 'writable/media-ids/test_before.py', ROOT / 'writable/media-ids/test_after.py']
HASHES = {str(path): RUN.sha(path) for path in FILES}
RESULT = {'status': 'failed', 'runner_sha256': RUN.sha(RUNNER), 'source_ref': RUN.SOURCE_REF,
          'files': HASHES, 'runs': []}

CHILD = '''import json,sys,time,zipfile,pytest
sys.path.insert(0,%r)
zipfile.time.localtime=lambda *_:time.struct_time((%d,1,1,0,0,0,2,1,-1))
s={'nodes':[],'reports':[],'errors':[]}
class H:
 def pytest_collection_finish(self,session):s['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed:s['errors'].append(report.nodeid)
 def pytest_runtest_logreport(self,report):s['reports'].append([report.nodeid,report.when,report.outcome])
r=pytest.main(%r,plugins=[H()]);s['return_code']=r
print('MEDIA_IDS_RESULT='+json.dumps(s,sort_keys=True));raise SystemExit(r)
'''

def run_one(path, year, collect):
    argv = [str(path), '-c', str(RUN.SOURCE / 'pytest.ini'), '-q', '-p', 'no:cacheprovider',
            '--tb=no', '--show-capture=no']
    if collect:
        argv.append('--collect-only')
    meta, output = RUN.invoke(CHILD % (str(RUN.SOURCE / 'src'), year, argv), 60)
    lines = [line[len('MEDIA_IDS_RESULT='):] for line in output.splitlines() if line.startswith('MEDIA_IDS_RESULT=')]
    RUN.require(len(lines) == 1, 'callback')
    data = json.loads(lines[0])
    RESULT['runs'].append({'file': str(path), 'year': year, 'collect_only': collect, 'capture': meta, 'data': data})
    RUN.require(meta['exit_code'] == 0 and meta['stopped_reason'] is None, 'child_nonpass')
    RUN.require(not data['errors'] and data['return_code'] == 0, 'pytest_nonpass')
    RUN.require(len(data['nodes']) == 13 and len(set(data['nodes'])) == 13, 'node_count')
    return data

try:
    controls, output = RUN.invoke(RUN.CONTROL, 30)
    RESULT['controls'] = {'capture': controls, 'checks': json.loads(output)}
    RUN.require(controls['exit_code'] == 0 and controls['stopped_reason'] is None, 'controls')
    red0 = run_one(FILES[0], 2020, True)
    red1 = run_one(FILES[0], 2026, True)
    changed = [index for index, pair in enumerate(zip(red0['nodes'], red1['nodes'])) if pair[0] != pair[1]]
    RUN.require(len(changed) == 2, 'expected_red_id_drift')
    RESULT['red_changed_node_indices'] = changed
    green0 = run_one(FILES[1], 2020, True)
    green1 = run_one(FILES[1], 2026, True)
    RUN.require(green0['nodes'] == green1['nodes'], 'green_id_drift')
    RUN.require(any(node.endswith('[docx]') for node in green0['nodes']) and any(node.endswith('[xlsx]') for node in green0['nodes']), 'semantic_ids')
    tested = run_one(FILES[1], 2026, False)
    RUN.require(tested['nodes'] == green1['nodes'], 'execution_id_drift')
    RUN.require(len(tested['reports']) == 39 and all(row[2] == 'passed' for row in tested['reports']), 'stage_nonpass')
    RUN.require(HASHES == {str(path): RUN.sha(path) for path in FILES}, 'file_drift')
    RESULT['status'] = 'passed'
except BaseException:
    RESULT['error_type'] = type(sys.exc_info()[1]).__name__
finally:
    RUN.put(ROOT / 'evidence/media-ids-regression.json', RESULT)
print(json.dumps({'status': RESULT['status'], 'runs': len(RESULT['runs'])}))
raise SystemExit(0 if RESULT['status'] == 'passed' else 1)
