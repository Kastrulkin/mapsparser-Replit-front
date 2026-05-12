from __future__ import annotations

import json
import hashlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any

from core.finance_imports import normalize_finance_import_rows

ALTEGIO_DOCS_URL = "https://developer.alteg.io/en"
YCLIENTS_DOCS_URL = "https://support.yclients.com/67-68-199--dostup-k-api/"


CRM_PROVIDERS = [
    {
        "provider": "mock_demo",
        "label": "Demo CRM",
        "status": "available",
        "description": "Безопасный тестовый адаптер для проверки финансовой синхронизации.",
        "requires_auth": False,
    },
    {
        "provider": "yclients",
        "label": "YCLIENTS",
        "status": "available",
        "description": "Подготовленный API-коннектор. Нужны partner token, user token и ID филиала YCLIENTS.",
        "requires_auth": True,
        "docs_url": YCLIENTS_DOCS_URL,
        "api_base_url": "https://api.yclients.com/api/v1",
        "required_auth_fields": ["partner_token", "user_token"],
        "required_settings_fields": ["location_id"],
        "capabilities": ["services", "staff", "appointments", "payments", "workplaces", "schedules"],
        "notes": [
            "Для боевого доступа нужно приложение/интеграция в YCLIENTS и права системного пользователя.",
            "Без договоренности и токенов коннектор не выполняет синхронизацию.",
        ],
    },
    {
        "provider": "altegio",
        "label": "Altegio",
        "status": "available",
        "description": "Подготовленный API-коннектор Altegio Business Management v1. Нужны partner token, user token и ID филиала.",
        "requires_auth": True,
        "docs_url": ALTEGIO_DOCS_URL,
        "api_base_url": "https://api.alteg.io/api/v1",
        "required_auth_fields": ["partner_token", "user_token"],
        "required_settings_fields": ["location_id"],
        "capabilities": ["services", "staff", "appointments", "payments", "workplaces", "schedules", "analytics"],
        "notes": [
            "Altegio документирует partner + user authorization для бизнес-данных.",
            "Лимит из публичной документации: 200 запросов/мин или 5 запросов/сек на IP.",
        ],
    },
]


class CRMConnectionError(RuntimeError):
    pass


