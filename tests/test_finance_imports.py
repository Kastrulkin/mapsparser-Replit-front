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
    assert "yclients_stats" in templates

    crm_rows = parse_finance_file("yclients.csv", finance_import_template_csv("yclients").encode("utf-8"))
    workplace_rows = parse_finance_file("workplaces.csv", finance_import_template_csv("workplaces").encode("utf-8"))

    assert crm_rows[0]["record_type"] == "service"
    assert crm_rows[1]["record_type"] == "staff"
    assert workplace_rows[0]["record_type"] == "workplace"


def test_finance_import_reads_yclients_daily_stats_utf16_tsv() -> None:
    content = "\n".join(
        [
            "Статья\t1 мая (нал)\t1 мая (б/н)\t1 мая (Всего)\t2 мая (нал)\t2 мая (б/н)\t2 мая (Всего)\tВсего",
            "Доходы\t100\t200\t300\t0\t0\t0\t300",
            "Оказание услуг\t100\t200\t300\t0\t0\t0\t300",
            "Продажа товаров\t0\t0\t0\t50\t75,50\t125,50\t125,50",
            "Закупка материалов\t0\t0\t20\t0\t0\t0\t20",
            "Остаток на конец дня\t1\t2\t3\t4\t5\t6\t9",
        ]
    ).encode("utf-16")

    rows = parse_finance_file("май.csv", content)
    result = normalize_finance_import_rows(rows)

    assert result["errors"] == []
    assert result["total"] == 3
    assert result["rows"][0]["record_type"] == "entry"
    assert result["rows"][0]["date"].endswith("-05-01")
    assert result["rows"][0]["type"] == "revenue"
    assert result["rows"][0]["category"] == "services"
    assert result["rows"][0]["amount"] == 300
    assert result["rows"][1]["date"].endswith("-05-02")
    assert result["rows"][1]["category"] == "retail"
    assert result["rows"][1]["amount"] == 125.5
    assert result["rows"][2]["type"] == "expense"
    assert result["rows"][2]["category"] == "materials"


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
