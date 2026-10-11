"""Adapters for the existing Today builder; no independent home-data endpoint."""
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from services.today_preferences_service import (
    FLOW_CAPABILITIES, FLOWS, enabled, normalize_flow, read_preferences, schema_available,
)
from subscription_manager import build_subscription_capabilities, capability_access_payload


def _row(cursor, value):
    if value is None:
        return {}
    if hasattr(value, "keys"):
        return dict(value)
    return dict(zip([column[0] for column in cursor.description], value))


def _iso(value):
    return value.isoformat() if isinstance(value, (datetime, date)) else value


def allowed_priority_flows(cursor, *, scope, is_superadmin=False):
    if is_superadmin:
        return list(FLOWS)
    ids = scope.get("business_ids") or ([scope["id"]] if scope.get("kind") == "business" else [])
    if not ids:
        return ["overview"]
    cursor.execute("SELECT id,subscription_tier,subscription_status,subscription_ends_at FROM businesses WHERE id=ANY(%s) AND COALESCE(is_active,TRUE)", (ids,))
    rows = [_row(cursor, row) for row in cursor.fetchall()]
    if len(rows) != len(set(ids)):
        return ["overview"]
    allowed = set(FLOWS)
    for row in rows:
        access = build_subscription_capabilities(tier=str(row.get("subscription_tier") or ""), status=str(row.get("subscription_status") or ""), subscription_ends_at=row.get("subscription_ends_at"))
        allowed.intersection_update(["overview"] + [flow for flow, capability in FLOW_CAPABILITIES.items() if capability_access_payload(access, capability).get("allowed")])
    return [flow for flow in FLOWS if flow in allowed]


def work_item(*, entity_type, entity_id, flow, business_id, title, status, url,
              now, updated_at=None, due_at=None, description="", preview=None,
              urgent=False, message_code=None, business_name=None):
    return {
        "id": f"{entity_type}:{entity_id}", "entity_type": entity_type,
        "entity_id": str(entity_id), "flow": flow, "business_id": business_id, "business_name": business_name,
        "title": title, "description": description, "status": status,
        "urgency": "urgent" if urgent else "normal", "due_at": _iso(due_at),
        "requires_decision": entity_type == "journey_action" or (entity_type == "content_item" and status == "approved"),
        "preview": preview, "action": {"label": "Открыть", "label_code": "today.open", "url": url},
        "occurred_at": _iso(updated_at),
        "freshness": {"as_of": _iso(now), "status": "live"},
        "reason_code": status, "message_code": message_code,
        "params": {"status": status},
    }


def content_work(cursor, scope, now):
    cursor.execute("""SELECT i.id,i.plan_id,i.business_id,i.theme,i.status,i.scheduled_for,
        i.updated_at,b.name business_name,LEFT(COALESCE(i.draft_text,''),360) preview
        FROM contentplanitems i JOIN contentplans p ON p.id=i.plan_id JOIN businesses b ON b.id=i.business_id
        WHERE i.business_id=ANY(%s) AND COALESCE(p.plan_status,'')<>'archived'
          AND i.status NOT IN ('archived','skipped')
        ORDER BY CASE WHEN i.status IN ('draft_generated','edited') THEN 0 WHEN i.status='published' THEN 2 ELSE 1 END,
          i.scheduled_for,i.updated_at DESC LIMIT 20""", (scope["business_ids"],))
    result = []
    for row in [_row(cursor, value) for value in cursor.fetchall()]:
        status = row["status"]
        due = row.get("scheduled_for")
        overdue = bool(due and str(due)[:10] < now.date().isoformat() and status == "approved")
        result.append(work_item(entity_type="content_item", entity_id=row["id"], flow="content", business_id=row["business_id"],business_name=row.get("business_name"),
            title=row["theme"], status=status, url="/dashboard/content?" + urlencode({"plan_id": row["plan_id"], "item_id": row["id"], "business_id": row["business_id"]}),
            now=now, updated_at=row.get("updated_at"), due_at=due, preview=row["preview"], urgent=overdue))
    return result


