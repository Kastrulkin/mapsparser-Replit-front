import json

from src.services.content_plan_service import (
    _annotate_story_facts_requirement,
    _build_content_brief_v1,
    _content_generation_v2_prompt,
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


def test_story_topic_requires_explicit_real_story_facts():
    brief = _build_content_brief_v1(
        {
            "theme": "История ученика: как проекты помогают стать самостоятельнее",
            "goal": "Показать результат через реальный процесс без гарантированных обещаний.",
            "content_type": "story",
            "source_kind": "seasonal",
            "source_ref": "",
            "metadata_json": {
                "brief_answers": {
                    "infopovod": "История ученика о проектной работе",
                    "confirmed_details": "Показать результат через реальный процесс",
                    "source": "Официальный сайт школы",
                }
            },
        },
        {"description": "Школа проектного обучения", "site_description": "", "services": ""},
    )

    assert brief["complete"] is False
    assert brief["requires_story_facts"] is True
    assert brief["missing_fields"][0] == "story_facts"
    assert "реальную историю" in brief["questions"][0].lower()


def test_story_facts_complete_story_brief():
    story_facts = (
        "Ученик сначала боялся презентовать макет, но после двух репетиций "
        "сам рассказал группе о своём решении."
    )
    brief = _build_content_brief_v1(
        {
            "theme": "История ученика",
            "goal": "Показать реальный процесс",
            "content_type": "story",
            "source_kind": "owner",
            "source_ref": "Комментарий педагога",
            "metadata_json": {
                "brief_answers": {
                    "infopovod": "История ученика о проектной работе",
                    "story_facts": story_facts,
                    "source": "Комментарий педагога",
                }
            },
        },
        {"description": "Школа проектного обучения", "site_description": "", "services": ""},
    )

    assert brief["complete"] is True
    assert "story_facts" in {source["id"] for source in brief["sources"]}
    assert story_facts in brief["confirmed_details"]


def test_plan_response_highlights_missing_story_facts_before_generation():
    metadata = _annotate_story_facts_requirement(
        {
            "content_type": "story",
            "theme": "История ученика",
            "goal": "Показать реальный процесс",
            "metadata_json": {},
        }
    )

    assert metadata["generation_source"] == "needs_context"
    assert metadata["content_brief_v1"]["missing_fields"][0] == "story_facts"
    assert metadata["content_brief_v1"]["complete"] is False


def test_story_variant_without_story_facts_cannot_invent_a_hero():
    prompt = _content_generation_v2_prompt(
        business_facts={"name": "Intellectum School", "description": "Школа"},
        brief={
            "event": "Научная лаборатория",
            "confirmed_details": ["Занятие для детей"],
            "sources": [{"id": "event", "label": "Тема", "fact": "Научная лаборатория"}],
        },
        voice={"preferences": {}, "examples": [], "forbidden_phrases": []},
        language="ru",
    )

    assert "не придумывай героя" in prompt
    assert "ситуационный вариант" in prompt


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


def test_long_candidate_requires_short_paragraphs():
    candidate = {
        "id": "variant-1",
        "angle": "Объяснение",
        "text": (
            "После прилёта проверьте подтверждённое место встречи и держите телефон включённым. "
            "Если багаж задержался, сообщите об этом до выхода из терминала. "
            "Так водитель получит обновление, а пассажиру не придётся искать машину в другой зоне аэропорта. "
            "Все детали поездки остаются в бронировании."
        ),
        "used_fact_ids": ["event"],
        "unsupported_facts": [],
    }

    scored = _score_content_candidate(
        candidate,
        {"sources": [{"id": "event"}], "confirmed_details": ["Место встречи подтверждено"]},
        {},
    )

    assert scored["quality_passed"] is False
    assert "Разделите длинный текст на короткие абзацы" in scored["issues"]


def test_candidate_blocks_internal_plan_language_and_slop_cliches():
    candidate = {
        "id": "variant-1",
        "angle": "Анонс",
        "text": "Цель публикации — показать уникальную возможность и вывести бизнес на новый уровень.",
        "used_fact_ids": ["event"],
        "unsupported_facts": [],
    }

    scored = _score_content_candidate(
        candidate,
        {"sources": [{"id": "event"}], "confirmed_details": ["Новый формат"]},
        {},
    )

    assert scored["quality_passed"] is False
    assert any("внутренняя формулировка" in issue for issue in scored["issues"])
    assert any("Рекламное клише" in issue for issue in scored["issues"])


def test_dry_katok_bulletin_does_not_pass_live_voice_gate():
    candidate = {
        "id": "variant-1",
        "angle": "Анонс",
        "text": (
            "В афише «Катка» опубликованы три события на 22, 23 и 28 августа. "
            "22 августа в 19:00 — «Тиндер Чайковского»; 23 августа в 19:00 — «Локсток»; "
            "28 августа в 19:00 — «Черный ящик». Все события проходят в «Катке» в Краснодаре.\n\n"
            "Подробности — на официальной странице «Катка»."
        ),
        "used_fact_ids": ["event", "owner_detail", "owner_source"],
        "unsupported_facts": [],
    }
    brief = {
        "sources": [
            {"id": "event"},
            {"id": "owner_detail"},
            {"id": "owner_source"},
        ],
        "confirmed_details": ["Три события опубликованы в официальной афише"],
    }
    voice = {
        "summary": (
            "Разговорно, интеллектуально и с лёгкой дерзостью. Начинать с интриги "
            "или необычной механики события, затем давать точные дату, время и формат."
        ),
        "forbidden_phrases": [],
    }

    scored = _score_content_candidate(candidate, brief, voice)

    assert scored["quality_passed"] is False
    assert scored["factual_gate_passed"] is True
    assert scored["neuroslop_passed"] is True
    assert scored["editorial_quality_passed"] is False
    assert scored["voice_adherence_passed"] is False
    assert any("Сухое начало" in issue for issue in scored["issues"])


def test_compressed_katok_metaphors_do_not_pass_clarity_and_story_gates():
    candidate = {
        "id": "variant-1",
        "angle": "Механики событий",
        "text": (
            "В конце августа в «Катке» музыку будут свайпать, на числовые ответы — ставить, "
            "а Вивальди превратят в подсказку к чёрному ящику.\n\n"
            "22 августа — «Тиндер Чайковского», 23-го — «Локсток», 28-го — «Черный ящик». "
            "Все три вечера начинаются в 19:00. Выбирайте механику в афише «Катка»."
        ),
        "used_fact_ids": ["event", "owner_detail", "owner_source"],
        "unsupported_facts": [],
    }
    brief = {
        "sources": [
            {"id": "event"},
            {"id": "owner_detail"},
            {"id": "owner_source"},
        ],
        "confirmed_details": ["Три события опубликованы в официальной афише"],
    }
    voice = {
        "summary": (
            "Разговорно, интеллектуально и с лёгкой дерзостью. Начинать с интриги "
            "или необычной механики события, затем давать точные дату, время и формат."
        ),
        "forbidden_phrases": [],
    }

    scored = _score_content_candidate(candidate, brief, voice)

    assert scored["quality_passed"] is False
    assert scored["clarity_passed"] is False
    assert scored["story_passed"] is False


def test_short_individual_katok_story_passes_all_quality_gates():
    candidate = {
        "id": "variant-1",
        "angle": "Три разных вечера",
        "text": (
            "В конце августа в «Катке» можно прожить три совершенно разных вечера.\n\n"
            "22 августа классическая музыка станет поводом познакомиться: на «Тиндере Чайковского» "
            "гости будут слушать произведения, узнавать любовные истории композиторов и искать совпавшую пару.\n\n"
            "Уже на следующий день настроение изменится. В «Локстоке» понадобятся чувство числа, "
            "немного смелости и умение вовремя сказать «пас».\n\n"
            "А 28 августа зал будет слушать Вивальди особенно внимательно — музыка подскажет, "
            "что спрятано в «Чёрном ящике».\n\n"
            "Все три события начинаются в 19:00. Осталось выбрать, какой вечер хочется прожить первым."
        ),
        "used_fact_ids": ["event", "owner_detail", "owner_source"],
        "unsupported_facts": [],
    }
    brief = {
        "sources": [
            {"id": "event"},
            {"id": "owner_detail"},
            {"id": "owner_source"},
        ],
        "confirmed_details": ["Три события опубликованы в официальной афише"],
    }
    voice = {
        "summary": (
            "Разговорно, интеллектуально и с лёгкой дерзостью. Начинать с интриги "
            "или необычной механики события, затем давать точные дату, время и формат."
        ),
        "forbidden_phrases": [],
    }

    scored = _score_content_candidate(candidate, brief, voice)

    assert scored["quality_passed"] is True
    assert scored["factual_gate_passed"] is True
    assert scored["neuroslop_passed"] is True
    assert scored["editorial_quality_passed"] is True
    assert scored["voice_adherence_passed"] is True
    assert scored["clarity_passed"] is True
    assert scored["story_passed"] is True


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


def test_generation_prompt_uses_confirmed_business_and_audience_descriptions():
    prompt = _content_generation_v2_prompt(
        business_facts={"name": "Каток", "services": []},
        brief={
            "event": "Лекция 7 августа",
            "confirmed_details": ["Начало в 19:00"],
            "sources": [{"id": "event", "label": "Афиша", "fact": "Лекция 7 августа"}],
        },
        voice={
            "summary": "Спокойно и конкретно",
            "preferences": {
                "business_description": "Культурный центр для жителей района",
                "audience_description": "Жители, которые ищут события рядом с домом",
            },
            "examples": [],
        },
        language="ru",
    )

    assert "Культурный центр для жителей района" in prompt
    assert "Жители, которые ищут события рядом с домом" in prompt
    assert "коротких абзацев" in prompt
    assert "не копируй источник дословно" in prompt
    assert "свяжи их в короткий рассказ" in prompt
    assert "не выдавай перечень дат и названий" in prompt
    assert "без знания маркетингового жаргона" in prompt


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
