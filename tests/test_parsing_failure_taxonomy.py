from parsing_failure_taxonomy import (
    REASON_CAPTCHA,
    REASON_EMPTY_PAYLOAD,
    REASON_PROXY_TRANSPORT,
    REASON_QUALITY_GATE_FAIL,
    REASON_RETRY_EXHAUSTED,
    REASON_TASK_TTL_EXCEEDED,
    classify_failure_reason,
    with_reason_code_prefix,
)


def test_classify_captcha_reason():
    assert classify_failure_reason("captcha", "captcha_required: x") == REASON_CAPTCHA
    assert classify_failure_reason("error", "Вы не робот?") == REASON_CAPTCHA


def test_classify_proxy_transport_reason():
    msg = "playwright failed net::ERR_PROXY_CONNECTION_FAILED"
    assert classify_failure_reason("error", msg) == REASON_PROXY_TRANSPORT


def test_classify_empty_payload_reason():
    msg = "transient_error=org_api_not_loaded; detail=error"
    assert classify_failure_reason("error", msg) == REASON_EMPTY_PAYLOAD


def test_classify_quality_gate_reason():
    msg = "low_quality_payload:quality_score=0.2"
    assert classify_failure_reason("error", msg) == REASON_QUALITY_GATE_FAIL


def test_reason_code_prefix_idempotent():
    msg = with_reason_code_prefix("captcha", "captcha_required: u")
    assert msg.startswith("reason_code=captcha;")
    same = with_reason_code_prefix("captcha", msg)
    assert same == msg


def test_classify_dlq_reasons():
    ttl_msg = "reason_code=unknown; dlq_reason=task_ttl_exceeded; task_age_hours=77"
    retry_msg = "reason_code=unknown; dlq_reason=captcha_retry_exhausted; attempt=5"
    assert classify_failure_reason("error", ttl_msg) == REASON_TASK_TTL_EXCEEDED
    assert classify_failure_reason("error", retry_msg) == REASON_RETRY_EXHAUSTED
