from __future__ import annotations

from datetime import datetime, timedelta, timezone

from services.outreach_playbook import beauty_outreach_guidance
from services.outreach_signal_hypothesis_service import derive_pain_signal_hypotheses
from services.outreach_safety_service import strategy_fingerprint


NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def social_post(identifier: str, text: str, age_days: int) -> dict:
    return {
        "id": identifier,
        "kind": "telegram_post",
        "fact": text,
        "source_url": f"https://t.me/company/{identifier}",
        "author_or_organization": "Компания",
        "observed_at": NOW - timedelta(days=age_days),
        "freshness": "fresh",
    }


def test_active_social_and_map_gap_becomes_marketing_hypothesis_not_recipient_fact():
    hypotheses = derive_pain_signal_hypotheses(
        {
            "rating": 4.3,
            "reviews_count": 3,
            "source_url": "https://yandex.ru/maps/org/1",
            "official_social_activity": {
                "official": True,
                "last_post_at": NOW - timedelta(days=2),
                "posts_30d": 6,
                "posts_90d": 12,
            },
        },
        [],
        now=NOW,
    )
    assert len(hypotheses) == 1
    result = hypotheses[0]
    assert result["signal_combo"] == "active_social_with_map_gap"
    assert result["pain_key"] == "marketing_and_clients"
    assert result["hypothesis_status"] == "segment_hypothesis_only"
    assert "старается" not in result["observed_fact"].lower()
    assert "вкладывается" not in result["observed_fact"].lower()
    assert "могут" in result["hypothesis"].lower()


def test_active_social_alone_does_not_diagnose_marketing_pain():
    hypotheses = derive_pain_signal_hypotheses(
        {
            "rating": 4.9,
            "reviews_count": 200,
            "source_url": "https://yandex.ru/maps/org/1",
            "official_social_activity": {
                "official": True,
                "last_post_at": NOW - timedelta(days=1),
                "posts_30d": 20,
                "posts_90d": 50,
            },
        },
        [],
        now=NOW,
    )
    assert hypotheses == []


def test_two_recent_open_slot_posts_create_testable_demand_hypothesis():
    ledger = [
        social_post("1", "Есть свободное окошко на завтра", 2),
        social_post("2", "Горящие окошки на выходные", 8),
    ]
    hypotheses = derive_pain_signal_hypotheses({}, ledger, now=NOW)
    result = next(item for item in hypotheses if item["signal_combo"] == "repeated_open_slots")
    assert result["pain_key"] == "marketing_and_clients"
    assert result["evidence_ids"] == ["1", "2"]
    assert "может" in result["hypothesis"].lower()


def test_one_open_slot_post_is_a_counterexample_not_a_pain_signal():
    hypotheses = derive_pain_signal_hypotheses(
        {},
        [social_post("1", "Есть свободное окошко на завтра", 2)],
        now=NOW,
    )
    assert all(item["signal_combo"] != "repeated_open_slots" for item in hypotheses)


def test_three_discount_posts_map_to_pricing_hypothesis_without_low_check_claim():
    hypotheses = derive_pain_signal_hypotheses(
        {},
        [
            social_post("1", "Акция недели на уход", 3),
            social_post("2", "Скидка на комплекс услуг", 15),
            social_post("3", "Новый промокод для записи", 40),
        ],
        now=NOW,
    )
    result = next(item for item in hypotheses if item["signal_combo"] == "repeated_discount_promotions")
    assert result["pain_key"] == "pricing_and_average_ticket"
    assert "средний чек низкий" not in result["hypothesis"].lower()


def test_repeated_hiring_does_not_claim_staff_turnover():
    hypotheses = derive_pain_signal_hypotheses(
        {},
        [
            social_post("1", "Ищем мастера в команду", 10),
            social_post("2", "Открыта вакансия администратора", 45),
        ],
        now=NOW,
    )
    result = next(item for item in hypotheses if item["signal_combo"] == "repeated_hiring_signals")
    assert result["pain_key"] == "staff_and_processes"
    assert "текуч" not in result["hypothesis"].lower()


def test_signal_library_is_versioned_and_contains_counterexamples():
    playbook = beauty_outreach_guidance()
    assert playbook["pain_signal_library_version"] == "beauty_pain_signals_v2"
    assert len(playbook["pain_signal_hypotheses"]) == 10
    assert all(item["contraindications"] for item in playbook["pain_signal_hypotheses"])
    assert all(item["status"] == "testable" for item in playbook["pain_signal_hypotheses"])


def test_learning_fingerprint_separates_signal_to_pain_hypotheses():
    base = {
        "workstream_type": "localos_sales",
        "channel": "email",
        "angle": "signal",
        "signal_combo": "public_activity",
    }
    marketing = strategy_fingerprint({
        **base,
        "signal_hypothesis_key": "repeated_open_slots",
        "signal_pain_key": "marketing_and_clients",
        "signal_hypothesis_status": "segment_hypothesis_only",
    })
    pricing = strategy_fingerprint({
        **base,
        "signal_hypothesis_key": "repeated_discount_promotions",
        "signal_pain_key": "pricing_and_average_ticket",
        "signal_hypothesis_status": "segment_hypothesis_only",
    })
    assert marketing != pricing


def test_active_social_and_missing_service_prices_create_pricing_hypothesis():
    hypotheses = derive_pain_signal_hypotheses(
        {
            "source_url": "https://yandex.ru/maps/org/1",
            "services_json": [
                {"name": "Услуга 1", "price": 1000},
                {"name": "Услуга 2", "price": ""},
                {"name": "Услуга 3"},
                {"name": "Услуга 4"},
                {"name": "Услуга 5", "price": 2000},
            ],
            "official_social_activity": {
                "official": True,
                "last_post_at": NOW - timedelta(days=3),
                "source_url": "https://t.me/company",
            },
        },
        [],
        now=NOW,
    )
    result = next(
        item for item in hypotheses
        if item["signal_combo"] == "active_social_with_service_price_gap"
    )
    assert result["pain_key"] == "pricing_and_average_ticket"
    assert "5 услуг" in result["observed_fact"]
    assert "цена указана у 2" in result["observed_fact"]


def test_active_social_and_unanswered_negative_review_never_copy_review_text():
    review_text = "Очень неприятное неподтверждённое обвинение"
    hypotheses = derive_pain_signal_hypotheses(
        {
            "source_url": "https://yandex.ru/maps/org/1",
            "reviews_json": [{
                "id": "review-1",
                "rating": 2,
                "date": (NOW - timedelta(days=20)).isoformat(),
                "text": review_text,
                "business_comment": "",
            }],
            "official_social_activity": {
                "official": True,
                "last_post_at": NOW - timedelta(days=2),
                "source_url": "https://t.me/company",
            },
        },
        [],
        now=NOW,
    )
    result = next(
        item for item in hypotheses
        if item["signal_combo"] == "active_social_with_unanswered_negative_review"
    )
    assert result["pain_key"] == "reviews_and_service"
    assert review_text not in result["observed_fact"]
    assert "оценкой до 3" in result["observed_fact"]


def test_recent_new_service_and_event_are_separate_timing_hypotheses():
    hypotheses = derive_pain_signal_hypotheses(
        {},
        [
            social_post("service", "Новая услуга - электроэпиляция", 3),
            social_post("event", "Приглашаем на клиентский день", 5),
        ],
        now=NOW,
    )

    combos = {item["signal_combo"] for item in hypotheses}
    assert "recent_new_service_announcement" in combos
    assert "recent_event_announcement" in combos
