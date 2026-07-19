from pathlib import Path

from services import outreach_campaign_service
from services.contact_intelligence_service import build_message_brief, build_native_research_payload
from services.outreach_campaign_service import (
    _founder_story,
    _quality_gate,
    _strategy_dimensions,
    finalize_no_reply_campaigns,
    record_campaign_business_outcome,
)
from services.outreach_safety_service import (
    approval_snapshot_hash,
    classify_inbound_event,
    confirmed_reply_learning_outcome,
    learning_sample_status,
    learning_stat_metrics,
    normalized_contact_hash,
    reconcile_reaction_learning_event,
    recipient_key,
    sender_health,
    strategy_fingerprint,
    wilson_lower_bound,
)
from services.outreach_dispatch_service import dispatch_due_outreach_queue


def test_human_reply_stops_campaign_and_unsubscribe_suppresses():
    reply = classify_inbound_event({"text": "Да, интересно. Когда сможем обсудить?"})
    unsubscribe = classify_inbound_event({"text": "Удалите мой контакт и больше не пишите"})

    assert reply["classification"] == "question"
    assert reply["is_human"] is True
    assert reply["stops_campaign"] is True
    assert unsubscribe["classification"] == "unsubscribe"
    assert unsubscribe["creates_suppression"] is True


def test_automatic_reply_pauses_but_is_not_a_human_terminal_reply():
    result = classify_inbound_event(
        {
            "subject": "Automatic reply: out of office",
            "auto_submitted": "auto-replied",
            "text": "I am out of office until Monday",
        }
    )

    assert result["classification"] == "out_of_office"
    assert result["is_human"] is False
    assert result["stops_campaign"] is False


def test_sender_health_circuit_breaker_separates_warning_and_pause():
    warning = sender_health({"sent_count": 100, "bounce_count": 4})
    paused = sender_health({"sent_count": 100, "bounce_count": 16})
    blocked = sender_health({"sent_count": 10, "blocked": True})

    assert warning["status"] == "warning"
    assert paused["status"] == "paused"
    assert blocked["status"] == "blocked"


def test_strategy_and_approval_fingerprints_are_stable_and_version_sensitive():
    strategy = {
        "workstream_type": "localos_sales",
        "segment": "стоматологии",
        "signal_kind": "map_rating",
        "channel": "telegram",
        "sequence_index": 0,
        "day_offset": 0,
        "angle": "signal",
    }
    first = strategy_fingerprint(strategy)
    second = strategy_fingerprint(dict(reversed(list(strategy.items()))))
    campaign = {"id": "campaign-1", "version": 1, "lead_id": "lead-1", "policy_json": {"daily_limit": 10}}
    touches = [{"id": "touch-1", "sequence_index": 0, "generated_text": "Первый текст"}]
    changed_touches = [{"id": "touch-1", "sequence_index": 0, "generated_text": "Другой текст"}]

    assert first == second
    assert approval_snapshot_hash(campaign, touches) != approval_snapshot_hash(campaign, changed_touches)


def test_strategy_dimensions_remember_semantic_signal_founder_story_offer_and_touch():
    strategy = _strategy_dimensions(
        {
            "workstream_type": "client_partnership",
            "category": "фитнес",
            "sender_profile": {"id": "profile-1"},
        },
        {"segment": "локальные фитнес-клубы", "buyer_persona": "владелец"},
        {
            "evidence_id": "evidence-42",
            "evidence_kind": "service_compatibility",
            "freshness": "current_snapshot",
            "founder_story": "Мы развиваем семейную студию в этом районе.",
            "founder_proof": "Проводили совместные мероприятия с локальными компаниями.",
            "relevance_to_offer": "У аудиторий есть локальное пересечение.",
            "next_step": "Обсудить один безопасный тест.",
        },
        {"story": "Резервная история", "proof": "Резервный факт", "offer": "Совместный тест"},
        channel="telegram",
        sequence_index=1,
        day_offset=3,
        angle="founder_story",
    )

    assert strategy["signal_kind"] == "service_compatibility"
    assert strategy["evidence_id"] == "evidence-42"
    assert strategy["founder_story"].startswith("Мы развиваем")
    assert strategy["founder_proof"].startswith("Проводили")
    assert strategy["offer"] == "Совместный тест"
    assert strategy["sequence_index"] == 1


