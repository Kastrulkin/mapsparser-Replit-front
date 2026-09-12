from datetime import datetime, timedelta, timezone

from core.card_platform_policy import rule_for
from services.card_growth_service import _actions_for_location, _measurement, _normalized_category, recommend_goal
from services.lead_journey_service import _next_action_spec, serialize_action


def _provider_state(provider="yandex"):
    facts = {
        "access": {"state": "observed", "confidence": 1.0},
        "verified": {"state": "observed", "confidence": 1.0},
        "duplicate": {"state": "observed", "confidence": 0.8},
        "category": {"state": "observed", "confidence": 1.0},
        "contacts": {"state": "observed", "confidence": 1.0},
        "schedule": {"state": "observed", "confidence": 1.0},
        "action_path": {"state": "observed", "confidence": 1.0},
        "services": {"state": "observed", "confidence": 1.0},
        "prices": {"state": "observed", "confidence": 1.0},
        "reviews": {"state": "observed", "confidence": 1.0},
        "review_responses": {"state": "observed", "confidence": 1.0},
        "photos": {"state": "observed", "confidence": 1.0},
        "publications": {"state": "observed", "confidence": 1.0},
    }
    if provider == "2gis":
        facts.pop("verified")
        facts["publications"] = {"state": "not_applicable", "confidence": 1.0}
    return {
        "provider": provider,
        "provider_label": {"yandex": "Яндекс", "google": "Google", "2gis": "2ГИС"}[provider],
        "source_state": "observed",
        "facts": facts,
        "metrics": {},
        "benchmark": {"sample_size": 0, "metrics": {}},
    }


def _location(provider_state):
    return {
        "business_id": "business-1",
        "business_name": "Тестовая точка",
        "providers": [provider_state],
    }


def test_unknown_fact_is_not_treated_as_missing():
    provider = _provider_state()
    provider["facts"]["category"] = {"state": "unknown", "confidence": 0.0}

    actions = _actions_for_location(_location(provider), "bookings")

    assert all(action["fact"] != "category" for action in actions)


def test_unknown_source_creates_one_refresh_action_without_guessing_missing_facts():
    provider = _provider_state()
    provider["source_state"] = "unknown"
    for fact in provider["facts"].values():
        fact["state"] = "unknown"

    actions = _actions_for_location(_location(provider), "bookings")

    assert len(actions) == 1
    assert actions[0]["gate"] == 0
    assert actions[0]["title"] == "Обновите данные Яндекс"


def test_critical_category_precedes_review_response_and_publication():
    provider = _provider_state()
    provider["facts"]["category"] = {"state": "missing", "confidence": 1.0}
    provider["facts"]["review_responses"] = {"state": "missing", "confidence": 1.0}
    provider["facts"]["publications"] = {"state": "missing", "confidence": 1.0}

    actions = _actions_for_location(_location(provider), "bookings")

    assert actions[0]["fact"] == "category"
    assert actions[0]["gate"] == 1
    assert actions[0]["priority"] > actions[1]["priority"]


def test_2gis_never_creates_publication_action():
    provider = _provider_state("2gis")

    actions = _actions_for_location(_location(provider), "inquiries")

    assert all(action["fact"] != "publications" for action in actions)
    assert rule_for("2gis", "publications")["influence"] == "not_applicable"
    assert rule_for("2gis", "publications")["applicability"] == "unsupported"
    assert rule_for("2gis", "publications")["verified_at"] == "2026-09-11"


def test_yandex_publication_is_not_marked_as_ranking_factor():
    provider = _provider_state()
    provider["facts"]["publications"] = {"state": "missing", "confidence": 1.0}

    actions = _actions_for_location(_location(provider), "website_visits")

    assert actions[0]["fact"] == "publications"
    assert actions[0]["influence"] == "conversion_only"


def test_goal_recommendation_uses_business_model():
    assert recommend_goal("Детская школа") == "bookings"
    assert recommend_goal("Ресторан") == "orders"
    assert recommend_goal("Парк") == "directions"
    assert recommend_goal("Трансферы") == "inquiries"


def test_benchmark_categories_normalize_comparable_business_names():
    assert _normalized_category("Детская парикмахерская") == "beauty"
    assert _normalized_category("Салон красоты") == "beauty"
    assert _normalized_category("Частная начальная школа") == "education"
    assert _normalized_category("Трансферы для туристов") == "transport"


def test_completed_action_waits_until_measurement_checkpoint():
    action = {
        "action_type": "complete_map_task",
        "flow_type": "maps",
        "payload_json": {
            "managed_growth_cycle": True,
            "measurement_days": [14, 28],
            "tasks_total": 1,
        },
    }

    next_type, status, due_at, payload = _next_action_spec(action, "complete", {})

    assert next_type == "compare_snapshot"
    assert status == "completed"
    assert due_at > datetime.now(timezone.utc) + timedelta(days=13)
    assert payload["checkpoint_days"] == 14


def test_waiting_measurement_has_no_command_before_due_date():
    action = {
        "id": "action-1",
        "action_type": "compare_snapshot",
        "flow_type": "maps",
        "status": "waiting",
        "due_at": datetime.now(timezone.utc) + timedelta(days=2),
        "payload_json": {},
    }

    assert serialize_action(action)["allowed_commands"] == []


def test_measurement_contract_exposes_14_28_and_60_day_checks():
    cycle = {
        "status": "waiting_for_measurement",
        "started_at": datetime.now(timezone.utc),
        "measurement_days_json": [14, 28, 60],
    }

    measurement = _measurement(cycle)

    assert [checkpoint["days"] for checkpoint in measurement["checkpoints"]] == [14, 28, 60]
    assert measurement["status"] == "waiting_for_measurement"


def test_measurement_dates_start_when_action_was_completed():
    completed_at = datetime.now(timezone.utc) - timedelta(days=2)
    cycle = {
        "status": "waiting_for_measurement",
        "started_at": completed_at - timedelta(days=20),
        "action_completed_at": completed_at,
        "measurement_days_json": [14, 28],
    }

    measurement = _measurement(cycle)

    first_due = datetime.fromisoformat(measurement["checkpoints"][0]["due_at"])
    assert first_due == completed_at + timedelta(days=14)


def test_completed_checkpoint_does_not_remain_due():
    cycle = {
        "status": "waiting_for_measurement",
        "action_completed_at": datetime.now(timezone.utc) - timedelta(days=20),
        "measurement_days_json": [14, 28],
        "measurement_json": {"checkpoint_days": 14},
    }

    measurement = _measurement(cycle)

    assert [checkpoint["status"] for checkpoint in measurement["checkpoints"]] == ["completed", "waiting"]
