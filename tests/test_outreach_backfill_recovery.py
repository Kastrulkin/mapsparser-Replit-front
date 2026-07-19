from scripts.recover_outreach_backfill_inconsistencies import (
    build_report,
    inconsistency_action,
)


def test_inconsistency_action_reconciles_stale_ready_job_status():
    assert inconsistency_action({
        "readiness_code": "needs_evidence",
        "result_draft_id": "draft-1",
        "sourced_passed_draft_count": 1,
    }) == "reconcile_terminal_status"


def test_inconsistency_action_regenerates_missing_sourced_draft():
    assert inconsistency_action({
        "readiness_code": "ready",
        "result_draft_id": None,
        "sourced_passed_draft_count": 0,
    }) == "regenerate_missing_sourced_draft"


def test_inconsistency_action_regenerates_legacy_or_failed_draft():
    assert inconsistency_action({
        "readiness_code": "ready",
        "result_draft_id": "draft-1",
        "sourced_passed_draft_count": 0,
    }) == "regenerate_failed_or_legacy_draft"


def test_recovery_report_is_explicitly_non_sending_and_free():
    report = build_report(
        [
            {
                "workstream_id": "ws-1",
                "readiness_code": "ready",
                "result_draft_id": None,
                "sourced_passed_draft_count": 0,
            },
            {
                "workstream_id": "ws-2",
                "readiness_code": "needs_evidence",
                "result_draft_id": "draft-2",
                "sourced_passed_draft_count": 1,
            },
        ],
        mode="dry-run",
    )

    assert report == {
        "mode": "dry-run",
        "workstream_type": "localos_sales",
        "flagged_workstreams": 2,
        "actions": {
            "reconcile_terminal_status": 1,
            "regenerate_missing_sourced_draft": 1,
        },
        "workstream_ids": ["ws-1", "ws-2"],
        "external_send": False,
        "paid_enrichment": False,
    }
