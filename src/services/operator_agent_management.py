"""Operator lifecycle controls for existing agent blueprints and versions."""
from __future__ import annotations

import json
from typing import Any

from core.auth_helpers import verify_business_write_access
from services.agent_blueprint_workspace import build_version_payload_from_row
from services.agent_schedule_contract import ScheduleError, apply_schedule, describe_schedule
from services.agent_version_store import insert_version
from services.operator_conversations import _row


def _authorized_actor(cursor: Any, *, business_id: str, user_id: str, actor_context: dict | None) -> dict:
    context = actor_context or {}
    if context.get("session_kind") == "demo" or context.get("impersonating") or context.get("impersonated_by"):
        return {}
    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    actor = _row(cursor, cursor.fetchone())
    actor["user_id"] = user_id
    actor.update(session_kind=context.get("session_kind", "standard"), impersonating=False)
    if not actor.get("is_active") or not verify_business_write_access(cursor, business_id, actor)[0]:
        return {}
    return actor


def _resolve_blueprint(cursor: Any, *, business_id: str, arguments: dict) -> tuple[dict, str]:
    blueprint_id = str(arguments.get("blueprint_id") or "").strip()
    name = str(arguments.get("name") or arguments.get("blueprint_name") or "").strip()
    if not blueprint_id and not name:
        return {}, "automation_reference_required"
    if blueprint_id:
        cursor.execute("SELECT * FROM agent_blueprints WHERE id=%s AND business_id=%s FOR UPDATE", (blueprint_id, business_id))
        row = _row(cursor, cursor.fetchone())
        return (row, "") if row and row.get("status") != "archived" else ({}, "agent_not_found")
    cursor.execute(
        """SELECT * FROM agent_blueprints WHERE business_id=%s AND status<>'archived'
           AND lower(name)=lower(%s) ORDER BY updated_at DESC LIMIT 3""",
        (business_id, name),
    )
    rows = [_row(cursor, item) for item in (cursor.fetchall() or [])]
    if len(rows) == 1:
        return rows[0], ""
    if len(rows) > 1:
        return {}, "automation_reference_ambiguous"
    cursor.execute(
        """SELECT * FROM agent_blueprints WHERE business_id=%s AND status<>'archived'
           AND name ILIKE %s ORDER BY updated_at DESC LIMIT 3""",
        (business_id, f"%{name}%"),
    )
    rows = [_row(cursor, item) for item in (cursor.fetchall() or [])]
    if len(rows) == 1:
        return rows[0], ""
    return {}, "automation_reference_ambiguous" if rows else "agent_not_found"


def _versions(cursor: Any, blueprint: dict) -> tuple[dict, dict]:
    blueprint_id = str(blueprint.get("id") or "")
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE blueprint_id=%s ORDER BY version_number DESC LIMIT 1", (blueprint_id,))
    latest = _row(cursor, cursor.fetchone())
    metadata = blueprint.get("metadata_json") if isinstance(blueprint.get("metadata_json"), dict) else {}
    active_id = str(metadata.get("active_version_id") or "")
    active = {}
    if active_id:
        cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s", (active_id, blueprint_id))
        active = _row(cursor, cursor.fetchone())
    return latest, active


def _version_summary(version: dict) -> dict:
    if not version:
        return {}
    return {
        "id": version.get("id"), "version_number": version.get("version_number"),
        "goal": version.get("goal"), "execution_mode": version.get("execution_mode"),
        "trigger": version.get("trigger"), "schedule": version.get("schedule_json") or {},
        "compiled_state": version.get("compiled_state") or "legacy",
        "outreach_config": (version.get("runtime_config_json") or {}).get("outreach_config"),
    }


def _status_text(blueprint, latest, active, runs):
    lines = [f"{blueprint.get('name') or blueprint['id']}: {blueprint.get('status')}"]
    for label, version in (("Действующие условия", active), ("Последняя версия", latest)):
        if not version:
            continue
        lines.append(f"{label}: №{version.get('version_number') or version.get('id')}")
        schedule = version.get("schedule_json") or {}
        if schedule:
            lines.append("Расписание: " + describe_schedule(version.get("trigger"), schedule))
        config = (version.get("runtime_config_json") or {}).get("outreach_config") or {}
        if config:
            lines.append(f"Цель: {config.get('target_count')} новых компаний; страна: {config.get('agency_country')}; направление: {config.get('sold_destination')}; режим: {config.get('mode')}")
            lines.append(f"Бюджет поиска: {config.get('search_budget_cents')} центов; запросов: {config.get('max_search_calls')}")
    if runs:
        lines.append("Последние запуски: " + "; ".join(f"{run.get('status')}: {run.get('error_text') or run.get('id')}" for run in runs))
    return "\n".join(lines)


