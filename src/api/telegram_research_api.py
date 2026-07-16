from __future__ import annotations

import uuid
from typing import Any

from flask import Blueprint, jsonify, request

from auth_encryption import encrypt_auth_data
from core.auth_helpers import require_auth_from_request, verify_business_access
from core.industry_patterns import detect_industry_key
from core.telegram_userbot import (
    confirm_code,
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


telegram_research_bp = Blueprint("telegram_research", __name__)


def _user_id(user_data: dict[str, Any]) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "").strip()


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
    return load_userbot_account(cursor, business_id=business_id)


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


def _save_account(cursor: Any, business_id: str, auth_data: dict[str, Any]) -> str:
    account_id = str(auth_data.get("account_id") or "").strip()
    if account_id:
        update_userbot_session(cursor, account_id, auth_data)
        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET external_id = %s, display_name = 'Telegram-источники', is_active = TRUE, updated_at = NOW()
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
        ) VALUES (%s, %s, 'telegram_app', %s, 'Telegram-источники', %s, TRUE, NOW(), NOW())
        """,
        (account_id, business_id, str(auth_data.get("phone") or ""), encrypted),
    )
    return account_id


def _json_text(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False)


@telegram_research_bp.post("/api/business/<business_id>/telegram-research/connect")
def connect_research_account(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
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
        auth_data = _account_for_business(cursor, business_id) or {}
        auth_data.update({"phone": phone, "api_id": api_id, "api_hash": api_hash})
        account_id = _save_account(cursor, business_id, auth_data)
        db.conn.commit()
        result = send_code(auth_data)
        auth_data.update({key: value for key, value in result.items() if value is not None})
        auth_data["account_id"] = account_id
        auth_data["business_id"] = business_id
        update_userbot_session(cursor, account_id, auth_data)
        db.conn.commit()
        result_status = str(result.get("status") or "code_sent")
        authorized = result_status == "already_authorized"
        return jsonify({
            "success": True,
            "status": result_status,
            "authorized": authorized,
            "account_id": account_id,
            "phone": mask_phone(phone),
            "message": (
                "Telegram уже подключён. Выберите источники."
                if authorized
                else "Код отправлен в Telegram. Введите его для завершения подключения."
            ),
        })
    except Exception as exc:
        db.conn.rollback()
        return jsonify({"success": False, "error": str(exc)}), 400
    finally:
        db.close()


@telegram_research_bp.post("/api/business/<business_id>/telegram-research/confirm")
def confirm_research_account(business_id: str):
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code") or "").strip()
    password = str(payload.get("password") or "")
    try:
        auth_data = _account_for_business(cursor, business_id)
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
        db.conn.commit()
        status = str(result.get("status") or "")
        return jsonify({
            "success": True,
            "status": status,
            "authorized": status == "authorized",
            "password_required": status == "password_required",
            "phone": mask_phone(auth_data.get("phone")),
            "message": "Telegram подключён" if status == "authorized" else "Введите пароль двухэтапной проверки",
        })
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
        result = list_dialogs(auth_data, limit=int(request.args.get("limit") or 300))
        if result.get("status") != "ok":
            return jsonify({"success": False, "error": "Нужно заново подключить Telegram"}), 409
        cursor.execute(
            """
            SELECT metadata_json->>'telegram_chat_id' AS telegram_chat_id
            FROM knowledge_sources
            WHERE source_type = 'telegram' AND account_id = %s AND status = 'active'
            """,
            (auth_data["account_id"],),
        )
        selected = {str(row[0]) for row in cursor.fetchall() if row and row[0]}
        dialogs = []
        for dialog in result.get("dialogs") or []:
            dialogs.append({**dialog, "selected": str(dialog.get("telegram_chat_id") or "") in selected})
        return jsonify({"success": True, "dialogs": dialogs, "count": len(dialogs)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
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
        knowledge_context = _business_knowledge_context(cursor, business_id)
        selected_chat_ids: list[str] = []
        saved: list[dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            chat_id = str(source.get("telegram_chat_id") or "").strip()
            if not chat_id:
                continue
            selected_chat_ids.append(chat_id)
            visibility = "public" if str(source.get("visibility") or "") == "public" else "private"
            username = str(source.get("telegram_username") or "").strip().lstrip("@")
            allowed_uses = (
                ["market", "localos_content", "client_content", "industry_recommendations"]
                if visibility == "public"
                else ["localos_content"]
            )
            knowledge_source = upsert_knowledge_source(
                db.conn,
                source_type="telegram",
                external_key=f"telegram-research:{business_id}:{chat_id}",
                title=str(source.get("title") or "Telegram"),
                canonical_url=f"https://t.me/{username}" if username else None,
                source_role="community",
                visibility=visibility,
                sensitivity_class="public" if visibility == "public" else "tenant_confidential",
                allowed_uses=allowed_uses,
                status="active",
                metadata={
                    "telegram_chat_id": chat_id,
                    "telegram_username": username or None,
                    "telegram_source_type": str(source.get("source_type") or "chat"),
                    "industry_key": knowledge_context["industry_key"],
                    "audience": knowledge_context["audience"],
                },
                business_id=business_id,
                account_id=str(auth_data["account_id"]),
                sync_mode="telegram_userbot",
                sync_status="queued",
                backfill_days=90,
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
            saved.append({"id": str(knowledge_source["id"]), "title": knowledge_source["title"], "visibility": visibility})
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET status = 'paused', sync_status = 'idle', updated_at = NOW()
            WHERE source_type = 'telegram' AND business_id = %s AND account_id = %s
              AND NOT (metadata_json->>'telegram_chat_id' = ANY(%s))
            """,
            (business_id, auth_data["account_id"], selected_chat_ids or ["__none__"]),
        )
        cursor.execute(
            """
            UPDATE telegram_opportunity_sources
            SET is_active = FALSE, updated_at = NOW()
            WHERE business_id = %s AND account_id = %s
              AND NOT (telegram_chat_id = ANY(%s))
            """,
            (business_id, auth_data["account_id"], selected_chat_ids or ["__none__"]),
        )
        db.conn.commit()
        return jsonify({"success": True, "sources": saved, "count": len(saved)})
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
        cursor.execute(
            """
            UPDATE knowledge_sources
            SET sync_status = 'queued', next_sync_at = NOW(), last_sync_error = NULL,
                cursor_json = cursor_json - 'backfill_before_id', backfill_completed_at = NULL,
                updated_at = NOW()
            WHERE source_type = 'telegram' AND business_id = %s
              AND status = 'active' AND sync_mode = 'telegram_userbot'
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
    db, cursor, _user_data, error = _require_business(business_id)
    if error:
        return error
    try:
        account = _account_for_business(cursor, business_id)
        cursor.execute(
            """
            SELECT id, title, visibility, status, sync_status, backfill_days,
                   backfill_completed_at, last_collected_at, next_sync_at, last_sync_error,
                   (SELECT COUNT(*) FROM knowledge_documents d WHERE d.source_id = s.id AND d.invalidated_at IS NULL) AS documents_count
            FROM knowledge_sources s
            WHERE source_type = 'telegram' AND business_id = %s
            ORDER BY status, title
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
            "enabled": knowledge_layer_enabled(),
            "account": {
                "configured": bool(account),
                "authorized": bool(account and account.get("session_string")),
                "phone": mask_phone(account.get("phone") if account else ""),
            },
            "sources": sources,
            "active_sources": sum(1 for source in sources if source.get("status") == "active"),
        })
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
