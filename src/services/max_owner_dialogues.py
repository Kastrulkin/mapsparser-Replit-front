"""MAX transport for the canonical Telegram owner dialogues, without a second bot.

Every command/callback calls the original handler. Only identity, durable state,
review boundaries and provider I/O differ. No MAX identity is used as Telegram ID.
"""
import asyncio
import base64
import hashlib
import importlib
import json
import os
import secrets
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from psycopg2.extras import Json

from services.owner_bot_context import OwnerBotContext, current_owner_bot
from services.operator_conversations import _row
from services.max_webapp_auth import load_localos_user_for_max
from services.telegram_control_scope import resolve_control_scope


# Telegram-only payment APIs deliberately resolve to LocalOS checkout in MAX.
PLATFORM_REPLACEMENTS = {'crypto_pay_': 'checkout', 'crypto_check_': 'checkout'}


def scope_fingerprint(cursor, max_id, actor, scope):
    cursor.execute('SELECT linked_at FROM max_identities WHERE max_id=%s AND revoked_at IS NULL', (max_id,))
    binding = _row(cursor, cursor.fetchone())
    return hashlib.sha256(json.dumps([str((actor or {}).get('id') or ''), str(binding.get('linked_at') or ''),
        (scope or {}).get('kind'), (scope or {}).get('id')], sort_keys=True).encode()).hexdigest()


def checkout_url(tier=''):
    return 'https://localos.pro/dashboard/profile?' + urlencode({'payment': 'required', 'tier': tier,
        'return_to': '/max/control?screen=settings'}) + '#subscription'


def platform_url(value, *, web_app=False):
    parsed = urlsplit(str(value))
    query = dict(parse_qsl(parsed.query))
    if parsed.netloc in {'localos.pro', 'www.localos.pro'} or not parsed.netloc:
        path = parsed.path.replace('/telegram/control', '/max/control')
        screens = {'operator': 'operator', 'partnerships': 'partnerships', 'content': 'content',
            'work-journal': 'work_journal', 'finance': 'finance', 'progress': 'progress',
            'today': 'today', 'settings': 'settings', 'card': 'cards', 'reviews': 'reviews'}
        route = path.removeprefix('/dashboard/').split('/')[0]
        if route in screens and path.startswith('/dashboard/'):
            query['screen'] = screens[route]
            if route == 'finance' and query.get('section') == 'import':
                query['screen'] = 'finance_import'
            business = query.pop('business_id', None)
            context = current_owner_bot.get()
            if not business and context and context.actor:
                scope = resolve_control_scope(context.cursor, user_id=str(context.actor['id']), platform='max') or {}
                if scope.get('id'):
                    query.update(scope_type=scope['kind'], scope_id=str(scope['id']))
            elif business:
                query.update(scope_type='business', scope_id=business)
            path = '/max/control'
        if path.startswith('/max/control') and os.getenv('MAX_BOT_USERNAME'):
            nav = {key: item for key, item in query.items() if key in {'screen', 'scope_type', 'scope_id', 'item_type', 'item_id'}}
            start = 'nav_' + base64.urlsafe_b64encode(json.dumps(nav, separators=(',', ':')).encode()).decode().rstrip('=')
            return 'https://max.ru/' + os.environ['MAX_BOT_USERNAME'].strip() + '?startapp=' + start
        if path.startswith('/dashboard'):
            query['return_to'] = '/max/control'
        return urlunsplit(('https', 'localos.pro', path, urlencode(query), parsed.fragment))
    return str(value)


def platform_text(value):
    # Drafts and approval previews must reach the user byte-for-byte unchanged.
    return str(value)


