from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from database_manager import DatabaseManager
from core.card_audit import build_card_audit_snapshot
from core.helpers import get_business_owner_id
from core.seo_keywords import collect_ranked_keywords
from core.content_plan_generator import build_content_plan_skeleton
from services.gigachat_client import analyze_text_with_gigachat
from subscription_manager import get_allowed_content_plan_horizons, get_subscription_access


def _row_get(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            return default
    try:
        return row[index]
    except Exception:
        return default


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if not row:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    description = getattr(cursor, "description", None) or []
    if description and isinstance(row, (tuple, list)):
        return {
            str(column[0]): row[idx]
            for idx, column in enumerate(description)
            if idx < len(row)
        }
    return {}


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (str(table_name or "").lower(), str(column_name or "").lower()),
    )
    return bool(cursor.fetchone())


def _normalize_scope_type(raw_scope_type: str) -> str:
    value = str(raw_scope_type or "").strip().lower()
    if value in {"network_parent", "network_location"}:
        return value
    return "single_business"


def _scope_target_business_id(cursor: Any, business_id: str, scope_type: str, scope_target_id: str | None) -> str:
    normalized_scope = _normalize_scope_type(scope_type)
    target_id = str(scope_target_id or "").strip() or str(business_id or "").strip()
    if normalized_scope in {"network_location", "network_parent"}:
        return target_id
    return str(business_id or "").strip()


def _scope_description(scope_type: str, label: str, city: str, address: str) -> str:
    normalized_scope = _normalize_scope_type(scope_type)
    clean_label = str(label or "").strip()
    clean_city = str(city or "").strip()
    clean_address = str(address or "").strip()
    if normalized_scope == "network_parent":
        if clean_label:
            return f"Общий план для сети {clean_label}: брендовые темы, сезонные акценты и единый ритм публикаций."
        return "Общий план для всей сети: брендовые темы, сезонные акценты и единый ритм публикаций."
    if normalized_scope == "network_location":
        location_hint = clean_city or clean_address or clean_label
        if location_hint:
            return f"Локальный план для точки {location_hint}: адресные поводы, отзывы, локальный спрос и конкретные услуги."
        return "Локальный план для отдельной точки: адресные поводы, отзывы, локальный спрос и конкретные услуги."
    return "План для текущего бизнеса: новости, услуги, SEO-сценарии и регулярные обновления карточки."


