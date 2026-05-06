from pathlib import Path


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0

    def execute(self, _sql, _params=None):
        self.calls += 1

    def fetchone(self):
        return {"count": len(self.rows)}

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


def test_industry_patterns_admin_ui_contains_safety_and_confirm_flows():
    source = Path("frontend/src/components/IndustryPatternsManagement.tsx").read_text()

    assert "Safety status" in source
    assert "Последние действия админки" in source
    assert "ConfirmActionPanel" in source
    assert "Business effect" in source
    assert "EffectList" in source
    assert "confirmation_token" in source
    assert "confirm: true" in source
    assert "/admin/industry-patterns/admin-events?limit=8" in source


def test_telegram_pending_pattern_markup_supports_fourth_and_fifth_accept_buttons(monkeypatch):
    import telegram_bot

    rows = [
        {
            "id": f"proposal-{index}",
            "industry_key": "food",
            "pattern_type": "news",
            "proposed_pattern": f"Паттерн {index}",
            "confidence": 0.8,
            "risk_level": "low",
            "examples_json": [{"text": f"пример {index}"}],
            "source_counts_json": {"successful_entities": 4, "news_samples": 3},
            "created_at": "2026-05-06",
        }
        for index in range(1, 6)
    ]

    monkeypatch.setattr(telegram_bot, "_is_superadmin_telegram_user", lambda _telegram_id: True)
    monkeypatch.setattr(telegram_bot, "ensure_industry_pattern_tables", lambda _conn: None)
    monkeypatch.setattr(telegram_bot, "get_db_connection", lambda: FakeConnection(rows))

    text, markup = telegram_bot._build_industry_pattern_proposals_text("1001", industry_key="all", page=0)
    buttons = [
        button.text
        for row in markup.inline_keyboard
        for button in row
    ]

    assert "Показаны: 1-5 из 5" in text
    assert "✅ Принять 4" in buttons
    assert "✅ Принять 5" in buttons
    assert "↩️ Доработать 5" in buttons
    assert "❌ Отклонить 5" in buttons
