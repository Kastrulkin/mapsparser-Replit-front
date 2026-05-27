#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[backend-lint] py_compile focused backend modules"
python3 -m py_compile \
  src/main.py \
  src/core/action_policy.py \
  src/api/admin_growth_api.py \
  src/api/business_types_api.py \
  src/api/reports_api.py \
  src/api/agent_builder_api.py \
  src/api/agent_blueprints_api.py \
  src/api/auth_user_api.py \
  src/api/superadmin_business_api.py \
  src/services/agent_blueprint_orchestrator.py \
  src/services/agent_builder_session.py \
  src/services/agent_blueprint_draft_builder.py \
  src/services/agent_blueprint_workspace.py \
  src/services/agent_source_ingestion.py \
  src/services/agent_datahub.py \
  src/services/agent_document_llm.py \
  src/services/agent_email_llm.py \
  src/services/agent_review_reply_analysis.py \
  src/services/agent_table_analysis.py \
  src/services/agent_blueprint_runner.py \
  src/services/outreach_send_capability.py \
  src/api/operator_api.py \
  src/services/operator_intent_ai_router.py \
  src/worker.py \
  src/services/operator_review_reply_bulk.py \
  src/services/operator_refresh_result.py \
  src/services/operator_refresh_retry.py \
  src/services/operator_refresh_telegram_followup.py \
  scripts/audit_approval_boundaries.py \
  scripts/smoke_operator_services_apply_api.py \
  scripts/smoke_operator_bulk_review_replies.py \
  scripts/smoke_agent_blueprint_document_api.py \
  scripts/smoke_agent_blueprint_email_api.py \
  scripts/smoke_agent_blueprint_reviews_api.py \
  scripts/smoke_agent_blueprint_outreach_api.py \
  scripts/smoke_agent_blueprint_table_api.py \
  scripts/smoke_agent_blueprint_generic_boundaries.py \
  scripts/smoke_agent_builder_dialog_api.py \
  src/api/growth_workflow_api.py \
  src/auth_encryption.py \
  tests/test_reports_api_routes.py \
  tests/test_agent_blueprint_layer.py \
  tests/test_auth_user_routes.py \
  tests/test_superadmin_business_routes.py \
  tests/test_growth_workflow_routes.py \
  tests/test_security_runtime_config.py \
  tests/test_operator_chat_fallback_api.py \
  tests/test_operator_intent_ai_router.py \
  tests/test_operator_review_reply_bulk.py

echo "[backend-lint] import and route ownership smoke"
PYTHONPATH=src python3 - <<'PY'
import main
import api.admin_growth_api
import api.business_types_api
import api.growth_workflow_api
import api.reports_api
import api.agent_builder_api
import api.agent_blueprints_api
import api.auth_user_api
import api.superadmin_business_api

