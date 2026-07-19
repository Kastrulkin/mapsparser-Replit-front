from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator
from services.agent_blueprint_runner import AgentBlueprintRunner, parse_json_field
from services.agent_capability_handlers import capability_runtime_contract
from services.agent_run_queue import async_agent_runs_enabled, enqueue_agent_run


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
            "preview_mode": False,
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


def dispatch_scheduled_agent_blueprints(
    cursor: Any,
    business_id: str,
    *,
    now: datetime | None = None,
    trigger: str = "schedule.daily",
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    now_text = now.isoformat().replace("+00:00", "Z")
    trigger_event_id = str(uuid.uuid4())
    _ensure_trigger_event_table(cursor)
    event_payload = {
        "trigger": trigger,
        "scheduled_at": now_text,
        "source": "scheduler",
    }
    cursor.execute(
        """
        INSERT INTO agent_trigger_events (
            id, business_id, source, event_type, status, payload_json, reason_code
        )
        VALUES (%s, %s, 'scheduler', %s, 'received', %s::jsonb, NULL)
        """,
        (trigger_event_id, business_id, trigger, json.dumps(event_payload, ensure_ascii=False)),
    )
    blueprints = _load_candidate_blueprints(cursor, business_id)
    started_runs = []
    skipped = []
    for blueprint in blueprints:
        version = _resolve_active_version(cursor, blueprint)
        if not version:
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "active_version_missing"})
            continue
        if not _matches_schedule_trigger(blueprint, version, trigger):
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "trigger_mismatch"})
            continue
        beta_gate = _scheduled_version_beta_gate(version)
        if not beta_gate.get("ready"):
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "capability_not_beta_enabled", "capabilities": beta_gate.get("blocked")})
            continue
        if not async_agent_runs_enabled(str(blueprint.get("business_id") or "")):
            skipped.append({"blueprint_id": blueprint.get("id"), "reason": "async_runtime_not_enabled_for_business"})
            continue
        user_data = {
            "user_id": str(blueprint.get("created_by_user_id") or ""),
            "id": str(blueprint.get("created_by_user_id") or ""),
            "is_superadmin": False,
        }
        run_input = {
            "trigger": trigger,
            "scheduled_at": now_text,
            "preview_mode": False,
            "trigger_event_id": trigger_event_id,
            "source_event": {
                "id": trigger_event_id,
                "source": "scheduler",
                "event_type": trigger,
            },
        }
        defaults = _custom_process_defaults(blueprint, version)
        for key, value in defaults.items():
            if value and not run_input.get(key):
                run_input[key] = value
        result = enqueue_agent_run(
            cursor,
            blueprint=blueprint,
            version=version,
            input_payload=run_input,
            user_data=user_data,
            idempotency_key=f"scheduler:{blueprint.get('id')}:{now.date().isoformat()}:{trigger}",
        )
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
            skipped.append(
                {
                    "blueprint_id": blueprint.get("id"),
                    "reason": result.get("code") or result.get("error") or "run_start_failed",
                    "preflight": result.get("preflight") if isinstance(result.get("preflight"), dict) else {},
                }
            )
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
        "legacy_reply_should_continue": False,
    }


