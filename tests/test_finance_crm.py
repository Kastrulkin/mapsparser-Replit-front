import sys
from pathlib import Path

from core.finance_crm import (
    CRM_PROVIDERS,
    CRMConnectionError,
    AltegioCRMAdapter,
    YClientsCRMAdapter,
    build_crm_sync_preview,
    crm_appointments_to_service_metrics,
    crm_appointments_to_staff_metrics,
    crm_appointments_to_workplace_metrics,
    crm_schedules_to_workplace_metrics,
    create_crm_connector,
    crm_dataset_to_finance_rows,
    get_crm_provider,
    load_crm_contract_fixture,
)


def test_crm_provider_registry_exposes_mock_and_planned_providers() -> None:
    provider_keys = {item["provider"] for item in CRM_PROVIDERS}

    assert "mock_demo" in provider_keys
    assert "yclients" in provider_keys
    assert "altegio" in provider_keys
    assert get_crm_provider("mock_demo")["status"] == "available"
    assert get_crm_provider("yclients")["status"] == "available"
    assert get_crm_provider("altegio")["docs_url"].startswith("https://developer.alteg.io")


def test_mock_crm_connector_returns_finance_dataset() -> None:
    connector = create_crm_connector("mock_demo")
    dataset = connector.fetch_all("2026-05-01", "2026-05-31")

    assert dataset["payments"]
    assert dataset["services"]
    assert dataset["staff"]
    assert dataset["workplaces"]
    assert dataset["schedules"]


def test_crm_dataset_normalizes_to_finance_rows_with_duplicate_keys() -> None:
    connector = create_crm_connector("mock_demo")
    dataset = connector.fetch_all("2026-05-01", "2026-05-31")
    result = crm_dataset_to_finance_rows(dataset, "2026-05-01", "2026-05-31")

    assert result["errors"] == []
    record_types = {item["record_type"] for item in result["rows"]}
    assert {"entry", "service", "staff", "workplace"}.issubset(record_types)
    assert all(item["duplicate_key"] for item in result["rows"])


def test_unknown_crm_provider_raises_clear_error() -> None:
    try:
        create_crm_connector("unknown_crm")
    except ValueError:
        assert "not available" in str(sys.exc_info()[1])
    else:
        raise AssertionError("unknown provider should not be available")


def test_yclients_connector_requires_tokens_and_location() -> None:
    connector = create_crm_connector("yclients")

    try:
        connector.fetch_all("2026-05-01", "2026-05-31")
    except CRMConnectionError:
        assert "partner_token" in str(sys.exc_info()[1])
        assert "user_token" in str(sys.exc_info()[1])
        assert "location_id" in str(sys.exc_info()[1])
    else:
        raise AssertionError("yclients connector should require credentials")


def test_real_crm_connectors_build_partner_user_auth_header() -> None:
    connector = YClientsCRMAdapter(
        {"partner_token": "partner", "user_token": "user"},
        {"location_id": "123"},
    )
    headers = connector._headers()

    assert headers["Authorization"] == "Bearer partner, User user"
    assert headers["Accept"] == "application/vnd.yclients.v2+json"


def test_altegio_connector_uses_altegio_base_url_and_accept_header() -> None:
    connector = AltegioCRMAdapter(
        {"partner_token": "partner", "user_token": "user"},
        {"location_id": "456"},
    )

    assert connector.base_url == "https://api.alteg.io/api/v1"
    assert connector._headers()["Accept"] == "application/vnd.api.v2+json"


def test_real_crm_payload_normalizes_to_finance_rows_without_http() -> None:
    connector = YClientsCRMAdapter(
        {"partner_token": "partner", "user_token": "user"},
        {"location_id": "123"},
    )
    dataset = {
        "payments": [
            connector._normalize_payment({"id": 10, "date": "2026-05-12", "amount": 9000, "payment_method": "card"}, "2026-05-31"),
        ],
        "services": [
            connector._normalize_service({"id": 20, "title": "Маникюр", "price": 3000, "duration": 7200}, "2026-05-01", "2026-05-31"),
        ],
        "staff": [
            connector._normalize_staff({"id": 30, "name": "Анна", "position": "Мастер"}, "2026-05-01", "2026-05-31"),
        ],
        "workplaces": [],
    }

    normalized = crm_dataset_to_finance_rows(dataset, "2026-05-01", "2026-05-31")

    assert normalized["errors"] == []
    assert {row["record_type"] for row in normalized["rows"]} == {"entry", "service", "staff"}


