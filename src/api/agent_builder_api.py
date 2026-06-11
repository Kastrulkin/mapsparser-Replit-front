import json
import uuid

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.agent_blueprint_draft_builder import compile_agent_blueprint
from services.agent_blueprint_runner import normalize_steps, parse_json_field
from services.agent_builder_billing import charge_agent_creation_credits
from services.agent_builder_session import append_user_message, build_agent_builder_state, preview_to_setup
from services.agent_integration_preflight import build_agent_integration_preflight
from services.agent_provider_registry import integration_provider_catalog


agent_builder_bp = Blueprint("agent_builder_api", __name__)


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _require_auth():
    user_data = require_auth_from_request()
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    return user_data, None


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "")


def _require_business_access(cursor, business_id: str, user_data: dict):
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not owner_id:
        return False, _json_error("Business not found", 404, "BUSINESS_NOT_FOUND")
    if not has_access:
        return False, _json_error("Forbidden", 403, "FORBIDDEN")
    return True, None


def _normalize_session(row: dict) -> dict:
    result = dict(row)
    result["messages"] = parse_json_field(result.pop("messages_json", []), [])
    result["preview"] = parse_json_field(result.pop("preview_json", {}), {})
    result["missing_questions"] = parse_json_field(result.pop("missing_questions_json", []), [])
    return result