def _fetch_business_row(cursor: Any, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, owner_id, name, city, address, network_id, business_type, categories
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _resolve_scope_target_meta(cursor: Any, plan_business_id: str, scope_type: str, scope_target_id: str | None) -> dict[str, str]:
    normalized_scope = _normalize_scope_type(scope_type)
    target_id = str(scope_target_id or "").strip()
    fallback_business_id = str(plan_business_id or "").strip()
    lookup_id = target_id or fallback_business_id
    row = _fetch_business_row(cursor, lookup_id) if lookup_id else {}
    if not row and fallback_business_id and fallback_business_id != lookup_id:
        row = _fetch_business_row(cursor, fallback_business_id)
    label = str(row.get("name") or "").strip()
    city = str(row.get("city") or "").strip()
    address = str(row.get("address") or "").strip()
    if not label:
        if normalized_scope == "network_parent":
            label = "Материнская точка"
        elif normalized_scope == "network_location":
            label = "Точка сети"
        else:
            label = "Текущий бизнес"
    return {
        "scope_target_label": label,
        "scope_target_city": city,
        "scope_target_address": address,
    }


def _network_location_targets_from_context(context: dict[str, Any]) -> list[dict[str, str]]:
    scope = context.get("scope") if isinstance(context.get("scope"), dict) else {}
    scope_options = scope.get("scope_options") if isinstance(scope.get("scope_options"), list) else []
    targets: list[dict[str, str]] = []
    for item in scope_options:
        if not isinstance(item, dict):
            continue
        if str(item.get("scope_type") or "").strip() != "network_location":
            continue
        target_id = str(item.get("scope_target_id") or "").strip()
        if not target_id:
            continue
        targets.append(
            {
                "business_id": target_id,
                "label": str(item.get("label") or "").strip(),
                "city": str(item.get("city") or "").strip(),
                "address": str(item.get("address") or "").strip(),
            }
        )
    return targets


def _fetch_network_scope_options(cursor: Any, business_row: dict[str, Any]) -> list[dict[str, Any]]:
    network_id = str(business_row.get("network_id") or "").strip()
    business_id = str(business_row.get("id") or "").strip()
    if not network_id:
        return [
            {
                "scope_type": "single_business",
                "scope_target_id": business_id,
                "label": str(business_row.get("name") or "Текущий бизнес"),
                "is_current": True,
            }
        ]

    cursor.execute(
        """
        SELECT id, name, city, address
        FROM businesses
        WHERE network_id = %s OR id = %s
        ORDER BY created_at ASC, name ASC
        """,
        (network_id, network_id),
    )
    rows = cursor.fetchall() or []
    options = []
    parent_business_id = network_id
    for row in rows:
        item = _row_to_dict(cursor, row)
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        is_parent = item_id == parent_business_id
        scope_type = "network_parent" if is_parent else "network_location"
        options.append(
            {
                "scope_type": scope_type,
                "scope_target_id": item_id,
                "label": str(item.get("name") or "Точка").strip() or "Точка",
                "city": str(item.get("city") or "").strip(),
                "address": str(item.get("address") or "").strip(),
                "is_parent": is_parent,
                "is_current": item_id == business_id,
            }
        )
    if not options:
        options.append(
            {
                "scope_type": "single_business",
                "scope_target_id": business_id,
                "label": str(business_row.get("name") or "Текущий бизнес"),
                "is_current": True,
            }
        )
    return options


def _fetch_services(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, name, description, category, price
        FROM userservices
        WHERE business_id = %s
          AND (is_active IS TRUE OR is_active IS NULL)
        ORDER BY updated_at DESC NULLS LAST, created_at DESC
        LIMIT 100
        """,
        (business_id,),
    )
    rows = cursor.fetchall() or []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "name": str(_row_get(row, "name", 1, "") or "").strip(),
            "description": str(_row_get(row, "description", 2, "") or "").strip(),
            "category": str(_row_get(row, "category", 3, "") or "").strip(),
            "price": str(_row_get(row, "price", 4, "") or "").strip(),
        }
        for row in rows
        if str(_row_get(row, "name", 1, "") or "").strip()
    ]


def _fetch_recent_news(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    has_business_id = _table_has_column(cursor, "usernews", "business_id")
    if has_business_id:
        cursor.execute(
            """
            SELECT id, generated_text, approved, created_at
            FROM usernews
            WHERE user_id = %s AND business_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id, business_id),
        )
    else:
        cursor.execute(
            """
            SELECT id, generated_text, approved, created_at
            FROM usernews
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user_id,),
        )
    rows = cursor.fetchall() or []
    return [
        {
            "id": str(_row_get(row, "id", 0, "") or "").strip(),
            "text": str(_row_get(row, "generated_text", 1, "") or "").strip(),
            "approved": bool(_row_get(row, "approved", 2, False)),
            "created_at": _row_get(row, "created_at", 3),
        }
        for row in rows
        if str(_row_get(row, "generated_text", 1, "") or "").strip()
    ]


def _fetch_map_link_count(cursor: Any, business_id: str) -> int:
    try:
        cursor.execute("SELECT to_regclass('public.businessmaplinks')")
        row = cursor.fetchone()
        if not _row_get(row, "to_regclass", 0, None):
            return 0
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM businessmaplinks
            WHERE business_id = %s
            """,
            (business_id,),
        )
        count_row = cursor.fetchone()
        return int(_row_get(count_row, "count", 0, 0) or 0)
    except Exception:
        return 0


