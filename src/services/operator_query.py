from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from services.operator_mobile_modules import list_operator_mobile_module


OPERATOR_QUERY_SCHEMA = "localos_operator_query_v1"
QUERY_RESOURCES = {"services", "reviews", "content"}
QUERY_OPERATORS = {"eq", "contains", "gte", "lte", "is_empty"}
QUERY_FIELDS = {
    "services": {"title", "category", "source", "status", "price", "updated_at"},
    "reviews": {"author_name", "source", "rating", "has_response", "text", "published_at", "created_at"},
    "content": {"title", "status", "content_type", "scheduled_for", "updated_at"},
}
QUERY_SORT_FIELDS = {
    "services": {"title", "category", "price", "updated_at"},
    "reviews": {"published_at", "created_at", "rating"},
    "content": {"scheduled_for", "updated_at", "title"},
}
FIELD_ALIASES = {
    "services": {"name": "title", "query": "title", "is_active": "status"},
    "reviews": {"author": "author_name", "query": "text", "date": "published_at", "answered": "has_response"},
    "content": {"theme": "title", "query": "title", "date": "scheduled_for", "type": "content_type"},
}
RESOURCE_TITLES = {
    "services": "услуги",
    "reviews": "отзывы",
    "content": "контент-план",
}
RESOURCE_HREFS = {
    "services": "/dashboard/card?tab=services",
    "reviews": "/dashboard/card?tab=reviews",
    "content": "/dashboard/content",
}


