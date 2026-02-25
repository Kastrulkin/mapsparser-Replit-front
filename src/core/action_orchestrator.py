import json
import uuid
from datetime import timedelta
from typing import Any, Callable, Dict, Optional

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

    def _send_callback(self, callback_url: str, payload: Dict[str, Any]) -> None:
        if not callback_url:
            return
        try:
            requests.post(callback_url, json=payload, timeout=5)
        except Exception:
            # Callback ошибки не должны ломать основной workflow.
            return

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
                cursor.execute(
                    """
                    INSERT INTO action_approvals (action_id, status, requested_at, expires_at, callback_url)
                    VALUES (%s, 'pending_human', %s, %s, %s)
                    """,
                    (action_id, requested_at, expires_at, (approval or {}).get("callback_url")),
                )
                self._transition(cursor, action_id, "policy_checked", "pending_human", risk.get("reason", "approval required"))
                db.conn.commit()
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
            db2.conn.commit()
            db2.close()

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
            db.conn.commit()

            if decision != "approved":
                self._send_callback(
                    callback_url,
                    {
                        "action_id": action_id,
                        "status": decision,
                        "decision_reason": decision_reason,
                    },
                )
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
                    "status": exec_result.get("status"),
                    "success": exec_result.get("success"),
                    "trace_id": exec_result.get("trace_id"),
                    "error": exec_result.get("error"),
                },
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
