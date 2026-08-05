from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.outreach_experiment_service import (
    ACTIVE_SOCIAL_MAP_GAP,
    SAFE_CORPUS_MESSAGE_RULES,
    STAGES,
    build_active_social_map_gap_signal,
    derive_composite_signal,
    dedupe_corpus_documents,
    next_stage,
    pattern_support_ready,
)
from services.outreach_safety_service import strategy_fingerprint
from services.outreach_founder_led_copy import founder_led_localos_text
from services.outreach_playbook import beauty_outreach_guidance, beauty_touch_learning_dimensions
from services.llm.registry import get_task_definition


ROOT = Path(__file__).resolve().parents[1]


def test_composite_signal_requires_map_gap_and_active_official_social():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    result = build_active_social_map_gap_signal(
        {"rating": 4.3, "reviews_count": 3, "source_url": "https://yandex.ru/maps/org/1"},
        {"official": True, "last_post_at": now - timedelta(days=2), "posts_30d": 6, "posts_90d": 10},
        now=now,
    )
    assert result["eligible"] is True
    assert result["pattern_key"] == ACTIVE_SOCIAL_MAP_GAP
    assert "рейтинг 4.3" in result["observed_fact"]
    assert "вкладывается" in result["hypothesis"]
    assert "не хватает времени" not in result["observed_fact"].lower()
    assert "теряет клиентов" not in result["observed_fact"].lower()


def test_composite_signal_rejects_unconfirmed_or_stale_social_activity():
    now = datetime(2026, 8, 5, tzinfo=timezone.utc)
    stale = build_active_social_map_gap_signal(
        {"rating": 4.1, "reviews_count": 2},
        {"official": True, "last_post_at": now - timedelta(days=45), "posts_30d": 0, "posts_90d": 20},
        now=now,
    )
    unofficial = build_active_social_map_gap_signal(
        {"rating": 4.1, "reviews_count": 2},
        {"official": False, "last_post_at": now - timedelta(days=2), "posts_30d": 10, "posts_90d": 20},
        now=now,
    )
    assert stale["eligible"] is False
    assert unofficial["eligible"] is False


def test_composite_signal_uses_linked_source_cadence_not_only_preview_posts():
    now = datetime.now(timezone.utc)
    signal = derive_composite_signal(
        {
            "rating": 4.3,
            "reviews_count": 3,
            "source_url": "https://yandex.ru/maps/org/1",
            "official_social_activity": {
                "official": True,
                "last_post_at": now - timedelta(days=1),
                "posts_30d": 6,
                "posts_90d": 12,
            },
        },
        [{"kind": "telegram_post", "observed_at": now.isoformat()}],
    )
    assert signal is not None
    assert signal["signal_combo"] == ACTIVE_SOCIAL_MAP_GAP


def test_pattern_support_deduplicates_and_requires_independent_sources():
    documents = [
        {"content": "Карты и отзывы", "source_id": "a"},
        {"content": "  Карты  и отзывы ", "source_id": "a"},
        {"content": "Социальные сети работают", "source_id": "a"},
        {"content": "Персонализация по действиям", "source_id": "b"},
    ]
    assert len(dedupe_corpus_documents(documents)) == 3
    assert pattern_support_ready(documents) is True


def test_stage_order_is_manual_and_bounded():
    assert STAGES[0] == {"key": "canary_1", "variant": "treatment", "size": 1}
    assert next_stage("canary_1") == "treatment_10_a"
    assert next_stage("treatment_100") is None
    assert all(stage["size"] <= 100 for stage in STAGES)


def test_learning_fingerprint_tracks_pattern_but_not_experiment_assignment():
    base = {
        "workstream_type": "localos_sales",
        "signal_kind": "composite_signal",
        "signal_combo": ACTIVE_SOCIAL_MAP_GAP,
        "pattern_id": "pattern-1",
        "pattern_version": 1,
        "opening_type": "specific_observation",
        "channel": "email",
    }
    first = strategy_fingerprint({**base, "experiment_id": "experiment-a", "cohort": "canary_1"})
    second = strategy_fingerprint({**base, "experiment_id": "experiment-b", "cohort": "treatment_10_a"})
    changed = strategy_fingerprint({**base, "pattern_version": 2})
    assert first == second
    assert changed != first


def test_implementation_keeps_corpus_filter_and_draft_only_boundary():
    api_source = (ROOT / "src/api/outreach_campaign_api.py").read_text(encoding="utf-8")
    service_source = (ROOT / "src/services/outreach_experiment_service.py").read_text(encoding="utf-8")
    assert "metadata_json->>'corpus_tag' = 'telegram_b2b'" in api_source
    assert '"drafts_prepared"' in api_source
    assert "external_dispatch_performed\": False" in api_source
    assert "automatic_dispatch\": False" in service_source
    assert "outreachsendqueue" not in service_source
    assert "ORDER BY has_existing_draft DESC" in service_source


def test_corpus_copy_change_invalidates_old_drafts():
    assert get_task_definition("outreach_personalization").prompt_version == "outreach_personalization_v12"


