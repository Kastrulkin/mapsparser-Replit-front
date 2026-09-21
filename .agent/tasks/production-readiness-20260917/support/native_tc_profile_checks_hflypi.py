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
                 "PARENT_DATABASE_PROFILES": frozenset({"client-info-v1", "capabilities-phase1-v1"}),
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
    for mode in ("client-info-v1", "capabilities-phase1-v1"):
        environment["LOCALOS_HFLYPI_TC_MODE"] = mode
        bind(12345)
        assert validated[-1] == {"host": "127.0.0.1", "port": "12345", "dbname": "test", "user": "test", "password": "test"}
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
    assert events == ["parent_database_bound", "parent_database_unbound"] * 2
    environment["LOCALOS_HFLYPI_TC_MODE"] = "card-growth-v1"
    bind(12345)
    assert "DATABASE_URL" not in environment and len(validated) == 2


def check_adapter_profile_bindings() -> None:
    source = Path(__file__).with_name("native_tc_adapter_hflypi.py")
    tree = ast.parse(source.read_text())
    assignments = {
        target.id: node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id in {"PROFILE_PREFIXES", "PARENT_DATABASE_PROFILES"}
    }
    assert ast.literal_eval(assignments["PROFILE_PREFIXES"]) == {
        "card-growth-v1": "native-tc-one",
        "client-info-v1": "native-tc-client-info",
        "capabilities-phase1-v1": "native-tc-capabilities-phase1",
    }
    parent_profiles = assignments["PARENT_DATABASE_PROFILES"]
    assert isinstance(parent_profiles, ast.Call) and len(parent_profiles.args) == 1
    assert ast.literal_eval(parent_profiles.args[0]) == {"client-info-v1", "capabilities-phase1-v1"}


def fixture_nodeids() -> list[str]:
    source = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source/tests/test_capabilities_api_phase1.py")
    tree = ast.parse(source.read_text())
    return [
        "tests/test_capabilities_api_phase1.py::" + node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        and any(argument.arg == "capabilities_client" for argument in node.args.args)
    ]


def sitecustomize_modes() -> set[str]:
    source = Path(__file__).with_name("native_hflypi_sitecustomize.py")
    tree = ast.parse(source.read_text())
    modes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            values = {value.value for value in node.elts if isinstance(value, ast.Constant) and isinstance(value.value, str)}
            if {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1"}.issubset(values):
                modes.update(values)
    return modes


def check_relay_budgets() -> None:
    source = Path(__file__).with_name("native_tc_relay_hflypi.py")
    tree = ast.parse(source.read_text())
    assignments = [node for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PROFILE_CONNECTION_BUDGETS" for target in node.targets)]
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "connection_budget"]
    assert len(assignments) == 1 and len(functions) == 1
    budgets = ast.literal_eval(assignments[0].value)
    assert budgets == {"card-growth-v1": 32, "client-info-v1": 32, "capabilities-phase1-v1": 1024}
    namespace = {"MAX_CONNECTIONS": 32, "PROFILE_CONNECTION_BUDGETS": budgets}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)
    budget = namespace["connection_budget"]
    assert budget("") == 32
    assert budget("card-growth-v1") == 32
    assert budget("client-info-v1") == 32
    assert budget("capabilities-phase1-v1") == 1024
    for foreign in ("unknown", "capabilities-phase1-v2"):
        try:
            budget(foreign)
        except PermissionError:
            pass
        else:
            raise AssertionError("foreign relay profile received a budget")


def check_relay_evidence_bounds(namespace) -> None:
    validate = namespace["relay_evidence"]

    def final(connections: int, budget: int) -> dict:
        return {
            "connections": connections,
            "connection_budget": budget,
            "active": 0,
            "rejections": 0,
            "failures": [],
            "exec_results": [{} for _ in range(connections)],
        }

    assert validate("card-growth-v1", final(2, 32))[0] == 2
    assert validate("capabilities-phase1-v1", final(171, 1024))[0] == 171
    for candidate in (final(170, 1024), final(1025, 1024), final(171, 32)):
        try:
            validate("capabilities-phase1-v1", candidate)
        except RuntimeError:
            pass
        else:
            raise AssertionError("capabilities relay evidence outside its literal bounds was accepted")


def main() -> None:
    check_parent_database()
    check_adapter_profile_bindings()
    check_relay_budgets()
    namespace = runpy.run_path(str(Path(__file__).with_name("native_tc_one_hflypi.py")))
    profiles = namespace["PROFILES"]
    parse = namespace["parse_test"]
    check_relay_evidence_bounds(namespace)
    assert set(profiles) == {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1"}
    assert profiles["card-growth-v1"]["count"] == 1
    assert profiles["client-info-v1"] == {"target": "tests/test_client_info_gate.py", "count": 8, "prefix": "native-tc-client-info"}
    capabilities = profiles["capabilities-phase1-v1"]
    expected_nodeids = fixture_nodeids()
    assert len(expected_nodeids) == 57 and len(set(expected_nodeids)) == 57
    assert capabilities == {
        "targets": expected_nodeids,
        "count": 57,
        "exact_nodeids": True,
        "prefix": "native-tc-capabilities-phase1",
    }
    assert sitecustomize_modes() == {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1"}

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
        targets = profile.get("targets", [profile.get("target")])
        nodeids = targets if profile.get("exact_nodeids") is True else ([targets[0]] if count == 1 else [targets[0] + "::test_case_" + str(index) for index in range(count)])
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
        if profile.get("exact_nodeids") is True:
            denied({**state, "nodeids": ["tests/test_foreign.py::test_other"] + nodeids[1:]}, profile)
            denied({**state, "nodeids": [nodeids[0] + "::foreign_child"] + nodeids[1:]}, profile)
        compile(namespace["plugin_source"](targets), "<reviewed-profile-runner>", "exec")
    for malformed in ([], ["tests/test_capabilities_api_phase1.py::test_ok", 1]):
        try:
            namespace["plugin_source"](malformed)
        except ValueError:
            pass
        else:
            raise AssertionError("malformed target allowlist was accepted")
    print("native TC profiles: 3 exact profiles, parent-DSN lifecycle and negative result gates passed")


if __name__ == "__main__":
    main()