def influencer_work(cursor, scope, now):
    cursor.execute("""SELECT c.id,c.business_id,c.status,c.scheduled_visit_at,c.updated_at,
        cp.title campaign_title,p.display_name,b.name business_name
        FROM creator_collaborations c JOIN creator_campaigns cp ON cp.id=c.campaign_id
        JOIN creator_profiles p ON p.id=c.creator_profile_id JOIN businesses b ON b.id=c.business_id
        WHERE c.business_id=ANY(%s) AND c.status NOT IN ('declined','stopped','no_reply')
        ORDER BY CASE WHEN c.status IN ('replied','negotiating','overdue','disputed') THEN 0 ELSE 1 END,
          c.updated_at DESC LIMIT 20""", (scope["business_ids"],))
    return [work_item(entity_type="creator_collaboration",entity_id=row["id"],flow="influencers",business_id=row["business_id"],business_name=row.get("business_name"),
        title=row["display_name"],description=row["campaign_title"],status=row["status"],
        url="/dashboard/influencers/operations?"+urlencode({"section":"collaborations","collaboration_id":row["id"],"business_id":row["business_id"]}),
        now=now,updated_at=row["updated_at"],due_at=row.get("scheduled_visit_at"),urgent=row["status"] in {"overdue","disputed"})
        for row in [_row(cursor,value) for value in cursor.fetchall()]]


def automation_work(cursor, scope, now):
    cursor.execute("""SELECT r.id,r.blueprint_id,r.business_id,r.status,r.updated_at,b.name,
            sheet.apply_state provider_state,biz.name business_name
        FROM agent_runs r JOIN agent_blueprints b ON b.id=r.blueprint_id JOIN businesses biz ON biz.id=r.business_id
        LEFT JOIN LATERAL (
            SELECT s.apply_state FROM agent_sheet_operation_requests s
            WHERE s.bound_run_id=r.id AND s.business_id=r.business_id
              AND r.status='waiting_provider' AND s.apply_state<>'applied'
            ORDER BY CASE WHEN s.apply_state IN ('provider_reconciliation_required','provider_failed','provider_unavailable','approval_invalid') THEN 0 ELSE 1 END,
                s.updated_at DESC LIMIT 1
        ) sheet ON TRUE
        WHERE r.business_id=ANY(%s) AND r.status NOT IN ('cancelled')
        ORDER BY CASE WHEN r.status IN ('failed','waiting_approval','awaiting_approval')
            OR sheet.apply_state IN ('provider_reconciliation_required','provider_failed','provider_unavailable','approval_invalid') THEN 0 ELSE 1 END,
            r.updated_at DESC LIMIT 20""", (scope["business_ids"],))
    result = []
    descriptions = {
        "waiting_provider": "Запись в таблицу подтверждена и ожидает выполнения.",
        "provider_request_queued": "Запись в таблицу подтверждена и ожидает выполнения.",
        "provider_executing": "Выполняется запись в таблицу.",
        "provider_reconciliation_required": "Результат записи неизвестен. Сверьте таблицу перед следующими действиями.",
        "provider_failed": "Запись требует внимания. Откройте результат, чтобы проверить причину.",
        "provider_unavailable": "Для записи нужен доступ к таблице. Откройте результат, чтобы проверить подключение.",
        "approval_invalid": "Подтверждение записи больше не действует. Откройте результат для проверки.",
    }
    attention = {"failed", "provider_reconciliation_required", "provider_failed", "provider_unavailable", "approval_invalid"}
    for row in [_row(cursor, value) for value in cursor.fetchall()]:
        status = (row.get("provider_state") or row["status"]) if row["status"] == "waiting_provider" else row["status"]
        result.append(work_item(entity_type="agent_run",entity_id=row["id"],flow="automation",business_id=row["business_id"],business_name=row.get("business_name"),
            title=row["name"],status=status,description=descriptions.get(status, ""),
            message_code=f"today.automation.{status}" if status in descriptions else None,
            url="/dashboard/agents?"+urlencode({"blueprint_id":row["blueprint_id"],"run_id":row["id"],"business_id":row["business_id"]}),
            now=now,updated_at=row["updated_at"],urgent=status in attention))
    return result


