"""Exercise actual installed pytest report types against the generated callback."""

import ast
import json
from pathlib import Path
import runpy

from _pytest.reports import TestReport
from _pytest.subtests import SubtestReport


SUPPORT = Path(__file__).resolve().parent


def callback_namespace(source):
    tree = ast.parse(source)
    nodes = [node for node in tree.body if (
        isinstance(node, ast.ClassDef) and node.name == 'Results'
        or isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'state' for target in node.targets)
    )]
    namespace = {'SubtestReport': SubtestReport}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<actual-generated-callback>', 'exec'), namespace)
    return namespace


def report(report_type, outcome):
    return report_type(nodeid='tests/test_example.py::test_one', location=('tests/test_example.py', 1, 'test_one'),
                       keywords={}, outcome=outcome, longrepr=None, when='call')


def main():
    helper = runpy.run_path(str(SUPPORT / 'native_tc_one_hflypi.py'))
    namespace = callback_namespace(helper['plugin_source']('tests/test_example.py'))
    callback = namespace['Results']()
    callback.pytest_runtest_logreport(report(TestReport, 'passed'))
    callback.pytest_runtest_logreport(report(SubtestReport, 'passed'))
    callback.pytest_runtest_logreport(report(SubtestReport, 'passed'))
    state = namespace['state']
    assert state['passed'] == 1, 'subtests were counted as collected parent nodes'
    assert state['subtests_passed'] == 2
    state.update(collected=1, nodeids=['tests/test_example.py::test_one'], pytest_exitstatus=0, pytest_return=0)
    profile = {'target': 'tests/test_example.py', 'count': 1}

    def encoded():
        return {'stdout': 'HFLYPI_TC_ONE_RESULT=' + json.dumps(state), 'exit_code': 0, 'timed_out': False}

    assert helper['parse_test'](encoded(), profile)['passed'] == 1
    for outcome, key in [('failed', 'subtests_failed'), ('skipped', 'subtests_skipped')]:
        callback.pytest_runtest_logreport(report(SubtestReport, outcome))
        assert state[key] == 1
        rejected = False
        try:
            helper['parse_test'](encoded(), profile)
        except RuntimeError:
            rejected = True
        assert rejected, 'non-passing subtest was accepted'
        state[key] = 0
    xfailed = report(SubtestReport, 'skipped')
    xfailed.wasxfail = 'synthetic expected failure'
    callback.pytest_runtest_logreport(xfailed)
    assert state['subtests_xfailed'] == 1
    print('actual parent/subtest report accounting and negative acceptance controls passed')


if __name__ == '__main__':
    main()
