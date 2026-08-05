"""Compiled corpus patterns and explicitly staged LocalOS outreach experiments.

This module never approves, queues or dispatches a campaign. It only derives
evidence, selects cohorts and prepares versioned drafts through the canonical
campaign service.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json

from services.llm import LLMTaskRequest, run_llm_task


ACTIVE_SOCIAL_MAP_GAP = "active_social_with_map_gap"
PATTERN_TITLE = "Бизнес активно привлекает клиентов, но недоиспользует карты"
STAGES = (
    {"key": "canary_1", "variant": "treatment", "size": 1},
    {"key": "treatment_10_a", "variant": "treatment", "size": 10},
    {"key": "control_10_a", "variant": "control", "size": 10},
    {"key": "treatment_10_b", "variant": "treatment", "size": 10},
    {"key": "control_10_b", "variant": "control", "size": 10},
    {"key": "treatment_50", "variant": "treatment", "size": 50},
    {"key": "treatment_100", "variant": "treatment", "size": 100},
)

SAFE_CORPUS_MESSAGE_RULES = (
    "Назвать конкретную подтверждённую активность официальной соцсети.",
    "Описать состояние карточки на картах только проверяемыми числами или полями аудита.",
    "Отделить предположение о возможности усилить карты от наблюдаемого факта.",
    "Дать ссылку на готовый разбор и оставить один вопрос о просмотре.",
)


def experiments_enabled() -> bool:
    return str(os.getenv("OUTREACH_EXPERIMENTS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def corpus_patterns_enabled() -> bool:
    return str(os.getenv("OUTREACH_CORPUS_PATTERNS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def dedupe_corpus_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact/whitespace duplicates while retaining source provenance."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        content = _text(document.get("content") or document.get("text")).lower()
        if not content:
            continue
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        result.append(document)
    return result


def pattern_support_ready(documents: list[dict[str, Any]]) -> bool:
    unique = dedupe_corpus_documents(documents)
    sources = {
        _text(item.get("source_id") or item.get("source_url") or item.get("channel"))
        for item in unique
        if _text(item.get("source_id") or item.get("source_url") or item.get("channel"))
    }
    return len(unique) >= 3 and len(sources) >= 2


def build_active_social_map_gap_signal(
    map_snapshot: dict[str, Any],
    social_activity: dict[str, Any],
    peer_context: dict[str, Any] | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the first approved composite-signal contract.

    Observations and interpretation are intentionally separate: an active
    social account plus a weak map profile may indicate missed map potential,
    but never proves that the owner lacks time or loses customers.
    """
    current_time = now or datetime.now(timezone.utc)
    peers = peer_context or {}
    rating = float(map_snapshot.get("rating") or 0)
    reviews = int(map_snapshot.get("reviews_count") or 0)
    peer_rating = float(peers.get("median_rating") or 0)
    peer_reviews = int(peers.get("median_reviews_count") or 0)
    incomplete = bool(map_snapshot.get("profile_incomplete"))
    gap_checks = {
        "rating_at_or_below_4_4": bool(rating and rating <= 4.4),
        "reviews_at_or_below_10": reviews <= 10,
        "rating_below_peers": bool(rating and peer_rating and rating <= peer_rating - 0.2),
        "reviews_below_peers": bool(peer_reviews and reviews < peer_reviews),
        "profile_incomplete": incomplete,
    }
    map_gap = sum(1 for passed in gap_checks.values() if passed) >= 2
    last_post_at = _parse_time(social_activity.get("last_post_at"))
    age_days = (current_time - last_post_at).days if last_post_at else None
    posts_30d = int(social_activity.get("posts_30d") or 0)
    posts_90d = int(social_activity.get("posts_90d") or 0)
    social_active = bool(
        social_activity.get("official")
        and age_days is not None
        and age_days <= 30
        and (posts_30d >= 4 or posts_90d >= 8)
    )
    eligible = map_gap and social_active
    observations = [
        f"В карточке на картах рейтинг {rating:.1f} и {reviews} отзывов.",
        (
            f"Официальная соцсеть обновлялась {age_days} дней назад; "
            f"опубликовано {posts_30d} сообщений за 30 дней."
        ) if age_days is not None else "Свежесть официальной соцсети не подтверждена.",
    ]
    return {
        "eligible": eligible,
        "pattern_key": ACTIVE_SOCIAL_MAP_GAP,
        "title": PATTERN_TITLE,
        "kind": "composite_signal",
        "observed_fact": " ".join(observations),
        "hypothesis": (
            "Компания уже вкладывается в привлечение клиентов через контент, "
            "а карточка на картах может использоваться сильнее."
        ),
        "relevance": (
            "LocalOS может показать конкретные шаги по карточке, которые дополнят уже ведущиеся каналы."
        ),
        "map_gap": {"eligible": map_gap, "checks": gap_checks},
        "social_activity": {
            "eligible": social_active,
            "official": bool(social_activity.get("official")),
            "last_post_at": last_post_at.isoformat() if last_post_at else None,
            "posts_30d": posts_30d,
            "posts_90d": posts_90d,
        },
        "source_url": map_snapshot.get("source_url"),
        "source_type": "composite_public_evidence",
        "confidence": 0.9 if eligible else 0.0,
        "freshness": "current_snapshot",
        "usable_for_outreach": eligible,
    }


