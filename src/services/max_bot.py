"""MAX owner control surface over the same LocalOS scope and Operator services."""
import os
import sys
import base64
import json

from core.auth_helpers import verify_business_write_access
from services.max_identity import consume_link_code, consume_link_hash
from services.max_webapp_auth import load_localos_user_for_max
from services.operator_chat_service import process_chat
from services.operator_conversations import _row
from services.operator_core import route_operator_message, confirm_pending_operator_action, reject_pending_operator_action
from services.operator_scope_summary import build_operator_scope_summary
from services.telegram_control_scope import list_control_scopes, resolve_control_scope


class MaxEventDeferred(RuntimeError):
    """A referenced LocalOS job has not committed its terminal state yet."""


def event_actor(payload):
    kind = payload.get("update_type")
    message = payload.get("message") or {}
    if kind == "localos_voice_ready":
        identity = payload.get("max_id")
        return identity if isinstance(identity, str) and identity.isdigit() else None
    if kind in {"bot_started", "bot_stopped"}:
        actor = payload.get("user") or {}
    elif kind == "message_callback":
        if (message.get("recipient") or {}).get("chat_type") != "dialog":
            return None
        actor = (payload.get("callback") or {}).get("user") or {}
    elif kind == "message_created":
        if (message.get("recipient") or {}).get("chat_type") != "dialog":
            return None
        actor = message.get("sender") or {}
    else:
        return None
    identity = actor.get("user_id")
    if type(identity) is not int or identity <= 0 or actor.get("is_bot"):
        return None
    return str(identity)


def app_keyboard(screen="today", scope=None, item_type=None, item_id=None):
    # open_app is resolved by MAX to the mini app registered on this bot.
    bot_name = os.getenv("MAX_BOT_USERNAME", "").strip()
    if not bot_name:
        return []
    navigation = {'screen': screen}
    if scope:
        navigation.update(scope_type=scope.get('kind'), scope_id=scope.get('id'))
    if item_type and item_id:
        navigation.update(item_type=item_type, item_id=item_id)
    start = 'nav_' + base64.urlsafe_b64encode(json.dumps(navigation, separators=(',', ':')).encode()).decode().rstrip('=')
    return [{"type": "inline_keyboard", "payload": {"buttons": [[
        {"type": "link", "text": "Открыть LocalOS", "url": f"https://max.ru/{bot_name}?startapp={start}"}
    ]]}}]


def response(max_id, text, *, buttons=None):
    return {"user_id": max_id, "text": text, "attachments": buttons or app_keyboard()}


def _catalog_response(cursor, max_id, user_id, query=""):
    catalog = list_control_scopes(cursor, user_id=user_id, business_limit=50, search_query=query)
    options = []
    if catalog.get("platform"):
        options.append(("platform", "", "Вся платформа"))
    options.extend(("network", item["id"], item["name"]) for item in catalog.get("networks") or [])
    options.extend(("business", item["id"], item["name"]) for item in catalog.get("businesses") or [])
    buttons = [{"type": "inline_keyboard", "payload": {"buttons": [
        [{"type": "callback", "text": title[:100], "payload": f"scope:{kind}:{identity}"}]
        for kind, identity, title in options[:30]
    ]}}] if options else []
    return response(max_id, "Выберите бизнес или сеть. Полный список доступен в приложении LocalOS.", buttons=buttons + app_keyboard())


