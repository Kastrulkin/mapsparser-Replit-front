#!/usr/bin/env python3
"""Run a named, reviewed hfLYPi pure-unit slice after explicit review.

The launcher has no Testcontainers mode, database URL, provider credential or
Docker command.  It reuses only process/result helpers from the reviewed
single-node launcher.  The default frozen guard receives its mandatory local
identity environment and still rejects Testcontainers startup.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import re
import runpy
import shutil
import sys
import time


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
VENV = NATIVE / "venv/bin/python"
INSTALLED_GUARD = SOURCE / "src/sitecustomize.py"
DEFAULT_GUARD_SHA256 = "07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150"
PROFILES = {
    "card-growth-v1": {
        "modules": {"tests/test_card_growth_copy_contract.py": 200},
        "prefix": "native-unit-card-growth", "timeout": 90,
    },
    "policy-content-v1": {
        "modules": {
            "tests/test_founder_outreach_campaigns.py": 174,
            "tests/test_legacy_agent_approval_policy.py": 69,
            "tests/test_content_plan_generation.py": 67,
            "tests/test_agent_template_validation_fixtures.py": 54,
        },
        "prefix": "native-unit-policy-content", "timeout": 120,
    },
}
MIN_START = 5 * 1024**3


def valid_attempt(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def require_module_counts(callback: dict[str, object], modules: dict[str, int]) -> dict[str, int]:
    nodes = callback.get("nodeids")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise RuntimeError("unit slice node inventory is missing")
    observed = {module: sum(node.startswith(module + "::") for node in nodes) for module in modules}
    if observed != modules or sum(observed.values()) != len(nodes):
        raise RuntimeError("unit slice per-module counts differ from the reviewed inventory")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=valid_attempt)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="card-growth-v1")
    values = parser.parse_args()
    selected = PROFILES[values.profile]
    modules = selected["modules"]
    profile = {"targets": list(modules), "count": sum(modules.values())}
    timeout = selected["timeout"]
    destination = EVIDENCE / f"{selected['prefix']}-{values.attempt}.json"
    output: dict[str, object] = {
        "attempt": values.attempt,
        "profile": values.profile,
        "targets": profile["targets"],
        "expected_count": profile["count"],
        "expected_module_counts": modules,
        "phase": "preflight",
    }
    guard_helpers = None
    shared = None
    started = time.monotonic()
    try:
        if platform.machine() != "arm64":
            raise RuntimeError("native unit slice requires arm64 parent")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("attempt evidence path already exists")
        if shutil.disk_usage(BASE).free < MIN_START:
            raise RuntimeError("native unit slice requires 5 GiB free")
        guard_helpers = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
        shared = runpy.run_path(str(SUPPORT / "native_tc_one_hflypi.py"))
        if shared["digest"](INSTALLED_GUARD) != DEFAULT_GUARD_SHA256:
            raise RuntimeError("installed default guard identity differs")
        output["installed_guard_sha256_before"] = DEFAULT_GUARD_SHA256
        output["frozen_blobs_before"] = guard_helpers["verify_frozen_source"]()
        if output["frozen_blobs_before"] != 5720:
            raise RuntimeError("unexpected frozen blob count")
        environment = guard_helpers["environment"](DEFAULT_GUARD_SHA256)
        environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        output["environment_keys"] = sorted(environment)
        output["launcher_sha256"] = shared["digest"](Path(__file__))
        output["shared_helpers_sha256"] = shared["digest"](SUPPORT / "native_tc_one_hflypi.py")
        output["guard_helpers_sha256"] = shared["digest"](SUPPORT / "native_guard_checks_hflypi.py")
        output["phase"] = "test"
        capture = shared["result"](
            ["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", shared["plugin_source"](profile["targets"])],
            environment,
            timeout,
            started + timeout,
        )
        output["test"] = capture
        output["callbacks"] = shared["parse_test"](capture, profile)
        output["observed_module_counts"] = require_module_counts(output["callbacks"], modules)
        output["phase"] = "passed"
    except BaseException:
        error = sys.exception()
        output["phase"] = "failed"
        output["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if guard_helpers is None or shared is None:
                raise RuntimeError("post-verification helpers were not loaded")
            output["installed_guard_sha256_after"] = shared["digest"](INSTALLED_GUARD)
            output["frozen_blobs_after"] = guard_helpers["verify_frozen_source"]()
            if output["installed_guard_sha256_after"] != DEFAULT_GUARD_SHA256:
                raise RuntimeError("installed default guard changed during unit slice")
            if output["frozen_blobs_after"] != 5720:
                raise RuntimeError("frozen source changed during unit slice")
        except BaseException:
            error = sys.exception()
            output["phase"] = "failed"
            output["postverify_error"] = f"{type(error).__name__}: {error}"
        output["duration_seconds"] = round(time.monotonic() - started, 3)
        output["free_bytes_after"] = shutil.disk_usage(BASE).free
        if not destination.exists() and not destination.is_symlink():
            writer = shared["write_exclusive"] if shared is not None else None
            if callable(writer):
                writer(destination, output)
            else:
                raise RuntimeError("could not write exclusive unit-slice evidence")
    return 0 if output.get("phase") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
