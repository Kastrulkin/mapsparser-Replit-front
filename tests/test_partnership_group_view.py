from services.partnership_group_view import presentation, load_group_scope, GroupNotFound
import pytest


def task(**overrides):
    return {'id': 'g', 'business_id': 'b', 'status': 'completed',
            'config': {'mode': 'find_only', 'target_count': 10},
            'state': {'phase': 'prepare', 'started': True},
            'report': {'found': 41, 'eligible': 0, 'awaiting_check': 41,
                       'credit_limit': 65, 'credits_charged': 5, 'credit_estimate_only': True}, **overrides}


def test_raw_results_never_represent_target():
    p = presentation(task())
    assert p['metrics']['found'] == 41
    assert p['metrics']['eligible'] == 0
    assert p['metrics']['target'] == 10
    assert p['next_action']['href'] == '/dashboard/partnerships?business_id=b&search_task_id=g&section=companies'
    assert p['expenses'] == {'charged': 5, 'estimate': 65, 'estimate_only': True}


def test_balance_recheck_requires_explicit_resume():
    t = task(status='waiting_for_review', state={'phase': 'prepare', 'started': True, 'blocker': 'insufficient_credits'})
    assert presentation(t, available_credits=0)['next_action']['label'] == 'Пополнить баланс'
    p = presentation(t, available_credits=10)
    assert p['active'] is False
    assert p['next_action']['action'] == 'resume'


def test_unknown_balance_and_cost_are_not_zero():
    p = presentation(task(report={}), available_credits=None)
    assert p['expenses']['charged'] is None
    assert p['available_credits'] is None


def test_uncertain_delivery_never_offers_replay():
    t = task(status='waiting_for_review', state={'started': True, 'inflight_search': True})
    assert presentation(t)['next_action']['kind'] == 'link'
    assert 'сверки' in presentation(t)['reason']


def test_manual_selection_does_not_grant_auto_send():
    t = task(config={'mode': 'auto_send'}, report={'queued': 1})
    assert presentation(t)['send_mode'] == 'manual'
    t['report']['automatic_send_authorized'] = True
    assert presentation(t)['send_mode'] == 'automatic_authorized'


def test_draft_pause_uses_existing_job_not_new_search():
    draft = {'id': 'letters', 'status': 'waiting_for_review', 'result_json': {}}
    p = presentation(task(), draft_job=draft, available_credits=10)
    assert p['phase'] == 'letters'
    assert p['active'] is False
    assert p['next_action']['kind'] == 'draft_resume'


def test_revoked_rules_do_not_offer_resume():
    t = task(status='waiting_for_review', state={'blocker': 'ai_rules_revoked_or_changed', 'started': True})
    assert presentation(t)['next_action']['kind'] == 'link'


def test_tenant_scoped_group_lookup():
    class Cursor:
        def execute(self, sql, params):
            assert 'business_id=%s' in sql
            assert params == ('g', 'other-business')
        def fetchone(self): return None
    with pytest.raises(GroupNotFound):
        load_group_scope(Cursor(), 'other-business', 'g')


def test_stopped_search_never_offers_topup_or_resume():
    t = task(status='cancelled', state={'blocker': 'insufficient_credits', 'started': True}, report={'prepared': 2})
    p = presentation(t, available_credits=0)
    assert p['label'] == 'Поиск остановлен'
    assert p['next_action']['label'] == 'Посмотреть письма'
    assert p['active'] is False


def test_failed_letters_never_restarts_search():
    p = presentation(task(status='waiting_for_review'), draft_job={'status': 'failed', 'result_json': {}})
    assert p['next_action']['kind'] == 'link'
    assert p['phase'] == 'letters'
