#!/usr/bin/env python3
"""Pure acceptance controls for the frontend flake repeat launcher."""

from __future__ import annotations

import json
from pathlib import Path
import runpy


ROOT = Path("/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре")
HELPER = ROOT / ".agent/tasks/production-readiness-20260917/support/native_frontend_flake_repeat_hflypi.py"
OUTPUT = ROOT / ".agent/tasks/production-readiness-20260917/evidence/frontend-flake-repeat-hflypi-20260921/helper-controls-v2.json"


def successful_result(number: int) -> dict[str, object]:
    return {
        "repeat": number,
        "exit_code": 0,
        "stopped_reason": None,
        "stdout": "Test Files  2 passed (2)\n      Tests  3 passed (3)\n",
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError("refusing to overwrite helper control evidence")
    namespace = runpy.run_path(str(HELPER))
    classify = namespace["classification"]
    repeats = namespace["REPEATS"]
    good = [successful_result(number) for number in range(1, repeats + 1)]
    identity = {"checked_tracked_blobs": 5720, "mismatch_count": 0}
    checks = {
        "all_five_exact_passes": classify(good, True, identity) == "NOT_REPRODUCED",
        "four_passes_are_not_enough": classify(good[:-1], True, identity) == "INCONCLUSIVE",
        "missing_test_count_is_not_enough": classify(
            [dict(result, stdout="Test Files  2 passed (2)\nTests  2 passed (2)\n") for result in good],
            True,
            identity,
        ) == "INCONCLUSIVE",
        "config_change_is_not_enough": classify(good, False, identity) == "INCONCLUSIVE",
        "identity_mismatch_is_not_enough": classify(good, True, {"checked_tracked_blobs": 5720, "mismatch_count": 1}) == "INCONCLUSIVE",
    }
    OUTPUT.write_text(json.dumps({"checks": checks}, indent=2, sort_keys=True) + "\n")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