def operator_query_tool_contract() -> dict[str, Any]:
    return {
        "name": "localos.query",
        "capability": "operator.query",
        "title": "Поиск и фильтрация данных LocalOS",
        "description": (
            "Универсально читает услуги, отзывы или элементы контент-плана выбранного бизнеса. "
            "Скомпилируйте запрос пользователя в resource, filters, sort_by, sort_direction, limit и view. "
            "services fields: title, category, source, status, price, updated_at. "
            "reviews fields: author_name, source, rating, has_response, text, published_at, created_at. "
            "content fields: title, status, content_type, scheduled_for, updated_at. "
            "filters use operator eq, contains, gte, lte or is_empty. "
            "Для последней записи используйте sort_direction=desc и limit=1. "
            "Относительные даты переводите в YYYY-MM-DD с учётом current_time из состояния."
        ),
        "input_schema": {
            "type": "object",
            "required": ["resource"],
            "properties": {
                "resource": {"type": "string", "enum": ["services", "reviews", "content"]},
                "filters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["field", "operator"],
                        "properties": {
                            "field": {"type": "string"},
                            "operator": {"type": "string", "enum": ["eq", "contains", "gte", "lte", "is_empty"]},
                            "value": {},
                        },
                    },
                },
                "sort_by": {"type": "string"},
                "sort_direction": {"type": "string", "enum": ["asc", "desc"]},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "view": {"type": "string", "enum": ["auto", "count", "compact", "full"]},
            },
        },
        "risk_class": "read_only",
        "approval_required": False,
        "deterministic_response": True,
    }


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _iso(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _load_module_items(cursor: Any, *, business_id: str, module: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = list_operator_mobile_module(
        cursor,
        module=module,
        scope={"kind": "business", "id": business_id, "business_ids": [business_id]},
    )
    items = [dict(item) for item in result.get("items") or [] if isinstance(item, dict)]
    return items, {
        "as_of": result.get("as_of"),
        "freshness": result.get("freshness") or {},
        "data_warnings": list(result.get("data_warnings") or []),
    }


def _load_reviews(cursor: Any, *, business_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, business_id, source, external_review_id, rating, author_name,
               text, response_text, published_at, created_at, updated_at
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND COALESCE(TRIM(text), '') <> ''
        ORDER BY published_at DESC NULLS LAST, created_at DESC
        LIMIT 500
        """,
        (business_id,),
    )
    items = []
    latest_seen_at = None
    for value in cursor.fetchall() or []:
        item = _row(cursor, value)
        published_at = item.get("published_at") or item.get("created_at")
        if latest_seen_at is None and published_at is not None:
            latest_seen_at = _iso(published_at)
        response_text = str(item.get("response_text") or "").strip()
        items.append(
            {
                **item,
                "kind": "review",
                "title": str(item.get("author_name") or "Отзыв"),
                "subtitle": str(item.get("text") or ""),
                "has_response": bool(response_text),
                "published_at": _iso(item.get("published_at")),
                "created_at": _iso(item.get("created_at")),
                "updated_at": _iso(item.get("updated_at")),
            }
        )
    return items, {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "freshness": {"status": "stored_snapshot", "latest_seen_at": latest_seen_at},
        "data_warnings": [],
    }


def _canonical_field(resource: str, value: Any) -> str:
    field = str(value or "").strip().lower()
    return FIELD_ALIASES.get(resource, {}).get(field, field)


def compile_operator_query(arguments: Any) -> dict[str, Any]:
    source = arguments if isinstance(arguments, dict) else {}
    resource = str(source.get("resource") or "").strip().lower()
    if resource not in QUERY_RESOURCES:
        raise ValueError("unsupported_resource")
    filters = []
    raw_filters = source.get("filters") if isinstance(source.get("filters"), list) else []
    for raw_filter in raw_filters[:10]:
        if not isinstance(raw_filter, dict):
            raise ValueError("invalid_filter")
        field = _canonical_field(resource, raw_filter.get("field"))
        operator = str(raw_filter.get("operator") or "eq").strip().lower()
        if field not in QUERY_FIELDS[resource]:
            raise ValueError(f"unsupported_filter_field:{field}")
        if operator not in QUERY_OPERATORS:
            raise ValueError(f"unsupported_filter_operator:{operator}")
        if operator != "is_empty" and "value" not in raw_filter:
            raise ValueError(f"missing_filter_value:{field}")
        filters.append({"field": field, "operator": operator, "value": raw_filter.get("value")})
    sort_by = _canonical_field(resource, source.get("sort_by"))
    if not sort_by:
        sort_by = {"services": "updated_at", "reviews": "published_at", "content": "scheduled_for"}[resource]
    if sort_by not in QUERY_SORT_FIELDS[resource]:
        raise ValueError(f"unsupported_sort_field:{sort_by}")
    sort_direction = str(source.get("sort_direction") or "desc").strip().lower()
    if sort_direction not in {"asc", "desc"}:
        raise ValueError("unsupported_sort_direction")
    limit = source.get("limit") if isinstance(source.get("limit"), int) and not isinstance(source.get("limit"), bool) else 10
    limit = max(1, min(limit, 50))
    view = str(source.get("view") or "auto").strip().lower()
    if view not in {"auto", "count", "compact", "full"}:
        raise ValueError("unsupported_view")
    return {
        "schema": OPERATOR_QUERY_SCHEMA,
        "operation": "query",
        "resource": resource,
        "filters": filters,
        "sort_by": sort_by,
        "sort_direction": sort_direction,
        "limit": limit,
        "view": view,
    }


def _normalized(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(_iso(value) if value is not None else "").strip().casefold()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = str(value or "").replace(" ", "").replace(",", ".")
    digits = "".join(character for character in cleaned if character.isdigit() or character in {".", "-"})
    try:
        return float(digits)
    except ValueError:
        return None


def _matches(item: dict[str, Any], query_filter: dict[str, Any]) -> bool:
    field = query_filter["field"]
    operator = query_filter["operator"]
    actual = item.get(field)
    expected = query_filter.get("value")
    if operator == "is_empty":
        should_be_empty = True if expected is None else bool(expected)
        is_empty = actual in (None, "", [], {})
        return is_empty == should_be_empty
    if field in {"rating", "price"} and operator in {"eq", "gte", "lte"}:
        actual_number = _number(actual)
        expected_number = _number(expected)
        if actual_number is None or expected_number is None:
            return False
        if operator == "eq":
            return actual_number == expected_number
        if operator == "gte":
            return actual_number >= expected_number
        return actual_number <= expected_number
    actual_text = _normalized(actual)
    expected_text = _normalized(expected)
    if operator == "contains":
        return expected_text in actual_text
    if operator == "eq":
        if field == "status" and isinstance(expected, bool):
            expected_text = "active" if expected else "archived"
        return actual_text == expected_text
    if operator == "gte":
        return actual_text >= expected_text
    if operator == "lte":
        return actual_text <= expected_text
    return False


def _sort_value(item: dict[str, Any], field: str) -> tuple[bool, Any]:
    value = item.get(field)
    if field in {"rating", "price"}:
        numeric = _number(value)
        return numeric is None, numeric if numeric is not None else 0
    return value in (None, ""), _normalized(value)


def _render_service(item: dict[str, Any], *, full: bool) -> str:
    title = str(item.get("title") or item.get("name") or "Услуга").strip()
    details = " · ".join(
        value for value in (
            str(item.get("category") or "").strip(),
            str(item.get("price") or "").strip(),
            str(item.get("source") or "").strip(),
        ) if value
    )
    line = title + (f" — {details}" if details else "")
    description = str(item.get("description") or item.get("subtitle") or "").strip()
    return line + (f"\n{description}" if full and description else "")


def _render_review(item: dict[str, Any], *, full: bool) -> str:
    author = str(item.get("author_name") or "Автор не указан").strip()
    rating = str(item.get("rating") or "").strip()
    published_at = str(item.get("published_at") or item.get("created_at") or "").strip()[:10]
    source = str(item.get("source") or "").strip()
    details = " · ".join(value for value in (published_at, f"{rating}/5" if rating else "", source) if value)
    line = author + (f" — {details}" if details else "")
    text = str(item.get("text") or item.get("subtitle") or "").strip()
    if full and text:
        line += f"\n{text}"
    line += "\nОтвет опубликован" if item.get("has_response") else "\nБез ответа"
    return line


def _render_content(item: dict[str, Any], *, full: bool) -> str:
    title = str(item.get("title") or item.get("theme") or "Элемент контент-плана").strip()
    details = " · ".join(
        value for value in (
            str(item.get("scheduled_for") or "").strip()[:10],
            str(item.get("status") or "").strip(),
            str(item.get("content_type") or "").strip(),
        ) if value
    )
    line = title + (f" — {details}" if details else "")
    body = str(item.get("draft_text") or item.get("subtitle") or "").strip()
    return line + (f"\n{body}" if full and body else "")


def render_operator_query(query: dict[str, Any], items: list[dict[str, Any]], total_count: int) -> str:
    resource = query["resource"]
    resource_title = RESOURCE_TITLES[resource]
    if not items:
        return f"По заданным условиям не нашёл данные в разделе «{resource_title}»."
    if query["view"] == "count":
        return f"Найдено записей в разделе «{resource_title}»: {total_count}."
    full = query["view"] == "full" or (query["view"] == "auto" and query["limit"] <= 10)
    renderer = {"services": _render_service, "reviews": _render_review, "content": _render_content}[resource]
    rendered_items = items[:10] if full else items
    lines = [f"{index}. {renderer(item, full=full)}" for index, item in enumerate(rendered_items, start=1)]
    response = f"Нашёл {total_count} записей в разделе «{resource_title}»:\n\n" + "\n\n".join(lines)
    if len(items) > len(rendered_items):
        response += f"\n\nПоказал первые {len(rendered_items)} из {len(items)} выбранных записей."
    return response


def execute_operator_query(cursor: Any, *, business_id: str, arguments: Any) -> dict[str, Any]:
    try:
        query = compile_operator_query(arguments)
    except ValueError as exc:
        return {
            "status": "denied",
            "intent": "operator.query",
            "error_code": "invalid_operator_query",
            "details": [str(exc)],
            "chat_response": "Не удалось безопасно применить фильтры запроса. Уточните условие.",
            "external_writes_performed": False,
        }
    if query["resource"] == "reviews":
        items, metadata = _load_reviews(cursor, business_id=business_id)
    else:
        items, metadata = _load_module_items(cursor, business_id=business_id, module=query["resource"])
    matched = [item for item in items if all(_matches(item, query_filter) for query_filter in query["filters"])]
    reverse = query["sort_direction"] == "desc"
    matched.sort(key=lambda item: _sort_value(item, query["sort_by"])[1], reverse=reverse)
    matched.sort(key=lambda item: _sort_value(item, query["sort_by"])[0])
    total_count = len(matched)
    selected = matched[:query["limit"]]
    chat_response = render_operator_query(query, selected, total_count)
    if query["resource"] == "reviews":
        latest_seen_at = str((metadata.get("freshness") or {}).get("latest_seen_at") or "").strip()
        freshness_note = (
            f"Последний сохранённый отзыв датирован {latest_seen_at[:10]}."
            if latest_seen_at
            else "В сохранённом снимке пока нет даты последнего отзыва."
        )
        chat_response += (
            "\n\n"
            + freshness_note
            + " Для проверки новых отзывов во внешних картах используйте отдельную команду обновления."
        )
    return {
        "status": "completed",
        "intent": "operator.query",
        "resource": query["resource"],
        "query": query,
        "items": selected,
        "count": total_count,
        "as_of": metadata.get("as_of"),
        "freshness": metadata.get("freshness") or {},
        "data_warnings": metadata.get("data_warnings") or [],
        "provenance": {"source": "localos_stored_data", "business_id": business_id},
        "chat_response": chat_response,
        "result_ref": {
            "entity_type": f"{query['resource']}.query",
            "entity_id": None,
            "label": f"Открыть раздел «{RESOURCE_TITLES[query['resource']]}»",
            "href": RESOURCE_HREFS[query["resource"]],
        },
        "ui_actions": [
            {
                "action": "open_result",
                "label": f"Открыть раздел «{RESOURCE_TITLES[query['resource']]}»",
                "href": RESOURCE_HREFS[query["resource"]],
                "payload": {},
            }
        ],
        "external_calls_performed": False,
        "external_writes_performed": False,
        "paid_actions_performed": False,
    }
