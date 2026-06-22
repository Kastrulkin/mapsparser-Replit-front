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
SOCIAL_POST_SERVICE = ROOT / "src" / "services" / "social_post_service.py"


REQUIRED_COPY = {
    "main next action": "Следующий шаг публикаций",
    "overview quick launch": "Быстрый запуск публикаций",
    "overview controlled placement": "LocalOS готовит контролируемое размещение",
    "overview openclaw readiness": "OpenClaw readiness для Яндекс/2ГИС проверяется отдельно",
    "overview openclaw check action": "Проверить OpenClaw",
    "overview channel next actions": "Каналы: что сделать",
    "overview learning loop": "social-overview-learning-loop-status",
    "overview learning loop action": "Открыть результаты",
    "goal progress contract": "goal_progress",
    "goal progress maps safety": "maps_are_supervised_or_manual",
    "launch checklist": "До рабочего запуска",
    "launch checklist progress": "Готово ${summary.done} из ${summary.total}",
    "launch checklist current": "Сейчас: ",
    "launch readiness": "Готовность к рабочему запуску",
    "launch loop path": "Короткий путь до полного цикла",
    "launch primary signal": "заявки и обращения важнее охватов",
    "overview first api readiness": "social-overview-first-api-readiness",
    "overview first api needs keys": "Пока нет готового API-канала",
    "overview first api approval guard": "Наружу только после preview, human approval, queue и даты публикации",
    "schedule preview": "Проверить расписание",
    "worker launch preflight": "Проверить запуск worker",
    "worker launch preflight result": "Preflight запуска worker",
    "production readiness block": "social-production-readiness",
    "production readiness heading": "Готовность к первому циклу",
    "production readiness blockers": "Блокеры перед запуском",
    "production readiness next action": "Что сделать: ",
    "worker launch live api block": "Live API-preflight остановил запуск",
    "worker launch live api blocked field": "api_preflight_blocked_due_posts",
    "worker launch recommended scope": "Рекомендованный scope",
    "worker launch gate contract": "launch_gate",
    "worker launch gate test id": "social-first-cycle-launch-gate",
    "worker launch gate heading": "Можно ли запускать сейчас",
    "worker launch gate click guard": "Яндекс/2ГИС без финального клика",
    "worker controlled launch env": "Команды для безопасного запуска",
    "worker copy env action": "Скопировать env для worker",
    "worker dispatch env enabled": "SOCIAL_POST_DISPATCH_ENABLED",
    "worker metrics env scope": "SOCIAL_POST_METRICS_BUSINESS_ID",
    "worker launch no publish": "Preflight ничего не публикует",
    "worker first cycle preview": "Что сделает первый цикл",
    "worker first cycle expected status": "Ожидаемый статус",
    "worker first cycle safety boundaries": "Границы безопасности",
    "manual fallback button": "Нужен ручной fallback",
    "dispatch scope guard": "заблокировано без выбранного бизнеса",
    "dispatch guarded notice": "Dispatch включён, но остановлен защитой",
    "dispatch scope mismatch notice": "Dispatch включён для другого бизнеса",
    "dispatch dry-run next step": "Следующий шаг: ",
    "metrics scope guard": "реакции: заблокировано без выбранного бизнеса",
    "metrics guarded notice": "Сбор реакций включён, но LocalOS не будет вызывать внешние API",
    "queue summary": "Очередь публикаций по каналам",
    "channel readiness": "Готовность каналов",
    "live api channel summary": "Live API-проверка каналов",
    "live api checked without publish": "Проверено без публикации",
    "live api approval guard": "publish только после approval",
    "first api post readiness": "Первый API-пост",
    "first api post approval queue guard": "после preview, approval и расписания",
    "first api post blocked channels": "Сначала исправить:",
    "first api post preflight action": "Проверить API",
    "launch first api readiness contract": "first_api_publish_readiness",
    "launch first api checklist": "Чеклист первого API-поста",
    "launch first api checklist contract ru": "first_post_checklist_ru",
    "launch first api checklist contract en": "first_post_checklist_en",
    "launch first api recommended start": "recommended_start_platform",
    "launch first api needs keys": "нужны ключи",
    "readiness next action": "Что сделать:",
    "channel checks owner heading": "Что проверить",
    "channel check needed label": "Нужно",
    "channel-specific setup action": "Открыть настройку канала",
    "telegram setup focus path": "/dashboard/settings?focus=channels",
    "integrations setup focus path": "/dashboard/settings?focus=integrations",
    "approval preview": "Предпросмотр перед подтверждением",
    "prepare preview panel": "Preview подготовки каналов",
    "prepare preview no write copy": "drafts ещё не записаны",
    "prepare preview second action": "Создать drafts для проверки",
    "approval preview panel": "Preview перед approval",
    "approval preview no publish": "Approval только фиксирует проверку текста",
    "approval preview next step": "после этого отдельный шаг - “Поставить в расписание”",
    "approval preview second action": "Подтвердить тексты",
    "approval empty text guard": "Перед approval заполните и сохраните текст",
    "bulk approval saved preview guard": "Сначала сохраните правки текста",
    "queue preview panel": "Preview постановки в расписание",
    "queue preview execution permission": "Разрешить исполнение по дате",
    "queue preview worker permission": "worker сможет обработать due API-каналы по дате",
    "queue preview maps guarded": "Карты после queue не публикуются тихо",
    "queue preview second action": "Поставить в расписание после проверки",
    "queue action": "Поставить в расписание",
    "selected post path": "Маршрут выбранных постов",
    "next step selects review posts": "Выделили темы с постами на проверку",
    "selected preview first": "Сначала откройте карточку темы ниже",
    "selected prepared topics stay checked": "LocalOS отметил подготовленные темы",
    "selected api queue warning": "Перед расписанием эти API-каналы не готовы",
    "selected api queue can save": "Queue можно сохранить",
    "selected api worker will not publish": "worker не будет публиковать эти каналы",
    "preview api readiness fallback": "socialChannelReadinessByPlatform",
    "first publishing loop launch": "Первый запуск publishing loop",
    "first launch prepare step": "1. Подготовить каналы",
    "first launch review step": "2. Проверить тексты",
    "first launch approve queue step": "3. Утвердить и поставить",
    "first launch execute step": "4. Исполнить по режиму",
    "first launch primary action": "Подготовить первые публикации",
    "first launch no external send": "Наружу ничего не отправится на первом шаге",
    "prepared posts next action": "Проверьте готовые публикации",
    "prepared posts preview guard": "Главный шаг сейчас — preview и approval",
    "approved posts next action": "Поставьте утверждённые посты в расписание",
    "supervised posts next action": "Откройте контролируемое размещение",
    "published posts learning action": "Соберите результат и улучшите план",
    "queue hero cta safe next step": "Кнопка ведёт к безопасному шагу",
    "queue hero cta safe flow": "preview, approval, queue, контролируемое размещение или сбор результата",
    "queue saved guard feedback": "Queue сохранена, но LocalOS не запустит внешний worker",
    "queue saved scope feedback": "текущий worker смотрит другой business scope",
    "supervised placement state": "Контролируемое размещение",
    "supervised handoff state": "Состояние handoff",
    "supervised payload ready": "payload готов",
    "supervised external task not requested": "task не отправлен во внешний runtime",
    "supervised external task requested": "task отправлен",
    "supervised outbox id": "outbox:",
    "supervised final click forbidden": "финальный клик запрещён",
    "supervised placement owner action": "Подготовить контролируемое размещение",
    "manual placement action": "Отметить размещённым",
    "copy-ready fallback": "Скопировать текст",
    "next-plan recommendations": "Что менять в следующем плане",
    "learning loop status": "Статус learning loop",
    "learning loop publish first": "Результаты появятся после публикаций",
    "learning loop collect reactions": "Соберите реакции или отметьте заявки",
    "recommendation preview": "Предпросмотр изменений плана",
    "apply with confirmation": "Применить после подтверждения",
    "apply approval audit feedback": "Корректировка применена после подтверждения",
    "apply future-only feedback": "только будущие неопубликованные пункты",
    "apply blocked explanation": "Почему нельзя применить сейчас",
    "apply blocked reason contract": "apply_blocked_reason_ru",
    "next-plan fact totals": "Факты для следующего плана",
    "next-plan fact leads": "заявки ${Number(socialRecommendation.learning_readiness.leads",
    "next-plan fact early signals": "лайки ${Number(socialRecommendation.learning_readiness.likes",
    "lead attribution": "Была заявка",
    "inquiry attribution": "Было обращение",
    "primary result attribution group": "Главный результат",
    "primary result learning hint": "LocalOS считает их главным результатом",
    "early signal attribution group": "Ранние сигналы",
    "early signal learning hint": "Лайки и просмотры - только ранний сигнал",
    "comment attribution": "Комментарий",
    "share attribution": "Репост",
    "click attribution": "Клик",
    "like attribution": "Лайк",
    "view attribution": "Просмотр",
    "result nudge": "Есть заявки/обращения",
    "stale recommendation guard": "Рекомендации сброшены",
    "provider proof quality": "social-provider-proof-quality",
    "provider proof external proven": "внешняя публикация подтверждена",
    "provider proof ready metrics": "готово к метрикам",
}


