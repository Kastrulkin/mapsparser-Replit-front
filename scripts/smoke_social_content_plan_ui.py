#!/usr/bin/env python3
"""Verify the owner-facing social posting cockpit contract.

This smoke is intentionally static and fast: it guards the UX promises that
make the content-plan screen usable before a heavier browser pass runs.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTENT_PLAN_TAB = ROOT / "frontend" / "src" / "components" / "content-plan" / "ContentPlanTab.tsx"


REQUIRED_COPY = {
    "main next action": "Следующий шаг публикаций",
    "schedule preview": "Проверить расписание",
    "dispatch scope guard": "заблокировано без выбранного бизнеса",
    "dispatch guarded notice": "Dispatch включён, но остановлен защитой",
    "dispatch scope mismatch notice": "Dispatch включён для другого бизнеса",
    "dispatch dry-run next step": "Следующий шаг: ",
    "metrics scope guard": "реакции: заблокировано без выбранного бизнеса",
    "metrics guarded notice": "Сбор реакций включён, но LocalOS не будет вызывать внешние API",
    "queue summary": "Очередь публикаций по каналам",
    "channel readiness": "Готовность каналов",
    "readiness next action": "Что сделать:",
    "approval preview": "Предпросмотр перед подтверждением",
    "queue action": "Поставить в расписание",
    "queue saved guard feedback": "Queue сохранена, но LocalOS не запустит внешний worker",
    "queue saved scope feedback": "текущий worker смотрит другой business scope",
    "supervised placement state": "Контролируемое размещение",
    "manual placement action": "Отметить размещённым",
    "copy-ready fallback": "Скопировать текст",
    "next-plan recommendations": "Что менять в следующем плане",
    "recommendation preview": "Предпросмотр изменений плана",
    "apply with confirmation": "Применить после подтверждения",
    "lead attribution": "Была заявка",
    "inquiry attribution": "Было обращение",
    "like attribution": "Был лайк",
    "view attribution": "Был просмотр",
}


REQUIRED_SAFETY_COPY = {
    "external approval invariant": "Внешние публикации всё равно требуют approval",
    "maps no final click": "Яндекс/2ГИС не нажимают финальную кнопку без человека",
    "supervised task is not autopublish": "финальная публикация остаётся за человеком",
    "api publish is scheduled": "API-публикация запустится только worker",
}


REQUIRED_DATA_CONTRACT = {
    "runtime status": "socialRuntimeStatus",
    "dispatch blocked without scope": "blocked_without_scope",
    "dispatch allow unscoped flag": "allow_unscoped",
    "metrics business scope guard": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "dispatch next action contract": "next_action_ru",
    "dispatch recommended env contract": "recommended_dispatch_env",
    "dispatch dry-run": "socialDispatchPreview",
    "readiness next action ru": "next_action_ru",
    "readiness next action en": "next_action_en",
    "supervised task id": "automation_task_id",
    "supervised ledger id": "agent_action_ledger_id",
    "openclaw capability status": "openclaw_capability_status",
    "plan recommendation signal priority": "signal_priority",
}


FORBIDDEN_COPY = {
    "silent maps autopublish ru": "Яндекс/2ГИС автопубликация",
    "silent maps autopublish en": "Yandex/2GIS autopublish",
}


def _assert_contains(source: str, markers: dict[str, str]) -> list[str]:
    missing = []
    for label, marker in markers.items():
        if marker not in source:
            missing.append(f"{label}: {marker}")
    return missing


def _assert_absent(source: str, markers: dict[str, str]) -> list[str]:
    present = []
    for label, marker in markers.items():
        if marker in source:
            present.append(f"{label}: {marker}")
    return present


def main() -> int:
    if not CONTENT_PLAN_TAB.exists():
        print(f"Missing UI source: {CONTENT_PLAN_TAB}", file=sys.stderr)
        return 1

    source = CONTENT_PLAN_TAB.read_text(encoding="utf-8")
    missing = []
    missing.extend(_assert_contains(source, REQUIRED_COPY))
    missing.extend(_assert_contains(source, REQUIRED_SAFETY_COPY))
    missing.extend(_assert_contains(source, REQUIRED_DATA_CONTRACT))
    forbidden = _assert_absent(source, FORBIDDEN_COPY)

    if missing or forbidden:
        if missing:
            print("Missing required social content-plan UX markers:", file=sys.stderr)
            for item in missing:
                print(f"  - {item}", file=sys.stderr)
        if forbidden:
            print("Forbidden social content-plan UX markers found:", file=sys.stderr)
            for item in forbidden:
                print(f"  - {item}", file=sys.stderr)
        return 1

    print("social content-plan UX smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
