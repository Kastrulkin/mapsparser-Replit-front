"""Grounded founder-led outreach previews and versioned multichannel campaigns."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from psycopg2.extras import Json

from services.outreach_personalization_ai import (
    QUALITY_CRITERIA,
    ai_personalization_enabled,
    generation_contract_current,
    generate_personalized_sequence,
)
from services.outreach_decision_service import (
    _is_residential_recipient,
    build_outreach_decision,
    offer_candidates,
    select_offer,
    select_trust,
    trust_candidates,
)
from services.outreach_relationship_service import (
    ROOM_INVITATION_CLASSIFICATIONS,
    mark_room_ready_after_positive_reply,
    mirror_inbound_to_room,
    prepare_private_room,
    upsert_relationship_from_reply,
)
from services.outreach_sender_profile_service import evaluate_sender_profile_completeness
from services.outreach_safety_service import (
    approval_snapshot_hash,
    classify_inbound_event,
    recipient_key,
    record_learning_event,
    sender_scope_preflight_reason,
    strategy_fingerprint,
)


AUTOMATIC_CHANNELS = {"telegram", "email", "vk"}
MANUAL_CHANNELS = {"max", "whatsapp", "sms", "manual"}
SUPPORTED_CHANNELS = AUTOMATIC_CHANNELS | MANUAL_CHANNELS
SENDER_MODE_LOCALOS = "localos"
SENDER_MODE_PARTNER_BUSINESS = "partner_business"
SENDER_MODE_LOCALOS_FOR_PARTNER = "localos_for_partner"
SENDER_MODES = {
    SENDER_MODE_LOCALOS,
    SENDER_MODE_PARTNER_BUSINESS,
    SENDER_MODE_LOCALOS_FOR_PARTNER,
}
CAMPAIGN_BUSINESS_OUTCOMES = {
    "no_reply", "interested", "question", "call_planned", "contacts_exchanged",
    "pilot_agreed", "campaign_launched", "joint_project", "recurring_partnership",
    "hard_no", "not_relevant", "lost", "meeting_booked", "converted",
}
DEFAULT_SEQUENCE = (
    ("telegram", 0, "signal"),
    ("email", 3, "founder_story"),
    ("next", 7, "proof"),
    ("next", 12, "respectful_close"),
)
NON_RECIPIENT_EMAIL_DOMAINS = {
    "company24.com",
    "dikidi.net",
    "yclients.com",
    "zoon.ru",
}
EMAIL_ROLE_MISMATCH_PREFIXES = (
    "hr", "job", "jobs", "career", "careers", "vacancy", "vacancies",
    "resume", "rabota", "noreply", "no-reply", "donotreply",
)
PILOT_REASON_GUIDANCE = {
    "campaign_generation_not_ready": "Создайте новую версию и исправьте замечания проверки текста.",
    "pilot_campaign_not_approved": "Проверьте preview и подтвердите всю цепочку один раз.",
    "pilot_first_touch_manual": "Отправьте первое касание вручную и отметьте результат в LocalOS.",
    "sender_account_missing": "Выберите подключённый аккаунт отправителя и создайте новую версию.",
    "pilot_queue_missing": "Сохраните и подтвердите новую версию кампании.",
    "pilot_queue_not_ready": "Откройте журнал кампании и устраните причину паузы очереди.",
    "pilot_requires_global_dispatcher_disabled": "Для точечного пилота оставьте фоновую отправку выключенной.",
    "sender_not_connected": "Подключите аккаунт отправителя заново.",
    "sender_permission_revoked": "Разрешите отправку и обязательную проверку ответов.",
    "sender_scope_mismatch": "Выберите аккаунт из правильного контура: LocalOS или текущего бизнеса.",
    "sender_business_mismatch": "Выберите аккаунт, принадлежащий текущему бизнесу.",
    "sender_mode_scope_mismatch": "Создайте новую версию с правильным способом представления отправителя.",
    "represented_business_mismatch": "Заново выберите бизнес, которого представляет LocalOS, и создайте новую версию.",
    "sender_mode_invalid": "Выберите допустимый способ представления отправителя и создайте новую версию.",
    "sender_adapter_incomplete": "Пройдите безопасную проверку отправки и получения ответов.",
    "sender_paused": "Проверьте здоровье аккаунта отправителя.",
    "sender_blocked": "Подключите другой разрешённый аккаунт после проверки причины блокировки.",
    "recipient_contact_invalid": "Перепроверьте или обогатите контакт получателя.",
    "suppressed_contact": "Получатель находится в stop-list; отправка запрещена.",
    "recipient_replied": "Ответ уже получен; зафиксируйте результат разговора.",
    "conflicting_active_campaign": "Остановите другую активную кампанию этому получателю.",
    "cross_channel_cooldown": "Дождитесь окончания безопасного интервала между касаниями.",
    "sender_daily_limit_reached": "Дождитесь обновления дневного лимита отправителя.",
    "approval_snapshot_missing": "Подтвердите текущую версию кампании заново.",
    "approval_version_changed": "Создайте и подтвердите новую версию после изменений.",
    "generation_contract_outdated": "Обновите preview: правила персонализации изменились.",
    "pilot_reply_sync_required": "Проверьте входящие ответы для аккаунта этой кампании.",
}


def record_campaign_event(
    cursor: Any,
    campaign_id: str,
    event_type: str,
    *,
    actor_id: str | None,
    touch_id: str | None = None,
    reason_code: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    cursor.execute(
        """
        INSERT INTO outreach_campaign_events (
            id, campaign_id, touch_id, event_type, reason_code,
            payload_json, actor_id, created_at
        ) VALUES (%s, %s, NULLIF(%s, '')::uuid, %s, NULLIF(%s, ''), %s, NULLIF(%s, ''), NOW())
        """,
        (
            str(uuid.uuid4()), campaign_id, touch_id or "", event_type,
            reason_code or "", Json(payload or {}), actor_id or None,
        ),
    )


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _scalar(row: Any, key: str) -> Any:
    if row is None:
        return None
    if hasattr(row, "keys"):
        return row[key]
    return row[0]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _represented_business_opening(context: dict[str, Any]) -> str:
    """Build the external company voice for an authorised LocalOS sender account."""
    business_name = _text(context.get("represented_business_name"))
    if not business_name:
        return ""
    profile = (
        context.get("business_sender_profile")
        if isinstance(context.get("business_sender_profile"), dict)
        else {}
    )
    profile_context = (
        profile.get("outreach_context_json")
        if profile.get("confirmed_at") and isinstance(profile.get("outreach_context_json"), dict)
        else {}
    )
    descriptor = _text(
        profile_context.get("sender_description")
        or profile_context.get("business_description")
    ).strip(" .")
    categories = _list(context.get("client_business_categories"))
    primary_category = _text(categories[0] if categories else "").lower()
    business_type = _text(context.get("client_business_type")).lower()
    if not descriptor:
        descriptor_by_category = {
            "детский салон-парикмахерская": "детская парикмахерская",
            "детская парикмахерская": "детская парикмахерская",
            "салон красоты": "салон красоты",
            "медицинский центр": "медицинский центр",
            "стоматологическая клиника": "стоматологическая клиника",
            "фитнес-клуб": "фитнес-клуб",
            "образовательный центр": "образовательный центр",
        }
        descriptor = descriptor_by_category.get(primary_category) or descriptor_by_category.get(business_type) or ""
        if descriptor and context.get("client_business_network_id"):
            if descriptor == "детская парикмахерская":
                descriptor = "сеть детских парикмахерских"
            elif not descriptor.startswith("сеть "):
                descriptor = f"сеть {descriptor}"
    identity = f"{descriptor} {business_name}" if descriptor else business_name
    return f"Мы ваши соседи - {identity}."


def resolve_sender_mode(workstream_type: str, requested_mode: Any = None) -> str:
    """Resolve an explicit sender identity without allowing a hidden fallback."""
    motion = _text(workstream_type)
    if motion not in {"localos_sales", "client_partnership"}:
        raise ValueError("Unsupported workstream_type for outreach sender")
    requested = _text(requested_mode).lower()
    default_mode = (
        SENDER_MODE_LOCALOS
        if motion == "localos_sales"
        else SENDER_MODE_PARTNER_BUSINESS
    )
    mode = requested or default_mode
    if mode not in SENDER_MODES:
        raise ValueError("Unsupported sender_mode")
    if motion == "localos_sales" and mode != SENDER_MODE_LOCALOS:
        raise ValueError("LocalOS sales campaigns must be sent by LocalOS")
    if motion == "client_partnership" and mode == SENDER_MODE_LOCALOS:
        raise ValueError("Partner campaigns require partner_business or localos_for_partner sender_mode")
    return mode


def _profile_facts(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _localos_representative_profile(context: dict[str, Any]) -> dict[str, Any]:
    """Use LocalOS infrastructure while keeping the external voice with the authorised business."""
    localos_profile = dict(context.get("platform_sender_profile") or {})
    if not localos_profile:
        return {}
    represented_profile = dict(context.get("business_sender_profile") or {})
    represented_confirmed = bool(represented_profile.get("confirmed_at"))
    identity = dict(localos_profile)
    identity["display_name"] = ""
    identity["role_title"] = ""
    identity["company_name"] = _text(context.get("represented_business_name"))
    identity["competence_story"] = ""
    identity["proof_points_json"] = []
    identity["verified_cases_json"] = []
    represented_offers = (
        _profile_facts(represented_profile.get("allowed_offers_json"))
        if represented_confirmed
        else []
    )
    identity["allowed_offers_json"] = represented_offers
    identity["forbidden_claims_json"] = (
        _profile_facts(localos_profile.get("forbidden_claims_json"))
        + (
            _profile_facts(represented_profile.get("forbidden_claims_json"))
            if represented_confirmed
            else []
        )
    )
    identity["voice_examples_json"] = []
    represented_context = (
        dict(represented_profile.get("outreach_context_json"))
        if represented_confirmed
        and isinstance(represented_profile.get("outreach_context_json"), dict)
        else {}
    )
    if not _profile_facts(represented_context.get("desired_partner_types")):
        represented_context["desired_partner_types"] = [
            _text(item)
            for item in re.split(r"\s*/\s*", _text(context.get("category")))
            if _text(item)
        ]
    represented_context["representation_only"] = True
    represented_context["competence_story_status"] = "missing"
    identity["outreach_context_json"] = represented_context
    identity["_business_service_count"] = context.get("business_service_count")
    identity["_represented_profile_id"] = (context.get("business_sender_profile") or {}).get("id")
    return identity


def _apply_sender_mode(context: dict[str, Any], requested_mode: Any = None) -> dict[str, Any]:
    mode = resolve_sender_mode(_text(context.get("workstream_type")), requested_mode)
    context["sender_mode"] = mode
    context["represented_business_id"] = (
        context.get("client_business_id") if mode == SENDER_MODE_LOCALOS_FOR_PARTNER else None
    )
    context["represented_business_name"] = (
        context.get("client_business_name") if mode == SENDER_MODE_LOCALOS_FOR_PARTNER else None
    )
    if mode == SENDER_MODE_LOCALOS_FOR_PARTNER:
        context["sender_profile"] = _localos_representative_profile(context)
    elif mode == SENDER_MODE_PARTNER_BUSINESS:
        context["sender_profile"] = dict(context.get("business_sender_profile") or {})
    else:
        context["sender_profile"] = dict(context.get("platform_sender_profile") or context.get("sender_profile") or {})
    return context


def build_pilot_readiness(
    state: dict[str, Any],
    *,
    dispatch_preflight: dict[str, Any] | None = None,
    global_dispatcher_enabled: bool = False,
) -> dict[str, Any]:
    """Explain the exact next step before a one-touch live pilot without sending."""
    campaign_status = _text(state.get("campaign_status"))
    stop_reason = _text(state.get("stop_reason"))
    channel = _text(state.get("channel")).lower()
    touch_status = _text(state.get("touch_status"))
    delivery_status = _text(state.get("delivery_status"))
    full_chain_ready = bool(state.get("generation_current") and state.get("quality_passed"))
    campaign_approved = campaign_status in {"approved", "active"}
    first_touch_automatic = channel in AUTOMATIC_CHANNELS
    sender_selected = bool(_text(state.get("sender_account_id"))) if first_touch_automatic else True
    queue_ready = bool(_text(state.get("queue_id")) and delivery_status == "queued")
    already_sent = touch_status in {"manual_sent", "sent", "delivered"} or delivery_status in {
        "sent", "delivered",
    }
    reply_received = stop_reason == "recipient_replied" or bool(state.get("last_reply_at"))
    safety_ready = bool((dispatch_preflight or {}).get("allowed"))
    checks = [
        {"code": "full_chain_ready", "label": "Тексты и источники прошли проверку", "passed": full_chain_ready},
        {"code": "campaign_approved", "label": "Вся цепочка подтверждена человеком", "passed": campaign_approved},
        {"code": "first_touch_automatic", "label": "Первое касание поддерживает безопасную отправку", "passed": first_touch_automatic},
        {"code": "sender_selected", "label": "Выбран конкретный аккаунт отправителя", "passed": sender_selected},
        {"code": "queue_ready", "label": "Первое касание готово в очереди", "passed": queue_ready},
        {"code": "global_dispatcher_disabled", "label": "Фоновая отправка выключена на время пилота", "passed": not global_dispatcher_enabled},
        {"code": "dispatch_preflight", "label": "Разрешения, ответы, stop-list и лимиты проверены", "passed": safety_ready},
    ]

    if reply_received:
        status, reason_code = "reply_received", "recipient_replied"
    elif already_sent:
        status, reason_code = "waiting_reply", "pilot_reply_sync_required"
    elif not full_chain_ready:
        status, reason_code = "needs_attention", "campaign_generation_not_ready"
    elif not campaign_approved:
        status, reason_code = "needs_attention", "pilot_campaign_not_approved"
    elif not first_touch_automatic:
        status, reason_code = "manual_first_touch", "pilot_first_touch_manual"
    elif not sender_selected:
        status, reason_code = "needs_attention", "sender_account_missing"
    elif not state.get("queue_id"):
        status, reason_code = "needs_attention", "pilot_queue_missing"
    elif not queue_ready:
        status, reason_code = "needs_attention", "pilot_queue_not_ready"
    elif global_dispatcher_enabled:
        status, reason_code = "needs_attention", "pilot_requires_global_dispatcher_disabled"
    elif not safety_ready:
        status = "needs_attention"
        reason_code = _text((dispatch_preflight or {}).get("reason_code")) or "campaign_preflight_failed"
    else:
        status, reason_code = "ready", "pilot_preflight_passed"

    return {
        "status": status,
        "reason_code": reason_code,
        "can_dispatch_first_touch": status == "ready",
        "messages_sent": 0,
        "first_touch": {
            "touch_id": _text(state.get("touch_id")) or None,
            "channel": channel or None,
            "queue_id": _text(state.get("queue_id")) or None,
            "sender_account_id": _text(state.get("sender_account_id")) or None,
            "delivery_status": delivery_status or None,
        },
        "checks": checks,
        "next_action": (
            "Можно отправить ровно первое касание. Перед отправкой LocalOS повторит проверки."
            if status == "ready"
            else PILOT_REASON_GUIDANCE.get(
                reason_code,
                "Откройте журнал кампании и устраните указанную причину.",
            )
        ),
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _quality_criterion_scores(checks: dict[str, Any]) -> dict[str, int]:
    """Translate deterministic safety checks into the canonical 0-2 review scale."""

    return {
        "source_validity": 2 if checks.get("fact") else 0,
        "observation_accuracy": 2 if checks.get("fact") and checks.get("removal") else 0,
        "freshness_and_why_now": 2 if checks.get("freshness") else 0,
        "offer_bridge": 2 if checks.get("bridge") else 0,
        "recipient_specificity": 2 if checks.get("specificity") and checks.get("removal") else 0,
        "proof_integrity": 2 if checks.get("proof_integrity") else 0,
        "channel_fit": 2 if checks.get("channel_fit") and checks.get("human_tone") and checks.get("style_contract") else 0,
        "single_cta_and_length": 2 if checks.get("single_cta") and checks.get("channel_fit") else 0,
        "state_and_suppression_safety": 2 if checks.get("suppression_safety") else 0,
    }


def _merge_semantic_quality(
    deterministic_gate: dict[str, Any],
    semantic_review: dict[str, Any],
) -> dict[str, Any]:
    """Use the most conservative deterministic/semantic score for each criterion."""

    gate = dict(deterministic_gate)
    deterministic_scores = gate.get("criterion_scores") or {}
    semantic_scores = semantic_review.get("scores") or {}
    criterion_scores = {
        criterion: min(
            int(deterministic_scores.get(criterion) or 0),
            max(0, min(2, int(semantic_scores.get(criterion) or 0))),
        )
        for criterion in QUALITY_CRITERIA
    }
    reason_codes = list(dict.fromkeys(
        list(gate.get("reason_codes") or [])
        + list(semantic_review.get("reason_codes") or [])
    ))
    total_score = sum(criterion_scores.values())
    semantic_verdict = _text(semantic_review.get("verdict")).lower()
    if gate.get("blocking_reasons") or semantic_verdict == "reject":
        verdict = "reject"
    elif total_score >= 15 and not reason_codes and semantic_verdict == "approve":
        verdict = "approve"
    else:
        verdict = "revise"
    gate.update({
        "criterion_scores": criterion_scores,
        "score": total_score,
        "total_score": total_score,
        "max_score": 18,
        "verdict": verdict,
        "passed": verdict == "approve",
        "reason_codes": reason_codes,
        "canonical_reason_codes": reason_codes,
        "semantic_review": semantic_review,
    })
    return gate


def _aggregate_quality_gate(touches: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one conservative campaign review while preserving touch-level results."""

    gates = [
        touch.get("quality_gate")
        for touch in touches
        if isinstance(touch.get("quality_gate"), dict)
    ]
    if not gates:
        return {
            "criterion_scores": {criterion: 0 for criterion in QUALITY_CRITERIA},
            "score": 0,
            "total_score": 0,
            "max_score": 18,
            "verdict": "reject",
            "passed": False,
            "reason_codes": ["SOURCE_MISSING"],
            "touch_results": [],
        }
    criterion_scores = {
        criterion: min(
            int((gate.get("criterion_scores") or {}).get(criterion) or 0)
            for gate in gates
        )
        for criterion in QUALITY_CRITERIA
    }
    reason_codes = list(dict.fromkeys(
        code
        for gate in gates
        for code in gate.get("reason_codes") or []
    ))
    verdicts = {_text(gate.get("verdict")).lower() for gate in gates}
    if "reject" in verdicts:
        verdict = "reject"
    elif "revise" in verdicts or reason_codes:
        verdict = "revise"
    else:
        verdict = "approve"
    return {
        "criterion_scores": criterion_scores,
        "score": sum(criterion_scores.values()),
        "total_score": sum(criterion_scores.values()),
        "max_score": 18,
        "verdict": verdict,
        "passed": verdict == "approve",
        "reason_codes": reason_codes,
        "touch_results": [
            {
                "sequence_index": touch.get("sequence_index"),
                "channel": touch.get("channel"),
                "criterion_scores": gate.get("criterion_scores") or {},
                "total_score": int(gate.get("total_score") or gate.get("score") or 0),
                "max_score": int(gate.get("max_score") or 18),
                "verdict": gate.get("verdict") or "reject",
                "reason_codes": gate.get("reason_codes") or [],
            }
            for touch, gate in zip(touches, gates)
        ],
    }


