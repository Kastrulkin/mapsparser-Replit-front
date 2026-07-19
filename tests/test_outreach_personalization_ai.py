import json

from services.outreach_personalization_ai import (
    PROMPT_VERSION,
    QUALITY_CRITERIA,
    REVIEW_PROMPT_VERSION,
    generation_contract_current,
    generate_personalized_sequence,
)


OBSERVATION = "Рейтинг - 4,1; публичных отзывов - 27."


def test_saved_generation_contract_blocks_old_drafts_when_ai_is_required():
    current_brief = {
        "generation_source": "gigachat",
        "generation_prompt_version": PROMPT_VERSION,
        "semantic_review_prompt_version": REVIEW_PROMPT_VERSION,
    }
    current_gate = {
        "passed": True,
        "semantic_review": {"passed": True},
    }

    assert generation_contract_current(current_brief, current_gate, require_ai=True) is True
    assert generation_contract_current({}, {"passed": True}, require_ai=True) is False
    assert generation_contract_current({}, {"passed": True}, require_ai=False) is True
    assert generation_contract_current(
        {**current_brief, "generation_prompt_version": "outdated"},
        current_gate,
        require_ai=True,
    ) is False


def _candidate():
    return {
        "evidence_id": "map-rating",
        "evidence_ids": ["map-rating"],
        "evidence_kind": "map_issue",
        "observed_fact": OBSERVATION,
        "problem_hypothesis": "Карточка может формировать меньше доверия, чем могла бы.",
        "relevance_to_offer": "Можно проверить, как карточка формирует доверие",
        "source_url": "https://maps.example/clinic",
        "source_type": "public_map",
        "observed_at": "2026-07-18T00:00:00Z",
        "freshness": "fresh",
        "confidence": 0.95,
        "sender": "Александр",
        "sender_role": "руководитель",
        "sender_company": "LocalOS",
        "next_step": "Короткий разбор карточки",
    }


def _story():
    return {
        "story": "Я сам разбираю публичные данные локальных компаний.",
        "proof": "LocalOS собирает факты карточки в проверяемый аудит.",
        "offer": "Короткий разбор карточки",
        "forbidden_claims": ["гарантированный рост"],
    }


def _sequence():
    return [
        {
            "sequence_index": 0,
            "channel": "telegram",
            "angle": "signal",
            "day_offset": 0,
            "text": "deterministic one",
            "subject": None,
        },
        {
            "sequence_index": 1,
            "channel": "email",
            "angle": "founder_story",
            "day_offset": 3,
            "text": "deterministic two",
            "subject": "Короткий вопрос",
        },
    ]


def _generation_response():
    return {
        "schema_version": "1.0",
        "touches": [
            {
                "sequence_index": 0,
                "channel": "telegram",
                "angle": "signal",
                "subject": None,
                "text_template": (
                    "{{RECIPIENT}}, здравствуйте! Я {{SENDER_NAME}} из {{SENDER_BUSINESS}}. "
                    "{{OBSERVATION}} {{BRIDGE}}. Прислать короткий разбор?"
                ),
                "evidence_ids": ["map-rating"],
                "observation": OBSERVATION,
                "problem_hypothesis": None,
                "relevance_bridge": "Можно проверить, как карточка формирует доверие",
            },
            {
                "sequence_index": 1,
                "channel": "email",
                "angle": "founder_story",
                "subject": "Короткий вопрос по карточке",
                "text_template": (
                    "{{RECIPIENT}}, здравствуйте! {{FOUNDER_STORY}} "
                    "{{OBSERVATION}} {{BRIDGE}}. Отправить один проверяемый разбор?"
                ),
                "evidence_ids": ["map-rating"],
                "observation": OBSERVATION,
                "problem_hypothesis": None,
                "relevance_bridge": "Опыт отправителя помогает проверить публичный сигнал",
            },
        ],
    }


def _review_response(score=2, reason_codes=None):
    return {
        "schema_version": "1.0",
        "reviews": [
            {
                "sequence_index": index,
                "scores": {criterion: score for criterion in QUALITY_CRITERIA},
                "total_score": score * len(QUALITY_CRITERIA),
                "verdict": "approve" if score == 2 and not reason_codes else "revise",
                "reason_codes": reason_codes or [],
                "notes": [],
            }
            for index in range(2)
        ],
    }


def _fragment_generation_response():
    return {
        "schema_version": "1.0",
        "touches": [
            {
                "sequence_index": 0,
                "channel": "telegram",
                "angle": "signal",
                "subject": None,
                "opening_template": "{{RECIPIENT}}, здравствуйте! Я {{SENDER_NAME}} из {{SENDER_BUSINESS}}",
                "cta_question": "Прислать короткий разбор?",
                "evidence_ids": ["map-rating"],
                "observation": OBSERVATION,
                "problem_hypothesis": None,
                "relevance_bridge": "Можно проверить, как карточка формирует доверие",
            },
            {
                "sequence_index": 1,
                "channel": "email",
                "angle": "founder_story",
                "subject": "Короткий вопрос по карточке",
                "opening_template": "{{RECIPIENT}}, здравствуйте!",
                "cta_question": "Отправить один проверяемый разбор?",
                "evidence_ids": ["map-rating"],
                "observation": OBSERVATION,
                "problem_hypothesis": None,
                "relevance_bridge": "Можно проверить, как карточка формирует доверие",
            },
        ],
    }


