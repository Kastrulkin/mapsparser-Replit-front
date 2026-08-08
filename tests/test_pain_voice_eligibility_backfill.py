from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.backfill_pain_voice_eligibility import (
    EXPECTED_PROOF_TEXT,
    apply_seed,
    load_seed,
    merged_metadata,
)


SOURCE_ID = "11111111-1111-1111-1111-111111111111"
DOCUMENT_ID = "22222222-2222-2222-2222-222222222222"
SOURCE_URL = "https://t.me/salon_owner"
DOCUMENT_URL = "https://t.me/salon_owner/42"
CONTRACT_SHA = "a" * 64


def seed_payload():
    return {
        "schema_version": "1.0",
        "review_status": "approved",
        "reviewed_by": "corpus-review-agent",
        "reviewed_at": "2026-08-08T20:00:00+03:00",
        "contract_sha256": CONTRACT_SHA,
        "entries": [{
            "source_id": SOURCE_ID,
            "source_url": SOURCE_URL,
            "document_id": DOCUMENT_ID,
            "document_url": DOCUMENT_URL,
            "eligibility": {
                "industry": "beauty_salon",
                "audience": "business_owner",
                "speaker_role": "owner",
                "content_role": "first_person_experience",
                "pain_support_eligible": True,
                "voice_style_eligible": True,
                "eligibility_confidence": "high",
            },
            "themes": ["price_surface_sync"],
            "reviewed_urls": [DOCUMENT_URL],
            "review_note": "Owner describes the workflow in first person.",
        }],
    }


