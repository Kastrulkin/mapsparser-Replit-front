from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo


FINANCE_ROUTE = "/dashboard/finance"
MAX_FINANCE_SALES_ROWS = 100
MAX_FINANCE_SALE_AMOUNT = Decimal("99999999.99")
SALE_TYPES = {"service", "upsell", "cross_sell"}


def finance_result_ref(label: str = "Открыть импорт продаж") -> dict[str, Any]:
    return {
        "entity_type": "finance.sales_import",
        "entity_id": None,
        "label": label,
        "href": FINANCE_ROUTE,
    }


def finance_sales_ingest_tool_contract() -> dict[str, Any]:
    return {
        "name": "finance.ingest_sales",
        "capability": "finance.sales_import",
        "title": "Распознать и добавить продажи",
        "description": (
            "Используйте, когда пользователь вставил одну или несколько фактических продаж и хочет внести их в Финансы. "
            "Преобразуйте каждую продажу в transaction_date YYYY-MM-DD, amount, title, sale_type и notes. "
            "sale_type: service — основная услуга, upsell — допродажа, cross_sell — товар или отдельная кросс-продажа. "
            "Для «сегодня» и «вчера» используйте current_time и Europe/Moscow. "
            "Если непонятно, является ли число суммой одной строки или общим итогом, или если в документе несколько валют, не вызывайте инструмент: верните action=clarification с одним конкретным вопросом. "
            "Не используйте для простого чтения статистики или плана продаж. Запись произойдёт только после preview и подтверждения."
        ),
        "input_schema": {
            "type": "object",
            "required": ["transactions"],
            "properties": {
                "transactions": {
                    "type": "array",
                    "maxItems": MAX_FINANCE_SALES_ROWS,
                    "items": {
                        "type": "object",
                        "required": ["transaction_date", "amount", "title"],
                        "properties": {
                            "transaction_date": {"type": "string", "maxLength": 10},
                            "amount": {"type": "number", "minimum": 0.01, "maximum": 99999999.99},
                            "title": {"type": "string", "maxLength": 300},
                            "sale_type": {"type": "string", "enum": ["service", "upsell", "cross_sell"]},
                            "notes": {"type": "string", "maxLength": 1000},
                        },
                    },
                },
            },
        },
        "risk_class": "financial_write_request",
        "approval_required": True,
        "deterministic_preparation_response": True,
    }


def _clean_text(value: Any, limit: int) -> str:
    return " ".join(str(value or "").strip().split())[:limit]