def configure(cursor, *, business_id, user_id, arguments, actor_context=None):
    actor = _authorized_actor(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context)
    if not actor:
        return {"status": "blocked", "blocked_reasons": ["access_denied"]}
    operation = str(arguments.get("operation") or "")
    if operation == "list":
        cursor.execute("SELECT id,name,description,category,status,updated_at FROM agent_blueprints WHERE business_id=%s AND status<>'archived' ORDER BY updated_at DESC LIMIT 50", (business_id,))
        items = [_row(cursor, item) for item in (cursor.fetchall() or [])]
        return {"status": "completed", "automations": items, "count": len(items), "chat_response": ("Автоматизации:\n" + "\n".join(f"{item.get('name') or item['id']} — {item.get('status')}" for item in items)) if items else "Автоматизаций пока нет. Опишите работу и расписание, чтобы подготовить первую.", "external_writes_performed": False}
    if operation == "create":
        from services.agent_blueprint_creation import prepare_creation
        return prepare_creation(cursor, business_id=business_id, user_id=user_id,
                               actor_context=actor_context or {}, payload=arguments)
    blueprint, error = _resolve_blueprint(cursor, business_id=business_id, arguments=arguments)
    if error:
        if error == "automation_reference_ambiguous":
            return {"status": "clarification_required", "chat_response": "Нашёл несколько автоматизаций с таким названием. Уточните название или выберите её в списке ИИ-сотрудников."}
        return {"status": "blocked", "blocked_reasons": [error]}
    blueprint_id = str(blueprint.get("id") or "")
    latest, active = _versions(cursor, blueprint)
    if operation == "status":
        cursor.execute("SELECT id,status,created_at,completed_at,error_text FROM agent_runs WHERE blueprint_id=%s ORDER BY created_at DESC LIMIT 5", (blueprint_id,))
        runs = [_row(cursor, item) for item in (cursor.fetchall() or [])]
        return {"status": "completed", "blueprint_id": blueprint_id, "name": blueprint.get("name"), "state": blueprint.get("status"),
                "candidate": _version_summary(latest), "active_version": _version_summary(active), "runs": runs,
                "chat_response": _status_text(blueprint, latest, active, runs), "external_writes_performed": False}
    if operation == "preview":
        from api.agent_blueprints_api import _build_activation_gate_summary, _blueprint_metadata
        version = latest
        gate = _build_activation_gate_summary(cursor, blueprint=blueprint, active_version=version, metadata=_blueprint_metadata(blueprint)) if version else {"can_activate": False, "summary": "Сначала создайте сценарий."}
        return {"status": "completed", "blueprint_id": blueprint_id, "name": blueprint.get("name"), "candidate": _version_summary(version),
                "activation_gate": gate, "chat_response": str(gate.get("summary") or "Предварительная проверка завершена."), "external_writes_performed": False}
    if operation in {"schedule", "conditions"}:
        if not latest:
            return {"status": "blocked", "blocked_reasons": ["agent_version_required"]}
        if str(latest.get("compiled_state") or "legacy") != "legacy":
            return {"status": "blocked", "blocked_reasons": ["compiled_schedule_edit_requires_rebuild"],
                    "chat_response": "Расписание этого compiled-сценария нельзя менять отдельно: сначала пересоберите и проверьте сценарий в карточке ИИ-сотрудника."}
        expected = arguments.get("expected_version_id")
        if not expected or latest["id"] != expected:
            return {"status": "clarification_required", "chat_response": "Версия условий изменилась. Сначала покажите текущие условия и повторите изменение.", "candidate_version_id": latest["id"]}
        from services.business_input_settings import resolve
        try:
            payload = build_version_payload_from_row(latest)
            if operation == "schedule":
                payload = apply_schedule(payload, arguments.get("schedule") or {}, business_timezone=resolve(cursor, business_id).get("timezone"))
            else:
                from services.outreach_continuation import normalize_config
                previous = (payload.get("runtime_config") or {}).get("outreach_config")
                changes = arguments.get("outreach_config")
                if not isinstance(previous, dict) or not isinstance(changes, dict) or not changes:
                    raise ValueError("outreach_conditions_required")
                unknown = set(changes) - set(previous)
                if unknown:
                    raise ValueError("unknown_outreach_conditions")
                revised = normalize_config({**previous, **changes})
                payload["runtime_config"] = {**payload["runtime_config"], "outreach_config": revised}
        except (ScheduleError, ValueError, TypeError) as exc:
            return {"status": "blocked", "blocked_reasons": [str(getattr(exc, "code", "invalid_schedule"))]}
        candidate = insert_version(cursor, blueprint_id, payload, actor)
        return {"status": "completed", "blueprint_id": blueprint_id, "candidate_version_id": candidate["id"], "schedule": payload.get("schedule") or {},
                "outreach_config": (payload.get("runtime_config") or {}).get("outreach_config"),
                "active_version_unchanged": True, "chat_response": "Сохранил условия как новую версию для проверки. Текущая версия продолжает действовать до согласования."}
    return {"status": "blocked", "blocked_reasons": ["unsupported_operation"]}


