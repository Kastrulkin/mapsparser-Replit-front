#!/usr/bin/env python3
"""Apply a reviewed Pain/Voice eligibility seed without broad classification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


SCHEMA_VERSION = "1.0"
REVIEWED_SEED_ID = "beauty_public_pain_voice_seed_v1"
EXPECTED_CONTRACT_SHA256 = "0a258ddf2ff11365d677f5d87664078b755619991a132b2302fa5b6f068c1790"
EXPECTED_PROOF_TEXT = (
    "Салон красоты в пару кликов обновляет прайс-лист на 300+ позиций через LocalOS. "
    "Вам может быть интересно также сэкономить время?"
)
ALLOWED_THEMES = {
    "price_surface_sync",
    "event_distribution",
    "content_reuse",
    "review_workflow",
    "manual_time",
}
ALLOWED_AUDIENCES = {"business_owner", "beauty_professional"}
ALLOWED_SPEAKER_ROLES = {"owner", "manager", "master", "expert", "vendor"}
ALLOWED_CONTENT_ROLES = {
    "first_person_experience",
    "professional_discussion",
    "advice",
}
ALLOWED_CONFIDENCE = {"high", "medium"}
REVIEWED_AUDIENCE_MAP = {
    "beauty_owner_manager_master": "business_owner",
    "beauty_owner_manager": "business_owner",
    "beauty_master": "beauty_professional",
}
REVIEWED_SPEAKER_ROLE_MAP = {
    "professional_community": "expert",
    "expert_operator": "expert",
    "expert_consultant": "expert",
    "owner_operator_expert": "owner",
    "expert_team": "expert",
    "beauty_business_expert": "expert",
}
REVIEWED_CONTENT_ROLE_MAP = {
    "first_person_owner_master_discussion": "first_person_experience",
    "professional_analysis_and_case_discussion": "professional_discussion",
    "professional_audit_and_operational_advice": "advice",
    "first_person_business_operations": "first_person_experience",
    "professional_growth_and_execution_analysis": "professional_discussion",
    "professional_marketing_education": "advice",
    "first_person_master_questions_and_peer_discussion": "first_person_experience",
    "professional_content_marketing_advice": "advice",
    "professional_financial_and_team_management": "professional_discussion",
    "professional_map_marketing_advice": "advice",
    "first_person_beauty_business_education": "first_person_experience",
    "first_person_salon_network_operations": "first_person_experience",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _public_telegram_url(value: Any) -> bool:
    url = _text(value).lower()
    return url.startswith("https://t.me/") and "/+" not in url and "joinchat" not in url


def _uuid(value: Any, field: str) -> str:
    normalized = _text(value)
    try:
        return str(uuid.UUID(normalized))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f"invalid_{field}") from None


def _json_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"invalid_{field}")
    return value


def _eligibility(value: Any) -> dict[str, Any]:
    item = _json_object(value, "eligibility")
    normalized = {
        "industry": _text(item.get("industry")),
        "audience": _text(item.get("audience")),
        "speaker_role": _text(item.get("speaker_role")),
        "content_role": _text(item.get("content_role")),
        "pain_support_eligible": item.get("pain_support_eligible"),
        "voice_style_eligible": item.get("voice_style_eligible"),
        "eligibility_confidence": _text(item.get("eligibility_confidence")),
    }
    if normalized["industry"] != "beauty_salon":
        raise ValueError("invalid_eligibility_industry")
    if normalized["audience"] not in ALLOWED_AUDIENCES:
        raise ValueError("invalid_eligibility_audience")
    if normalized["speaker_role"] not in ALLOWED_SPEAKER_ROLES:
        raise ValueError("invalid_eligibility_speaker_role")
    if normalized["content_role"] not in ALLOWED_CONTENT_ROLES:
        raise ValueError("invalid_eligibility_content_role")
    if normalized["pain_support_eligible"] is not True:
        raise ValueError("invalid_pain_support_eligibility")
    if not isinstance(normalized["voice_style_eligible"], bool):
        raise ValueError("invalid_voice_style_eligibility")
    if normalized["eligibility_confidence"] not in ALLOWED_CONFIDENCE:
        raise ValueError("invalid_eligibility_confidence")
    return normalized


def _themes(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("invalid_themes")
    normalized = list(dict.fromkeys(_text(item) for item in value if _text(item)))
    if not normalized or any(item not in ALLOWED_THEMES for item in normalized):
        raise ValueError("invalid_themes")
    return normalized


def _reviewed_sources_to_entries(root: dict[str, Any]) -> list[dict[str, Any]]:
    if _text(root.get("seed_id")) != REVIEWED_SEED_ID:
        raise ValueError("unexpected_seed_id")
    if root.get("production_write_performed") is not False:
        raise ValueError("seed_production_state_invalid")
    methods = root.get("review_method")
    if not isinstance(methods, list) or not methods:
        raise ValueError("review_method_missing")
    proof = root.get("approved_proof_case")
    if not isinstance(proof, dict) or _text(proof.get("exact_text")) != EXPECTED_PROOF_TEXT:
        raise ValueError("approved_proof_mismatch")
    sources = root.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("seed_sources_missing")
    if int(root.get("source_count") or 0) != len(sources):
        raise ValueError("seed_source_count_mismatch")
    entries = []
    for source in sources:
        source = _json_object(source, "reviewed_source")
        audience = REVIEWED_AUDIENCE_MAP.get(_text(source.get("audience")))
        speaker_role = REVIEWED_SPEAKER_ROLE_MAP.get(_text(source.get("speaker_role")))
        content_role = REVIEWED_CONTENT_ROLE_MAP.get(_text(source.get("content_role")))
        if not audience or not speaker_role or not content_role:
            raise ValueError("reviewed_role_mapping_missing")
        source_url = _text(source.get("public_tme"))
        source_themes = _themes(source.get("permitted_themes"))
        documents = source.get("evidence_documents")
        if not isinstance(documents, list) or not documents:
            raise ValueError("reviewed_documents_missing")
        for document in documents:
            document = _json_object(document, "reviewed_document")
            document_themes = _themes(document.get("themes"))
            if any(theme not in source_themes for theme in document_themes):
                raise ValueError("document_theme_not_permitted")
            entries.append({
                "source_id": source.get("source_id"),
                "source_url": source_url,
                "document_id": document.get("document_id"),
                "document_url": document.get("permalink"),
                "eligibility": {
                    "industry": source.get("industry"),
                    "audience": audience,
                    "speaker_role": speaker_role,
                    "content_role": content_role,
                    "pain_support_eligible": source.get("pain_support_eligible"),
                    "voice_style_eligible": source.get("voice_style_eligible"),
                    "eligibility_confidence": source.get("confidence"),
                },
                "themes": document_themes,
                "reviewed_urls": [source_url, document.get("permalink")],
                "review_note": document.get("review_note"),
            })
    return entries


def load_seed(path: Path, *, expected_sha256: str | None = None) -> dict[str, Any]:
    raw = path.read_bytes()
    seed_sha256 = hashlib.sha256(raw).hexdigest()
    if expected_sha256 and seed_sha256 != _text(expected_sha256).lower():
        raise ValueError("seed_sha256_mismatch")
    payload = json.loads(raw.decode("utf-8"))
    root = _json_object(payload, "seed")
    if _text(root.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError("unsupported_schema_version")
    reviewed_source_format = bool(root.get("sources"))
    if reviewed_source_format:
        root = {
            **root,
            "review_status": "approved",
            "contract_sha256": EXPECTED_CONTRACT_SHA256,
            "entries": _reviewed_sources_to_entries(root),
        }
    elif _text(root.get("review_status")) != "approved":
        raise ValueError("seed_not_reviewed")
    if not _text(root.get("reviewed_by")) or not _text(root.get("reviewed_at")):
        raise ValueError("review_provenance_missing")
    contract_sha = _text(root.get("contract_sha256"))
    if len(contract_sha) != 64:
        raise ValueError("contract_sha256_missing")
    entries = root.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("seed_entries_missing")

    normalized_entries = []
    seen_targets: set[tuple[str, str]] = set()
    for index, raw_entry in enumerate(entries):
        entry = _json_object(raw_entry, f"entry_{index}")
        source_id = _uuid(entry.get("source_id"), "source_id")
        source_url = _text(entry.get("source_url"))
        if not _public_telegram_url(source_url):
            raise ValueError("invalid_source_url")
        document_id = _text(entry.get("document_id"))
        document_url = _text(entry.get("document_url"))
        if bool(document_id) != bool(document_url):
            raise ValueError("document_identity_incomplete")
        if document_id:
            document_id = _uuid(document_id, "document_id")
            if not _public_telegram_url(document_url):
                raise ValueError("invalid_document_url")
        target = (source_id, document_id)
        if target in seen_targets:
            raise ValueError("duplicate_seed_target")
        seen_targets.add(target)
        reviewed_urls = entry.get("reviewed_urls")
        if not isinstance(reviewed_urls, list) or not reviewed_urls:
            raise ValueError("reviewed_urls_missing")
        if any(not _public_telegram_url(item) for item in reviewed_urls):
            raise ValueError("invalid_reviewed_url")
        normalized_entries.append({
            "source_id": source_id,
            "source_url": source_url,
            "document_id": document_id,
            "document_url": document_url,
            "eligibility": _eligibility(entry.get("eligibility")),
            "themes": _themes(entry.get("themes")),
            "reviewed_urls": list(dict.fromkeys(_text(item) for item in reviewed_urls)),
            "review_note": _text(entry.get("review_note")),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "review_status": "approved",
        "reviewed_by": _text(root.get("reviewed_by")),
        "reviewed_at": _text(root.get("reviewed_at")),
        "contract_sha256": contract_sha,
        "seed_sha256": seed_sha256,
        "entries": normalized_entries,
    }


def merged_metadata(
    current: Any,
    *,
    entry: dict[str, Any],
    seed: dict[str, Any],
) -> dict[str, Any]:
    metadata = deepcopy(current) if isinstance(current, dict) else {}
    metadata["pain_voice_eligibility"] = deepcopy(entry["eligibility"])
    if not _text(metadata.get("segment")):
        metadata["segment"] = "beauty"

    def merged_values(value: Any, additions: list[str]) -> list[str]:
        existing = value if isinstance(value, (list, tuple)) else [value]
        return list(dict.fromkeys(
            text
            for item in [*existing, *additions]
            if (text := _text(item))
        ))

    metadata["segments"] = merged_values(metadata.get("segments"), ["beauty"])
    metadata["themes"] = merged_values(metadata.get("themes"), list(entry["themes"]))
    metadata["pain_voice_review"] = {
        "status": "approved",
        "reviewed_by": seed["reviewed_by"],
        "reviewed_at": seed["reviewed_at"],
        "contract_sha256": seed["contract_sha256"],
        "seed_sha256": seed["seed_sha256"],
        "reviewed_urls": list(entry["reviewed_urls"]),
        "review_note": entry["review_note"],
    }
    return metadata


def _source(cursor: Any, entry: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, source_type, canonical_url, status, visibility,
               sensitivity_class, allowed_uses, metadata_json
        FROM knowledge_sources
        WHERE id = %s
        FOR UPDATE
        """,
        (entry["source_id"],),
    )
    row = cursor.fetchone()
    source = dict(row) if row else {}
    if not source:
        raise ValueError("source_not_found")
    if _text(source.get("source_type")) != "telegram":
        raise ValueError("source_not_telegram")
    if _text(source.get("status")) != "active":
        raise ValueError("source_not_active")
    if _text(source.get("visibility")) != "public":
        raise ValueError("source_not_public")
    if _text(source.get("sensitivity_class")) != "public":
        raise ValueError("source_sensitive")
    if "outreach" not in list(source.get("allowed_uses") or []):
        raise ValueError("source_outreach_not_allowed")
    if not _public_telegram_url(source.get("canonical_url")):
        raise ValueError("source_permalink_not_public")
    if _text(source.get("canonical_url")).rstrip("/") != entry["source_url"].rstrip("/"):
        raise ValueError("source_url_mismatch")
    return source


