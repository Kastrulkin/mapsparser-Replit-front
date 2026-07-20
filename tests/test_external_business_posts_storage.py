from pathlib import Path

import worker


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "alembic_migrations" / "versions" / "20260720_add_external_business_posts.py"


def test_external_business_posts_migration_has_runtime_contract() -> None:
    source = MIGRATION.read_text(encoding="utf-8").lower()

    assert 'revision = "20260720_001"' in source
    assert 'down_revision = "20260718_001"' in source
    assert "create table if not exists externalbusinessposts" in source
    assert "business_id text not null references businesses(id) on delete cascade" in source
    assert "external_post_id text" in source
    assert "published_at timestamp" in source
    assert "raw_payload text" in source
    assert "idx_externalbusinessposts_business_published" in source


def test_public_post_identity_is_stable_without_provider_id() -> None:
    item = {
        "title": "Новая секция",
        "text": "Открыли набор в группу",
        "date": "2026-07-20",
    }

    first = worker._public_post_identity("business-1", "yandex_maps", item)
    second = worker._public_post_identity("business-1", "yandex_maps", dict(item))

    assert first == second
    assert first[1] == f"public_{first[0]}"


def test_public_post_identity_prefers_provider_id() -> None:
    first = worker._public_post_identity(
        "business-1",
        "yandex_maps",
        {"id": "post-42", "title": "Старый заголовок"},
    )
    second = worker._public_post_identity(
        "business-1",
        "yandex_maps",
        {"id": "post-42", "title": "Обновлённый заголовок"},
    )

    assert first == second
    assert first[1] == "post-42"
