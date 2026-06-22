#!/usr/bin/env python3
"""Fast contract smoke for the LocalOS social posting loop.

This complements unit tests with a deploy-friendly check that the owner-facing
workflow still has all critical seams wired: content plan UI, API endpoints,
worker loops, provider boundaries, and human approval invariants.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_PLAN_TAB = ROOT / "frontend" / "src" / "components" / "content-plan" / "ContentPlanTab.tsx"
SOCIAL_POSTS_API = ROOT / "src" / "api" / "social_posts_api.py"
SOCIAL_POST_SERVICE = ROOT / "src" / "services" / "social_post_service.py"
WORKER = ROOT / "src" / "worker.py"
RUNTIME_SMOKE = ROOT / "scripts" / "smoke_social_posting_runtime.sh"


REQUIRED_UI_MARKERS = {
    "overview cockpit": "Быстрый запуск публикаций",
    "channel next actions": "Каналы: что сделать",
    "preview before approval": "Предпросмотр перед подтверждением",
    "approve action": "Подтвердить",
    "queue action": "Поставить в расписание",
    "supervised placement action": "Подготовить контролируемое размещение",
    "manual published action": "Отметить размещённым",
    "metrics action": "Собрать реакции",
    "next-plan panel": "Что менять в следующем плане",
    "maps are not autopublish": "LocalOS готовит контролируемое размещение",
}


REQUIRED_API_MARKERS = {
    "prepare endpoint": "/api/content-plans/items/<item_id>/social-posts/prepare",
    "list endpoint": "/api/content-plans/<plan_id>/social-posts",
    "approve endpoint": "/api/social-posts/<post_id>/approve",
    "queue endpoint": "/api/social-posts/<post_id>/queue",
    "bulk queue endpoint": "/api/social-posts/bulk-queue",
    "dispatch preview endpoint": "/api/social-posts/dispatch/preview",
    "dispatch run-once endpoint": "/api/social-posts/dispatch/run-once",
    "metrics run-once endpoint": "/api/social-posts/metrics/run-once",
    "manual published endpoint": "/api/social-posts/<post_id>/mark-manual-published",
    "supervised task endpoint": "/api/social-posts/<post_id>/supervised-task",
    "recommend endpoint": "/api/content-plans/<plan_id>/social-posts/recommend-next-plan",
    "apply recommendation endpoint": "/api/content-plans/<plan_id>/social-posts/apply-recommendation",
    "run-once approval guard": "Для запуска первого цикла публикаций нужно явное подтверждение",
    "metrics approval guard": "Для сбора реакций нужно явное подтверждение",
    "runtime status scope guard": "blocked_without_scope",
}


REQUIRED_SERVICE_MARKERS = {
    "telegram publish adapter": "https://api.telegram.org/bot{bot_token}/sendMessage",
    "vk publish adapter": "https://api.vk.com/method/wall.post",
    "vk metrics adapter": "https://api.vk.com/method/wall.getById",
    "telegram metrics limit status": "telegram_bot_api_metrics_unavailable",
    "google metrics explicit boundary": "google_business_metrics_not_enabled",
    "meta metrics explicit boundary": "meta_graph_metrics_permissions_required",
    "maps metrics explicit boundary": "map_metrics_manual_input_required",
    "supervised task capability": "social.post.publish_supervised_browser",
    "stop before final publish": "stop_before_final_publish",
    "human final click policy": "human_final_click_required",
    "no approval no queue": "Перед постановкой в расписание нужно подтверждение человека",
    "recommendation approval": "approved_at",
}


REQUIRED_WORKER_MARKERS = {
    "dispatch env flag": "SOCIAL_POST_DISPATCH_ENABLED",
    "dispatch business scope": "SOCIAL_POST_DISPATCH_BUSINESS_ID",
    "metrics env flag": "SOCIAL_POST_METRICS_ENABLED",
    "metrics business scope": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "dispatch loop call": "dispatch_due_social_posts",
    "metrics loop call": "collect_due_social_post_metrics",
    "main loop dispatch": "_dispatch_social_posts_if_due()",
    "main loop metrics": "_collect_social_post_metrics_if_due()",
}


REQUIRED_RUNTIME_SMOKE_MARKERS = {
    "production mode": "server)",
    "auth guard": "/api/social-posts/runtime-status",
    "scope safety": "SOCIAL_SMOKE_ALLOW_UNSCOPED",
    "approval invariant": "approval_required invariant failed",
    "browser final click invariant": "browser_final_click_allowed invariant failed",
    "dispatch worker logs": "[SOCIAL_POST_DISPATCH]",
    "metrics worker logs": "[SOCIAL_POST_METRICS]",
    "scoped business smoke": "SOCIAL_RUNTIME_SMOKE_BUSINESS_ID",
    "scoped dry-run": "scoped launch preflight dry-run",
    "launch preflight dry-run invariant": "launch preflight must be dry-run",
    "launch preflight maps invariant": "launch preflight maps supervision invariant failed",
    "live cockpit copy": "OpenClaw не нажимает финальную кнопку публикации",
    "old copy guard": "Яндекс/2ГИС controlled/manual",
}


FORBIDDEN_UI_MARKERS = {
    "maps autopublish claim ru": "Яндекс/2ГИС автопубликация",
    "maps autopublish claim en": "Yandex/2GIS autopublish",
}


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path.read_text(encoding="utf-8")


def _missing(source: str, markers: dict[str, str]) -> list[str]:
    return [f"{label}: {marker}" for label, marker in markers.items() if marker not in source]


def _present(source: str, markers: dict[str, str]) -> list[str]:
    return [f"{label}: {marker}" for label, marker in markers.items() if marker in source]


def main() -> int:
    try:
        ui = _read(CONTENT_PLAN_TAB)
        api = _read(SOCIAL_POSTS_API)
        service = _read(SOCIAL_POST_SERVICE)
        worker = _read(WORKER)
        runtime_smoke = _read(RUNTIME_SMOKE)
    except FileNotFoundError as exc:
        print(f"Missing source file: {exc}", file=sys.stderr)
        return 1

    errors: list[str] = []
    errors.extend(f"UI missing {item}" for item in _missing(ui, REQUIRED_UI_MARKERS))
    errors.extend(f"API missing {item}" for item in _missing(api, REQUIRED_API_MARKERS))
    errors.extend(f"service missing {item}" for item in _missing(service, REQUIRED_SERVICE_MARKERS))
    errors.extend(f"worker missing {item}" for item in _missing(worker, REQUIRED_WORKER_MARKERS))
    errors.extend(f"runtime smoke missing {item}" for item in _missing(runtime_smoke, REQUIRED_RUNTIME_SMOKE_MARKERS))
    errors.extend(f"UI forbidden {item}" for item in _present(ui, FORBIDDEN_UI_MARKERS))

    if errors:
        print("social posting loop contract smoke failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("social posting loop contract smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