def prepare_lifecycle(cursor, *, business_id: str, user_id: str, arguments: dict, actor_context: dict | None = None) -> dict:
    actor = _authorized_actor(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context)
    if not actor:
        return {"status": "blocked", "blocked_reasons": ["access_denied"]}
    operation = str(arguments.get("operation") or "")
    if operation not in {"activate", "pause", "resume", "stop"}:
        return {"status": "blocked", "blocked_reasons": ["unsupported_operation"]}
    blueprint, error = _resolve_blueprint(cursor, business_id=business_id, arguments=arguments)
    if error:
        return {"status": "clarification_required" if error == "automation_reference_ambiguous" else "blocked",
                "blocked_reasons": [error], "chat_response": "Уточните, какую автоматизацию нужно изменить." if error == "automation_reference_ambiguous" else None}
    latest, active = _versions(cursor, blueprint)
    expected_status = str(blueprint.get("status") or "")
    target_version = str(arguments.get("version_id") or (latest.get("id") if operation == "activate" else active.get("id")) or "")
    if operation == "activate":
        if not target_version or target_version != str(latest.get("id") or ""):
            return {"status": "clarification_required", "chat_response": "Версия сценария изменилась. Сначала откройте актуальный preview."}
        from api.agent_blueprints_api import _build_activation_gate_summary, _blueprint_metadata
        gate = _build_activation_gate_summary(cursor, blueprint=blueprint, active_version=latest, metadata=_blueprint_metadata(blueprint))
        if not gate.get("can_activate"):
            return {"status": "blocked", "blocked_reasons": ["activation_gate_blocked"], "activation_gate": gate,
                    "chat_response": str(gate.get("summary") or "Сначала проверьте сценарий и устраните замечания.")}
    elif operation == "pause" and expected_status != "active":
        return {"status": "blocked", "blocked_reasons": ["automation_not_active"]}
    elif operation == "resume" and expected_status != "paused":
        return {"status": "blocked", "blocked_reasons": ["automation_not_paused"]}
    if operation == "stop" and expected_status not in {"active", "paused", "draft"}:
        return {"status": "blocked", "blocked_reasons": ["automation_not_stoppable"]}
    if operation == "resume" and not active:
        return {"status": "blocked", "blocked_reasons": ["active_version_required"]}
    label = {"activate": "Включить автоматизацию", "pause": "Поставить автоматизацию на паузу", "resume": "Возобновить автоматизацию", "stop": "Остановить текущую работу и отключить следующие запуски"}[operation]
    summary = f"{label}: {blueprint.get('name') or 'ИИ-сотрудник'}"
    return {"status": "approval_required", "chat_response": summary + ". Подтвердите это действие.",
            "approval": {"status": "pending", "capability": "agents.lifecycle", "summary": summary,
                         "envelope": {"business_id": business_id, "blueprint_id": str(blueprint["id"]), "operation": operation,
                                      "expected_status": expected_status, "version_id": target_version}},
            "external_writes_performed": False}


