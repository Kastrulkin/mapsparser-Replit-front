"""Pure result-accounting controls; no Docker, sockets or test bodies."""
import copy
import runpy
from pathlib import Path

MODULE = runpy.run_path(str(Path(__file__).with_name('native_sandbox_aggregate_hflypi.py')))
PHASE = MODULE['aggregate_phase']


def main():
    nodes = [f'tests/synthetic.py::test_{index}' for index in range(5481)]
    good = {'collected': nodes, 'collection_errors': [], 'subtests': [],
            'reports': [{'nodeid': node, 'when': 'call', 'outcome': 'passed', 'xfail': False} for node in nodes]}
    capture = {'exit_code': 0, 'timed_out': False}
    assert PHASE(capture, good) == 'passed'
    for field, value in [('outcome', 'skipped'), ('outcome', 'failed'), ('xfail', True)]:
        changed = copy.deepcopy(good)
        changed['reports'][0][field] = value
        assert PHASE(capture, changed) != 'passed'
    for field, value in [('exit_code', 1), ('timed_out', True)]:
        assert PHASE({**capture, field: value}, good) != 'passed'
    missing = copy.deepcopy(good)
    missing['reports'].pop()
    assert PHASE(capture, missing) != 'passed'
    duplicate = copy.deepcopy(good)
    duplicate['reports'][-1] = duplicate['reports'][0]
    assert PHASE(capture, duplicate) != 'passed'
    for event in ('collection_errors', 'subtests'):
        changed = copy.deepcopy(good)
        changed[event].append('synthetic' if event == 'collection_errors' else {'outcome': 'skipped', 'xfail': False})
        assert PHASE(capture, changed) != 'passed'
    meta = MODULE['capture_metadata']({**capture, 'duration_seconds': 1, 'stopped_reason': None,
                                       'stdout': 'synthetic-sensitive-content', 'stderr': 'synthetic-error'})
    assert 'synthetic-sensitive-content' not in str(meta)
    assert 'synthetic-error' not in str(meta)
    assert meta['stdout']['bytes'] == 27
    print('Sandbox aggregate result controls PASS: nonpasses, timeout, duplicate/missing, subtests, capture omission')


if __name__ == '__main__':
    main()