def test_learning_metrics_include_no_reply_meetings_conversions_and_sender_health():
    metrics = learning_stat_metrics({
        "sent_count": 40,
        "delivered_count": 40,
        "positive_reply_count": 8,
        "hard_no_count": 2,
        "unsubscribe_count": 0,
        "complaint_count": 0,
        "meeting_count": 4,
        "converted_count": 2,
        "no_reply_count": 20,
        "sender_health_score": 80,
        "sender_health_status": "paused",
        "recommendation_status": "candidate_for_reuse",
    })

    assert metrics["positive_reply_rate"] == 0.2
    assert metrics["meeting_rate"] == 0.1
    assert metrics["conversion_rate"] == 0.05
    assert metrics["no_reply_rate"] == 0.5
    assert metrics["recommendation_status"] == "review_sender_health"


def test_recipient_and_contact_keys_are_stable_without_exposing_contact_value():
    first = normalized_contact_hash("email", " Info@Example.RU ")
    second = normalized_contact_hash("email", "info@example.ru")

    assert first == second
    assert "example.ru" not in first
    assert recipient_key("lead-1") == "lead:lead-1"


def test_learning_sample_status_and_confidence_guard_small_samples():
    assert learning_sample_status(19) == "insufficient_data"
    assert learning_sample_status(20) == "preliminary"
    assert learning_sample_status(100) == "reliable"
    assert wilson_lower_bound(1, 1) < 0.3
    assert wilson_lower_bound(80, 100) > wilson_lower_bound(8, 10)


def test_human_confirmation_maps_only_real_reply_outcomes():
    assert confirmed_reply_learning_outcome("positive") == "positive_reply"
    assert confirmed_reply_learning_outcome("question") == "question"
    assert confirmed_reply_learning_outcome("hard_no") == "hard_no"
    assert confirmed_reply_learning_outcome("no_response") is None


class _ReactionLearningCursor:
    def __init__(self, existing_outcome="positive_reply"):
        self.existing_outcome = existing_outcome
        self.current = None
        self.executed = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))
        if "FROM outreachreactions reaction" in normalized:
            self.current = {
                "reaction_id": "reaction-1",
                "lead_id": "lead-1",
                "workstream_id": "workstream-1",
                "campaign_workstream_id": "workstream-1",
                "campaign_touch_id": "touch-1",
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "scope_type": "platform",
                "business_id": None,
                "workstream_type": "localos_sales",
                "strategy_fingerprint": "fingerprint-1",
                "strategy_json": {"segment": "стоматологии", "channel": "email"},
                "channel": "email",
            }
        elif "FROM outreach_learning_events" in normalized:
            self.current = {
                "id": "learning-1",
                "outcome_type": self.existing_outcome,
            } if self.existing_outcome else None
        else:
            self.current = None

    def fetchone(self):
        return self.current


def test_human_reply_override_rewrites_learning_and_lead_lifecycle(monkeypatch):
    cursor = _ReactionLearningCursor(existing_outcome="positive_reply")
    refreshed = []
    monkeypatch.setattr(
        "services.outreach_safety_service.refresh_strategy_stats",
        lambda *args, **kwargs: refreshed.append(kwargs) or {},
    )

    result = reconcile_reaction_learning_event(
        cursor,
        reaction_id="reaction-1",
        confirmed_outcome="hard_no",
        user_id="user-1",
    )

    assert result["outcome_type"] == "hard_no"
    assert result["safety_outcome_retained"] is False
    learning_updates = [item for item in cursor.executed if "UPDATE outreach_learning_events" in item[0]]
    assert learning_updates[0][1][0] == "hard_no"
    lifecycle_updates = [item for item in cursor.executed if "UPDATE lead_workstreams" in item[0]]
    assert lifecycle_updates[0][1][0] == "not_interested"
    assert any("INSERT INTO outreach_suppressions" in query for query, _params in cursor.executed)
    assert refreshed[0]["fingerprint"] == "fingerprint-1"


def test_human_reply_override_cannot_downgrade_complaint(monkeypatch):
    cursor = _ReactionLearningCursor(existing_outcome="complaint")
    monkeypatch.setattr(
        "services.outreach_safety_service.refresh_strategy_stats",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not refresh unchanged safety outcome")),
    )

    result = reconcile_reaction_learning_event(
        cursor,
        reaction_id="reaction-1",
        confirmed_outcome="positive",
        user_id="user-1",
    )

    assert result["outcome_type"] == "complaint"
    assert result["safety_outcome_retained"] is True
    assert not any("UPDATE outreach_learning_events" in query for query, _params in cursor.executed)


