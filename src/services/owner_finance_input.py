"""Review and atomic application for the owner bot's existing sales input.

Both messengers use the same frozen values; neither reparses a photo after consent.
"""
import json
import secrets
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from services.owner_bot_ui import InlineKeyboardButton, InlineKeyboardMarkup


def freeze_rows(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise ValueError('Нужно от 1 до 100 продаж за один просмотр')
    result = []
    for row in rows:
        try:
            amount = Decimal(str(row.get('amount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            day = date.fromisoformat(str(row.get('transaction_date') or date.today().isoformat()))
        except (InvalidOperation, ValueError):
            raise ValueError('Проверьте сумму и дату продажи в формате ГГГГ-ММ-ДД') from None
        if not amount.is_finite() or amount <= 0 or amount > Decimal('99999999.99'):
            raise ValueError('Сумма продажи должна быть положительной')
        services = row.get('services') or []
        if not isinstance(services, list) or any(not isinstance(item, str) or len(item) > 500 for item in services):
            raise ValueError('Проверьте список услуг')
        result.append({'transaction_date': day.isoformat(), 'amount': str(amount),
            'client_type': 'returning' if row.get('client_type') == 'returning' else 'new',
            'services': [item.strip() for item in services if item.strip()],
            'master_name': str(row.get('master_name') or '').strip()[:500], 'notes': str(row.get('notes') or '')[:4000]})
    return result


async def preview_sales(update, host, external_id, business_id, rows):
    try:
        rows = freeze_rows(rows)
    except ValueError:
        import sys
        await update.message.reply_text(str(sys.exception()))
        return
    nonce = secrets.token_urlsafe(24)
    host.user_states[external_id] = {'state': 'waiting_finance_review', 'business_id': business_id,
        'active_business_id': business_id, 'finance_preview': {'nonce': nonce, 'rows': rows}}
    lines = ['Проверьте продажи перед сохранением:', 'Бизнес: ' + str(business_id)]
    for index, row in enumerate(rows, 1):
        lines.append(f"{index}. {row['transaction_date']} · {row['amount']} ₽ · {row['client_type']}\nУслуги: {', '.join(row['services']) or 'не указаны'}\nМастер: {row['master_name'] or 'не указан'}\nПримечание: {row['notes'] or 'нет'}")
    lines.append('Отсутствующие услуги будут добавлены в выбранный бизнес. Если мастер не найден, продажа сохранится без привязки к мастеру.')
    markup = InlineKeyboardMarkup([[InlineKeyboardButton('Сохранить продажи', callback_data='finance_apply:' + nonce)],
        [InlineKeyboardButton('Отменить', callback_data='finance_cancel:' + nonce)]])
    await update.message.reply_text('\n\n'.join(lines), reply_markup=markup)


def apply_sales(cursor, *, actor, business_id, nonce, rows):
    from services.business_permissions import require_permission
    from services.operator_audio import authorize_actor
    from subscription_manager import capability_access_payload
    from services.operator_conversations import _row
    user_id = str(actor.get('id') or actor.get('user_id'))
    actor, subscription = authorize_actor(cursor, user_id, business_id, require_write=True)
    require_permission(cursor, business_id, actor, 'operations.write')
    if not capability_access_payload(subscription, 'finance').get('allowed'):
        raise PermissionError('Финансы недоступны на текущем тарифе')
    rows = freeze_rows(rows)
    cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', ('owner-sales:' + user_id + ':' + nonce,))
    saved = 0
    for index, row in enumerate(rows):
        transaction_id = str(uuid.uuid5(uuid.NAMESPACE_URL, 'owner-sales:' + user_id + ':' + nonce + ':' + str(index)))
        cursor.execute('SELECT id FROM financialtransactions WHERE id=%s', (transaction_id,))
        if cursor.fetchone():
            continue
        master_id = None
        if row['master_name']:
            cursor.execute('SELECT id FROM masters WHERE business_id=%s AND name=%s ORDER BY id LIMIT 1', (business_id, row['master_name']))
            master = _row(cursor, cursor.fetchone())
            master_id = master.get('id')
        cursor.execute('''INSERT INTO financialtransactions(id,user_id,business_id,transaction_date,amount,client_type,services,notes,master_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',
            (transaction_id, user_id, business_id, row['transaction_date'], row['amount'], row['client_type'], json.dumps(row['services'], ensure_ascii=False), row['notes'], master_id))
        saved += 1
        for name in row['services']:
            cursor.execute('SELECT id FROM userservices WHERE business_id=%s AND name=%s LIMIT 1', (business_id, name))
            if not cursor.fetchone():
                cursor.execute('INSERT INTO userservices(id,user_id,business_id,name) VALUES (%s,%s,%s,%s)',
                    (str(uuid.uuid4()), user_id, business_id, name))
    return saved


async def finance_callback(update, context, host):
    data = update.callback_query.data
    external_id = str(update.effective_user.id)
    state = host.user_states.get(external_id, {})
    preview = state.get('finance_preview') or {}
    if not preview.get('nonce') or not secrets.compare_digest(data.partition(':')[2], preview['nonce']):
        await update.callback_query.edit_message_text('Просмотр устарел. Подготовьте продажи заново.')
        return
    if data.startswith('finance_cancel:'):
        host.user_states[external_id] = {'state': 'idle'}
        await update.callback_query.edit_message_text('Сохранение продаж отменено.')
        return
    scope = host._resolve_telegram_control_scope(external_id)
    if not scope or scope.get('kind') != 'business' or str(scope.get('id')) != str(state.get('business_id')):
        await update.callback_query.edit_message_text('Бизнес изменился. Подготовьте новый просмотр.')
        return
    user_id = host.get_user_id_from_telegram(external_id)
    conn = host.get_db_connection()
    try:
        saved = apply_sales(conn.cursor(), actor={'user_id': user_id}, business_id=scope['id'], nonce=preview['nonce'], rows=preview['rows'])
        conn.commit()
        host.user_states[external_id] = {'state': 'idle'}
        await update.callback_query.edit_message_text('Продажи сохранены. Новых записей: ' + str(saved))
    finally:
        conn.rollback()
        conn.close()
