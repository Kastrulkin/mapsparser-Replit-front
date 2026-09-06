"""Single application boundary for durable agent-run admission.

Routes may do presentation-level validation, but they must hand the final
blueprint, pinned version and the complete session-derived ``AuthContext`` to
this service before a run is reserved.  That keeps generic and compiled runs
on one idempotency, credit-reservation and transaction path.
"""
from __future__ import annotations

from typing import Any

from core.auth_context import AuthContext
from core.auth_helpers import verify_business_access
from core.unit_of_work import UnitOfWork
from services.agent_run_queue import enqueue_agent_run


class AgentRunAdmissionService:
    """Admit a run only for the session scope that owns its business."""

    def __init__(self, cursor: Any) -> None:
        self.cursor = cursor

    @classmethod
    def admit_atomically(
        cls,
        *,
        auth: AuthContext,
        blueprint: dict[str, Any],
        version: dict[str, Any],
        input_payload: dict[str, Any],
        idempotency_key: str,
        input_snapshot: dict[str, Any] | None = None,
        require_execution_mode_confirmation: bool = False,
        database_factory: Any = None,
    ) -> dict[str, Any]:
        """Commit a successful reservation and run row as one transaction.

        This is the entry point for transports that do not already have a
        transaction.  The cursor-level ``admit`` remains available to an API
        command that has already loaded and authorized the pinned resources in
        the same transaction.
        """
        factory = database_factory if database_factory is not None else None
        unit = UnitOfWork() if factory is None else UnitOfWork(database_factory=factory)
        with unit:
            result = cls(unit.cursor).admit(
                auth=auth,
                blueprint=blueprint,
                version=version,
                input_payload=input_payload,
                idempotency_key=idempotency_key,
                input_snapshot=input_snapshot,
                require_execution_mode_confirmation=require_execution_mode_confirmation,
            )
            if result.get("success"):
                unit.commit()
            else:
                unit.rollback()
            return result

    def admit(
        self,
        *,
        auth: AuthContext,
        blueprint: dict[str, Any],
        version: dict[str, Any],
        input_payload: dict[str, Any],
        idempotency_key: str,
        input_snapshot: dict[str, Any] | None = None,
        require_execution_mode_confirmation: bool = False,
    ) -> dict[str, Any]:
        blueprint_id = str(blueprint.get("id") or "")
        version_id = str(version.get("id") or "")
        # Re-read pinned resources inside the admission transaction. The UI
        # preflight is advisory; a concurrent pause/version replacement must
        # win before credits or a durable run are created.
        self.cursor.execute("SELECT * FROM agent_blueprints WHERE id=%s FOR SHARE", (blueprint_id,))
        current_blueprint = self.cursor.fetchone()
        self.cursor.execute(
            "SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s FOR SHARE",
            (version_id, blueprint_id),
        )
        current_version = self.cursor.fetchone()
        if not current_blueprint:
            return {"success": False, "code": "AGENT_RUN_VERSION_STALE", "error": "blueprint changed"}
        blueprint = dict(current_blueprint)
        # Authorization is always evaluated against the current blueprint
        # before an idempotency replay.  The executable-state checks belong in
        # ``enqueue_agent_run`` after its advisory lock and replay lookup:
        # a lost response must return its already admitted, pinned run even if
        # this blueprint was paused or activated on a newer version later.
        # A missing pinned version still reaches that lookup and is rejected
        # for a genuinely new intent by the queue boundary.
        version = dict(current_version) if current_version else {
            "id": version_id,
            "blueprint_id": blueprint_id,
        }
        business_id = str(blueprint.get("business_id") or "")
        if not business_id or not auth.permits_business(business_id):
            return {
                "success": False,
                "code": "AGENT_RUN_SCOPE_FORBIDDEN",
                "error": "agent run is outside the current session scope",
            }
        if not auth.user_id:
            return {
                "success": False,
                "code": "AGENT_RUN_ACTOR_REQUIRED",
                "error": "agent run requires an authenticated actor",
            }
        has_access, owner_id = verify_business_access(
            self.cursor,
            business_id,
            {
                "user_id": auth.user_id,
                "id": auth.user_id,
                "is_superadmin": auth.is_superadmin,
                "session_kind": auth.session_kind,
                "scope_business_id": auth.scope_business_id,
                "impersonating": auth.impersonating,
            },
        )
        if not owner_id:
            return {
                "success": False,
                "code": "AGENT_RUN_BUSINESS_NOT_FOUND",
                "error": "business is unavailable for agent admission",
            }
        if not has_access:
            return {
                "success": False,
                "code": "AGENT_RUN_SCOPE_FORBIDDEN",
                "error": "agent run is outside the current business membership",
            }
        if str(version.get("compiled_state") or "legacy").strip() != "legacy" and (
            auth.session_kind != "standard" or auth.impersonating
        ):
            return {
                "success": False,
                "code": "COMPILED_SESSION_NOT_ALLOWED",
                "error": "compiled runs require a direct standard session",
            }
        if str(version.get("compiled_state") or "legacy").strip() != "legacy":
            snapshot_id = str((input_snapshot or {}).get("snapshot_id") or "")
            if not snapshot_id:
                return {
                    "success": False,
                    "code": "COMPILED_INPUT_SNAPSHOT_REQUIRED",
                    "error": "compiled runs require an immutable input snapshot",
                }
            from services.compiled_input_snapshots import SnapshotUnavailable, resolve_snapshot
            try:
                input_snapshot = resolve_snapshot(
                    self.cursor,
                    snapshot_id,
                    business_id,
                    auth.user_id,
                    blueprint_id=blueprint_id,
                    lock=True,
                )
            except SnapshotUnavailable:
                return {
                    "success": False,
                    "code": "COMPILED_INPUT_SNAPSHOT_UNAVAILABLE",
                    "error": "compiled input snapshot is unavailable",
                }
            input_payload = input_snapshot["input"]
        return enqueue_agent_run(
            self.cursor,
            blueprint=blueprint,
            version=version,
            input_payload=input_payload,
            user_data={
                "user_id": auth.user_id,
                "id": auth.user_id,
                "is_superadmin": auth.is_superadmin,
                "session_kind": auth.session_kind,
                "scope_business_id": auth.scope_business_id,
                "impersonating": auth.impersonating,
            },
            idempotency_key=idempotency_key,
            input_snapshot=input_snapshot,
            require_execution_mode_confirmation=require_execution_mode_confirmation,
        )
