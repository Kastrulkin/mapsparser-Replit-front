from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, jsonify, request
from psycopg2.extras import Json

from auth_encryption import encrypt_auth_data
from core.auth_helpers import require_auth_from_request, verify_business_access
from core.industry_patterns import detect_industry_key
from core.telegram_userbot import (
    confirm_code,
    inspect_telegram_entity,
    list_dialogs,
    load_userbot_account,
    send_code,
    update_userbot_session,
)
from database_manager import DatabaseManager
from services.knowledge_graph_service import knowledge_layer_enabled, upsert_source as upsert_knowledge_source
from services.telegram_opportunity_radar import upsert_source as upsert_radar_source
from services.telegram_research_service import (
    decide_audience_insight,
    list_audience_insights,
    mask_phone,
)
from services.knowledge_public_telegram import inspect_public_channel
from services.telegram_account_permissions_service import (
    assert_account_access,
    disconnect_account,
    ensure_permissions,
    get_permissions,
    sync_sender_binding,
    update_permissions,
)


telegram_research_bp = Blueprint("telegram_research", __name__)


def _user_id(user_data: dict[str, Any]) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "").strip()


def _requested_sender_scope(user_data: dict[str, Any], payload: dict[str, Any]) -> str:
    """Resolve an explicit sender scope without inferring it from the actor role."""
    scope_type = str(payload.get("scope_type") or "business").strip().lower()
    if scope_type not in {"business", "platform"}:
        raise ValueError("scope_type должен быть business или platform")
    if scope_type == "platform" and not bool(user_data.get("is_superadmin")):
        raise PermissionError("Platform scope доступен только суперадмину")
    return scope_type


def _sync_requested_sender_binding(
    cursor: Any,
    *,
    account_id: str,
    user_data: dict[str, Any],
    scope_type: str,
) -> str:
    sender_account_id = sync_sender_binding(
        cursor,
        account_id,
        owner_user_id=_user_id(user_data),
        scope_type=scope_type,
    )
    cursor.execute(
        """
        UPDATE outreach_sender_accounts
        SET status = 'disabled', updated_at = NOW()
        WHERE external_account_id = %s AND id <> %s
        """,
        (account_id, sender_account_id),
    )
    return sender_account_id


def _require_business(business_id: str):
    user_data = require_auth_from_request()
    if not user_data:
        return None, None, None, (jsonify({"success": False, "error": "Требуется авторизация"}), 401)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        db.close()
        status = 403 if owner_id else 404
        return None, None, None, (jsonify({"success": False, "error": "Нет доступа к бизнесу"}), status)
    return db, cursor, user_data, None


def _account_for_business(cursor: Any, business_id: str) -> dict[str, Any] | None:
    return _account_for_scope(cursor, business_id, "business")


def _account_for_scope(
    cursor: Any,
    business_id: str,
    scope_type: str,
) -> dict[str, Any] | None:
    """Load only the Telegram credential explicitly bound to this sender scope.

    ``externalbusinessaccounts`` is the encrypted credential container and may
    hold more than one Telegram account for a superadmin's current business.
    ``outreach_sender_accounts`` remains the authority for whether a credential
    is a business sender or a LocalOS platform sender. Pending authorizations
    carry the requested scope inside the encrypted auth payload until a binding
    can be created.
    """
    binding_business_id = business_id if scope_type == "business" else None
    cursor.execute(
        """
        SELECT account.id AS account_id,
               binding.id AS sender_account_id,
               EXISTS (
                   SELECT 1
                   FROM outreach_sender_accounts any_binding
                   WHERE any_binding.external_account_id = account.id
                     AND any_binding.channel = 'telegram'
                     AND any_binding.status = 'connected'
               ) AS has_any_binding
        FROM externalbusinessaccounts account
        LEFT JOIN outreach_sender_accounts binding
          ON binding.external_account_id = account.id
         AND binding.channel = 'telegram'
         AND binding.status = 'connected'
         AND binding.scope_type = %s
         AND COALESCE(binding.business_id, '') = COALESCE(%s, '')
        WHERE account.business_id = %s
          AND account.source = 'telegram_app'
          AND account.is_active = TRUE
        ORDER BY binding.id IS NOT NULL DESC,
                 account.updated_at DESC NULLS LAST,
                 account.created_at DESC NULLS LAST
        """,
        (scope_type, binding_business_id, business_id),
    )
    for row in cursor.fetchall() or []:
        values = {key: row[key] for key in row.keys()} if hasattr(row, "keys") else {
            "account_id": row[0],
            "sender_account_id": row[1],
            "has_any_binding": row[2],
        }
        account = load_userbot_account(cursor, account_id=str(values.get("account_id") or ""))
        if not account:
            continue
        requested_scope = str(account.get("sender_scope") or "").strip().lower()
        if values.get("sender_account_id") or requested_scope == scope_type:
            return account
        if scope_type == "business" and not requested_scope and not values.get("has_any_binding"):
            return account
    return None


