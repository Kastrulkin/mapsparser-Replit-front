"""MAX drives the actual Telegram dialogue handlers; all provider I/O is replaced."""
import asyncio
import ast
import importlib
import json
from pathlib import Path

import pytest
from psycopg2.extras import Json

from tests.test_max_control_pg import max_pg
from services import max_owner_dialogues
from services.owner_bot_context import OwnerBotContext, current_owner_bot, owner_bot_channel


@pytest.fixture
def dialogues(max_pg, monkeypatch):
    connection, connect = max_pg
    import database_manager
    from services import business_permissions, operator_audio
    import subscription_manager
    from api import operator_api
    host = importlib.import_module('telegram_bot')
    cursor = connection.cursor()
    cursor.execute('''CREATE TABLE businesses(id TEXT PRIMARY KEY,owner_id TEXT,name TEXT,address TEXT,working_hours TEXT,
        phone TEXT,yandex_url TEXT,network_id TEXT,is_active BOOLEAN DEFAULT TRUE,updated_at TIMESTAMPTZ)''')
    cursor.execute("INSERT INTO businesses(id,owner_id,name) VALUES ('b1','u1','My business'),('b2','u2','Other')")
    cursor.execute('CREATE TABLE business_members(business_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    cursor.execute('CREATE TABLE network_members(network_id TEXT,user_id TEXT,status TEXT,role TEXT)')
    cursor.execute('CREATE TABLE networks(id TEXT,owner_id TEXT)')
    cursor.execute('CREATE TABLE masters(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,name TEXT)')
    cursor.execute('CREATE TABLE userservices(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,name TEXT)')
    cursor.execute('''CREATE TABLE financialtransactions(id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,transaction_date DATE,
        amount NUMERIC,client_type TEXT,services TEXT,notes TEXT,master_id TEXT)''')
    connection.commit()
    class Database:
        def __init__(self): self.conn = connect()
        def close(self): self.conn.close()
    monkeypatch.setattr(database_manager, 'DatabaseManager', Database)
    from services import operator_telegram_voice
    monkeypatch.setattr(operator_telegram_voice, 'DatabaseManager', Database)
    monkeypatch.setattr(host, 'get_db_connection', connect)
    selection = {'scope': None}
    monkeypatch.setattr(max_owner_dialogues, 'resolve_control_scope', lambda *args, **kwargs: selection['scope'])
    monkeypatch.setattr(host, '_resolve_telegram_control_scope', lambda *args, **kwargs: selection['scope'])
    monkeypatch.setattr(operator_api, '_scope_subscription_access', lambda *args: {})
    monkeypatch.setattr(subscription_manager, 'capability_access_payload', lambda *args: {'allowed': True})
    monkeypatch.setattr(host, 'get_subscription_info', lambda *args, **kwargs: {})
    def authorize(cursor, user_id, business_id, **kwargs):
        actor = {'user_id': user_id, 'id': user_id, 'is_superadmin': False}
        business_permissions.require_permission(cursor, business_id, actor, 'operations.write')
        return actor, {}
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize)
    yield connection, connect, host, selection


def receive(dialogues, text='', callback='', identity='123'):
    connection = dialogues[0]
    payload = {'update_type': 'message_callback' if callback else 'message_created', 'message': {
        'body': {'mid': 'input-mid', 'text': text}, 'recipient': {'chat_type': 'dialog'}}}
    if callback: payload['callback'] = {'payload': callback, 'callback_id': 'callback'}
    result = max_owner_dialogues.prepare_owner_dialogue(connection.cursor(), payload, 'event-' + str(uuid_value()), identity)
    connection.commit()
    return result


def uuid_value():
    import uuid
    return uuid.uuid4().hex


def button(reply, label):
    for message in reply['messages']:
        for attachment in message.get('attachments') or []:
            for row in attachment['payload']['buttons']:
                for item in row:
                    if label in item['text']: return item['payload']
    raise AssertionError('Missing button: ' + label)


def bind(dialogues):
    from services.max_identity import issue_link_code, consume_link_code
    cursor = dialogues[0].cursor()
    consume_link_code(cursor, issue_link_code(cursor, 'u1'), '123')
    dialogues[0].commit()
    dialogues[3]['scope'] = {'kind': 'business', 'id': 'b1', 'name': 'My business', 'business_ids': ['b1']}


def test_all_registered_commands_use_the_actual_telegram_handlers(dialogues):
    host = dialogues[2]
    commands = max_owner_dialogues.command_handlers(host)
    from services.mobile_bot_menu import MAX_COMMANDS
    assert set(commands) == {command for command, _ in MAX_COMMANDS}
    assert commands['reply_review'] is host.reply_review_command
    assert commands['generate_news'] is host.generate_news_command
    assert commands['industry_patterns'] is host.industry_patterns_command


