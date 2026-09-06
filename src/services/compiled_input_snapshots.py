"""Application-side read gateway. The runner receives data, never credentials."""
import hashlib
import json
import uuid

from services.compiled_table_contract import TABLE_SCHEMA, normalize_table_input


class SnapshotUnavailable(ValueError):
    pass


class SnapshotQuotaExceeded(SnapshotUnavailable):
    pass


def content_hash(value):
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def create_snapshot(cursor, *, auth, blueprint_id, business_id, input_payload, name="Таблица"):
    # Blueprint membership must be checked by the application command as well.
    if not auth.permits_business(business_id) or auth.session_kind != "standard" or auth.impersonating:
        raise SnapshotUnavailable("compiled_snapshot_scope_denied")
    normalized = normalize_table_input(input_payload)
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"compiled-snapshots:{business_id}:{auth.user_id}",))
    cursor.execute("""SELECT COUNT(*) count FROM compiled_input_snapshots
        WHERE business_id=%s AND user_id=%s AND expires_at > NOW()""", (str(business_id), auth.user_id))
    if cursor.fetchone()["count"] >= 100:
        raise SnapshotQuotaExceeded("compiled_snapshot_quota_exceeded")
    snapshot_id = str(uuid.uuid4())
    digest = content_hash(normalized)
    cursor.execute("""INSERT INTO compiled_input_snapshots
        (id,business_id,user_id,blueprint_id,source_kind,source_name,schema_version,content_hash,input_json,row_count)
        VALUES (%s,%s,%s,%s,'user_table',%s,%s,%s,%s::jsonb,%s)
        RETURNING expires_at""", (snapshot_id, str(business_id), auth.user_id, str(blueprint_id), str(name or "Таблица")[:120], TABLE_SCHEMA, digest, json.dumps(normalized, ensure_ascii=False), len(normalized["rows"])))
    row = cursor.fetchone()
    return {"id": snapshot_id, "hash": digest, "input": normalized, "row_count": len(normalized["rows"]), "expires_at": row["expires_at"].isoformat(), "source_kind": "user_table", "schema_version": TABLE_SCHEMA}


def resolve_snapshot(cursor, snapshot_id, business_id, user_id, blueprint_id=None, lock=False):
    lock_clause = " FOR SHARE" if lock else ""
    cursor.execute("""SELECT id,business_id,user_id,blueprint_id,schema_version,source_kind,content_hash,input_json
        FROM compiled_input_snapshots WHERE id=%s AND business_id=%s AND user_id=%s AND expires_at > NOW()""" + lock_clause, (str(snapshot_id), str(business_id), str(user_id)))
    row = cursor.fetchone()
    if not row or blueprint_id is not None and str(row["blueprint_id"]) != str(blueprint_id):
        raise SnapshotUnavailable("compiled_snapshot_unavailable")
    value = row["input_json"]
    if isinstance(value, str):
        value = json.loads(value)
    normalized = normalize_table_input(value)
    if row["schema_version"] != TABLE_SCHEMA or content_hash(normalized) != row["content_hash"]:
        raise SnapshotUnavailable("compiled_snapshot_integrity_failed")
    return {"snapshot_id": str(row["id"]), "content_hash": row["content_hash"], "schema_version": row["schema_version"], "source_kind": row["source_kind"], "input": normalized}


def purge_expired_snapshots(cursor, limit=100):
    """Delete expired run data, retaining report metadata and immutable approvals.

    Snapshot and run locks prevent deletion while admission/execution owns the
    data. A running job is retried by the next sweep after normal lease recovery.
    The caller commits cleanup and credit release in one transaction.
    """
    from services.agent_run_billing import finalize_agent_run_credits
    cursor.execute("""SELECT id FROM compiled_input_snapshots WHERE expires_at <= NOW()
        ORDER BY expires_at LIMIT %s FOR UPDATE SKIP LOCKED""", (min(max(int(limit), 1), 1000),))
    snapshots = cursor.fetchall()
    purged = 0
    expired_runs = 0
    for snapshot in snapshots:
        snapshot_id = snapshot["id"]
        cursor.execute("SELECT COUNT(*) count FROM agent_runs WHERE input_snapshot_id=%s", (snapshot_id,))
        expected = cursor.fetchone()["count"]
        cursor.execute("SELECT * FROM agent_runs WHERE input_snapshot_id=%s FOR UPDATE SKIP LOCKED", (snapshot_id,))
        runs = cursor.fetchall()
        if len(runs) != expected or any(row["status"] == "running" for row in runs):
            continue
        for row in runs:
            run = dict(row)
            if run["status"] in {"queued", "retry_wait"}:
                cursor.execute("""UPDATE agent_runs SET status='failed', error_text='compiled_input_expired',
                    completed_at=NOW(), next_attempt_at=NULL, lease_token=NULL, updated_at=NOW() WHERE id=%s""", (run["id"],))
                run["status"] = "failed"
                finalize_agent_run_credits(cursor, run=run, actual_tokens=0)
                expired_runs += 1
            cursor.execute("""UPDATE agent_runs SET
                input_json=jsonb_build_object('snapshot_id',input_snapshot_id,'data_expired',true),
                output_json=(COALESCE(output_json,'{}'::jsonb)-'rows') || jsonb_build_object('data_expired',true),
                updated_at=NOW() WHERE id=%s""", (run["id"],))
        cursor.execute("DELETE FROM compiled_input_snapshots WHERE id=%s", (snapshot_id,))
        purged += 1
    return {"purged_snapshots": purged, "expired_runs": expired_runs}