def _business_knowledge_context(cursor: Any, business_id: str) -> dict[str, str]:
    cursor.execute(
        """
        SELECT name, business_type, industry, categories
        FROM businesses WHERE id = %s
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return {"industry_key": "local_business", "audience": "customers"}
    if hasattr(row, "keys"):
        values = {key: row[key] for key in row.keys()}
    else:
        values = {
            "name": row[0],
            "business_type": row[1],
            "industry": row[2],
            "categories": row[3],
        }
    industry_key = detect_industry_key(
        business_name=values.get("name"),
        business_type=values.get("business_type"),
        industry=values.get("industry"),
        categories=values.get("categories"),
    )
    audience = "travel_agents" if industry_key == "travel" else "customers"
    return {"industry_key": industry_key, "audience": audience}


def _public_telegram_username(value: Any) -> str:
    raw = str(value or "").strip()
    raw = raw.removeprefix("https://").removeprefix("http://").removeprefix("www.")
    raw = raw.removeprefix("t.me/").removeprefix("telegram.me/").lstrip("@").strip("/")
    if not raw or "/" in raw or "+" in raw or raw.lower().startswith("joinchat"):
        return ""
    return raw.lower()


def _subscribe_public_source(
    cursor: Any,
    *,
    business_id: str,
    source_id: str,
    industry_key: str,
    topics: list[str] | None = None,
    interval_hours: int = 24,
) -> None:
    cursor.execute(
        """
        INSERT INTO knowledge_source_subscriptions (
            business_id, source_id, purposes_json, topics_json, schedule_json, is_active
        ) VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (business_id, source_id) DO UPDATE SET
            purposes_json = EXCLUDED.purposes_json,
            topics_json = EXCLUDED.topics_json,
            schedule_json = EXCLUDED.schedule_json,
            is_active = TRUE,
            updated_at = NOW()
        """,
        (
            business_id,
            source_id,
            Json(["community_pulse", "content_ideas"]),
            Json(topics or [industry_key]),
            Json({"interval_hours": interval_hours if interval_hours in {6, 12, 24, 72, 168} else 24}),
        ),
    )


def _save_account(cursor: Any, business_id: str, auth_data: dict[str, Any]) -> str:
    account_id = str(auth_data.get("account_id") or "").strip()
    if account_id:
        update_userbot_session(cursor, account_id, auth_data)
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET external_id = %s, display_name = 'Telegram-аккаунт', is_active = TRUE, updated_at = NOW()
            WHERE id = %s AND business_id = %s
            """,
            (str(auth_data.get("phone") or ""), account_id, business_id),
        )
        return account_id
    account_id = str(uuid.uuid4())
    auth_data["account_id"] = account_id
    auth_data["business_id"] = business_id
    encrypted = encrypt_auth_data(_json_text(auth_data))
    cursor.execute(
        """
        INSERT INTO externalbusinessaccounts (
            id, business_id, source, external_id, display_name,
            auth_data_encrypted, is_active, created_at, updated_at
        ) VALUES (%s, %s, 'telegram_app', %s, 'Telegram-аккаунт', %s, TRUE, NOW(), NOW())
        """,
        (account_id, business_id, str(auth_data.get("phone") or ""), encrypted),
    )
    return account_id


