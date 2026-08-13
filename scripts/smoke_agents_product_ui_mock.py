#!/usr/bin/env python3
"""Render /dashboard/agents with mocked API data and verify the employee-first agents UI."""

import argparse
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright


DEFAULT_URL = "http://127.0.0.1:3000/dashboard/agents"
SHEETS_AGENT_BUILDER_SESSION_ID = "builder-session-sheets-telegram"
BROWSER_AGENT_BUILDER_SESSION_ID = "builder-session-browser-telegram"
WHATSAPP_AGENT_BUILDER_SESSION_ID = "builder-session-whatsapp-faq"
MOCK_CREATED_AGENT_IDS = set()
MOCK_CONNECTED_AGENT_PROVIDERS = set()


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
                "subscription_tier": "professional",
                "subscription_status": "active",
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
        if "agent-whatsapp-faq" in MOCK_CREATED_AGENT_IDS:
            blueprints.append({
                "id": "agent-whatsapp-faq",
                "business_id": "biz-1",
                "name": "Вопросы WhatsApp → FAQ",
                "category": "custom",
                "status": "draft",
                "description": "Собирает вопросы клиентов из WhatsApp и предлагает новые пункты FAQ после проверки.",
                "active_version_id": "ver-whatsapp-faq",
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

    if path == "/agent-templates":
        await _fulfill(route, {
            "success": True,
            "count": 2,
            "templates": [
                {
                    "key": "daily_owner_digest",
                    "version": "1.0.0",
                    "name": "Ежедневная сводка владельцу",
                    "business_result": "К началу дня владелец видит один короткий список отклонений и задач.",
                    "vertical": "operations",
                    "trigger": "schedule.daily",
                    "required_connections": [],
                    "risk_level": "low",
                    "certification_status": "beta",
                },
                {
                    "key": "partnership_outreach_draft",
                    "version": "1.0.0",
                    "name": "Черновик партнёрского предложения",
                    "business_result": "Менеджер получает персональные черновики первого контакта.",
                    "vertical": "partnerships",
                    "trigger": "manual.run",
                    "required_connections": [],
                    "risk_level": "high",
                    "certification_status": "draft",
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
        elif "whatsapp" in message_lower or "ватсап" in message_lower or "faq" in message_lower:
            await _fulfill(route, {
                "session": _builder_session(
                    session_id=WHATSAPP_AGENT_BUILDER_SESSION_ID,
                    agent_name="Вопросы WhatsApp → FAQ",
                    message=message,
                    data_sources=["whatsapp", "customer_questions", "business_profile"],
                    extraction_rules="Собрать вопросы клиентов из WhatsApp, сгруппировать по темам и выделить повторяющиеся.",
                    processing_rules="Предлагать пункты FAQ как черновик, ничего не отправлять клиентам без подтверждения.",
                    output_format="Список тем и новых пунктов FAQ для проверки.",
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

    if path == f"/agent-builder/sessions/{WHATSAPP_AGENT_BUILDER_SESSION_ID}/create-blueprint" and method == "POST":
        MOCK_CREATED_AGENT_IDS.add("agent-whatsapp-faq")
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-whatsapp-faq",
                "business_id": "biz-1",
                "name": "Вопросы WhatsApp → FAQ",
                "category": "custom",
                "status": "draft",
                "description": "Собирает вопросы клиентов из WhatsApp и предлагает новые пункты FAQ после проверки.",
                "active_version_id": "ver-whatsapp-faq",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "version": {"id": "ver-whatsapp-faq", "version_number": 1},
            "session": {"id": WHATSAPP_AGENT_BUILDER_SESSION_ID, "status": "blueprint_created", "blueprint_id": "agent-whatsapp-faq"},
            "post_create_handoff": {
                "schema": "localos_agent_post_create_handoff_v1",
                "status": "needs_connection",
                "workspace_mode": "connections",
                "next_binding_key": "whatsapp_questions",
            },
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
                "next_binding_key": "browser_use_read",
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
            "execution_mode": "scheduled",
            "execution_contract": {
                "schema": "localos_agent_execution_contract_v1",
                "original_request": "Каждый вечер проверяй новые строки Google Sheets и готовь внутреннюю сводку.",
                "execution_mode": "scheduled",
                "description_complete": True,
                "has_unpublished_changes": False,
                "active": {
                    "role": "active",
                    "version_id": "ver-sheets-telegram",
                    "version_number": 1,
                    "goal": "Проверять новые строки Google Sheets и готовить внутреннюю сводку.",
                    "execution_mode": "scheduled",
                    "trigger": "schedule.daily",
                    "schedule": {"time": "18:00", "timezone": "Europe/Moscow"},
                    "inputs_schema": {"type": "object", "properties": {}},
                    "steps": [
                        {"key": "read_google_sheets", "position": 1, "title": "Прочитать новые строки", "step_type": "capability", "capability": "google_sheets.read_rows"},
                        {"key": "prepare_bounded_result", "position": 2, "title": "Подготовить сводку", "step_type": "artifact", "artifact_type": "agent_output_draft"},
                        {"key": "save_internal_result", "position": 3, "title": "Сохранить результат", "step_type": "artifact", "artifact_type": "agent_final_result"},
                    ],
                    "sources": [{"key": "google_sheets_read", "provider": "google_sheets"}],
                    "connections": {},
                    "expected_result": {"type": "object", "properties": {"summary": {"type": "string"}, "items": {"type": "array"}}},
                    "limits": {"max_items_per_run": 100, "max_model_calls_per_run": 1},
                    "approval_boundaries": [],
                    "validation": {"tested": False, "status": "not_tested"},
                    "is_active": True,
                },
            },
        })
        return

    if path == "/agent-blueprints/agent-sheets-telegram/graph" and method == "GET":
        await _fulfill(route, {
            "success": True,
            "blueprint_id": "agent-sheets-telegram",
            "version_id": "ver-sheets-telegram",
            "graph": {
                "schema": "localos_agent_workflow_graph_v1",
                "nodes": [
                    {"id": "read_google_sheets", "kind": "capability", "config": {"key": "read_google_sheets", "type": "capability", "capability": "google_sheets.read_rows", "payload": {}}},
                    {"id": "prepare_bounded_result", "kind": "bounded_model_call", "config": {"key": "prepare_bounded_result", "type": "artifact", "bounded_model_call": True, "model_preset": "sheet_business_digest", "payload": {"source_scope": ["google_sheets"]}}},
                    {"id": "save_internal_result", "kind": "artifact", "config": {"key": "save_internal_result", "type": "artifact"}},
                ],
                "edges": [
                    {"id": "a", "source": "read_google_sheets", "target": "prepare_bounded_result"},
                    {"id": "b", "source": "prepare_bounded_result", "target": "save_internal_result"},
                ],
            },
            "settings": {"execution_mode": "scheduled", "trigger": "schedule.daily", "schedule": {"time": "18:00", "timezone": "Europe/Moscow"}, "limits": {"max_items_per_run": 100, "max_model_calls_per_run": 1}},
            "editor_registry": {
                "triggers": [
                    {"key": "manual", "title": "По команде", "trigger": "manual.run", "execution_mode": "manual"},
                    {"key": "daily", "title": "Каждый день", "trigger": "schedule.daily", "execution_mode": "scheduled"},
                    {"key": "weekly", "title": "Раз в неделю", "trigger": "schedule.weekly", "execution_mode": "scheduled"},
                ],
                "sources": [
                    {"key": "business_profile", "title": "Профиль бизнеса"},
                    {"key": "reviews", "title": "Отзывы"},
                    {"key": "services", "title": "Услуги"},
                    {"key": "google_sheets", "title": "Google Sheets — только чтение"},
                ],
                "checks": [
                    {"key": "required_data", "title": "Остановиться, если данных нет"},
                    {"key": "deduplicate", "title": "Убрать повторы"},
                    {"key": "limit_items", "title": "Ограничить объём"},
                ],
                "ai_presets": [
                    {"key": "owner_digest", "title": "Сводка владельцу"},
                    {"key": "sheet_business_digest", "title": "Сводка строк таблицы"},
                ],
                "approvals": [
                    {"key": "none", "title": "Не требуется для внутреннего результата"},
                    {"key": "manual_review", "title": "Проверить результат человеком"},
                ],
                "results": [
                    {"key": "internal_result", "title": "Сохранить результат в LocalOS"},
                    {"key": "review_queue", "title": "Сохранить в очередь проверки"},
                ],
                "limits": {
                    "max_items_per_run": {"title": "Элементов за запуск", "minimum": 1, "maximum": 500, "default": 100},
                    "max_model_calls_per_run": {"title": "AI-шагов за запуск", "minimum": 1, "maximum": 1, "default": 1},
                },
            },
        })
        return

    if path == "/agent-blueprints/agent-sheets-telegram/graph/candidate" and method == "POST":
        await _fulfill(route, {"success": True, "candidate_version": {"id": "ver-sheets-telegram-2", "version_number": 2}, "active_version_unchanged": True, "next_step": "run_preview"})
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

    if path == "/agent-blueprints/agent-browser-telegram/integrations" and method == "POST":
        MOCK_CONNECTED_AGENT_PROVIDERS.add("agent-browser-telegram:browser_use")
        await _fulfill(route, {
            "integration": {"id": "browser-use-integration-1", "provider": "browser_use", "status": "active"},
            "post_connect_handoff": {
                "schema": "localos_agent_post_connect_handoff_v1",
                "status": "connected",
                "workspace_mode": "connections",
            },
        })
        return

    if path == "/agent-blueprints/agent-browser-telegram/integrations":
        connected = "agent-browser-telegram:browser_use" in MOCK_CONNECTED_AGENT_PROVIDERS
        await _fulfill(route, {
            "integrations": [{
                "id": "browser-use-integration-1",
                "provider": "browser_use",
                "display_name": "Browser use",
                "status": "active",
                "config": {"target_urls": ["https://example.com"], "mode": "openclaw_browser_boundary"},
                "limits": {"daily_page_check_cap": 50},
            }] if connected else [],
            "available_integrations": [],
            "provider_catalog": [{
                "provider": "browser_use",
                "title": "Browser use",
                "status": "available",
            }],
            "external_auth_options": [],
            "binding_status": [
                {
                    "key": "browser_use_read",
                    "provider": "browser_use",
                    "status": "connected" if connected else "missing",
                    "direction": "external_read",
                    "capability": "browser_use.read_page",
                    "missing_config": [] if connected else ["target_urls"],
                    "approval_required": True,
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "status": "missing",
                    "missing_config": ["telegram_chat_id"],
                },
            ],
            "custom_process": {},
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq":
        await _fulfill(route, {
            "blueprint": {
                "id": "agent-whatsapp-faq",
                "business_id": "biz-1",
                "name": "Вопросы WhatsApp → FAQ",
                "category": "custom",
                "status": "draft",
                "description": "Собирает вопросы клиентов из WhatsApp и предлагает новые пункты FAQ после проверки.",
                "active_version_id": "ver-whatsapp-faq",
                "active_version_number": 1,
                "latest_version_number": 1,
            },
            "active_version_id": "ver-whatsapp-faq",
            "active_version_number": 1,
            "active_version": {"id": "ver-whatsapp-faq", "version_number": 1, "status": "draft"},
            "versions": [{"id": "ver-whatsapp-faq", "version_number": 1, "status": "draft"}],
            "runs": [],
            "approval_queue": [],
            "learning_events": [],
            "version_events": [],
            "legacy_migration": {},
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/review":
        await _fulfill(route, {
            "review": {
                "has_run": False,
                "run_status": "",
                "setup": {
                    "workflow_description": "Собирать вопросы клиентов из WhatsApp и готовить FAQ-черновик.",
                    "extraction_rules": "Вопросы, темы, повторяющиеся формулировки и контекст услуги.",
                    "processing_rules": "Не отвечать клиентам без подтверждения.",
                    "output_format": "Список новых пунктов FAQ.",
                },
                "sources": [],
                "used_sources": [],
                "sections": [],
            },
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/sources/catalog":
        await _fulfill(route, {"catalog": []})
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/integrations" and method == "POST":
        MOCK_CONNECTED_AGENT_PROVIDERS.add("agent-whatsapp-faq:whatsapp")
        await _fulfill(route, {
            "integration": {"id": "whatsapp-integration-1", "provider": "whatsapp", "status": "active"},
            "post_connect_handoff": {
                "schema": "localos_agent_post_connect_handoff_v1",
                "status": "connected",
                "workspace_mode": "connections",
            },
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/integrations":
        connected = "agent-whatsapp-faq:whatsapp" in MOCK_CONNECTED_AGENT_PROVIDERS
        await _fulfill(route, {
            "integrations": [{
                "id": "whatsapp-integration-1",
                "provider": "whatsapp",
                "display_name": "WhatsApp",
                "status": "active",
                "config": {"channel_mode": "whatsapp_business"},
                "limits": {"daily_message_cap": 50},
            }] if connected else [],
            "available_integrations": [],
            "provider_catalog": [{
                "provider": "whatsapp",
                "title": "WhatsApp",
                "status": "available",
            }],
            "external_auth_options": [],
            "binding_status": [{
                "key": "whatsapp_questions",
                "provider": "whatsapp",
                "status": "connected" if connected else "missing",
                "direction": "trigger",
                "trigger": "whatsapp.message.received",
                "missing_config": [] if connected else ["channel_mode"],
                "approval_required": True,
            }],
            "custom_process": {},
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/preflight" and method == "POST":
        await _fulfill(route, {
            "success": True,
            "blueprint_id": "agent-whatsapp-faq",
            "blueprint_version_id": "ver-whatsapp-faq",
            "preflight": {
                "status": "ready",
                "ready": True,
                "items": [{
                    "key": "whatsapp_questions",
                    "provider": "whatsapp",
                    "status": "ready",
                    "resolution": "agent_integration",
                    "required": True,
                    "missing_config": [],
                }],
                "missing": [],
                "missing_count": 0,
                "next_action": "",
            },
            "connection_plan": {
                "items": [{
                    "key": "whatsapp_questions",
                    "provider": "whatsapp",
                    "binding_status": "ready",
                    "action": "ready",
                }],
            },
            "next_binding_key": "",
            "preview_run_gate": {
                "schema": "localos_agent_preview_run_gate_v1",
                "status": "ready",
                "can_preview_run": True,
                "external_side_effects_allowed": False,
                "approval_required_for_external_actions": True,
                "next_step": "start_preview_run",
            },
            "preview_input": {"schema": "localos_agent_preview_input_v1", "preview_mode": True},
            "can_start": True,
        })
        return

    if path == "/agent-blueprints/agent-whatsapp-faq/runs" and method == "POST":
        await _fulfill(route, {
            "success": True,
            "run": {
                "id": "run-whatsapp-faq-preview",
                "blueprint_id": "agent-whatsapp-faq",
                "version_id": "ver-whatsapp-faq",
                "status": "completed",
                "started_at": "2026-06-21 11:50",
                "completed_at": "2026-06-21 11:50",
                "input_json": {"schema": "localos_agent_preview_input_v1", "preview_mode": True},
                "observability": {
                    "preview_summary": {
                        "schema": "localos_agent_preview_summary_v1",
                        "preflight_ready": True,
                        "external_actions_performed": False,
                        "completed_steps": ["collect_questions", "group_topics", "draft_faq"],
                        "next_step": "review_result",
                    },
                },
                "steps": [{
                    "id": "step-whatsapp-faq",
                    "step_key": "draft_faq",
                    "step_type": "artifact",
                    "status": "completed",
                    "output_json": {
                        "topics": ["Запись", "Цены", "Подготовка"],
                        "external_dispatch_performed": False,
                    },
                }],
                "artifacts": [{
                    "id": "artifact-whatsapp-faq",
                    "artifact_type": "agent_preview_result",
                    "title": "Черновик FAQ по WhatsApp-вопросам",
                    "payload_json": {"items": ["Как записаться?", "Какие цены?", "Как подготовиться?"]},
                }],
                "approvals": [],
            },
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
        failed_requests = []
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.on("requestfailed", lambda request: failed_requests.append(f"{request.method} {request.url}: {request.failure}"))
        await page.route("**/api/**", _handle_mock_api)
        await page.add_init_script(
            "localStorage.setItem('auth_token','mock-token');"
            "localStorage.setItem('selectedBusinessId','biz-1');"
            "localStorage.setItem('dashboard_sidebar_collapsed','true');"
            "localStorage.setItem('language','ru');"
        )
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.get_by_text("Автоматизация задач", exact=True).wait_for(state="visible", timeout=60000)
        await page.wait_for_timeout(500)
        body = await page.locator("body").inner_text(timeout=10000)

        required = [
            "Автоматизация задач",
            "Настроить задачу",
            "Готовые практики",
            "Ежедневная сводка владельцу",
            "Просмотр бесплатный и ничего не создаёт",
            "Сегодня",
            "Нужны действия",
            "Автоматизированные задачи",
            "Цель агента",
            "Готовность процесса",
            "Последняя работа",
            "Следующая работа",
            "Требует вашего внимания",
            "Подтвердить отправку",
            "Настройки",
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
            "Daily responsibilities",
            "Current status",
            "Test Result",
            "Approve",
            "Reject",
            "ток.",
        ]
        leaked = [item for item in forbidden if item.lower() in body_lower]

        primary_actions = page.get_by_role("button", name="Подтвердить отправку")
        if await primary_actions.count() != 1:
            missing.append("exactly one selected employee primary action")

        if "последняя работа" not in body_lower:
            missing.append("embedded employee history story")
        if "цель агента" not in body_lower:
            missing.append("employee responsibilities")
        if "Open" in body:
            leaked.append("old row action label")

        create_buttons = page.get_by_role("button", name="Настроить задачу")
        if await create_buttons.count() == 0:
            missing.append("button: Настроить задачу")
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
            confirm_mode = dialog.get_by_role("button", name="Подтвердить тип", exact=True)
            if await confirm_mode.count():
                await confirm_mode.click()
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
            confirm_mode = dialog.get_by_role("button", name="Подтвердить тип", exact=True)
            if await confirm_mode.count():
                await confirm_mode.click()
            draft_button = dialog.get_by_role("button", name="Создать агента и подключить сервисы", exact=True)
            for _ in range(20):
                if await draft_button.is_enabled():
                    break
                await page.wait_for_timeout(250)
            if not await draft_button.is_enabled():
                missing.append("enabled dialog draft create button")
            else:
                await draft_button.click()
                await page.wait_for_timeout(1000)
                created_body = await page.locator("body").inner_text(timeout=10000)
                created_body_lower = created_body.lower()
                if "Google Sheets → Telegram" not in created_body:
                    missing.append("created Google Sheets Telegram agent")
                if "цель агента" not in created_body_lower or "готовность процесса" not in created_body_lower:
                    missing.append("created agent opened overview")
                if (
                    "approval_required:" in created_body_lower
                    or "next questions:" in created_body_lower
                    or "правки: ; формат:" in created_body_lower
                ):
                    leaked.append("raw payload dump visible in normal agent workspace")
                if "Агент создан" in created_body:
                    leaked.append("old post-create banner still visible")
                scenario_tab = page.get_by_text("Сценарий", exact=True)
                if await scenario_tab.count() == 0:
                    missing.append("scenario tab")
                else:
                    await scenario_tab.last.click()
                    await page.wait_for_timeout(700)
                    configure_process = page.get_by_role("button", name="Настроить процесс", exact=True)
                    if await configure_process.count() == 0:
                        missing.append("visual editor entry")
                    else:
                        await configure_process.focus()
                        await page.keyboard.press("Enter")
                        await page.wait_for_timeout(500)
                        editor_body = await page.locator("body").inner_text(timeout=10000)
                        for label in [
                            "Какие данные использовать",
                            "Проверки перед AI",
                            "Как обработать",
                            "Ручная проверка",
                            "Куда сохранить",
                            "Код, произвольные провайдеры",
                        ]:
                            if label not in editor_body:
                                missing.append(f"visual editor: {label}")

        known_telemetry_failure = failed_requests and all("hdrc.yandex.net" in item for item in failed_requests)
        if console_errors and not known_telemetry_failure:
            leaked.append(f"console errors: {console_errors[:2]}")
        if failed_requests and not known_telemetry_failure:
            leaked.append(f"failed requests: {failed_requests[:3]}")

        if screenshot:
            path = Path(screenshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(path), full_page=True)
            await page.set_viewport_size({"width": 390, "height": 844})
            await page.wait_for_timeout(300)
            overflow = await page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if overflow > 2:
                leaked.append(f"mobile horizontal overflow: {overflow}px")
            mobile_path = path.with_name(f"{path.stem}-mobile{path.suffix}")
            await page.screenshot(path=str(mobile_path), full_page=True)

        if missing or leaked:
            print("Agents product UI mock smoke failed")
            if missing:
                print("Missing:", ", ".join(missing))
            if leaked:
                print("Leaked:", ", ".join(leaked))
            return 1

        print("OK: agents workspace v2 mock rendered")
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
