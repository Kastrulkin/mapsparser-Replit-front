#!/usr/bin/env python3
"""Find map cards, build audits, and refresh existing partnership rooms."""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from api import admin_prospecting
from psycopg2.extras import Json
from pg_db_utils import get_db_connection


FINAL_PARSE_STATUSES = {"completed", "done", "failed", "error", "cancelled"}
SUCCESS_PARSE_STATUSES = {"completed", "done"}


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(inner) for key, inner in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _load_context(business_id: str) -> tuple[list[dict[str, Any]], str]:
    conn = get_db_connection()
    try:
        admin_prospecting._ensure_partnership_columns(conn)
        cur = conn.cursor()
        cur.execute("SELECT owner_id FROM businesses WHERE id = %s LIMIT 1", (business_id,))
        business = cur.fetchone()
        if not business:
            raise RuntimeError("Business not found")
        owner_id = str(business.get("owner_id") if hasattr(business, "get") else business[0])
        cur.execute(
            """
            SELECT *
            FROM prospectingleads
            WHERE business_id = %s
              AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
              AND COALESCE(pipeline_status, '') IN ('qualified', 'in_progress')
            ORDER BY name ASC, created_at ASC
            """,
            (business_id,),
        )
        return [dict(row) for row in (cur.fetchall() or [])], owner_id
    finally:
        conn.close()


def _search_lead(lead: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "lead_id": str(lead.get("id") or ""),
        "company": str(lead.get("name") or ""),
        "source_document": str(lead.get("source_url") or ""),
        "map_url": "",
        "confidence": 0,
        "profile": "",
        "audit_url": "",
        "room_url": "",
        "status": "skipped",
        "qa": "not_run",
        "reason": "",
    }
    if admin_prospecting._is_synthetic_partnership_lead(lead):
        result["reason"] = "synthetic_group"
        return result

    if not admin_prospecting._is_internal_partnership_source_url(lead.get("source_url")):
        result["map_url"] = str(lead.get("source_url") or "")
        result["confidence"] = 1.0
        result["status"] = "confirmed"
        result["reason"] = "existing_map_source"
        return result

    candidates, provider_error = admin_prospecting._find_yandex_candidates_for_partnership_lead(lead)
    if provider_error:
        result["reason"] = f"provider_error:{provider_error}"
        return result
    candidate, status = admin_prospecting._select_partnership_map_candidate(candidates)
    result["candidates"] = candidates
    result["reason"] = status
    if not candidate:
        return result
    result["candidate"] = candidate
    result["map_url"] = str(candidate.get("yandex_maps_url") or "")
    result["confidence"] = float(candidate.get("confidence") or 0)
    result["status"] = "confirmed"
    return result


def _wait_for_parse(task_id: str, timeout_seconds: int) -> tuple[str, str]:
    deadline = time.monotonic() + timeout_seconds
    last_status = "pending"
    last_error = ""
    while time.monotonic() < deadline:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT status, error_message FROM parsequeue WHERE id = %s LIMIT 1",
                (task_id,),
            )
            row = cur.fetchone()
            if row:
                last_status = str(row.get("status") if hasattr(row, "get") else row[0]).strip().lower()
                last_error = str(
                    (row.get("error_message") if hasattr(row, "get") else row[1]) or ""
                ).strip()
                if last_status in FINAL_PARSE_STATUSES:
                    return last_status, last_error
        finally:
            conn.close()
        time.sleep(4)
    return "timeout", last_error or f"last_status={last_status}"


def _load_lead(lead_id: str, business_id: str) -> dict[str, Any]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        lead = admin_prospecting._load_partnership_lead(cur, lead_id=lead_id, business_id=business_id)
        return dict(lead or {})
    finally:
        conn.close()