def test_guest_menu_and_compare_stages_survive_reopening_connection(dialogues, monkeypatch):
    reply = receive(dialogues, '/start')
    compare = button(reply, 'Сравнить')
    reply = receive(dialogues, callback=compare)
    assert 'Сначала пришлите ссылку' in reply['text']
    reply = receive(dialogues, 'https://yandex.ru/maps/org/salon/123456789/')
    assert 'конкурента' in reply['text']
    host = dialogues[2]
    monkeypatch.setattr(host, '_start_public_report_request', lambda identity, url, source: (True, {'public_url': 'https://localos.pro/report', 'slug': 'report'}))
    seen = []
    monkeypatch.setattr(host, 'build_guest_compare_result', lambda own_url, competitor_url, **reports: seen.append((own_url, competitor_url)) or 'Карточки сравнены')
    reply = receive(dialogues, 'https://yandex.ru/maps/org/competitor/987654321/')
    assert 'Карточки сравнены' in reply['text']
    assert len(seen) == 1 and '123456789' in seen[0][0] and '987654321' in seen[0][1]


def test_same_numeric_identity_cannot_read_telegram_binding_or_state(dialogues, monkeypatch):
    host = dialogues[2]
    host.user_states.telegram_states['123'] = {'state': 'telegram-only'}
    context = OwnerBotContext('123', {'id': 'u1'}, {'123': {'state': 'max-only'}}, 'e', dialogues[0].cursor())
    token = current_owner_bot.set(context)
    try:
        monkeypatch.setattr(host, 'get_db_connection', lambda: pytest.fail('MAX must not query users.telegram_id'))
        assert host.get_user_id_from_telegram('123') == 'u1'
        assert host.user_states['123']['state'] == 'max-only'
        assert asyncio.run(asyncio.to_thread(owner_bot_channel)) == 'max_bot'
        host.user_states['123'] = {'state': 'idle'}
        assert host.user_states.telegram_states['123']['state'] == 'telegram-only'
        with pytest.raises(PermissionError): host.get_user_id_from_telegram('456')
    finally:
        current_owner_bot.reset(token)
        host.user_states.telegram_states.pop('123', None)


def test_review_tone_buttons_match_and_click_runs_once(dialogues, monkeypatch):
    bind(dialogues)
    host = dialogues[2]
    calls = []
    monkeypatch.setattr(host, '_perform_reviews_reply', lambda context, text, tone: calls.append((context, text, tone, owner_bot_channel())) or (True, 'Ответ готов'))
    monkeypatch.setattr(host, '_compose_openclaw_followup', lambda identity, text: (text, host._build_reviews_menu()))
    reply = receive(dialogues, '/reply_review Хороший салон')
    control = button(reply, 'Профессиональный')
    assert 'Выберите тон' in reply['text']
    reply = receive(dialogues, callback=control)
    assert 'Ответ готов' in reply['text']
    assert calls[0][1:] == ('Хороший салон', 'professional', 'max_bot')
    repeated = receive(dialogues, callback=control)
    assert 'устарела' in repeated['text'] and len(calls) == 1


def test_button_from_another_user_or_scope_never_executes(dialogues):
    bind(dialogues)
    reply = receive(dialogues, '/reply_review Отзыв')
    control = button(reply, 'Деловой')
    assert 'устарела' in receive(dialogues, callback=control, identity='456')['text']
    dialogues[3]['scope'] = {'kind': 'business', 'id': 'b2', 'name': 'Other', 'business_ids': ['b2']}
    assert 'устарела' in receive(dialogues, callback=control)['text']


def test_cancel_clears_max_form_but_preserves_telegram_form(dialogues):
    bind(dialogues)
    host = dialogues[2]
    host.user_states.telegram_states['123'] = {'state': 'telegram-form'}
    receive(dialogues, '/reply_review')
    reply = receive(dialogues, '/cancel')
    assert 'отменены' in reply['text']
    cursor = dialogues[0].cursor()
    cursor.execute("SELECT state_json FROM max_dialogue_states WHERE max_id='123'")
    assert cursor.fetchone()['state_json']['state'] == 'idle'
    assert host.user_states.telegram_states.pop('123')['state'] == 'telegram-form'


def test_every_source_button_shape_is_preserved_and_callbacks_are_bound(dialogues):
    host = dialogues[2]
    tree = ast.parse(Path(host.__file__).read_text())
    originals, rows = [], []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'InlineKeyboardButton':
            fields = {item.arg: item.value for item in node.keywords}
            if 'callback_data' in fields:
                callback = ast.unparse(fields['callback_data'])
                originals.append(callback)
                rows.append([host.InlineKeyboardButton('Source button', callback_data=callback)])
            else:
                rows.append([host.InlineKeyboardButton('Source link', url='https://localos.pro/telegram/control?screen=reviews')])
    rendered = max_owner_dialogues.render_markup(dialogues[0].cursor(), host.InlineKeyboardMarkup(rows), max_id='123', revision=1, fingerprint='fingerprint')
    assert sum(len(row) for item in rendered for row in item['payload']['buttons']) == len(rows)
    controls = [button for item in rendered for row in item['payload']['buttons'] for button in row if button['type'] == 'callback']
    assert len(controls) == len(originals) and all(len(item['payload']) < 64 for item in controls)
    cursor = dialogues[0].cursor()
    cursor.execute("SELECT callback_data FROM max_dialogue_buttons WHERE max_id='123'")
    assert sorted(row['callback_data'] for row in cursor.fetchall()) == sorted(originals)


