from __future__ import annotations

from typing import Any


ITEM_SPECS = {
    "review": ("reviews", "externalbusinessreviews", "business_id"),
    "review_draft": ("reviews", "reviewreplydrafts", "business_id"),
    "content_plan": ("content", "contentplans", "business_id"),
    "content_item": ("content", "contentplanitems", "business_id"),
    "post": ("content", "social_posts", "business_id"),
    "service": ("services", "userservices", "business_id"),
    "sale": ("finance", "financialtransactions", "business_id"),
    "finance_import": ("finance", "finance_import_batches", "business_id"),
    "partner": ("partnerships", "prospectingleads", "business_id"),
    "agent": ("agents", "agent_blueprints", "business_id"),
    "agent_run": ("agents", "agent_runs", "business_id"),
    "agent_result": ("agents", "agent_runs", "business_id"),
    "operator_message": ("operator", "operatormessages", "business_id"),
    "operator_result": ("operator", "operatoractions", "business_id"),
    "approval": ("tasks", "operatoractions", "business_id"),
    "task": ("tasks", "operatoractions", "business_id"),
    "job": ("tasks", "operator_async_jobs", "business_id"),
    "parse_job": ("cards", "parsequeue", "business_id"),
    "integration_error": ("cards", "parsequeue", "business_id"),
    "diagnostic_job": ("diagnostics", "parsequeue", "business_id"),
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


def _screen_manifest(navigation: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("key") or ""): item
        for item in navigation
        if str(item.get("key") or "") and item.get("status") != "hidden"
    }


def _business_allowed(scope: dict[str, Any], business_id: str) -> bool:
    if scope.get("kind") == "platform":
        return True
    return business_id in {str(item) for item in scope.get("business_ids") or []}


def _company_allowed(cursor: Any, scope: dict[str, Any], company_id: str) -> bool:
    if scope.get("kind") == "platform":
        cursor.execute("SELECT id FROM companies WHERE id = %s AND status <> 'merged' LIMIT 1", (company_id,))
        return bool(cursor.fetchone())
    business_ids = [str(item) for item in scope.get("business_ids") or []]
    if not business_ids:
        return False
    cursor.execute(
        """
        SELECT company.id
        FROM companies company
        WHERE company.id = %s
          AND company.status <> 'merged'
          AND (
            EXISTS (
              SELECT 1 FROM business_company_links link
              WHERE link.company_id = company.id AND link.business_id = ANY(%s)
            )
            OR EXISTS (
              SELECT 1 FROM prospectingleads lead
              JOIN lead_workstreams workstream ON workstream.lead_id = lead.id
              WHERE lead.company_id = company.id AND workstream.client_business_id = ANY(%s)
            )
            OR EXISTS (
              SELECT 1 FROM company_relationships relationship
              WHERE (relationship.subject_company_id = company.id OR relationship.object_company_id = company.id)
                AND relationship.context_business_id = ANY(%s)
            )
          )
        LIMIT 1
        """,
        (company_id, business_ids, business_ids, business_ids),
    )
    return bool(cursor.fetchone())


def _source_allowed(cursor: Any, scope: dict[str, Any], source_id: str) -> bool:
    if scope.get("kind") == "platform":
        cursor.execute("SELECT id FROM knowledge_sources WHERE id = %s LIMIT 1", (source_id,))
        return bool(cursor.fetchone())
    business_ids = [str(item) for item in scope.get("business_ids") or []]
    cursor.execute(
        """
        SELECT source.id
        FROM knowledge_sources source
        JOIN knowledge_source_subscriptions subscription ON subscription.source_id = source.id
        WHERE source.id = %s AND subscription.business_id = ANY(%s) AND subscription.is_active = TRUE
        LIMIT 1
        """,
        (source_id, business_ids),
    )
    return bool(cursor.fetchone())


