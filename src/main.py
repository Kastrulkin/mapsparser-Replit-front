"""
main.py - Веб-сервер для SEO-анализатора Яндекс.Карт
"""
import os
import sys
if __name__.startswith("src."):
    sys.modules.setdefault("main", sys.modules[__name__])
else:
    sys.modules.setdefault("src.main", sys.modules[__name__])

import json
import sqlite3
import uuid
import base64
import hashlib
import hmac
import html
import random
import re
import threading
import logging
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import requests

# GigaChat TLS verification is explicit: use GIGACHAT_SSL_VERIFY=false only as a documented provider workaround.
os.environ.setdefault('GIGACHAT_SSL_VERIFY', 'true')
from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
from flask_cors import CORS
from werkzeug.serving import WSGIRequestHandler
from werkzeug.exceptions import HTTPException

# Rate limiting для защиты от brute force и DDoS
logger = logging.getLogger(__name__)
VERBOSE_OPTIONAL_STARTUP = os.getenv('LOCALOS_VERBOSE_STARTUP_WARNINGS', '').strip().lower() in {'1', 'true', 'yes'}

def _optional_startup_notice(feature: str, error: Exception, *, enabled: bool = False) -> None:
    if enabled or VERBOSE_OPTIONAL_STARTUP:
        logger.warning("Optional integration '%s' is unavailable: %s", feature, error)

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    RATE_LIMITER_AVAILABLE = os.getenv('RATE_LIMITING_ENABLED', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    if VERBOSE_OPTIONAL_STARTUP:
        logger.info("flask-limiter is not installed. Rate limiting remains disabled.")
from yandex_maps_scraper import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat
from database_manager import DatabaseManager, get_db_connection
from parsequeue_status import STATUS_COMPLETED, STATUS_ERROR, normalize_status
from auth_system import CONSENT_VERSION, authenticate_user, create_session, normalize_email, verify_email_token, verify_session, rotate_verification_token
from billing_constants import TARIFFS
from core.email_delivery import build_password_setup_link, send_email as deliver_email, send_password_setup_email, send_verification_email
from init_database_schema import init_database_schema
from core.default_ai_prompts import get_default_ai_prompts
from core.beauty_service_optimization import (
    apply_beauty_service_guardrails,
    beauty_canonical_service_key,
    format_beauty_generation_context,
    is_beauty_optimization_context,
)
from core.service_keyword_scoring import evaluate_service_keyword_score
from core.service_optimization_verticals import (
    detect_service_optimization_vertical,
    format_service_optimization_vertical_prompt,
    get_service_optimization_vertical_context,
)
from core.industry_patterns import detect_industry_key, evaluate_pattern_fit, format_industry_pattern_prompt
from core.finance_kpis import calculate_finance_snapshot, default_period_range, get_default_finance_thresholds
from core import finance_imports
from core import finance_crm
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from core.industry_pattern_recalibration import (
    build_pattern_impact_metrics,
    decide_industry_pattern_proposal,
    ensure_industry_pattern_tables,
    format_active_industry_patterns,
    format_loaded_active_industry_patterns,
    load_active_industry_patterns,
    record_industry_pattern_impact_event,
    run_monthly_industry_pattern_recalibration,
)
from chatgpt_api import chatgpt_bp
from chatgpt_search_api import chatgpt_search_bp
from stripe_integration import stripe_bp
from yookassa_integration import billing_bp
from crypto_pay_api import crypto_pay_bp
from admin_moderation import admin_moderation_bp
from bookings_api import bookings_bp
from ai_agent_webhooks import ai_webhooks_bp
from ai_agents_api import ai_agents_api_bp
from chats_api import chats_bp
from messengers_api import messengers_bp
from api.services_api import services_bp
from api.business_types_api import business_types_bp
from api.growth_api import growth_bp
from api.growth_overview_api import growth_overview_bp
from api.admin_growth_api import admin_growth_bp
from api.growth_workflow_api import growth_workflow_bp
from api.progress_api import progress_bp
from api.stage_progress_api import stage_progress_bp
from api.metrics_history_api import metrics_history_bp
from api.networks_api import networks_bp
from api.network_health_api import network_health_bp
from api.content_plans_api import content_plans_bp
from api.social_posts_api import social_posts_bp
from api.media_intelligence_api import media_intelligence_bp
from api.finance_api import finance_bp
from api.dashboard_feedback_api import dashboard_feedback_bp
from api.external_accounts_api import external_accounts_bp
from api.parsing_admin_api import parsing_admin_bp
from api.admin_prospecting import (
    admin_prospecting_bp,
    _ensure_admin_prospecting_public_offers_table,
    _ensure_partnership_public_offers_table,
    _slugify_company_name,
)
from api.partnership_leads_api import partnership_leads_bp
from api.sales_rooms_api import sales_rooms_bp
from api.admin_industry_patterns_api import admin_industry_patterns_bp
from api.admin_knowledge_api import admin_knowledge_bp
from api.knowledge_api import knowledge_bp
from api.agent_security_api import agent_security_bp
from api.agent_prospecting_api import agent_prospecting_bp
from api.agent_builder_api import agent_builder_bp
from api.agent_blueprints_api import agent_blueprints_bp
from api.capabilities_api import capabilities_bp, PHASE1_ACTION_ORCHESTRATOR
from api.average_ticket_api import average_ticket_bp
from api.reports_api import reports_bp
from api.operator_api import operator_bp
from api.auth_user_api import auth_user_bp
from api.superadmin_business_api import superadmin_business_bp
from api.telegram_opportunity_radar_api import telegram_opportunity_radar_bp
from core.agent_api_security import log_agent_discovery_event, should_track_discovery_path
from services.prospecting_service import ProspectingService
from core.card_audit import build_card_audit_snapshot, build_lead_card_preview_snapshot
from core.ai_learning import record_ai_learning_event
from core.card_automation import (
    ensure_card_automation_tables,
    get_card_automation_snapshot,
    run_card_automation_action,
    save_card_automation_settings,
)
from core.learning_patterns import get_service_optimization_learning_candidates
from core.telegram_userbot import (
    load_userbot_account,
    send_code as userbot_send_code,
    confirm_code as userbot_confirm_code,
    send_message as userbot_send_message,
    update_userbot_session,
)
from core.parsing_runtime_config import (
    get_use_apify_map_parsing,
    resolve_map_source_for_queue,
    set_use_apify_map_parsing,
)
from core.map_url_normalizer import is_google_map_url, normalize_map_url
from core.telegram_network import build_requests_proxy_kwargs
try:
    from api.google_business_api import google_business_bp
except ImportError as e:
    _optional_startup_notice(
        'google_business',
        e,
        enabled=bool(os.getenv('GOOGLE_CLIENT_ID') or os.getenv('GOOGLE_CLIENT_SECRET')),
    )
    google_business_bp = None

# Импорт YandexSyncService с обработкой ошибок
try:
    from yandex_sync_service import YandexSyncService
except ImportError as e:
    _optional_startup_notice(
        'yandex_sync',
        e,
        enabled=bool(os.getenv('YANDEX_BUSINESS_TOKEN') or os.getenv('YANDEX_BUSINESS_LOGIN')),
    )
    YandexSyncService = None

# Импорт YandexBusinessParser для парсинга из личного кабинета
try:
    from yandex_business_parser import YandexBusinessParser
    from yandex_business_sync_worker import YandexBusinessSyncWorker
    from auth_encryption import decrypt_auth_data
except ImportError as e:
    _optional_startup_notice(
        'yandex_business_parser',
        e,
        enabled=bool(os.getenv('YANDEX_BUSINESS_TOKEN') or os.getenv('YANDEX_BUSINESS_LOGIN')),
    )
    YandexBusinessParser = None
    YandexBusinessSyncWorker = None

# Автоматическая загрузка переменных окружения из .env / .env.test
try:
    from dotenv import load_dotenv
    # Если FLASK_ENV=test|testing - используем .env.test, иначе обычный .env
    env_file = ".env.test" if os.getenv("FLASK_ENV", "").lower() in ("test", "testing") else ".env"
    load_dotenv(env_file)
except ImportError:
    if VERBOSE_OPTIONAL_STARTUP:
        logger.info("python-dotenv is not installed. Skipping automatic .env loading.")

app = Flask(__name__)

# Flask-SQLAlchemy + Flask-Migrate: только для миграций (runtime по-прежнему pg_db_utils/psycopg2)
_database_url = os.getenv("DATABASE_URL")
if _database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url
app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
try:
    from flask_sqlalchemy import SQLAlchemy
    from flask_migrate import Migrate
    db = SQLAlchemy(app)
    # directory: не трогаем существующую папку migrations/ с кастомными скриптами
    migrate = Migrate(app, db, directory="alembic_migrations")
    import alembic_migrations.models_for_migrate  # noqa: F401  # модели только для Alembic
except ImportError:
    db = None
    migrate = None

# Настройка CORS для продакшена и разработки.
# В .env укажите: ALLOWED_ORIGINS=http://localhost:3000,https://localos.pro
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
CORS(app, supports_credentials=True, origins=allowed_origins)

# Настройка rate limiting
if RATE_LIMITER_AVAILABLE:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[],
        storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
    )
    print("✅ Rate limiting включен для чувствительных endpoint'ов")