class _CampaignOutcomeCursor:
    def __init__(self, *, status="stopped", has_human_reply=True, existing=None):
        self.status = status
        self.has_human_reply = has_human_reply
        self.existing = existing
        self.current = None
        self.executed = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split())
        self.executed.append((normalized, params))
        if "FROM outreach_campaigns c" in normalized:
            self.current = {
                "id": "campaign-1",
                "workstream_id": "workstream-1",
                "scope_type": "platform",
                "business_id": None,
                "workstream_type": "localos_sales",
                "lifecycle_status": "replied",
                "status": self.status,
                "stop_reason": "recipient_replied" if self.has_human_reply else None,
                "last_reply_at": "2026-07-18T12:00:00Z" if self.has_human_reply else None,
                "has_human_reply": self.has_human_reply,
                "reply_touch_id": "touch-1" if self.has_human_reply else None,
                "last_sent_touch_id": "touch-1",
            }
        elif "SELECT * FROM outreach_campaign_touches" in normalized:
            self.current = {
                "id": "touch-1",
                "campaign_id": "campaign-1",
                "strategy_fingerprint": "fingerprint-1",
                "strategy_json": {"segment": "стоматологии", "channel": "email"},
            }
        elif "FROM outreach_learning_events" in normalized:
            self.current = self.existing
        else:
            self.current = None

    def fetchone(self):
        return self.current


def test_campaign_business_outcome_records_meeting_and_updates_lifecycle(monkeypatch):
    cursor = _CampaignOutcomeCursor()
    monkeypatch.setattr(outreach_campaign_service, "record_learning_event", lambda *args, **kwargs: "learning-1")

    result = record_campaign_business_outcome(
        cursor,
        "campaign-1",
        "meeting_booked",
        user_id="user-1",
        note="Созвон во вторник в 12:00",
    )

    assert result["learning_event_id"] == "learning-1"
    assert result["reused"] is False
    lifecycle_updates = [item for item in cursor.executed if "UPDATE lead_workstreams" in item[0]]
    assert lifecycle_updates[0][1][0] == "qualified"
    assert lifecycle_updates[0][1][1] == "meeting_booked"
    assert any(
        params and "campaign_outcome_recorded" in params
        for _query, params in cursor.executed
    )


def test_campaign_no_reply_requires_completed_campaign_without_reply(monkeypatch):
    cursor = _CampaignOutcomeCursor(status="completed", has_human_reply=False)
    monkeypatch.setattr(outreach_campaign_service, "record_learning_event", lambda *args, **kwargs: "learning-2")

    result = record_campaign_business_outcome(
        cursor,
        "campaign-1",
        "no_reply",
        user_id="user-1",
    )

    assert result["outcome_type"] == "no_reply"
    lifecycle_updates = [item for item in cursor.executed if "UPDATE lead_workstreams" in item[0]]
    assert lifecycle_updates[0][1][0] == "closed_lost"


def test_campaign_no_reply_rejects_recorded_human_reply():
    cursor = _CampaignOutcomeCursor(status="completed", has_human_reply=True)

    try:
        record_campaign_business_outcome(
            cursor,
            "campaign-1",
            "no_reply",
            user_id="user-1",
        )
    except ValueError as exc:
        assert "conflicts with a recorded reply" in str(exc)
    else:
        raise AssertionError("Expected no-reply conflict")


class _NoReplyFinalizerCursor:
    def __init__(self):
        self.params = None

    def execute(self, query, params=None):
        self.params = params
        assert "campaign.status = 'completed'" in str(query)
        assert "FOR UPDATE SKIP LOCKED" in str(query)

    def fetchall(self):
        return [{"id": "campaign-1"}, {"id": "campaign-2"}]


