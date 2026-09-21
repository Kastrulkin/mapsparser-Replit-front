#!/usr/bin/env python3
"""Broad frozen backend attempt with inherited macOS network/write denial.

No fixture bodies are rewritten and no integration classes are silently removed.
Database/browser/provider tests may skip or fail in this zero-network lane;
those outcomes remain explicit and are not a production-readiness pass.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import runpy
import shutil
import subprocess
import tempfile
import time

SUPPORT = Path(__file__).resolve().parent
BASE = Path('/private/tmp/localos-readiness-20260921.hfLYPi')
SOURCE = BASE / 'source'
NATIVE = BASE / 'native'
VENV = NATIVE / 'venv/bin/python'
EVIDENCE = NATIVE / 'evidence'
GUARD_HASH = '07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150'
INVENTORY_HASH = 'e49b7a637b77af2c437d7fc2a7f9190c81f81c82da2d1a22fbcab13ed1dedb52'
MARKER = 'HFLYPI_SANDBOX_RESULT='


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sandbox_policy(writable):
    if writable.resolve(strict=True) != writable or writable.is_symlink() or not writable.is_dir():
        raise ValueError('noncanonical writable root')
    if writable.parent.parent != BASE or not writable.parent.name.startswith('sandbox-aggregate-') or writable.name != 'writable':
        raise ValueError('writable root is not an owned run directory')
    # The parent is a trusted controller; every descendant inherits these denials.
    # This is not a hostile-code security boundary against kernel vulnerabilities.
    return '\n'.join([
        '(version 1)', '(allow default)', '(deny network*)',
        '(deny file-write*)',
        '(deny file-read-data (subpath "/Users") (subpath "/private/tmp"))',
        *['(allow file-read-data (subpath ' + json.dumps(str(path), ensure_ascii=False) + '))'
          for path in ('/System', '/usr', '/bin', '/sbin', '/Library/Frameworks/Python.framework',
                       '/Library/Apple', '/private/etc', '/dev', SOURCE, NATIVE / 'venv', SUPPORT, writable)],
        '(allow file-write* (subpath ' + json.dumps(str(writable), ensure_ascii=False) + '))',
        '(allow file-write* (literal "/dev/null"))',
    ])


def probe_source(writable, forbidden):
    return """
import errno, json, os, socket, subprocess, sys
from pathlib import Path
writable = Path(%r)
forbidden = Path(%r)
checks = {}
def denied(name, operation):
    try:
        operation()
    except OSError:
        checks[name] = sys.exception().errno in {errno.EPERM, errno.EACCES}
    else:
        checks[name] = False
denied('read-outside-allowlist', lambda: forbidden.read_bytes())
denied('user-workspace-read-denied', lambda: Path(%r).read_bytes())
denied('write-outside-owned', lambda: forbidden.write_text('unexpected'))
denied('source-write', lambda: Path(%r).write_text('unexpected'))
(writable / 'allowed').write_text('owned probe')
checks['owned-write'] = (writable / 'allowed').read_text() == 'owned probe'
(writable / 'escape').symlink_to(forbidden)
denied('symlink-write', lambda: (writable / 'escape').write_text('unexpected'))
s = socket.socket()
checks['raw-tcp-denied'] = s.connect_ex(('127.0.0.1', 35418)) in {errno.EPERM, errno.EACCES}
s.close()
s = socket.socket(socket.AF_UNIX)
denied('docker-unix-denied', lambda: s.connect('/Users/alexdemyanov/.docker/run/docker.sock'))
s.close()
child = subprocess.run(['/bin/sh', '-c', '/usr/bin/touch "$1"', 'probe', str(forbidden)], capture_output=True)
checks['shell-write-denied'] = child.returncode != 0 and b'Operation not permitted' in child.stderr
child = subprocess.run(['/usr/bin/nc', '-v', '-z', '-w', '1', '127.0.0.1', '35418'], capture_output=True)
checks['native-child-network-denied'] = child.returncode != 0 and b'Operation not permitted' in child.stderr
print(json.dumps(checks, sort_keys=True))
raise SystemExit(0 if all(checks.values()) else 1)
""" % (
        str(writable), str(forbidden), str(SUPPORT.parents[3] / 'README.md'), str(SOURCE / '.sandbox-write-probe-must-not-exist'))


def pytest_source(writable):
    return """
