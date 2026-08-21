#!/usr/bin/env python3
"""Select exactly 50 disjoint, safe LocalOS leads for Party 3.

Read-only. Writes only the review selection artifact.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from database_manager import get_db_connection


PARTY_NUMBER = int(os.environ.get("LOCALOS_PARTY_NUMBER", "3"))
SEEDS = Path("/app/debug_data/localos-party2-seed-ready-artifacts-20260811.json")
PRIOR_PARTIES = (
    Path("/app/debug_data/localos-template-review-v12-20260811.json"),
    *(
        Path(f"/app/debug_data/localos-party{number}-review-v1-20260811.json")
        for number in range(2, PARTY_NUMBER)
    ),
)
OUTPUT = Path(f"/app/debug_data/localos-party{PARTY_NUMBER}-selection-20260811.json")


TERMINAL_LEAD_STATUSES = {
    "sent", "responded", "replied", "disqualified", "rejected",
    "not_relevant", "converted",
}
TERMINAL_PIPELINE_STATUSES = {
    "contacted", "waiting_reply", "second_message_sent", "replied",
    "converted", "closed_lost", "not_relevant", "disqualified",
    "rejected", "sent", "dialog",
}
TERMINAL_WORKSTREAM_STATUSES = TERMINAL_PIPELINE_STATUSES


def canonical_sha(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    seed_payload = json.loads(SEEDS.read_text(encoding="utf-8"))
    seeds = list(seed_payload["seeds"])
    prior_lead_ids = [
        str(item["lead_id"])
        for path in PRIOR_PARTIES
        for item in json.loads(path.read_text(encoding="utf-8"))["results"]
    ]
    lead_ids = [str(item["lead_id"]) for item in seeds]
    workstream_ids = [str(item["workstream_id"]) for item in seeds]
    connection = get_db_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute(
            """
            SELECT l.id AS lead_id,l.name,l.city,l.address,l.category,l.status AS lead_status,
                   l.pipeline_status,l.last_contact_at,l.next_action_at,l.deferred_until,
                   w.id AS workstream_id,w.status AS workstream_status,
                   w.lifecycle_status,w.last_contact_at AS workstream_last_contact_at,
                   w.next_action_at AS workstream_next_action_at,w.workstream_type,
                   research.score,research.qualification_stage,research.signal_label,
                   research.researched_at,research.signals_json,research.sources_json,
                   research.contact_evidence_json,research.message_brief_json,
                   research.limitations_json
            FROM prospectingleads l
            JOIN lead_workstreams w ON w.lead_id=l.id
            LEFT JOIN LATERAL (
              SELECT * FROM lead_workstream_research r
              WHERE r.workstream_id=w.id
              ORDER BY r.researched_at DESC,r.created_at DESC LIMIT 1
            ) research ON TRUE
            WHERE w.workstream_type='localos_sales'
              AND (
                l.id=ANY(%s)
                OR research.researched_at >= NOW() - INTERVAL '90 days'
              )
            """,
            (lead_ids,),
        )
        rows = [dict(row) for row in cursor.fetchall()]
        row_by_workstream = {str(row["workstream_id"]): row for row in rows}

        seeded_workstreams = {str(item["workstream_id"]) for item in seeds}
        for row in rows:
            workstream_id = str(row["workstream_id"])
            if workstream_id in seeded_workstreams:
                continue
            seeds.append(
                {
                    "lead_id": str(row["lead_id"]),
                    "workstream_id": workstream_id,
                    "name": row.get("name"),
                    "rank": None,
                    "prior_classification": "current_production_expansion",
                }
            )
        lead_ids = [str(item["lead_id"]) for item in seeds]
        workstream_ids = [str(item["workstream_id"]) for item in seeds]

        cursor.execute(
            """
            SELECT cp.lead_id,cp.id,cp.contact_type,cp.value,cp.normalized_value,
                   cp.verification_status,cp.source_type,cp.source_url,cp.verified_at,
                   cp.metadata_json
            FROM lead_contact_points cp
            WHERE cp.lead_id=ANY(%s)
            ORDER BY cp.lead_id,cp.created_at,cp.id
            """,
            (lead_ids + prior_lead_ids,),
        )
        contacts_by_lead: dict[str, list[dict[str, Any]]] = {}
        for row in cursor.fetchall():
            item = dict(row)
            contacts_by_lead.setdefault(str(item["lead_id"]), []).append(item)

        cursor.execute(
            """
            SELECT l.id AS lead_id,
              (SELECT COUNT(*) FROM outreachsendqueue q WHERE q.lead_id=l.id
                AND (q.sent_at IS NOT NULL OR q.delivery_status IN ('queued','retry','sending','sent','delivered'))) AS queue_or_sent,
              (SELECT COUNT(*) FROM outreach_campaign_touches t JOIN outreach_campaigns c ON c.id=t.campaign_id
                WHERE c.lead_id=l.id AND t.status IN ('sent','delivered','manual_sent','reply_cancelled')) AS sent_history,
              (SELECT COUNT(*) FROM outreach_inbound_events i WHERE i.lead_id=l.id AND COALESCE(i.is_human,FALSE)=TRUE) AS human_inbound,
              (SELECT COUNT(*) FROM outreachreactions r WHERE r.lead_id=l.id) AS reactions,
              (SELECT COUNT(*) FROM outreach_suppressions s WHERE s.lead_id=l.id
                AND (s.expires_at IS NULL OR s.expires_at>NOW())) AS active_suppressions,
              (SELECT COUNT(*) FROM outreach_campaigns c WHERE c.lead_id=l.id AND c.status<>'draft') AS non_draft_campaigns
            FROM prospectingleads l WHERE l.id=ANY(%s)
            """,
            (lead_ids,),
        )
        safety_by_lead = {str(row["lead_id"]): dict(row) for row in cursor.fetchall()}
        connection.rollback()
    finally:
        connection.close()

    def route_keys(lead_id: str) -> set[str]:
        return {
            f"{str(contact.get('contact_type') or '').lower()}:{str(contact.get('normalized_value') or contact.get('value') or '').strip().lower()}"
            for contact in contacts_by_lead.get(lead_id, [])
            if str(contact.get("verification_status") or "") in {"verified", "confirmed_source"}
            and str(contact.get("contact_type") or "") in {"email", "telegram", "vk", "phone", "whatsapp", "max"}
            and bool(contact.get("normalized_value") or contact.get("value"))
        }

    prior_route_keys = set().union(*(route_keys(lead_id) for lead_id in prior_lead_ids))
    records: list[dict[str, Any]] = []
    for seed in seeds:
        lead_id = str(seed["lead_id"])
        workstream_id = str(seed["workstream_id"])
        row = row_by_workstream.get(workstream_id)
        safety = safety_by_lead.get(lead_id) or {}
        blockers: list[str] = []
        if not row:
            blockers.append("CURRENT_ENTITY_MISSING")
        else:
            if row.get("workstream_type") != "localos_sales":
                blockers.append("WRONG_WORKSTREAM_TYPE")
            if str(row.get("lead_status") or "") in TERMINAL_LEAD_STATUSES:
                blockers.append("TERMINAL_LEAD_STATUS")
            if str(row.get("pipeline_status") or "") in TERMINAL_PIPELINE_STATUSES:
                blockers.append("TERMINAL_PIPELINE_STATUS")
            if str(row.get("workstream_status") or "") in TERMINAL_WORKSTREAM_STATUSES:
                blockers.append("TERMINAL_WORKSTREAM_STATUS")
            if row.get("last_contact_at") or row.get("workstream_last_contact_at"):
                blockers.append("LAST_CONTACT_PRESENT")
            if row.get("next_action_at") or row.get("workstream_next_action_at") or row.get("deferred_until"):
                blockers.append("ACTIVE_OR_RETAINED_FOLLOWUP_STATE")
        for key, code in (
            ("queue_or_sent", "QUEUE_OR_SENT_HISTORY"),
            ("sent_history", "SENT_HISTORY"),
            ("human_inbound", "HUMAN_INBOUND"),
            ("reactions", "REACTION_HISTORY"),
            ("active_suppressions", "ACTIVE_SUPPRESSION"),
            ("non_draft_campaigns", "NON_DRAFT_CAMPAIGN_HISTORY"),
        ):
            if int(safety.get(key) or 0):
                blockers.append(code)
        contacts = contacts_by_lead.get(lead_id, [])
        usable_contacts = [
            contact
            for contact in contacts
            if str(contact.get("verification_status") or "") not in {"invalid", "rejected", "suppressed"}
            and str(contact.get("contact_type") or "") in {"email", "telegram", "vk", "phone", "whatsapp", "max"}
            and bool(contact.get("normalized_value") or contact.get("value"))
        ]
        if not usable_contacts:
            blockers.append("NO_USABLE_CONTACT_ROUTE")
        current_route_keys = route_keys(lead_id)
        if lead_id in set(prior_lead_ids):
            blockers.append("PRIOR_PARTY_LEAD_OVERLAP")
        if current_route_keys.intersection(prior_route_keys):
            blockers.append("PRIOR_PARTY_RECIPIENT_ROUTE_OVERLAP")
        records.append(
            {
                **seed,
                "current": row,
                "safety": safety,
                "contacts": contacts,
                "usable_contact_count": len(usable_contacts),
                "verified_route_keys": sorted(current_route_keys),
                "blockers": sorted(set(blockers)),
            }
        )

    eligible = [record for record in records if not record["blockers"]]
    eligible.sort(
        key=lambda record: (
            -int((record.get("current") or {}).get("score") or 0),
            -int(record.get("usable_contact_count") or 0),
            record.get("rank") if isinstance(record.get("rank"), int) else 9999,
            str(record.get("name") or ""),
        )
    )
    selected: list[dict[str, Any]] = []
    selected_route_keys: set[str] = set()
    eligible_not_selected: list[dict[str, Any]] = []
    for record in eligible:
        keys = set(record.get("verified_route_keys") or [])
        if keys.intersection(selected_route_keys):
            record = {**record, "selection_skip_reason": f"PARTY{PARTY_NUMBER}_RECIPIENT_ROUTE_OVERLAP"}
            eligible_not_selected.append(record)
            continue
        if len(selected) < 50:
            selected.append(record)
            selected_route_keys.update(keys)
        else:
            eligible_not_selected.append(record)
    if len(selected) != 50:
        raise RuntimeError(f"expected_50_eligible_got_{len(selected)}")
    selected_ids = {record["lead_id"] for record in selected}
    result = {
        "schema_version": f"localos_party{PARTY_NUMBER}_selection_v1",
        "party": f"Партия {PARTY_NUMBER}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_transaction_read_only": True,
        "seed_count": len(records),
        "eligible_count": len(eligible),
        "selected_count": len(selected),
        "selected": selected,
        "eligible_not_selected": eligible_not_selected,
        "excluded": [record for record in records if record["blockers"]],
        "state_change": "none",
    }
    result["canonical_sha256"] = canonical_sha(selected)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "party": result["party"],
                "seed_count": result["seed_count"],
                "eligible_count": result["eligible_count"],
                "selected_count": result["selected_count"],
                "excluded_count": len(result["excluded"]),
                "canonical_sha256": result["canonical_sha256"],
                "state_change": "none",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
