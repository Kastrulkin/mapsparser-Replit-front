from datetime import date

from core.industry_patterns import (
    detect_industry_key,
    evaluate_pattern_fit,
    format_industry_pattern_prompt,
    get_industry_pattern_profile,
)
import core.industry_pattern_recalibration as recalibration
from core.industry_pattern_recalibration import (
    _build_proposals,
    build_pattern_impact_metrics,
    classify_industry_pattern_impact_item,
    compare_industry_pattern_version_texts,
    format_monthly_industry_pattern_impact_report,
    build_revised_pattern_text,
    format_monthly_recalibration_summary,
    previous_month_range,
    summarize_industry_pattern_detail_events,
)
from core.service_optimization_verticals import (
    detect_service_optimization_vertical,
    get_service_optimization_vertical_context,
)


def test_detects_food_without_beauty_drift() -> None:
    key = detect_industry_key(
        business_name="Хлебник",
        business_type="bakery",
        industry="food",
        categories='["Пекарня", "кофейня"]',
    )

    assert key == "food"
    prompt = format_industry_pattern_prompt(key, mode="news")
    assert "свежая выпечка" in prompt
    assert "салон красоты" not in prompt.lower()


def test_beauty_patterns_keep_guardrails_as_priority() -> None:
    prompt = format_industry_pattern_prompt("beauty", mode="service")

    assert "исходные факты -> guardrails" in prompt
    assert "препарат" in prompt
    assert "объем" in prompt
    assert "число зон" in prompt


def test_vertical_context_is_extended_by_industry_patterns() -> None:
    vertical = detect_service_optimization_vertical(
        business_name="Хлебник",
        business_type="bakery",
        industry="food",
        categories='["Пекарня"]',
    )
    context = get_service_optimization_vertical_context(vertical)

    assert vertical == "food"
    assert any("Продукт" in item for item in context["rules"])
    assert "food" in context["categories"]


def test_pattern_fit_flags_medical_claims() -> None:
    result = evaluate_pattern_fit("Лечение акне без боли с гарантией результата", "medical", mode="service")

    assert result["status"] == "needs_review"
    assert "forbidden_claim" in result["issue_codes"]


def test_profile_shape_contains_required_fields() -> None:
    profile = get_industry_pattern_profile("hospitality")

    for key in (
        "industry_key",
        "label",
        "markers",
        "service_patterns",
        "news_patterns",
        "review_reply_patterns",
        "forbidden_claims",
        "forbidden_industry_drifts",
        "positive_signals",
        "examples",
        "version",
    ):
        assert key in profile


def test_previous_month_range_uses_full_previous_month() -> None:
    start_day, end_day = previous_month_range(date(2026, 5, 6))

    assert start_day.isoformat() == "2026-04-01"
    assert end_day.isoformat() == "2026-04-30"


def test_monthly_summary_is_human_in_the_loop() -> None:
    text = format_monthly_recalibration_summary(
        start_day=date(2026, 4, 1),
        end_day=date(2026, 4, 30),
        counts={
            "audits": 12,
            "services": 120,
            "reviews": 55,
            "review_replies": 20,
            "news": 3,
        },
        proposals=[
            {
                "industry_key": "food",
                "pattern_type": "news",
                "proposed_pattern": "Продукт дня, свежая выпечка, кофе + продукт.",
            }
        ],
        created_count=1,
    )

    assert "Ежемесячная калибровка LocalOS" in text
    assert "Создано pending-предложений: 1" in text
    assert "Ничего не применено автоматически" in text


def test_build_proposals_uses_real_samples_and_examples() -> None:
    entities = [
        {
            "source": "business",
            "id": f"b{index}",
            "name": f"Пекарня {index}",
            "rating": 4.8,
            "reviews_count": 80,
            "industry_key": "food",
        }
        for index in range(1, 5)
    ]
    samples = {
        "food": {
            "service": [
                {"business_id": "b1", "text": "Круассан с кофе завтрак"},
                {"business_id": "b2", "text": "Свежая выпечка и кофе"},
                {"business_id": "b3", "text": "Кофе и круассан утром"},
            ],
            "news": [
                {"business_id": "b1", "text": "Сегодня свежая выпечка к завтраку"},
                {"business_id": "b2", "text": "Кофе и свежая выпечка утром"},
                {"business_id": "b3", "text": "Завтрак с кофе и круассаном"},
            ],
            "review_reply": [
                {"business_id": "b1", "text": "Спасибо за отзыв о кофе"},
                {"business_id": "b2", "text": "Спасибо, что отметили свежую выпечку"},
                {"business_id": "b3", "text": "Спасибо за теплые слова о завтраке"},
            ],
        }
    }

    proposals = _build_proposals(
        entities,
        {"audits": 4, "services": 3, "reviews": 3, "review_replies": 3, "news": 3},
        samples,
    )

    assert len(proposals) == 3
    service = next(item for item in proposals if item["pattern_type"] == "service")
    assert "Частые рабочие маркеры" in service["proposed_pattern"]
    assert service["source_counts"]["service_samples"] == 3
    assert service["examples"][0]["text"] == "Круассан с кофе завтрак"
    assert service["confidence"] >= 0.5