import json, os, sys
import pytest
from _pytest.subtests import SubtestReport
state = {'collected': [], 'reports': [], 'collection_errors': [], 'subtests': []}
class Results:
    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item, call):
        outcome = yield
        report = outcome.get_result()
        if report.failed and call.excinfo is not None:
            error = call.excinfo.value
            frames = []
            for frame in call.excinfo.traceback:
                name = str(frame.path)
                for root, label in [(os.getcwd(), 'source'), (sys.prefix, 'venv')]:
                    if name.startswith(root + '/'):
                        frames.append({'path': label + name[len(root):], 'line': frame.lineno + 1})
                        break
            report.hflypi_failure = {'exception_type': type(error).__name__,
                                     'errno': error.errno if isinstance(error, OSError) and isinstance(error.errno, int) else None,
                                     'frames': frames[-12:]}
    def pytest_collection_finish(self, session):
        state['collected'] = [item.nodeid for item in session.items]
    def pytest_collectreport(self, report):
        if report.failed:
            state['collection_errors'].append(report.nodeid)
    def pytest_runtest_logreport(self, report):
        target = state['subtests'] if isinstance(report, SubtestReport) else state['reports']
        target.append({'nodeid': report.nodeid, 'when': report.when, 'outcome': report.outcome,
                       'xfail': bool(getattr(report, 'wasxfail', False)),
                       'failure': getattr(report, 'hflypi_failure', None)})
result = pytest.main(['tests', '-q', '-p', 'no:cacheprovider', '--tb=no', '--show-capture=no',
                      '--basetemp', %r], plugins=[Results()])
