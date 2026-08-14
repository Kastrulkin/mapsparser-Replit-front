#!/usr/bin/env python3
"""Run the bounded Compiled AI template pilot through LocalOS HTTP contracts.

The command is dry-run by default. Applying requires an explicit confirmation.
It never approves an action, submits feedback, or bypasses integration preflight.
Stable idempotency keys make interrupted runs safe to resume.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from database_manager import DatabaseManager
from services.agent_template_catalog import build_agent_from_template, build_agent_template_catalog
from services.agent_template_pilot_plan import build_agent_template_pilot_plan


APPLY_CONFIRMATION = "RUN_COMPILED_AI_TEMPLATE_PILOT"
TERMINAL_STATUSES = {"completed", "failed", "rejected", "superseded", "waiting_approval"}
EXTERNAL_TRUE_KEYS = {
    "external_dispatch_performed",
    "external_write_performed",
    "provider_write_performed",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute the bounded Compiled AI pilot matrix")
    parser.add_argument("--business", action="append", default=[], metavar="KEY|UUID|NAME")
    parser.add_argument("--phase", choices=("preview", "production"), required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--poll-timeout", type=int, default=240)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.apply and args.confirm != APPLY_CONFIRMATION:
        parser.error(f"--apply requires --confirm {APPLY_CONFIRMATION}")

    businesses = [_parse_business(value) for value in args.business]
    templates = [
        item for item in build_agent_template_catalog()
        if item.get("certification_status") == "beta"
    ]
    _assert_safe_templates(templates)
    plan = build_agent_template_pilot_plan([item["key"] for item in templates], businesses)
    phase_field = "preview_runs" if args.phase == "preview" else "production_runs"
    planned = sum(int(item[phase_field]) for item in plan["templates"])
    summary = {
        "schema": "localos_compiled_ai_pilot_execution_v1",
        "dry_run": not args.apply,
        "phase": args.phase,
        "planned_runs": planned,
        "external_actions_allowed": False,
        "items": [],
    }
    if not args.apply:
        summary["status"] = "ready"
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    db = DatabaseManager()
    try:
        token = _latest_superadmin_session(db)
        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        for template_plan in plan["templates"]:
            template_key = str(template_plan["template_key"])
            for allocation in template_plan["allocations"]:
                run_count = int(allocation[phase_field])
                item = {
                    "template_key": template_key,
                    "business_key": allocation["business_key"],
                    "business_id": allocation["business_id"],
                    "planned_runs": run_count,
                    "completed_runs": 0,
                    "failed_runs": 0,
                    "blocked_runs": 0,
                    "run_ids": [],
                }
                summary["items"].append(item)
                blueprint_id, version_id, version_number = _ensure_blueprint(
                    session,
                    db,
                    args.base_url,
                    template_key,
                    str(allocation["business_id"]),
                )
                item["blueprint_id"] = blueprint_id
                item["blueprint_version_id"] = version_id
                request_text = (
                    f"Внутренний сертификационный пилот Compiled AI: {template_key}; "
                    "не публиковать и не отправлять результат вовне."
                )
                run_input = {"request": request_text}
                if args.phase == "preview":
                    run_input["preview_mode"] = True
                preflight = _post(
                    session,
                    f"{args.base_url}/api/agent-blueprints/{blueprint_id}/preflight",
                    {"blueprint_version_id": version_id, "input": run_input},
                )
                if not bool(preflight.get("can_start")):
                    item["status"] = "blocked_preflight"
                    item["blocked_runs"] = run_count
                    item["preflight"] = _safe_preflight_summary(preflight)
                    continue
                for index in range(1, run_count + 1):
                    idempotency_key = (
                        f"compiled-ai-pilot-v1:{args.phase}:{template_key}:"
                        f"{allocation['business_key']}:{index}"
                    )
                    if template_key == "google_sheets_business_result" and version_number > 1:
                        idempotency_key += f":version-{version_number}"
                    if args.phase == "preview" and template_key == "tomorrow_bookings_check":
                        idempotency_key += ":runtime-v2"
                    started = _post(
                        session,
                        f"{args.base_url}/api/agent-blueprints/{blueprint_id}/runs",
                        {
                            "blueprint_version_id": version_id,
                            "input": run_input,
                            "idempotency_key": idempotency_key,
                        },
                        allowed_statuses={200, 201, 202},
                    )
                    run_id = _run_id(started)
                    final_run = _poll_run(
                        session,
                        args.base_url,
                        run_id,
                        timeout=max(30, min(args.poll_timeout, 900)),
                    )
                    _assert_no_external_side_effect(final_run)
                    item["run_ids"].append(run_id)
                    if str(final_run.get("status") or "") == "completed":
                        item["completed_runs"] += 1
                    else:
                        item["failed_runs"] += 1
                        item.setdefault("failures", []).append(
                            {
                                "run_id": run_id,
                                "status": final_run.get("status"),
                                "error": str(final_run.get("error_text") or "")[:500],
                            }
                        )
                if args.phase == "preview" and item["completed_runs"] > 0:
                    activated = _post(
                        session,
                        f"{args.base_url}/api/agent-blueprints/{blueprint_id}/versions/{version_id}/activate",
                        {"reason": "Approved bounded Compiled AI internal pilot after successful preview"},
                    )
                    item["activated"] = bool(activated.get("success"))
                item["status"] = "completed" if item["completed_runs"] == run_count else "partial"
        summary["completed_runs"] = sum(item["completed_runs"] for item in summary["items"])
        summary["failed_runs"] = sum(item["failed_runs"] for item in summary["items"])
        summary["blocked_runs"] = sum(item["blocked_runs"] for item in summary["items"])
        if args.phase == "production":
            summary["schedule_pause"] = _pause_scheduled_pilot_blueprints(
                db,
                [str(item.get("blueprint_id") or "") for item in summary["items"]],
            )
        summary["status"] = (
            "completed"
            if summary["completed_runs"] == planned
            else "partial"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["failed_runs"] == 0 else 2
    finally:
        db.close()


def _parse_business(value: str) -> dict:
    parts = value.split("|", 2)
    if len(parts) != 3 or not all(part.strip() for part in parts):
        raise ValueError("business_must_use_key_uuid_name")
    return {
        "business_key": parts[0].strip(),
        "business_id": parts[1].strip(),
        "business_name": parts[2].strip(),
    }


def _assert_safe_templates(templates: list[dict]) -> None:
    if len(templates) != 6:
        raise ValueError("exactly_six_beta_templates_required")
    banned = ("send", "publish", "delete", "payment", "charge", "external_write")
    for template in templates:
        workflow = template.get("workflow_dsl") if isinstance(template.get("workflow_dsl"), dict) else {}
        limits = workflow.get("limits") if isinstance(workflow.get("limits"), dict) else {}
        if limits.get("autonomous_external_write_allowed") is not False:
            raise ValueError(f"unsafe_template_external_write:{template.get('key')}")
        capabilities = workflow.get("capability_allowlist") if isinstance(workflow.get("capability_allowlist"), list) else []
        if any(any(word in str(capability).lower() for word in banned) for capability in capabilities):
            raise ValueError(f"unsafe_template_capability:{template.get('key')}")


def _latest_superadmin_session(db: DatabaseManager) -> str:
    cursor = db.conn.cursor()
    cursor.execute(
        """
        SELECT session.token
        FROM usersessions session
        JOIN users account ON account.id = session.user_id
        WHERE session.expires_at > NOW()
          AND account.is_superadmin = TRUE
        ORDER BY session.created_at DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone() or {}
    token = str(row.get("token") or "")
    db.conn.rollback()
    if not token:
        raise RuntimeError("valid_superadmin_session_required")
    return token


