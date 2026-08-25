import inspect

from api.prospecting import audit_generation, sales_room_routes
from services import outreach_safety_service


def _guard():
    guard = getattr(outreach_safety_service, "partnership_repeat_contact_guard", None)
    assert callable(guard), (
        "Partnership batch creation has no shared repeat-contact guard, so an "
        "approved first-touch draft can be queued after a prior agreement."
    )
    return guard


def test_converted_partnership_cannot_be_queued_as_a_first_touch():
    decision = _guard()(
        lifecycle_status="converted",
        workstream_status="contacted",
        relationship_status="active",
        prior_conversation=None,
    )

    assert decision["blocked"] is True
    assert decision["reason"] == "active_partnership"
    assert decision["display_status"] == "converted"


def test_prior_partner_message_blocks_first_touch_even_when_status_is_stale():
    decision = _guard()(
        lifecycle_status="waiting_reply",
        workstream_status="contacted",
        relationship_status=None,
        prior_conversation={
            "direction": "room",
            "author_role": "visitor",
            "created_at": "2026-08-03T12:00:00+03:00",
            "channel": "digital_room",
            "text": "Договорились об обмене листовками и участии в акции.",
        },
    )

    assert decision["blocked"] is True
    assert decision["reason"] == "prior_partner_conversation"
    assert decision["display_status"] == "replied"
    assert decision["warning"]


def test_all_batch_entrypoints_apply_the_shared_guard_before_queueing():
    partnership_source = inspect.getsource(sales_room_routes.partnership_create_send_batch)
    legacy_source = inspect.getsource(audit_generation._create_send_batch)
    preflight_source = inspect.getsource(outreach_safety_service.run_dispatch_preflight)

    assert "load_partnership_repeat_contact_guard" in partnership_source
    assert "load_partnership_repeat_contact_guard" in legacy_source
    assert "load_partnership_repeat_contact_guard" in preflight_source
    assert "prior_partner_conversation" in partnership_source