def test_no_reply_finalizer_uses_grace_window_and_idempotent_outcome_writer(monkeypatch):
    cursor = _NoReplyFinalizerCursor()
    recorded = []

    def _record(_cursor, campaign_id, outcome_type, **kwargs):
        recorded.append((campaign_id, outcome_type, kwargs))
        return {"reused": campaign_id == "campaign-2"}

    monkeypatch.setattr(outreach_campaign_service, "record_campaign_business_outcome", _record)

    finalized = finalize_no_reply_campaigns(cursor, limit=50, default_grace_hours=168)

    assert cursor.params == (168, 50)
    assert finalized == 1
    assert [item[0] for item in recorded] == ["campaign-1", "campaign-2"]
    assert all(item[1] == "no_reply" for item in recorded)
    assert all(item[2]["user_id"] is None for item in recorded)


def test_native_sales_research_uses_public_map_evidence_without_inventing_pain():
    payload = build_native_research_payload(
        {
            "id": "lead-1",
            "name": "Клиника",
            "category": "стоматология",
            "rating": 4.1,
            "reviews_count": 27,
            "source_url": "https://yandex.ru/maps/org/example",
        },
        {"id": "workstream-1", "workstream_type": "localos_sales"},
    )

    assert payload["signals_json"]
    assert payload["signals_json"][0]["observed_fact"] == "В публичной карточке указан рейтинг 4.1 при 27 отзывах."
    assert payload["message_brief_json"]["pain"] == payload["signals_json"][0]["observed_fact"]
    assert payload["evidence_json"][0]["source_url"].startswith("https://yandex.ru/")


def test_native_partnership_research_uses_compatibility_without_pain():
    payload = build_native_research_payload(
        {
            "id": "lead-2",
            "name": "Фитнес-клуб",
            "category": "фитнес",
            "source_url": "https://example.ru",
        },
        {
            "id": "workstream-2",
            "workstream_type": "client_partnership",
            "client_business_name": "Салон",
        },
        {
            "match_json": {
                "recipient_observation": "В публичной карточке указаны услуги: фитнес, групповые тренировки.",
                "compatibility_hypothesis": "Гипотеза для проверки: у компаний пересекается локальная аудитория.",
                "relevance_bridge": "Есть основание проверить совместную механику.",
                "match_score": 84,
            }
        },
    )

    assert payload["signals_json"][0]["kind"] == "service_compatibility"
    assert payload["message_brief_json"]["pain"] == ""
    assert payload["message_brief_json"]["result"].startswith("проверить совместную механику")


def test_linked_public_telegram_signal_becomes_sourced_evidence():
    payload = build_native_research_payload(
        {
            "id": "lead-telegram",
            "name": "Фитнес-клуб",
            "source_url": "https://maps.example/fitness",
        },
        {
            "id": "workstream-telegram",
            "workstream_type": "client_partnership",
            "client_business_name": "Салон",
        },
        {
            "radar_signals": [{
                "chat_title": "Новости района",
                "message_text": "Фитнес-клуб запустил новую группу для жителей района.",
                "message_link": "https://t.me/district/42",
                "message_date": "2026-07-15T10:00:00Z",
                "relevance_score": 82,
            }],
        },
    )

    signal = payload["signals_json"][0]
    assert signal["kind"] == "telegram_post"
    assert signal["source_type"] == "telegram_public"
    assert signal["source_url"] == "https://t.me/district/42"
    assert signal["hypothesis"] is None


def test_safety_learning_migration_contains_required_contracts():
    migration = Path("alembic_migrations/versions/20260717_add_outreach_safety_learning.py").read_text(encoding="utf-8")

    for contract in (
        "outreach_sender_health_events",
        "outreach_inbound_events",
        "outreach_learning_events",
        "outreach_strategy_stats",
        "approved_snapshot_hash",
        "normalized_contact_hash",
        "awaiting_manual_send",
        "needs_evidence",
        "idempotency_key",
        "uq_outreachsendqueue_idempotency",
        "dispatch_started_at",
        "lead_signal_links",
    ):
        assert contract in migration


def test_learning_aggregation_uses_transaction_lock_and_health_recovery_boundary():
    source = Path("src/services/outreach_safety_service.py").read_text(encoding="utf-8")

    assert "pg_advisory_xact_lock" in source
    assert "event_type = 'recovered'" in source


def test_manual_channel_sent_event_is_included_in_learning_stats():
    source = Path("src/services/outreach_campaign_service.py").read_text(encoding="utf-8")

    assert 'if event_type in {"sent", "reply"}' in source
    assert 'outcome_type="sent"' in source
    assert '"source": "manual"' in source