rules = {
    "/api/download-report/<card_id>": "reports_api.download_report",
    "/api/view-report/<card_id>": "reports_api.view_report",
    "/api/reports/<card_id>/status": "reports_api.report_status",
    "/api/progress": "growth_workflow_api.get_business_progress",
    "/api/business/<business_id>/optimization-wizard": "growth_workflow_api.business_optimization_wizard",
    "/api/business/<business_id>/sprint": "growth_workflow_api.business_sprint",
    "/api/business-types": "business_types_api.get_business_types_public",
    "/api/agent-builder/sessions": "agent_builder_api.create_agent_builder_session",
    "/api/agent-builder/sessions/<session_id>/message": "agent_builder_api.add_agent_builder_message",
    "/api/agent-builder/sessions/<session_id>/create-blueprint": "agent_builder_api.create_blueprint_from_agent_builder_session",
    "/api/agent-blueprints/draft": "agent_blueprints_api.create_agent_blueprint_draft",
    "/api/agent-blueprints/<blueprint_id>": "agent_blueprints_api.get_agent_blueprint",
    "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff": "agent_blueprints_api.get_agent_blueprint_version_diff",
    "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate": "agent_blueprints_api.activate_agent_blueprint_version",
    "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback": "agent_blueprints_api.rollback_agent_blueprint_version",
    "/api/agent-blueprints/<blueprint_id>/setup": "agent_blueprints_api.setup_agent_blueprint",
        "/api/agent-blueprints/<blueprint_id>/sources": "agent_blueprints_api.add_agent_blueprint_source",
        "/api/agent-blueprints/<blueprint_id>/sources/catalog": "agent_blueprints_api.list_agent_blueprint_source_catalog",
        "/api/agent-blueprints/<blueprint_id>/sources/upload": "agent_blueprints_api.upload_agent_blueprint_source",
        "/api/agent-blueprints/<blueprint_id>/review": "agent_blueprints_api.review_agent_blueprint",
    "/api/agent-blueprints/<blueprint_id>/runs": "agent_blueprints_api.start_agent_blueprint_run",
    "/api/agent-runs/<run_id>": "agent_blueprints_api.get_agent_run",
    "/api/agent-runs/<run_id>/feedback": "agent_blueprints_api.create_agent_run_feedback",
    "/api/agent-runs/<run_id>/approvals/<approval_id>/approve": "agent_blueprints_api.approve_agent_run",
    "/api/auth/me": "auth_user_api.get_user_info",
    "/api/auth/logout": "auth_user_api.logout",
    "/api/users/profile": "auth_user_api.update_user_profile",
    "/api/superadmin/businesses/<business_id>/send-credentials": "superadmin_business_api.send_business_credentials",
    "/api/business/<string:business_id>/stages": "growth_api.get_business_stages",
    "/api/admin/business-types": "admin_growth_api.get_business_types",
    "/api/admin/business-types/<type_id>": "admin_growth_api.delete_business_type",
    "/api/admin/growth-stages/<type_id>": "admin_growth_api.get_growth_stages",
    "/api/admin/growth-stages": "admin_growth_api.create_growth_stage",
}

for rule, endpoint in rules.items():
    actual = next((item.endpoint for item in main.app.url_map.iter_rules() if item.rule == rule), None)
    if actual != endpoint:
        raise SystemExit(f"{rule}: expected {endpoint}, got {actual}")

print("OK: extracted routes are registered through their API blueprints")
PY

echo "[backend-lint] agent blueprint routes stay out of main.py"
python3 - <<'PY'
from pathlib import Path

main_text = Path("src/main.py").read_text(encoding="utf-8")
for marker in (
    '@app.route("/api/agent-blueprints',
    "@app.route('/api/agent-blueprints",
    '@app.route("/api/agent-runs',
    "@app.route('/api/agent-runs",
):
    if marker in main_text:
        raise SystemExit(f"agent blueprint route still declared in main.py: {marker}")

print("OK: agent blueprint routes are not declared in main.py")
PY

echo "[backend-lint] auth/user routes stay out of main.py"
python3 - <<'PY'
from pathlib import Path

main_text = Path("src/main.py").read_text(encoding="utf-8")
for marker in (
    "/api/auth/me",
    "/api/auth/logout",
    "/api/users/profile",
):
    if marker in main_text:
        raise SystemExit(f"auth/user route still owned by main.py: {marker}")

print("OK: auth/user routes are not declared in main.py")
PY

echo "[backend-lint] superadmin business routes stay out of main.py"
python3 - <<'PY'
from pathlib import Path

main_text = Path("src/main.py").read_text(encoding="utf-8")
for marker in (
    "@app.route('/api/superadmin/businesses'",
    '@app.route("/api/superadmin/businesses"',
    "@app.route('/api/superadmin/businesses/<business_id>'",
    '@app.route("/api/superadmin/businesses/<business_id>"',
    "@app.route('/api/superadmin/businesses/<business_id>/send-credentials'",
    '@app.route("/api/superadmin/businesses/<business_id>/send-credentials"',
):
    if marker in main_text:
        raise SystemExit(f"superadmin business route still owned by main.py: {marker}")

print("OK: superadmin business routes are not declared in main.py")
PY

echo "[backend-lint] superadmin business route ownership smoke"
PYTHONPATH=src python3 - <<'PY'
import main

