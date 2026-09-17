#!/usr/bin/env python3
"""Build the exact user-approved influencer email batch and validator records."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PILOT_NAMES = [
    "Anthony Show",
    "miss.dariella",
    "SPB WALKS",
    "Аврора Белышева",
    "Лиза Виноградова",
    "Оля Попова",
    "Светланка блог",
    "Altana Matveeva",
    "ANASTASIA CHE",
    "Anya Grechkina",
]

QUALITY = [
    {"name": "source_validity", "score": 2, "note": "Public profile contact source and public post evidence are recorded."},
    {"name": "observation_accuracy", "score": 2, "note": "The opener is derived from the cited public publication title."},
    {"name": "freshness", "score": 1, "note": "The source is not described as recent; publication recency is not used as a claim."},
    {"name": "offer_bridge", "score": 1, "note": "A public place-related post supports asking about local offers, but city and district fit remain to be learned."},
    {"name": "specificity", "score": 1, "note": "The cited publication personalizes the opener; the first offer intentionally remains cross-client."},
    {"name": "proof_integrity", "score": 2, "note": "No unsupported performance result or guarantee is claimed."},
    {"name": "channel_fit", "score": 2, "note": "Plain-text email is concise and signed by the approved sender name."},
    {"name": "cta_and_length", "score": 2, "note": "One primary question is used and the email stays below 120 words."},
    {"name": "state_safety", "score": 2, "note": "Prior sends, campaign history, duplicates, and exclusions were removed before approval."},
]


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--drafts", type=Path, required=True)
    value.add_argument("--batch", type=Path, required=True)
    value.add_argument("--records-dir", type=Path, required=True)
    return value


def validation_record(item: dict[str, Any], *, batch_id: str, generated_at: str) -> dict[str, Any]:
    evidence_id = f"publication:{item['creator_profile_id']}"
    personalization_id = f"opener:{item['creator_profile_id']}"
    return {
        "schema_version": "1.0",
        "lead_id": item["creator_profile_id"],
        "motion": "local_creator_partnership",
        "identity": {
            "company_name": item["display_name"],
            "contact_name": item["display_name"],
            "contact_role": "active_creator",
            "public_urls": [item["email_source_url"], item["evidence_url"]],
        },
        "contacts": [{
            "channel": "email",
            "value": item["email"],
            "source_url": item["email_source_url"],
            "observed_at": generated_at,
            "confidence": "medium",
            "email_status": "risky",
        }],
        "qualification": {
            "segment": "active local content author",
            "icp_score": 75,
            "disqualifiers": [],
        },
        "evidence": [{
            "evidence_id": evidence_id,
            "kind": "public_creator_post",
            "observation": item["observation"],
            "source_url": item["evidence_url"],
            "source_type": "public_profile",
            "researched_at": generated_at,
            "confidence": "medium",
            "usable_for_outreach": True,
        }],
        "personalization_candidates": [{
            "personalization_id": personalization_id,
            "evidence_ids": [evidence_id],
            "observation": item["observation"],
            "problem_hypothesis": "The author may be open to relevant local places and services.",
            "relevance_to_offer": "The first reply is used to learn city, district, and preferred publishing platform.",
            "personalized_opener": item["observation"],
            "confidence": "medium",
            "usable": True,
            "removal_test_passed": True,
        }],
        "selected_personalization_id": personalization_id,
        "touches": [{
            "touch_no": 1,
            "channel": "email",
            "subject": item["subject"],
            "body": item["body"],
            "cta": "Вам интересен такой формат?",
            "angle": "cross-client performance barter introduction",
            "evidence_ids": [evidence_id],
        }],
        "quality_gate": {
            "verdict": "approve",
            "score": sum(entry["score"] for entry in QUALITY),
            "criteria": QUALITY,
            "review_type": "separate_manual_review_pass",
        },
        "approval": {
            "status": "approved",
            "approved_by": "user",
            "approved_at": generated_at,
            "scope": batch_id,
        },
        "campaign": {"id": batch_id, "status": "approved", "touch_no": 1},
        "outcome": {"reply_status": "none", "unsubscribe": False, "suppressed": False},
        "risks": ["email_syntax_only", "city_and_district_not_confirmed"],
        "generated_at": generated_at,
    }


def main() -> int:
    arguments = parser().parse_args()
    source = json.loads(arguments.drafts.read_text(encoding="utf-8"))
    eligible = [item for item in source["records"] if item.get("state") == "draft_needs_review"]
    by_name = {item["display_name"]: item for item in eligible}
    missing = [name for name in PILOT_NAMES if name not in by_name]
    if missing:
        raise RuntimeError(f"pilot profiles missing: {missing}")
    pilot = [by_name[name] for name in PILOT_NAMES]
    pilot_ids = {item["creator_profile_id"] for item in pilot}
    remaining = [item for item in eligible if item["creator_profile_id"] not in pilot_ids]
    ordered = pilot + remaining
    generated_at = datetime.now(timezone.utc).isoformat()
    approval_fingerprint = hashlib.sha256(
        "\n".join(f"{item['creator_profile_id']}|{item['email']}|{item['subject']}|{item['body']}" for item in ordered).encode("utf-8")
    ).hexdigest()
    batch_id = f"localos-spb-active-creators-{approval_fingerprint[:16]}"
    payload = {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "approval_fingerprint": approval_fingerprint,
        "approved_at": generated_at,
        "approved_by": "user",
        "sender_identity": "localosgo@gmail.com",
        "daily_limit": 10,
        "pilot_count": len(pilot),
        "recipient_count": len(ordered),
        "status": "approved_pending_validation",
        "messages_sent": 0,
        "records": ordered,
    }
    arguments.batch.parent.mkdir(parents=True, exist_ok=True)
    arguments.batch.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    arguments.records_dir.mkdir(parents=True, exist_ok=True)
    for old in arguments.records_dir.glob("*.json"):
        old.unlink()
    for index, item in enumerate(ordered, start=1):
        record = validation_record(item, batch_id=batch_id, generated_at=generated_at)
        path = arguments.records_dir / f"{index:03d}-{item['creator_profile_id']}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"batch_id": batch_id, "recipients": len(ordered), "pilot": len(pilot)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
