#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from psycopg2.extras import RealDictCursor

from database_manager import DatabaseManager
from services.creator_catalog_service import import_creator_catalog


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError(f"Ожидался JSON-объект: {path}")
    return payload


def _contacts(shortlist_payload: dict) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for candidate in shortlist_payload.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        entity_id = str(candidate.get("entity_id") or "").strip()
        contact = candidate.get("public_contact")
        if not entity_id or not isinstance(contact, dict) or not str(contact.get("value") or "").strip():
            continue
        existing = result.get(entity_id)
        if existing and float(existing.get("confidence") or 0) >= float(contact.get("confidence") or 0):
            continue
        result[entity_id] = contact
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Import the reviewed influencer catalog into LocalOS")
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--shortlists", type=Path)
    parser.add_argument("--source", default="spb_catalog_20260823")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()

    catalog = _load_json(arguments.catalog)
    entities = [item for item in catalog.get("entities", []) if isinstance(item, dict)]
    if not entities:
        raise ValueError("Каталог не содержит entities")
    contacts = _contacts(_load_json(arguments.shortlists)) if arguments.shortlists else {}

    database = DatabaseManager()
    cursor = database.conn.cursor(cursor_factory=RealDictCursor)
    try:
        result = import_creator_catalog(
            cursor,
            entities=entities,
            contacts_by_entity_id=contacts,
            import_source=arguments.source,
        )
        if arguments.dry_run:
            database.conn.rollback()
        else:
            database.conn.commit()
        result["dry_run"] = arguments.dry_run
        result["requested_entities"] = len(entities)
        result["contact_overlays"] = len(contacts)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["error_count"] == 0 else 2
    except Exception:
        database.conn.rollback()
        raise
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
