"""Deterministic command aliases and durable input stages for MAX."""
import json
import hashlib
import secrets

from psycopg2.extras import Json
from services.operator_conversations import _row
from subscription_manager import capability_access_payload

INPUT_COMMANDS = {
    '/reply_review': ('maps.reviews', 'Подготовь ответ на отзыв: ', 'Пришлите текст отзыва.'),
    '/optimize_service': ('maps.services', 'Оптимизируй услугу: ', 'Пришлите название и описание услуги.'),
    '/generate_news': ('content', 'Подготовь новость: ', 'Пришлите тему и факты для новости.'),
}


def save_state(cursor, user_id, business_id, state):
    cursor.execute('''INSERT INTO max_bot_states(user_id,business_id,state_json) VALUES (%s,%s,%s)
        ON CONFLICT(user_id) DO UPDATE SET business_id=EXCLUDED.business_id,state_json=EXCLUDED.state_json,updated_at=NOW()''',
        (user_id, business_id, Json(state)))


def handle_command(cursor, *, text, callback, actor, business_id, subscription, event_key):
    user_id = str(actor['id'])
    cursor.execute('SELECT business_id,state_json FROM max_bot_states WHERE user_id=%s FOR UPDATE', (user_id,))
    stored = _row(cursor, cursor.fetchone())
    state = stored.get('state_json') or {}
    if callback.startswith('industry_recalibrate:'):
        if not actor.get('is_superadmin') or stored.get('business_id') != 'platform' or not secrets.compare_digest(callback.partition(':')[2], str(state.get('industry_nonce') or '')):
            raise PermissionError('Подтверждение устарело или недоступно')
        from core.industry_pattern_recalibration import run_monthly_industry_pattern_recalibration, format_monthly_recalibration_summary
        from services.mobile_diagnostics import run_reviewed_operation_once
        report = run_reviewed_operation_once('industry:' + state['industry_nonce'], lambda: {
            'summary': format_monthly_recalibration_summary(run_monthly_industry_pattern_recalibration(cursor.connection))})
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        return {'text': report}
    if callback.startswith('feature_category:'):
        category = callback.partition(':')[2]
        if category not in {'reviews', 'news', 'partnerships', 'cards', 'analytics', 'other'} or stored.get('business_id') != business_id or state.get('stage') != 'feature_category':
            raise PermissionError('Выбор категории устарел')
        save_state(cursor, user_id, business_id, {'command': '/feature_request', 'category': category})
        return {'text': 'Опишите задачу, которую хотите автоматизировать. Для отмены нажмите /cancel.'}
    if callback.startswith('diagnostics_decision:'):
        if stored.get('business_id') != business_id or not secrets.compare_digest(callback.partition(':')[2], str(state.get('diagnostics_nonce') or '')):
            raise PermissionError('Подтверждение устарело')
        from core.action_orchestrator import ActionOrchestrator
        from services.mobile_diagnostics import build_snapshot, recover, render_snapshot, run_reviewed_operation_once
        orchestrator = ActionOrchestrator()
        auth = {**actor, 'user_id': user_id}
        if state.get('diagnostics_operation') == 'recovery':
            current = build_snapshot(orchestrator, auth, business_id)
            if current['queues'] != state['snapshot']['queues']:
                raise PermissionError('Очередь изменилась. Запросите новый просмотр перед восстановлением.')
            report = run_reviewed_operation_once('diagnostics:' + state['diagnostics_nonce'], lambda: recover(orchestrator, auth, business_id))
            cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
            return {'text': report}
        targets = state.get('targets') or []
        for target in targets:
            # Durable internal deliveries re-check the recipient's current role below.
            cursor.execute("""INSERT INTO max_webhook_events(event_key,payload_json) VALUES (%s,%s)
                ON CONFLICT(event_key) DO NOTHING""", ('support:' + state['diagnostics_nonce'] + ':' + target,
                Json({'update_type': 'localos_support_report', 'max_id': target, 'business_id': business_id,
                      'requested_by': user_id, 'text': render_snapshot(state['snapshot'])})))
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        return {'text': 'Отчёт передан в очередь доставки поддержки. Получателей: ' + str(len(targets))}
    if callback.startswith('orchestrator_decision:'):
        if stored.get('business_id') != business_id or not secrets.compare_digest(callback.partition(':')[2], str(state.get('approval_nonce') or '')):
            raise PermissionError('Подтверждение устарело')
        from core.action_orchestrator import ActionOrchestrator
        cursor.execute('SELECT payload_json,capability FROM action_requests WHERE action_id=%s AND tenant_id=%s', (state['action_id'], business_id))
        current = _row(cursor, cursor.fetchone())
        digest = hashlib.sha256(json.dumps(current, sort_keys=True, default=str).encode()).hexdigest()
        if digest != state['approval_digest']:
            raise PermissionError('Действие изменилось после просмотра')
        value = ActionOrchestrator().resolve_human_decision(state['action_id'], state['decision'], {**actor, 'user_id': user_id}, 'confirmed via MAX')
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        if not value.get('success'):
            raise PermissionError('Не удалось применить решение')
        return {'text': 'Решение сохранено. Статус: ' + str(value.get('status') or '')}
    command, _, arguments = text.partition(' ')
    if not text.startswith('/') and not callback and state.get('command'):
        if stored.get('business_id') != business_id:
            cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
            return {'text': 'Выбранный бизнес изменился. Начните команду заново.'}
        command, arguments = state['command'], text
    if command in INPUT_COMMANDS:
        capability, prefix, prompt = INPUT_COMMANDS[command]
        if not capability_access_payload(subscription, capability).get('allowed'):
            return {'text': 'Функция недоступна на текущем тарифе. Проверьте тариф в LocalOS.'}
        if not arguments.strip():
            save_state(cursor, user_id, business_id, {'command': command})
            return {'text': prompt + ' Для отмены нажмите /cancel.'}
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        return {'operator_message': prefix + arguments}
    if command == '/feature_request':
        if not arguments.strip():
            save_state(cursor, user_id, business_id, {'stage': 'feature_category'})
            return {'text': 'Что хотите автоматизировать?', 'buttons': [{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'callback', 'text': title, 'payload': 'feature_category:' + category}] for category, title in [('reviews', 'Отзывы'), ('news', 'Новости'), ('partnerships', 'Партнёрства'), ('cards', 'Карточки'), ('analytics', 'Аналитика'), ('other', 'Другое')]]}}]}
        from services.bot_feature_requests import save_bot_feature_request
        save_bot_feature_request(cursor.connection, telegram_id='', max_id=actor['max_id'], user_id=user_id,
            business_id=business_id, source='max_bot', category=state.get('category') or 'other', request_text=arguments,
            request_key='max:' + event_key, commit=False)
        cursor.execute('DELETE FROM max_bot_states WHERE user_id=%s', (user_id,))
        return {'text': 'Запрос на автоматизацию сохранён.'}
    if command == '/services_audit':
        if not capability_access_payload(subscription, 'maps.services').get('allowed'):
            return {'text': 'Управление услугами недоступно на текущем тарифе.'}
        from core.service_keyword_scoring import build_services_quality_audit
        cursor.execute('''SELECT id,name,description,optimized_name,optimized_description,keywords FROM userservices
            WHERE business_id=%s AND COALESCE(is_active,TRUE) ORDER BY name''', (business_id,))
        audit = build_services_quality_audit([dict(row) for row in cursor.fetchall()])
        summary = audit.get('summary') or {}
        return {'text': f"Аудит услуг\nПроверено: {summary.get('total', 0)}\nТребуют доработки: {summary.get('needs_review', 0)}\n/optimize_service — подготовить улучшение услуги."}
    if command == '/partnerships':
        return {'operator_message': 'Покажи партнёров и следующие шаги по партнёрствам'}
    if command in {'/approve_action', '/reject_action'}:
        from core.action_orchestrator import ActionOrchestrator
        action_id = arguments.strip()
        value = ActionOrchestrator().get_action(action_id, {**actor, 'user_id': user_id})
        if not value.get('success') or str(value.get('tenant_id') or '') != business_id:
            raise PermissionError('Действие недоступно в выбранном бизнесе')
        cursor.execute('SELECT payload_json,capability FROM action_requests WHERE action_id=%s AND tenant_id=%s', (action_id, business_id))
        current = _row(cursor, cursor.fetchone())
        def public(value):
            if isinstance(value, dict):
                return {key: public(item) for key, item in value.items() if not any(secret in key.lower() for secret in ['token', 'secret', 'password', 'auth_data', 'credential', 'api_key', 'authorization', 'cookie', 'session', 'private_key', 'access_key'])}
            if isinstance(value, list): return [public(item) for item in value]
            return value
        nonce = secrets.token_urlsafe(24)
        save_state(cursor, user_id, business_id, {'approval_nonce': nonce, 'action_id': action_id,
            'decision': 'approved' if command == '/approve_action' else 'rejected',
            'approval_digest': hashlib.sha256(json.dumps(current, sort_keys=True, default=str).encode()).hexdigest()})
        return {'text': 'Проверьте действие перед решением:\n' + json.dumps(public(current), ensure_ascii=False, default=str),
            'buttons': [{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'callback', 'text': 'Подтвердить решение', 'payload': 'orchestrator_decision:' + nonce}]]}}]}
    if command in {'/support_export', '/recovery_report'}:
        from core.action_orchestrator import ActionOrchestrator
        from services.mobile_diagnostics import build_snapshot, render_snapshot
        snapshot = build_snapshot(ActionOrchestrator(), {**actor, 'user_id': user_id}, business_id)
        nonce = secrets.token_urlsafe(24)
        targets = []
        if command == '/support_export':
            cursor.execute("""SELECT m.max_id FROM max_identities m JOIN users u ON u.id=m.user_id
                WHERE m.revoked_at IS NULL AND m.notifications_enabled AND u.is_superadmin AND COALESCE(u.is_active,TRUE)""")
            targets = [str(row['max_id']) for row in cursor.fetchall()]
            if not targets:
                return {'text': render_snapshot(snapshot) + '\nПоддержка MAX не подключена. Отправку выполнить нельзя.'}
        save_state(cursor, user_id, business_id, {'diagnostics_nonce': nonce,
            'diagnostics_operation': 'recovery' if command == '/recovery_report' else 'support',
            'snapshot': snapshot, 'targets': targets})
        description = ('Восстановить до 200 записей retry/DLQ и выполнить их доставку?' if command == '/recovery_report'
            else 'Передать этот отчёт подключённым администраторам поддержки MAX? Получатели: ' + ', '.join(targets))
        return {'text': render_snapshot(snapshot) + '\n' + description,
            'buttons': [{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'callback', 'text': 'Подтвердить', 'payload': 'diagnostics_decision:' + nonce}]]}}]}
    if command in {'/actions', '/action_status', '/pending_approvals', '/status'}:
        from core.action_orchestrator import ActionOrchestrator
        orchestrator = ActionOrchestrator()
        auth = {**actor, 'user_id': user_id}
        if command == '/action_status':
            value = orchestrator.get_action(arguments.strip(), auth)
            if str(value.get('tenant_id') or '') != business_id:
                raise PermissionError('Действие недоступно в выбранном бизнесе')
        elif command == '/status':
            value = orchestrator.get_callback_metrics(auth, tenant_id=business_id, window_minutes=60)
        else:
            value = orchestrator.list_actions(auth, tenant_id=business_id,
                status='pending_human' if command == '/pending_approvals' else None, limit=8, offset=0)
        if not value.get('success'):
            raise PermissionError('Служебный результат недоступен')
        if command == '/status':
            return {'text': 'Состояние автоматизации\n' + json.dumps(value.get('metrics') or {}, ensure_ascii=False)}
        if command == '/action_status':
            return {'text': f"Действие {value.get('action_id')}\n{value.get('capability')}\nСтатус: {value.get('status')}"}
        return {'text': '\n'.join(f"{item.get('action_id')} · {item.get('capability')} · {item.get('status')}" for item in value.get('items') or []) or 'Действий не найдено.'}
    if command in {'/industry_patterns', '/industry_patterns_impact', '/industry_patterns_recalibrate'}:
        if not actor.get('is_superadmin'):
            raise PermissionError('Команда доступна только суперадминистратору')
        from core.industry_pattern_recalibration import (
            summarize_industry_pattern_health, run_monthly_industry_pattern_recalibration,
            format_monthly_recalibration_summary, build_monthly_industry_pattern_impact_report,
            format_monthly_industry_pattern_impact_report,
        )
        if command == '/industry_patterns_recalibrate':
            nonce = secrets.token_urlsafe(24)
            save_state(cursor, user_id, 'platform', {'industry_nonce': nonce})
            return {'text': 'Обновить отраслевые правила по текущим данным? Результат повлияет на последующие рекомендации.', 'buttons': [{'type': 'inline_keyboard', 'payload': {'buttons': [[{'type': 'callback', 'text': 'Обновить правила', 'payload': 'industry_recalibrate:' + nonce}]]}}]}
        if command == '/industry_patterns_impact':
            return {'text': format_monthly_industry_pattern_impact_report(build_monthly_industry_pattern_impact_report(cursor.connection))}
        return {'text': 'Состояние отраслевых правил\n' + json.dumps(summarize_industry_pattern_health(cursor.connection), ensure_ascii=False, default=str)}
    return None