REQUIRED_SAFETY_COPY = {
    "external approval invariant": "Внешние публикации всё равно требуют approval",
    "maps no final click": "Яндекс/2ГИС не нажимают финальную кнопку без человека",
    "supervised task is not autopublish": "финальная публикация остаётся за человеком",
    "api publish is scheduled": "API-публикация запустится только worker",
}


REQUIRED_DATA_CONTRACT = {
    "quick launch test id": 'data-testid="social-quick-launch"',
    "launch checklist test id": "social-launch-checklist",
    "launch checklist compact test id": "social-launch-checklist-compact",
    "publishing next step test id": 'data-testid="social-publishing-next-step"',
    "launch readiness test id": 'data-testid="social-launch-readiness"',
    "goal current step test id": 'data-testid="social-goal-current-step"',
    "goal remaining work test id": 'data-testid="social-goal-remaining-work"',
    "channel queue test id": 'data-testid="social-channel-queue"',
    "first api publish readiness test id": 'data-testid="social-first-api-publish-readiness"',
    "next plan recommendation test id": 'data-testid="social-next-plan-recommendation"',
    "preview before approval test id": 'data-testid="social-preview-before-approval"',
    "prepare preview panel test id": 'data-testid="social-prepare-preview-panel"',
    "approval preview panel test id": 'data-testid="social-approval-preview-panel"',
    "queue preview panel test id": 'data-testid="social-queue-preview-panel"',
    "item prepare preview action": "single-social-prepare",
    "supervised handoff test id": 'data-testid="social-supervised-handoff"',
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
    "openclaw readiness diagnostics": "diagnostics_ru",
    "openclaw final click guard": "OpenClaw не нажимает финальную кнопку публикации",
    "openclaw safe readiness check": "Безопасная проверка: LocalOS ничего не публикует",
    "openclaw owner-ready summary": "Проверка OpenClaw пройдена: можно создать контролируемую задачу",
    "openclaw owner-manual summary": "OpenClaw пока не подключён к этому экрану",
    "openclaw owner-error summary": "LocalOS не смог проверить OpenClaw",
    "openclaw delivery title": "Доставка OpenClaw task не готова",
    "openclaw callback outbox fallback": "callback/outbox для задачи не готов",
    "openclaw callback env action": "OPENCLAW_SOCIAL_SUPERVISED_CALLBACK_URL",
    "openclaw callback receiver path": "/m2m/localos/callbacks",
    "openclaw sandbox bridge blocked copy": "sandbox bridge не подходит для production callback",
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
    "settings setup steps": "Шаги подключения",
    "settings setup steps contract": "setup_steps_ru",
    "settings maps controlled": "Яндекс/2ГИС остаются ручными или контролируемыми",
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
    "telegram readiness refresh copy": "сразу обновит готовность каналов",
}


