from services.operator_consent_policy import (
    default_consent_policy,
    is_auto_execution_allowed,
    normalize_consent_policy_row,
    validate_consent_policy_payload,
)


def test_default_consent_policy_asks_each_time() -> None:
    policy = default_consent_policy("biz-1", "map_reviews_refresh")

    assert policy["mode"] == "ask_each_time"
    assert policy["is_persisted"] is False
    assert policy["execution_allowed_without_prompt"] is False


def test_auto_with_limits_requires_explicit_action_and_daily_limits() -> None:
    cleaned, errors = validate_consent_policy_payload(
        "map_reviews_refresh",
        {"mode": "auto_with_limits", "max_credits_per_action": 20},
    )

    assert cleaned is None
    assert "required_max_credits_per_day" in errors


def test_valid_auto_with_limits_marks_execution_allowed() -> None:
    cleaned, errors = validate_consent_policy_payload(
        "map_reviews_refresh",
        {
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
            "max_credits_per_month": 1000,
            "low_balance_warning_threshold": 50,
        },
    )

    assert errors == []
    assert cleaned is not None
    policy = normalize_consent_policy_row("biz-1", "map_reviews_refresh", cleaned)
    assert is_auto_execution_allowed(policy) is True


def test_unknown_action_key_is_rejected() -> None:
    cleaned, errors = validate_consent_policy_payload("unknown_action", {"mode": "ask_each_time"})

    assert cleaned is None
    assert "unknown_action_key" in errors
