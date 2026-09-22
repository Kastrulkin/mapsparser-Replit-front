#!/usr/bin/env python3
"""Bounded offline fixture regression runner; execution is opt-in."""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import time

BASE_ROOT = Path("/private/tmp/localos-current-full-v10.BYwJr6")
SOURCE = BASE_ROOT / "source"
HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "offline_suite_manifest.json"
MANIFEST_SHA = "99eea21488e53c1cd21e2f06e7a8168cb56af45ad679fffb0b3ed976ded51312"
RESULT = HERE / "result.json"
MARK = "OFFLINE_FIXTURES_FINAL_CALLBACK="
AUTHOR_SHA = "21a1a4c9c3337bb516a8c80a354b860d6ba380bf1c4ce0aed4ba0bc5196f782c"
RUNTIME_HASHES = {
    "src/services/outreach_safety_service.py": "b62b88334f854b9acaffec83dc5d504180396928626362fc3275e46b368ff7ac",
    "src/services/outreach_campaign_service.py": "45d7b3c92ab9b17d4c5eb0774a8cb3db8f5ccfce26fe13c26065fadd2630db17",
    "src/yandex_maps_scraper.py": "3a069c6724f31990792d74ff217e19ded6a39e24a0512139e4ea21fe9ef423c5",
}
BASE_RUNNER_SHA = "93c37b843e9ddbadc87f0bab9d7fc9c82685c4a8d9dfe8022e907f9f612d79d4"
POLICY_SHA = "e41663b03dfe1a0be7b27bb6fcb96abf27d302633464e7a8fd77d86e54d39201"
OWNER_SHA = "4f16b6c343223717dcf3b5bdbf86ff9159594b33fa92d744527891188c4c227b"
AUTHOR_NODES = (
    "test_author_gate_serializes_concurrent_reservations_and_uses_moscow_day",
    "test_author_gate_counts_sending_unknown_and_manual_history_but_retry_is_idempotent",
    "test_legacy_activity_contributes_across_all_platform_author_channels",
    "test_confirmed_send_after_later_claim_still_consumes_the_slot",
    "test_author_gate_blocks_cross_channel_second_touch_for_same_profile",
    "test_author_gate_uses_normalized_contact_to_merge_duplicate_profiles",
    "test_author_gate_enforces_total_and_channel_caps",
    "test_author_gate_requires_exact_policy_and_canonical_profile",
    "test_non_author_lane_keeps_legacy_policy_path",
    "test_manual_touch_accepts_user_confirmed_historical_send_with_actual_chronology",
    "test_manual_touch_historical_reply_uses_actual_time_without_provider_proof",
    "test_manual_touch_rejects_invalid_actual_time_before_database_access[naive-must include a timezone]",
    "test_manual_touch_rejects_invalid_actual_time_before_database_access[future-must not be in the future]",
    "test_native_author_dispatch_remains_blocked_without_trusted_reply_window_receipt",
    "test_author_preflight_carries_sender_identity_and_runs_generic_guards_before_receipt",
    "test_preflight_result_carries_the_selected_sender_identity",
    "test_author_dispatch_uses_creator_bridge_fingerprint_and_fails_closed_on_change",
    "test_author_preview_defaults_to_email_and_rejects_unreserved_manual_channels",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value: object, label: str) -> None:
    if not value:
        raise RuntimeError(label)


def regular_within(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    require(resolved.is_relative_to(HERE), "fixture_path_outside_owned_directory")
    require(not path.is_symlink() and resolved.is_file(), "fixture_path_not_regular")
    return resolved


def load_base():
    require(sha(BASE_ROOT / "run_current_full_v10.py") == BASE_RUNNER_SHA, "frozen_runner_drift")
    require(sha(BASE_ROOT / "policy-v10.sb") == POLICY_SHA, "frozen_policy_drift")
    require(sha(BASE_ROOT / "owned_processes.py") == OWNER_SHA, "frozen_owner_drift")
    sys.path.insert(0, str(BASE_ROOT))
    specification = importlib.util.spec_from_file_location("frozen_v10", BASE_ROOT / "run_current_full_v10.py")
    require(specification is not None and specification.loader is not None, "frozen_runner_unavailable")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def input_manifest() -> dict[str, object]:
    require(MANIFEST.is_file() and not MANIFEST.is_symlink(), "manifest_missing")
    require(sha(MANIFEST) == MANIFEST_SHA, "manifest_scope_drift")
    value = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "manifest_shape")
    return value


