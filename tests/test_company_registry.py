from pathlib import Path

from api.telegram_research_api import _public_telegram_username
from services.company_registry_service import normalize_identity_url, normalize_phone, normalize_text, normalize_url


ROOT = Path(__file__).resolve().parents[1]


def test_company_identity_normalization_keeps_map_identity_query():
    first = normalize_identity_url("https://Yandex.ru/maps/org/example/123/?z=14&ll=30")
    second = normalize_identity_url("https://yandex.ru/maps/org/example/123?ll=30&z=14")

    assert first == second
    assert first.endswith("?ll=30&z=14")
    assert normalize_url("Example.COM/") == "https://example.com"
    assert normalize_phone("8 (999) 111-22-33") == "79991112233"
    assert normalize_text("  Intellectum   School ") == "intellectum school"


def test_public_telegram_username_rejects_private_and_message_links():
    assert _public_telegram_username("https://t.me/localos_news") == "localos_news"
    assert _public_telegram_username("@localos_news") == "localos_news"
    assert _public_telegram_username("https://t.me/+privateInvite") == ""
    assert _public_telegram_username("https://t.me/joinchat/secret") == ""
    assert _public_telegram_username("https://t.me/localos_news/42") == ""


def test_registry_migration_is_additive_and_reversible_for_compatibility_links():
    migration = (ROOT / "alembic_migrations/versions/20260727_add_company_registry.py").read_text()
    required_tables = (
        "companies",
        "company_locations",
        "company_external_profiles",
        "company_identity_keys",
        "business_company_links",
        "company_contact_points",
        "company_observations",
        "company_social_source_links",
        "company_relationships",
        "company_merge_events",
        "knowledge_source_subscriptions",
    )
    for table in required_tables:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
        assert f"DROP TABLE IF EXISTS {table}" in migration

    assert "ALTER TABLE prospectingleads ADD COLUMN IF NOT EXISTS company_id" in migration
    assert "ALTER TABLE prospectingleads DROP COLUMN IF EXISTS company_id" in migration
    assert "partnership_partner_cards DROP COLUMN IF EXISTS company_id" in migration


def test_lead_intake_calls_registry_without_replacing_legacy_lead_table():
    database_manager = (ROOT / "src/database_manager.py").read_text()
    service = (ROOT / "src/services/company_registry_service.py").read_text()

    assert "ensure_company_for_lead(self.conn, lead_id, registry_payload)" in database_manager
    assert "UPDATE prospectingleads SET company_id" in service
    assert 'identity_candidates.append(("name"' not in service


def test_public_telegram_collection_is_global_and_subscriptions_are_tenant_scoped():
    api = (ROOT / "src/api/telegram_research_api.py").read_text()
    monitor = (ROOT / "src/services/knowledge_public_telegram.py").read_text()

    assert 'external_key=f"telegram-public:{username}"' in api
    assert "knowledge_source_subscriptions" in api
    assert "business_id=None" in api
    assert "visibility=\"public\"" in api
    assert "LEFT JOIN telegram_account_permissions" in monitor
