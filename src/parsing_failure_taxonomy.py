from typing import Any


REASON_CAPTCHA = "captcha"
REASON_EMPTY_PAYLOAD = "empty_payload"
REASON_PARSER_MISMATCH = "parser_mismatch"
REASON_PROXY_TRANSPORT = "proxy_transport"
REASON_TIMEOUT = "timeout"
REASON_BLOCKED_SESSION = "blocked_session"
REASON_INVALID_ORG_URL = "invalid_org_url"
REASON_QUALITY_GATE_FAIL = "quality_gate_fail"
REASON_UNKNOWN = "unknown"


def classify_failure_reason(status: Any, error_message: Any) -> str:
    status_lc = str(status or "").strip().lower()
    text = str(error_message or "").strip().lower()

    if status_lc == "captcha":
        return REASON_CAPTCHA
    if "captcha_required" in text or "captcha_detected" in text or "вы не робот" in text:
        return REASON_CAPTCHA

    if "invalid_org_url" in text or "invalid org url" in text:
        return REASON_INVALID_ORG_URL

    if "blocked session" in text or "session lost" in text or "captcha_session_lost" in text:
        return REASON_BLOCKED_SESSION

    if (
        "err_proxy_connection_failed" in text
        or "err_tunnel_connection_failed" in text
        or "proxy authentication" in text
        or "407" in text
        or "forbidden" in text
    ):
        return REASON_PROXY_TRANSPORT

    if (
        "timeout" in text
        or "timed out" in text
        or "navigation timeout" in text
        or "parser_subprocess_timeout" in text
    ):
        return REASON_TIMEOUT

    if "low_quality_payload" in text or "services_upsert_zero" in text:
        return REASON_QUALITY_GATE_FAIL

    if (
        "org_api_not_loaded" in text
        or "parser_returned_none" in text
        or "empty payload" in text
    ):
        return REASON_EMPTY_PAYLOAD

    if (
        "parser_subprocess_exception" in text
        or "playwright" in text
        or "cannot access 'l' before initialization" in text
        or "module not found" in text
    ):
        return REASON_PARSER_MISMATCH

    return REASON_UNKNOWN


def with_reason_code_prefix(status: Any, error_message: Any) -> str:
    message = str(error_message or "").strip()
    if not message:
        return message
    if "reason_code=" in message:
        return message
    reason = classify_failure_reason(status, message)
    return f"reason_code={reason}; {message}"
