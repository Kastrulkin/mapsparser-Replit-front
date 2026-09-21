#!/usr/bin/env python3
"""Pure harness checks for native_hflypi child environment propagation.

This parses and executes only helper AST nodes.  It does not import the guard,
start a child, contact Docker, open a socket, or load product code.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from types import SimpleNamespace


SUPPORT = Path(__file__).resolve().parent
GUARD = SUPPORT / "native_hflypi_sitecustomize.py"
SOURCE_ROOT = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source")
HASH = "a" * 64


def _helpers() -> dict[str, object]:
    tree = ast.parse(GUARD.read_text(encoding="utf-8"), filename=str(GUARD))
    names = {"_deny", "_child_kind", "_child_environment", "_safe_container_kwargs", "_patch_subprocess"}
    body = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace: dict[str, object] = {
        "os": os,
        "hashlib": hashlib,
        "Path": Path,
        "re": re,
        "subprocess": SimpleNamespace(Popen=None),
        "DOCKER_SOCKET": "/private/tmp/hflypi/docker.sock",
        "FROZEN_SOURCE_ROOT": SOURCE_ROOT,
        "PARENT_SESSION_ENV": "LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID",
        "TESTCONTAINERS_NETWORK_ENV": "LOCALOS_HFLYPI_TESTCONTAINERS_NETWORK",
        "TESTCONTAINERS_NETWORK": "localos-readiness-hflypi_internal",
        "GUARD_HASH_ENVIRONMENTS": (
            "LOCALOS_READINESS_ENDPOINT_GUARD_SHA256",
            "LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256",
            "LOCALOS_AGENT_FINANCE_UNTRUSTED_ROWS_GUARD_SHA256",
            "LOCALOS_VIEWER_MUTATION_GUARD_SHA256",
            "LOCALOS_SOCIAL_VIEWER_GUARD_SHA256",
        ),
        "LIBPQ_OVERRIDE_ENVIRONMENTS": ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS"),
    }
    module = ast.Module(body=body, type_ignores=[])
    exec(compile(module, str(GUARD), "exec"), namespace)
    return namespace


def _denied(action) -> None:
    try:
        action()
    except PermissionError:
        return
    raise AssertionError("guard unexpectedly permitted the case")


def _assertion_fails(action) -> None:
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("pre-patch fixture unexpectedly met the guarded assertion")


def _assert_guarded(call: dict[str, object], source_root: Path) -> None:
    environment = call["keywords"]["env"]
    assert isinstance(environment, dict)
    assert environment["PYTHONPATH"] == f"{source_root}/src:{source_root}"
    assert environment["TESTCONTAINERS_HOST_OVERRIDE"] == "127.0.0.1"


def main() -> int:
    helpers = _helpers()
    child_environment = helpers["_child_environment"]
    child_kind = helpers["_child_kind"]
    safe_container_kwargs = helpers["_safe_container_kwargs"]
    assert callable(child_environment)
    assert callable(child_kind)
    assert callable(safe_container_kwargs)

    stripped = {
        "PATH": "/usr/bin",
        "DATABASE_URL": "postgresql://audit_owner:hflypi-local-only@127.0.0.1:35418/readiness_full_test_hflypi",
        "FLASK_APP": "src.main:app",
        "PYTHONPATH": "/untrusted/src:/untrusted",
    }
    propagated = child_environment(stripped, SOURCE_ROOT, HASH)
    assert propagated["DATABASE_URL"] == stripped["DATABASE_URL"]
    assert propagated["FLASK_APP"] == stripped["FLASK_APP"]
    assert propagated["PYTHONPATH"] == f"{SOURCE_ROOT}/src:{SOURCE_ROOT}"
    assert propagated["LOCALOS_HFLYPI_DOCKER_SOCKET"] == "/private/tmp/hflypi/docker.sock"
    assert propagated["DOCKER_HOST"] == "unix:///private/tmp/hflypi/docker.sock"
    assert propagated["TESTCONTAINERS_RYUK_DISABLED"] == "true"
    assert propagated["TESTCONTAINERS_HOST_OVERRIDE"] == "127.0.0.1"
    assert propagated["LOCALOS_HFLYPI_TESTCONTAINERS_NETWORK"] == "localos-readiness-hflypi_internal"
    assert propagated["PYTHONDONTWRITEBYTECODE"] == "1"
    assert propagated["PYTHONNOUSERSITE"] == "1"
    assert propagated["LOCALOS_HFLYPI_EXPECTED_GUARD_SHA256"] == HASH
    for key in helpers["GUARD_HASH_ENVIRONMENTS"]:
        assert propagated[key] == HASH

    _denied(lambda: child_environment({"TESTCONTAINERS_HOST_OVERRIDE": "localhost"}, SOURCE_ROOT, HASH))
    _denied(lambda: child_environment({"DOCKER_HOST": "tcp://127.0.0.1:2375"}, SOURCE_ROOT, HASH))
    _denied(lambda: child_environment({"LOCALOS_READINESS_ENDPOINT_GUARD_SHA256": "b" * 64}, SOURCE_ROOT, HASH))
    _denied(lambda: child_environment({"PGOPTIONS": "-c search_path=public"}, SOURCE_ROOT, HASH))
    _denied(lambda: child_kind(["python3", "-I", "-c", "pass"], False))
    _denied(lambda: child_kind(["python3", "-S", "-c", "pass"], False))
    _denied(lambda: child_kind(["python3", "-E", "-c", "pass"], False))
    _denied(lambda: child_kind(["python3", "-BI", "-c", "pass"], False))
    _denied(lambda: child_kind(["python3", "-BS", "-c", "pass"], False))
    _denied(lambda: child_kind(["sh", "-c", "python3 -c pass"], False))
    _denied(lambda: child_kind("python3 -c pass", True))
    assert child_kind("python3", False) == "python"
    _denied(lambda: child_kind("python3 -E -c pass", False))
    assert child_kind(["git", "status"], False) == "other"
    assert child_kind(["node", "script.js"], False) == "other"

    assert safe_container_kwargs({"labels": {"localos.audit": "test"}, "platform": "linux/amd64"})["platform"] == "linux/amd64"
    for key in ("mounts", "volumes", "privileged", "devices", "cap_add", "network_mode", "pid_mode", "ipc_mode", "extra_hosts"):
        _denied(lambda key=key: safe_container_kwargs({key: True}))

    calls: list[dict[str, object]] = []

    def fake_popen(*arguments, **keywords):
        call = {"arguments": arguments, "keywords": keywords}
        calls.append(call)
        return call

    helpers["subprocess"].Popen = fake_popen
    fake_popen(["python3", "-m", "flask"], env=stripped)
    _assertion_fails(lambda: _assert_guarded(calls[-1], SOURCE_ROOT))

    temporary_context = TemporaryDirectory()
    try:
        source_root = (Path(temporary_context.name) / "source").resolve()
        guard_file = source_root / "src" / "sitecustomize.py"
        guard_file.parent.mkdir(parents=True)
        guard_file.write_text("# fake frozen guard\n", encoding="utf-8")
        helpers["FROZEN_SOURCE_ROOT"] = source_root
        helpers["__file__"] = str(guard_file)
        helpers["_patch_subprocess"]()
        guarded = helpers["subprocess"].Popen(["python3", "-m", "flask"], env=stripped)
        _assert_guarded(guarded, source_root)
        guarded_environment = guarded["keywords"]["env"]
        assert guarded_environment["DATABASE_URL"] == stripped["DATABASE_URL"]
        assert guarded_environment["DOCKER_HOST"] == "unix:///private/tmp/hflypi/docker.sock"
        _denied(lambda: helpers["subprocess"].Popen(["python3", "-E", "-c", "pass"], env=stripped))
        _denied(lambda: helpers["subprocess"].Popen(["python3", "-c", "pass"], None, "override", env=stripped))
        _denied(lambda: helpers["subprocess"].Popen(["python3", "-c", "pass"], executable="override", env=stripped))
        _denied(lambda: helpers["subprocess"].Popen(["echo", "safe"], executable="python3", env=stripped))
        _denied(lambda: helpers["subprocess"].Popen(["echo"], -1, "python3", env=stripped))
        string_python = helpers["subprocess"].Popen("python3", env=stripped)
        _assert_guarded(string_python, source_root)
        _denied(lambda: helpers["subprocess"].Popen(["sh", "-c", "python3 -c pass"], env=stripped))
        untouched = helpers["subprocess"].Popen(["git", "status"], env=stripped)
        assert untouched["keywords"]["env"] == stripped
    finally:
        temporary_context.cleanup()
    print("native_hflypi_child_checks: negative_control=expected_unpatched_assertion green=pure_helpers_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