def test_quality_gate_uses_18_point_contract_and_blocks_suppressed_recipient():
    candidate = {
        "recipient": "Клиника Ромашка",
        "observed_fact": "В карточке есть 14 отзывов и рейтинг 4.1.",
        "bridge": "Здесь можно проверить работу с отзывами.",
        "next_step": "Прислать короткий разбор",
        "source_url": "https://maps.example/clinic",
        "evidence_status": "observed",
        "freshness": "current_snapshot",
        "confidence": 0.95,
    }
    story = {"forbidden_claims": []}
    text = (
        "Клиника Ромашка: В карточке есть 14 отзывов и рейтинг 4.1. "
        "Здесь можно проверить работу с отзывами. Прислать короткий разбор?"
    )

    approved = _quality_gate(
        text, candidate, story,
        channel="telegram", channel_status="ready", suppressed=False,
    )
    blocked = _quality_gate(
        text, candidate, story,
        channel="telegram", channel_status="ready", suppressed=True,
    )

    assert approved["score"] == 18
    assert approved["verdict"] == "approve"
    assert blocked["score"] == 16
    assert blocked["verdict"] == "reject"
    assert "recipient_suppressed" in blocked["blocking_reasons"]


def test_founder_story_excludes_hypotheses_and_uses_only_confirmed_facts():
    story = _founder_story({
        "confirmed_at": "2026-07-17T10:00:00Z",
        "competence_story": "Непроверенная гипотеза",
        "outreach_context_json": {"competence_story_status": "hypothesis"},
        "proof_points_json": [
            {"fact": "Наблюдаемый опыт", "status": "observed"},
            {"fact": "Ещё одна гипотеза", "status": "hypothesis"},
        ],
        "verified_cases_json": [],
        "allowed_offers_json": ["Короткий разбор"],
        "forbidden_claims_json": [],
    })

    assert story is not None
    assert story["story"] == "Наблюдаемый опыт"
    assert "Гипотез" not in story["story"]


def test_founder_story_is_ranked_for_recipient_signal():
    profile = {
        "confirmed_at": "2026-07-17T10:00:00Z",
        "competence_story": "Мы запускали партнёрские программы для салонов",
        "outreach_context_json": {"competence_story_status": "approved"},
        "proof_points_json": [
            {"fact": "Наша команда наладила работу с отзывами и рейтингом карточки", "status": "approved"},
        ],
        "verified_cases_json": [],
        "allowed_offers_json": ["Короткий разбор"],
        "forbidden_claims_json": [],
    }

    story = _founder_story(profile, "низкий рейтинг и отзывы без ответа")

    assert story is not None
    assert "партнёрские программы" in story["story"]
    assert "отзывами" in story["proof"]


def test_learning_reuse_creates_draft_and_never_transfers_recipient_facts():
    source = Path("src/api/outreach_campaign_api.py").read_text(encoding="utf-8")

    assert "apply-learning-recommendation" in source
    assert '"facts_transferred": False' in source
    assert '"approval_required": True' in source
    assert "learning_segment_mismatch" in source
    assert "learning_recommendation_not_eligible" in source


def test_sender_strategy_context_fills_brief_without_inventing_recipient_facts():
    brief, readiness = build_message_brief(
        {"name": "Клиника", "category": ""},
        {"workstream_type": "localos_sales"},
        {
            "why_now": "В карточке есть отзывы без ответа.",
            "message_brief_json": {"pain": "Отзывы без ответа.", "proof": "Проверенный кейс."},
            "evidence_json": [],
            "sources_json": [],
        },
        {"contact_type": "email", "role_title": ""},
            {
                "confirmed_at": "2026-07-17T10:00:00Z",
                "display_name": "Александр",
                "role_title": "основатель",
                "company_name": "LocalOS",
                "competence_story": "Помогаем локальным компаниям выстраивать работу с карточками.",
            "proof_points_json": [{"fact": "Проверенный кейс.", "status": "approved"}],
            "verified_cases_json": [],
                "outreach_context_json": {
                    "competence_story_status": "approved",
                    "segments": ["стоматологии"],
                    "audience": "Владельцы стоматологий",
                    "recipient_roles": ["владелец"],
                    "product_outcome": "получить план улучшения карточки",
                    "allowed_ctas": ["Прислать короткий аудит?"],
                },
                "allowed_offers_json": ["Короткий аудит карточки"],
                "forbidden_claims_json": ["Не обещать рост обращений"],
                "voice_examples_json": ["Здравствуйте! Могу прислать короткий аудит?"],
            },
    )

    assert brief["segment"] == "стоматологии"
    assert brief["buyer_persona"] == "владелец"
    assert brief["result"] == "получить план улучшения карточки"
    assert brief["cta"] == "Прислать короткий аудит?"
    assert readiness["code"] == "ready"