def test_build_proposals_skips_industry_without_text_evidence() -> None:
    entities = [
        {"source": "business", "id": f"b{index}", "name": f"Clinic {index}", "industry_key": "medical"}
        for index in range(1, 5)
    ]

    proposals = _build_proposals(
        entities,
        {"audits": 4, "services": 0, "reviews": 0, "review_replies": 0, "news": 0},
        {"medical": {"service": [], "news": [], "review_reply": []}},
    )

    assert proposals == []


def test_revised_pattern_text_keeps_original_and_comment() -> None:
    text = build_revised_pattern_text(
        "Для индустрии Food использовать продукт дня.",
        "Слишком общее",
        2,
    )

    assert "Уточненная версия 2" in text
    assert "Для индустрии Food использовать продукт дня" in text
    assert "Слишком общее" in text
    assert "без общих советов" in text


def test_pattern_impact_metrics_counts_service_quality_signals() -> None:
    metrics = build_pattern_impact_metrics(
        {
            "services": [
                {
                    "optimized_name": "Биоревитализация Belarti lift 1 ml",
                    "seo_description": "Биоревитализация Belarti lift 1 ml для ухода за кожей.",
                    "seo_keyword_score": {"total": 2, "found": 2, "close_count": 0, "missing": []},
                    "pattern_fit": {"status": "good"},
                },
                {
                    "optimized_name": "Ваксинг бровей",
                    "seo_description": "Услуга по исходному формату записи.",
                    "seo_keyword_score": {"total": 2, "found": 1, "close_count": 1, "missing": ["депиляция"]},
                    "pattern_fit": {"status": "needs_review"},
                    "guardrail_reasons": ["narrowed_service"],
                    "fallback_used": True,
                },
            ]
        },
        "service",
    )

    assert metrics["total"] == 2
    assert metrics["fallback"] == 1
    assert metrics["guardrail_failed"] == 1
    assert metrics["pattern_fit"] == 1
    assert metrics["missing_keywords"] == 1
    assert metrics["needs_review"] >= 1


def test_pattern_impact_metrics_tracks_business_effect_signals() -> None:
    metrics = build_pattern_impact_metrics(
        {
            "services": [
                {
                    "optimized_name": "Биоревитализация Belarti lift 1 ml",
                    "seo_score_before": 42,
                    "seo_score_after": 56,
                    "seo_keyword_score_before": {"total": 2, "found": 1},
                    "seo_keyword_score": {"total": 2, "found": 2, "missing": []},
                    "accepted": True,
                },
                {
                    "optimized_name": "Коррекция бровей мужская",
                    "seo_score_delta": 3,
                    "seo_keyword_score_before": {"total": 1, "found": 0},
                    "seo_keyword_score": {"total": 1, "found": 1, "missing": []},
                    "manual_edit": True,
                },
            ]
        },
        "service",
    )

    assert metrics["seo_score_delta"] == 17
    assert metrics["keyword_found_delta"] == 2
    assert metrics["accepted"] == 1
    assert metrics["manual_edits"] == 1
    assert metrics["business_effect_score"] > 0
    assert metrics["business_effect_status"] == "positive"


def test_pattern_impact_metrics_flags_news_fact_risk_and_drift() -> None:
    metrics = build_pattern_impact_metrics(
        {"generated_text": "Сегодня скидка на стрижку и свежие круассаны для гостей АЗС."},
        "news",
        industry_key="gas_station",
        source_text="АЗС на карте, адрес и маршрут.",
    )

    assert metrics["total"] == 1
    assert metrics["needs_review"] == 1
    assert metrics["factual_risk"] == 1
    assert metrics["industry_drift"] == 1


def test_pattern_impact_metrics_flags_review_reply_without_detail() -> None:
    metrics = build_pattern_impact_metrics(
        {"reply": "Спасибо за отзыв, будем рады видеть вас снова."},
        "review_reply",
        industry_key="food",
        source_text="Очень понравился круассан и капучино утром.",
    )

    assert metrics["total"] == 1
    assert metrics["needs_review"] == 1
    assert metrics["no_review_detail"] == 1
    assert metrics["no_gratitude"] == 0


