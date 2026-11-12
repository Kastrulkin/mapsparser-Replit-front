"""Saved connection facts for Operator; never probe providers or load secrets."""
from services.operator_conversations import _row
from services.operator_platform_context import platform_business_id, platform_chat_business


def read_connection_status(cursor, *, business_id, user_id, query="", actor=None):
    platform = business_id == platform_business_id()
    if not business_id:
        raise ValueError("Бизнес не выбран")
    from services.operator_platform_outreach import require_outreach_scope
    require_outreach_scope(cursor, user_id=user_id,
        scope_kind="platform" if platform else "business",
        scope_id=None if platform else business_id, actor=actor)
    term = str(query or "").strip()[:160]
    pattern = "%" + term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    external_where = "COALESCE(business.is_active, TRUE)" if platform else "account.business_id = %s"
    sender_where = "(sender.scope_type = 'platform' OR business.is_active IS DISTINCT FROM FALSE)" if platform else "sender.scope_type = 'business' AND sender.business_id = %s"
    params = () if platform else (business_id,)
    search_params = (pattern, pattern, pattern) if term else ()
    external_search = " AND (business.name ILIKE %s OR account.display_name ILIKE %s OR account.external_id ILIKE %s)" if term else ""
    sender_search = " AND (business.name ILIKE %s OR sender.display_name ILIKE %s OR sender.sender_identity ILIKE %s)" if term else ""
    cursor.execute(f"""SELECT account.id, account.source, account.external_id,
            account.display_name, account.is_active, account.last_sync_at,
            NULLIF(account.last_error, '') IS NOT NULL AS has_error,
            account.updated_at, account.business_id, business.name AS business_name
        FROM externalbusinessaccounts account
        LEFT JOIN businesses business ON business.id = account.business_id
        WHERE {external_where}{external_search}
        ORDER BY account.source, account.id LIMIT 201""", params + search_params)
    external = [_row(cursor, value) for value in cursor.fetchall()]
    cursor.execute(f"""SELECT sender.id, sender.channel, sender.sender_identity,
            sender.display_name, sender.status, sender.scope_type, sender.business_id,
            business.name AS business_name, sender.outreach_enabled,
            COALESCE(sender.capabilities_json->>'reply_sync', 'false') = 'true' AS reply_sync,
            sender.last_reply_sync_at, sender.updated_at,
            NULLIF(sender.reply_sync_error, '') IS NOT NULL AS has_error
        FROM outreach_sender_accounts sender
        LEFT JOIN businesses business ON business.id = sender.business_id
        WHERE {sender_where}{sender_search}
        ORDER BY sender.channel, sender.id LIMIT 201""", params + search_params)
    senders = [_row(cursor, value) for value in cursor.fetchall()]
    accounts = [{
        **account, "connection_type": "external_account",
        "last_error": "Есть ошибка синхронизации. Проверьте подключение." if account.get("has_error") else "",
    } for account in external[:200]]
    accounts.extend({
        "id": str(sender.get("id") or ""), "source": sender.get("channel"),
        "external_id": sender.get("sender_identity"), "display_name": sender.get("display_name"),
        "connection_type": "outreach_sender", "scope_type": sender.get("scope_type"),
        "business_id": sender.get("business_id"), "business_name": sender.get("business_name"),
        "status": sender.get("status"), "is_active": sender.get("status") in {"connected", "attention"},
        "outreach_enabled": bool(sender.get("outreach_enabled")),
        "reply_sync_enabled": bool(sender.get("outreach_enabled") and sender.get("reply_sync")),
        "last_sync_at": sender.get("last_reply_sync_at"), "updated_at": sender.get("updated_at"),
        "has_error": bool(sender.get("has_error")),
        "last_error": "Есть ошибка синхронизации. Проверьте подключение." if sender.get("has_error") else "",
    } for sender in senders[:200])
    truncated = len(external) > 200 or len(senders) > 200
    return {
        "status": "completed", "accounts": accounts, "count": len(accounts),
        "active_count": sum(bool(account.get("is_active")) for account in accounts),
        "error_count": sum(bool(account.get("has_error")) for account in accounts),
        "scope": "platform" if platform else "business", "query": term,
        "has_more": truncated, "absence_is_conclusive": not truncated and not term,
        "lookup_note": "Если нет совпадений по названию или адресу, повторите без фильтра перед выводом об отсутствии подключения." if term else "Показаны подключения выбранной области.",
        "evidence": "Сохранённые подключения LocalOS; проверка входа в почту сейчас не выполнялась.",
        "mail_read_scope": "Синхронизация ответов аутрича не означает доступ ко всей почте ящика.",
        "external_writes_performed": False,
    }
