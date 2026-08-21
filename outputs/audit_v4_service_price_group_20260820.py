#!/usr/bin/env python3
"""Read-only live Apify audit for exact v4 service-price first touches."""

from __future__ import annotations

import datetime
import json
import re
import time
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import get_db_connection
from services.prospecting_service import ProspectingService


MANIFEST = Path("/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json")
EXPECTED_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
TARGET_TOUCH_IDS = {
    "4b3d9794-55a6-4d0b-9bcc-c63644356e72",
    "ec975c57-da8b-40fb-95a3-9b325e273910",
    "0f840f7c-9748-4902-a294-e3a79bca530c",
    "db834cc1-7ea5-4923-9145-e7a59bc42a96",
    "f03f1759-9992-4720-adf7-661f9cba82f3",
    "dabb08e9-9484-4be2-ad8c-041ac6805d69",
    "a1343995-06f4-4832-9544-6fae7bbb56b9",
    "df0d4811-723c-42a1-b91d-81e6a47f3672",
    "003d1a28-1ac3-44bb-a371-ae00d3696a69",
    "575bdcaa-1f9c-44dc-8401-5cb4512926c6",
    "79ed0287-3e45-4950-9148-c6340adba0be",
    "404c1efa-9b10-4fe9-9b54-6a76821e1871",
}


def expected_counts(item):
    observation = str((item.get("message_brief_json") or {}).get("observation") or "")
    match = re.search(r"всего услуг\s*-\s*(\d+);\s*с ценой\s*-\s*(\d+)", observation, re.I)
    if not match:
        raise RuntimeError(f"counts_missing:{item.get('touch_id')}")
    return int(match.group(1)), int(match.group(2))


def org_id(url):
    match = re.search(r"/(\d{6,})/?(?:reviews/?)?(?:[?#].*)?$", str(url or ""))
    return match.group(1) if match else ""


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")
    items = {row.get("touch_id"): row for row in manifest.get("touches") or [] if row.get("touch_id") in TARGET_TOUCH_IDS}
    if set(items) != TARGET_TOUCH_IDS:
        raise RuntimeError("target_manifest_rows_missing")

    connection = get_db_connection()
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    cursor.execute(
        """
        SELECT id, name, city, source_url, source_external_id, search_payload_json, updated_at
        FROM prospectingleads
        WHERE id IN (
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
        )
        """,
        tuple(items[touch_id]["lead_id"] for touch_id in sorted(items)),
    )
    leads = {str(row["id"]): dict(row) for row in cursor.fetchall()}
    connection.rollback()
    connection.close()

    targets = []
    for touch_id in sorted(items):
        item = items[touch_id]
        lead = leads.get(str(item.get("lead_id"))) or {}
        source_url = str(lead.get("source_url") or "").strip()
        source_external_id = str(lead.get("source_external_id") or org_id(source_url)).strip()
        if not source_url or not source_external_id:
            raise RuntimeError(f"map_identity_missing:{touch_id}")
        total, priced = expected_counts(item)
        targets.append(
            {
                "touch_id": touch_id,
                "lead_id": item.get("lead_id"),
                "name": item.get("name"),
                "recipient": item.get("recipient"),
                "source_url": source_url,
                "source_external_id": source_external_id,
                "expected_total": total,
                "expected_priced": priced,
                "cached_updated_at": lead.get("updated_at"),
            }
        )

    service = ProspectingService(source="apify_yandex")
    if not service.api_token:
        raise RuntimeError("APIFY_TOKEN_missing")
    run_input = service._build_run_input_for_map_url(targets[0]["source_url"], limit=len(targets))
    run_input["query"] = []
    run_input["location"] = ""
    run_input["maxResults"] = len(targets)
    run_input["maxPhotos"] = 0
    run_input["maxPosts"] = 0
    run_input["startUrls"] = [{"url": target["source_url"]} for target in targets]
    run_input["businessIds"] = [target["source_external_id"] for target in targets]
    meta = service._start_run_with_input(service._strip_none_values(run_input))
    run_id = str(meta.get("run_id") or "")
    dataset_id = str(meta.get("dataset_id") or "")
    status = str(meta.get("status") or "RUNNING").upper()
    started = datetime.datetime.now(datetime.timezone.utc)
    while status in {"READY", "RUNNING", "TIMING-OUT", "ABORTING"}:
        if (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds() > 420:
            raise TimeoutError("apify_service_group_timeout")
        time.sleep(4)
        run_data = service.get_run(run_id)
        status = str(run_data.get("status") or status).upper()
        dataset_id = str(run_data.get("defaultDatasetId") or dataset_id)
    if status != "SUCCEEDED":
        raise RuntimeError(f"apify_service_group_{status.lower()}")

    rows = service.fetch_dataset_items(dataset_id)
    by_org = {str(row.get("source_external_id") or ""): row for row in rows}
    audited = []
    for target in targets:
        live = by_org.get(target["source_external_id"])
        if not live:
            audited.append({**target, "verdict": "block", "reasons": ["current_map_entity_missing"]})
            continue
        payload = live.get("search_payload_json") or {}
        total = int(payload.get("services_total_count") or 0)
        priced = int(payload.get("services_with_price_count") or 0)
        identity_match = str(live.get("source_external_id") or "") == target["source_external_id"]
        reasons = []
        if not identity_match:
            reasons.append("map_identity_mismatch")
        if total != target["expected_total"]:
            reasons.append("service_total_changed")
        if priced != target["expected_priced"]:
            reasons.append("service_price_count_changed")
        if total <= 0 or priced >= total:
            reasons.append("service_price_gap_missing")
        audited.append(
            {
                **target,
                "current_name": live.get("name"),
                "current_source_url": live.get("source_url"),
                "current_total": total,
                "current_priced": priced,
                "checked_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "verdict": "exact_v4_fact_match" if not reasons else "block",
                "reasons": sorted(set(reasons)),
            }
        )
    print(json.dumps({"status": status, "target_count": len(targets), "result_count": len(rows), "items": audited}, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
