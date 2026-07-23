from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.discovered_telegram_source_service import (
    discovered_telegram_signals,
    parse_telegram_reference,
    source_attribution_for_lead,
    sync_discovered_telegram_sources,
)
from services.contact_intelligence_service import (
    evaluate_first_message,
    exclude_public_channel_contacts,
)


def test_public_telegram_reference_is_normalized_without_assuming_direct_message():
    reference = parse_telegram_reference("https://t.me/s/LocalOS_news/123?single")

    assert reference == {
        "kind": "public_reference",
        "username": "LocalOS_news",
        "canonical_url": "https://t.me/LocalOS_news",
        "discovered_url": "https://t.me/s/LocalOS_news/123?single",
        "message_id": "123",
    }


def test_booking_provider_channel_is_shared_source_not_lead_channel(monkeypatch):
    class Cursor:
        def __init__(self):
            self.last_query = ""
            self.executions = []

        def execute(self, query, params=None):
            self.last_query = query
            self.executions.append((query, params or ()))

        def fetchall(self):
            if "FROM lead_workstreams" in self.last_query:
                return [{
                    "id": "workstream-047",
                    "workstream_type": "client_partnership",
                    "client_business_id": "business-047",
                }]
            return []

        def fetchone(self):
            if "FROM outreach_sender_accounts" in self.last_query:
                return {"account_id": "telegram-account", "radar_enabled": True}
            return None

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self, **_kwargs):
            return self.cursor_instance

    saved_sources = []

    def fake_upsert_source(_conn, **payload):
        saved_sources.append(payload)
        return {"id": "source-dikidi"}

    monkeypatch.setattr(
        "services.discovered_telegram_source_service.upsert_source",
        fake_upsert_source,
    )
    connection = Connection()

    result = sync_discovered_telegram_sources(
        connection,
        {
            "id": "lead-047",
            "name": "047 Beauty Zone",
            "messenger_links_json": ["https://t.me/dikidi_business"],
        },
    )

    assert result["references"] == 1
    assert result["sources"] == 1
    assert saved_sources[0]["title"] == "Telegram · Dikidi"
    assert not any(
        "INSERT INTO lead_signal_links" in query
        for query, _params in connection.cursor_instance.executions
    )


def test_residential_telegram_source_belongs_to_complex_not_sender_business():
    attribution = source_attribution_for_lead({
        "id": "lead-legenda-yakhtennaya",
        "name": "Legenda на Яхтенной, 24",
        "category": "Жилой комплекс",
    })

    assert attribution == {
        "source_owner_type": "residential_complex",
        "source_owner_role": "outreach_recipient",
        "source_owner_scope": "lead_signal_links",
        "sender_business_is_owner": False,
        "lead_attribution": "recipient_signal_source",
    }


def test_residential_source_is_saved_as_recipient_radar_source(monkeypatch):
    class Cursor:
        def __init__(self):
            self.last_query = ""
            self.executions = []

        def execute(self, query, params=None):
            self.last_query = query
            self.executions.append((query, params or ()))

        def fetchall(self):
            if "FROM lead_workstreams" in self.last_query:
                return [{
                    "id": "workstream-legenda",
                    "workstream_type": "client_partnership",
                    "client_business_id": "business-oliver",
                }]
            return []

        def fetchone(self):
            if "FROM outreach_sender_accounts" in self.last_query:
                return {"account_id": "telegram-account", "radar_enabled": True}
            return None

        def close(self):
            return None

    class Connection:
        def __init__(self):
            self.cursor_instance = Cursor()

        def cursor(self, **_kwargs):
            return self.cursor_instance

    saved_sources = []

    def fake_upsert_source(_conn, **payload):
        saved_sources.append(payload)
        return {"id": "source-legenda"}

    monkeypatch.setattr(
        "services.discovered_telegram_source_service.upsert_source",
        fake_upsert_source,
    )
    connection = Connection()

    result = sync_discovered_telegram_sources(
        connection,
        {
            "id": "lead-legenda-yakhtennaya",
            "name": "Legenda на Яхтенной, 24",
            "category": "Жилой комплекс",
            "messenger_links_json": ["https://t.me/LegendaDevelopment"],
        },
    )

    assert result == {"references": 1, "sources": 1, "queued": 1}
    assert saved_sources[0]["title"] == "Telegram ЖК · @LegendaDevelopment"
    assert saved_sources[0]["source_role"] == "community"
    assert saved_sources[0]["business_id"] == "business-oliver"
    assert saved_sources[0]["metadata"]["source_owner_type"] == "residential_complex"
    assert saved_sources[0]["metadata"]["sender_business_is_owner"] is False
    assert any(
        "INSERT INTO lead_signal_links" in query
        for query, _params in connection.cursor_instance.executions
    )


