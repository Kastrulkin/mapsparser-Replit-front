#!/usr/bin/env python3
"""Read-only audit of the LocalOS first-touch cohort against manifest v4."""

import collections
import concurrent.futures
import datetime
import hashlib
import json
import os
import re
import sys
import urllib.parse

import psycopg2
import requests
from psycopg2.extras import RealDictCursor


MANIFEST_PATH = "/app/debug_data/localos-1000-safe-final-manifest-v4-20260814.json"
CURRENT_BLOCKLIST_PATH = "/app/debug_data/localos-goal-current-fact-blocklist-20260816.json"
EXPECTED_CANONICAL_SHA = "4b21c0f98df7a726e0afae3504692e0b7c2a4faace8cdddf733590257a46a386"
OUTPUT_PATH = "/app/debug_data/localos-first-touch-safe-audit-20260820.json"

QUARANTINE_NAMES = {
    "laser prolab",
    "pro skin",
    "pro лицо тело",
    "your face clinic",
    "yourwings",
    "аристократка",
    "благодатная",
    "грейс клуб",
    "отражение",
    "ремеди",
    "эсма",
}

UNSUITABLE_LOCAL_PARTS = re.compile(
    r"(^|[._-])(no.?reply|donotreply|hr|career|careers|job|jobs|vacancy|resume|"
    r"press|support|help|security|abuse|postmaster|webmaster|privacy|legal|billing|"
    r"accounting|zakaz|order|booking|reservation|reception|call.?center|desk)([._-]|$)",
    re.IGNORECASE,
)


def normalized_name(value):
    return re.sub(r"[^a-zа-я0-9]+", "", (value or "").lower().replace("ё", "е"))


def host(value):
    try:
        return urllib.parse.urlparse(value or "").netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def fetch_page(item):
    url = item["contact_source_url"]
    result = {
        "lead_id": item["lead_id"],
        "url": url,
        "ok": False,
        "status_code": None,
        "final_url": None,
        "email_visible": False,
        "error": None,
    }
    try:
        response = requests.get(
            url,
            timeout=15,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; LocalOSContactAudit/1.0; +https://localos.pro)"
            },
        )
        body = response.text.lower()
        email = (item["email"] or "").lower()
        compact_body = re.sub(r"\s+", "", body)
        result.update(
            {
                "ok": 200 <= response.status_code < 400,
                "status_code": response.status_code,
                "final_url": response.url,
                "email_visible": email in body or email.replace("@", "&#64;") in body or email.replace("@", "[at]") in compact_body,
                "content_bytes": len(response.content),
            }
        )
    except requests.RequestException:
        result["error"] = "request_failed"
    return result


