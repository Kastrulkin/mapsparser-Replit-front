from core import card_automation
from datetime import date
from services import operator_scope_summary, superadmin_telegram_notifications
import sys
import types


class _FakeConn:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.commit_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1


def test_scheduled_review_sync_enqueues_delta_task(monkeypatch):
    captured = {}
    fake_module = types.ModuleType("api.admin_prospecting")

    def enqueue(business_id, user_id, source_url, **kwargs):
        captured.update(
            {
                "business_id": business_id,
                "user_id": user_id,
                "source_url": source_url,
                **kwargs,
            }
        )
        return {"id": "queue-1", "existing": False, "source": "apify_yandex", "task_type": kwargs["task_type"]}

    fake_module._enqueue_parse_task_for_business = enqueue
    monkeypatch.setitem(sys.modules, "api.admin_prospecting", fake_module)
    monkeypatch.setattr(card_automation, "_business_context", lambda _conn, _business_id: {"owner_id": "owner-1"})
    monkeypatch.setattr(
        card_automation,
        "_map_link_for_business",
        lambda _conn, _business_id: "https://yandex.ru/maps/org/test/1/",
    )

    result = card_automation._enqueue_review_sync(_FakeConn(), "business-1")

    assert result["task_type"] == "reviews_delta"
    assert captured["task_type"] == "reviews_delta"


def test_run_card_automation_action_rolls_back_before_error_event(monkeypatch):
    conn = _FakeConn()
    observed: dict[str, int | str] = {}

    monkeypatch.setattr(card_automation, "ensure_card_automation_tables", lambda _conn: None)
    monkeypatch.setattr(card_automation, "_ensure_settings_row", lambda _conn, _business_id: None)
    monkeypatch.setattr(
        card_automation,
        "_load_settings_row",
        lambda _conn, _business_id: {"review_sync_interval_hours": 24},
    )

    def _boom(_conn, _business_id):
        raise RuntimeError("sql failed before rollback")

    def _record_event(_conn, **kwargs):
        observed["rollback_calls_during_event"] = conn.rollback_calls
        observed["event_status"] = str(kwargs.get("status") or "")

    def _update_runtime(_conn, **kwargs):
        observed["runtime_status"] = str(kwargs.get("status") or "")

    monkeypatch.setattr(card_automation, "_enqueue_review_sync", _boom)
    monkeypatch.setattr(card_automation, "_record_event", _record_event)
    monkeypatch.setattr(card_automation, "_update_action_runtime", _update_runtime)

    result = card_automation.run_card_automation_action(
        conn,
        business_id="biz_1",
        action_type=card_automation.ACTION_REVIEW_SYNC,
        triggered_by="scheduler",
    )

    assert result["success"] is False
    assert result["status"] == "error"
    assert observed["rollback_calls_during_event"] == 1
    assert observed["event_status"] == "error"
    assert observed["runtime_status"] == "error"
    assert conn.commit_calls == 1


def test_run_card_automation_action_returns_error_even_if_error_logging_fails(monkeypatch):
    conn = _FakeConn()

    monkeypatch.setattr(card_automation, "ensure_card_automation_tables", lambda _conn: None)
    monkeypatch.setattr(card_automation, "_ensure_settings_row", lambda _conn, _business_id: None)
    monkeypatch.setattr(
        card_automation,
        "_load_settings_row",
        lambda _conn, _business_id: {"review_sync_interval_hours": 24},
    )
    monkeypatch.setattr(
        card_automation,
        "_enqueue_review_sync",
        lambda _conn, _business_id: (_ for _ in ()).throw(RuntimeError("queue failure")),
    )

    def _broken_record_event(_conn, **kwargs):
        raise RuntimeError("cannot write error event")

    monkeypatch.setattr(card_automation, "_record_event", _broken_record_event)
    monkeypatch.setattr(card_automation, "_update_action_runtime", lambda _conn, **kwargs: None)

    result = card_automation.run_card_automation_action(
        conn,
        business_id="biz_1",
        action_type=card_automation.ACTION_REVIEW_SYNC,
        triggered_by="scheduler",
    )

    assert result["success"] is False
    assert result["status"] == "error"
    assert result["message"] == "queue failure"
    assert conn.rollback_calls == 2
    assert conn.commit_calls == 0


