from __future__ import annotations

import uuid

import pytest

from services.manual_access_grants import create_manual_access_grant


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.description = []

    def execute(self, query, params=None):
        self.calls.append((" ".join(query.split()), params))

    def fetchone(self):
        return self.results.pop(0)

    def fetchall(self):
        return self.results.pop(0)


def grant(cursor, *, request_id=None, **overrides):
    payload = {
        "actor_user_id": str(uuid.uuid4()),
        "target_type": "business",
        "target_id": "business-1",
        "tariff_id": "pro_monthly",
        "period_end": "2026-11-05",
        "payment_amount_rub": 5000,
        "payment_reference": "Перевод 05.10",
        "request_id": request_id or str(uuid.uuid4()),
    }
    payload.update(overrides)
    return create_manual_access_grant(cursor, **payload)


def test_offline_professional_grant_updates_access_and_credits_atomically():
    cursor = FakeCursor([
        None,
        {"id": "business-1", "name": "Клиент", "owner_id": "user-1"},
        {"id": "user-1", "credits_balance": 40},
    ])

    result = grant(cursor)

    assert result["status"] == "applied"
    assert result["tier"] == "professional"
    assert result["credit_amount"] == 1000
    assert result["balance_before"] == 40
    assert result["balance_after"] == 1040
    assert result["payment_amount_rub"] == 5000
    statements = [call[0] for call in cursor.calls]
    assert any(statement.startswith("UPDATE businesses") for statement in statements)
    assert any(statement.startswith("UPDATE users SET credits_balance") for statement in statements)
    assert any(statement.startswith("INSERT INTO credit_ledger") for statement in statements)
    assert any(statement.startswith("INSERT INTO manual_access_grants") for statement in statements)
    assert not any(statement.startswith("INSERT INTO subscriptions") for statement in statements)


def test_repeat_request_id_returns_existing_grant_without_second_credit_update():
    request_id = str(uuid.uuid4())
    cursor = FakeCursor([
        {
            "id": "grant-1", "request_id": request_id, "target_type": "business",
            "target_id": "business-1", "user_id": "user-1", "tariff_id": "pro_monthly",
            "credit_amount": 1000, "balance_after": 1000, "payment_amount_rub": 5000,
        },
    ])

    result = grant(cursor, request_id=request_id)

    assert result["status"] == "already_applied"
    assert result["applied"] is False
    assert not any("UPDATE users SET credits_balance" in call[0] for call in cursor.calls)


def test_request_id_cannot_be_reused_for_a_different_payment():
    request_id = str(uuid.uuid4())
    cursor = FakeCursor([
        {
            "id": "grant-1", "request_id": request_id, "target_type": "business",
            "target_id": "another-business", "user_id": "user-1", "tariff_id": "pro_monthly",
            "credit_amount": 1000, "balance_after": 1000, "payment_amount_rub": 5000,
        },
    ])

    with pytest.raises(ValueError, match="request_id_conflicts_with_existing_grant"):
        grant(cursor, request_id=request_id)


def test_network_credits_are_granted_once_to_network_owner():
    cursor = FakeCursor([
        None,
        {"id": "network-1", "name": "Сеть", "owner_id": "network-owner"},
        [{"id": "business-1"}, {"id": "business-2"}],
        {"id": "network-owner", "credits_balance": 7},
    ])

    result = grant(cursor, target_type="network", target_id="network-1")

    assert result["business_ids"] == ["business-1", "business-2"]
    assert result["balance_after"] == 1007
    assert sum("UPDATE users SET credits_balance" in call[0] for call in cursor.calls) == 1


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("payment_amount_rub", 0, "invalid_payment_amount"),
        ("period_end", "not-a-date", "invalid_period_end"),
        ("payment_reference", "x" * 501, "payment_reference_too_long"),
        ("tariff_id", "unknown", "invalid_tariff"),
    ],
)
def test_invalid_manual_grant_is_rejected_before_database_writes(field, value, error):
    cursor = FakeCursor([])

    with pytest.raises(ValueError, match=error):
        grant(cursor, **{field: value})

    assert cursor.calls == []