def _public_http_url(value: Any) -> str:
    url = _text(value)
    parsed = urlparse(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def _contact_confidence(value: Any) -> str:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.6:
        return "medium"
    return "low"


def _review_contacts(context: dict[str, Any], generated_at: datetime) -> list[dict[str, Any]]:
    fallback_source = _public_http_url(context.get("source_url")) or _public_http_url(context.get("website"))
    contacts = []
    for contact in context.get("contacts") or []:
        value = _text(contact.get("value"))
        source_url = _public_http_url(contact.get("source_url")) or fallback_source
        if not value or not source_url:
            continue
        raw_channel = _text(contact.get("contact_type")).lower()
        channel = raw_channel if raw_channel in {"telegram", "email", "vk", "whatsapp", "max"} else "manual"
        verification = _text(contact.get("verification_status")).lower()
        if channel != "email":
            email_status = "not_applicable"
        elif verification in {"verified", "confirmed", "confirmed_source", "valid"}:
            email_status = "verified"
        elif verification == "invalid":
            email_status = "invalid"
        elif verification in {"risky", "catch_all"}:
            email_status = "risky"
        else:
            email_status = "unknown"
        contacts.append({
            "channel": channel,
            "value": value,
            "source_url": source_url,
            "observed_at": _json_safe(
                contact.get("observed_at")
                or contact.get("updated_at")
                or contact.get("created_at")
                or generated_at
            ),
            "confidence": _contact_confidence(contact.get("confidence")),
            "email_status": email_status,
        })
    return contacts


def _review_record(
    context: dict[str, Any],
    *,
    ledger: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    selected_candidate_id: str,
    touches: list[dict[str, Any]],
    quality_gate: dict[str, Any],
    risks: list[str],
    generated_at: datetime,
) -> dict[str, Any]:
    research = context.get("research") or {}
    research_brief = research.get("message_brief_json") or {}
    if not isinstance(research_brief, dict):
        research_brief = {}
    public_urls = list(dict.fromkeys(
        url
        for url in (
            _public_http_url(context.get("source_url")),
            _public_http_url(context.get("website")),
        )
        if url
    ))
    limitations = []
    for item in _list(research.get("limitations_json")):
        if isinstance(item, dict):
            limitation = _text(item.get("reason") or item.get("code") or item.get("label"))
        else:
            limitation = _text(item)
        if limitation:
            limitations.append(limitation)
    try:
        icp_score = max(0, min(100, int(research.get("score") or 0)))
    except (TypeError, ValueError):
        icp_score = 0
    disqualifiers = []
    for item in _list(research_brief.get("disqualifiers")):
        disqualifier = _text(item.get("reason") if isinstance(item, dict) else item)
        if disqualifier:
            disqualifiers.append(disqualifier)
    selected_candidate = next(
        (candidate for candidate in candidates if candidate.get("id") == selected_candidate_id),
        {},
    )
    canonical_evidence = []
    for item in ledger:
        evidence_id = _text(item.get("evidence_id") or item.get("id"))
        observation = _text(item.get("observation") or item.get("fact"))
        source_url = _public_http_url(item.get("source_url"))
        if not evidence_id or not observation or not source_url:
            continue
        canonical_evidence.append({
            "evidence_id": evidence_id,
            "kind": _text(item.get("kind") or "other"),
            "observation": observation,
            "source_url": source_url,
            "source_type": _text(item.get("source_type") or item.get("kind") or "public_source"),
            "source_date": _json_safe(item.get("observed_at")) if item.get("observed_at") else None,
            "researched_at": _json_safe(research.get("researched_at") or generated_at),
            "confidence": _contact_confidence(item.get("confidence")),
            "usable_for_outreach": item.get("status") in {"approved", "observed"},
            "rejection_reason": _text(item.get("rejected_reason")) or None,
        })
    canonical_candidates = []
    for candidate in candidates:
        candidate_id = _text(candidate.get("personalization_id") or candidate.get("id"))
        observation = _text(candidate.get("observation") or candidate.get("observed_fact"))
        evidence_ids = [
            _text(item)
            for item in _list(candidate.get("evidence_ids"))
            if _text(item)
        ]
        if not evidence_ids and _text(candidate.get("evidence_id")):
            evidence_ids = [_text(candidate.get("evidence_id"))]
        hypothesis = _text(candidate.get("problem_hypothesis")) or (
            "Гипотеза не используется: сообщение опирается только на наблюдаемый публичный факт."
        )
        relevance = _text(candidate.get("relevance_to_offer") or candidate.get("bridge"))
        canonical_candidates.append({
            "personalization_id": candidate_id,
            "evidence_ids": evidence_ids,
            "observation": observation,
            "problem_hypothesis": hypothesis,
            "relevance_to_offer": relevance,
            "personalized_opener": _text(candidate.get("personalized_opener")) or f"{observation} {relevance}".strip(),
            "confidence": _contact_confidence(candidate.get("confidence")),
            "usable": bool(candidate_id and observation and evidence_ids and relevance),
            "removal_test_passed": bool(candidate_id and observation and evidence_ids and relevance),
            "rejection_reason": _text(candidate.get("rejection_reason")) or None,
        })
    canonical_touches = []
    for touch in touches:
        body = _text(touch.get("text") or touch.get("body"))
        questions = re.findall(r"[^.!?\n]*\?", body)
        cta = _text(questions[-1]) if questions else ""
        raw_channel = _text(touch.get("channel")).lower()
        channel = raw_channel if raw_channel in {"telegram", "email", "vk", "whatsapp", "max"} else "manual"
        evidence_id = _text(touch.get("evidence_id"))
        canonical_touches.append({
            "touch_no": int(touch.get("sequence_index") or 0) + 1,
            "channel": channel,
            "day_offset": int(touch.get("day_offset") or 0),
            "angle": _text(touch.get("angle")),
            "subject": _text(touch.get("subject")) or None,
            "body": body,
            "cta": cta,
            "evidence_ids": [evidence_id] if evidence_id else [],
            "quality_gate": touch.get("quality_gate") or {},
            "sender_account_id": _text(touch.get("sender_account_id")) or None,
            "channel_status": _text(touch.get("channel_status")),
        })
    review_risks = list(risks) + limitations
    return _json_safe({
        "schema_version": "1.0",
        "lead_id": str(context.get("lead_id") or ""),
        "motion": _text(context.get("workstream_type")),
        "identity": {
            "company_name": _text(context.get("lead_name")),
            "contact_name": _text(selected_candidate.get("contact_name")),
            "contact_role": _text(selected_candidate.get("contact_role")),
            "public_urls": public_urls,
        },
        "contacts": _review_contacts(context, generated_at),
        "qualification": {
            "segment": _text(research_brief.get("segment") or context.get("category")),
            "icp_score": icp_score,
            "disqualifiers": disqualifiers,
        },
        "evidence": canonical_evidence,
        "personalization_candidates": canonical_candidates,
        "selected_personalization_id": selected_candidate_id,
        "touches": canonical_touches,
        "quality_gate": quality_gate,
        "approval": {
            "status": "needs_review",
            "requires_human_approval": True,
        },
        "campaign": {
            "status": "draft",
            "stop_on_reply": True,
            "sender_mode": context.get("sender_mode"),
            "selected_offer": selected_candidate.get("next_step"),
            "selected_offer_id": selected_candidate.get("offer_id"),
            "trust_strategy": selected_candidate.get("trust_strategy"),
            "trust_statement": selected_candidate.get("trust_statement"),
        },
        "outcome": {
            "reply_status": "not_contacted",
            "unsubscribe": False,
            "suppressed": False,
        },
        "risks": list(dict.fromkeys(risk for risk in review_risks if risk)),
        "generated_at": generated_at,
    })


def _recipient_contact_eligible(contact: dict[str, Any]) -> bool:
    if _text(contact.get("contact_type")) != "email":
        return True
    if _text(contact.get("verification_status")) not in {"verified", "confirmed_source"}:
        return False
    value = _text(contact.get("value")).lower()
    if "@" not in value:
        return False
    local_part, domain = value.rsplit("@", 1)
    domain = domain.removeprefix("www.")
    if domain in NON_RECIPIENT_EMAIL_DOMAINS:
        return False
    normalized_local = re.sub(r"[^a-zа-яё0-9-]", "", local_part.lower())
    return not any(normalized_local.startswith(prefix) for prefix in EMAIL_ROLE_MISMATCH_PREFIXES)


def _contact_outreach_rank(contact: dict[str, Any]) -> tuple[int, int, int, float, str]:
    contact_type = _text(contact.get("contact_type"))
    if contact_type != "email":
        return 0, 0, 0, -float(contact.get("confidence") or 0), _text(contact.get("value"))
    value = _text(contact.get("value")).lower()
    local_part = value.split("@", 1)[0]
    if not _recipient_contact_eligible(contact):
        role_rank = 100
    elif local_part in {"info", "hello", "contact", "office", "admin", "marketing"}:
        role_rank = 0
    elif local_part.startswith(("info_", "info-", "contact_", "contact-")):
        role_rank = 1
    elif local_part.startswith(("sales", "client", "reception")):
        role_rank = 2
    else:
        role_rank = 3
    verification_rank = {
        "verified": 0,
        "confirmed_source": 1,
        "valid_format": 2,
        "accept_all": 3,
    }.get(_text(contact.get("verification_status")), 4)
    source_url = _text(contact.get("source_url"))
    try:
        source_host = (urlparse(source_url).hostname or "").lower().removeprefix("www.")
    except ValueError:
        source_host = ""
    source_rank = 0 if _text(contact.get("source_type")) == "official_website" else (
        1 if "maps" in source_host else 2
    )
    return role_rank, verification_rank, source_rank, -float(contact.get("confidence") or 0), value


def _normalize_outreach_fact(value: Any) -> str:
    fact = (
        _text(value)
        .replace("—", "-")
        .replace("«", '"')
        .replace("»", '"')
    )
    services_match = re.search(
        r"(?:в аудите публичной карточки )?найдено\s+(\d+)\s+услуг,\s+цена указана у\s+(\d+)",
        fact,
        flags=re.I,
    )
    if services_match:
        return (
            "По данным аудита карточки: всего услуг - "
            f"{services_match.group(1)}; с ценой - {services_match.group(2)}."
        )
    compact_services_match = re.search(
        r"(?:по данным аудита,\s*)?услуг в карточке\s*[—-]\s*(\d+),"
        r"\s*с указанной ценой\s*[—-]\s*(\d+)",
        fact,
        flags=re.I,
    )
    if compact_services_match:
        return (
            "По данным аудита карточки: всего услуг - "
            f"{compact_services_match.group(1)}; с ценой - "
            f"{compact_services_match.group(2)}."
        )
    current_services_match = re.search(
        r"(?:по данным аудита карточки:\s*)?всего услуг\s*[—-]\s*(\d+);"
        r"\s*с ценой\s*[—-]\s*(\d+)",
        fact,
        flags=re.I,
    )
    if current_services_match:
        return (
            "По данным аудита карточки: всего услуг - "
            f"{current_services_match.group(1)}; с ценой - {current_services_match.group(2)}."
        )
    rating_match = re.search(
        r"(?:в (?:публичной )?карточке )?указан рейтинг\s+([0-9]+(?:[.,][0-9]+)?)\s+при\s+(\d+)\s+отзывах",
        fact,
        flags=re.I,
    )
    if rating_match:
        rating = rating_match.group(1).replace(".", ",")
        return f"Рейтинг - {rating}; публичных отзывов - {rating_match.group(2)}."
    compact_rating_match = re.search(
        r"(?:в публичной карточке:\s*)?рейтинг\s*[—-]\s*([0-9]+(?:[.,][0-9]+)?)"
        r"\s*[,;]\s*(?:публичных\s+)?отзывов\s*[—-]\s*(\d+)",
        fact,
        flags=re.I,
    )
    if compact_rating_match:
        rating = compact_rating_match.group(1).replace(".", ",")
        return f"Рейтинг - {rating}; публичных отзывов - {compact_rating_match.group(2)}."
    return fact


def _outreach_bridge(evidence: dict[str, Any]) -> str:
    fact = _text(evidence.get("fact")).lower()
    kind = _text(evidence.get("kind"))
    if kind == "residential_context":
        return "Это позволяет обсудить предложение непосредственно для жителей комплекса"
    if (
        ("услуг в карточке" in fact and "указанной ценой" in fact)
        or ("всего услуг" in fact and "с ценой" in fact)
    ):
        return "Можно предметно проверить, для каких услуг клиент видит цену прямо в карточке"
    if "рейтинг -" in fact and "отзывов -" in fact:
        return "Можно предметно проверить, как карточка сейчас формирует доверие через рейтинг и отзывы"
    if "описание бизнеса не найдено" in fact:
        return "Можно проверить, понятно ли из карточки, чем занимается компания и что она предлагает"
    if kind == "service_compatibility":
        return "Это даёт конкретную основу для одного небольшого партнёрского теста без общих обещаний"
    if kind == "review":
        return "Это публичный клиентский сигнал, который нельзя превращать в вывод о внутренней работе без проверки"
    return _text(evidence.get("relevance")) or "Этот публичный факт можно проверить в коротком разборе"


def _signal_is_material(candidate: dict[str, Any]) -> bool:
    fact = _text(candidate.get("observed_fact")).lower()
    service_match = re.search(
        r"(?:услуг в карточке\s*[—-]\s*(\d+),\s*с указанной ценой"
        r"|всего услуг\s*[—-]\s*(\d+);\s*с ценой)\s*[—-]\s*(\d+)",
        fact,
    )
    if service_match:
        total = int(service_match.group(1) or service_match.group(2))
        priced = int(service_match.group(3))
        missing = max(0, total - priced)
        return total > 0 and missing >= 3 and (priced / total) <= 0.8
    rating_match = re.search(
        r"рейтинг\s*[—-]\s*([0-9]+(?:[.,][0-9]+)?);\s*публичных отзывов\s*[—-]\s*(\d+)",
        fact,
    )
    if rating_match:
        rating = float(rating_match.group(1).replace(",", "."))
        reviews = int(rating_match.group(2))
        return rating <= 4.2 or reviews <= 10
    return True


def _load_context(cursor: Any, workstream_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT ws.*, l.name AS lead_name, l.address, l.city, l.category,
               l.rating, l.reviews_count, l.website, l.source_url,
               l.phone, l.email, l.telegram_url, l.whatsapp_url,
               l.business_id AS lead_business_id,
               client.name AS client_business_name,
               client.business_type AS client_business_type,
               client.categories AS client_business_categories,
               client.description AS client_business_description,
               client.network_id AS client_business_network_id
        FROM lead_workstreams ws
        JOIN prospectingleads l ON l.id = ws.lead_id
        LEFT JOIN businesses client ON client.id = ws.client_business_id
        WHERE ws.id = %s
        """,
        (workstream_id,),
    )
    workstream = _dict(cursor.fetchone())
    if not workstream:
        raise LookupError("Lead workstream not found")
    cursor.execute(
        """
        SELECT * FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC LIMIT 1
        """,
        (workstream_id,),
    )
    workstream["research"] = _dict(cursor.fetchone())
    cursor.execute(
        """
        SELECT * FROM outreach_sender_profiles
        WHERE workstream_type = %s
          AND COALESCE(client_business_id, '') = COALESCE(%s, '')
          AND is_active = TRUE
        LIMIT 1
        """,
        (workstream.get("workstream_type"), workstream.get("client_business_id")),
    )
    workstream["sender_profile"] = _dict(cursor.fetchone())
    workstream["business_sender_profile"] = (
        dict(workstream["sender_profile"])
        if workstream.get("workstream_type") == "client_partnership"
        else {}
    )
    cursor.execute(
        """
        SELECT * FROM outreach_sender_profiles
        WHERE workstream_type = 'localos_sales'
          AND client_business_id IS NULL
          AND is_active = TRUE
        ORDER BY updated_at DESC
        LIMIT 1
        """
    )
    workstream["platform_sender_profile"] = _dict(cursor.fetchone())
    if workstream.get("workstream_type") == "client_partnership":
        cursor.execute(
            """
            SELECT COUNT(*) AS service_count
            FROM userservices
            WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
            """,
            (workstream.get("client_business_id"),),
        )
        service_row = cursor.fetchone()
        service_count = int(_scalar(service_row, "service_count") or 0)
        workstream["business_service_count"] = service_count
        workstream["sender_profile"]["_business_service_count"] = service_count
    cursor.execute(
        """
        SELECT * FROM lead_contact_points
        WHERE lead_id = %s AND verification_status NOT IN ('invalid', 'stale')
        ORDER BY confidence DESC, updated_at DESC
        """,
        (workstream.get("lead_id"),),
    )
    workstream["contacts"] = sorted(
        [_dict(row) for row in cursor.fetchall()],
        key=_contact_outreach_rank,
    )
    if workstream.get("workstream_type") == "client_partnership":
        cursor.execute(
            "SELECT match_json FROM partnershipleadartifacts WHERE lead_id = %s",
            (workstream.get("lead_id"),),
        )
        row = cursor.fetchone()
        workstream["partnership_match"] = (
            row.get("match_json") if row and hasattr(row, "get") else row[0] if row else {}
        ) or {}
    else:
        workstream["partnership_match"] = {}
    return workstream


def build_evidence_ledger(context: dict[str, Any]) -> list[dict[str, Any]]:
    research = context.get("research") or {}
    ledger: list[dict[str, Any]] = []
    research_evidence = _list(research.get("evidence_json"))
    source_items = research_evidence or _list(research.get("signals_json"))
    for index, signal in enumerate(source_items):
        if not isinstance(signal, dict):
            continue
        if signal.get("usable_for_outreach") is False:
            continue
        if _text(signal.get("freshness")) in {"stale", "unknown_dated_source"}:
            continue
        fact = _normalize_outreach_fact(
            signal.get("observed_fact") or signal.get("fact") or signal.get("text") or signal.get("title")
        )
        source_url = _text(signal.get("source_url") or signal.get("url") or research.get("opener_source_url"))
        if not fact or not source_url:
            continue
        ledger.append({
            "id": _text(signal.get("evidence_id") or signal.get("id")) or f"research-{index + 1}",
            "kind": _text(signal.get("kind") or "public_signal"),
            "fact": fact,
            "status": "observed",
            "source_url": source_url,
            "observed_at": signal.get("published_at") or signal.get("observed_at") or research.get("researched_at"),
            "freshness": _text(signal.get("freshness") or "unknown"),
            "confidence": float(signal.get("confidence") or 0.7),
            "hypothesis": _text(signal.get("hypothesis")) or None,
            "relevance": _text(signal.get("relevance") or signal.get("why_it_matters")) or None,
            "author_or_organization": _text(signal.get("author_or_organization")) or None,
            "source_type": _text(signal.get("source_type")) or None,
            "rejected_reason": None,
        })
    rating = context.get("rating")
    if rating is not None and float(rating) < 4.5 and context.get("source_url"):
        ledger.append({
            "id": "map-rating",
            "kind": "map_rating",
            "fact": (
                f"Рейтинг - {float(rating):.1f}; "
                f"публичных отзывов - {int(context.get('reviews_count') or 0)}."
            ).replace(".", ",", 1),
            "status": "observed",
            "source_url": context.get("source_url"),
            "observed_at": context.get("updated_at"),
            "freshness": "current_snapshot",
            "confidence": 0.95,
            "hypothesis": None,
            "relevance": "Есть конкретная точка для проверки карточки и работы с отзывами.",
        })
    match = context.get("partnership_match") or {}
    residential_recipient = _is_residential_recipient(context)
    if (
        context.get("workstream_type") == "client_partnership"
        and residential_recipient
        and context.get("source_url")
    ):
        lead_name = _text(context.get("lead_name")) or "жилого комплекса"
        ledger.append({
            "id": "residential-recipient-context",
            "kind": "residential_context",
            "fact": f'В публичной карточке {lead_name} указана категория "Жилой комплекс".',
            "status": "observed",
            "source_url": context.get("source_url"),
            "observed_at": context.get("updated_at"),
            "freshness": "current_snapshot",
            "confidence": 0.95,
            "hypothesis": None,
            "relevance": "Есть конкретный получатель и аудитория жителей для партнёрского предложения.",
        })
    match_fact = _normalize_outreach_fact(match.get("recipient_observation"))
    placeholder_residential_fact = residential_recipient and any(
        token in match_fact.lower()
        for token in (
            "общее описание без структуры",
            "нет цены или формата",
        )
    )
    if (
        context.get("workstream_type") == "client_partnership"
        and match_fact
        and not placeholder_residential_fact
        and float(match.get("match_score") or 0) >= 40
    ):
        ledger.append({
            "id": "partnership-compatibility",
            "kind": "service_compatibility",
            "fact": match_fact,
            "status": "observed",
            "source_url": context.get("source_url") or context.get("website"),
            "observed_at": context.get("updated_at"),
            "freshness": "current_snapshot",
            "confidence": min(1.0, float(match.get("match_score") or 70) / 100),
            "hypothesis": _text(match.get("compatibility_hypothesis")) or None,
            "relevance": _text(match.get("relevance_bridge"))
            or "Есть фактическое основание проверить один безопасный партнёрский тест.",
        })
    def evidence_priority(item: dict[str, Any]) -> tuple[int, float]:
        fact = _text(item.get("fact")).lower()
        kind = _text(item.get("kind"))
        if kind == "residential_context":
            rank = -1
        elif kind == "service_compatibility":
            rank = 0
        elif (
            "по данным аудита, услуг в карточке" in fact
            or "по данным аудита карточки: всего услуг" in fact
            or "описание бизнеса не найдено" in fact
        ):
            rank = 1
        elif "рейтинг -" in fact and "отзывов -" in fact:
            rank = 2
        elif kind == "review":
            rank = 9
        else:
            rank = 4
        return rank, -float(item.get("confidence") or 0)

    ledger.sort(key=evidence_priority)
    return ledger


def _founder_story(profile: dict[str, Any], evidence_text: str = "") -> dict[str, Any] | None:
    if not profile or not profile.get("confirmed_at"):
        return None
    outreach_context = (
        profile.get("outreach_context_json")
        if isinstance(profile.get("outreach_context_json"), dict)
        else {}
    )
    competence_status = _text(outreach_context.get("competence_story_status") or "approved")
    competence_story = (
        _text(profile.get("competence_story"))
        if competence_status in {"approved", "observed"}
        else ""
    )
    proofs = []
    for item in _list(profile.get("proof_points_json")) + _list(profile.get("verified_cases_json")):
        if isinstance(item, dict):
            if _text(item.get("status") or "approved").lower() not in {"approved", "observed"}:
                continue
            value = _text(item.get("fact") or item.get("text") or item.get("result") or item.get("title"))
        else:
            value = _text(item)
        if value:
            proofs.append(value)
    offers = []
    for item in _list(profile.get("allowed_offers_json")):
        if isinstance(item, dict):
            if _text(item.get("status") or "approved").lower() not in {"approved", "observed"}:
                continue
            value = _text(
                item.get("fact") or item.get("text") or item.get("result") or item.get("title")
            )
        else:
            value = _text(item)
        if value:
            offers.append(value)
    forbidden_claims = []
    for item in _list(profile.get("forbidden_claims_json")):
        if isinstance(item, dict):
            if _text(item.get("status") or "approved").lower() not in {"approved", "observed"}:
                continue
            value = _text(item.get("fact") or item.get("text") or item.get("claim"))
        else:
            value = _text(item)
        if value:
            forbidden_claims.append(value)
    if not competence_story and not proofs:
        return None
    def relevance_tokens(value: str) -> set[str]:
        return {
            token[:6] if len(token) > 6 else token
            for token in re.findall(r"[a-zа-яё0-9]+", value.lower())
            if len(token) >= 4
        }

    evidence_tokens = relevance_tokens(evidence_text)
    ranked_proofs = sorted(
        enumerate(proofs),
        key=lambda indexed: (
            -len(evidence_tokens.intersection(relevance_tokens(indexed[1]))),
            indexed[0],
        ),
    )
    ordered_proofs = [proof for _index, proof in ranked_proofs]
    story = competence_story or ordered_proofs[0]
    proof = ordered_proofs[0] if competence_story and ordered_proofs else None
    return {
        "sender": _text(profile.get("display_name")),
        "role": _text(profile.get("role_title")),
        "company": _text(profile.get("company_name")),
        "story": story,
        "proof": proof,
        "offer": offers[0] if offers else "",
        "forbidden_claims": forbidden_claims,
    }


def build_personalization_candidates(
    context: dict[str, Any],
    ledger: list[dict[str, Any]],
    *,
    selected_offer: dict[str, Any] | None = None,
    selected_trust: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    profile = context.get("sender_profile") or {}
    sender_mode = _text(context.get("sender_mode")) or SENDER_MODE_LOCALOS
    completeness = evaluate_sender_profile_completeness(
        profile,
        workstream_type=_text(context.get("workstream_type") or profile.get("workstream_type") or "localos_sales"),
        business_service_count=context.get("business_service_count") or profile.get("_business_service_count"),
    )
    story = _founder_story(profile) if completeness["ready"] else None
    if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER:
        story = None
    if not ledger or (sender_mode != SENDER_MODE_LOCALOS_FOR_PARTNER and not story):
        return []
    offer = selected_offer or {
        "text": story.get("offer") if story else "",
        "cta": story.get("offer") if story else "",
        "source": "approved_sender_profile",
    }
    trust = selected_trust or {
        "strategy": "founder_story",
        "statement": story.get("story") if story else "",
        "source": "approved_sender_profile",
    }
    next_step = _text(offer.get("cta") or offer.get("text"))
    trust_statement = _text(trust.get("statement"))
    if not next_step or not trust_statement:
        return []
    candidates = []
    lead_name = _text(context.get("lead_name"))
    recipient_type = (
        "residential_complex"
        if _is_residential_recipient(context)
        else "business"
    )
    for index, evidence in enumerate(ledger[:3]):
        relevant_story = None
        if story:
            relevant_story = _founder_story(
                context.get("sender_profile") or {},
                f"{evidence.get('fact') or ''} {evidence.get('relevance') or ''}",
            ) or story
        problem_hypothesis = _text(evidence.get("hypothesis")) or None
        relevance_to_offer = _outreach_bridge(evidence)
        candidates.append({
            "id": f"personalization-{index + 1}",
            "recipient": lead_name,
            "recipient_type": recipient_type,
            "evidence_id": evidence["id"],
            "evidence_ids": [evidence["id"]],
            "observed_fact": evidence["fact"],
            "problem_hypothesis": problem_hypothesis,
            "problem_hypothesis_status": "hypothesis" if problem_hypothesis else "missing",
            "relevance_to_offer": relevance_to_offer,
            "bridge": relevance_to_offer,
            "evidence_kind": evidence.get("kind"),
            "founder_story": relevant_story.get("story") if relevant_story else "",
            "founder_proof": relevant_story.get("proof") if relevant_story else "",
            "sender": (
                relevant_story.get("sender") if relevant_story
                else _text(profile.get("display_name"))
            ),
            "sender_role": (
                relevant_story.get("role") if relevant_story
                else _text(profile.get("role_title"))
            ),
            "sender_company": (
                relevant_story.get("company") if relevant_story
                else _text(profile.get("company_name"))
            ),
            "trust_strategy": trust.get("strategy"),
            "trust_statement": trust_statement,
            "trust_source": trust.get("source"),
            "offer_id": offer.get("id"),
            "offer_source": offer.get("source"),
            "next_step": next_step,
            "source_url": evidence.get("source_url"),
            "source_type": evidence.get("source_type"),
            "confidence": evidence.get("confidence"),
            "freshness": evidence.get("freshness"),
            "observed_at": evidence.get("observed_at"),
            "evidence_status": evidence.get("status"),
            "limitations": ["public_evidence_only"] if evidence.get("confidence", 0) < 0.8 else [],
            "sender_mode": sender_mode,
            "represented_business": context.get("represented_business_name"),
            "representation_disclosure": "",
            "represented_business_opening": (
                _represented_business_opening(context)
                if context.get("sender_mode") == SENDER_MODE_LOCALOS_FOR_PARTNER
                else ""
            ),
        })
    return candidates


def _strategy_dimensions(
    context: dict[str, Any],
    research_brief: dict[str, Any],
    candidate: dict[str, Any],
    story: dict[str, Any],
    *,
    channel: str,
    sequence_index: int,
    day_offset: int,
    angle: str,
) -> dict[str, Any]:
    """Describe the complete, reusable outreach hypothesis for one touch.

    Recipient evidence remains addressable through ``evidence_id`` while the
    aggregate dimension stores the semantic signal kind. This prevents two
    otherwise identical map-rating strategies from being split merely because
    their evidence rows have different identifiers.
    """
    return {
        "workstream_type": context.get("workstream_type"),
        "sender_mode": context.get("sender_mode"),
        "represented_business_id": context.get("represented_business_id"),
        "segment": research_brief.get("segment") or context.get("category"),
        "recipient_role": research_brief.get("buyer_persona"),
        "signal_kind": candidate.get("evidence_kind") or "public_signal",
        "evidence_id": candidate.get("evidence_id"),
        "freshness": candidate.get("freshness"),
        "founder_story_id": str(context.get("sender_profile", {}).get("id") or ""),
        "founder_story": candidate.get("founder_story") or story.get("story"),
        "founder_proof": candidate.get("founder_proof") or story.get("proof"),
        "trust_strategy": candidate.get("trust_strategy"),
        "trust_statement": candidate.get("trust_statement"),
        "bridge_type": candidate.get("relevance_to_offer") or candidate.get("bridge"),
        "offer_id": candidate.get("offer_id"),
        "offer": (
            candidate.get("next_step")
            if candidate.get("offer_id")
            else story.get("offer") or candidate.get("next_step")
        ),
        "cta": candidate.get("next_step"),
        "channel": channel,
        "sequence_index": sequence_index,
        "day_offset": day_offset,
        "angle": angle,
    }


def channel_availability(cursor: Any, context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    contacts_by_type: dict[str, dict[str, Any]] = {}
    for contact in context.get("contacts") or []:
        if not _recipient_contact_eligible(contact):
            continue
        contacts_by_type.setdefault(str(contact.get("contact_type") or ""), contact)
    scope_type = (
        "platform"
        if context.get("sender_mode") in {SENDER_MODE_LOCALOS, SENDER_MODE_LOCALOS_FOR_PARTNER}
        else "business"
    )
    business_id = None if scope_type == "platform" else context.get("client_business_id")
    cursor.execute(
        """
        SELECT s.id, s.channel, s.status, s.external_account_id,
               s.sender_identity, s.display_name,
               s.health_status, s.capabilities_json,
               s.outreach_enabled AS sender_outreach_enabled,
               p.outreach_enabled AS telegram_outreach_enabled
        FROM outreach_sender_accounts s
        LEFT JOIN telegram_account_permissions p ON p.account_id = s.external_account_id
        WHERE s.scope_type = %s
          AND COALESCE(s.business_id, '') = COALESCE(%s, '')
          AND s.status = 'connected'
        ORDER BY s.channel, s.updated_at DESC
        """,
        (scope_type, business_id),
    )
    senders_by_channel: dict[str, list[dict[str, Any]]] = {}
    for row in cursor.fetchall():
        sender_row = _dict(row)
        senders_by_channel.setdefault(str(sender_row.get("channel")), []).append(sender_row)
    result: dict[str, dict[str, Any]] = {}
    for channel in ("telegram", "email", "whatsapp", "max", "vk", "sms", "manual"):
        contact = contacts_by_type.get(channel)
        if channel == "email" and not contact and context.get("email"):
            fallback = {
                "id": None,
                "contact_type": "email",
                "value": context.get("email"),
                "source_url": context.get("source_url"),
            }
            contact = fallback if _recipient_contact_eligible(fallback) else None
        if channel == "telegram" and not contact and context.get("telegram_url"):
            contact = {"id": None, "value": context.get("telegram_url")}
        if channel == "whatsapp" and not contact and context.get("whatsapp_url"):
            contact = {"id": None, "value": context.get("whatsapp_url")}
        if channel == "sms" and not contact:
            contact = contacts_by_type.get("phone")
        senders = senders_by_channel.get(channel) or []
        sender = senders[0] if len(senders) == 1 else None

        def sender_status(sender_item: dict[str, Any] | None) -> str:
            capabilities = sender_item.get("capabilities_json") if sender_item else {}
            if not isinstance(capabilities, dict):
                capabilities = {}
            if not sender_item:
                return "connect_required"
            if sender_item.get("health_status") in {"paused", "blocked"}:
                return "sender_paused"
            if sender_item.get("health_status") == "degraded":
                return "sender_degraded"
            if channel == "telegram" and not sender_item.get("telegram_outreach_enabled"):
                return "permission_required"
            if channel in {"email", "vk"} and not sender_item.get("sender_outreach_enabled"):
                return "permission_required"
            if channel in AUTOMATIC_CHANNELS and (
                not capabilities.get("direct_send") or not capabilities.get("reply_sync")
            ):
                return "adapter_unavailable"
            return "ready"

        sender_options = [{
            "id": str(item.get("id") or ""),
            "sender_identity": item.get("sender_identity"),
            "display_name": item.get("display_name"),
            "health_status": item.get("health_status"),
            "status": sender_status(item),
        } for item in senders]
        if not contact:
            status = "recipient_missing"
        elif channel in MANUAL_CHANNELS:
            status = "manual"
        elif len(senders) > 1:
            status = "sender_selection_required"
        else:
            status = sender_status(sender)
        result[channel] = {
            "status": status,
            "contact_point_id": str(contact.get("id")) if contact and contact.get("id") else None,
            "recipient": _text(contact.get("value")) if contact else None,
            "sender_account_id": str(sender.get("id")) if sender and sender.get("id") else None,
            "sender_health": sender.get("health_status") if sender else None,
            "sender_accounts": sender_options,
        }
    return result


def _suppression_status(cursor: Any, context: dict[str, Any]) -> dict[str, Any]:
    scope_type = "platform" if context.get("workstream_type") == "localos_sales" else "business"
    business_id = None if scope_type == "platform" else context.get("client_business_id")
    cursor.execute(
        """
        SELECT reason_code, scope_type, expires_at
        FROM outreach_suppressions
        WHERE (expires_at IS NULL OR expires_at > NOW())
          AND (lead_id = %s OR NULLIF(recipient_key, '') = %s)
          AND (
              scope_type = 'platform_safety'
              OR (scope_type = %s AND COALESCE(business_id, '') = COALESCE(%s, ''))
          )
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (context.get("lead_id"), recipient_key(str(context.get("lead_id") or "")), scope_type, business_id),
    )
    row = _dict(cursor.fetchone())
    return {
        "suppressed": bool(row),
        "reason_code": row.get("reason_code"),
        "scope_type": row.get("scope_type"),
        "expires_at": row.get("expires_at"),
    }


def _quality_gate(
    text: str,
    candidate: dict[str, Any],
    story: dict[str, Any] | None,
    *,
    channel: str,
    channel_status: str,
    suppressed: bool,
    angle: str | None = None,
) -> dict[str, Any]:
    question_count = text.count("?")
    word_count = len(re.findall(r"\b[\wа-яА-ЯёЁ0-9-]+\b", text, flags=re.UNICODE))
    channel_word_limit = 120 if channel == "email" else 60 if channel == "sms" else 90
    normalized_text = text.lower()

    def contains(value: Any) -> bool:
        normalized = _text(value).lower()
        return bool(normalized) and normalized in normalized_text

    personalization_anchors = (
        candidate.get("observed_fact"),
        candidate.get("bridge"),
        candidate.get("founder_story"),
        candidate.get("founder_proof"),
        candidate.get("trust_statement"),
    )
    proof_context = story or {}
    respectful_close = _text(angle) == "respectful_close"
    banned_machine_phrases = (
        "есть конкретный элемент карточки",
        "подтверждённый контекст",
        "отзыв даёт проверяемую тему",
        "без приписывания бизнесу скрытой проблемы",
    )
    checks = {
        "removal": contains(candidate.get("recipient")) and (
            any(contains(anchor) for anchor in personalization_anchors)
            or respectful_close
        ),
        "bridge": any(contains(anchor) for anchor in personalization_anchors[1:]),
        "fact": bool(candidate.get("source_url") and candidate.get("evidence_status") in {"approved", "observed"}),
        "freshness": _text(candidate.get("freshness")).lower() not in {
            "",
            "stale",
            "unknown_dated_source",
        },
        "specificity": bool(
            contains(candidate.get("recipient"))
            and (respectful_close or len(_text(candidate.get("observed_fact"))) >= 20)
        ),
        "proof_integrity": bool(story or candidate.get("trust_statement")) and not any(
            claim.lower() in text.lower() for claim in proof_context.get("forbidden_claims", [])
        ),
        "channel_fit": channel in SUPPORTED_CHANNELS and word_count <= channel_word_limit,
        "single_cta": question_count == 1 and bool(_text(candidate.get("next_step"))),
        "suppression_safety": not suppressed,
        "human_tone": not any(phrase in normalized_text for phrase in banned_machine_phrases),
        "sensitive_review": candidate.get("evidence_kind") != "review",
        "signal_strength": _signal_is_material(candidate),
        "style_contract": not any(mark in text for mark in ("—", "«", "»")),
    }
    criterion_scores = _quality_criterion_scores(checks)
    score = sum(criterion_scores.values())
    blocking_reasons = []
    if not checks["fact"]:
        blocking_reasons.append("unverified_or_unsourced_fact")
    if not checks["proof_integrity"]:
        blocking_reasons.append("proof_integrity_failed")
    if not checks["suppression_safety"]:
        blocking_reasons.append("recipient_suppressed")
    if not checks["removal"]:
        blocking_reasons.append("decorative_personalization")
    if not checks["human_tone"]:
        blocking_reasons.append("machine_language_detected")
    if not checks["sensitive_review"]:
        blocking_reasons.append("sensitive_review_requires_manual_rewrite")
    if not checks["signal_strength"]:
        blocking_reasons.append("signal_too_weak_for_cold_outreach")
    if not checks["style_contract"]:
        blocking_reasons.append("style_contract_violation")
    canonical_reason_map = {
        "unverified_or_unsourced_fact": "SOURCE_MISSING",
        "proof_integrity_failed": "UNSUPPORTED_PROOF",
        "recipient_suppressed": "SUPPRESSED_CONTACT",
        "decorative_personalization": "DECORATIVE_PERSONALIZATION",
        "machine_language_detected": "STYLE_VIOLATION",
        "sensitive_review_requires_manual_rewrite": "SENSITIVE_TARGETING",
        "signal_too_weak_for_cold_outreach": "DECORATIVE_PERSONALIZATION",
        "style_contract_violation": "STYLE_VIOLATION",
    }
    diagnostic_reason_map = {
        "fact": "SOURCE_MISSING",
        "freshness": "STALE_AS_CURRENT",
        "bridge": "WEAK_OFFER_BRIDGE",
        "removal": "DECORATIVE_PERSONALIZATION",
        "specificity": "DECORATIVE_PERSONALIZATION",
        "proof_integrity": "UNSUPPORTED_PROOF",
        "channel_fit": "CHANNEL_LIMIT_EXCEEDED",
        "single_cta": "MULTIPLE_CTA",
        "suppression_safety": "SUPPRESSED_CONTACT",
        "human_tone": "STYLE_VIOLATION",
        "sensitive_review": "SENSITIVE_TARGETING",
        "signal_strength": "DECORATIVE_PERSONALIZATION",
        "style_contract": "STYLE_VIOLATION",
    }
    diagnostic_codes = [key for key, passed in checks.items() if not passed]
    reason_codes = list(dict.fromkeys(
        [
            diagnostic_reason_map[key]
            for key in diagnostic_codes
            if key in diagnostic_reason_map
        ]
        + [
            canonical_reason_map[reason]
            for reason in blocking_reasons
            if reason in canonical_reason_map
        ]
    ))
    return {
        "score": score,
        "total_score": score,
        "max_score": 18,
        "verdict": (
            "reject" if blocking_reasons
            else "approve" if score >= 15 and not reason_codes
            else "revise"
        ),
        "passed": score >= 15 and not blocking_reasons and not reason_codes,
        "criterion_scores": criterion_scores,
        "checks": checks,
        "diagnostic_codes": diagnostic_codes,
        "reason_codes": reason_codes,
        "blocking_reasons": blocking_reasons,
        "canonical_reason_codes": reason_codes,
        "word_count": word_count,
        "word_limit": channel_word_limit,
    }


def _message_for_angle(
    angle: str,
    candidate: dict[str, Any],
    story: dict[str, Any] | None,
    previous_angles: list[str],
) -> str:
    name = candidate["recipient"]
    sender = _text(candidate.get("sender"))
    sender_role = _text(candidate.get("sender_role"))
    sender_company = _text(candidate.get("sender_company"))
    introduction = f"Я {sender}" if sender else ""
    if sender_role and sender_company:
        if sender_company.lower() in sender_role.lower():
            introduction += f", {sender_role}. "
        else:
            introduction += f", {sender_role} в {sender_company}. "
    elif sender_role:
        introduction += f", {sender_role}. "
    elif sender_company:
        introduction += f" из {sender_company}. "
    elif introduction:
        introduction += ". "
    next_step = _text(candidate.get("next_step")).rstrip(".?!")
    observed_fact = _text(candidate.get("observed_fact")).rstrip(". ")
    observed_fact_inline = observed_fact[0].lower() + observed_fact[1:] if observed_fact else ""
    bridge = _text(candidate.get("bridge")).rstrip(". ")
    founder_story = _text(candidate.get("founder_story")).rstrip(". ")
    founder_proof = _text(candidate.get("founder_proof") or founder_story).rstrip(". ")
    trust_statement = _text(candidate.get("trust_statement")).rstrip(". ")
    sender_mode = _text(candidate.get("sender_mode"))
    representation = _text(candidate.get("representation_disclosure"))
    represented_business_opening = _text(candidate.get("represented_business_opening"))
    representation_block = f"{representation} " if representation else ""
    residential_recipient = _text(candidate.get("recipient_type")) == "residential_complex"
    if residential_recipient:
        if represented_business_opening:
            company_opening = represented_business_opening
        elif sender_company:
            company_opening = f"Мы ваши соседи - {sender_company}."
        else:
            company_opening = introduction.strip()
        greeting = "Здравствуйте!"
        opening = f"{greeting}\n\n{company_opening}\n\n" if company_opening else f"{greeting}\n\n"
        invitation = "Хотели бы пригласить ваших жителей к нам."
        terms = "Конкретный формат и условия предложим отдельно с учётом правил комплекса."
        if angle == "signal":
            return (
                opening
                + f"{invitation}\n\n{observed_fact}. {bridge}.\n\n"
                + f"{terms} Подскажите, с кем можно это обсудить?"
            )
        if angle in {"founder_story", "business_reputation", "matching_authority"}:
            trust_or_story = trust_statement or founder_story
            trust_block = f"{trust_or_story}. " if trust_or_story else ""
            return (
                opening
                + f"{trust_block}{invitation} {observed_fact}. {bridge}.\n\n"
                + f"{terms} Можно обсудить подходящий формат для жителей?"
            )
        if angle == "proof":
            proof = founder_proof or trust_statement
            proof_block = f"{proof}. " if proof else ""
            return (
                opening
                + f"{proof_block}{invitation} {observed_fact}. {bridge}.\n\n"
                + f"{terms} Прислать один вариант предложения для жителей?"
            )
        return (
            opening
            + f"Коротко закроем тему по {name}. {invitation} {bridge}. "
            + "Если сейчас неактуально, больше писать не будем. Вернуться к этому позже?"
        )
    if angle == "signal":
        if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER:
            return (
                f"Здравствуйте!\n\n{represented_business_opening}\n\n"
                f'Обратили внимание на "{name}": {observed_fact_inline}. {bridge}.\n\n'
                "Мы собрали несколько простых идей для небольшого совместного пилота. Прислать?"
            )
        if sender_mode == SENDER_MODE_PARTNER_BUSINESS:
            return f'Здравствуйте! {introduction}{representation_block}Обратил внимание на "{name}": {observed_fact_inline}. {bridge}. {next_step} - обсудим?'
        return f'Здравствуйте! {introduction}{representation_block}Посмотрел публичную карточку "{name}". {observed_fact}. {bridge}. Могу прислать {next_step.lower()} - посмотреть?'
    if angle in {"founder_story", "business_reputation", "matching_authority"}:
        if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER:
            opening = "Здравствуйте!\n\n"
            if represented_business_opening:
                opening += f"{represented_business_opening}\n\n"
            return opening + (
                f'Пишем по поводу возможного знакомства с "{name}". {trust_statement}.\n\n'
                f"Основание для знакомства - {observed_fact_inline}.\n\n"
                f"{next_step} - обсудим?"
            )
        opening = f"Здравствуйте! {introduction.rstrip()}\n\n"
        if representation:
            opening += f"{representation}\n\n"
        trust_or_story = trust_statement if angle == "business_reputation" else founder_story or trust_statement
        return opening + (
            f'Пишу по поводу карточки "{name}". {trust_or_story}.\n\n'
            f"Конкретный повод - {observed_fact_inline}.\n\n"
            f"{next_step} - будет полезно?"
        )
    if angle == "proof":
        proof = founder_proof or trust_statement
        company_identity = f"{represented_business_opening} " if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER else ""
        verb = "дополним" if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER else "дополню"
        return f'Здравствуйте! {company_identity}Коротко {verb} по "{name}". {proof}. {next_step} - прислать детали?'
    if sender_mode == SENDER_MODE_LOCALOS_FOR_PARTNER:
        return f'Здравствуйте! {represented_business_opening} Коротко закроем тему по "{name}". {bridge}. Если сейчас неактуально, больше писать не будем. Вернуться позже?'
    return f'Здравствуйте! {representation_block}Коротко закрою тему по "{name}". {bridge}. Если сейчас неактуально, больше не напомню. Вернуться позже?'


def _email_subject(angle: str, candidate: dict[str, Any]) -> str:
    labels = {
        "signal": "короткий вопрос по публичному сигналу",
        "founder_story": "вопрос по публичной карточке",
        "business_reputation": "идея для знакомства компаний",
        "matching_authority": "основание для знакомства компаний",
        "proof": "пример, который может быть полезен",
        "respectful_close": "закрою тему",
    }
    recipient = _text(candidate.get("recipient"))[:100]
    return f"{recipient} - {labels.get(angle, 'короткий вопрос')}"[:200]


def build_preview(
    cursor: Any,
    workstream_id: str,
    *,
    sequence: list[dict[str, Any]] | None = None,
    start_at: datetime | None = None,
    sender_mode: str | None = None,
    offer_id: str | None = None,
    trust_strategy: str | None = None,
    generate_ai: bool | None = None,
) -> dict[str, Any]:
    context = _apply_sender_mode(_load_context(cursor, workstream_id), sender_mode)
    ledger = build_evidence_ledger(context)
    profile_completeness = evaluate_sender_profile_completeness(
        context.get("sender_profile") or {},
        workstream_type=_text(context.get("workstream_type") or "localos_sales"),
        business_service_count=context.get("business_service_count"),
    )
    profile_ready = bool(profile_completeness["ready"])
    if context.get("sender_mode") == SENDER_MODE_LOCALOS_FOR_PARTNER:
        platform_profile = context.get("platform_sender_profile") or {}
        profile_ready = bool(platform_profile.get("confirmed_at"))
    story = (
        _founder_story(context.get("sender_profile") or {})
        if profile_ready and context.get("sender_mode") != SENDER_MODE_LOCALOS_FOR_PARTNER
        else None
    )
    availability = channel_availability(cursor, context)
    suppression = _suppression_status(cursor, context)
    decision = build_outreach_decision(
        context,
        ledger,
        availability,
        suppression,
        sender_mode=_text(context.get("sender_mode")),
        profile_ready=profile_ready,
    )
    offers = offer_candidates(context, _text(context.get("sender_mode")))
    trusts = trust_candidates(context, _text(context.get("sender_mode")))
    selected_offer = select_offer(offers, offer_id)
    selected_trust = select_trust(trusts, trust_strategy)
    candidates = build_personalization_candidates(
        context,
        ledger,
        selected_offer=selected_offer,
        selected_trust=selected_trust,
    )
    base_payload = {
        "workstream_id": workstream_id,
        "lead_id": str(context.get("lead_id")),
        "lead": {
            "name": context.get("lead_name"),
            "city": context.get("city"),
            "category": context.get("category"),
            "source_url": context.get("source_url"),
        },
        "sender_mode": context.get("sender_mode"),
        "represented_business_id": context.get("represented_business_id"),
        "represented_business_name": context.get("represented_business_name"),
        "decision": decision,
        "offers": offers,
        "trust_strategies": trusts,
        "selected_offer": selected_offer,
        "selected_trust": selected_trust,
        "evidence": ledger,
        "personalization_candidates": candidates,
        "channel_availability": availability,
    }
    if decision["action"] == "excluded":
        return {
            **base_payload,
            "status": "suppressed" if suppression["suppressed"] else "excluded",
            "suppression": suppression,
            "touches": [],
        }
    if decision["action"] != "write_now" or not candidates:
        missing = []
        if not profile_ready:
            missing.extend(
                item["code"] for item in profile_completeness["missing_items"]
            )
            if not profile_completeness["missing_items"]:
                missing.append("approved_sender_profile")
        if not ledger:
            missing.append("recipient_evidence")
        if not selected_offer:
            missing.append("approved_offer")
        if not selected_trust:
            missing.append("trust_strategy")
        return {
            **base_payload,
            "status": decision["action"],
            "missing": missing,
            "sender_profile_completeness": profile_completeness,
            "touches": [],
        }
    selected_sequence = sequence or [
        {"channel": channel, "day_offset": day, "angle": angle}
        for channel, day, angle in DEFAULT_SEQUENCE
    ]
    if sequence is None and context.get("sender_mode") == SENDER_MODE_PARTNER_BUSINESS:
        selected_sequence[1]["angle"] = "business_reputation"
    if sequence is None and context.get("sender_mode") == SENDER_MODE_LOCALOS_FOR_PARTNER:
        selected_sequence[1]["angle"] = "matching_authority"
    if context.get("sender_mode") == SENDER_MODE_PARTNER_BUSINESS:
        selected_sequence = [
            {
                **item,
                "angle": "business_reputation"
                if _text(item.get("angle")) == "founder_story"
                else _text(item.get("angle")),
            }
            for item in selected_sequence
        ]
    if context.get("sender_mode") == SENDER_MODE_LOCALOS_FOR_PARTNER:
        selected_sequence = [
            {
                **item,
                "angle": "matching_authority"
                if _text(item.get("angle")) == "founder_story"
                else _text(item.get("angle")),
            }
            for item in selected_sequence
        ]
    usable = [channel for channel, item in availability.items() if item["status"] in {"ready", "manual"}]
    touches = []
    previous_angles: list[str] = []
    sequence_issues: list[str] = []
    start = start_at or datetime.now(timezone.utc)
    previous_offset: int | None = None
    research_brief = (context.get("research") or {}).get("message_brief_json") or {}
    if not isinstance(research_brief, dict):
        research_brief = {}
    selected_candidate_id = _text(
        (context.get("research") or {}).get("selected_personalization_id")
    )
    primary_candidate = next(
        (candidate for candidate in candidates if candidate.get("id") == selected_candidate_id),
        candidates[0],
    )
    for index, item in enumerate(selected_sequence):
        requested_channel = _text(item.get("channel")).lower()
        if requested_channel == "next":
            requested_channel = next((channel for channel in usable if channel not in [touch["channel"] for touch in touches]), "")
        if not requested_channel or requested_channel not in SUPPORTED_CHANNELS:
            continue
        angle = _text(item.get("angle") or "proof")
        day_offset = max(0, int(item.get("day_offset") or 0))
        if angle in previous_angles:
            sequence_issues.append(f"duplicate_angle:{angle}")
        if previous_offset is not None and day_offset <= previous_offset:
            sequence_issues.append(f"unsafe_interval:{previous_offset}:{day_offset}")
        # A sequence changes the angle, not the underlying public fact. Introducing a
        # new signal in a follow-up (especially a negative review) requires a separate
        # explicit personalization selection and a new approval version.
        candidate = primary_candidate
        message = _message_for_angle(angle, candidate, story, previous_angles)
        availability_item = dict(availability[requested_channel])
        requested_sender_id = _text(item.get("sender_account_id"))
        if requested_channel in AUTOMATIC_CHANNELS and requested_sender_id:
            sender_option = next(
                (
                    option for option in availability_item.get("sender_accounts") or []
                    if _text(option.get("id")) == requested_sender_id
                ),
                None,
            )
            if sender_option:
                availability_item["status"] = sender_option.get("status")
                availability_item["sender_account_id"] = requested_sender_id
                availability_item["sender_health"] = sender_option.get("health_status")
            else:
                availability_item["status"] = "sender_selection_required"
                availability_item["sender_account_id"] = None
        gate = _quality_gate(
            message,
            candidate,
            story,
            channel=requested_channel,
            channel_status=availability_item["status"],
            suppressed=suppression["suppressed"],
            angle=angle,
        )
        strategy = _strategy_dimensions(
            context,
            research_brief,
            candidate,
            story or {},
            channel=requested_channel,
            sequence_index=len(touches),
            day_offset=day_offset,
            angle=angle,
        )
        touches.append({
            "sequence_index": len(touches),
            "channel": requested_channel,
            "day_offset": day_offset,
            "scheduled_at": start + timedelta(days=day_offset),
            "angle": angle,
            "subject": (
                _text(item.get("subject"))[:200]
                if requested_channel == "email" and _text(item.get("subject"))
                else _email_subject(angle, candidate) if requested_channel == "email" else None
            ),
            "text": message,
            "quality_gate": gate,
            "channel_status": availability_item["status"],
            "contact_point_id": availability_item.get("contact_point_id"),
            "sender_account_id": availability_item.get("sender_account_id"),
            "evidence_id": candidate["evidence_id"],
            "source_url": candidate["source_url"],
            "observation": candidate.get("observed_fact"),
            "problem_hypothesis": candidate.get("problem_hypothesis"),
            "relevance_bridge": candidate.get("relevance_to_offer") or candidate.get("bridge"),
            "strategy": strategy,
            "strategy_fingerprint": strategy_fingerprint(strategy),
        })
        previous_angles.append(angle)
        previous_offset = day_offset
    ai_enabled = ai_personalization_enabled() if generate_ai is None else bool(generate_ai)
    generation: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "disabled",
        "source": "deterministic",
        "prompt_version": None,
        "review_prompt_version": None,
        "error_code": None,
        "error": None,
    }
    semantic_failed = False
    if ai_enabled and touches:
        sender_profile = context.get("sender_profile") or {}
        generation_story = story or {
            "sender": _text(sender_profile.get("display_name")),
            "role": _text(sender_profile.get("role_title")),
            "company": _text(sender_profile.get("company_name")),
            "story": _text(selected_trust.get("statement")),
            "proof": "",
            "offer": _text(selected_offer.get("text")),
            "forbidden_claims": [],
        }

        def voice_example_text(item: Any) -> str:
            if isinstance(item, dict):
                return _text(item.get("text") or item.get("message") or item.get("example"))
            return _text(item)

        voice_examples = [
            voice_example_text(item)
            for item in _list(sender_profile.get("voice_examples_json"))
            if voice_example_text(item)
        ]
        generation = generate_personalized_sequence(
            motion=_text(context.get("workstream_type")),
            identity={
                "company_name": _text(context.get("lead_name")),
                "contact_name": _text(primary_candidate.get("contact_name")),
                "contact_role": _text(primary_candidate.get("contact_role")),
            },
            candidate=primary_candidate,
            founder_story=generation_story,
            sequence=touches,
            voice_examples=voice_examples,
            business_id=_text(context.get("client_business_id")),
            user_id=_text(sender_profile.get("created_by")),
        )
        if generation.get("status") == "ready":
            generated_by_index = {
                int(item["sequence_index"]): item
                for item in generation.get("touches") or []
            }
            review_by_index = {
                int(item["sequence_index"]): item
                for item in generation.get("semantic_reviews") or []
            }
            for touch in touches:
                index = int(touch["sequence_index"])
                generated_touch = generated_by_index[index]
                semantic_review = review_by_index[index]
                touch["text"] = generated_touch["text"]
                if touch["channel"] == "email":
                    touch["subject"] = generated_touch.get("subject") or touch.get("subject")
                touch["problem_hypothesis"] = generated_touch.get("problem_hypothesis")
                touch["relevance_bridge"] = generated_touch.get("relevance_bridge")
                touch["generation_source"] = generation.get("source")
                touch["generation_prompt_version"] = generation.get("prompt_version")
                touch["semantic_review_prompt_version"] = generation.get("review_prompt_version")
                gate = _quality_gate(
                    touch["text"],
                    primary_candidate,
                    story,
                    channel=touch["channel"],
                    channel_status=touch["channel_status"],
                    suppressed=suppression["suppressed"],
                    angle=touch["angle"],
                )
                gate = _merge_semantic_quality(gate, semantic_review)
                if not semantic_review.get("passed"):
                    semantic_failed = True
                    gate["blocking_reasons"] = list(dict.fromkeys(
                        list(gate.get("blocking_reasons") or []) + ["semantic_review_failed"]
                    ))
                touch["quality_gate"] = gate
        else:
            for touch in touches:
                gate = dict(touch.get("quality_gate") or {})
                gate["passed"] = False
                gate["verdict"] = "revise"
                gate["blocking_reasons"] = list(dict.fromkeys(
                    list(gate.get("blocking_reasons") or []) + ["ai_generation_failed"]
                ))
                reason_codes = list(dict.fromkeys(
                    list(gate.get("reason_codes") or []) + ["STYLE_VIOLATION"]
                ))
                gate["reason_codes"] = reason_codes
                gate["canonical_reason_codes"] = reason_codes
                touch["quality_gate"] = gate
    missing = sorted({
        f"{touch['channel']}:{touch['channel_status']}"
        for touch in touches
        if touch["channel_status"] not in {"ready", "manual"}
    })
    content_ready = bool(touches) and all(touch["quality_gate"]["passed"] for touch in touches)
    if sequence_issues:
        preview_status = "invalid_sequence"
    elif ai_enabled and generation.get("status") != "ready":
        preview_status = "needs_generation"
    elif semantic_failed:
        preview_status = "needs_revision"
    elif not content_ready:
        preview_status = "needs_evidence"
    elif missing:
        preview_status = "needs_channel_setup"
    else:
        preview_status = "ready"
    quality_gate = _aggregate_quality_gate(touches)
    risks = list(sequence_issues) + list(missing) + list(quality_gate.get("reason_codes") or [])
    review_record = _review_record(
        context,
        ledger=ledger,
        candidates=candidates,
        selected_candidate_id=_text(primary_candidate.get("id")),
        touches=touches,
        quality_gate=quality_gate,
        risks=risks,
        generated_at=start,
    )
    return {
        "status": preview_status,
        "workstream_id": workstream_id,
        "lead_id": str(context.get("lead_id")),
        "lead": base_payload["lead"],
        "scope_type": "platform" if context.get("workstream_type") == "localos_sales" else "business",
        "business_id": context.get("client_business_id"),
        "sender_mode": context.get("sender_mode"),
        "decision": decision,
        "offers": offers,
        "trust_strategies": trusts,
        "selected_offer": selected_offer,
        "selected_trust": selected_trust,
        "sender_scope_type": (
            "platform"
            if context.get("sender_mode") in {SENDER_MODE_LOCALOS, SENDER_MODE_LOCALOS_FOR_PARTNER}
            else "business"
        ),
        "represented_business_id": context.get("represented_business_id"),
        "represented_business_name": context.get("represented_business_name"),
        "represented_sender_profile_id": (
            str((context.get("business_sender_profile") or {}).get("id") or "") or None
        ),
        "sender_profile_id": str(context["sender_profile"].get("id")),
        "evidence": ledger,
        "personalization_candidates": candidates,
        "channel_availability": availability,
        "suppression": suppression,
        "touches": touches,
        "quality_gate": quality_gate,
        "review_record": review_record,
        "generation": generation,
        "sequence_issues": sequence_issues,
        "missing": missing,
    }


