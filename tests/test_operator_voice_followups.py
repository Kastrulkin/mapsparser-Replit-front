from datetime import date
from services import operator_voice_followups


def test_explicit_date_needs_no_timezone():
    assert operator_voice_followups.requested_date(None,'b','Нет, перенеси на 2026-11-01')==date(2026,11,1)


def test_other_topic_is_not_date_edit():
    assert operator_voice_followups.requested_date(None,'b','Расскажи об услугах') is None


def test_no_history_is_not_a_target():
    assert operator_voice_followups.route(None,business_id='b',user_id='u',channel='web',message='Покажи услуги',history=[],request_id='r') is None
