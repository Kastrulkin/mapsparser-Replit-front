from __future__ import annotations

import json
from typing import Any

from psycopg2.extras import Json


SCOPE_TYPES = {"platform", "network", "business"}


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(row, (tuple, list)):
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return {}


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, type(fallback)):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, type(fallback)) else fallback
        except Exception:
            return fallback
    return fallback


def _active_business_clause(alias: str = "b") -> str:
    return f"COALESCE({alias}.is_active, TRUE) = TRUE"


def _load_actor(cursor: Any, user_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, email, name, telegram_id, COALESCE(is_superadmin, FALSE) AS is_superadmin
        FROM users
        WHERE id = %s
        LIMIT 1
        """,
        (user_id,),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_networks(cursor: Any, user_id: str, is_superadmin: bool) -> list[dict[str, Any]]:
    owner_filter = "" if is_superadmin else "WHERE n.owner_id = %s"
    params: tuple[Any, ...] = () if is_superadmin else (user_id,)
    cursor.execute(
        f"""
        SELECT
            n.id,
            n.name,
            n.owner_id,
            COUNT(b.id) FILTER (WHERE b.id <> n.id AND {_active_business_clause('b')}) AS locations_count
        FROM networks n
        LEFT JOIN businesses b ON b.network_id = n.id
        {owner_filter}
        GROUP BY n.id, n.name, n.owner_id
        ORDER BY n.name
        """,
        params,
    )
    return [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]


def _load_businesses(
    cursor: Any,
    user_id: str,
    is_superadmin: bool,
    *,
    query: str = "",
    limit: int = 100,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    access_filter = "TRUE"
    if not is_superadmin:
        access_filter = "(b.owner_id = %s OR n.owner_id = %s)"
        params.extend([user_id, user_id])
    search_filter = ""
    cleaned_query = str(query or "").strip()
    if cleaned_query:
        search_filter = "AND (b.name ILIKE %s OR COALESCE(b.address, '') ILIKE %s)"
        pattern = f"%{cleaned_query}%"
        params.extend([pattern, pattern])
    params.append(max(1, min(int(limit or 100), 200)))
    cursor.execute(
        f"""
        SELECT DISTINCT
            b.id,
            b.name,
            COALESCE(b.address, '') AS address,
            b.network_id,
            n.name AS network_name,
            b.owner_id
        FROM businesses b
        LEFT JOIN networks n ON n.id = b.network_id
        WHERE {_active_business_clause('b')}
          AND {access_filter}
          AND NOT (b.network_id IS NOT NULL AND b.id = b.network_id)
          {search_filter}
        ORDER BY b.name, b.address
        LIMIT %s
        """,
        tuple(params),
    )
    return [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]


def _network_business_ids(cursor: Any, network_id: str) -> list[str]:
    cursor.execute(
        f"""
        SELECT id
        FROM businesses
        WHERE network_id = %s
          AND {_active_business_clause('businesses')}
          AND id <> %s
        ORDER BY name
        """,
        (network_id, network_id),
    )
    ids = [str(_row_to_dict(cursor, row).get("id") or "") for row in (cursor.fetchall() or [])]
    ids = [item for item in ids if item]
    if ids:
        return ids
    cursor.execute(
        f"SELECT id FROM businesses WHERE id = %s AND {_active_business_clause('businesses')} LIMIT 1",
        (network_id,),
    )
    parent = _row_to_dict(cursor, cursor.fetchone())
    return [str(parent.get("id"))] if parent.get("id") else []


def _scope_payload(
    *,
    kind: str,
    scope_id: str | None,
    name: str,
    business_ids: list[str],
    can_switch: bool,
    parent_scope: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": scope_id,
        "name": name,
        "business_ids": business_ids,
        "can_switch": bool(can_switch),
        "parent_scope": parent_scope,
    }


def list_control_scopes(
    cursor: Any,
    *,
    user_id: str,
    search_query: str = "",
    business_limit: int = 100,
) -> dict[str, Any]:
    actor = _load_actor(cursor, user_id)
    if not actor:
        return {"actor": {}, "platform": None, "networks": [], "businesses": [], "total_choices": 0}
    is_superadmin = bool(actor.get("is_superadmin"))
    networks = _load_networks(cursor, user_id, is_superadmin)
    businesses = _load_businesses(
        cursor,
        user_id,
        is_superadmin,
        query=search_query,
        limit=business_limit,
    )
    platform = None
    if is_superadmin:
        cursor.execute(f"SELECT COUNT(*) AS cnt FROM businesses b WHERE {_active_business_clause('b')}")
        total_businesses = int(_row_to_dict(cursor, cursor.fetchone()).get("cnt") or 0)
        platform = _scope_payload(
            kind="platform",
            scope_id=None,
            name="Вся платформа",
            business_ids=[],
            can_switch=True,
        )
        platform["businesses_count"] = total_businesses
    total_choices = len(businesses) + len(networks) + (1 if platform else 0)
    return {
        "actor": {
            "id": str(actor.get("id") or ""),
            "name": str(actor.get("name") or ""),
            "is_superadmin": is_superadmin,
        },
        "platform": platform,
        "networks": [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "Сеть"),
                "locations_count": int(item.get("locations_count") or 0),
            }
            for item in networks
        ],
        "businesses": [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or "Бизнес"),
                "address": str(item.get("address") or ""),
                "network_id": str(item.get("network_id") or "") or None,
                "network_name": str(item.get("network_name") or "") or None,
            }
            for item in businesses
        ],
        "total_choices": total_choices,
    }


def _load_preference(cursor: Any, user_id: str) -> dict[str, Any]:
    cursor.execute("SELECT to_regclass('public.telegramcontrolpreferences') AS table_ref")
    if not _row_to_dict(cursor, cursor.fetchone()).get("table_ref"):
        return {}
    cursor.execute("SELECT * FROM telegramcontrolpreferences WHERE user_id = %s LIMIT 1", (user_id,))
    row = _row_to_dict(cursor, cursor.fetchone())
    if not row:
        return {}
    row["recent_scopes_json"] = _json_value(row.get("recent_scopes_json"), [])
    row["favorite_scopes_json"] = _json_value(row.get("favorite_scopes_json"), [])
    row["last_business_by_network_json"] = _json_value(row.get("last_business_by_network_json"), {})
    row["notification_preferences_json"] = _json_value(row.get("notification_preferences_json"), {})
    return row


def _resolve_requested_scope(
    cursor: Any,
    *,
    catalog: dict[str, Any],
    kind: str,
    scope_id: str | None,
) -> dict[str, Any] | None:
    can_switch = int(catalog.get("total_choices") or 0) > 1
    if kind == "platform":
        platform = catalog.get("platform")
        if not isinstance(platform, dict):
            return None
        return {**platform, "can_switch": can_switch}
    if kind == "network":
        network = next(
            (item for item in catalog.get("networks") or [] if str(item.get("id") or "") == str(scope_id or "")),
            None,
        )
        if not network:
            return None
        business_ids = _network_business_ids(cursor, str(network["id"]))
        return _scope_payload(
            kind="network",
            scope_id=str(network["id"]),
            name=str(network.get("name") or "Сеть"),
            business_ids=business_ids,
            can_switch=can_switch,
        )
    if kind == "business":
        business = next(
            (item for item in catalog.get("businesses") or [] if str(item.get("id") or "") == str(scope_id or "")),
            None,
        )
        if not business and scope_id:
            actor = catalog.get("actor") if isinstance(catalog.get("actor"), dict) else {}
            user_id = str(actor.get("id") or "")
            is_superadmin = bool(actor.get("is_superadmin"))
            access_filter = "TRUE" if is_superadmin else "(b.owner_id = %s OR n.owner_id = %s)"
            params: list[Any] = [scope_id]
            if not is_superadmin:
                params.extend([user_id, user_id])
            cursor.execute(
                f"""
                SELECT b.id, b.name, COALESCE(b.address, '') AS address,
                       b.network_id, n.name AS network_name
                FROM businesses b
                LEFT JOIN networks n ON n.id = b.network_id
                WHERE b.id = %s
                  AND {_active_business_clause('b')}
                  AND {access_filter}
                LIMIT 1
                """,
                tuple(params),
            )
            loaded = _row_to_dict(cursor, cursor.fetchone())
            business = loaded or None
        if not business:
            return None
        parent_scope = None
        if business.get("network_id"):
            parent_scope = {
                "kind": "network",
                "id": business.get("network_id"),
                "name": business.get("network_name") or "Сеть",
            }
        return _scope_payload(
            kind="business",
            scope_id=str(business["id"]),
            name=str(business.get("name") or "Бизнес"),
            business_ids=[str(business["id"])],
            can_switch=can_switch,
            parent_scope=parent_scope,
        )
    return None


def resolve_control_scope(
    cursor: Any,
    *,
    user_id: str,
    requested_kind: str = "",
    requested_id: str | None = None,
    persist: bool = False,
    telegram_id: str = "",
) -> dict[str, Any] | None:
    catalog = list_control_scopes(cursor, user_id=user_id, business_limit=200)
    kind = str(requested_kind or "").strip().lower()
    if kind in SCOPE_TYPES:
        selected = _resolve_requested_scope(cursor, catalog=catalog, kind=kind, scope_id=requested_id)
        if not selected:
            return None
        if persist and telegram_id:
            save_control_scope(cursor, user_id=user_id, telegram_id=telegram_id, scope=selected)
        return selected

    preference = _load_preference(cursor, user_id)
    preferred_kind = str(preference.get("scope_type") or "").strip().lower()
    preferred_id = str(preference.get("scope_id") or "").strip() or None
    if preferred_kind in SCOPE_TYPES:
        selected = _resolve_requested_scope(
            cursor,
            catalog=catalog,
            kind=preferred_kind,
            scope_id=preferred_id,
        )
        if selected:
            return selected

    if catalog.get("platform"):
        return _resolve_requested_scope(cursor, catalog=catalog, kind="platform", scope_id=None)
    networks = catalog.get("networks") or []
    if networks:
        return _resolve_requested_scope(cursor, catalog=catalog, kind="network", scope_id=str(networks[0]["id"]))
    businesses = catalog.get("businesses") or []
    if businesses:
        return _resolve_requested_scope(cursor, catalog=catalog, kind="business", scope_id=str(businesses[0]["id"]))
    return None


def save_control_scope(
    cursor: Any,
    *,
    user_id: str,
    telegram_id: str,
    scope: dict[str, Any],
) -> dict[str, Any]:
    kind = str(scope.get("kind") or "").strip().lower()
    scope_id = str(scope.get("id") or "").strip() or None
    if kind not in SCOPE_TYPES:
        raise ValueError("unsupported_control_scope")
    current = _load_preference(cursor, user_id)
    recent = list(current.get("recent_scopes_json") or [])
    item = {"kind": kind, "id": scope_id, "name": str(scope.get("name") or "")}
    recent = [value for value in recent if not (value.get("kind") == kind and value.get("id") == scope_id)]
    recent.insert(0, item)
    recent = recent[:8]
    last_by_network = dict(current.get("last_business_by_network_json") or {})
    parent = scope.get("parent_scope") if isinstance(scope.get("parent_scope"), dict) else {}
    if kind == "business" and parent.get("id"):
        last_by_network[str(parent["id"])] = scope_id
    cursor.execute(
        """
        INSERT INTO telegramcontrolpreferences (
            user_id, telegram_id, scope_type, scope_id,
            recent_scopes_json, last_business_by_network_json, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
            telegram_id = EXCLUDED.telegram_id,
            scope_type = EXCLUDED.scope_type,
            scope_id = EXCLUDED.scope_id,
            recent_scopes_json = EXCLUDED.recent_scopes_json,
            last_business_by_network_json = EXCLUDED.last_business_by_network_json,
            updated_at = NOW()
        """,
        (user_id, telegram_id, kind, scope_id, Json(recent), Json(last_by_network)),
    )
    return scope


def load_control_preferences(cursor: Any, user_id: str) -> dict[str, Any]:
    return _load_preference(cursor, user_id)


def toggle_favorite_control_scope(
    cursor: Any,
    *,
    user_id: str,
    telegram_id: str,
    scope: dict[str, Any],
) -> bool:
    save_control_scope(
        cursor,
        user_id=user_id,
        telegram_id=telegram_id,
        scope=scope,
    )
    current = _load_preference(cursor, user_id)
    favorites = [item for item in (current.get("favorite_scopes_json") or []) if isinstance(item, dict)]
    kind = str(scope.get("kind") or "")
    scope_id = str(scope.get("id") or "").strip() or None
    exists = any(item.get("kind") == kind and item.get("id") == scope_id for item in favorites)
    favorites = [item for item in favorites if not (item.get("kind") == kind and item.get("id") == scope_id)]
    if not exists:
        favorites.insert(0, {"kind": kind, "id": scope_id, "name": str(scope.get("name") or "")})
    cursor.execute(
        "UPDATE telegramcontrolpreferences SET favorite_scopes_json = %s, updated_at = NOW() WHERE user_id = %s",
        (Json(favorites[:20]), user_id),
    )
    return not exists