REQUIRED_SETTINGS_PAGE_COPY = {
    "settings channels focus note": "После сохранения LocalOS обновит готовность каналов для контент-плана",
    "settings channels focus param": "focusTarget === 'channels'",
    "settings telegram focus param": "focusTarget === 'telegram'",
    "settings readiness refresh key": "socialReadinessRefreshKey",
    "settings telegram saved callback": "onSaved={() => setSocialReadinessRefreshKey",
    "settings integrations refresh prop": "readinessRefreshKey={socialReadinessRefreshKey}",
}


REQUIRED_BACKEND_DISPATCH_COPY = {
    "worker first cycle api step": "API: публикация после approval",
    "worker first cycle maps step": "Карты: контроль/вручную без финального клика",
    "worker first cycle manual step": "Ручной fallback или подключение канала",
    "worker first cycle safety notes": "Внешние публикации уходят только из approved/queued постов.",
    "worker first cycle final click guard": "финальный клик публикации не выполняется worker",
}


REQUIRED_BACKEND_GOAL_PROGRESS_COPY = {
    "goal progress schema": "localos_social_goal_progress_v1",
    "goal progress review stage": "review_approval",
    "goal progress plan path": "Контент-план → посты → approval → расписание → исполнение → реакции → корректировка следующего плана.",
    "goal progress primary metric": "Заявки и обращения",
}