class DialogueOutput:
    def __init__(self, payload):
        self.messages = []
        self.callback_mid = str((((payload.get('message') or {}).get('body') or {}).get('mid') or ''))

    async def emit(self, text, *, reply_markup=None, parse_mode=None, edit=False, **kwargs):
        item = {'text': platform_text(text), '_markup': reply_markup,
            **({'format': 'html' if parse_mode == 'HTML' else 'markdown'} if parse_mode else {})}
        if edit and self.callback_mid:
            item['edit_mid'] = self.callback_mid
            previous = next((message for message in self.messages if message.get('edit_mid') == self.callback_mid), None)
            if previous is not None:
                self.messages.remove(previous)
        self.messages.append(item)
        return SimpleNamespace(message_id=0)


class Message:
    def __init__(self, payload, output):
        self._attachments = ((payload.get('message') or {}).get('body') or {}).get('attachments') or []
        body = (payload.get('message') or {}).get('body') or {}
        self.text = str(payload.get('transcript') if payload.get('update_type') == 'localos_voice_ready' else body.get('text') or '')
        self.message_id = str(body.get('mid') or payload.get('_event_key') or 'event')
        self.reply_to_message = None
        self.caption = self.text
        self.photo = []
        self.document = None
        self.voice = None
        for index, attachment in enumerate(self._attachments):
            details = attachment.get('payload') or {}
            media = SimpleNamespace(file_id=str(index), file_name=attachment.get('filename') or details.get('filename') or ('photo.jpg' if attachment.get('type') == 'image' else 'document'), mime_type=details.get('mime_type'), file_size=details.get('size') or 0)
            if attachment.get('type') == 'image': self.photo.append(media)
            elif attachment.get('type') == 'file': self.document = media
        self.output = output

    async def reply_text(self, text, **kwargs):
        return await self.output.emit(text, **kwargs)


class InputBot:
    def __init__(self, message):
        self.message = message

    async def get_file(self, file_id):
        from services.max_inputs import download_input
        attachment = self.message._attachments[int(file_id)]
        content, mime = await asyncio.to_thread(download_input, (attachment.get('payload') or {}).get('url'))
        for media in self.message.photo + ([self.message.document] if self.message.document else []):
            if media.file_id == file_id: media.mime_type = mime
        class File:
            async def download_as_bytearray(self): return bytearray(content)
        return File()


class Callback:
    def __init__(self, data, message, output):
        self.data = data
        self.message = message
        self.output = output

    async def answer(self, *args, **kwargs):
        return None  # Provider callback is acknowledged by the durable worker.

    async def edit_message_text(self, text, **kwargs):
        return await self.output.emit(text, edit=True, **kwargs)


def command_handlers(host):
    # Extract the actual registrations, so future commands cannot silently diverge.
    import ast
    from pathlib import Path
    tree = ast.parse(Path(host.__file__).read_text())
    return {node.args[0].value: getattr(host, node.args[1].id) for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'CommandHandler'
        and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Name)}


def consume_button(token, max_id, revision, fingerprint):
    from database_manager import DatabaseManager
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute('''UPDATE max_dialogue_buttons SET consumed_at=NOW() WHERE token=%s AND max_id=%s
            AND revision=%s AND scope_fingerprint=%s AND consumed_at IS NULL AND expires_at>NOW()
            RETURNING callback_data''', (token, max_id, revision, fingerprint))
        row = _row(cursor, cursor.fetchone())
        db.conn.commit()  # Intent survives a crash or a later business-handler rollback.
        return row.get('callback_data')
    finally:
        db.conn.rollback()
        db.close()


