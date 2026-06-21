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
EXTERNAL_INTEGRATIONS = ROOT / "frontend" / "src" / "components" / "ExternalIntegrations.tsx"
TELEGRAM_BOT_CREDENTIALS = ROOT / "frontend" / "src" / "components" / "TelegramBotCredentials.tsx"
SETTINGS_PAGE = ROOT / "frontend" / "src" / "pages" / "dashboard" / "SettingsPage.tsx"


REQUIRED_COPY = {
    "main next action": "Следующий шаг публикаций",
    "launch readiness": "Готовность к рабочему запуску",
    "launch loop path": "Короткий путь до полного цикла",
    "launch primary signal": "заявки и обращения важнее охватов",
    "schedule preview": "Проверить расписание",
    "worker launch preflight": "Проверить запуск worker",
    "worker launch preflight result": "Preflight запуска worker",
    "worker launch recommended scope": "Рекомендованный scope",
    "worker launch no publish": "Preflight ничего не публикует",
    "manual fallback button": "Нужен ручной fallback",
    "dispatch scope guard": "заблокировано без выбранного бизнеса",
    "dispatch guarded notice": "Dispatch включён, но остановлен защитой",
    "dispatch scope mismatch notice": "Dispatch включён для другого бизнеса",
    "dispatch dry-run next step": "Следующий шаг: ",
    "metrics scope guard": "реакции: заблокировано без выбранного бизнеса",
    "metrics guarded notice": "Сбор реакций включён, но LocalOS не будет вызывать внешние API",
    "queue summary": "Очередь публикаций по каналам",
    "channel readiness": "Готовность каналов",
    "readiness next action": "Что сделать:",
    "channel-specific setup action": "Открыть настройку канала",
    "telegram setup focus path": "/dashboard/settings?focus=channels",
    "integrations setup focus path": "/dashboard/settings?focus=integrations",
    "approval preview": "Предпросмотр перед подтверждением",
    "bulk approval saved preview guard": "Сначала сохраните правки текста",
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
    "result nudge": "Есть заявки/обращения",
    "stale recommendation guard": "Рекомендации сброшены",
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
    "launch preflight": "socialLaunchPreflight",
    "launch preflight endpoint": "/social-posts/launch-preflight",
    "supervised blocked endpoint": "/mark-supervised-blocked",
    "readiness next action ru": "next_action_ru",
    "readiness next action en": "next_action_en",
    "supervised task id": "automation_task_id",
    "supervised ledger id": "agent_action_ledger_id",
    "openclaw capability status": "openclaw_capability_status",
    "plan recommendation signal priority": "signal_priority",
}


REQUIRED_SETTINGS_COPY = {
    "settings publishing checklist": "Чеклист публикаций",
    "settings telegram requirements": "telegram_bot_token + telegram_chat_id",
    "settings vk requirements": "access_token + group_id/owner_id + wall.post",
    "settings vk form title": "VK публикации",
    "settings vk form description": "утверждённые посты выходили во VK по расписанию",
    "settings vk token placeholder": "VK access_token с правом wall.post",
    "settings vk owner placeholder": "group_id или owner_id",
    "settings vk encrypted storage": "Токен хранится зашифрованно",
    "settings vk save action": "Сохранить VK",
    "settings google requirements": "Business Profile + location",
    "settings meta requirements": "Page/IG business + permissions",
    "settings next action": "Что сделать: ",
    "settings maps controlled": "Яндекс/2ГИС остаются controlled/manual",
}


REQUIRED_SETTINGS_DATA_CONTRACT = {
    "settings readiness next action ru": "next_action_ru",
    "settings readiness next action en": "next_action_en",
    "settings channel readiness endpoint": "/social-posts/channel-readiness",
    "settings external accounts endpoint": "/external-accounts",
    "settings vk source": 'source: "vk"',
    "settings vk auth token": "access_token: tokenValue",
    "settings vk group id": "group_id: ownerValue.replace",
}


REQUIRED_TELEGRAM_SETTINGS_COPY = {
    "telegram publish target label": "Канал или чат для публикаций",
    "telegram publish chat id need": "Для постов из контент-плана нужен telegram_chat_id",
    "telegram publish chat id placeholder": "@channelname или -1001234567890",
    "telegram publish api warning": "не сможет отправить его по API",
    "telegram publish save success": "Telegram подключён для публикаций из контент-плана.",
}


REQUIRED_SETTINGS_PAGE_COPY = {
    "settings channels focus note": "вернитесь в контент-план и обновите готовность каналов",
    "settings channels focus param": "focusTarget === 'channels'",
    "settings telegram focus param": "focusTarget === 'telegram'",
}


REQUIRED_TELEGRAM_SETTINGS_DATA_CONTRACT = {
    "telegram status endpoint": "/api/business/telegram-bot/status",
    "telegram profile endpoint": "/api/business/profile",
    "telegram chat id payload": "telegram_chat_id",
    "telegram optional token payload": "telegram_bot_token",
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
    if not EXTERNAL_INTEGRATIONS.exists():
        print(f"Missing settings source: {EXTERNAL_INTEGRATIONS}", file=sys.stderr)
        return 1
    if not TELEGRAM_BOT_CREDENTIALS.exists():
        print(f"Missing Telegram settings source: {TELEGRAM_BOT_CREDENTIALS}", file=sys.stderr)
        return 1
    if not SETTINGS_PAGE.exists():
        print(f"Missing settings page source: {SETTINGS_PAGE}", file=sys.stderr)
        return 1

    source = CONTENT_PLAN_TAB.read_text(encoding="utf-8")
    settings_source = EXTERNAL_INTEGRATIONS.read_text(encoding="utf-8")
    telegram_settings_source = TELEGRAM_BOT_CREDENTIALS.read_text(encoding="utf-8")
    settings_page_source = SETTINGS_PAGE.read_text(encoding="utf-8")
    missing = []
    missing.extend(_assert_contains(source, REQUIRED_COPY))
    missing.extend(_assert_contains(source, REQUIRED_SAFETY_COPY))
    missing.extend(_assert_contains(source, REQUIRED_DATA_CONTRACT))
    missing.extend(_assert_contains(settings_source, REQUIRED_SETTINGS_COPY))
    missing.extend(_assert_contains(settings_source, REQUIRED_SETTINGS_DATA_CONTRACT))
    missing.extend(_assert_contains(telegram_settings_source, REQUIRED_TELEGRAM_SETTINGS_COPY))
    missing.extend(_assert_contains(telegram_settings_source, REQUIRED_TELEGRAM_SETTINGS_DATA_CONTRACT))
    missing.extend(_assert_contains(settings_page_source, REQUIRED_SETTINGS_PAGE_COPY))
    forbidden = _assert_absent(source, FORBIDDEN_COPY)
    forbidden.extend(_assert_absent(settings_source, FORBIDDEN_COPY))

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
