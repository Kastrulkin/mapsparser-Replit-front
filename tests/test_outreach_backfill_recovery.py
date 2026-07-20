from scripts.recover_outreach_backfill_inconsistencies import (
    INCONSISTENT_WORKSTREAMS_SQL,
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


def test_inconsistency_action_retries_quality_failure_after_compaction_fix():
    assert inconsistency_action({
        "job_status": "failed",
        "error_code": "message_quality_failed",
        "readiness_code": "ready",
        "result_draft_id": None,
        "sourced_passed_draft_count": 0,
    }) == "retry_quality_failed_after_compaction"


def test_inconsistency_action_retries_ai_generation_after_validator_fix():
    assert inconsistency_action({
        "job_status": "failed",
        "error_code": "ai_generation_invalid",
        "readiness_code": "ready",
        "result_draft_id": None,
        "sourced_passed_draft_count": 0,
    }) == "retry_ai_generation_invalid_after_validator_fix"


def test_recovery_query_does_not_loop_on_semantic_quality_rejections():
    assert "decorative_personalization" not in INCONSISTENT_WORKSTREAMS_SQL
    assert "Письмо длиннее 90 слов" in INCONSISTENT_WORKSTREAMS_SQL
    assert "Invalid control character at:%%" in INCONSISTENT_WORKSTREAMS_SQL


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
