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


def test_public_audit_regeneration_releases_read_transaction_before_ai(
    monkeypatch,
) -> None:
    class Connection:
        def __init__(self) -> None:
            self.commit_count = 0

        def cursor(self):
            return object()

        def commit(self) -> None:
            self.commit_count += 1

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    connection = Connection()
    commits_seen_by_ai: list[int] = []
    lead = {"id": "lead-1", "name": "Салон", "category": "Салон красоты"}

    monkeypatch.setattr(regenerate_all_active_public_audits, "_connect", lambda: connection)
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_pick_superadmin_user_id",
        lambda cursor: "user-1",
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_load_target_leads",
        lambda *args, **kwargs: [lead],
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_drop_mismatched_explicit_business_link",
        lambda value: value,
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_sync_lead_business_link_from_parse_history",
        lambda value: value,
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_sync_lead_contacts_from_parsed_data",
        lambda value: value,
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_normalize_lead_for_display",
        lambda value: value,
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_choose_languages",
        lambda display_lead, raw_lead: ("ru", ["ru"]),
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "build_lead_card_preview_snapshot",
        lambda display_lead: {},
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_build_admin_lead_offer_payload",
        lambda **kwargs: {"audit": {}},
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_generate_lead_audit_enrichment",
        lambda *args, **kwargs: commits_seen_by_ai.append(connection.commit_count) or {},
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "normalize_public_audit_page_json",
        lambda value: value,
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_ensure_slug",
        lambda *args, **kwargs: "salon",
    )
    monkeypatch.setattr(
        regenerate_all_active_public_audits,
        "_upsert_offer",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "sys.argv",
        ["regenerate_all_active_public_audits.py", "--skip-schema-ensure"],
    )

    regenerate_all_active_public_audits.main()

    assert commits_seen_by_ai == [1]
