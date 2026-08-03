import json

from src.services.content_plan_service import (
    _build_content_brief_v1,
    _load_publication_matrix_override,
    _parse_content_candidates,
    _score_content_candidate,
)
from src.services.content_voice_service import _derive_profile


def test_seo_only_topic_requires_real_context():
    brief = _build_content_brief_v1(
        {
            "theme": "Почему выбрать вас по запросу «культурный центр рядом»",
            "goal": "Привести человека в карточку",
            "content_type": "seo",
            "source_kind": "seo_keyword",
            "source_ref": "культурный центр рядом",
            "seo_keyword": "культурный центр рядом",
            "metadata_json": {},
        },
        {
            "description": "Культурный центр Каток",
            "site_description": "Лекции, концерты и встречи",
            "services": "",
        },
    )

    assert brief["complete"] is False
    assert "infopovod" in brief["missing_fields"]
    assert len(brief["questions"]) <= 3


def test_owner_event_details_complete_katok_brief():
    brief = _build_content_brief_v1(
        {
            "theme": "Лекция о современном искусстве",
            "goal": "Проверить афишу",
            "content_type": "event",
            "source_kind": "seo_keyword",
            "source_ref": "",
            "metadata_json": {
                "brief_answers": {
                    "infopovod": "7 августа в Катке пройдёт лекция о современном искусстве",
                    "confirmed_details": "Начало в 19:00, спикер — автор курса из афиши",
                    "source": "Официальная афиша Катка",
                }
            },
        },
        {"description": "Культурный центр", "site_description": "", "services": ""},
    )

    assert brief["complete"] is True
    assert brief["missing_fields"] == []
    assert {source["id"] for source in brief["sources"]} >= {"event", "owner_detail", "owner_source"}


def test_candidates_require_known_fact_ids_and_quality_threshold():
    raw = json.dumps(
        {
            "candidates": [
                {
                    "id": f"variant-{index}",
                    "angle": "Анонс",
                    "text": "7 августа в Катке пройдёт лекция о современном искусстве. Начало в 19:00. Подробности смотрите в афише.",
                    "used_fact_ids": ["event", "owner_detail"],
                    "unsupported_facts": [],
                }
                for index in range(1, 4)
            ]
        },
        ensure_ascii=False,
    )
    candidates = _parse_content_candidates(raw)
    brief = {
        "sources": [{"id": "event"}, {"id": "owner_detail"}],
        "confirmed_details": ["Начало в 19:00"],
    }
    scored = [_score_content_candidate(candidate, brief, {"summary": "Спокойный стиль", "forbidden_phrases": []}) for candidate in candidates]

    assert len(scored) == 3
    assert all(candidate["grounded"] for candidate in scored)
    assert all(candidate["quality_passed"] for candidate in scored)


def test_candidate_with_unknown_fact_is_disqualified():
    candidate = {
        "id": "variant-1",
        "angle": "Анонс",
        "text": "7 августа состоится лекция. Подробности смотрите в афише.",
        "used_fact_ids": ["unknown-source"],
        "unsupported_facts": [],
    }
    scored = _score_content_candidate(candidate, {"sources": [{"id": "event"}], "confirmed_details": ["Лекция"]}, {})

    assert scored["grounded"] is False
    assert scored["quality_passed"] is False


def test_voice_profile_is_derived_without_applying_hidden_rules():
    profile = _derive_profile(
        [
            {"text": "7 августа встречаемся в Катке. Начало в 19:00.\n\nПодробности — в афише."},
            {"text": "Новый вечер музыки уже в пятницу.\n\nСмотрите программу в афише."},
            {"text": "Один зал, один разговор и много вопросов. Ближайшие даты — на сайте."},
        ]
    )

    assert profile["summary"]
    assert profile["preferences"]["average_length"] > 0
    assert isinstance(profile["typical_ctas"], list)


def test_missing_optional_prompt_does_not_abort_generation_transaction():
    class Cursor:
        def __init__(self):
            self.commands = []

        def execute(self, statement, params=None):
            self.commands.append(statement)
            if statement.startswith("SELECT prompt_text"):
                raise RuntimeError("optional table is unavailable")

        def fetchone(self):
            return None

    cursor = Cursor()

    assert _load_publication_matrix_override(cursor, "culture", "announcement") == ""
    assert "ROLLBACK TO SAVEPOINT content_matrix_override" in cursor.commands
    assert cursor.commands[-1] == "RELEASE SAVEPOINT content_matrix_override"
