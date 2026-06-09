from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator
from services.agent_blueprint_runner import AgentBlueprintRunner, parse_json_field


def dispatch_telegram_message_to_agent_blueprints(cursor: Any, business_id: str, telegram_event: Dict[str, Any]) -> Dict[str, Any]:
    event_payload = _normalize_telegram_event(telegram_event)
    trigger_event_id = str(uuid.uuid4())
    _ensure_trigger_event_table(cursor)
    cursor.execute(
        """
        INSERT INTO agent_trigger_events (
            id, business_id, source, event_type, status, payload_json, reason_code
        )
        VALUES (%s, %s, 'telegram', 'telegram.message.received', 'received', %s::jsonb, NULL)
        """,
        (trigger_event_id, business_id, json.dumps(event_payload, ensure_ascii=False)),
    )
    blueprints = _load_candidate_blueprints(cursor, business_id)
    started_runs = []
    skipped = []
    for blueprint in blueprints:
        version = _resolve_active_version(cursor, blueprint)
        if not version:
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "active_version_missing"})
            continue
        if not _matches_telegram_trigger(blueprint, version):
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "trigger_mismatch"})
            continue
        user_data = {
            "user_id": str(blueprint.get("created_by_user_id") or ""),
            "id": str(blueprint.get("created_by_user_id") or ""),
            "is_superadmin": False,
        }
        run_input = {
            **event_payload,
            "trigger_event_id": trigger_event_id,
            "source_event": {
                "id": trigger_event_id,
                "source": "telegram",
                "event_type": "telegram.message.received",
            },
        }
        defaults = _custom_process_defaults(blueprint, version)
        for key, value in defaults.items():
            if value and not run_input.get(key):
                run_input[key] = value
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        result = runner.start_run(str(version.get("id") or ""), run_input, user_data)
        if result.get("success"):
            run = result.get("run") if isinstance(result.get("run"), dict) else {}
            run_id = str(run.get("id") or "")
            started_runs.append(
                {
                    "blueprint_id": str(blueprint.get("id") or ""),
                    "version_id": str(version.get("id") or ""),
                    "run_id": run_id,
                    "run_status": str(run.get("status") or ""),
                }
            )
            cursor.execute(
                """
                UPDATE agent_trigger_events
                SET blueprint_id = %s,
                    run_id = %s,
                    status = 'run_started',
                    updated_at = NOW()
                WHERE id = %s
                """,
                (str(blueprint.get("id") or ""), run_id or None, trigger_event_id),
            )
        else:
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": result.get("error") or "run_start_failed"})
    if not started_runs:
        cursor.execute(
            """
            UPDATE agent_trigger_events
            SET status = 'ignored',
                reason_code = %s,
                updated_at = NOW()
            WHERE id = %s
            """,
            ("NO_MATCHING_ACTIVE_BLUEPRINT", trigger_event_id),
        )
    return {
        "success": True,
        "trigger_event_id": trigger_event_id,
        "matched_count": len(started_runs),
        "started_runs": started_runs,
        "skipped": skipped,
        "legacy_reply_should_continue": len(started_runs) == 0,
    }


def _ensure_trigger_event_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_trigger_events (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            blueprint_id TEXT,
            run_id TEXT,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            reason_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_trigger_events_business_created ON agent_trigger_events(business_id, created_at DESC)"
    )


def _normalize_telegram_event(telegram_event: Dict[str, Any]) -> Dict[str, Any]:
    received_at = str(telegram_event.get("received_at") or "").strip()
    if not received_at:
        received_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "message_text": str(telegram_event.get("message_text") or "").strip(),
        "telegram_user_id": str(telegram_event.get("telegram_user_id") or "").strip(),
        "telegram_username": str(telegram_event.get("telegram_username") or "").strip(),
        "telegram_first_name": str(telegram_event.get("telegram_first_name") or "").strip(),
        "chat_id": str(telegram_event.get("chat_id") or "").strip(),
        "message_id": str(telegram_event.get("message_id") or "").strip(),
        "received_at": received_at,
        "telegram": {
            "message_text": str(telegram_event.get("message_text") or "").strip(),
            "telegram_user_id": str(telegram_event.get("telegram_user_id") or "").strip(),
            "telegram_username": str(telegram_event.get("telegram_username") or "").strip(),
            "chat_id": str(telegram_event.get("chat_id") or "").strip(),
            "received_at": received_at,
        },
    }


def _load_candidate_blueprints(cursor: Any, business_id: str) -> list[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprints
        WHERE business_id = %s
          AND status = 'active'
          AND category IN ('custom', 'tables')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 25
        """,
        (business_id,),
    )
    return [dict(row) for row in cursor.fetchall() or []]


def _resolve_active_version(cursor: Any, blueprint: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _metadata(blueprint)
    active_version_id = str(metadata.get("active_version_id") or "").strip()
    if active_version_id:
        cursor.execute(
            """
            SELECT *
            FROM agent_blueprint_versions
            WHERE id = %s
              AND blueprint_id = %s
            LIMIT 1
            """,
            (active_version_id, str(blueprint.get("id") or "")),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprint_versions
        WHERE blueprint_id = %s
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (str(blueprint.get("id") or ""),),
    )
    row = cursor.fetchone()
    return dict(row) if row else {}


def _matches_telegram_trigger(blueprint: Dict[str, Any], version: Dict[str, Any]) -> bool:
    metadata = _metadata(blueprint)
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    if str(custom_process.get("trigger") or "") == "telegram.message.received":
        return True
    steps = parse_json_field(version.get("steps_json"), [])
    if isinstance(steps, list):
        for step in steps:
            if not isinstance(step, dict):
                continue
            payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
            if str(payload.get("trigger") or "") == "telegram.message.received":
                return True
    return False


def _custom_process_defaults(blueprint: Dict[str, Any], version: Dict[str, Any]) -> Dict[str, Any]:
    metadata = _metadata(blueprint)
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    sheet = custom_process.get("google_sheets") if isinstance(custom_process.get("google_sheets"), dict) else {}
    payload = parse_json_field(version.get("output_schema_json"), {})
    defaults = {
        "integration_id": str(sheet.get("integration_id") or "").strip(),
        "spreadsheet_id": str(sheet.get("spreadsheet_id") or "").strip(),
        "sheet_name": str(sheet.get("sheet_name") or "").strip(),
    }
    if isinstance(payload, dict) and not defaults.get("sheet_name"):
        defaults["sheet_name"] = str(payload.get("sheet_name") or "").strip()
    return defaults


def _metadata(blueprint: Dict[str, Any]) -> Dict[str, Any]:
    metadata = parse_json_field(blueprint.get("metadata_json"), {})
    return metadata if isinstance(metadata, dict) else {}
