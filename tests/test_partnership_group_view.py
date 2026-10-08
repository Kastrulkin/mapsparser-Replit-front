from services.partnership_group_view import company_substeps, presentation, load_group_scope, GroupNotFound
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


def test_collected_evidence_is_not_qualification():
    from services.partnership_group_view import company_substeps
    t = task(state={"lead_ids": ["one", "two"], "phase": "prepare"},
             report={"found": 2, "checked": 0, "eligible": 0})
    jobs = [{"status": "needs_evidence", "completed_at": "today",
             "readiness_json": {"missing": ["continuation_campaign_preparation"]},
             "result_json": {"selected_contact_point_id": "contact"}} for _ in range(2)]
    steps = company_substeps(t, jobs)
    assert steps[1]["status"] == "completed"
    assert steps[1]["processed"] == 2
    assert steps[2]["processed"] == 0
    assert steps[2]["status"] != "completed"


def test_enrichment_queue_is_not_running_spinner():
    from services.partnership_group_view import company_substeps
    t = task(status="queued", state={"lead_ids": ["one"], "phase": "prepare"})
    steps = company_substeps(t, [{"status": "queued", "result_json": {}}])
    assert steps[1]["status"] == "queued"
    assert steps[1]["remaining"] == 1


def test_access_revoked_draft_is_not_resumed_after_topup():
    draft = {"id": "letters", "status": "waiting_for_review", "result_json": {"blocker": "access_revoked"}}
    result = presentation(task(), draft_job=draft, available_credits=100)
    assert result["blocker"] == "access_revoked"
    assert result["next_action"]["kind"] == "link"


def test_queued_work_is_identified_as_waiting_not_running():
    result = presentation(task(status="queued"))
    assert result["status"] == "queued"
    assert result["label"] == "Ожидает запуска"


def test_achievements_only_show_produced_outputs():
    from services.partnership_group_view import achievements
    t = task(state={'substeps': [{'id': 'enrichment', 'processed': 12}]},
             report={'found': 41, 'eligible': 2, 'prepared': 1, 'queued': 3, 'confirmed_sent': 0})
    outputs = achievements(t)
    assert [x['id'] for x in outputs] == ['letters', 'qualified', 'enriched']
    assert [x['count'] for x in outputs] == [1, 2, 12]
    assert not any(x['id'] == 'sent' for x in outputs)
    assert achievements(task(report={}, state={})) == []


def test_provider_search_is_running_between_polling_leases():
    t = task(status="queued", state={"phase": "search_poll", "search_run": {"id": "provider-run"}})
    result = presentation(t)
    assert result["status"] == "running"
    assert result["label"] == "Ищем компании"
    assert company_substeps(t, [])[0]["status"] == "running"


def test_blocked_letter_setup_never_claims_letters_are_ready():
    value = task(status='waiting_for_review', config={'mode': 'prepare_only', 'target_count': 3},
        state={'phase': 'prepare', 'started': True, 'blocker': 'draft_sender_setup',
               'campaign_results': {'ws': {'status': 'needs_sender_setup', 'lead_id': 'lead'}}},
        report={'eligible': 1, 'awaiting_check': 0, 'checking': 0, 'prepared': 0})
    result = presentation(value)
    assert result['label'] == 'Требуется действие'
    assert result['next_action']['label'] == 'Настроить отправителя'
    assert result['next_action']['href'].endswith('&lead=lead')


def test_failed_generation_is_attention_even_when_company_goal_is_reached():
    value = task(status='waiting_for_review', config={'mode': 'prepare_only', 'target_count': 3},
        state={'phase': 'prepare', 'started': True, 'blocker': 'draft_generation_failed'},
        report={'eligible': 3, 'awaiting_check': 0, 'checking': 0, 'prepared': 0})
    result = presentation(value)
    assert result['status'] == 'needs_attention'
    assert result['label'] == 'Требуется действие'
    assert result['metrics']['prepared'] == 0
