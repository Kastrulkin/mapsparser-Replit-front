from src.core.public_audit_editor import (
    ACTION_PLAN_BLOCK_KEY,
    STRONG_DEMAND_BLOCK_KEY,
    SUMMARY_BLOCK_KEY,
    TOP_ISSUES_BLOCK_KEY,
    WEAK_DEMAND_BLOCK_KEY,
    WHY_BLOCK_KEY,
    apply_editor_blocks_to_page_json,
    build_generated_editor_blocks,
    classify_edit_kind,
    compute_editor_diff,
    normalize_editor_blocks,
)


def _sample_page_json() -> dict:
    return {
        "name": "Dom Capri",
        "category": "Салон красоты",
        "city": "Кудрово",
        "audit": {
            "summary_text": "Карточка уже даёт спрос по отдельным услугам, но теряет общий выбор салона.",
            "search_intents_to_target": ["педикюр", "косметология"],
            "weak_fit_guest_profile": ["салон красоты рядом"],
            "issue_blocks": [
                {
                    "section": "positioning",
                    "problem": "Не объяснено, какие направления ключевые.",
                    "evidence": "Часть услуг выглядит как общий список.",
                }
            ],
            "top_3_issues": [
                {
                    "title": "Слабая упаковка услуг",
                    "problem": "Нет ясного разделения направлений.",
                    "priority": "high",
                }
            ],
            "action_plan": {
                "next_24h": ["Переписать блок услуг"],
                "next_7d": ["Добавить цены"],
                "ongoing": ["Публиковать работы"],
            },
            "audit_profile": "beauty",
            "current_state": {
                "services_count": 20,
                "services_with_price_count": 8,
                "reviews_count": 44,
            },
            "services_preview": [
                {"current_name": "Педикюр"},
                {"current_name": "Косметология"},
            ],
            "reviews_preview": [
                {"review": "Нравится аккуратная работа"},
            ],
        },
    }


def test_build_generated_editor_blocks_extracts_six_core_blocks() -> None:
    blocks = build_generated_editor_blocks(_sample_page_json())

    assert blocks[SUMMARY_BLOCK_KEY]["body"].startswith("Карточка уже даёт спрос")
    assert blocks[STRONG_DEMAND_BLOCK_KEY]["items"] == ["педикюр", "косметология"]
    assert blocks[WEAK_DEMAND_BLOCK_KEY]["items"] == ["салон красоты рядом"]
    assert blocks[WHY_BLOCK_KEY]["items"] == [
        "Не объяснено, какие направления ключевые.",
        "Часть услуг выглядит как общий список.",
    ]
    assert blocks[TOP_ISSUES_BLOCK_KEY]["items"][0]["title"] == "Слабая упаковка услуг"
    assert blocks[ACTION_PLAN_BLOCK_KEY]["sections"][0]["items"] == ["Переписать блок услуг"]


def test_apply_editor_blocks_to_page_json_updates_published_payload_fields() -> None:
    page_json = _sample_page_json()
    edited_blocks = normalize_editor_blocks(
        {
            "summary": {"title": "Итог", "body": "Новый summary"},
            "strong_demand": {"title": "Сильный спрос", "items": ["маникюр", "педикюр"]},
            "weak_demand": {"title": "Слабый спрос", "items": ["салон красоты рядом", "поиск услуги по цене"]},
            "why": {"title": "Почему", "items": ["Карточка не объясняет, что главное."]},
            "top_issues": {
                "title": "Что исправить",
                "items": [{"title": "Добавить цены", "body": "Без цен сложнее сравнивать", "priority": "high"}],
            },
            "action_plan": {
                "title": "План",
                "sections": [
                    {"key": "next_24h", "title": "Следующие 24 часа", "items": ["Добавить цены"]},
                    {"key": "next_7d", "title": "Следующие 7 дней", "items": ["Обновить описание"]},
                    {"key": "ongoing", "title": "На постоянной основе", "items": ["Публиковать фото"]},
                ],
            },
        }
    )

    published = apply_editor_blocks_to_page_json(page_json, edited_blocks)
    audit = published["audit"]

    assert audit["summary_text"] == "Новый summary"
    assert audit["search_intents_to_target"] == ["маникюр", "педикюр"]
    assert audit["weak_fit_guest_profile"] == ["салон красоты рядом", "поиск услуги по цене"]
    assert audit["top_3_issues"][0]["title"] == "Добавить цены"
    assert audit["action_plan"]["next_7d"] == ["Обновить описание"]
    assert audit["editor_blocks"]["why"]["items"] == ["Карточка не объясняет, что главное."]


def test_compute_editor_diff_marks_semantic_and_structure_changes() -> None:
    generated = build_generated_editor_blocks(_sample_page_json())
    edited = normalize_editor_blocks(generated)
    edited["summary"]["body"] = "Полностью переписанный вывод для карточки."
    edited["strong_demand"]["items"] = ["маникюр", "педикюр", "косметология"]

    diff = compute_editor_diff(generated, edited, generated)

    assert diff["summary"]["changed_in_draft"] is True
    assert diff["summary"]["edit_kind"] == "semantic_rewrite"
    assert diff["strong_demand"]["edit_kind"] == "structure_edit"


def test_classify_edit_kind_detects_minor_copy_edit() -> None:
    kind = classify_edit_kind(
        "Карточка отвечает на точечный спрос по услугам.",
        "Карточка хорошо отвечает на точечный спрос по услугам.",
    )

    assert kind == "minor_copy_edit"
