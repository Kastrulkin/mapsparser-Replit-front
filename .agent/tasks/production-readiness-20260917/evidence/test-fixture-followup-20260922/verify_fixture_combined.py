"""One-process adjacent regression of the three changed test modules."""
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
OUTPUT = ROOT / 'evidence/fixture-combined-v1.json'
EXPECTED = {
 'writable/dist-fix/patched/tests/test_frontend_dist_integrity.py':'54406cd59ee744ec7f260b9fb50257cd2f163455eb93580369b41cbd39729f8f',
 'writable/dist-fix/patched/scripts/verify_frontend_dist_integrity.sh':'d2c7af2e0ae6792c90ed8f03c87a332985e4de0a54ed27f2743dea9ecca63a1c',
 'writable/polling-heartbeat-prep/test_after_lint.py':'5d11ef067ed35c45d656385d645feee8406dc1fb6d568ecbf4fd7bb33ddfa86a',
 'writable/media-ids/test_after.py':'f33a3106522ffd2df4db5276957b3d26acb870a763904100038b8652e184bfa9',
}
CHILD = '''import json,pytest,sys
from pathlib import Path
source=Path(%r);sys.path.insert(0,str(source/'src'))
r={'nodes':[],'reports':[],'errors':[]}
class H:
 def pytest_collection_modifyitems(self,items):
  for item in items:
   if item.module.__name__=='test_frontend_dist_integrity':item.module.REPO_ROOT=source
 def pytest_collection_finish(self,session):r['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed:r['errors'].append(report.nodeid)
 def pytest_runtest_logreport(self,report):r['reports'].append([report.nodeid,report.when,report.outcome,bool(getattr(report,'wasxfail',False))])
code=pytest.main(%r,plugins=[H()]);r['return_code']=code
print('COMBINED='+json.dumps(r,sort_keys=True));raise SystemExit(code)
'''
result = {'status':'failed','source_ref':RUN.SOURCE_REF,'input_hashes':EXPECTED}
RUN.require(not OUTPUT.exists(), 'exclusive_output')
try:
 RUN.require(RUN.sha(ROOT/'run_current_full_v10.py')=='93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4','runner')
 RUN.require(RUN.sha(RUN.POLICY)==RUN.POLICY_SHA and RUN.sha(ROOT/'owned_processes.py')==RUN.HELPER_SHA,'policy_helper')
 RUN.require(all(RUN.sha(ROOT/name)==value for name,value in EXPECTED.items()),'input_drift')
 before=RUN.manifest()
 controls,output=RUN.invoke(RUN.CONTROL,30)
 result['controls']={'capture':controls,'checks':json.loads(output)}
 RUN.require(controls['exit_code']==0 and controls['stopped_reason'] is None,'controls')
 args=[str(ROOT/name) for name in EXPECTED if name.endswith('.py')]+['-c',str(RUN.SOURCE/'pytest.ini'),'-q','-p','no:cacheprovider','--tb=no','--show-capture=no','--basetemp',str(ROOT/'writable/fixture-combined-v1')]
 capture,output=RUN.invoke(CHILD%(str(RUN.SOURCE),args),120)
 result['capture']=capture
 rows=[line[len('COMBINED='):] for line in output.splitlines() if line.startswith('COMBINED=')]
 RUN.require(len(rows)==1,'callback')
 data=json.loads(rows[0]);result['data']=data
 RUN.require(capture['exit_code']==data['return_code']==0 and capture['stopped_reason'] is None,'exit')
 RUN.require(not any(value['truncated'] for value in capture['streams'].values()),'truncation')
 RUN.require(not data['errors'] and len(data['nodes'])==len(set(data['nodes']))==24,'nodes')
 expected=Counter((node,stage) for node in data['nodes'] for stage in ('setup','call','teardown'))
 RUN.require(Counter((row[0],row[1]) for row in data['reports'])==expected,'stages')
 RUN.require(all(row[2]=='passed' and not row[3] for row in data['reports']),'nonpass')
 RUN.require(RUN.manifest()==before and all(RUN.sha(ROOT/name)==value for name,value in EXPECTED.items()),'source_after')
 result['source_inputs_unchanged']=True;result['status']='passed'
except BaseException:
 result['error_type']=type(sys.exception()).__name__
finally:
 RUN.put(OUTPUT,result)
print(json.dumps({'status':result['status']}))
raise SystemExit(0 if result['status']=='passed' else 1)
