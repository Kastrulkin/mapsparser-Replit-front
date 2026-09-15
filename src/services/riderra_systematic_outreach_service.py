"""Prepare exact Riderra buyer batches from the saved CRM lead pool."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo

from psycopg2.extras import Json

from services.agent_google_sheets_adapter import load_google_sheets_read_adapter
from services.outreach_campaign_service import (
    approve_campaign_by_riderra_template,
    build_riderra_template_preview,
    persist_preview,
)
from services.outreach_safety_service import research_source_fact_fingerprint
from services.riderra_template_authorization_service import (
    AUTHORIZATION_REFERENCE,
    BUSINESS_ID,
    DAILY_LIMIT,
    PRICEBOOK_ID,
    PRICEBOOK_PROVIDER,
    PRICEBOOK_SHEET,
    SENDER_ACCOUNT_ID,
    _hash,
    canonical_currency_price,
    load_standing_authorization,
    record_pricebook_attestation,
    render_record,
    set_authorization,
)


PRICEBOOK_RANGE = f"'{PRICEBOOK_SHEET}'!A1:G2500"
ELIGIBLE_CONTACT_STATUSES = {"verified", "confirmed_source"}
TERMINAL_LEAD_STATES = {"disqualified", "lost", "do_not_contact", "suppressed", "archived"}


def _dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        return dict(row)
    return {}


def _city_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.casefold()).strip()


def _artifact_bytes(values: list[list[Any]], observed_at: datetime) -> bytes:
    ranges: list[dict[str, Any]] = []
    for row_number, values_row in enumerate(values, start=1):
        row = list(values_row[:7])
        if len(row) < 7:
            row.extend([""] * (7 - len(row)))
        if not any(str(value or "").strip() for value in row):
            continue
        ranges.append({"range": f"'{PRICEBOOK_SHEET}'!A{row_number}:G{row_number}", "values": [row]})
    artifact = {
        "spreadsheet_id": PRICEBOOK_ID,
        "sheet": PRICEBOOK_SHEET,
        "evidence_kind": "provider_observed",
        "provider": PRICEBOOK_PROVIDER,
        "verified_at": observed_at.astimezone(timezone.utc).isoformat(),
        "ranges": ranges,
    }
    return json.dumps(artifact, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def refresh_pricebook_attestation(cursor: Any, *, actor_id: str, now: datetime | None = None) -> dict[str, Any]:
    adapter = load_google_sheets_read_adapter(cursor, business_id=BUSINESS_ID)
    values = adapter.read_range_values(
        PRICEBOOK_ID,
        PRICEBOOK_RANGE,
        value_render_option="FORMATTED_VALUE",
    )
    artifact = _artifact_bytes(values, now or datetime.now(timezone.utc))
    return record_pricebook_attestation(
        cursor,
        actor_id=actor_id,
        artifact_bytes=artifact,
        evidence_reference=f"automatic:{PRICEBOOK_ID}:{PRICEBOOK_SHEET}",
    )


def _price_number(value: Any) -> Decimal:
    clean = re.sub(r"[^0-9.,-]", "", str(value or "")).replace(",", ".")
    try:
        return Decimal(clean)
    except InvalidOperation:
        return Decimal("Infinity")


def _route_priority(values: list[Any]) -> tuple[int, Decimal, str]:
    route_from = str(values[1] or "")
    vehicle = str(values[3] or "").casefold()
    airport_rank = 0 if "airport" in route_from.casefold() else 1
    if "standard sedan" in vehicle:
        vehicle_rank = 0
    elif "standard minivan" in vehicle:
        vehicle_rank = 1
    else:
        vehicle_rank = 2
    return airport_rank * 10 + vehicle_rank, _price_number(values[5]), route_from.casefold()


def select_pricebook_route(city: str, attestation: dict[str, Any]) -> tuple[int, list[Any]] | None:
    city_key = _city_key(city)
    candidates: list[tuple[int, list[Any]]] = []
    for row_number, raw_values in (attestation.get("rows") or {}).items():
        values = list(raw_values) if isinstance(raw_values, list) else []
        if len(values) == 7 and _city_key(values[2]) == city_key and "airport" in str(values[1]).casefold():
            candidates.append((int(row_number), values))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (*_route_priority(item[1]), item[0]))[0]


def _currency_price(currency: str, value: Any) -> str:
    return canonical_currency_price(currency, value)


def build_candidate_record(row: dict[str, Any], attestation: dict[str, Any]) -> dict[str, Any]:
    route = select_pricebook_route(str(row.get("city") or ""), attestation)
    if not route:
        raise ValueError("route_price_missing")
    row_number, values = route
    country, route_from, route_to, vehicle_cell, pax_cell, price_cell, currency = [str(value).strip() for value in values]
    del country
    pax = int(pax_cell)
    vehicle = re.sub(rf"\s+{re.escape(pax_cell)}\s+pax$", "", vehicle_cell, flags=re.I).strip().lower()
    source_fingerprint = research_source_fact_fingerprint(row)
    record = {
        "audience": "transfer_buyer",
        "lead_id": str(row.get("lead_id") or ""),
        "workstream_id": str(row.get("workstream_id") or ""),
        "contact_point_id": str(row.get("contact_point_id") or ""),
        "recipient": str(row.get("recipient") or "").strip().lower(),
        "company": str(row.get("company") or "").strip(),
        "city": str(row.get("city") or "").strip(),
        "opening": "",
        "opening_source_url": "",
        "opening_variant": "no_opening_v1",
        "source_fact_fingerprint": source_fingerprint,
        "pricebook": {
            "spreadsheet_id": PRICEBOOK_ID,
            "sheet": PRICEBOOK_SHEET,
            "row": row_number,
            "route": f"{route_from} to a hotel in {route_to}",
            "vehicle": vehicle,
            "pax": pax,
            "price": _currency_price(currency, price_cell),
            "currency": currency,
            "source_row_sha256": _hash(values),
            "source_artifact_sha256": attestation["artifact_sha256"],
            "source_version": attestation["artifact_sha256"],
        },
    }
    record.update(render_record(record))
    return record


def load_candidate_rows(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """SELECT ws.id AS workstream_id,ws.lead_id,ws.workstream_type,ws.client_business_id,
                  ws.lifecycle_status,ws.status AS workstream_status,
                  lead.name AS company,lead.city,lead.category,lead.pipeline_status,lead.status AS lead_status,
                  contact.id AS contact_point_id,contact.contact_type,contact.verification_status,
                  lower(btrim(contact.normalized_value)) AS recipient,
                  research.evidence_json,research.signals_json,research.report_hash,
                  research.suggested_opener,research.opener_source_url,research.researched_at,
                  EXISTS(SELECT 1 FROM outreach_campaigns campaign WHERE campaign.workstream_id=ws.id) AS has_campaign,
                  EXISTS(SELECT 1 FROM outreach_suppressions suppression
                         WHERE suppression.lead_id=ws.lead_id
                           AND (suppression.expires_at IS NULL OR suppression.expires_at>NOW())
                           AND (suppression.scope_type='platform_safety'
                                OR (suppression.scope_type='business' AND suppression.business_id=%s))) AS suppressed
           FROM lead_workstreams ws JOIN prospectingleads lead ON lead.id=ws.lead_id
           LEFT JOIN lead_contact_points contact ON contact.id=ws.selected_contact_point_id AND contact.lead_id=lead.id
           LEFT JOIN LATERAL (
             SELECT evidence_json,signals_json,report_hash,suggested_opener,opener_source_url,researched_at
             FROM lead_workstream_research item WHERE item.workstream_id=ws.id
             ORDER BY researched_at DESC NULLS LAST,created_at DESC LIMIT 1
           ) research ON TRUE
           WHERE ws.workstream_type='client_partnership' AND ws.client_business_id=%s
           ORDER BY ws.created_at,ws.id""",
        (BUSINESS_ID, BUSINESS_ID),
    )
    return [_dict(row) for row in (cursor.fetchall() or [])]


def candidate_exclusion(row: dict[str, Any], *, now: datetime) -> str | None:
    if "berlin" in str(row.get("city") or "").casefold():
        return "excluded_city"
    if not str(row.get("city") or "").strip():
        return "city_missing"
    if not str(row.get("category") or "").strip():
        return "occupation_missing"
    if row.get("contact_type") != "email" or row.get("verification_status") not in ELIGIBLE_CONTACT_STATUSES:
        return "confirmed_email_missing"
    if "@" not in str(row.get("recipient") or ""):
        return "confirmed_email_missing"
    if row.get("suppressed"):
        return "suppressed"
    if row.get("has_campaign"):
        return "campaign_exists"
    states = {
        str(row.get("lifecycle_status") or "").casefold(),
        str(row.get("workstream_status") or "").casefold(),
        str(row.get("pipeline_status") or "").casefold(),
        str(row.get("lead_status") or "").casefold(),
    }
    if states.intersection(TERMINAL_LEAD_STATES):
        return "terminal_state"
    researched_at = row.get("researched_at")
    if not isinstance(researched_at, datetime):
        return "research_missing"
    observed_at = researched_at if researched_at.tzinfo else researched_at.replace(tzinfo=timezone.utc)
    if (now - observed_at.astimezone(timezone.utc)).days >= 90:
        return "research_stale"
    if not research_source_fact_fingerprint(row):
        return "research_missing"
    return None


def remaining_daily_capacity(cursor: Any) -> int:
    cursor.execute(
        """WITH activity AS (
             SELECT lower(regexp_replace(btrim(lead.name),'\\s+',' ','g')) AS company_key,
                    COALESCE(queue.sent_at,queue.dispatch_started_at,queue.scheduled_at,queue.created_at) AS occurred_at
             FROM outreachsendqueue queue
             JOIN outreach_campaign_touches touch ON touch.id=queue.campaign_touch_id
             JOIN outreach_campaigns campaign ON campaign.id=touch.campaign_id
             JOIN prospectingleads lead ON lead.id=queue.lead_id
             WHERE campaign.business_id=%s
               AND (queue.delivery_status IN ('queued','sending','sent','delivered')
                    OR lower(COALESCE(queue.error_text,'')) LIKE '%%send_uncertain%%')
             UNION ALL
             SELECT lower(regexp_replace(btrim(lead.name),'\\s+',' ','g')) AS company_key,
                    COALESCE(
                      CASE WHEN COALESCE(pg_input_is_valid(event.payload_json->>'occurred_at','timestamp with time zone'),FALSE)
                           THEN (event.payload_json->>'occurred_at')::timestamptz ELSE NULL END,
                      event.created_at
                    ) AS occurred_at
             FROM outreach_campaign_events event
             JOIN outreach_campaigns campaign ON campaign.id=event.campaign_id
             JOIN prospectingleads lead ON lead.id=campaign.lead_id
             WHERE campaign.business_id=%s AND event.event_type='manual_sent'
               AND event.payload_json->>'evidence_kind'='user_confirmed'
           )
           SELECT COUNT(DISTINCT company_key)::int AS used FROM activity
           WHERE (occurred_at AT TIME ZONE 'Europe/Moscow')::date=(NOW() AT TIME ZONE 'Europe/Moscow')::date""",
        (BUSINESS_ID, BUSINESS_ID),
    )
    row = _dict(cursor.fetchone())
    return max(0, DAILY_LIMIT - int(row.get("used") or 0))


def classify_candidates(
    rows: list[dict[str, Any]], attestation: dict[str, Any], *, now: datetime,
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, int]]:
    eligible: list[dict[str, Any]] = []
    exclusions: Counter[str] = Counter()
    missing_routes: Counter[str] = Counter()
    company_keys: set[str] = set()
    recipients: set[str] = set()
    for row in rows:
        reason = candidate_exclusion(row, now=now)
        if reason:
            exclusions[reason] += 1
            continue
        company_key = _city_key(row.get("company"))
        recipient = str(row.get("recipient") or "").strip().casefold()
        if company_key in company_keys or recipient in recipients:
            exclusions["duplicate_company_or_email"] += 1
            continue
        try:
            record = build_candidate_record(row, attestation)
        except ValueError as exc:
            reason = str(exc)
            exclusions[reason] += 1
            if reason == "route_price_missing":
                missing_routes[str(row.get("city") or "Unknown")] += 1
            continue
        eligible.append(record)
        company_keys.add(company_key)
        recipients.add(recipient)
    return eligible, dict(sorted(exclusions.items())), dict(sorted(missing_routes.items()))


def _run_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def record_run(cursor: Any, result: dict[str, Any]) -> dict[str, Any]:
    fingerprint_payload = {
        key: result.get(key) for key in (
            "local_date", "status", "target_count", "eligible_count", "selected_count",
            "remaining_daily_capacity", "exclusion_counts", "missing_routes", "error_code",
        )
    }
    fingerprint = _run_fingerprint(fingerprint_payload)
    run_id = str(uuid.uuid4())
    cursor.execute(
        """INSERT INTO riderra_outreach_runs(
             id,local_date,status,target_count,eligible_count,selected_count,queued_count,
             remaining_daily_capacity,standing_authorization_id,batch_authorization_id,
             pricebook_attestation_id,exclusion_counts_json,missing_routes_json,error_code,
             fingerprint,notification_required,created_at,updated_at
           ) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,NULLIF(%s,'')::uuid,NULLIF(%s,'')::uuid,
                    NULLIF(%s,'')::uuid,%s,%s,%s,%s,%s,NOW(),NOW())
           ON CONFLICT(fingerprint) DO UPDATE SET updated_at=NOW()
           RETURNING id,notification_required,notified_at""",
        (
            run_id, result["local_date"], result["status"], result["target_count"],
            result["eligible_count"], result["selected_count"], result["queued_count"],
            result["remaining_daily_capacity"], result.get("standing_authorization_id") or "",
            result.get("batch_authorization_id") or "", result.get("pricebook_attestation_id") or "",
            Json(result.get("exclusion_counts") or {}), Json(result.get("missing_routes") or {}),
            result.get("error_code"), fingerprint, bool(result.get("notification_required")),
        ),
    )
    persisted = _dict(cursor.fetchone())
    return {**result, "run_id": str(persisted.get("id") or run_id), "fingerprint": fingerprint,
            "should_notify": bool(persisted.get("notification_required") and not persisted.get("notified_at"))}


def prepare_systematic_batch(cursor: Any, *, target_count: int = DAILY_LIMIT,
                             now: datetime | None = None) -> dict[str, Any]:
    checked_at = now or datetime.now(timezone.utc)
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("riderra:systematic-batch",))
    standing = load_standing_authorization(cursor)
    capacity = remaining_daily_capacity(cursor)
    base = {
        "local_date": checked_at.astimezone(ZoneInfo("Europe/Moscow")).date(),
        "target_count": min(max(0, target_count), capacity),
        "remaining_daily_capacity": capacity,
        "eligible_count": 0,
        "selected_count": 0,
        "queued_count": 0,
        "exclusion_counts": {},
        "missing_routes": {},
        "standing_authorization_id": str(standing.get("id") or ""),
    }
    if not standing:
        return record_run(cursor, {**base, "status": "blocked", "error_code": "standing_authorization_missing", "notification_required": True})
    if capacity <= 0:
        return record_run(cursor, {**base, "status": "daily_limit_reached", "notification_required": False})
    cursor.execute("SAVEPOINT riderra_pricebook_refresh")
    try:
        snapshot = refresh_pricebook_attestation(cursor, actor_id=standing["approved_by"], now=checked_at)
        cursor.execute("RELEASE SAVEPOINT riderra_pricebook_refresh")
    except Exception as exc:
        cursor.execute("ROLLBACK TO SAVEPOINT riderra_pricebook_refresh")
        cursor.execute("RELEASE SAVEPOINT riderra_pricebook_refresh")
        error_text = str(exc).casefold()
        if "invalid_grant" in error_text:
            error_code = "pricebook_refresh_failed:google_sheets_reauthorization_required"
        else:
            error_code = f"pricebook_refresh_failed:{exc.__class__.__name__}"
        return record_run(cursor, {**base, "status": "blocked", "error_code": error_code, "notification_required": True})
    attestation = {"id": snapshot["id"], **snapshot["attestation"]}
    rows = load_candidate_rows(cursor)
    eligible, exclusions, missing_routes = classify_candidates(rows, attestation, now=checked_at)
    selected = eligible[:base["target_count"]]
    result = {
        **base,
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "exclusion_counts": exclusions,
        "missing_routes": missing_routes,
        "pricebook_attestation_id": snapshot["id"],
    }
    if not selected:
        return record_run(cursor, {**result, "status": "shortage", "notification_required": True})
    batch = set_authorization(
        cursor,
        actor_id=standing["approved_by"],
        enabled=True,
        records=selected,
        authorization_reference=AUTHORIZATION_REFERENCE,
        pricebook_attestation_id=snapshot["id"],
        standing_authorization_id=standing["id"],
    )
    queued = 0
    runtime_exclusions = Counter(exclusions)
    granted_records = list((batch.get("manifest") or {}).get("records") or [])
    for record in granted_records:
        savepoint = f"riderra_{queued}_{uuid.uuid4().hex[:8]}"
        cursor.execute(f"SAVEPOINT {savepoint}")
        try:
            preview = build_riderra_template_preview(cursor, record, start_at=checked_at)
            campaign = persist_preview(cursor, preview, user_id=standing["approved_by"])
            approve_campaign_by_riderra_template(cursor, str(campaign["id"]))
            cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            queued += 1
        except Exception as exc:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
            runtime_exclusions[f"campaign_prepare_failed:{exc.__class__.__name__}"] += 1
    shortage = queued < base["target_count"]
    result.update({
        "status": "shortage" if shortage else "ready",
        "queued_count": queued,
        "batch_authorization_id": batch["id"],
        "exclusion_counts": dict(sorted(runtime_exclusions.items())),
        "notification_required": shortage,
    })
    return record_run(cursor, result)


def format_run_notification(result: dict[str, Any]) -> str:
    status = str(result.get("status") or "")
    if status == "blocked":
        return (
            "⚠️ Riderra: автоматическая подготовка партии остановлена.\n"
            f"Причина: {result.get('error_code') or 'неизвестная ошибка'}.\n"
            "Следующее действие: восстановить указанное подключение или разрешение; отправки не выполнялись."
        )
    shortage = max(0, int(result.get("target_count") or 0) - int(result.get("queued_count") or 0))
    reasons = ", ".join(f"{key}: {value}" for key, value in (result.get("exclusion_counts") or {}).items()) or "нет"
    routes = ", ".join(f"{key}: {value}" for key, value in (result.get("missing_routes") or {}).items()) or "нет"
    return (
        "⚠️ Riderra: подходящих лидов меньше доступного объёма партии.\n"
        f"Нужно: {result.get('target_count')}; найдено: {result.get('eligible_count')}; поставлено в очередь: {result.get('queued_count')}; не хватает: {shortage}.\n"
        f"Причины исключения: {reasons}.\n"
        f"Города без точного маршрута и цены 005: {routes}.\n"
        "Следующее действие: пополнить или дообогатить лиды и восстановить недостающие маршруты в 005. Доступный остаток уже поставлен в очередь."
    )


def mark_run_notified(cursor: Any, run_id: str) -> None:
    cursor.execute(
        "UPDATE riderra_outreach_runs SET notified_at=NOW(),updated_at=NOW() WHERE id=%s AND notified_at IS NULL",
        (run_id,),
    )
