from services.telegram_control_scope import save_scope_notification_preferences


class PreferenceCursor:
    def __init__(self):
        self.rows = []
        self.saved = None

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        if "to_regclass" in normalized:
            self.rows = [{"table_ref": "public.telegramcontrolpreferences"}]
        elif normalized.startswith("select * from telegramcontrolpreferences"):
            self.rows = [{"notification_preferences_json": {"business:b-2": {"reviews": True}}}]
        elif normalized.startswith("insert into telegramcontrolpreferences"):
            self.saved = params[2].adapted
            self.rows = []
        else:
            raise AssertionError(normalized)

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_notification_preferences_are_isolated_per_scope_and_allowlisted():
    cursor = PreferenceCursor()
    result = save_scope_notification_preferences(
        cursor,
        user_id="u-1",
        telegram_id="tg-1",
        scope={"kind": "network", "id": "n-1"},
        notifications={"reviews": True, "errors": False, "unsafe": True},
    )

    assert result == {"reviews": True, "errors": False}
    assert cursor.saved["network:n-1"] == result
    assert cursor.saved["business:b-2"] == {"reviews": True}