class CRMConnector:
    provider = "base"

    def __init__(self, auth_data: dict[str, Any] | None = None, settings: dict[str, Any] | None = None):
        self.auth_data = auth_data or {}
        self.settings = settings or {}

    def fetch_appointments(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_payments(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_clients(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_services(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_staff(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_workplaces(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_schedules(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return []

    def fetch_all(self, start_date: str, end_date: str) -> dict[str, list[dict[str, Any]]]:
        return {
            "appointments": self.fetch_appointments(start_date, end_date),
            "payments": self.fetch_payments(start_date, end_date),
            "clients": self.fetch_clients(start_date, end_date),
            "services": self.fetch_services(start_date, end_date),
            "staff": self.fetch_staff(start_date, end_date),
            "workplaces": self.fetch_workplaces(start_date, end_date),
            "schedules": self.fetch_schedules(start_date, end_date),
        }


class MockDemoCRMAdapter(CRMConnector):
    provider = "mock_demo"

    def fetch_payments(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return [
            {
                "external_id": f"mock-payment-{start_date}-{end_date}",
                "date": end_date,
                "type": "revenue",
                "category": "sales",
                "amount": 420000,
                "comment": "Demo CRM: оплаченные визиты",
            },
            {
                "external_id": f"mock-materials-{start_date}-{end_date}",
                "date": end_date,
                "type": "expense",
                "category": "materials",
                "amount": 48000,
                "comment": "Demo CRM: материалы",
            },
        ]

    def fetch_services(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return [
            {
                "external_id": f"mock-service-color-{start_date}-{end_date}",
                "service_name": "Окрашивание",
                "category": "Волосы",
                "period_start": start_date,
                "period_end": end_date,
                "revenue": 250000,
                "visits_count": 25,
                "avg_price": 10000,
                "duration_minutes": 180,
                "material_cost": 35000,
                "staff_payout": 90000,
            },
            {
                "external_id": f"mock-service-care-{start_date}-{end_date}",
                "service_name": "Уход для волос",
                "category": "Волосы",
                "period_start": start_date,
                "period_end": end_date,
                "revenue": 90000,
                "visits_count": 30,
                "avg_price": 3000,
                "duration_minutes": 60,
                "material_cost": 12000,
                "staff_payout": 30000,
            },
        ]

    def fetch_staff(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return [
            {
                "external_id": f"mock-staff-anna-{start_date}-{end_date}",
                "staff_name": "Анна",
                "role": "Стилист",
                "period_start": start_date,
                "period_end": end_date,
                "revenue": 260000,
                "visits_count": 28,
                "booked_hours": 92,
                "available_hours": 132,
                "no_show_count": 2,
                "rebooking_count": 18,
            }
        ]

    def fetch_workplaces(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return [
            {
                "external_id": f"mock-chair-1-{start_date}-{end_date}",
                "workplace_name": "Кресло 1",
                "workplace_type": "hair_chair",
                "period_start": start_date,
                "period_end": end_date,
                "available_hours": 132,
                "booked_hours": 92,
                "revenue": 260000,
                "gross_profit": 135000,
            }
        ]

    def fetch_schedules(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        return [
            {
                "external_id": f"mock-chair-1-schedule-{start_date}-{end_date}",
                "workplace": {"name": "Кресло 1", "type": "hair_chair"},
                "date": end_date,
                "start_time": "10:00",
                "end_time": "20:00",
            }
        ]


class HttpCRMAdapter(CRMConnector):
    provider = "http"
    default_base_url = ""
    default_accept = "application/vnd.api.v2+json"

    def __init__(self, auth_data: dict[str, Any] | None = None, settings: dict[str, Any] | None = None):
        super().__init__(auth_data, settings)
        self.base_url = str(
            self.auth_data.get("api_base_url")
            or self.settings.get("api_base_url")
            or self.default_base_url
        ).rstrip("/")
        self.location_id = str(
            self.auth_data.get("location_id")
            or self.auth_data.get("company_id")
            or self.settings.get("location_id")
            or self.settings.get("company_id")
            or ""
        ).strip()

    def _partner_token(self) -> str:
        return str(self.auth_data.get("partner_token") or self.auth_data.get("api_token") or "").strip()

    def _user_token(self) -> str:
        return str(self.auth_data.get("user_token") or "").strip()

    def validate_credentials(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("api_base_url")
        if not self.location_id:
            missing.append("location_id")
        if not self._partner_token():
            missing.append("partner_token")
        if not self._user_token():
            missing.append("user_token")
        if missing:
            raise CRMConnectionError(f"CRM credentials are incomplete: {', '.join(missing)}")

    def _authorization_header(self) -> str:
        return f"Bearer {self._partner_token()}, User {self._user_token()}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self._authorization_header(),
            "Accept": str(self.settings.get("accept") or self.default_accept),
            "Content-Type": "application/json",
            "User-Agent": "LocalOS-FinanceCRM/1.0",
        }

    def _url(self, path: str, params: dict[str, Any] | None = None) -> str:
        clean_path = path if path.startswith("/") else f"/{path}"
        url = f"{self.base_url}{clean_path}"
        filtered = {key: value for key, value in (params or {}).items() if value not in (None, "")}
        if filtered:
            url = f"{url}?{urllib.parse.urlencode(filtered)}"
        return url

    def _request_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.validate_credentials()
        request = urllib.request.Request(self._url(path, params), headers=self._headers(), method="GET")
        response = None
        try:
            response = urllib.request.urlopen(request, timeout=int(self.settings.get("timeout_seconds") or 20))
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError:
            error = sys_error_text()
            raise CRMConnectionError(f"CRM API HTTP error: {error}")
        except urllib.error.URLError:
            error = sys_error_text()
            raise CRMConnectionError(f"CRM API connection error: {error}")
        except json.JSONDecodeError:
            raise CRMConnectionError("CRM API returned invalid JSON")
        finally:
            if response:
                response.close()

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("data", "items", "records", "transactions", "services", "staff"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        nested = payload.get("data")
        if isinstance(nested, dict):
            for key in ("items", "records", "transactions", "services", "staff"):
                value = nested.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _first_value(self, item: dict[str, Any], keys: list[str], default: Any = "") -> Any:
        for key in keys:
            if key in item and item.get(key) not in (None, ""):
                return item.get(key)
        return default

    def _nested_first_value(self, item: dict[str, Any], parent_keys: list[str], child_keys: list[str], default: Any = "") -> Any:
        for parent_key in parent_keys:
            parent = item.get(parent_key)
            if isinstance(parent, dict):
                value = self._first_value(parent, child_keys, None)
                if value not in (None, ""):
                    return value
        return default

    def _safe_amount(self, item: dict[str, Any]) -> Any:
        value = self._first_value(item, ["amount", "sum", "paid", "cost", "price", "total"], "")
        if isinstance(value, dict):
            return self._first_value(value, ["amount", "value"], "")
        return value

    def _safe_date(self, item: dict[str, Any], fallback: str) -> str:
        value = self._first_value(item, ["date", "datetime", "paid_at", "created_at", "time"], fallback)
        return str(value or fallback)[:10]

    def _normalize_payment(self, item: dict[str, Any], end_date: str) -> dict[str, Any]:
        external_id = self._first_value(item, ["id", "record_id", "document_id", "transaction_id"], "")
        return {
            "external_id": f"{self.provider}-payment-{external_id or self._safe_date(item, end_date)}",
            "date": self._safe_date(item, end_date),
            "type": "revenue",
            "category": str(self._first_value(item, ["category", "payment_method", "type"], "sales")),
            "amount": self._safe_amount(item),
            "comment": f"{self.provider}: payment",
        }

    def _normalize_service(self, item: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
        external_id = self._first_value(item, ["id", "service_id"], "")
        title = self._first_value(item, ["title", "name", "service_name"], "")
        return {
            "external_id": f"{self.provider}-service-{external_id or title}",
            "service_name": title,
            "category": self._nested_first_value(item, ["category", "service_category"], ["title", "name"], ""),
            "period_start": start_date,
            "period_end": end_date,
            "revenue": self._first_value(item, ["revenue", "amount", "cost", "price_min", "price"], ""),
            "visits_count": self._first_value(item, ["visits_count", "count", "records_count"], ""),
            "avg_price": self._first_value(item, ["avg_price", "average_price", "price", "cost"], ""),
            "duration_minutes": self._duration_minutes(item),
        }

    def _normalize_staff(self, item: dict[str, Any], start_date: str, end_date: str) -> dict[str, Any]:
        external_id = self._first_value(item, ["id", "staff_id", "user_id"], "")
        name = self._first_value(item, ["name", "fullname", "title"], "")
        return {
            "external_id": f"{self.provider}-staff-{external_id or name}",
            "staff_name": name,
            "role": self._first_value(item, ["role", "position", "specialization"], ""),
            "period_start": start_date,
            "period_end": end_date,
            "revenue": self._first_value(item, ["revenue", "sales", "amount"], ""),
            "visits_count": self._first_value(item, ["visits_count", "records_count", "count"], ""),
            "booked_hours": self._first_value(item, ["booked_hours"], ""),
            "available_hours": self._first_value(item, ["available_hours"], ""),
            "no_show_count": self._first_value(item, ["no_show_count"], ""),
            "rebooking_count": self._first_value(item, ["rebooking_count"], ""),
        }

    def _duration_minutes(self, item: dict[str, Any]) -> Any:
        value = self._first_value(item, ["duration_minutes", "duration"], "")
        if isinstance(value, (int, float)):
            return int(value / 60) if value > 600 else value
        try:
            number = float(str(value).replace(",", "."))
            return int(number / 60) if number > 600 else number
        except Exception:
            return value


class YClientsCRMAdapter(HttpCRMAdapter):
    provider = "yclients"
    default_base_url = "https://api.yclients.com/api/v1"
    default_accept = "application/vnd.yclients.v2+json"

    def fetch_services(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        payload = self._request_json(f"/company/{self.location_id}/services")
        return [self._normalize_service(item, start_date, end_date) for item in self._extract_items(payload)]

    def fetch_staff(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        payload = self._request_json(f"/company/{self.location_id}/staff")
        return [self._normalize_staff(item, start_date, end_date) for item in self._extract_items(payload)]

    def fetch_appointments(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            f"/records/{self.location_id}",
            {"start_date": start_date, "end_date": end_date},
        )
        return self._extract_items(payload)

    def fetch_payments(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        payload = self._request_json(
            f"/transactions/{self.location_id}",
            {"start_date": start_date, "end_date": end_date},
        )
        return [self._normalize_payment(item, end_date) for item in self._extract_items(payload)]


class AltegioCRMAdapter(YClientsCRMAdapter):
    provider = "altegio"
    default_base_url = "https://api.alteg.io/api/v1"
    default_accept = "application/vnd.api.v2+json"


def get_crm_provider(provider: str) -> dict[str, Any] | None:
    for item in CRM_PROVIDERS:
        if item["provider"] == provider:
            return item
    return None


def create_crm_connector(provider: str, auth_data: dict[str, Any] | None = None, settings: dict[str, Any] | None = None) -> CRMConnector:
    if provider == "mock_demo":
        return MockDemoCRMAdapter(auth_data, settings)
    if provider == "yclients":
        return YClientsCRMAdapter(auth_data, settings)
    if provider == "altegio":
        return AltegioCRMAdapter(auth_data, settings)
    raise ValueError(f"CRM provider is not available: {provider}")


def crm_dataset_to_finance_rows(dataset: dict[str, list[dict[str, Any]]], start_date: str, end_date: str) -> dict[str, Any]:
    raw_rows = []
    for payment in dataset.get("payments") or []:
        raw_rows.append({"record_type": "entry", **payment})
    for service in dataset.get("services") or []:
        raw_rows.append({"record_type": "service", **service})
    for staff in dataset.get("staff") or []:
        raw_rows.append({"record_type": "staff", **staff})
    for workplace in dataset.get("workplaces") or []:
        raw_rows.append({"record_type": "workplace", **workplace})
    raw_rows.extend(crm_appointments_to_staff_metrics(dataset.get("appointments") or [], start_date, end_date))
    raw_rows.extend(crm_appointments_to_service_metrics(dataset.get("appointments") or [], start_date, end_date))
    raw_rows.extend(crm_schedules_to_workplace_metrics(dataset.get("schedules") or [], start_date, end_date))
    raw_rows.extend(crm_appointments_to_workplace_metrics(dataset.get("appointments") or [], start_date, end_date))
    return normalize_finance_import_rows(raw_rows, period_start=start_date, period_end=end_date)


def crm_appointments_to_staff_metrics(appointments: list[dict[str, Any]], start_date: str, end_date: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    completed_by_client = _completed_appointments_by_client(appointments)
    for appointment in appointments:
        staff_name = _appointment_staff_name(appointment)
        if not staff_name:
            continue
        key = staff_name.lower()
        metric = grouped.setdefault(
            key,
            {
                "record_type": "staff",
                "external_id": f"crm-appointments-staff-{key}-{start_date}-{end_date}",
                "staff_name": staff_name,
                "role": _nested_text(appointment, ["staff", "master", "user"], ["role", "position", "specialization"]),
                "period_start": start_date,
                "period_end": end_date,
                "revenue": 0,
                "visits_count": 0,
                "booked_minutes": 0,
                "available_minutes": 0,
                "no_show_count": 0,
                "rebooking_count": 0,
            },
        )
        if _is_no_show_appointment(appointment):
            metric["no_show_count"] += 1
            metric["booked_minutes"] += _appointment_duration_minutes(appointment)
            continue
        if not _is_completed_appointment(appointment):
            continue
        metric["visits_count"] += 1
        metric["revenue"] += _appointment_amount(appointment)
        metric["booked_minutes"] += _appointment_duration_minutes(appointment)
        client_key = _appointment_client_key(appointment)
        if client_key and _has_later_completed_or_booked_visit(appointment, completed_by_client.get(client_key) or []):
            metric["rebooking_count"] += 1
    return list(grouped.values())


def crm_appointments_to_service_metrics(appointments: list[dict[str, Any]], start_date: str, end_date: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for appointment in appointments:
        if not _is_completed_appointment(appointment):
            continue
        services = _appointment_services(appointment)
        if not services:
            service_name = _text_value(appointment, ["service_name", "service", "title", "name"]) or "CRM услуга"
            services = [{"title": service_name, "cost": _appointment_amount(appointment), "duration": _appointment_duration_minutes(appointment)}]
        split_count = max(len(services), 1)
        for service in services:
            service_name = _text_value(service, ["title", "name", "service_name"]) or "CRM услуга"
            key = service_name.lower()
            metric = grouped.setdefault(
                key,
                {
                    "record_type": "service",
                    "external_id": f"crm-appointments-service-{key}-{start_date}-{end_date}",
                    "service_name": service_name,
                    "category": _nested_text(service, ["category", "service_category"], ["title", "name"]),
                    "period_start": start_date,
                    "period_end": end_date,
                    "revenue": 0,
                    "visits_count": 0,
                    "avg_price": 0,
                    "duration_minutes": 0,
                    "material_cost": 0,
                    "staff_payout": 0,
                },
            )
            amount = _moneyish(_first_from(service, ["amount", "cost", "price", "sum", "paid"]))
            if amount <= 0:
                amount = _appointment_amount(appointment) / split_count
            duration = _durationish_minutes(_first_from(service, ["duration_minutes", "duration", "length"]))
            if duration <= 0:
                duration = int(round(_appointment_duration_minutes(appointment) / split_count))
            metric["revenue"] += amount
            metric["visits_count"] += 1
            metric["duration_minutes"] = max(metric["duration_minutes"], duration)
    for metric in grouped.values():
        visits = metric.get("visits_count") or 0
        metric["avg_price"] = round((metric.get("revenue") or 0) / visits, 2) if visits else 0
    return list(grouped.values())


def crm_appointments_to_workplace_metrics(appointments: list[dict[str, Any]], start_date: str, end_date: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for appointment in appointments:
        resources = _appointment_workplaces(appointment)
        if not resources:
            continue
        duration = _appointment_duration_minutes(appointment)
        if duration <= 0:
            continue
        amount = _appointment_amount(appointment)
        split_amount = amount / max(len(resources), 1)
        for resource in resources:
            name = _text_value(resource, ["name", "title", "workplace_name", "resource_name"])
            if not name:
                continue
            key = name.lower()
            metric = grouped.setdefault(
                key,
                {
                    "record_type": "workplace",
                    "external_id": f"crm-appointments-workplace-{key}-{start_date}-{end_date}",
                    "workplace_name": name,
                    "workplace_type": _workplace_type(resource, appointment),
                    "period_start": start_date,
                    "period_end": end_date,
                    "available_minutes": 0,
                    "booked_minutes": 0,
                    "revenue": 0,
                    "gross_profit": 0,
                },
            )
            metric["booked_minutes"] += duration
            if _is_completed_appointment(appointment):
                metric["revenue"] += split_amount
            available_minutes = _resource_available_minutes(resource)
            if available_minutes > 0:
                metric["available_minutes"] += available_minutes
    return list(grouped.values())


def crm_schedules_to_workplace_metrics(schedules: list[dict[str, Any]], start_date: str, end_date: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for schedule in schedules:
        resource = _schedule_workplace(schedule)
        name = _text_value(resource, ["name", "title", "workplace_name", "resource_name"])
        if not name:
            name = _text_value(schedule, ["workplace_name", "resource_name", "room_name", "chair_name", "cabinet_name"])
        if not name:
            continue
        key = name.lower()
        metric = grouped.setdefault(
            key,
            {
                "record_type": "workplace",
                "external_id": f"crm-schedule-workplace-{key}-{start_date}-{end_date}",
                "workplace_name": name,
                "workplace_type": _workplace_type(resource, schedule),
                "period_start": start_date,
                "period_end": end_date,
                "available_minutes": 0,
                "booked_minutes": 0,
                "revenue": 0,
                "gross_profit": 0,
            },
        )
        metric["available_minutes"] += _schedule_available_minutes(schedule, resource)
    return list(grouped.values())


def build_crm_sync_preview(
    provider: str,
    dataset: dict[str, list[dict[str, Any]]],
    start_date: str,
    end_date: str,
    sample_limit: int = 5,
) -> dict[str, Any]:
    normalized = crm_dataset_to_finance_rows(dataset, start_date, end_date)
    rows = normalized.get("rows") or []
    errors = normalized.get("errors") or []
    dataset_counts = {
        "appointments": len(dataset.get("appointments") or []),
        "payments": len(dataset.get("payments") or []),
        "clients": len(dataset.get("clients") or []),
        "services": len(dataset.get("services") or []),
        "staff": len(dataset.get("staff") or []),
        "workplaces": len(dataset.get("workplaces") or []),
        "schedules": len(dataset.get("schedules") or []),
    }
    normalized_counts: dict[str, int] = {}
    for row in rows:
        record_type = str(row.get("record_type") or "unknown")
        normalized_counts[record_type] = normalized_counts.get(record_type, 0) + 1
    raw_samples = {}
    for key, items in dataset.items():
        raw_samples[key] = [_safe_preview_item(item) for item in (items or [])[:sample_limit]]
    preview_token = build_crm_preview_token(provider, start_date, end_date, normalized)
    return {
        "provider": provider,
        "period": {"start_date": start_date, "end_date": end_date},
        "preview_token": preview_token,
        "will_write": False,
        "dataset_counts": dataset_counts,
        "normalized_counts": normalized_counts,
        "rows_total": normalized.get("total", 0),
        "valid_rows": len(rows),
        "failed_rows": len(errors),
        "preview_rows": rows[:sample_limit],
        "errors": errors[:20],
        "raw_samples": raw_samples,
    }


def build_crm_preview_token(provider: str, start_date: str, end_date: str, normalized: dict[str, Any]) -> str:
    rows = normalized.get("rows") or []
    errors = normalized.get("errors") or []
    basis = {
        "provider": provider,
        "start_date": start_date,
        "end_date": end_date,
        "rows_total": normalized.get("total", 0),
        "valid_rows": len(rows),
        "failed_rows": len(errors),
        "duplicate_keys": sorted(str(row.get("duplicate_key") or "") for row in rows),
    }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def load_crm_contract_fixture(path: str) -> dict[str, Any]:
    file_obj = open(path, "r", encoding="utf-8")
    try:
        payload = json.load(file_obj)
    finally:
        file_obj.close()
    provider = str(payload.get("provider") or "unknown")
    dataset = payload.get("dataset") or {}
    period = payload.get("period") or {}
    start_date = str(period.get("start_date") or default_crm_period()[0])
    end_date = str(period.get("end_date") or default_crm_period()[1])
    return {
        "provider": provider,
        "dataset": dataset,
        "start_date": start_date,
        "end_date": end_date,
        "preview": build_crm_sync_preview(provider, dataset, start_date, end_date),
    }


def _safe_preview_item(item: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in (item or {}).items():
        normalized_key = str(key).lower()
        if any(secret in normalized_key for secret in ("token", "password", "secret", "authorization")):
            result[key] = "***"
            continue
        if isinstance(value, dict):
            result[key] = _safe_preview_item(value)
            continue
        if isinstance(value, list):
            result[key] = [
                _safe_preview_item(entry) if isinstance(entry, dict) else entry
                for entry in value[:3]
            ]
            continue
        result[key] = value
    return result


def _completed_appointments_by_client(appointments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for appointment in appointments:
        client_key = _appointment_client_key(appointment)
        if not client_key:
            continue
        grouped.setdefault(client_key, []).append(appointment)
    for items in grouped.values():
        items.sort(key=_appointment_datetime)
    return grouped


def _appointment_staff_name(appointment: dict[str, Any]) -> str:
    return (
        _nested_text(appointment, ["staff", "master", "user", "employee"], ["name", "fullname", "title"])
        or _text_value(appointment, ["staff_name", "master_name", "employee_name"])
    )


def _appointment_client_key(appointment: dict[str, Any]) -> str:
    value = (
        _nested_text(appointment, ["client", "customer"], ["id", "phone", "email", "name"])
        or _text_value(appointment, ["client_id", "client_phone", "phone", "email"])
    )
    return value.lower()


def _appointment_services(appointment: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("services", "service", "records_services"):
        value = appointment.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
    return []


def _appointment_workplaces(appointment: dict[str, Any]) -> list[dict[str, Any]]:
    resources: list[dict[str, Any]] = []
    for key in ("workplaces", "resources", "resource_instances", "rooms", "chairs"):
        value = appointment.get(key)
        if isinstance(value, list):
            resources.extend(item for item in value if isinstance(item, dict))
        elif isinstance(value, dict):
            resources.append(value)
    for key in ("workplace", "resource", "room", "chair", "cabinet"):
        value = appointment.get(key)
        if isinstance(value, dict):
            resources.append(value)
    seen = set()
    unique = []
    for resource in resources:
        name = _text_value(resource, ["name", "title", "workplace_name", "resource_name"])
        resource_id = _text_value(resource, ["id", "resource_id", "workplace_id"])
        key = f"{resource_id}:{name}".lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(resource)
    return unique


def _schedule_workplace(schedule: dict[str, Any]) -> dict[str, Any]:
    for key in ("workplace", "resource", "room", "chair", "cabinet"):
        value = schedule.get(key)
        if isinstance(value, dict):
            return value
    return schedule


def _workplace_type(resource: dict[str, Any], appointment: dict[str, Any]) -> str:
    raw = (
        _text_value(resource, ["type", "workplace_type", "resource_type"])
        or _nested_text(resource, ["category"], ["name", "title"])
        or _text_value(appointment, ["workplace_type"])
    ).lower()
    if any(word in raw for word in ("hair", "парик", "крес")):
        return "hair_chair"
    if any(word in raw for word in ("nail", "маник", "педик")):
        return "nail_place"
    if any(word in raw for word in ("cosmet", "космет", "кабин")):
        return "cosmetology_room"
    if any(word in raw for word in ("massage", "массаж")):
        return "massage_room"
    return "other"


def _resource_available_minutes(resource: dict[str, Any]) -> int:
    direct = _durationish_minutes(_first_from(resource, ["available_minutes"]))
    if direct > 0:
        return direct
    hours = _moneyish(_first_from(resource, ["available_hours", "work_hours", "working_hours"]))
    return int(round(hours * 60)) if hours > 0 else 0


def _schedule_available_minutes(schedule: dict[str, Any], resource: dict[str, Any]) -> int:
    direct = _durationish_minutes(_first_from(schedule, ["available_minutes", "work_minutes", "working_minutes"]))
    if direct > 0:
        return direct
    hours = _moneyish(_first_from(schedule, ["available_hours", "work_hours", "working_hours"]))
    if hours > 0:
        return int(round(hours * 60))
    resource_minutes = _resource_available_minutes(resource)
    if resource_minutes > 0:
        return resource_minutes
    return _minutes_between(
        _text_value(schedule, ["start_at", "start", "from", "start_time", "time_from"]),
        _text_value(schedule, ["end_at", "end", "to", "end_time", "time_to"]),
        _text_value(schedule, ["date", "day"]),
    )


def _is_completed_appointment(appointment: dict[str, Any]) -> bool:
    attendance = _first_from(appointment, ["attendance", "attendance_status"])
    if str(attendance) == "1":
        return True
    status = _text_value(appointment, ["status", "state", "visit_status", "attendance"])
    return status.lower() in {"completed", "done", "arrived", "came", "visited", "finished", "paid"}


def _is_no_show_appointment(appointment: dict[str, Any]) -> bool:
    attendance = _first_from(appointment, ["attendance", "attendance_status"])
    if str(attendance) == "-1":
        return True
    status = _text_value(appointment, ["status", "state", "visit_status", "attendance"])
    normalized = status.lower().replace(" ", "_").replace("-", "_")
    return normalized in {"no_show", "noshow", "not_come", "did_not_come"}


def _has_later_completed_or_booked_visit(appointment: dict[str, Any], client_appointments: list[dict[str, Any]]) -> bool:
    current_time = _appointment_datetime(appointment)
    for other in client_appointments:
        if other is appointment:
            continue
        other_time = _appointment_datetime(other)
        if other_time <= current_time:
            continue
        if _is_no_show_appointment(other):
            continue
        if _is_completed_appointment(other) or _is_booked_appointment(other):
            return True
    return False


def _is_booked_appointment(appointment: dict[str, Any]) -> bool:
    attendance = _first_from(appointment, ["attendance", "attendance_status"])
    if str(attendance) in {"0", "2"}:
        return True
    status = _text_value(appointment, ["status", "state", "visit_status"])
    normalized = status.lower().replace(" ", "_").replace("-", "_")
    return normalized in {"booked", "confirmed", "planned", "waiting", "new"}


def _appointment_datetime(appointment: dict[str, Any]) -> str:
    return _text_value(appointment, ["datetime", "date", "start_at", "start", "time", "created_at"])


def _appointment_duration_minutes(appointment: dict[str, Any]) -> int:
    value = _first_from(appointment, ["duration_minutes", "duration", "length", "seance_length"])
    result = _durationish_minutes(value)
    if result > 0:
        return result
    services = _appointment_services(appointment)
    return sum(_durationish_minutes(_first_from(service, ["duration_minutes", "duration", "length"])) for service in services)


def _appointment_amount(appointment: dict[str, Any]) -> float:
    value = _moneyish(_first_from(appointment, ["amount", "paid", "cost", "price", "sum", "total"]))
    if value > 0:
        return value
    services = _appointment_services(appointment)
    return sum(_moneyish(_first_from(service, ["amount", "cost", "price", "sum", "paid"])) for service in services)


def _durationish_minutes(value: Any) -> int:
    amount = _moneyish(value)
    if amount <= 0:
        return 0
    return int(round(amount / 60)) if amount > 600 else int(round(amount))


def _minutes_between(start_value: str, end_value: str, day_value: str = "") -> int:
    start_dt = _parse_datetimeish(start_value, day_value)
    end_dt = _parse_datetimeish(end_value, day_value)
    if not start_dt or not end_dt or end_dt <= start_dt:
        return 0
    return int(round((end_dt - start_dt).total_seconds() / 60))


def _parse_datetimeish(value: str, day_value: str = "") -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidates = [raw]
    if day_value and len(raw) <= 5:
        candidates.append(f"{str(day_value)[:10]}T{raw}:00")
        candidates.append(f"{str(day_value)[:10]} {raw}:00")
    for candidate in candidates:
        clean = candidate.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(clean)
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%H:%M:%S", "%H:%M"):
            try:
                parsed = datetime.strptime(clean, fmt)
                if fmt.startswith("%H") and day_value:
                    parsed_date = date.fromisoformat(str(day_value)[:10])
                    return datetime.combine(parsed_date, parsed.time())
                return parsed
            except ValueError:
                continue
    return None


def _moneyish(value: Any) -> float:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value or "").strip().replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if not raw:
        return 0
    try:
        return float(raw)
    except Exception:
        return 0


def _text_value(item: dict[str, Any], keys: list[str]) -> str:
    value = _first_from(item, keys)
    return str(value or "").strip()


def _nested_text(item: dict[str, Any], parent_keys: list[str], child_keys: list[str]) -> str:
    for parent_key in parent_keys:
        parent = item.get(parent_key)
        if isinstance(parent, dict):
            value = _text_value(parent, child_keys)
            if value:
                return value
    return ""


def _first_from(item: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in item and item.get(key) not in (None, ""):
            return item.get(key)
    return None


def default_crm_period() -> tuple[str, str]:
    today = date.today()
    start = date(today.year, today.month, 1)
    return start.isoformat(), today.isoformat()


def sys_error_text() -> str:
    import sys

    return str(sys.exc_info()[1])
