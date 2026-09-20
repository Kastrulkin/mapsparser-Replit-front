"""Read-only message metadata keeps Russian legacy copy and factual data intact."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from core.card_platform_policy import provider_rules
from services import card_growth_service


def provider_state(provider="yandex"):
    return {
        "provider": provider, "source_state": "observed",
        "facts": {rule["fact"]: {"state": "missing", "confidence": 1.0}
                  for rule in provider_rules(provider) if rule["applicability"] != "unsupported"},
        "metrics": {"reviews_count": 2},
        "benchmark": {"sample_size": 10, "metrics": {"reviews_count": {"median": 12.5}}},
    }


def location(provider):
    return {"business_id": "synthetic-1", "business_name": "Весёлая расчёска", "providers": [provider]}


@pytest.mark.parametrize(("provider", "fact"), [(provider, rule["fact"])
    for provider in ("google", "yandex", "2gis") for rule in provider_rules(provider)
    if rule["applicability"] != "unsupported"])
@pytest.mark.parametrize("goal", sorted(card_growth_service.GOALS))
def test_action_has_stable_copy_code_without_changing_legacy_contract(provider, fact, goal):
    actions = card_growth_service._actions_for_location(location(provider_state(provider)), goal)
    action = next(item for item in actions if item["fact"] == fact)
    title, reason, cta, url = card_growth_service._action_copy(provider, fact, "missing")
    assert action["title"] == title
    assert action["reason"].startswith(reason)
    assert action["cta_label"] == cta
    assert action["cta_url"] == url
    assert action["target_scope"] == {"kind": "business", "id": "synthetic-1"}
    assert action["business_name"] == "Весёлая расчёска"
    assert action["provider_label"] == {"google": "Google", "yandex": "Яндекс", "2gis": "2ГИС"}[provider]
    assert action["copy_code"] == fact
    assert action["copy_params"] == ({"goal": goal, "benchmark_median": 12.5}
                                     if fact == "reviews" else {"goal": goal})


@pytest.mark.parametrize(("source", "code"), [("unknown", "refresh"), ("blocked", "restore")])
def test_refresh_copy_does_not_conflate_missing_source_and_failed_source(source, code):
    provider = provider_state()
    provider["source_state"] = source
    actions = card_growth_service._actions_for_location(location(provider), "orders")
    assert len(actions) == 1
    assert actions[0]["copy_code"] == code
    assert actions[0]["copy_params"] == {"goal": "orders"}
    assert actions[0]["cta_url"] == "/dashboard/card"


def test_blocked_fact_copy_is_distinct_from_missing_fact():
    provider = provider_state()
    provider["facts"] = {"contacts": {"state": "blocked", "confidence": 0.0}}
    action = card_growth_service._actions_for_location(location(provider), "inquiries")[0]
    assert action["copy_code"] == "blocked"
    assert action["title"] == "Восстановите обновление Яндекс"


@pytest.fixture
def synthetic_sources(monkeypatch):
    monkeypatch.setattr(card_growth_service, "_review_state", lambda *args: (None, None, None))
    monkeypatch.setattr(card_growth_service, "_priced_services", lambda *args: (3, 2))
    monkeypatch.setattr(card_growth_service, "_latest_search_queries", lambda *args: [])
    monkeypatch.setattr(card_growth_service, "_benchmark", lambda *args: {})


@pytest.mark.parametrize(("provider", "news_code"), [("yandex", "conversion_content"), ("2gis", "no_organic_news")])
def test_fact_evidence_codes_preserve_external_values(synthetic_sources, provider, news_code):
    business = {"id": "synthetic-1", "phone": "synthetic-phone", "working_hours": "synthetic-hours"}
    parse = {"created_at": datetime.now(timezone.utc), "categories": ["Салон"], "overview": {"is_duplicate": False}}
    facts = card_growth_service._provider_state(None, business, provider, {"url": "synthetic"}, parse)["facts"]
    expected = {"access": "connected", "duplicate": "no_duplicates", "contacts": "internal_contacts",
                "schedule": "internal_schedule", "services": "internal_services", "prices": "internal_prices",
                "publications": news_code}
    for fact, code in expected.items():
        assert facts[fact]["evidence_code"] == code
        assert facts[fact]["evidence"]
    assert facts["category"]["value"] == ["Салон"]
    assert facts["category"]["evidence_code"] is None


def test_missing_link_and_unverified_duplicate_have_distinct_codes(synthetic_sources):
    facts = card_growth_service._provider_state(None, {"id": "synthetic-1"}, "google", None, None)["facts"]
    assert facts["access"]["evidence_code"] == "link_missing"
    assert facts["duplicate"]["evidence_code"] == "duplicate_unverified"


def test_source_failure_replaces_evidence_code_together_with_text(synthetic_sources):
    facts = card_growth_service._provider_state(None, {"id": "synthetic-1"}, "2gis", {"url": "synthetic"}, {"status": "failed"})["facts"]
    assert facts["access"]["evidence_code"] == "connected"
    assert facts["publications"]["evidence_code"] == "no_organic_news"
    for name, fact in facts.items():
        if name not in {"access", "publications"}:
            assert fact["state"] == "blocked"
            assert fact["evidence_code"] == "source_error"


@pytest.mark.parametrize("decision", ["insufficient_data", "continue", "adjust", "replace", "future_decision"])
def test_legacy_measurement_gets_codes_without_mutating_stored_json(decision):
    cycle = {"decision": decision, "decision_reason": "Системное объяснение", "started_at": "2026-09-01T00:00:00Z",
             "measurement_json": {"checkpoint_days": 14, "disclaimer": "Платформенные действия — не продажи."}}
    before = deepcopy(cycle)
    measurement = card_growth_service._measurement(cycle)
    assert measurement["decision_reason_code"] == (None if decision == "future_decision" else decision)
    assert measurement["decision_reason"] == cycle["decision_reason"]
    assert measurement["result"]["disclaimer_code"] == "platform_actions_not_sales"
    assert cycle == before


def test_old_measurement_json_decision_gets_code_without_rewriting_raw_fields():
    cycle = {"measurement_json": {"decision": "continue", "decision_reason": "Действия выросли"}}
    before = deepcopy(cycle)
    measurement = card_growth_service._measurement(cycle)
    assert measurement["decision_reason_code"] == "continue"
    assert measurement["decision"] == "continue"
    assert measurement["decision_reason"] == "Действия выросли"
    assert measurement["result"]["decision_reason"] == "Действия выросли"
    assert cycle == before


def test_no_provider_action_has_explicit_copy_code(monkeypatch):
    monkeypatch.setattr(card_growth_service, "_business", lambda *args: {"id": "synthetic-1", "name": "Весёлая расчёска"})
    monkeypatch.setattr(card_growth_service, "_latest_sources", lambda *args: ({}, {}))
    monkeypatch.setattr(card_growth_service, "_active_cycle", lambda *args: None)
    monkeypatch.setattr(card_growth_service, "_baseline", lambda *args: {})
    growth = card_growth_service.build_card_growth(None, {"business_id": "synthetic-1"})
    action = growth["focus_action"]
    assert action["copy_code"] == "add_provider"
    assert action["copy_params"] == {"goal": "inquiries"}
    assert action["title"] == "Добавьте площадку для проверки"
    assert action["cta_url"] == "/dashboard/profile"


class EmptyReadCursor:
    def execute(self, sql, args):
        assert sql.lstrip().startswith("SELECT")

    def fetchall(self):
        return []


def test_metric_disclaimers_have_stable_codes(monkeypatch):
    monkeypatch.setattr(card_growth_service, "_table_exists", lambda *args: True)
    cursor = EmptyReadCursor()
    baseline = card_growth_service._baseline(cursor, "synthetic-1")
    benchmark = card_growth_service._benchmark(cursor, {"id": "synthetic-1"}, "yandex")
    assert baseline["disclaimer_code"] == "views_not_sales"
    assert benchmark["disclaimer_code"] == "relative_benchmark"