expected = {
    ("/api/superadmin/businesses", frozenset({"GET"})): "superadmin_business_api.get_all_businesses",
    ("/api/superadmin/businesses", frozenset({"POST"})): "superadmin_business_api.create_business",
    ("/api/superadmin/businesses/<business_id>", frozenset({"PUT"})): "superadmin_business_api.update_business",
    ("/api/superadmin/businesses/<business_id>", frozenset({"DELETE"})): "superadmin_business_api.delete_business",
    ("/api/superadmin/businesses/<business_id>/send-credentials", frozenset({"POST"})): "superadmin_business_api.send_business_credentials",
}

actual = {}
for rule in main.app.url_map.iter_rules():
    methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
    actual[(rule.rule, methods)] = rule.endpoint

for key, endpoint in expected.items():
    if actual.get(key) != endpoint:
        raise SystemExit(f"{key}: expected {endpoint}, got {actual.get(key)}")

print("OK: superadmin business routes are registered through superadmin_business_api")
PY

echo "[backend-lint] agent blueprint capability guardrails"
python3 - <<'PY'
from pathlib import Path

api_text = Path("src/api/agent_blueprints_api.py").read_text(encoding="utf-8")
builder_api_text = Path("src/api/agent_builder_api.py").read_text(encoding="utf-8")
runner_text = Path("src/services/agent_blueprint_runner.py").read_text(encoding="utf-8")
orchestrator_text = Path("src/services/agent_blueprint_orchestrator.py").read_text(encoding="utf-8")
builder_session_text = Path("src/services/agent_builder_session.py").read_text(encoding="utf-8")
draft_builder_text = Path("src/services/agent_blueprint_draft_builder.py").read_text(encoding="utf-8")
workspace_text = Path("src/services/agent_blueprint_workspace.py").read_text(encoding="utf-8")
source_ingestion_text = Path("src/services/agent_source_ingestion.py").read_text(encoding="utf-8")
datahub_text = Path("src/services/agent_datahub.py").read_text(encoding="utf-8")
document_llm_text = Path("src/services/agent_document_llm.py").read_text(encoding="utf-8")
capability_text = Path("src/services/outreach_send_capability.py").read_text(encoding="utf-8")
ui_text = Path("frontend/src/pages/dashboard/AgentBlueprintsPage.tsx").read_text(encoding="utf-8")