def execute_lifecycle(cursor, *, business_id: str, user_id: str, envelope: dict, actor_context: dict | None = None) -> dict:
    actor = _authorized_actor(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context)
    if not actor or str(envelope.get("business_id") or "") != business_id:
        return {"status": "blocked", "blocked_reasons": ["access_denied"]}
    blueprint_id = str(envelope.get("blueprint_id") or "")
    operation = str(envelope.get("operation") or "")
    if operation not in {"activate", "pause", "resume", "stop"}:
        return {"status": "blocked", "blocked_reasons": ["unsupported_operation"]}
    # Serialize lifecycle transitions with run-step admission and provider dispatch fences.
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"agent-pause-fence:{blueprint_id}",))
    cursor.execute("SELECT * FROM agent_blueprints WHERE id=%s AND business_id=%s FOR UPDATE", (blueprint_id, business_id))
    blueprint = _row(cursor, cursor.fetchone())
    if not blueprint or str(blueprint.get("status") or "") != str(envelope.get("expected_status") or ""):
        return {"status": "blocked", "blocked_reasons": ["automation_state_changed"]}
    from api.agent_blueprints_api import _build_activation_gate_summary, _blueprint_metadata, _remember_active_version
    metadata = _blueprint_metadata(blueprint)
    if operation == "activate":
        version_id = str(envelope.get("version_id") or "")
        cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id=%s AND blueprint_id=%s FOR UPDATE", (version_id, blueprint_id))
        version = _row(cursor, cursor.fetchone())
        cursor.execute("SELECT id FROM agent_blueprint_versions WHERE blueprint_id=%s ORDER BY version_number DESC LIMIT 1", (blueprint_id,))
        latest_id = str((_row(cursor, cursor.fetchone()).get("id") or ""))
        if not version or version_id != latest_id:
            return {"status": "blocked", "blocked_reasons": ["agent_version_changed"]}
        gate = _build_activation_gate_summary(cursor, blueprint=blueprint, active_version=version, metadata=metadata)
        if not gate.get("can_activate"):
            return {"status": "blocked", "blocked_reasons": ["activation_gate_blocked"], "activation_gate": gate}
        _remember_active_version(cursor, blueprint, version, actor, "activated", "Operator confirmation")
        return {"status": "completed", "blueprint_id": blueprint_id, "state": "active", "active_version_id": version_id,
                "chat_response": "Автоматизация включена.", "external_writes_performed": False}
    if operation == "stop":
        if str(envelope.get("version_id") or "") != str(metadata.get("active_version_id") or ""):
            return {"status": "blocked", "blocked_reasons": ["active_version_changed"]}
        result = _stop_runs(cursor, blueprint_id=blueprint_id, business_id=business_id, user_id=user_id)
        if result.get("status") != "completed":
            return result
        cursor.execute("UPDATE agent_blueprints SET status='paused',updated_at=NOW() WHERE id=%s AND business_id=%s", (blueprint_id, business_id))
        events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
        cursor.execute("SELECT clock_timestamp() AS stopped_at")
        metadata["outreach_stopped_at"] = cursor.fetchone()["stopped_at"].isoformat()
        events.append({"action": "stopped", "created_by_user_id": user_id, "cancelled_runs": result["cancelled_runs"]})
        metadata["version_events"] = events[-50:]
        from api.agent_blueprints_api import _save_blueprint_metadata
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        return {**result, "blueprint_id": blueprint_id, "state": "paused", "chat_response": "Текущая работа остановлена; следующие запуски отключены. Результаты сохранены. Возобновление создаст новую работу по действующим условиям.", "external_writes_performed": False}
    if operation == "pause":
        cursor.execute("UPDATE agent_blueprints SET status='paused', updated_at=NOW() WHERE id=%s AND business_id=%s AND status='active'", (blueprint_id, business_id))
        if not cursor.rowcount:
            return {"status": "blocked", "blocked_reasons": ["automation_state_changed"]}
        events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
        events.append({"action": "paused", "created_by_user_id": user_id})
        metadata["version_events"] = events[-50:]
        from api.agent_blueprints_api import _save_blueprint_metadata
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        return {"status": "completed", "blueprint_id": blueprint_id, "state": "paused", "chat_response": "Автоматизация поставлена на паузу.", "external_writes_performed": False}
    active_id = str(metadata.get("active_version_id") or "")
    if not active_id or not str(envelope.get("version_id") or "") == active_id:
        return {"status": "blocked", "blocked_reasons": ["active_version_changed"]}
    cursor.execute("UPDATE agent_blueprints SET status='active', updated_at=NOW() WHERE id=%s AND business_id=%s AND status='paused'", (blueprint_id, business_id))
    if not cursor.rowcount:
        return {"status": "blocked", "blocked_reasons": ["automation_state_changed"]}
    events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
    events.append({"action": "resumed", "active_version_id": active_id, "created_by_user_id": user_id})
    metadata["version_events"] = events[-50:]
    from api.agent_blueprints_api import _save_blueprint_metadata
    _save_blueprint_metadata(cursor, blueprint_id, metadata)
    return {"status": "completed", "blueprint_id": blueprint_id, "state": "active", "active_version_id": active_id,
            "chat_response": "Автоматизация возобновлена.", "external_writes_performed": False}


