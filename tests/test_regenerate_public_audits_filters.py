from scripts import regenerate_all_active_public_audits


class AuditCursor:
    def __init__(self) -> None:
        self.query = ""
        self.params = []

    def execute(self, query, params=None):
        self.query = str(query)
        self.params = list(params or [])

    def fetchall(self):
        return []


def test_public_audit_regeneration_can_target_localos_beauty_leads() -> None:
    cursor = AuditCursor()
    regenerate_all_active_public_audits._load_target_leads(
        cursor,
        None,
        None,
        None,
        None,
        None,
        False,
        True,
        False,
        False,
        "localos_sales",
        "(салон красоты|парикмах|косметолог)",
    )

    assert "FROM lead_workstreams ws" in cursor.query
    assert "LOWER(COALESCE(l.category, '')) ~ %s" in cursor.query
    assert "localos_sales" in cursor.params
    assert cursor.params[-1] == "(салон красоты|парикмах|косметолог)"