def derive_composite_signal(context: dict[str, Any], ledger: list[dict[str, Any]]) -> dict[str, Any] | None:
    stored_activity = context.get("official_social_activity")
    if isinstance(stored_activity, dict) and stored_activity.get("last_post_at"):
        signal = build_active_social_map_gap_signal(
            {
                "rating": context.get("rating"),
                "reviews_count": context.get("reviews_count"),
                "profile_incomplete": bool(context.get("profile_incomplete")),
                "source_url": context.get("source_url"),
            },
            stored_activity,
        )
        if signal["eligible"]:
            return {
                "id": f"composite-{ACTIVE_SOCIAL_MAP_GAP}",
                **signal,
                "fact": signal["observed_fact"],
                "status": "observed",
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "pattern_id": None,
                "pattern_version": 1,
                "opening_type": "specific_observation",
                "signal_combo": ACTIVE_SOCIAL_MAP_GAP,
            }
    social_items = [
        item for item in ledger
        if _text(item.get("source_type") or item.get("kind")).lower() in {
            "telegram", "telegram_post", "vk", "vk_post", "instagram", "instagram_post", "social_post", "public_social_post"
        }
        or any(host in _text(item.get("source_url")).lower() for host in ("t.me/", "vk.", "instagram.com/"))
    ]
    if not social_items:
        return None
    dated = [(_parse_time(item.get("observed_at")), item) for item in social_items]
    dated = [item for item in dated if item[0]]
    if not dated:
        return None
    latest_at, latest = max(dated, key=lambda item: item[0])
    now = datetime.now(timezone.utc)
    posts_30d = sum(1 for published, _ in dated if (now - published).days <= 30)
    posts_90d = sum(1 for published, _ in dated if (now - published).days <= 90)
    signal = build_active_social_map_gap_signal(
        {
            "rating": context.get("rating"),
            "reviews_count": context.get("reviews_count"),
            "profile_incomplete": bool(context.get("profile_incomplete")),
            "source_url": context.get("source_url"),
        },
        {
            "official": bool(latest.get("author_or_organization") or latest.get("source_url")),
            "last_post_at": latest_at,
            "posts_30d": posts_30d,
            "posts_90d": posts_90d,
        },
        now=now,
    )
    if not signal["eligible"]:
        return None
    return {
        "id": f"composite-{ACTIVE_SOCIAL_MAP_GAP}",
        **signal,
        "fact": signal["observed_fact"],
        "status": "observed",
        "observed_at": now.isoformat(),
        "pattern_id": None,
        "pattern_version": 1,
        "opening_type": "specific_observation",
        "signal_combo": ACTIVE_SOCIAL_MAP_GAP,
    }


def stage_definition(stage_key: str) -> dict[str, Any]:
    for stage in STAGES:
        if stage["key"] == stage_key:
            return dict(stage)
    raise ValueError("Unknown experiment stage")


def next_stage(stage_key: str) -> str | None:
    keys = [stage["key"] for stage in STAGES]
    index = keys.index(stage_key)
    return keys[index + 1] if index + 1 < len(keys) else None


