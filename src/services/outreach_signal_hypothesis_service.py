"""Safe mappings from public signals to testable owner-pain hypotheses.

Signals are observations.  Pain mappings are cohort hypotheses.  The service
never turns a mapping into a claim about a specific recipient and never sends
or queues outreach.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from services.outreach_experiment_service import derive_composite_signal
from services.outreach_playbook import beauty_outreach_guidance


OPEN_SLOT_RE = re.compile(r"\b(?:свободн\w*\s+(?:окн|мест)|горящ\w*\s+окн|окошк\w*\s+на|есть\s+окошк)\w*", re.IGNORECASE)
DISCOUNT_RE = re.compile(r"\b(?:скидк\w*|акци\w*|спецпредложени\w*|промокод\w*)\b", re.IGNORECASE)
HIRING_RE = re.compile(
    r"\b(?:ваканси\w*|ищем\s+(?:мастер\w*|администратор\w*|сотрудник\w*)|"
    r"требуется\s+(?:мастер\w*|администратор\w*|сотрудник\w*))\b",
    re.IGNORECASE,
)
UNANSWERED_REVIEW_RE = re.compile(r"\b(?:отзыв\w*\s+без\s+ответ|неотвеченн\w*\s+отзыв)\b", re.IGNORECASE)


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _recent_matches(
    ledger: list[dict[str, Any]],
    pattern: re.Pattern[str],
    *,
    days: int,
    now: datetime,
) -> list[dict[str, Any]]:
    matches = []
    for item in ledger:
        observed_at = _time(item.get("observed_at") or item.get("published_at"))
        if not observed_at or (now - observed_at.astimezone(timezone.utc)).days > days:
            continue
        if _text(item.get("freshness")).lower() == "stale":
            continue
        if not pattern.search(_text(item.get("fact") or item.get("observed_fact"))):
            continue
        source_type = _text(item.get("source_type") or item.get("kind")).lower()
        if source_type not in {
            "telegram", "telegram_post", "social_post", "public_social_post",
            "vk", "vk_post", "instagram", "instagram_post", "review", "map_review",
        }:
            continue
        if source_type not in {"review", "map_review"} and not (
            item.get("author_or_organization") or item.get("official") is True
        ):
            continue
        matches.append(item)
    return matches


def _library(playbook: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    guidance = playbook if isinstance(playbook, dict) else beauty_outreach_guidance()
    return {
        _text(item.get("key")): item
        for item in guidance.get("pain_signal_hypotheses") or []
        if isinstance(item, dict) and _text(item.get("key"))
    }


def _result(
    rule: dict[str, Any],
    evidence: list[dict[str, Any]],
    *,
    observed_fact: str,
    confidence: float,
    now: datetime,
) -> dict[str, Any]:
    key = _text(rule.get("key"))
    return {
        "id": f"pain-signal-{key}",
        "kind": "pain_signal_hypothesis",
        "pattern_key": key,
        "signal_combo": key,
        "pain_key": _text(rule.get("pain_key")),
        "fact": observed_fact,
        "observed_fact": observed_fact,
        "status": "observed",
        "hypothesis": _text(rule.get("hypothesis")),
        "hypothesis_status": "segment_hypothesis_only",
        "safe_formulation": _text(rule.get("safe_formulation")),
        "relevance": _text(rule.get("safe_formulation")),
        "evidence_ids": [_text(item.get("id") or item.get("evidence_id")) for item in evidence],
        "source_url": next((_text(item.get("source_url")) for item in evidence if _text(item.get("source_url"))), ""),
        "source_type": "composite_public_evidence",
        "observed_at": now.isoformat(),
        "freshness": "current_snapshot",
        "confidence": confidence,
        "usable_for_outreach": True,
        "opening_type": "specific_observation",
        "test_status": "candidate",
    }


def derive_pain_signal_hypotheses(
    context: dict[str, Any],
    ledger: list[dict[str, Any]],
    *,
    playbook: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return only hypotheses whose full observable contract is satisfied."""

    current = now or datetime.now(timezone.utc)
    rules = _library(playbook)
    results: list[dict[str, Any]] = []

    social_map = derive_composite_signal(context, ledger)
    social_map_rule = rules.get("active_social_with_map_gap")
    if social_map and social_map_rule:
        evidence_ids = set(social_map.get("evidence_ids") or [])
        evidence = [item for item in ledger if _text(item.get("id")) in evidence_ids]
        if not evidence:
            evidence = [{
                "id": "map-and-social-snapshot",
                "source_url": social_map.get("source_url"),
            }]
        result = _result(
            social_map_rule,
            evidence,
            observed_fact=_text(social_map.get("observed_fact") or social_map.get("fact")),
            confidence=float(social_map.get("confidence") or 0.9),
            now=current,
        )
        result["map_gap"] = social_map.get("map_gap")
        result["social_activity"] = social_map.get("social_activity")
        results.append(result)

    repeated_specs = (
        ("repeated_open_slots", OPEN_SLOT_RE, 30, 2),
        ("repeated_discount_promotions", DISCOUNT_RE, 60, 3),
        ("repeated_hiring_signals", HIRING_RE, 90, 2),
    )
    for key, pattern, days, minimum in repeated_specs:
        rule = rules.get(key)
        if not rule:
            continue
        matches = _recent_matches(ledger, pattern, days=days, now=current)
        if len(matches) < minimum:
            continue
        results.append(_result(
            rule,
            matches,
            observed_fact=(
                f"В официальных каналах найдено {len(matches)} публикации по теме "
                f"за последние {days} дней."
            ),
            confidence=0.75,
            now=current,
        ))

    review_rule = rules.get("unanswered_reviews_with_active_presence")
    review_matches = _recent_matches(ledger, UNANSWERED_REVIEW_RE, days=90, now=current)
    social = context.get("official_social_activity") if isinstance(context.get("official_social_activity"), dict) else {}
    if review_rule and len(review_matches) >= 2 and social.get("official"):
        results.append(_result(
            review_rule,
            review_matches,
            observed_fact=f"Найдено {len(review_matches)} свежих отзыва без ответа компании.",
            confidence=0.8,
            now=current,
        ))

    network_rule = rules.get("multi_location_profile_inconsistency")
    locations = int(context.get("location_count") or context.get("network_locations_count") or 0)
    inconsistencies = context.get("verified_profile_inconsistencies")
    if network_rule and locations >= 2 and isinstance(inconsistencies, list) and inconsistencies:
        evidence = [item for item in inconsistencies if isinstance(item, dict) and item.get("source_url")]
        if evidence:
            results.append(_result(
                network_rule,
                evidence,
                observed_fact=(
                    f"У {locations} точек подтверждено {len(evidence)} расхождения в публичных карточках."
                ),
                confidence=0.85,
                now=current,
            ))

    return sorted(results, key=lambda item: float(item.get("confidence") or 0), reverse=True)
