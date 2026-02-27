import json
import time
import uuid
from datetime import timedelta
from typing import Any, Callable, Dict, Optional

import hashlib
import hmac
import os
import requests

from database_manager import DatabaseManager
from core.action_ledger import ensure_ledger_tables, write_ledger_entry
from core.action_policy import check_tenant_access, check_token_limit, evaluate_risk_policy, utcnow


Handler = Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


class ActionOrchestrator:
    def __init__(self, handlers: Dict[str, Handler]):
        self.handlers = handlers or {}

    def _row_value(self, row: Any, index: int, key: str, default: Any = None) -> Any:
        if row is None:
            return default
        if isinstance(row, (tuple, list)):
            try:
                return row[index]
            except Exception:
                return default
        if hasattr(row, "get"):
            try:
                return row.get(key, default)
            except Exception:
                return default
        return default

    def ensure_tables(self, cursor) -> None:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_requests (
                action_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                capability TEXT NOT NULL,
                actor_json JSONB NOT NULL,
                payload_json JSONB NOT NULL,
                approval_json JSONB,
                billing_json JSONB,
                trace_id TEXT,
                idempotency_key TEXT NOT NULL,
                status TEXT NOT NULL,
                result_json JSONB,
                error_code TEXT,
                error_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_action_requests_tenant_idempotency ON action_requests(tenant_id, idempotency_key)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_requests_status ON action_requests(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_requests_tenant_created ON action_requests(tenant_id, created_at DESC)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_transitions (
                id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                from_status TEXT,
                to_status TEXT NOT NULL,
                reason TEXT,
                meta_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_transitions_action_id ON action_transitions(action_id)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_approvals (
                action_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                requested_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                decider_actor_json JSONB,
                decision_reason TEXT,
                callback_url TEXT,
                resolved_at TIMESTAMP
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_action_approvals_status ON action_approvals(status)")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_callback_outbox (
                id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                callback_url TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload_json JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_error TEXT,
                locked_at TIMESTAMP,
                sent_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_callback_outbox_status_next ON action_callback_outbox(status, next_attempt_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_callback_outbox_action_id ON action_callback_outbox(action_id)"
        )
        cursor.execute(
            "ALTER TABLE action_callback_outbox ADD COLUMN IF NOT EXISTS dedupe_key TEXT"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_action_callback_outbox_dedupe_key ON action_callback_outbox(dedupe_key)"
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS action_callback_attempts (
                id TEXT PRIMARY KEY,
                outbox_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                attempt_no INTEGER NOT NULL,
                success BOOLEAN NOT NULL DEFAULT FALSE,
                http_status INTEGER,
                duration_ms INTEGER,
                error_text TEXT,
                response_excerpt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_callback_attempts_action_id ON action_callback_attempts(action_id, created_at DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_action_callback_attempts_outbox_id ON action_callback_attempts(outbox_id)"
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS openclaw_capability_health_history (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                status TEXT NOT NULL,
                ready BOOLEAN NOT NULL DEFAULT FALSE,
                checks_json JSONB NOT NULL,
                metrics_json JSONB NOT NULL,
                alerts_json JSONB NOT NULL,
                window_minutes INTEGER NOT NULL DEFAULT 60,
                captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_openclaw_health_history_tenant_captured ON openclaw_capability_health_history(tenant_id, captured_at DESC)"
        )

        ensure_ledger_tables(cursor)

    def _transition(self, cursor, action_id: str, from_status: Optional[str], to_status: str, reason: str = "", meta: Optional[Dict[str, Any]] = None) -> None:
        cursor.execute(
            """
            INSERT INTO action_transitions (id, action_id, from_status, to_status, reason, meta_json)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                action_id,
                from_status,
                to_status,
                reason or None,
                json.dumps(meta or {}, ensure_ascii=False),
            ),
        )
        cursor.execute(
            "UPDATE action_requests SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE action_id = %s",
            (to_status, action_id),
        )

    def _validate(self, envelope: Dict[str, Any]) -> Optional[str]:
        required = ["tenant_id", "actor", "trace_id", "idempotency_key", "capability", "approval", "billing"]
        for key in required:
            if key not in envelope:
                return f"missing required field: {key}"
        if envelope.get("capability") not in self.handlers:
            return "unsupported capability"
        return None

    def _read_tokenusage_total(self, cursor, tenant_id: str, user_id: str) -> int:
        try:
            cursor.execute("SELECT to_regclass('tokenusage') AS reg")
            reg_row = cursor.fetchone()
            reg_val = self._row_value(reg_row, 0, "reg")
            if not reg_val:
                return 0
            cursor.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM tokenusage
                WHERE business_id = %s
                  AND user_id = %s
                """,
                (tenant_id, user_id),
            )
            row = cursor.fetchone()
            return int(self._row_value(row, 0, "total_tokens", 0) or 0)
        except Exception:
            return 0

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    def _release_action_reserve(self, cursor, action_id: str, tenant_id: str, tariff_id: Optional[str] = None) -> int:
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN entry_type='reserve' THEN tokens_out ELSE 0 END), 0) AS reserve_total,
                COALESCE(SUM(CASE WHEN entry_type='settle' THEN tokens_out ELSE 0 END), 0) AS settled_total,
                COALESCE(SUM(CASE WHEN entry_type='release' THEN tokens_out ELSE 0 END), 0) AS released_total
            FROM billing_ledger
            WHERE action_id = %s
            """,
            (action_id,),
        )
        row = cursor.fetchone() or (0, 0, 0)
        reserve_total = int(self._row_value(row, 0, "reserve_total", 0) or 0)
        settled_total = int(self._row_value(row, 1, "settled_total", 0) or 0)
        released_total = int(self._row_value(row, 2, "released_total", 0) or 0)
        pending_release = max(reserve_total - settled_total - released_total, 0)
        if pending_release > 0:
            write_ledger_entry(
                cursor,
                action_id=action_id,
                tenant_id=tenant_id,
                entry_type="release",
                tokens_out=pending_release,
                cost=0.0,
                tariff_id=tariff_id,
                meta={"reason": "action_finalized_without_execution"},
            )
        return pending_release

    def _retry_delay_seconds(self, attempts: int) -> int:
        # bounded exponential backoff: 5s, 10s, 20s, ... max 300s
        safe_attempts = max(1, int(attempts or 1))
        return min(300, 5 * (2 ** (safe_attempts - 1)))

    def _enqueue_callback(
        self,
        cursor,
        *,
        action_id: str,
        tenant_id: str,
        callback_url: str,
        event_type: str,
        payload: Dict[str, Any],
        dedupe_key: Optional[str] = None,
        max_attempts: int = 5,
    ) -> Optional[str]:
        callback_url = str(callback_url or "").strip()
        if not callback_url:
            return None
        outbox_id = str(uuid.uuid4())
        effective_dedupe_key = str(dedupe_key or f"{action_id}:{event_type}")
        cursor.execute(
            """
            INSERT INTO action_callback_outbox
                (id, action_id, tenant_id, callback_url, event_type, payload_json, status, attempts, max_attempts, next_attempt_at, dedupe_key)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', 0, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (dedupe_key) DO NOTHING
            RETURNING id
            """,
            (
                outbox_id,
                action_id,
                tenant_id,
                callback_url,
                event_type,
                json.dumps(payload or {}, ensure_ascii=False),
                max(1, int(max_attempts or 5)),
                effective_dedupe_key,
            ),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_value(row, 0, "id", outbox_id)

    def _callback_signature_secret(self) -> str:
        # Use dedicated secret when provided; fallback to integration token for bootstrap.
        return (
            os.getenv("OPENCLAW_CALLBACK_SIGNING_SECRET", "").strip()
            or os.getenv("OPENCLAW_LOCALOS_TOKEN", "").strip()
        )

    def _build_callback_signature(self, payload: Dict[str, Any], event_id: str, event_ts: str) -> str:
        secret = self._callback_signature_secret()
        if not secret:
            return ""
        body = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        message = f"{event_id}.{event_ts}.{body}"
        return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()

    def _send_callback(
        self,
        callback_url: str,
        payload: Dict[str, Any],
        *,
        action_id: str,
        tenant_id: str,
        event_type: str,
    ) -> None:
        if not callback_url:
            return
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            self._enqueue_callback(
                cursor,
                action_id=action_id,
                tenant_id=tenant_id,
                callback_url=callback_url,
                event_type=event_type,
                payload=payload,
            )
            db.conn.commit()
        except Exception:
            db.conn.rollback()
        finally:
            db.close()
        # best-effort immediate dispatch; failures stay in outbox with retries
        try:
            self.dispatch_callback_outbox(batch_size=10)
        except Exception:
            pass

    def dispatch_callback_outbox(self, batch_size: int = 50, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            batch_size = max(1, min(int(batch_size or 50), 500))

            tenant_clause = "AND tenant_id = %s" if tenant_id else ""
            query = f"""
                WITH picked AS (
                    SELECT id
                    FROM action_callback_outbox
                    WHERE status IN ('pending', 'retry')
                      AND next_attempt_at <= CURRENT_TIMESTAMP
                      {tenant_clause}
                    ORDER BY created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE action_callback_outbox o
                SET status='sending', locked_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                FROM picked
                WHERE o.id = picked.id
                RETURNING o.id, o.action_id, o.tenant_id, o.callback_url, o.event_type, o.payload_json, o.attempts, o.max_attempts, o.dedupe_key
            """
            params = [batch_size]
            if tenant_id:
                params = [str(tenant_id), batch_size]
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() or []
            db.conn.commit()

            sent = 0
            retried = 0
            dlq = 0
            for row in rows:
                outbox_id = self._row_value(row, 0, "id")
                action_id = self._row_value(row, 1, "action_id")
                tenant_id = self._row_value(row, 2, "tenant_id")
                callback_url = self._row_value(row, 3, "callback_url")
                event_type = self._row_value(row, 4, "event_type")
                payload = self._row_value(row, 5, "payload_json") or {}
                attempts = int(self._row_value(row, 6, "attempts", 0) or 0)
                max_attempts = int(self._row_value(row, 7, "max_attempts", 5) or 5)
                dedupe_key = self._row_value(row, 8, "dedupe_key") or f"{outbox_id}"

                ok = True
                error_text = ""
                http_status: Optional[int] = None
                response_excerpt = ""
                duration_ms: Optional[int] = None
                start_ts = time.monotonic()
                try:
                    # OpenClaw callback contract expects epoch-seconds string.
                    event_ts = str(int(time.time()))
                    signature = self._build_callback_signature(payload, outbox_id, event_ts)
                    canonical_body = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    headers = {
                        "Content-Type": "application/json",
                        "X-LocalOS-Event-Id": str(outbox_id),
                        "X-LocalOS-Event-Timestamp": event_ts,
                        "X-LocalOS-Dedupe-Key": str(dedupe_key),
                    }
                    if signature:
                        headers["X-LocalOS-Signature"] = signature
                    response = requests.post(callback_url, data=canonical_body.encode("utf-8"), timeout=5, headers=headers)
                    duration_ms = int((time.monotonic() - start_ts) * 1000)
                    http_status = int(getattr(response, "status_code", 500))
                    response_excerpt = str(getattr(response, "text", "") or "")[:1000]
                    if http_status >= 400:
                        ok = False
                        error_text = f"http_{http_status}"
                except Exception as exc:
                    ok = False
                    error_text = str(exc)
                    duration_ms = int((time.monotonic() - start_ts) * 1000)

                db2 = DatabaseManager()
                cur2 = db2.conn.cursor()
                try:
                    cur2.execute(
                        """
                        INSERT INTO action_callback_attempts
                        (id, outbox_id, action_id, tenant_id, event_type, attempt_no, success, http_status, duration_ms, error_text, response_excerpt)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid.uuid4()),
                            str(outbox_id),
                            str(action_id),
                            str(tenant_id),
                            str(event_type),
                            attempts + 1,
                            bool(ok),
                            http_status,
                            duration_ms,
                            (error_text or "")[:1000] if not ok else None,
                            response_excerpt,
                        ),
                    )
                    if ok:
                        cur2.execute(
                            """
                            UPDATE action_callback_outbox
                            SET status='sent', sent_at=CURRENT_TIMESTAMP, locked_at=NULL, updated_at=CURRENT_TIMESTAMP
                            WHERE id=%s
                            """,
                            (outbox_id,),
                        )
                        sent += 1
                    else:
                        new_attempts = attempts + 1
                        if new_attempts >= max_attempts:
                            cur2.execute(
                                """
                                UPDATE action_callback_outbox
                                SET status='dlq', attempts=%s, last_error=%s, locked_at=NULL, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s
                                """,
                                (new_attempts, (error_text or "")[:1000], outbox_id),
                            )
                            dlq += 1
                        else:
                            backoff_sec = self._retry_delay_seconds(new_attempts)
                            cur2.execute(
                                """
                                UPDATE action_callback_outbox
                                SET status='retry', attempts=%s, last_error=%s,
                                    next_attempt_at=(CURRENT_TIMESTAMP + (%s || ' seconds')::interval),
                                    locked_at=NULL, updated_at=CURRENT_TIMESTAMP
                                WHERE id=%s
                                """,
                                (new_attempts, (error_text or "")[:1000], backoff_sec, outbox_id),
                            )
                            retried += 1
                    db2.conn.commit()
                finally:
                    db2.close()

            payload = {
                "success": True,
                "picked": len(rows),
                "sent": sent,
                "retried": retried,
                "dlq": dlq,
            }
            if tenant_id:
                payload["tenant_id"] = str(tenant_id)
            return payload
        finally:
            db.close()

    def dispatch_callback_outbox_for_tenant(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        batch_size: int = 50,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}
            db.conn.commit()
        finally:
            db.close()

        return self.dispatch_callback_outbox(batch_size=batch_size, tenant_id=str(tenant_id))

    def _is_expired(self, expires_at: Any) -> bool:
        if not expires_at:
            return False
        now_naive = utcnow().replace(tzinfo=None)
        try:
            dt = expires_at.replace(tzinfo=None) if getattr(expires_at, "tzinfo", None) else expires_at
            return now_naive > dt
        except Exception:
            return False

    def _expire_pending_if_needed(
        self,
        cursor,
        *,
        action_id: str,
        action_status: str,
        approval_status: str,
        expires_at: Any,
        tenant_id: str,
        billing_json: Any,
    ) -> str:
        if action_status != "pending_human":
            return action_status
        if approval_status != "pending_human":
            return action_status
        if not self._is_expired(expires_at):
            return action_status

        cursor.execute(
            """
            UPDATE action_approvals
            SET status='expired', decision_reason=%s, resolved_at=CURRENT_TIMESTAMP
            WHERE action_id=%s
            """,
            ("ttl expired", action_id),
        )
        self._transition(cursor, action_id, "pending_human", "expired", "ttl expired")
        cursor.execute("SELECT callback_url FROM action_approvals WHERE action_id=%s", (action_id,))
        callback_row = cursor.fetchone()
        callback_url = self._row_value(callback_row, 0, "callback_url")
        self._enqueue_callback(
            cursor,
            action_id=action_id,
            tenant_id=tenant_id,
            callback_url=callback_url,
            event_type="expired",
            payload={
                "action_id": action_id,
                "tenant_id": tenant_id,
                "status": "expired",
                    "decision_reason": "ttl expired",
            },
            dedupe_key=f"{action_id}:expired",
        )
        billing_obj = self._as_dict(billing_json)
        self._release_action_reserve(cursor, action_id, tenant_id, billing_obj.get("tariff_id"))
        return "expired"

    def execute(self, envelope: Dict[str, Any], user_data: Dict[str, Any], *, allow_execute_when_approved: bool = False) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)

            validation_error = self._validate(envelope)
            if validation_error:
                return {"success": False, "status": "failed", "error": validation_error}

            tenant_id = str(envelope["tenant_id"])
            actor = envelope.get("actor") or {}
            actor_user_id = str(actor.get("id") or user_data.get("user_id") or "")
            is_superadmin = bool(user_data.get("is_superadmin"))
            capability = str(envelope["capability"])
            payload = envelope.get("payload") or {}
            approval = envelope.get("approval") or {}
            billing = envelope.get("billing") or {}
            idempotency_key = str(envelope["idempotency_key"])
            trace_id = str(envelope.get("trace_id") or "")
            action_id = str(envelope.get("action_id") or "")

            reused_existing_action = False
            if action_id:
                cursor.execute(
                    """
                    SELECT action_id, status, result_json, error_code, error_text, billing_json
                    FROM action_requests
                    WHERE action_id = %s
                    LIMIT 1
                    """,
                    (action_id,),
                )
                existing_by_id = cursor.fetchone()
                if existing_by_id:
                    status_by_id = self._row_value(existing_by_id, 1, "status")
                    if status_by_id in ("completed", "failed"):
                        return {
                            "success": status_by_id == "completed",
                            "status": status_by_id,
                            "action_id": action_id,
                            "trace_id": trace_id,
                            "result": self._row_value(existing_by_id, 2, "result_json"),
                            "error_code": self._row_value(existing_by_id, 3, "error_code"),
                            "error": self._row_value(existing_by_id, 4, "error_text"),
                            "billing": self._row_value(existing_by_id, 5, "billing_json"),
                            "idempotent_replay": True,
                        }
                    reused_existing_action = True

            cursor.execute(
                """
                SELECT action_id, status, result_json, error_code, error_text, billing_json
                FROM action_requests
                WHERE tenant_id = %s AND idempotency_key = %s
                LIMIT 1
                """,
                (tenant_id, idempotency_key),
            )
            existing = cursor.fetchone()
            if existing:
                action_id = self._row_value(existing, 0, "action_id")
                status = self._row_value(existing, 1, "status")
                return {
                    "success": status in ("completed", "approved"),
                    "status": status,
                    "action_id": action_id,
                    "trace_id": trace_id,
                    "result": self._row_value(existing, 2, "result_json"),
                    "error_code": self._row_value(existing, 3, "error_code"),
                    "error": self._row_value(existing, 4, "error_text"),
                    "billing": self._row_value(existing, 5, "billing_json"),
                    "idempotent_replay": True,
                }

            if not reused_existing_action:
                action_id = action_id or str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO action_requests (
                        action_id, tenant_id, capability, actor_json, payload_json, approval_json,
                        billing_json, trace_id, idempotency_key, status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'received')
                    """,
                    (
                        action_id,
                        tenant_id,
                        capability,
                        json.dumps(actor, ensure_ascii=False),
                        json.dumps(payload, ensure_ascii=False),
                        json.dumps(approval, ensure_ascii=False),
                        json.dumps(billing, ensure_ascii=False),
                        trace_id,
                        idempotency_key,
                    ),
                )
                self._transition(cursor, action_id, "received", "validated")
            else:
                self._transition(cursor, action_id, None, "validated", "resume approved action")

            access_check = check_tenant_access(cursor, tenant_id, actor_user_id, is_superadmin)
            if not access_check.get("ok"):
                self._transition(cursor, action_id, "validated", "failed", access_check.get("reason", "access denied"), {"error_code": access_check.get("code")})
                cursor.execute(
                    "UPDATE action_requests SET error_code=%s, error_text=%s WHERE action_id=%s",
                    (access_check.get("code"), access_check.get("reason"), action_id),
                )
                db.conn.commit()
                return {
                    "success": False,
                    "status": "failed",
                    "action_id": action_id,
                    "trace_id": trace_id,
                    "error_code": access_check.get("code"),
                    "error": access_check.get("reason"),
                }

            risk = evaluate_risk_policy(capability, payload, approval)
            self._transition(cursor, action_id, "validated", "policy_checked", risk.get("reason", ""))

            requires_human = bool(risk.get("requires_human")) and not allow_execute_when_approved
            if requires_human:
                ttl_sec = int((approval or {}).get("ttl_sec") or 1800)
                requested_at = utcnow()
                expires_at = requested_at + timedelta(seconds=ttl_sec)
                callback_url = (approval or {}).get("callback_url")
                cursor.execute(
                    """
                    INSERT INTO action_approvals (action_id, status, requested_at, expires_at, callback_url)
                    VALUES (%s, 'pending_human', %s, %s, %s)
                    """,
                    (action_id, requested_at, expires_at, callback_url),
                )
                self._transition(cursor, action_id, "policy_checked", "pending_human", risk.get("reason", "approval required"))
                self._enqueue_callback(
                    cursor,
                    action_id=action_id,
                    tenant_id=tenant_id,
                    callback_url=callback_url,
                    event_type="pending_human",
                    payload={
                        "action_id": action_id,
                        "tenant_id": tenant_id,
                        "status": "pending_human",
                        "trace_id": trace_id,
                        "capability": capability,
                        "reason": risk.get("reason"),
                        "expires_at": expires_at.isoformat(),
                    },
                    dedupe_key=f"{action_id}:pending_human",
                )
                db.conn.commit()
                try:
                    self.dispatch_callback_outbox(batch_size=10)
                except Exception:
                    pass
                return {
                    "success": True,
                    "status": "pending_human",
                    "action_id": action_id,
                    "trace_id": trace_id,
                    "approval": {
                        "status": "pending_human",
                        "reason": risk.get("reason"),
                        "expires_at": expires_at.isoformat(),
                    },
                }

            reserve_tokens = int((billing or {}).get("reserve_tokens") or 2000)
            limit_check = check_token_limit(cursor, tenant_id, reserve_tokens)
            if not limit_check.get("ok"):
                self._transition(cursor, action_id, "policy_checked", "failed", limit_check.get("reason", "limit exceeded"), {"error_code": limit_check.get("code")})
                cursor.execute(
                    "UPDATE action_requests SET error_code=%s, error_text=%s WHERE action_id=%s",
                    (limit_check.get("code"), limit_check.get("reason"), action_id),
                )
                db.conn.commit()
                return {
                    "success": False,
                    "status": "failed",
                    "action_id": action_id,
                    "trace_id": trace_id,
                    "error_code": limit_check.get("code"),
                    "error": limit_check.get("reason"),
                    "limits": {
                        "limit_tokens": limit_check.get("limit_tokens"),
                        "spent_tokens": limit_check.get("spent_tokens"),
                        "reserved_tokens": limit_check.get("reserved_tokens"),
                        "requested_tokens": limit_check.get("requested_tokens"),
                    },
                }

            write_ledger_entry(
                cursor,
                action_id=action_id,
                tenant_id=tenant_id,
                entry_type="reserve",
                tokens_out=reserve_tokens,
                cost=0.0,
                tariff_id=(billing or {}).get("tariff_id"),
                meta={"capability": capability},
            )
            self._transition(cursor, action_id, "policy_checked", "reserved")
            self._transition(cursor, action_id, "reserved", "executing")
            before_total_tokens = self._read_tokenusage_total(cursor, tenant_id, actor_user_id)
            db.conn.commit()

            handler = self.handlers[capability]
            handler_result = handler(
                {
                    "tenant_id": tenant_id,
                    "actor": actor,
                    "trace_id": trace_id,
                    "capability": capability,
                    "payload": payload,
                    "approval": approval,
                    "billing": billing,
                    "action_id": action_id,
                },
                user_data,
            ) or {}

            out_billing = handler_result.get("billing") or {}
            db2 = DatabaseManager()
            cur2 = db2.conn.cursor()
            after_total_tokens = self._read_tokenusage_total(cur2, tenant_id, actor_user_id)
            delta_tokens = max(after_total_tokens - before_total_tokens, 0)
            used_tokens = int(out_billing.get("total_tokens") or 0)
            if used_tokens <= 0:
                used_tokens = delta_tokens
            used_cost = float(out_billing.get("cost") or 0.0)
            tariff_id = out_billing.get("tariff_id") or (billing or {}).get("tariff_id")

            self.ensure_tables(cur2)
            write_ledger_entry(
                cur2,
                action_id=action_id,
                tenant_id=tenant_id,
                entry_type="settle",
                tokens_out=used_tokens,
                cost=used_cost,
                tariff_id=tariff_id,
                meta={"capability": capability},
            )
            if reserve_tokens > used_tokens:
                write_ledger_entry(
                    cur2,
                    action_id=action_id,
                    tenant_id=tenant_id,
                    entry_type="release",
                    tokens_out=reserve_tokens - used_tokens,
                    cost=0.0,
                    tariff_id=tariff_id,
                    meta={"reason": "reserve_excess"},
                )

            self._transition(cur2, action_id, "executing", "completed")
            cur2.execute(
                """
                UPDATE action_requests
                SET result_json=%s, billing_json=%s, updated_at=CURRENT_TIMESTAMP
                WHERE action_id=%s
                """,
                (
                    json.dumps(handler_result.get("result") or {}, ensure_ascii=False),
                    json.dumps(out_billing, ensure_ascii=False),
                    action_id,
                ),
            )
            callback_url = self._as_dict(approval).get("callback_url")
            self._enqueue_callback(
                cur2,
                action_id=action_id,
                tenant_id=tenant_id,
                callback_url=callback_url,
                event_type="completed",
                payload={
                    "action_id": action_id,
                    "tenant_id": tenant_id,
                    "status": "completed",
                    "trace_id": trace_id,
                    "capability": capability,
                    "result": handler_result.get("result") or {},
                    "billing": out_billing,
                },
                dedupe_key=f"{action_id}:completed",
            )
            db2.conn.commit()
            db2.close()
            try:
                self.dispatch_callback_outbox(batch_size=10)
            except Exception:
                pass

            return {
                "success": True,
                "status": "completed",
                "action_id": action_id,
                "trace_id": trace_id,
                "result": handler_result.get("result") or {},
                "billing": out_billing,
            }

        except Exception as e:
            try:
                self._transition(cursor, action_id, "executing", "failed", str(e))
                cursor.execute(
                    "UPDATE action_requests SET error_code=%s, error_text=%s WHERE action_id=%s",
                    ("EXECUTION_ERROR", str(e), action_id),
                )
                reserve_tokens = int((envelope.get("billing") or {}).get("reserve_tokens") or 2000)
                write_ledger_entry(
                    cursor,
                    action_id=action_id,
                    tenant_id=str(envelope.get("tenant_id") or ""),
                    entry_type="release",
                    tokens_out=reserve_tokens,
                    cost=0.0,
                    tariff_id=(envelope.get("billing") or {}).get("tariff_id"),
                    meta={"reason": "execution_error"},
                )
                db.conn.commit()
            except Exception:
                pass
            return {
                "success": False,
                "status": "failed",
                "action_id": action_id if "action_id" in locals() else None,
                "trace_id": envelope.get("trace_id"),
                "error_code": "EXECUTION_ERROR",
                "error": str(e),
            }
        finally:
            db.close()

    def resolve_human_decision(self, action_id: str, decision: str, user_data: Dict[str, Any], decision_reason: str = "") -> Dict[str, Any]:
        decision = str(decision or "").strip().lower()
        if decision not in {"approved", "rejected", "expired"}:
            return {"success": False, "error": "decision must be approved|rejected|expired", "http_code": 400}

        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            cursor.execute(
                """
                SELECT ar.action_id, ar.tenant_id, ar.capability, ar.payload_json, ar.actor_json, ar.approval_json, ar.billing_json, ar.trace_id, ar.status, b.owner_id
                FROM action_requests ar
                LEFT JOIN businesses b ON b.id = ar.tenant_id
                WHERE ar.action_id = %s
                LIMIT 1
                """,
                (action_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "action not found", "http_code": 404}

            owner_id = self._row_value(row, 9, "owner_id")
            if str(owner_id) != str(user_data.get("user_id")) and not user_data.get("is_superadmin"):
                return {"success": False, "error": "forbidden", "http_code": 403}

            status = self._row_value(row, 8, "status")
            if status != "pending_human":
                return {"success": False, "error": f"action is not pending_human (status={status})", "http_code": 400}

            cursor.execute("SELECT status, expires_at, callback_url FROM action_approvals WHERE action_id=%s", (action_id,))
            appr = cursor.fetchone()
            if not appr:
                return {"success": False, "error": "approval record not found", "http_code": 404}

            expires_at = self._row_value(appr, 1, "expires_at")
            callback_url = self._row_value(appr, 2, "callback_url")
            if decision == "approved" and expires_at and utcnow().replace(tzinfo=None) > expires_at:
                decision = "expired"

            cursor.execute(
                """
                UPDATE action_approvals
                SET status=%s, decider_actor_json=%s, decision_reason=%s, resolved_at=CURRENT_TIMESTAMP
                WHERE action_id=%s
                """,
                (
                    decision,
                    json.dumps(
                        {
                            "id": user_data.get("user_id"),
                            "name": user_data.get("name"),
                            "email": user_data.get("email"),
                        },
                        ensure_ascii=False,
                    ),
                    decision_reason,
                    action_id,
                ),
            )
            self._transition(cursor, action_id, "pending_human", decision, decision_reason or "")
            billing_json = self._as_dict(self._row_value(row, 6, "billing_json"))
            if decision in {"rejected", "expired"}:
                self._release_action_reserve(
                    cursor,
                    action_id,
                    self._row_value(row, 1, "tenant_id"),
                    billing_json.get("tariff_id"),
                )
                self._enqueue_callback(
                    cursor,
                    action_id=action_id,
                    tenant_id=self._row_value(row, 1, "tenant_id"),
                    callback_url=callback_url,
                    event_type=decision,
                    payload={
                        "action_id": action_id,
                        "tenant_id": self._row_value(row, 1, "tenant_id"),
                        "status": decision,
                        "decision_reason": decision_reason,
                        "trace_id": self._row_value(row, 7, "trace_id"),
                        "capability": self._row_value(row, 2, "capability"),
                    },
                    dedupe_key=f"{action_id}:{decision}",
                )
            db.conn.commit()
            try:
                self.dispatch_callback_outbox(batch_size=10)
            except Exception:
                pass

            if decision != "approved":
                return {
                    "success": True,
                    "status": decision,
                    "action_id": action_id,
                }

            payload_json = self._as_dict(self._row_value(row, 3, "payload_json"))
            actor_json = self._as_dict(self._row_value(row, 4, "actor_json"))
            approval_json = self._as_dict(self._row_value(row, 5, "approval_json"))
            billing_json = self._as_dict(self._row_value(row, 6, "billing_json"))

            envelope = {
                "action_id": self._row_value(row, 0, "action_id"),
                "tenant_id": self._row_value(row, 1, "tenant_id"),
                "capability": self._row_value(row, 2, "capability"),
                "payload": payload_json,
                "actor": actor_json,
                "approval": approval_json,
                "billing": billing_json,
                "trace_id": self._row_value(row, 7, "trace_id"),
                "idempotency_key": f"{action_id}:approved",
            }
            exec_result = self.execute(envelope, user_data, allow_execute_when_approved=True)
            self._send_callback(
                callback_url,
                {
                    "action_id": action_id,
                    "tenant_id": self._row_value(row, 1, "tenant_id"),
                    "status": exec_result.get("status"),
                    "success": exec_result.get("success"),
                    "trace_id": exec_result.get("trace_id"),
                    "error": exec_result.get("error"),
                },
                action_id=action_id,
                tenant_id=self._row_value(row, 1, "tenant_id"),
                event_type="approved",
            )
            return exec_result
        finally:
            db.close()

    def get_action(self, action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            cursor.execute(
                """
                SELECT ar.action_id, ar.tenant_id, ar.capability, ar.status, ar.result_json, ar.error_code, ar.error_text,
                       ar.billing_json, ar.trace_id, b.owner_id, aa.status AS approval_status, aa.expires_at
                FROM action_requests ar
                LEFT JOIN businesses b ON b.id = ar.tenant_id
                LEFT JOIN action_approvals aa ON aa.action_id = ar.action_id
                WHERE ar.action_id = %s
                LIMIT 1
                """,
                (action_id,),
            )
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "action not found", "http_code": 404}

            owner_id = self._row_value(row, 9, "owner_id")
            if str(owner_id) != str(user_data.get("user_id")) and not user_data.get("is_superadmin"):
                return {"success": False, "error": "forbidden", "http_code": 403}

            status = self._row_value(row, 3, "status")
            status = self._expire_pending_if_needed(
                cursor,
                action_id=self._row_value(row, 0, "action_id"),
                action_status=status,
                approval_status=self._row_value(row, 10, "approval_status"),
                expires_at=self._row_value(row, 11, "expires_at"),
                tenant_id=self._row_value(row, 1, "tenant_id"),
                billing_json=self._row_value(row, 7, "billing_json"),
            )
            db.conn.commit()

            return {
                "success": True,
                "action_id": self._row_value(row, 0, "action_id"),
                "tenant_id": self._row_value(row, 1, "tenant_id"),
                "capability": self._row_value(row, 2, "capability"),
                "status": status,
                "result": self._row_value(row, 4, "result_json"),
                "error_code": self._row_value(row, 5, "error_code"),
                "error": self._row_value(row, 6, "error_text"),
                "billing": self._row_value(row, 7, "billing_json"),
                "trace_id": self._row_value(row, 8, "trace_id"),
            }
        finally:
            db.close()

    def list_actions(self, user_data: Dict[str, Any], tenant_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            where = []
            params = []
            if not is_superadmin:
                where.append("b.owner_id = %s")
                params.append(current_user)
            if tenant_id:
                where.append("ar.tenant_id = %s")
                params.append(str(tenant_id))
            if status:
                where.append("ar.status = %s")
                params.append(str(status))
            where_clause = ("WHERE " + " AND ".join(where)) if where else ""

            limit = max(1, min(int(limit or 50), 200))
            offset = max(0, int(offset or 0))

            cursor.execute(
                f"""
                SELECT ar.action_id, ar.tenant_id, ar.capability, ar.status, ar.result_json, ar.error_code, ar.error_text,
                       ar.billing_json, ar.trace_id, ar.created_at, ar.updated_at, aa.status AS approval_status, aa.expires_at
                FROM action_requests ar
                LEFT JOIN businesses b ON b.id = ar.tenant_id
                LEFT JOIN action_approvals aa ON aa.action_id = ar.action_id
                {where_clause}
                ORDER BY ar.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cursor.fetchall() or []

            items = []
            for row in rows:
                item_status = self._row_value(row, 3, "status")
                item_status = self._expire_pending_if_needed(
                    cursor,
                    action_id=self._row_value(row, 0, "action_id"),
                    action_status=item_status,
                    approval_status=self._row_value(row, 11, "approval_status"),
                    expires_at=self._row_value(row, 12, "expires_at"),
                    tenant_id=self._row_value(row, 1, "tenant_id"),
                    billing_json=self._row_value(row, 7, "billing_json"),
                )
                items.append(
                    {
                        "action_id": self._row_value(row, 0, "action_id"),
                        "tenant_id": self._row_value(row, 1, "tenant_id"),
                        "capability": self._row_value(row, 2, "capability"),
                        "status": item_status,
                        "result": self._row_value(row, 4, "result_json"),
                        "error_code": self._row_value(row, 5, "error_code"),
                        "error": self._row_value(row, 6, "error_text"),
                        "billing": self._row_value(row, 7, "billing_json"),
                        "trace_id": self._row_value(row, 8, "trace_id"),
                        "created_at": str(self._row_value(row, 9, "created_at") or ""),
                        "updated_at": str(self._row_value(row, 10, "updated_at") or ""),
                    }
                )

            db.conn.commit()
            return {
                "success": True,
                "items": items,
                "limit": limit,
                "offset": offset,
                "count": len(items),
            }
        finally:
            db.close()

    def get_action_billing(self, action_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)

            cursor.execute(
                """
                SELECT ar.action_id, ar.tenant_id, ar.status, ar.billing_json, b.owner_id, aa.status AS approval_status, aa.expires_at
                FROM action_requests ar
                LEFT JOIN businesses b ON b.id = ar.tenant_id
                LEFT JOIN action_approvals aa ON aa.action_id = ar.action_id
                WHERE ar.action_id = %s
                LIMIT 1
                """,
                (action_id,),
            )
            action_row = cursor.fetchone()
            if not action_row:
                return {"success": False, "error": "action not found", "http_code": 404}

            owner_id = self._row_value(action_row, 4, "owner_id")
            if str(owner_id) != str(user_data.get("user_id")) and not user_data.get("is_superadmin"):
                return {"success": False, "error": "forbidden", "http_code": 403}

            action_status = self._expire_pending_if_needed(
                cursor,
                action_id=self._row_value(action_row, 0, "action_id"),
                action_status=self._row_value(action_row, 2, "status"),
                approval_status=self._row_value(action_row, 5, "approval_status"),
                expires_at=self._row_value(action_row, 6, "expires_at"),
                tenant_id=self._row_value(action_row, 1, "tenant_id"),
                billing_json=self._row_value(action_row, 3, "billing_json"),
            )

            cursor.execute(
                """
                SELECT id, entry_type, tokens_in, tokens_out, cost, tariff_id, month_key, meta_json, created_at
                FROM billing_ledger
                WHERE action_id = %s
                ORDER BY created_at ASC
                """,
                (action_id,),
            )
            rows = cursor.fetchall() or []

            entries = []
            reserve_total = 0
            settle_total = 0
            release_total = 0
            cost_total = 0.0

            for row in rows:
                entry_type = str(self._row_value(row, 1, "entry_type") or "")
                tokens_out = int(self._row_value(row, 3, "tokens_out", 0) or 0)
                cost = float(self._row_value(row, 4, "cost", 0.0) or 0.0)
                if entry_type == "reserve":
                    reserve_total += tokens_out
                elif entry_type == "settle":
                    settle_total += tokens_out
                elif entry_type == "release":
                    release_total += tokens_out
                cost_total += cost

                entries.append(
                    {
                        "id": self._row_value(row, 0, "id"),
                        "entry_type": entry_type,
                        "tokens_in": int(self._row_value(row, 2, "tokens_in", 0) or 0),
                        "tokens_out": tokens_out,
                        "cost": cost,
                        "tariff_id": self._row_value(row, 5, "tariff_id"),
                        "month_key": self._row_value(row, 6, "month_key"),
                        "meta": self._row_value(row, 7, "meta_json"),
                        "created_at": str(self._row_value(row, 8, "created_at") or ""),
                    }
                )

            db.conn.commit()
            return {
                "success": True,
                "action_id": self._row_value(action_row, 0, "action_id"),
                "tenant_id": self._row_value(action_row, 1, "tenant_id"),
                "status": action_status,
                "summary": {
                    "reserved_tokens": reserve_total,
                    "settled_tokens": settle_total,
                    "released_tokens": release_total,
                    "inflight_reserved_tokens": max(reserve_total - settle_total - release_total, 0),
                    "total_cost": round(cost_total, 6),
                },
                "entries": entries,
            }
        finally:
            db.close()

    def get_action_timeline(
        self,
        action_id: str,
        user_data: Dict[str, Any],
        *,
        limit: int = 200,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            limit = max(1, min(int(limit or 200), 500))

            cursor.execute(
                """
                SELECT ar.action_id, ar.tenant_id, ar.capability, ar.status, ar.trace_id, b.owner_id
                FROM action_requests ar
                LEFT JOIN businesses b ON b.id = ar.tenant_id
                WHERE ar.action_id = %s
                LIMIT 1
                """,
                (action_id,),
            )
            action_row = cursor.fetchone()
            if not action_row:
                return {"success": False, "error": "action not found", "http_code": 404}

            owner_id = self._row_value(action_row, 5, "owner_id")
            if str(owner_id) != str(user_data.get("user_id")) and not user_data.get("is_superadmin"):
                return {"success": False, "error": "forbidden", "http_code": 403}

            timeline_query = """
                SELECT occurred_at, source, event_type, status, details_json
                FROM (
                    SELECT
                        ar.created_at AS occurred_at,
                        'action_request'::text AS source,
                        'created'::text AS event_type,
                        ar.status::text AS status,
                        jsonb_build_object(
                            'capability', ar.capability,
                            'idempotency_key', ar.idempotency_key,
                            'trace_id', ar.trace_id
                        ) AS details_json
                    FROM action_requests ar
                    WHERE ar.action_id = %s

                    UNION ALL

                    SELECT
                        tr.created_at AS occurred_at,
                        'action_transition'::text AS source,
                        'status_changed'::text AS event_type,
                        tr.to_status::text AS status,
                        jsonb_build_object(
                            'from_status', tr.from_status,
                            'to_status', tr.to_status,
                            'reason', tr.reason,
                            'meta', tr.meta_json
                        ) AS details_json
                    FROM action_transitions tr
                    WHERE tr.action_id = %s

                    UNION ALL

                    SELECT
                        aa.requested_at AS occurred_at,
                        'approval'::text AS source,
                        'approval_requested'::text AS event_type,
                        aa.status::text AS status,
                        jsonb_build_object(
                            'expires_at', aa.expires_at,
                            'callback_url', aa.callback_url
                        ) AS details_json
                    FROM action_approvals aa
                    WHERE aa.action_id = %s

                    UNION ALL

                    SELECT
                        aa.resolved_at AS occurred_at,
                        'approval'::text AS source,
                        'approval_resolved'::text AS event_type,
                        aa.status::text AS status,
                        jsonb_build_object(
                            'decision_reason', aa.decision_reason,
                            'decider_actor', aa.decider_actor_json
                        ) AS details_json
                    FROM action_approvals aa
                    WHERE aa.action_id = %s
                      AND aa.resolved_at IS NOT NULL

                    UNION ALL

                    SELECT
                        o.created_at AS occurred_at,
                        'callback_outbox'::text AS source,
                        'callback_enqueued'::text AS event_type,
                        o.status::text AS status,
                        jsonb_build_object(
                            'event_type', o.event_type,
                            'callback_url', o.callback_url,
                            'attempts', o.attempts,
                            'max_attempts', o.max_attempts,
                            'dedupe_key', o.dedupe_key
                        ) AS details_json
                    FROM action_callback_outbox o
                    WHERE o.action_id = %s

                    UNION ALL

                    SELECT
                        o.updated_at AS occurred_at,
                        'callback_outbox'::text AS source,
                        'callback_state'::text AS event_type,
                        o.status::text AS status,
                        jsonb_build_object(
                            'event_type', o.event_type,
                            'attempts', o.attempts,
                            'max_attempts', o.max_attempts,
                            'last_error', o.last_error,
                            'next_attempt_at', o.next_attempt_at
                        ) AS details_json
                    FROM action_callback_outbox o
                    WHERE o.action_id = %s
                      AND o.updated_at > o.created_at

                    UNION ALL

                    SELECT
                        ca.created_at AS occurred_at,
                        'callback_delivery'::text AS source,
                        'attempt'::text AS event_type,
                        CASE WHEN ca.success THEN 'sent' ELSE 'failed' END::text AS status,
                        jsonb_build_object(
                            'outbox_id', ca.outbox_id,
                            'event_type', ca.event_type,
                            'attempt_no', ca.attempt_no,
                            'http_status', ca.http_status,
                            'duration_ms', ca.duration_ms,
                            'error_text', ca.error_text,
                            'response_excerpt', ca.response_excerpt
                        ) AS details_json
                    FROM action_callback_attempts ca
                    WHERE ca.action_id = %s

                    UNION ALL

                    SELECT
                        bl.created_at AS occurred_at,
                        'billing_ledger'::text AS source,
                        bl.entry_type::text AS event_type,
                        NULL::text AS status,
                        jsonb_build_object(
                            'tokens_in', bl.tokens_in,
                            'tokens_out', bl.tokens_out,
                            'cost', bl.cost,
                            'tariff_id', bl.tariff_id,
                            'month_key', bl.month_key,
                            'meta', bl.meta_json
                        ) AS details_json
                    FROM billing_ledger bl
                    WHERE bl.action_id = %s
                ) t
                ORDER BY occurred_at DESC NULLS LAST, source ASC
                LIMIT %s
            """
            cursor.execute(
                timeline_query,
                (
                    action_id,
                    action_id,
                    action_id,
                    action_id,
                    action_id,
                    action_id,
                    action_id,
                    action_id,
                    limit,
                ),
            )
            rows = cursor.fetchall() or []
            rows = list(reversed(rows))

            events = []
            for row in rows:
                events.append(
                    {
                        "occurred_at": str(self._row_value(row, 0, "occurred_at") or ""),
                        "source": str(self._row_value(row, 1, "source") or ""),
                        "event_type": str(self._row_value(row, 2, "event_type") or ""),
                        "status": self._row_value(row, 3, "status"),
                        "details": self._row_value(row, 4, "details_json") or {},
                    }
                )

            db.conn.commit()
            return {
                "success": True,
                "action_id": self._row_value(action_row, 0, "action_id"),
                "tenant_id": self._row_value(action_row, 1, "tenant_id"),
                "capability": self._row_value(action_row, 2, "capability"),
                "status": self._row_value(action_row, 3, "status"),
                "trace_id": self._row_value(action_row, 4, "trace_id"),
                "events": events,
                "count": len(events),
                "limit": limit,
            }
        finally:
            db.close()

    def get_action_support_package(
        self,
        action_id: str,
        user_data: Dict[str, Any],
        *,
        limit: int = 200,
    ) -> Dict[str, Any]:
        action_result = self.get_action(action_id, user_data)
        if not action_result.get("success"):
            return action_result

        billing_result = self.get_action_billing(action_id, user_data)
        if not billing_result.get("success"):
            return billing_result

        timeline_result = self.get_action_timeline(action_id, user_data, limit=limit)
        if not timeline_result.get("success"):
            return timeline_result

        return {
            "success": True,
            "action_id": action_result.get("action_id"),
            "tenant_id": action_result.get("tenant_id"),
            "capability": action_result.get("capability"),
            "trace_id": action_result.get("trace_id"),
            "status": action_result.get("status"),
            "action": action_result,
            "billing": billing_result,
            "timeline": timeline_result,
        }

    def list_callback_outbox(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            where = ["o.tenant_id = %s"]
            params = [str(tenant_id)]
            if not is_superadmin:
                where.append("b.owner_id = %s")
                params.append(current_user)
            if status:
                where.append("o.status = %s")
                params.append(str(status))

            where_clause = "WHERE " + " AND ".join(where)
            limit = max(1, min(int(limit or 50), 200))
            offset = max(0, int(offset or 0))

            cursor.execute(
                f"""
                SELECT o.id, o.action_id, o.tenant_id, o.callback_url, o.event_type, o.status,
                       o.attempts, o.max_attempts, o.next_attempt_at, o.last_error, o.sent_at, o.created_at, o.updated_at
                FROM action_callback_outbox o
                LEFT JOIN businesses b ON b.id = o.tenant_id
                {where_clause}
                ORDER BY o.created_at DESC
                LIMIT %s OFFSET %s
                """,
                (*params, limit, offset),
            )
            rows = cursor.fetchall() or []
            items = []
            for row in rows:
                items.append(
                    {
                        "id": self._row_value(row, 0, "id"),
                        "action_id": self._row_value(row, 1, "action_id"),
                        "tenant_id": self._row_value(row, 2, "tenant_id"),
                        "callback_url": self._row_value(row, 3, "callback_url"),
                        "event_type": self._row_value(row, 4, "event_type"),
                        "status": self._row_value(row, 5, "status"),
                        "attempts": int(self._row_value(row, 6, "attempts", 0) or 0),
                        "max_attempts": int(self._row_value(row, 7, "max_attempts", 0) or 0),
                        "next_attempt_at": str(self._row_value(row, 8, "next_attempt_at") or ""),
                        "last_error": self._row_value(row, 9, "last_error"),
                        "sent_at": str(self._row_value(row, 10, "sent_at") or ""),
                        "created_at": str(self._row_value(row, 11, "created_at") or ""),
                        "updated_at": str(self._row_value(row, 12, "updated_at") or ""),
                    }
                )
            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "items": items,
                "count": len(items),
                "limit": limit,
                "offset": offset,
            }
        finally:
            db.close()

    def get_callback_metrics(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        window_minutes: int = 60,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            window_minutes = max(1, min(int(window_minutes or 60), 7 * 24 * 60))

            cursor.execute(
                """
                SELECT status, COUNT(*) AS cnt
                FROM action_callback_outbox
                WHERE tenant_id = %s
                  AND created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                GROUP BY status
                """,
                (str(tenant_id), window_minutes),
            )
            grouped = cursor.fetchall() or []
            counts = {str(self._row_value(r, 0, "status") or ""): int(self._row_value(r, 1, "cnt", 0) or 0) for r in grouped}

            cursor.execute(
                """
                SELECT COUNT(*) AS stuck_retry
                FROM action_callback_outbox
                WHERE tenant_id = %s
                  AND status = 'retry'
                  AND next_attempt_at < (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                """,
                (str(tenant_id), int(os.getenv("OPENCLAW_CALLBACK_RETRY_STUCK_MINUTES", "15"))),
            )
            stuck_row = cursor.fetchone()
            stuck_retry_count = int(self._row_value(stuck_row, 0, "stuck_retry", 0) or 0)

            sent = int(counts.get("sent", 0))
            retry = int(counts.get("retry", 0))
            dlq = int(counts.get("dlq", 0))
            pending = int(counts.get("pending", 0))
            sending = int(counts.get("sending", 0))
            total_recent = sent + retry + dlq + pending + sending
            delivery_success_rate = round((sent / total_recent) * 100, 2) if total_recent > 0 else 100.0

            dlq_threshold = int(os.getenv("OPENCLAW_CALLBACK_DLQ_ALERT_THRESHOLD", "1"))
            stuck_threshold = int(os.getenv("OPENCLAW_CALLBACK_STUCK_RETRY_ALERT_THRESHOLD", "1"))
            low_success_threshold = float(os.getenv("OPENCLAW_CALLBACK_SUCCESS_RATE_MIN", "90"))

            alerts = []
            if dlq >= dlq_threshold:
                alerts.append(
                    {
                        "code": "DLQ_THRESHOLD",
                        "severity": "high",
                        "message": f"DLQ count is {dlq} (threshold={dlq_threshold})",
                    }
                )
            if stuck_retry_count >= stuck_threshold:
                alerts.append(
                    {
                        "code": "STUCK_RETRY",
                        "severity": "medium",
                        "message": f"Stuck retries: {stuck_retry_count} (threshold={stuck_threshold})",
                    }
                )
            if delivery_success_rate < low_success_threshold:
                alerts.append(
                    {
                        "code": "LOW_SUCCESS_RATE",
                        "severity": "medium",
                        "message": f"Delivery success rate is {delivery_success_rate}% (min={low_success_threshold}%)",
                    }
                )

            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "window_minutes": window_minutes,
                "metrics": {
                    "sent": sent,
                    "retry": retry,
                    "dlq": dlq,
                    "pending": pending,
                    "sending": sending,
                    "stuck_retry": stuck_retry_count,
                    "total_recent": total_recent,
                    "delivery_success_rate": delivery_success_rate,
                },
                "alerts": alerts,
            }
        finally:
            db.close()

    def replay_callback_outbox(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        include_retry: bool = False,
        limit: int = 100,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            limit = max(1, min(int(limit or 100), 2000))
            if include_retry:
                cursor.execute(
                    """
                    WITH picked AS (
                        SELECT id
                        FROM action_callback_outbox
                        WHERE tenant_id = %s
                          AND status IN ('dlq', 'retry')
                        ORDER BY created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE action_callback_outbox o
                    SET status='pending',
                        attempts=0,
                        last_error=NULL,
                        next_attempt_at=CURRENT_TIMESTAMP,
                        locked_at=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    FROM picked
                    WHERE o.id = picked.id
                    RETURNING o.id, o.action_id, o.event_type
                    """,
                    (str(tenant_id), limit),
                )
            else:
                cursor.execute(
                    """
                    WITH picked AS (
                        SELECT id
                        FROM action_callback_outbox
                        WHERE tenant_id = %s
                          AND status = 'dlq'
                        ORDER BY created_at ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                    )
                    UPDATE action_callback_outbox o
                    SET status='pending',
                        attempts=0,
                        last_error=NULL,
                        next_attempt_at=CURRENT_TIMESTAMP,
                        locked_at=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    FROM picked
                    WHERE o.id = picked.id
                    RETURNING o.id, o.action_id, o.event_type
                    """,
                    (str(tenant_id), limit),
                )
            rows = cursor.fetchall() or []
            replayed = [
                {
                    "id": self._row_value(r, 0, "id"),
                    "action_id": self._row_value(r, 1, "action_id"),
                    "event_type": self._row_value(r, 2, "event_type"),
                }
                for r in rows
            ]
            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "statuses": (["dlq", "retry"] if include_retry else ["dlq"]),
                "replayed_count": len(replayed),
                "replayed": replayed,
            }
        finally:
            db.close()

    def cleanup_callback_outbox(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        older_than_minutes: int = 24 * 60,
        limit: int = 500,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            older_than_minutes = max(1, min(int(older_than_minutes or (24 * 60)), 180 * 24 * 60))
            limit = max(1, min(int(limit or 500), 5000))

            cursor.execute(
                """
                WITH picked AS (
                    SELECT id
                    FROM action_callback_outbox
                    WHERE tenant_id = %s
                      AND status = 'sent'
                      AND sent_at IS NOT NULL
                      AND sent_at < (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                    ORDER BY sent_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                DELETE FROM action_callback_outbox o
                USING picked
                WHERE o.id = picked.id
                RETURNING o.id, o.action_id, o.event_type
                """,
                (str(tenant_id), older_than_minutes, limit),
            )
            rows = cursor.fetchall() or []
            deleted = [
                {
                    "id": self._row_value(r, 0, "id"),
                    "action_id": self._row_value(r, 1, "action_id"),
                    "event_type": self._row_value(r, 2, "event_type"),
                }
                for r in rows
            ]
            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "deleted_count": len(deleted),
                "deleted": deleted,
                "older_than_minutes": older_than_minutes,
            }
        finally:
            db.close()

    def reconcile_billing(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        window_minutes: int = 24 * 60,
        limit: int = 200,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")

            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = str(self._row_value(owner_row, 0, "owner_id") or "")
            if owner_id != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            window_minutes = max(1, min(int(window_minutes or (24 * 60)), 30 * 24 * 60))
            limit = max(1, min(int(limit or 200), 1000))

            cursor.execute(
                """
                SELECT
                    ar.action_id,
                    ar.status,
                    ar.billing_json,
                    ar.created_at,
                    COALESCE(SUM(CASE WHEN bl.entry_type='reserve' THEN bl.tokens_out ELSE 0 END), 0) AS reserve_total,
                    COALESCE(SUM(CASE WHEN bl.entry_type='settle' THEN bl.tokens_out ELSE 0 END), 0) AS settle_total,
                    COALESCE(SUM(CASE WHEN bl.entry_type='release' THEN bl.tokens_out ELSE 0 END), 0) AS release_total,
                    COALESCE(SUM(CASE WHEN bl.entry_type='settle' THEN bl.cost ELSE 0 END), 0.0) AS settle_cost_total
                FROM action_requests ar
                LEFT JOIN billing_ledger bl ON bl.action_id = ar.action_id
                WHERE ar.tenant_id = %s
                  AND ar.created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                GROUP BY ar.action_id, ar.status, ar.billing_json, ar.created_at
                ORDER BY ar.created_at DESC
                LIMIT %s
                """,
                (str(tenant_id), window_minutes, limit),
            )
            rows = cursor.fetchall() or []

            items = []
            total_issue_count = 0
            actions_with_issues = 0
            settled_sum = 0
            reserve_sum = 0
            release_sum = 0
            expected_tokens_sum = 0
            expected_cost_sum = 0.0

            for row in rows:
                action_id = str(self._row_value(row, 0, "action_id") or "")
                status = str(self._row_value(row, 1, "status") or "")
                billing_json = self._as_dict(self._row_value(row, 2, "billing_json"))
                created_at = str(self._row_value(row, 3, "created_at") or "")
                reserve_total = int(self._row_value(row, 4, "reserve_total", 0) or 0)
                settle_total = int(self._row_value(row, 5, "settle_total", 0) or 0)
                release_total = int(self._row_value(row, 6, "release_total", 0) or 0)
                settle_cost_total = float(self._row_value(row, 7, "settle_cost_total", 0.0) or 0.0)

                expected_tokens = int(billing_json.get("total_tokens") or 0)
                expected_cost = float(billing_json.get("cost") or 0.0)
                issue_codes = []

                is_final = status in {"completed", "failed", "rejected", "expired"}
                if is_final and reserve_total != (settle_total + release_total):
                    issue_codes.append("reserve_balance_mismatch")
                # "missing_settle" is only actionable when reserved tokens were not fully released.
                if status == "completed" and reserve_total > release_total and settle_total == 0:
                    issue_codes.append("missing_settle")
                if expected_tokens > 0 and settle_total != expected_tokens:
                    issue_codes.append("settle_tokens_mismatch")
                if abs(expected_cost - settle_cost_total) > 0.000001:
                    issue_codes.append("settle_cost_mismatch")
                if reserve_total > 0 and settle_total > reserve_total:
                    issue_codes.append("settle_exceeds_reserve")

                if issue_codes:
                    actions_with_issues += 1
                    total_issue_count += len(issue_codes)

                items.append(
                    {
                        "action_id": action_id,
                        "status": status,
                        "created_at": created_at,
                        "ledger": {
                            "reserved_tokens": reserve_total,
                            "settled_tokens": settle_total,
                            "released_tokens": release_total,
                            "settled_cost": round(settle_cost_total, 6),
                        },
                        "expected": {
                            "total_tokens": expected_tokens,
                            "cost": round(expected_cost, 6),
                        },
                        "issues": issue_codes,
                    }
                )

                reserve_sum += reserve_total
                settled_sum += settle_total
                release_sum += release_total
                expected_tokens_sum += expected_tokens
                expected_cost_sum += expected_cost

            cursor.execute("SELECT to_regclass('tokenusage') AS reg")
            tokenusage_exists_row = cursor.fetchone()
            tokenusage_exists = bool(self._row_value(tokenusage_exists_row, 0, "reg"))
            tokenusage_total = 0
            if tokenusage_exists:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
                    FROM tokenusage
                    WHERE (business_id = %s OR (business_id IS NULL AND user_id = %s))
                      AND created_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                    """,
                    (str(tenant_id), owner_id, window_minutes),
                )
                tr = cursor.fetchone()
                tokenusage_total = int(self._row_value(tr, 0, "total_tokens", 0) or 0)

            aggregate_mismatch = max(tokenusage_total - settled_sum, 0)

            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "window_minutes": window_minutes,
                "limit": limit,
                "summary": {
                    "actions_checked": len(items),
                    "actions_with_issues": actions_with_issues,
                    "issue_count": total_issue_count,
                    "reserved_tokens_total": reserve_sum,
                    "settled_tokens_total": settled_sum,
                    "released_tokens_total": release_sum,
                    "expected_tokens_total": expected_tokens_sum,
                    "expected_cost_total": round(expected_cost_sum, 6),
                    "tokenusage_total": tokenusage_total,
                    "tokenusage_minus_settled": aggregate_mismatch,
                },
                "items": items,
                "count": len(items),
            }
        finally:
            db.close()

    def record_capability_health_snapshot(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        status: str,
        ready: bool,
        checks: Dict[str, Any],
        metrics: Dict[str, Any],
        alerts: Any,
        window_minutes: int = 60,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")
            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            snapshot_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO openclaw_capability_health_history
                    (id, tenant_id, status, ready, checks_json, metrics_json, alerts_json, window_minutes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    snapshot_id,
                    str(tenant_id),
                    str(status or "degraded"),
                    bool(ready),
                    json.dumps(checks or {}, ensure_ascii=False),
                    json.dumps(metrics or {}, ensure_ascii=False),
                    json.dumps(alerts if isinstance(alerts, list) else [], ensure_ascii=False),
                    max(1, min(int(window_minutes or 60), 7 * 24 * 60)),
                ),
            )
            db.conn.commit()
            return {"success": True, "snapshot_id": snapshot_id}
        finally:
            db.close()

    def get_capability_health_trend(
        self,
        user_data: Dict[str, Any],
        *,
        tenant_id: str,
        window_minutes: int = 24 * 60,
        limit: int = 200,
    ) -> Dict[str, Any]:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        try:
            self.ensure_tables(cursor)
            is_superadmin = bool(user_data.get("is_superadmin"))
            current_user = str(user_data.get("user_id") or "")
            cursor.execute(
                """
                SELECT owner_id
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (str(tenant_id),),
            )
            owner_row = cursor.fetchone()
            if not owner_row:
                return {"success": False, "error": "tenant_id not found", "http_code": 404}
            owner_id = self._row_value(owner_row, 0, "owner_id")
            if str(owner_id) != current_user and not is_superadmin:
                return {"success": False, "error": "forbidden", "http_code": 403}

            window_minutes = max(1, min(int(window_minutes or (24 * 60)), 30 * 24 * 60))
            limit = max(1, min(int(limit or 200), 1000))

            cursor.execute(
                """
                SELECT id, tenant_id, status, ready, checks_json, metrics_json, alerts_json, window_minutes, captured_at
                FROM openclaw_capability_health_history
                WHERE tenant_id = %s
                  AND captured_at >= (CURRENT_TIMESTAMP - (%s || ' minutes')::interval)
                ORDER BY captured_at DESC
                LIMIT %s
                """,
                (str(tenant_id), window_minutes, limit),
            )
            rows = cursor.fetchall() or []
            items = []
            for row in rows:
                alerts_raw = self._row_value(row, 6, "alerts_json")
                if isinstance(alerts_raw, list):
                    alerts_list = alerts_raw
                elif isinstance(alerts_raw, str):
                    try:
                        parsed_alerts = json.loads(alerts_raw)
                        alerts_list = parsed_alerts if isinstance(parsed_alerts, list) else []
                    except Exception:
                        alerts_list = []
                else:
                    alerts_list = []
                items.append(
                    {
                        "id": self._row_value(row, 0, "id"),
                        "tenant_id": self._row_value(row, 1, "tenant_id"),
                        "status": self._row_value(row, 2, "status"),
                        "ready": bool(self._row_value(row, 3, "ready", False)),
                        "checks": self._as_dict(self._row_value(row, 4, "checks_json")),
                        "metrics": self._as_dict(self._row_value(row, 5, "metrics_json")),
                        "alerts": alerts_list,
                        "window_minutes": int(self._row_value(row, 7, "window_minutes", 60) or 60),
                        "captured_at": str(self._row_value(row, 8, "captured_at") or ""),
                    }
                )

            db.conn.commit()
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "window_minutes": window_minutes,
                "limit": limit,
                "items": items,
                "count": len(items),
            }
        finally:
            db.close()
