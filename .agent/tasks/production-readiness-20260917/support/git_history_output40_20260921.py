#!/usr/bin/env python3
"""Value-free proof for the frozen output-manifest history rows 21–43,45–61.

This reads only immutable Git blobs and the redacted report. It never writes or
prints a scanner value, a value hash, raw source, Match/Secret text, or a URI.
"""

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
ROW_IDS = (
    21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37,
    38, 39, 40, 41, 42, 43, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    56, 57, 58, 59, 60, 61,
)
ROW_IDS_SHA256 = "64322cdceafc232edb352f87527f14ea56cad22b51c42649fc19c4fadce6ed60"

# Transcription used only to locate the captured scalar on the exact source
# line. Whole-redacted-Match equality below, not this transcription alone,
# binds each report finding.
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


def blob_bytes(commit: str, path: str) -> bytes:
    object_id = git("rev-parse", f"{commit}:{path}").decode().strip()
    data = git("cat-file", "blob", f"{commit}:{path}")
    actual_object_id = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    assert actual_object_id == object_id
    return data


def report_finding(report: list[dict[str, Any]], row_id: int) -> dict[str, Any]:
    finding = report[row_id - 1]
    assert finding["RuleID"] == "generic-api-key"
    assert finding["Secret"] == "REDACTED"
    assert finding["StartLine"] == finding["EndLine"]
    assert isinstance(finding["Commit"], str)
    assert isinstance(finding["File"], str) and finding["File"].startswith("outputs/")
    return finding


def exact_line(data: bytes, line_number: int) -> str:
    lines = data.decode("utf-8").splitlines()
    assert 1 <= line_number <= len(lines)
    return lines[line_number - 1]


def scalar_paths(value: object, candidate: str, path: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
    if isinstance(value, dict):
        found: list[tuple[object, ...]] = []
        for key, child in value.items():
            found.extend(scalar_paths(child, candidate, path + (key,)))
        return found
    if isinstance(value, list):
        found = []
        for index, child in enumerate(value):
            found.extend(scalar_paths(child, candidate, path + (index,)))
        return found
    return [path] if isinstance(value, str) and value == candidate else []


def container_at(document: object, path: tuple[object, ...]) -> dict[str, object] | None:
    if not path:
        return None
    cursor = document
    for component in path[:-1]:
        if not isinstance(cursor, (dict, list)):
            return None
        cursor = cursor[component]
    return cursor if isinstance(cursor, dict) else None


def safe_relative_path(value: object) -> str | None:
    if not isinstance(value, str) or value.startswith("/"):
        return None
    candidate = Path(value)
    if not value or ".." in candidate.parts:
        return None
    return value


def referenced_paths(document: object, scalar_path: tuple[object, ...]) -> set[str]:
    if len(scalar_path) == 2 and scalar_path[0] == "files":
        direct = safe_relative_path(scalar_path[1])
        return {direct} if direct is not None else set()

    container = container_at(document, scalar_path)
    field = scalar_path[-1] if scalar_path else None
    if not isinstance(container, dict) or not isinstance(field, str) or not field.endswith("_sha256"):
        return set()

    references: set[str] = set()
    for key in ("path", "file", "source", "artifact", "source_path", "artifact_path", "source_file", "artifact_file"):
        reference = safe_relative_path(container.get(key))
        if reference is not None:
            references.add(reference)
    return references


def git_path_exists(commit: str, path: str) -> bool:
    """Return false only for an explicit empty ls-tree result.

    A failed Git invocation is not evidence that a referenced artifact is
    absent and must propagate to the top-level fatal handler.
    """
    listing = git("ls-tree", "-z", "--full-tree", commit, "--", path)
    return bool(listing)


def verified_artifact_paths(commit: str, paths: set[str], candidate: str) -> tuple[int, int]:
    matches = 0
    missing = 0
    for path in paths:
        if not git_path_exists(commit, path):
            missing += 1
            continue
        artifact = blob_bytes(commit, path)
        if hashlib.sha256(artifact).hexdigest() == candidate:
            matches += 1
    return matches, missing


def main() -> int:
    assert REPORT.is_file(), "frozen redacted report unavailable"
    report_bytes = REPORT.read_bytes()
    assert hashlib.sha256(report_bytes).hexdigest() == EXPECTED_REPORT_SHA256
    report = json.loads(report_bytes)
    assert isinstance(report, list) and len(report) == 711
    scope_text = ",".join(str(row_id) for row_id in ROW_IDS)
    assert hashlib.sha256(scope_text.encode()).hexdigest() == ROW_IDS_SHA256
    assert len(ROW_IDS) == 40 and len(set(ROW_IDS)) == 40

    rows: list[dict[str, object]] = []
    for row_id in ROW_IDS:
        finding = report_finding(report, row_id)
        commit = finding["Commit"]
        path = finding["File"]
        line_number = finding["StartLine"]
        assert isinstance(commit, str) and isinstance(path, str) and isinstance(line_number, int)
        source = blob_bytes(commit, path)
        line = exact_line(source, line_number)
        matches = list(GENERIC_API_KEY_RE.finditer(line))
        assert len(matches) == 1
        candidate = matches[0].group(1)
        assert matches[0].group(0).replace(candidate, "REDACTED") == finding["Match"]

        document = json.loads(source)
        paths = scalar_paths(document, candidate)
        association_is_exact = len(paths) == 1
        artifact_matches = 0
        artifact_missing = 0
        if association_is_exact:
            artifact_matches, artifact_missing = verified_artifact_paths(
                commit,
                referenced_paths(document, paths[0]),
                candidate,
            )
        classification = (
            "HISTORICAL_OUTPUT_ARTIFACT_SHA256_DIGEST_NONSECRET"
            if association_is_exact and artifact_matches == 1
            else "HISTORICAL_OUTPUT_VALUE_UNKNOWN"
        )
        rows.append(
            {
                "row_id": row_id,
                "report_tuple_bound": True,
                "git_object_hash_verified": True,
                "exact_redacted_whole_match_equal": True,
                "parsed_json_scalar_association_exact": association_is_exact,
                "referenced_artifact_sha256_equal": artifact_matches == 1,
                "referenced_artifact_confirmed_missing": artifact_missing > 0,
                "classification": classification,
            }
        )

    print(json.dumps({"scope_sha256": ROW_IDS_SHA256, "rows": rows}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, IndexError, OSError, UnicodeDecodeError, json.JSONDecodeError, subprocess.CalledProcessError):
        print(json.dumps({"status": "failed", "error_type": type(sys.exc_info()[1]).__name__}), file=sys.stderr)
        raise SystemExit(1)
