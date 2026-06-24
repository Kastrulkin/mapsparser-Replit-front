from __future__ import annotations

import csv
import hashlib
import importlib
import io
import json
import re
from datetime import datetime
from typing import Any


ENTRY_TYPES = {"revenue", "expense"}
WORKPLACE_TYPES = {"hair_chair", "nail_place", "cosmetology_room", "massage_room", "other"}

RU_MONTHS_GENITIVE = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

YCLIENTS_STATS_REVENUE_ROWS = {
    "оказание услуг": "services",
    "пополнение счета": "account_topup",
    "продажа абонементов": "subscriptions",
    "продажа сертификатов": "certificates",
    "продажа товаров": "retail",
    "прочие доходы": "other_revenue",
}

YCLIENTS_STATS_EXPENSE_ROWS = {
    "закупка материалов": "materials",
    "закупка товаров": "goods_purchase",
    "зарплата персонала": "payroll",
    "комиссия за эквайринг": "acquiring_fee",
    "налоги и сборы": "taxes",
    "прочие расходы": "other_expense",
}

FIELD_ALIASES = {
    "record_type": ["record_type", "type_record", "тип записи", "тип строки", "раздел"],
    "date": ["date", "transaction_date", "дата", "день"],
    "type": ["type", "тип", "доход/расход", "операция"],
    "category": ["category", "категория", "статья", "направление"],
    "amount": ["amount", "sum", "сумма", "выручка", "расход"],
    "comment": ["comment", "notes", "комментарий", "примечание"],
    "service_name": ["service_name", "service", "услуга", "название услуги"],
    "staff_name": ["staff_name", "master", "мастер", "сотрудник"],
    "role": ["role", "роль", "должность"],
    "workplace_name": ["workplace_name", "workplace", "кресло", "кабинет", "рабочее место"],
    "workplace_type": ["workplace_type", "тип места", "тип рабочего места"],
    "period_start": ["period_start", "начало периода", "период начало"],
    "period_end": ["period_end", "конец периода", "период конец"],
    "revenue": ["revenue", "выручка услуги", "выручка мастера", "выручка места"],
    "visits_count": ["visits_count", "visits", "визиты", "продаж", "количество"],
    "avg_price": ["avg_price", "average_price", "средняя цена", "средний чек"],
    "duration_minutes": ["duration_minutes", "duration", "длительность", "минут"],
    "material_cost": ["material_cost", "materials", "материалы", "себестоимость"],
    "staff_payout": ["staff_payout", "payout", "выплата мастеру", "фот услуги"],
    "booked_hours": ["booked_hours", "занято часов", "занятые часы"],
    "available_hours": ["available_hours", "доступно часов", "доступные часы"],
    "booked_minutes": ["booked_minutes", "занято минут", "занятые минуты"],
    "available_minutes": ["available_minutes", "доступно минут", "доступные минуты"],
    "no_show_count": ["no_show_count", "no-show", "неявки"],
    "rebooking_count": ["rebooking_count", "rebooking", "повторная запись"],
    "gross_profit": ["gross_profit", "валовая прибыль", "прибыль"],
    "external_id": ["external_id", "id", "внешний id", "номер"],
}


TEMPLATE_COLUMNS = [
    "record_type",
    "date",
    "type",
    "category",
    "amount",
    "service_name",
    "staff_name",
    "role",
    "workplace_name",
    "workplace_type",
    "period_start",
    "period_end",
    "revenue",
    "visits_count",
    "avg_price",
    "duration_minutes",
    "material_cost",
    "staff_payout",
    "booked_hours",
    "available_hours",
    "no_show_count",
    "rebooking_count",
    "gross_profit",
    "external_id",
    "comment",
]


IMPORT_TEMPLATE_PROFILES = {
    "manual": {
        "label": "Ручная таблица LocalOS",
        "description": "Универсальный шаблон для ручного заполнения выручки, услуг, мастеров и рабочих мест.",
    },
    "yclients": {
        "label": "YCLIENTS / Altegio продажи",
        "description": "Упрощенный шаблон для выгрузки продаж, услуг и мастеров из CRM.",
    },
    "workplaces": {
        "label": "Кресла и кабинеты",
        "description": "Шаблон для загрузки рабочих мест, доступных часов, занятости и прибыли.",
    },
    "yclients_stats": {
        "label": "YCLIENTS / Altegio статистика",
        "description": "Широкая выгрузка статистики по дням: Статья, 1 июня (нал), 1 июня (б/н), 1 июня (Всего).",
    },
}


def finance_import_templates() -> dict[str, dict[str, str]]:
    return dict(IMPORT_TEMPLATE_PROFILES)


