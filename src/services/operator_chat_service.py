"""Channel-neutral conversation transaction. Callers own commit/rollback."""
import hashlib
import json

from services.operator_conversations import (
    _row, append_operator_message, conversation_pending_context,
    create_pending_operator_action, get_or_create_operator_conversation,
    list_operator_messages, list_pending_operator_actions, set_operator_pending_context, find_latest_operator_conversation,
)


def process_chat(cursor, *, business_id, user_id, channel, message, router,
                 payload=None, actor_context=None, subscription_access=None,
                 refresh_handler=None, ai_router_handler=None, manual_review_handler=None):
    payload = payload or {}
    if not isinstance(message, str) or not message.strip() or len(message) > 10000 or len(str(payload.get("request_id") or "")) > 200:
        raise ValueError("Проверьте длину команды и идентификатор запроса")
    if channel not in {"web", "telegram", "telegram_mini_app"}:
        raise ValueError("Неизвестный канал")
    # Lock before resolving the active conversation, including first-message races.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                   (f"operator:{user_id}:{business_id}:{channel}",))
    selected_id = payload.get('conversation_id')
    if not selected_id:
        selected_id = find_latest_operator_conversation(cursor,business_id=business_id,user_id=user_id,channel=channel).get('id')
    conversation = get_or_create_operator_conversation(
        cursor, business_id=business_id, user_id=user_id, channel=channel,
        conversation_id=selected_id,
        transport_key=f"chat:{user_id}:{business_id}:{channel}",
    )
    conversation_id = str(conversation.get("id") or "")
    request_id = str(payload.get("request_id") or "").strip()
    digest = hashlib.sha256(json.dumps([message, payload.get("transcription_id"), payload.get("url")], ensure_ascii=False).encode()).hexdigest()
    if payload.get("input_context"):
        digest = hashlib.sha256((digest + str(payload["input_context"])).encode()).hexdigest()
    if payload.get("work_change_hash"):
        digest = hashlib.sha256((digest + str(payload["work_change_hash"])).encode()).hexdigest()
    if request_id:
        cursor.execute("SELECT * FROM operator_chat_requests WHERE user_id=%s AND business_id=%s AND channel=%s AND request_id=%s FOR UPDATE",
                       (user_id, business_id, channel, request_id))
        previous = _row(cursor, cursor.fetchone())
        if previous:
            if previous.get("input_hash") != digest:
                raise ValueError("Идентификатор запроса уже использован для другого текста")
            return {**previous.get("result_json", {}), "idempotent": True}
    transcript = payload.get("transcription_id")
    if transcript:
        from services.operator_audio import consume_transcription
        consume_transcription(cursor, transcript, user_id, business_id, conversation_id, message)
    user_message_id = append_operator_message(cursor, conversation_id=conversation_id, business_id=business_id,
                            user_id=user_id, role="user", content=message,
                            result={"input_type": "voice" if transcript else "text", "transcription_id": transcript})
    result, pending = router(
        cursor, business_id=business_id, user_id=user_id, channel=channel, message=message,
        conversation_id=conversation_id, pending_context=conversation_pending_context(conversation),
        conversation_history=list_operator_messages(cursor, conversation_id=conversation_id, business_id=business_id, limit=12),
        pending_approvals=list_pending_operator_actions(cursor, conversation_id=conversation_id, business_id=business_id, user_id=user_id),
        actor_context=actor_context, subscription_access=subscription_access,
        action_payload=payload, explicit_url=payload.get("url"), limit=payload.get("limit") or 5,
        refresh_handler=refresh_handler, ai_router_handler=ai_router_handler, manual_review_handler=manual_review_handler,
    )
    result["conversation_id"] = conversation_id
    approval = result.get("approval") or {}
    if result.get("status") == "approval_required" and approval.get("envelope"):
        action = create_pending_operator_action(cursor, conversation_id=conversation_id,
            business_id=business_id, user_id=user_id, capability=result.get("capability") or result.get("intent") or "unknown",
            envelope=approval["envelope"], request_key=f"{conversation_id}:{request_id or user_message_id}")
        approval["action_id"] = str(action.get("id") or "")
        result["approval"] = approval
        cursor.execute("UPDATE operatoractions SET expires_at=COALESCE(expires_at,NOW()+INTERVAL '30 minutes') WHERE id=%s", (approval['action_id'],))
        cursor.execute("UPDATE operatoractions SET status='rejected',updated_at=NOW() WHERE conversation_id=%s AND capability=%s AND status='pending_approval' AND id<>%s", (conversation_id,result.get('capability') or result.get('intent') or 'unknown',approval['action_id']))
    set_operator_pending_context(cursor, conversation_id, pending)
    result["input_type"] = "voice" if transcript else "text"
    message_id = append_operator_message(cursor, conversation_id=conversation_id, business_id=business_id,
        user_id=user_id, role="operator", content=result.get("chat_response") or result.get("summary"),
        capability=result.get("capability"), status=result.get("status"), result=result)
    result["message_id"] = message_id
    cursor.execute("UPDATE operatormessages SET result_json=%s::jsonb WHERE id=%s", (json.dumps(result, ensure_ascii=False, default=str), message_id))
    if request_id:
        cursor.execute("INSERT INTO operator_chat_requests (user_id,business_id,channel,request_id,input_hash,result_json) VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                       (user_id,business_id,channel,request_id,digest,json.dumps(result,ensure_ascii=False,default=str)))
    return result
