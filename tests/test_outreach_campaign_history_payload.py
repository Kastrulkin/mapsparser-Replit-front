from api.outreach_campaign_api import _campaign_payload


class CampaignHistoryCursor:
    def __init__(self):
        self.rows = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        if "from outreach_campaigns where id" in normalized:
            self.rows = [{
                "id": "campaign-1",
                "workstream_id": "workstream-1",
                "room_id": None,
                "status": "stopped",
                "last_reply_at": "2026-07-23T10:30:00+00:00",
            }]
        elif (
            "from outreach_campaign_touches where campaign_id" in normalized
            or "from outreach_campaign_touches touch" in normalized
        ):
            self.rows = [{
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "sequence_index": 0,
                "channel": "email",
                "status": "sent",
                "generated_text": "Первое сообщение",
                "message_brief_json": {},
                "quality_gate_json": {},
            }]
        elif "from outreach_campaign_events" in normalized:
            self.rows = []
        elif "from outreach_inbound_events" in normalized:
            self.rows = [{
                "id": "reply-1",
                "campaign_id": "campaign-1",
                "touch_id": "touch-1",
                "channel": "email",
                "event_type": "reply",
                "classification": "interested",
                "is_human": True,
                "stops_campaign": True,
                "raw_payload_json": {"raw_reply": "Да, пришлите детали"},
            }]
        elif "from outreachsendqueue queue" in normalized:
            self.rows = [{
                "id": "delivery-1",
                "touch_id": "touch-1",
                "channel": "email",
                "delivery_status": "delivered",
                "provider_message_id": "provider-message-1",
            }]
        elif "from sales_rooms" in normalized:
            self.rows = []
        elif "from lead_relationship_states" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_campaign_payload_links_delivery_and_human_reply_to_exact_touch():
    payload = _campaign_payload(CampaignHistoryCursor(), "campaign-1")

    assert payload is not None
    assert payload["touches"][0]["id"] == "touch-1"
    assert payload["deliveries"][0]["touch_id"] == "touch-1"
    assert payload["inbound_events"][0]["touch_id"] == "touch-1"
    assert payload["inbound_events"][0]["raw_payload_json"]["raw_reply"] == "Да, пришлите детали"
    assert payload["inbound_events"][0]["stops_campaign"] is True


class DraftTouchUpdateCursor:
    def __init__(self):
        self.rows = []
        self.queries = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, params))
        if "from outreach_campaign_touches t" in normalized and "join outreach_campaigns c" in normalized:
            self.rows = [{
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "campaign_status": "draft",
                "campaign_version": 4,
                "channel": "email",
                "status": "draft",
                "subject": "Старая тема",
                "generated_text": "Старый текст",
                "message_brief_json": {},
            }]
        elif "update outreach_campaign_touches" in normalized:
            self.rows = [{
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "sequence_index": 0,
                "channel": "email",
                "status": "draft",
                "subject": params[0],
                "generated_text": params[1],
                "message_brief_json": {"human_edited": True},
            }]
        elif "insert into outreach_campaign_events" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_accept_touch_edit_updates_current_draft_without_creating_campaign_version(monkeypatch):
    from services.outreach_campaign_service import update_draft_campaign_touch

    cursor = DraftTouchUpdateCursor()
    edited_text = "Первый абзац.\n\nВторой абзац."
    learning_events = []
    monkeypatch.setattr(
        "services.outreach_campaign_service.record_learning_event",
        lambda *_args, **kwargs: learning_events.append(kwargs) or "learning-1",
    )
    result = update_draft_campaign_touch(
        cursor,
        campaign_id="campaign-1",
        touch_id="touch-1",
        subject="Yes apart | Весёлая расчёска",
        generated_text=edited_text,
        user_id="user-1",
    )

    assert result["campaign_id"] == "campaign-1"
    assert result["campaign_version"] == 4
    assert result["subject"] == "Yes apart | Весёлая расчёска"
    assert result["generated_text"] == edited_text
    assert result["message_brief_json"]["human_edited"] is True
    assert learning_events[0]["outcome_type"] == "editorial_correction"
    assert any("update outreach_campaign_touches" in query for query, _ in cursor.queries)
    assert not any("insert into outreach_campaigns" in query for query, _ in cursor.queries)
    assert not any("update outreach_campaigns" in query for query, _ in cursor.queries)


