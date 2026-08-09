from datetime import datetime, timezone

import services.operator_mobile_today as mobile_today


def _growth(priority=80):
    return {
        "generated_at": "2026-07-27T08:00:00+00:00",
        "summary": {"completed_milestones": 3, "total_milestones": 10},
        "focus_action": {
            "title": "Подготовить контент",
            "reason": "План заканчивается",
            "expected_outcome": "Неделя публикаций будет готова",
            "cta_label": "Открыть контент",
            "cta_url": "/dashboard/content",
            "priority": priority,
        },
        "areas": [{"key": "content", "action": {"cta_label": "Открыть", "cta_url": "/dashboard/content"}}],
        "recent_achievements": [],
        "growth_loop": {"mission_id": "growth-content"},
        "data_health": {"status": "fresh"},
        "analytics_level": {"level": "baseline", "label": "Базовая аналитика"},
        "rhythm": {"status": "forming", "active_weeks": 2},
    }


def test_today_and_progress_use_the_same_focus(monkeypatch):
    summary = {
        "primary_action": {
            "id": "reviews_unanswered",
            "title": "Ответить на отзывы",
            "description": "Есть четыре новых отзыва",
            "severity": "high",
            "count": 4,
        },
        "freshness": {"status": "live"},
        "data_warnings": [],
    }
    monkeypatch.setattr(mobile_today, "build_operator_scope_summary", lambda *_args, **_kwargs: summary)
    monkeypatch.setattr(mobile_today, "_load_active_work", lambda *_args: [])
    monkeypatch.setattr(mobile_today, "_load_changes", lambda *_args: [])
    monkeypatch.setattr(mobile_today, "_load_community_pulse", lambda *_args: [])
    monkeypatch.setattr(mobile_today, "_load_completed_results", lambda *_args: [])
    scope = {"kind": "business", "id": "business-1", "business_ids": ["business-1"]}

    today = mobile_today.build_mobile_today(object(), scope=scope, user_id="user-1", growth_loader=lambda _business_id: _growth())
    progress = mobile_today.build_mobile_progress(object(), scope=scope, user_id="user-1", growth_loader=lambda _business_id: _growth())

    assert today["focus_action"] == progress["focus_action"]
    assert today["focus_action"]["screen"] == "content"
    assert progress["areas"][0]["action"]["screen"] == "content"
    assert today["growth_loop"]["mission_id"] == "growth-content"
    assert today["analytics_level"] == progress["analytics_level"]
    assert today["rhythm"] == progress["rhythm"]


def test_today_uses_exact_rolling_24_hour_window(monkeypatch):
    observed_cutoffs = []
    monkeypatch.setattr(mobile_today, "build_operator_scope_summary", lambda *_args, **_kwargs: {"primary_action": None})
    monkeypatch.setattr(mobile_today, "_load_active_work", lambda *_args: [])
    monkeypatch.setattr(mobile_today, "_load_changes", lambda _cursor, _scope, cutoff: observed_cutoffs.append(cutoff) or [])
    monkeypatch.setattr(mobile_today, "_load_community_pulse", lambda *_args: [])
    monkeypatch.setattr(mobile_today, "_load_completed_results", lambda *_args: [])
    now = datetime(2026, 7, 27, 9, 30, tzinfo=timezone.utc)

    payload = mobile_today.build_mobile_today(
        object(),
        scope={"kind": "business", "id": "business-1", "business_ids": ["business-1"]},
        user_id="user-1",
        now=now,
        growth_loader=lambda _business_id: _growth(),
    )

    assert observed_cutoffs == [datetime(2026, 7, 26, 9, 30, tzinfo=timezone.utc)]
    assert payload["period"] == {"kind": "rolling_24h", "since": "2026-07-26T09:30:00+00:00"}


def test_pulse_hides_unconfirmed_topic_and_keeps_provenance():
    single = [{
        "source_id": "source-1",
        "chat_title": "Owners One",
        "telegram_message_id": "1",
        "message_text": "Владельцы обсуждают подорожание красителей",
        "message_date": "2026-07-27T08:00:00+00:00",
    }]
    assert mobile_today._cluster_pulse(single) == []

    confirmed = single + [
        {
            "source_id": "source-2",
            "chat_title": "Owners Two",
            "telegram_message_id": "2",
            "message_text": "Обсуждают подорожание красителей и смену бренда",
            "message_date": "2026-07-27T08:10:00+00:00",
            "message_link": "https://t.me/owners/2",
        }
    ]
    pulse = mobile_today._cluster_pulse(confirmed)

    assert len(pulse) == 1
    assert pulse[0]["message_count"] == 2
    assert pulse[0]["sources_count"] == 2
    assert {item["message_id"] for item in pulse[0]["provenance"]} == {"1", "2"}


def test_pulse_does_not_merge_unrelated_long_business_posts():
    rows = [
        {
            "source_id": "calls",
            "chat_title": "Beauty Calls",
            "telegram_message_id": "1",
            "message_text": "Сколько денег салон теряет на пропущенных звонках? Разбираем возврат клиентов и запись.",
            "message_date": "2026-07-29T08:00:00+00:00",
        },
        {
            "source_id": "margin",
            "chat_title": "Beauty Finance",
            "telegram_message_id": "2",
            "message_text": "Парадокс оборота: почему рост выручки не означает рост прибыли? Считаем маржу салона.",
            "message_date": "2026-07-29T09:00:00+00:00",
        },
        {
            "source_id": "education",
            "chat_title": "Beauty Education",
            "telegram_message_id": "3",
            "message_text": "Как добавить новую услугу без покупки оборудования? Обсуждаем обучение мастеров.",
            "message_date": "2026-07-29T10:00:00+00:00",
        },
    ]

    assert mobile_today._cluster_pulse(rows) == []


def test_pulse_cluster_links_only_to_primary_source():
    rows = [
        {
            "source_id": "law-one",
            "chat_title": "Beauty Law",
            "telegram_message_id": "11",
            "message_text": "Обсуждают новые требования к маркировке косметики",
            "message_date": "2026-07-29T08:00:00+00:00",
            "message_link": "https://t.me/beautylaw/11",
        },
        {
            "source_id": "law-two",
            "chat_title": "Salon Owners",
            "telegram_message_id": "12",
            "message_text": "Новые требования к маркировке косметики обсуждают владельцы салонов",
            "message_date": "2026-07-29T09:00:00+00:00",
            "message_link": "https://t.me/salonowners/12",
        },
    ]

    pulse = mobile_today._cluster_pulse(rows)

    assert len(pulse) == 1
    assert pulse[0]["eyebrow"] == "Обсуждали"
    assert pulse[0]["source_url"] in {"https://t.me/beautylaw/11", "https://t.me/salonowners/12"}
    assert len(pulse[0]["source_links"]) == 1


def test_growth_focus_wins_when_operator_item_has_lower_effect():
    focus = mobile_today.select_daily_focus(
        {"primary_action": {"id": "minor", "title": "Проверить", "severity": "low", "count": 1}},
        _growth(priority=75),
        {"kind": "business"},
    )

    assert focus["title"] == "Подготовить контент"
    assert focus["screen"] == "content"