def _outreach_object_business(cursor: Any, item_type: str, item_id: str) -> dict[str, Any]:
    if item_type == "outreach_touch":
        cursor.execute(
            """
            SELECT touch.id, campaign.business_id
            FROM outreach_campaign_touches touch
            JOIN outreach_campaigns campaign ON campaign.id = touch.campaign_id
            WHERE touch.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        return _row(cursor, cursor.fetchone())
    if item_type == "partnership_reply":
        cursor.execute(
            """
            SELECT inbound.id, campaign.business_id
            FROM outreach_inbound_events inbound
            JOIN outreach_campaigns campaign ON campaign.id = inbound.campaign_id
            WHERE inbound.id = %s
            LIMIT 1
            """,
            (item_id,),
        )
        return _row(cursor, cursor.fetchone())
    return {}


def resolve_mobile_deep_link(
    cursor: Any,
    *,
    scope: dict[str, Any],
    navigation: list[dict[str, Any]],
    screen: str,
    item_type: str,
    item_id: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = _screen_manifest(navigation)
    requested_screen = str(screen or "today").strip().lower()
    if requested_screen == "analytics":
        requested_screen = "finance"
    resolved_screen = requested_screen if requested_screen in manifest else "today"
    fallback_reason = "screen_unavailable" if resolved_screen != requested_screen else ""
    clean_type = str(item_type or "").strip().lower()
    clean_id = str(item_id or "").strip()
    if not clean_type or not clean_id:
        return {
            "screen": resolved_screen,
            "item_type": None,
            "item_id": None,
            "filters": filters or {},
            "fallback_applied": bool(fallback_reason),
            "fallback_reason": fallback_reason or None,
        }

    if clean_type == "company":
        company_screen = "companies" if scope.get("kind") == "platform" else "company"
        if company_screen in manifest and _company_allowed(cursor, scope, clean_id):
            return {"screen": company_screen, "item_type": clean_type, "item_id": clean_id, "filters": filters or {}, "fallback_applied": False, "fallback_reason": None}
        return {"screen": "today", "item_type": None, "item_id": None, "filters": {}, "fallback_applied": True, "fallback_reason": "object_forbidden"}

    if clean_type in {"community_source", "knowledge_source"}:
        if _source_allowed(cursor, scope, clean_id):
            return {"screen": "community_sources", "item_type": "community_source", "item_id": clean_id, "filters": filters or {}, "fallback_applied": False, "fallback_reason": None}
        return {"screen": "today", "item_type": None, "item_id": None, "filters": {}, "fallback_applied": True, "fallback_reason": "object_forbidden"}

    if clean_type in {"outreach_touch", "partnership_reply"}:
        item = _outreach_object_business(cursor, clean_type, clean_id)
        business_id = str(item.get("business_id") or "")
        if "partnerships" in manifest and item and _business_allowed(scope, business_id):
            return {"screen": "partnerships", "item_type": clean_type, "item_id": clean_id, "filters": filters or {}, "fallback_applied": False, "fallback_reason": None}
        return {"screen": "today", "item_type": None, "item_id": None, "filters": {}, "fallback_applied": True, "fallback_reason": "object_forbidden"}

    spec = ITEM_SPECS.get(clean_type)
    if not spec:
        return {"screen": resolved_screen, "item_type": None, "item_id": None, "filters": filters or {}, "fallback_applied": True, "fallback_reason": "item_type_unsupported"}
    target_screen, table_name, business_column = spec
    if target_screen not in manifest:
        return {"screen": "today", "item_type": None, "item_id": None, "filters": {}, "fallback_applied": True, "fallback_reason": "screen_unavailable"}
    cursor.execute(
        f"SELECT id, {business_column} AS business_id FROM {table_name} WHERE id = %s LIMIT 1",
        (clean_id,),
    )
    item = _row(cursor, cursor.fetchone())
    business_id = str(item.get("business_id") or "")
    if not item or not _business_allowed(scope, business_id):
        return {"screen": "today", "item_type": None, "item_id": None, "filters": {}, "fallback_applied": True, "fallback_reason": "object_forbidden"}
    return {
        "screen": target_screen,
        "item_type": clean_type,
        "item_id": clean_id,
        "filters": filters or {},
        "fallback_applied": False,
        "fallback_reason": None,
    }
