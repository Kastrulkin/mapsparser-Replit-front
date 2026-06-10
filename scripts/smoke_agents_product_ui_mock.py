#!/usr/bin/env python3
"""Render /dashboard/agents with mocked API data and verify the product cockpit."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


DEFAULT_URL = "http://127.0.0.1:3000/dashboard/agents"


def _json_response(body):
    return json.dumps(body, ensure_ascii=False)


async def _fulfill(route, body):
    await route.fulfill(
        status=200,
        content_type="application/json",
        body=_json_response(body),
    )


async def _handle_mock_api(route):
    parsed = urlparse(route.request.url)
    path = parsed.path
    if path.startswith("/api"):
        path = path[4:] or "/"

    if path == "/auth/me":
        await _fulfill(route, {
            "user": {
                "id": "user-1",
                "email": "owner@example.com",
                "name": "Demo Owner",
                "is_superadmin": False,
            },
            "businesses": [{
                "id": "biz-1",
                "name": "Riderra (Tallinn)",
                "description": "Demo business",
                "moderation_status": "active",
            }],
        })
        return

    if path == "/agent-blueprints":
        await _fulfill(route, {
            "blueprints": [
                {
                    "id": "agent-reminder",
                    "business_id": "biz-1",
                    "name": "Напоминание о записи",
                    "category": "communications",
                    "status": "active",
                    "description": "Напоминает клиентам о записи, готовит текст и ждёт подтверждение перед отправкой.",
                    "active_version_id": "ver-1",
                    "active_version_number": 3,
                    "latest_version_number": 3,
                    "active_goal": "Напомнить клиенту о записи и предложить пакет после релевантной услуги.",
                    "last_run_id": "run-1",
                    "last_run_status": "waiting_approval",
                    "last_run_started_at": "2026-06-10 11:40",
                    "pending_approvals_count": 1,
                    "sources_count": 4,
                    "voice": {"id": "voice-1", "name": "Спокойный администратор"},
                },
                {
                    "id": "agent-table",
                    "business_id": "biz-1",
                    "name": "Telegram → Google Sheets",
                    "category": "tables",
                    "status": "draft",
                    "description": "Собирает входящие заявки из Telegram и готовит строку для таблицы после проверки.",
                    "active_version_id": "ver-2",
                    "active_version_number": 1,
                    "latest_version_number": 1,
                    "last_run_status": "completed",
                    "pending_approvals_count": 0,
                    "sources_count": 2,
                },
                {
                    "id": "agent-review",
                    "business_id": "biz-1",
                    "name": "Черновик ответа на отзывы",
                    "category": "reviews",
                    "status": "paused",
                    "description": "Готовит черновики ответов на отзывы с учётом голоса бизнеса.",
                    "active_version_id": "ver-3",
                    "active_version_number": 2,
                    "latest_version_number": 2,
                    "last_run_status": "completed",
                    "pending_approvals_count": 0,
                    "sources_count": 3,
                },
            ],
        })
        return

    if path == "/agent-blueprints/legacy-migration-plan":
        await _fulfill(route, {"migration_plan": {"legacy_agents": [], "business_settings": {"fields": {}}}})
        return

    if path == "/business/biz-1/ai-agents/manage":
        await _fulfill(route, {
            "agents": [{
                "id": "voice-1",
                "name": "Спокойный администратор",
                "type": "voice",
                "description": "Дружелюбный и короткий стиль общения.",
                "is_active": True,
            }],
        })
        return

    if path == "/agent-blueprints/agent-reminder":
        await _fulfill(route, {
            "active_version_id": "ver-1",
            "active_version_number": 3,
            "active_version": {"id": "ver-1", "version_number": 3, "status": "active"},
            "versions": [{
                "id": "ver-1",
                "version_number": 3,
                "status": "active",
                "goal": "Напоминание клиентам",
                "created_at": "2026-06-10",
            }],
            "runs": [{"id": "run-1", "status": "waiting_approval", "started_at": "2026-06-10 11:40"}],
            "approval_queue": [{
                "id": "approval-1",
                "run_id": "run-1",
                "title": "Подтвердить отправку 7 напоминаний",
                "status": "pending",
                "approval_type": "external_delivery",
                "requested_at": "2026-06-10 11:42",
                "payload_json": {"count": 7},
            }],
            "learning_events": [{
                "trigger_type": "manual_edit",
                "candidate_version_number": 3,
                "feedback": "Сделать текст короче.",
                "created_at": "2026-06-10",
            }],
            "version_events": [{
                "action": "activated",
                "active_version_number": 3,
                "reason": "Активировано после проверки.",
                "created_at": "2026-06-10",
            }],
            "legacy_migration": {},
        })
        return

    if path == "/agent-blueprints/agent-reminder/review":
        await _fulfill(route, {
            "review": {
                "has_run": True,
                "run_status": "waiting_approval",
                "setup": {
                    "workflow_description": "Напомнить клиентам о записи",
                    "extraction_rules": "Клиенты с записью завтра",
                    "processing_rules": "Не отправлять без подтверждения",
                    "output_format": "Черновики сообщений",
                },
                "sources": [{"source_type": "internal", "internal_source": "appointments", "name": "Записи"}],
                "used_sources": [],
                "sections": [],
            },
        })
        return

    if path == "/agent-blueprints/agent-reminder/sources/catalog":
        await _fulfill(route, {"catalog": []})
        return

    if path == "/agent-blueprints/agent-reminder/integrations":
        await _fulfill(route, {
            "integrations": [],
            "available_integrations": [],
            "provider_catalog": [],
            "external_auth_options": [],
            "binding_status": [],
            "custom_process": {},
        })
        return

    await _fulfill(route, {})


async def run_smoke(url, screenshot):
    manager = async_playwright()
    playwright = await manager.start()
    browser = await playwright.chromium.launch(headless=True)
    try:
        page = await browser.new_page(viewport={"width": 1180, "height": 820}, device_scale_factor=1)
        await page.route("**/api/**", _handle_mock_api)
        await page.add_init_script(
            "localStorage.setItem('auth_token','mock-token');"
            "localStorage.setItem('selectedBusinessId','biz-1');"
            "localStorage.setItem('dashboard_sidebar_collapsed','true');"
        )
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2500)
        body = await page.locator("body").inner_text(timeout=10000)

        required = [
            "Мои агенты",
            "Создать агента",
            "Проверить решения",
            "Следующий шаг",
            "Что делает агент",
            "Готовность",
            "Ручной контроль",
        ]
        missing = [item for item in required if item not in body]
        forbidden = [
            "Advanced runtime",
            "OpenClaw",
            "Action ledger",
            "runtime truth",
            "capability не подключена",
            "Preview run",
        ]
        leaked = [item for item in forbidden if item in body]

        if screenshot:
            path = Path(screenshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(path), full_page=True)

        if missing or leaked:
            print("Agents product UI mock smoke failed")
            if missing:
                print("Missing:", ", ".join(missing))
            if leaked:
                print("Leaked:", ", ".join(leaked))
            return 1

        print("OK: agents product UI mock cockpit rendered")
        if screenshot:
            print(f"Screenshot: {screenshot}")
        return 0
    finally:
        await browser.close()
        await playwright.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--screenshot", default="")
    args = parser.parse_args()
    return asyncio.run(run_smoke(args.url, args.screenshot))


if __name__ == "__main__":
    raise SystemExit(main())