def _ensure_blueprint(
    session: requests.Session,
    db: DatabaseManager,
    base_url: str,
    template_key: str,
    business_id: str,
) -> tuple[str, str, int]:
    payload = _post(
        session,
        f"{base_url}/api/agent-templates/{template_key}/use",
        {"business_id": business_id},
        allowed_statuses={200, 201},
    )
    blueprint = payload.get("blueprint") if isinstance(payload.get("blueprint"), dict) else {}
    blueprint_id = str(blueprint.get("id") or "")
    if not blueprint_id:
        raise RuntimeError(f"blueprint_id_missing:{template_key}:{business_id}")
    cursor = db.conn.cursor()
    cursor.execute(
        """
        SELECT id, version_number, steps_json, trigger, schedule_json
        FROM agent_blueprint_versions
        WHERE blueprint_id = %s
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (blueprint_id,),
    )
    row = cursor.fetchone() or {}
    version_id = str(row.get("id") or "")
    version_number = int(row.get("version_number") or 0)
    schedule = row.get("schedule_json") if isinstance(row.get("schedule_json"), dict) else {}
    needs_schedule_resolution = (
        str(row.get("trigger") or "").startswith("schedule.")
        and str(schedule.get("timezone") or "") in {"", "business_timezone"}
    )
    resolved_schedule = {}
    if needs_schedule_resolution:
        cursor.execute(
            """
            SELECT schedule_json
            FROM agent_blueprint_versions
            WHERE blueprint_id = %s
              AND COALESCE(schedule_json->>'timezone', '') NOT IN ('', 'business_timezone')
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (blueprint_id,),
        )
        schedule_row = cursor.fetchone() or {}
        resolved_schedule = (
            schedule_row.get("schedule_json")
            if isinstance(schedule_row.get("schedule_json"), dict)
            else {}
        )
    db.conn.rollback()
    if not version_id:
        raise RuntimeError(f"blueprint_version_missing:{blueprint_id}")
    steps = row.get("steps_json") if isinstance(row.get("steps_json"), list) else []
    if template_key == "google_sheets_business_result" and (
        not _uses_native_sheets_read(steps) or needs_schedule_resolution
    ):
        bundle = build_agent_from_template(template_key) or {}
        draft = bundle.get("draft") if isinstance(bundle.get("draft"), dict) else {}
        version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
        if resolved_schedule:
            version_payload["schedule"] = resolved_schedule
        created = _post(
            session,
            f"{base_url}/api/agent-blueprints/{blueprint_id}/versions",
            version_payload,
            allowed_statuses={201},
        )
        candidate = created.get("version") if isinstance(created.get("version"), dict) else {}
        version_id = str(candidate.get("id") or "")
        version_number = int(candidate.get("version_number") or 0)
        if not version_id or version_number < 2:
            raise RuntimeError(f"native_sheets_candidate_missing:{blueprint_id}")
    return blueprint_id, version_id, version_number