class _BusinessCursor:
    def __init__(self, row):
        self.row = row
        self.executed: list[str] = []

    def execute(self, query, params):
        self.executed.append(" ".join(str(query).split()))

    def fetchone(self):
        return self.row


class _BusinessConn:
    def __init__(self, row):
        self.cursor_obj = _BusinessCursor(row)

    def cursor(self):
        return self.cursor_obj


def test_business_context_prefers_ai_agent_language_column(monkeypatch):
    conn = _BusinessConn(
        {
            "id": "biz_1",
            "owner_id": "user_1",
            "name": "Capri",
            "language": "ru",
            "address": "Кудрово",
        }
    )

    def _fake_has_column(_cursor, table_name, column_name):
        return table_name == "businesses" and column_name == "ai_agent_language"

    monkeypatch.setattr(card_automation, "_table_has_column", _fake_has_column)

    result = card_automation._business_context(conn, "biz_1")

    assert result["language"] == "ru"
    assert "ai_agent_language AS language" in conn.cursor_obj.executed[0]


def test_generate_news_supports_seo_keyword_prompt_placeholders(monkeypatch):
    observed: dict[str, str] = {}

    class _Cursor:
        def __init__(self) -> None:
            self.last_query = ""

        def execute(self, query, params=None):
            self.last_query = " ".join(str(query).split())

        def fetchone(self):
            if "FROM businesses" in self.last_query:
                return {
                    "id": "biz_1",
                    "owner_id": "user_1",
                    "name": "Оливер",
                    "language": "ru",
                    "address": "Санкт-Петербург",
                    "business_type": "beauty_salon",
                    "industry": "beauty",
                    "categories": [],
                }
            if "FROM aiprompts" in self.last_query:
                return {
                    "prompt_text": (
                        "Бизнес: {business_name}\n"
                        "SEO: {seo_keywords}\n"
                        "Top: {seo_keywords_top10}\n"
                        "Hint: {seo_generation_hint}\n"
                        "Контекст: {service_context}\n"
                        'Верни JSON: {"news": "текст новости"}'
                    )
                }
            return None

        def fetchall(self):
            return []

    class _Conn:
        def __init__(self) -> None:
            self.cursor_obj = _Cursor()

        def cursor(self):
            return self.cursor_obj

    monkeypatch.setattr(card_automation, "_table_has_column", lambda *_args: True)
    monkeypatch.setattr(card_automation, "_load_settings_row", lambda *_args: {"news_content_source": "services"})
    monkeypatch.setattr(card_automation, "load_active_industry_patterns", lambda *_args: [])
    monkeypatch.setattr(card_automation, "record_ai_learning_event", lambda **_kwargs: None)

    def _fake_analyze(prompt, **_kwargs):
        observed["prompt"] = prompt
        return '{"news": "Короткая новость"}'

    monkeypatch.setattr(card_automation, "analyze_text_with_gigachat", _fake_analyze)

    result = card_automation._generate_news_for_business(_Conn(), "biz_1")

    assert result["news_id"]
    assert "SEO:" in observed["prompt"]
    assert "Top:" in observed["prompt"]
    assert "Hint:" in observed["prompt"]
    assert '{"news": "текст новости"}' in observed["prompt"]


def test_digest_plan_lines_follow_weekly_rhythm_for_starter():
    monday = card_automation._digest_plan_lines_for_weekday(date(2026, 5, 4), "starter", False)
    assert "• Ответить на новые отзывы и не оставлять негатив без реакции" in monday
    assert "• Сгенерировать новость недели по контент-плану" in monday
    assert "• Добавить свежие фото в карточку: без фото новости и услуги работают слабее" in monday

    wednesday = card_automation._digest_plan_lines_for_weekday(date(2026, 5, 6), "starter", False)
    assert "• Обновить фото в карточке: показать свежие работы, витрину, зал или процесс" in wednesday
    assert "• Сгенерировать новость недели по контент-плану" not in wednesday

    friday = card_automation._digest_plan_lines_for_weekday(date(2026, 5, 8), "starter", False)
    assert "• Проверить статистику карт: звонки, маршруты, просмотры и динамику отзывов" in friday


