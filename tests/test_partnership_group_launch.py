from copy import deepcopy
from datetime import datetime, timedelta, timezone
import pytest
from services import partnership_group_launch as launch

NOW = datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc)
OPTIONS = {'telegram_start':'2026-10-23T13:00:00+03:00','email_start':'2026-10-23T14:30:00+03:00','interval_minutes':5}


def item(number, channel='telegram'):
    base = datetime(2026,10,22,11,0,tzinfo=timezone.utc)
    return {'id':f'campaign-{number}','lead_id':f'lead-{number}','company_id':f'company-{number}','workstream_id':f'work-{number}',
        'name':f'Компания {number:02}','status':'draft','review_digest':f'digest-{number}','policy_json':{'stop_on_reply':True,'sender_mode':'localos_for_partner','represented_business_id':'business'},
        'touches':[{'id':f'touch-{number}-{index}','channel':channel,'sequence_index':index,'scheduled_at':base+timedelta(days=days),'recipient':f'contact-{number}','sender_account_id':'sender-'+channel,'contact_point_id':f'cp-{number}','status':'draft','generated_text':'Сохранённое письмо','quality_gate_json':{'reason_codes':[]}} for index,days in enumerate([0,3,7,12])]}


def test_schedules_sixteen_telegram_before_remaining_thirty_four_email():
    items=[item(number,'telegram' if number<16 else 'email') for number in range(50)]
    scheduled,counts=launch.schedule_items(items,OPTIONS,NOW)
    assert counts=={'telegram':16,'email':34}
    assert all(row['touches'][0]['channel']=='telegram' for row in scheduled[:16])
    assert max(datetime.fromisoformat(row['touches'][0]['scheduled_at']) for row in scheduled[:16]) < min(datetime.fromisoformat(row['touches'][0]['scheduled_at']) for row in scheduled[16:])
    assert len({row['touches'][0]['scheduled_at'] for row in scheduled})==50
    assert items[0]['touches'][0]['scheduled_at'].date().isoformat()=='2026-10-22'
    assert scheduled[0]['touches'][1]['scheduled_at'].startswith('2026-10-26T13:00')


@pytest.mark.parametrize('change',[
 {'telegram_start':'2026-10-22T13:00:00+03:00'},
 {'telegram_start':'2026-10-23T11:04:00+03:00'},
 {'telegram_start':'2026-10-23T13:00:00'},
 {'telegram_start':'invalid'},
 {'telegram_start':'2026-12-23T13:00:00+03:00'},
 {'telegram_start':'2026-10-24T13:00:00+03:00'},
 {'telegram_start':'2026-10-23T19:00:00+03:00'},
 {'interval_minutes':True},{'interval_minutes':2},{'interval_minutes':61},
 {'email_start':'2026-10-23T13:00:00+03:00'},
])
def test_rejects_ambiguous_past_or_overlapping_schedule(change):
    with pytest.raises(ValueError):launch.schedule_items([item(1),item(2,'email')],{**OPTIONS,**change},NOW)


def test_evening_rollover_preserves_spacing_and_never_duplicates_slots():
    opts={**OPTIONS,'telegram_start':'2026-10-23T17:55:00+03:00','email_start':'2026-10-26T11:00:00+03:00'}
    scheduled,_=launch.schedule_items([item(i) for i in range(4)],opts,NOW)
    dates=[row['touches'][0]['scheduled_at'] for row in scheduled]
    assert dates==['2026-10-23T17:55:00+03:00','2026-10-26T10:00:00+03:00','2026-10-26T10:05:00+03:00','2026-10-26T10:10:00+03:00']


def test_defaults_are_future_and_email_follows_actual_telegram_count():
    items=[item(i,'telegram' if i<16 else 'email') for i in range(50)]
    options=launch.default_schedule(items,NOW)
    assert datetime.fromisoformat(options['telegram_start'])>NOW
    assert datetime.fromisoformat(options['email_start'])-datetime.fromisoformat(options['telegram_start'])==timedelta(minutes=80)
    launch.schedule_items(items,options,NOW)


class Cursor:
    rowcount=1
    def __init__(self,receipt=None):self.calls=[];self.receipt=receipt
    def execute(self,query,params=None):self.calls.append((query,params))
    def fetchall(self):return []
    def fetchone(self):return {'result_json':{'reviewed_launch':self.receipt} if self.receipt else {'lead_ids':['lead-1','lead-2']}}


@pytest.fixture
def preview_setup(monkeypatch):
    rows=[item(1),item(2,'email')]
    monkeypatch.setattr(launch,'authorize',lambda *args:None)
    monkeypatch.setattr(launch,'load_collections',lambda *args,**kwargs:[{'id':'group','result_json':{'lead_ids':['lead-1','lead-2']}}])
    monkeypatch.setattr(launch.prepared,'list_prepared',lambda *args,**kwargs:deepcopy(rows))
    monkeypatch.setattr(launch.prepared,'load_touches',lambda cursor,campaign_id:deepcopy(next(row['touches'] for row in rows if row['id']==campaign_id)))
    senders={channel:{'id':'sender-'+channel,'label':channel+' sender','scope_type':'platform','business_id':None,'status':'connected','health_status':'healthy','outreach_enabled':True,'telegram_outreach_enabled':True,'capabilities_json':{'direct_send':True,'reply_sync':True}} for channel in ['telegram','email']}
    monkeypatch.setattr(launch,'sender_contexts',lambda *args:{'sender-'+key:value for key,value in senders.items()})
    monkeypatch.setenv('OUTREACH_DISPATCH_ENABLED','true');monkeypatch.setenv('OUTREACH_DISPATCH_BUSINESS_IDS','business')
    return rows,senders


