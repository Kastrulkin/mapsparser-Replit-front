#!/usr/bin/env python3
"""Value-free verifier for bounded frozen-history rows 4, 6, 7, 44, 96–101,
169–175, 681–683, and 689–694.

Only immutable Git blobs and the frozen redacted report are read.  No source
is executed.  Stdout intentionally contains metadata predicates and
classifications only: never Match/Secret/source text/candidate/value hash/URI.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


REPORT = Path("/private/tmp/localos-git-history-verified-20260921.qZcoBF/history-redacted.json")
EXPECTED_REPORT_SHA256 = "7fbbbdb37d231b6b5a32d56d66d6ec24f4a5f0f64f95d4a6113f448f8acc2732"
ROW_IDS = (
    4, 6, 7, 44, 96, 97, 98, 99, 100, 101, 169, 170, 171, 172, 173, 174,
    175, 681, 682, 683, 689, 690, 691, 692, 693, 694,
)
ROW_IDS_SHA256 = "f0bb276f531f0fce4caef168399afb66ea1f23c533eaf59431dc9ffa269bcc49"

# Candidate-discovery transcription of Gitleaks v8.30.1 generic-api-key.
# Whole redacted-Match equality below, rather than this transcription alone,
# binds every report row to its exact historical scalar.
GENERIC_API_KEY_RE = re.compile(
    r"[\w.-]{0,50}?(?:access|auth|(?:[Aa]pi|API)|credential|creds|key|"
    r"passw(?:or)?d|secret|token)(?:[ \t\w.-]{0,20})[\s\x27\"]{0,3}"
    r"(?:=|>|:{1,3}=|\|\||:|=>|\?=|,)[\x60\x27\"\s=]{0,5}"
    r"([\w.=-]{10,150}|[a-z0-9][a-z0-9+/]{11,}={0,3})"
    r"(?:[\x60\x27\"\s;]|\\\\[nr]|$)",
    re.IGNORECASE,
)


def git(*args: str) -> bytes:
    environment = {
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
        env=environment,
        stderr=subprocess.PIPE,
    )


def blob_bytes(commit: str, path: str) -> tuple[str, bytes]:
    object_id = git("rev-parse", f"{commit}:{path}").decode().strip()
    data = git("cat-file", "blob", f"{commit}:{path}")
    assert hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() == object_id
    return object_id, data


def finding(report: list[dict[str, Any]], row_id: int) -> dict[str, Any]:
    item = report[row_id - 1]
    assert item["Secret"] == "REDACTED"
    assert item["RuleID"] in {"generic-api-key", "curl-auth-header"}
    assert isinstance(item["Commit"], str) and isinstance(item["File"], str)
    assert isinstance(item["StartLine"], int) and item["StartLine"] <= item["EndLine"]
    return item


def source_span(data: bytes, start_line: int, end_line: int) -> str:
    lines = data.decode("utf-8").splitlines()
    assert 1 <= start_line <= end_line <= len(lines)
    return "\n".join(lines[start_line - 1 : end_line])


def exact_candidate(item: dict[str, Any], span: str) -> str:
    if item["RuleID"] == "curl-auth-header":
        # The scanner's multi-line curl Match is authoritative.  Splitting the
        # frozen masked Match avoids pretending a shortened local curl regex is
        # equivalent to the scanner rule.
        parts = item["Match"].split("REDACTED")
        assert len(parts) == 2
        expression = re.compile(re.escape(parts[0]) + r"(.+?)" + re.escape(parts[1]), re.S)
    else:
        expression = GENERIC_API_KEY_RE
    matches = list(expression.finditer(span))
    assert len(matches) == 1
    candidate = matches[0].group(1)
    assert matches[0].group(0).replace(candidate, "REDACTED") == item["Match"]
    return candidate


def base_result(row_id: int, item: dict[str, Any], oid: str, data: bytes) -> dict[str, Any]:
    return {
        "row_id": row_id,
        "commit": item["Commit"],
        "path": item["File"],
        "line_start": item["StartLine"],
        "line_end": item["EndLine"],
        "rule_id": item["RuleID"],
        "git_blob_oid": oid,
        "raw_blob_sha1": hashlib.sha1(data).hexdigest(),
        "raw_blob_sha256": hashlib.sha256(data).hexdigest(),
        "report_tuple_bound": True,
        "git_object_hash_verified": True,
        "single_candidate_on_exact_span": True,
        "redacted_whole_match_equal": True,
    }


def record_identifier_proven(tree: ast.AST, candidate: str, line: int) -> bool:
    """Require the UUID assignment and record filter in the same lexical scope."""
    try:
        if str(uuid.UUID(candidate)) != candidate.lower():
            return False
    except (ValueError, AttributeError):
        return False
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def scope(node: ast.AST) -> ast.AST:
        node = parents.get(node, tree)
        while node is not tree:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                return node
            node = parents.get(node, tree)
        return tree

    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and node.lineno == line
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "auth_id"
        and isinstance(node.value, ast.Constant)
        and node.value.value == candidate
    ]
    if len(assignments) != 1:
        return False
    assignment = assignments[0]
    owner = scope(assignment)
    stores = [
        node for node in ast.walk(owner)
        if isinstance(node, ast.Name) and node.id == "auth_id"
        and isinstance(node.ctx, ast.Store) and scope(node) is owner
    ]
    if len(stores) != 1:
        return False
    return any(
        isinstance(node, ast.Call)
        and scope(node) is owner
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "eq"
        and len(node.args) == 2
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in {"id", "auth_id", "user_id"}
        and isinstance(node.args[1], ast.Name)
        and node.args[1].id == "auth_id"
        for node in ast.walk(owner)
    )


def main() -> int:
    report_bytes = REPORT.read_bytes()
    assert hashlib.sha256(report_bytes).hexdigest() == EXPECTED_REPORT_SHA256
    report = json.loads(report_bytes)
    assert isinstance(report, list) and len(report) == 711
    scope_text = ",".join(str(row_id) for row_id in ROW_IDS)
    assert hashlib.sha256(scope_text.encode()).hexdigest() == ROW_IDS_SHA256
    assert len(ROW_IDS) == len(set(ROW_IDS)) == 26

    rows: list[dict[str, Any]] = []
    for row_id in ROW_IDS:
        item = finding(report, row_id)
        oid, data = blob_bytes(item["Commit"], item["File"])
        candidate = exact_candidate(item, source_span(data, item["StartLine"], item["EndLine"]))
        result = base_result(row_id, item, oid, data)
        classification = "HISTORICAL_VALUE_UNKNOWN"
        if row_id in {169, 170, 171, 172, 173, 174, 175, 682}:
            assert candidate == "YOUR_TOKEN"
            classification = "HISTORICAL_CURL_TOKEN_PLACEHOLDER_NONSECRET"
            result["exact_documented_placeholder_equal"] = True
        elif row_id in {691, 693, 694}:
            assert record_identifier_proven(ast.parse(data.decode("utf-8")), candidate, item["StartLine"])
            classification = "HISTORICAL_STATIC_AUTH_RECORD_UUID_IDENTIFIER_NONSECRET"
            result["same_scope_single_uuid_assignment_and_record_filter"] = True
        result["classification"] = classification
        rows.append(result)
    assert sum(row["classification"].endswith("NONSECRET") for row in rows) == 11
    assert sum(row["classification"].endswith("UNKNOWN") for row in rows) == 15
    print(json.dumps({"report_sha256": EXPECTED_REPORT_SHA256, "scope_sha256": ROW_IDS_SHA256, "rows": rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, IndexError, OSError, UnicodeDecodeError, ValueError, SyntaxError, subprocess.CalledProcessError):
        print(json.dumps({"status": "failed", "error_type": type(sys.exc_info()[1]).__name__}), file=sys.stderr)
        raise SystemExit(1)