class PausedTouchUpdateCursor:
    def __init__(self):
        self.rows = []
        self.queries = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, params))
        if "from outreach_campaign_touches t" in normalized and "join outreach_campaigns c" in normalized:
            self.rows = [{
                "id": "touch-queued",
                "campaign_id": "campaign-paused",
                "campaign_status": "paused",
                "campaign_version": 11,
                "channel": "vk",
                "status": "paused",
                "generated_text": "Старый текст VK",
                "message_brief_json": {},
            }]
        elif "from outreachsendqueue" in normalized and "for update" in normalized:
            self.rows = [{
                "id": "queue-1",
                "draft_id": "draft-1",
                "delivery_status": "paused",
            }]
        elif "update outreach_campaign_touches" in normalized:
            self.rows = [{
                "id": "touch-queued",
                "campaign_id": "campaign-paused",
                "sequence_index": 2,
                "channel": "vk",
                "status": "paused",
                "generated_text": params[1],
                "message_brief_json": {"human_edited": True, "manual_edit_review_required": True},
            }]
        elif "update outreachmessagedrafts" in normalized:
            self.rows = []
        elif "update outreach_campaigns" in normalized:
            self.rows = []
        elif "insert into outreach_campaign_events" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_paused_queued_touch_edit_updates_linked_draft_without_resuming(monkeypatch):
    from services.outreach_campaign_service import update_draft_campaign_touch

    cursor = PausedTouchUpdateCursor()
    monkeypatch.setattr(
        "services.outreach_campaign_service.record_learning_event",
        lambda *_args, **_kwargs: "learning-1",
    )

    result = update_draft_campaign_touch(
        cursor,
        campaign_id="campaign-paused",
        touch_id="touch-queued",
        subject=None,
        generated_text="Новый проверяемый текст VK",
        user_id="user-1",
    )

    assert result["campaign_version"] == 11
    assert result["status"] == "paused"
    assert result["generated_text"] == "Новый проверяемый текст VK"
    assert any("update outreachmessagedrafts" in query for query, _ in cursor.queries)
    assert any("approved_text = null" in query for query, _ in cursor.queries)
    assert any("approved_snapshot_hash = null" in query for query, _ in cursor.queries)
    assert not any("delivery_status = 'queued'" in query for query, _ in cursor.queries)


class DraftCampaignReviewCursor:
    def __init__(self):
        self.rows = []
        self.queries = []
        self.updated_touch_ids = []
        self.updated_quality_gates = []
        self.updated_message_briefs = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, params))
        if "from outreach_campaigns" in normalized and "for update" in normalized:
            self.rows = [{
                "id": "campaign-1",
                "version": 4,
                "status": "draft",
            }]
        elif "from outreach_campaign_touches" in normalized and "order by sequence_index" in normalized:
            self.rows = [
                {
                    "id": f"touch-{index}",
                    "campaign_id": "campaign-1",
                    "sequence_index": index,
                    "status": "draft",
                    "message_brief_json": {
                        "human_edited": True,
                        "manual_edit_review_required": True,
                    },
                }
                for index in range(4)
            ]
        elif "update outreach_campaign_touches" in normalized:
            self.updated_touch_ids.append(str(params[-1]))
            self.updated_quality_gates.append(params[0].adapted)
            self.updated_message_briefs.append(params[1].adapted)
            self.rows = []
        elif "insert into outreach_campaign_events" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_review_saved_touch_edits_updates_current_draft_without_new_version():
    from services.outreach_campaign_service import apply_draft_campaign_review

    cursor = DraftCampaignReviewCursor()
    reviewed_touches = [
        {
            "sequence_index": index,
            "quality_gate": {
                "passed": True,
                "verdict": "approve",
                "total_score": 18,
                "max_score": 18,
                "reason_codes": [],
            },
        }
        for index in range(4)
    ]

    result = apply_draft_campaign_review(
        cursor,
        campaign_id="campaign-1",
        reviewed_touches=reviewed_touches,
        user_id="user-1",
    )

    assert result == {
        "campaign_id": "campaign-1",
        "campaign_version": 4,
        "reviewed_touch_count": 4,
        "all_passed": True,
    }
    assert cursor.updated_touch_ids == ["touch-0", "touch-1", "touch-2", "touch-3"]
    assert not any("insert into outreach_campaigns" in query for query, _ in cursor.queries)
    assert not any("update outreach_campaigns" in query for query, _ in cursor.queries)


class PausedCampaignReviewCursor:
    def __init__(self):
        self.rows = []
        self.queries = []
        self.updated_touch_ids = []

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.queries.append((normalized, params))
        if "from outreach_campaigns" in normalized and "for update" in normalized:
            self.rows = [{
                "id": "campaign-paused",
                "version": 11,
                "status": "paused",
                "workstream_id": "workstream-1",
                "lead_id": "lead-1",
                "policy_json": {},
            }]
        elif "from outreach_campaign_touches" in normalized and "order by sequence_index" in normalized:
            self.rows = [
                {
                    "id": "touch-sent",
                    "campaign_id": "campaign-paused",
                    "sequence_index": 0,
                    "status": "sent",
                    "channel": "email",
                    "generated_text": "Уже отправлено",
                    "message_brief_json": {},
                    "quality_gate_json": {"passed": True},
                },
                {
                    "id": "touch-paused",
                    "campaign_id": "campaign-paused",
                    "sequence_index": 2,
                    "status": "paused",
                    "channel": "vk",
                    "generated_text": "Новый проверяемый текст VK",
                    "message_brief_json": {
                        "human_edited": True,
                        "manual_edit_review_required": True,
                    },
                    "quality_gate_json": {"passed": False},
                },
            ]
        elif "update outreach_campaign_touches" in normalized:
            self.updated_touch_ids.append(str(params[-1]))
            self.rows = []
        elif "update outreachmessagedrafts" in normalized:
            self.rows = []
        elif "update outreach_campaigns" in normalized:
            self.rows = []
        elif "insert into outreach_campaign_events" in normalized:
            self.rows = []
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return list(self.rows)