def test_preview_is_read_only_and_binds_text_contact_sender_and_dates(monkeypatch,preview_setup):
    rows,_=preview_setup;c=Cursor()
    def build():return launch.build_preview(c,user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,now=NOW)
    original=build();assert c.calls==[];assert original['messages_sent']==0;assert original['runtime_ready']
    for key in ['generated_text','recipient','sender_account_id']:
        old=rows[0]['touches'][0][key]
        if key=='sender_account_id':continue
        rows[0]['touches'][0][key]='changed'
        assert build()['digest']!=original['digest']
        rows[0]['touches'][0][key]=old
    changed=launch.build_preview(c,user={'user_id':'owner'},business_id='business',collection_id='group',options={**OPTIONS,'email_start':'2026-10-23T15:30:00+03:00'},now=NOW)
    assert changed['digest']!=original['digest']


@pytest.mark.parametrize('change',[{'status':'approved'},{'hold_reason':'Прежнее обращение'},{'company_id':'company-2'}])
def test_preview_rejects_running_held_or_duplicate_company(preview_setup,change):
    rows,_=preview_setup;rows[0].update(change)
    with pytest.raises(ValueError):launch.build_preview(Cursor(),user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,now=NOW)


@pytest.mark.parametrize('field,value',[('status','disabled'),('outreach_enabled',False),('health_status','blocked'),('scope_type','business')])
def test_preview_rechecks_live_sender_permissions_and_scope(preview_setup,field,value):
    _,senders=preview_setup;senders['email'][field]=value
    with pytest.raises(ValueError):launch.build_preview(Cursor(),user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,now=NOW)


def test_foreign_group_has_no_preview(monkeypatch,preview_setup):
    monkeypatch.setattr(launch,'load_collections',lambda *args,**kwargs:[])
    with pytest.raises(LookupError):launch.build_preview(Cursor(),user={'user_id':'owner'},business_id='business',collection_id='foreign',options=OPTIONS,now=NOW)


def test_hard_quality_errors_cannot_be_human_waived(preview_setup):
    rows,_=preview_setup;rows[0]['touches'][0]['quality_gate_json']['reason_codes']=['UNSUPPORTED_CLAIM']
    with pytest.raises(ValueError,match='безопасности'):launch.build_preview(Cursor(),user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,now=NOW)


def test_disabled_runtime_is_visible_and_not_silently_enabled(monkeypatch,preview_setup):
    monkeypatch.setenv('OUTREACH_DISPATCH_ENABLED','false')
    result=launch.build_preview(Cursor(),user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,now=NOW)
    assert not result['runtime_ready'];assert result['warning'];assert result['messages_sent']==0


@pytest.mark.parametrize('reviewed,confirmed',[(False,True),(True,False),(None,True),('yes',True)])
def test_confirmation_requires_two_explicit_true_decisions(monkeypatch,reviewed,confirmed):
    monkeypatch.setattr(launch,'authorize',lambda *args:None);c=Cursor()
    with pytest.raises(ValueError):launch.confirm_launch(c,user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,digest='digest',reviewed=reviewed,confirmed=confirmed)
    assert c.calls==[]


def test_repeated_confirmation_returns_same_native_batch_without_enrolling_again(monkeypatch):
    monkeypatch.setattr(launch,'authorize',lambda *args:None)
    c=Cursor({'digest':'digest','batch_id':'batch','status':'scheduled'})
    result=launch.confirm_launch(c,user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,digest='digest',reviewed=True,confirmed=True)
    assert result['idempotent'];assert result['batch_id']=='batch';assert len(c.calls)==1


def test_changed_digest_stops_before_any_native_approval(monkeypatch):
    monkeypatch.setattr(launch,'authorize',lambda *args:None)
    monkeypatch.setattr(launch,'build_preview',lambda *args,**kwargs:{'digest':'new','runtime_ready':True})
    c=Cursor()
    with pytest.raises(ValueError,match='изменились'):launch.confirm_launch(c,user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,digest='old',reviewed=True,confirmed=True)
    assert not any(query.lstrip().startswith(('INSERT','UPDATE')) for query,_ in c.calls)


def test_confirmation_reuses_native_copy_review_and_approval_in_one_batch(monkeypatch):
    from services import outreach_campaign_service
    monkeypatch.setattr(launch,'authorize',lambda *args:None)
    native=[]
    items=[{'campaign_id':'c1','review_digest':'d1','touches':[{'id':'t1','scheduled_at':'future'}]},{'campaign_id':'c2','review_digest':'d2','touches':[{'id':'t2','scheduled_at':'future'}]}]
    monkeypatch.setattr(launch,'build_preview',lambda *args,**kwargs:{'digest':'digest','runtime_ready':True,'items':items,'company_count':2,'touch_count':2,'counts':{'telegram':1,'email':1}})
    monkeypatch.setattr(launch.prepared,'review_copy',lambda *args,**kwargs:native.append(('review',kwargs)))
    monkeypatch.setattr(outreach_campaign_service,'approve_campaign',lambda *args,**kwargs:native.append(('approve',args,kwargs)))
    c=Cursor();result=launch.confirm_launch(c,user={'user_id':'owner'},business_id='business',collection_id='group',options=OPTIONS,digest='digest',reviewed=True,confirmed=True)
    assert [entry[0] for entry in native]==['review','approve','review','approve']
    assert native[1][2]['reviewed_batch_id']==native[3][2]['reviewed_batch_id']==result['batch_id']
    assert result['messages_sent']==0
    assert 'approved' in c.calls[-2][0]