def _load_session(cursor, session_id: str):
    cursor.execute("SELECT * FROM agent_builder_sessions WHERE id = %s", (session_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_builder_connection_inventory(cursor, business_id: str) -> list[dict]:
    result = []
    cursor.execute(
        """
        SELECT id, source, display_name
        FROM externalbusinessaccounts
        WHERE business_id = %s
          AND is_active = TRUE
          AND source IN ('maton', 'google_sheets', 'telegram_app')
        ORDER BY updated_at DESC
        LIMIT 50
        """,
        (business_id,),
    )
    for row in cursor.fetchall() or []:
        item = dict(row)
        source = str(item.get("source") or "").strip()
        provider = source
        config = {}
        if source == "telegram_app":
            provider = "telegram"
            config = {"bot_mode": "business_bot"}
        elif source == "maton":
            provider = "maton"
            config = {"channel": "maton_bridge"}
        result.append(
            {
                "id": str(item.get("id") or ""),
                "provider": provider,
                "status": "active",
                "display_name": str(item.get("display_name") or source or provider),
                "config": config,
            }
        )
    cursor.execute(
        """
        SELECT telegram_bot_token
        FROM Businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    business = cursor.fetchone() or {}
    if str(dict(business).get("telegram_bot_token") or "").strip():
        result.append(
            {
                "id": "business_telegram_bot",
                "provider": "telegram",
                "status": "active",
                "display_name": "Бот бизнеса",
                "config": {"bot_mode": "business_bot"},
            }
        )
    return result


def _save_session_state(cursor, session_id: str, state: dict, status: str = "draft", blueprint_id: str = ""):
    cursor.execute(
        """
        UPDATE agent_builder_sessions
        SET status = %s,
            category = %s,
            messages_json = %s::jsonb,
            preview_json = %s::jsonb,
            missing_questions_json = %s::jsonb,
            blueprint_id = COALESCE(NULLIF(%s, ''), blueprint_id),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            str(state.get("category") or "custom"),
            json.dumps(state.get("messages") if isinstance(state.get("messages"), list) else [], ensure_ascii=False),
            json.dumps(state.get("preview") if isinstance(state.get("preview"), dict) else {}, ensure_ascii=False),
            json.dumps(state.get("missing_questions") if isinstance(state.get("missing_questions"), list) else [], ensure_ascii=False),
            blueprint_id,
            session_id,
        ),
    )


def _insert_version(cursor, blueprint_id: str, payload: dict, user_data: dict):
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM agent_blueprint_versions WHERE blueprint_id = %s",
        (blueprint_id,),
    )
    version_row = cursor.fetchone() or {}
    version_number = int(version_row.get("next_version") or 1)
    version_id = str(uuid.uuid4())
    steps = normalize_steps(payload.get("steps"))
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            persona_agent_id, capability_allowlist_json, approval_policy_json,
            output_schema_json, created_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        """,
        (
            version_id,
            blueprint_id,
            version_number,
            str(payload.get("goal") or "").strip(),
            json.dumps(payload.get("inputs_schema") if isinstance(payload.get("inputs_schema"), dict) else {}, ensure_ascii=False),
            json.dumps(steps, ensure_ascii=False),
            str(payload.get("persona_agent_id") or "").strip() or None,
            json.dumps(payload.get("capability_allowlist") if isinstance(payload.get("capability_allowlist"), list) else [], ensure_ascii=False),
            json.dumps(payload.get("approval_policy") if isinstance(payload.get("approval_policy"), dict) else {}, ensure_ascii=False),
            json.dumps(payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {}, ensure_ascii=False),
            _user_id(user_data),
        ),
    )
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    return dict(cursor.fetchone())


@agent_builder_bp.route("/api/agent-builder/sessions", methods=["POST"])
def create_agent_builder_session():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    message = str(payload.get("message") or payload.get("description") or "").strip()
    if not business_id or not message:
        return _json_error("business_id and message are required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        session_id = str(uuid.uuid4())
        state = build_agent_builder_state(
            [{"role": "user", "content": message}],
            str(payload.get("category") or ""),
            use_ai=bool(payload.get("use_ai_compiler")),
            business_id=business_id,
            user_id=_user_id(user_data),
            connected_integrations=_load_builder_connection_inventory(cursor, business_id),
        )
        cursor.execute(
            """
            INSERT INTO agent_builder_sessions (
                id, business_id, created_by_user_id, status, initial_prompt, category,
                messages_json, preview_json, missing_questions_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                session_id,
                business_id,
                _user_id(user_data),
                "draft",
                message,
                state["category"],
                json.dumps(state["messages"], ensure_ascii=False),
                json.dumps(state["preview"], ensure_ascii=False),
                json.dumps(state["missing_questions"], ensure_ascii=False),
            ),
        )
        db.conn.commit()
        session = _load_session(cursor, session_id)
        return jsonify({"success": True, "session": _normalize_session(session)}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_builder_bp.route("/api/agent-builder/sessions/<session_id>/message", methods=["POST"])
def add_agent_builder_message(session_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    if not message:
        return _json_error("message is required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        session = _load_session(cursor, session_id)
        if not session:
            return _json_error("Session not found", 404, "NOT_FOUND")
        allowed, access_error = _require_business_access(cursor, str(session.get("business_id") or ""), user_data)
        if not allowed:
            return access_error
        messages = append_user_message(parse_json_field(session.get("messages_json"), []), message)
        state = build_agent_builder_state(
            messages,
            str(payload.get("category") or session.get("category") or ""),
            use_ai=bool(payload.get("use_ai_compiler")),
            business_id=str(session.get("business_id") or ""),
            user_id=_user_id(user_data),
            connected_integrations=_load_builder_connection_inventory(cursor, str(session.get("business_id") or "")),
        )
        _save_session_state(cursor, session_id, state)
        db.conn.commit()
        refreshed = _load_session(cursor, session_id)
        return jsonify({"success": True, "session": _normalize_session(refreshed)})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_builder_bp.route("/api/agent-builder/sessions/<session_id>/create-blueprint", methods=["POST"])
def create_blueprint_from_agent_builder_session(session_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        session = _load_session(cursor, session_id)
        if not session:
            return _json_error("Session not found", 404, "NOT_FOUND")
        business_id = str(session.get("business_id") or "")
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        preview = parse_json_field(session.get("preview_json"), {})
        feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
        setup_flow = preview.get("setup_flow") if isinstance(preview.get("setup_flow"), dict) else {}
        if feasibility.get("status") == "forbidden":
            return jsonify(
                {
                    "success": False,
                    "error": "Такой агент не может быть создан в рамках политики LocalOS.",
                    "code": "AGENT_REQUEST_FORBIDDEN",
                    "feasibility": feasibility,
                }
            ), 400
        if setup_flow and not bool(setup_flow.get("can_create_draft")):
            return jsonify(
                {
                    "success": False,
                    "error": "Сначала завершите настройку агента.",
                    "code": "AGENT_SETUP_INCOMPLETE",
                    "setup_flow": setup_flow,
                    "feasibility": feasibility,
                }
            ), 400
        planner_context = preview.get("openclaw_planner_context") if isinstance(preview.get("openclaw_planner_context"), dict) else {}
        planner_loop = preview.get("openclaw_planner_loop") if isinstance(preview.get("openclaw_planner_loop"), dict) else {}
        description = str(preview.get("understood_task") or session.get("initial_prompt") or "").strip()
        category = str(preview.get("category") or session.get("category") or "").strip()
        billing = charge_agent_creation_credits(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            source_id=session_id,
            description=description,
        )
        if billing.get("status") == "blocked":
            db.conn.rollback()
            return jsonify(
                {
                    "success": False,
                    "error": "Недостаточно кредитов для создания агента.",
                    "code": "AGENT_CREATION_BILLING_BLOCKED",
                    "billing": billing,
                }
            ), 402
        draft = compile_agent_blueprint(
            description,
            category,
            use_ai=bool(payload.get("use_ai_compiler")),
            business_id=business_id,
            user_id=_user_id(user_data),
            planner_context=planner_context,
        )
        metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
        metadata["builder"] = "dialog_builder_v1"
        metadata["compiler"] = "agent_compiler_v1"
        metadata["builder_session_id"] = session_id
        metadata["agent_builder_preview"] = preview
        metadata["feasibility"] = feasibility
        metadata["openclaw_planner_context"] = planner_context
        metadata["openclaw_planner_loop"] = planner_loop
        metadata["required_connectors"] = preview.get("required_connectors") if isinstance(preview.get("required_connectors"), list) else []
        metadata["builder_setup_flow"] = setup_flow
        metadata["agent_setup"] = preview_to_setup(preview)
        metadata["setup_completed"] = True
        blueprint_id = str(uuid.uuid4())
        metadata["billing"] = billing
        cursor.execute(
            """
            INSERT INTO agent_blueprints (
                id, business_id, name, category, description, status, created_by_user_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                blueprint_id,
                business_id,
                str(draft.get("name") or preview.get("agent_name") or "Кастомный агент").strip(),
                str(draft.get("category") or category or "custom").strip().lower(),
                description or None,
                "draft",
                _user_id(user_data),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
        version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        _save_session_state(
            cursor,
            session_id,
            {
                "category": draft.get("category") or category or "custom",
                "messages": parse_json_field(session.get("messages_json"), []),
                "preview": preview,
                "missing_questions": parse_json_field(session.get("missing_questions_json"), []),
            },
            "blueprint_created",
            blueprint_id,
        )
        db.conn.commit()
        cursor.execute(
            """
            SELECT b.*,
                   v.id AS latest_version_id,
                   v.version_number AS latest_version_number,
                   v.goal AS latest_goal
            FROM agent_blueprints b
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            WHERE b.id = %s
            """,
            (blueprint_id,),
        )
        blueprint = dict(cursor.fetchone())
        refreshed = _load_session(cursor, session_id)
        connection_preflight = build_agent_integration_preflight(
            cursor,
            business_id=business_id,
            metadata=metadata,
            input_payload={},
        )
        post_create_handoff = _build_post_create_handoff(connection_preflight)
        return jsonify(
            {
                "success": True,
                "session": _normalize_session(refreshed),
                "blueprint": blueprint,
                "version": version,
                "billing": billing,
                "connection_preflight": connection_preflight,
                "post_create_handoff": post_create_handoff,
                "next_step": str(post_create_handoff.get("next_step") or "review_and_activate"),
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _build_post_create_handoff(connection_preflight: dict) -> dict:
    missing = connection_preflight.get("missing") if isinstance(connection_preflight.get("missing"), list) else []
    items = connection_preflight.get("items") if isinstance(connection_preflight.get("items"), list) else []
    ready = bool(connection_preflight.get("ready"))
    connection_plan = _build_handoff_connection_plan(items)
    if ready:
        return {
            "schema": "localos_agent_post_create_handoff_v1",
            "status": "ready_for_review",
            "next_step": "review_and_activate",
            "workspace_mode": "settings",
            "title": "Draft агента создан",
            "description": "Подключения готовы. Проверьте логику, сделайте preview run и активируйте агента.",
            "missing_bindings": [],
            "items": items,
            "connection_plan": connection_plan,
        }
    providers = []
    for item in missing:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider and provider not in providers:
            providers.append(provider)
    labels = [provider.replace("_", " ") for provider in providers[:3]]
    return {
        "schema": "localos_agent_post_create_handoff_v1",
        "status": "needs_connections",
        "next_step": "connect_required_integrations",
        "workspace_mode": "connections",
        "title": "Draft агента создан. Остались подключения",
        "description": f"Подключите {', '.join(labels) if labels else 'обязательные источники'}, затем запустите preflight и preview run.",
        "missing_bindings": missing,
        "items": items,
        "connection_plan": connection_plan,
    }


def _build_handoff_connection_plan(items: list) -> dict:
    catalog_by_provider = {
        str(item.get("provider") or "").strip(): item
        for item in integration_provider_catalog()
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    }
    plan_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        status = str(item.get("status") or "").strip()
        resolution = str(item.get("resolution") or "").strip()
        catalog_item = catalog_by_provider.get(provider, {})
        action = _handoff_connection_action(status, resolution, catalog_item)
        plan_items.append(
            {
                "key": str(item.get("key") or provider or ""),
                "provider": provider,
                "title": str(catalog_item.get("title") or provider.replace("_", " ") or "подключение"),
                "capability": str(item.get("capability") or ""),
                "trigger": str(item.get("trigger") or ""),
                "direction": str(item.get("direction") or ""),
                "binding_status": status,
                "action": action,
                "primary_label": _handoff_connection_label(action),
                "explanation": _handoff_connection_explanation(provider, action, item),
                "missing_config": item.get("missing_config") if isinstance(item.get("missing_config"), list) else [],
                "approval_required": bool(item.get("required", True)),
                "existing_integrations": [],
                "attached_integrations": [],
                "provider_paths": _handoff_provider_paths(catalog_item),
            }
        )
    missing_count = len([item for item in plan_items if item.get("action") not in {"ready", "native_ready"}])
    return {
        "schema": "localos_agent_connection_plan_v1",
        "status": "ready" if missing_count == 0 else "needs_action",
        "missing_count": missing_count,
        "items": plan_items,
    }


def _handoff_connection_action(status: str, resolution: str, catalog_item: dict) -> str:
    if status == "ready":
        return "native_ready" if resolution == "native_localos" else "ready"
    if str(catalog_item.get("status") or "").strip() == "planned":
        return "planned_provider"
    return "connect_required"


def _handoff_connection_label(action: str) -> str:
    labels = {
        "ready": "Готово",
        "native_ready": "Готово в LocalOS",
        "connect_required": "Подключите сервис",
        "planned_provider": "Будет доступно позже",
    }
    return labels.get(action, "Проверьте подключение")


def _handoff_connection_explanation(provider: str, action: str, item: dict) -> str:
    if action in {"ready", "native_ready"}:
        return "Подключение готово для preflight и активации."
    if action == "planned_provider":
        return "Этот provider есть в roadmap, но пока недоступен для активации агента."
    missing_config = item.get("missing_config") if isinstance(item.get("missing_config"), list) else []
    if missing_config:
        return f"Заполните: {', '.join([str(value) for value in missing_config])}."
    return f"Подключите {provider.replace('_', ' ')}, чтобы агент можно было активировать."


def _handoff_provider_paths(catalog_item: dict) -> list:
    providers = catalog_item.get("providers") if isinstance(catalog_item.get("providers"), list) else []
    result = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        result.append(
            {
                "provider": provider,
                "label": str(item.get("label") or provider),
                "status": str(item.get("status") or "unknown"),
            }
        )
    return result