def test_crm_sync_preview_is_dry_run_and_masks_secret_samples() -> None:
    dataset = {
        "payments": [
            {
                "external_id": "payment-1",
                "date": "2026-05-12",
                "type": "revenue",
                "category": "sales",
                "amount": 9000,
                "authorization_token": "secret",
            },
        ],
        "services": [],
        "staff": [],
        "workplaces": [],
        "appointments": [],
        "clients": [],
    }

    preview = build_crm_sync_preview("yclients", dataset, "2026-05-01", "2026-05-31")

    assert preview["will_write"] is False
    assert len(preview["preview_token"]) == 32
    assert preview["dataset_counts"]["payments"] == 1
    assert preview["normalized_counts"]["entry"] == 1
    assert preview["valid_rows"] == 1
    assert preview["raw_samples"]["payments"][0]["authorization_token"] == "***"


def test_crm_appointments_build_staff_metrics_for_visits_no_show_and_rebooking() -> None:
    appointments = [
        {
            "id": 1,
            "datetime": "2026-05-01T10:00:00+03:00",
            "attendance": 1,
            "staff": {"name": "Анна", "position": "Мастер"},
            "client": {"phone": "+79990000001"},
            "services": [{"title": "Маникюр", "cost": 3000, "duration": 7200}],
            "paid": 3000,
        },
        {
            "id": 2,
            "datetime": "2026-05-15T10:00:00+03:00",
            "attendance": 1,
            "staff": {"name": "Анна", "position": "Мастер"},
            "client": {"phone": "+79990000001"},
            "services": [{"title": "Маникюр", "cost": 3000, "duration": 7200}],
            "paid": 3000,
        },
        {
            "id": 3,
            "datetime": "2026-05-16T10:00:00+03:00",
            "attendance": -1,
            "staff": {"name": "Анна", "position": "Мастер"},
            "client": {"phone": "+79990000002"},
            "services": [{"title": "Маникюр", "duration": 7200}],
        },
    ]

    metrics = crm_appointments_to_staff_metrics(appointments, "2026-05-01", "2026-05-31")

    assert len(metrics) == 1
    assert metrics[0]["staff_name"] == "Анна"
    assert metrics[0]["visits_count"] == 2
    assert metrics[0]["no_show_count"] == 1
    assert metrics[0]["rebooking_count"] == 1
    assert metrics[0]["revenue"] == 6000
    assert metrics[0]["booked_minutes"] == 360


def test_crm_appointments_build_service_metrics() -> None:
    appointments = [
        {
            "id": 1,
            "datetime": "2026-05-01T10:00:00+03:00",
            "attendance": 1,
            "staff": {"name": "Анна"},
            "client": {"phone": "+79990000001"},
            "services": [{"title": "Маникюр", "cost": 3000, "duration": 7200}],
        },
        {
            "id": 2,
            "datetime": "2026-05-02T10:00:00+03:00",
            "attendance": 1,
            "staff": {"name": "Мария"},
            "client": {"phone": "+79990000002"},
            "services": [{"title": "Маникюр", "cost": 3500, "duration": 7200}],
        },
    ]

    metrics = crm_appointments_to_service_metrics(appointments, "2026-05-01", "2026-05-31")

    assert len(metrics) == 1
    assert metrics[0]["service_name"] == "Маникюр"
    assert metrics[0]["visits_count"] == 2
    assert metrics[0]["revenue"] == 6500
    assert metrics[0]["avg_price"] == 3250