def test_monthly_impact_classifies_disable_and_stable_candidates() -> None:
    disable_item = {
        "total_items": 10,
        "needs_review": 6,
        "bad_rate": 0.6,
        "applied_count": 10,
        "industry_drift": 2,
    }
    stable_item = {
        "total_items": 8,
        "needs_review": 0,
        "bad_rate": 0,
        "applied_count": 8,
    }

    assert classify_industry_pattern_impact_item(disable_item) == "disable_candidate"
    assert classify_industry_pattern_impact_item(stable_item) == "stable"


def test_monthly_impact_report_text_is_hitl_and_actionable() -> None:
    text = format_monthly_industry_pattern_impact_report(
        {
            "period_days": 30,
            "totals": {
                "active_patterns": 2,
                "applied_count": 12,
                "result_count": 10,
                "total_items": 10,
                "good": 7,
                "needs_review": 3,
                "fallback": 1,
                "guardrail_failed": 0,
                "missing_keywords": 1,
                "industry_drift": 1,
                "factual_risk": 1,
                "too_long": 0,
                "no_review_detail": 1,
                "business_effect_score": 0.2,
                "seo_score_delta": 3,
                "keyword_found_delta": 2,
                "accepted": 4,
                "manual_edits": 1,
                "business_effect_positive": 3,
                "business_effect_neutral": 1,
                "business_effect_negative": 1,
            },
            "by_type": {
                "news": {"applied_count": 5, "good": 3, "needs_review": 2, "business_effect_score": 0.1},
                "review_reply": {"applied_count": 7, "good": 4, "needs_review": 1, "business_effect_score": 0.3},
            },
            "problematic": [
                {
                    "industry_key": "food",
                    "pattern_type": "news",
                    "recommendation": "revise_candidate",
                    "bad_rate": 0.4,
                    "needs_review": 2,
                    "business_effect_score": -0.2,
                    "business_effect_status": "negative",
                    "pattern_text": "Писать о продукте дня только при наличии факта.",
                }
            ],
            "effective": [
                {
                    "industry_key": "beauty",
                    "pattern_type": "service",
                    "business_effect_score": 0.8,
                    "accepted": 4,
                    "applied_count": 5,
                    "pattern_text": "Сохранять препарат и объем.",
                }
            ],
            "questionable": [
                {
                    "industry_key": "food",
                    "pattern_type": "news",
                    "business_effect_score": -0.2,
                    "business_effect_status": "negative",
                    "pattern_text": "Писать об акции без факта.",
                }
            ],
            "stable": [],
        }
    )

    assert "Monthly impact report" in text
    assert "needs_review: 3" in text
    assert "Business effect" in text
    assert "keyword delta 2" in text
    assert "Эффективные по business effect" in text
    assert "Сомнительные по business effect" in text
    assert "Топ кандидатов" in text
    assert "Ничего не применяется автоматически" in text


def test_rollback_text_compare_shows_added_and_removed_terms() -> None:
    diff = compare_industry_pattern_version_texts(
        "Для beauty услуг сохранять препарат, объем и зону.",
        "Для beauty услуг сохранять препарат, возраст и число сеансов.",
    )

    assert diff["same_text"] is False
    assert "возраст" in diff["added_terms"]
    assert "зону" in diff["removed_terms"]
    assert diff["similarity"] < 1


def test_rollback_preview_contains_confirmation_token(monkeypatch) -> None:
    def fake_detail(_conn, *, version_id: str, days: int, event_limit: int) -> dict:
        status = "active" if version_id == "current" else "disabled"
        disabled_at = "" if version_id == "current" else "2026-05-01"
        return {
            "version": {
                "version_id": version_id,
                "industry_key": "beauty",
                "pattern_type": "service",
                "pattern_text": f"Паттерн {version_id}",
                "status": status,
                "disabled_at": disabled_at,
            },
            "health": {"version_id": version_id, "applied_count": 1, "good": 1, "needs_review": 0},
        }

    monkeypatch.setattr(recalibration, "get_industry_pattern_detail_card", fake_detail)

    preview = recalibration.get_industry_pattern_rollback_preview(
        object(),
        current_version_id="current",
        target_version_id="target",
        days=30,
    )

    assert preview["confirmation_token"] == "rollback:current:target"
    assert preview["can_confirm"] is True
    assert preview["same_scope"] is True


def test_detail_event_summary_supports_disabled_rollback_candidates() -> None:
    summary = summarize_industry_pattern_detail_events(
        [
            {"event_type": "applied", "metrics": {}},
            {
                "event_type": "result",
                "metrics": {
                    "total": 3,
                    "good": 2,
                    "needs_review": 1,
                    "fallback": 1,
                    "guardrail_failed": 1,
                },
            },
        ]
    )

    assert summary["applied_count"] == 1
    assert summary["result_count"] == 1
    assert summary["total_items"] == 3
    assert summary["bad_rate"] == 0.333
    assert summary["fallback"] == 1