def validate(config: dict[str, object]) -> tuple[list[dict[str, object]], dict[str, str]]:
    require(config.get("version") == 1, "manifest_version")
    suites = config.get("suites")
    require(isinstance(suites, list) and suites, "suite_list")
    validated: list[dict[str, object]] = []
    for suite in suites:
        require(isinstance(suite, dict), "suite_shape")
        label, relative, expected_hash, nodes = suite.get("label"), suite.get("test"), suite.get("sha256"), suite.get("nodes")
        require(isinstance(label, str) and isinstance(relative, str) and isinstance(expected_hash, str), "suite_identity")
        require(expected_hash != "PENDING_FINAL_HASH" and len(expected_hash) == 64, "final_hash_required")
        require(isinstance(nodes, list) and nodes and len(nodes) == len(set(nodes)), "suite_nodes")
        path = regular_within(HERE / relative)
        require(sha(path) == expected_hash, "suite_hash_drift")
        validated.append({"label": label, "path": str(path), "sha256": expected_hash, "nodes": nodes})
    require(len({suite["label"] for suite in validated}) == len(validated), "duplicate_suite_label")
    require([suite["label"] for suite in validated] == ["diagnostic", "author_daily_gate", "legacy_leaf_diagnostics"], "suite_order")
    diagnostic = validated[0]
    require(len(diagnostic["nodes"]) == 6, "diagnostic_exactly_six_nodes")
    author = validated[1]
    require(tuple(author["nodes"]) == AUTHOR_NODES, "author_exact_18_pure_nodes")
    require(sha(HERE / "author/test_author_daily_gate.py") == AUTHOR_SHA, "author_copy_hash")
    hashes = {str(MANIFEST): sha(MANIFEST)}
    for suite in validated:
        hashes[str(suite["path"])] = str(suite["sha256"])
    for relative, expected_hash in RUNTIME_HASHES.items():
        digest = sha(SOURCE / relative)
        require(digest == expected_hash, "runtime_source_drift")
        hashes[str(SOURCE / relative)] = digest
    diagnostic_source = regular_within(HERE / "src/yandex_maps_scraper.py")
    require(sha(diagnostic_source) == hashes[str(SOURCE / "src/yandex_maps_scraper.py")], "diagnostic_source_copy_drift")
    hashes[str(diagnostic_source)] = sha(diagnostic_source)
    return validated, hashes


def child_code(suites: list[dict[str, object]]) -> str:
    selected = [(suite["label"], suite["path"], suite["nodes"]) for suite in suites]
    return r'''import json,os,pytest,subprocess,sys
selected=%r
pytest_ini=%r
base_temp=%r
source_src=%r
sys.path.insert(0,source_src)
state={'suites':[],'sentinel':None}
try: from _pytest.subtests import SubtestReport
except ImportError: SubtestReport=()
class H:
 def __init__(self,label): self.label=label;self.nodes=[];self.errors=[];self.reports=[];self.subtests=[]
 def pytest_collection_finish(self,session): self.nodes=['::'.join(item.nodeid.split('::')[1:]) for item in session.items]
 def pytest_collectreport(self,report):
  if report.failed:self.errors.append(report.nodeid)
 def pytest_runtest_logreport(self,report):
  row={'nodeid':'::'.join(report.nodeid.split('::')[1:]),'when':report.when,'outcome':report.outcome,'xfail':bool(getattr(report,'wasxfail',False))}
  (self.subtests if isinstance(report,SubtestReport) else self.reports).append(row)
for label,path,nodes in selected:
 h=H(label);code=pytest.main([path+'::'+node for node in nodes]+['-q','-c',pytest_ini,'-p','no:cacheprovider','--tb=no','--show-capture=no','--basetemp',base_temp+'/'+label],plugins=[h])
 state['suites'].append({'label':label,'nodes':h.nodes,'collection_errors':h.errors,'reports':h.reports,'subtests':h.subtests,'return_code':code})
 if code: break
if all(suite['return_code']==0 for suite in state['suites']):
 try:
  subprocess.run([sys.executable,'-B','-I','-c','pass'],check=True,capture_output=True)
  state['sentinel']={'status':'completed'}
 except BaseException:
  state['sentinel']={'status':'failed','exception_type':type(sys.exception()).__name__}
print(%r+json.dumps(state,sort_keys=True));raise SystemExit(0 if state['sentinel']=={'status':'completed'} and len(state['suites'])==len(selected) else 1)
''' % (selected, str(SOURCE / "pytest.ini"), str(HERE / "basetemp"), str(SOURCE / "src"), MARK)