required = {
    "src/api/agent_builder_api.py": [
        "/api/agent-builder/sessions",
        "/api/agent-builder/sessions/<session_id>/message",
        "/api/agent-builder/sessions/<session_id>/create-blueprint",
        "build_agent_builder_state",
        "preview_to_setup",
        "agent_builder_sessions",
        "blueprint_created",
    ],
    "src/services/agent_builder_session.py": [
        "QUESTION_LIBRARY",
        "build_agent_builder_state",
        "missing_questions",
        "external_dispatch_performed",
        "preview_to_setup",
    ],
    "src/api/agent_blueprints_api.py": [
        "VERSION_BLUEPRINT_MISMATCH",
        "build_agent_blueprint_orchestrator()",
        "build_agent_blueprint_draft",
        "/api/agent-blueprints/draft",
        "/api/agent-blueprints/<blueprint_id>/setup",
        "/api/agent-blueprints/<blueprint_id>/sources",
        "/api/agent-blueprints/<blueprint_id>/sources/catalog",
        "/api/agent-blueprints/<blueprint_id>/sources/upload",
        "build_agent_datahub_catalog",
        "build_agent_source_from_upload",
        "/api/agent-runs/<run_id>/feedback",
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff",
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate",
        "/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback",
        "_resolve_active_version",
        "_remember_active_version",
    ],
    "src/services/agent_blueprint_draft_builder.py": [
        "description_builder_v1",
        "preferred_category",
        "category = _normalized_category(preferred_category)",
        "capability_allowlist\": []",
        "external_delivery",
        "none_in_draft_builder",
    ],
    "src/services/agent_blueprint_workspace.py": [
        "normalize_agent_setup",
        "normalize_agent_source",
        "build_generic_artifact_payload",
        "build_blueprint_review",
        "_review_journal",
        "external_dispatch_performed",
        "analyze_document_sources_with_llm",
        "build_agent_version_diff",
        "_document_fields",
        "_document_next_questions",
    ],
    "src/services/agent_document_llm.py": [
        "analyze_text_with_gigachat",
        "agent_document_analysis",
        "analysis_source",
        "deterministic_fallback",
        "external_dispatch_performed",
        "provenance",
        "MAX_DOCUMENT_LLM_CONTEXT_CHARS",
    ],
    "src/services/agent_source_ingestion.py": [
        "MAX_AGENT_SOURCE_FILE_BYTES",
        "SUPPORTED_AGENT_SOURCE_EXTENSIONS",
        "extract_text_from_agent_source_bytes",
        "_extract_pdf_text",
        "_extract_docx_text",
        "_extract_xlsx_text",
    ],
    "src/services/agent_datahub.py": [
        "AGENT_DATAHUB_SOURCES",
        "build_agent_datahub_catalog",
        "business_profile",
        "prospectingleads",
        "outreach_drafts",
    ],
    "src/services/agent_blueprint_runner.py": [
        "allow_execute_when_approved=True",
        "build_generic_artifact_payload",
        "CAPABILITY_BLOCKED",
        "required_approval_type",
        "_build_lead_source_payload",
        "source\": \"prospectingleads",
        "source_artifact\": \"lead_source_plan",
        "status_counts",
        "_create_message_drafts_for_approved_shortlist",
        "_apply_drafts_approval",
        "_latest_artifact_item_ids",
    ],
    "src/services/agent_blueprint_orchestrator.py": [
        "OUTREACH_SEND_BATCH_CAPABILITY",
        "handle_outreach_send_batch",
    ],
    "src/services/outreach_send_capability.py": [
        "external_dispatch_performed",
        "queued_not_dispatched",
        "dispatch_due_outreach_queue",
        "l.business_id = %s",
    ],
    "frontend/src/pages/dashboard/AgentBlueprintsPage.tsx": [
        "runSource",
        "runCity",
        "runCategory",
        "Не удалось собрать черновик агента",
        "Создать агента",
        "Тип агента",
        "Правила и контроль",
        "Системные агенты",
        "Пользовательские агенты",
        "Ждут решения",
        "Сохранённые результаты",
        "Настройка агента",
        "Данные агента",
        "Datahub LocalOS",
        "sourceCatalog",
        "sources/catalog",
        "Журнал запуска",
        "JournalEntryCard",
        "Как настроен агент",
        "HumanPayloadView",
        "Создать новую версию",
        "Источник лидов: prospectingleads",
        "source_artifact",
        "Поставлено в очередь, но не отправлено",
        "sources/upload",
        "Новая активная версия",
        "ApprovalPayloadSummary",
        "DialogAgentBuilder",
        "Preview будущего агента",
        "Нужно уточнить",
        "Создать из preview",
    ],
    "scripts/smoke_agent_blueprint_document_api.py": [
        "/api/agent-blueprints/draft",
        "/sources/upload",
        "/feedback",
        "external_dispatch_performed",
        "system_agents_config_persisted",
    ],
    "scripts/smoke_agent_blueprint_generic_boundaries.py": [
        "GENERIC_AGENT_CASES",
        "documents",
        "email",
        "tables",
        "reviews",
        "step_type\") == \"capability",
        "external_dispatch_performed",
        "dispatch_state",
        "final_output",
        "dispatcher_started",
    ],
    "scripts/smoke_agent_builder_dialog_api.py": [
        "/api/agent-builder/sessions",
        "/message",
        "/create-blueprint",
        "missing_questions",
        "preview_available",
        "blueprint_created",
    ],
}

