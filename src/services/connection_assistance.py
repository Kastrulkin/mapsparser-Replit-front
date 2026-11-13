"""Connection questions use the existing owner feedback queue."""
import hashlib
import json
import uuid

from core.auth_helpers import verify_business_access
from services.bot_feature_requests import save_bot_feature_request


def create(conn, business_id, user, data):
    if user.get("session_kind") == "demo":
        raise PermissionError("Для запроса помощи войдите в свой аккаунт.")
    if not isinstance(data, dict):
        raise ValueError("Проверьте сообщение.")
    message, service = data.get("message"), data.get("service", "Подключения")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000 or not isinstance(service, str) or not 1 <= len(service) <= 100:
        raise ValueError("Опишите вопрос, до 2000 символов.")
    try:
        request_id = str(uuid.UUID(data.get("request_id", "")))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Обновите форму запроса помощи.")
    cursor = conn.cursor()
    allowed, _ = verify_business_access(cursor, business_id, user)
    if not allowed:
        raise PermissionError("Нет доступа к этому бизнесу.")
    user_id = str(user.get("user_id") or user.get("id"))
    key = "connection-help:" + user_id + ":" + business_id + ":" + request_id
    digest = hashlib.sha256(json.dumps([service, message.strip()]).encode()).hexdigest()
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
    stable_id = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
    cursor.execute("SELECT id,metadata_json FROM botfeaturerequests WHERE id=%s", (stable_id,))
    existing = cursor.fetchone()
    if existing:
        if existing["metadata_json"].get("content_hash") != digest:
            raise ValueError("Сообщение изменилось. Откройте новый запрос.")
        return existing["id"]
    cursor.execute("SELECT name,address FROM businesses WHERE id=%s", (business_id,))
    business = cursor.fetchone()
    result = save_bot_feature_request(conn, telegram_id="", user_id=user_id, business_id=business_id,
        source="dashboard", category="connection_help", request_text=message.strip(),
        request_key=key, commit=False,
        metadata={"service": service, "business_name": business["name"], "address": business["address"],
                  "user_email": user.get("email"), "content_hash": digest})
    return result["id"]


def list_requests(cursor, business_id, user_id=None):
    cursor.execute("""SELECT id,request_text,status,metadata_json,created_at FROM botfeaturerequests
        WHERE business_id=%s AND category='connection_help' AND (%s IS NULL OR user_id=%s)
        ORDER BY created_at DESC LIMIT 20""", (business_id,user_id,user_id))
    return [{**dict(row), "created_at": row["created_at"].isoformat()} for row in cursor.fetchall()]


def update(cursor, business_id, data):
    if not isinstance(data, dict) or data.get("status") not in {"in_progress", "done"}:
        raise ValueError("Выберите статус обращения.")
    cursor.execute("""UPDATE botfeaturerequests SET status=%s,updated_at=NOW()
        WHERE id=%s AND business_id=%s AND category='connection_help' AND status=%s RETURNING id""",
        (data["status"], data.get("id"), business_id, data.get("previous_status")))
    if not cursor.fetchone():
        raise ValueError("Обращение изменилось. Обновите список.")