def section_items(items, primary_flow, *, limit=8, now=None):
    observed_at = now or datetime.now(timezone.utc)
    def deadline(item):
        value = item.get("due_at")
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
        except (ValueError, TypeError):
            return None
    failures = {"failed", "blocked", "disputed", "provider_reconciliation_required", "provider_failed", "provider_unavailable", "approval_invalid"}
    def human(item):
        return item.get("status") in decisions or item.get("requires_decision") is True or item.get("kind") == "owner_action"
    def priority(item):
        due = deadline(item)
        return 0 if human(item) and due and due < observed_at else 1 if human(item) and item.get("status") in failures else 2 if human(item) else 3

    decisions = {"failed","waiting_approval","awaiting_approval","needs_review","replied","negotiating","disputed","overdue","draft_generated","edited","blocked","provider_reconciliation_required","provider_failed","provider_unavailable","approval_invalid"}
    completed = {"completed","published","succeeded"}
    sections = {"needs_decision": [], "continue_work": [], "results": []}
    seen = set()
    for item in items:
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        section = "results" if item.get("status") in completed else "needs_decision" if human(item) else "continue_work"
        sections[section].append(item)
    for name, values in sections.items():
        # Results are actual recent work, not the lexicographically first IDs.
        if name == "results":
            values.sort(key=lambda item: (item.get("occurred_at") or "", item["id"]), reverse=True)
            sections[name] = values[:limit]
            continue
        values.sort(key=lambda item: (
            priority(item),
            item.get("urgency") != "urgent",
            item.get("flow") != primary_flow,
            item.get("due_at") or "9999",
            item["id"],
        ))
        sections[name] = values[:limit]
    return sections


def canonical_work_items(payload, now):
    """Retain current jobs and confirmed results while adapters migrate by domain."""
    routes = {"cards":"/dashboard/card", "reviews":"/dashboard/card?tab=reviews&review_filter=needs_reply",
        "content":"/dashboard/content", "services":"/dashboard/card?tab=services",
        "finance":"/dashboard/finance", "partnerships":"/dashboard/partnerships",
        "agents":"/dashboard/agents", "progress":"/dashboard/progress", "tasks":"/dashboard/operator"}
    result = []
    for section in ("active_work","completed_results"):
        for original in payload.get(section) or []:
            # Preserve aggregate/setup facts in the legacy response, not in completed work.
            if section == "completed_results" and (not original.get("occurred_at") or original.get("kind") in {"growth_achievement", "aggregate", "summary"}):
                continue
            screen = str(original.get("screen") or "tasks")
            flow = normalize_flow(screen)
            flow = flow if flow in FLOWS else "overview"
            identity = str(original.get("id") or "")
            if not identity:
                continue
            entity_type = "journey_action" if original.get("kind") == "owner_action" else "agent_run" if identity.startswith("agent:") else "canonical_work"
            entity_id = str(original.get("entity_id") or identity.split(":",1)[1]) if entity_type in {"agent_run", "journey_action"} else identity
            existing_url = (original.get("action") or {}).get("url")
            url = existing_url if str(existing_url or "").startswith("/dashboard/") else routes.get(screen, "/dashboard/progress")
            if entity_type == "journey_action":
                url = "/dashboard/operator?" + urlencode({"business_id": original.get("business_id") or "", "journey_action": entity_id})
            item = work_item(entity_type=entity_type,entity_id=entity_id,flow=flow,
                business_id=original.get("business_id"),business_name=original.get("business_name"),title=original.get("title") or "",
                description=original.get("description") or original.get("stage") or "",
                status=(original.get("status") or "completed") if section=="completed_results" else original.get("work_status") or original.get("status") or "unknown",
                url=url,now=now,updated_at=original.get("occurred_at"),due_at=original.get("due_at"))
            result.append({**original, **item, "action": {**(original.get("action") or {}), **item["action"], "label": (original.get("action") or {}).get("label") or item["action"]["label"]}})
    return result


