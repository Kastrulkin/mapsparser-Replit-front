from __future__ import annotations

import argparse
import json

from database_manager import DatabaseManager


def build_plan(cursor) -> dict:
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM agent_approvals a
        JOIN agent_runs r ON r.id = a.run_id
        JOIN agent_blueprints b ON b.id = r.blueprint_id
        WHERE a.status = 'pending' AND b.status = 'archived'
        """
    )
    archived_pending = int((cursor.fetchone() or {}).get("count") or 0)
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM agent_runs r
        JOIN agent_blueprints b ON b.id = r.blueprint_id
        WHERE b.status = 'archived'
          AND r.status IN ('queued', 'retry_wait', 'waiting_approval')
        """
    )
    archived_unfinished_runs = int((cursor.fetchone() or {}).get("count") or 0)
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM agent_blueprints
        WHERE COALESCE(metadata_json->>'execution_mode', '') NOT IN ('one_off', 'manual', 'scheduled')
        """
    )
    legacy_without_mode = int((cursor.fetchone() or {}).get("count") or 0)
    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM agent_blueprints
        WHERE status = 'active'
          AND COALESCE(metadata_json->>'execution_mode', '') NOT IN ('one_off', 'manual', 'scheduled')
        """
    )
    unsafe_active = int((cursor.fetchone() or {}).get("count") or 0)
    return {
        "archived_pending_approvals": archived_pending,
        "archived_unfinished_runs": archived_unfinished_runs,
        "legacy_blueprints_without_explicit_mode": legacy_without_mode,
        "active_legacy_blueprints_to_pause": unsafe_active,
    }


def apply_plan(cursor) -> dict:
    cursor.execute(
        """
        UPDATE agent_approvals a
        SET status = 'superseded',
            decision_reason = COALESCE(decision_reason, 'Archived agent approval closed during Agents beta migration'),
            decided_at = COALESCE(decided_at, NOW())
        FROM agent_runs r
        JOIN agent_blueprints b ON b.id = r.blueprint_id
        WHERE a.run_id = r.id
          AND a.status = 'pending'
          AND b.status = 'archived'
        """
    )
    approvals_updated = int(cursor.rowcount or 0)
    cursor.execute(
        """
        UPDATE agent_runs r
        SET status = 'superseded',
            completed_at = COALESCE(completed_at, NOW()),
            heartbeat_at = NULL,
            next_attempt_at = NULL,
            error_text = COALESCE(error_text, 'Archived agent run closed during Agents beta reconciliation'),
            updated_at = NOW()
        FROM agent_blueprints b
        WHERE r.blueprint_id = b.id
          AND b.status = 'archived'
          AND r.status IN ('queued', 'retry_wait', 'waiting_approval')
        """
    )
    runs_superseded = int(cursor.rowcount or 0)
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET metadata_json = jsonb_set(
                COALESCE(metadata_json, '{}'::jsonb),
                '{suggested_execution_mode}',
                to_jsonb(
                    CASE
                        WHEN COALESCE(metadata_json->'custom_process'->>'trigger', metadata_json->>'trigger', '') = 'schedule.daily'
                          OR jsonb_typeof(metadata_json->'custom_process'->'schedule') = 'object'
                        THEN 'scheduled'
                        ELSE 'manual'
                    END::text
                ),
                true
            ),
            updated_at = NOW()
        WHERE COALESCE(metadata_json->>'execution_mode', '') NOT IN ('one_off', 'manual', 'scheduled')
          AND COALESCE(metadata_json->>'suggested_execution_mode', '') = ''
        """
    )
    suggestions_updated = int(cursor.rowcount or 0)
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET status = 'draft',
            metadata_json = jsonb_set(
                COALESCE(metadata_json, '{}'::jsonb),
                '{activation_blocked_reason}',
                to_jsonb('execution_mode_confirmation_required'::text),
                true
            ),
            updated_at = NOW()
        WHERE status = 'active'
          AND COALESCE(metadata_json->>'execution_mode', '') NOT IN ('one_off', 'manual', 'scheduled')
        """
    )
    active_paused = int(cursor.rowcount or 0)
    return {
        "approvals_superseded": approvals_updated,
        "archived_runs_superseded": runs_superseded,
        "suggested_modes_written": suggestions_updated,
        "active_legacy_blueprints_paused": active_paused,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare legacy agent state for the controlled Agents beta.")
    parser.add_argument("--apply", action="store_true", help="Apply the idempotent updates. Default is dry-run.")
    args = parser.parse_args()
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        before = build_plan(cursor)
        result = {"mode": "dry_run", "before": before}
        if args.apply:
            result = {"mode": "apply", "before": before, "updated": apply_plan(cursor)}
            db.conn.commit()
            result["after"] = build_plan(cursor)
        else:
            db.conn.rollback()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
