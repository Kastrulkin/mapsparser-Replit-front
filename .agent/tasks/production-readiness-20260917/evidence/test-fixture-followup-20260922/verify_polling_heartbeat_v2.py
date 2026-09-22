"""Bounded red/green proof for Telegram-polling heartbeat test isolation."""
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path('/private/tmp/localos-current-full-v10.BYwJr6')
RUNNER = ROOT / 'run_current_full_v10.py'
SPEC = importlib.util.spec_from_file_location('frozen_full_v10', RUNNER)
RUN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUN)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(RUN.PSUTIL))

RUNNER_SHA = '93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4'
POLICY_SHA = 'e41663b03dfe1a0be7b27bb6fcb96abf27d302633464e7a8fd77d86e54d39201'
HELPER_SHA = '4f16b6c343223717dcf3b5bdbf86ff9159594b33fa92d744527891188c4c227b'
PREP = ROOT / 'writable/polling-heartbeat-prep'
BEFORE = PREP / 'test_before.py'
AFTER = PREP / 'test_after.py'
BEFORE_SHA = 'bbc2306b205f597bbfb493da5368483346349b206231b4300038b9940edafde5'
AFTER_SHA = 'e35ae7abc066e24f107b243622dde1b2c0beacfee3370315bcd71e28f0733b67'
WORK = ROOT / 'writable/polling-heartbeat-run-v2'
RESULT = WORK / 'result.json'
MARK = 'POLLING_HEARTBEAT_RESULT='
RED_FUNCTIONS = [
    'test_timeout_is_bounded_and_reported',
    'test_watchdog_exits_on_stale_receiver',
    'test_network_errors_do_not_keep_receiver_healthy',
    'test_unused_transport_does_not_start_restart_watchdog',
]


