#!/usr/bin/env python3
"""Serve built frontend assets with a mocked agents API for browser QA."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "frontend" / "dist"

STATE = {
    "created_agents": set(),
    "connected": set(),
}


def _session(session_id: str, *, name: str, sources: list[str], can_create: bool = True) -> dict:
    return {
        "id": session_id,
        "status": "draft",
        "business_id": "biz-1",
        "category": "custom",
        "messages": [],
        "missing_questions": [] if can_create else [
            {
                "key": "orders_columns",
                "question": "Какие столбцы в таблице считать новыми заказами?",
                "reason": "compiled_intent_clarification",
            }
        ],
        "preview": {
            "agent_name": name,
            "goal": name,
            "data_sources": sources,
            "extraction_rules": "Собрать новые факты из подключённых источников.",
            "processing_rules": "Подготовить черновик результата, ничего не отправлять без подтверждения.",
            "output_format": "Короткий черновик для владельца.",
            "required_connectors": [
                {"provider": source, "key": f"{source}_read"}
                for source in sources
                if source in {"google_sheets", "browser_use", "whatsapp", "telegram"}
            ],
            "setup_flow": {
                "status": "ready_for_draft" if can_create else "needs_clarification",
                "primary_action": "create_draft" if can_create else "answer_question",
                "can_create_draft": can_create,
                "next_step_title": "Создать черновик агента" if can_create else "Ответьте на вопрос",
                "next_step_description": "После создания подключите источники и запустите проверку.",
            },
        },
    }


def _blueprint(agent_id: str, *, name: str, description: str, version_id: str) -> dict:
    return {
        "id": agent_id,
        "business_id": "biz-1",
        "name": name,
        "category": "custom",
        "status": "draft",
        "description": description,
        "active_version_id": version_id,
        "active_version_number": 1,
        "latest_version_number": 1,
    }


def _blueprints() -> list[dict]:
    result = [
        _blueprint(
            "agent-reminder",
            name="Напоминание о записи",
            description="Готовит напоминания клиентам и ждёт подтверждение перед отправкой.",
            version_id="ver-reminder",
        ),
    ]
    if "agent-browser-telegram" in STATE["created_agents"]:
        result.append(
            _blueprint(
                "agent-browser-telegram",
                name="Мониторинг сайта конкурента",
                description="Через browser use проверяет сайт конкурента и готовит Telegram-отчёт.",
                version_id="ver-browser-telegram",
            )
        )
    if "agent-whatsapp-faq" in STATE["created_agents"]:
        result.append(
            _blueprint(
                "agent-whatsapp-faq",
                name="Вопросы WhatsApp → FAQ",
                description="Собирает вопросы клиентов из WhatsApp и предлагает пункты FAQ.",
                version_id="ver-whatsapp-faq",
            )
        )
    return result


def _integration_payload(agent_id: str) -> dict:
    connected = STATE["connected"]
    if agent_id == "agent-browser-telegram":
        browser_connected = f"{agent_id}:browser_use" in connected
        telegram_connected = f"{agent_id}:telegram" in connected
        return {
            "integrations": [
                {
                    "id": "browser-use-integration-1",
                    "provider": "browser_use",
                    "display_name": "Browser use",
                    "status": "active",
                    "config": {"target_urls": ["https://example.com"], "mode": "openclaw_browser_boundary"},
                    "limits": {"daily_page_check_cap": 50},
                }
            ] if browser_connected else [],
            "available_integrations": [],
            "provider_catalog": [
                {"provider": "browser_use", "title": "Browser use", "status": "available"},
                {"provider": "telegram", "title": "Telegram", "status": "available"},
            ],
            "external_auth_options": [],
            "binding_status": [
                {
                    "key": "browser_use_read",
                    "provider": "browser_use",
                    "status": "connected" if browser_connected else "missing",
                    "missing_config": [] if browser_connected else ["target_urls"],
                },
                {
                    "key": "telegram_delivery",
                    "provider": "telegram",
                    "status": "connected" if telegram_connected else "missing",
                    "missing_config": [],
                },
            ],
            "custom_process": {},
        }
    if agent_id == "agent-whatsapp-faq":
        whatsapp_connected = f"{agent_id}:whatsapp" in connected
        return {
            "integrations": [
                {
                    "id": "whatsapp-integration-1",
                    "provider": "whatsapp",
                    "display_name": "WhatsApp",
                    "status": "active",
                    "config": {"channel_mode": "manual_whatsapp"},
                    "limits": {"daily_message_cap": 50},
                }
            ] if whatsapp_connected else [],
            "available_integrations": [],
            "provider_catalog": [{"provider": "whatsapp", "title": "WhatsApp", "status": "available"}],
            "external_auth_options": [],
            "binding_status": [
                {
                    "key": "whatsapp_delivery",
                    "provider": "whatsapp",
                    "status": "connected" if whatsapp_connected else "missing",
                    "missing_config": [] if whatsapp_connected else ["channel_mode"],
                }
            ],
            "custom_process": {},
        }
    return {
        "integrations": [],
        "available_integrations": [],
        "provider_catalog": [],
        "external_auth_options": [],
        "binding_status": [],
        "custom_process": {},
    }


def _preflight_payload(agent_id: str) -> dict:
    integrations = _integration_payload(agent_id)["binding_status"]
    ready = all(item.get("status") == "connected" for item in integrations)
    return {
        "success": True,
        "blueprint_id": agent_id,
        "blueprint_version_id": "ver-browser-telegram" if agent_id == "agent-browser-telegram" else "ver-whatsapp-faq",
        "preflight": {
            "ready": ready,
            "status": "ready" if ready else "blocked",
            "items": integrations,
            "missing": [item for item in integrations if item.get("status") != "connected"],
            "missing_count": len([item for item in integrations if item.get("status") != "connected"]),
        },
        "connection_plan": {"items": integrations},
        "preview_run_gate": {
            "status": "ready" if ready else "blocked",
            "can_preview_run": ready,
            "external_side_effects_allowed": False,
            "next_step": "start_preview_run" if ready else "connect_required_integrations",
        },
        "preview_input": {
            "schema": "localos_agent_preview_input_v1",
            "preview_mode": True,
            "external_side_effects_allowed": False,
        },
        "can_start": ready,
    }


def _json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return None

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            return {}

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        api_path = path[4:] if path.startswith("/api") else path
        if api_path == "/auth/me":
            _json_response(self, {
                "user": {"id": "user-1", "email": "owner@example.com", "name": "Demo Owner"},
                "businesses": [{"id": "biz-1", "name": "Demo Business", "moderation_status": "active"}],
            })
            return None
        if api_path == "/agent-blueprints":
            _json_response(self, {"blueprints": _blueprints()})
            return None
        if api_path == "/agent-blueprints/legacy-migration-plan":
            _json_response(self, {"migration_plan": {"legacy_agents": [], "business_settings": {"fields": {}}}})
            return None
        if api_path == "/business/biz-1/ai-agents/manage":
            _json_response(self, {"agents": []})
            return None
        if api_path.endswith("/sources/catalog"):
            _json_response(self, {"success": True, "catalog": []})
            return None
        if api_path.endswith("/review"):
            agent_id = api_path.split("/")[2]
            _json_response(self, {
                "success": True,
                "review": {
                    "has_run": False,
                    "setup": {
                        "workflow_description": "Проверить источник и подготовить черновик.",
                        "extraction_rules": "Найти изменения и важные факты.",
                        "processing_rules": "Не выполнять внешние действия без подтверждения.",
                        "output_format": "Короткий отчёт владельцу.",
                    },
                    "sources": [],
                    "used_sources": [],
                    "sections": [],
                },
            })
            return None
        if api_path.endswith("/integrations"):
            agent_id = api_path.split("/")[2]
            _json_response(self, _integration_payload(agent_id))
            return None
        if api_path.startswith("/agent-blueprints/"):
            agent_id = api_path.split("/")[2]
            match = next((item for item in _blueprints() if item["id"] == agent_id), None)
            if match:
                version_id = match["active_version_id"]
                _json_response(self, {
                    "blueprint": match,
                    "active_version_id": version_id,
                    "active_version_number": 1,
                    "active_version": {"id": version_id, "version_number": 1, "status": "draft"},
                    "versions": [{"id": version_id, "version_number": 1, "status": "draft"}],
                    "runs": [],
                    "approval_queue": [],
                    "learning_events": [],
                    "version_events": [],
                    "legacy_migration": {},
                })
                return None
        self._serve_static(path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        api_path = path[4:] if path.startswith("/api") else path
        body = self._body()
        if api_path == "/auth/login":
            _json_response(self, {
                "success": True,
                "token": "mock-token",
                "user": {"id": "user-1", "email": body.get("email") or "owner@example.com", "name": "Demo Owner"},
                "businesses": [{"id": "biz-1", "name": "Demo Business", "moderation_status": "active"}],
            })
            return None
        if api_path == "/agent-builder/sessions":
            text = str(body.get("message") or "").lower()
            if "whatsapp" in text or "ватсап" in text:
                _json_response(self, {"session": _session(
                    "builder-session-whatsapp",
                    name="Вопросы WhatsApp → FAQ",
                    sources=["whatsapp", "customer_questions", "business_profile"],
                )})
                return None
            _json_response(self, {"session": _session(
                "builder-session-browser",
                name="Мониторинг сайта конкурента",
                sources=["browser_use", "competitor_websites", "telegram", "business_profile"],
            )})
            return None
        if api_path == "/agent-builder/sessions/builder-session-browser/create-blueprint":
            STATE["created_agents"].add("agent-browser-telegram")
            _json_response(self, {
                "success": True,
                "blueprint": _blueprint(
                    "agent-browser-telegram",
                    name="Мониторинг сайта конкурента",
                    description="Через browser use проверяет сайт конкурента и готовит Telegram-отчёт.",
                    version_id="ver-browser-telegram",
                ),
                "version": {"id": "ver-browser-telegram", "version_number": 1},
                "session": {"id": "builder-session-browser", "status": "blueprint_created", "blueprint_id": "agent-browser-telegram"},
                "post_create_handoff": {"status": "needs_connection", "workspace_mode": "connections", "next_binding_key": "browser_use_read"},
            }, 201)
            return None
        if api_path == "/agent-builder/sessions/builder-session-whatsapp/create-blueprint":
            STATE["created_agents"].add("agent-whatsapp-faq")
            _json_response(self, {
                "success": True,
                "blueprint": _blueprint(
                    "agent-whatsapp-faq",
                    name="Вопросы WhatsApp → FAQ",
                    description="Собирает вопросы клиентов из WhatsApp и предлагает пункты FAQ.",
                    version_id="ver-whatsapp-faq",
                ),
                "version": {"id": "ver-whatsapp-faq", "version_number": 1},
                "session": {"id": "builder-session-whatsapp", "status": "blueprint_created", "blueprint_id": "agent-whatsapp-faq"},
                "post_create_handoff": {"status": "needs_connection", "workspace_mode": "connections", "next_binding_key": "whatsapp_delivery"},
            }, 201)
            return None
        if api_path.endswith("/integrations"):
            agent_id = api_path.split("/")[2]
            provider = str(body.get("provider") or "").strip()
            STATE["connected"].add(f"{agent_id}:{provider}")
            _json_response(self, {
                "success": True,
                "integration": {"id": f"{provider}-integration-1", "provider": provider, "status": "active"},
                "post_connect_handoff": {"status": "connected", "workspace_mode": "connections"},
            }, 201)
            return None
        if api_path.endswith("/preflight"):
            agent_id = api_path.split("/")[2]
            _json_response(self, _preflight_payload(agent_id))
            return None
        if api_path.endswith("/runs"):
            agent_id = api_path.split("/")[2]
            run_id = f"run-{agent_id}"
            version_id = "ver-browser-telegram" if agent_id == "agent-browser-telegram" else "ver-whatsapp-faq"
            _json_response(self, {
                "success": True,
                "run": {
                    "id": run_id,
                    "blueprint_id": agent_id,
                    "blueprint_version_id": version_id,
                    "business_id": "biz-1",
                    "status": "completed",
                    "input_json": {
                        "schema": "localos_agent_preview_input_v1",
                        "preview_mode": True,
                        "external_side_effects_allowed": False,
                        "trigger": "manual.preview",
                        "goal": "Проверить сайт конкурента и подготовить Telegram-отчёт.",
                        "provider_bindings": [
                            {"provider": "browser_use", "key": "browser_use_read", "status": "connected"},
                            {"provider": "telegram", "key": "telegram_delivery", "status": "connected"},
                        ],
                    },
                    "output_json": {
                        "status": "completed",
                        "message": "Safe preview готов. Внешние отправки не выполнялись.",
                    },
                    "steps": [
                        {"step_key": "browser_use_read", "step_type": "capability", "status": "completed"},
                        {"step_key": "telegram_delivery", "step_type": "draft", "status": "completed"},
                    ],
                    "artifacts": [],
                    "approvals": [],
                    "observability": {
                        "preview_summary": {
                            "is_preview": True,
                            "safe_preview": True,
                            "headline": "Агент проверил сценарий без внешней отправки.",
                            "understood_task": "Открыть сайт конкурента, найти изменения цен и акций, подготовить Telegram-отчёт владельцу.",
                            "manual_control": "Telegram-сообщение остаётся черновиком до подтверждения человека.",
                            "data_sources": ["browser_use", "telegram"],
                            "completed_steps": ["browser_use_read", "telegram_delivery"],
                            "pending_approvals": [],
                            "waiting_actions": [],
                            "preflight_ready": True,
                            "next_step": "review_preview",
                            "next_step_label": "Проверить preview",
                            "next_step_description": "Проверьте текст и включите агента только после ручной проверки.",
                        },
                        "step_history": {"count": 2},
                        "errors": [],
                        "action_ledger": {"items": []},
                        "domain_requests": {"items": [], "pending": 0, "count": 0},
                    },
                },
            }, 201)
            return None
        _json_response(self, {"error": "not found", "path": api_path}, 404)

    def _serve_static(self, path: str) -> None:
        target = (DIST / path.lstrip("/")).resolve()
        if not str(target).startswith(str(DIST.resolve())) or not target.is_file():
            target = DIST / "index.html"
        body = target.read_bytes()
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if target.name == "index.html":
            content_type = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4177)
    args = parser.parse_args()
    if not (DIST / "index.html").exists():
        raise SystemExit("frontend/dist/index.html not found; run frontend build first")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving agents product UI mock at http://{args.host}:{args.port}/dashboard/agents", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