texts = {
    "src/api/agent_builder_api.py": builder_api_text,
    "src/api/agent_blueprints_api.py": api_text,
    "src/services/agent_builder_session.py": builder_session_text,
    "src/services/agent_blueprint_runner.py": runner_text,
    "src/services/agent_blueprint_orchestrator.py": orchestrator_text,
    "src/services/agent_blueprint_draft_builder.py": draft_builder_text,
    "src/services/agent_blueprint_workspace.py": workspace_text,
    "src/services/agent_source_ingestion.py": source_ingestion_text,
    "src/services/agent_datahub.py": datahub_text,
    "src/services/agent_document_llm.py": document_llm_text,
    "src/services/outreach_send_capability.py": capability_text,
    "frontend/src/pages/dashboard/AgentBlueprintsPage.tsx": ui_text,
    "scripts/smoke_agent_blueprint_document_api.py": Path("scripts/smoke_agent_blueprint_document_api.py").read_text(encoding="utf-8"),
    "scripts/smoke_agent_blueprint_generic_boundaries.py": Path("scripts/smoke_agent_blueprint_generic_boundaries.py").read_text(encoding="utf-8"),
    "scripts/smoke_agent_builder_dialog_api.py": Path("scripts/smoke_agent_builder_dialog_api.py").read_text(encoding="utf-8"),
}

for path, markers in required.items():
    for marker in markers:
        if marker not in texts[path]:
            raise SystemExit(f"{path}: missing guardrail marker {marker}")

print("OK: agent blueprint runtime uses registered safe outreach capability")
PY

echo "[backend-lint] operator route and paid draft guardrails"
PYTHONPATH=src python3 - <<'PY'
import main

expected = {
    "/api/operator/review-replies/generate": "operator_api.operator_review_replies_generate",
    "/api/operator/chat": "operator_api.operator_chat",
    "/api/operator/review-reply-drafts/<draft_id>/mark-manual-published": "operator_api.operator_review_reply_draft_mark_manual_published",
    "/api/operator/services/optimize/apply": "operator_api.operator_services_optimize_apply",
    "/api/operator/reviews/refresh-jobs/<queue_id>/retry": "operator_api.operator_review_refresh_job_retry",
}

actual = {rule.rule: rule.endpoint for rule in main.app.url_map.iter_rules()}
for route, endpoint in expected.items():
    if actual.get(route) != endpoint:
        raise SystemExit(f"{route}: expected {endpoint}, got {actual.get(route)}")

print("OK: Operator bulk/manual review routes are registered through operator_api")
PY

python3 - <<'PY'
from pathlib import Path

operator_text = Path("src/services/operator_review_reply_bulk.py").read_text(encoding="utf-8")
api_text = Path("src/api/operator_api.py").read_text(encoding="utf-8")
blueprint_handler_text = Path("src/services/outreach_send_capability.py").read_text(encoding="utf-8")

for marker in (
    "reserve_paid_action_credits",
    "finalize_reserved_action_credits",
    "external_writes_performed",
    "manual_publication_only",
):
    if marker not in operator_text:
        raise SystemExit(f"operator_review_reply_bulk missing guardrail marker: {marker}")

if "dispatch_due_outreach_queue(" in blueprint_handler_text:
    raise SystemExit("Agent Blueprint outreach capability must not call dispatch_due_outreach_queue directly")

if "generate_review_reply_drafts_for_unanswered_reviews" not in api_text:
    raise SystemExit("operator_api does not expose bulk review reply service")

print("OK: paid Operator drafts and Agent Blueprint dispatch boundaries are guarded")
PY

echo "[backend-lint] Operator AI fallback router stays paid and bounded"
python3 - <<'PY'
from pathlib import Path

api_text = Path("src/api/operator_api.py").read_text(encoding="utf-8")
router_text = Path("src/services/operator_intent_ai_router.py").read_text(encoding="utf-8")
ui_text = Path("frontend/src/pages/dashboard/OperatorPage.tsx").read_text(encoding="utf-8")
paid_text = Path("src/services/operator_paid_actions.py").read_text(encoding="utf-8")