def account(suites: list[dict[str, object]], callback: dict[str, object], capture: dict[str, object]) -> list[str]:
    reasons: list[str] = []
    if capture["exit_code"] != 0 or capture["stopped_reason"] or callback.get("sentinel") != {"status": "completed"}:
        reasons.append("process_or_sentinel_nonpass")
    actual = callback.get("suites")
    if not isinstance(actual, list) or len(actual) != len(suites):
        return reasons + ["suite_count"]
    for expected, observed in zip(suites, actual):
        if not isinstance(observed, dict) or observed.get("label") != expected["label"] or observed.get("return_code") != 0:
            reasons.append("suite_nonpass")
            continue
        nodes = observed.get("nodes")
        if nodes != expected["nodes"] or observed.get("collection_errors"):
            reasons.append("node_or_collection_drift")
        reports = observed.get("reports")
        required = collections.Counter((node, stage) for node in expected["nodes"] for stage in ("setup", "call", "teardown"))
        if not isinstance(reports, list):
            reasons.append("stage_or_outcome_drift")
            continue
        stages = collections.Counter((row.get("nodeid"), row.get("when")) for row in reports if isinstance(row, dict))
        bad_outcome = any(not isinstance(row, dict) or row.get("outcome") != "passed" or row.get("xfail") for row in reports)
        if stages != required or bad_outcome:
            reasons.append("stage_or_outcome_drift")
        if observed.get("subtests"):
            reasons.append("unexpected_subtest")
    if any(stream["truncated"] for stream in capture["streams"].values()):
        reasons.append("truncated")
    return sorted(set(reasons))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    config = input_manifest()
    suites, inputs_before = validate(config)
    plan = {"status": "prepared", "suites": [{"label": suite["label"], "nodes": suite["nodes"]} for suite in suites], "input_hashes": inputs_before}
    if not args.execute:
        print(json.dumps(plan, sort_keys=True))
        return 0
    require(not RESULT.exists() and not RESULT.is_symlink(), "existing_result")
    base = load_base()
    started = time.monotonic()
    result: dict[str, object] = {"status": "failed", "input_hashes_before": inputs_before}
    try:
        require(shutil.disk_usage(BASE_ROOT).free >= 5 * 1024**3, "start_disk_floor")
        sys.path.insert(0, str(base.PSUTIL))
        import psutil
        require(psutil.__version__ == "7.0.0", "psutil_version")
        source_before = base.manifest()
        frozen = json.loads(base.FREEZE.read_text(encoding="utf-8"))
        require(source_before == frozen["source_manifest"], "frozen_source_drift_before")
        result["source_file_count"] = len(source_before)
        control_capture, control_output = base.invoke(base.CONTROL, 30)
        controls = json.loads(control_output)
        require(control_capture["exit_code"] == 0 and control_capture["stopped_reason"] is None, "controls_nonpass")
        require(set(controls) == {"users", "source_write", "tcp", "docker", "native_tcp", "owned_write", "symlink_target", "symlink_write"}, "controls_shape")
        result["controls"] = {"capture": control_capture, "checks": controls}
        capture, output = base.invoke(child_code(suites), 300)
        lines = [line[len(MARK):] for line in output.splitlines() if line.startswith(MARK)]
        require(len(lines) == 1, "callback_missing_or_duplicate")
        callback = json.loads(lines[0])
        result.update({"capture": capture, "callback": callback, "nonpass_reasons": account(suites, callback, capture)})
        inputs_after = validate(config)[1]
        result["input_hashes_after"] = inputs_after
        require(inputs_before == inputs_after, "input_drift_after")
        require(source_before == base.manifest(), "source_drift_after")
        result["source_unchanged"] = True
        result["status"] = "passed" if not result["nonpass_reasons"] else "nonpass"
    except BaseException:
        result["error_type"] = type(sys.exception()).__name__
    result["duration_seconds"] = round(time.monotonic() - started, 3)
    base.put(RESULT, result)
    print(json.dumps({"status": result["status"]}, sort_keys=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
