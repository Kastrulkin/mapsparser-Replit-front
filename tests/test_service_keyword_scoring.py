from core.service_keyword_scoring import (
    build_services_quality_audit,
    evaluate_service_keyword_score,
    evaluate_service_quality,
    match_keyword_level,
)


def test_keyword_level_exact_normalized_close_and_missing() -> None:
    assert match_keyword_level("Биозавивка афрокудри", "афро") == "exact"
    assert match_keyword_level("Коррекция бровей мужская", "брови") == "normalized"
    assert match_keyword_level("Ваксинг одной зоны", "восковая депиляция") == "close"
    assert match_keyword_level("Кофе с собой", "восковая депиляция") is None


def test_keyword_score_counts_missing_added_and_weak_matches() -> None:
    score = evaluate_service_keyword_score(
        "Пудровое напыление бровей",
        ["перманентный макияж", "брови", "ресницы"],
        "Макияж бровей",
    )

    assert score["found"] == 2
    assert score["missing"] == ["ресницы"]
    assert score["weak"] == ["перманентный макияж"]
    assert score["added"] == ["перманентный макияж"]
    assert score["close_count"] == 1
    assert score["normalized_count"] == 1


def test_organika_regression_keyword_cases() -> None:
    cases = [
        {
            "draft": "Коррекция бровей мужская",
            "keywords": ["брови"],
            "expected_keyword": "брови",
            "level": "normalized",
        },
        {
            "draft": "Пудровое напыление бровей",
            "keywords": ["перманентный макияж"],
            "expected_keyword": "перманентный макияж",
            "level": "close",
        },
        {
            "draft": "Татуаж губ",
            "keywords": ["перманент"],
            "expected_keyword": "перманент",
            "level": "close",
        },
        {
            "draft": "Ламинирование ресниц",
            "keywords": ["ресницы"],
            "expected_keyword": "ресницы",
            "level": "normalized",
        },
        {
            "draft": "Долговременная укладка бровей",
            "keywords": ["ламинирование"],
            "expected_keyword": "ламинирование",
            "level": "close",
        },
        {
            "draft": "Наращивание ресниц 1D классика",
            "keywords": ["ресницы"],
            "expected_keyword": "ресницы",
            "level": "normalized",
        },
        {
            "draft": "Ваксинг одной зоны",
            "keywords": ["восковая депиляция"],
            "expected_keyword": "восковая депиляция",
            "level": "close",
        },
        {
            "draft": "Лазерная эпиляция ног",
            "keywords": ["эпиляция"],
            "expected_keyword": "эпиляция",
            "level": "exact",
        },
        {
            "draft": "Биозавивка афрокудри на длинные волосы",
            "keywords": ["афро"],
            "expected_keyword": "афро",
            "level": "exact",
        },
        {
            "draft": "Биозавивка на экстра длинные волосы",
            "keywords": ["биозавивка"],
            "expected_keyword": "биозавивка",
            "level": "exact",
        },
        {
            "draft": "Детская стрижка 12-15 лет",
            "keywords": ["для детей"],
            "expected_keyword": "для детей",
            "level": "close",
        },
        {
            "draft": "Макияж вечерний",
            "keywords": ["визаж"],
            "expected_keyword": "визаж",
            "level": "close",
        },
        {
            "draft": "Ботулинотерапия лица",
            "keywords": ["ботокс"],
            "expected_keyword": "ботокс",
            "level": "close",
        },
        {
            "draft": "Инъекционная косметология препаратом Belarti lift 1 ml",
            "keywords": ["инъекции"],
            "expected_keyword": "инъекции",
            "level": "close",
        },
        {
            "draft": "Чистка лица комбинированная",
            "keywords": ["уход за лицом"],
            "expected_keyword": "уход за лицом",
            "level": "close",
        },
        {
            "draft": "Пилинг лица",
            "keywords": ["чистка лица"],
            "expected_keyword": "чистка лица",
            "level": "close",
        },
        {
            "draft": "Маникюр с покрытием ногтей",
            "keywords": ["ногти"],
            "expected_keyword": "ногти",
            "level": "normalized",
        },
        {
            "draft": "Покрытие ногтей гель-лаком",
            "keywords": ["маникюр"],
            "expected_keyword": "маникюр",
            "level": "close",
        },
        {
            "draft": "Гигиенический педикюр",
            "keywords": ["стопы"],
            "expected_keyword": "стопы",
            "level": "close",
        },
        {
            "draft": "Педикюр и обработка стоп",
            "keywords": ["ногти на ногах"],
            "expected_keyword": "ногти на ногах",
            "level": "close",
        },
    ]

    assert len(cases) >= 20

    for case in cases:
        score = evaluate_service_keyword_score(case["draft"], case["keywords"])
        assert score["found"] == 1
        assert score["matches"] == [
            {"keyword": case["expected_keyword"], "level": case["level"]}
        ]


