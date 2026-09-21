#!/usr/bin/env python3
"""Value-free reproducibility check for frozen history rows 92–95, 684, 686.

Reads exact frozen Git blobs and a redacted Gitleaks report. It never writes or
prints source text, Match/Secret values, URIs, or hashes of matched values.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


REPORT = Path("/private/tmp/localos-git-history-verified-20260921.qZcoBF/history-redacted.json")
EXPECTED_REPORT_SHA256 = "7fbbbdb37d231b6b5a32d56d66d6ec24f4a5f0f64f95d4a6113f448f8acc2732"

# Candidate-discovery transcription of Gitleaks v8.30.1 `generic-api-key`:
# https://raw.githubusercontent.com/gitleaks/gitleaks/v8.30.1/config/gitleaks.toml
# The captured scanner-defaults.toml has only `extend.useDefault = true`.
# This is not a cross-engine rule equivalence claim: exact whole redacted
# Match equality below binds these six findings independently.
GENERIC_API_KEY_RE = re.compile(
    r"[\w.-]{0,50}?(?:access|auth|(?:[Aa]pi|API)|credential|creds|key|"
    r"passw(?:or)?d|secret|token)(?:[ \t\w.-]{0,20})[\s\x27\"]{0,3}"
    r"(?:=|>|:{1,3}=|\|\||:|=>|\?=|,)[\x60\x27\"\s=]{0,5}"
    r"([\w.=-]{10,150}|[a-z0-9][a-z0-9+/]{11,}={0,3})"
    r"(?:[\x60\x27\"\s;]|\\\\[nr]|$)",
    re.IGNORECASE,
)

ROWS = (
    (92, "1607cd8931fa62eeeeec9c24824f6318d573c395", "src/services/outreach_playbook.py", 462, "content"),
    (93, "1607cd8931fa62eeeeec9c24824f6318d573c395", "src/services/outreach_playbook.py", 481, "content"),
    (94, "1607cd8931fa62eeeeec9c24824f6318d573c395", "src/services/outreach_playbook.py", 497, "content"),
    (95, "0b8a1927b19494891569907c6369a2c33c848312", "src/services/outreach_playbook.py", 344, "content"),
    (684, "06ee25d93651e64627b5013d557d895d7c332647", "src/wordstat_config.py", 9, "environment_default"),
    (686, "06ee25d93651e64627b5013d557d895d7c332647", "src/wordstat_client.py", 187, "unknown"),
)

APPROVED_COLLECTIONS = {
    92: "APPROVED_LOCALOS_MESSAGE_EXAMPLES",
    93: "APPROVED_OUTREACH_COPY_CONTRACTS",
    94: "APPROVED_OUTREACH_COPY_CONTRACTS",
    95: "APPROVED_LOCALOS_CASES",
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
        ["/usr/bin/git", "--no-replace-objects", "-c", "core.attributesfile=/dev/null", *args],
        env=env,
        stderr=subprocess.PIPE,
    )


def blob_bytes(commit: str, path: str) -> tuple[str, bytes]:
    oid = git("rev-parse", f"{commit}:{path}").decode().strip()
    data = git("cat-file", "blob", f"{commit}:{path}")
    assert hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() == oid
    return oid, data


def source_line(data: bytes, line_number: int) -> str:
    lines = data.decode("utf-8").splitlines()
    if line_number < 1 or line_number > len(lines):
        raise AssertionError("frozen source line unavailable")
    return lines[line_number - 1]


def enclosing_assign(tree: ast.AST, line_number: int) -> ast.Assign | ast.AnnAssign:
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno)
    ]
    if len(candidates) != 1:
        raise AssertionError("expected one enclosing assignment")
    return candidates[0]


def assignment_targets(node: ast.Assign | ast.AnnAssign) -> set[str]:
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    return {target.id for target in targets if isinstance(target, ast.Name)}


def dict_value_fields(tree: ast.AST, value: str, line_number: int) -> set[str]:
    fields: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, item in zip(node.keys, node.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(item, ast.Constant)
                and item.value == value
                and item.lineno == line_number
            ):
                fields.add(key.value)
    return fields


def getenv_argument(tree: ast.AST, value: str, position: int) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "os"
        and node.func.attr == "getenv"
        and len(node.args) > position
        and isinstance(node.args[position], ast.Constant)
        and node.args[position].value == value
        for node in ast.walk(tree)
    )


def keyword_argument(tree: ast.AST, value: str) -> set[str]:
    return {
        node.arg
        for node in ast.walk(tree)
        if isinstance(node, ast.keyword)
        and isinstance(node.value, ast.Constant)
        and node.value.value == value
        and node.arg is not None
    }


def report_finding(report: list[dict[str, Any]], row_id: int) -> dict[str, Any]:
    # Evidence metadata IDs are one-based; JSON array offsets are zero-based.
    finding = report[row_id - 1]
    assert finding["RuleID"] == "generic-api-key"
    assert finding["Secret"] == "REDACTED"
    return finding


def classify(kind: str, row_id: int, tree: ast.AST, assign: ast.Assign | ast.AnnAssign, value: str, line_number: int) -> str:
    if kind == "content":
        assert assignment_targets(assign) == {APPROVED_COLLECTIONS[row_id]}
        assert dict_value_fields(assign, value, line_number) == {"key"}
        assert re.fullmatch(r"[a-z][a-z0-9_]*", value)
        assert not re.search(r"access|auth|credential|creds|key|passw|secret|token", value, re.I)
        assert not any(isinstance(node, ast.Call) for node in ast.walk(assign))
        return "HISTORICAL_STATIC_CONTENT_KEY_LITERAL_NONSECRET"
    if kind == "environment_default":
        assert getenv_argument(tree, value, 1)
        assert not getenv_argument(tree, value, 0)
        return "HISTORICAL_ENVIRONMENT_DEFAULT_LITERAL_UNKNOWN"
    if kind == "unknown":
        assert keyword_argument(tree, value) == {"client_secret"}
        return "HISTORICAL_HARDCODED_CLIENT_SECRET_LITERAL_UNKNOWN"
    raise AssertionError("unsupported classification kind")


def main() -> int:
    if not REPORT.is_file():
        raise AssertionError("frozen redacted report unavailable")
    report_bytes = REPORT.read_bytes()
    assert hashlib.sha256(report_bytes).hexdigest() == EXPECTED_REPORT_SHA256
    report = json.loads(report_bytes)
    assert isinstance(report, list) and len(report) == 711

    results: list[dict[str, Any]] = []
    for row_id, commit, path, line_number, kind in ROWS:
        finding = report_finding(report, row_id)
        assert finding["Commit"] == commit
        assert finding["File"] == path
        assert finding["StartLine"] == line_number == finding["EndLine"]
        oid, data = blob_bytes(commit, path)
        line = source_line(data, line_number)
        candidates = list(GENERIC_API_KEY_RE.finditer(line))
        assert len(candidates) == 1
        candidate = candidates[0].group(1)
        assert candidates[0].group(0).replace(candidate, "REDACTED") == finding["Match"]
        tree = ast.parse(data.decode("utf-8"))
        assign = enclosing_assign(tree, line_number)
        classification = classify(kind, row_id, tree, assign, candidate, line_number)
        current_oid, _current_data = blob_bytes("074ee5a01841d7e52adaa7fe5395a60217c24add", path)
        assert current_oid != oid
        results.append(
            {
                "row_id": row_id,
                "commit": commit,
                "path": path,
                "line": line_number,
                "git_blob_oid": oid,
                "raw_blob_sha1": hashlib.sha1(data).hexdigest(),
                "raw_blob_sha256": hashlib.sha256(data).hexdigest(),
                "report_match_masked": "REDACTED" in str(finding["Match"]),
                "single_candidate_on_exact_line": True,
                "redacted_whole_match_equal": True,
                "git_object_hash_verified": True,
                "current_blob_differs": True,
                "classification": classification,
            }
        )
    print(json.dumps({"report_sha256": EXPECTED_REPORT_SHA256, "rows": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, IndexError, OSError, subprocess.CalledProcessError, UnicodeDecodeError, SyntaxError):
        print(json.dumps({"status": "failed", "error_type": type(sys.exc_info()[1]).__name__}), file=sys.stderr)
        raise SystemExit(1)
