#!/usr/bin/env python3
"""Backfill deterministic partnership match artifacts without moving lead stages."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from psycopg2.extras import Json


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api.admin_prospecting import (  # noqa: E402
    _compute_partnership_match_result,
    _enqueue_parse_task_for_business,
    _ensure_parse_business_for_partnership_lead,
    _normalize_lead_for_display,
    _to_json_compatible,
    build_lead_card_preview_snapshot,
)
from database_manager import DatabaseManager  # noqa: E402
from services.contact_intelligence_service import enqueue_enrichment_job  # noqa: E402


def _service_names(value: object) -> list[str]:
    items = value
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except json.JSONDecodeError:
            items = []
    if not isinstance(items, list):
        return []
    names: list[str] = []
    for item in items:
        if isinstance(item, dict):
            name = str(
                item.get("name") or item.get("title") or item.get("current_name") or ""
            ).strip()
        else:
            name = str(item or "").strip()
        if name:
            names.append(name)
    return names


def _snapshot_service_names(snapshot: dict[str, object] | None) -> list[str]:
    services = snapshot.get("services_preview") if isinstance(snapshot, dict) else []
    if not isinstance(services, list):
        return []
    names: list[str] = []
    for item in services:
        if not isinstance(item, dict):
            continue
        name = str(
            item.get("current_name") or item.get("suggested_name") or item.get("name") or ""
        ).strip()
        if name:
            names.append(name)
    return names


def _source_skip_reason(row: dict[str, object]) -> str | None:
    source_url = str(row.get("source_url") or "").strip().lower()
    search_payload = row.get("search_payload_json")
    if isinstance(search_payload, str):
        try:
            search_payload = json.loads(search_payload)
        except json.JSONDecodeError:
            search_payload = {}
    source_kind = str(
        (search_payload or {}).get("source") if isinstance(search_payload, dict) else ""
    ).strip()
    if source_kind == "manual_google_doc_import" or source_url.startswith("localos-doc://"):
        return "manual_import_without_public_service_evidence"
    if not source_url.startswith(("http://", "https://")):
        return "public_source_missing"
    return None


def _skip_reason(
    row: dict[str, object],
    snapshot: dict[str, object] | None = None,
) -> str | None:
    source_reason = _source_skip_reason(row)
    if source_reason:
        return source_reason
    explicit_services = _service_names(row.get("services_json"))
    snapshot_services = _snapshot_service_names(snapshot)
    if max(len(explicit_services), len(snapshot_services)) < 3:
        if _has_verified_category_evidence(row, snapshot):
            return None
        return "partner_services_missing"
    return None


def _has_verified_category_evidence(
    row: dict[str, object],
    snapshot: dict[str, object] | None,
) -> bool:
    source_url = str(row.get("source_url") or "").strip().lower()
    category = str(row.get("category") or "").strip()
    parse_context = snapshot.get("parse_context") if isinstance(snapshot, dict) else {}
    parse_status = str(
        parse_context.get("last_parse_status")
        if isinstance(parse_context, dict)
        else ""
    ).strip().lower()
    return bool(
        category
        and source_url.startswith(("http://", "https://"))
        and str(row.get("parse_business_id") or "").strip()
        and parse_status in {"completed", "done"}
    )


def _match_skip_reason(match: dict[str, object]) -> str | None:
    reason_codes = match.get("reason_codes")
    if isinstance(reason_codes, list) and "SENDER_PROFILE_INCOMPLETE" in reason_codes:
        return "sender_profile_incomplete"
    try:
        score = int(match.get("match_score") or 0)
    except (TypeError, ValueError):
        score = 0
    if score < 40:
        return "compatibility_below_threshold"
    source_url = str(match.get("source_url") or "").strip().lower()
    if (
        not str(match.get("recipient_observation") or "").strip()
        or not source_url.startswith(("http://", "https://"))
    ):
        return "compatibility_evidence_missing"
    return None


def _should_persist_match_assessment(skip_reason: str | None) -> bool:
    """Keep a visible result without treating weak evidence as a match."""

    return skip_reason in {
        "sender_profile_incomplete",
        "compatibility_below_threshold",
        "compatibility_evidence_missing",
    }


def _build_prerequisite_assessment(
    row: dict[str, object],
    skip_reason: str,
    snapshot: dict[str, object] | None = None,
) -> dict[str, object]:
    """Describe why matching cannot run yet without claiming compatibility."""

    recovery_action = _recovery_action(row, skip_reason, snapshot)
    reason_codes = {
        "manual_import_without_public_service_evidence": "PUBLIC_CARD_REQUIRED",
        "public_source_missing": "PUBLIC_SOURCE_REQUIRED",
        "partner_services_missing": "RECIPIENT_EVIDENCE_INCOMPLETE",
    }
    next_actions = {
        "find_public_card": "Найдите публичную карточку компании и повторите сбор данных",
        "find_public_source": "Добавьте официальный публичный источник компании",
        "wait_for_parse": "Дождитесь завершения сбора данных — результат обновится после повторной проверки",
        "resolve_captcha": "Завершите проверку источника и повторите сбор данных",
        "retry_parse": "Повторите сбор данных карточки",
        "find_alternate_public_source": "Найдите другой публичный источник: карточку, официальный сайт или каталог",
        "mark_closed_not_relevant": "Проверьте статус и исключите закрытую организацию из воронки",
        "evaluate_category_only_match": "Повторите мэтчинг по подтверждённой категории компании",
        "repair_recipient_identity_mapping": "Найдите правильную карточку компании и повторите сбор данных",
        "start_parse": "Соберите данные публичной карточки компании",
        "resolve_public_map_card": "Найдите карточку компании на карте и запустите сбор данных",
        "review_manually": "Проверьте источник и данные компании вручную",
    }
    source_url = str(row.get("source_url") or "").strip()
    if not source_url.lower().startswith(("http://", "https://")):
        source_url = ""
    return {
        "assessment_kind": "prerequisite",
        "match_score": 0,
        "overlap": [],
        "complement": {"our_strength_tokens": [], "partner_strength_tokens": []},
        "risks": ["Совместимость не оценивалась: не хватает проверяемых данных получателя."],
        "offer_angles": [],
        "source_counts": {"our_services": 0, "partner_services": 0},
        "reason_codes": [reason_codes.get(skip_reason, "RECIPIENT_EVIDENCE_INCOMPLETE")],
        "score_explanation": "Оценка совместимости ещё не запускалась.",
        "recipient_observation": None,
        "compatibility_hypothesis": None,
        "relevance_bridge": None,
        "source_url": source_url or None,
        "score_breakdown": {},
        "profile_completeness": {},
        "direct_competitor": False,
        "readiness_code": "needs_evidence",
        "prerequisite_code": skip_reason,
        "recovery_action": recovery_action,
        "next_action": next_actions.get(recovery_action, next_actions["review_manually"]),
    }


def _persist_match_artifact(
    cursor: object,
    *,
    lead_id: str,
    snapshot: dict[str, object] | None,
    match: dict[str, object],
) -> None:
    cursor.execute(
        """
        INSERT INTO partnershipleadartifacts (lead_id, audit_json, match_json, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (lead_id) DO UPDATE
        SET audit_json = CASE
                WHEN partnershipleadartifacts.audit_json IS NULL
                  OR partnershipleadartifacts.audit_json = '{}'::jsonb
                THEN EXCLUDED.audit_json
                ELSE partnershipleadartifacts.audit_json
            END,
            match_json = EXCLUDED.match_json,
            updated_at = NOW()
        """,
        (lead_id, Json(snapshot or {}), Json(match)),
    )


def _recovery_action(
    row: dict[str, object],
    skip_reason: str,
    snapshot: dict[str, object] | None = None,
) -> str:
    if skip_reason == "manual_import_without_public_service_evidence":
        return "find_public_card"
    if skip_reason == "public_source_missing":
        return "find_public_source"
    if skip_reason != "partner_services_missing":
        return "review_manually"

    parse_status = str(row.get("parse_status") or "").strip().lower()
    if parse_status in {"pending", "processing"}:
        return "wait_for_parse"
    if parse_status == "captcha":
        return "resolve_captcha"
    if parse_status == "error":
        parse_error = str(row.get("parse_error") or "").strip().lower()
        if "business_closed" in parse_error or "permanent_closed" in parse_error:
            return "mark_closed_not_relevant"
        if "apify_empty_dataset" in parse_error or "empty dataset" in parse_error:
            return "find_alternate_public_source"
        return "retry_parse"
    if parse_status in {"completed", "done"}:
        parse_context = snapshot.get("parse_context") if isinstance(snapshot, dict) else {}
        snapshot_status = str(
            parse_context.get("last_parse_status")
            if isinstance(parse_context, dict)
            else ""
        ).strip().lower()
        if snapshot_status not in {"completed", "done"}:
            return "repair_recipient_identity_mapping"
        return "evaluate_category_only_match"
    if str(row.get("parse_business_id") or "").strip():
        return "retry_parse"
    return "start_parse" if _is_direct_map_card_url(row.get("source_url")) else "resolve_public_map_card"


def _is_direct_map_card_url(value: object) -> bool:
    url = str(value or "").strip().lower()
    if not url.startswith(("http://", "https://")):
        return False
    if re.search(r"yandex\.(?:ru|com|kz|by|uz|com\.tr)/maps/org/[^/?#]+/\d+", url):
        return True
    if "2gis." in url and re.search(r"/(?:firm|geo)/\d+", url):
        return True
    if "google." in url and "/maps/place/" in url:
        return True
    if "maps.app.goo.gl/" in url or "maps.apple.com/" in url:
        return True
    return False


def _record_recovery(
    report: dict[str, object],
    row: dict[str, object],
    skip_reason: str,
    sample_size: int,
    snapshot: dict[str, object] | None = None,
) -> None:
    action = _recovery_action(row, skip_reason, snapshot)
    actions = report.get("recovery_actions")
    if not isinstance(actions, dict):
        actions = {}
        report["recovery_actions"] = actions
    actions[action] = int(actions.get(action) or 0) + 1

    samples_by_action = report.get("recovery_samples_by_action")
    if not isinstance(samples_by_action, dict):
        samples_by_action = {}
        report["recovery_samples_by_action"] = samples_by_action
    action_samples = samples_by_action.get(action)
    if not isinstance(action_samples, list):
        action_samples = []
        samples_by_action[action] = action_samples
    if len(action_samples) >= max(0, sample_size):
        return
    action_samples.append({
        "lead_id": str(row.get("id") or ""),
        "lead_name": str(row.get("name") or ""),
        "skip_reason": skip_reason,
        "parse_status": str(row.get("parse_status") or "") or None,
        "parse_error": str(row.get("parse_error") or "") or None,
        "has_parse_business_id": bool(str(row.get("parse_business_id") or "").strip()),
        "source_url": str(row.get("source_url") or "") or None,
    })


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--business-id")
    parser.add_argument("--sample-size", type=int, default=10)
    parser.add_argument(
        "--refresh-enrichment",
        action="store_true",
        help="Enqueue a fresh free enrichment job after saving each match artifact",
    )
    parser.add_argument(
        "--allow-openclaw",
        action="store_true",
        help="Allow configured OpenClaw matching; deterministic matching is the safe default",
    )
    parser.add_argument(
        "--enqueue-missing-parses",
        action="store_true",
        help="Enqueue direct public map cards that still lack service evidence",
    )
    parser.add_argument(
        "--parse-limit",
        type=int,
        default=20,
        help="Maximum missing-service parse tasks per run; 0 means no limit",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.allow_openclaw:
        os.environ["OPENCLAW_PARTNERS_ENABLED"] = "0"

    database = DatabaseManager()
    cursor = database.conn.cursor()
    where = [
        "ws.workstream_type = 'client_partnership'",
        "NOT EXISTS ("
        "SELECT 1 FROM partnershipleadartifacts artifact "
        "WHERE artifact.lead_id = lead.id "
        "AND artifact.match_json IS NOT NULL "
        "AND artifact.match_json <> '{}'::jsonb "
        "AND COALESCE(artifact.match_json->>'assessment_kind', '') <> 'prerequisite')",
    ]
    params: list[object] = []
    if args.business_id:
        where.append("ws.client_business_id = %s")
        params.append(args.business_id)
    limit_sql = "LIMIT %s" if args.limit > 0 else ""
    if args.limit > 0:
        params.append(args.limit)
    cursor.execute(
        f"""
        SELECT ws.id AS workstream_id, ws.client_business_id,
               (SELECT owner_id FROM businesses owner_business
                WHERE owner_business.id::text = ws.client_business_id LIMIT 1) AS client_owner_id,
               lead.*,
               parse_last.status AS parse_status,
               parse_last.error_message AS parse_error,
               COALESCE(parse_last.updated_at, parse_last.created_at) AS parse_updated_at
        FROM lead_workstreams ws
        JOIN prospectingleads lead ON lead.id = ws.lead_id
        LEFT JOIN LATERAL (
            SELECT queue.status, queue.error_message, queue.updated_at, queue.created_at
            FROM parsequeue queue
            WHERE (
                    (lead.parse_business_id IS NOT NULL AND queue.business_id = lead.parse_business_id)
                    OR (
                        lead.parse_business_id IS NULL
                        AND COALESCE(lead.source_url, '') <> ''
                        AND queue.url = lead.source_url
                    )
                  )
              AND queue.task_type IN ('parse_card', 'sync_yandex_business')
            ORDER BY COALESCE(queue.updated_at, queue.created_at) DESC
            LIMIT 1
        ) parse_last ON TRUE
        WHERE {' AND '.join(where)}
        ORDER BY ws.created_at, ws.id
        {limit_sql}
        """,
        tuple(params),
    )
    rows = [dict(row) for row in cursor.fetchall() or []]
    report = {
        "mode": "execute" if args.execute else "dry-run",
        "workstreams": len(rows),
        "matches_saved": 0,
        "assessments_saved": 0,
        "prerequisite_assessments_saved": 0,
        "matches_evaluated": 0,
        "eligible": 0,
        "jobs_enqueued": 0,
        "jobs_reused": 0,
        "parse_candidates": 0,
        "parse_tasks_queued": 0,
        "parse_tasks_existing": 0,
        "parse_businesses_created": 0,
        "parse_limit": max(0, args.parse_limit),
        "score_bands": {"strong": 0, "medium": 0, "low": 0},
        "skipped": {},
        "recovery_actions": {},
        "recovery_samples_by_action": {},
        "lead_stages_changed": 0,
        "external_send": False,
        "openclaw_enabled": bool(args.allow_openclaw),
        "samples": [],
    }

    try:
        for index, row in enumerate(rows, start=1):
            source_skip_reason = _source_skip_reason(row)
            if source_skip_reason:
                report["skipped"][source_skip_reason] = report["skipped"].get(source_skip_reason, 0) + 1
                _record_recovery(report, row, source_skip_reason, args.sample_size)
                if args.execute:
                    _persist_match_artifact(
                        cursor,
                        lead_id=str(row["id"]),
                        snapshot=None,
                        match=_build_prerequisite_assessment(row, source_skip_reason),
                    )
                    report["prerequisite_assessments_saved"] += 1
                continue
            snapshot = _to_json_compatible(build_lead_card_preview_snapshot(row))
            skip_reason = _skip_reason(row, snapshot)
            if skip_reason:
                report["skipped"][skip_reason] = report["skipped"].get(skip_reason, 0) + 1
                _record_recovery(report, row, skip_reason, args.sample_size, snapshot)
                recovery_action = _recovery_action(row, skip_reason, snapshot)
                if recovery_action in {"start_parse", "retry_parse"}:
                    report["parse_candidates"] += 1
                    parse_limit_reached = (
                        args.parse_limit > 0
                        and report["parse_tasks_queued"] + report["parse_tasks_existing"] >= args.parse_limit
                    )
                    if args.execute and args.enqueue_missing_parses and not parse_limit_reached:
                        display_lead = _normalize_lead_for_display(dict(row))
                        owner_id = str(row.get("client_owner_id") or "").strip()
                        if not display_lead or not owner_id:
                            report["skipped"]["parse_owner_or_lead_missing"] = (
                                report["skipped"].get("parse_owner_or_lead_missing", 0) + 1
                            )
                            continue
                        parse_business, business_created = _ensure_parse_business_for_partnership_lead(
                            display_lead,
                            owner_id,
                        )
                        parse_business_id = str(parse_business.get("id") or "").strip()
                        source_url = str(
                            parse_business.get("yandex_url") or row.get("source_url") or ""
                        ).strip()
                        if not parse_business_id or not source_url:
                            report["skipped"]["parse_business_or_url_missing"] = (
                                report["skipped"].get("parse_business_or_url_missing", 0) + 1
                            )
                            continue
                        cursor.execute(
                            """
                            UPDATE prospectingleads
                            SET parse_business_id = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (parse_business_id, str(row["id"])),
                        )
                        task = _enqueue_parse_task_for_business(
                            parse_business_id,
                            owner_id,
                            source_url,
                        )
                        if task.get("existing"):
                            report["parse_tasks_existing"] += 1
                        else:
                            report["parse_tasks_queued"] += 1
                        if business_created:
                            report["parse_businesses_created"] += 1
                        database.conn.commit()
                if args.execute:
                    _persist_match_artifact(
                        cursor,
                        lead_id=str(row["id"]),
                        snapshot=snapshot,
                        match=_build_prerequisite_assessment(row, skip_reason, snapshot),
                    )
                    report["prerequisite_assessments_saved"] += 1
                continue
            report["eligible"] += 1
            match = _compute_partnership_match_result(
                cursor,
                business_id=str(row["client_business_id"]),
                lead_id=str(row["id"]),
                audit_json=snapshot,
            )
            report["matches_evaluated"] += 1
            score = int(match.get("match_score") or 0)
            band = "strong" if score >= 70 else "medium" if score >= 40 else "low"
            report["score_bands"][band] += 1
            if len(report["samples"]) < max(0, args.sample_size):
                report["samples"].append({
                    "lead_id": str(row["id"]),
                    "lead_name": str(row.get("name") or ""),
                    "business_id": str(row["client_business_id"]),
                    "explicit_services": len(_service_names(row.get("services_json"))),
                    "snapshot_services": len(_snapshot_service_names(snapshot)),
                    "match_score": score,
                    "reason_codes": match.get("reason_codes") or [],
                    "score_explanation": match.get("score_explanation"),
                })
            reason = _match_skip_reason(match)
            if reason:
                report["skipped"][reason] = report["skipped"].get(reason, 0) + 1
                if args.execute and _should_persist_match_assessment(reason):
                    _persist_match_artifact(
                        cursor,
                        lead_id=str(row["id"]),
                        snapshot=snapshot,
                        match=match,
                    )
                    report["assessments_saved"] += 1
                    if args.refresh_enrichment:
                        job = enqueue_enrichment_job(
                            cursor,
                            str(row["workstream_id"]),
                            force=True,
                            allow_paid_enrichment=False,
                        )
                        key = "jobs_reused" if job.get("reused") else "jobs_enqueued"
                        report[key] += 1
                continue
            if args.dry_run:
                continue
            _persist_match_artifact(
                cursor,
                lead_id=str(row["id"]),
                snapshot=snapshot,
                match=match,
            )
            report["matches_saved"] += 1
            if args.refresh_enrichment:
                job = enqueue_enrichment_job(
                    cursor,
                    str(row["workstream_id"]),
                    force=True,
                    allow_paid_enrichment=False,
                )
                key = "jobs_reused" if job.get("reused") else "jobs_enqueued"
                report[key] += 1
            if not args.dry_run and index % 50 == 0:
                database.conn.commit()
        if args.execute:
            database.conn.commit()
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
