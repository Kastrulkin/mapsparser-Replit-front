"""Read-only projections of existing work; never a second task store."""
from urllib.parse import urlencode


def aggregate_growth_paths(locations):
    result = {}
    for location in locations:
        for path in location.get("paths") or []:
            flow = path["flow_type"]
            if flow not in result:
                result[flow] = {**path, "action": None, "locations": []}
            item = result[flow]
            access = path.get("access") or {}
            item["locations"].append({"business_id": location["business_id"],
                "business_name": location.get("business_name"), "status": path.get("status"),
                "access": access, "action": path.get("action") if access.get("status") == "available" else None})
            if access.get("status") == "available":
                item["access"] = access
    attention = ['failed', 'error', 'blocked', 'needs_attention', 'needs_review', 'waiting_approval', 'awaiting_approval', 'ready', 'draft', 'draft_generated', 'edited']
    for item in result.values():
        statuses = [row.get('status') or 'unknown' for row in item['locations'] if (row.get('access') or {}).get('status') == 'available']
        if not statuses:
            continue
        if len(set(statuses)) == 1:
            status = statuses[0]
        else:
            status = next((value for value in attention if value in statuses), 'unknown')
        if len(statuses) < len(item['locations']) and status in {'completed', 'succeeded', 'published', 'delivered'}:
            status = 'unknown'
        item['status'] = status
    return list(result.values())


def work_projection(item):
    """Attach identity without discarding source status, timestamps or URLs."""
    return {**item, "work_ref": {
        "business_id": item.get("business_id"), "entity_type": item.get("entity_type"),
        "entity_id": item.get("entity_id") or item.get("id"),
        "flow": item.get("flow"), "status": item.get("status"), "requires_decision": item.get("requires_decision", False),
        "due_at": item.get("due_at"), "updated_at": item.get("occurred_at"),
        "href": (item.get("action") or {}).get("url"), "source": item.get("source"),
    }}


def linked_draft_route(action, business_id):
    payload = action.get("payload_json") or {}
    # Work-journal post drafts are news drafts, not content-plan items.
    draft_id = payload.get("draft_id")
    if not draft_id:
        return None
    return "/dashboard/card?" + urlencode({"tab": "news", "mode": "drafts", "draft_id": draft_id, "business_id": business_id})


def discuss_existing_work(action, business_id):
    """Read the selected work; commands remain on its existing approval controller."""
    status = action.get("status") or "unknown"
    return {"status": "completed", "capability": "operator.query",
        "summary": action.get("title") or "Выбранная работа",
        "chat_response": "\n".join(filter(None, [action.get("title"), action.get("description"),
            "Проверка и подтверждение доступны в выбранной работе. Обсуждение само ничего не запускает."])),
        "selected_work": {"id": str(action["id"]), "business_id": business_id, "status": status,
            "entity_type": action.get("entity_type"), "entity_id": str(action.get("entity_id") or "")},
        "result_ref": {"href": "/dashboard/operator?" + urlencode({"business_id": business_id, "journey_action": str(action["id"])}), "label": "Открыть работу"}}


def internal_work_ref(value, business_id):
    """Validate a read-only return target; never interpret navigation as a command."""
    from urllib.parse import urlsplit, parse_qs, urlencode
    if not isinstance(value, str) or not value.startswith('/dashboard/') or any(char in value for char in ('\\', '\r', '\n')):
        return None
    parts = urlsplit(value)
    allowed = {'/dashboard/content', '/dashboard/card', '/dashboard/partnerships', '/dashboard/influencers', '/dashboard/agents', '/dashboard/average-ticket', '/dashboard/work-journal'}
    if parts.netloc or parts.scheme or parts.path not in allowed:
        return None
    params = parse_qs(parts.query)
    if params.get('business_id') and params['business_id'] != [str(business_id)]:
        return None
    params['business_id'] = [str(business_id)]
    return parts.path + '?' + urlencode(params, doseq=True)


def unavailable_work_context(href):
    text = 'Для этой записи пока нет связи с управлением через чат. Откройте работу, чтобы проверить материал и продолжить её. Новое поручение не создано.'
    return {'status': 'blocked', 'capability': 'operator.query', 'summary': text, 'chat_response': text,
            'result_ref': {'kind': 'work', 'href': href}}


def redact_unavailable_work(action):
    """Keep the envelope and access remedy, withhold paid material content."""
    result = dict(action)
    for key in ('payload', 'payload_json', 'result', 'result_json'):
        if key in result:
            result[key] = {}
    result['title'] = 'Для этой работы нужен доступ'
    for key in ('description', 'reason', 'expected_outcome'):
        if key in result:
            result[key] = (result.get('access') or {}).get('reason') or ''
    return result
