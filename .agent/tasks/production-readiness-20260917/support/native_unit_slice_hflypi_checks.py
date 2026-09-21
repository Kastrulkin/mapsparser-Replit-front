#!/usr/bin/env python3
"""Pure parser controls for ``native_unit_slice_hflypi.py``; no pytest run."""

from __future__ import annotations

import json
from pathlib import Path
import runpy


SUPPORT = Path(__file__).resolve().parent
def payload(modules: dict[str, int], skipped: int = 0) -> dict[str, object]:
    nodeids = [f"{module}::synthetic_{index}" for module, count in modules.items() for index in range(count)]
    total = sum(modules.values())
    state = {
        "collected": total, "passed": total - skipped, "failed": 0,
        "skipped": skipped, "xfailed": 0, "setup_failed": 0,
        "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0,
        "nodeids": nodeids,
    }
    return {"exit_code": 0, "timed_out": False, "stdout": "HFLYPI_TC_ONE_RESULT=" + json.dumps(state)}


def rejected(action) -> None:
    try:
        action()
    except RuntimeError:
        return
    raise AssertionError("invalid pure-unit result accepted")


def main() -> int:
    helper = runpy.run_path(str(SUPPORT / "native_tc_one_hflypi.py"))
    unit = runpy.run_path(str(SUPPORT / "native_unit_slice_hflypi.py"))
    profiles = unit["PROFILES"]
    assert set(profiles) == {"card-growth-v1", "policy-content-v1"}
    assert profiles["card-growth-v1"]["modules"] == {"tests/test_card_growth_copy_contract.py": 200}
    assert profiles["policy-content-v1"]["modules"] == {
        "tests/test_founder_outreach_campaigns.py": 174,
        "tests/test_legacy_agent_approval_policy.py": 69,
        "tests/test_content_plan_generation.py": 67,
        "tests/test_agent_template_validation_fixtures.py": 54,
    }
    for selected in profiles.values():
        modules = selected["modules"]
        profile = {"targets": list(modules), "count": sum(modules.values())}
        positive = helper["parse_test"](payload(modules), profile)
        assert unit["require_module_counts"](positive, modules) == modules
        rejected(lambda: helper["parse_test"](payload(modules, 1), profile))
        rejected(lambda: unit["require_module_counts"]({"nodeids": []}, modules))
        changed_nodes = list(positive["nodeids"])
        changed_nodes[0] = "tests/test_foreign.py::synthetic_other"
        rejected(lambda: unit["require_module_counts"]({"nodeids": changed_nodes}, modules))
        if len(modules) > 1:
            changed_nodes[0] = list(modules)[1] + "::synthetic_extra"
            rejected(lambda: unit["require_module_counts"]({"nodeids": changed_nodes}, modules))
        compile(helper["plugin_source"](profile["targets"]), "<reviewed-unit-runner>", "exec")
    print("native unit profiles: exact 200/364-module inventories and negative gates passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
