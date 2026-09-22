"""Read-only diagnostic of two harmless dist fixtures under unchanged policy."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path('/private/tmp/localos-current-full-v10.BYwJr6')
SPEC = importlib.util.spec_from_file_location('frozen_v10', ROOT / 'run_current_full_v10.py')
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
RUN.require(RUN.sha(ROOT / 'run_current_full_v10.py') == '93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4', 'runner_drift')
RUN.require(RUN.sha(RUN.POLICY) == RUN.POLICY_SHA, 'policy_drift')
RUN.require(RUN.sha(ROOT / 'owned_processes.py') == RUN.HELPER_SHA, 'helper_drift')
sys.path[:0] = [str(ROOT), str(RUN.PSUTIL)]
OUTPUT = ROOT / 'evidence/dist-fixture-matrix-v1.json'
RUN.require(not OUTPUT.exists(), 'exclusive_output')
CHILD = '''import importlib.util,json
from pathlib import Path
source=Path(%r); root=Path(%r)
spec=importlib.util.spec_from_file_location('dist_test',source/'tests/test_frontend_dist_integrity.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
import subprocess
rows=[]
path=root/'complete'
module._write_dist_fixture(path,include_lazy_chunk=True)
for script in (source/'scripts/verify_frontend_dist_integrity.sh', source.parent/'writable/dist-fix/clean/scripts/verify_frontend_dist_integrity.sh'):
 for cwd in (source,source.parent/'writable/dist-fix/clean'):
  result=subprocess.run([str(script),str(path)],cwd=cwd,capture_output=True,text=True,check=False)
  rows.append({'script':str(script),'cwd':str(cwd),'return_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
print(json.dumps(rows))
'''
result = {'status': 'failed', 'source_ref': RUN.SOURCE_REF}
try:
    before = RUN.manifest()
    control, output = RUN.invoke(RUN.CONTROL, 30)
    result['controls'] = {'capture': control, 'checks': json.loads(output)}
    RUN.require(control['exit_code'] == 0 and control['stopped_reason'] is None, 'controls')
    capture, output = RUN.invoke(CHILD % (str(RUN.SOURCE), str(ROOT / 'writable/dist-fixture-matrix-v1')), 30)
    result['capture'] = capture
    RUN.require(capture['exit_code'] == 0 and capture['stopped_reason'] is None, 'capture')
    RUN.require(not any(value['truncated'] for value in capture['streams'].values()), 'truncated')
    result['fixtures'] = json.loads(output)
    RUN.require(RUN.manifest() == before, 'source_drift')
    result['source_unchanged'] = True
    result['status'] = 'diagnostic_complete'
except BaseException:
    result['error_type'] = type(sys.exc_info()[1]).__name__
finally:
    RUN.put(OUTPUT, result)
print(json.dumps({'status': result['status']}))
raise SystemExit(0 if result['status'] == 'diagnostic_complete' else 1)
