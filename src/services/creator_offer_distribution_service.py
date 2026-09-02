from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from psycopg2.extras import Json


RECIPIENT_STATUSES = {
    "pending_account", "available", "interested", "needs_details",
    "declined", "selected", "not_selected", "expired",
}
BUSINESS_DISPOSITIONS = {"available", "shortlisted", "excluded"}


def distribution_enabled(business_id: str | None = None) -> bool:
    enabled = str(os.getenv("CREATOR_OFFER_DISTRIBUTION_ENABLED") or "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not enabled:
        return False
    allowed = {
        item.strip()
        for item in str(os.getenv("CREATOR_OFFER_DISTRIBUTION_BUSINESS_IDS") or "").split(",")
        if item.strip()
    }
    return not allowed or business_id is None or business_id in allowed


def _dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return fallback


def _ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def _text_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _normalized(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def _matches(value: Any, candidates: list[str]) -> bool:
    haystack = _normalized(value)
    return any(_normalized(candidate) in haystack or haystack in _normalized(candidate) for candidate in candidates if haystack)


def set_business_disposition(
    cursor: Any,
    *,
    business_id: str,
    profile_id: str,
    disposition: str,
    reason: str | None,
    user_id: str,
) -> dict[str, Any]:
    if disposition not in BUSINESS_DISPOSITIONS:
        raise ValueError("Недопустимая отметка автора")
    cursor.execute("SELECT id FROM creator_profiles WHERE id = %s", (profile_id,))
    if not cursor.fetchone():
        raise LookupError("Автор не найден")
    cursor.execute(
        """
        INSERT INTO creator_business_preferences (
            id, business_id, creator_profile_id, disposition, reason, updated_by
        ) VALUES (%s, %s, %s, %s, %s, NULLIF(%s, ''))
        ON CONFLICT (business_id, creator_profile_id) DO UPDATE SET
            disposition = EXCLUDED.disposition,
            reason = EXCLUDED.reason,
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
        RETURNING disposition, reason, updated_at
        """,
        (str(uuid.uuid4()), business_id, profile_id, disposition, reason, user_id),
    )
    return _ready(_dict(cursor.fetchone()))


def list_catalog(
    cursor: Any,
    *,
    business_id: str,
    filters: dict[str, Any],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    conditions = ["profile.verification_status <> 'rejected'", "profile.brand_safety_status <> 'blocked'"]
    params: list[Any] = [business_id]
    mappings = {
        "city": "COALESCE(taxonomy.home_city, profile.primary_city, '') ILIKE %s",
        "district": "(COALESCE(taxonomy.home_district, profile.primary_area, '') ILIKE %s OR taxonomy.content_geographies_json::text ILIKE %s)",
        "metro": "taxonomy.metro_stations_json::text ILIKE %s",
        "audience_geography": "taxonomy.audience_geography_json::text ILIKE %s",
        "topic": "(profile.topics_json::text ILIKE %s OR COALESCE(taxonomy.primary_topic, '') ILIKE %s OR taxonomy.secondary_topics_json::text ILIKE %s)",
        "format": "(commercial.formats_json::text ILIKE %s OR taxonomy.observed_formats_json::text ILIKE %s OR taxonomy.confirmed_formats_json::text ILIKE %s)",
        "audience_size_band": "taxonomy.audience_size_band = %s",
    }
    for key, sql in mappings.items():
        value = str(filters.get(key) or "").strip()
        if not value:
            continue
        conditions.append(sql)
        parameter = value if key == "audience_size_band" else f"%{value}%"
        params.extend([parameter] * sql.count("%s"))
    platform = str(filters.get("platform") or "").strip()
    if platform:
        conditions.append("EXISTS (SELECT 1 FROM creator_channels platform_channel WHERE platform_channel.creator_profile_id = profile.id AND platform_channel.platform = %s)")
        params.append(platform)
    if str(filters.get("barter") or "").lower() in {"1", "true", "yes", "on"}:
        conditions.append("commercial.accepts_barter IS TRUE")
    if str(filters.get("contactable") or "").lower() in {"1", "true", "yes", "on"}:
        conditions.append(
            "NULLIF(commercial.preferred_contact, '') IS NOT NULL "
            "AND commercial.confirmation_status IN ('creator_confirmed', 'business_confirmed')"
        )
    disposition = str(filters.get("disposition") or "").strip()
    if disposition:
        if disposition not in BUSINESS_DISPOSITIONS:
            raise ValueError("Недопустимый фильтр")
        conditions.append("COALESCE(preference.disposition, 'available') = %s")
        params.append(disposition)
    search = str(filters.get("query") or "").strip()
    if search:
        conditions.append("(profile.display_name ILIKE %s OR COALESCE(profile.description, '') ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    where_clause = " AND ".join(conditions)
    cursor.execute(
        f"""
        SELECT COUNT(*) AS count
        FROM creator_profiles profile
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN creator_business_preferences preference
          ON preference.creator_profile_id = profile.id AND preference.business_id = %s
        WHERE {where_clause}
        """,
        tuple(params),
    )
    total = int(_dict(cursor.fetchone()).get("count") or 0)
    page_params = [*params, limit, offset]
    cursor.execute(
        f"""
        SELECT profile.id, profile.display_name, profile.description, profile.profile_type,
               COALESCE(taxonomy.home_city, profile.primary_city) AS city,
               COALESCE(taxonomy.home_district, profile.primary_area) AS area,
               taxonomy.metro_stations_json, taxonomy.content_geographies_json,
               taxonomy.audience_geography_json, taxonomy.audience_size_band,
               taxonomy.primary_topic, taxonomy.secondary_topics_json,
               taxonomy.content_styles_json, profile.topics_json,
               commercial.formats_json, commercial.accepts_barter,
               COALESCE(preference.disposition, 'available') AS disposition,
               preference.reason AS disposition_reason,
               account.status AS account_status,
               channel.platform, channel.canonical_url AS public_url,
               channel.public_metrics_json,
               COALESCE(platforms.items, '[]'::jsonb) AS platforms_json
        FROM creator_profiles profile
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN creator_business_preferences preference
          ON preference.creator_profile_id = profile.id AND preference.business_id = %s
        LEFT JOIN creator_accounts account ON account.creator_profile_id = profile.id
        LEFT JOIN LATERAL (
            SELECT item.platform, item.canonical_url, item.public_metrics_json
            FROM creator_channels item WHERE item.creator_profile_id = profile.id
            ORDER BY CASE item.verification_status WHEN 'verified' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
                     item.last_observed_at DESC NULLS LAST LIMIT 1
        ) channel ON TRUE
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(DISTINCT item.platform) AS items
            FROM creator_channels item WHERE item.creator_profile_id = profile.id
        ) platforms ON TRUE
        WHERE {where_clause}
        ORDER BY CASE COALESCE(preference.disposition, 'available')
                    WHEN 'shortlisted' THEN 0 WHEN 'available' THEN 1 ELSE 2 END,
                 profile.updated_at DESC, profile.id
        LIMIT %s OFFSET %s
        """,
        tuple(page_params),
    )
    items: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        item = _dict(row)
        topics = [
            *_text_list(_json(item.pop("topics_json", None), [])),
            str(item.get("primary_topic") or "").strip(),
            *_text_list(_json(item.pop("secondary_topics_json", None), [])),
        ]
        metrics = _json(item.pop("public_metrics_json", None), {})
        audience_count = next((int(metrics[key]) for key in ("followers", "subscribers", "members", "audience") if metrics.get(key)), None)
        item.update({
            "result_id": str(item["id"]),
            "shortlist_status": "shortlisted" if item.get("disposition") == "shortlisted" else "rejected" if item.get("disposition") == "excluded" else "suggested",
            "topics": sorted({value for value in topics if value}),
            "content_styles": _json(item.pop("content_styles_json", None), []),
            "formats": _json(item.pop("formats_json", None), []),
            "metro_stations": _json(item.pop("metro_stations_json", None), []),
            "content_geographies": _json(item.pop("content_geographies_json", None), []),
            "audience_geography": _json(item.pop("audience_geography_json", None), []),
            "platforms": _json(item.pop("platforms_json", None), []),
            "audience_count": audience_count,
        })
        items.append(_ready(item))
    cursor.execute(
        """
        SELECT COALESCE(preference.disposition, 'available') AS disposition, COUNT(*) AS count
        FROM creator_profiles profile
        LEFT JOIN creator_business_preferences preference
          ON preference.creator_profile_id = profile.id AND preference.business_id = %s
        WHERE profile.verification_status <> 'rejected' AND profile.brand_safety_status <> 'blocked'
        GROUP BY COALESCE(preference.disposition, 'available')
        """,
        (business_id,),
    )
    counts = {str(row["disposition"]): int(row["count"]) for row in cursor.fetchall()}
    return {
        "creators": items,
        "counts": {"total": total, "returned": len(items), "shortlisted": counts.get("shortlisted", 0), "excluded": counts.get("excluded", 0)},
        "cursor": str(offset + len(items)) if offset + len(items) < total else None,
    }


def _load_campaign(cursor: Any, business_id: str, campaign_id: str, lock: bool = False) -> dict[str, Any]:
    suffix = " FOR UPDATE" if lock else ""
    cursor.execute(
        f"SELECT campaign.*, business.name AS business_name, business.city AS business_city, business.address AS business_address FROM creator_campaigns campaign JOIN businesses business ON business.id = campaign.business_id WHERE campaign.id = %s AND campaign.business_id = %s{suffix}",
        (campaign_id, business_id),
    )
    campaign = _dict(cursor.fetchone())
    if not campaign:
        raise LookupError("Предложение не найдено")
    for key in ("audience_json", "geography_json", "formats_json", "offer_json", "budget_json", "period_json", "constraints_json"):
        campaign[key.removesuffix("_json")] = _json(campaign.pop(key, None), [] if key == "formats_json" else {})
    return campaign


def validate_offer(campaign: dict[str, Any]) -> None:
    geography = _json(campaign.get("geography"), {})
    offer = _json(campaign.get("offer"), {})
    period = _json(campaign.get("period"), {})
    required = {
        "услуга": offer.get("service"),
        "выгода автору": offer.get("benefit") or offer.get("reward"),
        "география": geography.get("city") or geography.get("cities"),
        "срок окончания": period.get("end_at"),
        "количество мест": offer.get("capacity"),
    }
    missing = [label for label, value in required.items() if not value]
    if missing:
        raise ValueError(f"Заполните: {', '.join(missing)}")
    try:
        if int(offer.get("capacity")) < 1:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Количество мест должно быть больше нуля") from None
    try:
        end_at = datetime.fromisoformat(str(period.get("end_at")).replace("Z", "+00:00"))
        if end_at.tzinfo is None:
            end_at = end_at.replace(tzinfo=timezone.utc)
        if end_at <= datetime.now(timezone.utc):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Срок окончания должен быть корректной будущей датой") from None


def submit_offer(cursor: Any, *, business_id: str, campaign_id: str) -> dict[str, Any]:
    campaign = _load_campaign(cursor, business_id, campaign_id, lock=True)
    if campaign.get("distribution_locked_at"):
        raise ValueError("Запущенное предложение нельзя изменить; создайте новое")
    validate_offer(campaign)
    cursor.execute(
        "UPDATE creator_campaigns SET status = 'needs_review', approved_terms_version = NULL, reviewed_by = NULL, reviewed_at = NULL, updated_at = NOW() WHERE id = %s",
        (campaign_id,),
    )
    return {"campaign_id": campaign_id, "status": "needs_review", "external_messages_sent": 0}


def _candidate_rows(
    cursor: Any,
    business_id: str,
    *,
    after_profile_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    page_condition = "AND profile.id > %s" if after_profile_id else ""
    page_limit = "LIMIT %s" if limit else ""
    params: list[Any] = [business_id]
    if after_profile_id:
        params.append(after_profile_id)
    if limit:
        params.append(limit)
    cursor.execute(
        f"""
        SELECT profile.id, profile.brand_safety_status,
               COALESCE(taxonomy.home_city, profile.primary_city) AS city,
               COALESCE(taxonomy.home_district, profile.primary_area) AS district,
               profile.topics_json, taxonomy.primary_topic, taxonomy.secondary_topics_json,
               taxonomy.metro_stations_json, taxonomy.content_geographies_json,
               taxonomy.audience_geography_json, taxonomy.observed_formats_json,
               taxonomy.confirmed_formats_json, commercial.formats_json,
               commercial.accepts_barter,
               COALESCE(business_preference.disposition, 'available') AS disposition,
               account.id AS account_id, account.status AS account_status,
               account.telegram_id, account.email, account.email_verified_at,
               account.notification_preferences_json,
               offer_preference.paused_until, offer_preference.paused_indefinitely,
               offer_preference.excluded_categories_json
        FROM creator_profiles profile
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN creator_commercial_profiles commercial ON commercial.creator_profile_id = profile.id
        LEFT JOIN creator_business_preferences business_preference
          ON business_preference.creator_profile_id = profile.id AND business_preference.business_id = %s
        LEFT JOIN creator_accounts account ON account.creator_profile_id = profile.id
        LEFT JOIN creator_offer_preferences offer_preference ON offer_preference.creator_profile_id = profile.id
        WHERE profile.verification_status <> 'rejected'
          {page_condition}
        ORDER BY profile.id
        {page_limit}
        """,
        tuple(params),
    )
    return [_dict(row) for row in cursor.fetchall()]


def _eligibility(candidate: dict[str, Any], campaign: dict[str, Any]) -> tuple[str | None, dict[str, Any]]:
    geography = _json(campaign.get("geography"), {})
    audience = _json(campaign.get("audience"), {})
    offer = _json(campaign.get("offer"), {})
    target_cities = _text_list(geography.get("cities")) or _text_list(geography.get("city"))
    target_districts = [*_text_list(geography.get("districts")), *_text_list(geography.get("areas")), *_text_list(geography.get("area"))]
    target_metros = _text_list(geography.get("metros")) or _text_list(geography.get("metro"))
    candidate_geography = [
        str(candidate.get("city") or ""), str(candidate.get("district") or ""),
        *_text_list(_json(candidate.get("metro_stations_json"), [])),
        *_text_list(_json(candidate.get("content_geographies_json"), [])),
        *_text_list(_json(candidate.get("audience_geography_json"), [])),
    ]
    target_topics = _text_list(audience.get("topics")) or _text_list(campaign.get("topics"))
    candidate_topics = [
        *_text_list(_json(candidate.get("topics_json"), [])),
        str(candidate.get("primary_topic") or ""),
        *_text_list(_json(candidate.get("secondary_topics_json"), [])),
    ]
    desired_formats = _text_list(campaign.get("formats"))
    candidate_formats = [
        *_text_list(_json(candidate.get("formats_json"), [])),
        *_text_list(_json(candidate.get("observed_formats_json"), [])),
        *_text_list(_json(candidate.get("confirmed_formats_json"), [])),
    ]
    category = str(offer.get("category") or offer.get("service") or "").strip()
    excluded_categories = _text_list(_json(candidate.get("excluded_categories_json"), []))
    now = datetime.now(timezone.utc)
    reason = None
    if candidate.get("brand_safety_status") == "blocked":
        reason = "brand_safety"
    elif candidate.get("disposition") == "excluded":
        reason = "excluded_for_business"
    elif candidate.get("paused_indefinitely") or (candidate.get("paused_until") and candidate["paused_until"] > now):
        reason = "creator_paused"
    elif category and any(_matches(category, [item]) for item in excluded_categories):
        reason = "category_blocked"
    elif not any(str(item).strip() for item in candidate_geography):
        reason = "geography_unknown"
    elif target_cities and not any(_matches(item, target_cities) for item in candidate_geography):
        reason = "geography_mismatch"
    elif target_districts and not any(_matches(item, target_districts) for item in candidate_geography):
        reason = "geography_mismatch"
    elif target_metros and not any(_matches(item, target_metros) for item in candidate_geography):
        reason = "geography_mismatch"
    elif target_topics and not any(_matches(item, target_topics) for item in candidate_topics):
        reason = "topic_mismatch"
    elif offer.get("barter") is True and candidate.get("accepts_barter") is not True:
        reason = "barter_unconfirmed"
    elif desired_formats and candidate_formats and not any(_matches(item, desired_formats) for item in candidate_formats):
        reason = "format_mismatch"
    return reason, {
        "geography": candidate_geography,
        "topics": candidate_topics,
        "formats": candidate_formats,
        "disposition": candidate.get("disposition"),
        "account_active": candidate.get("account_status") == "active",
    }


def distribution_preview(cursor: Any, *, business_id: str, campaign_id: str, include_rows: bool = False) -> dict[str, Any]:
    campaign = _load_campaign(cursor, business_id, campaign_id)
    validate_offer(campaign)
    reasons: dict[str, int] = {}
    eligible: list[dict[str, Any]] = []
    active_accounts = 0
    pending_accounts = 0
    shortlisted = 0
    for candidate in _candidate_rows(cursor, business_id):
        reason, snapshot = _eligibility(candidate, campaign)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            continue
        candidate["match_snapshot"] = snapshot
        eligible.append(candidate)
        if candidate.get("account_status") == "active":
            active_accounts += 1
        else:
            pending_accounts += 1
        if candidate.get("disposition") == "shortlisted":
            shortlisted += 1
    result: dict[str, Any] = {
        "campaign_id": campaign_id,
        "terms_version": int(campaign.get("terms_version") or 1),
        "eligible": len(eligible),
        "active_accounts": active_accounts,
        "pending_accounts": pending_accounts,
        "shortlisted": shortlisted,
        "excluded": sum(reasons.values()),
        "excluded_reasons": reasons,
    }
    if include_rows:
        result["rows"] = eligible
        result["campaign"] = campaign
    return result


def _offer_snapshot(campaign: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": campaign.get("title"), "goal": campaign.get("goal"),
        "offer": campaign.get("offer"), "period": campaign.get("period"),
        "formats": campaign.get("formats"), "constraints": campaign.get("constraints"),
        "geography": campaign.get("geography"), "audience": campaign.get("audience"),
        "business_name": campaign.get("business_name"), "city": campaign.get("business_city"),
        "address": campaign.get("business_address"),
    }


def _queue_channels(cursor: Any, recipient_id: str, campaign: dict[str, Any], candidate: dict[str, Any]) -> int:
    preferences = _json(candidate.get("notification_preferences_json"), {})
    queued = 0
    portal_url = f"{str(os.getenv('PUBLIC_BASE_URL') or os.getenv('FRONTEND_URL') or 'https://localos.pro').rstrip('/')}/creator/offers/{recipient_id}"
    channels = []
    if candidate.get("telegram_id") and preferences.get("telegram", True):
        channels.append("telegram")
    if candidate.get("email") and candidate.get("email_verified_at") and preferences.get("email", True):
        channels.append("email")
    for channel in channels:
        cursor.execute(
            """
            INSERT INTO creator_notification_outbox (
                id, creator_account_id, offer_recipient_id, channel, event_type,
                payload_json, dedupe_key
            ) VALUES (%s, %s, %s, %s, 'offer_available', %s, %s)
            ON CONFLICT (dedupe_key) DO NOTHING
            """,
            (str(uuid.uuid4()), candidate["account_id"], recipient_id, channel,
             Json({"portal_url": portal_url}),
             f"offer-available:{recipient_id}:{channel}:{campaign.get('terms_version')}"),
        )
        queued += cursor.rowcount
    return queued


def approve_and_distribute(
    cursor: Any,
    *,
    business_id: str,
    campaign_id: str,
    reviewer_id: str,
) -> dict[str, Any]:
    campaign = _load_campaign(cursor, business_id, campaign_id, lock=True)
    if campaign.get("status") != "needs_review":
        raise ValueError("Предложение не ожидает проверки LocalOS")
    preview = distribution_preview(cursor, business_id=business_id, campaign_id=campaign_id)
    cursor.execute(
        "SELECT id, status, counts_json FROM creator_offer_distribution_runs WHERE campaign_id = %s AND terms_version = %s",
        (campaign_id, campaign["terms_version"]),
    )
    existing = _dict(cursor.fetchone())
    if existing:
        return {"run_id": str(existing["id"]), "status": existing["status"], "counts": _json(existing.get("counts_json"), {})}
    run_id = str(uuid.uuid4())
    counts = {key: value for key, value in preview.items() if key not in {"rows", "campaign"}}
    cursor.execute(
        """
        INSERT INTO creator_offer_distribution_runs (
            id, campaign_id, terms_version, status, filters_snapshot_json,
            counts_json, progress_json, created_by
        ) VALUES (%s, %s, %s, 'queued', %s, %s, '{}'::jsonb, NULLIF(%s, ''))
        """,
        (run_id, campaign_id, campaign["terms_version"],
         Json({"geography": campaign["geography"], "audience": campaign["audience"], "formats": campaign["formats"], "offer": campaign["offer"]}),
         Json(counts), reviewer_id),
    )
    cursor.execute(
        """
        UPDATE creator_campaigns SET status = 'approved', approved_terms_version = terms_version,
            approved_at = NOW(), reviewed_by = NULLIF(%s, ''), reviewed_at = NOW(),
            distribution_locked_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (reviewer_id, campaign_id),
    )
    return {"run_id": run_id, "status": "queued", "counts": counts}


def process_next_distribution_run(cursor: Any, *, batch_size: int = 500) -> dict[str, Any]:
    """Materialize one approved offer in resumable batches.

    Recipients are idempotent per campaign/profile. Notifications are created only
    after the complete audience has been materialized and the campaign is active.
    """
    cursor.execute(
        """
        SELECT run.*, campaign.business_id
        FROM creator_offer_distribution_runs run
        JOIN creator_campaigns campaign ON campaign.id = run.campaign_id
        WHERE run.status IN ('queued', 'running', 'failed')
        ORDER BY CASE run.status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 ELSE 2 END,
                 run.created_at
        FOR UPDATE OF run SKIP LOCKED
        LIMIT 1
        """
    )
    run = _dict(cursor.fetchone())
    if not run:
        return {"processed": 0}
    run_id = str(run["id"])
    cursor.execute("SAVEPOINT creator_distribution_batch")
    try:
        cursor.execute(
            "UPDATE creator_offer_distribution_runs SET status = 'running', started_at = COALESCE(started_at, NOW()), error_json = '{}'::jsonb, updated_at = NOW() WHERE id = %s",
            (run_id,),
        )
        campaign = _load_campaign(cursor, str(run["business_id"]), str(run["campaign_id"]))
        progress = _json(run.get("progress_json"), {})
        counts = _json(run.get("counts_json"), {})
        last_profile_id = str(progress.get("last_profile_id") or "") or None
        rows = _candidate_rows(
            cursor,
            str(run["business_id"]),
            after_profile_id=last_profile_id,
            limit=max(1, min(int(batch_size), 1000)),
        )
        actual_reasons = _json(progress.get("excluded_reasons"), {})
        inserted = 0
        snapshot = _offer_snapshot(campaign)
        for candidate in rows:
            reason, match_snapshot = _eligibility(candidate, campaign)
            if reason:
                actual_reasons[reason] = int(actual_reasons.get(reason) or 0) + 1
                continue
            cursor.execute(
                """
                INSERT INTO creator_offer_recipients (
                    id, campaign_id, distribution_run_id, business_id, creator_profile_id,
                    status, terms_version, match_snapshot_json, offer_snapshot_json
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (campaign_id, creator_profile_id) DO NOTHING
                """,
                (str(uuid.uuid4()), campaign["id"], run_id, run["business_id"], candidate["id"],
                 "available" if candidate.get("account_status") == "active" else "pending_account",
                 campaign["terms_version"], Json(match_snapshot), Json(snapshot)),
            )
            inserted += cursor.rowcount
        scanned = int(progress.get("scanned") or 0) + len(rows)
        eligible = int(progress.get("eligible") or 0) + inserted
        progress.update({
            "scanned": scanned,
            "eligible": eligible,
            "excluded_reasons": actual_reasons,
            "last_profile_id": str(rows[-1]["id"]) if rows else last_profile_id,
        })
        if len(rows) >= max(1, min(int(batch_size), 1000)):
            cursor.execute(
                "UPDATE creator_offer_distribution_runs SET progress_json = %s, updated_at = NOW() WHERE id = %s",
                (Json(progress), run_id),
            )
            cursor.execute("RELEASE SAVEPOINT creator_distribution_batch")
            return {"processed": len(rows), "run_id": run_id, "status": "running", "eligible": eligible}

        cursor.execute(
            """
            UPDATE creator_campaigns SET status = 'active', updated_at = NOW()
            WHERE id = %s AND status = 'approved'
            """,
            (campaign["id"],),
        )
        cursor.execute(
            """
            SELECT recipient.id, account.id AS account_id, account.telegram_id, account.email,
                   account.email_verified_at,
                   account.notification_preferences_json
            FROM creator_offer_recipients recipient
            JOIN creator_accounts account ON account.creator_profile_id = recipient.creator_profile_id
            WHERE recipient.distribution_run_id = %s AND recipient.status = 'available'
              AND account.status = 'active'
            """,
            (run_id,),
        )
        notifications = 0
        for account_row in cursor.fetchall():
            candidate = _dict(account_row)
            notifications += _queue_channels(cursor, str(candidate["id"]), campaign, candidate)
        counts.update({
            "actual_eligible": eligible,
            "actual_excluded": sum(int(value or 0) for value in actual_reasons.values()),
            "actual_excluded_reasons": actual_reasons,
            "notifications_queued": notifications,
        })
        cursor.execute(
            """
            UPDATE creator_offer_distribution_runs
            SET status = 'completed', counts_json = %s, progress_json = %s,
                completed_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (Json(counts), Json(progress), run_id),
        )
        cursor.execute("RELEASE SAVEPOINT creator_distribution_batch")
        return {"processed": len(rows), "run_id": run_id, "status": "completed", "eligible": eligible}
    except Exception as exc:
        cursor.execute("ROLLBACK TO SAVEPOINT creator_distribution_batch")
        cursor.execute(
            "UPDATE creator_offer_distribution_runs SET status = 'failed', error_json = %s, updated_at = NOW() WHERE id = %s",
            (Json({"message": str(exc)[:1000]}), run_id),
        )
        cursor.execute("RELEASE SAVEPOINT creator_distribution_batch")
        return {"processed": 0, "run_id": run_id, "status": "failed", "error": str(exc)}


def expire_creator_offers(cursor: Any) -> int:
    cursor.execute(
        """
        UPDATE creator_offer_recipients recipient
        SET status = 'expired', updated_at = NOW()
        FROM creator_campaigns campaign
        WHERE campaign.id = recipient.campaign_id
          AND recipient.distribution_run_id IS NOT NULL
          AND recipient.status IN ('pending_account', 'available', 'interested', 'needs_details')
          AND NULLIF(campaign.period_json->>'end_at', '') IS NOT NULL
          AND (campaign.period_json->>'end_at')::timestamptz <= NOW()
        RETURNING recipient.id
        """
    )
    expired_count = len(cursor.fetchall())
    if expired_count:
        cursor.execute(
            """
            UPDATE creator_notification_outbox outbox
            SET status = 'cancelled', updated_at = NOW()
            FROM creator_offer_recipients recipient
            WHERE recipient.id = outbox.offer_recipient_id
              AND recipient.status = 'expired'
              AND outbox.status IN ('pending', 'failed')
            """
        )
    return expired_count


def activate_pending_offers(cursor: Any, *, profile_id: str, account_id: str) -> int:
    cursor.execute(
        """
        SELECT recipient.id, recipient.campaign_id, campaign.terms_version,
               campaign.title, campaign.goal, campaign.offer_json, campaign.period_json,
               campaign.formats_json, campaign.constraints_json, campaign.geography_json,
               campaign.audience_json, business.name AS business_name,
               business.city AS business_city, business.address AS business_address,
               account.telegram_id, account.email, account.email_verified_at,
               account.notification_preferences_json,
               account.id AS account_id
        FROM creator_offer_recipients recipient
        JOIN creator_campaigns campaign ON campaign.id = recipient.campaign_id
        JOIN businesses business ON business.id = recipient.business_id
        JOIN creator_accounts account ON account.id = %s
        LEFT JOIN creator_offer_preferences preference ON preference.creator_profile_id = recipient.creator_profile_id
        WHERE recipient.creator_profile_id = %s AND recipient.status = 'pending_account'
          AND campaign.status = 'active'
          AND COALESCE(preference.paused_indefinitely, FALSE) = FALSE
          AND (preference.paused_until IS NULL OR preference.paused_until <= NOW())
          AND COALESCE((campaign.period_json->>'end_at')::timestamptz, NOW() + INTERVAL '1 day') > NOW()
        FOR UPDATE OF recipient
        """,
        (account_id, profile_id),
    )
    rows = [_dict(row) for row in cursor.fetchall()]
    for item in rows:
        cursor.execute("UPDATE creator_offer_recipients SET status = 'available', updated_at = NOW() WHERE id = %s", (item["id"],))
        campaign = {
            "terms_version": item["terms_version"], "title": item["title"], "goal": item["goal"],
        }
        _queue_channels(cursor, str(item["id"]), campaign, item)
    return len(rows)


def update_offer_preferences(cursor: Any, *, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("pause_mode") or "active")
    paused_indefinitely = mode == "indefinite"
    paused_until = payload.get("paused_until") if mode == "until" else None
    if mode not in {"active", "until", "indefinite"}:
        raise ValueError("Недопустимый режим паузы")
    categories = _text_list(payload.get("excluded_categories"))
    cursor.execute(
        """
        INSERT INTO creator_offer_preferences (
            creator_profile_id, paused_until, paused_indefinitely, excluded_categories_json
        ) VALUES (%s, %s, %s, %s)
        ON CONFLICT (creator_profile_id) DO UPDATE SET
            paused_until = EXCLUDED.paused_until,
            paused_indefinitely = EXCLUDED.paused_indefinitely,
            excluded_categories_json = EXCLUDED.excluded_categories_json,
            updated_at = NOW()
        RETURNING paused_until, paused_indefinitely, excluded_categories_json
        """,
        (profile_id, paused_until, paused_indefinitely, Json(categories)),
    )
    result = _dict(cursor.fetchone())
    result["excluded_categories"] = _json(result.pop("excluded_categories_json", None), [])
    if mode == "active":
        cursor.execute(
            "SELECT id FROM creator_accounts WHERE creator_profile_id = %s AND status = 'active'",
            (profile_id,),
        )
        account = _dict(cursor.fetchone())
        if account:
            result["activated_offers"] = activate_pending_offers(
                cursor,
                profile_id=profile_id,
                account_id=str(account["id"]),
            )
    return _ready(result)


def select_recipient(
    cursor: Any,
    *,
    business_id: str,
    recipient_id: str,
    user_id: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT recipient.*, campaign.offer_json, campaign.status AS campaign_status
        FROM creator_offer_recipients recipient
        JOIN creator_campaigns campaign ON campaign.id = recipient.campaign_id
        WHERE recipient.id = %s AND recipient.business_id = %s FOR UPDATE OF recipient, campaign
        """,
        (recipient_id, business_id),
    )
    recipient = _dict(cursor.fetchone())
    if not recipient:
        raise LookupError("Отклик не найден")
    if recipient.get("status") != "interested":
        raise ValueError("Выбрать можно только заинтересованного автора")
    offer = _json(recipient.get("offer_json"), {})
    capacity = max(1, int(offer.get("capacity") or 1))
    cursor.execute("SELECT COUNT(*) AS count FROM creator_offer_recipients WHERE campaign_id = %s AND status = 'selected'", (recipient["campaign_id"],))
    selected_count = int(_dict(cursor.fetchone()).get("count") or 0)
    if selected_count >= capacity:
        raise ValueError("Все места уже заполнены")
    candidate_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_campaign_candidates (
            id, campaign_id, creator_profile_id, selection_reason, status
        ) VALUES (%s, %s, %s, 'Выбран LocalOS из откликнувшихся авторов', 'negotiating')
        ON CONFLICT (campaign_id, creator_profile_id) DO UPDATE SET status = 'negotiating', updated_at = NOW()
        RETURNING id
        """,
        (candidate_id, recipient["campaign_id"], recipient["creator_profile_id"]),
    )
    candidate_id = str(_dict(cursor.fetchone())["id"])
    collaboration_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_collaborations (
            id, campaign_id, campaign_candidate_id, business_id, creator_profile_id,
            status, agreed_terms_json, owner_user_id, review_status, reviewed_by, reviewed_at
        ) VALUES (%s, %s, %s, %s, %s, 'negotiating', %s, NULLIF(%s, ''), 'approved', NULLIF(%s, ''), NOW())
        ON CONFLICT (campaign_candidate_id) DO UPDATE SET status = 'negotiating', updated_at = NOW()
        RETURNING id
        """,
        (collaboration_id, recipient["campaign_id"], candidate_id, business_id,
         recipient["creator_profile_id"], Json(_json(recipient.get("offer_snapshot_json"), {})),
         user_id, user_id),
    )
    collaboration_id = str(_dict(cursor.fetchone())["id"])
    cursor.execute(
        "UPDATE creator_offer_recipients SET status = 'selected', selected_at = NOW(), collaboration_id = %s, updated_at = NOW() WHERE id = %s",
        (collaboration_id, recipient_id),
    )
    selected_count += 1
    if selected_count >= capacity:
        cursor.execute(
            "UPDATE creator_offer_recipients SET status = 'not_selected', updated_at = NOW() WHERE campaign_id = %s AND status IN ('pending_account', 'available', 'interested', 'needs_details')",
            (recipient["campaign_id"],),
        )
        cursor.execute(
            """
            UPDATE creator_notification_outbox outbox
            SET status = 'cancelled', updated_at = NOW()
            FROM creator_offer_recipients recipient
            WHERE recipient.id = outbox.offer_recipient_id
              AND recipient.campaign_id = %s
              AND recipient.status = 'not_selected'
              AND outbox.status IN ('pending', 'failed')
            """,
            (recipient["campaign_id"],),
        )
        cursor.execute("UPDATE creator_campaigns SET status = 'completed', updated_at = NOW() WHERE id = %s", (recipient["campaign_id"],))
    return {"recipient_id": recipient_id, "status": "selected", "collaboration_id": collaboration_id, "capacity": capacity, "selected_count": selected_count}


def list_campaign_recipients(
    cursor: Any,
    *,
    business_id: str,
    campaign_id: str,
    is_superadmin: bool,
) -> dict[str, Any]:
    _load_campaign(cursor, business_id, campaign_id)
    cursor.execute(
        """
        SELECT recipient.id, recipient.status, recipient.responded_at, recipient.selected_at,
               recipient.response_text, recipient.collaboration_id,
               profile.id AS creator_profile_id, profile.display_name,
               COALESCE(taxonomy.home_city, profile.primary_city) AS city,
               COALESCE(taxonomy.home_district, profile.primary_area) AS area,
               COALESCE(preference.disposition, 'available') AS disposition
        FROM creator_offer_recipients recipient
        JOIN creator_profiles profile ON profile.id = recipient.creator_profile_id
        LEFT JOIN creator_profile_taxonomy taxonomy ON taxonomy.creator_profile_id = profile.id
        LEFT JOIN creator_business_preferences preference
          ON preference.creator_profile_id = profile.id AND preference.business_id = recipient.business_id
        WHERE recipient.campaign_id = %s AND recipient.business_id = %s
        ORDER BY CASE recipient.status WHEN 'interested' THEN 0 WHEN 'needs_details' THEN 1
                     WHEN 'selected' THEN 2 WHEN 'available' THEN 3 ELSE 4 END,
                 recipient.updated_at DESC
        """,
        (campaign_id, business_id),
    )
    items = []
    counts: dict[str, int] = {}
    for row in cursor.fetchall():
        item = _dict(row)
        status = str(item.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
        if not is_superadmin:
            item.pop("response_text", None)
        items.append(_ready(item))
    return {"items": items, "counts": counts, "total": len(items)}


def add_recipient_message(
    cursor: Any,
    *,
    business_id: str,
    recipient_id: str,
    sender_id: str,
    body: str,
) -> dict[str, Any]:
    text = str(body or "").strip()
    if not text:
        raise ValueError("Напишите сообщение")
    cursor.execute(
        """
        SELECT recipient.id, recipient.status, recipient.creator_profile_id, campaign.terms_version,
               account.id AS account_id, account.telegram_id, account.email,
               account.email_verified_at, account.notification_preferences_json
        FROM creator_offer_recipients recipient
        JOIN creator_campaigns campaign ON campaign.id = recipient.campaign_id
        LEFT JOIN creator_accounts account
          ON account.creator_profile_id = recipient.creator_profile_id AND account.status = 'active'
        WHERE recipient.id = %s AND recipient.business_id = %s
        """,
        (recipient_id, business_id),
    )
    recipient = _dict(cursor.fetchone())
    if not recipient:
        raise LookupError("Отклик не найден")
    if recipient.get("status") in {"declined", "not_selected", "expired"}:
        raise ValueError("Предложение уже закрыто")
    message_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO creator_offer_messages (
            id, offer_recipient_id, sender_type, sender_id, body_text, visible_to_business
        ) VALUES (%s, %s, 'localos', %s, %s, FALSE)
        """,
        (message_id, recipient_id, sender_id, text),
    )
    notifications = 0
    preferences = _json(recipient.get("notification_preferences_json"), {})
    channels = []
    if recipient.get("telegram_id") and preferences.get("telegram", True):
        channels.append("telegram")
    if recipient.get("email") and recipient.get("email_verified_at") and preferences.get("email", True):
        channels.append("email")
    portal_url = f"{str(os.getenv('PUBLIC_BASE_URL') or os.getenv('FRONTEND_URL') or 'https://localos.pro').rstrip('/')}/creator/offers/{recipient_id}"
    for channel in channels:
        cursor.execute(
            """
            INSERT INTO creator_notification_outbox (
                id, creator_account_id, offer_recipient_id, channel, event_type,
                payload_json, dedupe_key
            ) VALUES (%s, %s, %s, %s, 'offer_message', %s, %s)
            ON CONFLICT (dedupe_key) DO NOTHING
            """,
            (str(uuid.uuid4()), recipient["account_id"], recipient_id, channel,
             Json({"portal_url": portal_url, "message": text}),
             f"offer-message:{recipient_id}:{message_id}:{channel}"),
        )
        notifications += cursor.rowcount
    return {"id": message_id, "offer_recipient_id": recipient_id, "body_text": text, "notifications_queued": notifications}
