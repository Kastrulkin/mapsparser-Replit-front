"""PostgreSQL proof for compiled model-generation admission."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.compiled_generation_admission import (
    mark_generation_failed,
    mark_generation_succeeded,
    reserve_generation,
)


@pytest.fixture
def generation_db():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_generation_admission_" + uuid.uuid4().hex
    cursor = first.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    second.cursor().execute(f'SET search_path TO "{schema}"')
    second.commit()
    cursor.execute("""CREATE TABLE compiled_generation_requests(
        id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,blueprint_id TEXT,
        idempotency_key TEXT,input_digest TEXT,state TEXT,result_version_id TEXT,
        error_code TEXT,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),completed_at TIMESTAMPTZ
    )""")
    cursor.execute("CREATE UNIQUE INDEX request_key ON compiled_generation_requests(user_id,business_id,blueprint_id,idempotency_key)")
    first.commit()
    try:
        yield first, second
    finally:
        second.rollback()
        first.rollback()
        cursor = first.cursor()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()


def _reserve(cursor, key, digest="sha256:one"):
    return reserve_generation(cursor, user_id="user", business_id="business", blueprint_id="blueprint", idempotency_key=key, request_digest=digest)


def test_generation_replay_conflict_failure_and_quota_are_durable(generation_db):
    first, second = generation_db
    cursor = first.cursor()
    reserved = _reserve(cursor, "same")
    assert reserved["status"] == "reserved"
    request_id = reserved["request"]["id"]
    first.commit()

    assert _reserve(second.cursor(), "same")["status"] == "in_progress"
    second.rollback()
    mark_generation_succeeded(cursor, request_id, "version-1")
    first.commit()
    replay = _reserve(second.cursor(), "same")
    assert replay["status"] == "replayed"
    assert replay["request"]["result_version_id"] == "version-1"
    assert _reserve(second.cursor(), "same", "sha256:other")["code"] == "COMPILED_GENERATION_IDEMPOTENCY_CONFLICT"
    second.rollback()

    cursor.execute("UPDATE compiled_generation_requests SET created_at=NOW()-INTERVAL '61 seconds'")
    for number in range(19):
        cursor.execute("""INSERT INTO compiled_generation_requests(
            id,user_id,business_id,blueprint_id,idempotency_key,input_digest,state,created_at
        ) VALUES (%s,'user','business','other',%s,'sha256:x','failed',NOW()-INTERVAL '61 seconds')""", (str(uuid.uuid4()), f"old-{number}"))
    first.commit()
    quota = _reserve(second.cursor(), "quota")
    assert quota["code"] == "COMPILED_GENERATION_QUOTA_EXCEEDED"
    second.rollback()


def test_failed_generation_is_not_silently_retried(generation_db):
    first, second = generation_db
    reserved = _reserve(first.cursor(), "failed")
    mark_generation_failed(first.cursor(), reserved["request"]["id"], "COMPILED_ARTIFACT_INVALID")
    first.commit()
    replay = _reserve(second.cursor(), "failed")
    assert replay["status"] == "failed"
    assert replay["code"] == "COMPILED_ARTIFACT_INVALID"