REQUIRED_BACKEND_PRODUCTION_READINESS_COPY = {
    "production readiness schema": "localos_social_production_readiness_v1",
    "production readiness scoped cycle": "ready_for_first_scoped_cycle",
    "production readiness dispatch warning": "dispatch_runtime_not_aligned",
    "production readiness api blocker": "api_preflight_blocked",
    "production readiness maps guard": "maps_are_supervised_or_manual",
}


REQUIRED_TELEGRAM_SETTINGS_DATA_CONTRACT = {
    "telegram status endpoint": "/api/business/telegram-bot/status",
    "telegram profile endpoint": "/api/business/profile",
    "telegram chat id payload": "telegram_chat_id",
    "telegram optional token payload": "telegram_bot_token",
    "telegram saved callback": "onSaved?.()",
}


FORBIDDEN_COPY = {
    "silent maps autopublish ru": "Яндекс/2ГИС автопубликация",
    "silent maps autopublish en": "Yandex/2GIS autopublish",
    "owner-facing mixed controlled/manual ru": "Яндекс/2ГИС controlled/manual",
    "owner-facing maps mixed mode ru": "Карты идут через controlled/manual",
    "owner-facing manual controlled mix ru": "ручное/controlled",
    "owner-facing manual controlled mix en": "manual/controlled placement",
    "owner-facing controlled placement en": "controlled placement, not hidden autopublish",
    "owner-facing controlled task ru": "controlled-задач",
    "owner-facing controlled task en": "Controlled task",
    "owner-facing controlled launch ru": "Команды для controlled launch",
    "owner-facing controlled launch en": "Controlled launch env",
    "owner-facing controlled mode ru": "Controlled-режим",
    "owner-facing controlled finish en": "manual or controlled finish",
    "owner-facing raw final click": "final_click: human",
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
    if not SOCIAL_POST_SERVICE.exists():
        print(f"Missing social post service source: {SOCIAL_POST_SERVICE}", file=sys.stderr)
        return 1

    source = CONTENT_PLAN_TAB.read_text(encoding="utf-8")
    settings_source = EXTERNAL_INTEGRATIONS.read_text(encoding="utf-8")
    telegram_settings_source = TELEGRAM_BOT_CREDENTIALS.read_text(encoding="utf-8")
    settings_page_source = SETTINGS_PAGE.read_text(encoding="utf-8")
    service_source = SOCIAL_POST_SERVICE.read_text(encoding="utf-8")
    missing = []
    missing.extend(_assert_contains(source, REQUIRED_COPY))
    missing.extend(_assert_contains(source, REQUIRED_SAFETY_COPY))
    missing.extend(_assert_contains(source, REQUIRED_DATA_CONTRACT))
    missing.extend(_assert_contains(settings_source, REQUIRED_SETTINGS_COPY))
    missing.extend(_assert_contains(settings_source, REQUIRED_SETTINGS_DATA_CONTRACT))
    missing.extend(_assert_contains(telegram_settings_source, REQUIRED_TELEGRAM_SETTINGS_COPY))
    missing.extend(_assert_contains(telegram_settings_source, REQUIRED_TELEGRAM_SETTINGS_DATA_CONTRACT))
    missing.extend(_assert_contains(settings_page_source, REQUIRED_SETTINGS_PAGE_COPY))
    missing.extend(_assert_contains(service_source, REQUIRED_BACKEND_DISPATCH_COPY))
    missing.extend(_assert_contains(service_source, REQUIRED_BACKEND_GOAL_PROGRESS_COPY))
    missing.extend(_assert_contains(service_source, REQUIRED_BACKEND_PRODUCTION_READINESS_COPY))
    forbidden = _assert_absent(source, FORBIDDEN_COPY)
    forbidden.extend(_assert_absent(settings_source, FORBIDDEN_COPY))
    forbidden.extend(_assert_absent(service_source, FORBIDDEN_COPY))

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