def test_private_invites_shares_and_bots_are_not_channel_candidates():
    assert parse_telegram_reference("https://t.me/+privateInvite") is None
    assert parse_telegram_reference("https://t.me/share/url?url=https://localos.pro") is None
    assert parse_telegram_reference("https://example.com/localos") is None
    assert parse_telegram_reference("https://t.me/localos_helper_bot")["kind"] == "bot"


def test_only_specific_fresh_channel_posts_become_personalization_signals():
    now = datetime.now(timezone.utc)

    class Cursor:
        description = None

        def execute(self, _query, _params=None):
            return None

        def fetchall(self):
            return [
                {
                    "message_text": "Открыли набор на новый курс: осталось 12 мест, старт уже в августе.",
                    "message_link": "https://t.me/example/10",
                    "message_date": now - timedelta(days=3),
                    "chat_title": "Example",
                    "metadata_json": {"auto_discovered": True},
                },
                {
                    "message_text": "Доброе утро, друзья. Желаем всем прекрасного дня и отличного настроения!",
                    "message_link": "https://t.me/example/9",
                    "message_date": now - timedelta(days=2),
                    "chat_title": "Example",
                    "metadata_json": {"auto_discovered": True},
                },
                {
                    "message_text": "Новый курс уже открыт, запись доступна на сайте, количество мест ограничено.",
                    "message_link": "https://t.me/example/1",
                    "message_date": now - timedelta(days=220),
                    "chat_title": "Example",
                    "metadata_json": {"auto_discovered": True},
                },
            ]

    signals = discovered_telegram_signals(
        Cursor(),
        {"name": "Example", "category": "Школа танцев", "city": "Москва"},
        {"id": "workstream-1"},
    )

    assert len(signals) == 1
    assert signals[0]["message_link"] == "https://t.me/example/10"
    assert signals[0]["auto_discovered"] is True
    assert signals[0]["relevance_score"] >= 60
    assert signals[0]["source_owner_type"] == "prospecting_recipient"
    assert signals[0]["source_owner_name"] == "Example"
    assert signals[0]["sender_business_is_owner"] is False


def test_monitor_requires_radar_permission_and_preflights_auto_discovered_sources():
    source = Path("src/services/knowledge_public_telegram.py").read_text(encoding="utf-8")

    assert "JOIN telegram_account_permissions permission" in source
    assert "permission.radar_enabled = TRUE" in source
    assert "source.status = 'candidate'" in source
    assert "mark_discovered_source_classification" in source
    assert "inspect_telegram_entity" in source
    assert 'classification_method="telegram_entity_api"' in source


def test_discovery_is_scoped_and_linked_to_workstream():
    source = Path("src/services/discovered_telegram_source_service.py").read_text(encoding="utf-8")
    migration = Path(
        "alembic_migrations/versions/20260720_link_discovered_telegram_sources.py"
    ).read_text(encoding="utf-8")

    assert "sender.scope_type = %s" in source
    assert "COALESCE(sender.business_id, '') = COALESCE(%s, '')" in source
    assert "telegram_knowledge_source" in source
    assert "telegram_knowledge_source" in migration
    assert "radar_permission_required" in source
    assert "telegram_account_required" in source
    assert "source.allowed_uses @>" in source
    assert "source.allowed_uses ?" not in source