def _json_text(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


@telegram_research_bp.post("/api/business/<business_id>/telegram-research/connect")
def connect_research_account(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    phone = str(payload.get("phone") or "").strip()
    api_id = str(payload.get("api_id") or "").strip()
    api_hash = str(payload.get("api_hash") or "").strip()
    if not phone or not api_id.isdigit() or not api_hash:
        db.close()
        return jsonify({"success": False, "error": "Укажите номер, API ID и API hash"}), 400
    try:
        scope_type = _requested_sender_scope(user_data, payload)
        auth_data = _account_for_scope(cursor, business_id, scope_type) or {}
        auth_data.update({
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "sender_scope": scope_type,
        })
        account_id = _save_account(cursor, business_id, auth_data)
        ensure_permissions(cursor, account_id)
        db.conn.commit()
        result = send_code(auth_data)
        auth_data.update({key: value for key, value in result.items() if value is not None})
        auth_data["account_id"] = account_id
        auth_data["business_id"] = business_id
        update_userbot_session(cursor, account_id, auth_data)
        db.conn.commit()
        result_status = str(result.get("status") or "code_sent")
        authorized = result_status == "already_authorized"
        sender_account_id = None
        if authorized:
            sender_account_id = _sync_requested_sender_binding(
                cursor,
                account_id=account_id,
                user_data=user_data,
                scope_type=scope_type,
            )
            db.conn.commit()
        return jsonify({
            "success": True,
            "status": result_status,
            "authorized": authorized,
            "account_id": account_id,
            "sender_account_id": sender_account_id,
            "scope_type": scope_type,
            "phone": mask_phone(phone),
            "message": (
                "Telegram уже подключён. Выберите источники."
                if authorized
                else "Код отправлен в Telegram. Введите его для завершения подключения."
            ),
        })
    except PermissionError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/telegram-research/confirm")
def confirm_research_account(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip()
    password = str(payload.get("password") or "")
    try:
        scope_type = _requested_sender_scope(user_data, payload)
        auth_data = _account_for_scope(cursor, business_id, scope_type)
        if not auth_data:
            return jsonify({"success": False, "error": "Сначала запросите код Telegram"}), 400
        if not code and not (password and auth_data.get("authorization_status") == "password_required"):
            return jsonify({"success": False, "error": "Введите код Telegram"}), 400
        result = confirm_code(auth_data, code, password=password)
        auth_data.update({key: value for key, value in result.items() if value is not None})
        if result.get("status") == "authorized":
            for key in ("phone_code_hash", "pending_session_string", "authorization_status"):
                auth_data.pop(key, None)
        update_userbot_session(cursor, str(auth_data["account_id"]), auth_data)
        ensure_permissions(cursor, str(auth_data["account_id"]))
        sender_account_id = None
        if result.get("status") == "authorized":
            sender_account_id = _sync_requested_sender_binding(
                cursor,
                account_id=str(auth_data["account_id"]),
                user_data=user_data,
                scope_type=scope_type,
            )
        db.conn.commit()
        status = str(result.get("status") or "")
        return jsonify({
            "success": True,
            "status": status,
            "authorized": status == "authorized",
            "password_required": status == "password_required",
            "sender_account_id": sender_account_id,
            "scope_type": scope_type,
            "phone": mask_phone(auth_data.get("phone")),
            "message": "Telegram подключён" if status == "authorized" else "Введите пароль двухэтапной проверки",
        })
    except PermissionError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.get("/api/business/<business_id>/telegram-research/dialogs")
def research_dialogs(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        auth_data = _account_for_business(cursor, business_id)
        if not auth_data or not auth_data.get("session_string"):
            return jsonify({"success": False, "error": "Telegram-аккаунт ещё не подключён"}), 409
        allowed, reason, _context = assert_account_access(
            cursor,
            str(auth_data["account_id"]),
            business_id=business_id,
            scope_type="business",
            capability="radar",
        )
        if not allowed:
            return jsonify({"success": False, "error": "Telegram-радар выключен", "reason_code": reason}), 409
        result = list_dialogs(auth_data, limit=int(request.args.get("limit") or 300))
        if result.get("status") != "ok":
            return jsonify({"success": False, "error": "Нужно заново подключить Telegram"}), 409
        cursor.execute(
            """
            SELECT source.metadata_json->>'telegram_username' AS telegram_username
            FROM knowledge_source_subscriptions subscription
            JOIN knowledge_sources source ON source.id = subscription.source_id
            WHERE subscription.business_id = %s
              AND subscription.is_active = TRUE
              AND source.source_type = 'telegram'
              AND source.visibility = 'public'
            """,
            (business_id,),
        )
        selected = {str(row[0]).lower() for row in cursor.fetchall() if row and row[0]}
        dialogs = []
        for dialog in result.get("dialogs") or []:
            username = str(dialog.get("telegram_username") or "").strip().lstrip("@").lower()
            if not username:
                continue
            dialogs.append({**dialog, "selected": username in selected})
        return jsonify({"success": True, "dialogs": dialogs, "count": len(dialogs)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.get("/api/business/<business_id>/community-sources")
def community_sources(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        cursor.execute(
            """
            SELECT source.id, source.title, source.canonical_url, source.status,
                   source.source_role, source.sync_status, source.last_collected_at, source.next_sync_at,
                   source.last_sync_error, subscription.purposes_json,
                   subscription.topics_json, subscription.schedule_json,
                   (SELECT COUNT(*) FROM knowledge_documents document
                    WHERE document.source_id = source.id AND document.invalidated_at IS NULL) AS documents_count,
                   (SELECT COUNT(DISTINCT link.chunk_id)
                    FROM knowledge_document_chunk_links link
                    JOIN knowledge_documents document ON document.id = link.document_id
                    JOIN knowledge_embedding_chunks chunk ON chunk.id = link.chunk_id
                    WHERE document.source_id = source.id AND document.invalidated_at IS NULL
                      AND chunk.status = 'ready' AND chunk.stale_at IS NULL) AS embeddings_count
            FROM knowledge_source_subscriptions subscription
            JOIN knowledge_sources source ON source.id = subscription.source_id
            WHERE subscription.business_id = %s AND subscription.is_active = TRUE
              AND source.source_type = 'telegram' AND source.visibility = 'public'
            ORDER BY source.last_collected_at DESC NULLS LAST, source.title
            """,
            (business_id,),
        )
        items = []
        columns = [item[0] for item in (cursor.description or [])]
        for row in cursor.fetchall() or []:
            items.append(dict(row) if hasattr(row, "keys") else dict(zip(columns, row)))
        return jsonify({"success": True, "items": items, "count": len(items), "collection_cost_credits": 0})
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/community-sources")
def add_community_source(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    username = _public_telegram_username(payload.get("url") or payload.get("username"))
    if not username:
        db.close()
        return jsonify({"success": False, "error": "Добавьте ссылку на публичный канал или открытую группу вида t.me/name"}), 400
    canonical_url = f"https://t.me/{username}"
    try:
        account = _account_for_business(cursor, business_id)
        title = ""
        entity_type = ""
        verified = False
        if account and account.get("session_string"):
            inspection = inspect_telegram_entity(account, canonical_url)
            entity_type = str(inspection.get("entity_type") or "")
            verified = bool(inspection.get("status") == "ok" and inspection.get("signal_source_eligible") and inspection.get("username"))
            title = str(inspection.get("title") or "")
        if not verified:
            inspection = inspect_public_channel(canonical_url, timeout=8)
            verified = bool(inspection.get("is_public_channel"))
            title = title or str(inspection.get("title") or "")
            entity_type = entity_type or "broadcast_channel"
        if not verified:
            return jsonify({"success": False, "error": "Источник не подтверждён как публичный канал или открытая группа. Личные и закрытые чаты LocalOS не собирает."}), 400

        context = _business_knowledge_context(cursor, business_id)
        requested_role = str(payload.get("source_role") or "community").strip().lower()
        source_role = requested_role if requested_role in {"expert", "salon", "vendor", "community", "service", "competitor"} else "community"
        source = upsert_knowledge_source(
            db.conn,
            source_type="telegram",
            external_key=f"telegram-public:{username}",
            title=title or f"@{username}",
            canonical_url=canonical_url,
            source_role=source_role,
            visibility="public",
            sensitivity_class="public",
            allowed_uses=["market", "localos_content", "client_content", "industry_recommendations"],
            status="active",
            metadata={"telegram_username": username, "telegram_source_type": entity_type, "collector": "public_telegram_preview"},
            business_id=None,
            account_id=None,
            sync_mode="public_preview",
            sync_status="queued",
            backfill_days=90,
        )
        topics = [str(item).strip() for item in payload.get("topics", []) if str(item).strip()][:20] if isinstance(payload.get("topics"), list) else []
        interval_hours = int(payload.get("interval_hours") or 24)
        _subscribe_public_source(
            cursor,
            business_id=business_id,
            source_id=str(source["id"]),
            industry_key=context["industry_key"],
            topics=topics or None,
            interval_hours=interval_hours,
        )
        cursor.execute("UPDATE knowledge_sources SET status = 'active', sync_status = 'queued', next_sync_at = NOW(), updated_at = NOW() WHERE id = %s", (source["id"],))
        db.conn.commit()
        return jsonify({
            "success": True,
            "source": {"id": str(source["id"]), "title": source.get("title"), "canonical_url": canonical_url, "status": "active", "sync_status": "queued"},
            "reused": str(source.get("created_at") or "") != str(source.get("updated_at") or ""),
            "collection_cost_credits": 0,
            "message": "Источник добавлен. Публичные сообщения собираются один раз для всей базы LocalOS.",
        })
    except (TypeError, ValueError):
        db.conn.rollback()
        return jsonify({"success": False, "error": "Выберите доступную частоту обновления"}), 400
    except Exception:
        db.conn.rollback()
        return jsonify({"success": False, "error": "Не удалось проверить источник. Попробуйте ещё раз."}), 400
    finally:
        db.close()


@telegram_research_bp.delete("/api/business/<business_id>/community-sources/<source_id>")
def remove_community_source(business_id: str, source_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        cursor.execute(
            "UPDATE knowledge_source_subscriptions SET is_active = FALSE, updated_at = NOW() WHERE business_id = %s AND source_id = %s",
            (business_id, source_id),
        )
        changed = int(getattr(cursor, "rowcount", 0) or 0)
        db.conn.commit()
        if not changed:
            return jsonify({"success": False, "error": "Источник не найден"}), 404
        return jsonify({"success": True, "source_id": source_id})
    finally:
        db.close()


@telegram_research_bp.patch("/api/business/<business_id>/community-sources/<source_id>")
def update_community_source_subscription(business_id: str, source_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    topics = [str(item).strip() for item in payload.get("topics", []) if str(item).strip()][:20] if isinstance(payload.get("topics"), list) else []
    try:
        interval_hours = int(payload.get("interval_hours") or 24)
        if interval_hours not in {6, 12, 24, 72, 168}:
            return jsonify({"success": False, "error": "Выберите доступную частоту обновления"}), 400
        cursor.execute(
            """
            UPDATE knowledge_source_subscriptions
            SET topics_json = %s,
                schedule_json = %s,
                updated_at = NOW()
            WHERE business_id = %s AND source_id = %s AND is_active = TRUE
            RETURNING source_id, topics_json, schedule_json
            """,
            (Json(topics), Json({"interval_hours": interval_hours}), business_id, source_id),
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"success": False, "error": "Источник не найден"}), 404
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET next_sync_at = LEAST(
                    COALESCE(next_sync_at, NOW()),
                    NOW() + (%s * INTERVAL '1 hour')
                ),
                updated_at = NOW()
            WHERE id = %s
            """,
            (interval_hours, source_id),
        )
        db.conn.commit()
        result = dict(row) if hasattr(row, "keys") else {"source_id": source_id, "topics_json": topics, "schedule_json": {"interval_hours": interval_hours}}
        return jsonify({"success": True, "subscription": result})
    except (TypeError, ValueError):
        db.conn.rollback()
        return jsonify({"success": False, "error": "Выберите доступную частоту обновления"}), 400
    finally:
        db.close()


@telegram_research_bp.put("/api/business/<business_id>/telegram-research/sources")
def save_research_sources(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    try:
        auth_data = _account_for_business(cursor, business_id)
        if not auth_data or not auth_data.get("session_string"):
            return jsonify({"success": False, "error": "Telegram-аккаунт ещё не подключён"}), 409
        allowed, reason, _context = assert_account_access(
            cursor,
            str(auth_data["account_id"]),
            business_id=business_id,
            scope_type="business",
            capability="radar",
        )
        if not allowed:
            return jsonify({"success": False, "error": "Сначала разрешите Telegram-радар", "reason_code": reason}), 409
        knowledge_context = _business_knowledge_context(cursor, business_id)
        selected_source_ids: list[str] = []
        saved: list[dict[str, Any]] = []
        rejected: list[dict[str, str]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            chat_id = str(source.get("telegram_chat_id") or "").strip()
            if not chat_id:
                continue
            username = str(source.get("telegram_username") or "").strip().lstrip("@").lower()
            if not username or str(source.get("visibility") or "").strip().lower() != "public":
                rejected.append({"title": str(source.get("title") or "Telegram"), "reason": "Можно отслеживать только публичные каналы и открытые группы"})
                continue
            allowed_uses = ["market", "localos_content", "client_content", "industry_recommendations"]
            knowledge_source = upsert_knowledge_source(
                db.conn,
                source_type="telegram",
                external_key=f"telegram-public:{username}",
                title=str(source.get("title") or "Telegram"),
                canonical_url=f"https://t.me/{username}",
                source_role="community",
                visibility="public",
                sensitivity_class="public",
                allowed_uses=allowed_uses,
                status="active",
                metadata={
                    "telegram_chat_id": chat_id,
                    "telegram_username": username,
                    "telegram_source_type": str(source.get("source_type") or "chat"),
                    "collector": "public_telegram_preview",
                },
                business_id=None,
                account_id=None,
                sync_mode="public_preview",
                sync_status="queued",
                backfill_days=90,
            )
            selected_source_ids.append(str(knowledge_source["id"]))
            _subscribe_public_source(
                cursor,
                business_id=business_id,
                source_id=str(knowledge_source["id"]),
                industry_key=knowledge_context["industry_key"],
            )
            radar_source = upsert_radar_source(cursor, {
                "business_id": business_id,
                "user_id": _user_id(user_data),
                "account_id": str(auth_data["account_id"]),
                "source": {
                    "telegram_chat_id": chat_id,
                    "telegram_username": username,
                    "title": str(source.get("title") or "Telegram"),
                    "source_type": str(source.get("source_type") or "chat"),
                    "monitor_config": {"keywords": [], "research_enabled": True},
                },
            })
            cursor.execute(
                """
                UPDATE telegram_opportunity_sources
                SET knowledge_source_id = %s, account_id = %s, is_active = TRUE, updated_at = NOW()
                WHERE id = %s
                """,
                (knowledge_source["id"], auth_data["account_id"], radar_source["id"]),
            )
            saved.append({"id": str(knowledge_source["id"]), "title": knowledge_source["title"], "visibility": "public", "collection_cost_credits": 0})
        cursor.execute(
            """
            UPDATE knowledge_source_subscriptions subscription
            SET is_active = FALSE, updated_at = NOW()
            FROM knowledge_sources source
            WHERE source.id = subscription.source_id
              AND subscription.business_id = %s
              AND source.source_type = 'telegram'
              AND NOT (subscription.source_id = ANY(%s::uuid[]))
            """,
            (business_id, selected_source_ids or ["00000000-0000-0000-0000-000000000000"]),
        )
        cursor.execute(
            """
            UPDATE telegram_opportunity_sources
            SET is_active = FALSE, updated_at = NOW()
            WHERE business_id = %s AND account_id = %s
              AND NOT (knowledge_source_id = ANY(%s::uuid[]))
            """,
            (business_id, auth_data["account_id"], selected_source_ids or ["00000000-0000-0000-0000-000000000000"]),
        )
        db.conn.commit()
        return jsonify({"success": True, "sources": saved, "count": len(saved), "rejected": rejected})
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/telegram-research/backfill")
def queue_research_backfill(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        account = _account_for_business(cursor, business_id)
        if not account:
            return jsonify({"success": False, "error": "Telegram-аккаунт ещё не подключён"}), 409
        allowed, reason, _context = assert_account_access(
            cursor,
            str(account["account_id"]),
            business_id=business_id,
            scope_type="business",
            capability="radar",
        )
        if not allowed:
            return jsonify({"success": False, "error": "Telegram-радар выключен", "reason_code": reason}), 409
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET sync_status = 'queued', next_sync_at = NOW(), last_sync_error = NULL,
                cursor_json = cursor_json - 'backfill_before_id', backfill_completed_at = NULL,
                updated_at = NOW()
            WHERE source_type = 'telegram'
              AND status = 'active' AND sync_mode = 'public_preview'
              AND id IN (
                  SELECT source_id FROM knowledge_source_subscriptions
                  WHERE business_id = %s AND is_active = TRUE
              )
            """,
            (business_id,),
        )
        queued = max(int(getattr(cursor, "rowcount", 0) or 0), 0)
        db.conn.commit()
        return jsonify({"success": True, "queued": queued, "message": "Загрузка истории поставлена в очередь"})
    finally:
        db.close()


@telegram_research_bp.get("/api/business/<business_id>/telegram-research/status")
def research_status(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        scope_type = _requested_sender_scope(user_data, request.args)
        account = _account_for_scope(cursor, business_id, scope_type)
        permissions = (
            ensure_permissions(cursor, str(account["account_id"]))
            if account
            else {"radar_enabled": False, "outreach_enabled": False}
        )
        cursor.execute(
            """
            SELECT s.id, s.title, s.visibility, s.status, s.sync_status, s.backfill_days,
                   backfill_completed_at, last_collected_at, next_sync_at, last_sync_error,
                   (SELECT COUNT(*) FROM knowledge_documents d WHERE d.source_id = s.id AND d.invalidated_at IS NULL) AS documents_count
            FROM knowledge_sources s
            JOIN knowledge_source_subscriptions subscription ON subscription.source_id = s.id
            WHERE s.source_type = 'telegram' AND subscription.business_id = %s
              AND subscription.is_active = TRUE
            ORDER BY s.status, s.title
            """,
            (business_id,),
        )
        sources = []
        for row in cursor.fetchall():
            if hasattr(row, "keys"):
                sources.append({key: row[key] for key in row.keys()})
            else:
                columns = [description[0] for description in cursor.description]
                sources.append(dict(zip(columns, row)))
        return jsonify({
            "success": True,
            "scope_type": scope_type,
            "enabled": knowledge_layer_enabled(),
            "account": {
                "configured": bool(account),
                "authorized": bool(account and account.get("session_string")),
                "phone": mask_phone(account.get("phone") if account else ""),
                "account_id": str(account.get("account_id") or "") if account else None,
                "display_name": "Telegram-аккаунт",
                "radar_enabled": bool(permissions.get("radar_enabled")),
                "outreach_enabled": bool(permissions.get("outreach_enabled")),
                "reply_sync_enabled": bool(permissions.get("outreach_enabled")),
                "permissions_updated_at": permissions.get("updated_at"),
            },
            "sources": sources,
            "active_sources": sum(1 for source in sources if source.get("status") == "active"),
        })
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.patch("/api/business/<business_id>/telegram-account/permissions")
def change_account_permissions(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    if "radar_enabled" not in payload and "outreach_enabled" not in payload:
        db.close()
        return jsonify({"success": False, "error": "Передайте хотя бы одно разрешение"}), 400
    for key in ("radar_enabled", "outreach_enabled"):
        if key in payload and not isinstance(payload[key], bool):
            db.close()
            return jsonify({"success": False, "error": f"{key} должно быть boolean"}), 400
    try:
        scope_type = _requested_sender_scope(user_data, payload)
        account = _account_for_scope(cursor, business_id, scope_type)
        if not account:
            return jsonify({"success": False, "error": "Telegram-аккаунт ещё не подключён"}), 404
        account_id = str(account["account_id"])
        permissions = update_permissions(
            cursor,
            account_id,
            radar_enabled=payload.get("radar_enabled"),
            outreach_enabled=payload.get("outreach_enabled"),
            changed_by=_user_id(user_data),
        )
        sender_account_id = _sync_requested_sender_binding(
            cursor,
            account_id=account_id,
            user_data=user_data,
            scope_type=scope_type,
        )
        db.conn.commit()
        return jsonify({
            "success": True,
            "account_id": account_id,
            "permissions": permissions,
            "sender_account_id": sender_account_id,
            "scope_type": scope_type,
            "reply_sync_enabled": bool(permissions.get("outreach_enabled")),
        })
    except PermissionError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.delete("/api/business/<business_id>/telegram-account")
def disconnect_telegram_account(business_id: str):
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        scope_type = _requested_sender_scope(user_data, request.args)
        account = _account_for_scope(cursor, business_id, scope_type)
        if not account:
            return jsonify({"success": False, "error": "Telegram-аккаунт не найден"}), 404
        disconnect_account(cursor, str(account["account_id"]), changed_by=_user_id(user_data))
        db.conn.commit()
        return jsonify({"success": True, "status": "disconnected"})
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/telegram-account/preflight/<capability>")
def telegram_account_preflight(business_id: str, capability: str):
    if capability not in {"radar", "outreach"}:
        return jsonify({"success": False, "error": "Неизвестная функция"}), 404
    db, cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        payload = request.get_json(silent=True) or {}
        scope_type = _requested_sender_scope(user_data, payload)
        account = _account_for_scope(cursor, business_id, scope_type)
        if not account:
            return jsonify({
                "success": True,
                "ready": False,
                "reason_code": "connect_required",
                "scope": {"type": scope_type, "business_id": business_id if scope_type == "business" else None},
            })
        allowed, reason, context = assert_account_access(
            cursor,
            str(account["account_id"]),
            business_id=business_id if scope_type == "business" else None,
            scope_type=scope_type,
            capability=capability,
        )
        if allowed and not account.get("session_string"):
            allowed, reason = False, "authorization_required"
        return jsonify({
            "success": True,
            "ready": allowed,
            "reason_code": reason,
            "account_id": str(account["account_id"]),
            "phone": mask_phone(account.get("phone")),
            "reply_sync_required": capability == "outreach",
            "scope": {
                "type": scope_type,
                "business_id": context.get("business_id") if context and scope_type == "business" else None,
            },
        })
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.get("/api/business/<business_id>/audience-insights")
def audience_insights(business_id: str):
    db, _cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        context = _business_knowledge_context(_cursor, business_id)
        items = list_audience_insights(
            db.conn,
            business_id=business_id,
            industry=context["industry_key"],
            limit=int(request.args.get("limit") or 50),
        )
        return jsonify({
            "success": True,
            "items": items,
            "count": len(items),
            "industry_key": context["industry_key"],
        })
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/audience-insights/<insight_id>/decision")
def audience_insight_decision(business_id: str, insight_id: str):
    db, _cursor, user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    try:
        result = decide_audience_insight(
            db.conn,
            business_id=business_id,
            insight_id=insight_id,
            decision=str(payload.get("decision") or ""),
            user_id=_user_id(user_data),
        )
        db.conn.commit()
        return jsonify({"success": True, "insight": result})
    except LookupError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 404
    except ValueError as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()
