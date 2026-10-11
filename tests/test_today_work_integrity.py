"""Read-only adapter checks: Today must describe actual work, not setup counters."""
from datetime import datetime, timedelta, timezone
from services.today_workspace import canonical_work_items, section_items, work_item
NOW = datetime(2026, 10, 11, 10, tzinfo=timezone.utc)

def item(identity, status, **kwargs):
    return work_item(entity_type='test', entity_id=identity, flow=kwargs.pop('flow','maps'), business_id='b', title=identity, status=status, url='/dashboard/card', now=NOW, **kwargs)

def test_deadlines_and_failure_outrank_personal_priority():
    late=item('late','needs_review',due_at=NOW-timedelta(days=1))
    failure=item('failure','failed')
    draft=item('draft','edited',flow='content')
    sections=section_items([draft,failure,late],'content',now=NOW)
    assert [i['entity_id'] for i in sections['needs_decision']]==['late','failure','draft']

def test_urgent_background_queue_is_not_a_human_decision():
    sections=section_items([item('queue','queued',urgent=True)],'maps',now=NOW)
    assert not sections['needs_decision']
    assert sections['continue_work'][0]['status']=='queued'

def test_legacy_adapter_preserves_status_date_and_specific_url():
    url='/dashboard/content?plan_id=p&item_id=i'
    view=canonical_work_items({'active_work':[{'id':'parse:q','status':'in_progress','work_status':'queued','screen':'cards','due_at':NOW.isoformat(),'action':{'url':url}}]},NOW)
    assert view[0]['status']=='queued'
    assert view[0]['due_at']==NOW.isoformat()
    assert view[0]['action']['url']==url

def test_legacy_results_keep_real_events_not_aggregates_or_undated_milestones():
    payload={'completed_results':[{'id':'aggregate','kind':'growth_achievement','occurred_at':NOW.isoformat()}, {'id':'undated'}, {'id':'real','kind':'confirmed_action','occurred_at':NOW.isoformat(),'screen':'content'}]}
    assert [i['entity_id'] for i in canonical_work_items(payload,NOW)]==['real']
    assert len(payload['completed_results'])==3  # legacy/Telegram facts remain available

def test_owner_action_links_to_its_existing_approval_boundary():
    view=canonical_work_items({'active_work':[{'id':'owner:o','kind':'owner_action','entity_id':'o','status':'ready','business_id':'b'}]},NOW)
    assert view[0]['action']['url']=='/dashboard/operator?business_id=b&journey_action=o'
    assert section_items(view,'automation',now=NOW)['needs_decision']

def test_approved_content_still_requires_manual_publication():
    task=work_item(entity_type='content_item',entity_id='approved',flow='content',business_id='b',title='Review publication',status='approved',url='/dashboard/content?item_id=approved',now=NOW,due_at=NOW-timedelta(days=1))
    failure=item('failure','failed')
    sections=section_items([failure,task],'maps',now=NOW)
    assert sections['needs_decision'][0]['entity_id']=='approved'
    assert sections['needs_decision'][0]['status']=='approved'