def finance_import_template_csv(profile: str = "manual") -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TEMPLATE_COLUMNS)
    writer.writeheader()
    if profile == "yclients":
        writer.writerow(
            {
                "record_type": "service",
                "service_name": "Маникюр с покрытием",
                "staff_name": "Анна",
                "period_start": "2026-03-01",
                "period_end": "2026-05-31",
                "revenue": "240000",
                "visits_count": "80",
                "avg_price": "3000",
                "duration_minutes": "120",
                "external_id": "crm-service-001",
            }
        )
        writer.writerow(
            {
                "record_type": "staff",
                "staff_name": "Анна",
                "role": "Мастер",
                "period_start": "2026-03-01",
                "period_end": "2026-05-31",
                "revenue": "240000",
                "visits_count": "80",
                "booked_hours": "160",
                "available_hours": "220",
                "no_show_count": "4",
                "rebooking_count": "45",
                "external_id": "crm-staff-001",
            }
        )
        return output.getvalue()
    if profile == "workplaces":
        writer.writerow(
            {
                "record_type": "workplace",
                "workplace_name": "Кресло 1",
                "workplace_type": "hair_chair",
                "period_start": "2026-03-01",
                "period_end": "2026-05-31",
                "revenue": "500000",
                "gross_profit": "250000",
                "booked_hours": "120",
                "available_hours": "160",
            }
        )
        return output.getvalue()
    writer.writerow(
        {
            "record_type": "entry",
            "date": "2026-05-01",
            "type": "revenue",
            "category": "sales",
            "amount": "900000",
            "comment": "Выручка за месяц",
        }
    )
    writer.writerow(
        {
            "record_type": "service",
            "service_name": "Окрашивание",
            "category": "Волосы",
            "period_start": "2026-03-01",
            "period_end": "2026-05-31",
            "revenue": "500000",
            "visits_count": "50",
            "avg_price": "10000",
            "duration_minutes": "180",
            "material_cost": "70000",
            "staff_payout": "180000",
        }
    )
    writer.writerow(
        {
            "record_type": "staff",
            "staff_name": "Анна",
            "role": "Стилист",
            "period_start": "2026-03-01",
            "period_end": "2026-05-31",
            "revenue": "500000",
            "visits_count": "50",
            "booked_hours": "120",
            "available_hours": "160",
            "no_show_count": "3",
            "rebooking_count": "32",
        }
    )
    writer.writerow(
        {
            "record_type": "workplace",
            "workplace_name": "Кресло 1",
            "workplace_type": "hair_chair",
            "period_start": "2026-03-01",
            "period_end": "2026-05-31",
            "revenue": "500000",
            "gross_profit": "250000",
            "booked_hours": "120",
            "available_hours": "160",
        }
    )
    return output.getvalue()


def file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_finance_file(filename: str, content: bytes) -> list[dict[str, Any]]:
    lower = filename.lower()
    if lower.endswith(".csv") or lower.endswith(".txt"):
        return _parse_csv(content)
    if lower.endswith(".xlsx") or lower.endswith(".xls"):
        return _parse_excel(content)
    raise ValueError("Поддерживаются CSV и XLSX")


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = _decode_text_content(content)
    sample = text[:2048]
    delimiter = ","
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t").delimiter
    except Exception:
        delimiter = ";"

    plain_rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    stats_rows = _parse_yclients_stats_rows(plain_rows)
    if stats_rows:
        return stats_rows

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [_clean_row(row) for row in reader]


def _decode_text_content(content: bytes) -> str:
    if content.startswith((b"\xff\xfe", b"\xfe\xff")):
        return content.decode("utf-16")
    text = content.decode("utf-8-sig", errors="ignore")
    if "\x00" in text:
        try:
            return content.decode("utf-16")
        except Exception:
            return text.replace("\x00", "")
    return text


def _parse_yclients_stats_rows(rows: list[list[str]]) -> list[dict[str, Any]]:
    if not rows:
        return []

    header = [_normalize_header(cell) for cell in rows[0]]
    if not header or header[0] != "статья":
        return []

    day_columns = []
    for index, title in enumerate(header):
        match = re.match(r"^(\d{1,2})\s+([а-яё]+)\s+\(([^)]+)\)$", title)
        if not match:
            continue
        payment_marker = _normalize_header(match.group(3))
        month_number = RU_MONTHS_GENITIVE.get(_normalize_header(match.group(2)))
        if payment_marker != "всего" or not month_number:
            continue
        day_columns.append((index, int(match.group(1)), month_number))

    if not day_columns:
        return []

    year = datetime.now().year
    result = []
    for row in rows[1:]:
        if not row:
            continue
        row_name = _normalize_header(row[0])
        row_type = ""
        category = ""
        if row_name in YCLIENTS_STATS_REVENUE_ROWS:
            row_type = "revenue"
            category = YCLIENTS_STATS_REVENUE_ROWS[row_name]
        elif row_name in YCLIENTS_STATS_EXPENSE_ROWS:
            row_type = "expense"
            category = YCLIENTS_STATS_EXPENSE_ROWS[row_name]
        else:
            continue

        label = str(row[0] or "").strip()
        for index, day, month_number in day_columns:
            raw_amount = row[index] if index < len(row) else ""
            amount = _money(raw_amount)
            if amount is None or amount == 0:
                continue
            date_value = datetime(year, month_number, day).date().isoformat()
            result.append(
                {
                    "record_type": "entry",
                    "date": date_value,
                    "type": row_type,
                    "category": category,
                    "amount": str(amount),
                    "external_id": f"yclients-stats:{date_value}:{row_type}:{category}",
                    "comment": f"YCLIENTS статистика: {label}",
                }
            )

    return result


