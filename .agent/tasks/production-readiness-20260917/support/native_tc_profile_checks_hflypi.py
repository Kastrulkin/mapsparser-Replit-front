#!/usr/bin/env python3
"""Pure profile/result acceptance checks; no Docker, sockets or test startup."""

import ast
import json
from pathlib import Path
import runpy
from types import SimpleNamespace


def check_parent_database() -> None:
    source = Path(__file__).with_name("native_tc_adapter_hflypi.py")
    names = {"deny", "bind_parent_database", "unbind_parent_database"}
    tree = ast.parse(source.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    environment = {"LOCALOS_HFLYPI_TC_MODE": "client-info-v1", "LOCALOS_HFLYPI_TC_OWNER_PID": "42"}
    validated = []
    events = []
    namespace = {"os": SimpleNamespace(environ=environment, getpid=lambda: 42), "PREFIX": "LOCALOS_HFLYPI_TC_", "_database_url": None,
                 "validate_dsn": lambda parsed: validated.append(parsed), "record": lambda event, **fields: events.append(event)}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    bind, unbind = namespace["bind_parent_database"], namespace["unbind_parent_database"]
    for key, value in (("DATABASE_URL", ""), ("DATABASE_URL", "foreign"), ("LOCALOS_HFLYPI_TC_OWNER_PID", "43")):
        previous = environment.get(key)
        environment[key] = value
        try:
            bind(12345)
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign configuration was replaced")
        assert environment[key] == value and not validated
        if previous is None:
            del environment[key]
        else:
            environment[key] = previous
    def deny_capability(parsed):
        raise PermissionError("synthetic invalid capability")
    namespace["validate_dsn"] = deny_capability
    try:
        bind(12345)
    except PermissionError:
        pass
    else:
        raise AssertionError("invalid capability allowed parent configuration")
    assert "DATABASE_URL" not in environment and namespace["_database_url"] is None
    namespace["validate_dsn"] = lambda parsed: validated.append(parsed)
    bind(12345)
    assert validated == [{"host": "127.0.0.1", "port": "12345", "dbname": "test", "user": "test", "password": "test"}]
    assert environment["DATABASE_URL"] == "postgresql://test:test@127.0.0.1:12345/test"
    environment["DATABASE_URL"] = "changed"
    try:
        unbind()
    except PermissionError:
        pass
    else:
        raise AssertionError("changed configuration was removed")
    assert environment["DATABASE_URL"] == "changed"
    environment["DATABASE_URL"] = namespace["_database_url"]
    unbind()
    assert "DATABASE_URL" not in environment and namespace["_database_url"] is None
    assert events == ["parent_database_bound", "parent_database_unbound"]
    environment["LOCALOS_HFLYPI_TC_MODE"] = "card-growth-v1"
    bind(12345)
    assert "DATABASE_URL" not in environment and len(validated) == 1


def main() -> None:
    check_parent_database()
    namespace = runpy.run_path(str(Path(__file__).with_name("native_tc_one_hflypi.py")))
    profiles = namespace["PROFILES"]
    parse = namespace["parse_test"]
    assert set(profiles) == {"card-growth-v1", "client-info-v1"}
    assert profiles["card-growth-v1"]["count"] == 1
    assert profiles["client-info-v1"] == {"target": "tests/test_client_info_gate.py", "count": 8, "prefix": "native-tc-client-info"}

    def capture(state):
        return {"stdout": "HFLYPI_TC_ONE_RESULT=" + json.dumps(state), "exit_code": 0, "timed_out": False}

    def denied(state, profile):
        try:
            parse(capture(state), profile)
        except RuntimeError:
            return
        raise AssertionError("invalid result was accepted")

    for profile in profiles.values():
        count = profile["count"]
        target = profile["target"]
        nodeids = [target] if count == 1 else [target + "::test_case_" + str(index) for index in range(count)]
        state = {"collected": count, "passed": count, "failed": 0, "skipped": 0, "xfailed": 0, "setup_failed": 0, "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0, "nodeids": nodeids}
        state.update(subtests_passed=0, subtests_failed=0, subtests_skipped=0, subtests_xfailed=0)
        assert parse(capture(state), profile) == state
        for key in ("failed", "skipped", "xfailed", "setup_failed", "call_failed", "pytest_exitstatus", "pytest_return", "subtests_failed", "subtests_skipped", "subtests_xfailed"):
            denied({**state, key: 1}, profile)
        denied({**state, "passed": count - 1}, profile)
        denied({**state, "collected": count + 1}, profile)
        denied({**state, "nodeids": ["tests/test_foreign.py::test_other"] * count}, profile)
        denied({**state, "nodeids": []}, profile)
        if count > 1:
            denied({**state, "nodeids": [nodeids[0]] * count}, profile)
        compile(namespace["plugin_source"](target), "<reviewed-profile-runner>", "exec")
    print("native TC profiles: 2 exact profiles, positive counts and negative result gates passed")


if __name__ == "__main__":
    main()
