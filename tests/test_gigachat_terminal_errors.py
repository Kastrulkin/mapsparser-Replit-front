import json

import pytest
import requests

from services.contact_intelligence_service import (
    PersonalizationGenerationError,
    fail_enrichment_job,
    provider_error_is_retryable,
)
from services.gigachat_client import GigaChatClient, GigaChatProviderError
from services.outreach_personalization_ai import generate_personalized_sequence


class ProviderResponse:
    status_code = 402
    text = "provider billing body must stay private"

    def raise_for_status(self):
        raise requests.HTTPError(response=self)

    def json(self):
        return {"private": self.text}


class FailureCursor:
    def __init__(self):
        self.executions = []

    def execute(self, query, params=None):
        self.executions.append((query, params or ()))

    def fetchone(self):
        status = self.executions[0][1][0]
        return {"id": "job-1", "workstream_id": "ws-1", "status": status}


def valid_personalization_input():
    return {
        "motion": "localos_sales",
        "identity": {"company_name": "Клиника"},
        "candidate": {
            "evidence_id": "map-1",
            "observed_fact": "В карточке указано 27 отзывов",
            "source_url": "https://maps.example/clinic",
        },
        "founder_story": {"story": "Я развиваю LocalOS", "offer": "Короткий разбор"},
        "sequence": [{"sequence_index": 0, "channel": "email", "angle": "signal", "day_offset": 0}],
    }


def test_gigachat_402_is_terminal_after_one_request_and_redacts_body(monkeypatch):
    client = object.__new__(GigaChatClient)
    client.verify_tls = True
    calls = []

    def post(*_args, **_kwargs):
        calls.append(True)
        return ProviderResponse()

    monkeypatch.setattr("services.gigachat_client.requests.post", post)
    monkeypatch.setattr("services.gigachat_client.time.sleep", lambda *_args: None)

    with pytest.raises(GigaChatProviderError) as caught:
        client._post_with_retry(
            "https://api.giga.chat/v1/chat/completions",
            {"Authorization": "Bearer synthetic"},
            {"messages": []},
        )

    assert len(calls) == 1
    assert caught.value.code == "gigachat_payment_required"
    assert caught.value.retryable is False
    assert "provider billing body" not in str(caught.value)


def test_outreach_preserves_terminal_provider_code_without_private_body():
    def generator(*_args, **_kwargs):
        raise GigaChatProviderError(
            code="gigachat_payment_required",
            status_code=402,
            retryable=False,
        )

    result = generate_personalized_sequence(**valid_personalization_input(), generator=generator)

    assert result["status"] == "failed"
    assert result["error_code"] == "gigachat_payment_required"
    assert result["retryable"] is False
    assert "billing body" not in json.dumps(result)


def test_terminal_personalization_failure_finishes_enrichment_without_retry():
    error = PersonalizationGenerationError(
        "gigachat_payment_required",
        "GigaChat request rejected (HTTP 402)",
        retryable=False,
    )
    cursor = FailureCursor()

    assert provider_error_is_retryable(error) is False
    result = fail_enrichment_job(
        cursor,
        {"id": "job-1", "attempt_count": 0, "max_attempts": 2},
        error,
    )

    assert result["status"] == "failed"
    assert cursor.executions[0][1][4] == "gigachat_payment_required"