def _document(cursor: Any, entry: dict[str, Any]) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, source_id, permalink, sensitivity_class, allowed_uses,
               invalidated_at, metadata_json
        FROM knowledge_documents
        WHERE id = %s
        FOR UPDATE
        """,
        (entry["document_id"],),
    )
    row = cursor.fetchone()
    document = dict(row) if row else {}
    if not document:
        raise ValueError("document_not_found")
    if _text(document.get("source_id")) != entry["source_id"]:
        raise ValueError("document_source_mismatch")
    if document.get("invalidated_at") is not None:
        raise ValueError("document_invalidated")
    if _text(document.get("sensitivity_class")) != "public":
        raise ValueError("document_sensitive")
    if "outreach" not in list(document.get("allowed_uses") or []):
        raise ValueError("document_outreach_not_allowed")
    if not _public_telegram_url(document.get("permalink")):
        raise ValueError("document_permalink_not_public")
    if _text(document.get("permalink")).rstrip("/") != entry["document_url"].rstrip("/"):
        raise ValueError("document_url_mismatch")
    return document


def apply_seed(
    connection: Any,
    seed: dict[str, Any],
    *,
    apply: bool,
    backup_path: Path | None = None,
) -> dict[str, Any]:
    cursor = connection.cursor(cursor_factory=RealDictCursor)
    planned = []
    backups = []
    changed = 0
    try:
        for entry in seed["entries"]:
            source = _source(cursor, entry)
            target_type = "document" if entry["document_id"] else "source"
            target = _document(cursor, entry) if entry["document_id"] else source
            target_id = entry["document_id"] or entry["source_id"]
            before = target.get("metadata_json") if isinstance(target.get("metadata_json"), dict) else {}
            after = merged_metadata(before, entry=entry, seed=seed)
            will_change = before != after
            if will_change:
                changed += 1
            backups.append({
                "target_type": target_type,
                "target_id": target_id,
                "metadata_json": before,
            })
            planned.append({
                "target_type": target_type,
                "target_id": target_id,
                "source_id": entry["source_id"],
                "themes": entry["themes"],
                "will_change": will_change,
            })

        if apply:
            if backup_path is None:
                raise ValueError("backup_path_required")
            backup_payload = {
                "schema_version": SCHEMA_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "seed_sha256": seed["seed_sha256"],
                "targets": backups,
            }
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(
                json.dumps(backup_payload, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            for item, entry in zip(planned, seed["entries"]):
                if not item["will_change"]:
                    continue
                target_table = "knowledge_documents" if item["target_type"] == "document" else "knowledge_sources"
                current = next(
                    backup["metadata_json"]
                    for backup in backups
                    if backup["target_type"] == item["target_type"]
                    and backup["target_id"] == item["target_id"]
                )
                after = merged_metadata(current, entry=entry, seed=seed)
                cursor.execute(
                    f"UPDATE {target_table} SET metadata_json = %s, updated_at = NOW() WHERE id = %s",
                    (Json(after), item["target_id"]),
                )
            connection.commit()
        else:
            connection.rollback()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
    return {
        "mode": "apply" if apply else "dry_run",
        "seed_sha256": seed["seed_sha256"],
        "entry_count": len(seed["entries"]),
        "changed_count": changed,
        "unchanged_count": len(seed["entries"]) - changed,
        "targets": planned,
        "backup_path": str(backup_path) if apply and backup_path else None,
    }


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.apply and args.backup is None:
        raise SystemExit("--backup is required with --apply")
    database_url = _text(os.getenv("DATABASE_URL"))
    if not database_url:
        raise SystemExit("DATABASE_URL is required")
    seed = load_seed(args.seed, expected_sha256=args.expected_sha256)
    connection = psycopg2.connect(database_url)
    try:
        report = apply_seed(
            connection,
            seed,
            apply=bool(args.apply),
            backup_path=args.backup,
        )
    finally:
        connection.close()
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