def persist_preview(cursor: Any, preview: dict[str, Any], *, user_id: str) -> dict[str, Any]:
    if preview.get("status") not in {"ready", "needs_channel_setup"} or not preview.get("touches"):
        raise ValueError("needs_evidence")
    workstream_id = str(preview["workstream_id"])
    cursor.execute("SELECT COALESCE(MAX(version), 0) + 1 AS next_version FROM outreach_campaigns WHERE workstream_id = %s", (workstream_id,))
    version = int(_scalar(cursor.fetchone(), "next_version"))
    campaign_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreach_campaigns (
            id, workstream_id, lead_id, scope_type, business_id, sender_profile_id,
            version, status, sender_mode, selected_offer_json, trust_strategy,
            decision_snapshot_json, policy_json, recipient_key, created_by, created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s, NULLIF(%s, ''),
            %s, %s, %s, %s, NOW(), NOW()
        )
        """,
        (
            campaign_id, workstream_id, preview["lead_id"], preview["scope_type"],
            preview.get("business_id"), preview.get("sender_profile_id"), version,
            preview.get("sender_mode"), Json(preview.get("selected_offer") or {}),
            preview.get("selected_trust", {}).get("strategy") or "",
            Json(_json_safe(preview.get("decision") or {})),
            Json({
                "stop_on_reply": True,
                "daily_limit": 10,
                "minimum_cadence_hours": 24,
                "manual_timeout_hours": 48,
                "manual_timeout_action": "needs_attention",
                "no_reply_grace_hours": 168,
                "approval_scope": "whole_sequence",
                "sender_mode": preview.get("sender_mode"),
                "sender_scope_type": preview.get("sender_scope_type"),
                "represented_business_id": preview.get("represented_business_id"),
                "represented_business_name": preview.get("represented_business_name"),
                "represented_sender_profile_id": preview.get("represented_sender_profile_id"),
            }),
            recipient_key(str(preview["lead_id"])), user_id,
        ),
    )
    for touch in preview["touches"]:
        cursor.execute(
            """
            INSERT INTO outreach_campaign_touches (
                id, campaign_id, sequence_index, channel, contact_point_id,
                sender_account_id, angle_type, scheduled_at, status,
                subject, generated_text, message_brief_json, quality_gate_json,
                strategy_fingerprint, strategy_json,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, NULLIF(%s, '')::uuid, NULLIF(%s, '')::uuid,
                      %s, %s, 'draft', %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                str(uuid.uuid4()), campaign_id, touch["sequence_index"], touch["channel"],
                touch.get("contact_point_id") or "", touch.get("sender_account_id") or "",
                touch["angle"], touch["scheduled_at"], touch.get("subject"), touch["text"],
                Json({
                    "evidence_id": touch["evidence_id"],
                    "source_url": touch["source_url"],
                    "channel_status": touch["channel_status"],
                    "observation": touch.get("observation"),
                    "problem_hypothesis": touch.get("problem_hypothesis"),
                    "relevance_bridge": touch.get("relevance_bridge"),
                    "generation_source": touch.get("generation_source") or "deterministic",
                    "generation_prompt_version": touch.get("generation_prompt_version"),
                    "semantic_review_prompt_version": touch.get("semantic_review_prompt_version"),
                }),
                Json(touch["quality_gate"]),
                touch.get("strategy_fingerprint"), Json(touch.get("strategy") or {}),
            ),
        )
    record_campaign_event(
        cursor,
        campaign_id,
        "campaign_preview_created",
        actor_id=user_id,
        payload={
            "version": version,
            "touch_count": len(preview["touches"]),
            "sender_mode": preview.get("sender_mode"),
            "represented_business_id": preview.get("represented_business_id"),
        },
    )
    cursor.execute(
        """
        UPDATE lead_workstream_research
        SET evidence_json = %s, personalization_candidates_json = %s,
            selected_personalization_id = %s, outreach_decision_json = %s
        WHERE id = (
            SELECT id FROM lead_workstream_research
            WHERE workstream_id = %s ORDER BY researched_at DESC, created_at DESC LIMIT 1
        )
        """,
        (
            Json(_json_safe(preview["evidence"])), Json(_json_safe(preview["personalization_candidates"])),
            preview["personalization_candidates"][0]["id"],
            Json(_json_safe(preview.get("decision") or {})), workstream_id,
        ),
    )
    context = _apply_sender_mode(
        _load_context(cursor, workstream_id),
        _text(preview.get("sender_mode")),
    )
    room_sync_enabled = str(os.getenv("OUTREACH_ROOM_SYNC_ENABLED") or "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    room = (
        prepare_private_room(
            cursor,
            campaign_id=campaign_id,
            preview=preview,
            context=context,
            user_id=user_id,
        )
        if room_sync_enabled
        else None
    )
    return {
        "id": campaign_id,
        "version": version,
        "status": "draft",
        "room": room,
    }