def attach_today_workspace(cursor, *, scope, user_id, payload, now):
    if not enabled() or scope.get("kind") not in {"business","network"} or not schema_available(cursor):
        return payload
    cursor.execute("SELECT COALESCE(is_superadmin,FALSE) is_superadmin FROM users WHERE id=%s", (user_id,))
    is_superadmin = bool(_row(cursor,cursor.fetchone()).get("is_superadmin"))
    allowed = allowed_priority_flows(cursor,scope=scope,is_superadmin=is_superadmin)
    preferences = read_preferences(cursor,user_id=user_id,scope=scope,allowed_flows=allowed,now=now)
    preferences["preference"]["available_flows"] = allowed
    primary = preferences["preference"]["primary_flow"]
    items, warnings = [], list(payload.get("data_warnings") or [])
    source_states = {}
    for flow, loader in (("content",content_work),("influencers",influencer_work),("automation",automation_work)):
        if flow not in allowed:
            source_states[flow] = {"status":"unavailable","as_of":now.isoformat()}
            continue
        cursor.execute("SAVEPOINT today_workspace_source")
        try:
            items.extend(loader(cursor,scope,now))
            source_states[flow] = {"status":"live","as_of":now.isoformat()}
        except Exception:
            cursor.execute("ROLLBACK TO SAVEPOINT today_workspace_source")
            source_states[flow] = {"status":"error","as_of":now.isoformat()}
            warnings.append({"code":"today_source_unavailable","flow":flow})
        finally:
            cursor.execute("RELEASE SAVEPOINT today_workspace_source")
    if 'automation' in allowed:
        for action in payload.get('active_work') or []:
            if action.get('kind') != 'owner_action':
                continue
            due=datetime.fromisoformat(action['due_at'])
            items.append({**action, **work_item(entity_type='journey_action',entity_id=action['entity_id'],flow='automation',business_id=action['business_id'],business_name=action.get('business_name'),
                title=action['title'],description=action['description'],status=action['status'],due_at=due,
                updated_at=action['occurred_at'],now=now,urgent=due<=now,
                url='/dashboard/operator?'+urlencode({'business_id':action['business_id'],'journey_action':action['entity_id']}))})
    # Other tracks use their existing next-action records, with existing approval URLs.
    for action in payload.get("journey_actions") or []:
        flow = normalize_flow(action.get("flow_type"))
        if flow not in allowed or flow in {"content","influencers","automation"}:
            continue
        routes = {"maps":"/dashboard/card","partnerships":"/dashboard/promotion/partnerships","upsells":"/dashboard/average-ticket"}
        url = routes.get(flow)
        if url:
            items.append(work_item(entity_type="journey_action",entity_id=action["id"],flow=flow,business_id=action.get("business_id"),
                title=action.get("title") or "Продолжить",description=action.get("description") or "",status=action.get("status") or "ready",
                url=url+"?"+urlencode({"journey_action":action["id"],"business_id":action.get("business_id") or ""}),now=now,due_at=action.get("due_at")))
    focus = payload.get("focus_action") or {}
    if int(focus.get("priority") or 0) >= 100:
        focus_flow = normalize_flow({"reviews":"maps", "finance":"upsells"}.get(focus.get("screen"), focus.get("screen")))
        focus_routes = {"maps":"/dashboard/card?tab=reviews&review_filter=needs_reply", "partnerships":"/dashboard/partnerships", "automation":"/dashboard/agents", "content":"/dashboard/content", "upsells":"/dashboard/average-ticket"}
        if focus_flow in allowed and focus_flow in focus_routes:
            items.append(work_item(entity_type="attention",entity_id=focus.get("id") or focus_flow,flow=focus_flow,
                business_id=(focus.get("target_scope") or {}).get("id") or (scope["id"] if scope["kind"]=="business" else None),
                title=focus.get("title") or "Требует внимания",description=focus.get("reason") or "",
                status="needs_review",url=focus.get("cta_url") if str(focus.get("cta_url") or "").startswith("/dashboard/") else focus_routes[focus_flow],now=now,urgent=True))
    items.extend(item for item in canonical_work_items(payload,now) if item["flow"] in allowed)
    sections = section_items(items, primary if primary in allowed else "overview", now=now)
    return {**payload,**preferences,"work_sections":sections,"work_source_states":source_states,"data_warnings":warnings}