required = {
    "src/api/operator_api.py": [
        "should_use_ai_intent_router",
        "classify_operator_intent_with_ai",
        "manual_review_text_not_explicit",
        "_attach_ai_router",
    ],
    "src/services/operator_intent_ai_router.py": [
        "OPERATOR_INTENT_CLASSIFY_ACTION_KEY",
        "build_paid_action_preflight",
        "reserve_paid_action_credits",
        "finalize_reserved_action_credits",
        "raw_response",
        "external_writes_performed",
        "manual_publication_only",
    ],
    "frontend/src/pages/dashboard/OperatorPage.tsx": [
        "AI-разбор команды",
        "ai_router",
    ],
    "src/services/operator_paid_actions.py": [
        "operator_intent_classify",
        "external_write\": False",
    ],
}
texts = {
    "src/api/operator_api.py": api_text,
    "src/services/operator_intent_ai_router.py": router_text,
    "frontend/src/pages/dashboard/OperatorPage.tsx": ui_text,
    "src/services/operator_paid_actions.py": paid_text,
}
for path, markers in required.items():
    for marker in markers:
        if marker not in texts[path]:
            raise SystemExit(f"{path}: missing Operator AI router marker {marker}")

if '"raw_response"' in router_text or "'raw_response'" in router_text:
    raise SystemExit("Operator AI router must not expose raw_response in public result")

print("OK: Operator AI fallback router is paid, cheap-gated, and bounded")
PY

echo "[backend-lint] Operator services apply smoke is self-contained"
python3 - <<'PY'
from pathlib import Path

smoke_text = Path("scripts/smoke_operator_services_apply_api.py").read_text(encoding="utf-8")
required = [
    "setup_fixture",
    "cleanup_fixture",
    "fake_services_generator",
    "request_json",
    "/api/operator/services/optimize/apply",
    '"confirm_apply": True',
    "explicit_confirmation_required",
    "ledger_after_apply == ledger_after_generate",
    "external_writes_performed",
    "fixture_cleaned",
]
for marker in required:
    if marker not in smoke_text:
        raise SystemExit(f"operator services apply smoke missing marker: {marker}")
if "from tests" in smoke_text or "import tests" in smoke_text:
    raise SystemExit("operator services apply smoke must not import tests")

print("OK: Operator services apply smoke is self-contained")
PY

echo "[backend-lint] outreach dispatcher stays explicit opt-in"
python3 - <<'PY'
from pathlib import Path

worker_text = Path("src/worker.py").read_text(encoding="utf-8")
compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

if '_env_bool("OUTREACH_DISPATCH_ENABLED", False)' not in worker_text:
    raise SystemExit("OUTREACH_DISPATCH_ENABLED must default to false in worker")

if compose_text.count("OUTREACH_DISPATCH_ENABLED: ${OUTREACH_DISPATCH_ENABLED:-false}") < 2:
    raise SystemExit("docker-compose.yml must expose OUTREACH_DISPATCH_ENABLED as explicit opt-in for app and worker")

print("OK: outreach dispatcher is disabled unless explicitly enabled")
PY

echo "[backend-lint] Operator refresh Telegram follow-up stays bounded"
python3 - <<'PY'
from pathlib import Path

service_text = Path("src/services/operator_refresh_telegram_followup.py").read_text(encoding="utf-8")
worker_text = Path("src/worker.py").read_text(encoding="utf-8")

required_service_markers = [
    "FOLLOWUP_ATTEMPTED_AT_KEY",
    "FOLLOWUP_DELIVERED_AT_KEY",
    "telegram_refresh_followup_already_attempted",
    "owner_telegram_id_missing",
    "refresh_still_processing",
    "send_func(telegram_id, text)",
    "публикация в карты остаётся ручной",
    "вы копируете и вставляете сами",
]
for marker in required_service_markers:
    if marker not in service_text:
        raise SystemExit(f"operator refresh Telegram follow-up missing guard marker: {marker}")

for forbidden in (
    "yandex_business",
    "publish",
    "provider_write",
    "external_write",
    "ActionOrchestrator",
):
    if forbidden in service_text:
        raise SystemExit(f"operator refresh Telegram follow-up must not perform external writes: {forbidden}")

if "dispatch_operator_refresh_telegram_followup" not in worker_text:
    raise SystemExit("worker does not dispatch operator refresh Telegram follow-up")