else:
    limiter = None
    if VERBOSE_OPTIONAL_STARTUP:
        logger.info("Rate limiting disabled in this runtime.")

# Декоратор для применения rate limiting (если доступен)
def rate_limit_if_available(limit_str):
    """Декоратор для применения rate limiting, если limiter доступен"""
    def decorator(f):
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

if limiter:
    @app.errorhandler(429)
    def handle_rate_limit(error):
        return jsonify(
            {
                "success": False,
                "error": "rate_limited",
                "message": "Слишком много запросов. Повторите позже.",
            }
        ), 429

# Регистрируем Blueprint'ы сразу после создания app, чтобы они имели приоритет над SPA fallback
app.register_blueprint(chatgpt_bp)
app.register_blueprint(chatgpt_search_bp)
app.register_blueprint(stripe_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(admin_moderation_bp)
app.register_blueprint(bookings_bp)
app.register_blueprint(ai_webhooks_bp)
app.register_blueprint(crypto_pay_bp)
app.register_blueprint(ai_agents_api_bp)
app.register_blueprint(chats_bp)
if "messengers" not in app.blueprints:
    app.register_blueprint(messengers_bp)
app.register_blueprint(services_bp)
app.register_blueprint(business_types_bp)
app.register_blueprint(growth_bp)
app.register_blueprint(growth_overview_bp)
app.register_blueprint(admin_growth_bp)
app.register_blueprint(growth_workflow_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(stage_progress_bp)
app.register_blueprint(metrics_history_bp)
app.register_blueprint(networks_bp)
app.register_blueprint(network_health_bp)
app.register_blueprint(content_plans_bp)
app.register_blueprint(social_posts_bp)
app.register_blueprint(media_intelligence_bp)
app.register_blueprint(finance_bp)
app.register_blueprint(dashboard_feedback_bp)
app.register_blueprint(external_accounts_bp)
app.register_blueprint(parsing_admin_bp)
app.register_blueprint(partnership_leads_bp)
app.register_blueprint(admin_prospecting_bp)
app.register_blueprint(sales_rooms_bp)
app.register_blueprint(admin_industry_patterns_bp)
app.register_blueprint(admin_knowledge_bp)
app.register_blueprint(knowledge_bp)
app.register_blueprint(agent_security_bp)
app.register_blueprint(agent_prospecting_bp)
app.register_blueprint(agent_builder_bp)
app.register_blueprint(agent_blueprints_bp)
app.register_blueprint(capabilities_bp)
app.register_blueprint(average_ticket_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(operator_bp)
app.register_blueprint(auth_user_bp)
app.register_blueprint(superadmin_business_bp)
app.register_blueprint(telegram_opportunity_radar_bp)

# Dev-safeguard: не допускаем дублирования /api/services/list
try:
    _routes = [r.rule for r in app.url_map.iter_rules()]
    assert _routes.count("/api/services/list") == 1, "Duplicate /api/services/list route detected"
except Exception as e:
    # В debug режиме пусть assert падает явно, в проде только логируем.
    if getattr(app, "debug", False):
        raise
    else:
        logger.warning("[ROUTE_CHECK] %s", e)

try:
    from api.wordstat_api import wordstat_bp
    app.register_blueprint(wordstat_bp)
except ImportError as e:
    _optional_startup_notice('wordstat', e)

if google_business_bp:
    app.register_blueprint(google_business_bp)

# Путь к собранному фронтенду (SPA)
FRONTEND_DIST_DIR = os.path.abspath(
    os.getenv(
        "FRONTEND_DIST_DIR",
        os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'),
    )
)
PUBLIC_FRONTEND_DIST_DIR = os.path.abspath(
    os.getenv(
        "PUBLIC_FRONTEND_DIST_DIR",
        os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public-dist'),
    )
)
CONTENT_SEO_FILE = "content-seo.json"
SITE_URL = "https://localos.pro"
DEFAULT_OG_IMAGE = "https://localos.pro/assets/hero-image-BXgvVNKj.jpg"
PUBLIC_AUDIT_APP_ROUTES = {
    "about",
    "contact",
    "policy",
    "requisites",
    "login",
    "dashboard",
    "dashboard-old",
    "wizard",
    "sprint",
    "phrases",
    "card-recs",
    "set-password",
    "reset-password",
    "verify-email",
    "bazich",
    "public-audit",
    "assets",
}

# HTML шаблон для главной страницы
INDEX_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Анализатор Яндекс.Карт</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="url"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 4px; }
        button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005a87; }
        .result { margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 4px; }
        .error { background: #ffebee; border-left: 4px solid #f44336; }
        .success { background: #e8f5e8; border-left: 4px solid #4caf50; }
    </style>
</head>
<body>
    <h1>SEO Анализатор Яндекс.Карт</h1>
    <form id="analyzeForm">
        <div class="form-group">
            <label for="url">Ссылка на карточку Яндекс.Карт:</label>
            <input type="url" id="url" name="url" placeholder="https://yandex.ru/maps/org/..." required>
        </div>
        <button type="submit">Анализировать</button>
    </form>
    <div id="result"></div>

    <script>
        document.getElementById('analyzeForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            const url = document.getElementById('url').value;
            const resultDiv = document.getElementById('result');

            resultDiv.innerHTML = '<div class="result">Анализируем...</div>';

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });

                const data = await response.json();

                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="result success">
                            <h3>Анализ завершён!</h3>
                            <p><strong>Название:</strong> ${data.title}</p>
                            <p><strong>SEO Score:</strong> ${data.seo_score}</p>
                            <p><strong>ID карточки:</strong> ${data.card_id}</p>
                            <p><a href="/api/download-report/${data.card_id}" target="_blank">Скачать отчёт</a></p>
                        </div>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="result error"><strong>Ошибка:</strong> ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="result error"><strong>Ошибка:</strong> ${error.message}</div>`;
            }
        });
    </script>
</body>
</html>
"""

# ==================== ЛОКАЛЬНЫЕ УТИЛИТЫ ДЛЯ SQLITE ====================

# ===== АДМИНСКИЕ ЭНДПОИНТЫ ДЛЯ ПАРСИНГА =====

# ===== YCLIENTS MARKETPLACE CALLBACKS =====

# ===== EXTERNAL SOURCES API (Яндекс.Бизнес / Google Business / 2ГИС) =====

# ==================== SUPERADMIN USER MANAGEMENT ====================
# Эти маршруты должны быть ПЕРЕД SPA fallback, чтобы Flask их правильно обрабатывал

SENSITIVE_PROBE_PATH_MARKERS = (
    ".env",
    ".git",
    "phpinfo",
    "app_dev.php",
    "_profiler",
)
SENSITIVE_PROBE_EXACT_PATHS = {
    "test.php",
    "api/test",
}

# SPA-фолбэк: любые не-API пути возвращают index.html

# Временные заглушки для тихой работы фронтенда

# ==================== ХЕЛПЕР: РАБОТА С БИЗНЕСАМИ ====================
# Импортируем helper функции из core модуля
from core.helpers import get_business_owner_id, get_business_id_from_user, get_user_language, find_business_id_for_user

# ==================== СЕРВИС: ОПТИМИЗАЦИЯ УСЛУГ ====================

# ==================== ПРИМЕРЫ ФОРМУЛИРОВОК УСЛУГ (ПОЛЬЗОВАТЕЛЯ) ====================

# ==================== НОВОСТИ ДЛЯ КАРТ ====================

# ==================== ПРИМЕРЫ ДЛЯ ОТЗЫВОВ И НОВОСТЕЙ ====================

# ==================== СЕРВИС: ОТВЕТЫ НА ОТЗЫВЫ ====================

# ==================== СЕРВИС: УПРАВЛЕНИЕ УСЛУГАМИ ====================

# ==================== КЛИЕНТСКАЯ ИНФОРМАЦИЯ (ПРОФИЛЬ БИЗНЕСА) ====================

# ==================== ДИАГНОСТИКА GIGACHAT ====================

# ==================== ЭНДПОИНТЫ ДЛЯ СЕТЕЙ ====================

# ===== EXTERNAL SOURCES API (Яндекс.Бизнес / Google Business / 2ГИС) =====
# ДУБЛИКАТ УДАЛЁН - см. определения выше (строки 429, 500, 627)

# ==================== УПРАВЛЕНИЕ ПРОКСИ ====================

# ==================== ПРОМПТЫ ДЛЯ AI ====================

# ===== TELEGRAM BOT API =====

_RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ы": "y", "э": "e", "ю": "yu", "я": "ya",
}

_EXTRA_LAT = {
    "ç": "c", "ğ": "g", "ı": "i", "İ": "i", "ö": "o", "ş": "s", "ü": "u",
    "á": "a", "à": "a", "â": "a", "ä": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ñ": "n",
}

class QuietWSGIRequestHandler(WSGIRequestHandler):
    """Suppress malformed scanner noise while keeping normal access logs."""

    _HTTP_METHOD_PREFIXES = (
        "GET ",
        "POST ",
        "PUT ",
        "PATCH ",
        "DELETE ",
        "OPTIONS ",
        "HEAD ",
    )

    def log_error(self, format, *args):
        try:
            if (
                format.startswith("code %d, message %s")
                and len(args) >= 2
                and int(args[0]) in (400, 505)
            ):
                message = str(args[1] or "")
                if (
                    "Bad request syntax" in message
                    or "Bad request version" in message
                    or "Bad HTTP/0.9 request type" in message
                    or "Invalid HTTP version" in message
                ):
                    return
        except Exception:
            pass
        super().log_error(format, *args)

    def log_request(self, code="-", size="-"):
        try:
            status_code = int(code)
        except Exception:
            status_code = -1
        if status_code in (400, 505):
            request_line = (self.requestline or "")
            if not request_line.startswith(self._HTTP_METHOD_PREFIXES):
                return
        super().log_request(code, size)

from functools import wraps as _compat_wraps
from legacy_routes import shared as _legacy_shared

_legacy_shared.configure(globals())

from legacy_routes import core_public as _chunk_core_public
from legacy_routes import content_services as _chunk_content_services
from legacy_routes import client_reports as _chunk_client_reports
from legacy_routes import parsing_networks as _chunk_parsing_networks
from legacy_routes import auth_admin as _chunk_auth_admin
from legacy_routes import public_requests as _chunk_public_requests
from legacy_routes import report_pipeline as _chunk_report_pipeline

_CHUNK_MODULES = (
    _chunk_core_public,
    _chunk_content_services,
    _chunk_client_reports,
    _chunk_parsing_networks,
    _chunk_auth_admin,
    _chunk_public_requests,
    _chunk_report_pipeline,
)
_IMPLEMENTATIONS = {
    name: value
    for module in _CHUNK_MODULES
    for name, value in vars(module).items()
    if callable(value) and getattr(value, "__module__", "") == module.__name__
}


def _bind_runtime_namespace() -> None:
    namespace = {
        name: value
        for name, value in globals().items()
        if name not in {"_bind_runtime_namespace", "_compatibility_wrapper"}
    }
    _legacy_shared.configure(namespace)
    for module in _CHUNK_MODULES:
        vars(module).update(namespace)


def _compatibility_wrapper(name: str, implementation: Any):
    @_compat_wraps(implementation)
    def wrapper(*args: Any, **kwargs: Any):
        _bind_runtime_namespace()
        return _IMPLEMENTATIONS[name](*args, **kwargs)

    return wrapper


for _name, _implementation in _IMPLEMENTATIONS.items():
    if _name in {"_bind_runtime_namespace", "_compatibility_wrapper"}:
        continue
    globals()[_name] = _compatibility_wrapper(_name, _implementation)

for _endpoint, _view_func in list(app.view_functions.items()):
    for _name, _implementation in _IMPLEMENTATIONS.items():
        if _view_func is _implementation:
            app.view_functions[_endpoint] = globals()[_name]
            break

_bind_runtime_namespace()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