def _persist_match(lead: dict[str, Any], search_result: dict[str, Any]) -> dict[str, Any]:
    candidate = search_result.get("candidate")
    if not isinstance(candidate, dict):
        return lead
    candidates = search_result.get("candidates")
    if not isinstance(candidates, list):
        candidates = [candidate]
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        admin_prospecting._store_partnership_map_match(
            cur,
            lead=lead,
            candidate=candidate,
            candidates=candidates,
        )
        conn.commit()
    finally:
        conn.close()
    return _load_lead(str(lead.get("id") or ""), str(lead.get("business_id") or ""))


def _enqueue_and_wait_parse(lead: dict[str, Any], user_id: str, timeout_seconds: int) -> tuple[dict[str, Any], str]:
    business, _created = admin_prospecting._ensure_parse_business_for_partnership_lead(lead, user_id)
    parse_business_id = str(business.get("id") or "").strip()
    if not parse_business_id:
        raise RuntimeError("parse_business_not_resolved")
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE prospectingleads SET parse_business_id = %s, updated_at = NOW() WHERE id = %s",
            (parse_business_id, str(lead.get("id") or "")),
        )
        conn.commit()
    finally:
        conn.close()

    source_url = str(business.get("yandex_url") or lead.get("source_url") or "").strip()
    last_error = ""
    for attempt in range(2):
        task = admin_prospecting._enqueue_parse_task_for_business(parse_business_id, user_id, source_url)
        task_id = str(task.get("id") or "")
        status, last_error = _wait_for_parse(task_id, timeout_seconds)
        if status in SUCCESS_PARSE_STATUSES:
            return task, status
        if attempt == 0 and status in {"failed", "error", "timeout"}:
            continue
        raise RuntimeError(f"parse_{status}:{last_error}")
    raise RuntimeError(f"parse_failed:{last_error}")


def _build_audit_and_room(
    lead: dict[str, Any],
    *,
    business_id: str,
    user_id: str,
) -> dict[str, Any]:
    lead = admin_prospecting._sync_partnership_lead_from_parsed_data(lead)
    conn = get_db_connection()
    try:
        admin_prospecting._ensure_partnership_artifacts_table(conn)
        admin_prospecting._ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()
        audit_slug, audit_url, page_json = admin_prospecting._create_admin_public_audit_for_lead(
            cur,
            lead=lead,
            user_id=user_id,
            source_type="partnership_partner",
        )
        audit = page_json.get("audit") if isinstance(page_json.get("audit"), dict) else {}
        quality = page_json.get("quality") if isinstance(page_json.get("quality"), dict) else {}
        cur.execute(
            """
            INSERT INTO partnershipleadartifacts (lead_id, audit_json, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (lead_id) DO UPDATE
            SET audit_json = EXCLUDED.audit_json,
                updated_at = NOW()
            """,
            (str(lead.get("id") or ""), Json(audit)),
        )
        conn.commit()
    finally:
        conn.close()

    room_result = admin_prospecting._prepare_partnership_sales_room(
        lead_id=str(lead.get("id") or ""),
        business_id=business_id,
        user_id=user_id,
        data_mode=admin_prospecting.SALES_ROOM_DATA_TEMPLATE,
        channel="manual",
        reuse_existing=True,
        audit_offer={
            "enabled": True,
            "status": "prepared",
            "lead_id": str(lead.get("id") or ""),
            "lead_email": str(lead.get("email") or ""),
            "company_name": str(lead.get("name") or ""),
            "company_map_url": str(lead.get("source_url") or ""),
            "company_address": str(lead.get("address") or ""),
            "platform": "yandex",
            "prepared_audit_slug": audit_slug,
            "prepared_audit_url": audit_url,
        },
    )
    if room_result.get("error"):
        raise RuntimeError(str(room_result.get("error")))
    room = room_result.get("room") if isinstance(room_result.get("room"), dict) else {}
    return {
        "audit_url": audit_url,
        "profile": str(audit.get("audit_profile") or ""),
        "quality": quality,
        "room_url": str(room.get("public_url") or admin_prospecting._make_sales_room_url(str(room.get("slug") or ""))),
        "room_reused": bool(room_result.get("reused")),
    }


