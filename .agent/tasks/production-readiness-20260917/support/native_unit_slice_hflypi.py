#!/usr/bin/env python3
"""Run the reviewed hfLYPi pure-unit card-growth slice after explicit review.

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
TARGET = "tests/test_card_growth_copy_contract.py"
PROFILE = {"target": TARGET, "count": 200}
MIN_START = 5 * 1024**3
MAX_RUNTIME = 90


def valid_attempt(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=valid_attempt)
    values = parser.parse_args()
    destination = EVIDENCE / f"native-unit-card-growth-{values.attempt}.json"
    output: dict[str, object] = {
        "attempt": values.attempt,
        "target": TARGET,
        "expected_count": PROFILE["count"],
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
            ["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", shared["plugin_source"](TARGET)],
            environment,
            MAX_RUNTIME,
            started + MAX_RUNTIME,
        )
        output["test"] = capture
        output["callbacks"] = shared["parse_test"](capture, PROFILE)
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
