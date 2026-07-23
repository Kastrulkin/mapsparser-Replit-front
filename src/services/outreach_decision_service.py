"""Explainable Outreach v2 scoring and pre-generation choices."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


DECISION_VERSION = "outreach-v2.1"
TRUST_STRATEGIES = {
    "founder_story",
    "business_reputation",
    "matching_authority",
    "case_study",
    "referral",
    "neighbour_context",
}
TRUST_BY_SENDER_MODE = {
    "localos": (
        "founder_story",
        "case_study",
        "business_reputation",
        "neighbour_context",
    ),
    "partner_business": (
        "business_reputation",
        "case_study",
        "founder_story",
        "referral",
        "neighbour_context",
    ),
    "localos_for_partner": (
        "matching_authority",
        "business_reputation",
        "referral",
        "neighbour_context",
    ),
}
TERMINAL_LIFECYCLE_STATES = {
    "replied",
    "converted",
    "closed_lost",
    "suppressed",
    "not_relevant",
}

RESIDENTIAL_RECIPIENT_TOKENS = (
    "residential_complex",
    "residential complex",
    "жилой комплекс",
    "жилые комплексы",
    "жилой комплекс / апартаменты",
    "жилкомплекс",
)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _is_residential_recipient(context: dict[str, Any]) -> bool:
    combined = " ".join(
        _text(context.get(key)).lower()
        for key in ("lead_name", "category", "partner_kind")
        if _text(context.get(key))
    )
    return combined.startswith("жк ") or any(
        token in combined for token in RESIDENTIAL_RECIPIENT_TOKENS
    )


def _clamp(value: Any, minimum: float = 0, maximum: float = 100) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = minimum
    return max(minimum, min(maximum, number))


def _stable_id(prefix: str, payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _confidence_score(value: Any) -> float:
    label = _text(value).lower()
    if label == "high":
        return 95
    if label == "medium":
        return 70
    if label == "low":
        return 35
    number = _clamp(value, 0, 1)
    return round(number * 100, 2)


def _freshness_score(evidence: dict[str, Any], now: datetime) -> float:
    label = _text(evidence.get("freshness")).lower()
    if label in {"fresh", "current", "current_snapshot"}:
        return 100
    if label == "stale":
        return 15
    observed_at = evidence.get("observed_at") or evidence.get("published_at")
    if observed_at:
        try:
            parsed = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            age_days = max(0, (now - parsed.astimezone(timezone.utc)).days)
            if age_days <= 30:
                return 100
            if age_days <= 90:
                return 80
            if age_days <= 180:
                return 55
            return 20
        except (TypeError, ValueError):
            pass
    return 40


def _specificity_score(evidence: dict[str, Any]) -> float:
    fact = _text(evidence.get("fact") or evidence.get("observed_fact"))
    if len(fact) >= 60 and (re.search(r"\d", fact) or len(fact.split()) >= 10):
        return 95
    if len(fact) >= 30:
        return 75
    if len(fact) >= 15:
        return 50
    return 20


def _relevance_score(evidence: dict[str, Any]) -> float:
    explicit = evidence.get("relevance_score")
    if explicit is not None:
        return _clamp(explicit)
    relevance = _text(evidence.get("relevance") or evidence.get("why_it_matters"))
    if len(relevance) >= 50:
        return 90
    if len(relevance) >= 20:
        return 75
    if relevance:
        return 55
    return 25


def score_evidence(evidence: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    components: dict[str, dict[str, Any]] = {
        "relevance": {"score": _relevance_score(evidence), "weight": 30},
        "source_confidence": {"score": _confidence_score(evidence.get("confidence")), "weight": 25},
        "freshness": {"score": _freshness_score(evidence, current_time), "weight": 20},
        "specificity": {"score": _specificity_score(evidence), "weight": 15},
    }
    engagement = evidence.get("engagement_score")
    if engagement is None and evidence.get("engagement_comparable") is True:
        engagement = evidence.get("engagement")
    if engagement is not None and evidence.get("engagement_comparable") is not False:
        components["engagement"] = {"score": _clamp(engagement), "weight": 10}
    total_weight = sum(float(item["weight"]) for item in components.values())
    score = sum(
        float(item["score"]) * float(item["weight"]) / total_weight
        for item in components.values()
    )
    return {
        "evidence_id": evidence.get("id") or evidence.get("evidence_id"),
        "score": round(score),
        "components": components,
        "engagement_omitted": "engagement" not in components,
        "calculated_at": current_time.isoformat(),
    }


def _fit_score(context: dict[str, Any]) -> float:
    if _text(context.get("workstream_type")) == "client_partnership":
        match = context.get("partnership_match") if isinstance(context.get("partnership_match"), dict) else {}
        return _clamp(match.get("match_score"))
    research = context.get("research") if isinstance(context.get("research"), dict) else {}
    return _clamp(research.get("score"))


def _readiness_score(
    context: dict[str, Any],
    ledger: list[dict[str, Any]],
    availability: dict[str, dict[str, Any]],
    *,
    profile_ready: bool,
) -> dict[str, Any]:
    contacts = context.get("contacts") if isinstance(context.get("contacts"), list) else []
    usable_contacts = [
        item for item in contacts
        if isinstance(item, dict) and _text(item.get("verification_status")).lower() not in {"invalid", "stale"}
    ]
    channel_states = {
        _text(item.get("status"))
        for item in availability.values()
        if isinstance(item, dict)
    }
    components = {
        "contactability": 100 if usable_contacts else 0,
        "evidence": 100 if ledger else 0,
        "sender_and_channel": 100 if channel_states.intersection({"ready", "manual"}) else 0,
        "relationship_permission": 100,
        "activity_or_timing": 100 if any(
            _text(item.get("freshness")) in {"fresh", "current", "current_snapshot"}
            for item in ledger
        ) else 50,
        "sender_profile": 100 if profile_ready else 0,
    }
    score = (
        components["contactability"] * 0.30
        + components["evidence"] * 0.20
        + components["sender_and_channel"] * 0.20
        + components["relationship_permission"] * 0.10
        + components["activity_or_timing"] * 0.10
        + components["sender_profile"] * 0.10
    )
    return {"score": round(score), "components": components}


def build_outreach_decision(
    context: dict[str, Any],
    ledger: list[dict[str, Any]],
    availability: dict[str, dict[str, Any]],
    suppression: dict[str, Any],
    *,
    sender_mode: str,
    profile_ready: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or datetime.now(timezone.utc)
    evidence_scores = [score_evidence(item, now=current_time) for item in ledger]
    best_signal = max(evidence_scores, key=lambda item: item["score"], default=None)
    signal_score = int(best_signal["score"]) if best_signal else 0
    fit_score = round(_fit_score(context))
    readiness = _readiness_score(
        context,
        ledger,
        availability,
        profile_ready=profile_ready,
    )
    priority_score = round(fit_score * 0.40 + signal_score * 0.35 + readiness["score"] * 0.25)
    reason_codes: list[str] = []
    lifecycle = _text(context.get("lifecycle_status")).lower()
    contacts = context.get("contacts") if isinstance(context.get("contacts"), list) else []
    has_contacts = any(
        isinstance(item, dict)
        and _text(item.get("verification_status")).lower() not in {"invalid", "stale"}
        for item in contacts
    )
    compatibility = next(
        (
            item for item in ledger
            if _text(item.get("kind")) in {"service_compatibility", "residential_context"}
        ),
        None,
    )
    if suppression.get("suppressed"):
        action = "excluded"
        reason_codes.append("suppressed_contact")
    elif lifecycle in TERMINAL_LIFECYCLE_STATES:
        action = "excluded"
        reason_codes.append(f"terminal_state:{lifecycle}")
    elif not has_contacts:
        action = "needs_contact"
        reason_codes.append("recipient_contact_missing")
    elif sender_mode == "partner_business" and not profile_ready:
        action = "needs_sender_setup"
        reason_codes.append("business_sender_profile_missing")
    elif not any(
        isinstance(item, dict) and _text(item.get("status")) in {"ready", "manual"}
        for item in availability.values()
    ):
        action = "needs_sender_setup"
        reason_codes.append("sender_or_channel_unavailable")
    elif sender_mode == "localos" and not ledger:
        action = "needs_evidence"
        reason_codes.append("recipient_evidence_missing")
    elif sender_mode in {"partner_business", "localos_for_partner"} and compatibility and fit_score >= 40:
        action = "write_now"
        reason_codes.append("partnership_compatibility_confirmed")
    elif ledger and priority_score >= 60:
        action = "write_now"
        reason_codes.append("evidence_and_readiness_sufficient")
    else:
        action = "observe"
        reason_codes.append("wait_for_stronger_reason")
    return {
        "version": DECISION_VERSION,
        "action": action,
        "fit_score": fit_score,
        "signal_score": signal_score,
        "readiness_score": readiness["score"],
        "priority_score": priority_score,
        "signal": best_signal,
        "evidence_scores": evidence_scores,
        "readiness": readiness,
        "reason_codes": reason_codes,
        "calculated_at": current_time.isoformat(),
    }


def _approved_fact_values(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    result = []
    for item in items:
        if isinstance(item, dict):
            if _text(item.get("status") or "approved").lower() not in {"approved", "observed"}:
                continue
            value = _text(item.get("fact") or item.get("text") or item.get("title") or item.get("result"))
        else:
            value = _text(item)
        if value:
            result.append(value)
    return list(dict.fromkeys(result))


def offer_candidates(context: dict[str, Any], sender_mode: str) -> list[dict[str, Any]]:
    profile_key = "business_sender_profile" if sender_mode in {"partner_business", "localos_for_partner"} else "platform_sender_profile"
    profile = context.get(profile_key) if isinstance(context.get(profile_key), dict) else {}
    profile_can_supply_claims = sender_mode != "localos_for_partner" or bool(profile.get("confirmed_at"))
    values = _approved_fact_values(profile.get("allowed_offers_json")) if profile_can_supply_claims else []
    source = "approved_sender_profile"
    if sender_mode == "localos_for_partner" and not values:
        match = context.get("partnership_match") if isinstance(context.get("partnership_match"), dict) else {}
        values = _approved_fact_values(match.get("offer_angles"))
        if not values and _text(match.get("relevance_bridge")):
            values = [_text(match.get("relevance_bridge"))]
        source = "partnership_matching"
    candidates = []
    if sender_mode in {"partner_business", "localos_for_partner"} and _is_residential_recipient(context):
        lead_name = _text(context.get("lead_name")) or "жилого комплекса"
        business_name = _text(
            context.get("represented_business_name")
            or context.get("client_business_name")
            or profile.get("company_name")
        ) or "наш бизнес"
        normalized_business_name = business_name.lower().replace("ё", "е")
        category = _text(context.get("category")).lower()
        veselaya_rascheska = normalized_business_name == "веселая расческа"
        if veselaya_rascheska:
            audience = (
                f"семей гостей и жителей {lead_name}"
                if lead_name.lower() == "yes apart" or "апарт-отел" in category
                else f"жителей {lead_name}"
            )
            text = f"Предложить особые условия на детские стрижки для {audience}"
            offer_source = "approved_business_outreach_policy"
            offer_cta = "Уточнить, с кем можно обсудить детали предложения для жителей"
        else:
            text = f"Пригласить жителей {lead_name} в {business_name}"
            offer_source = "residential_recipient_policy"
            offer_cta = (
                f"Обсудить предложение для жителей {lead_name}; "
                "конкретные условия согласовать отдельно"
            )
        payload = {
            "text": text,
            "sender_mode": sender_mode,
            "source": offer_source,
        }
        candidates.append({
            "id": _stable_id("offer", payload),
            "text": text,
            "source": offer_source,
            "sender_mode": sender_mode,
            "cta": offer_cta,
        })
    for value in values[:6]:
        payload = {"text": value, "sender_mode": sender_mode, "source": source}
        candidate = {
            "id": _stable_id("offer", payload),
            "text": value,
            "source": source,
            "sender_mode": sender_mode,
            "cta": value,
        }
        if not any(item["text"].lower() == value.lower() for item in candidates):
            candidates.append(candidate)
    return candidates


def trust_candidates(context: dict[str, Any], sender_mode: str) -> list[dict[str, Any]]:
    allowed = TRUST_BY_SENDER_MODE.get(sender_mode, ())
    profile_key = (
        "business_sender_profile"
        if sender_mode in {"partner_business", "localos_for_partner"}
        else "platform_sender_profile"
    )
    profile = context.get(profile_key) if isinstance(context.get(profile_key), dict) else {}
    profile_can_supply_claims = sender_mode != "localos_for_partner" or bool(profile.get("confirmed_at"))
    story = _text(profile.get("competence_story")) if profile_can_supply_claims else ""
    proofs = (
        _approved_fact_values(profile.get("proof_points_json"))
        + _approved_fact_values(profile.get("verified_cases_json"))
        if profile_can_supply_claims
        else []
    )
    match = context.get("partnership_match") if isinstance(context.get("partnership_match"), dict) else {}
    result = []
    for strategy in allowed:
        statement = ""
        source = "sender_profile"
        if strategy == "founder_story":
            statement = story
        elif strategy == "case_study":
            statement = proofs[0] if proofs else ""
        elif strategy == "matching_authority":
            statement = _text(match.get("relevance_bridge")) or "По публичным данным и услугам у компаний есть основание обсудить сотрудничество."
            source = "partnership_matching"
        elif strategy == "business_reputation":
            statement = proofs[0] if proofs else story or _text(match.get("recipient_observation"))
        elif strategy == "referral":
            statement = _text(match.get("referral_context"))
            source = "partnership_matching"
        elif strategy == "neighbour_context":
            statement = _text(match.get("geography_context")) or _text(context.get("city"))
            source = "public_business_context"
        if statement:
            result.append({"strategy": strategy, "statement": statement, "source": source})
    return result


def select_offer(candidates: list[dict[str, Any]], requested_id: Any = None) -> dict[str, Any]:
    requested = _text(requested_id)
    if requested:
        selected = next((item for item in candidates if item.get("id") == requested), None)
        if not selected:
            raise ValueError("Selected offer is not available for this sender mode")
        return selected
    return candidates[0] if candidates else {}


def select_trust(candidates: list[dict[str, Any]], requested_strategy: Any = None) -> dict[str, Any]:
    requested = _text(requested_strategy)
    if requested and requested not in TRUST_STRATEGIES:
        raise ValueError("Unsupported trust strategy")
    if requested:
        selected = next((item for item in candidates if item.get("strategy") == requested), None)
        if not selected:
            raise ValueError("Trust strategy is not available for this sender mode")
        return selected
    return candidates[0] if candidates else {}