def test_verified_channel_is_excluded_from_direct_message_contacts():
    source = Path("src/services/contact_intelligence_service.py").read_text(encoding="utf-8")

    assert "def exclude_public_channel_contacts" in source
    assert "('public_channel', 'public_group', 'bot')" in source
    assert "exclude_public_channel_contacts(cursor" in source


def test_public_channel_from_website_enrichment_stays_out_of_recipients():
    class Cursor:
        def execute(self, _query, _params=None):
            return None

        def fetchall(self):
            return [{"canonical_url": "https://t.me/cream_shop"}]

    contacts = exclude_public_channel_contacts(
        Cursor(),
        "lead-1",
        [
            {
                "contact_type": "telegram",
                "value": "https://t.me/cream_shop",
                "source_type": "official_website",
            },
            {"contact_type": "phone", "value": "+79990000000"},
        ],
    )

    assert contacts == [{"contact_type": "phone", "value": "+79990000000"}]


def test_website_contacts_are_filtered_after_they_are_collected():
    source = Path("src/services/contact_intelligence_service.py").read_text(encoding="utf-8")
    collect_index = source.index("contacts.extend(website_contacts)")
    filter_index = source.index(
        'contacts = exclude_public_channel_contacts(cursor, str(lead["id"]), contacts)',
        collect_index,
    )

    assert filter_index > collect_index


def test_enabling_radar_queues_previously_discovered_candidates():
    source = Path("src/services/telegram_account_permissions_service.py").read_text(encoding="utf-8")

    assert "not bool(current.get(\"radar_enabled\")) and next_radar" in source
    assert "metadata_json->>'auto_discovered'" in source
    assert "THEN 'queued'" in source
    assert "permission_reason\":\"ready" in source


def test_message_quality_keeps_grounding_when_only_source_punctuation_changes():
    signal = 'В публичном источнике «Арлекино» опубликовано: «Открыт новый набор». '
    story = "Я развиваю LocalOS и проверяю карточки локальных компаний."
    quality = evaluate_first_message(
        (
            'Здравствуйте! Пишу по поводу "Арлекино". '
            "Я развиваю LocalOS и проверяю карточки локальных компаний. "
            'В публичном источнике "Арлекино" опубликовано — "Открыт новый набор". '
            "Прислать короткий разбор?"
        ),
        {
            "lead_name": "Арлекино",
            "signal": signal,
            "pain": "",
            "result": "короткий разбор",
            "founder_story": story,
            "source_urls": ["https://t.me/arlekinospb/10"],
            "evidence_ids": ["evidence:telegram:10"],
            "evidence_fresh": True,
            "suppression_safe": True,
        },
    )

    assert quality["checks"]["removal"] is True
    assert "decorative_personalization" not in quality["blocking_reasons"]


def test_lead_drawer_exposes_channel_source_status_in_human_language():
    api = Path("src/api/prospecting/contact_intelligence_routes.py").read_text(encoding="utf-8")
    ui = Path("frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text(encoding="utf-8")

    assert '"telegram_sources": telegram_sources' in api
    assert "documents_count" in api
    assert "Telegram-источники" in ui
    assert "Они не считаются каналами бизнеса-отправителя" in ui
    assert "source_owner_label" in api
    assert "Источник {ownerLabel}" in ui
    assert "подключите Telegram-радар" in ui
    assert "Публичный канал" in ui


def test_manual_telegram_channel_uses_the_same_scoped_radar_pipeline():
    api = Path("src/api/prospecting/contact_intelligence_routes.py").read_text(encoding="utf-8")
    service = Path("src/services/discovered_telegram_source_service.py").read_text(encoding="utf-8")
    admin_ui = Path("frontend/src/components/prospecting/AdminLeadRegistry.tsx").read_text(encoding="utf-8")
    partner_ui = Path("frontend/src/components/prospecting/PartnershipLeadDetailDrawer.tsx").read_text(encoding="utf-8")

    assert 'telegram_usage == "signal_source"' in api
    assert 'discovery_origin="manual_lead_contact"' in api
    assert 'discovery_origin: str = "map_parse"' in service
    assert "Публичный канал — использовать для поиска сигналов" in admin_ui
    assert "Публичный канал — источник сигналов" in partner_ui
