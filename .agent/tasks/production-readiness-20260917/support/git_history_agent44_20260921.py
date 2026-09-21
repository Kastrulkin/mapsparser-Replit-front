#!/usr/bin/env python3
"""Value-free proof for frozen history rows 5, 8–20, and 62–91."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPORT = Path("/private/tmp/localos-git-history-verified-20260921.qZcoBF/history-redacted.json")
EXPECTED_REPORT_SHA256 = "7fbbbdb37d231b6b5a32d56d66d6ec24f4a5f0f64f95d4a6113f448f8acc2732"
PLAN_COMMIT = "4611377145726445adcc3ed9bd8760c1686dc29d"

# Candidate discovery provenance: Gitleaks v8.30.1 default `generic-api-key`.
# https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/config/gitleaks.toml
# Captured scanner defaults set only `extend.useDefault = true`. Exact whole
# redacted-Match equality below independently binds report findings.
GENERIC_API_KEY_RE = re.compile(
    r"[\w.-]{0,50}?(?:access|auth|(?:[Aa]pi|API)|credential|creds|key|"
    r"passw(?:or)?d|secret|token)(?:[ \t\w.-]{0,20})[\s\x27\"]{0,3}"
    r"(?:=|>|:{1,3}=|\|\||:|=>|\?=|,)[\x60\x27\"\s=]{0,5}"
    r"([\w.=-]{10,150}|[a-z0-9][a-z0-9+/]{11,}={0,3})"
    r"(?:[\x60\x27\"\s;]|\\\\[nr]|$)",
    re.IGNORECASE,
)

PLAN_EVIDENCE = ".agent/tasks/localos-plan-20260906/evidence.json"
FRONTEND_PROOF = ".agent/tasks/localos-plan-20260906/raw/frontend-production-build-proof.json"
LINE_MAP = {
    8: 335, 9: 336, 10: 338, 11: 351, 12: 359, 13: 360, 14: 361,
    15: 363, 16: 381, 17: 397, 18: 398, 19: 403, 20: 406,
    62: 22, 63: 50, 64: 117, 65: 123, 66: 126, 67: 127, 68: 130,
    69: 179, 70: 180, 71: 225, 72: 318, 73: 365, 74: 403, 75: 404,
    76: 408, 77: 409, 78: 427, 79: 428, 80: 430, 81: 461, 82: 525,
    83: 571, 84: 586, 85: 657, 86: 674, 87: 697, 88: 737, 89: 745,
    90: 760, 91: 793,
}


def git(*args: str) -> bytes:
    env = {
        "PATH": "/usr/bin:/bin",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.check_output(
        ["/usr/bin/git", "--no-replace-objects", "--literal-pathspecs", "-c", "core.attributesfile=/dev/null", *args],
        env=env,
        stderr=subprocess.PIPE,
    )


def blob_bytes(commit: str, path: str) -> tuple[str, bytes]:
    oid = git("rev-parse", f"{commit}:{path}").decode().strip()
    data = git("cat-file", "blob", f"{commit}:{path}")
    assert hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() == oid
    return oid, data


def report_row(report: list[dict[str, Any]], row_id: int, commit: str, path: str, line: int) -> dict[str, Any]:
    finding = report[row_id - 1]  # Evidence row IDs are one-based.
    assert finding["RuleID"] == "generic-api-key"
    assert finding["Secret"] == "REDACTED"
    assert finding["Commit"] == commit
    assert finding["File"] == path
    assert finding["StartLine"] == line == finding["EndLine"]
    return finding


def physical_json_key(line: str) -> str:
    match = re.match(r'\s*"([^"]+)"\s*:', line)
    if not match:
        raise AssertionError("expected JSON property source line")
    return match.group(1)


def has_exact_mapping(document: Any, key: str, value: str) -> bool:
    if isinstance(document, dict):
        if document.get(key) == value:
            return True
        return any(has_exact_mapping(item, key, value) for item in document.values())
    if isinstance(document, list):
        return any(has_exact_mapping(item, key, value) for item in document)
    return False


def result_base(row_id: int, commit: str, path: str, line: int, oid: str, data: bytes) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "commit": commit,
        "path": path,
        "line": line,
        "git_blob_oid": oid,
        "raw_blob_sha1": hashlib.sha1(data).hexdigest(),
        "raw_blob_sha256": hashlib.sha256(data).hexdigest(),
        "single_candidate_on_exact_line": True,
        "redacted_whole_match_equal": True,
        "git_object_hash_verified": True,
    }


def review_unknown_markdown(report: list[dict[str, Any]]) -> dict[str, Any]:
    row_id = 5
    commit = "88ad2437e71826967e2cd8ace7f545be60c0913f"
    path = ".agent/tasks/production-readiness-20260917/evidence.md"
    line_number = 18
    finding = report_row(report, row_id, commit, path, line_number)
    oid, data = blob_bytes(commit, path)
    line = data.decode("utf-8").splitlines()[line_number - 1]
    candidates = list(GENERIC_API_KEY_RE.finditer(line))
    assert len(candidates) == 1
    candidate = candidates[0].group(1)
    assert candidates[0].group(0).replace(candidate, "REDACTED") == finding["Match"]
    result = result_base(row_id, commit, path, line_number, oid, data)
    result["classification"] = "HISTORICAL_EVIDENCE_LITERAL_UNKNOWN"
    return result


def review_digest_row(report: list[dict[str, Any]], row_id: int, source_path: str) -> dict[str, Any]:
    line_number = LINE_MAP[row_id]
    finding = report_row(report, row_id, PLAN_COMMIT, source_path, line_number)
    oid, data = blob_bytes(PLAN_COMMIT, source_path)
    line = data.decode("utf-8").splitlines()[line_number - 1]
    candidates = list(GENERIC_API_KEY_RE.finditer(line))
    assert len(candidates) == 1
    candidate = candidates[0].group(1)
    assert re.fullmatch(r"[a-f0-9]{64}", candidate)
    assert candidates[0].group(0).replace(candidate, "REDACTED") == finding["Match"]
    referenced_path = physical_json_key(line)
    document = json.loads(data)
    assert has_exact_mapping(document, referenced_path, candidate)
    result = result_base(row_id, PLAN_COMMIT, source_path, line_number, oid, data)
    result["parsed_json_reference_binding_verified"] = True
    listing = git("ls-tree", "-z", "--full-tree", PLAN_COMMIT, "--", referenced_path)
    if not listing:
        result["referenced_historical_blob_present"] = False
        result["classification"] = "HISTORICAL_UNVERIFIED_BUILD_OUTPUT_DIGEST_UNKNOWN"
        return result
    _target_oid, target_data = blob_bytes(PLAN_COMMIT, referenced_path)
    assert hashlib.sha256(target_data).hexdigest() == candidate
    result["referenced_historical_blob_present"] = True
    result["classification"] = "HISTORICAL_REFERENCED_BLOB_SHA256_DIGEST_NONSECRET"
    return result


def main() -> int:
    report_bytes = REPORT.read_bytes()
    assert hashlib.sha256(report_bytes).hexdigest() == EXPECTED_REPORT_SHA256
    report = json.loads(report_bytes)
    assert isinstance(report, list) and len(report) == 711

    rows = [review_unknown_markdown(report)]
    rows.extend(review_digest_row(report, row_id, PLAN_EVIDENCE) for row_id in range(8, 21))
    rows.extend(review_digest_row(report, row_id, FRONTEND_PROOF) for row_id in range(62, 92))
    assert len(rows) == 44
    assert sum(item["classification"].endswith("NONSECRET") for item in rows) == 35
    assert sum(item["classification"].endswith("UNKNOWN") for item in rows) == 9
    print(json.dumps({"report_sha256": EXPECTED_REPORT_SHA256, "rows": rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, IndexError, OSError, UnicodeDecodeError, ValueError, subprocess.CalledProcessError):
        print(json.dumps({"status": "failed", "error_type": type(sys.exc_info()[1]).__name__}), file=sys.stderr)
        raise SystemExit(1)
