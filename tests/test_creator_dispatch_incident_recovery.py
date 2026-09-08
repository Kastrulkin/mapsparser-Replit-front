from datetime import datetime, timezone

import pytest

from scripts.recover_creator_dispatch_incident_20260908 import (
    EXPECTED,
    PENDING_QUEUE_ID,
    SENT_QUEUE_ID,
    validate_proof,
)


NOW = datetime(2026, 9, 8, 13, 20, tzinfo=timezone.utc)


def valid_proof():
    results = []
    for queue_id, expected in EXPECTED.items():
        sent = queue_id == SENT_QUEUE_ID
        matches = []
        if sent:
            matches = [
                {
                    "sent_uid": "2831",
                    "message_id": "<creator-pilot@gmail.com>",
                    "gmail_message_id": "1875769429967126031",
                    "gmail_thread_id": "1875769429967126031",
                    "message_date": "2026-09-08T13:12:07+00:00",
                    "from_matches": True,
                    "recipient_matches": True,
                    "unexpected_cc_bcc": False,
                    "subject_matches": True,
                    "body": {
                        "matches": True,
                        "sha256": expected["body_sha256"],
                    },
                }
            ]
        results.append(
            {
                "queue_id": queue_id,
                "approved_body_sha256": expected["body_sha256"],
                "provider": {
                    "verified_sent": sent,
                    "exact_match_count": len(matches),
                    "matches": matches,
                },
            }
        )
    return {
        "observed_at": "2026-09-08T13:15:07+00:00",
        "mailbox": "localosgo@gmail.com",
        "scope": "exact_two_approved_messages_read_only",
        "results": results,
    }


def test_accepts_exact_fresh_one_sent_one_pending_proof():
    result = validate_proof(valid_proof(), now=NOW)
    assert result["message_id"] == "<creator-pilot@gmail.com>"
    assert result["message_date"] == datetime(2026, 9, 8, 13, 12, 7, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda proof: proof.update(mailbox="other@gmail.com"),
        lambda proof: proof.update(observed_at="2026-09-08T12:00:00+00:00"),
        lambda proof: proof["results"][0]["provider"].update(verified_sent=True),
        lambda proof: proof["results"][1]["provider"]["matches"][0]["body"].update(matches=False),
        lambda proof: proof["results"][1]["provider"]["matches"][0].update(message_id="invalid"),
    ],
)
def test_rejects_inexact_or_stale_provider_proof(mutation):
    proof = valid_proof()
    by_queue = {item["queue_id"]: item for item in proof["results"]}
    proof["results"] = [by_queue[PENDING_QUEUE_ID], by_queue[SENT_QUEUE_ID]]
    mutation(proof)
    with pytest.raises(ValueError):
        validate_proof(proof, now=NOW)