def _parse_excel(content: bytes) -> list[dict[str, Any]]:
    pandas_module = importlib.import_module("pandas")
    frame = pandas_module.read_excel(io.BytesIO(content))
    rows = json.loads(frame.fillna("").to_json(orient="records", force_ascii=False))
    return [_clean_row(row) for row in rows]


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for key, value in (row or {}).items():
        clean_key = _normalize_header(key)
        if not clean_key:
            continue
        result[clean_key] = "" if value is None else str(value).strip()
    return result


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower().replace("\ufeff", "")


def suggest_finance_mapping(headers: list[str]) -> dict[str, str]:
    normalized_headers = {_normalize_header(header): header for header in headers}
    mapping = {}
    for canonical, aliases in FIELD_ALIASES.items():
        candidates = [_normalize_header(canonical)] + [_normalize_header(alias) for alias in aliases]
        for candidate in candidates:
            if candidate in normalized_headers:
                mapping[canonical] = normalized_headers[candidate]
                break
    return mapping


def normalize_finance_import_rows(
    rows: list[dict[str, Any]],
    mapping: dict[str, str] | None = None,
    period_start: str | None = None,
    period_end: str | None = None,
) -> dict[str, Any]:
    mapping = mapping or suggest_finance_mapping(list(rows[0].keys()) if rows else [])
    normalized = []
    errors = []

    for index, raw in enumerate(rows, start=1):
        canonical = _apply_mapping(raw, mapping)
        item, item_errors = _normalize_import_row(canonical, period_start, period_end)
        if item_errors:
            errors.append({"row": index, "errors": item_errors, "raw": raw})
            continue
        item["row_number"] = index
        item["duplicate_key"] = build_duplicate_key(item)
        normalized.append(item)

    return {
        "mapping": mapping,
        "rows": normalized,
        "errors": errors,
        "total": len(rows),
    }


