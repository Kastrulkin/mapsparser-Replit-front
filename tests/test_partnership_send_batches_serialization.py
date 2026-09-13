from datetime import date, datetime, timezone
import sys


def test_partnership_reaction_timestamps_are_json_ready():
    if "src" not in sys.path:
        sys.path.insert(0, "src")

    from api.prospecting.sales_room_routes import _serialize_timestamp_fields

    created_at = datetime(2026, 9, 9, 12, 5, tzinfo=timezone.utc)
    payload = _serialize_timestamp_fields(
        {
            "created_at": created_at,
            "follow_up_on": date(2026, 9, 13),
            "lead_name": "Example Buyer",
            "confidence": 0.98,
        }
    )

    assert payload == {
        "created_at": "2026-09-09T12:05:00+00:00",
        "follow_up_on": "2026-09-13",
        "lead_name": "Example Buyer",
        "confidence": 0.98,
    }
