from urllib.parse import parse_qs, urlsplit
from services.work_coherence import aggregate_growth_paths, discuss_existing_work, linked_draft_route, work_projection
from services.today_workspace import section_items


def test_network_retains_location_identity_and_does_not_leak_locked_action():
    path = {"flow_type": "content", "status": "in_progress", "action": {"id": "draft"}, "access": {"status": "available"}}
    paths = aggregate_growth_paths([
        {"business_id": "a", "business_name": "A", "paths": [path]},
        {"business_id": "b", "business_name": "B", "paths": [{**path, "action": None}]},
        {"business_id": "c", "paths": [{**path, "access": {"status": "payment_required"}}]},
    ])
    assert paths[0]["action"] is None
    assert paths[0]["status"] == "in_progress"
    assert [row["business_id"] for row in paths[0]["locations"]] == ["a", "b", "c"]
    assert paths[0]["locations"][2]["action"] is None


def test_projection_is_additive_and_preserves_source_meaning():
    source = {"id": "i", "entity_type": "lead", "entity_id": "l", "business_id": "b", "flow": "partnerships", "status": "approved_for_send", "due_at": "2026-10-11", "action": {"url": "/dashboard/partnerships?lead_id=l"}}
    projected = work_projection(source)
    assert {key: projected[key] for key in source} == source
    assert projected["work_ref"]["status"] == "approved_for_send"
    assert projected["work_ref"]["flow"] == "partnerships"
    assert projected["work_ref"]["href"].endswith("lead_id=l")
    assert "work_ref" not in source


def test_journal_material_link_uses_the_actual_news_draft_id():
    url = linked_draft_route({"payload_json": {"draft_id": 42}}, "business")
    assert urlsplit(url).path == "/dashboard/card"
    assert parse_qs(urlsplit(url).query) == {"tab": ["news"], "mode": ["drafts"], "draft_id": ["42"], "business_id": ["business"]}
    assert linked_draft_route({"payload_json": {}}, "business") is None


def test_discussion_keeps_source_status_and_only_returns_a_read_result():
    source = {"id": "task", "entity_type": "lead", "entity_id": "lead", "status": "approved_for_send", "title": "Offer"}
    result = discuss_existing_work(source, "b")
    assert result["selected_work"]["status"] == "approved_for_send"
    assert result["selected_work"]["id"] == source["id"]
    assert result["capability"] == "operator.query"
    assert "approval" not in result
    assert parse_qs(urlsplit(result["result_ref"]["href"]).query)["journey_action"] == ["task"]


def test_unlinked_material_cannot_create_a_new_instruction_in_chat():
    from services.work_coherence import internal_work_ref, unavailable_work_context
    href = internal_work_ref('/dashboard/card?draft_id=42', 'business')
    result = unavailable_work_context(href)
    assert result['status'] == 'blocked'
    assert result['result_ref']['href'].endswith('business_id=business')
    assert 'approval' not in result
    assert internal_work_ref('//example.com/dashboard/card', 'business') is None
    assert internal_work_ref('/dashboard/card?business_id=other', 'business') is None
    assert internal_work_ref('/dashboard/card\\\\external', 'business') is None


def test_network_blocked_work_is_not_relabelled_as_execution():
    paths = aggregate_growth_paths([{'business_id': 'a', 'paths': [{'flow_type': 'content', 'status': 'blocked', 'action': {'id': 'a'}, 'access': {'status': 'available'}}]}])
    assert paths[0]['status'] == 'blocked'


def test_network_incomplete_states_do_not_become_completed():
    paths = aggregate_growth_paths([{'business_id': 'a', 'paths': [{'flow_type': 'content', 'status': 'completed', 'access': {'status': 'available'}}]}, {'business_id': 'b', 'paths': [{'flow_type': 'content', 'status': 'unknown', 'access': {'status': 'available'}}]}])
    assert paths[0]['status'] == 'unknown'