def compile_pattern_draft(
    cursor: Any,
    documents: list[dict[str, Any]],
    *,
    user_id: str,
    compiler_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    unique = dedupe_corpus_documents(documents)
    if not pattern_support_ready(unique):
        raise ValueError("pattern_support_insufficient")
    sources = sorted({_text(item.get("source_id") or item.get("source_url") or item.get("channel")) for item in unique})
    cursor.execute("SELECT COALESCE(MAX(version), 0) + 1 AS version FROM outreach_knowledge_patterns WHERE pattern_key = %s", (ACTIVE_SOCIAL_MAP_GAP,))
    row = cursor.fetchone()
    version = int((row.get("version") if hasattr(row, "get") else row[0]) or 1)
    pattern_id = str(uuid.uuid4())
    source_refs = [
        {
            "document_id": str(item.get("id") or "") or None,
            "source_id": str(item.get("source_id") or "") or None,
            "source_url": item.get("source_url"),
        }
        for item in unique
    ]
    trigger = {
        "map_gap": {"minimum_checks": 2, "rating_lte": 4.4, "reviews_lte": 10, "rating_peer_delta": -0.2},
        "social_active": {"official_required": True, "freshness_days": 30, "posts_30d_gte": 4, "posts_90d_gte": 8},
        "observation_and_hypothesis_separate": True,
    }
    rules = {
        "opening_type": "specific_observation",
        "bridge": "existing_social_effort_to_map_opportunity",
        "forbidden_claims": ["вам не хватает времени", "вы теряете клиентов", "карты точно дают меньше клиентов"],
        "cta_count": 1,
    }
    if compiler_result:
        review = compiler_result.get("review") if isinstance(compiler_result.get("review"), dict) else {}
        # Model extraction remains available in compiler_result_json for audit,
        # but it never becomes executable copy policy. Corpus authors and model
        # reviewers may suggest unsupported statistics or causal claims.
        rules["corpus_message_rules"] = list(SAFE_CORPUS_MESSAGE_RULES)
        rules["reviewed_safe_rules"] = review.get("safe_message_rules") or []
        rules["compiler_extracted_rules_status"] = "reference_only"
    cursor.execute(
        """
        INSERT INTO outreach_knowledge_patterns (
            id, pattern_key, version, title, pattern_type, status, segment,
            trigger_contract_json, message_rule_json, contraindications_json,
            source_refs_json, support_document_count, support_source_count,
            compiled_by, compiler_result_json, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, 'signal', 'draft', 'beauty', %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        """,
        (
            pattern_id, ACTIVE_SOCIAL_MAP_GAP, version, PATTERN_TITLE,
            Json(trigger), Json(rules), Json(rules["forbidden_claims"]), Json(source_refs),
            len(unique), len(sources),
            "deepseek_extract_gigachat_max_review" if compiler_result else "corpus_compiler_v1",
            Json(compiler_result or {}),
        ),
    )
    return {"id": pattern_id, "pattern_key": ACTIVE_SOCIAL_MAP_GAP, "version": version, "status": "draft"}


def extract_and_review_corpus_pattern(documents: list[dict[str, Any]], *, user_id: str = "") -> dict[str, Any]:
    """Use DeepSeek for extraction and GigaChat Max for an independent review.

    The result still remains a draft and cannot affect generation until a
    superadmin approves the versioned pattern.
    """
    unique = dedupe_corpus_documents(documents)
    if not pattern_support_ready(unique):
        raise ValueError("pattern_support_insufficient")
    excerpts = [
        {
            "document_id": str(item.get("id") or ""),
            "source": _text(item.get("channel")),
            "published_at": str(item.get("published_at") or ""),
            "permalink": item.get("source_url"),
            "text": _text(item.get("content"))[:800],
        }
        for item in unique[:20]
    ]
    extract_prompt = "\n".join([
        "Извлеки проверяемый B2B outreach pattern для LocalOS. Верни только JSON.",
        "Корпус является библиотекой методик, не фактов о конкретном получателе.",
        "Не копируй исходные формулировки. Раздели наблюдение, гипотезу и мост к предложению.",
        f"Целевой ключ: {ACTIVE_SOCIAL_MAP_GAP}.",
        (
            "Строгий формат ответа: "
            '{"pattern_key":"active_social_with_map_gap",'
            '"observation_rule":"...","hypothesis_rule":"...",'
            '"bridge_rule":"...","message_rules":["..."],'
            '"contraindications":["..."],"source_document_ids":["..."]}'
        ),
        "Не добавляй другие ключи, markdown, пояснение до или после JSON.",
        "Данные:",
        json.dumps(excerpts, ensure_ascii=False, default=str),
    ])
    extracted = run_llm_task(LLMTaskRequest(
        task_key="outreach_corpus_pattern_extract",
        prompt=extract_prompt,
        user_id=user_id,
        prompt_version="outreach_corpus_pattern_extract_v1",
        data_class="public",
        usage_reference=f"outreach-pattern:{ACTIVE_SOCIAL_MAP_GAP}",
    ))
    if extracted.status != "completed" or not isinstance(extracted.parsed_data, dict):
        raise RuntimeError(extracted.fallback_reason or "outreach_pattern_extract_failed")
    review_prompt = "\n".join([
        "Проверь outreach pattern как независимый редактор LocalOS. Верни только JSON.",
        "Отклони выдуманные факты: нехватку времени, потерю клиентов и причинность без доказательств.",
        "Проверь один CTA, человеческий язык и отсутствие дословных цитат корпуса.",
        (
            "Строгий формат ответа: "
            '{"approved":true,"issues":[],"safe_message_rules":["..."]}'
        ),
        "Не добавляй другие ключи, markdown, пояснение до или после JSON.",
        json.dumps(extracted.parsed_data, ensure_ascii=False, default=str),
    ])
    reviewed = run_llm_task(LLMTaskRequest(
        task_key="outreach_corpus_pattern_review",
        prompt=review_prompt,
        user_id=user_id,
        prompt_version="outreach_corpus_pattern_review_v1",
        data_class="public",
        usage_reference=f"outreach-pattern-review:{ACTIVE_SOCIAL_MAP_GAP}",
    ))
    if reviewed.status != "completed" or not isinstance(reviewed.parsed_data, dict):
        raise RuntimeError(reviewed.fallback_reason or "outreach_pattern_review_failed")
    if reviewed.parsed_data.get("approved") is not True:
        raise ValueError("outreach_pattern_review_rejected")
    return {
        "extracted": extracted.parsed_data,
        "review": reviewed.parsed_data,
        "providers": {"extract": extracted.provider, "review": reviewed.provider},
    }


def default_experiment_policy() -> dict[str, Any]:
    return {
        "stages": list(STAGES),
        "daily_send_cap": 10,
        "automatic_stage_advancement": False,
        "automatic_approval": False,
        "automatic_dispatch": False,
        "no_reply_window_days": 14,
        "sender_email": "localosgo@gmail.com",
        "offer": {"amount_rub_month": 1200, "status": "approved"},
    }


def list_experiments(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT experiment.*,
               COUNT(member.id) AS member_count,
               COUNT(member.id) FILTER (WHERE member.status = 'draft') AS draft_count,
               COUNT(member.id) FILTER (WHERE member.status IN ('approved', 'active', 'completed')) AS reviewed_count
        FROM outreach_experiments experiment
        LEFT JOIN outreach_experiment_members member ON member.experiment_id = experiment.id
        WHERE experiment.scope_type = 'platform'
        GROUP BY experiment.id
        ORDER BY experiment.updated_at DESC
        """
    )
    return [dict(row) for row in cursor.fetchall()]


def create_beauty_experiment(cursor: Any, *, user_id: str) -> dict[str, Any]:
    experiment_id = str(uuid.uuid4())
    experiment_key = f"beauty-map-social-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    hypothesis = {
        "treatment": PATTERN_TITLE,
        "control": "Слабая карточка на картах без подтверждённой активности официальной соцсети",
        "primary_metric": "positive_reply_rate",
        "safety_metrics": ["hard_no_rate", "unsubscribe_rate", "complaint_rate"],
    }
    cursor.execute(
        """
        INSERT INTO outreach_experiments (
            id, experiment_key, title, scope_type, workstream_type, segment,
            hypothesis_json, policy_json, status, current_stage, created_by,
            created_at, updated_at
        ) VALUES (%s, %s, %s, 'platform', 'localos_sales', 'beauty', %s, %s,
                  'draft', 'canary_1', %s, NOW(), NOW())
        """,
        (
            experiment_id,
            experiment_key,
            "Проверка сигнала: соцсети работают, карты недоиспользуются",
            Json(hypothesis),
            Json(default_experiment_policy()),
            user_id,
        ),
    )
    return {"id": experiment_id, "experiment_key": experiment_key, "status": "draft", "current_stage": "canary_1"}


def _candidate_ledger(evidence: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in (evidence or []) if isinstance(item, dict)]


def select_stage_candidates(cursor: Any, experiment_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM outreach_experiments WHERE id = %s", (experiment_id,))
    experiment = dict(cursor.fetchone() or {})
    if not experiment:
        raise LookupError("Experiment not found")
    stage = stage_definition(str(experiment["current_stage"]))
    cursor.execute(
        """
        SELECT workstream.id AS workstream_id, lead.id AS lead_id, lead.name,
               lead.category, lead.rating, lead.reviews_count, lead.source_url,
               research.evidence_json, research.researched_at,
               social.last_post_at, social.posts_30d, social.posts_90d,
               EXISTS (
                   SELECT 1 FROM outreach_campaigns existing_draft
                   WHERE existing_draft.workstream_id = workstream.id
                     AND existing_draft.status = 'draft'
               ) AS has_existing_draft,
               EXISTS (
                   SELECT 1 FROM lead_contact_points contact
                   WHERE contact.lead_id = lead.id
                     AND contact.verification_status NOT IN ('invalid', 'stale')
               ) AS has_contact
        FROM lead_workstreams workstream
        JOIN prospectingleads lead ON lead.id = workstream.lead_id
        LEFT JOIN LATERAL (
            SELECT evidence_json, researched_at
            FROM lead_workstream_research
            WHERE workstream_id = workstream.id
            ORDER BY researched_at DESC, created_at DESC
            LIMIT 1
        ) research ON TRUE
        LEFT JOIN LATERAL (
            SELECT MAX(document.published_at) AS last_post_at,
                   COUNT(*) FILTER (WHERE document.published_at >= NOW() - INTERVAL '30 days') AS posts_30d,
                   COUNT(*) FILTER (WHERE document.published_at >= NOW() - INTERVAL '90 days') AS posts_90d
            FROM lead_signal_links link
            JOIN knowledge_sources source ON source.id::text = link.source_id
            JOIN knowledge_documents document
              ON document.source_id = source.id AND document.invalidated_at IS NULL
            WHERE link.workstream_id = workstream.id
              AND link.source_type = 'telegram_knowledge_source'
              AND link.status = 'selected'
              AND source.status = 'active'
              AND source.visibility = 'public'
              AND document.document_type = 'telegram_message'
        ) social ON TRUE
        WHERE workstream.workstream_type = 'localos_sales'
          AND COALESCE(workstream.lifecycle_status, 'active') NOT IN ('closed', 'excluded', 'suppressed', 'replied')
          AND (
              lead.category ILIKE ANY(ARRAY['%салон красот%', '%косметолог%', '%парикмахер%', '%beauty%', '%маникюр%', '%бров%'])
          )
          AND NOT EXISTS (
              SELECT 1 FROM outreach_experiment_members member
              WHERE member.experiment_id = %s AND member.workstream_id = workstream.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM outreach_campaigns campaign
              WHERE campaign.workstream_id = workstream.id
                AND campaign.status IN ('approved', 'active', 'paused')
          )
        ORDER BY has_existing_draft DESC,
                 lead.rating ASC NULLS LAST,
                 lead.reviews_count ASC NULLS LAST,
                 lead.name
        LIMIT 500
        """,
        (experiment_id,),
    )
    candidates: list[dict[str, Any]] = []
    for raw in cursor.fetchall():
        row = dict(raw)
        row["official_social_activity"] = {
            "official": bool(row.get("last_post_at")),
            "last_post_at": row.get("last_post_at"),
            "posts_30d": row.get("posts_30d"),
            "posts_90d": row.get("posts_90d"),
        }
        ledger = _candidate_ledger(row.get("evidence_json"))
        signal = derive_composite_signal(row, ledger)
        map_gap = sum((
            bool(row.get("rating") and float(row["rating"]) <= 4.4),
            int(row.get("reviews_count") or 0) <= 10,
        )) >= 2
        treatment = signal is not None
        eligible = treatment if stage["variant"] == "treatment" else map_gap and not treatment
        reasons = []
        if not row.get("has_contact"):
            reasons.append("needs_contact")
        if not row.get("source_url"):
            reasons.append("needs_audit_link")
        if not eligible:
            reasons.append("variant_signal_mismatch")
        if reasons:
            continue
        candidates.append({
            "workstream_id": str(row["workstream_id"]),
            "lead_id": str(row["lead_id"]),
            "name": row.get("name"),
            "variant": stage["variant"],
            "cohort": stage["key"],
            "signal": signal,
        })
        if len(candidates) >= int(stage["size"]):
            break
    return {"experiment": experiment, "stage": stage, "candidates": candidates, "requested": stage["size"], "ready": len(candidates)}


def assign_experiment_member(
    cursor: Any,
    *,
    experiment_id: str,
    workstream_id: str,
    campaign_id: str,
    cohort: str,
    variant: str,
    pattern: dict[str, Any] | None,
) -> str:
    member_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO outreach_experiment_members (
            id, experiment_id, workstream_id, campaign_id, cohort, variant,
            pattern_id, pattern_version, status, assigned_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft', NOW(), NOW())
        ON CONFLICT (experiment_id, workstream_id) DO UPDATE
        SET campaign_id = EXCLUDED.campaign_id, cohort = EXCLUDED.cohort,
            variant = EXCLUDED.variant, pattern_id = EXCLUDED.pattern_id,
            pattern_version = EXCLUDED.pattern_version, status = 'draft', updated_at = NOW()
        RETURNING id
        """,
        (
            member_id, experiment_id, workstream_id, campaign_id, cohort, variant,
            pattern.get("id") if pattern else None,
            pattern.get("version") if pattern else None,
        ),
    )
    row = cursor.fetchone()
    return str((row.get("id") if hasattr(row, "get") else row[0]) or member_id)
