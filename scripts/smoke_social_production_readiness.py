#!/usr/bin/env python3
"""Static production-readiness smoke for the Social Posting Agent.

The runtime smoke checks a live container. This one is intentionally local and
side-effect free: it guards the release contract before anyone enables the
worker flags that can publish approved queued posts.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_PLAN_TAB = ROOT / "frontend" / "src" / "components" / "content-plan" / "ContentPlanTab.tsx"
SOCIAL_POST_SERVICE = ROOT / "src" / "services" / "social_post_service.py"
SOCIAL_POSTS_API = ROOT / "src" / "api" / "social_posts_api.py"
WORKER = ROOT / "src" / "worker.py"
RUNTIME_SMOKE = ROOT / "scripts" / "smoke_social_posting_runtime.sh"
DEPLOY_BACKEND = ROOT / "scripts" / "deploy_backend_src.sh"
DOCKER_COMPOSE = ROOT / "docker-compose.yml"
ACCEPTANCE_PROBE = ROOT / "scripts" / "social_posting_acceptance_probe.py"


REQUIRED_SERVICE_CONTRACT = {
    "prepare preview service": "preview_social_posts_for_item",
    "prepare preview no database writes": "database_write_performed",
    "launch preflight builder": "_build_social_launch_preflight_payload",
    "safe scoped dispatch flag": "safe_to_enable_scoped_dispatch",
    "api preflight blocker": "api_preflight_blocked_due_posts",
    "launch runbook": "launch_runbook",
    "first cycle verification": "first_cycle_verification",
    "first API publish readiness": "first_api_publish_readiness",
    "first API launch plan": "first_api_launch_plan_ru",
    "first API proof check": "proof_check_ru",
    "first API metrics followup": "metrics_followup_ru",
    "launch rehearsal in preflight": "launch_rehearsal",
    "launch rehearsal summary": "launch_rehearsal_ready_posts",
    "dispatch execution report": "localos_social_dispatch_execution_report_v1",
    "first API proof candidate schema": "localos_social_first_api_proof_candidate_v1",
    "first API proof candidate contract": "first_api_proof_candidate",
    "first API proof summary schema": "localos_social_first_api_proof_summary_v1",
    "first API proof summary contract": "first_api_proof_summary",
    "first API publish schema": "localos_social_first_api_publish_readiness_v1",
    "dispatch dry run preview": "preview_due_social_post_dispatch",
    "worker dispatch live preflight": "_dispatch_live_api_preflight_block",
    "api preflight source marker": "worker_dispatch_live_api_preflight",
    "dispatch scope env": "SOCIAL_POST_DISPATCH_BUSINESS_ID",
    "metrics scope env": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "dispatch enabled env": "SOCIAL_POST_DISPATCH_ENABLED",
    "metrics enabled env": "SOCIAL_POST_METRICS_ENABLED",
    "maps supervised capability": "social.post.publish_supervised_browser",
    "supervised handoff state schema": "localos_social_supervised_handoff_state_v1",
    "openclaw outbox schema": "localos_social_supervised_openclaw_request_v1",
    "openclaw callback env": "OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL",
    "legacy openclaw callback env": "OPENCLAW_SUPERVISED_CALLBACK_URL",
    "openclaw catalog route error": "не смог прочитать capability catalog",
    "openclaw production vps next action": "production VPS",
    "outbox table": "action_callback_outbox",
    "stop before final publish": "stop_before_final_publish",
    "final click policy": "human_final_click_required",
    "browser final click false": "browser_final_click_allowed",
    "recommendation future scope": "future_unpublished_content_plan_items",
    "recommendation approval audit": "approval_record",
}


REQUIRED_API_CONTRACT = {
    "prepare preview endpoint": "/api/content-plans/items/<item_id>/social-posts/prepare-preview",
    "runtime status endpoint": "/api/social-posts/runtime-status",
    "launch preflight endpoint": "/api/business/<business_id>/social-posts/launch-preflight",
    "dispatch preview endpoint": "/api/social-posts/dispatch/preview",
    "dispatch run once endpoint": "/api/social-posts/dispatch/run-once",
    "metrics run once endpoint": "/api/social-posts/metrics/run-once",
    "recommend next plan endpoint": "/api/content-plans/<plan_id>/social-posts/recommend-next-plan",
    "apply recommendation endpoint": "/api/content-plans/<plan_id>/social-posts/apply-recommendation",
    "dispatch explicit approval": "Для запуска первого цикла публикаций нужно явное подтверждение",
    "metrics explicit approval": "Для сбора реакций нужно явное подтверждение",
    "runtime blocked without scope": "blocked_without_scope",
    "approval invariant": "approval_required",
    "final click invariant": "browser_final_click_allowed",
}


REQUIRED_WORKER_CONTRACT = {
    "dispatch flag": "SOCIAL_POST_DISPATCH_ENABLED",
    "dispatch interval": "SOCIAL_POST_DISPATCH_INTERVAL_SEC",
    "dispatch batch size": "SOCIAL_POST_DISPATCH_BATCH_SIZE",
    "dispatch business scope": "SOCIAL_POST_DISPATCH_BUSINESS_ID",
    "metrics flag": "SOCIAL_POST_METRICS_ENABLED",
    "metrics interval": "SOCIAL_POST_METRICS_INTERVAL_SEC",
    "metrics batch size": "SOCIAL_POST_METRICS_BATCH_SIZE",
    "metrics business scope": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "dispatch loop": "dispatch_due_social_posts",
    "metrics loop": "collect_due_social_post_metrics",
    "dispatch log": "[SOCIAL_POST_DISPATCH]",
    "dispatch scoped empty-cycle log": "picked > 0 or failed > 0 or business_scope",
    "metrics log": "[SOCIAL_POST_METRICS]",
    "metrics scoped empty-cycle log": "picked > 0 or failed > 0 or business_scope",
}


REQUIRED_COMPOSE_CONTRACT = {
    "app dispatch flag": "SOCIAL_POST_DISPATCH_ENABLED: ${SOCIAL_POST_DISPATCH_ENABLED:-false}",
    "app dispatch interval": "SOCIAL_POST_DISPATCH_INTERVAL_SEC: ${SOCIAL_POST_DISPATCH_INTERVAL_SEC:-60}",
    "app dispatch batch size": "SOCIAL_POST_DISPATCH_BATCH_SIZE: ${SOCIAL_POST_DISPATCH_BATCH_SIZE:-10}",
    "app dispatch business scope": "SOCIAL_POST_DISPATCH_BUSINESS_ID: ${SOCIAL_POST_DISPATCH_BUSINESS_ID:-}",
    "app dispatch allow unscoped": "SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED: ${SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED:-false}",
    "app metrics flag": "SOCIAL_POST_METRICS_ENABLED: ${SOCIAL_POST_METRICS_ENABLED:-false}",
    "app metrics interval": "SOCIAL_POST_METRICS_INTERVAL_SEC: ${SOCIAL_POST_METRICS_INTERVAL_SEC:-3600}",
    "app metrics batch size": "SOCIAL_POST_METRICS_BATCH_SIZE: ${SOCIAL_POST_METRICS_BATCH_SIZE:-50}",
    "app metrics business scope": "SOCIAL_POST_METRICS_BUSINESS_ID: ${SOCIAL_POST_METRICS_BUSINESS_ID:-}",
    "app metrics allow unscoped": "SOCIAL_POST_METRICS_ALLOW_UNSCOPED: ${SOCIAL_POST_METRICS_ALLOW_UNSCOPED:-false}",
    "worker dispatch business scope": "SOCIAL_POST_DISPATCH_BUSINESS_ID: ${SOCIAL_POST_DISPATCH_BUSINESS_ID:-}",
    "worker dispatch allow unscoped": "SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED: ${SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED:-false}",
    "worker metrics business scope": "SOCIAL_POST_METRICS_BUSINESS_ID: ${SOCIAL_POST_METRICS_BUSINESS_ID:-}",
    "worker metrics allow unscoped": "SOCIAL_POST_METRICS_ALLOW_UNSCOPED: ${SOCIAL_POST_METRICS_ALLOW_UNSCOPED:-false}",
    "app openclaw sandbox bridge url": "OPENCLAW_SANDBOX_BRIDGE_URL: ${OPENCLAW_SANDBOX_BRIDGE_URL:-}",
    "app openclaw sandbox bridge token": "OPENCLAW_SANDBOX_BRIDGE_TOKEN: ${OPENCLAW_SANDBOX_BRIDGE_TOKEN:-}",
    "worker openclaw sandbox bridge url": "OPENCLAW_SANDBOX_BRIDGE_URL: ${OPENCLAW_SANDBOX_BRIDGE_URL:-}",
    "worker openclaw sandbox bridge token": "OPENCLAW_SANDBOX_BRIDGE_TOKEN: ${OPENCLAW_SANDBOX_BRIDGE_TOKEN:-}",
}


REQUIRED_COMPOSE_MIN_COUNTS = {
    "SOCIAL_POST_DISPATCH_ENABLED: ${SOCIAL_POST_DISPATCH_ENABLED:-false}": 2,
    "SOCIAL_POST_DISPATCH_INTERVAL_SEC: ${SOCIAL_POST_DISPATCH_INTERVAL_SEC:-60}": 2,
    "SOCIAL_POST_DISPATCH_BATCH_SIZE: ${SOCIAL_POST_DISPATCH_BATCH_SIZE:-10}": 2,
    "SOCIAL_POST_DISPATCH_BUSINESS_ID: ${SOCIAL_POST_DISPATCH_BUSINESS_ID:-}": 2,
    "SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED: ${SOCIAL_POST_DISPATCH_ALLOW_UNSCOPED:-false}": 2,
    "SOCIAL_POST_METRICS_ENABLED: ${SOCIAL_POST_METRICS_ENABLED:-false}": 2,
    "SOCIAL_POST_METRICS_INTERVAL_SEC: ${SOCIAL_POST_METRICS_INTERVAL_SEC:-3600}": 2,
    "SOCIAL_POST_METRICS_BATCH_SIZE: ${SOCIAL_POST_METRICS_BATCH_SIZE:-50}": 2,
    "SOCIAL_POST_METRICS_BUSINESS_ID: ${SOCIAL_POST_METRICS_BUSINESS_ID:-}": 2,
    "SOCIAL_POST_METRICS_ALLOW_UNSCOPED: ${SOCIAL_POST_METRICS_ALLOW_UNSCOPED:-false}": 2,
    "OPENCLAW_SANDBOX_BRIDGE_URL: ${OPENCLAW_SANDBOX_BRIDGE_URL:-}": 2,
    "OPENCLAW_SANDBOX_BRIDGE_TOKEN: ${OPENCLAW_SANDBOX_BRIDGE_TOKEN:-}": 2,
}


REQUIRED_UI_CONTRACT = {
    "quick launch test id": 'data-testid="social-quick-launch"',
    "publishing next step test id": 'data-testid="social-publishing-next-step"',
    "launch readiness test id": 'data-testid="social-launch-readiness"',
    "launch rehearsal test id": 'data-testid="social-launch-rehearsal"',
    "first API launch plan test id": 'data-testid="social-first-api-launch-plan"',
    "first API launch plan copy": "План первого API-поста",
    "first API proof check": "provider_post_id/provider_post_url",
    "first API metrics followup": "соберите реакции/заявки",
    "dispatch execution report test id": 'data-testid="social-dispatch-execution-report"',
    "first API proof candidate test id": 'data-testid="social-first-api-proof-candidate"',
    "first API proof candidate copy": "Кандидат на первый API-proof",
    "first API proof summary test id": 'data-testid="social-first-api-proof-summary"',
    "first API proof summary copy": "Proof первого API-loop",
    "publish to learning next step test id": 'data-testid="social-post-publish-to-learning-next-step"',
    "channel queue test id": 'data-testid="social-channel-queue"',
    "channel connection guide test id": 'data-testid="social-channel-connection-guide"',
    "channel connection first action": "Первое действие:",
    "channel connection maps final click": "Финальный клик остаётся за человеком",
    "next plan recommendation test id": 'data-testid="social-next-plan-recommendation"',
    "preview before approval test id": 'data-testid="social-preview-before-approval"',
    "supervised handoff test id": 'data-testid="social-supervised-handoff"',
    "production launch section": "Готовность к рабочему запуску",
    "worker preflight action": "Проверить запуск worker",
    "worker preflight result": "Preflight запуска worker",
    "live api blocked": "Live API-preflight остановил запуск",
    "live api blocked setup action": "Открыть настройку",
    "live api blocked recovery copy": "Worker не будет публиковать этот due-пост",
    "safe launch env": "Команды для безопасного запуска",
    "copy worker env": "Скопировать env для worker",
    "dispatch enabled env": "SOCIAL_POST_DISPATCH_ENABLED",
    "dispatch scope env": "SOCIAL_POST_DISPATCH_BUSINESS_ID",
    "metrics scope env": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "first cycle preview": "Что сделает первый цикл",
    "first cycle expected status": "Ожидаемый статус",
    "runtime alignment": "Runtime этого бизнеса",
    "preflight no publish": "Preflight ничего не публикует",
    "approval still required": "Внешние публикации всё равно требуют approval",
    "maps final click guard": "Яндекс/2ГИС не нажимают финальную кнопку без человека",
    "api publish worker only": "API-публикация запустится только worker",
    "supervised handoff state": "Состояние handoff",
    "openclaw final click copy": "OpenClaw не нажимает финальную кнопку публикации",
    "recommendation facts": "Факты для следующего плана",
    "apply future only": "только будущие неопубликованные пункты",
}


REQUIRED_RUNTIME_SMOKE_CONTRACT = {
    "auth guard": "/api/social-posts/runtime-status",
    "approval invariant": "approval_required invariant failed",
    "browser final click invariant": "browser_final_click_allowed invariant failed",
    "scoped launch dry run": "scoped launch preflight dry-run",
    "scoped business id passed into container": '-e SOCIAL_RUNTIME_SMOKE_BUSINESS_ID="${SMOKE_BUSINESS_ID}"',
    "dry run invariant": "launch preflight must be dry-run",
    "maps supervision invariant": "launch preflight maps supervision invariant failed",
    "dispatch logs": "[SOCIAL_POST_DISPATCH]",
    "scoped dispatch picked log": "[SOCIAL_POST_DISPATCH] picked=",
    "metrics logs": "[SOCIAL_POST_METRICS]",
    "env alignment check": "app/worker social env alignment",
    "env mismatch failure": "app/worker social env mismatch",
    "server mode": "server)",
    "server workdir": "cd /opt/seo-app",
}


REQUIRED_DEPLOY_CONTRACT = {
    "runtime social scripts list": "runtime_script_files",
    "acceptance probe upload": "scripts/social_posting_acceptance_probe.py",
    "social readiness smoke upload": "scripts/smoke_social_production_readiness.py",
    "container script sync": "docker compose cp ${remote_tmp}/scripts/. app:/app/scripts/",
    "worker script sync": "docker compose cp ${remote_tmp}/scripts/. worker:/app/scripts/",
    "container probe compile check": "python3 -m py_compile /app/scripts/social_posting_acceptance_probe.py",
}


REQUIRED_ACCEPTANCE_PROBE_CONTRACT = {
    "acceptance ready": "acceptance_ready",
    "read only": "read_only",
    "no external publish": "external_publish_performed",
    "no database writes": "database_write_performed",
    "approval required": "approval_required",
    "browser final click false": "browser_final_click_allowed",
    "maps supervised or manual": "maps_are_supervised_or_manual",
    "plan summary": "plan_summary",
    "ready candidates": "ready_items_without_social_posts",
    "channel readiness": "channel_readiness_summary",
    "api preflight": "api_preflight_summary",
    "launch status": "launch_status",
    "dispatch readiness": "dispatch_readiness",
    "first cycle verification": "first_cycle_verification",
    "first API publish readiness": "first_api_publish_readiness",
    "safe scoped dispatch": "launch_safe_to_enable_scoped_dispatch",
    "dispatch dry run": "dispatch_preview",
    "launch rehearsal": "launch_rehearsal",
    "bulk rehearsal schema": "localos_social_publish_rehearsal_bulk_v1",
    "due queued post ids": "due_queued_post_ids",
    "rehearsal blocks provider write": "provider_write_performed",
    "next human step": "next_required_human_step",
    "prepare channels guidance": "Подготовить каналы",
}


FORBIDDEN_RELEASE_CLAIMS = {
    "maps autopublish ru": "Яндекс/2ГИС автопубликация",
    "maps autopublish en": "Yandex/2GIS autopublish",
    "old mixed maps label": "Яндекс/2ГИС controlled/manual",
    "old controlled launch": "Controlled launch env",
}


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")


def _missing(source: str, markers: dict[str, str]) -> list[str]:
    missing = []
    for label, marker in markers.items():
        if marker not in source:
            missing.append(f"{label}: {marker}")
    return missing


def _present(source: str, markers: dict[str, str]) -> list[str]:
    present = []
    for label, marker in markers.items():
        if marker in source:
            present.append(f"{label}: {marker}")
    return present


def main() -> int:
    try:
        service = _read(SOCIAL_POST_SERVICE)
        api = _read(SOCIAL_POSTS_API)
        worker = _read(WORKER)
        ui = _read(CONTENT_PLAN_TAB)
        runtime_smoke = _read(RUNTIME_SMOKE)
        deploy_backend = _read(DEPLOY_BACKEND)
        docker_compose = _read(DOCKER_COMPOSE)
        acceptance_probe = _read(ACCEPTANCE_PROBE)
    except FileNotFoundError:
        print(f"Missing source file: {sys.exc_info()[1]}", file=sys.stderr)
        return 1

    errors = []
    errors.extend(f"service missing {item}" for item in _missing(service, REQUIRED_SERVICE_CONTRACT))
    errors.extend(f"API missing {item}" for item in _missing(api, REQUIRED_API_CONTRACT))
    errors.extend(f"worker missing {item}" for item in _missing(worker, REQUIRED_WORKER_CONTRACT))
    errors.extend(f"compose missing {item}" for item in _missing(docker_compose, REQUIRED_COMPOSE_CONTRACT))
    for marker, minimum_count in REQUIRED_COMPOSE_MIN_COUNTS.items():
        actual_count = docker_compose.count(marker)
        if actual_count < minimum_count:
            errors.append(
                f"compose needs {minimum_count} occurrences of {marker}, found {actual_count}"
            )
    errors.extend(f"UI missing {item}" for item in _missing(ui, REQUIRED_UI_CONTRACT))
    errors.extend(f"runtime smoke missing {item}" for item in _missing(runtime_smoke, REQUIRED_RUNTIME_SMOKE_CONTRACT))
    errors.extend(f"deploy backend missing {item}" for item in _missing(deploy_backend, REQUIRED_DEPLOY_CONTRACT))
    errors.extend(f"acceptance probe missing {item}" for item in _missing(acceptance_probe, REQUIRED_ACCEPTANCE_PROBE_CONTRACT))

    combined_owner_surface = "\n".join([ui, service])
    errors.extend(f"forbidden release claim {item}" for item in _present(combined_owner_surface, FORBIDDEN_RELEASE_CLAIMS))

    if errors:
        print("social production readiness smoke failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("social production readiness smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
