#!/usr/bin/env python3
"""Pure parser controls for ``native_unit_slice_hflypi.py``; no pytest run."""

from __future__ import annotations

import json
from pathlib import Path
import runpy


SUPPORT = Path(__file__).resolve().parent
TARGET = "tests/test_card_growth_copy_contract.py"
PROFILE = {"target": TARGET, "count": 200}


def payload(skipped: int) -> dict[str, object]:
    nodeids = [f"{TARGET}::synthetic_{index}" for index in range(200)]
    state = {
        "collected": 200, "passed": 200 - skipped, "failed": 0,
        "skipped": skipped, "xfailed": 0, "setup_failed": 0,
        "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0,
        "nodeids": nodeids,
    }
    return {"exit_code": 0, "timed_out": False, "stdout": "HFLYPI_TC_ONE_RESULT=" + json.dumps(state)}


def main() -> int:
    helper = runpy.run_path(str(SUPPORT / "native_tc_one_hflypi.py"))
    positive = helper["parse_test"](payload(0), PROFILE)
    if positive.get("passed") != 200:
        raise RuntimeError("positive parser control failed")
    try:
        helper["parse_test"](payload(1), PROFILE)
    except RuntimeError:
        return 0
    raise RuntimeError("negative skip parser control was accepted")


if __name__ == "__main__":
    raise SystemExit(main())