def write_once(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        while raw:
            raw = raw[os.write(descriptor, raw):]
    finally:
        os.close(descriptor)


def manifest_hash(manifest):
    raw = json.dumps(manifest, separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(raw).hexdigest()


CHILD = '''import json,os,sys,pytest
SOURCE=%r
MARK=%r
sys.path.insert(0, os.path.join(SOURCE, 'src'))
os.chdir(SOURCE)
summary={'nodes': [], 'collection_errors': [], 'reports': []}
class Recorder:
 @pytest.hookimpl(hookwrapper=True)
 def pytest_runtest_makereport(self,item,call):
  outcome=yield
  report=outcome.get_result()
  if report.failed and call.excinfo is not None:
   error=call.excinfo.value
   frame=None
   for entry in call.excinfo.traceback:
    if str(entry.path).endswith('/src/core/telegram_polling.py'):
     frame={'path':'src/core/telegram_polling.py','line':entry.lineno+1}
   report.safe_failure={'exception_type':type(error).__name__, 'errno':getattr(error,'errno',None), 'filename':getattr(error,'filename',None), 'frame':frame}
 def pytest_collection_finish(self,session): summary['nodes']=[item.nodeid for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed: summary['collection_errors'].append(report.nodeid)
 def pytest_runtest_logreport(self,report):
  summary['reports'].append({'nodeid':report.nodeid, 'when':report.when, 'outcome':report.outcome, 'xfail':bool(getattr(report,'wasxfail',False)), 'failure':getattr(report,'safe_failure',None)})
code=pytest.main(%r,plugins=[Recorder()])
summary['return_code']=int(code)
print(MARK+json.dumps(summary,sort_keys=True))
raise SystemExit(code)
'''


def invoke(arguments):
    capture, output = RUN.invoke(CHILD % (str(RUN.SOURCE), MARK, arguments), 90)
    lines = [line[len(MARK):] for line in output.splitlines() if line.startswith(MARK)]
    entry = {'capture': capture, 'callback_count': len(lines)}
    if len(lines) == 1:
        entry['data'] = json.loads(lines[0])
    return entry


def suffixes(rows):
    return [row['nodeid'].rsplit('::', 1)[-1] for row in rows]


def assert_clean_capture(run, label):
    capture = run['capture']
    RUN.require(capture['stopped_reason'] is None, label + '_stopped')
    RUN.require(capture['process_cleanup']['status'] == 'clean', label + '_process_cleanup')
    RUN.require(not any(stream['truncated'] for stream in capture['streams'].values()), label + '_truncated')
    RUN.require(run['callback_count'] == 1, label + '_callback')


def assert_stages(data, expected_nodes, label):
    RUN.require(data['nodes'] == expected_nodes, label + '_nodes')
    RUN.require(not data['collection_errors'], label + '_collection')
    stages = collections.Counter((row['nodeid'], row['when']) for row in data['reports'])
    wanted = collections.Counter((node, when) for node in expected_nodes for when in ('setup', 'call', 'teardown'))
    RUN.require(stages == wanted, label + '_stages')


def main():
    result = {'status': 'diagnostic_failed', 'scope': 'test_only_heartbeat_isolation',
              'source_ref': RUN.SOURCE_REF, 'runs': {}}
    source_before = None
    try:
        RUN.require(RUN.sha(RUNNER) == RUNNER_SHA, 'runner_drift')
        RUN.require(RUN.sha(RUN.POLICY) == POLICY_SHA == RUN.POLICY_SHA, 'policy_drift')
        RUN.require(RUN.sha(ROOT / 'owned_processes.py') == HELPER_SHA == RUN.HELPER_SHA, 'helper_drift')
        RUN.require(RUN.sha(BEFORE) == BEFORE_SHA and RUN.sha(AFTER) == AFTER_SHA, 'prepared_file_drift')
        RUN.require(not WORK.exists() and not WORK.is_symlink(), 'existing_owned_workdir')
        RUN.require(WORK.parent == RUN.WRITABLE, 'workdir_boundary')
        WORK.mkdir(mode=0o700)
        source_before = RUN.manifest()
        result['input_hashes'] = {'runner_sha256': RUNNER_SHA, 'policy_sha256': POLICY_SHA,
                                  'helper_sha256': HELPER_SHA, 'before_sha256': BEFORE_SHA,
                                  'after_sha256': AFTER_SHA, 'source_manifest_sha256': manifest_hash(source_before)}

        controls, control_output = RUN.invoke(RUN.CONTROL, 30)
        result['controls'] = {'capture': controls, 'checks': json.loads(control_output)}
        RUN.require(controls['exit_code'] == 0 and controls['stopped_reason'] is None, 'os_controls')
        RUN.require(controls['process_cleanup']['status'] == 'clean', 'controls_cleanup')

        red_arguments = [str(BEFORE) + '::' + function for function in RED_FUNCTIONS]
        red = invoke([*red_arguments, '-c', str(RUN.SOURCE / 'pytest.ini'), '-q', '-p', 'no:cacheprovider',
                      '--tb=no', '--show-capture=no', '--basetemp', str(WORK / 'red-basetemp')])
        result['runs']['red'] = red
        assert_clean_capture(red, 'red')
        red_data = red['data']
        RUN.require(red['capture']['exit_code'] == 1 and red_data['return_code'] == 1, 'red_exit')
        RUN.require([node.rsplit('::', 1)[-1] for node in red_data['nodes']] == RED_FUNCTIONS, 'red_nodes')
        assert_stages(red_data, red_data['nodes'], 'red')
        RUN.require(all(row['outcome'] == 'passed' for row in red_data['reports'] if row['when'] != 'call'), 'red_setup_teardown')
        RUN.require(not any(row['xfail'] for row in red_data['reports']), 'red_xfail')
        failed = [row for row in red_data['reports'] if row['when'] == 'call' and row['outcome'] == 'failed']
        RUN.require(suffixes(failed) == RED_FUNCTIONS, 'red_failure_nodes')
        RUN.require(len(failed) == 4, 'red_failure_count')
        for row in failed:
            RUN.require(row['failure'] == {'exception_type': 'PermissionError', 'errno': 1,
                                           'filename': '/tmp/localos-telegram-poll.heartbeat',
                                           'frame': {'path': 'src/core/telegram_polling.py', 'line': 27}},
                        'red_failure_shape')
        write_once(WORK / 'red-structured-failures.json', red)

        green = invoke([str(AFTER), '-c', str(RUN.SOURCE / 'pytest.ini'), '-q', '-p', 'no:cacheprovider',
                        '--tb=no', '--show-capture=no', '--basetemp', str(WORK / 'green-basetemp')])
        result['runs']['green'] = green
        assert_clean_capture(green, 'green')
        green_data = green['data']
        RUN.require(green['capture']['exit_code'] == 0 and green_data['return_code'] == 0, 'green_exit')
        RUN.require(len(green_data['nodes']) == 9 and len(set(green_data['nodes'])) == 9, 'green_node_count')
        assert_stages(green_data, green_data['nodes'], 'green')
        RUN.require(all(row['outcome'] == 'passed' and not row['xfail'] for row in green_data['reports']), 'green_nonpass')
        RUN.require(len(green_data['reports']) == 27, 'green_stage_count')

        result['status'] = 'diagnostic_passed'
    except BaseException:
        result['error_type'] = type(sys.exception()).__name__
    finally:
        if source_before is not None:
            source_after = RUN.manifest()
            result['source_manifest_unchanged'] = source_after == source_before
            result['test_hashes_unchanged'] = RUN.sha(BEFORE) == BEFORE_SHA and RUN.sha(AFTER) == AFTER_SHA
            if source_after != source_before or not result['test_hashes_unchanged']:
                result['status'] = 'diagnostic_failed'
                result['error_type'] = 'RuntimeError'
        if WORK.exists() and not RESULT.exists():
            write_once(RESULT, result)
    print(json.dumps({'status': result['status'], 'scope': result['scope'], 'result': str(RESULT)}))
    raise SystemExit(0 if result['status'] == 'diagnostic_passed' else 1)


if __name__ == '__main__':
    main()