def test_crm_appointments_build_workplace_metrics_from_resources() -> None:
    appointments = [
        {
            "id": 1,
            "datetime": "2026-05-01T10:00:00+03:00",
            "attendance": 1,
            "resource": {"id": "chair-1", "name": "Кресло 1", "type": "hair_chair"},
            "services": [{"title": "Окрашивание", "cost": 9000, "duration": 10800}],
        },
        {
            "id": 2,
            "datetime": "2026-05-02T10:00:00+03:00",
            "attendance": -1,
            "resource": {"id": "chair-1", "name": "Кресло 1", "type": "hair_chair"},
            "services": [{"title": "Окрашивание", "duration": 7200}],
        },
        {
            "id": 3,
            "datetime": "2026-05-03T10:00:00+03:00",
            "attendance": 1,
            "resources": [{"id": "room-1", "name": "Кабинет косметологии", "type": "cosmetology_room", "available_hours": 8}],
            "services": [{"title": "Чистка лица", "cost": 5000, "duration": 7200}],
        },
    ]

    metrics = crm_appointments_to_workplace_metrics(appointments, "2026-05-01", "2026-05-31")
    by_name = {item["workplace_name"]: item for item in metrics}

    assert by_name["Кресло 1"]["booked_minutes"] == 300
    assert by_name["Кресло 1"]["revenue"] == 9000
    assert by_name["Кресло 1"]["workplace_type"] == "hair_chair"
    assert by_name["Кабинет косметологии"]["available_minutes"] == 480
    assert by_name["Кабинет косметологии"]["booked_minutes"] == 120
    assert by_name["Кабинет косметологии"]["revenue"] == 5000


def test_crm_schedules_build_available_workplace_minutes() -> None:
    schedules = [
        {
            "id": 1,
            "date": "2026-05-01",
            "workplace": {"name": "Кресло 1", "type": "hair_chair"},
            "start_time": "10:00",
            "end_time": "18:00",
        },
        {
            "id": 2,
            "resource_name": "Кабинет косметологии",
            "workplace_type": "cosmetology_room",
            "available_hours": 6,
        },
    ]

    metrics = crm_schedules_to_workplace_metrics(schedules, "2026-05-01", "2026-05-31")
    by_name = {item["workplace_name"]: item for item in metrics}

    assert by_name["Кресло 1"]["available_minutes"] == 480
    assert by_name["Кресло 1"]["workplace_type"] == "hair_chair"
    assert by_name["Кабинет косметологии"]["available_minutes"] == 360
    assert by_name["Кабинет косметологии"]["workplace_type"] == "cosmetology_room"


def test_crm_dataset_adds_workplace_rows_from_appointments() -> None:
    dataset = {
        "payments": [],
        "services": [],
        "staff": [],
        "workplaces": [],
        "appointments": [
            {
                "id": 1,
                "datetime": "2026-05-01T10:00:00+03:00",
                "attendance": 1,
                "resource": {"id": "chair-1", "name": "Кресло 1", "type": "hair_chair"},
                "services": [{"title": "Окрашивание", "cost": 9000, "duration": 10800}],
            }
        ],
        "clients": [],
    }

    normalized = crm_dataset_to_finance_rows(dataset, "2026-05-01", "2026-05-31")
    workplace_rows = [row for row in normalized["rows"] if row["record_type"] == "workplace"]

    assert normalized["errors"] == []
    assert len(workplace_rows) == 1
    assert workplace_rows[0]["workplace_name"] == "Кресло 1"
    assert workplace_rows[0]["booked_minutes"] == 180


def test_crm_preview_token_changes_when_dataset_changes() -> None:
    base_dataset = {
        "payments": [{"external_id": "payment-1", "date": "2026-05-12", "type": "revenue", "category": "sales", "amount": 9000}],
        "services": [],
        "staff": [],
        "workplaces": [],
        "appointments": [],
        "clients": [],
    }
    changed_dataset = {
        "payments": [{"external_id": "payment-2", "date": "2026-05-12", "type": "revenue", "category": "sales", "amount": 9000}],
        "services": [],
        "staff": [],
        "workplaces": [],
        "appointments": [],
        "clients": [],
    }

    base_preview = build_crm_sync_preview("yclients", base_dataset, "2026-05-01", "2026-05-31")
    changed_preview = build_crm_sync_preview("yclients", changed_dataset, "2026-05-01", "2026-05-31")

    assert base_preview["preview_token"] != changed_preview["preview_token"]


def test_crm_contract_fixture_locks_preview_mapping() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "crm" / "yclients_contract_sample.json"
    fixture = load_crm_contract_fixture(str(fixture_path))
    preview = fixture["preview"]

    assert fixture["provider"] == "yclients"
    assert preview["dataset_counts"]["appointments"] == 3
    assert preview["dataset_counts"]["payments"] == 1
    assert preview["normalized_counts"]["staff"] == 1
    assert preview["normalized_counts"]["service"] == 2
    assert preview["normalized_counts"]["entry"] == 1
    assert preview["failed_rows"] == 0
