from core import card_automation
from datetime import date
from services import superadmin_telegram_notifications


class _FakeConn:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.commit_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1


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
    assert superadmin_telegram_notifications.CONTENT_URL in text
    assert "Автоматических касаний на сегодня нет" in text


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

    assert "LocalOS → 047 Beauty Zone · Email в 10:00: уйдёт автоматически" in text
    assert "Оливер → Legenda · MAX в 12:00: отправить вручную" in text
    assert superadmin_telegram_notifications.OUTREACH_URL in text


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