def _policy_bound_generation_response():
    generated = _fragment_generation_response()
    for touch in generated["touches"]:
        touch.pop("opening_template")
        touch.pop("cta_question")
        touch["opening_style"] = "direct"
        touch["cta_intent"] = "send_short_review"
    return generated


def test_native_ai_sequence_preserves_evidence_and_gets_independent_reviews():
    responses = iter([
        json.dumps(_generation_response(), ensure_ascii=False),
        json.dumps(_review_response(), ensure_ascii=False),
    ])

    def generate(_prompt, **_kwargs):
        return next(responses)

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника", "contact_name": "", "contact_role": "владелец"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=generate,
    )

    assert result["status"] == "ready"
    assert result["schema_version"] == "1.0"
    assert len(result["touches"]) == 2
    assert all(item["evidence_ids"] == ["map-rating"] for item in result["touches"])
    assert all(item["passed"] is True for item in result["semantic_reviews"])


def test_native_ai_sequence_fails_closed_when_observation_is_rewritten():
    generated = _generation_response()
    generated["touches"][0]["text_template"] = "{{RECIPIENT}}, здравствуйте! Обсудим?"

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: json.dumps(generated, ensure_ascii=False),
    )

    assert result["status"] == "failed"
    assert result["error_code"] == "ai_generation_invalid"
    assert "misses required evidence placeholders" in result["error"]


def test_semantic_review_can_only_downgrade_generated_copy():
    responses = iter([
        json.dumps(_generation_response(), ensure_ascii=False),
        json.dumps(_review_response(score=1, reason_codes=["WEAK_OFFER_BRIDGE"]), ensure_ascii=False),
    ])

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: next(responses),
    )

    assert result["status"] == "ready"
    assert all(item["passed"] is False for item in result["semantic_reviews"])
    assert all(item["verdict"] == "revise" for item in result["semantic_reviews"])
    assert all(item["reason_codes"] == ["WEAK_OFFER_BRIDGE"] for item in result["semantic_reviews"])


def test_constrained_fragments_keep_ai_voice_but_localos_inserts_all_facts():
    responses = iter([
        json.dumps(_fragment_generation_response(), ensure_ascii=False),
        json.dumps(_review_response(), ensure_ascii=False),
    ])

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: next(responses),
    )

    assert result["status"] == "ready"
    assert all(OBSERVATION in item["text"] for item in result["touches"])
    assert all("Можно проверить, как карточка формирует доверие" in item["text"] for item in result["touches"])
    assert _story()["story"] in result["touches"][1]["text"]


def test_policy_bound_choices_produce_clean_founder_led_copy():
    responses = iter([
        json.dumps(_policy_bound_generation_response(), ensure_ascii=False),
        json.dumps(_review_response(), ensure_ascii=False),
    ])

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: next(responses),
    )

    assert result["status"] == "ready"
    assert result["touches"][0]["text"].startswith(
        "Здравствуйте! Я Александр, руководитель LocalOS."
    )
    assert result["touches"][0]["text"].count("?") == 1
    assert result["touches"][1]["subject"] == "Короткий вопрос по карточке Клиника"
    assert "Гипотеза для проверки:" in result["touches"][0]["text"]


def test_constrained_fragments_allow_neutral_recipient_vocabulary():
    generated = _fragment_generation_response()
    generated["touches"][0]["opening_template"] = (
        "{{RECIPIENT}}, здравствуйте! Пишу как клиенту локального бизнеса"
    )
    generated["touches"][0]["cta_question"] = "Прислать короткий разбор — интересно?"
    responses = iter([
        json.dumps(generated, ensure_ascii=False),
        json.dumps(_review_response(), ensure_ascii=False),
    ])

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: next(responses),
    )

    assert result["status"] == "ready"
    assert "—" not in result["touches"][0]["text"]


def test_constrained_fragments_reject_claims_in_ai_written_opening():
    generated = _fragment_generation_response()
    generated["touches"][0]["opening_template"] = "{{RECIPIENT}}, здравствуйте! Гарантируем рост"

    result = generate_personalized_sequence(
        motion="localos_sales",
        identity={"company_name": "Клиника"},
        candidate=_candidate(),
        founder_story=_story(),
        sequence=_sequence(),
        generator=lambda _prompt, **_kwargs: json.dumps(generated, ensure_ascii=False),
    )

    assert result["status"] == "failed"
    assert "opening contains an unsupported claim" in result["error"]
