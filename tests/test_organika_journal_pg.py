import pytest
from tests.test_operator_voice_pg import pg
from tests.test_finance_daily_pg import daily
from tests.test_work_journal_pg import journal
from tests.test_work_review_pg import review
from services import operator_followups,operator_chat_service,work_review

@pytest.mark.parametrize('channel',['web','telegram','telegram_mini_app'])
def test_note_edit_cancel_and_replay(review,channel):
    _,c=review
    def router(cursor,**kw):
        return operator_followups.route(cursor,business_id='b',user_id='u',channel=channel,message=kw['message'],history=kw['conversation_history'],conversation_id=kw['conversation_id'],payload=kw['action_payload'],actor={},access=None)
    args=dict(business_id='b',user_id='u',channel=channel,router=router)
    first=operator_chat_service._process_chat(c,**args,message='Пожелание клиента: напоминать за три часа. Передай администратору.',payload={'request_id':'first'})
    payload={'request_id':'edit','conversation_id':first['conversation_id']}
    changed=operator_chat_service._process_chat(c,**args,message='Исправь эту заметку: напоминать за пять часов.',payload=payload)
    assert changed['journal_entries'][0]['id']==first['journal_entries'][0]['id']
    assert changed['journal_entries'][0]['version']==2
    assert 'пять' in changed['journal_entries'][0]['facts_json']['quote']
    duplicate=operator_chat_service._process_chat(c,**args,message='Исправь эту заметку: напоминать за пять часов.',payload=payload)
    assert duplicate['idempotent']
    cancelled=operator_chat_service._process_chat(c,**args,message='Отмени эту заметку.',payload={'request_id':'void','conversation_id':first['conversation_id']})
    assert cancelled['journal_entries'][0]['is_voided']
    assert not work_review.list_inbox(c,'b','u')


def test_two_observations_are_independent_review_items(review):
    _,c=review
    source='Передай руководителю два замечания: первый клиент пожаловался на грязный салон. Второй попросил более удобное кресло.'
    value,_=operator_followups.route(c,business_id='b',user_id='u',channel='web',message=source,history=[],conversation_id='x',payload={'request_id':'two'},actor={},access=None)
    assert len(value['journal_entries'])==2
    rows=work_review.list_inbox(c,'b','u')
    assert {r['category'] for r in rows}=={'complaint','wish'}


def test_directed_refusal_does_not_require_booking_or_task(review):
    _,c=review
    source='Клиент отказался от дополнительного ухода, сказал дорого. Передай руководителю.'
    value,_=operator_followups.route(c,business_id='b',user_id='u',channel='web',message=source,history=[],conversation_id='x',payload={'request_id':'refusal'},actor={},access=None)
    assert value['status']=='completed'
    assert value['journal_entries'][0]['facts_json']['outcome']=='declined'
    assert 'Владелец увидит запись' in value['chat_response']
    assert 'booking' not in value['chat_response'] and '@ref' not in value['chat_response']
    assert len(work_review.list_inbox(c,'b','u'))==1


def test_literal_ban_has_real_service_period_and_owner_scope(review,monkeypatch):
    from services import operator_work_journal,work_recommendations
    _,c=review
    def prepare(cursor,business,user,channel,message,args,orchestrator):
        envelope=work_recommendations.prepare_policy(cursor,business,user,args)
        return {'status':'approval_required','envelope':envelope}
    monkeypatch.setattr(operator_work_journal,'prepare_approval',prepare)
    value=operator_work_journal.ban_request(c,'b','u','web','На этой неделе не предлагайте Уход.')
    assert value['status']=='approval_required'
    rule=value['envelope']['data']['rules'][0]
    assert rule['addon_service_id']=='care' and rule['action']=='ban'
    from datetime import datetime
    assert datetime.fromisoformat(rule['ends_at']).weekday()==0
    assert work_recommendations.policy(c,'b')['version']==0
    assert operator_work_journal.ban_request(c,'b','master','web','На этой неделе не предлагайте Уход.')['status']=='blocked'
    value=operator_work_journal.ban_request(c,'b','u','web','На этой неделе не предлагайте непонятный уход. Нужен результат по выбранному бизнесу.')
    assert value['status']=='clarification_required'


def test_mixed_rules_are_not_partially_approved(review):
    from services import operator_work_journal,work_recommendations
    _,c=review
    value=operator_work_journal.ban_request(c,'b','u','web','На этой неделе сначала предлагайте Уход. Не предлагайте Набор.')
    assert value['status']=='clarification_required'
    assert 'approval' not in value and work_recommendations.policy(c,'b')['version']==0
