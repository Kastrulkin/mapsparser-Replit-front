from core.service_problem_regeneration import (
    build_problem_regeneration_instructions,
    select_problem_services_for_regeneration,
)


def test_problem_regeneration_instructions_include_quality_reasons() -> None:
    instructions = build_problem_regeneration_instructions({
        "issue_codes": ["missing_keywords", "weak_matches_only", "fallback_description", "guardrail_reasons"],
        "keyword_score": {"missing": ["ботокс", "1 ml"]},
    })

    assert "Сохрани SEO-ключи: ботокс, 1 ml." in instructions
    assert "близкое совпадение" in instructions
    assert "шаблонное описание" in instructions
    assert "Не добавляй неподтвержденные" in instructions


def test_select_problem_services_limits_batch_and_marks_repeat_failures_manual() -> None:
    services = [
        {"id": "svc-1", "name": "Ботулинотерапия лица"},
        {"id": "svc-2", "name": "Афро на длинные волосы"},
        {"id": "svc-3", "name": "Коррекция бровей"},
    ]
    audit_items = [
        {"service_id": "svc-1", "needs_review": True, "issue_codes": ["missing_keywords"], "keyword_score": {"missing": ["ботокс"]}},
        {"service_id": "svc-2", "needs_review": True, "issue_codes": ["fallback_description"], "keyword_score": {"missing": []}},
        {"service_id": "svc-3", "needs_review": False, "issue_codes": [], "keyword_score": {"missing": []}},
    ]

    selected = select_problem_services_for_regeneration(
        services,
        audit_items,
        {"svc-1": 1},
        limit=10,
    )

    assert [item["service"]["id"] for item in selected["selected"]] == ["svc-2"]
    assert [item["service"]["id"] for item in selected["manual_review"]] == ["svc-1"]
    assert selected["remaining_after_batch"] == 0


def test_select_problem_services_respects_limit() -> None:
    services = [{"id": f"svc-{index}", "name": f"Услуга {index}"} for index in range(12)]
    audit_items = [
        {"service_id": f"svc-{index}", "needs_review": True, "issue_codes": ["missing_keywords"], "keyword_score": {"missing": ["ключ"]}}
        for index in range(12)
    ]

    selected = select_problem_services_for_regeneration(services, audit_items, {}, limit=10)

    assert len(selected["selected"]) == 10
    assert selected["remaining_after_batch"] == 2
