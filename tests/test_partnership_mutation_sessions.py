"""Native preparation/review/queue entrypoints retain direct-session limits."""
from datetime import datetime,timezone
from unittest.mock import Mock

import pytest
from flask import Flask,jsonify,request

from services import partnership_group_launch as launch, partnership_prepared_campaigns as prepared, operator_audio
from tests.test_operator_platform_entrypoints import load_function

RESTRICTIONS=[{'session_kind':'demo','scope_business_id':'business'}, {'impersonating':True}, {'impersonated_by':'admin'}]


@pytest.mark.parametrize('restriction',RESTRICTIONS)
@pytest.mark.parametrize('operation',['group_preview','group_confirm','prepare','review_copy','enqueue_preparation'])
def test_restricted_native_mutation_stops_before_sql_or_provider(monkeypatch,restriction,operation):
    cursor=Mock();user={'user_id':'owner','is_superadmin':True,**restriction}
    actor=Mock(side_effect=AssertionError('Session must be guarded before DB authorization'))
    monkeypatch.setattr(operator_audio,'authorize_actor',actor)
    with pytest.raises(PermissionError):
        if operation=='group_preview':
            launch.build_preview(cursor,user=user,business_id='business',collection_id='collection',options={})
        elif operation=='group_confirm':
            launch.confirm_launch(cursor,user=user,business_id='business',collection_id='collection',options={},digest='digest',reviewed=True,confirmed=True)
        elif operation=='prepare':
            prepared.prepare(cursor,user=user,business_id='business',item={})
        elif operation=='review_copy':
            prepared.review_copy(cursor,user=user,business_id='business',campaign_id='campaign',digest='digest')
        else:
            prepared.enqueue_preparation(cursor,user=user,business_id='business',item={})
    cursor.execute.assert_not_called();actor.assert_not_called()


@pytest.mark.parametrize('operation',['prepare','enqueue_preparation'])
def test_cached_superadmin_flag_cannot_prepare_through_platform_sender(monkeypatch,operation):
    actor=Mock(return_value=({'is_superadmin':False},{}))
    monkeypatch.setattr(operator_audio,'authorize_actor',actor)
    monkeypatch.setattr('subscription_manager.capability_access_payload',lambda *args:{'allowed':True})
    cursor=Mock();user={'user_id':'owner','is_superadmin':True}
    with pytest.raises(PermissionError,match='администратору'):
        getattr(prepared,operation)(cursor,business_id='business',user=user,item={})
    assert actor.call_args.kwargs['require_write'] is True
    cursor.execute.assert_not_called()


@pytest.mark.parametrize('operation',['prepare','review_copy','enqueue_preparation'])
def test_revoked_current_database_access_blocks_preparation_mutations(monkeypatch,operation):
    monkeypatch.setattr(operator_audio,'authorize_actor',Mock(side_effect=PermissionError('revoked')))
    cursor=Mock();kwargs={'business_id':'business','user':{'user_id':'owner','is_superadmin':True}}
    if operation=='review_copy':kwargs.update(campaign_id='campaign',digest='digest')
    else:kwargs['item']={}
    with pytest.raises(PermissionError,match='revoked'):getattr(prepared,operation)(cursor,**kwargs)
    cursor.execute.assert_not_called()


def test_current_admin_native_preparation_uses_existing_queue(monkeypatch):
    actor=Mock(return_value=({'is_superadmin':True},{}))
    monkeypatch.setattr(operator_audio,'authorize_actor',actor)
    monkeypatch.setattr('subscription_manager.capability_access_payload',lambda *args:{'allowed':True})
    selection=Mock();monkeypatch.setattr('services.operator_partner_work.partner_selection',selection)
    create=Mock(return_value={'id':'native-job','kind':'partner_copy_prepare','status':'queued'})
    monkeypatch.setattr('services.operator_async_jobs.create_operator_async_job',create)
    item={'lead_id':'lead','channel':'telegram','contact':'@company','source':'https://example.test/about',
          'observation':'Подтверждённый факт','observed_at':datetime.now(timezone.utc).isoformat(),
          'touches':[{'day_offset':0,'text':'Сохранённый текст'}]}
    result=prepared.enqueue_preparation(Mock(),business_id='business',user={'user_id':'admin','is_superadmin':False},item=item)
    assert result['id']=='native-job'
    assert create.call_args.kwargs['payload']=={'item':item}
    assert create.call_args.kwargs['kind']=='partner_copy_prepare'
    selection.assert_called_once()


def test_current_owner_group_authorization_uses_own_business_write_rights(monkeypatch):
    actor=Mock(return_value=({'is_superadmin':False},{}))
    monkeypatch.setattr(operator_audio,'authorize_actor',actor)
    monkeypatch.setattr('subscription_manager.capability_access_payload',lambda *args:{'allowed':True})
    launch.authorize(Mock(),{'user_id':'owner'},'business')
    assert actor.call_args.kwargs['require_write'] is True


@pytest.mark.parametrize('restriction',RESTRICTIONS)
@pytest.mark.parametrize('action',['review','prepare'])
def test_prepared_post_rejects_restricted_session_before_opening_database(restriction,action):
    connection=Mock(side_effect=AssertionError('No DB for restricted mutation'))
    namespace={'request':request,'jsonify':jsonify,'_require_auth':lambda:({'user_id':'owner','is_superadmin':True,**restriction},None),
               'get_db_connection':connection,'RealDictCursor':object}
    endpoint=load_function('src/api/prospecting/outreach_routes.py','partnership_prepared_messages',namespace)
    app=Flask(__name__);app.add_url_rule('/api/partnership/prepared-messages',view_func=endpoint,methods=['POST'])
    response=app.test_client().post('/api/partnership/prepared-messages',json={'business_id':'business','action':action,'save':True})
    assert response.status_code==403
    connection.assert_not_called()
