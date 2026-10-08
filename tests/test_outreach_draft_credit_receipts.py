from services.outreach_credit_billing import reserve_step, DRAFT_ACTION
from services.outreach_continuation import preparation_report, _release_draft_hold


def test_draft_uses_existing_tariff_and_attempt_identity(monkeypatch):
    from services import operator_credit_reservation
    calls = []
    monkeypatch.setattr(operator_credit_reservation,'reserve_paid_action_credits',
                       lambda cursor,**kw: calls.append(kw) or {'status':'reserved'})
    row={'id':'group','business_id':'business','user_id':'user'}
    reserve_step(object(),row,step='draft',key='lead:revision:23',credits=1)
    assert calls[0]['action_key'] == DRAFT_ACTION == 'partnership_draft_generate'
    assert calls[0]['idempotency_key'] == 'outreach:group:draft:lead:revision:23'


def test_report_includes_actual_copy_receipt():
    config={'target_count':3,'max_search_calls':1,'max_qualification_calls':50,
            'search_budget_cents':50,'mode':'prepare_only'}
    report=preparation_report(config,{'search_credits_charged':5,'check_credits_charged':88,
                                      'draft_credits_charged':3})
    assert report['credits_charged']==96
    assert report['draft_credits_charged']==3


def test_interrupted_copy_releases_hold_without_external_retry(monkeypatch):
    from services import outreach_credit_billing
    calls=[]
    monkeypatch.setattr(outreach_credit_billing,'charge_step',lambda *args,**kw:calls.append(kw))
    _release_draft_hold(object(),{}, {'credit_reservation_id':'reservation','credit_key':'attempt'})
    assert calls == [{'reservation_id':'reservation','credits':0,'step':'draft','key':'attempt'}]
    _release_draft_hold(object(),{}, {'status':'preparing'})
    assert len(calls)==1