def prepare_bot_response(cursor, payload, event_key):
    if payload.get('update_type') == 'localos_support_report':
        actor = load_localos_user_for_max(cursor, payload.get('max_id'))
        if not actor or not actor.get('is_superadmin'):
            return None
        cursor.execute('SELECT notifications_enabled FROM max_identities WHERE max_id=%s AND revoked_at IS NULL', (payload['max_id'],))
        if not _row(cursor, cursor.fetchone()).get('notifications_enabled'):
            return None
        return response(str(payload['max_id']), payload['text'])
    if payload.get('update_type') == 'localos_guest_audit_ready':
        from services.max_guest_audits import prepare_guest_audit_result
        return prepare_guest_audit_result(cursor, payload)
    if payload.get('update_type') == 'localos_notification':
        from services.max_notifications import prepare_notification
        return prepare_notification(cursor, payload)
    max_id = event_actor(payload)
    if not max_id:
        return None
    if payload.get('update_type') == 'localos_voice_ready':
        cursor.execute('''SELECT j.status FROM operator_audio_assets a JOIN operator_async_jobs j ON j.id=a.job_id
            WHERE a.id=%s AND a.business_id=%s''', (payload['asset_id'], payload['business_id']))
        job = _row(cursor, cursor.fetchone())
        if job.get('status') in {'queued', 'running', 'waiting_for_review'}:
            raise MaxEventDeferred()
        if job.get('status') != 'completed':
            return response(max_id, 'Обработка голосовой записи остановлена. Проверьте задание в LocalOS.')
    if payload.get("update_type") == "bot_stopped":
        cursor.execute("UPDATE max_identities SET notifications_enabled=FALSE WHERE max_id=%s", (max_id,))
        cursor.execute("UPDATE max_guest_audits SET notifications_enabled=FALSE WHERE max_id=%s", (max_id,))
        return None
    body = (payload.get("message") or {}).get("body") or {}
    text = str(payload.get('transcript') if payload.get('update_type') == 'localos_voice_ready' else body.get('text') or '').strip()
    callback = str((payload.get("callback") or {}).get("payload") or "")
    if text.startswith('/link '):
        if payload.get('_localos_link_hash'):
            consume_link_hash(cursor, payload['_localos_link_hash'], max_id)
        else:
            consume_link_code(cursor, text.split(maxsplit=1)[1], max_id)
        return response(max_id, "Аккаунт LocalOS подключён. Откройте приложение или выберите бизнес через /businesses.")
    actor = load_localos_user_for_max(cursor, max_id)
    attachments = body.get('attachments') or []
    from services.max_owner_dialogues import prepare_owner_dialogue
    from services.max_inputs import is_audio_attachment
    # Callback events include the original bot message's keyboard/media. Those
    # attachments are not new user input and must not bypass token validation.
    if callback or not attachments or len(attachments) == 1 and attachments[0].get('type') in {'image', 'file'} and not is_audio_attachment(attachments[0]):
        dialogue = prepare_owner_dialogue(cursor, payload, event_key, max_id)
        if dialogue is not NotImplemented:
            return dialogue
    if not actor:
        if text:
            from services.max_guest_audits import request_guest_audit
            report = request_guest_audit(cursor, max_id=max_id, text=text, event_key=event_key)
            if report:
                return response(max_id, report)
        return response(max_id, "Подключите свой аккаунт: получите код на https://localos.pro/dashboard/max и отправьте /link КОД. Если аккаунта нет, сначала зарегистрируйтесь в LocalOS.")
    user_id = str(actor["id"])
    actor["user_id"] = user_id
    if text.startswith('/industry_patterns') or callback.startswith('industry_recalibrate:'):
        from services.max_commands import handle_command
        special = handle_command(cursor, text=text, callback=callback, actor={**actor, 'max_id': max_id}, business_id='platform', subscription={}, event_key=event_key)
        if special: return response(max_id, special['text'], buttons=special.get('buttons'))
    if text in {'/businesses', '/use_business'} or callback == 'businesses':
        return _catalog_response(cursor, max_id, user_id)
    if text.startswith('/use_business '):
        query = text.split(maxsplit=1)[1].strip()
        items = list_control_scopes(cursor, user_id=user_id, business_limit=50, search_query=query).get('businesses') or []
        exact = [item for item in items if str(item.get('id')).lower() == query.lower() or str(item.get('name')).lower() == query.lower()]
        selected_item = exact[0] if len(exact) == 1 else items[0] if len(items) == 1 else None
        if not selected_item:
            return _catalog_response(cursor, max_id, user_id, query)
        callback = 'scope:business:' + str(selected_item['id'])
    if callback.startswith('scope:'):
        parts = callback.split(':', 2)
        if len(parts) != 3:
            raise ValueError('Некорректный выбор бизнеса')
        selected = resolve_control_scope(cursor, user_id=user_id, requested_kind=parts[1], requested_id=parts[2] or None,
                                         persist=True, telegram_id=max_id, platform='max')
        if not selected:
            raise PermissionError('Бизнес или сеть недоступны')
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        return response(max_id, 'Выбран раздел: ' + str(selected.get('name') or 'LocalOS'))
    scope = resolve_control_scope(cursor, user_id=user_id, platform='max')
    if text in {'/help', '/cancel'}:
        if text == '/cancel':
            cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
            from services.operator_conversations import find_latest_operator_conversation, set_operator_pending_context
            if scope and scope.get('kind') == 'business':
                conversation = find_latest_operator_conversation(cursor, business_id=scope['id'], user_id=user_id, channel='max_bot')
                if conversation:
                    set_operator_pending_context(cursor, conversation_id=conversation['id'], context={})
            return response(max_id, 'Текущий шаг отменён. Сохранённые задачи можно проверить в приложении.')
        from services.mobile_bot_menu import MAX_COMMANDS
        return response(max_id, '\n'.join('/' + command + ' — ' + description for command, description in MAX_COMMANDS) + '\nМожно написать поручение, отправить голос, фото или документ.')
    if not scope:
        return _catalog_response(cursor, max_id, user_id)
    if payload.get('update_type') == 'bot_started' or text in {'/start', '/control'}:
        summary = build_operator_scope_summary(cursor, scope=scope, user_id=user_id)
        items = summary.get('attention_items') or []
        lines = [str(scope.get('name') or 'LocalOS')]
        lines.extend(str(item.get('title') or item.get('description') or '') for item in items[:5])
        if not items:
            lines.append('Проверьте задачи и результаты в приложении или напишите поручение.')
        return response(max_id, '\n\n'.join(lines))
    if scope.get('kind') != 'business':
        return response(max_id, 'Для поручения выберите конкретный бизнес через /businesses.')
    business_id = str(scope['id'])
    if payload.get('update_type') == 'localos_voice_ready' and payload.get('business_id') != business_id:
        return response(max_id, 'Выбранный бизнес изменился. Голосовая команда остановлена до выполнения.')
    allowed, owner_id = verify_business_write_access(cursor, business_id, actor)
    if not allowed:
        raise PermissionError('Доступ к бизнесу изменился')
    from api.operator_api import _scope_subscription_access
    from subscription_manager import capability_access_payload
    subscription = _scope_subscription_access(cursor, scope, bool(actor.get('is_superadmin')))
    from services.max_commands import handle_command
    special = handle_command(cursor, text=text, callback=callback, actor={**actor, 'max_id': max_id},
        business_id=business_id, subscription=subscription, event_key=event_key)
    if special and 'operator_message' not in special:
        return response(max_id, special['text'], buttons=special.get('buttons'))
    if special:
        text = special['operator_message']
    elif not callback and not capability_access_payload(subscription, 'operator').get('allowed'):
        return response(max_id, 'Оператор недоступен на текущем тарифе. Проверьте тариф в приложении.')
    if callback.startswith(('confirm:', 'reject:')):
        parts = callback.split(':', 2)
        if len(parts) != 3 or parts[1] != business_id:
            raise PermissionError('Выбранный бизнес изменился. Откройте действие заново.')
        if parts[0] == 'confirm':
            result, _ = confirm_pending_operator_action(cursor, action_id=parts[2], business_id=business_id,
                user_id=user_id, subscription_access=subscription, actor_context=actor)
        else:
            result, _ = reject_pending_operator_action(cursor, action_id=parts[2], business_id=business_id, user_id=user_id)
    else:
        if callback:
            return response(max_id, 'Кнопка больше недоступна. Откройте актуальное действие в LocalOS.')
        attachments = body.get('attachments') or []
        if attachments:
            from services.max_inputs import receive_inputs
            notice = receive_inputs(cursor, attachments, user_id=user_id, business_id=business_id, max_id=max_id, event_key=event_key, caption=text)
            if notice:
                return response(max_id, notice)
        if not text:
            from services.operator_photo_brief import NOTICE
            return response(max_id, NOTICE if all(item.get('type') == 'image' for item in attachments) else
                'Файлы сохранены. Напишите поручение: что нужно сделать с материалами.')
        result = process_chat(cursor, business_id=business_id, user_id=user_id, channel='max_bot', message=text,
            payload={'request_id': 'max:' + event_key, **({'transcription_id': payload['asset_id'], 'conversation_id': payload['conversation_id']} if payload.get('update_type') == 'localos_voice_ready' else {})}, router=route_operator_message,
            subscription_access=subscription, actor_context={**actor,
                'role': 'business_owner' if owner_id == user_id else 'business_user'})
    approval = result.get('approval') or {}
    buttons = app_keyboard()
    if approval.get('action_id'):
        buttons = [{"type": "inline_keyboard", "payload": {"buttons": [[
            {"type": "callback", "text": "Подтвердить", "payload": f"confirm:{business_id}:{approval['action_id']}"},
            {"type": "callback", "text": "Отказаться", "payload": f"reject:{business_id}:{approval['action_id']}"}
        ]]}}] + buttons
    return response(max_id, str(result.get('chat_response') or result.get('message') or 'Результат доступен в LocalOS.'), buttons=buttons)


