"""Native, evidence-bound AI personalization for supervised outreach previews."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

from services.gigachat_client import analyze_text_with_gigachat


SCHEMA_VERSION = "1.0"
PROMPT_VERSION = "outreach_personalization_v1"
REVIEW_PROMPT_VERSION = "outreach_semantic_review_v1"
QUALITY_CRITERIA = (
    "source_validity",
    "observation_accuracy",
    "freshness_and_why_now",
    "offer_bridge",
    "recipient_specificity",
    "proof_integrity",
    "channel_fit",
    "single_cta_and_length",
    "state_and_suppression_safety",
)
CANONICAL_REASON_CODES = {
    "SOURCE_MISSING",
    "SOURCE_MISMATCH",
    "STALE_AS_CURRENT",
    "INFERENCE_AS_FACT",
    "DECORATIVE_PERSONALIZATION",
    "WEAK_OFFER_BRIDGE",
    "UNSUPPORTED_PROOF",
    "MULTIPLE_CTA",
    "CHANNEL_LIMIT_EXCEEDED",
    "STYLE_VIOLATION",
    "TERMINAL_CONTACT_STATE",
    "SUPPRESSED_CONTACT",
    "APPROVAL_BYPASS",
    "SENSITIVE_TARGETING",
}
ALLOWED_TEMPLATE_FIELDS = {
    "RECIPIENT",
    "SENDER_NAME",
    "SENDER_ROLE",
    "SENDER_BUSINESS",
    "OBSERVATION",
    "BRIDGE",
    "FOUNDER_STORY",
    "FOUNDER_PROOF",
    "OFFER",
}


def ai_personalization_enabled() -> bool:
    return str(os.getenv("OUTREACH_AI_PERSONALIZATION_ENABLED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }


def generation_contract_current(
    message_brief: dict[str, Any] | None,
    quality_gate: dict[str, Any] | None,
    *,
    require_ai: bool | None = None,
) -> bool:
    """Return whether a saved draft is safe under the active generation contract."""

    brief = message_brief if isinstance(message_brief, dict) else {}
    gate = quality_gate if isinstance(quality_gate, dict) else {}
    if not bool(gate.get("passed")):
        return False
    ai_required = ai_personalization_enabled() if require_ai is None else bool(require_ai)
    if not ai_required:
        return True
    generation = gate.get("generation") if isinstance(gate.get("generation"), dict) else {}
    source = str(
        brief.get("generation_source") or generation.get("source") or ""
    ).strip().lower()
    prompt_version = str(
        brief.get("generation_prompt_version") or generation.get("prompt_version") or ""
    ).strip()
    review_prompt_version = str(
        brief.get("semantic_review_prompt_version")
        or generation.get("review_prompt_version")
        or ""
    ).strip()
    semantic_review = gate.get("semantic_review") if isinstance(gate.get("semantic_review"), dict) else {}
    return bool(
        source == "gigachat"
        and prompt_version == PROMPT_VERSION
        and review_prompt_version == REVIEW_PROMPT_VERSION
        and semantic_review.get("passed")
    )


def generate_personalized_sequence(
    *,
    motion: str,
    identity: dict[str, Any],
    candidate: dict[str, Any],
    founder_story: dict[str, Any],
    sequence: list[dict[str, Any]],
    voice_examples: list[Any] | None = None,
    business_id: str = "",
    user_id: str = "",
    generator: Callable[..., str] | None = None,
    reviewer: Callable[..., str] | None = None,
) -> dict[str, Any]:
    if not candidate.get("source_url") or not candidate.get("observed_fact"):
        return _failed("missing_evidence", "Evidence source and observation are required")
    if not founder_story.get("story"):
        return _failed("missing_founder_story", "Approved founder story is required")
    if not sequence:
        return _failed("empty_sequence", "At least one touch is required")

    request_record = _request_record(
        motion=motion,
        identity=identity,
        candidate=candidate,
        founder_story=founder_story,
        sequence=sequence,
        voice_examples=voice_examples or [],
    )
    generate = generator or _default_generator
    review = reviewer or generate
    try:
        generation_prompt = _generation_prompt(request_record)
        touches: list[dict[str, Any]] = []
        generation_error: Exception | None = None
        for attempt in range(2):
            retry_note = "" if attempt == 0 else (
                "\n\nПредыдущий ответ отклонён валидатором: "
                f"{generation_error}. Исправь только эту ошибку, не добавляй новые факты."
            )
            raw_generation = generate(
                generation_prompt + retry_note,
                business_id=business_id,
                user_id=user_id,
            )
            generated = _parse_json_object(raw_generation)
            try:
                touches = _normalize_touches(generated.get("touches"), request_record)
                generation_error = None
                break
            except ValueError as exc:
                generation_error = exc
        if generation_error is not None:
            raise generation_error
        review_record = {
            "schema_version": SCHEMA_VERSION,
            "request": request_record,
            "touches": touches,
        }
        raw_review = review(
            _review_prompt(review_record),
            business_id=business_id,
            user_id=user_id,
        )
        reviewed = _parse_json_object(raw_review)
        reviews = _normalize_reviews(reviewed.get("reviews"), touches)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "ready",
            "source": "gigachat",
            "prompt_version": PROMPT_VERSION,
            "review_prompt_version": REVIEW_PROMPT_VERSION,
            "touches": touches,
            "semantic_reviews": reviews,
            "error_code": None,
            "error": None,
        }
    except Exception as exc:
        return _failed("ai_generation_invalid", str(exc))


def _request_record(
    *,
    motion: str,
    identity: dict[str, Any],
    candidate: dict[str, Any],
    founder_story: dict[str, Any],
    sequence: list[dict[str, Any]],
    voice_examples: list[Any],
) -> dict[str, Any]:
    hypothesis = _clean(candidate.get("problem_hypothesis")) or None
    return {
        "schema_version": SCHEMA_VERSION,
        "motion": _clean(motion),
        "identity": {
            "company_name": _clean(identity.get("company_name")),
            "contact_name": _clean(identity.get("contact_name")),
            "contact_role": _clean(identity.get("contact_role")),
        },
        "evidence": [{
            "evidence_id": _clean(candidate.get("evidence_id")),
            "kind": _clean(candidate.get("evidence_kind")) or "other",
            "observation": _clean(candidate.get("observed_fact")),
            "source_url": _clean(candidate.get("source_url")),
            "source_type": _clean(candidate.get("source_type")) or "public",
            "source_date": candidate.get("observed_at"),
            "confidence": candidate.get("confidence"),
            "freshness": _clean(candidate.get("freshness")),
            "usable_for_outreach": True,
        }],
        "personalization": {
            "observation": _clean(candidate.get("observed_fact")),
            "evidence_ids": list(candidate.get("evidence_ids") or [candidate.get("evidence_id")]),
            "problem_hypothesis": hypothesis,
            "problem_hypothesis_status": "hypothesis" if hypothesis else "missing",
            "relevance_to_offer": _clean(
                candidate.get("relevance_to_offer") or candidate.get("bridge")
            ),
        },
        "sender": {
            "name": _clean(candidate.get("sender")),
            "role": _clean(candidate.get("sender_role")),
            "business": _clean(candidate.get("sender_company")),
            "founder_story": _clean(founder_story.get("story")),
            "proof": _clean(founder_story.get("proof")),
            "offer": _clean(founder_story.get("offer") or candidate.get("next_step")),
            "forbidden_claims": [
                _clean(item) for item in founder_story.get("forbidden_claims") or [] if _clean(item)
            ],
            "voice_examples": [_clean(item) for item in voice_examples if _clean(item)][:5],
        },
        "sequence": [{
            "sequence_index": int(item.get("sequence_index") or 0),
            "channel": _clean(item.get("channel")).lower(),
            "angle": _clean(item.get("angle")),
            "day_offset": max(0, int(item.get("day_offset") or 0)),
            "deterministic_draft": _clean(item.get("text")),
            "deterministic_subject": _clean(item.get("subject")) or None,
        } for item in sequence],
        "policy": {
            "approval_required": True,
            "external_dispatch_performed": False,
            "telegram_word_limit": 90,
            "email_word_limit": 120,
            "single_cta": True,
            "different_angle_per_touch": True,
            "no_new_recipient_facts": True,
        },
    }


def _generation_prompt(record: dict[str, Any]) -> str:
    return (
        "Ты готовишь founder-led мультиканальную outreach-цепочку LocalOS. "
        "Используй только INPUT_JSON и верни только JSON без markdown. "
        "Не добавляй факты, боли, результаты, коммерческие условия или знакомство, которых нет во входе. "
        "Observation - факт. problem_hypothesis - только гипотеза: не утверждай её как факт. "
        "LocalOS сам вставит observation, bridge, founder story и proof без изменений. "
        "Ты выбираешь только opening_style и cta_intent для каждого касания. "
        "opening_style: direct, warm или concise. "
        "cta_intent: send_short_review, send_example или ask_permission. "
        "LocalOS сам соберёт вступление и CTA из разрешённых формулировок. "
        "Если problem_hypothesis отсутствует, верни null и не пиши о боли, потере клиентов или влиянии факта на бизнес. "
        "Заверши каждое касание ровно одним вопросом-CTA. "
        "Свяжи факт с релевантным опытом отправителя. "
        "Каждое касание должно иметь новый угол, один простой CTA и работать отдельно. "
        "Не используй ритуальные комплименты, давление, ложную срочность, длинное тире и кавычки-ёлочки. "
        "Telegram - максимум 90 слов, email - максимум 120 слов. "
        "Для email дай спокойную фактическую тему; для других каналов subject=null. "
        "Верни объект schema_version=1.0 и touches. В каждом touch обязательны: "
        "sequence_index, channel, angle, subject, opening_style, cta_intent, evidence_ids, observation, "
        "problem_hypothesis, relevance_bridge. Индексы, каналы и углы не меняй.\n\n"
        f"INPUT_JSON:\n{json.dumps(record, ensure_ascii=False, default=str)}"
    )


def _review_prompt(record: dict[str, Any]) -> str:
    return (
        "Ты независимый редактор evidence-based outreach LocalOS. "
        "Проверь каждый touch только по INPUT_JSON. Не переписывай сообщения и не добавляй факты. "
        "Оцени от 0 до 2: source_validity, observation_accuracy, freshness_and_why_now, "
        "offer_bridge, recipient_specificity, proof_integrity, channel_fit, "
        "single_cta_and_length, state_and_suppression_safety. "
        "approve допустим только при сумме >=15, без блокирующей ошибки и при наличии источника для каждого факта. "
        "Иначе verdict=revise или reject. reason_codes могут быть только: "
        f"{', '.join(sorted(CANONICAL_REASON_CODES))}. "
        "Верни только JSON без markdown: schema_version=1.0, reviews. "
        "В каждом review: sequence_index, scores(object), total_score, verdict, reason_codes(list), notes(list).\n\n"
        f"INPUT_JSON:\n{json.dumps(record, ensure_ascii=False, default=str)}"
    )


def _normalize_touches(value: Any, request_record: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AI response touches must be a list")
    expected = request_record["sequence"]
    by_index = {
        int(item.get("sequence_index")): item
        for item in value
        if isinstance(item, dict) and str(item.get("sequence_index", "")).isdigit()
    }
    normalized = []
    allowed_evidence_ids = {
        _clean(item.get("evidence_id")) for item in request_record["evidence"]
    }
    forbidden_claims = request_record["sender"]["forbidden_claims"]
    observation = request_record["personalization"]["observation"]
    expected_hypothesis = request_record["personalization"]["problem_hypothesis"]
    relevance_bridge = request_record["personalization"]["relevance_to_offer"]
    recipient = request_record["identity"]["company_name"]
    template_values = {
        "RECIPIENT": recipient,
        "SENDER_NAME": request_record["sender"]["name"],
        "SENDER_ROLE": request_record["sender"]["role"],
        "SENDER_BUSINESS": request_record["sender"]["business"],
        "OBSERVATION": observation,
        "BRIDGE": relevance_bridge,
        "FOUNDER_STORY": request_record["sender"]["founder_story"],
        "FOUNDER_PROOF": request_record["sender"]["proof"],
        "OFFER": request_record["sender"]["offer"],
    }
    for expected_item in expected:
        index = int(expected_item["sequence_index"])
        item = by_index.get(index)
        if not item:
            raise ValueError(f"Missing generated touch {index}")
        channel = _clean(item.get("channel")).lower()
        angle = _clean(item.get("angle"))
        template = _clean(item.get("text_template"))
        text = _clean(item.get("text"))
        evidence_ids = [_clean(entry) for entry in item.get("evidence_ids") or [] if _clean(entry)]
        if channel != expected_item["channel"] or angle != expected_item["angle"]:
            raise ValueError(f"Touch {index} changed channel or angle")
        if template:
            required_fields = {"RECIPIENT", "OBSERVATION", "BRIDGE"}
            used_fields = set(re.findall(r"\{\{([A-Z_]+)\}\}", template))
            unknown_fields = used_fields.difference(ALLOWED_TEMPLATE_FIELDS)
            if unknown_fields:
                raise ValueError(
                    f"Touch {index} contains unsupported template fields: "
                    f"{', '.join(sorted(unknown_fields))}"
                )
            if not required_fields.issubset(used_fields):
                raise ValueError(f"Touch {index} misses required evidence placeholders")
            for field in used_fields:
                value = template_values.get(field)
                if not value:
                    raise ValueError(f"Touch {index} references missing sender field {field}")
                template = template.replace(f"{{{{{field}}}}}", value)
            if re.search(r"\{\{[^{}]+\}\}", template):
                raise ValueError(f"Touch {index} contains an unresolved placeholder")
            text = _clean(template)
        else:
            text = _assemble_constrained_text(
                item=item,
                expected_item=expected_item,
                request_record=request_record,
                template_values=template_values,
            )
        if not text or observation not in text:
            raise ValueError(f"Touch {index} does not preserve sourced observation")
        if relevance_bridge and relevance_bridge not in text:
            raise ValueError(f"Touch {index} does not preserve the offer bridge")
        if recipient and recipient.lower() not in text.lower():
            raise ValueError(f"Touch {index} does not identify the recipient")
        if not evidence_ids or not set(evidence_ids).issubset(allowed_evidence_ids):
            raise ValueError(f"Touch {index} has unsupported evidence ids")
        if any(claim.lower() in text.lower() for claim in forbidden_claims):
            raise ValueError(f"Touch {index} contains a forbidden claim")
        generated_hypothesis = _clean(item.get("problem_hypothesis")) or None
        if generated_hypothesis and generated_hypothesis != expected_hypothesis:
            raise ValueError(f"Touch {index} introduced an unsupported hypothesis")
        normalized.append({
            "sequence_index": index,
            "channel": channel,
            "angle": angle,
            "subject": _safe_subject(channel, recipient),
            "text": text,
            "evidence_ids": evidence_ids,
            "observation": _clean(item.get("observation")) or observation,
            "problem_hypothesis": generated_hypothesis,
            "relevance_bridge": _clean(item.get("relevance_bridge")) or relevance_bridge,
        })
    return normalized


def _assemble_constrained_text(
    *,
    item: dict[str, Any],
    expected_item: dict[str, Any],
    request_record: dict[str, Any],
    template_values: dict[str, Any],
) -> str:
    index = int(expected_item["sequence_index"])
    opening_style = _clean(item.get("opening_style")).lower()
    cta_intent = _clean(item.get("cta_intent")).lower()
    if opening_style or cta_intent:
        return _assemble_policy_bound_text(
            index=index,
            opening_style=opening_style,
            cta_intent=cta_intent,
            expected_item=expected_item,
            request_record=request_record,
        )
    opening = _clean(item.get("opening_template"))
    cta = _clean(item.get("cta_question"))
    if not opening or not cta:
        raise ValueError(f"Touch {index} must provide opening_template and cta_question")
    opening = _normalize_safe_typography(opening)
    cta = _normalize_safe_typography(cta)
    opening_fields = set(re.findall(r"\{\{([A-Z_]+)\}\}", opening))
    allowed_opening_fields = {"RECIPIENT", "SENDER_NAME", "SENDER_ROLE", "SENDER_BUSINESS"}
    if opening_fields.difference(allowed_opening_fields):
        raise ValueError(f"Touch {index} opening uses unsupported placeholders")
    if "RECIPIENT" not in opening_fields:
        opening = "{{RECIPIENT}}, " + opening.lstrip(" ,")
        opening_fields.add("RECIPIENT")
    for field in opening_fields:
        value = _clean(template_values.get(field))
        if not value:
            raise ValueError(f"Touch {index} references missing sender field {field}")
        opening = opening.replace(f"{{{{{field}}}}}", value)
    unsafe_fragment_patterns = (
        r"\d",
        r"\b(?:теря|потер|сниж|огранич|проблем|недостат|выруч|рост|гарант)",
    )
    for fragment_name, fragment in (("opening", opening), ("cta", cta)):
        if any(re.search(pattern, fragment, flags=re.I) for pattern in unsafe_fragment_patterns):
            raise ValueError(f"Touch {index} {fragment_name} contains an unsupported claim")
        if re.search(r"[^\w\sа-яА-ЯёЁ.,!?;:()'\"/-]", fragment, flags=re.UNICODE):
            raise ValueError(f"Touch {index} {fragment_name} contains unsupported symbols")
    if cta.count("?") != 1 or not cta.endswith("?"):
        raise ValueError(f"Touch {index} CTA must be one question")
    if len(re.findall(r"\b[\wа-яА-ЯёЁ0-9-]+\b", cta, flags=re.UNICODE)) > 16:
        raise ValueError(f"Touch {index} CTA is too long")

    angle = _clean(expected_item.get("angle"))
    trusted_sender_block = ""
    if angle == "founder_story":
        trusted_sender_block = _clean(request_record["sender"].get("founder_story"))
    elif angle == "proof":
        trusted_sender_block = _clean(
            request_record["sender"].get("proof") or request_record["sender"].get("founder_story")
        )
    elif angle == "respectful_close":
        trusted_sender_block = "Если сейчас неактуально, больше напоминать не буду."
    blocks = [
        opening.rstrip(" .!?;") + ".",
        trusted_sender_block.rstrip(" .!?;") + "." if trusted_sender_block else "",
        _clean(request_record["personalization"]["observation"]).rstrip(" .!?;") + ".",
        _clean(request_record["personalization"]["relevance_to_offer"]).rstrip(" .!?;") + ".",
        cta,
    ]
    return _clean(" ".join(block for block in blocks if block))


def _assemble_policy_bound_text(
    *,
    index: int,
    opening_style: str,
    cta_intent: str,
    expected_item: dict[str, Any],
    request_record: dict[str, Any],
) -> str:
    if opening_style not in {"direct", "warm", "concise"}:
        raise ValueError(f"Touch {index} has unsupported opening_style")
    cta_by_intent = {
        "send_short_review": "Могу прислать короткий разбор?",
        "send_example": "Прислать пример разбора?",
        "ask_permission": "Можно отправить короткий разбор?",
    }
    if cta_intent not in cta_by_intent:
        raise ValueError(f"Touch {index} has unsupported cta_intent")

    sender = request_record["sender"]
    recipient = request_record["identity"]["company_name"]
    sender_name = _clean(sender.get("name"))
    sender_role = _clean(sender.get("role"))
    sender_business = _clean(sender.get("business"))
    role_and_business = sender_role
    if sender_business and sender_business.lower() not in sender_role.lower():
        role_and_business = _clean(f"{sender_role} {sender_business}")
    sender_identity = sender_name
    if role_and_business:
        sender_identity = f"{sender_identity}, {role_and_business}" if sender_identity else role_and_business

    salutation = "Добрый день!" if opening_style == "warm" else "Здравствуйте!"
    angle = _clean(expected_item.get("angle"))
    if angle == "signal":
        opening = f'{salutation} Я {sender_identity}. Посмотрел публичную карточку "{recipient}".'
    elif angle == "founder_story":
        opening = f'{salutation} Я {sender_identity}. Пишу по поводу карточки "{recipient}".'
    elif angle == "proof":
        opening = f'{salutation} Коротко дополню по карточке "{recipient}".'
    elif angle == "respectful_close":
        opening = f'{salutation} Коротко закрою тему по карточке "{recipient}".'
    else:
        opening = f'{salutation} Я {sender_identity}. Пишу по поводу "{recipient}".'

    trusted_sender_block = ""
    if angle == "founder_story":
        trusted_sender_block = _clean(sender.get("founder_story"))
    elif angle == "proof":
        trusted_sender_block = _clean(sender.get("proof") or sender.get("founder_story"))
    elif angle == "respectful_close":
        trusted_sender_block = "Если сейчас неактуально, больше напоминать не буду."

    hypothesis_block = ""
    hypothesis = _clean(request_record["personalization"].get("problem_hypothesis"))
    if hypothesis and angle == "signal":
        hypothesis_block = f"Гипотеза для проверки: {hypothesis.rstrip(' .!?;')}."
    blocks = [
        opening,
        trusted_sender_block.rstrip(" .!?;") + "." if trusted_sender_block else "",
        _clean(request_record["personalization"]["observation"]).rstrip(" .!?;") + ".",
        hypothesis_block,
        _clean(request_record["personalization"]["relevance_to_offer"]).rstrip(" .!?;") + ".",
        cta_by_intent[cta_intent],
    ]
    return _clean(" ".join(block for block in blocks if block))


def _safe_subject(channel: str, recipient: str) -> str | None:
    if channel != "email":
        return None
    suffix = f" по карточке {recipient}" if recipient else ""
    return f"Короткий вопрос{suffix}"


def _normalize_reviews(value: Any, touches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("AI response reviews must be a list")
    by_index = {
        int(item.get("sequence_index")): item
        for item in value
        if isinstance(item, dict) and str(item.get("sequence_index", "")).isdigit()
    }
    normalized = []
    for touch in touches:
        index = int(touch["sequence_index"])
        item = by_index.get(index)
        if not item or not isinstance(item.get("scores"), dict):
            raise ValueError(f"Missing semantic review {index}")
        scores = {
            criterion: max(0, min(2, int(item["scores"].get(criterion) or 0)))
            for criterion in QUALITY_CRITERIA
        }
        total = sum(scores.values())
        reason_codes = [
            _clean(code).upper()
            for code in item.get("reason_codes") or []
            if _clean(code).upper() in CANONICAL_REASON_CODES
        ]
        requested_verdict = _clean(item.get("verdict")).lower()
        verdict = requested_verdict if requested_verdict in {"approve", "revise", "reject"} else "reject"
        if total < 15 or reason_codes:
            verdict = "reject" if requested_verdict == "reject" else "revise"
        normalized.append({
            "sequence_index": index,
            "scores": scores,
            "total_score": total,
            "max_score": 18,
            "verdict": verdict,
            "passed": verdict == "approve" and total >= 15 and not reason_codes,
            "reason_codes": list(dict.fromkeys(reason_codes)),
            "notes": [_clean(note) for note in item.get("notes") or [] if _clean(note)][:10],
        })
    return normalized


def _parse_json_object(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("AI returned an empty response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI response does not contain a JSON object")
        parsed = json.loads(text[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("AI response JSON must be an object")
    if str(parsed.get("schema_version") or SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("Unsupported outreach schema version")
    return parsed


def _default_generator(prompt: str, *, business_id: str = "", user_id: str = "") -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="outreach_personalization",
        business_id=business_id or None,
        user_id=user_id or None,
    )


def _failed(code: str, message: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "failed",
        "source": "gigachat",
        "prompt_version": PROMPT_VERSION,
        "review_prompt_version": REVIEW_PROMPT_VERSION,
        "touches": [],
        "semantic_reviews": [],
        "error_code": code,
        "error": re.sub(r"\s+", " ", str(message or "")).strip()[:500],
    }


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_safe_typography(value: str) -> str:
    return value.translate(str.maketrans({"—": "-", "–": "-", "«": '"', "»": '"'}))