def _fetch_sales_signals(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, transaction_date, amount, services, notes
        FROM financialtransactions
        WHERE user_id = %s AND business_id = %s
        ORDER BY transaction_date DESC NULLS LAST, created_at DESC
        LIMIT 20
        """,
        (user_id, business_id),
    )
    rows = cursor.fetchall() or []
    signals = []
    for row in rows:
        services_raw = _row_get(row, "services", 3, None)
        services_list = []
        if services_raw:
            try:
                parsed = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                if isinstance(parsed, list):
                    services_list = [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                services_list = []
        title = ", ".join(services_list[:3]) if services_list else str(_row_get(row, "notes", 4, "") or "").strip()
        if not title:
            title = f"Продажа на {_row_get(row, 'transaction_date', 1, '')}"
        signals.append(
            {
                "transaction_id": str(_row_get(row, "id", 0, "") or "").strip(),
                "title": title,
                "amount": float(_row_get(row, "amount", 2, 0) or 0),
                "transaction_date": _row_get(row, "transaction_date", 1),
            }
        )
    return signals


def _fetch_seo_keywords(cursor: Any, user_id: str, business_id: str) -> list[dict[str, Any]]:
    payload = collect_ranked_keywords(
        cursor,
        business_id,
        user_id,
        limit=30,
        add_city_suffix=True,
        # Content planning should stay grounded in real business context.
        # If the card has no services/business-type hints yet, returning empty
        # is safer than proposing unrelated global demand topics.
        fallback_global_when_empty_terms=False,
    )
    items = payload.get("items") if isinstance(payload.get("items"), list) else []
    return [
        {
            "keyword": str(item.get("keyword") or "").strip(),
            "views": int(item.get("views") or 0),
            "category": str(item.get("category") or "").strip(),
        }
        for item in items[:20]
        if str(item.get("keyword") or "").strip()
    ]


def _fetch_seo_keywords_isolated(user_id: str, business_id: str) -> list[dict[str, Any]]:
    seo_db = DatabaseManager()
    seo_cursor = seo_db.conn.cursor()
    try:
        return _fetch_seo_keywords(seo_cursor, user_id, business_id)
    except Exception:
        try:
            seo_db.conn.rollback()
        except Exception:
            pass
        return []
    finally:
        seo_db.close()


def _fetch_audit_signals(scope_business_id: str) -> list[dict[str, Any]]:
    try:
        audit = build_card_audit_snapshot(scope_business_id)
    except Exception:
        return []
    issue_blocks = audit.get("issue_blocks") if isinstance(audit.get("issue_blocks"), list) else []
    return [
        {
            "title": str(item.get("title") or "").strip(),
            "problem": str(item.get("problem") or "").strip(),
            "priority": str(item.get("priority") or "").strip(),
        }
        for item in issue_blocks[:10]
        if str(item.get("title") or item.get("problem") or "").strip()
    ]


def _build_planning_readiness(
    *,
    map_links_count: int,
    services_count: int,
    seo_keywords_count: int,
    sales_signals_count: int,
    audit_signals_count: int,
) -> dict[str, Any]:
    missing_inputs: list[str] = []
    if map_links_count <= 0:
        missing_inputs.append("map_links")
    if services_count <= 0:
        missing_inputs.append("services")
    if seo_keywords_count <= 0:
        missing_inputs.append("seo_keywords")

    return {
        "map_links_count": int(map_links_count or 0),
        "has_map_links": map_links_count > 0,
        "has_services": services_count > 0,
        "has_seo_keywords": seo_keywords_count > 0,
        "has_sales_signals": sales_signals_count > 0,
        "has_audit_signals": audit_signals_count > 0,
        "missing_inputs": missing_inputs,
        "is_grounded_for_search": map_links_count > 0 and services_count > 0 and seo_keywords_count > 0,
    }


def ensure_content_plan_tables(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplans (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            network_id TEXT,
            scope_type TEXT NOT NULL DEFAULT 'single_business',
            scope_target_id TEXT,
            title TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            plan_status TEXT NOT NULL DEFAULT 'generated',
            generation_mode TEXT NOT NULL DEFAULT 'manual',
            input_snapshot_json JSONB,
            generated_plan_json JSONB,
            edited_plan_json JSONB,
            published_plan_json JSONB,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplanitems (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES contentplans(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            scheduled_for DATE NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'news',
            theme TEXT NOT NULL,
            goal TEXT,
            source_kind TEXT,
            source_ref TEXT,
            seo_keyword TEXT,
            service_id TEXT,
            transaction_id TEXT,
            location_scope TEXT,
            draft_text TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            usernews_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _ensure_usernews_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS usernews (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            service_id TEXT,
            source_text TEXT,
            generated_text TEXT NOT NULL,
            approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS business_id TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")


def _build_scope_business_context(cursor: Any, business_row: dict[str, Any], scope_type: str, scope_target_id: str | None) -> dict[str, Any]:
    scope_business_id = _scope_target_business_id(cursor, str(business_row.get("id") or ""), scope_type, scope_target_id)
    scope_business_row = _fetch_business_row(cursor, scope_business_id)
    if not scope_business_row:
        return business_row
    return scope_business_row


def load_plan_context_for_business(user_id: str, business_id: str, scope_type: str, scope_target_id: str | None = None) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        business_row = _fetch_business_row(cursor, business_id)
        if not business_row:
            raise ValueError("Бизнес не найден")
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            superadmin_row = cursor.fetchone()
            if not bool(_row_get(superadmin_row, "coalesce", 0, False)):
                raise PermissionError("Нет доступа к бизнесу")

        subscription = get_subscription_access(business_id)
        allowed_horizons = get_allowed_content_plan_horizons(business_id)
        scope_options = _fetch_network_scope_options(cursor, business_row)
        normalized_scope = _normalize_scope_type(scope_type)
        target_id = str(scope_target_id or "").strip()
        if not target_id:
            current_scope_option = next((item for item in scope_options if item.get("is_current")), None)
            if current_scope_option:
                normalized_scope = str(current_scope_option.get("scope_type") or normalized_scope)
                target_id = str(current_scope_option.get("scope_target_id") or business_id)
            else:
                target_id = business_id
        selected_scope_option = next(
            (
                item
                for item in scope_options
                if str(item.get("scope_type") or "") == normalized_scope
                and str(item.get("scope_target_id") or "") == target_id
            ),
            None,
        )
        scope_business_row = _build_scope_business_context(cursor, business_row, normalized_scope, target_id)
        scope_business_id = str(scope_business_row.get("id") or business_id)
        map_links_count = _fetch_map_link_count(cursor, scope_business_id)
        services = _fetch_services(cursor, scope_business_id)
        seo_keywords = _fetch_seo_keywords_isolated(user_id, scope_business_id)
        sales_signals = _fetch_sales_signals(cursor, user_id, scope_business_id)
        recent_news = _fetch_recent_news(cursor, user_id, scope_business_id)
        audit_signals = _fetch_audit_signals(scope_business_id)
        readiness = _build_planning_readiness(
            map_links_count=map_links_count,
            services_count=len(services),
            seo_keywords_count=len(seo_keywords),
            sales_signals_count=len(sales_signals),
            audit_signals_count=len(audit_signals),
        )

        return {
            "business": {
                "id": str(scope_business_row.get("id") or ""),
                "name": str(scope_business_row.get("name") or "").strip(),
                "city": str(scope_business_row.get("city") or "").strip(),
                "address": str(scope_business_row.get("address") or "").strip(),
                "business_type": str(scope_business_row.get("business_type") or "").strip(),
                "categories": str(scope_business_row.get("categories") or "").strip(),
            },
            "root_business": {
                "id": str(business_row.get("id") or ""),
                "name": str(business_row.get("name") or "").strip(),
                "network_id": str(business_row.get("network_id") or "").strip(),
            },
            "scope": {
                "scope_type": normalized_scope,
                "scope_target_id": target_id,
                "scope_options": scope_options,
                "selected_scope_label": str(selected_scope_option.get("label") or "").strip() if selected_scope_option else str(scope_business_row.get("name") or "").strip(),
                "selected_scope_description": _scope_description(
                    normalized_scope,
                    str(selected_scope_option.get("label") or scope_business_row.get("name") or "").strip(),
                    str(selected_scope_option.get("city") or scope_business_row.get("city") or "").strip(),
                    str(selected_scope_option.get("address") or scope_business_row.get("address") or "").strip(),
                ),
                "network": {
                    "is_network": len(scope_options) > 1,
                    "locations_count": len([item for item in scope_options if str(item.get("scope_type") or "") == "network_location"]),
                    "has_parent_scope": any(str(item.get("scope_type") or "") == "network_parent" for item in scope_options),
                },
            },
            "subscription": {
                "tier": subscription.get("tier"),
                "status": subscription.get("status"),
                "allowed_horizons": allowed_horizons,
                "automation_access": bool(subscription.get("automation_access")),
                "reason": subscription.get("reason"),
            },
            "services": services,
            "seo_keywords": seo_keywords,
            "sales_signals": sales_signals,
            "recent_news": recent_news,
            "audit_signals": audit_signals,
            "readiness": readiness,
        }
    finally:
        db.close()


def list_content_plans(user_id: str, business_id: str) -> list[dict[str, Any]]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        owner_id = get_business_owner_id(cursor, business_id)
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к бизнесу")
        cursor.execute(
            """
            SELECT id, title, scope_type, scope_target_id, period_days, period_start, period_end,
                   plan_status, generation_mode, created_at, updated_at
            FROM contentplans
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        rows = cursor.fetchall() or []
        plans = []
        for row in rows:
            plan_business_id = str(business_id or "").strip()
            scope_type = str(_row_get(row, "scope_type", 2, "") or "").strip()
            scope_target_id = str(_row_get(row, "scope_target_id", 3, "") or "").strip()
            target_meta = _resolve_scope_target_meta(cursor, plan_business_id, scope_type, scope_target_id)
            plans.append(
                {
                    "id": str(_row_get(row, "id", 0, "") or "").strip(),
                    "title": str(_row_get(row, "title", 1, "") or "").strip(),
                    "scope_type": scope_type,
                    "scope_target_id": scope_target_id,
                    "scope_target_label": str(target_meta.get("scope_target_label") or "").strip(),
                    "scope_target_city": str(target_meta.get("scope_target_city") or "").strip(),
                    "scope_target_address": str(target_meta.get("scope_target_address") or "").strip(),
                    "period_days": int(_row_get(row, "period_days", 4, 30) or 30),
                    "period_start": _row_get(row, "period_start", 5),
                    "period_end": _row_get(row, "period_end", 6),
                    "plan_status": str(_row_get(row, "plan_status", 7, "") or "").strip(),
                    "generation_mode": str(_row_get(row, "generation_mode", 8, "") or "").strip(),
                    "created_at": _row_get(row, "created_at", 9),
                    "updated_at": _row_get(row, "updated_at", 10),
                }
            )
        return plans
    finally:
        db.close()


def create_generated_content_plan(
    user_id: str,
    business_id: str,
    *,
    scope_type: str,
    scope_target_id: str | None,
    period_days: int,
    density: str,
    content_mix: dict[str, Any] | None,
) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        allowed_horizons = get_allowed_content_plan_horizons(business_id)
        normalized_period = int(period_days or 30)
        if normalized_period not in allowed_horizons:
            raise PermissionError("Горизонт планирования недоступен на текущем тарифе")
        context = load_plan_context_for_business(user_id, business_id, scope_type, scope_target_id)
        if not bool(context.get("subscription", {}).get("automation_access")):
            raise PermissionError(context.get("subscription", {}).get("reason") or "Автоматизация недоступна")
        skeleton = build_content_plan_skeleton(
            context,
            period_days=normalized_period,
            density=str(density or "standard"),
            content_mix=content_mix if isinstance(content_mix, dict) else {},
        )
        plan_id = str(uuid.uuid4())
        normalized_scope = _normalize_scope_type(scope_type)
        target_id = str(scope_target_id or "").strip() or str(context.get("scope", {}).get("scope_target_id") or business_id)
        root_business = context.get("root_business") if isinstance(context.get("root_business"), dict) else {}
        scope_business = context.get("business") if isinstance(context.get("business"), dict) else {}
        network_location_targets = _network_location_targets_from_context(context)
        context_json = _json_ready(context)
        skeleton_json = _json_ready(skeleton)
        title = str(skeleton.get("title") or "").strip() or f"Контент-план на {normalized_period} дней"
        period_start = str(skeleton.get("period_start") or date.today().isoformat())
        period_end = str(skeleton.get("period_end") or date.today().isoformat())
        cursor.execute(
            """
            INSERT INTO contentplans (
                id, business_id, network_id, scope_type, scope_target_id, title,
                period_days, period_start, period_end, plan_status, generation_mode,
                input_snapshot_json, generated_plan_json, published_plan_json, created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'generated', 'manual', %s::jsonb, %s::jsonb, %s::jsonb, %s)
            """,
            (
                plan_id,
                business_id,
                str(root_business.get("network_id") or "").strip() or None,
                normalized_scope,
                target_id or None,
                title,
                normalized_period,
                period_start,
                period_end,
                json.dumps(context_json, ensure_ascii=False),
                json.dumps(skeleton_json, ensure_ascii=False),
                json.dumps(skeleton_json, ensure_ascii=False),
                user_id,
            ),
        )

        items = skeleton.get("items") if isinstance(skeleton.get("items"), list) else []
        for idx, item in enumerate(items):
            item_id = str(uuid.uuid4())
            item_business_id = str(scope_business.get("id") or business_id)
            item_location_scope = target_id
            if normalized_scope == "network_parent" and network_location_targets:
                assigned_target = network_location_targets[idx % len(network_location_targets)]
                item_business_id = str(assigned_target.get("business_id") or item_business_id)
                item_location_scope = item_business_id
            cursor.execute(
                """
                INSERT INTO contentplanitems (
                    id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                    source_kind, source_ref, seo_keyword, service_id, transaction_id,
                    location_scope, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'planned')
                """,
                (
                    item_id,
                    plan_id,
                    item_business_id,
                    item.get("scheduled_for"),
                    item.get("content_type") or "news",
                    item.get("theme") or "Тема публикации",
                    item.get("goal") or "",
                    item.get("source_kind") or "",
                    item.get("source_ref") or "",
                    item.get("seo_keyword") or None,
                    item.get("service_id") or None,
                    item.get("transaction_id") or None,
                    item_location_scope,
                ),
            )
        db.conn.commit()
        return get_content_plan(user_id, plan_id)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def get_content_plan(user_id: str, plan_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT id, business_id, network_id, scope_type, scope_target_id, title,
                   period_days, period_start, period_end, plan_status, generation_mode,
                   input_snapshot_json, generated_plan_json, edited_plan_json, published_plan_json,
                   created_by, created_at, updated_at
            FROM contentplans
            WHERE id = %s
            LIMIT 1
            """,
            (plan_id,),
        )
        plan_row = cursor.fetchone()
        if not plan_row:
            raise ValueError("Контент-план не найден")
        plan = _row_to_dict(cursor, plan_row)
        owner_id = get_business_owner_id(cursor, str(plan.get("business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к плану")

        cursor.execute(
            """
            SELECT id, business_id, scheduled_for, content_type, theme, goal, source_kind, source_ref,
                   seo_keyword, service_id, transaction_id, location_scope, draft_text, status, usernews_id,
                   created_at, updated_at
            FROM contentplanitems
            WHERE plan_id = %s
            ORDER BY scheduled_for ASC, created_at ASC
            """,
            (plan_id,),
        )
        item_rows = cursor.fetchall() or []
        items = []
        for row in item_rows:
            item_business_id = str(_row_get(row, "business_id", 1, "") or "").strip()
            item_location_scope = str(_row_get(row, "location_scope", 11, "") or "").strip()
            location_meta = _resolve_scope_target_meta(
                cursor,
                item_business_id or str(plan.get("business_id") or ""),
                "network_location" if item_location_scope else str(plan.get("scope_type") or ""),
                item_location_scope or item_business_id,
            )
            items.append(
                {
                    "id": str(_row_get(row, "id", 0, "") or "").strip(),
                    "business_id": item_business_id,
                    "scheduled_for": _row_get(row, "scheduled_for", 2),
                    "content_type": str(_row_get(row, "content_type", 3, "") or "").strip(),
                    "theme": str(_row_get(row, "theme", 4, "") or "").strip(),
                    "goal": str(_row_get(row, "goal", 5, "") or "").strip(),
                    "source_kind": str(_row_get(row, "source_kind", 6, "") or "").strip(),
                    "source_ref": str(_row_get(row, "source_ref", 7, "") or "").strip(),
                    "seo_keyword": str(_row_get(row, "seo_keyword", 8, "") or "").strip(),
                    "service_id": str(_row_get(row, "service_id", 9, "") or "").strip(),
                    "transaction_id": str(_row_get(row, "transaction_id", 10, "") or "").strip(),
                    "location_scope": item_location_scope,
                    "location_label": str(location_meta.get("scope_target_label") or "").strip(),
                    "location_city": str(location_meta.get("scope_target_city") or "").strip(),
                    "location_address": str(location_meta.get("scope_target_address") or "").strip(),
                    "draft_text": str(_row_get(row, "draft_text", 12, "") or "").strip(),
                    "status": str(_row_get(row, "status", 13, "") or "").strip(),
                    "usernews_id": str(_row_get(row, "usernews_id", 14, "") or "").strip(),
                    "created_at": _row_get(row, "created_at", 15),
                    "updated_at": _row_get(row, "updated_at", 16),
                }
            )
        target_meta = _resolve_scope_target_meta(
            cursor,
            str(plan.get("business_id") or ""),
            str(plan.get("scope_type") or ""),
            str(plan.get("scope_target_id") or ""),
        )
        return {
            "id": str(plan.get("id") or ""),
            "business_id": str(plan.get("business_id") or ""),
            "network_id": str(plan.get("network_id") or ""),
            "scope_type": str(plan.get("scope_type") or ""),
            "scope_target_id": str(plan.get("scope_target_id") or ""),
            "scope_target_label": str(target_meta.get("scope_target_label") or "").strip(),
            "scope_target_city": str(target_meta.get("scope_target_city") or "").strip(),
            "scope_target_address": str(target_meta.get("scope_target_address") or "").strip(),
            "title": str(plan.get("title") or ""),
            "period_days": int(plan.get("period_days") or 30),
            "period_start": plan.get("period_start"),
            "period_end": plan.get("period_end"),
            "plan_status": str(plan.get("plan_status") or ""),
            "generation_mode": str(plan.get("generation_mode") or ""),
            "input_snapshot_json": plan.get("input_snapshot_json") if isinstance(plan.get("input_snapshot_json"), dict) else {},
            "generated_plan_json": plan.get("generated_plan_json") if isinstance(plan.get("generated_plan_json"), dict) else {},
            "edited_plan_json": plan.get("edited_plan_json") if isinstance(plan.get("edited_plan_json"), dict) else {},
            "published_plan_json": plan.get("published_plan_json") if isinstance(plan.get("published_plan_json"), dict) else {},
            "items": items,
            "created_at": plan.get("created_at"),
            "updated_at": plan.get("updated_at"),
        }
    finally:
        db.close()


def update_content_plan_item(user_id: str, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.status, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        data = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(data.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")

        updates = []
        params: list[Any] = []
        for field in ("scheduled_for", "theme", "goal", "content_type", "seo_keyword", "draft_text"):
            if field in payload:
                updates.append(f"{field} = %s")
                params.append(payload.get(field))
        if "status" in payload:
            next_status = str(payload.get("status") or "").strip()
            if next_status in {"planned", "draft_generated", "edited", "approved", "published", "skipped"}:
                updates.append("status = %s")
                params.append(next_status)
        if "draft_text" in payload:
            updates.append("status = %s")
            params.append("edited")
        if not updates:
            return get_content_plan(user_id, str(data.get("plan_id") or ""))
        updates.append("updated_at = CURRENT_TIMESTAMP")
        params.extend([item_id])
        cursor.execute(
            f"""
            UPDATE contentplanitems
            SET {', '.join(updates)}
            WHERE id = %s
            """,
            tuple(params),
        )
        db.conn.commit()
        return get_content_plan(user_id, str(data.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def duplicate_content_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.scheduled_for, i.content_type, i.theme, i.goal,
                   i.source_kind, i.source_ref, i.seo_keyword, i.service_id, i.transaction_id,
                   i.location_scope, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")

        scheduled_for = item.get("scheduled_for")
        next_scheduled_for: Any = scheduled_for
        if isinstance(scheduled_for, datetime):
            next_scheduled_for = (scheduled_for.date() + timedelta(days=7)).isoformat()
        elif isinstance(scheduled_for, date):
            next_scheduled_for = (scheduled_for + timedelta(days=7)).isoformat()
        else:
            raw_date = str(scheduled_for or "").strip()
            if raw_date:
                try:
                    next_scheduled_for = (date.fromisoformat(raw_date) + timedelta(days=7)).isoformat()
                except Exception:
                    next_scheduled_for = raw_date

        duplicated_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO contentplanitems (
                id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                source_kind, source_ref, seo_keyword, service_id, transaction_id,
                location_scope, draft_text, status, usernews_id, created_at, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            """,
            (
                duplicated_id,
                str(item.get("plan_id") or ""),
                str(item.get("business_id") or ""),
                next_scheduled_for,
                str(item.get("content_type") or "").strip(),
                str(item.get("theme") or "").strip(),
                str(item.get("goal") or "").strip(),
                str(item.get("source_kind") or "").strip(),
                str(item.get("source_ref") or "").strip(),
                str(item.get("seo_keyword") or "").strip(),
                str(item.get("service_id") or "").strip() or None,
                str(item.get("transaction_id") or "").strip() or None,
                str(item.get("location_scope") or "").strip() or None,
                "",
                "planned",
                None,
            ),
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _fallback_draft_text(business_name: str, item: dict[str, Any]) -> str:
    theme = str(item.get("theme") or "Новость компании").strip()
    source_ref = str(item.get("source_ref") or "").strip()
    keyword = str(item.get("seo_keyword") or "").strip()
    goal = str(item.get("goal") or "").strip()
    lines = [f"{business_name}: {theme}."]
    if source_ref:
        lines.append(f"В фокусе сейчас: {source_ref}.")
    if keyword:
        lines.append(f"Это также помогает закрыть спрос по запросу: {keyword}.")
    if goal:
        lines.append(goal)
    lines.append("Подробности, запись или актуальные предложения можно уточнить по контактам в карточке.")
    return " ".join(lines)


def generate_draft_for_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.theme, i.goal, i.content_type, i.source_kind, i.source_ref,
                   i.seo_keyword, i.service_id, i.transaction_id, i.location_scope,
                   p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")
        cursor.execute("SELECT name FROM businesses WHERE id = %s", (item.get("business_id"),))
        business_name = str(_row_get(cursor.fetchone(), "name", 0, "Бизнес") or "Бизнес").strip() or "Бизнес"
        prompt = (
            "Ты — маркетолог локального бизнеса. Напиши короткую новость для публикации на картах. "
            "До 900 символов, без хештегов, без выдуманных фактов, с понятным CTA.\n\n"
            f"Бизнес: {business_name}\n"
            f"Тема: {str(item.get('theme') or '').strip()}\n"
            f"Цель: {str(item.get('goal') or '').strip()}\n"
            f"Источник идеи: {str(item.get('source_kind') or '').strip()} / {str(item.get('source_ref') or '').strip()}\n"
            f"SEO-запрос: {str(item.get('seo_keyword') or '').strip()}\n\n"
            'Верни только JSON вида {"news":"..."}'
        )
        try:
            result = analyze_text_with_gigachat(
                prompt,
                task_type="news_generation",
                business_id=str(item.get("business_id") or ""),
                user_id=user_id,
            )
            generated_text = str(result or "").strip()
            if generated_text.startswith("{"):
                try:
                    generated_payload = json.loads(generated_text)
                    generated_text = str(generated_payload.get("news") or generated_payload.get("text") or "").strip()
                except Exception:
                    pass
            if not generated_text:
                generated_text = _fallback_draft_text(business_name, item)
        except Exception:
            generated_text = _fallback_draft_text(business_name, item)
        cursor.execute(
            """
            UPDATE contentplanitems
            SET draft_text = %s,
                status = 'draft_generated',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (generated_text, item_id),
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def create_news_from_plan_item(user_id: str, item_id: str) -> dict[str, Any]:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        ensure_content_plan_tables(cursor)
        _ensure_usernews_table(cursor)
        cursor.execute(
            """
            SELECT i.id, i.plan_id, i.business_id, i.theme, i.goal, i.source_ref, i.draft_text, i.service_id, p.business_id AS root_business_id
            FROM contentplanitems i
            JOIN contentplans p ON p.id = i.plan_id
            WHERE i.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError("Элемент плана не найден")
        item = _row_to_dict(cursor, row)
        owner_id = get_business_owner_id(cursor, str(item.get("root_business_id") or ""))
        if str(owner_id or "").strip() != str(user_id or "").strip():
            cursor.execute("SELECT COALESCE(is_superadmin, FALSE) FROM users WHERE id = %s", (user_id,))
            if not bool(_row_get(cursor.fetchone(), "coalesce", 0, False)):
                raise PermissionError("Нет доступа к элементу плана")
        generated_text = str(item.get("draft_text") or "").strip()
        if not generated_text:
            generated_text = _fallback_draft_text("Бизнес", item)
        news_id = str(uuid.uuid4())
        source_text = "\n".join(
            part
            for part in [
                str(item.get("theme") or "").strip(),
                str(item.get("goal") or "").strip(),
                str(item.get("source_ref") or "").strip(),
            ]
            if part
        )
        cursor.execute(
            """
            INSERT INTO usernews (
                id, user_id, business_id, service_id, source_text, generated_text,
                original_generated_text, edited_before_approve, prompt_key, prompt_version, approved, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, 'content_plan', 'v1', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                news_id,
                user_id,
                str(item.get("business_id") or ""),
                str(item.get("service_id") or "").strip() or None,
                source_text,
                generated_text,
                generated_text,
            ),
        )
        cursor.execute(
            """
            UPDATE contentplanitems
            SET usernews_id = %s,
                status = 'draft_generated',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (news_id, item_id),
        )
        db.conn.commit()
        return get_content_plan(user_id, str(item.get("plan_id") or ""))
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