def render_markup(cursor, markup, *, max_id, revision, fingerprint):
    rows = []
    if markup is None:
        return []
    if isinstance(markup, list):  # Existing MAX extension controls.
        for attachment in markup:
            if attachment.get('type') != 'inline_keyboard':
                raise ValueError('Неподдерживаемый элемент меню')
            for row in attachment.get('payload', {}).get('buttons', []):
                rows.append([dict(button) for button in row])
    else:
        for row in markup.inline_keyboard:
            converted = []
            for button in row:
                label = button.text
                callback = button.callback_data
                if callback and callback.startswith('crypto_pay_'):
                    converted.append({'type': 'link', 'text': '💳 Оплата в кабинете LocalOS', 'url': checkout_url(callback.removeprefix('crypto_pay_'))})
                elif callback and callback.startswith('crypto_check_'):
                    converted.append({'type': 'link', 'text': '✅ Проверить оплату в LocalOS', 'url': checkout_url()})
                elif callback:
                    converted.append({'type': 'callback', 'text': label, 'payload': callback})
                elif button.web_app or button.url:
                    converted.append({'type': 'link', 'text': label, 'url': platform_url(button.web_app.url if button.web_app else button.url, web_app=bool(button.web_app))})
                else:
                    raise ValueError('Кнопка не имеет поддерживаемого действия')
            rows.append(converted)
    for row in rows:
        for button in row:
            if button.get('type') == 'callback':
                token = secrets.token_urlsafe(24)
                cursor.execute('''INSERT INTO max_dialogue_buttons(token,max_id,revision,scope_fingerprint,callback_data,expires_at)
                    VALUES (%s,%s,%s,%s,%s,NOW()+INTERVAL '6 hours')''',
                    (token, max_id, revision, fingerprint, button['payload']))
                button['payload'] = 'd:' + token
    # Keep every button; the caller splits oversized keyboards into additional messages.
    return [{'type': 'inline_keyboard', 'payload': {'buttons': rows[index:index+20]}} for index in range(0, len(rows), 20)]


def verify_dialogue_access(cursor, actor, scope, state, callback, command):
    if not actor:
        return
    from services.business_permissions import require_permission
    business_id = (scope or {}).get('id') if (scope or {}).get('kind') == 'business' else None
    stored_business = state.get('business_id')
    if stored_business and str(stored_business) != str(business_id) and state.get('state') not in {'', 'idle'}:
        state.clear()
        state['state'] = 'idle'
        raise PermissionError('Выбранный бизнес изменился. Начните диалог заново.')
    candidate = None
    for prefix in ('business_transaction_', 'business_settings_', 'optimizepick_', 'optmode_openclaw_', 'optmode_legacy_'):
        if callback.startswith(prefix):
            candidate = callback[len(prefix):]
    if callback.startswith('setting_'):
        candidate = callback.split('_', 2)[-1]
    if candidate:
        require_permission(cursor, candidate, actor, 'business.settings.write' if 'setting' in callback else 'operations.write')
        if str(candidate) != str(business_id):
            raise PermissionError('Сначала выберите этот бизнес через общий переключатель')
    if business_id:
        changing = callback.startswith(('setting_', 'business_', 'optmode_', 'openclaw_review_tone_', 'svc_regen_go:', 'operator_confirm:', 'operator_reject:', 'approval_'))
        changing = changing or command not in {'', 'start', 'help', 'control', 'businesses', 'status', 'actions', 'action_status', 'pending_approvals', 'services_audit', 'industry_patterns', 'industry_patterns_impact', 'cancel'} or state.get('state') not in {'', 'idle', 'waiting_control_scope_search'}
        require_permission(cursor, business_id, actor, 'business.settings.write' if callback.startswith('setting_') or str(state.get('state', '')).startswith('waiting_setting_') else 'operations.write' if changing else 'business.read')
        from api.operator_api import _scope_subscription_access
        from subscription_manager import capability_access_payload
        capability = ('finance' if callback.startswith(('menu_transaction', 'business_transaction_')) or state.get('state') == 'waiting_transaction'
            else 'maps.reviews' if command == 'reply_review' or callback.startswith('openclaw_review') or str(state.get('state', '')).startswith('waiting_review_')
            else 'maps.services' if command in {'services_audit', 'optimize_service'} or callback.startswith(('svc_', 'optmode_', 'optimizepick_', 'menu_optimize', 'client_services')) or 'optimize' in str(state.get('state') or '')
            else 'social_content' if command == 'generate_news' or callback == 'openclaw_news_generate_start' or state.get('state') == 'waiting_openclaw_news_text'
            else 'partnerships' if command == 'partnerships' or callback == 'menu_partnerships' else None)
        if capability and not capability_access_payload(_scope_subscription_access(cursor, scope, bool(actor.get('is_superadmin'))), capability).get('allowed'):
            raise PermissionError('Функция недоступна на текущем тарифе')


