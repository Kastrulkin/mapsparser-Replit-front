"""Client for the isolated compiled-script runner; no user source runs in Flask."""
from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import secrets
import time
from typing import Any
from urllib.parse import urlsplit

from services.compiled_script_artifact import PILOT_KIND, validate_artifact
from services.compiled_json_schema import validate_value
from services.compiled_table_contract import normalize_table_input


class CompiledRuntimeUnavailable(RuntimeError):
    pass


class CompiledScriptRejected(ValueError):
    """The authenticated runner executed/rejected this candidate program."""


def _key(row: dict[str, Any], fields: list[str]) -> str:
    return hashlib.sha256("\x1f".join(str(row.get(field) or "").strip().lower() for field in fields).encode()).hexdigest()


def _fixture_value(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in {"artifact_hash", "runtime_ai_calls", "external_effects"}}


def execute_pilot(artifact: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    """Independent oracle for the sheet pilot only; never a production executor."""
    checked = validate_artifact(artifact)
    if not checked["valid"] or checked["manifest"].get("kind") != PILOT_KIND:
        raise ValueError("compiled_oracle_unavailable")
    rows = input_payload.get("rows") if isinstance(input_payload.get("rows"), list) else []
    required = checked["manifest"].get("required_columns") if isinstance(checked["manifest"].get("required_columns"), list) else []
    dedupe = checked["manifest"].get("dedupe_columns") if isinstance(checked["manifest"].get("dedupe_columns"), list) else required
    detailed_duplicates = (checked["manifest"].get("table_contract") or {}).get("version") == 2
    accepted, errors, seen, duplicates = [], [], set(), 0
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append({"row": index + 1, "code": "row_not_object"})
            continue
        missing = [field for field in required if not str(row.get(field) or "").strip()]
        if missing:
            errors.append({"row": index + 1, "code": "required", "columns": missing})
            continue
        key = _key(row, dedupe)
        if key in seen:
            duplicates += 1
            if detailed_duplicates:
                errors.append({"row": index + 1, "code": "duplicate"})
            continue
        seen.add(key)
        accepted.append(dict(row))
    invalid = sum(1 for error in errors if error["code"] != "duplicate")
    return {"schema": "localos_compiled_script_result_v1", "artifact_hash": checked["artifact_hash"], "runtime_ai_calls": 0, "external_effects": [], "rows": accepted, "report": {"received": len(rows), "accepted": len(accepted), "duplicates": duplicates, "invalid": invalid, "errors": errors}}


def _request_payload(artifact: dict[str, Any], input_payload: dict[str, Any]) -> tuple[bytes, dict[str, str]]:
    secret = os.environ.get("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", "")
    if len(secret) < 32:
        raise CompiledRuntimeUnavailable("compiled_script_runner_secret_missing")
    body = json.dumps({"artifact_hash": artifact["artifact_hash"], "source": artifact["source"], "manifest": artifact["manifest"], "fixtures": artifact["fixtures"], "input": input_payload}, ensure_ascii=False, separators=(",", ":")).encode()
    if len(body) > 262144:
        raise ValueError("compiled_input_invalid:request_size_limit")
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    signed = timestamp.encode() + b"." + nonce.encode() + b"." + body
    return body, {"Content-Type": "application/json", "X-Compiled-Timestamp": timestamp, "X-Compiled-Nonce": nonce, "X-Compiled-Signature": hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()}


def execute_in_attested_sandbox(artifact: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    checked = validate_artifact(artifact)
    if not checked["valid"]:
        raise ValueError("compiled_artifact_invalid")
    input_errors = validate_value(checked["manifest"]["input_schema"], input_payload)
    if input_errors:
        raise ValueError("compiled_input_invalid:" + ",".join(input_errors))
    if "table_contract" in checked["manifest"]:
        normalize_table_input(input_payload, checked["manifest"]["table_contract"]["columns"])
    endpoint = os.environ.get("COMPILED_SCRIPT_RUNNER_URL", "")
    expected_digest = os.environ.get("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "")
    if not endpoint or not expected_digest.startswith("sha256:"):
        raise CompiledRuntimeUnavailable("compiled_script_runner_not_attested")
    if checked["manifest"].get("runner_image_digest") != expected_digest:
        raise CompiledRuntimeUnavailable("compiled_script_runner_digest_changed")
    parsed = urlsplit(endpoint)
    if parsed.scheme != "http" or not parsed.hostname:
        raise CompiledRuntimeUnavailable("compiled_script_runner_endpoint_invalid")
    body, headers = _request_payload(artifact, input_payload)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=4)
    try:
        connection.request("POST", "/v1/run", body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read(1_100_000)
    except (OSError, http.client.HTTPException):
        raise CompiledRuntimeUnavailable("compiled_script_runner_unreachable") from None
    finally:
        connection.close()
    if response.status == 503:
        raise CompiledRuntimeUnavailable("compiled_script_runner_busy")
    if response.status == 408:
        raise CompiledRuntimeUnavailable("compiled_script_runner_timeout")
    if response.status not in {200, 422} or response.getheader("X-Compiled-Image-Digest") != expected_digest:
        raise CompiledRuntimeUnavailable("compiled_script_runner_rejected")
    signature = hmac.new(os.environ["COMPILED_SCRIPT_RUNNER_SHARED_SECRET"].encode(), raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(response.getheader("X-Compiled-Signature", ""), signature):
        raise CompiledRuntimeUnavailable("compiled_script_runner_response_invalid")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError):
        raise CompiledRuntimeUnavailable("compiled_script_runner_response_invalid") from None
    if response.status == 422:
        error_code = result.get("error") if isinstance(result, dict) else ""
        if error_code in {"compiled_script_failed", "compiled_script_output_limit", "script_result_must_be_object", "output_schema_invalid", "unsafe_source", "compiled_script_timeout"}:
            raise CompiledScriptRejected(error_code)
        raise CompiledRuntimeUnavailable("compiled_script_runner_rejected")
    if not isinstance(result, dict) or result.get("artifact_hash") != checked["artifact_hash"] or result.get("runtime_ai_calls") != 0 or result.get("external_effects") != []:
        raise CompiledRuntimeUnavailable("compiled_script_runner_contract_invalid")
    output_errors = validate_value(checked["manifest"]["output_schema"], _fixture_value(result))
    if output_errors:
        raise CompiledRuntimeUnavailable("compiled_script_runner_output_invalid")
    return result


def preview(artifact: dict[str, Any], input_payload: dict[str, Any]) -> dict[str, Any]:
    try:
        result = execute_in_attested_sandbox(artifact, input_payload)
    except CompiledScriptRejected:
        import sys
        return {"status": "failed", "safe_preview": True, "reason": str(sys.exc_info()[1]),
                "result": {"artifact_hash": artifact.get("artifact_hash")}, "fixture_results": []}
    pilot = (artifact.get("manifest") or {}).get("kind") == PILOT_KIND
    oracle = execute_pilot(artifact, input_payload) if pilot else None
    if oracle is not None and result != oracle:
        return {"status": "failed", "safe_preview": True, "reason": "oracle_mismatch", "result": result, "oracle": oracle}
    fixtures = artifact.get("fixtures") if isinstance(artifact.get("fixtures"), list) else []
    fixture_results = []
    for fixture in fixtures:
        fixture_input = fixture.get("input") if isinstance(fixture, dict) and isinstance(fixture.get("input"), dict) else {}
        expected = fixture.get("expected") if isinstance(fixture, dict) and "expected" in fixture else None
        try:
            actual = execute_in_attested_sandbox(artifact, fixture_input)
        except CompiledScriptRejected:
            import sys
            fixture_results.append({"source": fixture.get("source"), "input": fixture_input, "expected": expected,
                                    "actual": None, "passed": False, "error": str(sys.exc_info()[1])})
            continue
        actual_value = _fixture_value(actual)
        passed = expected is not None and actual_value == expected
        if pilot:
            passed = passed and actual == execute_pilot(artifact, fixture_input)
        fixture_results.append({"source": fixture.get("source"), "input": fixture_input, "expected": expected, "actual": actual_value, "passed": passed})
    has_user_expectation = any(item.get("source") == "user" and item.get("expected") is not None for item in fixture_results)
    fixtures_passed = bool(fixture_results) and all(item["passed"] for item in fixture_results)
    digest = hashlib.sha256(json.dumps({"artifact_hash": artifact.get("artifact_hash"), "fixtures": fixture_results}, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if not has_user_expectation or not fixtures_passed:
        return {"status": "failed", "safe_preview": True, "reason": "fixtures_failed", "result": result, "fixture_results": fixture_results, "fixture_digest": "sha256:" + digest}
    return {"status": "passed", "safe_preview": True, "result": result, "fixture_results": fixture_results, "fixture_digest": "sha256:" + digest}