def approve_campaign(cursor: Any, campaign_id: str, *, user_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT c.*, COUNT(t.id) AS touch_count,
               BOOL_AND(COALESCE((t.quality_gate_json->>'passed')::boolean, FALSE)) AS quality_passed,
               BOOL_AND(CASE WHEN t.channel IN ('telegram', 'email', 'vk') THEN t.sender_account_id IS NOT NULL ELSE TRUE END) AS senders_ready,
               BOOL_AND(
                   CASE
                       WHEN t.channel IN ('telegram', 'email', 'vk') THEN t.message_brief_json->>'channel_status' = 'ready'
                       ELSE t.message_brief_json->>'channel_status' = 'manual'
                   END
               ) AS channels_ready
        FROM outreach_campaigns c
        LEFT JOIN outreach_campaign_touches t ON t.campaign_id = c.id
        WHERE c.id = %s
        GROUP BY c.id
        """,
        (campaign_id,),
    )
    campaign = _dict(cursor.fetchone())
    if not campaign:
        raise LookupError("Campaign not found")
    if campaign.get("status") != "draft":
        raise ValueError("Only a draft campaign can be approved")
    if (
        not campaign.get("touch_count")
        or not campaign.get("quality_passed")
        or not campaign.get("senders_ready")
        or not campaign.get("channels_ready")
    ):
        raise ValueError("Campaign preflight failed")
    cursor.execute(
        """
        SELECT touch.*,
               sender.scope_type AS sender_scope_type,
               sender.business_id AS sender_business_id
        FROM outreach_campaign_touches touch
        LEFT JOIN outreach_sender_accounts sender ON sender.id = touch.sender_account_id
        WHERE touch.campaign_id = %s
        ORDER BY touch.sequence_index
        """,
        (campaign_id,),
    )
    approval_touches = [_dict(row) for row in cursor.fetchall()]
    if not all(
        generation_contract_current(
            touch.get("message_brief_json"),
            touch.get("quality_gate_json"),
        )
        for touch in approval_touches
    ):
        raise ValueError("Campaign generation is outdated; create a new preview")
    if any(
        sender_scope_preflight_reason({**campaign, **touch}) is not None
        for touch in approval_touches
        if touch.get("channel") in AUTOMATIC_CHANNELS
    ):
        raise ValueError("Sender scope, mode, or represented business preflight failed")
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id = t.campaign_id
        JOIN outreach_sender_accounts s ON s.id = t.sender_account_id
        LEFT JOIN telegram_account_permissions p ON p.account_id = s.external_account_id
        WHERE t.campaign_id = %s
          AND t.channel IN ('telegram', 'email', 'vk')
          AND (
              s.status <> 'connected'
              OR s.health_status IN ('paused', 'blocked')
              OR COALESCE((s.capabilities_json->>'direct_send')::boolean, FALSE) = FALSE
              OR COALESCE((s.capabilities_json->>'reply_sync')::boolean, FALSE) = FALSE
              OR (t.channel = 'telegram' AND COALESCE(p.outreach_enabled, FALSE) = FALSE)
              OR (t.channel IN ('email', 'vk') AND COALESCE(s.outreach_enabled, FALSE) = FALSE)
          )
        """,
        (campaign_id,),
    )
    if int(_scalar(cursor.fetchone(), "count") or 0) > 0:
        raise ValueError("Sender permission, health, adapter, or tenant preflight failed")
    snapshot_hash = approval_snapshot_hash(campaign, approval_touches)
    cursor.execute(
        """
        UPDATE outreach_campaigns
        SET status = 'approved', approved_by = %s, approved_at = NOW(),
            approved_snapshot_hash = %s, updated_at = NOW()
        WHERE id = %s
        RETURNING id, version, status, approved_at
        """,
        (user_id, snapshot_hash, campaign_id),
    )
    result = _dict(cursor.fetchone())
    cursor.execute(
        "UPDATE outreach_campaign_touches SET status = 'approved', approved_text = generated_text, updated_at = NOW() WHERE campaign_id = %s",
        (campaign_id,),
    )
    batch_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreachsendbatches (
            id, batch_date, daily_limit, status, created_by, approved_by, created_at, updated_at
        ) VALUES (%s, CURRENT_DATE, 10, 'approved', %s, %s, NOW(), NOW())
        """,
        (batch_id, user_id, user_id),
    )
    cursor.execute(
        """
        SELECT t.*, c.lead_id, c.workstream_id, c.sender_profile_id
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id = t.campaign_id
        WHERE t.campaign_id = %s
        ORDER BY t.sequence_index
        """,
        (campaign_id,),
    )
    for row in cursor.fetchall():
        touch = _dict(row)
        if touch.get("channel") in MANUAL_CHANNELS:
            cursor.execute(
                "UPDATE outreach_campaign_touches SET status = 'awaiting_manual_send', manual_due_at = NOW() + INTERVAL '48 hours', updated_at = NOW() WHERE id = %s",
                (touch["id"],),
            )
            continue
        draft_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO outreachmessagedrafts (
                id, lead_id, workstream_id, channel, angle_type, tone, status,
                generated_text, approved_text, message_brief_json, quality_gate_json,
                contact_point_id, sender_profile_id, created_by, approved_by,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, 'founder_led', 'approved',
                      %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                draft_id, touch["lead_id"], touch["workstream_id"], touch["channel"],
                touch["angle_type"], touch["generated_text"], touch["generated_text"],
                Json(touch.get("message_brief_json") or {}), Json(touch.get("quality_gate_json") or {}),
                touch.get("contact_point_id"), touch.get("sender_profile_id"), user_id, user_id,
            ),
        )
        cursor.execute(
            """
            INSERT INTO outreachsendqueue (
                id, batch_id, lead_id, workstream_id, draft_id, channel,
                delivery_status, sender_account_id, campaign_touch_id, scheduled_at,
                recipient_key, idempotency_key, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'queued', %s, %s, %s, %s, %s, NOW(), NOW())
            """,
            (
                str(uuid.uuid4()), batch_id, touch["lead_id"], touch["workstream_id"],
                draft_id, touch["channel"], touch.get("sender_account_id"), touch["id"], touch["scheduled_at"],
                recipient_key(str(touch["lead_id"])), f"outreach:{touch['id']}",
            ),
        )
        cursor.execute(
            "UPDATE outreach_campaign_touches SET draft_id = %s, status = 'scheduled', updated_at = NOW() WHERE id = %s",
            (draft_id, touch["id"]),
        )
    result["batch_id"] = batch_id
    record_campaign_event(
        cursor,
        campaign_id,
        "campaign_approved",
        actor_id=user_id,
        payload={"version": int(result.get("version") or 0), "batch_id": batch_id},
    )
    return result


def change_campaign_status(
    cursor: Any,
    campaign_id: str,
    action: str,
    *,
    user_id: str,
) -> dict[str, Any]:
    transitions = {
        "pause": ({"approved", "active"}, "paused"),
        "resume": ({"paused"}, "approved"),
        "cancel": ({"draft", "approved", "active", "paused"}, "cancelled"),
    }
    if action not in transitions:
        raise ValueError("Unsupported campaign action")
    allowed_from, next_status = transitions[action]
    cursor.execute("SELECT id, status FROM outreach_campaigns WHERE id = %s FOR UPDATE", (campaign_id,))
    campaign = _dict(cursor.fetchone())
    if not campaign:
        raise LookupError("Campaign not found")
    if campaign.get("status") not in allowed_from:
        raise ValueError(f"Cannot {action} campaign from {campaign.get('status')}")
    if action == "resume":
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM outreach_campaign_touches t
            JOIN outreach_campaigns c ON c.id = t.campaign_id
            LEFT JOIN outreach_sender_accounts s ON s.id = t.sender_account_id
            LEFT JOIN telegram_account_permissions p ON p.account_id = s.external_account_id
            WHERE t.campaign_id = %s
              AND t.channel IN ('telegram', 'email', 'vk')
              AND (
                  s.id IS NULL
                  OR s.status <> 'connected'
                  OR s.scope_type <> c.scope_type
                  OR COALESCE(s.business_id, '') <> COALESCE(c.business_id, '')
                  OR s.health_status IN ('paused', 'blocked')
                  OR COALESCE((s.capabilities_json->>'direct_send')::boolean, FALSE) = FALSE
                  OR COALESCE((s.capabilities_json->>'reply_sync')::boolean, FALSE) = FALSE
                  OR (t.channel = 'telegram' AND COALESCE(p.outreach_enabled, FALSE) = FALSE)
                  OR (t.channel IN ('email', 'vk') AND COALESCE(s.outreach_enabled, FALSE) = FALSE)
              )
            """,
            (campaign_id,),
        )
        if int(_scalar(cursor.fetchone(), "count") or 0) > 0:
            raise ValueError("Sender account preflight failed")
    cursor.execute(
        "UPDATE outreach_campaigns SET status = %s, stop_reason = %s, updated_at = NOW() WHERE id = %s RETURNING id, version, status, stop_reason",
        (next_status, "manual_pause" if action == "pause" else None, campaign_id),
    )
    result = _dict(cursor.fetchone())
    if action in {"pause", "cancel"}:
        touch_status = "paused" if action == "pause" else "cancelled"
        queue_status = "paused" if action == "pause" else "failed"
        cursor.execute(
            "UPDATE outreach_campaign_touches SET status = %s, updated_at = NOW() WHERE campaign_id = %s AND status IN ('draft', 'approved', 'scheduled', 'queued', 'awaiting_manual_send', 'needs_attention')",
            (touch_status, campaign_id),
        )
        cursor.execute(
            "UPDATE outreachsendqueue SET delivery_status = %s, error_text = %s, updated_at = NOW() WHERE campaign_touch_id IN (SELECT id FROM outreach_campaign_touches WHERE campaign_id = %s) AND delivery_status IN ('queued', 'retry')",
            (queue_status, f"campaign_{action}", campaign_id),
        )
    else:
        cursor.execute(
            "UPDATE outreach_campaign_touches SET status = CASE WHEN channel IN ('max', 'vk', 'whatsapp', 'sms', 'manual') THEN 'awaiting_manual_send' ELSE 'scheduled' END, manual_due_at = CASE WHEN channel IN ('max', 'vk', 'whatsapp', 'sms', 'manual') THEN NOW() + INTERVAL '48 hours' ELSE manual_due_at END, updated_at = NOW() WHERE campaign_id = %s AND status = 'paused'",
            (campaign_id,),
        )
        cursor.execute(
            "UPDATE outreachsendqueue SET delivery_status = 'queued', error_text = NULL, updated_at = NOW() WHERE campaign_touch_id IN (SELECT id FROM outreach_campaign_touches WHERE campaign_id = %s) AND delivery_status = 'paused'",
            (campaign_id,),
        )
    event_name = {"pause": "campaign_paused", "resume": "campaign_resumed", "cancel": "campaign_cancelled"}[action]
    record_campaign_event(cursor, campaign_id, event_name, actor_id=user_id)
    return result