def split_reply(text):
    """Keep the whole preview; attach approval controls only to its final part."""
    return [text[index:index + 3900] for index in range(0, len(text), 3900)] or ['Результат доступен в LocalOS.']


class MaxDeliveryCancelled(RuntimeError):
    pass


def capture_delivery_guard(cursor, payload):
    max_id = event_actor(payload) or payload.get('max_id')
    if not max_id:
        return None
    actor = load_localos_user_for_max(cursor, max_id)
    if not actor:
        return None  # An unbound guest response contains only public/onboarding data.
    cursor.execute('SELECT linked_at FROM max_identities WHERE max_id=%s AND revoked_at IS NULL', (max_id,))
    binding = _row(cursor, cursor.fetchone())
    scope = resolve_control_scope(cursor, user_id=str(actor['id']), platform='max')
    return {'max_id': str(max_id), 'user_id': str(actor['id']), 'linked_at': str(binding.get('linked_at')),
            'superadmin': bool(actor.get('is_superadmin')),
            'business_ids': [str(payload['business_id'])] if payload.get('business_id') else (scope or {}).get('business_ids') or []}


def check_delivery_guard(cursor, guard):
    if not guard:
        return
    actor = load_localos_user_for_max(cursor, guard['max_id'])
    if not actor or str(actor['id']) != guard['user_id'] or guard['superadmin'] and not actor.get('is_superadmin'):
        raise MaxDeliveryCancelled()
    cursor.execute('SELECT linked_at FROM max_identities WHERE max_id=%s AND revoked_at IS NULL', (guard['max_id'],))
    if str(_row(cursor, cursor.fetchone()).get('linked_at')) != guard['linked_at']:
        raise MaxDeliveryCancelled()
    from core.auth_helpers import verify_business_access
    for business_id in guard['business_ids']:
        if not verify_business_access(cursor, business_id, actor)[0]:
            raise MaxDeliveryCancelled()


