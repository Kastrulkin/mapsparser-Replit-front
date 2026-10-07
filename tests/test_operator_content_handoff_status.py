from api.operator_api import _content_handoff_status


def test_handoff_status_requires_complete_receipt_for_delivery():
    assert _content_handoff_status({"staff_handoff": {"telegram_deliveries": {"user-1": {
        "parts": {"photo": {"status": "sent"}},
    }}}}) == "needs_reconciliation"
    assert _content_handoff_status({"staff_handoff": {"telegram_deliveries": {"user-1": {
        "sent_at": "2026-10-07T10:00:00+03:00",
    }}}}) == "delivered"


def test_handoff_failure_and_uncertain_outcome_are_not_reported_as_delivered():
    assert _content_handoff_status({"staff_handoff": {"telegram_deliveries": {"user-1": {
        "parts": {"photo": {"status": "sent"}, "text:0": {"status": "not_sent"}},
    }}}}) == "failed"
    assert _content_handoff_status({"staff_handoff": {"telegram_deliveries": {"user-1": {
        "parts": {"photo": {"status": "sent"}, "text:0": {"status": "uncertain"}},
    }}}}) == "needs_reconciliation"
    assert _content_handoff_status("not-json") == "not_sent"