state['pytest_return'] = int(result)
print(%r + json.dumps(state, sort_keys=True))
raise SystemExit(result)
""" % (str(writable / 'pytest'), MARKER)


def parse_callback(capture, expected, inventory):
    rows = [row for row in capture['stdout'].splitlines() if row.startswith(MARKER)]
    if len(rows) != 1:
        raise RuntimeError('missing or ambiguous callback')
    callback = json.loads(rows[0][len(MARKER):])
    observed = callback['collected']
    if observed != expected:
        inventory['timestamp_normalizations'](expected, observed)
    if len(observed) != 5481 or len(set(observed)) != 5481:
        raise RuntimeError('not the complete frozen collection')
    outcomes = {}
    for row in callback['reports']:
        if row['nodeid'] not in observed:
            raise RuntimeError('report is outside the collection')
        label = row['when'] + '_' + row['outcome']
        outcomes[label] = outcomes.get(label, 0) + 1
    callback['counts'] = outcomes
    return callback


def capture_metadata(capture):
    return {**{key: capture[key] for key in ('exit_code', 'duration_seconds', 'timed_out', 'stopped_reason')},
            **{name: {'bytes': len(capture[name].encode()),
                      'sha256': hashlib.sha256(capture[name].encode()).hexdigest()}
               for name in ('stdout', 'stderr')}}


def aggregate_phase(capture, callback):
    if capture['timed_out'] or capture['exit_code'] != 0 or callback['collection_errors']:
        return 'test_failures'
    reports = callback['reports']
    passed = [row['nodeid'] for row in reports if row['when'] == 'call' and row['outcome'] == 'passed' and not row['xfail']]
    failures = [row for row in reports + callback['subtests'] if row['outcome'] != 'passed' or row['xfail']]
    if failures or len(passed) != 5481 or set(passed) != set(callback['collected']):
        return 'completed_with_nonpasses'
    return 'passed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--controls-only', action='store_true')
    args = parser.parse_args()
    if re.fullmatch(r'v[1-9][0-9]*', args.attempt) is None:
        raise ValueError('invalid attempt')
    kind = 'controls' if args.controls_only else 'full'
    destination = EVIDENCE / f'native-sandbox-{kind}-{args.attempt}.json'
    if destination.exists() or destination.is_symlink():
        raise RuntimeError('evidence path already exists')
    if platform.machine() != 'arm64' or shutil.disk_usage(BASE).free < 5 * 1024**3:
        raise RuntimeError('ARM64 and 5 GiB free are required')
    guard = runpy.run_path(str(SUPPORT / 'native_guard_checks_hflypi.py'))
    shared = runpy.run_path(str(SUPPORT / 'native_tc_one_hflypi.py'))
    inventory = runpy.run_path(str(SUPPORT / 'native_fixture_inventory_hflypi.py'))
    guard['verify_endpoints']()
    if digest(SOURCE / 'src/sitecustomize.py') != GUARD_HASH:
        raise RuntimeError('default guard hash mismatch')
    if digest(EVIDENCE / 'native-fixture-inventory-v4.json') != INVENTORY_HASH:
        raise RuntimeError('fixture inventory hash mismatch')
    started = time.monotonic()
    owned = Path(tempfile.mkdtemp(prefix='sandbox-aggregate-', dir=BASE))
    writable = owned / 'writable'
    writable.mkdir(mode=0o700)
    forbidden = owned / 'read-write-canary'
    forbidden.write_text('synthetic unchanged canary')
    policy = sandbox_policy(writable)
    report = {'kind': kind, 'attempt': args.attempt, 'source_commit': guard['COMMIT'],
              'owned_directory': str(owned), 'policy': policy,
              'helper_sha256': digest(Path(__file__)), 'phase': 'preflight',
              'inventory_sha256': INVENTORY_HASH, 'guard_sha256': GUARD_HASH,
              'scope': 'Whole frozen 5481-node attempt. Network denied even for local DB/Docker. No integration pass implied.'}
    environment = guard['environment'](GUARD_HASH)
    environment.pop('LOCALOS_HFLYPI_PROBE_DSN', None)
    environment.update({'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'TMPDIR': str(writable),
                        'DATABASE_URL': 'postgresql+psycopg2://metadata_only@127.0.0.1:1/localos_metadata_only'})
    try:
        report['frozen_blobs_before'] = guard['verify_frozen_source']()
        prefix = ['/usr/bin/sandbox-exec', '-p', policy, '/usr/bin/arch', '-arm64', str(VENV), '-B']
        # Probe without sitecustomize so denial proves the OS policy, not monkeypatches.
        probes = shared['result'](prefix + ['-I', '-c', probe_source(writable, forbidden)],
                                  {'PATH': '/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'}, 30, time.monotonic() + 30)
        report['controls'] = probes
        if probes['exit_code'] != 0 or probes['timed_out']:
            raise RuntimeError('OS sandbox controls failed')
        report['control_checks'] = json.loads(probes['stdout'])
        if not args.controls_only:
            expected = inventory['nodeids_from_collection'](inventory['COLLECTION'])
            report['phase'] = 'running'
            capture = shared['result'](prefix + ['-c', pytest_source(writable)], environment, 900, time.monotonic() + 900)
            report['test'] = capture_metadata(capture)
            callback = parse_callback(capture, expected, inventory)
            report['callback'] = callback
            report['phase'] = aggregate_phase(capture, callback)
        else:
            report['phase'] = 'controls_passed'
    except BaseException:
        import sys
        report['phase'] = 'harness_failed'
        report['error_type'] = type(sys.exception()).__name__
    finally:
        report['frozen_blobs_after'] = guard['verify_frozen_source']()
        report['guard_sha256_after'] = digest(SOURCE / 'src/sitecustomize.py')
        report['canary_unchanged'] = forbidden.read_text() == 'synthetic unchanged canary'
        report['forbidden_source_path_absent'] = not (SOURCE / '.sandbox-write-probe-must-not-exist').exists()
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        report['free_bytes_after'] = shutil.disk_usage(BASE).free
        if report['frozen_blobs_after'] != 5720 or report['guard_sha256_after'] != GUARD_HASH or not report['canary_unchanged'] or not report['forbidden_source_path_absent']:
            report['phase'] = 'postcheck_failed'
        # Keep bounded owned temp artifacts for failed-test diagnosis, no destructive cleanup.
        shared['write_exclusive'](destination, report)
    print(json.dumps({'path': str(destination), 'phase': report['phase'], 'duration_seconds': report['duration_seconds']}))
    return 0 if report['phase'] in {'passed', 'controls_passed'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
