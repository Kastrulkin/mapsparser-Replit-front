import pytest

from services.compiled_ai_pilot_credit_grant import grant_compiled_ai_pilot_credits


USER_ID = "c01b9480-34b9-479f-bd9b-96e1956f55d0"
EXTERNAL_ID = "compiled-ai-pilot:organika:first-wave-v1"


class CreditGrantCursor:
    def __init__(self, *, balance=0, existing=None, user_exists=True):
        self.balance = balance
        self.existing = existing
        self.user_exists = user_exists
        self.queries = []
        self.params = []
        self.next_row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).lower().split())
        self.queries.append(normalized)
        self.params.append(params)
        if "select credits_balance from users" in normalized:
            self.next_row = {"credits_balance": self.balance} if self.user_exists else None
        elif "from credit_ledger" in normalized:
            self.next_row = self.existing
        elif normalized.startswith("update users"):
            self.balance += int(params[0])
            self.next_row = None
        elif normalized.startswith("insert into credit_ledger"):
            self.existing = {
                "id": params[0],
                "user_id": params[1],
                "delta": params[2],
                "reason": params[3],
                "external_id": params[4],
            }
            self.next_row = None
        else:
            self.next_row = None

    def fetchone(self):
        return self.next_row


def test_credit_grant_dry_run_reports_change_without_mutation():
    cursor = CreditGrantCursor(balance=0)

    result = grant_compiled_ai_pilot_credits(
        cursor,
        user_id=USER_ID,
        credits=24,
        external_id=EXTERNAL_ID,
    )

    assert result == {
        "status": "ready",
        "applied": False,
        "user_id": USER_ID,
        "credits": 24,
        "balance_before": 0,
        "balance_after": 24,
        "external_id": EXTERNAL_ID,
        "credit_ledger_id": None,
    }
    assert cursor.balance == 0
    assert not any(query.startswith("update users") for query in cursor.queries)
    assert not any(query.startswith("insert into credit_ledger") for query in cursor.queries)


def test_credit_grant_apply_updates_balance_and_writes_positive_ledger_entry():
    cursor = CreditGrantCursor(balance=0)

    result = grant_compiled_ai_pilot_credits(
        cursor,
        user_id=USER_ID,
        credits=24,
        external_id=EXTERNAL_ID,
        apply=True,
    )

    assert result["status"] == "applied"
    assert result["applied"] is True
    assert result["balance_after"] == 24
    assert result["credit_ledger_id"]
    assert cursor.balance == 24
    assert cursor.existing["delta"] == 24
    assert cursor.existing["reason"] == "compiled_ai_pilot_credit_grant"
    assert cursor.existing["external_id"] == EXTERNAL_ID


def test_credit_grant_is_idempotent_for_matching_external_id():
    cursor = CreditGrantCursor(
        balance=24,
        existing={
            "id": "ledger-1",
            "user_id": USER_ID,
            "delta": 24,
            "reason": "compiled_ai_pilot_credit_grant",
            "external_id": EXTERNAL_ID,
        },
    )

    result = grant_compiled_ai_pilot_credits(
        cursor,
        user_id=USER_ID,
        credits=24,
        external_id=EXTERNAL_ID,
        apply=True,
    )

    assert result["status"] == "already_applied"
    assert result["applied"] is False
    assert result["credit_ledger_id"] == "ledger-1"
    assert cursor.balance == 24
    assert not any(query.startswith("update users") for query in cursor.queries)


def test_credit_grant_rejects_conflicting_external_id():
    cursor = CreditGrantCursor(
        existing={
            "id": "ledger-1",
            "user_id": USER_ID,
            "delta": 12,
            "reason": "compiled_ai_pilot_credit_grant",
            "external_id": EXTERNAL_ID,
        }
    )

    with pytest.raises(ValueError, match="external_id_conflicts"):
        grant_compiled_ai_pilot_credits(
            cursor,
            user_id=USER_ID,
            credits=24,
            external_id=EXTERNAL_ID,
            apply=True,
        )


@pytest.mark.parametrize("credits", [0, 25, -1, True])
def test_credit_grant_rejects_amounts_outside_pilot_limit(credits):
    with pytest.raises(ValueError):
        grant_compiled_ai_pilot_credits(
            CreditGrantCursor(),
            user_id=USER_ID,
            credits=credits,
            external_id=EXTERNAL_ID,
        )


def test_credit_grant_rejects_missing_user_and_non_pilot_external_id():
    with pytest.raises(ValueError, match="user_not_found"):
        grant_compiled_ai_pilot_credits(
            CreditGrantCursor(user_exists=False),
            user_id=USER_ID,
            credits=24,
            external_id=EXTERNAL_ID,
        )
    with pytest.raises(ValueError, match="external_id_must_use"):
        grant_compiled_ai_pilot_credits(
            CreditGrantCursor(),
            user_id=USER_ID,
            credits=24,
            external_id="manual-credit",
        )
