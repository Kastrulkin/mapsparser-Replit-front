#!/usr/bin/env python3
import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
for candidate in (str(REPO_ROOT), str(SRC_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from database_manager import DatabaseManager
from services.agent_blueprint_draft_builder import build_agent_blueprint_draft


PACK_KEY = "popular_default_v1"
SEED_NAMESPACE = uuid.UUID("8ff3f2df-8c50-4eb8-a247-20f02c2dce5f")

POPULAR_AGENT_EXAMPLES = [
    {
        "key": "daily_owner_digest",
        "title": "Ежедневный отчёт владельцу",
        "category": "custom",
        "required_connectors": ["telegram"],
        "prompt": "Каждый день собирай короткий отчёт: что требует внимания по отзывам, новостям, услугам, партнёрствам и финансам, и присылай владельцу в Telegram.",
    },
    {
        "key": "negative_review_reply",
        "title": "Черновик ответа на негативный отзыв",
        "category": "reviews",
        "required_connectors": ["telegram"],
        "prompt": "Если появился новый негативный отзыв, подготовь короткий ответ в стиле компании и пришли черновик владельцу в Telegram.",
    },
    {
        "key": "card_posts_from_signals",
        "title": "Новости для карточек из сигналов",
        "category": "content",
        "prompt": "Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач.",
    },
    {
        "key": "service_seo_cleanup",
        "title": "SEO-проверка услуг",
        "category": "services",
        "prompt": "Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки.",
    },
    {
        "key": "partnership_outreach_draft",
        "title": "Партнёрский outreach",
        "category": "outreach",
        "prompt": "Найди или возьми из списка потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение.",
    },
    {
        "key": "competitor_website_monitor",
        "title": "Мониторинг сайта конкурента",
        "category": "custom",
        "required_connectors": ["browser_use", "telegram"],
        "prompt": "Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь короткий отчёт владельцу в Telegram.",
    },
    {
        "key": "google_sheets_leads_to_telegram",
        "title": "Google Sheets → Telegram",
        "category": "custom",
        "required_connectors": ["google_sheets", "telegram"],
        "prompt": "Проверяй Google Sheets с заявками или заказами и присылай новые строки ответственному в Telegram.",
    },
    {
        "key": "whatsapp_telegram_faq_miner",
        "title": "FAQ из WhatsApp и Telegram",
        "category": "custom",
        "required_connectors": ["whatsapp", "telegram"],
        "prompt": "Собирай повторяющиеся вопросы клиентов из WhatsApp и Telegram, группируй их и предлагай новые ответы для FAQ.",
    },
    {
        "key": "finance_import_assistant",
        "title": "Импорт расходов в финансы",
        "category": "custom",
        "required_connectors": ["google_sheets"],
        "prompt": "Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS.",
    },
    {
        "key": "tomorrow_bookings_check",
        "title": "Проверка записей на завтра",
        "category": "communications",
        "required_connectors": ["telegram"],
        "prompt": "Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up.",
    },
]


def _json_dumps(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _stable_id(business_id: str, example_key: str, suffix: str) -> str:
    return str(uuid.uuid5(SEED_NAMESPACE, f"{PACK_KEY}:{business_id}:{example_key}:{suffix}"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


USER_CONNECTORS = {"browser_use", "google_sheets", "telegram", "whatsapp", "maton", "composio"}


def _connector_binding(provider: str) -> dict:
    if provider == "browser_use":
        return {
            "key": "browser_use_read",
            "provider": "browser_use",
            "direction": "external_read",
            "capability": "browser_use.read_page",
            "required": True,
            "approval_required": True,
            "required_config": ["target_urls"],
            "default_limits": {"daily_page_check_cap": 50, "frequency_cap_minutes": 60},
            "execution_boundary": "openclaw_browser_boundary",
        }
    if provider == "google_sheets":
        return {
            "key": "google_sheets_read",
            "provider": "google_sheets",
            "direction": "external_read",
            "capability": "google_sheets.read_rows",
            "required": True,
            "approval_required": True,
            "required_config": ["spreadsheet_id", "sheet_name"],
            "default_limits": {"daily_read_cap": 50, "frequency_cap_minutes": 0},
        }
    if provider == "whatsapp":
        return {
            "key": "whatsapp_delivery",
            "provider": "whatsapp",
            "direction": "external_write",
            "capability": "communications.draft",
            "required": True,
            "approval_required": True,
            "required_config": ["channel_mode"],
            "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
        }
    return {
        "key": f"{provider}_delivery",
        "provider": provider,
        "direction": "external_write",
        "capability": "communications.draft",
        "required": True,
        "approval_required": True,
        "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
    }


def _merge_required_bindings(metadata: dict, explicit_connectors: list[str]) -> list[dict]:
    bindings = metadata.get("required_integration_bindings")
    merged = [dict(item) for item in bindings if isinstance(item, dict)] if isinstance(bindings, list) else []
    existing_providers = {str(item.get("provider") or "").strip() for item in merged}
    for provider in explicit_connectors:
        if provider and provider not in existing_providers:
            merged.append(_connector_binding(provider))
            existing_providers.add(provider)
    return merged


def _required_connectors(metadata: dict, explicit_connectors: list[str] | None = None) -> list[str]:
    bindings = metadata.get("required_integration_bindings")
    explicit = [item for item in (explicit_connectors or []) if item in USER_CONNECTORS]
    if not isinstance(bindings, list):
        return explicit
    result = []
    seen = set()
    for provider in explicit:
        seen.add(provider)
        result.append(provider)
    for item in bindings:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider in USER_CONNECTORS and provider not in seen:
            seen.add(provider)
            result.append(provider)
    return result


def _table_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = %s
        """,
        (table_name.lower(),),
    )
    return {str(row.get("column_name") or "").strip().lower() for row in cursor.fetchall() or []}


def _load_target_businesses(cursor, business_id: str = "", include_inactive: bool = False) -> list[dict]:
    business_columns = _table_columns(cursor, "businesses")
    filters = [
        "(%s = '' OR b.id = %s)",
        "(%s OR COALESCE(b.is_active, TRUE) = TRUE)",
        "COALESCE(u.is_active, TRUE) = TRUE",
    ]
    params = [business_id, business_id, include_inactive]
    if "moderation_status" in business_columns:
        filters.append("COALESCE(LOWER(b.moderation_status), '') <> 'lead_outreach'")
    if "description" in business_columns:
        filters.append("LOWER(COALESCE(b.description, '')) NOT LIKE 'lead shadow business for outreach lead%%'")
    sql = (
        """
        SELECT b.id, b.name, b.owner_id
        FROM businesses b
        JOIN users u ON u.id = b.owner_id
        WHERE 
        """
        + "\n          AND ".join(filters)
        + """
        ORDER BY b.created_at ASC NULLS LAST, b.id ASC
        """
    )
    cursor.execute(sql, tuple(params))
    return [dict(row) for row in cursor.fetchall() or []]


def _existing_examples(cursor, business_id: str) -> dict[str, dict]:
    cursor.execute(
        """
        SELECT id, metadata_json, metadata_json->>'example_key' AS example_key
        FROM agent_blueprints
        WHERE business_id = %s
          AND metadata_json->>'example_pack' = %s
        """,
        (business_id, PACK_KEY),
    )
    result = {}
    for row in cursor.fetchall() or []:
        key = str(row.get("example_key") or "").strip()
        if key:
            result[key] = dict(row)
    return result


def _apply_example_metadata(metadata: dict, example: dict) -> dict:
    explicit_connectors = [str(item) for item in example.get("required_connectors", []) if str(item).strip()]
    metadata["example_pack"] = PACK_KEY
    metadata["example_key"] = str(example["key"])
    metadata["example_title"] = str(example["title"])
    metadata["is_account_example"] = True
    metadata["account_example_status"] = "draft_disabled"
    metadata["enabled"] = False
    metadata["seeded_by"] = "scripts/seed_popular_agent_examples.py"
    metadata["required_integration_bindings"] = _merge_required_bindings(metadata, explicit_connectors)
    metadata["required_connectors"] = _required_connectors(metadata, explicit_connectors)
    metadata["setup_completed"] = False
    metadata["agent_setup"] = {
        "status": "needs_connections" if metadata["required_connectors"] else "ready_for_preview",
        "headline": "Пример готов. Осталось подключить нужные сервисы и проверить запуск.",
        "next_action": "connect_required_integrations" if metadata["required_connectors"] else "preview_example_agent",
        "required_connectors": metadata["required_connectors"],
        "manual_approval_required": True,
    }
    return metadata


def _insert_example(cursor, business: dict, example: dict) -> dict:
    business_id = str(business["id"])
    user_id = str(business["owner_id"])
    example_key = str(example["key"])
    prompt = str(example["prompt"])
    draft = build_agent_blueprint_draft(
        prompt,
        str(example.get("category") or "custom"),
        use_ai=False,
        business_id=business_id,
        user_id=user_id,
    )
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    metadata["seeded_at"] = _now_iso()
    metadata = _apply_example_metadata(metadata, example)

    version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
    blueprint_id = _stable_id(business_id, example_key, "blueprint")
    version_id = _stable_id(business_id, example_key, "version-1")
    metadata["active_version_id"] = version_id
    metadata["version_events"] = [
        {
            "action": "seeded_example",
            "active_version_id": version_id,
            "previous_active_version_id": "",
            "created_by_user_id": user_id,
            "created_at": _now_iso(),
            "reason": "popular_default_v1 account example",
        }
    ]

    cursor.execute(
        """
        INSERT INTO agent_blueprints (
            id, business_id, name, category, description, status, created_by_user_id, metadata_json
        )
        VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s::jsonb)
        """,
        (
            blueprint_id,
            business_id,
            str(example["title"]),
            str(draft.get("category") or example.get("category") or "custom"),
            prompt,
            user_id,
            _json_dumps(metadata),
        ),
    )
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            persona_agent_id, capability_allowlist_json, approval_policy_json,
            output_schema_json, created_by_user_id
        )
        VALUES (%s, %s, 1, %s, %s::jsonb, %s::jsonb, NULL, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        """,
        (
            version_id,
            blueprint_id,
            str(version_payload.get("goal") or prompt),
            _json_dumps(version_payload.get("inputs_schema") if isinstance(version_payload.get("inputs_schema"), dict) else {}),
            _json_dumps(version_payload.get("steps") if isinstance(version_payload.get("steps"), list) else []),
            _json_dumps(version_payload.get("capability_allowlist") if isinstance(version_payload.get("capability_allowlist"), list) else []),
            _json_dumps(version_payload.get("approval_policy") if isinstance(version_payload.get("approval_policy"), dict) else {}),
            _json_dumps(version_payload.get("output_schema") if isinstance(version_payload.get("output_schema"), dict) else {}),
            user_id,
        ),
    )
    return {
        "business_id": business_id,
        "business_name": str(business.get("name") or ""),
        "example_key": example_key,
        "blueprint_id": blueprint_id,
        "version_id": version_id,
        "required_connectors": metadata["required_connectors"],
    }


def _refresh_existing_example(cursor, row: dict, example: dict) -> dict:
    metadata = row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {}
    refreshed = _apply_example_metadata(dict(metadata), example)
    refreshed["metadata_refreshed_at"] = _now_iso()
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET metadata_json = %s::jsonb,
            status = CASE WHEN status = 'active' THEN 'draft' ELSE status END,
            updated_at = NOW()
        WHERE id = %s
        """,
        (_json_dumps(refreshed), str(row["id"])),
    )
    return {"blueprint_id": str(row["id"]), "example_key": str(example["key"]), "required_connectors": refreshed["required_connectors"]}


def seed_examples(
    business_id: str = "",
    include_inactive: bool = False,
    dry_run: bool = True,
    refresh_existing: bool = False,
) -> dict:
    db = DatabaseManager()
    cursor = db.conn.cursor()
    inserted = []
    skipped = []
    try:
        businesses = _load_target_businesses(cursor, business_id=business_id, include_inactive=include_inactive)
        for business in businesses:
            existing = _existing_examples(cursor, str(business["id"]))
            for example in POPULAR_AGENT_EXAMPLES:
                example_key = str(example["key"])
                if example_key in existing:
                    if refresh_existing:
                        if dry_run:
                            inserted.append(
                                {
                                    "business_id": str(business["id"]),
                                    "business_name": str(business.get("name") or ""),
                                    "example_key": example_key,
                                    "refresh_existing": True,
                                    "dry_run": True,
                                }
                            )
                        else:
                            refreshed = _refresh_existing_example(cursor, existing[example_key], example)
                            refreshed["business_id"] = str(business["id"])
                            refreshed["business_name"] = str(business.get("name") or "")
                            inserted.append(refreshed)
                    skipped.append({"business_id": str(business["id"]), "example_key": str(example["key"])})
                    continue
                if dry_run:
                    inserted.append(
                        {
                            "business_id": str(business["id"]),
                            "business_name": str(business.get("name") or ""),
                            "example_key": str(example["key"]),
                            "dry_run": True,
                        }
                    )
                    continue
                inserted.append(_insert_example(cursor, business, example))
        if dry_run:
            db.conn.rollback()
        else:
            db.conn.commit()
        return {
            "pack": PACK_KEY,
            "dry_run": dry_run,
            "businesses": len(businesses),
            "examples_per_business": len(POPULAR_AGENT_EXAMPLES),
            "inserted": len(inserted),
            "skipped_existing": len(skipped),
            "refresh_existing": refresh_existing,
            "inserted_preview": inserted[:20],
        }
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed disabled popular LocalOS agent examples into every account.")
    parser.add_argument("--apply", action="store_true", help="Write examples. Default is dry-run.")
    parser.add_argument("--business-id", default="", help="Limit to one business id.")
    parser.add_argument("--include-inactive", action="store_true", help="Include inactive businesses. Owners must still be active.")
    parser.add_argument("--refresh-existing", action="store_true", help="Refresh metadata for already seeded examples.")
    args = parser.parse_args()
    result = seed_examples(
        business_id=str(args.business_id or "").strip(),
        include_inactive=bool(args.include_inactive),
        dry_run=not bool(args.apply),
        refresh_existing=bool(args.refresh_existing),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