def process_next_max_event():
    from database_manager import DatabaseManager
    from services.max_webapp_auth import max_enabled
    from services.max_transport import MaxTransport, MaxTransportError
    from psycopg2.extras import Json
    if not max_enabled():
        return None
    db = DatabaseManager()
    key = None
    sending_intent = False
    try:
        cursor = db.conn.cursor()
        cursor.execute("""UPDATE max_webhook_events SET status='needs_attention',error_code='execution_interrupted'
            WHERE status='processing' AND started_at<NOW()-INTERVAL '10 minutes'""")
        cursor.execute("""SELECT * FROM max_webhook_events WHERE status='pending' AND available_at<=NOW()
            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""")
        event = _row(cursor, cursor.fetchone())
        if not event:
            db.conn.commit()
            return None
        key = event['event_key']
        cursor.execute("UPDATE max_webhook_events SET status='processing',started_at=NOW(),attempts=attempts+1 WHERE event_key=%s", (key,))
        db.conn.commit()
        callback_id = (event['payload_json'].get('callback') or {}).get('callback_id')
        if callback_id:
            try:
                MaxTransport().call('POST', '/answers', params={'callback_id': callback_id}, body={})
            except MaxTransportError:
                pass  # Acknowledgement cannot replay or authorize a business operation.
        cursor.execute('SAVEPOINT max_prepare')
        delivery_guard = None
        try:
            delivery_guard = capture_delivery_guard(cursor, event['payload_json'])
            reply = prepare_bot_response(cursor, event['payload_json'], key)
        except MaxEventDeferred:
            cursor.execute('ROLLBACK TO SAVEPOINT max_prepare')
            cursor.execute("UPDATE max_webhook_events SET status='pending',started_at=NULL,available_at=NOW()+INTERVAL '5 seconds' WHERE event_key=%s", (key,))
            db.conn.commit()
            return key
        except (ValueError, PermissionError):
            cursor.execute('ROLLBACK TO SAVEPOINT max_prepare')
            max_id = event_actor(event['payload_json'])
            reply = response(max_id, 'Не удалось выполнить запрос. Проверьте привязку, выбранный бизнес и доступ или откройте LocalOS.') if max_id else None
        cursor.execute("UPDATE max_webhook_events SET result_json=%s WHERE event_key=%s", (Json(reply), key))
        db.conn.commit()
        if reply:
            if delivery_guard and 'delivery_business_ids' in reply:
                delivery_guard['business_ids'] = reply['delivery_business_ids']
            messages = reply.get('messages') or [{'text': reply['text'], 'attachments': reply['attachments']}]
            mids = []
            for message in messages:
                parts = split_reply(message['text'])
                for index, part in enumerate(parts):
                    check_delivery_guard(cursor, delivery_guard)
                    cursor.execute("UPDATE max_webhook_events SET error_code='delivery_intent' WHERE event_key=%s", (key,))
                    db.conn.commit()
                    sending_intent = True
                    options = {'attachments': message['attachments'] if index == len(parts)-1 else []}
                    if message.get('format'):
                        options['format'] = message['format']
                    if message.get('edit_mid') and index == 0:
                        delivered = MaxTransport().edit(message['edit_mid'], part, **options)
                    else:
                        delivered = MaxTransport().send(reply['user_id'], part, **options)
                    mids.append(delivered['message']['body']['mid'])
                    cursor.execute("UPDATE max_webhook_events SET result_json=result_json || %s WHERE event_key=%s",
                                   (Json({'provider_message_ids': mids}), key))
                    db.conn.commit()
            if reply.get('request_audit_ids'):
                from services.operator_request_history import mark_delivery
                for audit_id in reply['request_audit_ids']:
                    if audit_id: mark_delivery(audit_id, 'delivered')
        cursor.execute("UPDATE max_webhook_events SET status='completed',completed_at=NOW(),error_code=NULL WHERE event_key=%s", (key,))
        db.conn.commit()
        return key
    except Exception:
        error = sys.exception()
        db.conn.rollback()
        if key:
            cursor = db.conn.cursor()
            uncertain = error.uncertain if isinstance(error, MaxTransportError) else sending_intent
            cursor.execute("UPDATE max_webhook_events SET status=%s,error_code=%s WHERE event_key=%s",
                ('needs_attention' if uncertain else 'failed', error.code if isinstance(error, MaxTransportError) else 'delivery_access_revoked' if isinstance(error, MaxDeliveryCancelled) else 'max_processing_failed', key))
            db.conn.commit()
        return None
    finally:
        db.conn.rollback()
        db.close()