def test_digest_plan_lines_ask_concierge_for_new_photos_on_monday():
    lines = card_automation._digest_plan_lines_for_weekday(date(2026, 5, 4), "concierge", False)
    assert "• Прислать новые фото для карточек: интерьер, работы, товары или команда" in lines
    assert "• Добавить свежие фото в карточку: без фото новости и услуги работают слабее" not in lines


def test_superadmin_morning_digest_names_posts_and_separates_manual_actions():
    text = superadmin_telegram_notifications.format_superadmin_morning_operations(
        [
            {
                "business_name": "Весёлая расчёска",
                "title": "Летние стрижки",
                "platform": "telegram",
                "publish_mode": "api",
                "status": "queued",
                "approved_at": "2026-07-23T07:00:00Z",
            },
            {
                "business_name": "Весёлая расчёска",
                "title": "Летние стрижки",
                "platform": "vk",
                "publish_mode": "api",
                "status": "needs_review",
                "approved_at": None,
            },
        ],
        [],
    )

    assert "«Летние стрижки» → Telegram: выйдет автоматически" in text
    assert "«Летние стрижки» → VK: проверить и подтвердить текст" in text
    assert superadmin_telegram_notifications.CONTENT_URL not in text
    assert "Аутрич" not in text


def test_superadmin_morning_digest_explains_automatic_and_manual_outreach():
    text = superadmin_telegram_notifications.format_superadmin_morning_operations(
        [],
        [
            {
                "business_name": "LocalOS",
                "lead_name": "047 Beauty Zone",
                "channel": "email",
                "local_time": "10:00",
                "touch_status": "scheduled",
                "campaign_status": "approved",
                "queue_status": "queued",
            },
            {
                "business_name": "Оливер",
                "lead_name": "Legenda",
                "channel": "max",
                "local_time": "12:00",
                "touch_status": "awaiting_manual_send",
                "campaign_status": "approved",
                "queue_status": None,
            },
        ],
    )

    assert "1 касание · Email · по расписанию на 10:00: уйдут автоматически" in text
    assert "1 касание · MAX · по расписанию на 12:00: нужно отправить вручную" in text
    assert superadmin_telegram_notifications.OUTREACH_URL not in text


def test_superadmin_morning_digest_groups_disabled_outreach_instead_of_listing_every_lead():
    items = [
        {
            "business_name": "LocalOS",
            "lead_name": f"Лид {index}",
            "channel": "email",
            "local_time": f"08:{index:02d}",
            "touch_status": "scheduled",
            "campaign_status": "approved",
            "queue_status": "queued",
            "dispatch_enabled": False,
        }
        for index in range(10)
    ]

    text = superadmin_telegram_notifications.format_superadmin_morning_operations([], items)

    assert "10 касаний · Email · по расписанию 08:00–08:09: не будут отправлены — автоматическая отправка выключена" in text
    assert "Лид 0" not in text
    assert "Ещё 2 касаний" not in text


def test_superadmin_platform_attention_prioritizes_reply_and_hides_duplicate_metrics():
    text = superadmin_telegram_notifications.format_superadmin_platform_attention(
        {
            "attention_items": [
                {"id": "failed_jobs", "count": 1647, "affected_businesses": 120},
                {"id": "pending_approvals", "count": 24},
                {"id": "outreach_replies", "count": 1},
            ],
            "metrics": [
                {"key": "businesses_total", "value": 1645},
                {"key": "networks_total", "value": 11},
                {"key": "failed_jobs", "value": 1647},
            ],
        }
    )

    assert text.index("Новый ответ в аутриче") < text.index("24 действия ждут подтверждения")
    assert "1 647 заданий обновления завершились с ошибкой" in text
    assert "Затронуто 120 бизнесов" in text
    assert "1 645 клиентских аккаунтов · 11 сетей" in text
    assert "Данные\n" not in text


