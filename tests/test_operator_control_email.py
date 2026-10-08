import pytest
from services import operator_control_email as control
from services.operator_tool_loop import run_operator_tool_loop

MESSAGE = ('Подготовь одно контрольное письмо на demyanovap@yandex.ru от подключённого localosgo@gmail.com. '
           'Тема: «Проверка отправки LocalOS». Текст: «' + control.BODY + '». Не отправляй до моего подтверждения.')


def test_exact_user_command_and_no_sender_substitution():
    fields = control.parse(MESSAGE)
    assert fields == {'recipient': 'demyanovap@yandex.ru', 'sender': 'localosgo@gmail.com', 'subject': control.SUBJECT, 'body': control.BODY}
    assert control.matches(MESSAGE)
    assert not control.matches('Тестовый ответ получен')


@pytest.mark.parametrize('text', [
    'Подготовь контрольное письмо на demyanovap@yandex.ru',
    'Подготовь контрольное письмо на x@y.ru от x@y.ru',
    'Подготовь контрольное письмо на x@y.ru от from@y.ru. Текст: «Купите тур»',
    'Подготовь контрольное письмо на x@y.ru от from@y.ru. Тема: «A\nB»',
])
def test_ambiguous_or_changed_control_requires_clarification(text):
    with pytest.raises(ValueError):
        control.parse(text)


def test_preview_only_returns_exact_confirmation_no_campaign(monkeypatch):
    monkeypatch.setattr(control, 'load_sender', lambda *a, **k: {'id': 'sender-id'})
    monkeypatch.setattr(control, '_create_campaign', lambda *a, **k: pytest.fail('preview must not create campaign'))
    result = control.preview(None, business_id='riderra', user_id='owner', message=MESSAGE)
    assert result['status'] == 'approval_required'
    env = result['approval']['envelope']
    assert env['review_hash'] == control.digest(env)
    assert 'localosgo@gmail.com' in result['chat_response']
    assert control.BODY in result['chat_response']
    assert not result['external_writes_performed']


@pytest.mark.parametrize('key,value', [('recipient','other@y.ru'),('body','marketing'),('sender','other@y.ru'),('business_id','organica')])
def test_changed_review_is_blocked_before_any_external_action(monkeypatch,key,value):
    env = {**control.parse(MESSAGE), 'business_id': 'riderra', 'user_id': 'owner', 'sender_account_id': 'sender-id'}
    env['review_hash'] = control.digest(env)
    env[key] = value
    monkeypatch.setattr(control, 'load_sender', lambda *a, **k: pytest.fail('must validate review first'))
    assert control.execute(None, business_id='riderra',user_id='owner',envelope=env,action_id='action')['status'] == 'blocked'


def test_revoked_sender_blocks_confirmation(monkeypatch):
    env = {**control.parse(MESSAGE), 'business_id':'riderra','user_id':'owner','sender_account_id':'sender-id'}
    env['review_hash'] = control.digest(env)
    def denied(*a,**k):
        raise ValueError('sender revoked')
    monkeypatch.setattr(control,'load_sender',denied)
    result=control.execute(None,business_id='riderra',user_id='owner',envelope=env,action_id='action')
    assert result['status']=='blocked'
    assert 'revoked' in result['chat_response']


def test_model_only_refusal_is_not_completed():
    result = run_operator_tool_loop(business_id='riderra',user_id='owner',message=MESSAGE,tools=[],
        planner=lambda _: {'action':'final','message':'Не могу подготовить контрольное письмо: такого действия в каталоге нет.'})
    assert result['status']=='unsupported'
    assert result['tool_calls']==0
    assert result['external_writes_performed'] is False


def test_chat_route_uses_control_preview_without_paid_model(monkeypatch):
    from services import operator_core
    monkeypatch.setattr(control,'load_sender',lambda *a,**k:{'id':'sender-id'})
    monkeypatch.setattr(operator_core,'run_paid_operator_tool_loop',lambda *a,**k:pytest.fail('fixed control preview needs no model'))
    result,pending=operator_core.route_operator_message(None,business_id='riderra',user_id='owner',message=MESSAGE,channel='web')
    assert result['status']=='approval_required'
    assert result['capability']==control.CAPABILITY
    assert pending=={}


def test_repeated_confirmation_returns_saved_result_without_new_queue(monkeypatch):
    from services import operator_core
    saved={'status':'completed','delivery_status':'queued','campaign_id':'one-campaign'}
    monkeypatch.setattr(operator_core,'get_operator_action',lambda *a,**k:{'status':'completed','result_json':saved})
    monkeypatch.setattr(control,'execute',lambda *a,**k:pytest.fail('repeat confirmation must not execute'))
    result,repeated=operator_core.confirm_pending_operator_action(None,action_id='action',business_id='riderra',user_id='owner')
    assert repeated is True
    assert result==saved