def dispatch_due_scheduled_agent_blueprints(
    cursor: Any,
    *,
    now: datetime | None = None,
    business_limit: int = 50,
    trigger: str = "schedule.daily",
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    _ensure_trigger_event_table(cursor)
    blueprints = _load_scheduled_blueprints(cursor, blueprint_limit=business_limit)
    dispatched = []
    skipped = []
    for blueprint in blueprints:
        version = _resolve_active_version(cursor, blueprint)
        if not version or not _matches_schedule_trigger(blueprint, version, trigger):
            continue
        beta_gate = _scheduled_version_beta_gate(version)
        if not beta_gate.get("ready"):
            skipped.append({"blueprint_id": str(blueprint.get("id") or ""), "business_id": str(blueprint.get("business_id") or ""), "reason": "capability_not_beta_enabled", "capabilities": beta_gate.get("blocked")})
            continue
        schedule_context = _schedule_context(blueprint, version, now)
        blueprint_id = str(blueprint.get("id") or "")
        business_id = str(blueprint.get("business_id") or "")
        if not async_agent_runs_enabled(business_id):
            skipped.append({"blueprint_id": blueprint_id, "business_id": business_id, "reason": "async_runtime_not_enabled_for_business"})
            continue
        if not schedule_context.get("ready"):
            skipped.append({"blueprint_id": blueprint_id, "business_id": business_id, "reason": schedule_context.get("reason")})
            continue
        if not schedule_context.get("due"):
            continue
        if _scheduled_blueprint_event_already_recorded(cursor, blueprint_id, trigger, schedule_context):
            skipped.append({"blueprint_id": blueprint_id, "business_id": business_id, "reason": "already_recorded_for_schedule"})
            continue
        result = _dispatch_scheduled_blueprint(cursor, blueprint, version, now, trigger, schedule_context)
        if not result.get("success"):
            skipped.append(
                {
                    "blueprint_id": blueprint_id,
                    "business_id": business_id,
                    "reason": result.get("reason") or "run_start_failed",
                    "trigger_event_id": result.get("trigger_event_id"),
                }
            )
            continue
        dispatched.append(
            {
                "blueprint_id": blueprint_id,
                "business_id": business_id,
                "trigger_event_id": result.get("trigger_event_id"),
                "run_id": result.get("run_id"),
                "run_status": result.get("run_status"),
            }
        )
    return {
        "success": True,
        "trigger": trigger,
        "checked_businesses": len({str(item.get("business_id") or "") for item in blueprints}),
        "checked_blueprints": len(blueprints),
        "dispatched_count": len(dispatched),
        "skipped_count": len(skipped),
        "dispatched": dispatched,
        "skipped": skipped,
    }


def _load_scheduled_blueprints(cursor: Any, *, blueprint_limit: int) -> list[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprints
        WHERE status = 'active'
          AND COALESCE(metadata_json->>'execution_mode', '') = 'scheduled'
        ORDER BY updated_at DESC, created_at DESC
        LIMIT %s
        """,
        (max(1, min(int(blueprint_limit), 500)),),
    )
    return [dict(row) for row in (cursor.fetchall() or [])]


def _schedule_context(
    blueprint: Dict[str, Any],
    version: Dict[str, Any],
    now: datetime,
) -> Dict[str, Any]:
    metadata = _metadata(blueprint)
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    schedule = custom_process.get("schedule") if isinstance(custom_process.get("schedule"), dict) else {}
    if not schedule:
        version_output = parse_json_field(version.get("output_schema_json"), {})
        schedule = version_output.get("schedule") if isinstance(version_output, dict) and isinstance(version_output.get("schedule"), dict) else {}
    schedule_time = str(schedule.get("time") or "").strip()
    timezone_name = str(schedule.get("timezone") or "").strip()
    if not schedule_time:
        return {"ready": False, "reason": "schedule_time_required"}
    if not timezone_name or timezone_name == "business_timezone":
        return {"ready": False, "reason": "schedule_timezone_required"}
    try:
        local_now = now.astimezone(ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return {"ready": False, "reason": "schedule_timezone_invalid"}
    try:
        hour_text, minute_text = schedule_time.split(":", 1)
        due_minute = int(hour_text) * 60 + int(minute_text)
    except Exception:
        return {"ready": False, "reason": "schedule_time_invalid"}
    current_minute = local_now.hour * 60 + local_now.minute
    return {
        "ready": True,
        "due": current_minute >= due_minute,
        "schedule_time": schedule_time,
        "timezone": timezone_name,
        "schedule_date": local_now.date().isoformat(),
        "local_now": local_now.isoformat(),
    }


def _scheduled_blueprint_event_already_recorded(
    cursor: Any,
    blueprint_id: str,
    trigger: str,
    schedule_context: Dict[str, Any],
) -> bool:
    cursor.execute(
        """
        SELECT id
        FROM agent_trigger_events
        WHERE blueprint_id = %s
          AND source = 'scheduler'
          AND event_type = %s
          AND payload_json->>'schedule_date' = %s
          AND payload_json->>'schedule_time' = %s
        LIMIT 1
        """,
        (
            blueprint_id,
            trigger,
            str(schedule_context.get("schedule_date") or ""),
            str(schedule_context.get("schedule_time") or ""),
        ),
    )
    return bool(cursor.fetchone())


def _dispatch_scheduled_blueprint(
    cursor: Any,
    blueprint: Dict[str, Any],
    version: Dict[str, Any],
    now: datetime,
    trigger: str,
    schedule_context: Dict[str, Any],
) -> Dict[str, Any]:
    trigger_event_id = str(uuid.uuid4())
    blueprint_id = str(blueprint.get("id") or "")
    business_id = str(blueprint.get("business_id") or "")
    event_payload = {
        "trigger": trigger,
        "scheduled_at": now.isoformat().replace("+00:00", "Z"),
        "source": "scheduler",
        "schedule_date": str(schedule_context.get("schedule_date") or ""),
        "schedule_time": str(schedule_context.get("schedule_time") or ""),
        "timezone": str(schedule_context.get("timezone") or ""),
    }
    cursor.execute(
        """
        INSERT INTO agent_trigger_events (
            id, business_id, blueprint_id, source, event_type, status, payload_json, reason_code
        )
        VALUES (%s, %s, %s, 'scheduler', %s, 'received', %s::jsonb, NULL)
        """,
        (trigger_event_id, business_id, blueprint_id, trigger, json.dumps(event_payload, ensure_ascii=False)),
    )
    user_data = {
        "user_id": str(blueprint.get("created_by_user_id") or ""),
        "id": str(blueprint.get("created_by_user_id") or ""),
        "is_superadmin": False,
    }
    run_input = {
        **event_payload,
        "preview_mode": False,
        "trigger_event_id": trigger_event_id,
        "source_event": {"id": trigger_event_id, "source": "scheduler", "event_type": trigger},
    }
    for key, value in _custom_process_defaults(blueprint, version).items():
        if value and not run_input.get(key):
            run_input[key] = value
    result = enqueue_agent_run(
        cursor,
        blueprint=blueprint,
        version=version,
        input_payload=run_input,
        user_data=user_data,
        idempotency_key=f"scheduler:{blueprint_id}:{schedule_context.get('schedule_date')}:{schedule_context.get('schedule_time')}",
    )
    run = result.get("run") if isinstance(result.get("run"), dict) else {}
    run_id = str(run.get("id") or "")
    cursor.execute(
        """
        UPDATE agent_trigger_events
        SET run_id = %s,
            status = %s,
            reason_code = %s,
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            run_id or None,
            "run_started" if result.get("success") else "failed",
            None if result.get("success") else str(result.get("code") or result.get("error") or "run_start_failed"),
            trigger_event_id,
        ),
    )
    return {
        "success": bool(result.get("success")),
        "trigger_event_id": trigger_event_id,
        "run_id": run_id,
        "run_status": str(run.get("status") or ""),
        "reason": None if result.get("success") else str(result.get("code") or result.get("error") or "run_start_failed"),
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


def _load_due_scheduled_businesses(
    cursor: Any,
    *,
    now: datetime,
    business_limit: int,
    trigger: str,
) -> list[Dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, business_id, metadata_json
        FROM agent_blueprints
        WHERE status = 'active'
          AND COALESCE(metadata_json->>'execution_mode', '') = 'scheduled'
        ORDER BY updated_at DESC, created_at DESC
        LIMIT %s
        """,
        (max(1, min(int(business_limit), 500)),),
    )
    business_ids: list[str] = []
    for row in cursor.fetchall() or []:
        blueprint = dict(row)
        metadata = _metadata(blueprint)
        custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
        if str(custom_process.get("trigger") or trigger) != trigger:
            continue
        schedule = custom_process.get("schedule") if isinstance(custom_process.get("schedule"), dict) else {}
        if not _schedule_is_due(schedule, now):
            continue
        business_id = str(blueprint.get("business_id") or "").strip()
        if business_id and business_id not in business_ids:
            business_ids.append(business_id)
    return [{"business_id": business_id} for business_id in business_ids]


def _schedule_is_due(schedule: Dict[str, Any], now: datetime) -> bool:
    if not isinstance(schedule, dict) or not schedule:
        return False
    schedule_time = str(schedule.get("time") or "19:00").strip()
    if not schedule_time:
        return False
    try:
        hour_text, minute_text = schedule_time.split(":", 1)
        due_hour = max(0, min(int(hour_text), 23))
        due_minute = max(0, min(int(minute_text), 59))
    except Exception:
        due_hour = 19
        due_minute = 0
    due_value = due_hour * 60 + due_minute
    now_value = now.hour * 60 + now.minute
    return now_value >= due_value


def _scheduled_event_already_recorded(cursor: Any, business_id: str, trigger: str, now: datetime) -> bool:
    run_date = now.date().isoformat()
    try:
        cursor.execute(
            """
            SELECT id
            FROM agent_trigger_events
            WHERE business_id = %s
              AND source = 'scheduler'
              AND event_type = %s
              AND created_at::date = %s::date
            LIMIT 1
            """,
            (business_id, trigger, run_date),
        )
        return bool(cursor.fetchone())
    except Exception:
        return False


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
    return {}


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


def _matches_schedule_trigger(blueprint: Dict[str, Any], version: Dict[str, Any], trigger: str) -> bool:
    metadata = _metadata(blueprint)
    if str(metadata.get("execution_mode") or "").strip().lower() != "scheduled":
        return False
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    if str(custom_process.get("trigger") or "") == trigger:
        return True
    schedule = custom_process.get("schedule") if isinstance(custom_process.get("schedule"), dict) else {}
    if schedule and trigger == "schedule.daily":
        return True
    payload = parse_json_field(version.get("output_schema_json"), {})
    if isinstance(payload, dict) and str(payload.get("trigger") or "") == trigger:
        return True
    return False


def _scheduled_version_beta_gate(version: Dict[str, Any]) -> Dict[str, Any]:
    capabilities = parse_json_field(version.get("capability_allowlist_json"), [])
    if not isinstance(capabilities, list):
        capabilities = []
    contracts = [capability_runtime_contract(str(item or "")) for item in capabilities if str(item or "").strip()]
    blocked = [item for item in contracts if not item.get("beta_enabled")]
    return {"ready": not blocked, "blocked": blocked, "capabilities": contracts}


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