def write_seed(tmp_path: Path, payload=None):
    path = tmp_path / "seed.json"
    path.write_text(
        json.dumps(payload or seed_payload(), ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def test_seed_must_be_explicitly_reviewed_and_use_stable_ids(tmp_path):
    payload = seed_payload()
    payload["review_status"] = "candidate"
    with pytest.raises(ValueError, match="seed_not_reviewed"):
        load_seed(write_seed(tmp_path, payload))

    with pytest.raises(ValueError, match="seed_sha256_mismatch"):
        load_seed(write_seed(tmp_path), expected_sha256="f" * 64)


def test_reviewed_source_seed_expands_only_exact_evidence_documents(tmp_path):
    payload = {
        "schema_version": "1.0",
        "seed_id": "beauty_public_pain_voice_seed_v1",
        "reviewed_at": "2026-08-08T21:30:00+03:00",
        "reviewed_by": "codex_localos_outreach_specialist",
        "production_write_performed": False,
        "review_method": ["stable source and document IDs inspected"],
        "approved_proof_case": {"exact_text": EXPECTED_PROOF_TEXT},
        "source_count": 1,
        "sources": [{
            "source_id": SOURCE_ID,
            "public_tme": SOURCE_URL,
            "industry": "beauty_salon",
            "audience": "beauty_owner_manager",
            "speaker_role": "owner_operator_expert",
            "content_role": "first_person_business_operations",
            "pain_support_eligible": True,
            "voice_style_eligible": True,
            "confidence": "high",
            "permitted_themes": ["manual_time"],
            "evidence_documents": [{
                "document_id": DOCUMENT_ID,
                "permalink": DOCUMENT_URL,
                "themes": ["manual_time"],
                "review_note": "Reviewed first-person workflow.",
            }],
        }],
    }

    seed = load_seed(write_seed(tmp_path, payload))

    assert len(seed["entries"]) == 1
    assert seed["entries"][0]["document_id"] == DOCUMENT_ID
    assert seed["entries"][0]["eligibility"]["audience"] == "business_owner"
    assert seed["entries"][0]["eligibility"]["speaker_role"] == "owner"

    payload = seed_payload()
    payload["entries"][0].pop("source_id")
    with pytest.raises(ValueError, match="invalid_source_id"):
        load_seed(write_seed(tmp_path, payload))


def test_metadata_merge_is_idempotent_and_preserves_unrelated_fields(tmp_path):
    seed = load_seed(write_seed(tmp_path))
    entry = seed["entries"][0]
    current = {
        "unrelated": {"keep": True},
        "segment": "wellness",
        "segments": ["wellness", "beauty"],
        "themes": ["appointment_reminders", "price_surface_sync"],
    }

    once = merged_metadata(current, entry=entry, seed=seed)
    twice = merged_metadata(once, entry=entry, seed=seed)

    assert once == twice
    assert once["unrelated"] == {"keep": True}
    assert once["pain_voice_eligibility"]["speaker_role"] == "owner"
    assert once["segment"] == "wellness"
    assert once["segments"] == ["wellness", "beauty"]
    assert once["themes"] == ["appointment_reminders", "price_surface_sync"]


def test_metadata_merge_sets_missing_classifications_without_replacing_arrays(tmp_path):
    seed = load_seed(write_seed(tmp_path))
    entry = seed["entries"][0]

    merged = merged_metadata(
        {"segment": "", "segments": "wellness", "themes": None},
        entry=entry,
        seed=seed,
    )

    assert merged["segment"] == "beauty"
    assert merged["segments"] == ["wellness", "beauty"]
    assert merged["themes"] == ["price_surface_sync"]


class FakeCursor:
    def __init__(self, source, document):
        self.source = source
        self.document = document
        self.row = None
        self.updates = []
        self.closed = False

    def execute(self, sql, params=None):
        normalized = " ".join(str(sql).lower().split())
        if "from knowledge_sources" in normalized:
            self.row = self.source
        elif "from knowledge_documents" in normalized:
            self.row = self.document
        elif normalized.startswith("update knowledge_"):
            self.updates.append((normalized, params))
            self.row = None
        else:
            raise AssertionError(normalized)

    def fetchone(self):
        return self.row

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, source, document):
        self.cursor_value = FakeCursor(source, document)
        self.commits = 0
        self.rollbacks = 0

    def cursor(self, cursor_factory=None):
        return self.cursor_value

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def valid_source():
    return {
        "id": SOURCE_ID,
        "source_type": "telegram",
        "canonical_url": SOURCE_URL,
        "status": "active",
        "visibility": "public",
        "sensitivity_class": "public",
        "allowed_uses": ["outreach", "market"],
        "metadata_json": {},
    }


def valid_document():
    return {
        "id": DOCUMENT_ID,
        "source_id": SOURCE_ID,
        "permalink": DOCUMENT_URL,
        "sensitivity_class": "public",
        "allowed_uses": ["outreach"],
        "invalidated_at": None,
        "metadata_json": {},
    }


def test_dry_run_revalidates_live_policy_and_never_updates(tmp_path):
    seed = load_seed(write_seed(tmp_path))
    connection = FakeConnection(valid_source(), valid_document())

    report = apply_seed(connection, seed, apply=False)

    assert report["mode"] == "dry_run"
    assert report["changed_count"] == 1
    assert connection.cursor_value.updates == []
    assert connection.commits == 0
    assert connection.rollbacks == 1


def test_live_private_or_unapproved_source_aborts_transaction(tmp_path):
    seed = load_seed(write_seed(tmp_path))
    source = valid_source()
    source["visibility"] = "private"
    connection = FakeConnection(source, valid_document())

    with pytest.raises(ValueError, match="source_not_public"):
        apply_seed(connection, seed, apply=False)

    assert connection.commits == 0
    assert connection.rollbacks == 1
    assert connection.cursor_value.updates == []


def test_apply_writes_backup_before_transactional_update_and_second_run_is_idempotent(tmp_path):
    seed = load_seed(write_seed(tmp_path))
    connection = FakeConnection(valid_source(), valid_document())
    backup = tmp_path / "backup.json"

    first = apply_seed(connection, seed, apply=True, backup_path=backup)

    assert first["changed_count"] == 1
    assert backup.exists()
    assert connection.commits == 1
    assert len(connection.cursor_value.updates) == 1

    updated_document = valid_document()
    updated_document["metadata_json"] = merged_metadata(
        {}, entry=seed["entries"][0], seed=seed
    )
    second_connection = FakeConnection(valid_source(), updated_document)
    second = apply_seed(
        second_connection,
        seed,
        apply=True,
        backup_path=tmp_path / "backup-second.json",
    )

    assert second["changed_count"] == 0
    assert second_connection.cursor_value.updates == []
    assert second_connection.commits == 1