def main():
    manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
    if manifest.get("schema_version") != "localos_1000_safe_final_manifest_v4":
        raise RuntimeError("manifest_v4_required")
    if manifest.get("canonical_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("manifest_canonical_sha_mismatch")

    blocklist = json.load(open(CURRENT_BLOCKLIST_PATH, encoding="utf-8"))
    if blocklist.get("base_manifest_sha256") != EXPECTED_CANONICAL_SHA:
        raise RuntimeError("blocklist_manifest_mismatch")
    manifest_touch_to_lead = {
        item.get("touch_id"): item.get("lead_id") for item in manifest.get("touches", [])
    }
    current_blocked_leads = {
        manifest_touch_to_lead.get(item.get("touch_id")) for item in blocklist.get("blocks", [])
    }
    current_blocked_leads.discard(None)

    connection = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    connection.set_session(readonly=True, autocommit=False)
    cursor = connection.cursor()
    cursor.execute("SET TRANSACTION READ ONLY")
    cursor.execute(
        """
        WITH contacted AS (
            SELECT DISTINCT campaign.lead_id
            FROM outreach_campaigns campaign
            JOIN outreach_campaign_touches touch ON touch.campaign_id = campaign.id
            WHERE touch.status IN ('sent', 'manual_sent')
        ), verified AS (
            SELECT DISTINCT lead_id
            FROM lead_contact_points
            WHERE contact_type = 'email'
              AND verification_status IN ('confirmed_source', 'valid_format', 'found')
        ), blocked AS (
            SELECT DISTINCT lead_id
            FROM outreach_suppressions
            WHERE expires_at IS NULL OR expires_at > NOW()
            UNION
            SELECT DISTINCT lead_id
            FROM outreach_inbound_events
            WHERE is_human OR stops_campaign
        ), ranked AS (
            SELECT workstream.id workstream_id,
                   workstream.lead_id,
                   workstream.lifecycle_status,
                   lead.name,
                   lead.city,
                   lead.address,
                   lead.phone,
                   lead.website,
                   lead.source_url,
                   lead.company_id,
                   lead.company_location_id,
                   lead.source_external_id,
                   lead.external_place_id,
                   lower(coalesce(contact.normalized_value, lead.email)) email,
                   contact.source_url contact_source_url,
                   contact.verification_status,
                   contact.observed_at,
                   contact.verified_at,
                   contact.stale_after,
                   row_number() OVER (
                       PARTITION BY workstream.lead_id
                       ORDER BY CASE contact.verification_status
                           WHEN 'confirmed_source' THEN 1
                           WHEN 'valid_format' THEN 2
                           ELSE 3
                       END, contact.updated_at DESC
                   ) row_number
            FROM lead_workstreams workstream
            JOIN prospectingleads lead ON lead.id = workstream.lead_id
            JOIN verified ON verified.lead_id = workstream.lead_id
            LEFT JOIN contacted ON contacted.lead_id = workstream.lead_id
            LEFT JOIN blocked ON blocked.lead_id = workstream.lead_id
            LEFT JOIN lead_contact_points contact
              ON contact.lead_id = workstream.lead_id
             AND contact.contact_type = 'email'
             AND contact.verification_status IN ('confirmed_source', 'valid_format', 'found')
            WHERE workstream.workstream_type = 'localos_sales'
              AND contacted.lead_id IS NULL
              AND blocked.lead_id IS NULL
        )
        SELECT * FROM ranked WHERE row_number = 1 ORDER BY name, lead_id
        """
    )
    candidates = [dict(row) for row in cursor.fetchall()]

    cursor.execute(
        """
        SELECT lower(normalized_value) email, count(DISTINCT lead_id) lead_count
        FROM lead_contact_points
        WHERE contact_type = 'email'
        GROUP BY lower(normalized_value)
        """
    )
    global_email_counts = {row["email"]: row["lead_count"] for row in cursor.fetchall()}

    cursor.execute(
        """
        WITH contacted AS (
            SELECT DISTINCT campaign.lead_id
            FROM outreach_campaigns campaign
            JOIN outreach_campaign_touches touch ON touch.campaign_id = campaign.id
            WHERE touch.status IN ('sent', 'manual_sent')
        )
        SELECT DISTINCT lower(contact.normalized_value) email
        FROM contacted
        JOIN lead_contact_points contact
          ON contact.lead_id = contacted.lead_id
         AND contact.contact_type = 'email'
        UNION
        SELECT DISTINCT lower(recipient_value)
        FROM outreachsendqueue
        WHERE delivery_status = 'sent' AND channel = 'email'
        """
    )
    contacted_emails = {row["email"] for row in cursor.fetchall() if row["email"]}

    cursor.execute(
        """
        SELECT DISTINCT campaign.lead_id
        FROM outreach_sender_health_events health
        JOIN outreach_campaigns campaign ON campaign.id = health.campaign_id
        WHERE health.event_type = 'delivery_failed'
          AND health.provider_code IN ('mail_host_unresolvable', 'email_transport_failed')
        """
    )
    failed_email_leads = {row["lead_id"] for row in cursor.fetchall()}

    cursor.execute(
        """
        SELECT DISTINCT ON (research.workstream_id)
               research.workstream_id,
               research.researched_at,
               research.opener_source_url,
               research.suggested_opener,
               research.sources_json,
               research.evidence_json,
               research.personalization_candidates_json,
               research.selected_personalization_id,
               research.message_readiness_json,
               research.outreach_decision_json
        FROM lead_workstream_research research
        ORDER BY research.workstream_id, research.researched_at DESC, research.created_at DESC
        """
    )
    research_by_workstream = {row["workstream_id"]: dict(row) for row in cursor.fetchall()}
    connection.rollback()
    connection.close()

    group_fields = {
        "email": lambda item: item.get("email"),
        "company": lambda item: item.get("company_id"),
        "location": lambda item: item.get("company_location_id"),
        "external": lambda item: item.get("source_external_id") or item.get("external_place_id"),
        "name_city": lambda item: normalized_name(item.get("name")) + "|" + normalized_name(item.get("city")),
    }
    duplicate_ids = set()
    duplicate_groups = []
    for kind, getter in group_fields.items():
        groups = collections.defaultdict(list)
        for item in candidates:
            key = getter(item)
            if key:
                groups[key].append(item)
        for key, items in groups.items():
            if len(items) > 1:
                duplicate_ids.update(item["lead_id"] for item in items)
                duplicate_groups.append(
                    {
                        "kind": kind,
                        "key_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
                        "lead_ids": [item["lead_id"] for item in items],
                        "names": [item["name"] for item in items],
                    }
                )

    exclusion_counts = collections.Counter()
    audited = []
    for item in candidates:
        reasons = []
        if item["lead_id"] in duplicate_ids:
            reasons.append("DUPLICATE_CLUSTER")
        if global_email_counts.get(item["email"], 0) > 1:
            reasons.append("GLOBAL_EMAIL_ALIAS")
        if item["email"] in contacted_emails:
            reasons.append("RECIPIENT_ALREADY_CONTACTED")
        if item["lead_id"] in current_blocked_leads:
            reasons.append("CURRENT_FACT_BLOCKLIST")
        if normalized_name(item["name"]) in {normalized_name(value) for value in QUARANTINE_NAMES}:
            reasons.append("INCIDENT_QUARANTINE")
        if item["lead_id"] in failed_email_leads:
            reasons.append("DELIVERY_FAILURE_HISTORY")
        local_part = (item["email"] or "").split("@", 1)[0]
        if UNSUITABLE_LOCAL_PARTS.search(local_part):
            reasons.append("UNSUITABLE_RECIPIENT_ROLE")
        if item["verification_status"] != "confirmed_source":
            reasons.append("EMAIL_NOT_SOURCE_CONFIRMED")
        if not (item["contact_source_url"] or "").startswith(("http://", "https://")):
            reasons.append("CONTACT_SOURCE_MISSING")
        if item["lifecycle_status"] != "ready_for_draft":
            reasons.append("NOT_READY_FOR_DRAFT")
        if item.get("stale_after") and item["stale_after"] < datetime.datetime.now(datetime.timezone.utc):
            reasons.append("CONTACT_SOURCE_STALE")
        for reason in set(reasons):
            exclusion_counts[reason] += 1
        research = research_by_workstream.get(item["workstream_id"])
        audited.append(
            {
                **item,
                "preflight_reasons": sorted(set(reasons)),
                "research": research,
                "website_host": host(item.get("website")),
                "contact_source_host": host(item.get("contact_source_url")),
            }
        )

    live_targets = [item for item in audited if not item["preflight_reasons"]]
    live_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_page, item) for item in live_targets]
        for future in concurrent.futures.as_completed(futures):
            fetched = future.result()
            live_results[fetched["lead_id"]] = fetched

    review_queue = []
    hold_queue = []
    for item in live_targets:
        live = live_results[item["lead_id"]]
        research = item.get("research") or {}
        reasons = []
        if not live["ok"]:
            reasons.append("CONTACT_PAGE_UNAVAILABLE")
        if not live["email_visible"]:
            reasons.append("EMAIL_NOT_VISIBLE_ON_CURRENT_SOURCE")
        if not research:
            reasons.append("RESEARCH_MISSING")
        if not research.get("opener_source_url"):
            reasons.append("OBSERVATION_SOURCE_MISSING")
        if not research.get("selected_personalization_id"):
            reasons.append("PERSONALIZATION_NOT_SELECTED")
        result = {
            "lead_id": item["lead_id"],
            "workstream_id": item["workstream_id"],
            "name": item["name"],
            "city": item["city"],
            "website": item["website"],
            "map_source_url": item["source_url"],
            "contact_source_url": item["contact_source_url"],
            "contact_verified_at": item["verified_at"],
            "live_contact_check": live,
            "researched_at": research.get("researched_at"),
            "observation_source_url": research.get("opener_source_url"),
            "suggested_opener": research.get("suggested_opener"),
            "selected_personalization_id": research.get("selected_personalization_id"),
            "hold_reasons": sorted(set(reasons)),
            "approval_state": "not_approved",
            "campaign_state": "not_queued",
        }
        if reasons:
            hold_queue.append(result)
        else:
            review_queue.append(result)

    payload = {
        "schema_version": "localos_first_touch_safe_audit_v1",
        "generated_at": datetime.datetime.now(datetime.timezone.utc),
        "manifest": {
            "path": MANIFEST_PATH,
            "schema_version": manifest.get("schema_version"),
            "file_sha256": sha256_file(MANIFEST_PATH),
            "canonical_sha256": manifest.get("canonical_sha256"),
            "touch_count": len(manifest.get("touches", [])),
        },
        "database_source": "PostgreSQL LocalOS read-only transaction",
        "funnel": {
            "no_confirmed_touch": 1078,
            "email_stored": 507,
            "email_verified": 473,
            "suppression_reply_safe": len(candidates),
            "ready_for_draft": sum(item["lifecycle_status"] == "ready_for_draft" for item in candidates),
            "structural_preflight_pass": len(live_targets),
            "safe_for_first_touch_review": len(review_queue),
            "live_check_hold": len(hold_queue),
        },
        "incident_quarantine_names": sorted(QUARANTINE_NAMES),
        "incident_quarantine_count": len(QUARANTINE_NAMES),
        "duplicate_groups": duplicate_groups,
        "duplicate_lead_count": len(duplicate_ids),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "review_queue": review_queue,
        "live_check_hold": hold_queue,
        "safety": {
            "database_mutations": 0,
            "drafts_created": 0,
            "approved": 0,
            "queued": 0,
            "sent": 0,
        },
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(
        json.dumps(
            {
                "funnel": payload["funnel"],
                "duplicate_lead_count": payload["duplicate_lead_count"],
                "exclusion_counts": payload["exclusion_counts"],
                "review_names": [item["name"] for item in review_queue],
                "hold": [
                    {"name": item["name"], "reasons": item["hold_reasons"]}
                    for item in hold_queue
                ],
                "safety": payload["safety"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("audit_failed", file=sys.stderr)
        raise