def _normalized_source_hash(message: Any) -> str:
    normalized = re.sub(r"\s+", " ", str(message or "").strip().casefold())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _amount(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    cleaned = re.sub(r"[^0-9,.-]", "", str(value or "").replace(" ", "")).replace(",", ".")
    try:
        amount = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if not amount.is_finite() or amount <= 0 or amount > MAX_FINANCE_SALE_AMOUNT:
        return None
    return amount.quantize(Decimal("0.01"))


def _transaction_date(value: Any, message: str) -> str:
    text = str(value or "").strip()
    if text:
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            for date_format in ("%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(text, date_format).date().isoformat()
                except ValueError:
                    continue
            return ""
    lowered = message.casefold()
    today = datetime.now(ZoneInfo("Europe/Moscow")).date()
    if any(marker in lowered for marker in ("сегодня", "today")):
        return today.isoformat()
    if any(marker in lowered for marker in ("вчера", "yesterday")):
        return (today - timedelta(days=1)).isoformat()
    return ""


def _duplicate_key(source_hash: str, index: int, row: dict[str, Any]) -> str:
    payload = "|".join(
        (
            source_hash,
            str(index),
            str(row.get("transaction_date") or ""),
            str(row.get("amount") or ""),
            str(row.get("title") or "").casefold(),
            str(row.get("sale_type") or "service"),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_finance_sales(
    arguments: Any,
    *,
    business_id: str,
    message: str,
) -> dict[str, Any]:
    source = arguments if isinstance(arguments, dict) else {}
    raw_rows = source.get("transactions") if isinstance(source.get("transactions"), list) else []
    if not raw_rows:
        return {"rows": [], "errors": ["Не нашёл отдельные строки продаж."]}
    if len(raw_rows) > MAX_FINANCE_SALES_ROWS:
        return {
            "rows": [],
            "errors": [f"За один импорт можно проверить не более {MAX_FINANCE_SALES_ROWS} строк."],
        }
    source_hash = _normalized_source_hash(message)
    import_batch_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos:operator-finance:{business_id}:{source_hash}"))
    rows = []
    errors = []
    for index, raw in enumerate(raw_rows, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Строка {index}: не удалось распознать поля.")
            continue
        amount = _amount(raw.get("amount"))
        transaction_date = _transaction_date(raw.get("transaction_date") or raw.get("date"), message)
        title = _clean_text(raw.get("title") or raw.get("service") or raw.get("description"), 300)
        sale_type = str(raw.get("sale_type") or "service").strip().lower()
        row_errors = []
        if amount is None:
            row_errors.append("нет однозначной суммы")
        if not transaction_date:
            row_errors.append("нет даты")
        if not title:
            row_errors.append("нет названия продажи")
        if sale_type not in SALE_TYPES:
            row_errors.append("непонятен тип продажи")
        if row_errors:
            errors.append(f"Строка {index}: " + ", ".join(row_errors) + ".")
            continue
        row = {
            "transaction_date": transaction_date,
            "amount": str(amount),
            "title": title,
            "sale_type": sale_type,
            "notes": _clean_text(raw.get("notes"), 1000),
            "transaction_type": "income",
            "source": "operator_chat",
            "source_hash": source_hash,
            "import_batch_id": import_batch_id,
        }
        row["duplicate_key"] = _duplicate_key(source_hash, index, row)
        rows.append(row)
    return {
        "rows": rows,
        "errors": errors,
        "source_hash": source_hash,
        "import_batch_id": import_batch_id,
    }


def _existing_duplicate_keys(cursor: Any, business_id: str, rows: list[dict[str, Any]]) -> set[str]:
    keys = [str(row.get("duplicate_key") or "") for row in rows if row.get("duplicate_key")]
    if not keys:
        return set()
    cursor.execute(
        "SELECT duplicate_key FROM financialtransactions WHERE business_id = %s AND duplicate_key = ANY(%s)",
        (business_id, keys),
    )
    existing = set()
    for value in cursor.fetchall() or []:
        if isinstance(value, dict):
            key = value.get("duplicate_key")
        elif hasattr(value, "keys"):
            key = value["duplicate_key"]
        else:
            key = value[0]
        if key:
            existing.add(str(key))
    return existing


def _preview_text(rows: list[dict[str, Any]], duplicate_count: int) -> str:
    total = sum((Decimal(str(row.get("amount") or "0")) for row in rows), Decimal("0"))
    lines = []
    for index, row in enumerate(rows[:10], start=1):
        lines.append(
            f"{index}. {row['transaction_date']} · {row['title']} · {row['amount']} · {row['sale_type']}"
        )
    response = f"Подготовил к записи {len(rows)} продаж на сумму {total:.2f}."
    if duplicate_count:
        response += f" Найдено дублей: {duplicate_count}; они не будут записаны."
    if lines:
        response += "\n\n" + "\n".join(lines)
    if len(rows) > len(lines):
        response += f"\n\nПоказаны первые {len(lines)} из {len(rows)} строк."
    response += "\n\nПроверьте данные и подтвердите запись в «Финансы»."
    return response


def build_finance_sales_preview(
    cursor: Any,
    *,
    business_id: str,
    message: str,
    arguments: Any,
) -> dict[str, Any]:
    normalized = normalize_finance_sales(arguments, business_id=business_id, message=message)
    rows = list(normalized.get("rows") or [])
    errors = list(normalized.get("errors") or [])
    result_ref = finance_result_ref()
    if errors:
        question = errors[0] + " Уточните эту строку или откройте импорт продаж."
        return {
            "status": "clarification_required",
            "intent": "finance.sales_import",
            "chat_response": question,
            "clarification": {"question": question},
            "errors": errors,
            "rows": rows,
            "result_ref": result_ref,
            "external_writes_performed": False,
        }
    try:
        duplicate_keys = _existing_duplicate_keys(cursor, business_id, rows)
    except Exception:
        return {
            "status": "manual_handoff",
            "intent": "finance.sales_import",
            "chat_response": "Не смог безопасно проверить дубли. Откройте импорт продаж в разделе «Финансы».",
            "blocked_reasons": ["finance_duplicate_check_unavailable"],
            "result_ref": result_ref,
            "external_writes_performed": False,
        }
    importable = [row for row in rows if str(row.get("duplicate_key") or "") not in duplicate_keys]
    duplicates = [row for row in rows if str(row.get("duplicate_key") or "") in duplicate_keys]
    if not importable:
        return {
            "status": "completed",
            "intent": "finance.sales_import",
            "chat_response": "Все распознанные продажи уже есть в «Финансах». Повторная запись не нужна.",
            "rows": [],
            "duplicates": duplicates,
            "duplicate_count": len(duplicates),
            "result_ref": finance_result_ref("Открыть Финансы"),
            "external_writes_performed": False,
        }
    return {
        "status": "ready",
        "intent": "finance.sales_import",
        "chat_response": _preview_text(importable, len(duplicates)),
        "rows": importable,
        "duplicates": duplicates,
        "duplicate_count": len(duplicates),
        "recognized_count": len(rows),
        "import_count": len(importable),
        "total_amount": str(sum((Decimal(row["amount"]) for row in importable), Decimal("0"))),
        "source_hash": normalized.get("source_hash"),
        "import_batch_id": normalized.get("import_batch_id"),
        "result_ref": result_ref,
        "external_writes_performed": False,
    }
