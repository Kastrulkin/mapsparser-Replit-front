from datetime import datetime, timezone

from services import operator_refresh_recovery
from services.operator_refresh_recovery import build_refresh_recovery_plan, release_failed_refresh_reservation
from tests.test_operator_refresh_result import FakeCursor


def _failed_cursor():
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    return FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "failed",
            "error_message": "reason_code=timeout; transient_retry_attempt=3",
            "created_at": started_at,
            "updated_at": started_at,
        },
        reservations=[
            {
                "id": "reservation-1",
                "status": "reserved",
                "estimated_credits": 10,
                "reserved_credits": 10,
                "charged_credits": 0,
                "released_credits": 0,
                "metadata": {"parsequeue_id": "queue-1"},
                "created_at": started_at,
                "updated_at": started_at,
                "finalized_at": None,
            }
        ],
    )


def test_refresh_recovery_plan_marks_failed_job_retry_and_release_candidates() -> None:
    plan = build_refresh_recovery_plan(_failed_cursor(), business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert plan["status"] == "ready"
    assert plan["retry_allowed"] is True
    assert plan["release_allowed"] is True
    assert plan["reservation_id"] == "reservation-1"
    assert plan["side_effects"]["retry_job_created"] is False
    assert plan["side_effects"]["external_writes_performed"] is False


def test_refresh_recovery_blocks_processing_job() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    cursor = FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "processing",
            "created_at": started_at,
            "updated_at": started_at,
        }
    )

    plan = build_refresh_recovery_plan(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert plan["status"] == "blocked"
    assert "refresh_job_not_terminal" in plan["blocked_reasons"]


def test_failed_refresh_release_requires_explicit_confirmation() -> None:
    result = release_failed_refresh_reservation(
        _failed_cursor(),
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
    )

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["explicit_release_confirmation_required"]


def test_failed_refresh_release_uses_finalization_boundary(monkeypatch) -> None:
    cursor = _failed_cursor()

    def fake_finalize(cursor_arg, *, reservation_id, business_id, user_id, finalization_mode, external_id):
        assert cursor_arg is cursor
        assert reservation_id == "reservation-1"
        assert business_id == "biz-1"
        assert user_id == "user-1"
        assert finalization_mode == "release"
        assert external_id == "failed_refresh_release:queue-1"
        return {"status": "released", "side_effects": {"credit_released": True}}

    monkeypatch.setattr(operator_refresh_recovery, "finalize_reserved_action_credits", fake_finalize)

    result = release_failed_refresh_reservation(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
        confirm_release=True,
    )

    assert result["status"] == "released"
    assert result["side_effects"]["reservation_released"] is True
    assert result["side_effects"]["credit_charged"] is False
    assert result["side_effects"]["external_writes_performed"] is False
