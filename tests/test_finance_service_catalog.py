import sys


if "src" not in sys.path:
    sys.path.insert(0, "src")

from api.finance_api import _finance_catalog_rows


def test_finance_services_follow_card_catalog_and_aggregate_period_metrics():
    catalog = [
        {
            "id": "service-1",
            "name": "Стрижка",
            "category": "Волосы",
            "price": 2500,
            "source": "yandex_maps",
            "updated_at": "2026-07-24T12:00:00+00:00",
        },
        {
            "id": "service-2",
            "name": "Укладка",
            "category": "Волосы",
            "price": 1800,
            "source": "2gis",
            "updated_at": "2026-07-23T12:00:00+00:00",
        },
    ]
    metrics = [
        {"service_name": " Стрижка ", "revenue": 5000, "visits_count": 2, "avg_price": 2500},
        {"service_name": "стрижка", "revenue": 7500, "visits_count": 3, "avg_price": 2500},
        {"service_name": "Старая услуга", "revenue": 999999, "visits_count": 1},
    ]

    rows = _finance_catalog_rows(catalog, metrics)

    assert [row["service_name"] for row in rows] == ["Стрижка", "Укладка"]
    assert rows[0]["service_id"] == "service-1"
    assert rows[0]["revenue"] == 12500
    assert rows[0]["visits_count"] == 5
    assert rows[0]["has_finance_data"] is True
    assert rows[1]["catalog_price"] == 1800
    assert rows[1]["has_finance_data"] is False
    assert rows[1]["status"] == "no_finance_data"
