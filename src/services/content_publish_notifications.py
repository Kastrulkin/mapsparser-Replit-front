from __future__ import annotations

import json
import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TELEGRAM_MINI_APP_URL = "https://localos.pro/telegram/control"
HANDOFF_PLATFORMS = {"telegram", "vk", "max"}
HANDOFF_STATUSES = {"approved", "needs_manual_publish"}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(value, (tuple, list)):
        return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}
    return {}


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _normalize_photo(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    versions = _json_object(value.get("versions_json"))
    original = _json_object(versions.get("original"))
    upload = _json_object(_json_object(value.get("metadata_json")).get("upload"))
    asset_id = str(value.get("id") or value.get("asset_id") or value.get("photo_asset_id") or "").strip()
    storage_path = str(value.get("storage_path") or original.get("storage_path") or value.get("storage_key") or "").strip()
    if not asset_id and not storage_path:
        return None
    return {
        "id": asset_id,
        "storage_path": storage_path,
        "public_url": str(value.get("public_url") or original.get("public_url") or "").strip(),
        "mime_type": str(value.get("mime_type") or original.get("mime_type") or "image/jpeg").strip(),
        "original_name": str(value.get("original_name") or upload.get("original_name") or "").strip(),
    }


def _selected_photo(cursor: Any, post: dict[str, Any]) -> dict[str, Any] | None:

    media_json = post.get("media_json")
    candidates = media_json if isinstance(media_json, list) else [media_json]
    for candidate in candidates:
        selected = _normalize_photo(candidate)
        if selected:
            return selected

    business_id = str(post.get("business_id") or "").strip()
    target_ids = [
        value
        for value in (
            str(post.get("id") or "").strip(),
            str(post.get("content_plan_item_id") or "").strip(),
        )
        if value
    ]
    platform = str(post.get("platform") or "").strip()
    if not business_id or not target_ids:
        return None
    cursor.execute(
        """
        SELECT pa.id, pa.original_url, pa.storage_key, pa.versions_json, pa.metadata_json,
               usage.target_platform, usage.created_at
        FROM photo_asset_usage_events usage
        JOIN photo_assets pa
          ON pa.id = usage.photo_asset_id
         AND pa.business_id = usage.business_id
        WHERE usage.business_id = %s
          AND usage.usage_type = 'publication'
          AND usage.target_id = ANY(%s)
          AND (usage.target_platform IS NULL OR usage.target_platform = '' OR usage.target_platform = %s)
        ORDER BY usage.created_at DESC
        LIMIT 1
        """,
        (business_id, target_ids, platform),
    )
    return _normalize_photo(_row(cursor, cursor.fetchone()))


def _selected_photos(cursor: Any, post: dict[str, Any]) -> list[dict[str, Any]]:
    media = post.get("media_json")
    if isinstance(media, list) and media:
        selected = [_normalize_photo(value) for value in media]
        if any(value is None for value in selected):
            return []
        return selected
    selected = _selected_photo(cursor, post)
    return [selected] if selected else []


def _enabled_scopes(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT user_id, telegram_id, notification_preferences_json
        FROM telegramcontrolpreferences
        WHERE NULLIF(BTRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        """
    )
    scopes: list[dict[str, Any]] = []
    for raw in cursor.fetchall() or []:
        preference = _row(cursor, raw)
        notifications = _json_object(preference.get("notification_preferences_json"))
        for scope_key, settings in notifications.items():
            if not isinstance(settings, dict) or not bool(settings.get("content_publications")):
                continue
            scope_type, separator, scope_id = str(scope_key).partition(":")
            if not separator or scope_type not in {"business", "network"} or not scope_id:
                continue
            scopes.append(
                {
                    "user_id": str(preference.get("user_id") or ""),
                    "telegram_id": str(preference.get("telegram_id") or ""),
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                    "lead_days": str(_content_publication_lead_days(settings)),
                    "handoff_time": str(settings.get("content_publications_time") or ""),
                    "required_platforms": settings.get("content_publications_platforms") or [],
                }
            )
    return scopes


def _active_compiled_handoff_scopes(cursor: Any) -> set[tuple[str, str]]:
    """Prevent the legacy preference scanner from dispatching a compiled-owned scope."""
    cursor.execute(
        """SELECT blueprint.business_id::text AS business_id,
                  step.value->'payload'->>'recipient_user_id' AS recipient_user_id
           FROM agent_blueprints blueprint
           JOIN agent_blueprint_versions version
             ON version.blueprint_id=blueprint.id
            AND version.id::text=blueprint.metadata_json->>'active_version_id'
           CROSS JOIN LATERAL jsonb_array_elements(version.steps_json) AS step(value)
           WHERE blueprint.status='active'
             AND version.execution_mode='scheduled'
             AND version.trigger='schedule.daily'
             AND step.value->>'capability'='content.publish_handoff'
             AND blueprint.metadata_json->'compiled_content_handoff_consent'->>'version_id'=version.id::text
             AND blueprint.metadata_json->'compiled_content_handoff_consent'->'scope'->>'business_id'=blueprint.business_id::text
             AND blueprint.metadata_json->'compiled_content_handoff_consent'->'scope'->>'recipient_user_id'=step.value->'payload'->>'recipient_user_id'"""
    )
    return {
        (str(item.get("business_id") or ""), str(item.get("recipient_user_id") or ""))
        for item in (_row(cursor, raw) for raw in (cursor.fetchall() or []))
        if item.get("business_id") and item.get("recipient_user_id")
    }


def _content_publication_lead_days(settings: dict[str, Any]) -> int:
    try:
        value = int(settings.get("content_publications_lead_days") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(value, 7))


def collect_due_content_publish_handoffs(
    conn: Any,
    *,
    now: datetime | None = None,
    limit: int = 100,
    business_id: str | None = None,
    recipient_user_id: str | None = None,
    compiled_scope: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    observed_at = now or datetime.now(timezone.utc)
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    scopes = [dict(compiled_scope)] if isinstance(compiled_scope, dict) else _enabled_scopes(cursor)
    compiled_owned_scopes = _active_compiled_handoff_scopes(cursor) if not isinstance(compiled_scope, dict) else set()
    for scope in scopes:
        if isinstance(compiled_scope, dict):
            scope.setdefault("scope_type", "business")
            scope.setdefault("scope_id", str(scope.get("business_id") or ""))
            scope.setdefault("lead_days", "1")
            scope.setdefault("handoff_time", "10:00")
            scope.setdefault("required_platforms", list(HANDOFF_PLATFORMS))
            scope.setdefault("business_id", scope.get("scope_id"))
            if not all(str(scope.get(key) or "").strip() for key in ("business_id", "user_id", "telegram_id")):
                continue
        # Compiled LocalOS workflows may request one exact business/recipient
        # scope. The legacy worker keeps the unfiltered behavior.
        if business_id and (scope["scope_type"] != "business" or scope["scope_id"] != str(business_id)):
            continue
        if recipient_user_id and scope["user_id"] != str(recipient_user_id):
            continue
        if (scope["scope_type"] == "business" and
                (scope["scope_id"], scope["user_id"]) in compiled_owned_scopes):
            continue
        scope_filter = "sp.business_id = %s" if scope["scope_type"] == "business" else "b.network_id = %s"
        cursor.execute(
            f"""
            SELECT sp.*, b.name business_name, COALESCE(b.address, '') business_address,
                   COALESCE(NULLIF(settings.timezone, ''), to_jsonb(b)->>'timezone') business_timezone
            FROM social_posts sp
            JOIN businesses b ON b.id = sp.business_id
            LEFT JOIN business_finance_settings settings ON settings.business_id = b.id
            WHERE {scope_filter}
              AND sp.platform = ANY(%s)
              AND sp.publish_mode = 'manual'
              AND sp.status = ANY(%s)
              AND sp.scheduled_for IS NOT NULL
              AND ((sp.scheduled_for >= %s AND sp.scheduled_for < %s)
                   OR (sp.scheduled_for > %s AND sp.metadata_json->'staff_handoff'->'telegram_deliveries' ? %s))
            ORDER BY sp.scheduled_for, sp.created_at
            LIMIT %s
            """,
            (
                scope["scope_id"],
                list(scope.get("required_platforms") or HANDOFF_PLATFORMS),
                list(HANDOFF_STATUSES | {"needs_review", "draft"}),
                observed_at - timedelta(days=1),
                observed_at + timedelta(days=int(scope.get("lead_days") or 0) + 2),
                observed_at, scope["user_id"],
                max(1, limit),
            ),
        )
        for raw in cursor.fetchall() or []:
            post = _row(cursor, raw)
            post_id = str(post.get("id") or "")
            user_id = scope["user_id"]
            identity = (post_id, user_id)
            metadata = _json_object(post.get("metadata_json"))
            deliveries = _json_object(_json_object(metadata.get("staff_handoff")).get("telegram_deliveries"))
            delivery = _json_object(deliveries.get(user_id))
            is_update = bool(delivery.get("sent_at") or delivery.get("is_update"))
            if not post_id or identity in seen or not handoff_due({**post, **scope, "is_update": is_update}, observed_at) or not handoff_plan_current(cursor, post):
                continue
            seen.add(identity)
            photos = _selected_photos(cursor, post)
            item = {**post, **scope, "selected_photo": photos[0] if photos else None, "selected_photos": photos}
            item["revision"] = handoff_revision(item)
            if post.get("status") not in HANDOFF_STATUSES or not handoff_kit_complete(cursor, item):
                item["blocked_reason"] = "incomplete"
            delivery = _json_object(deliveries.get(user_id))
            # Legacy receipts are conclusive; never replay them on upgrade.
            if delivery and not delivery.get("revision"):
                continue
            if delivery.get("revision") == item["revision"] and delivery.get("sent_at"):
                continue
            if any(part.get("status") in {"attempting", "uncertain"}
                   for part in _json_object(delivery.get("parts")).values() if isinstance(part, dict)):
                item["blocked_reason"] = "needs_reconciliation"
            item["is_update"] = is_update
            result.append(item)
            if len(result) >= max(1, limit):
                return result
    return result


def format_content_publish_handoff(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    platform = str(item.get("platform") or "").strip()
    platform_label = {
        "telegram": "Telegram",
        "vk": "VK",
        "max": "MAX",
    }.get(platform, platform)
    business_name = str(item.get("business_name") or "Бизнес").strip()
    address = str(item.get("business_address") or "").strip()
    text = str(item.get("platform_text") or item.get("base_text") or "").strip()
    scheduled = item.get("scheduled_for")
    if isinstance(scheduled, datetime):
        zone_name = item.get("business_timezone")
        local = scheduled.astimezone(ZoneInfo(zone_name)) if zone_name else scheduled
        date_label = local.date().strftime("%d.%m.%Y")
    elif isinstance(scheduled, date):
        date_label = scheduled.strftime("%d.%m.%Y")
    else:
        date_label = "сегодня"
    heading = f"Публикация для {platform_label} · {date_label}"
    if item.get("is_update"):
        heading = "Обновление материалов · " + heading
    location = " · ".join(value for value in (business_name, address) if value)
    message = "\n\n".join(
        [heading, location, text, "Разместите текст вручную и отметьте публикацию в ЛокалОС."]
    )
    query = urlencode(
        {
            "screen": "content",
            "scope_type": "business",
            "scope_id": str(item.get("business_id") or ""),
            "item_id": str(item.get("content_plan_item_id") or ""),
        }
    )
    reply_markup = {
        "inline_keyboard": [[{"text": "Открыть публикацию", "web_app": {"url": f"{TELEGRAM_MINI_APP_URL}?{query}"}}]]
    }
    return message, reply_markup


def mark_content_publish_handoff_sent(
    conn: Any,
    *,
    post_id: str,
    user_id: str,
    telegram_message_id: int,
    telegram_photo_message_id: int = 0,
    sent_at: datetime | None = None,
) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT metadata_json FROM social_posts WHERE id = %s FOR UPDATE", (post_id,))
    row = _row(cursor, cursor.fetchone())
    if not row:
        return False
    metadata = _json_object(row.get("metadata_json"))
    handoff = _json_object(metadata.get("staff_handoff"))
    deliveries = _json_object(handoff.get("telegram_deliveries"))
    deliveries[str(user_id)] = {
        "sent_at": (sent_at or datetime.now(timezone.utc)).isoformat(),
        "telegram_message_id": int(telegram_message_id or 0),
        "telegram_photo_message_id": int(telegram_photo_message_id or 0),
    }
    metadata["staff_handoff"] = {**handoff, "telegram_deliveries": deliveries}
    cursor.execute(
        "UPDATE social_posts SET metadata_json = %s::jsonb, updated_at = NOW() WHERE id = %s",
        (json.dumps(metadata, ensure_ascii=False), post_id),
    )
    return bool(cursor.rowcount)


def handoff_due(item: dict[str, Any], now: datetime) -> bool:
    """Previous calendar day in the explicitly configured business timezone."""
    scheduled = item.get("scheduled_for")
    if not isinstance(scheduled, datetime) or scheduled.tzinfo is None or now.tzinfo is None:
        return False
    try:
        zone = ZoneInfo(str(item.get("business_timezone") or ""))
    except (ValueError, ZoneInfoNotFoundError):
        return False
    local_now = now.astimezone(zone)
    if item.get("is_update") and scheduled > now:
        return True
    if item.get("handoff_time"):
        try:
            planned = datetime.strptime(item["handoff_time"], "%H:%M").time()
        except ValueError:
            return False
        if local_now.time() < planned:
            return False
    return scheduled.astimezone(zone).date() == (
        now.astimezone(zone).date() + timedelta(days=int(item.get("lead_days") or 0))
    )


def handoff_revision(item: dict[str, Any]) -> str:
    payload = [str(item.get("scheduled_for") or ""), item.get("platform"),
               item.get("platform_text") or item.get("base_text"), item.get("selected_photos") or [item.get("selected_photo")]]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def claim_handoff_part(conn: Any, item: dict[str, Any], part_key: str, *, compiled_scope: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist intent before sending. Interrupted attempts require reconciliation."""
    from services.operator_audio import authorize_actor
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM social_posts WHERE id=%s FOR UPDATE", (item["id"],))
    current = _row(cursor, cursor.fetchone())
    if not current or current.get("status") not in HANDOFF_STATUSES or current.get("publish_mode") != "manual" or not handoff_plan_current(cursor, current):
        return {"status": "cancelled"}
    if isinstance(compiled_scope, dict):
        scope = dict(compiled_scope)
        dispatch = scope.get('compiled_dispatch')
        if isinstance(dispatch, dict):
            from services.compiled_content_program import dispatch_fence, program_allowed
            run = {'id': dispatch.get('run_id'), 'blueprint_id': dispatch.get('blueprint_id'),
                   'blueprint_version_id': dispatch.get('version_id'), 'lease_token': dispatch.get('lease_token')}
            consent_scope = {'business_id': scope['business_id'], 'recipient_user_id': scope['user_id'],
                'platforms': sorted(scope['required_platforms']), 'lead_days': int(scope['lead_days']),
                'time': scope['handoff_time'], 'timezone': scope['timezone']}
            if (not program_allowed(scope['business_id'], dispatch.get('blueprint_id'))
                    or not dispatch_fence(cursor, run, dispatch.get('artifact_hash'), consent_scope)):
                return {'status': 'paused'}
        cursor.execute(
            """SELECT p.user_id, p.telegram_id, u.is_active FROM telegramcontrolpreferences p
               JOIN users u ON u.id=p.user_id WHERE p.user_id=%s LIMIT 1""",
            (str(scope.get("user_id") or ""),),
        )
        recipient = _row(cursor, cursor.fetchone())
        if (
            not recipient
            or not recipient.get("is_active")
            or str(recipient.get("telegram_id") or "") != str(scope.get("telegram_id") or "")
            or str(scope.get("business_id") or "") != str(item.get("business_id") or "")
            or str(scope.get("user_id") or "") != str(item.get("user_id") or "")
        ):
            return {"status": "paused"}
        authorize_actor(cursor, scope["user_id"], scope["business_id"], check_subscription=False)
        scope.update(scope_type="business", scope_id=scope["business_id"])
    else:
        scopes = _enabled_scopes(cursor)
        scope = next((scope for scope in scopes if scope["user_id"] == item["user_id"]
                      and scope["telegram_id"] == item["telegram_id"]
                      and scope["scope_type"] == item["scope_type"] and scope["scope_id"] == item["scope_id"]), None)
    if not scope:
        return {"status": "paused"}
    if current.get("platform") not in (scope.get("required_platforms") or HANDOFF_PLATFORMS):
        return {"status": "paused"}
    authorize_actor(cursor, item["user_id"], current["business_id"], check_subscription=False)
    from services.business_input_settings import resolve
    current["business_timezone"] = resolve(cursor, current["business_id"]).get("timezone")
    current_receipt = _json_object(_json_object(_json_object(current.get("metadata_json")).get("staff_handoff")).get("telegram_deliveries")).get(item["user_id"]) or {}
    current["is_update"] = bool(current_receipt.get("sent_at") or current_receipt.get("is_update"))
    current["lead_days"] = scope["lead_days"]
    current["handoff_time"] = scope["handoff_time"]
    current["required_platforms"] = scope["required_platforms"]
    if not handoff_kit_complete(cursor, current):
        return {"status": "incomplete"}
    current["selected_photos"] = _selected_photos(cursor, current)
    current["selected_photo"] = current["selected_photos"][0] if current["selected_photos"] else None
    if not handoff_due(current, datetime.now(timezone.utc)) or handoff_revision(current) != item["revision"]:
        return {"status": "stale"}
    if not current["selected_photo"] or not str(current.get("platform_text") or current.get("base_text") or "").strip():
        return {"status": "incomplete"}
    metadata = _json_object(current.get("metadata_json"))
    handoff = _json_object(metadata.get("staff_handoff"))
    deliveries = _json_object(handoff.get("telegram_deliveries"))
    receipt = _json_object(deliveries.get(item["user_id"]))
    if receipt and not receipt.get("revision"):
        return {"status": "legacy_sent"}
    parts = _json_object(receipt.get("parts"))
    if any(part.get("status") in {"attempting", "uncertain"} for part in parts.values() if isinstance(part, dict)):
        return {"status": "uncertain"}
    if receipt.get("revision") != item["revision"]:
        receipt = {"revision": item["revision"], "previous": receipt, "parts": {}, "is_update": bool(receipt.get("sent_at") or receipt.get("is_update"))}
        parts = {}
    previous_part = _json_object(parts.get(part_key))
    if previous_part.get("status") == "sent":
        return previous_part
    attempts = previous_part.get("attempt_count", 0)
    if attempts >= 3:
        return {"status": "needs_attention"}
    attempted_at = previous_part.get("attempted_at")
    if attempted_at and datetime.fromisoformat(attempted_at) + timedelta(minutes=5 * max(attempts, 1)) > datetime.now(timezone.utc):
        return {"status": "retry_wait"}
    parts[part_key] = {"status": "attempting", "attempt_count": attempts + 1,
                       "attempted_at": datetime.now(timezone.utc).isoformat()}
    receipt["parts"] = parts
    deliveries[item["user_id"]] = receipt
    metadata["staff_handoff"] = {**handoff, "telegram_deliveries": deliveries}
    cursor.execute("UPDATE social_posts SET metadata_json=%s::jsonb WHERE id=%s", (json.dumps(metadata, ensure_ascii=False), item["id"]))
    conn.commit()
    return {"status": "claimed"}


def finish_handoff_part(conn: Any, item: dict[str, Any], part_key: str, result: dict[str, Any], *, final: bool = False) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT metadata_json FROM social_posts WHERE id=%s FOR UPDATE", (item["id"],))
    metadata = _json_object(_row(cursor, cursor.fetchone()).get("metadata_json"))
    handoff = _json_object(metadata.get("staff_handoff"))
    deliveries = _json_object(handoff.get("telegram_deliveries"))
    receipt = _json_object(deliveries.get(item["user_id"]))
    if receipt.get("revision") != item["revision"]:
        raise ValueError("handoff_receipt_revision_changed")
    parts = _json_object(receipt.get("parts"))
    if _json_object(parts.get(part_key)).get("status") != "attempting":
        raise ValueError("handoff_part_not_claimed")
    success = bool(result.get("success") and result.get("message_id"))
    outcome = result.get("publish_outcome")
    status = "sent" if success else ("not_sent" if outcome in {"rejected", "not_attempted"} else "uncertain")
    parts[part_key] = {**parts[part_key], "status": status, "message_id": result.get("message_id"),
                       "reason_code": result.get("reason_code", "")}
    if success and final:
        receipt["sent_at"] = datetime.now(timezone.utc).isoformat()
    receipt["parts"] = parts
    deliveries[item["user_id"]] = receipt
    metadata["staff_handoff"] = {**handoff, "telegram_deliveries": deliveries}
    cursor.execute("UPDATE social_posts SET metadata_json=%s::jsonb WHERE id=%s", (json.dumps(metadata, ensure_ascii=False), item["id"]))
    conn.commit()


def deliver_content_publish_handoff(conn: Any, item: dict[str, Any], *, send_photo: Any, send_text: Any, validate_media: Any = None, compiled_scope: dict[str, Any] | None = None) -> str:
    if item.get("blocked_reason"):
        return item["blocked_reason"]
    if not item.get("selected_photo") or not str(item.get("platform_text") or item.get("base_text") or "").strip():
        return "incomplete"
    message, markup = format_content_publish_handoff(item)
    # Telegram's limit uses UTF-16 units; 2000 code points also fit with emoji.
    chunks = [message[index:index + 2000] for index in range(0, len(message), 2000)]
    photos = item.get("selected_photos") or [item["selected_photo"]]
    if item.get("required_platforms") and not handoff_kit_complete(conn.cursor(), item, validate_media=validate_media):
        return "incomplete"
    if validate_media and any(not validate_media(photo) for photo in photos):
        return "incomplete"
    keys = [("photo" if index == 0 else f"photo:{index}") for index in range(len(photos))] + [f"text:{index}" for index in range(len(chunks))]
    for index, key in enumerate(keys):
        claim = (
            claim_handoff_part(conn, item, key, compiled_scope=compiled_scope)
            if isinstance(compiled_scope, dict)
            else claim_handoff_part(conn, item, key)
        )
        if claim["status"] == "sent":
            continue
        if claim["status"] != "claimed":
            conn.rollback()
            return claim["status"]
        if key.startswith("photo"):
            result = send_photo({**item, "selected_photo": photos[index]})
        else:
            result = send_text(item["telegram_id"], chunks[index - len(photos)], reply_markup=markup if index == len(keys) - 1 else None)
        finish_handoff_part(conn, item, key, result, final=index == len(keys) - 1)
        if not result.get("success") or not result.get("message_id"):
            return "needs_attention"
    return "sent"


def queue_handoff_alert(conn: Any, *, business_id: str, event_key: str, message: str) -> None:
    """Use the existing journey action/outbox for one alert per condition."""
    import uuid
    cursor = conn.cursor()
    cursor.execute("SELECT id, telegram_id FROM users WHERE is_superadmin IS TRUE AND is_active IS TRUE AND NULLIF(BTRIM(telegram_id::text),'') IS NOT NULL")
    recipients = [_row(cursor, row) for row in cursor.fetchall()]
    for recipient in recipients:
        key = hashlib.sha256(f"content-handoff:{business_id}:{event_key}:{recipient['id']}".encode()).hexdigest()
        action_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
        cursor.execute("""INSERT INTO journey_actions(id,business_id,user_id,flow_type,entity_type,entity_id,action_type,
            title,description,cta_label,cta_target_json,payload_json,dedupe_key,due_at)
            VALUES(%s,%s,%s,'content','content_handoff_alert',%s,'review_content','Материалы для публикации',%s,
            'Открыть контент-план','{}'::jsonb,'{}'::jsonb,%s,NOW()) ON CONFLICT(id) DO NOTHING""",
            (action_id, business_id, recipient['id'], event_key, message, key))
        cursor.execute("""INSERT INTO journey_action_notification_deliveries(dedupe_key,action_id,action_version,user_id,
            telegram_id,message_text,reply_markup_json,dispatch_state)
            VALUES(%s,%s,1,%s,%s,%s,'{}'::jsonb,'queued') ON CONFLICT(dedupe_key) DO NOTHING""",
            (key, action_id, recipient['id'], str(recipient['telegram_id']), message))


def collect_exhausted_content_plan_alerts(conn: Any, *, now: datetime | None = None) -> None:
    cursor = conn.cursor()
    moment = now or datetime.now(timezone.utc)
    for scope in _enabled_scopes(cursor):
        scope_filter = 'b.id=%s' if scope['scope_type'] == 'business' else 'b.network_id=%s'
        cursor.execute(f"""SELECT b.id business_id,b.name,plan.id plan_id,plan.period_end,
            COALESCE(NULLIF(settings.timezone,''),to_jsonb(b)->>'timezone') business_timezone
            FROM businesses b
            JOIN LATERAL (SELECT id,period_end FROM contentplans WHERE business_id=b.id AND plan_status<>'archived'
                          ORDER BY created_at DESC LIMIT 1) plan ON TRUE
            LEFT JOIN business_finance_settings settings ON settings.business_id=b.id
            WHERE {scope_filter}""", (scope['scope_id'],))
        plans = [_row(cursor, row) for row in cursor.fetchall()]
        for plan in plans:
            try:
                today = moment.astimezone(ZoneInfo(str(plan.get('business_timezone') or ''))).date()
            except (ValueError, ZoneInfoNotFoundError):
                continue
            if plan['period_end'] < today:
                queue_handoff_alert(conn, business_id=plan['business_id'], event_key='plan-ended:' + plan['plan_id'],
                    message=f"{plan['name']}: контент-план закончился {plan['period_end']:%d.%m.%Y}. Требуется создать новый план. Новый план автоматически не создавался.")


def dispatch_handoff_alerts(conn: Any, *, send_text: Any) -> None:
    """Claim-before-send on the existing outbox; no blind retry after restart."""
    cursor = conn.cursor()
    cursor.execute("""SELECT delivery.* FROM journey_action_notification_deliveries delivery
        JOIN journey_actions action ON action.id=delivery.action_id
        JOIN users recipient ON recipient.id=delivery.user_id
        WHERE action.entity_type='content_handoff_alert' AND action.status IN ('ready','blocked')
          AND recipient.is_superadmin IS TRUE AND recipient.is_active IS TRUE
          AND recipient.telegram_id::text=delivery.telegram_id
          AND delivery.attempted_at IS NULL AND delivery.sent_at IS NULL
        ORDER BY delivery.created_at LIMIT 20 FOR UPDATE OF delivery SKIP LOCKED""")
    deliveries = [_row(cursor, row) for row in cursor.fetchall()]
    for delivery in deliveries:
        cursor.execute("""UPDATE journey_action_notification_deliveries SET attempted_at=NOW(),dispatch_state='unknown'
            WHERE dedupe_key=%s AND attempted_at IS NULL RETURNING dedupe_key""", (delivery['dedupe_key'],))
        if not cursor.fetchone():
            continue
        conn.commit()
        try:
            result = send_text(delivery['telegram_id'], delivery['message_text'])
        except Exception:
            result = {'success': False}
        success = bool(result.get('success') and result.get('message_id'))
        cursor.execute("""UPDATE journey_action_notification_deliveries SET dispatch_state=%s,
            sent_at=CASE WHEN %s THEN NOW() ELSE NULL END,provider_message_id=%s WHERE dedupe_key=%s""",
            ('sent' if success else 'unknown', success, str(result.get('message_id') or ''), delivery['dedupe_key']))
        cursor.execute("UPDATE journey_actions SET status=%s,updated_at=NOW() WHERE id=%s",
                       ('completed' if success else 'blocked', delivery['action_id']))
        conn.commit()


def handoff_plan_current(cursor: Any, post: dict[str, Any]) -> bool:
    if not post.get('content_plan_id'):
        return True
    cursor.execute("""SELECT id,period_start,period_end FROM contentplans
        WHERE id=%s AND business_id=%s AND plan_status<>'archived'""",
        (post['content_plan_id'], post['business_id']))
    plan = _row(cursor, cursor.fetchone())
    if not plan:
        return False
    from services.business_input_settings import resolve
    scheduled = post.get('scheduled_for')
    if not isinstance(scheduled, datetime):
        return False
    try:
        zone = ZoneInfo(post.get('business_timezone') or resolve(cursor, post['business_id']).get('timezone') or '')
    except (ValueError, ZoneInfoNotFoundError):
        return False
    publication_date = scheduled.astimezone(zone).date()
    if not plan.get('period_start') or not plan.get('period_end') or not plan['period_start'] <= publication_date <= plan['period_end']:
        return False
    if post.get('content_plan_item_id'):
        cursor.execute('SELECT status FROM contentplanitems WHERE id=%s AND plan_id=%s AND business_id=%s',
                       (post['content_plan_item_id'], post['content_plan_id'], post['business_id']))
        status = _row(cursor, cursor.fetchone()).get('status')
        if not status or status in {'skipped', 'published'}:
            return False
    return True


def handoff_kit_complete(cursor: Any, post: dict[str, Any], validate_media: Any = None) -> bool:
    required = set(post.get('required_platforms') or [])
    if not required:
        return True
    if not post.get('content_plan_item_id'):
        return False
    cursor.execute("""SELECT * FROM social_posts WHERE content_plan_item_id=%s AND business_id=%s
        AND scheduled_for=%s AND platform=ANY(%s)""",
        (post['content_plan_item_id'], post['business_id'], post['scheduled_for'], list(required)))
    posts = [_row(cursor, value) for value in cursor.fetchall()]
    ready = set()
    for candidate in posts:
        if candidate.get('status') in HANDOFF_STATUSES and candidate.get('publish_mode') == 'manual' and str(candidate.get('platform_text') or candidate.get('base_text') or '').strip() and _selected_photos(cursor, candidate):
            photos = _selected_photos(cursor, candidate)
            if not validate_media or all(validate_media(photo) for photo in photos):
                ready.add(candidate['platform'])
    return ready == required