def test_superadmin_platform_attention_names_unanswered_reviews() -> None:
    text = superadmin_telegram_notifications.format_superadmin_platform_attention(
        {
            "attention_items": [
                {"id": "reviews_unanswered", "count": 10, "affected_businesses": 1},
            ],
            "metrics": [
                {"key": "businesses_total", "value": 1},
                {"key": "networks_total", "value": 0},
            ],
        }
    )

    assert "10 отзывов без ответа" in text
    assert "Нужно подготовить ответы" in text


def test_platform_summary_includes_unanswered_reviews(monkeypatch) -> None:
    class _PlatformCursor:
        def __init__(self) -> None:
            self.query = ""

        def execute(self, query, params=None) -> None:
            self.query = " ".join(str(query or "").lower().split())

        def fetchone(self):
            if "from businesses" in self.query:
                return {"cnt": 3}
            if "from networks" in self.query:
                return {"cnt": 1}
            return {"cnt": 0}

    def _count(_cursor, table_name, query, params=()):
        if table_name != "externalbusinessreviews":
            return 0
        if "distinct" in " ".join(str(query).lower().split()):
            return 1
        return 10

    monkeypatch.setattr(operator_scope_summary, "_safe_count", _count)
    summary = operator_scope_summary._platform_summary(
        _PlatformCursor(),
        {"kind": "platform", "id": "platform"},
    )

    review_item = next(item for item in summary["attention_items"] if item["id"] == "reviews_unanswered")
    assert review_item["count"] == 10
    assert review_item["affected_businesses"] == 1


def test_platform_summary_counts_only_current_client_contexts_and_actionable_items(monkeypatch) -> None:
    """Lead parser copies, delivery failures and expired approvals are not platform work."""

    class _PlatformCursor:
        def __init__(self) -> None:
            self.query = ""

        def execute(self, query, params=None) -> None:
            self.query = " ".join(str(query or "").lower().split())

        def fetchone(self):
            if "from businesses" in self.query:
                client_only = "entity_group" in self.query and "client" in self.query
                return {"cnt": 14 if client_only else 1966}
            if "from networks" in self.query:
                client_only = "entity_group" in self.query and "client" in self.query
                return {"cnt": 3 if client_only else 11}
            return {"cnt": 0}

    def _count(_cursor, table_name, query, params=()):
        normalized = " ".join(str(query).lower().split())
        if table_name == "action_requests":
            return 0 if "action_approvals" in normalized and "expires_at" in normalized else 24
        if table_name == "outreach_campaign_touches":
            true_replies_only = "needs_attention" not in normalized
            return 0 if true_replies_only else 3
        return 0

    monkeypatch.setattr(operator_scope_summary, "_safe_count", _count)
    summary = operator_scope_summary._platform_summary(
        _PlatformCursor(),
        {"kind": "platform", "id": "platform"},
    )

    metrics = {item["key"]: item["value"] for item in summary["metrics"]}
    assert metrics["businesses_total"] == 14
    assert metrics["networks_total"] == 3
    assert metrics["pending_approvals"] == 0
    assert metrics["outreach_replies"] == 0


def test_reply_notification_contains_original_touch_reply_and_stop_status():
    text = superadmin_telegram_notifications.format_outreach_reply_notification(
        {
            "business_name": "Весёлая расчёска",
            "lead_name": "Yes Apart",
            "channel": "telegram",
            "classification": "interested",
            "stops_campaign": True,
            "outbound_text": "Хотим предложить особые условия для ваших жителей.",
            "raw_payload_json": {"raw_reply": "Да, пришлите подробности"},
        }
    )

    assert "Весёлая расчёска → Yes Apart · Telegram" in text
    assert "Хотим предложить особые условия" in text
    assert "Да, пришлите подробности" in text
    assert "Следующие касания остановлены" in text


def test_reply_notification_query_does_not_use_question_mark_json_operator():
    class _Cursor:
        def execute(self, query, params=None):
            assert "?" not in str(query)
            assert params == (20,)

        def fetchall(self):
            return []

    class _Conn:
        def cursor(self):
            return _Cursor()

    assert superadmin_telegram_notifications.collect_pending_outreach_reply_notifications(_Conn()) == []