if "send_func=_send_telegram_plain_message" not in worker_text:
    raise SystemExit("operator refresh Telegram follow-up must use owner-bot plain message sender")

print("OK: Operator refresh Telegram follow-up is once-only and manual-publication bounded")
PY

echo "[backend-lint] Operator refresh reliability stays read-only"
python3 - <<'PY'
from pathlib import Path

service_text = Path("src/services/operator_refresh_result.py").read_text(encoding="utf-8")
frontend_text = Path("frontend/src/pages/dashboard/OperatorPage.tsx").read_text(encoding="utf-8")

required_service_markers = [
    "build_parse_reliability_state",
    "classify_failure_reason",
    "retrying",
    "captcha_required",
    "completed_with_warnings",
    "external_writes_performed",
    "manual_publication_only",
]
for marker in required_service_markers:
    if marker not in service_text:
        raise SystemExit(f"operator refresh reliability missing marker: {marker}")

for forbidden in (
    "INSERT INTO parsequeue",
    "UPDATE parsequeue",
    "reserve_paid_action_credits",
    "finalize_reserved_action_credits",
    "telegram_urlopen",
):
    if forbidden.lower() in service_text.lower():
        raise SystemExit(f"operator refresh reliability must stay read-only: {forbidden}")

for marker in ("reliability_state", "result.reliability_state.title", "result.reliability_state.explanation", "result.reliability_state.next_step"):
    if marker not in frontend_text:
        raise SystemExit(f"operator UI missing refresh reliability marker: {marker}")

print("OK: Operator refresh reliability is read-only and visible")
PY

echo "[backend-lint] Operator refresh retry stays controlled"
python3 - <<'PY'
from pathlib import Path

retry_text = Path("src/services/operator_refresh_retry.py").read_text(encoding="utf-8")
api_text = Path("src/api/operator_api.py").read_text(encoding="utf-8")

for marker in (
    "confirm_retry: bool = False",
    "explicit_retry_confirmation_required",
    "enqueue_paid_operator_map_refresh",
    "Старый failed job не изменялся",
    "external_writes_performed",
    "credit_charged\": False",
):
    if marker not in retry_text:
        raise SystemExit(f"operator refresh retry missing guardrail marker: {marker}")

for forbidden in (
    "UPDATE parsequeue",
    "DELETE FROM parsequeue",
    "ApifyClient",
    "send_message(",
    "publish",
):
    if forbidden in retry_text:
        raise SystemExit(f"operator refresh retry must not mutate old job or call providers directly: {forbidden}")

if "confirm_retry=bool(payload.get(\"confirm_retry\"))" not in api_text:
    raise SystemExit("operator refresh retry route must pass explicit confirm_retry")

print("OK: Operator refresh retry requires confirmation and uses paid enqueue boundary")
PY

echo "[backend-lint] approval boundary audit"
python3 scripts/audit_approval_boundaries.py

echo "[backend-lint] extracted growth routes stay out of main.py"
python3 - <<'PY'
from pathlib import Path

main_text = Path("src/main.py").read_text(encoding="utf-8")
for marker in (
    "/api/progress",
    "/api/business/<business_id>/optimization-wizard",
    "/api/business/<business_id>/sprint",
    "/api/business/<string:business_id>/stages",
    "/api/admin/growth-stages/<business_type_id>",
    "/api/admin/growth-stages",
    "/api/admin/growth-stages/<stage_id>",
    "/api/admin/business-types",
    "/api/admin/business-types/<type_id>",
    "/api/business-types",
):
    if marker in main_text:
        raise SystemExit(f"route still owned by main.py: {marker}")

print("OK: extracted growth routes are not declared in main.py")
PY

echo "[backend-lint] growth stage duplicate route smoke"
PYTHONPATH=src python3 - <<'PY'
import main

route_methods = {}
for rule in main.app.url_map.iter_rules():
    methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
    route_methods[(rule.rule, methods)] = rule.endpoint

expected_methods = {
    ("/api/admin/growth-stages/<stage_id>", frozenset({"PUT"})): "admin_growth_api.update_growth_stage",
    ("/api/admin/growth-stages/<stage_id>", frozenset({"DELETE"})): "admin_growth_api.delete_growth_stage",
}