def _apply_mapping(raw: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    normalized_raw = {_normalize_header(key): value for key, value in raw.items()}
    result = {}
    for canonical, source in mapping.items():
        result[canonical] = normalized_raw.get(_normalize_header(source), "")
    for key, value in raw.items():
        clean_key = _normalize_header(key)
        if clean_key not in result:
            result[clean_key] = value
    return result


def _normalize_import_row(row: dict[str, Any], default_start: str | None, default_end: str | None) -> tuple[dict[str, Any], list[str]]:
    errors = []
    record_type = _record_type(row)
    item = {"record_type": record_type, "external_id": _str(row.get("external_id"))}

    if record_type == "entry":
        entry_type = _str(row.get("type")).lower()
        if entry_type not in ENTRY_TYPES:
            errors.append("type должен быть revenue или expense")
        item.update(
            {
                "date": _date(row.get("date")),
                "type": entry_type,
                "category": _str(row.get("category")) or "other",
                "amount": _money(row.get("amount")),
                "comment": _str(row.get("comment")),
            }
        )
        if not item["date"]:
            errors.append("нужна дата")
        if item["amount"] is None:
            errors.append("сумма должна быть числом")
    elif record_type == "service":
        item.update(_period_fields(row, default_start, default_end))
        item.update(
            {
                "service_name": _str(row.get("service_name")),
                "category": _str(row.get("category")),
                "revenue": _money(row.get("revenue") or row.get("amount")),
                "visits_count": _int(row.get("visits_count")),
                "avg_price": _money(row.get("avg_price")),
                "duration_minutes": _minutes(row),
                "material_cost": _money(row.get("material_cost")),
                "staff_payout": _money(row.get("staff_payout")),
            }
        )
        if not item["service_name"]:
            errors.append("нужно название услуги")
        _require_nonnegative_numbers(item, errors, ["revenue", "visits_count", "avg_price", "duration_minutes", "material_cost", "staff_payout"])
    elif record_type == "staff":
        item.update(_period_fields(row, default_start, default_end))
        item.update(
            {
                "staff_name": _str(row.get("staff_name")),
                "role": _str(row.get("role")),
                "revenue": _money(row.get("revenue") or row.get("amount")),
                "visits_count": _int(row.get("visits_count")),
                "booked_minutes": _minutes_from_pair(row, "booked"),
                "available_minutes": _minutes_from_pair(row, "available"),
                "no_show_count": _int(row.get("no_show_count")),
                "rebooking_count": _int(row.get("rebooking_count")),
            }
        )
        if not item["staff_name"]:
            errors.append("нужно имя мастера")
        _require_nonnegative_numbers(item, errors, ["revenue", "visits_count", "booked_minutes", "available_minutes", "no_show_count", "rebooking_count"])
    elif record_type == "workplace":
        item.update(_period_fields(row, default_start, default_end))
        item.update(
            {
                "workplace_name": _str(row.get("workplace_name")),
                "workplace_type": _str(row.get("workplace_type")) or "other",
                "revenue": _money(row.get("revenue") or row.get("amount")),
                "gross_profit": _money(row.get("gross_profit")),
                "booked_minutes": _minutes_from_pair(row, "booked"),
                "available_minutes": _minutes_from_pair(row, "available"),
            }
        )
        if item["workplace_type"] not in WORKPLACE_TYPES:
            item["workplace_type"] = "other"
        if not item["workplace_name"]:
            errors.append("нужно название рабочего места")
        _require_nonnegative_numbers(item, errors, ["revenue", "gross_profit", "booked_minutes", "available_minutes"])
    else:
        errors.append("record_type должен быть entry, service, staff или workplace")

    return item, errors


def _record_type(row: dict[str, Any]) -> str:
    raw = _str(row.get("record_type")).lower()
    if raw in {"entry", "service", "staff", "workplace"}:
        return raw
    if _str(row.get("service_name")):
        return "service"
    if _str(row.get("staff_name")):
        return "staff"
    if _str(row.get("workplace_name")):
        return "workplace"
    return "entry"


def _period_fields(row: dict[str, Any], default_start: str | None, default_end: str | None) -> dict[str, str | None]:
    return {
        "period_start": _date(row.get("period_start")) or default_start,
        "period_end": _date(row.get("period_end")) or default_end,
    }


def _require_nonnegative_numbers(item: dict[str, Any], errors: list[str], fields: list[str]) -> None:
    for field in fields:
        value = item.get(field)
        if value is None:
            errors.append(f"{field} должно быть числом")
        elif value < 0:
            errors.append(f"{field} не может быть отрицательным")


def _str(value: Any) -> str:
    return str(value or "").strip()


def _money(value: Any) -> float | None:
    raw = _str(value).replace(" ", "").replace("\u00a0", "").replace(",", ".")
    if raw == "":
        return 0.0
    try:
        result = float(raw)
    except Exception:
        return None
    if result < 0:
        return None
    return result


def _int(value: Any) -> int | None:
    money = _money(value)
    if money is None:
        return None
    return int(round(money))


def _minutes(row: dict[str, Any]) -> int | None:
    raw_minutes = row.get("duration_minutes")
    if _str(raw_minutes):
        return _int(raw_minutes)
    return 0


def _minutes_from_pair(row: dict[str, Any], prefix: str) -> int | None:
    minutes = row.get(f"{prefix}_minutes")
    if _str(minutes):
        return _int(minutes)
    hours = _money(row.get(f"{prefix}_hours"))
    if hours is None:
        return None
    return int(round(hours * 60))


def _date(value: Any) -> str | None:
    raw = _str(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw[:10], fmt).date().isoformat()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def build_duplicate_key(item: dict[str, Any]) -> str:
    record_type = item.get("record_type")
    external_id = _str(item.get("external_id"))
    if external_id:
        basis = {"record_type": record_type, "external_id": external_id}
    elif record_type == "entry":
        basis = {
            "record_type": record_type,
            "date": item.get("date"),
            "type": item.get("type"),
            "category": item.get("category"),
            "amount": item.get("amount"),
        }
    elif record_type == "service":
        basis = {
            "record_type": record_type,
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "service_name": _str(item.get("service_name")).lower(),
            "revenue": item.get("revenue"),
            "visits_count": item.get("visits_count"),
        }
    elif record_type == "staff":
        basis = {
            "record_type": record_type,
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "staff_name": _str(item.get("staff_name")).lower(),
            "revenue": item.get("revenue"),
            "visits_count": item.get("visits_count"),
        }
    else:
        basis = {
            "record_type": record_type,
            "period_start": item.get("period_start"),
            "period_end": item.get("period_end"),
            "workplace_name": _str(item.get("workplace_name")).lower(),
            "available_minutes": item.get("available_minutes"),
            "booked_minutes": item.get("booked_minutes"),
        }
    raw = json.dumps(basis, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
