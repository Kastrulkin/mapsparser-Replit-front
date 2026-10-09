import pytest
from tests.test_business_chat_management_pg import managed
from tests.test_finance_daily_pg import daily
from tests.test_operator_voice_pg import pg
from services import business_team_management


def test_remove_exact_scope_preserves_account_and_blocks_missing(managed):
    _,c=managed
    args={'email':'anna@example.ru','name':'Анна','role':'admin','scope':'business','send_invitation':False}
    payload=business_team_management.prepare(c,'b','u',args)
    saved=business_team_management.apply(c,'b','u',payload,'grant')
    other=business_team_management.prepare(c,'b2','u',args)
    business_team_management.apply(c,'b2','u',other,'grant-other-location')
    removal=business_team_management.prepare(c,'b','u',{'email':'anna@example.ru','scope':'business','operation':'remove','send_invitation':False})
    assert 'Снять доступ' in business_team_management.preview_text(removal)
    business_team_management.apply(c,'b','u',removal,'remove')
    assert business_team_management.apply(c,'b','u',removal,'remove')['membership_saved']
    c.execute('SELECT status FROM business_members WHERE business_id=%s AND user_id=%s',('b',saved['user_id']))
    assert c.fetchone()['status']=='revoked'
    c.execute('SELECT status FROM business_members WHERE business_id=%s AND user_id=%s',('b2',saved['user_id']))
    assert c.fetchone()['status']=='active'
    c.execute('SELECT is_active FROM users WHERE id=%s',(saved['user_id'],));assert c.fetchone()['is_active'] is True
    with pytest.raises(ValueError,match='не найден'):business_team_management.prepare(c,'b','u',{'email':'missing@example.ru','scope':'business','operation':'remove','send_invitation':False})