def test_reply_runtime_delegates_atomic_campaign_stop_to_bounded_service():
    runtime = Path("src/api/prospecting/delivery_runtime.py").read_text(encoding="utf-8")
    inbound = Path("src/services/outreach_inbound_service.py").read_text(encoding="utf-8")

    assert "record_campaign_inbound_reaction(" in runtime
    assert "reply_arrived_during_provider_call" in inbound
    assert "status = 'reply_cancelled'" in inbound
    assert "record_learning_event(" in inbound
    assert len(runtime.splitlines()) < 2000


def test_worker_finalizes_no_reply_only_after_reply_sync_and_before_dispatch():
    worker = Path("src/worker.py").read_text(encoding="utf-8")
    function_start = worker.index("def _dispatch_outreach_queue_if_due()")
    function_end = worker.index("\ndef _run_card_automation_if_due()", function_start)
    block = worker[function_start:function_end]

    assert block.index("_sync_telegram_app_replies") < block.index("finalize_no_reply_campaigns")
    assert block.index("finalize_no_reply_campaigns") < block.index("dispatch_due_outreach_queue")
    assert 'OUTREACH_NO_REPLY_GRACE_HOURS", "168"' in block


def test_background_dispatch_fails_closed_without_explicit_cohort():
    result = dispatch_due_outreach_queue(
        batch_size=20,
        campaign_only=True,
        allowed_business_ids=[],
        allow_platform=False,
    )

    assert result["picked"] == 0
    assert result["sent"] == 0
    assert result["reason_code"] == "dispatch_cohort_not_configured"


def test_background_dispatch_query_targets_only_allowed_business_campaigns(monkeypatch):
    from api import admin_prospecting

    class FakeCursor:
        def __init__(self):
            self.calls = []

        def execute(self, query, params=()):
            self.calls.append((query, list(params)))

        def fetchone(self):
            return {"count": 0}

        def fetchall(self):
            return []

    class FakeConnection:
        def __init__(self):
            self.cursor_instance = FakeCursor()

        def cursor(self):
            return self.cursor_instance

        def commit(self):
            return None

        def close(self):
            return None

    connection = FakeConnection()
    monkeypatch.setattr(admin_prospecting, "get_db_connection", lambda: connection)

    result = dispatch_due_outreach_queue(
        batch_size=20,
        campaign_only=True,
        allowed_business_ids=["business-b", "business-a", "business-a"],
        allow_platform=False,
    )

    dispatch_query, dispatch_params = connection.cursor_instance.calls[1]
    assert result["picked"] == 0
    assert "q.campaign_touch_id IS NOT NULL" in dispatch_query
    assert "campaign.scope_type = 'business'" in dispatch_query
    assert "campaign.scope_type = 'platform'" not in dispatch_query
    assert dispatch_params[1:3] == ["business-a", "business-b"]


def test_worker_dispatch_is_limited_to_versioned_campaign_cohort():
    worker = Path("src/worker.py").read_text(encoding="utf-8")
    function_start = worker.index("def _dispatch_outreach_queue_if_due()")
    function_end = worker.index("\ndef _run_card_automation_if_due()", function_start)
    block = worker[function_start:function_end]
    dispatcher = Path("src/services/outreach_dispatch_service.py").read_text(encoding="utf-8")

    assert "OUTREACH_DISPATCH_BUSINESS_IDS" in block
    assert "OUTREACH_DISPATCH_PLATFORM_SCOPE_ENABLED" in block
    assert "dispatch_cohort_not_configured" in block
    assert "campaign_only=True" in block
    assert "allowed_business_ids=allowed_business_ids" in block
    assert "allow_platform=allow_platform" in block
    assert "q.campaign_touch_id IS NOT NULL" in dispatcher
    assert "campaign.business_id IN" in dispatcher
    assert "campaign.scope_type = 'platform'" in dispatcher
