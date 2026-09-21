from typing import Any


REASON_CAPTCHA = "captcha"
REASON_EMPTY_PAYLOAD = "empty_payload"
REASON_PARSER_MISMATCH = "parser_mismatch"
REASON_PROXY_TRANSPORT = "proxy_transport"
REASON_TIMEOUT = "timeout"
REASON_BLOCKED_SESSION = "blocked_session"
REASON_INVALID_ORG_URL = "invalid_org_url"
REASON_QUALITY_GATE_FAIL = "quality_gate_fail"
REASON_RETRY_EXHAUSTED = "retry_exhausted"
REASON_TASK_TTL_EXCEEDED = "task_ttl_exceeded"
REASON_CLOSED_BUSINESS = "closed_business"
REASON_UNKNOWN = "unknown"


def safe_parser_error_code(value: Any) -> str:
    """Keep only local parser codes; provider text is not a diagnostic code."""
    code = str(value or "").strip()
    if code in {
        "captcha_detected", "captcha_session_lost", "org_api_not_loaded",
        "yandex_rate_limited", "yandex_forbidden", "invalid_org_url",
        "empty_url", "unsupported_2gis_url", "2gis_parse_failed",
        "2gis_catalog_missing_firm_id", "2gis_catalog_missing_api_key",
        "2gis_catalog_api_failed", "2gis_http_fallback_failed",
        "parser_returned_none", "parser_returned_list", "parser_returned_tuple",
        "parser_returned_str", "parser_returned_int", "parser_returned_float",
        "parser_returned_bool", "parser_returned_bytes", "parser_returned_set",
        "parser_subprocess_exception", "parser_subprocess_timeout",
        "parser_subprocess_no_result", "parser_subprocess_invalid_result",
        "apify_parser_subprocess_exception", "apify_parser_subprocess_timeout",
        "apify_parser_subprocess_no_result", "apify_parser_subprocess_invalid_result",
        "apify_parser_subprocess_result_read_failed", "apify_empty_dataset",
        "native_parser_exception", "apify_fallback_exception",
        "proxy_preflight_failed", "services_upsert_zero",
    }:
        return code
    return "parser_error"


def classify_failure_reason(status: Any, error_message: Any) -> str:
    status_lc = str(status or "").strip().lower()
    text = str(error_message or "").strip().lower()

    if status_lc == "captcha":
        return REASON_CAPTCHA
    if "captcha_required" in text or "captcha_detected" in text or "вы не робот" in text:
        return REASON_CAPTCHA

    if "invalid_org_url" in text or "invalid org url" in text:
        return REASON_INVALID_ORG_URL

    if text.startswith("business_closed:"):
        return REASON_CLOSED_BUSINESS

    if "dlq_reason=task_ttl_exceeded" in text:
        return REASON_TASK_TTL_EXCEEDED
    if "dlq_reason=captcha_retry_exhausted" in text:
        return REASON_RETRY_EXHAUSTED

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