for key, endpoint in expected_methods.items():
    actual = route_methods.get(key)
    if actual != endpoint:
        raise SystemExit(f"{key}: expected {endpoint}, got {actual}")

stale_main_endpoints = {
    "get_business_stages",
    "get_growth_stages",
    "create_growth_stage",
    "update_or_delete_growth_stage",
}
actual_endpoints = {rule.endpoint for rule in main.app.url_map.iter_rules()}
stale = stale_main_endpoints.intersection(actual_endpoints)
if stale:
    raise SystemExit(f"stale main.py growth endpoints still registered: {sorted(stale)}")

print("OK: growth stage routes have no stale main.py duplicates")
PY

echo "[backend-lint] admin business-type duplicate route smoke"
PYTHONPATH=src python3 - <<'PY'
import main

route_methods = {}
for rule in main.app.url_map.iter_rules():
    methods = frozenset(rule.methods - {"HEAD", "OPTIONS"})
    route_methods[(rule.rule, methods)] = rule.endpoint

expected_methods = {
    ("/api/admin/business-types", frozenset({"GET"})): "admin_growth_api.get_business_types",
    ("/api/admin/business-types", frozenset({"POST"})): "admin_growth_api.create_business_type",
    ("/api/admin/business-types/<type_id>", frozenset({"PUT"})): "admin_growth_api.update_business_type",
    ("/api/admin/business-types/<type_id>", frozenset({"DELETE"})): "admin_growth_api.delete_business_type",
}

for key, endpoint in expected_methods.items():
    actual = route_methods.get(key)
    if actual != endpoint:
        raise SystemExit(f"{key}: expected {endpoint}, got {actual}")

stale_main_endpoints = {
    "get_business_types",
    "create_business_type",
    "update_or_delete_business_type",
}
actual_endpoints = {rule.endpoint for rule in main.app.url_map.iter_rules()}
stale = stale_main_endpoints.intersection(actual_endpoints)
if stale:
    raise SystemExit(f"stale main.py admin business-type endpoints still registered: {sorted(stale)}")

print("OK: admin business-type routes have no stale main.py duplicates")
PY

echo "[backend-lint] runtime SQL placeholder scan"
python3 - <<'PY'
import ast
from pathlib import Path

skip_parts = {"migrations", "scripts", "__pycache__"}
skip_prefixes = ("migrate_", "migration_", "debug_", "verify_", "clear_database.py", "add_to_queue.py")
allowed_files = {"src/api/reports_api.py"}
findings = []

for path in sorted(Path("src").rglob("*.py")):
    path_text = str(path)
    if path_text in allowed_files:
        continue
    if any(part in skip_parts for part in path.parts):
        continue
    if path.name.startswith(skip_prefixes):
        continue

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "attr", None) or getattr(func, "id", None)
        if name not in {"execute", "executemany"} or not node.args:
            continue
        arg = node.args[0]
        value = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
        if value and "?" in value:
            first_line = value.strip().splitlines()[0][:120]
            findings.append(f"{path}:{node.lineno}: {first_line}")

if findings:
    print("\n".join(findings))
    raise SystemExit(1)

print("OK: no direct runtime SQLite ? placeholders outside allowed legacy reports blueprint")
PY

echo "[backend-lint] growth workflow SQL placeholder scan"
python3 - <<'PY'
import ast
from pathlib import Path

path = Path("src/api/growth_workflow_api.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
findings = []

for node in ast.walk(tree):
    if not isinstance(node, ast.Call):
        continue
    func = node.func
    name = getattr(func, "attr", None) or getattr(func, "id", None)
    if name not in {"execute", "executemany"} or not node.args:
        continue
    arg = node.args[0]
    value = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else None
    if value and "?" in value:
        first_line = value.strip().splitlines()[0][:120]
        findings.append(f"{path}:{node.lineno}: {first_line}")

if findings:
    print("\n".join(findings))
    raise SystemExit(1)

print("OK: growth workflow blueprint uses PostgreSQL placeholders")
PY
