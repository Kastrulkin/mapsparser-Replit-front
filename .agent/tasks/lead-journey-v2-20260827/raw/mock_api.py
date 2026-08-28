from http.server import BaseHTTPRequestHandler, HTTPServer
import json


ACTION = {
    "id": "action-1",
    "journey_id": "journey-1",
    "business_id": "business-1",
    "flow_type": "influencer",
    "entity_type": "creator_profile",
    "entity_id": "creator-1",
    "action_type": "browse_creators",
    "status": "ready",
    "priority": 110,
    "title": "Выберите 2–5 подходящих авторов",
    "description": "Посмотрите причины соответствия, добавьте авторов в shortlist и подтвердите выбор.",
    "cta_label": "Подтвердить выбор",
    "cta_target": {"screen": "influencers"},
    "payload": {"offer": {"service": "Стрижка", "reward": "стрижка в подарок", "threshold": 3}},
    "allowed_commands": ["complete"],
    "version": 1,
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def reply(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin") or "http://127.0.0.1:3000")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.reply({})

    def do_GET(self):
        if self.path.startswith("/api/journeys/public/"):
            selected_flow = "content"
            for candidate in ("influencer", "partnership", "maps", "content"):
                if f"test-{candidate}" in self.path:
                    selected_flow = candidate
                    break
            return self.reply({
                "success": True,
                "journey": {
                    "id": "journey-content",
                    "status": "preview",
                    "source": "admin",
                    "selected_flow": selected_flow,
                    "business": {"name": "Студия Варвары", "city": "Санкт-Петербург"},
                    "opportunities": [
                        {"flow_type": "content", "entity_type": "contentplanitem", "entity_id": "item-1", "title": "Как сохранить результат процедуры", "summary": "Полезная тема для клиентов", "reason": "Тема отвечает на частый вопрос клиентов", "mechanic": "Черновик → календарь → публикация", "message_excerpt": "После процедуры важно соблюдать несколько простых правил", "public_url": "https://example.test/post"},
                        {"flow_type": "maps", "entity_type": "card_audit", "entity_id": "audit-1", "title": "Обновить услуги в карточке", "summary": "Один приоритетный шаг", "reason": "В карточке не хватает услуги"},
                        {"flow_type": "influencer", "entity_type": "creator_profile", "entity_id": "creator-1", "title": "Анна о Петербурге", "summary": "Локальный автор", "reason": "Совпадает география"},
                        {"flow_type": "partnership", "entity_type": "prospecting_lead", "entity_id": "partner-1", "title": "Кофейня рядом", "summary": "Общая аудитория", "reason": "Соседний бизнес"},
                    ],
                },
            })
        if self.path.startswith("/api/auth/me"):
            return self.reply({"user": {"id": "user-1", "email": "test@example.test", "name": "Варва", "is_superadmin": True}, "businesses": [{"id": "business-1", "name": "Студия Варвары", "subscription_tier": "trial", "subscription_status": "inactive"}]})
        if self.path.startswith("/api/admin/prospecting/leads"):
            return self.reply({"success": True, "leads": [{"id": "lead-varvara", "name": "[TEST] Journey Pilot 1 — Варвара", "city": "Санкт-Петербург"}]})
        if self.path.startswith("/api/journeys/preview"):
            return self.reply({"success": True, "preview": {"business_name": "Студия Варвары", "business_city": "Санкт-Петербург", "opportunities": [
                {"flow_type": "content", "entity_type": "contentplanitem", "entity_id": "item-1", "title": "Как сохранить результат процедуры", "summary": "Полезная тема для клиентов", "reason": "Тема отвечает на частый вопрос", "mechanic": "Черновик → календарь → публикация", "message_excerpt": "После процедуры важно соблюдать несколько простых правил"},
                {"flow_type": "maps", "entity_type": "card_audit", "entity_id": "audit-1", "title": "Обновить услуги", "summary": "Один шаг", "reason": "Не хватает услуги"},
                {"flow_type": "influencer", "entity_type": "creator_profile", "entity_id": "creator-1", "title": "Анна о Петербурге", "summary": "Локальный автор", "reason": "Совпадает география"},
                {"flow_type": "partnership", "entity_type": "prospecting_lead", "entity_id": "partner-1", "title": "Кофейня рядом", "summary": "Общая аудитория", "reason": "Соседний бизнес"},
            ]}})
        if self.path == "/api/journeys" or self.path.startswith("/api/journeys?"):
            return self.reply({"success": True, "journeys": []})
        if self.path.startswith("/api/growth-paths"):
            paths = [
                {"flow_type": "maps", "title": "Карты", "status": "not_started", "opportunity": "Исправьте самый заметный барьер в карточке.", "access": {"status": "available", "reason": "Доступно", "cta_label": "Открыть карты", "cta_target": {"screen": "progress"}}},
                {"flow_type": "content", "title": "Контент", "status": "not_started", "opportunity": "Подготовьте полезную публикацию.", "access": {"status": "payment_required", "reason": "Полный черновик и календарь открываются на платном тарифе.", "cta_label": "Выбрать тариф", "cta_target": {"screen": "settings"}}},
                {"flow_type": "influencer", "title": "Инфлюенсеры", "status": "ready", "opportunity": "Автор уже выбран", "access": {"status": "available", "reason": "Доступно", "cta_label": "Открыть автора", "cta_target": {"screen": "influencers", "action_id": "action-1"}}, "action": ACTION},
                {"flow_type": "partnership", "title": "Партнёрства", "status": "not_started", "opportunity": "Найдите партнёра рядом.", "access": {"status": "available", "reason": "Доступно", "cta_label": "Открыть партнёров", "cta_target": {"screen": "partnerships"}}},
            ]
            return self.reply({"success": True, "focus_action": ACTION, "paths": paths})
        if self.path.startswith("/api/promotion/influencers/workspace") or self.path.startswith("/api/promotion/influencers/catalog"):
            return self.reply({"success": True, "workspace": {"next_action": "Выберите 2–5 подходящих авторов", "offer": {"service": "Стрижка", "reward": "стрижка в подарок", "threshold": 3}, "latest_search": {"id": "search-1", "status": "completed", "brief": {"city": "Санкт-Петербург"}, "results_count": 2, "shortlisted_count": 1}, "creators": [{"id": "creator-1", "result_id": "result-1", "display_name": "Анна про Петербург", "description": "Обзоры локальных мест и beauty-услуг", "platform": "telegram", "public_url": "https://t.me/anna", "city": "Санкт-Петербург", "area": "Приморский район", "audience_count": 4200, "primary_topic": "Локальные места", "formats": ["обзор", "подборка"], "accepts_barter": True, "contactability": "advertising_contact", "score": 86, "fit_reasons": ["Пишет о местах рядом", "Аудитория совпадает по географии"], "shortlist_status": "shortlisted", "evidence": [{"summary": "Публичный обзор салона", "source_url": "https://t.me/anna/10"}]}], "counts": {"total": 2, "returned": 1, "shortlisted": 1}, "cursor": None, "filters": {"platforms": ["telegram"], "cities": ["Санкт-Петербург"], "topics": ["Локальные места"], "formats": ["обзор", "подборка"], "audience_size_bands": ["nano"]}, "access": {"message_generation": {"status": "payment_required", "reason": "Персональные сообщения доступны после оплаты.", "cta_label": "Выбрать тариф", "cta_target": {"screen": "settings"}}}}})
        if self.path.startswith("/api/journey-actions"):
            return self.reply({"success": True, "focus_action": ACTION, "actions": [ACTION]})
        if self.path.startswith("/api/operator/feed") or self.path.startswith("/api/operator/mobile/feed"):
            return self.reply({"success": True, "topics": [], "topic_trends": [], "items": [], "inbound_items": [{"id": "reply-1", "channel": "telegram", "classification": "interested", "sender_name": "Анна про Петербург", "text": "Да, интересно обсудить бартер", "received_at": "2026-08-27T16:00:00Z", "flow_type": "influencer", "target": {"screen": "influencers", "item_id": "reply-1"}}], "cursor": None, "as_of": "2026-08-27T16:00:00Z", "freshness": {"status": "live", "updated_at": "2026-08-27T16:00:00Z"}, "available_actions": []})
        if self.path.startswith("/api/journey-actions/action-1"):
            return self.reply({"success": True, "action": ACTION})
        return self.reply({"success": True})

    def do_POST(self):
        if self.path == "/api/auth/login":
            return self.reply({"success": True, "token": "test-token", "user": {"id": "user-1", "email": "test@example.test", "name": "Варва"}})
        if self.path == "/api/journeys/claim":
            return self.reply({"success": True, "action": ACTION})
        if self.path == "/api/journeys":
            return self.reply({"success": True, "journey": {"id": "journey-new", "status": "preview", "selected_flow": "content", "expires_at": "2026-09-26T12:00:00Z"}, "public_path": "/start/generated-test-token", "public_url": "http://127.0.0.1:4178/start/generated-test-token"})
        if "/opportunities/" in self.path:
            return self.reply({"success": True, "preview": {"partial_result": {"mechanic": "Черновик → календарь → публикация", "message_excerpt": "После процедуры важно соблюдать несколько простых правил"}}})
        return self.reply({"success": True})


HTTPServer(("", 8000), Handler).serve_forever()