def _uses_native_sheets_read(steps: list[dict]) -> bool:
    for step in steps:
        if str(step.get("capability") or "") != "google_sheets.read_rows":
            continue
        return (
            str(step.get("provider") or "") == "native_localos"
            and not str(step.get("provider_action_ref") or "").strip()
        )
    return False


def _pause_scheduled_pilot_blueprints(db: DatabaseManager, blueprint_ids: list[str]) -> dict:
    selected = sorted({blueprint_id for blueprint_id in blueprint_ids if blueprint_id})
    if not selected:
        return {"paused_count": 0, "blueprint_ids": []}
    cursor = db.conn.cursor()
    cursor.execute(
        """
        UPDATE agent_blueprints blueprint
        SET status = 'paused',
            metadata_json = COALESCE(blueprint.metadata_json, '{}'::jsonb) || jsonb_build_object(
                'pilot_schedule_state', 'paused_after_bounded_pilot',
                'pilot_schedule_paused_at', NOW()
            ),
            updated_at = NOW()
        FROM agent_blueprint_versions version
        WHERE blueprint.id = ANY(%s)
          AND blueprint.status = 'active'
          AND version.id = blueprint.metadata_json->>'active_version_id'
          AND version.trigger LIKE 'schedule.%%'
        RETURNING blueprint.id
        """,
        (selected,),
    )
    paused = sorted(str(row.get("id") or "") for row in (cursor.fetchall() or []) if row.get("id"))
    db.conn.commit()
    return {"paused_count": len(paused), "blueprint_ids": paused}


def _post(
    session: requests.Session,
    url: str,
    payload: dict,
    *,
    allowed_statuses: set[int] | None = None,
) -> dict:
    response = session.post(url, json=payload, timeout=60)
    allowed = allowed_statuses or {200}
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:500]}
    if response.status_code not in allowed:
        raise RuntimeError(
            f"http_error:{response.status_code}:{url}:{json.dumps(body, ensure_ascii=False)[:1000]}"
        )
    return body if isinstance(body, dict) else {}


def _run_id(payload: dict) -> str:
    run = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    run_id = str(run.get("id") or payload.get("run_id") or "")
    if not run_id:
        raise RuntimeError(f"run_id_missing:{json.dumps(payload, ensure_ascii=False)[:500]}")
    return run_id


def _poll_run(
    session: requests.Session,
    base_url: str,
    run_id: str,
    *,
    timeout: int,
) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = session.get(f"{base_url}/api/agent-runs/{run_id}", timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"poll_http_error:{response.status_code}:{run_id}")
        body = response.json()
        run = body.get("run") if isinstance(body.get("run"), dict) else {}
        if str(run.get("status") or "") in TERMINAL_STATUSES:
            return run
        time.sleep(0.5)
    raise RuntimeError(f"run_poll_timeout:{run_id}")


def _assert_no_external_side_effect(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in EXTERNAL_TRUE_KEYS and item is True:
                raise RuntimeError(f"external_side_effect_detected:{key}")
            _assert_no_external_side_effect(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_external_side_effect(item)


def _safe_preflight_summary(payload: dict) -> dict:
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), dict) else {}
    return {
        "ready": bool(preflight.get("ready")),
        "missing_required": preflight.get("missing_required") or [],
        "next_binding_key": payload.get("next_binding_key"),
        "preview_run_gate": payload.get("preview_run_gate") or {},
    }


if __name__ == "__main__":
    raise SystemExit(main())
