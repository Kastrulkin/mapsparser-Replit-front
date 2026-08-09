from datetime import date

from services.growth_rhythm_notifications import _due_locations, _message


def test_growth_rhythm_reminders_split_before_due_and_overdue_locations():
    result = _due_locations(
        {
            "locations": [
                {"location_id": "b-1", "name": "Центр", "status": "fresh", "next_due_at": "2026-08-11T09:00:00+00:00"},
                {"location_id": "b-2", "name": "Север", "status": "due", "next_due_at": "2026-08-08T09:00:00+00:00"},
                {"location_id": "b-3", "name": "Юг", "status": "missing", "next_due_at": None},
                {"location_id": "b-4", "name": "Запад", "status": "fresh", "next_due_at": "2026-08-15T09:00:00+00:00"},
            ]
        },
        date(2026, 8, 10),
    )

    assert [item["location_id"] for item in result["before_due"]] == ["b-1"]
    assert [item["location_id"] for item in result["overdue"]] == ["b-2", "b-3"]


def test_network_reminder_groups_locations_without_crm_language():
    text = _message(
        {"kind": "network", "id": "n-1", "name": "Весёлая расчёска"},
        "overdue",
        [{"name": "Центр"}, {"name": "Север"}],
    )

    assert "ЛокалОС · Весёлая расчёска" in text
    assert "• Центр" in text
    assert "• Север" in text
    assert "средний чек" in text