def test_service_quality_explains_review_reasons() -> None:
    quality = evaluate_service_quality({
        "id": "svc-1",
        "name": "Ботулинотерапия лица",
        "description": "",
        "optimized_name": "Ботулинотерапия лица",
        "optimized_description": "Ботулинотерапия лица: услуга по исходному формату записи.",
        "keywords": ["ботокс", "морщины"],
        "fallback_used": True,
        "guardrail_reasons": ["added_unconfirmed_medical_claim_name"],
    })

    assert quality["needs_review"] is True
    assert "missing_keywords" in quality["issue_codes"]
    assert "fallback_used" in quality["issue_codes"]
    assert "guardrail_reasons" in quality["issue_codes"]
    assert any("не хватает запроса" in label for label in quality["issue_labels"])


def test_unchanged_service_name_is_ok_when_description_and_keywords_are_good() -> None:
    quality = evaluate_service_quality({
        "id": "svc-ready",
        "name": "Лазерная эпиляция - Все тело",
        "description": "",
        "optimized_name": "Лазерная эпиляция - Все тело",
        "optimized_description": "Лазерная эпиляция всего тела.",
        "keywords": ["лазерная эпиляция"],
    })

    assert quality["status"] == "good"
    assert "name_unchanged" not in quality["issue_codes"]


def test_services_quality_audit_summary_counts() -> None:
    audit = build_services_quality_audit([
        {
            "id": "good",
            "name": "Коррекция бровей",
            "optimized_name": "Коррекция бровей мужская",
            "optimized_description": "Коррекция бровей мужская: короткое описание.",
            "keywords": ["брови"],
        },
        {
            "id": "bad",
            "name": "Пудровое напыление бровей",
            "optimized_name": "Пудровое напыление бровей",
            "optimized_description": "Пудровое напыление бровей: услуга по исходному формату записи.",
            "keywords": ["перманентный макияж", "ресницы"],
        },
    ])

    assert audit["summary"]["total"] == 2
    assert audit["summary"]["good"] == 1
    assert audit["summary"]["needs_review"] == 1
    assert audit["summary"]["missing_keywords"] == 1
    assert audit["summary"]["fallback"] == 1
    assert "Проверено 2 услуг" in audit["telegram_summary"]


def test_manual_review_status_is_separate_from_needs_review() -> None:
    quality = evaluate_service_quality({
        "id": "manual",
        "name": "Ботулинотерапия лица",
        "optimized_name": "Ботулинотерапия лица",
        "optimized_description": "Ботулинотерапия лица: услуга по исходному формату записи.",
        "keywords": ["ботокс"],
        "regeneration_status": "manual_review",
    })

    assert quality["status"] == "manual_review"
    assert quality["manual_review"] is True
    assert quality["needs_review"] is False
    assert "manual_review" in quality["issue_codes"]


def test_accepted_manual_service_text_is_scored_without_pending_draft() -> None:
    quality = evaluate_service_quality({
        "id": "accepted",
        "name": "Биозавивка длинные волосы",
        "description": "Биозавивка длинные волосы.",
        "optimized_name": "",
        "optimized_description": "",
        "keywords": ["биозавивка"],
        "fallback_used": False,
        "guardrail_reasons": [],
    })

    assert quality["status"] == "good"
    assert "no_suggestion" not in quality["issue_codes"]
    assert quality["keyword_score"]["found"] == 1