def test_paused_campaign_review_updates_only_edited_unsent_touch_and_restores_snapshot():
    from services.outreach_campaign_service import apply_draft_campaign_review

    cursor = PausedCampaignReviewCursor()
    result = apply_draft_campaign_review(
        cursor,
        campaign_id="campaign-paused",
        reviewed_touches=[{
            "sequence_index": 2,
            "text": "Новый проверяемый текст VK",
            "quality_gate": {
                "passed": True,
                "verdict": "approve",
                "reason_codes": [],
            },
        }],
        user_id="user-1",
    )

    assert result["reviewed_touch_count"] == 1
    assert result["all_passed"] is True
    assert cursor.updated_touch_ids == ["touch-paused"]
    assert any("approved_text = %s" in query for query, _ in cursor.queries)
    assert any("approved_snapshot_hash = %s" in query for query, _ in cursor.queries)


class PendingReviewResumeCursor:
    def __init__(self):
        self.rows = []

    def execute(self, query, _params=None):
        normalized = " ".join(query.lower().split())
        if "select id, status, approved_snapshot_hash" in normalized:
            self.rows = [{
                "id": "campaign-paused",
                "status": "paused",
                "approved_snapshot_hash": None,
            }]
        elif "from outreach_campaign_touches" in normalized and "select count" in normalized:
            self.rows = [{"count": 1}]
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_paused_campaign_cannot_resume_before_edited_message_review():
    import pytest

    from services.outreach_campaign_service import change_campaign_status

    with pytest.raises(ValueError, match="Review edited campaign messages before resuming"):
        change_campaign_status(
            PendingReviewResumeCursor(),
            "campaign-paused",
            "resume",
            user_id="user-1",
        )


def test_successful_manual_edit_review_removes_the_review_blocker_from_every_touch():
    from services.outreach_campaign_service import apply_draft_campaign_review

    cursor = DraftCampaignReviewCursor()
    reviewed_touches = [
        {
            "sequence_index": index,
            "quality_gate": {
                "passed": True,
                "verdict": "revise",
                "total_score": 18,
                "max_score": 18,
                "blocking_reasons": ["manual_edit_requires_review"],
                "reason_codes": ["MANUAL_EDIT_REQUIRES_REVIEW"],
                "canonical_reason_codes": ["MANUAL_EDIT_REQUIRES_REVIEW"],
            },
        }
        for index in range(4)
    ]

    result = apply_draft_campaign_review(
        cursor,
        campaign_id="campaign-1",
        reviewed_touches=reviewed_touches,
        user_id="user-1",
    )

    assert result["all_passed"] is True
    assert len(cursor.updated_quality_gates) == 4
    for gate in cursor.updated_quality_gates:
        assert gate["passed"] is True
        assert gate["verdict"] == "approve"
        assert "manual_edit_requires_review" not in gate["blocking_reasons"]
        assert "MANUAL_EDIT_REQUIRES_REVIEW" not in gate["reason_codes"]
        assert "MANUAL_EDIT_REQUIRES_REVIEW" not in gate["canonical_reason_codes"]
    for brief in cursor.updated_message_briefs:
        assert brief["manual_edit_review_required"] is False
        assert brief["manual_edit_review_passed"] is True


def test_successful_manual_edit_review_makes_current_draft_approvable_without_regeneration():
    from services.outreach_campaign_service import apply_draft_campaign_review
    from services.outreach_personalization_ai import (
        PROMPT_VERSION,
        REVIEW_PROMPT_VERSION,
        generation_contract_current,
    )

    cursor = DraftCampaignReviewCursor()
    reviewed_touches = [
        {
            "sequence_index": index,
            "quality_gate": {
                "passed": True,
                "verdict": "approve",
                "total_score": 18,
                "max_score": 18,
                "reason_codes": [],
                "manual_review": {
                    "passed": True,
                    "review_version": REVIEW_PROMPT_VERSION,
                    "reviewer_role": "superadmin",
                },
            },
        }
        for index in range(4)
    ]

    apply_draft_campaign_review(
        cursor,
        campaign_id="campaign-1",
        reviewed_touches=reviewed_touches,
        user_id="user-1",
    )

    assert len(cursor.updated_quality_gates) == 4
    assert len(cursor.updated_message_briefs) == 4
    for brief, gate in zip(
        cursor.updated_message_briefs,
        cursor.updated_quality_gates,
        strict=True,
    ):
        assert brief["generation_source"] == "manual_product_correction"
        assert brief["generation_prompt_version"] == PROMPT_VERSION
        assert brief["semantic_review_prompt_version"] == REVIEW_PROMPT_VERSION
        assert generation_contract_current(brief, gate, require_ai=True) is True
