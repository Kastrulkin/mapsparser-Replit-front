#!/usr/bin/env python3
"""Export canonical LocalOS campaign drafts into outreach-system review records.

This command is read-only. It creates review/transport JSON and never changes
campaign state, approval, queue state, sender permissions, or delivery state.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.pg_db_utils import get_db_connection


QUALITY_CRITERIA = (
    ("source validity", "fact"),
    ("observation accuracy", "specificity"),
    ("freshness and why-now", "freshness"),
    ("bridge from signal to offer", "bridge"),
    ("recipient specificity", "removal"),
    ("proof integrity", "proof_integrity"),
    ("natural channel fit", "channel_fit"),
    ("single CTA and length", "single_cta"),
    ("state and suppression safety", "suppression_safety"),
)


def _confidence(value: Any) -> str:
    numeric = float(value or 0)
    return "high" if numeric >= 0.8 else "medium" if numeric >= 0.6 else "low"


def _email_status(value: Any) -> str:
    status = str(value or "")
    if status == "verified":
        return "verified"
    if status in {"confirmed_source", "accept_all"}:
        return "risky"
    if status == "invalid":
        return "invalid"
    return "unknown"


def _cta(body: str) -> str:
    questions = re.findall(r"(?:^|(?<=[.!]))\s*([^.!?]*\?)", body)
    return questions[-1].strip() if questions else ""


def _evidence_source_type(item: dict[str, Any]) -> str:
    source_type = str(item.get("source_type") or "").strip()
    if source_type:
        return source_type
    source_url = str(item.get("source_url") or "")
    return "localos_public_audit" if "localos.pro/" in source_url else "public_map"


def _record(
    cursor: Any,
    campaign: dict[str, Any],
    generated_at: str,
    only_channel: str | None,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT t.*, cp.value AS contact_value, cp.source_url AS contact_source_url,
               cp.observed_at AS contact_observed_at, cp.confidence AS contact_confidence,
               cp.verification_status AS contact_verification_status
        FROM outreach_campaign_touches t
        LEFT JOIN lead_contact_points cp ON cp.id = t.contact_point_id
        WHERE t.campaign_id = %s
        ORDER BY t.sequence_index
        """,
        (campaign["campaign_id"],),
    )
    all_touches = [dict(row) for row in cursor.fetchall()]
    touches = (
        [touch for touch in all_touches if touch.get("channel") == only_channel]
        if only_channel
        else all_touches
    )
    if not touches:
        raise RuntimeError(f"{campaign['lead_name']}: no {only_channel or 'campaign'} touches")
    cursor.execute(
        """
        SELECT * FROM lead_workstream_research
        WHERE workstream_id = %s
        ORDER BY researched_at DESC, created_at DESC LIMIT 1
        """,
        (campaign["workstream_id"],),
    )
    research = dict(cursor.fetchone() or {})
    evidence_items = research.get("evidence_json") if isinstance(research.get("evidence_json"), list) else []
    candidate_items = (
        research.get("personalization_candidates_json")
        if isinstance(research.get("personalization_candidates_json"), list)
        else []
    )
    used_evidence_ids = {
        str((touch.get("message_brief_json") or {}).get("evidence_id") or "")
        for touch in touches
    }
    evidence = []
    for item in evidence_items:
        evidence_id = str(item.get("id") or item.get("evidence_id") or "")
        if not evidence_id or evidence_id not in used_evidence_ids:
            continue
        evidence.append({
            "evidence_id": evidence_id,
            "kind": str(item.get("kind") or "public_signal"),
            "observation": str(item.get("fact") or item.get("observed_fact") or ""),
            "source_url": str(item.get("source_url") or ""),
            "source_type": _evidence_source_type(item),
            "source_date": str(item.get("observed_at") or research.get("researched_at") or generated_at),
            "researched_at": str(research.get("researched_at") or generated_at),
            "confidence": _confidence(item.get("confidence")),
            "usable_for_outreach": True,
        })
    candidates = []
    for item in candidate_items:
        evidence_id = str(item.get("evidence_id") or "")
        if evidence_id not in used_evidence_ids:
            continue
        candidates.append({
            "personalization_id": str(item.get("id") or ""),
            "evidence_ids": [evidence_id],
            "observation": str(item.get("observed_fact") or ""),
            "problem_hypothesis": "Не установлена; сообщение опирается только на публичный факт.",
            "relevance_to_offer": str(item.get("bridge") or ""),
            "personalized_opener": str(touches[0].get("generated_text") or ""),
            "confidence": _confidence(item.get("confidence")),
            "usable": True,
            "removal_test_passed": True,
        })
    email_touch = next((touch for touch in all_touches if touch.get("channel") == "email"), None)
    if not email_touch or not email_touch.get("contact_value"):
        raise RuntimeError(f"{campaign['lead_name']}: selected email contact is missing")
    contact = {
        "channel": "email",
        "value": str(email_touch["contact_value"]),
        "source_url": str(email_touch.get("contact_source_url") or campaign.get("source_url") or ""),
        "observed_at": str(email_touch.get("contact_observed_at") or generated_at),
        "confidence": _confidence(email_touch.get("contact_confidence")),
        "email_status": _email_status(email_touch.get("contact_verification_status")),
    }
    rendered_touches = []
    for review_index, touch in enumerate(touches, 1):
        brief = touch.get("message_brief_json") if isinstance(touch.get("message_brief_json"), dict) else {}
        rendered_touches.append({
            "touch_no": review_index if only_channel else int(touch["sequence_index"]) + 1,
            "channel": str(touch["channel"]),
            "angle": str(touch.get("angle_type") or ""),
            "subject": str(touch.get("subject") or ""),
            "body": str(touch.get("generated_text") or ""),
            "cta": _cta(str(touch.get("generated_text") or "")),
            "evidence_ids": [str(brief.get("evidence_id") or "")],
            "day_offset": 0 if only_channel else int((touch.get("strategy_json") or {}).get("day_offset") or 0),
            "channel_status": str(brief.get("channel_status") or ""),
        })
    first_gate = touches[0].get("quality_gate_json") if isinstance(touches[0].get("quality_gate_json"), dict) else {}
    checks = first_gate.get("checks") if isinstance(first_gate.get("checks"), dict) else {}
    criteria = [
        {
            "name": name,
            "score": 2 if checks.get(check) else 0,
            "note": "passed" if checks.get(check) else "failed",
        }
        for name, check in QUALITY_CRITERIA
    ]
    public_urls = []
    for value in (campaign.get("website"), campaign.get("source_url")):
        url = str(value or "").strip()
        if url and url not in public_urls:
            public_urls.append(url)
    score_breakdown = research.get("score_breakdown") if isinstance(research.get("score_breakdown"), dict) else {}
    disqualifiers = score_breakdown.get("disqualifiers") if isinstance(score_breakdown.get("disqualifiers"), list) else []
    selected_id = str(research.get("selected_personalization_id") or "")
    if not selected_id and candidates:
        selected_id = str(candidates[0]["personalization_id"])
    risks = [
        "Email опубликован в публичном источнике, но точная доставляемость не проверена; status=risky.",
        "Email sender подключён, но outreach permission выключен.",
    ]
    if not only_channel:
        risks.append(
            "Telegram platform sender не подключён; автоматическая мультиканальная цепочка недоступна."
        )
    return {
        "schema_version": "1.0",
        "lead_id": str(campaign["lead_id"]),
        "motion": "localos_sales",
        "identity": {
            "company_name": str(campaign["lead_name"]),
            "contact_name": "",
            "contact_role": "владелец или управляющий",
            "public_urls": public_urls,
        },
        "contacts": [contact],
        "qualification": {
            "segment": str(campaign.get("category") or ""),
            "icp_score": max(0, min(int(research.get("score") or 0), 100)),
            "disqualifiers": disqualifiers,
        },
        "evidence": evidence,
        "personalization_candidates": candidates,
        "selected_personalization_id": selected_id,
        "touches": rendered_touches,
        "quality_gate": {
            "score": int(first_gate.get("score") or 0),
            "max_score": 18,
            "verdict": str(first_gate.get("verdict") or "reject"),
            "criteria": criteria,
            "reason_codes": list(first_gate.get("reason_codes") or []),
        },
        "approval": {
            "status": "needs_review",
            "approved_by": None,
            "approved_at": None,
            "external_send_authorized": False,
        },
        "campaign": {
            "id": str(campaign["campaign_id"]),
            "version": int(campaign["version"]),
            "status": "draft",
            "review_variant": f"{only_channel}_single_touch" if only_channel else "full_sequence",
            "dispatch_enabled": False,
            "external_send_performed": False,
        },
        "outcome": {
            "reply_status": "none",
            "unsubscribe": False,
            "suppressed": False,
        },
        "risks": risks,
        "generated_at": generated_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True)
    parser.add_argument("--version", required=True, type=int)
    parser.add_argument("--lead", action="append", dest="leads", required=True)
    parser.add_argument("--only-channel", choices=("telegram", "email", "whatsapp", "max"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--split-dir", type=Path)
    args = parser.parse_args()
    generated_at = datetime.now(timezone.utc).isoformat()
    connection = get_db_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT c.id AS campaign_id, c.version, c.workstream_id, c.lead_id,
                   l.name AS lead_name, l.category, l.website, l.source_url
            FROM outreach_campaigns c
            JOIN prospectingleads l ON l.id = c.lead_id
            WHERE l.pilot_cohort = %s AND c.version = %s AND c.status = 'draft'
              AND l.name = ANY(%s)
            ORDER BY ARRAY_POSITION(%s, l.name)
            """,
            (args.cohort, args.version, args.leads, args.leads),
        )
        campaigns = [dict(row) for row in cursor.fetchall()]
        if len(campaigns) != len(args.leads):
            found = {campaign["lead_name"] for campaign in campaigns}
            missing = [lead for lead in args.leads if lead not in found]
            raise RuntimeError(f"Draft campaigns not found: {', '.join(missing)}")
        records = [
            _record(cursor, campaign, generated_at, args.only_channel)
            for campaign in campaigns
        ]
    finally:
        connection.rollback()
        cursor.close()
        connection.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.split_dir:
        args.split_dir.mkdir(parents=True, exist_ok=True)
        for index, record in enumerate(records, 1):
            slug = re.sub(r"[^a-zа-яё0-9]+", "-", record["identity"]["company_name"].lower()).strip("-")
            (args.split_dir / f"{index:02d}-{slug}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    print(f"Wrote {args.output} ({len(records)} review records, external_send_performed=false)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
