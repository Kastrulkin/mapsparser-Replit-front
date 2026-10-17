"""Existing journals/queue on loopback PostgreSQL; no external execution."""
import uuid
import pytest
from tests.test_operator_voice_pg import pg
from tests.test_messenger_work_handoff_pg import postgres_container
from tests.test_max_control_pg import max_pg
from tests.test_max_owner_dialogues import dialogues, bind
from services import operator_audio, operator_chat_service, operator_core, operator_partner_work, operator_work_handoff, max_owner_dialogues


def lead_table(cursor):
    cursor.execute('''CREATE TABLE prospectingleads(id TEXT PRIMARY KEY,business_id TEXT,intent TEXT,name TEXT,city TEXT,category TEXT,
        status TEXT,selected_channel TEXT,email TEXT,phone TEXT,telegram_url TEXT,whatsapp_url TEXT,website TEXT,updated_at TIMESTAMPTZ DEFAULT NOW())''')


@pytest.fixture
def partner(pg, monkeypatch):
    conn, c = pg
    c.execute('ALTER TABLE users ADD COLUMN telegram_id TEXT, ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
    c.execute("UPDATE users SET telegram_id='123'")
    c.execute("ALTER TABLE operatorconversations ADD COLUMN input_context_json JSONB DEFAULT '{}'")
    c.execute('ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ')
    c.execute('CREATE TABLE max_identities(user_id TEXT,max_id TEXT,revoked_at TIMESTAMPTZ)')
    c.execute("INSERT INTO max_identities VALUES('u','123',NULL)")
    lead_table(c)
    lead_id = str(uuid.uuid4())
    c.execute("INSERT INTO prospectingleads(id,business_id,intent,name,status,selected_channel,email) VALUES(%s,'b','partnership_outreach','Детская студия','new','email','public@example.test')", (lead_id,))
    c.execute('''CREATE TABLE outreachmessagedrafts(id TEXT PRIMARY KEY,lead_id TEXT,channel TEXT,status TEXT,
        generated_text TEXT,edited_text TEXT,approved_text TEXT,created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW())''')
    c.execute("INSERT INTO outreachmessagedrafts(id,lead_id,channel,status,generated_text) VALUES('draft',%s,'email','draft','Проверенный черновик предложения.')", (lead_id,))
    c.execute('''CREATE TABLE lead_enrichment_jobs(id TEXT PRIMARY KEY,workstream_id TEXT,status TEXT,current_phase TEXT,
        attempt_count INT,max_attempts INT,next_attempt_at TIMESTAMPTZ,allow_paid_enrichment BOOLEAN,created_at TIMESTAMPTZ,updated_at TIMESTAMPTZ)''')
    def authorize(cursor, user_id, business_id, **kwargs):
        if user_id != 'u' or business_id != 'b': raise PermissionError('Denied')
        return {'role': 'business_owner'}, {'capabilities': ['operator', 'partnerships']}
    monkeypatch.setattr(operator_audio, 'authorize_actor', authorize)
    monkeypatch.setenv('MAX_BOT_USERNAME', 'fixture_bot')
    from services import lead_workstream_service
    def resolve(connection, **kwargs):
        assert connection is conn
        assert kwargs['client_business_id'] == 'b' and kwargs['expected_type'] == 'client_partnership'
        assert kwargs['lead_id'] == lead_id
        return {'id': 'workstream'}
    monkeypatch.setattr(lead_workstream_service, 'resolve_workstream', resolve)
    conn.commit()
    return conn, c, lead_id


@pytest.mark.parametrize('channel', ['web', 'telegram', 'telegram_mini_app', 'max_bot', 'max_mini_app'])
@pytest.mark.parametrize('voice', [False, True])
def test_read_prepare_confirm_once_and_resume_exact_partner(partner, channel, voice):
    conn, c, lead_id = partner
    selection = operator_partner_work.partner_selection(c, user_id='u', business_id='b', item_id=lead_id)
    payload = {'request_id': 'read', 'selected_object': {'type': 'partner', 'id': lead_id, 'version': selection['version']}}
    if voice:
        audio = operator_audio.create_transcription(c, content=b'fixture', user_id='u', business_id='b', channel=channel, conversation_id=None, request_id='recording')
        c.execute("UPDATE operator_audio_assets SET status='ready',transcript='Покажи письмо' WHERE id=%s", (audio['asset_id'],))
        c.execute("UPDATE operator_async_jobs SET status='completed' WHERE id=%s", (audio['job_id'],))
        payload.update(transcription_id=audio['asset_id'], conversation_id=audio['conversation_id'])
    arguments = dict(business_id='b', user_id='u', channel=channel, message='Покажи письмо', payload=payload, router=operator_core.route_operator_message)
    read = operator_chat_service.process_chat(c, **arguments); conn.commit()
    repeated = operator_chat_service.process_chat(c, **arguments)
    assert repeated['message_id'] == read['message_id']
    assert 'Проверенный черновик предложения.' in read['chat_response']
    platform = 'max' if channel.startswith('max') else 'telegram'
    assert f'/{platform}/control?screen=partnerships' in read['work_return_url'] and lead_id in read['work_return_url']
    preview = operator_chat_service.process_chat(c, business_id='b', user_id='u', channel=channel,
        message='Подготовь первое письмо', payload={'request_id': 'prepare'}, router=operator_core.route_operator_message)
    assert preview['status'] == 'approval_required'
    c.execute('SELECT COUNT(*) n FROM lead_enrichment_jobs'); assert c.fetchone()['n'] == 0
    action_id = preview['approval']['action_id']; conn.commit()
    result, replay = operator_core.confirm_pending_operator_action(c, action_id=action_id, business_id='b', user_id='u', subscription_access={'capabilities': ['partnerships']})
    assert result['status'] == 'completed' and replay is False
    conn.commit()
    result, replay = operator_core.confirm_pending_operator_action(c, action_id=action_id, business_id='b', user_id='u', subscription_access={'capabilities': ['partnerships']})
    assert replay is True
    c.execute('SELECT status,allow_paid_enrichment FROM lead_enrichment_jobs')
    assert c.fetchall() == [{'status': 'queued', 'allow_paid_enrichment': False}]
    c.execute('SELECT status FROM outreachmessagedrafts'); assert c.fetchone()['status'] == 'draft'
    link = operator_work_handoff.prepare_handoff(c, user_id='u', business_id='b', platform=platform,
        item_id=lead_id, item_type='partner', request_id=str(uuid.uuid4())); conn.commit()
    resumed = operator_work_handoff.resume_handoff(c, user_id='u', token=link['url'].split('start=')[1], platform=platform)
    assert resumed['item_type'] == 'partner' and lead_id in resumed['return_url']


def test_contact_change_invalidates_confirmation_without_creating_job(partner):
    conn, c, lead_id = partner
    selection = operator_partner_work.partner_selection(c, user_id='u', business_id='b', item_id=lead_id)
    preview, _ = operator_partner_work.route(c, user_id='u', business_id='b', selected=selection, message='Подготовь письмо')
    c.execute("UPDATE prospectingleads SET email='changed@example.test' WHERE id=%s", (lead_id,)); conn.commit()
    with pytest.raises(ValueError): operator_partner_work.apply(c, user_id='u', business_id='b', envelope=preview['approval']['envelope'])
    c.execute('SELECT COUNT(*) n FROM lead_enrichment_jobs'); assert c.fetchone()['n'] == 0


def test_max_bot_start_returns_to_partner_not_content(dialogues, monkeypatch):
    bind(dialogues)
    conn = dialogues[0]; c = conn.cursor(); lead_table(c)
    lead_id = str(uuid.uuid4())
    c.execute("INSERT INTO prospectingleads(id,business_id,intent,name,status) VALUES(%s,'b1','partnership_outreach','Студия','new')", (lead_id,))
    c.execute('''CREATE TABLE operatorconversations(id TEXT PRIMARY KEY,business_id TEXT,user_id TEXT,channel TEXT,
        transport_key TEXT,status TEXT DEFAULT 'active',pending_context JSONB DEFAULT '{}',input_context_json JSONB DEFAULT '{}',updated_at TIMESTAMPTZ DEFAULT NOW())''')
    monkeypatch.setenv('MAX_BOT_USERNAME', 'fixture_bot')
    link = operator_work_handoff.prepare_handoff(c, user_id='u1', business_id='b1', platform='max', item_id=lead_id, item_type='partner', request_id=str(uuid.uuid4())); conn.commit()
    reply = max_owner_dialogues.prepare_owner_dialogue(c, {'update_type':'bot_started','payload':link['url'].split('start=')[1],'user':{'user_id':123},'chat_id':123}, 'partner-start', '123')
    assert 'выбранного партнёра' in reply['text']
    buttons = [button for message in reply['messages'] for attachment in message.get('attachments',[]) for row in attachment['payload']['buttons'] for button in row]
    button = next(button for button in buttons if button['text'] == 'Вернуться к партнёру')
    assert button['url'].startswith('https://max.ru/fixture_bot?startapp=nav_')


def test_separate_messenger_approvals_reuse_existing_preparation(partner):
    conn, c, lead_id = partner
    for channel in ['telegram', 'max_bot']:
        selected = operator_partner_work.partner_selection(c, user_id='u', business_id='b', item_id=lead_id)
        preview = operator_chat_service.process_chat(c, business_id='b', user_id='u', channel=channel,
            message='Подготовь письмо', payload={'request_id': 'prepare-' + channel,
                'selected_object': {'type': 'partner', 'id': lead_id, 'version': selected['version']}},
            router=operator_core.route_operator_message)
        conn.commit()
        result, replay = operator_core.confirm_pending_operator_action(c, action_id=preview['approval']['action_id'],
            business_id='b', user_id='u', subscription_access={'capabilities': ['partnerships']})
        assert result['status'] == 'completed' and replay is False
        conn.commit()
    c.execute('SELECT COUNT(*) n FROM lead_enrichment_jobs')
    assert c.fetchone()['n'] == 1
