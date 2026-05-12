from core.finance_imports import (
    build_duplicate_key,
    finance_import_template_csv,
    finance_import_templates,
    normalize_finance_import_rows,
    parse_finance_file,
)


def test_finance_import_template_is_parseable_csv() -> None:
    content = finance_import_template_csv().encode("utf-8")
    rows = parse_finance_file("template.csv", content)

    assert len(rows) == 4
    assert rows[0]["record_type"] == "entry"
    assert rows[1]["record_type"] == "service"


def test_finance_import_templates_include_crm_and_workplace_profiles() -> None:
    templates = finance_import_templates()

    assert "manual" in templates
    assert "yclients" in templates
    assert "workplaces" in templates

    crm_rows = parse_finance_file("yclients.csv", finance_import_template_csv("yclients").encode("utf-8"))
    workplace_rows = parse_finance_file("workplaces.csv", finance_import_template_csv("workplaces").encode("utf-8"))

    assert crm_rows[0]["record_type"] == "service"
    assert crm_rows[1]["record_type"] == "staff"
    assert workplace_rows[0]["record_type"] == "workplace"


def test_finance_import_normalizes_service_and_workplace_rows() -> None:
    rows = [
        {
            "record_type": "service",
            "service_name": "Окрашивание",
            "period_start": "01.03.2026",
            "period_end": "31.05.2026",
            "revenue": "500 000",
            "visits_count": "50",
            "duration_minutes": "180",
            "material_cost": "70000",
            "staff_payout": "180000",
        },
        {
            "record_type": "workplace",
            "workplace_name": "Кресло 1",
            "workplace_type": "hair_chair",
            "available_hours": "160",
            "booked_hours": "120",
            "revenue": "500000",
            "gross_profit": "250000",
        },
    ]

    result = normalize_finance_import_rows(rows, period_start="2026-03-01", period_end="2026-05-31")

    assert result["errors"] == []
    assert result["rows"][0]["period_start"] == "2026-03-01"
    assert result["rows"][0]["revenue"] == 500000
    assert result["rows"][1]["available_minutes"] == 9600
    assert result["rows"][1]["booked_minutes"] == 7200


def test_finance_import_reports_invalid_rows() -> None:
    rows = [
        {"record_type": "entry", "date": "wrong", "type": "revenue", "amount": "1000"},
        {"record_type": "service", "revenue": "abc"},
    ]

    result = normalize_finance_import_rows(rows)

    assert len(result["errors"]) == 2
    assert result["rows"] == []


def test_finance_import_duplicate_key_is_stable_for_same_entry() -> None:
    rows = [
        {"record_type": "entry", "date": "2026-05-01", "type": "revenue", "category": "sales", "amount": "1000"},
        {"record_type": "entry", "date": "2026-05-01", "type": "revenue", "category": "sales", "amount": "1000"},
    ]
    result = normalize_finance_import_rows(rows)

    assert result["rows"][0]["duplicate_key"] == result["rows"][1]["duplicate_key"]
    assert build_duplicate_key(result["rows"][0]) == result["rows"][0]["duplicate_key"]
