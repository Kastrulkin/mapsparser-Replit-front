from core.finance_kpis import calculate_finance_snapshot


def _sample_payload():
    return {
        "entries": [
            {"type": "revenue", "category": "sales", "amount": 900000},
            {"type": "expense", "category": "rent", "amount": 150000},
            {"type": "expense", "category": "payroll", "amount": 360000},
            {"type": "expense", "category": "materials", "amount": 90000},
            {"type": "expense", "category": "marketing", "amount": 50000},
        ],
        "services": [
            {
                "service_name": "Окрашивание",
                "category": "Волосы",
                "revenue": 500000,
                "visits_count": 50,
                "avg_price": 10000,
                "duration_minutes": 180,
                "material_cost": 70000,
                "staff_payout": 180000,
            },
            {
                "service_name": "Укладка",
                "category": "Волосы",
                "revenue": 40000,
                "visits_count": 20,
                "avg_price": 2000,
                "duration_minutes": 60,
                "material_cost": 8000,
                "staff_payout": 25000,
            },
        ],
        "staff": [
            {
                "staff_name": "Анна",
                "role": "Стилист",
                "revenue": 500000,
                "visits_count": 50,
                "booked_minutes": 7200,
                "available_minutes": 9600,
                "no_show_count": 3,
                "rebooking_count": 32,
            }
        ],
        "workplaces": [
            {"id": "chair-1", "name": "Кресло 1", "type": "hair_chair", "is_active": True},
            {"id": "chair-2", "name": "Кресло 2", "type": "hair_chair", "is_active": True},
        ],
        "workplace_metrics": [
            {
                "workplace_id": "chair-1",
                "available_minutes": 9600,
                "booked_minutes": 7200,
                "revenue": 500000,
                "gross_profit": 250000,
            },
            {
                "workplace_id": "chair-2",
                "available_minutes": 9600,
                "booked_minutes": 4800,
                "revenue": 400000,
                "gross_profit": 200000,
            },
        ],
    }


def test_finance_snapshot_calculates_core_profit_and_break_even() -> None:
    snapshot = calculate_finance_snapshot(_sample_payload())
    kpis = snapshot["kpis"]

    assert kpis["revenue"] == 900000
    assert kpis["expenses"] == 650000
    assert kpis["operating_profit"] == 250000
    assert round(kpis["operating_margin"], 2) == 27.78
    assert kpis["fixed_costs"] == 150000
    assert kpis["variable_costs"] == 450000
    assert kpis["gross_profit"] == 450000
    assert kpis["gross_margin"] == 50
    assert kpis["break_even_revenue"] == 300000
    assert round(kpis["daily_revenue_target"], 2) == 13636.36


def test_finance_snapshot_calculates_workplace_metrics() -> None:
    snapshot = calculate_finance_snapshot(_sample_payload())
    kpis = snapshot["kpis"]

    assert kpis["active_workplaces"] == 2
    assert kpis["available_workplace_hours"] == 320
    assert kpis["booked_workplace_hours"] == 200
    assert kpis["idle_workplace_hours"] == 120
    assert kpis["workplace_occupancy"] == 62.5
    assert kpis["revenue_per_workplace"] == 450000
    assert kpis["revenue_per_workplace_hour"] == 2812.5
    assert kpis["gross_profit_per_workplace_hour"] == 1406.25


def test_finance_snapshot_marks_low_margin_services() -> None:
    snapshot = calculate_finance_snapshot(_sample_payload())
    services = snapshot["services"]

    low_margin = next(item for item in services if item["service_name"] == "Укладка")
    assert low_margin["status"] == "busy_without_profit"
    assert snapshot["kpis"]["low_margin_services_share"] == 50


def test_finance_snapshot_handles_division_by_zero_with_explanations() -> None:
    snapshot = calculate_finance_snapshot({"entries": [], "services": [], "staff": [], "workplaces": [], "workplace_metrics": []})

    assert snapshot["kpis"]["operating_margin"] is None
    assert snapshot["kpis"]["revenue_per_workplace_hour"] is None
    assert "operating_margin" in snapshot["explanations"]
    assert "revenue_per_workplace_hour" in snapshot["explanations"]
    assert snapshot["data_quality"]["score"] < 70


def test_finance_recommendations_include_red_zones() -> None:
    payload = _sample_payload()
    payload["entries"][1]["amount"] = 800000
    payload["staff"][0]["no_show_count"] = 20
    payload["workplace_metrics"][0]["booked_minutes"] = 2000
    payload["workplace_metrics"][1]["booked_minutes"] = 1000

    snapshot = calculate_finance_snapshot(payload)
    codes = {item["code"] for item in snapshot["recommendations"]}

    assert "low_operating_margin" in codes
    assert "high_no_show" in codes
    assert "low_workplace_occupancy" in codes

    low_margin = next(item for item in snapshot["recommendations"] if item["code"] == "low_operating_margin")
    assert low_margin["target_metric"] == "operating_margin"
    assert "today" in low_margin["actions"]
    assert "seven_days" in low_margin["actions"]
    assert "regular" in low_margin["actions"]
    assert "расходы" in low_margin["data_needed"]
    assert low_margin["localos_actions"][0]["route"].startswith("/dashboard/")


def test_finance_snapshot_applies_custom_thresholds_to_statuses() -> None:
    snapshot = calculate_finance_snapshot(
        _sample_payload(),
        {
            "operating_margin": {
                "green_min": 35,
                "green_max": None,
                "yellow_min": 20,
                "yellow_max": 34.99,
            },
            "workplace_occupancy": {
                "green_min": 80,
                "green_max": 90,
                "yellow_min": 60,
                "yellow_max": 100,
            },
        },
    )

    assert snapshot["statuses"]["operating_margin"] == "yellow"
    assert snapshot["statuses"]["workplace_occupancy"] == "yellow"
    assert snapshot["thresholds"]["operating_margin"]["green_min"] == 35


def test_finance_recommendations_include_custom_norm_text() -> None:
    payload = _sample_payload()
    payload["entries"][1]["amount"] = 800000
    snapshot = calculate_finance_snapshot(
        payload,
        {
            "operating_margin": {
                "label": "Маржа салона",
                "unit": "%",
                "green_min": 30,
                "green_max": None,
                "yellow_min": 15,
                "yellow_max": 29.99,
            }
        },
    )

    low_margin = next(item for item in snapshot["recommendations"] if item["code"] == "low_operating_margin")
    assert "Маржа салона" in low_margin["text"]
    assert "норма от 30%" in low_margin["text"]


def test_finance_recommendations_for_missing_data_include_onboarding_plan() -> None:
    snapshot = calculate_finance_snapshot({"entries": [], "services": [], "staff": [], "workplaces": [], "workplace_metrics": []})
    recommendation = snapshot["recommendations"][0]

    assert recommendation["code"] == "fill_data"
    assert recommendation["target_metric"] == "data_quality"
    assert "услуги" in recommendation["data_needed"]
    assert recommendation["actions"]["today"]
    assert recommendation["actions"]["seven_days"]
    assert recommendation["actions"]["regular"]
    assert recommendation["localos_actions"][0]["route"] == "/dashboard/finance"
