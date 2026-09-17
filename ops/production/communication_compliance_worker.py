"""Idempotent archive worker for communication evidence objects.

This module is mounted into the reviewed production app image. The shared
communication_outbox also contains operational jobs; the archive worker must
never claim those rows.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from datetime import datetime, timezone

from psycopg2.extras import RealDictCursor

from pg_db_utils import get_db_connection


def sha256_text(value) -> str:
    raw = value if isinstance(value, bytes) else str(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def archive_capability_report() -> dict[str, object]:
    configured = all(
        str(os.environ.get(name) or "").strip()
        for name in (
            "COMMUNICATION_ARCHIVE_BUCKET",
            "COMMUNICATION_ARCHIVE_ACCESS_KEY_ID",
            "COMMUNICATION_ARCHIVE_SECRET_ACCESS_KEY",
        )
    )
    explicitly_ready = (
        str(os.environ.get("COMMUNICATION_COMPLIANCE_READY") or "false").lower()
        == "true"
    )
    return {
        "backend": str(
            os.environ.get("COMMUNICATION_ARCHIVE_BACKEND") or "provisional_s3"
        ),
        "configured": configured,
        "compliance_ready": bool(configured and explicitly_ready),
    }


class ProvisionalS3Archive:
    def __init__(self) -> None:
        self.bucket = str(os.environ.get("COMMUNICATION_ARCHIVE_BUCKET") or "").strip()
        self.prefix = str(
            os.environ.get("COMMUNICATION_ARCHIVE_PREFIX")
            or "communication-archive-provisional"
        ).strip("/")
        if not self.bucket:
            raise RuntimeError("COMMUNICATION_ARCHIVE_BUCKET is required")

    def _client(self):
        import boto3

        access_key = str(
            os.environ.get("COMMUNICATION_ARCHIVE_ACCESS_KEY_ID") or ""
        ).strip()
        secret_key = str(
            os.environ.get("COMMUNICATION_ARCHIVE_SECRET_ACCESS_KEY") or ""
        ).strip()
        if not access_key or not secret_key:
            raise RuntimeError("communication archive credentials are required")
        return boto3.client(
            "s3",
            endpoint_url=(
                os.environ.get("COMMUNICATION_ARCHIVE_ENDPOINT_URL")
                or "https://storage.yandexcloud.net"
            ),
            region_name=os.environ.get("COMMUNICATION_ARCHIVE_REGION") or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def _key(self, key: str) -> str:
        clean = str(key or "").strip("/")
        return "/".join(part for part in (self.prefix, clean) if part)

    def append_content(self, key: str, raw: bytes, expected: str) -> dict[str, object]:
        actual = sha256_text(raw)
        if not expected or actual != str(expected):
            raise ValueError("archive content hash mismatch")
        archive_key = self._key(key)
        client = self._client()
        client.put_object(
            Bucket=self.bucket,
            Key=archive_key,
            Body=raw,
            ContentType="application/octet-stream",
            Metadata={"sha256": actual},
        )
        head = client.head_object(Bucket=self.bucket, Key=archive_key)
        metadata = head.get("Metadata") if isinstance(head, dict) else {}
        if int(head.get("ContentLength") or -1) != len(raw):
            raise RuntimeError("archive readback size mismatch")
        if str((metadata or {}).get("sha256") or "") != actual:
            raise RuntimeError("archive readback hash mismatch")
        report = archive_capability_report()
        return {
            "backend": report["backend"],
            "bucket": self.bucket,
            "key": archive_key,
            "sha256": actual,
            "compliance_ready": report["compliance_ready"],
        }

    def delete_after_retention(self, key: str) -> None:
        self._client().delete_object(Bucket=self.bucket, Key=str(key or "").strip("/"))


def reconciliation_snapshot(cur) -> dict[str, int]:
    cur.execute("SELECT COUNT(*) AS count FROM sales_room_messages")
    messages = int((cur.fetchone() or {}).get("count") or 0)
    cur.execute(
        "SELECT COUNT(DISTINCT message_id) AS count FROM communication_events "
        "WHERE event_type='accepted' AND message_id IS NOT NULL"
    )
    accepted_messages = int((cur.fetchone() or {}).get("count") or 0)
    cur.execute(
        "SELECT COUNT(*) AS count FROM communication_content_refs "
        "WHERE deleted_at IS NULL"
    )
    live_refs = int((cur.fetchone() or {}).get("count") or 0)
    cur.execute(
        "SELECT COUNT(*) AS count FROM communication_outbox WHERE status='archived'"
    )
    archived_objects = int((cur.fetchone() or {}).get("count") or 0)
    return {
        "messages": messages,
        "messages_with_accepted_event": accepted_messages,
        "messages_missing_accepted_event": max(0, messages - accepted_messages),
        "live_content_refs": live_refs,
        "archived_outbox_objects": archived_objects,
    }


def run_retention_batch(
    cur,
    archive: ProvisionalS3Archive,
    limit: int = 100,
) -> dict[str, int]:
    report = archive_capability_report()
    retention_enabled = (
        str(os.environ.get("COMMUNICATION_RETENTION_APPLY") or "false").lower()
        == "true"
    )
    if not report["compliance_ready"] or not retention_enabled:
        return {"enabled": 0, "deleted": 0}
    cur.execute(
        """SELECT r.id,r.archive_key,r.sha256,e.room_id
             FROM communication_content_refs r
             JOIN communication_events e ON e.id=r.event_id
            WHERE r.deleted_at IS NULL AND r.retained_until <= NOW()
              AND r.archive_status='archived'
              AND NOT EXISTS (
                SELECT 1 FROM communication_legal_holds h
                 WHERE h.released_at IS NULL
                   AND (h.room_id=e.room_id OR h.identity_id=e.sender_identity_id OR h.identity_id=e.recipient_identity_id)
              )
            ORDER BY r.retained_until FOR UPDATE OF r SKIP LOCKED LIMIT %s""",
        (limit,),
    )
    deleted = 0
    for row in cur.fetchall():
        archive.delete_after_retention(str(row["archive_key"]))
        proof = (
            f"retention_delete:{row['id']}:{row['sha256']}:"
            f"{datetime.now(timezone.utc).isoformat()}"
        )
        cur.execute(
            "UPDATE communication_content_refs SET deleted_at=NOW(), "
            "archive_status='deleted_after_retention' WHERE id=%s",
            (row["id"],),
        )
        cur.execute(
            """INSERT INTO communication_access_audit
               (id,room_id,actor_type,actor_ref,action,reason,occurred_at,audit_sha256,metadata_json)
               VALUES (gen_random_uuid(),%s,'system','communication-retention-worker','retention_deleted','retention_expired',NOW(),%s,%s)""",
            (
                row["room_id"],
                sha256_text(proof),
                json.dumps(
                    {"content_ref_id": str(row["id"]), "sha256": row["sha256"]}
                ),
            ),
        )
        deleted += 1
    return {"enabled": 1, "deleted": deleted}


def process_batch(limit: int = 100) -> dict[str, int]:
    conn = get_db_connection()
    processed = failed = 0
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """SELECT * FROM communication_outbox
                 WHERE object_kind IN ('metadata','content','attachment')
                   AND status IN ('pending','retry') AND next_attempt_at <= NOW()
                 ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s""",
            (limit,),
        )
        rows = list(cur.fetchall())
        archive = ProvisionalS3Archive()
        for row in rows:
            try:
                payload = row.get("payload_json") or {}
                envelope_raw = json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ).encode("utf-8")
                envelope_expected = str(row.get("payload_sha256") or "")
                if sha256_text(envelope_raw) != envelope_expected:
                    if bool(payload.get("legacy_partial")):
                        envelope_expected = sha256_text(envelope_raw)
                        cur.execute(
                            "UPDATE communication_outbox SET payload_sha256=%s WHERE id=%s",
                            (envelope_expected, row["id"]),
                        )
                    else:
                        raise ValueError("outbox payload hash mismatch")
                raw = envelope_raw
                expected = envelope_expected
                suffix = "json"
                if row["object_kind"] == "attachment":
                    raw = base64.b64decode(
                        str(payload.get("content_base64") or ""), validate=True
                    )
                    cur.execute(
                        "SELECT sha256 FROM communication_content_refs "
                        "WHERE event_id=%s AND content_kind='attachment'",
                        (row["event_id"],),
                    )
                    content_ref = cur.fetchone() or {}
                    expected = str(content_ref.get("sha256") or "")
                    if not expected or sha256_text(raw) != expected:
                        raise ValueError("attachment content hash mismatch")
                    suffix = "bin"
                key = (
                    f"{datetime.now(timezone.utc):%Y/%m}/{row['event_id']}/"
                    f"{row['object_kind']}.{suffix}"
                )
                result = archive.append_content(key, raw, expected)
                cur.execute(
                    """UPDATE communication_outbox
                          SET status='archived', archived_at=NOW(), updated_at=NOW(),
                              attempts=attempts+1, last_error=NULL
                        WHERE id=%s""",
                    (row["id"],),
                )
                if row["object_kind"] in {"content", "attachment"}:
                    cur.execute(
                        """UPDATE communication_content_refs
                              SET archive_backend=%s, archive_key=%s,
                                  archive_status=%s, verified_at=NOW()
                            WHERE event_id=%s""",
                        (
                            result.get("backend") or "provisional_s3",
                            result.get("key"),
                            "archived"
                            if result.get("compliance_ready")
                            else "provisional",
                            row["event_id"],
                        ),
                    )
                    if row["object_kind"] == "content":
                        cur.execute(
                            """UPDATE sales_room_messages SET archive_status=%s
                                 WHERE id=(SELECT message_id FROM communication_events WHERE id=%s)""",
                            (
                                "archived"
                                if result.get("compliance_ready")
                                else "provisional",
                                row["event_id"],
                            ),
                        )
                processed += 1
            except Exception as exc:
                cur.execute(
                    """UPDATE communication_outbox
                          SET status='retry', attempts=attempts+1,
                              next_attempt_at=NOW() + (LEAST(attempts+1, 12) * INTERVAL '5 minutes'),
                              last_error=%s, updated_at=NOW()
                        WHERE id=%s""",
                    (str(exc)[:2000], row["id"]),
                )
                failed += 1
        cur.execute(
            "SELECT COUNT(*) AS count FROM communication_outbox "
            "WHERE object_kind IN ('metadata','content','attachment') "
            "AND status IN ('pending','retry') "
            "AND created_at < NOW()-INTERVAL '15 minutes'"
        )
        delayed = int((cur.fetchone() or {}).get("count") or 0)
        cur.execute(
            "SELECT COUNT(*) AS count FROM communication_events "
            "WHERE recipient_ref IS NULL OR occurred_at IS NULL OR client_ip IS NULL "
            "OR client_port IS NULL OR service_ip IS NULL OR service_port IS NULL"
        )
        incomplete = int((cur.fetchone() or {}).get("count") or 0)
        retention = run_retention_batch(cur, archive)
        reconciliation = reconciliation_snapshot(cur)
        conn.commit()
        return {
            "processed": processed,
            "failed": failed,
            "archive_lag_over_15m": delayed,
            "incomplete_events": incomplete,
            "ready": int(archive_capability_report()["compliance_ready"]),
            "retention": retention,
            "reconciliation": reconciliation,
        }
    finally:
        conn.close()


def main() -> None:
    interval = max(5, int(os.environ.get("COMMUNICATION_ARCHIVE_POLL_SEC", "15")))
    while True:
        try:
            print(
                json.dumps(
                    {"communication_archive": process_batch()}, ensure_ascii=False
                ),
                flush=True,
            )
        except Exception as exc:
            print(
                json.dumps(
                    {"communication_archive_error": str(exc)}, ensure_ascii=False
                ),
                flush=True,
            )
        time.sleep(interval)


if __name__ == "__main__":
    main()