def prepare_owner_dialogue(cursor, payload, event_key, max_id):
    host = importlib.import_module('telegram_bot')
    actor = load_localos_user_for_max(cursor, max_id)
    scope = resolve_control_scope(cursor, user_id=str(actor['id']), platform='max') if actor else None
    fingerprint = scope_fingerprint(cursor, max_id, actor, scope)
    cursor.execute('''INSERT INTO max_dialogue_states(max_id,user_id) VALUES (%s,%s) ON CONFLICT(max_id) DO NOTHING''', (max_id, (actor or {}).get('id')))
    cursor.execute('SELECT state_json,revision,scope_fingerprint,user_id FROM max_dialogue_states WHERE max_id=%s FOR UPDATE', (max_id,))
    stored = _row(cursor, cursor.fetchone())
    state = stored.get('state_json') or {}
    if stored.get('scope_fingerprint') != fingerprint or str(stored.get('user_id') or '') != str((actor or {}).get('id') or ''):
        state = {}
    revision = int(stored.get('revision') or 0)
    callback = str((payload.get('callback') or {}).get('payload') or '')
    if callback.startswith('d:'):
        callback = consume_button(callback[2:], max_id, revision, fingerprint)
        if callback is None:
            return {'user_id': max_id, 'text': 'Кнопка устарела или решение уже принято. Откройте /start для актуального состояния.', 'attachments': []}
    elif callback:
        # Pre-parity MAX buttons are permitted only through their existing guarded handlers.
        if not callback.startswith(('confirm:', 'reject:', 'scope:', 'diagnostics_decision:', 'orchestrator_decision:', 'industry_recalibrate:', 'feature_category:')) and callback != 'businesses':
            return {'user_id': max_id, 'text': 'Кнопка не подтверждена. Откройте /start.', 'attachments': []}
        return NotImplemented
    output = DialogueOutput(payload)
    message = Message({**payload, '_event_key': event_key}, output)
    command = message.text.split(maxsplit=1)[0].removeprefix('/').split('@')[0] if message.text.startswith('/') else ''
    verify_dialogue_access(cursor, actor, scope, state, callback or '', command)
    runtime = OwnerBotContext(max_id, actor, {max_id: state}, event_key, cursor)
    if payload.get('update_type') == 'localos_voice_ready':
        runtime.input_payload = {'transcription_id': payload['asset_id'], 'conversation_id': payload['conversation_id'], 'request_id': 'voice:' + payload['asset_id']}
    token = current_owner_bot.set(runtime)
    try:
        identity = SimpleNamespace(id=int(max_id), full_name=str((actor or {}).get('name') or ''), username='', is_bot=False)
        update = SimpleNamespace(message=message, effective_message=message, effective_user=identity,
            effective_chat=SimpleNamespace(id=int(max_id), type='private'),
            callback_query=Callback(callback, message, output) if callback else None)
        start_payload = str(payload.get('payload') or '') if payload.get('update_type') == 'bot_started' else ''
        start_args = [start_payload] if start_payload.startswith(('work_', 'content_')) else []
        command_args = message.text.split()[1:]
        if command == 'start' and not (command_args and command_args[0].startswith(('work_', 'content_'))):
            command_args = []  # MAX account linking retains its separate /link boundary.
        context = SimpleNamespace(args=start_args if payload.get('update_type') == 'bot_started' else command_args, bot_data={}, user_data={}, bot=InputBot(message))
        async def dispatch():
            if command == 'industry_patterns_recalibrate' or callback == 'industry_patterns_recalibrate' or callback.startswith('industry_recalibrate:'):
                from services.max_commands import handle_command
                if not actor:
                    await message.reply_text('Команда доступна только суперадминистратору.')
                    return
                result = handle_command(cursor, text='/industry_patterns_recalibrate' if not callback.startswith('industry_recalibrate:') else '',
                    callback=callback if callback.startswith('industry_recalibrate:') else '', actor={**actor, 'max_id': max_id},
                    business_id='platform', subscription={}, event_key=event_key)
                await message.reply_text(result['text'], reply_markup=result.get('buttons'))
            elif callback.startswith(('crypto_pay_', 'crypto_check_')):
                await message.reply_text('Оплатите тариф в кабинете LocalOS и вернитесь в MAX.', reply_markup=[{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'link', 'text': 'Открыть оплату', 'url': checkout_url()}]]}}])
            elif callback in {'openclaw_support_export', 'openclaw_recovery_report'} or command in {'support_export', 'recovery_report', 'approve_action', 'reject_action'} or callback.startswith(('diagnostics_decision:', 'orchestrator_decision:', 'approval_approved_', 'approval_rejected_')):
                from services.max_commands import handle_command
                from api.operator_api import _scope_subscription_access
                if not actor or not scope or scope.get('kind') != 'business':
                    await message.reply_text('Выберите конкретный бизнес через /businesses.')
                    return
                text = '/support_export' if callback == 'openclaw_support_export' else '/recovery_report' if callback == 'openclaw_recovery_report' else message.text
                if callback.startswith(('approval_approved_', 'approval_rejected_')):
                    text = ('/approve_action ' if callback.startswith('approval_approved_') else '/reject_action ') + callback.partition('_')[2].partition('_')[2]
                    callback_argument = ''
                else:
                    callback_argument = callback or ''
                result = handle_command(cursor, text=text, callback=callback_argument, actor={**actor, 'max_id': max_id}, business_id=scope['id'],
                    subscription=_scope_subscription_access(cursor, scope, bool(actor.get('is_superadmin'))), event_key=event_key)
                if result:
                    await message.reply_text(result['text'], reply_markup=result.get('buttons'))
            elif callback:
                await host.button_callback(update, context)
            elif command:
                handler = command_handlers(host).get(command)
                if handler is None:
                    await host.help_command(update, context)
                else:
                    await handler(update, context)
            elif message.photo:
                await host.handle_photo(update, context)
            elif message.document:
                await host.handle_operator_document(update, context)
            elif payload.get('update_type') == 'bot_started':
                await host.start(update, context)
            else:
                await host.handle_text(update, context)
        asyncio.run(dispatch())
        next_scope = resolve_control_scope(cursor, user_id=str(actor['id']), platform='max') if actor else None
        next_fingerprint = scope_fingerprint(cursor, max_id, actor, next_scope)
        revision += 1
        state = runtime.state.get(max_id) or {}
        cursor.execute('''UPDATE max_dialogue_states SET state_json=%s,user_id=%s,scope_fingerprint=%s,revision=%s,updated_at=NOW() WHERE max_id=%s''',
            (Json(state), (actor or {}).get('id'), next_fingerprint, revision, max_id))
        messages = []
        for item in output.messages:
            keyboards = render_markup(cursor, item.pop('_markup'), max_id=max_id, revision=revision, fingerprint=next_fingerprint)
            messages.append({**item, 'attachments': keyboards[:1]})
            messages.extend({'text': 'Продолжение меню', 'attachments': [keyboard]} for keyboard in keyboards[1:])
        if not messages:
            return None
        return {'user_id': max_id, 'text': messages[-1]['text'], 'attachments': messages[-1]['attachments'],
                'messages': messages, 'request_audit_ids': runtime.request_audit_ids,
                'delivery_business_ids': (next_scope or {}).get('business_ids') or []}
    finally:
        current_owner_bot.reset(token)