def test_finance_requires_review_and_double_click_cannot_duplicate(dialogues, monkeypatch):
    bind(dialogues)
    receive(dialogues, '/start')
    cursor = dialogues[0].cursor()
    cursor.execute("UPDATE max_dialogue_states SET state_json=%s WHERE max_id='123'", (Json({'state': 'waiting_transaction', 'business_id': 'b1'}),))
    dialogues[0].commit()
    reply = receive(dialogues, 'Дата: 2026-10-15\nСумма: 1200\nУслуга: Стрижка')
    cursor.execute('SELECT COUNT(*) AS n FROM financialtransactions')
    assert cursor.fetchone()['n'] == 0
    apply = button(reply, 'Сохранить продажи')
    reply = receive(dialogues, callback=apply)
    assert 'Новых записей: 1' in reply['text']
    receive(dialogues, callback=apply)
    cursor.execute('SELECT business_id,amount FROM financialtransactions')
    assert [(row['business_id'], int(row['amount'])) for row in cursor.fetchall()] == [('b1', 1200)]
    cursor.execute('SELECT COUNT(*) AS n FROM userservices')
    assert cursor.fetchone()['n'] == 1


def test_finance_foreign_business_is_denied_before_write(dialogues):
    from services.owner_finance_input import apply_sales
    cursor = dialogues[0].cursor()
    with pytest.raises(PermissionError):
        apply_sales(cursor, actor={'user_id': 'u1'}, business_id='b2', nonce='test', rows=[{'amount': '1200'}])
    cursor.execute('SELECT COUNT(*) AS n FROM financialtransactions')
    assert cursor.fetchone()['n'] == 0


@pytest.mark.parametrize('setting,value,column', [('phone', '+7 999 123 45 67', 'phone'), ('maps', 'https://yandex.ru/maps/org/salon/123456789/', 'yandex_url')])
def test_settings_really_update_phone_and_map_without_false_success(dialogues, setting, value, column):
    from services.owner_bot_context import update_business_setting
    cursor = dialogues[0].cursor()
    update_business_setting(cursor, user_id='u1', business_id='b1', setting=setting, text=value)
    cursor.execute('SELECT ' + column + ' AS value FROM businesses WHERE id=%s', ('b1',))
    assert cursor.fetchone()['value'] == ('https://yandex.ru/maps/org/salon/123456789' if setting == 'maps' else value)
    with pytest.raises(PermissionError):
        update_business_setting(cursor, user_id='u1', business_id='b2', setting=setting, text=value)


def test_dialogues_import_without_telegram_sdk_or_httpx():
    import subprocess, sys, os
    script = '''
import importlib.abc,sys,io,contextlib
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname in {'telegram','httpx'} or fullname.startswith(('telegram.','httpx.')):
   raise ModuleNotFoundError(name=fullname)
sys.meta_path.insert(0,Block())
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
 import telegram_bot
 from services.owner_bot_ui import InlineKeyboardButton
 assert InlineKeyboardButton('test',callback_data='test').text == 'test'
print('portable-owner-dialogue-ok')
'''
    root = Path(__file__).parents[1]
    result = subprocess.run([sys.executable, '-c', script], cwd=root,
        env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(root/'src'), 'PYTHON_DOTENV_DISABLED': '1'},
        capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr[-1000:]
    assert result.stdout.strip() == 'portable-owner-dialogue-ok'


def test_administrator_recalibration_keeps_review_before_execution(dialogues, monkeypatch):
    bind(dialogues)
    connection = dialogues[0]
    connection.cursor().execute("UPDATE users SET is_superadmin=TRUE WHERE id='u1'")
    connection.commit()
    from core import industry_pattern_recalibration
    calls = []
    monkeypatch.setattr(industry_pattern_recalibration, 'run_monthly_industry_pattern_recalibration', lambda *args: calls.append('run') or {})
    monkeypatch.setattr(industry_pattern_recalibration, 'format_monthly_recalibration_summary', lambda report: 'Правила обновлены')
    preview = receive(dialogues, '/industry_patterns_recalibrate')
    assert not calls
    confirm = button(preview, 'Обновить правила')
    assert confirm.startswith('d:')
    applied = receive(dialogues, callback=confirm)
    assert 'Правила обновлены' in applied['text'] and calls == ['run']
    receive(dialogues, callback=confirm)
    assert calls == ['run']


def test_cancel_failure_does_not_claim_pending_actions_were_rejected(dialogues,monkeypatch):
    from services import operator_telegram_voice
    bind(dialogues)
    def failed_transaction(operation):
        raise RuntimeError('Synthetic database outage')
    monkeypatch.setattr(operator_telegram_voice,'transaction',failed_transaction)
    reply=receive(dialogues,'/cancel')
    assert 'не все действия удалось отклонить' in reply['text']