def _stop_runs(cursor, *, blueprint_id, business_id, user_id):
    """Caller holds the same lifecycle fence used by native provider dispatch."""
    from services.outreach_ai_authorization import SENDER_ACCOUNT_ID
    cursor.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS acquired",
                   (f"ai-outreach:{SENDER_ACCOUNT_ID}:automation:{blueprint_id}",))
    if not (cursor.fetchone() or {}).get("acquired"):
        return {"status":"blocked","blocked_reasons":["send_in_progress_retry"],
                "chat_response":"Завершается отправка. Повторите остановку после сверки её результата."}
    # Unknown provider work must be reconciled, never relabelled as cancelled.
    cursor.execute("""SELECT id FROM agent_runs r WHERE blueprint_id=%s AND business_id=%s
        AND (status='running' OR (status='waiting_provider' AND NOT EXISTS (
            SELECT 1 FROM operator_async_jobs j JOIN agent_run_steps s
              ON s.run_id=r.id AND s.status='waiting_provider'
                AND s.output_json->>'job_id'=j.id::text
                AND j.result_json->>'agent_step_id'=s.id::text
            WHERE j.kind='outreach_continue' AND j.status IN ('queued','running','waiting_for_review')
              AND j.business_id=r.business_id AND j.result_json->>'agent_run_id'=r.id::text))) LIMIT 1""",
        (blueprint_id,business_id))
    if cursor.fetchone():
        return {"status":"blocked","blocked_reasons":["running_operation_needs_reconciliation"],
                "chat_response":"Текущая операция ещё выполняется. Поставьте автоматизацию на паузу; остановку завершите после сверки её результата."}
    cursor.execute("""SELECT j.* FROM operator_async_jobs j JOIN agent_runs r
        ON r.id::text=j.result_json->>'agent_run_id' AND r.business_id=j.business_id
        JOIN agent_run_steps s ON s.run_id=r.id AND s.status='waiting_provider'
          AND s.output_json->>'job_id'=j.id::text AND j.result_json->>'agent_step_id'=s.id::text
        WHERE r.blueprint_id=%s AND r.business_id=%s AND r.status='waiting_provider' AND j.kind='outreach_continue'
          AND j.status IN ('queued','running','waiting_for_review') ORDER BY j.id FOR UPDATE OF j""",
        (blueprint_id,business_id))
    jobs = [dict(row) for row in cursor.fetchall()]
    from services.outreach_continuation import control_task, config_hash
    for job in jobs:
        control_task(cursor, task_id=str(job['id']), business_id=business_id, user_id=user_id,
                     action='stop', revision=config_hash(job['payload_json']))
    cursor.execute("""UPDATE agent_approvals a SET status='superseded',decided_by_user_id=%s,
        decision_reason='Automation stopped',decided_at=NOW() FROM agent_runs r
        WHERE a.run_id=r.id AND r.blueprint_id=%s AND r.business_id=%s AND a.status='pending'""",
        (user_id,blueprint_id,business_id))
    cursor.execute("""UPDATE agent_runs SET status='superseded',error_text='Automation stopped',
        completed_at=COALESCE(completed_at,NOW()),lease_token=NULL,updated_at=NOW()
        WHERE blueprint_id=%s AND business_id=%s AND status IN ('queued','retry_wait','waiting_approval') RETURNING *""",
        (blueprint_id,business_id))
    stopped = [dict(row) for row in cursor.fetchall()]
    from services.agent_run_billing import finalize_agent_run_credits
    for run in stopped:
        finalize_agent_run_credits(cursor,run=run)
    return {"status":"completed","cancelled_runs":len(stopped)+len(jobs)}