def test_beauty_playbook_keeps_corpus_method_separate_from_recipient_facts():
    playbook = beauty_outreach_guidance()
    assert playbook["method_source"] == "telegram_b2b"
    assert playbook["pain_language_status"] == "segment_hypothesis_only"
    assert len(playbook["method_rules"]) >= 6
    assert len(playbook["pain_library"]) == 7
    assert any(item["support"] == "partial" for item in playbook["pain_library"])
    constraints = " ".join(playbook["constraints"])
    assert "без отдельного evidence" in constraints


def test_beauty_playbook_labels_each_touch_for_outcome_learning():
    founder = beauty_touch_learning_dimensions("founder_story")
    proof = beauty_touch_learning_dimensions("proof")
    assert founder["playbook_version"] == "localos_outreach_playbook_v1"
    assert founder["pain_key"] == "operations_and_burnout"
    assert proof["pain_key"] == "marketing_and_clients"


def test_migration_has_three_versioned_experiment_tables():
    migration = (ROOT / "alembic_migrations/versions/20260805_add_outreach_experiments.py").read_text(encoding="utf-8")
    assert "outreach_knowledge_patterns" in migration
    assert "outreach_experiments" in migration
    assert "outreach_experiment_members" in migration
    assert "UNIQUE (pattern_key, version)" in migration


def test_treatment_copy_uses_social_map_contrast_audit_and_only_approved_price():
    candidate = {
        "sender_mode": "localos",
        "recipient": "Доктор-косметолог Татьяна Прокура",
        "recipient_segment": "private_beauty_specialist",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "signal_combo": ACTIVE_SOCIAL_MAP_GAP,
        "observed_fact": (
            "В карточке на картах рейтинг 4.3 и 3 отзывов. "
            "Официальная соцсеть обновлялась 2 дня назад; опубликовано 6 сообщений за 30 дней."
        ),
        "public_audit_url": "https://localos.pro/example-audit",
        "next_step": "Работа LocalOS от 1200 рублей в месяц",
    }
    text = founder_led_localos_text("signal", candidate, None)
    assert text is not None
    assert "активно ведёте соцсети" in text
    assert "рейтинг 4.3 и только 3 отзыва" in text
    assert "https://localos.pro/example-audit" in text
    assert "от 1200 рублей в месяц" in text
    assert "не успеваете" not in text
    assert "теряете клиентов" not in text


def test_active_social_copy_uses_audit_without_inventing_owner_pain():
    candidate = {
        "sender_mode": "localos",
        "recipient": "Freedom Beauty Studio",
        "recipient_segment": "beauty_team",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "evidence_kind": "telegram_post",
        "observed_fact": (
            'В публичном Telegram-источнике "FREEDOM | beauty studio" '
            'опубликовано: "Горящие окошки на завтра".'
        ),
        "map_observation": "Рейтинг - 4,3; публичных отзывов - 5.",
        "public_audit_url": "https://localos.pro/freedom-beauty-studio",
        "next_step": "Работа LocalOS от 1200 рублей в месяц",
    }
    text = founder_led_localos_text("signal", candidate, None)
    assert text is not None
    assert "в Telegram вы публикуете свободные окна для записи и активно ведёте канал" in text
    assert "Карты тоже могли бы помогать вам привлекать клиентов" in text
    assert "Сейчас в карточке на картах рейтинг 4,3 и всего 5 отзывов" in text
    assert "регулярно работаете" not in text
    assert "https://localos.pro/freedom-beauty-studio" in text
    assert "от 1200 рублей в месяц" in text
    assert "остаются на владельце" not in text
    assert "не хватает времени" not in text
    assert text.endswith("Вам может быть это интересно?")


def test_founder_follow_up_uses_operator_empathy_instead_of_product_abstraction():
    candidate = {
        "sender_mode": "localos",
        "recipient": "Линия красоты",
        "recipient_segment": "beauty_team",
        "sender": "Александр Демьянов",
        "sender_role": "основатель LocalOS",
        "founder_story": "Сам больше десяти лет в бизнесе.",
    }

    text = founder_led_localos_text("founder_story", candidate, None)

    assert "клиенты и ежедневная операционка всегда срочнее" in text
    assert "Сам больше десяти лет в бизнесе" in text
    assert '"Если не я, то никто"' in text
    assert "LocalOS не просто выдаёт" not in text


def test_corpus_compiler_uses_deepseek_then_gigachat_max_review():
    extract = get_task_definition("outreach_corpus_pattern_extract")
    review = get_task_definition("outreach_corpus_pattern_review")
    assert extract is not None and extract.primary_provider == "deepseek"
    assert extract.model_profile == "deepseek_reasoning"
    assert review is not None and review.primary_provider == "gigachat"
    assert review.model_profile == "gigachat_max"


def test_corpus_compiler_prompts_pin_exact_json_shapes():
    source = (ROOT / "src/services/outreach_experiment_service.py").read_text(encoding="utf-8")
    assert '"observation_rule":"..."' in source
    assert '"approved":true,"issues":[]' in source
    assert "Не добавляй другие ключи, markdown" in source


def test_model_extraction_cannot_define_executable_message_rules():
    rules = " ".join(SAFE_CORPUS_MESSAGE_RULES).lower()
    assert "до 30%" not in rules
    assert "кратно" not in rules
    assert "без дополнительных затрат" not in rules
    assert "проверяемыми числами" in rules
    assert "один вопрос" in rules