def record_manual_touch(
    cursor: Any,
    campaign_id: str,
    touch_id: str,
    event_type: str,
    *,
    user_id: str,
    note: str = "",
) -> dict[str, Any]:
    if event_type not in {"sent", "skipped", "reply"}:
        raise ValueError("Unsupported manual event")
    cursor.execute(
        """
        SELECT t.*, c.lead_id, c.workstream_id, c.scope_type, c.business_id,
               ws.workstream_type
        FROM outreach_campaign_touches t
        JOIN outreach_campaigns c ON c.id = t.campaign_id
        JOIN lead_workstreams ws ON ws.id = c.workstream_id
        WHERE t.id = %s AND t.campaign_id = %s
        FOR UPDATE OF t
        """,
        (touch_id, campaign_id),
    )
    touch = _dict(cursor.fetchone())
    if not touch:
        raise LookupError("Campaign touch not found")
    if touch.get("channel") not in MANUAL_CHANNELS:
        raise ValueError("Touch is not a manual channel")
    allowed_statuses = {"awaiting_manual_send", "needs_attention", "manual_expired"}
    if event_type == "reply":
        allowed_statuses |= {"manual_sent", "sent", "delivered"}
    if touch.get("status") not in allowed_statuses:
        raise ValueError(f"Manual event is not allowed from {touch.get('status')}")
    next_touch_status = "manual_sent" if event_type in {"sent", "reply"} else "manual_skipped"
    cursor.execute(
        """
        UPDATE outreach_campaign_touches
        SET status = %s, manual_due_at = NULL,
            delivery_json = delivery_json || %s, updated_at = NOW()
        WHERE id = %s
        """,
        (next_touch_status, Json({"manual_event": event_type, "note": note}), touch_id),
    )
    if event_type == "reply":
        classification = classify_inbound_event({"raw_reply": note})
        if classification["creates_suppression"]:
            cursor.execute(
                """
                INSERT INTO outreach_suppressions (
                    id, lead_id, workstream_id, scope_type, business_id,
                    recipient_key, reason_code, source, created_by,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'manual', %s, NOW(), NOW())
                """,
                (
                    str(uuid.uuid4()), touch["lead_id"], touch["workstream_id"],
                    touch.get("scope_type"), touch.get("business_id"),
                    recipient_key(str(touch["lead_id"])), classification["classification"], user_id,
                ),
            )
        cursor.execute(
            """
            INSERT INTO outreach_inbound_events (
                id, campaign_id, touch_id, lead_id, workstream_id, channel,
                event_type, classification, is_human, stops_campaign, confidence,
                raw_payload_json, classified_by, occurred_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'reply', %s, %s, %s, %s, %s, 'manual', NOW(), NOW())
            """,
            (
                str(uuid.uuid4()), campaign_id, touch_id, touch["lead_id"], touch["workstream_id"],
                touch.get("channel"), classification["classification"], classification["is_human"],
                classification["stops_campaign"], classification["confidence"], Json({"reply": note}),
            ),
        )
        cursor.execute(
            "UPDATE outreach_campaigns SET status = 'stopped', stop_reason = 'recipient_replied', last_reply_at = NOW(), updated_at = NOW() WHERE id = %s",
            (campaign_id,),
        )
        cursor.execute(
            "UPDATE outreach_campaign_touches SET status = 'reply_cancelled', delivery_json = delivery_json || %s, updated_at = NOW() WHERE campaign_id = %s AND sequence_index > (SELECT sequence_index FROM outreach_campaign_touches WHERE id = %s) AND status IN ('approved', 'scheduled', 'queued', 'manual', 'awaiting_manual_send', 'manual_expired', 'needs_attention', 'paused')",
            (Json({"stop_reason": "recipient_replied"}), campaign_id, touch_id),
        )
        cursor.execute(
            "UPDATE outreachsendqueue SET delivery_status = 'failed', error_text = 'recipient_replied', preflight_reason = 'recipient_replied', updated_at = NOW() WHERE campaign_touch_id IN (SELECT id FROM outreach_campaign_touches WHERE campaign_id = %s AND status = 'reply_cancelled') AND delivery_status IN ('queued', 'retry', 'paused')",
            (campaign_id,),
        )
        cursor.execute(
            """
            UPDATE lead_workstreams
            SET lifecycle_status = 'replied', status_reason = %s,
                next_step = 'Ответить получателю вручную', state_changed_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (classification["classification"], touch["workstream_id"]),
        )
        upsert_relationship_from_reply(
            cursor,
            workstream_id=str(touch.get("workstream_id") or ""),
            lead_id=str(touch.get("lead_id") or ""),
            scope_type=str(touch.get("scope_type") or "business"),
            business_id=str(touch.get("business_id") or "") or None,
            raw_reply=note,
            classification=classification["classification"],
            provider_event_id=None,
        )
        room_sync_enabled = str(os.getenv("OUTREACH_ROOM_SYNC_ENABLED") or "true").strip().lower() in {
            "1", "true", "yes", "on",
        }
        if room_sync_enabled:
            mirror_inbound_to_room(
                cursor,
                campaign_id=campaign_id,
                touch_id=touch_id,
                channel=str(touch.get("channel") or "manual"),
                provider_event_id=None,
                raw_reply=note,
                occurred_at=datetime.now(timezone.utc),
            )
            if classification["classification"] in ROOM_INVITATION_CLASSIFICATIONS:
                mark_room_ready_after_positive_reply(
                    cursor,
                    campaign_id=campaign_id,
                    represented_business_name=None,
                )
        learning_outcome = {
            "interested": "positive_reply",
            "question": "question",
            "not_interested": "hard_no",
            "unsubscribe": "unsubscribe",
            "complaint": "complaint",
            "human_unknown": "replied",
        }.get(classification["classification"])
        if learning_outcome:
            record_learning_event(
                cursor,
                campaign={
                    "id": campaign_id,
                    "scope_type": touch.get("scope_type"),
                    "business_id": touch.get("business_id"),
                    "workstream_type": touch.get("workstream_type"),
                },
                touch=touch,
                outcome_type=learning_outcome,
                payload={"source": "manual", "classification": classification["classification"]},
            )
    if event_type in {"sent", "reply"}:
        cursor.execute(
            """
            SELECT id
            FROM outreach_learning_events
            WHERE campaign_id = %s AND touch_id = %s AND outcome_type = 'sent'
            LIMIT 1
            """,
            (campaign_id, touch_id),
        )
        if not cursor.fetchone():
            record_learning_event(
                cursor,
                campaign={
                    "id": campaign_id,
                    "scope_type": touch.get("scope_type"),
                    "business_id": touch.get("business_id"),
                    "workstream_type": touch.get("workstream_type"),
                },
                touch=touch,
                outcome_type="sent",
                payload={"source": "manual", "manual_event": event_type},
            )
    record_campaign_event(
        cursor, campaign_id, f"manual_{event_type}", actor_id=user_id,
        touch_id=touch_id, reason_code="recipient_replied" if event_type == "reply" else None,
        payload={"note": note},
    )
    if event_type in {"sent", "skipped"}:
        cursor.execute(
            """
            UPDATE outreach_campaign_touches
            SET status = 'scheduled', preflight_at = NULL, preflight_reason = NULL,
                updated_at = NOW()
            WHERE campaign_id = %s
              AND sequence_index > %s
              AND status = 'paused'
              AND preflight_reason = 'prior_manual_touch_pending'
            """,
            (campaign_id, int(touch.get("sequence_index") or 0)),
        )
        cursor.execute(
            """
            UPDATE outreachsendqueue
            SET delivery_status = 'queued', error_text = NULL,
                preflight_at = NULL, preflight_reason = NULL, updated_at = NOW()
            WHERE campaign_touch_id IN (
                SELECT id FROM outreach_campaign_touches
                WHERE campaign_id = %s AND sequence_index > %s
            )
              AND delivery_status = 'paused'
              AND preflight_reason = 'prior_manual_touch_pending'
            """,
            (campaign_id, int(touch.get("sequence_index") or 0)),
        )
        cursor.execute(
            """
            UPDATE outreach_campaigns
            SET status = 'approved', stop_reason = NULL, needs_attention_reason = NULL,
                updated_at = NOW()
            WHERE id = %s
              AND status = 'paused'
              AND stop_reason IN ('prior_manual_touch_pending', 'manual_touch_timeout')
            """,
            (campaign_id,),
        )
        cursor.execute(
            """
            UPDATE outreach_campaigns c
            SET status = 'completed', updated_at = NOW()
            WHERE c.id = %s
              AND c.status IN ('approved', 'active')
              AND NOT EXISTS (
                  SELECT 1 FROM outreach_campaign_touches t
                  WHERE t.campaign_id = c.id
                    AND t.status IN ('draft', 'approved', 'scheduled', 'queued', 'manual', 'awaiting_manual_send', 'needs_attention', 'paused')
              )
            """,
            (campaign_id,),
        )
    return {"campaign_id": campaign_id, "touch_id": touch_id, "event_type": event_type}


def record_campaign_business_outcome(
    cursor: Any,
    campaign_id: str,
    outcome_type: str,
    *,
    user_id: str | None,
    note: str = "",
) -> dict[str, Any]:
    if outcome_type not in CAMPAIGN_BUSINESS_OUTCOMES:
        raise ValueError("Unsupported campaign outcome")
    cursor.execute(
        """
        SELECT c.*, ws.workstream_type, ws.lifecycle_status,
               EXISTS (
                   SELECT 1
                   FROM outreach_inbound_events inbound
                   WHERE inbound.campaign_id = c.id AND inbound.is_human = TRUE
               ) AS has_human_reply,
               (
                   SELECT inbound.touch_id
                   FROM outreach_inbound_events inbound
                   WHERE inbound.campaign_id = c.id AND inbound.is_human = TRUE
                   ORDER BY inbound.occurred_at DESC, inbound.created_at DESC
                   LIMIT 1
               ) AS reply_touch_id,
               (
                   SELECT touch.id
                   FROM outreach_campaign_touches touch
                   WHERE touch.campaign_id = c.id
                     AND touch.status IN ('manual_sent', 'sent', 'delivered')
                   ORDER BY touch.sequence_index DESC
                   LIMIT 1
               ) AS last_sent_touch_id
        FROM outreach_campaigns c
        JOIN lead_workstreams ws ON ws.id = c.workstream_id
        WHERE c.id = %s
        FOR UPDATE OF c
        """,
        (campaign_id,),
    )
    campaign = _dict(cursor.fetchone())
    if not campaign:
        raise LookupError("Campaign not found")

    has_human_reply = bool(campaign.get("has_human_reply"))
    if outcome_type != "no_reply":
        if not has_human_reply:
            raise ValueError("Record the recipient reply before the business outcome")
        if not note.strip():
            raise ValueError("Outcome note is required")
    if outcome_type == "no_reply":
        if campaign.get("status") != "completed":
            raise ValueError("No-reply can be recorded only after the campaign is completed")
        if has_human_reply or campaign.get("last_reply_at"):
            raise ValueError("No-reply conflicts with a recorded reply")
        cursor.execute(
            """
            SELECT id
            FROM outreach_learning_events
            WHERE campaign_id = %s
              AND outcome_type IN ('replied', 'positive_reply', 'question', 'hard_no',
                                   'unsubscribe', 'complaint', 'meeting_booked', 'converted',
                                   'interested', 'call_planned', 'contacts_exchanged',
                                   'pilot_agreed', 'campaign_launched', 'joint_project',
                                   'recurring_partnership', 'not_relevant', 'lost')
            LIMIT 1
            """,
            (campaign_id,),
        )
        if cursor.fetchone():
            raise ValueError("No-reply conflicts with an existing campaign outcome")

    touch_id = str(campaign.get("reply_touch_id") or campaign.get("last_sent_touch_id") or "").strip()
    if not touch_id:
        raise ValueError("Campaign has no sent touch for outcome attribution")
    cursor.execute(
        """
        SELECT *
        FROM outreach_campaign_touches
        WHERE id = %s AND campaign_id = %s
        FOR UPDATE
        """,
        (touch_id, campaign_id),
    )
    touch = _dict(cursor.fetchone())
    if not touch:
        raise LookupError("Attribution touch not found")

    cursor.execute(
        """
        SELECT id
        FROM outreach_learning_events
        WHERE campaign_id = %s AND touch_id = %s AND outcome_type = %s
        LIMIT 1
        """,
        (campaign_id, touch_id, outcome_type),
    )
    existing = _dict(cursor.fetchone())
    if existing:
        return {
            "campaign_id": campaign_id,
            "touch_id": touch_id,
            "outcome_type": outcome_type,
            "learning_event_id": str(existing.get("id") or ""),
            "reused": True,
        }

    learning_event_id = record_learning_event(
        cursor,
        campaign={
            "id": campaign_id,
            "scope_type": campaign.get("scope_type"),
            "business_id": campaign.get("business_id"),
            "workstream_type": campaign.get("workstream_type"),
        },
        touch=touch,
        outcome_type=outcome_type,
        payload={"source": "manual_business_outcome", "note": note.strip()},
    )
    lifecycle_status = {
        "no_reply": "closed_lost",
        "interested": "replied",
        "question": "replied",
        "call_planned": "qualified",
        "contacts_exchanged": "qualified",
        "pilot_agreed": "qualified",
        "campaign_launched": "converted",
        "joint_project": "converted",
        "recurring_partnership": "converted",
        "hard_no": "closed_lost",
        "not_relevant": "not_relevant",
        "lost": "closed_lost",
        "meeting_booked": "qualified",
        "converted": "converted",
    }[outcome_type]
    next_step = {
        "no_reply": "Кампания завершена без ответа",
        "interested": "Уточнить интерес и следующий шаг",
        "question": "Ответить на вопрос",
        "call_planned": "Провести разговор и зафиксировать договорённости",
        "contacts_exchanged": "Согласовать следующий шаг между командами",
        "pilot_agreed": "Подготовить пилот",
        "campaign_launched": "Отслеживать результат кампании",
        "joint_project": "Вести совместный проект",
        "recurring_partnership": "Поддерживать регулярное партнёрство",
        "hard_no": "Не продолжать аутрич",
        "not_relevant": "Закрыть как нерелевантный контакт",
        "lost": "Зафиксировать причину потери",
        "meeting_booked": "Провести встречу и зафиксировать результат",
        "converted": "Зафиксировать результат сотрудничества",
    }[outcome_type]
    cursor.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status = CASE
                WHEN lifecycle_status = 'converted' THEN 'converted'
                ELSE %s
            END,
            status_reason = %s, next_step = %s,
            state_changed_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (lifecycle_status, outcome_type, next_step, campaign.get("workstream_id")),
    )
    record_campaign_event(
        cursor,
        campaign_id,
        "campaign_outcome_recorded",
        actor_id=user_id,
        touch_id=touch_id,
        reason_code=outcome_type,
        payload={"note": note.strip(), "learning_event_id": learning_event_id},
    )
    if campaign.get("room_id"):
        room_status = (
            "won"
            if outcome_type in {"campaign_launched", "joint_project", "recurring_partnership", "converted"}
            else "lost" if outcome_type in {"hard_no", "not_relevant", "lost", "no_reply"}
            else "negotiating"
        )
        cursor.execute(
            """
            UPDATE sales_rooms
            SET status = %s,
                room_json = room_json || jsonb_build_object(
                    'outcome', %s,
                    'next_step', %s,
                    'outcome_note', %s
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (room_status, outcome_type, next_step, note.strip(), campaign.get("room_id")),
        )
        cursor.execute(
            """
            INSERT INTO sales_room_events (id, room_id, event_type, metadata_json, created_at)
            VALUES (%s, %s, 'outcome_recorded', %s, NOW())
            """,
            (
                str(uuid.uuid4()), campaign.get("room_id"),
                Json({"outcome": outcome_type, "note": note.strip()}),
            ),
        )
    return {
        "campaign_id": campaign_id,
        "touch_id": touch_id,
        "outcome_type": outcome_type,
        "learning_event_id": learning_event_id,
        "reused": False,
    }


def finalize_no_reply_campaigns(
    cursor: Any,
    *,
    limit: int = 200,
    default_grace_hours: int = 168,
) -> int:
    safe_limit = max(1, min(int(limit or 200), 1000))
    safe_grace = max(24, min(int(default_grace_hours or 168), 24 * 30))
    cursor.execute(
        """
        SELECT campaign.id
        FROM outreach_campaigns campaign
        WHERE campaign.status = 'completed'
          AND campaign.last_reply_at IS NULL
          AND campaign.updated_at <= NOW() - (
              GREATEST(
                  24,
                  LEAST(
                      720,
                      COALESCE(NULLIF(campaign.policy_json->>'no_reply_grace_hours', '')::integer, %s)
                  )
              ) * INTERVAL '1 hour'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM outreach_inbound_events inbound
              WHERE inbound.campaign_id = campaign.id AND inbound.is_human = TRUE
          )
          AND NOT EXISTS (
              SELECT 1
              FROM outreach_learning_events learning
              WHERE learning.campaign_id = campaign.id
                AND learning.outcome_type IN (
                    'replied', 'positive_reply', 'question', 'hard_no',
                    'unsubscribe', 'complaint', 'meeting_booked', 'converted', 'no_reply'
                )
          )
        ORDER BY campaign.updated_at
        LIMIT %s
        FOR UPDATE SKIP LOCKED
        """,
        (safe_grace, safe_limit),
    )
    campaign_ids = [str(_dict(row).get("id") or "") for row in cursor.fetchall()]
    finalized = 0
    for campaign_id in campaign_ids:
        if not campaign_id:
            continue
        result = record_campaign_business_outcome(
            cursor,
            campaign_id,
            "no_reply",
            user_id=None,
            note="Автоматически зафиксировано после завершения цепочки и окна ожидания ответа.",
        )
        if not result.get("reused"):
            finalized += 1
    return finalized


def expire_manual_touches(cursor: Any, *, limit: int = 200) -> int:
    safe_limit = max(1, min(int(limit or 200), 1000))
    cursor.execute(
        """
        WITH expired AS (
            SELECT id
            FROM outreach_campaign_touches
            WHERE status = 'awaiting_manual_send'
              AND manual_due_at IS NOT NULL
              AND manual_due_at <= NOW()
            ORDER BY manual_due_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        UPDATE outreach_campaign_touches touch
        SET status = 'needs_attention',
            delivery_json = delivery_json || jsonb_build_object(
                'manual_timeout', TRUE, 'manual_expired_at', NOW()
            ),
            updated_at = NOW()
        FROM expired
        WHERE touch.id = expired.id
        RETURNING touch.id, touch.campaign_id
        """,
        (safe_limit,),
    )
    expired = [_dict(row) for row in cursor.fetchall()]
    campaign_ids = sorted({str(row.get("campaign_id")) for row in expired if row.get("campaign_id")})
    for campaign_id in campaign_ids:
        cursor.execute(
            """
            UPDATE outreach_campaigns
            SET status = 'paused', needs_attention_reason = 'manual_touch_timeout',
                stop_reason = 'manual_touch_timeout', updated_at = NOW()
            WHERE id = %s AND status IN ('approved', 'active')
            """,
            (campaign_id,),
        )
        record_campaign_event(
            cursor,
            campaign_id,
            "manual_touch_timeout",
            actor_id=None,
            reason_code="manual_touch_timeout",
        )
    return len(expired)
