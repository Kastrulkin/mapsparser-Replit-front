#!/usr/bin/env python3
"""Render /dashboard/agents with mocked API data and verify the product cockpit."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


DEFAULT_URL = "http://127.0.0.1:3000/dashboard/agents"
SHEETS_AGENT_BUILDER_SESSION_ID = "builder-session-sheets-telegram"
BROWSER_AGENT_BUILDER_SESSION_ID = "builder-session-browser-telegram"
MOCK_CREATED_AGENT_IDS = set()


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
    method = route.request.method.upper()

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
        blueprints = [
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
        ]
        if "agent-sheets-telegram" in MOCK_CREATED_AGENT_IDS:
            blueprints.append({
                "id": "agent-sheets-telegram",
                "business_id": "biz-1",
                "name": "Google Sheets → Telegram",
                "category": "custom",
                "status": "draft",
                "description": "Проверяет новые строки в Google Sheets и готовит краткий статус владельцу в Telegram.",
                "active_version_id": "ver-sheets-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
                "last_run_status": "",
                "pending_approvals_count": 0,
                "sources_count": 0,
            })
        if "agent-browser-telegram" in MOCK_CREATED_AGENT_IDS:
            blueprints.append({
                "id": "agent-browser-telegram",
                "business_id": "biz-1",
                "name": "Мониторинг сайта конкурента",
                "category": "custom",
                "status": "draft",
                "description": "Через browser use проверяет сайт конкурента и готовит короткий Telegram-отчёт владельцу.",
                "active_version_id": "ver-browser-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
                "last_run_status": "",
                "pending_approvals_count": 0,
                "sources_count": 0,
            })
        await _fulfill(route, {
            "blueprints": blueprints,
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

    if path == "/agent-builder/sessions" and method == "POST":
        body = json.loads(route.request.post_data or "{}")
        message = str(body.get("message") or "")
        message_lower = message.lower()
        if "browser" in message_lower or "сайт конкурент" in message_lower or "example.com" in message_lower:
            await _fulfill(route, {
                "session": _builder_session(
                    session_id=BROWSER_AGENT_BUILDER_SESSION_ID,
                    agent_name="Мониторинг сайта конкурента",
                    message=message,
                    data_sources=["browser_use", "competitor_websites", "telegram", "business_profile"],
                    extraction_rules="Открыть сайт конкурента, найти изменения в акциях, ценах и новых блоках.",
                    processing_rules="Собрать короткий отчёт владельцу, не выполнять внешние действия без подтверждения.",
                    output_format="Короткий Telegram-отчёт владельцу.",
                    missing_questions=[],
                    can_create_draft=True,
                    next_step="create_draft_then_choose_route",
                ),
            })
        else:
            await _fulfill(route, {
                "session": _builder_session(
                    session_id=SHEETS_AGENT_BUILDER_SESSION_ID,
                    agent_name="Google Sheets → Telegram",
                    message="Каждый час бери новые строки из Google Sheets с заказами и отправляй краткий статус владельцу в Telegram после проверки.",
                    data_sources=["google_sheets", "telegram", "business_profile"],
                    extraction_rules="Новые строки, клиент, заказ, статус.",
                    processing_rules="Собирать короткий статус, не отправлять клиентам без подтверждения.",
                    output_format="Короткое сообщение владельцу в Telegram.",
                    missing_questions=[{
                        "key": "orders_columns",
                        "question": "Какие столбцы или критерии в Google Sheets определяют новый заказ?",
                        "reason": "compiled_intent_clarification",
                    }],
                    can_create_draft=False,
                    next_step="answer_clarification",
                ),
            })
        return

    if path == f"/agent-builder/sessions/{SHEETS_AGENT_BUILDER_SESSION_ID}/message" and method == "POST":
        body = json.loads(route.request.post_data or "{}")
        message = str(body.get("message") or "")
        await _fulfill(route, {
            "session": _builder_session(
                session_id=SHEETS_AGENT_BUILDER_SESSION_ID,
                agent_name="Google Sheets → Telegram",
                message=(
                    "Каждый час бери новые строки из Google Sheets с заказами и отправляй краткий статус владельцу "
                    "в Telegram после проверки. "
                    f"{message}"
                ),
                data_sources=["google_sheets", "telegram", "business_profile"],
                extraction_rules="Новые строки, клиент, заказ, статус.",
                processing_rules="Собирать короткий статус, не отправлять клиентам без подтверждения.",
                output_format="Короткое сообщение владельцу в Telegram.",
                missing_questions=[{
                    "key": "google_sheets_target",
                    "question": "Какую Google таблицу и вкладку использовать как источник данных?",
                    "reason": "connection_resolver",
                    "provider": "google_sheets",
                    "role": "source",
                }],
                can_create_draft=True,
                next_step="create_draft_then_choose_route",
            ),
        })
        return

    if path == f"/agent-builder/sessions/{SHEETS_AGENT_BUILDER_SESSION_ID}/create-blueprint" and method == "POST":
        MOCK_CREATED_AGENT_IDS.add("agent-sheets-telegram")
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-sheets-telegram",
                "business_id": "biz-1",
                "name": "Google Sheets → Telegram",
                "category": "custom",
                "status": "draft",
                "description": "Проверяет новые строки в Google Sheets и готовит краткий статус владельцу в Telegram.",
                "active_version_id": "ver-sheets-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "version": {"id": "ver-sheets-telegram", "version_number": 1},
            "session": {"id": SHEETS_AGENT_BUILDER_SESSION_ID, "status": "blueprint_created", "blueprint_id": "agent-sheets-telegram"},
            "post_create_handoff": {
                "schema": "localos_agent_post_create_handoff_v1",
                "status": "needs_connection",
                "workspace_mode": "connections",
                "next_binding_key": "google_sheets_read",
            },
        })
        return

    if path == f"/agent-builder/sessions/{BROWSER_AGENT_BUILDER_SESSION_ID}/create-blueprint" and method == "POST":
        MOCK_CREATED_AGENT_IDS.add("agent-browser-telegram")
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-browser-telegram",
                "business_id": "biz-1",
                "name": "Мониторинг сайта конкурента",
                "category": "custom",
                "status": "draft",
                "description": "Через browser use проверяет сайт конкурента и готовит короткий Telegram-отчёт владельцу.",
                "active_version_id": "ver-browser-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "version": {"id": "ver-browser-telegram", "version_number": 1},
            "session": {"id": BROWSER_AGENT_BUILDER_SESSION_ID, "status": "blueprint_created", "blueprint_id": "agent-browser-telegram"},
            "post_create_handoff": {
                "schema": "localos_agent_post_create_handoff_v1",
                "status": "needs_connection",
                "workspace_mode": "connections",
                "next_binding_key": "telegram_delivery",
            },
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

    if path == "/agent-blueprints/agent-sheets-telegram":
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-sheets-telegram",
                "business_id": "biz-1",
                "name": "Google Sheets → Telegram",
                "category": "custom",
                "status": "draft",
                "description": "Проверяет новые строки в Google Sheets и готовит краткий статус владельцу в Telegram.",
                "active_version_id": "ver-sheets-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "active_version_id": "ver-sheets-telegram",
            "active_version_number": 1,
            "active_version": {"id": "ver-sheets-telegram", "version_number": 1, "status": "draft"},
            "versions": [{"id": "ver-sheets-telegram", "version_number": 1, "status": "draft"}],
            "runs": [],
            "approval_queue": [],
            "learning_events": [],
            "version_events": [],
            "legacy_migration": {},
        })
        return

    if path == "/agent-blueprints/agent-sheets-telegram/review":
        await _fulfill(route, {
            "review": {
                "has_run": False,
                "run_status": "",
                "setup": {
                    "workflow_description": "Проверять новые строки Google Sheets и готовить Telegram-статус.",
                    "extraction_rules": "Дата, клиент, заказ, статус.",
                    "processing_rules": "Не отправлять клиентам без подтверждения.",
                    "output_format": "Короткое сообщение владельцу.",
                },
                "sources": [],
                "used_sources": [],
                "sections": [],
            },
        })
        return

    if path == "/agent-blueprints/agent-sheets-telegram/sources/catalog":
        await _fulfill(route, {"catalog": []})
        return

    if path == "/agent-blueprints/agent-sheets-telegram/integrations":
        await _fulfill(route, {
            "integrations": [],
            "available_integrations": [],
            "provider_catalog": [],
            "external_auth_options": [],
            "binding_status": [{
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "status": "missing",
                "missing_config": ["spreadsheet_id", "sheet_name"],
            }],
            "custom_process": {},
        })
        return

    if path == "/agent-blueprints/agent-browser-telegram":
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-browser-telegram",
                "business_id": "biz-1",
                "name": "Мониторинг сайта конкурента",
                "category": "custom",
                "status": "draft",
                "description": "Через browser use проверяет сайт конкурента и готовит короткий Telegram-отчёт владельцу.",
                "active_version_id": "ver-browser-telegram",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "active_version_id": "ver-browser-telegram",
            "active_version_number": 1,
            "active_version": {"id": "ver-browser-telegram", "version_number": 1, "status": "draft"},
            "versions": [{"id": "ver-browser-telegram", "version_number": 1, "status": "draft"}],
            "runs": [],
            "approval_queue": [],
            "learning_events": [],
            "version_events": [],
            "legacy_migration": {},
        })
        return

    if path == "/agent-blueprints/agent-browser-telegram/review":
        await _fulfill(route, {
            "review": {
                "has_run": False,
                "run_status": "",
                "setup": {
                    "workflow_description": "Через browser use проверять сайт конкурента и готовить Telegram-отчёт.",
                    "extraction_rules": "Изменения цен, акций, новых блоков и офферов.",
                    "processing_rules": "Не отправлять клиентам и не менять внешние системы без подтверждения.",
                    "output_format": "Короткий отчёт владельцу.",
                },
                "sources": [],
                "used_sources": [],
                "sections": [],
            },
        })
        return

    if path == "/agent-blueprints/agent-browser-telegram/sources/catalog":
        await _fulfill(route, {"catalog": []})
        return

    if path == "/agent-blueprints/agent-browser-telegram/integrations":
        await _fulfill(route, {
            "integrations": [],
            "available_integrations": [],
            "provider_catalog": [],
            "external_auth_options": [],
            "binding_status": [{
                "key": "telegram_delivery",
                "provider": "telegram",
                "status": "missing",
                "missing_config": ["telegram_chat_id"],
            }],
            "custom_process": {},
        })
        return

    await _fulfill(route, {})


def _builder_session(
    session_id,
    agent_name,
    message,
    data_sources,
    extraction_rules,
    processing_rules,
    output_format,
    missing_questions,
    can_create_draft,
    next_step,
):
    first_question = missing_questions[0]["question"] if missing_questions else "Деталей достаточно для первой версии."
    return {
        "id": session_id,
        "business_id": "biz-1",
        "status": "draft",
        "messages": [{"role": "user", "content": message}],
        "missing_questions": missing_questions,
        "preview": {
            "understood_task": message,
            "category": "custom",
            "category_label": "Кастомный агент",
            "agent_name": agent_name,
            "data_sources": data_sources,
            "extraction_rules": extraction_rules,
            "processing_rules": processing_rules,
            "output_format": output_format,
            "manual_control": "Ручное подтверждение перед внешним действием.",
            "cost_preview": {"estimated_credits": 3},
            "setup_flow": {
                "schema": "localos_agent_builder_setup_flow_v1",
                "status": "ready" if can_create_draft else "needs_clarification",
                "primary_action": "create_draft" if can_create_draft else "answer_question",
                "next_step": next_step,
                "next_step_title": "Создайте черновик, затем выберите способ выполнения" if can_create_draft else "Ответьте на уточнение",
                "next_step_description": (
                    "Черновик можно создать сейчас. После создания выберите способ выполнения: защищённый способ LocalOS, Maton.ai, встроенный способ LocalOS или ручной режим."
                    if can_create_draft
                    else first_question
                ),
                "can_create_draft": can_create_draft,
                "can_run_preview": False,
                "post_create_status": "needs_connection_choice" if can_create_draft else "needs_clarification",
                "post_create_description": "После создания выберите безопасный маршрут выполнения.",
                "activation_blockers": [],
                "steps": [{
                    "key": "clarify",
                    "label": "Уточнение",
                    "status": "done" if can_create_draft else "active",
                    "description": "Деталей достаточно для первой версии." if can_create_draft else first_question,
                    "questions": missing_questions,
                    "blocking_questions": [] if can_create_draft else missing_questions,
                }],
            },
            "connection_summary": {"items": []},
            "connection_resolver": {"items": []},
            "connection_readiness": {"items": [], "can_create_draft": True},
            "service_intelligence": {"items": [], "can_create_draft": True},
            "connector_intelligence": {"items": [], "can_create_draft": True},
        },
    }


async def run_smoke(url, screenshot):
    manager = async_playwright()
    playwright = await manager.start()
    browser = await playwright.chromium.launch(headless=True)
    try:
        page = await browser.new_page(viewport={"width": 1180, "height": 820}, device_scale_factor=1)
        console_errors = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
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
            "Что делает",
            "Доступы",
            "Тест",
            "Ждёт решения человека",
        ]
        body_lower = body.lower()
        missing = [item for item in required if item.lower() not in body_lower]
        forbidden = [
            "Advanced runtime",
            "OpenClaw",
            "Action ledger",
            "Preflight",
            "Compiled",
            "Policy",
            "Preview run",
            "provider route",
            "runtime truth",
            "capability не подключена",
            "ток.",
        ]
        leaked = [item for item in forbidden if item.lower() in body_lower]

        connection_buttons = page.get_by_role("button", name="Подключения")
        connection_count = await connection_buttons.count()
        if connection_count:
            await connection_buttons.nth(connection_count - 1).click()
            await page.wait_for_timeout(700)
            body_after_connections = await page.locator("body").inner_text(timeout=10000)
            if "Что-то пошло не так" in body_after_connections:
                leaked.append("error boundary after connections click")
            if "Подключения агента" not in body_after_connections:
                missing.append("Подключения агента")

        create_buttons = page.get_by_role("button", name="Создать агента")
        if await create_buttons.count() == 0:
            missing.append("button: Создать агента")
        else:
            await create_buttons.first.click()
            dialog = page.get_by_role("dialog", name="Создать агента")
            await dialog.wait_for(state="visible", timeout=10000)
            prompt_box = dialog.get_by_placeholder(
                "Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
            )
            await prompt_box.fill(
                "Каждый час бери новые строки из Google Sheets с заказами и отправляй краткий статус владельцу в Telegram после проверки."
            )
            await dialog.get_by_role("button", name="Начать диалог").click()
            await page.wait_for_timeout(1000)
            dialog_body = await dialog.inner_text(timeout=10000)
            if "Какие столбцы или критерии в Google Sheets определяют новый заказ?" not in dialog_body:
                missing.append("builder first clarification")
            reply_box = dialog.get_by_placeholder("Ответьте одним сообщением")
            await reply_box.fill(
                "Столбцы: дата, клиент, заказ, статус. Новые строки — добавленные после последнего запуска. "
                "Таблица называется Заказы, лист Новый поток. ID сейчас нет, создай черновик без ID, "
                "а подключение конкретной таблицы оставь следующим шагом в доступах. "
                "Результат — короткое сообщение владельцу в Telegram, без отправки клиентам."
            )
            await dialog.get_by_role("button", name="Ответить").click()
            await page.wait_for_timeout(1000)
            dialog_body = await dialog.inner_text(timeout=10000)
            if "Создать агента" not in dialog_body:
                missing.append("builder draft-ready step")
            draft_button = dialog.get_by_role("button", name="Создать агента")
            if not await draft_button.is_enabled():
                missing.append("enabled dialog draft create button")
            else:
                await draft_button.click()
                await page.wait_for_timeout(1000)
                created_body = await page.locator("body").inner_text(timeout=10000)
                if "Google Sheets → Telegram" not in created_body:
                    missing.append("created Google Sheets Telegram agent")
                if "Агент создан" not in created_body:
                    missing.append("post-create success banner")
                if "Подключения" not in created_body and "Доступы" not in created_body:
                    missing.append("post-create connection step")

            await page.wait_for_timeout(500)
            create_buttons = page.get_by_role("button", name="Создать агента")
            if await create_buttons.count() == 0:
                missing.append("second button: Создать агента")
            else:
                await create_buttons.first.click()
                dialog = page.get_by_role("dialog", name="Создать агента")
                await dialog.wait_for(state="visible", timeout=10000)
                prompt_box = dialog.get_by_placeholder(
                    "Например: мне нужен агент, который проверяет договоры, находит риски и готовит краткий отчёт"
                )
                await prompt_box.fill(
                    "Через browser use открой сайт конкурента https://example.com, проверь изменения цен и акций "
                    "и подготовь сообщение владельцу в Telegram."
                )
                await dialog.get_by_role("button", name="Начать диалог").click()
                await page.wait_for_timeout(1000)
                dialog_body = await dialog.inner_text(timeout=10000)
                if "Создать агента" not in dialog_body:
                    missing.append("browser-use draft-ready step")
                draft_button = dialog.get_by_role("button", name="Создать агента")
                if not await draft_button.is_enabled():
                    missing.append("enabled browser-use draft create button")
                else:
                    await draft_button.click()
                    await page.wait_for_timeout(1000)
                    created_body = await page.locator("body").inner_text(timeout=10000)
                    if "Мониторинг сайта конкурента" not in created_body:
                        missing.append("created browser-use Telegram agent")
                    if "Агент создан" not in created_body:
                        missing.append("browser-use post-create success banner")

        if console_errors:
            leaked.append(f"console errors: {console_errors[:2]}")

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