def _execute_lead(
    lead: dict[str, Any],
    search_result: dict[str, Any],
    *,
    business_id: str,
    user_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    result = dict(search_result)
    if result.get("status") != "confirmed":
        return result
    try:
        lead = _persist_match(lead, result)
        _task, parse_status = _enqueue_and_wait_parse(lead, user_id, timeout_seconds)
        lead = _load_lead(str(lead.get("id") or ""), business_id)
        generated = _build_audit_and_room(lead, business_id=business_id, user_id=user_id)
        result.update(generated)
        result["parse_status"] = parse_status
        result["status"] = "ready"
        result["qa"] = "passed" if generated.get("quality", {}).get("passed") else "blocked"
        result["reason"] = ""
    except admin_prospecting.AuditQualityError:
        quality_error = sys.exc_info()[1]
        result["status"] = "blocked"
        result["qa"] = "blocked"
        result["quality"] = quality_error.quality if isinstance(quality_error, admin_prospecting.AuditQualityError) else {}
        result["reason"] = "audit_quality_blocked"
    except Exception:
        result["status"] = "failed"
        result["qa"] = "failed"
        result["reason"] = str(sys.exc_info()[1])
    return result


def _write_reports(rows: list[dict[str, Any]], json_path: Path, csv_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(_json_value(rows), ensure_ascii=False, indent=2), encoding="utf-8")
    columns = [
        "lead_id", "company", "source_document", "map_url", "confidence", "profile",
        "audit_url", "room_url", "status", "qa", "reason",
    ]
    handle = csv_path.open("w", encoding="utf-8-sig", newline="")
    try:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    finally:
        handle.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--business-id", required=True)
    parser.add_argument("--user-id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--lead-id", action="append", default=[])
    parser.add_argument("--timeout-seconds", type=int, default=600)
    parser.add_argument("--json-report", default="")
    parser.add_argument("--csv-report", default="")
    args = parser.parse_args()

    leads, owner_id = _load_context(args.business_id)
    user_id = str(args.user_id or owner_id).strip()
    selected_ids = {str(item).strip() for item in args.lead_id if str(item).strip()}
    if selected_ids:
        leads = [lead for lead in leads if str(lead.get("id") or "") in selected_ids]
    if args.limit > 0:
        leads = leads[: args.limit]

    search_executor = ThreadPoolExecutor(max_workers=2)
    try:
        search_futures = {search_executor.submit(_search_lead, lead): lead for lead in leads}
        searched: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for future in as_completed(search_futures):
            lead = search_futures[future]
            searched.append((lead, future.result()))
    finally:
        search_executor.shutdown(wait=True)
    searched.sort(key=lambda item: str(item[1].get("company") or ""))

    if args.execute:
        execute_executor = ThreadPoolExecutor(max_workers=2)
        try:
            execute_futures = {
                execute_executor.submit(
                    _execute_lead,
                    lead,
                    result,
                    business_id=args.business_id,
                    user_id=user_id,
                    timeout_seconds=max(30, args.timeout_seconds),
                ): result
                for lead, result in searched
            }
            rows = [future.result() for future in as_completed(execute_futures)]
        finally:
            execute_executor.shutdown(wait=True)
        rows.sort(key=lambda item: str(item.get("company") or ""))
    else:
        rows = [result for _lead, result in searched]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_dir = Path(os.environ.get("PARTNER_AUDIT_REPORT_DIR") or ROOT / "artifacts")
    json_path = Path(args.json_report) if args.json_report else report_dir / f"partner_audit_rooms_{timestamp}.json"
    csv_path = Path(args.csv_report) if args.csv_report else report_dir / f"partner_audit_rooms_{timestamp}.csv"
    _write_reports(rows, json_path, csv_path)
    summary: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
    print(json.dumps({"summary": summary, "json_report": str(json_path), "csv_report": str(csv_path)}, ensure_ascii=False))
    return 0 if not any(row.get("status") == "failed" for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
