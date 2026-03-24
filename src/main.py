"""
main.py - Веб-сервер для SEO-анализатора Яндекс.Карт
"""
import os
import sys
import json
import sqlite3
import uuid
import base64
import random
import re
import threading
from datetime import datetime, timedelta
from typing import Any

# Устанавливаем переменную окружения для отключения SSL проверки GigaChat
os.environ.setdefault('GIGACHAT_SSL_VERIFY', 'false')
from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
from flask_cors import CORS
from werkzeug.serving import WSGIRequestHandler
from werkzeug.exceptions import HTTPException

# Rate limiting для защиты от brute force и DDoS
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    # Временно отключаем rate limiting для решения пробемы с 429
    RATE_LIMITER_AVAILABLE = False
except ImportError:
    RATE_LIMITER_AVAILABLE = False
    print('⚠️ flask-limiter не установлен. Rate limiting отключен. Установите: pip install flask-limiter')
from yandex_maps_scraper import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat
from database_manager import DatabaseManager, get_db_connection
from parsequeue_status import STATUS_COMPLETED, STATUS_ERROR, normalize_status
from auth_system import authenticate_user, create_session, verify_session
from init_database_schema import init_database_schema
from chatgpt_api import chatgpt_bp
from chatgpt_search_api import chatgpt_search_bp
from stripe_integration import stripe_bp
from admin_moderation import admin_moderation_bp
from bookings_api import bookings_bp
from ai_agent_webhooks import ai_webhooks_bp
from ai_agents_api import ai_agents_api_bp
from chats_api import chats_bp
from messengers_api import messengers_bp
from api.services_api import services_bp
from api.growth_api import growth_bp
from api.admin_growth_api import admin_growth_bp
from api.progress_api import progress_bp
from api.stage_progress_api import stage_progress_bp
from api.metrics_history_api import metrics_history_bp
from api.networks_api import networks_bp
from api.network_health_api import network_health_bp
from api.admin_prospecting import admin_prospecting_bp
from services.prospecting_service import ProspectingService
from core.card_audit import build_lead_card_preview_snapshot
from core.ai_learning import record_ai_learning_event
from core.parsing_runtime_config import (
    get_use_apify_map_parsing,
    resolve_map_source_for_queue,
    set_use_apify_map_parsing,
)
try:
    from api.google_business_api import google_business_bp
except ImportError as e:
    print(f"⚠️ Предупреждение: не удалось импортировать google_business_bp: {e}")
    google_business_bp = None

# Импорт YandexSyncService с обработкой ошибок
try:
    from yandex_sync_service import YandexSyncService
except ImportError as e:
    print(f"⚠️ Предупреждение: не удалось импортировать YandexSyncService: {e}")
    YandexSyncService = None

# Импорт YandexBusinessParser для парсинга из личного кабинета
try:
    from yandex_business_parser import YandexBusinessParser
    from yandex_business_sync_worker import YandexBusinessSyncWorker
    from auth_encryption import decrypt_auth_data
except ImportError as e:
    print(f"⚠️ Предупреждение: не удалось импортировать YandexBusinessParser: {e}")
    YandexBusinessParser = None
    YandexBusinessSyncWorker = None

# Автоматическая загрузка переменных окружения из .env / .env.test
try:
    from dotenv import load_dotenv
    # Если FLASK_ENV=test|testing - используем .env.test, иначе обычный .env
    env_file = ".env.test" if os.getenv("FLASK_ENV", "").lower() in ("test", "testing") else ".env"
    load_dotenv(env_file)
except ImportError:
    print('Внимание: для автоматической загрузки .env установите пакет python-dotenv')

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

# Настройка CORS для продакшена и разработки
# В .env укажите: ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
# For local debugging, allow all origins temporarily if needed, or ensure user's IP is here.
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"])

# Настройка rate limiting
if RATE_LIMITER_AVAILABLE:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["10000 per day", "1000 per hour"],
        storage_uri="memory://"  # Для продакшена лучше использовать Redis
    )
    print("✅ Rate limiting включен (с расширенными лимитами)")
else:
    limiter = None
    print("⚠️ Rate limiting ОТКЛЮЧЕН (для отладки доступа)")

# Декоратор для применения rate limiting (если доступен)
def rate_limit_if_available(limit_str):
    """Декоратор для применения rate limiting, если limiter доступен"""
    def decorator(f):
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator

# Регистрируем Blueprint'ы сразу после создания app, чтобы они имели приоритет над SPA fallback
app.register_blueprint(chatgpt_bp)
app.register_blueprint(chatgpt_search_bp)
app.register_blueprint(stripe_bp)
app.register_blueprint(admin_moderation_bp)
app.register_blueprint(bookings_bp)
app.register_blueprint(ai_webhooks_bp)
app.register_blueprint(ai_agents_api_bp)
app.register_blueprint(chats_bp)
if "messengers" not in app.blueprints:
    app.register_blueprint(messengers_bp)
app.register_blueprint(services_bp)
app.register_blueprint(growth_bp)
app.register_blueprint(admin_growth_bp)
app.register_blueprint(progress_bp)
app.register_blueprint(stage_progress_bp)
app.register_blueprint(metrics_history_bp)
app.register_blueprint(networks_bp)
app.register_blueprint(network_health_bp)
app.register_blueprint(admin_prospecting_bp)

# Dev-safeguard: не допускаем дублирования /api/services/list
try:
    _routes = [r.rule for r in app.url_map.iter_rules()]
    assert _routes.count("/api/services/list") == 1, "Duplicate /api/services/list route detected"
except Exception as e:
    # В debug режиме пусть assert падает явно, в проде только логируем.
    if getattr(app, "debug", False):
        raise
    else:
        print(f"[ROUTE_CHECK] Warning: {e}")

try:
    from api.wordstat_api import wordstat_bp
    app.register_blueprint(wordstat_bp)
except ImportError as e:
    print(f"⚠️ Could not import wordstat_bp: {e}")

if google_business_bp:
    app.register_blueprint(google_business_bp)

# Путь к собранному фронтенду (SPA)
FRONTEND_DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist'))

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
def competitor_exists(url: str) -> bool:
    try:
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("SELECT id FROM Cards WHERE url = ? LIMIT 1", (url,))
        row = cur.fetchone()
        db.close()
        return row is not None
    except Exception:
        return False

def save_card_to_db(card: dict) -> None:
    """Сохранить/обновить карточку в локальной БД `Cards`."""
    db = DatabaseManager()
    cur = db.conn.cursor()

    card_id = card.get('id') or str(uuid.uuid4())
    overview = card.get('overview') or {}

    # === АВТОМАТИЧЕСКИЙ АНАЛИЗ ПРИ СОХРАНЕНИИ ===
    try:
        from services.analytics_service import calculate_profile_completeness, generate_seo_recommendations
        
        # Подготовка данных для анализа
        analysis_data = {
            'phone': (overview or {}).get('phone'),
            'website': (overview or {}).get('site'),
            'schedule': (overview or {}).get('working_hours') or card.get('hours') or card.get('hours_full'),
            'photos_count': card.get('photos_count') or len(card.get('photos', [])),
            'services_count': card.get('services_count') or len(card.get('products', [])),
            'description': (overview or {}).get('description'),
            'messengers': card.get('messengers'),
            'is_verified': card.get('is_verified')
        }
        
        # Расчет баллов
        seo_score = calculate_profile_completeness(analysis_data)
        recommendations = generate_seo_recommendations(analysis_data)
        
        # Обновляем объект card перед сохранением
        card['seo_score'] = seo_score
        card['recommendations'] = json.dumps(recommendations, ensure_ascii=False)
        print(f"📊 [save_card_to_db] Auto-Analysis: Score {seo_score}%")
        
    except Exception as e:
        print(f"⚠️ Warning: Auto-analysis failed in save_card_to_db: {e}")
    # ============================================

    cur.execute(
        """
        INSERT OR REPLACE INTO Cards (
            id, url, title, address, phone, site, rating, reviews_count,
            categories, overview, products, news, photos, features_full,
            competitors, hours, hours_full, report_path, user_id, seo_score,
            ai_analysis, recommendations
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """,
        (
            card_id,
            card.get('url'),
            (overview or {}).get('title'),
            (overview or {}).get('address'),
            (overview or {}).get('phone'),
            (overview or {}).get('site'),
            (overview or {}).get('rating'),
            (overview or {}).get('reviews_count'),
            json.dumps(card.get('categories')),
            json.dumps(card.get('overview')),
            json.dumps(card.get('products')),
            json.dumps(card.get('news')),
            json.dumps(card.get('photos')),
            json.dumps(card.get('features_full')),
            json.dumps(card.get('competitors')),
            json.dumps(card.get('hours')),
            json.dumps(card.get('hours_full')),
            card.get('report_path'),
            card.get('user_id'),
            card.get('seo_score'),
            card.get('ai_analysis'),
            card.get('recommendations'),
        ),
    )
    db.conn.commit()
    db.close()

def _get_client_ip() -> str:
    """
    Определение IP-адреса клиента.
    Учитываем прокси (X-Forwarded-For / X-Real-IP), затем remote_addr.
    """
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        # Берём первый IP из списка
        return x_forwarded_for.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    return request.remote_addr or ''


def _detect_country_code() -> str:
    """
    Определяем страну пользователя.
    Сейчас:
    - поддерживаем X-Country-Override для тестов;
    - учитываем DEFAULT_COUNTRY_CODE из .env;
    - TODO: подключить GeoIP по IP-адресу (MaxMind или внешний сервис).
    """
    # Явная переопределяемая страна (для тестов и ручной проверки)
    override = request.headers.get('X-Country-Override')
    if override:
        return override.upper()

    # Значение по умолчанию из окружения (для dev/стейджа)
    env_country = os.getenv('DEFAULT_COUNTRY_CODE')
    if env_country:
        return env_country.upper()

    # На будущее: здесь можно сделать реальный GeoIP по _get_client_ip()
    # ip = _get_client_ip()
    # ...
    return 'US'


@app.route('/', methods=['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'])
def index():
    """Главная страница - раздаём собранный SPA"""
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        return ('', 405)
    try:
        return send_from_directory(FRONTEND_DIST_DIR, 'index.html')
    except Exception as e:
        # Фолбэк на встроенный шаблон, если сборка отсутствует
        return render_template_string(INDEX_HTML)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Раздача ассетов Vite/SPA"""
    return send_from_directory(os.path.join(FRONTEND_DIST_DIR, 'assets'), filename)

@app.route('/yandex_f5eb229fc5e67c03.html')
def serve_yandex_verification():
    """Yandex Webmaster verification"""
    # Explicitly define root directory to avoid traversal issues
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return send_from_directory(root_dir, 'yandex_f5eb229fc5e67c03.html')

@app.route('/api/geo/payment-provider', methods=['GET'])
def get_payment_provider():
    """
    Определение платёжного провайдера по стране пользователя.
    - Россия (RU)  -> 'russia'
    - Остальные    -> 'stripe'
    """
    try:
        country = _detect_country_code()
        provider = 'russia' if country == 'RU' else 'stripe'
        return jsonify({
            "success": True,
            "country": country,
            "payment_provider": provider
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/admin/token-usage', methods=['GET'])
def get_token_usage_stats():
    """Получить статистику использования токенов GigaChat по пользователям и бизнесам (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем, что это суперадмин
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Доступ запрещён"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT name, description, optimized_name, optimized_description
            FROM userservices
            WHERE id = %s AND user_id = %s
            """,
            (service_id, user_id),
        )
        previous_row = cursor.fetchone()
        previous_data = _row_to_dict(cursor, previous_row) if previous_row else {}
        
        # Проверяем, существует ли таблица tokenusage (Postgres)
        cursor.execute("SELECT to_regclass('public.tokenusage')")
        if not cursor.fetchone():
            db.close()
            return jsonify({
                "success": True,
                "total": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "requests_count": 0
                },
                "by_user": [],
                "by_business": [],
                "by_task_type": []
            })
        
        # Общая статистика
        cursor.execute("""
            SELECT 
                SUM(total_tokens) as total,
                SUM(prompt_tokens) as prompt_total,
                SUM(completion_tokens) as completion_total,
                COUNT(*) as requests_count
            FROM TokenUsage
        """)
        total_stats = cursor.fetchone()
        
        # По пользователям
        cursor.execute("""
            SELECT 
                u.id,
                u.email,
                u.name,
                COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                COUNT(tu.id) as requests_count
            FROM Users u
            LEFT JOIN TokenUsage tu ON u.id = tu.user_id
            GROUP BY u.id, u.email, u.name
            HAVING total_tokens > 0
            ORDER BY total_tokens DESC
        """)
        users_stats = []
        for row in cursor.fetchall():
            users_stats.append({
                "user_id": row[0],
                "email": row[1],
                "name": row[2],
                "total_tokens": row[3] or 0,
                "prompt_tokens": row[4] or 0,
                "completion_tokens": row[5] or 0,
                "requests_count": row[6] or 0
            })
        
        # По бизнесам
        cursor.execute("""
            SELECT 
                b.id,
                b.name,
                b.owner_id,
                u.email as owner_email,
                COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                COUNT(tu.id) as requests_count
            FROM Businesses b
            LEFT JOIN TokenUsage tu ON b.id = tu.business_id
            LEFT JOIN Users u ON b.owner_id = u.id
            GROUP BY b.id, b.name, b.owner_id, u.email
            HAVING total_tokens > 0
            ORDER BY total_tokens DESC
        """)
        businesses_stats = []
        for row in cursor.fetchall():
            businesses_stats.append({
                "business_id": row[0],
                "business_name": row[1],
                "owner_id": row[2],
                "owner_email": row[3],
                "total_tokens": row[4] or 0,
                "prompt_tokens": row[5] or 0,
                "completion_tokens": row[6] or 0,
                "requests_count": row[7] or 0
            })
        
        # По типам задач
        cursor.execute("""
            SELECT 
                task_type,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COUNT(*) as requests_count
            FROM TokenUsage
            GROUP BY task_type
            ORDER BY total_tokens DESC
        """)
        task_types_stats = []
        for row in cursor.fetchall():
            task_types_stats.append({
                "task_type": row[0] or "unknown",
                "total_tokens": row[1] or 0,
                "prompt_tokens": row[2] or 0,
                "completion_tokens": row[3] or 0,
                "requests_count": row[4] or 0
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "total": {
                "total_tokens": total_stats[0] or 0,
                "prompt_tokens": total_stats[1] or 0,
                "completion_tokens": total_stats[2] or 0,
                "requests_count": total_stats[3] or 0
            },
            "by_user": users_stats,
            "by_business": businesses_stats,
            "by_task_type": task_types_stats
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики токенов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ===== АДМИНСКИЕ ЭНДПОИНТЫ ДЛЯ ПАРСИНГА =====

def _count_from_row(cursor, row):
    """Безопасно извлечь число из строки SELECT COUNT(*) AS cnt: tuple или RealDictRow."""
    if row is None:
        return 0
    rd = _row_to_dict(cursor, row)
    if not rd:
        return 0
    if "cnt" in rd and rd["cnt"] is not None:
        return int(rd["cnt"])
    return int(list(rd.values())[0]) if rd else 0


@app.route('/api/admin/parsing/tasks', methods=['GET'])
def get_parsing_tasks():
    """Получить список задач парсинга для администратора"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403
        
        # Получаем параметры фильтрации
        status_filter = request.args.get('status')
        task_type_filter = request.args.get('task_type')
        source_filter = request.args.get('source')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Формируем WHERE условия
        where_conditions = []
        params = []
        
        if status_filter:
            # Фильтр "completed": учитываем и старый статус "done"
            if status_filter == STATUS_COMPLETED:
                where_conditions.append("(status = %s OR status = 'done')")
                params.append(STATUS_COMPLETED)
            else:
                where_conditions.append("status = %s")
                params.append(status_filter)
        
        if task_type_filter:
            where_conditions.append("task_type = %s")
            params.append(task_type_filter)
        
        if source_filter:
            where_conditions.append("source = %s")
            params.append(source_filter)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"

        cursor.execute(f"""
            SELECT
                pq.id, pq.url, pq.user_id, pq.business_id, pq.task_type, pq.account_id, pq.source,
                pq.status, pq.retry_after, pq.error_message, pq.created_at, pq.updated_at,
                b.name AS business_name
            FROM parsequeue pq
            LEFT JOIN businesses b ON b.id = pq.business_id
            WHERE {where_clause}
            ORDER BY pq.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cursor.fetchall()

        cursor.execute(f"""
            SELECT COUNT(*) AS cnt FROM parsequeue WHERE {where_clause}
        """, params)
        total = _count_from_row(cursor, cursor.fetchone())

        cursor.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY status
        """)
        status_stats = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                st_canonical = normalize_status(rd.get("status"))
                status_stats[st_canonical] = status_stats.get(st_canonical, 0) + (rd.get("cnt") or 0)

        tasks = []
        for row in rows:
            task_dict = _row_to_dict(cursor, row)
            if not task_dict:
                continue
            task_dict.setdefault("task_type", "parse_card")
            task_dict["status"] = normalize_status(task_dict.get("status"))
            task_dict["business_name"] = (task_dict.get("business_name") or "").strip() or None
            tasks.append(task_dict)
        
        db.close()
        
        return jsonify({
            "success": True,
            "tasks": tasks,
            "total": total,
            "stats": status_stats
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        body = {"success": False, "error": str(e), "where": "get_parsing_tasks"}
        if getattr(app, "debug", False):
            body["error_type"] = type(e).__name__
            body["traceback"] = traceback.format_exc()
        return jsonify(body), 500

@app.route('/api/admin/parsing/tasks/<task_id>/restart', methods=['POST'])
def restart_parsing_task(task_id):
    """Перезапустить задачу парсинга (сбросить статус на pending)"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, существует ли задача
        cursor.execute("SELECT id, status FROM parsequeue WHERE id = %s", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404
        
        if isinstance(task, dict):
            current_status = task.get('status')
        else:
             # tuple or sqlite3.Row
            current_status = task[1]
        
        cursor.execute("""
            UPDATE parsequeue
            SET status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (task_id,))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "message": f"Задача перезапущена (был статус: {current_status})"
        })
        
    except Exception as e:
        print(f"❌ Ошибка перезапуска задачи: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/parsing/tasks/<task_id>', methods=['DELETE'])
def delete_parsing_task(task_id):
    """Удалить задачу из очереди"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("DELETE FROM parsequeue WHERE id = %s", (task_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Задача удалена"})
        
    except Exception as e:
        print(f"❌ Ошибка удаления задачи: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/parsing/tasks/<task_id>/switch-to-sync', methods=['POST'])
def switch_task_to_sync(task_id):
    """Переключить задачу парсинга на синхронизацию с Яндекс.Бизнес"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT id, business_id, task_type, status
            FROM parsequeue
            WHERE id = %s
        """, (task_id,))
        raw_task = cursor.fetchone()
        task_dict = _row_to_dict(cursor, raw_task) if raw_task else None
        
        if not task_dict:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404
        
        business_id = task_dict.get('business_id')
        if not business_id:
            db.close()
            return jsonify({"error": "У задачи нет business_id"}), 400
        
        if task_dict.get('task_type') == 'sync_yandex_business':
            db.close()
            return jsonify({"error": "Задача уже является синхронизацией"}), 400
        
        cursor.execute("""
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'yandex_business' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        
        if not account_row:
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден активный аккаунт Яндекс.Бизнес",
                "message": "Добавьте аккаунт Яндекс.Бизнес в настройках внешних интеграций"
            }), 400
        
        account_id = account_row.get("id")
        
        cursor.execute("""
            UPDATE parsequeue
            SET task_type = 'sync_yandex_business',
                account_id = %s,
                source = 'yandex_business',
                status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (account_id, task_id))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "message": "Задача переключена на синхронизацию с Яндекс.Бизнес"
        })
        
    except Exception as e:
        print(f"❌ Ошибка переключения задачи на синхронизацию: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/parsing/stats', methods=['GET'])
def get_parsing_stats():
    """Получить общую статистику парсинга"""
    try:
        # Проверка авторизации и прав суперадмина
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) AS cnt FROM parsequeue")
        total_tasks = _count_from_row(cursor, cursor.fetchone())

        cursor.execute("""
            SELECT status, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY status
        """)
        by_status = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                st_canonical = normalize_status(rd.get("status") or "idle")
                by_status[st_canonical] = by_status.get(st_canonical, 0) + (rd.get("cnt") or 0)

        cursor.execute("""
            SELECT task_type, COUNT(*) AS cnt
            FROM parsequeue
            GROUP BY task_type
        """)
        by_task_type = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                by_task_type[rd.get("task_type") or "parse_card"] = rd.get("cnt") or 0

        cursor.execute("""
            SELECT source, COUNT(*) AS cnt
            FROM parsequeue
            WHERE source IS NOT NULL
            GROUP BY source
        """)
        by_source = {}
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd and rd.get("source") is not None:
                by_source[rd["source"]] = rd.get("cnt") or 0
        
        cursor.execute("""
            SELECT id, business_id, task_type, created_at, updated_at
            FROM parsequeue
            WHERE status = 'processing'
              AND COALESCE(updated_at, created_at) < NOW() - INTERVAL '30 minutes'
        """)
        stuck_tasks = []
        for row in cursor.fetchall():
            rd = _row_to_dict(cursor, row)
            if rd:
                stuck_tasks.append({
                    'id': rd.get('id'),
                    'business_id': rd.get('business_id'),
                    'task_type': rd.get('task_type') or 'parse_card',
                    'created_at': rd.get('created_at'),
                    'updated_at': rd.get('updated_at') or rd.get('created_at')
                })
        
        db.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_tasks": total_tasks,
                "by_status": by_status or {},
                "by_task_type": by_task_type or {},
                "by_source": by_source or {},
                "stuck_tasks_count": len(stuck_tasks),
                "stuck_tasks": stuck_tasks or []
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        body = {"success": False, "error": str(e), "where": "get_parsing_stats"}
        if getattr(app, "debug", False):
            body["error_type"] = type(e).__name__
            body["traceback"] = traceback.format_exc()
        return jsonify(body), 500

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.ico')

@app.route('/favicon.svg')
def favicon_svg():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.svg')

@app.route('/robots.txt')
def robots():
    return send_from_directory(FRONTEND_DIST_DIR, 'robots.txt')


# ===== EXTERNAL SOURCES API (Яндекс.Бизнес / Google Business / 2ГИС) =====

@app.route("/api/business/<business_id>/external-accounts", methods=["GET"])
def get_external_accounts(business_id):
    """
    Получить все подключённые внешние аккаунты (Яндекс.Бизнес, Google Business, 2ГИС)
    для конкретного бизнеса. Всегда возвращает JSON: 200 { "success": true, "accounts": [] } или список.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Таблица из миграции 20250207_008: externalbusinessaccounts (lowercase)
        try:
            cursor.execute(
                """
                SELECT id, source, external_id, display_name, is_active,
                       last_sync_at, last_error, created_at, updated_at
                FROM externalbusinessaccounts
                WHERE business_id = %s
                ORDER BY source, created_at DESC
                """,
                (business_id,),
            )
            rows = cursor.fetchall()
        except Exception as table_err:
            db.close()
            err_str = str(table_err)
            is_missing_relation = "does not exist" in err_str or "relation" in err_str.lower()
            if is_missing_relation and getattr(app, "debug", False):
                print(f"⚠️ GET external-accounts: таблица отсутствует, возвращаем [] (dev): {table_err}")
                return jsonify({"success": True, "accounts": [], "_debug": {"tableMissing": True, "tableName": "externalbusinessaccounts"}})
            if is_missing_relation:
                import traceback
                print(f"❌ GET external-accounts: таблица externalbusinessaccounts не найдена: {table_err}\n{traceback.format_exc()}")
                return jsonify({"error": "Schema error: external accounts table missing", "detail": "get_external_accounts"}), 500
            raise

        accounts = []
        for r in rows:
            row_dict = _row_to_dict(cursor, r)
            if not row_dict:
                continue
            accounts.append({
                "id": row_dict.get("id"),
                "source": row_dict.get("source"),
                "external_id": row_dict.get("external_id"),
                "display_name": row_dict.get("display_name"),
                "is_active": row_dict.get("is_active"),
                "last_sync_at": row_dict.get("last_sync_at"),
                "last_error": row_dict.get("last_error"),
                "created_at": row_dict.get("created_at"),
                "updated_at": row_dict.get("updated_at"),
            })
        db.close()
        resp = {"success": True, "accounts": accounts}
        if getattr(app, "debug", False):
            resp["_debug"] = {"tableName": "externalbusinessaccounts"}
        return jsonify(resp)

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка GET external-accounts: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "get_external_accounts"}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route("/api/business/<business_id>/external-accounts", methods=["POST"])
def upsert_external_account(business_id):
    """
    Создать или обновить внешний аккаунт источника для бизнеса.

    Body:
      - source: 'yandex_business' | 'google_business' | '2gis'
      - external_id: string (опционально)
      - display_name: string (опционально)
      - auth_data: string (cookie / refresh_token / token) - будет зашифрован позже
      - is_active: bool (опционально, по умолчанию True)
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        source = (data.get("source") or "").strip()
        external_id = (data.get("external_id") or "").strip() or None
        display_name = (data.get("display_name") or "").strip() or None
        is_active = data.get("is_active", True)

        # Нормализация auth_data: строка или объект → строка для шифрования; валидация JSON при необходимости
        raw_auth = data.get("auth_data")
        auth_data_str = None
        if raw_auth is not None:
            if isinstance(raw_auth, dict):
                try:
                    auth_data_str = json.dumps(raw_auth)
                except (TypeError, ValueError) as e:
                    return jsonify({"error": "auth_data: объект не сериализуется в JSON", "field": "auth_data", "detail": str(e)}), 400
            elif isinstance(raw_auth, str):
                s = raw_auth.strip() or None
                if s:
                    if s.startswith("{") or s.startswith("["):
                        try:
                            json.loads(s)
                        except json.JSONDecodeError as e:
                            return jsonify({"error": "auth_data: некорректный JSON", "field": "auth_data", "detail": str(e)}), 400
                    auth_data_str = s
            else:
                return jsonify({"error": "auth_data должен быть строкой или объектом", "field": "auth_data"}), 400

        if source not in ("yandex_business", "google_business", "2gis"):
            return jsonify({"error": "Некорректный source"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существует ли таблица externalbusinessaccounts (Postgres)
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'externalbusinessaccounts'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            db.close()
            return jsonify({
                "error": "Таблица externalbusinessaccounts не существует. Необходимо применить миграцию."
            }), 500

        import uuid
        from datetime import datetime
        from auth_encryption import encrypt_auth_data

        now = datetime.utcnow().isoformat()
        print(f"🔍 POST /api/business/{business_id}/external-accounts: source={source}, external_id={external_id}, display_name={display_name}, auth_data length={len(auth_data_str) if auth_data_str else 0}")

        # Шифруем auth_data перед сохранением (auth_data_str уже нормализован)
        auth_data_encrypted = None
        if auth_data_str:
            try:
                auth_data_encrypted = encrypt_auth_data(auth_data_str)
            except Exception as e:
                import traceback
                traceback.print_exc()
                db.close()
                return jsonify({"error": f"Ошибка шифрования данных: {str(e)}", "field": "auth_data"}), 500

        # SELECT с блокировкой при наличии строки, чтобы избежать гонки update/create
        cursor.execute(
            """
            SELECT id, external_id, display_name, is_active
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = %s
            FOR UPDATE
            """,
            (business_id, source),
        )
        existing_row = cursor.fetchone()
        existing_dict = _row_to_dict(cursor, existing_row) if existing_row else None
        account_id = (existing_dict.get("id") if existing_dict else None)

        if existing_dict:
            # Update: считаем реально изменённые поля для saved_fields
            action = "updated"
            old_ext = existing_dict.get("external_id")
            old_name = existing_dict.get("display_name")
            old_active = existing_dict.get("is_active")
            new_active = bool(is_active)
            saved_fields = []
            if (external_id or None) != (old_ext or None):
                saved_fields.append("external_id")
            if (display_name or None) != (old_name or None):
                saved_fields.append("display_name")
            if new_active != (bool(old_active) if old_active is not None else True):
                saved_fields.append("is_active")
            if auth_data_encrypted is not None:
                saved_fields.append("auth_data_updated")

            if auth_data_encrypted is not None:
                cursor.execute(
                    """
                    UPDATE externalbusinessaccounts
                    SET external_id = %s, display_name = %s, auth_data_encrypted = %s, is_active = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (external_id, display_name, auth_data_encrypted, new_active, now, account_id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE externalbusinessaccounts
                    SET external_id = %s, display_name = %s, is_active = %s, updated_at = %s
                    WHERE id = %s
                    """,
                    (external_id, display_name, new_active, now, account_id),
                )
        else:
            # Create: auth_data может отсутствовать для всех источников.
            # Это позволяет сохранять "минимальную" конфигурацию и запускать публичный парсинг по map URL.
            action = "created"
            new_active = bool(is_active)
            insert_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO externalbusinessaccounts (id, business_id, source, external_id, display_name, auth_data_encrypted, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (insert_id, business_id, source, external_id, display_name, auth_data_encrypted, new_active, now, now),
            )
            # Повторный SELECT по (business_id, source): при конкурентном create может быть несколько строк
            cursor.execute(
                """
                SELECT id, created_at FROM externalbusinessaccounts
                WHERE business_id = %s AND source = %s
                ORDER BY created_at ASC
                """,
                (business_id, source),
            )
            rows_after = cursor.fetchall()
            if len(rows_after) > 1:
                print(f"⚠️ Дубликаты externalbusinessaccounts (business_id={business_id}, source={source}): записей={len(rows_after)}, используем с min(created_at)")
            # Канонический id — запись с минимальным created_at (стабильный выбор при дублях)
            row0 = _row_to_dict(cursor, rows_after[0]) if rows_after else None
            account_id = row0.get("id") if row0 else insert_id
            saved_fields = ["external_id", "display_name", "is_active", "auth_data_updated"]

        db.conn.commit()
        db.close()

        resp = {"success": True, "account_id": account_id}
        if getattr(app, "debug", False):
            resp["_debug"] = {
                "action": action,
                "business_id": business_id,
                "source": source,
                "saved_fields": saved_fields,
                "returned_id": account_id,
            }
        return jsonify(resp)

    except Exception as e:
        print(f"❌ Ошибка сохранения внешнего аккаунта: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/parsing/runtime-settings', methods=['GET'])
def get_parsing_runtime_settings():
    """Получить runtime-настройки парсинга (только superadmin)."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        conn = get_db_connection()
        try:
            enabled = bool(get_use_apify_map_parsing(conn))
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "settings": {
                "use_apify_map_parsing": enabled
            }
        })
    except Exception as e:
        print(f"❌ Ошибка чтения runtime-настроек парсинга: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/parsing/runtime-settings', methods=['POST'])
def update_parsing_runtime_settings():
    """Обновить runtime-настройки парсинга (только superadmin)."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Требуются права администратора"}), 403

        payload = request.get_json(silent=True) or {}
        if "use_apify_map_parsing" not in payload:
            return jsonify({"error": "Поле use_apify_map_parsing обязательно"}), 400
        enabled = bool(payload.get("use_apify_map_parsing"))

        conn = get_db_connection()
        try:
            set_use_apify_map_parsing(conn, enabled)
            current = bool(get_use_apify_map_parsing(conn))
        finally:
            conn.close()

        return jsonify({
            "success": True,
            "settings": {
                "use_apify_map_parsing": current
            }
        })
    except Exception as e:
        print(f"❌ Ошибка обновления runtime-настроек парсинга: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/external-accounts/<account_id>", methods=["DELETE"])
def delete_external_account(account_id):
    """Отключить внешний аккаунт (делаем is_active = 0, но не удаляем записи отзывов/статистики)."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Находим аккаунт и соответствующий бизнес
        cursor.execute(
            "SELECT business_id FROM externalbusinessaccounts WHERE id = %s", (account_id,)
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Аккаунт не найден"}), 404

        business_id = row[0]

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        cursor.execute(
            """
            UPDATE externalbusinessaccounts
            SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (account_id,),
        )
        db.conn.commit()
        db.close()

        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Ошибка отключения внешнего аккаунта: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/business/<business_id>/external-accounts/test", methods=["POST"])
def test_external_account_cookies(business_id):
    """
    Тестирует cookies для внешнего аккаунта без сохранения.
    
    Body:
      - source: 'yandex_business' | '2gis'
      - auth_data: string (cookies в формате строки)
      - external_id: string (опционально, для Яндекс.Бизнес)
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        source = (data.get("source") or "").strip()
        auth_data = (data.get("auth_data") or "").strip()
        external_id = (data.get("external_id") or "").strip() or None

        if not source:
            return jsonify({"error": "source обязателен"}), 400

        if source not in ("yandex_business", "2gis"):
            return jsonify({"error": "Некорректный source"}), 400

        if source == "yandex_business" and not auth_data:
            return jsonify({"error": "source и auth_data обязательны"}), 400
        if source == "2gis" and not auth_data:
            return jsonify({
                "success": True,
                "message": "auth_data не указан: для 2ГИС будет использован публичный парсинг по ссылке/ID",
                "mode": "public_parse",
            }), 200

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        db.close()

        # Парсим auth_data
        try:
            auth_data_dict = json.loads(auth_data)
            cookies_str = auth_data_dict.get("cookies", auth_data)
        except json.JSONDecodeError:
            cookies_str = auth_data

        # Парсим cookies в словарь
        cookies_dict = {}
        for item in cookies_str.split(";"):
            item = item.strip()
            if "=" in item:
                key, value = item.split("=", 1)
                cookies_dict[key.strip()] = value.strip()

        if not cookies_dict:
            return jsonify({
                "success": False,
                "error": "Не удалось распарсить cookies",
                "message": "Проверьте формат cookies. Должен быть: key1=value1; key2=value2; ..."
            }), 200

        # Проверяем наличие критичных cookies для Яндекс.Бизнес
        required_cookies = ["Session_id", "yandexuid", "sessionid2"]
        missing_cookies = [cookie for cookie in required_cookies if cookie not in cookies_dict]
        
        if missing_cookies:
            return jsonify({
                "success": False,
                "error": "Отсутствуют обязательные cookies",
                "message": f"Не найдены критичные cookies: {', '.join(missing_cookies)}. Эти cookies обязательны для доступа к личному кабинету Яндекс.Бизнес. Скопируйте их из DevTools → Application → Cookies → yandex.ru",
                "missing_cookies": missing_cookies,
            }), 200

        # Тестируем cookies в зависимости от source
        if source == "yandex_business":
            # Для Яндекс.Бизнес тестируем простой запрос к API отзывов
            if not external_id:
                return jsonify({"error": "external_id обязателен для Яндекс.Бизнес"}), 400

            test_url = f"https://yandex.ru/sprav/api/{external_id}/reviews"
            test_params = {"ranking": "by_time"}

            try:
                # Импортируем requests (должен быть установлен)
                try:
                    import requests
                except ImportError:
                    return jsonify({
                        "success": False,
                        "error": "Библиотека requests не установлена",
                        "message": "Установите библиотеку requests: pip install requests",
                    }), 500
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "application/json",
                    "Referer": f"https://yandex.ru/sprav/{external_id}/p/edit/reviews/",
                }
                response = requests.get(test_url, params=test_params, cookies=cookies_dict, headers=headers, timeout=10, allow_redirects=False)
                
                # Логируем для отладки
                print(f"🔍 Тест cookies: URL={test_url}, статус={response.status_code}, content-type={response.headers.get('Content-Type', 'N/A')}")
                if response.status_code != 200:
                    print(f"   Ответ (первые 200 символов): {response.text[:200]}")

                # Проверяем content-type ответа
                content_type = response.headers.get('Content-Type', '').lower()
                
                # Если получили HTML вместо JSON - это признак того, что cookies устарели
                if 'text/html' in content_type or 'html' in response.text[:100].lower():
                    # Проверяем, есть ли в ответе признаки капчи или авторизации
                    response_text_lower = response.text.lower()
                    if 'captcha' in response_text_lower or 'робот' in response_text_lower:
                        return jsonify({
                            "success": False,
                            "error": "Капча",
                            "message": "Яндекс показал капчу. Cookies могут быть недействительны или запросы похожи на автоматические.",
                            "status_code": 200,
                        }), 200
                    elif 'авторизац' in response_text_lower or 'login' in response_text_lower or 'passport.yandex.ru' in response.text:
                        return jsonify({
                            "success": False,
                            "error": "Требуется авторизация",
                            "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации. Обновите cookies в личном кабинете.",
                            "status_code": 401,
                        }), 200
                    else:
                        return jsonify({
                            "success": False,
                            "error": "HTML ответ вместо JSON",
                            "message": "Сервер вернул HTML вместо JSON. Cookies устарели или требуется авторизация.",
                            "status_code": response.status_code,
                        }), 200

                if response.status_code == 200:
                    try:
                        data = response.json()
                        # Проверяем, что это не ошибка
                        if "error" in data:
                            error_msg = data.get("error", {}).get("message", "Неизвестная ошибка")
                            if error_msg == "NEED_RESET":
                                return jsonify({
                                    "success": False,
                                    "error": "Сессия истекла (NEED_RESET)",
                                    "message": "Cookies устарели. Обновите cookies в личном кабинете Яндекс.Бизнес.",
                                    "status_code": 401,
                                }), 200
                            return jsonify({
                                "success": False,
                                "error": error_msg,
                                "status_code": response.status_code,
                            }), 200
                        return jsonify({
                            "success": True,
                            "message": "Cookies работают корректно!",
                            "status_code": 200,
                        }), 200
                    except json.JSONDecodeError as e:
                        # Если не JSON, проверяем, что это за ответ
                        content_type = response.headers.get('Content-Type', '').lower()
                        response_text = response.text[:500]  # Первые 500 символов
                        
                        # Проверяем на капчу или HTML
                        if 'captcha' in response_text.lower() or 'робот' in response_text.lower():
                            return jsonify({
                                "success": False,
                                "error": "Капча",
                                "message": "Яндекс показал капчу. Cookies могут быть недействительны или запросы похожи на автоматические.",
                                "status_code": 200,
                            }), 200
                        
                        return jsonify({
                            "success": False,
                            "error": "Получен не JSON ответ",
                            "message": f"Сервер вернул {content_type}. Возможно, требуется авторизация или cookies устарели.",
                            "status_code": response.status_code,
                            "content_type": content_type,
                        }), 200
                    except Exception as e:
                        return jsonify({
                            "success": False,
                            "error": f"Ошибка парсинга ответа: {str(e)}",
                            "status_code": response.status_code,
                        }), 200
                elif response.status_code == 401:
                    return jsonify({
                        "success": False,
                        "error": "Не авторизован (401)",
                        "message": "Cookies устарели или недействительны. Обновите cookies.",
                        "status_code": 401,
                    }), 200
                elif response.status_code == 302:
                    return jsonify({
                        "success": False,
                        "error": "Редирект (302)",
                        "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации.",
                        "status_code": 302,
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Ошибка {response.status_code}",
                        "status_code": response.status_code,
                    }), 200
            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                # Определяем тип ошибки для более понятного сообщения
                if "Exceeded" in error_msg and "redirects" in error_msg:
                    return jsonify({
                        "success": False,
                        "error": "Редирект (302)",
                        "message": "Cookies устарели. Яндекс перенаправляет на страницу авторизации (слишком много редиректов).",
                        "status_code": 302,
                    }), 200
                elif "timeout" in error_msg.lower():
                    return jsonify({
                        "success": False,
                        "error": "Таймаут",
                        "message": "Превышено время ожидания ответа от сервера Яндекс.",
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "error": f"Ошибка запроса: {error_msg}",
                        "message": "Не удалось выполнить запрос к API Яндекс.Бизнес.",
                    }), 200
        elif source == "2gis":
            # Для 2ГИС можно добавить тестирование позже
            return jsonify({
                "success": True,
                "message": "Cookies приняты (тестирование 2ГИС пока не реализовано)",
            }), 200

        return jsonify({"error": "Неизвестный source"}), 400

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"❌ Ошибка в test_external_account_cookies: {e}")
        print(error_trace)
        return jsonify({
            "success": False,
            "error": f"Внутренняя ошибка сервера: {str(e)}",
            "message": "Произошла ошибка при тестировании cookies. Проверьте логи сервера.",
        }), 500


@app.route("/api/business/<business_id>/external/reviews", methods=["GET"])
def get_external_reviews(business_id):
    """
    Получить все спарсенные отзывы из внешних источников (Яндекс.Бизнес, Google Business, 2ГИС)
    для конкретного бизнеса.
    """
    try:
        # Авторизация: владелец бизнеса или суперадмин
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, что пользователь владелец бизнеса или суперадмин
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существует ли таблица externalbusinessreviews (Postgres)
        cursor.execute("SELECT to_regclass('public.externalbusinessreviews')")
        table_exists = cursor.fetchone()
        if not table_exists or (table_exists and (table_exists[0] if isinstance(table_exists, (list, tuple)) else table_exists) is None):
            db.close()
            return jsonify({"success": True, "reviews": [], "total": 0, "with_response": 0, "without_response": 0})

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        cursor.execute(
            """
            SELECT id, name, address, network_id
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (business_id,),
        )
        raw_business = cursor.fetchone()
        business_row = _row_to_dict(cursor, raw_business) if raw_business else None
        network_id = business_row.get("network_id") if business_row else None
        aggregate_network = bool(network_id) and requested_scope == "network"

        review_query = """
            SELECT r.id, r.source, r.external_review_id, r.rating, r.author_name, r.text,
                   r.response_text, r.response_at, r.published_at, r.created_at,
                   b.id AS location_business_id, b.name AS location_name, b.address AS location_address
            FROM externalbusinessreviews r
            LEFT JOIN businesses b ON b.id = r.business_id
        """
        review_params = []
        if aggregate_network:
            review_query += """
            WHERE r.business_id IN (
                SELECT id FROM businesses WHERE network_id = %s
            )
            """
            review_params.append(network_id)
        else:
            review_query += " WHERE r.business_id = %s "
            review_params.append(business_id)

        review_query += " ORDER BY COALESCE(r.published_at, r.created_at) DESC, r.created_at DESC "
        cursor.execute(review_query, tuple(review_params))
        rows = cursor.fetchall()
        db.close()

        reviews = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            resp_text = rd.get("response_text")
            reviews.append({
                "id": rd.get("id"),
                "source": rd.get("source"),
                "external_review_id": rd.get("external_review_id"),
                "rating": rd.get("rating"),
                "author_name": rd.get("author_name") or "Анонимный пользователь",
                "text": rd.get("text") or "",
                "response_text": resp_text,
                "response_at": rd.get("response_at"),
                "published_at": rd.get("published_at"),
                "created_at": rd.get("created_at"),
                "has_response": bool(resp_text),
                "location_business_id": rd.get("location_business_id"),
                "location_name": rd.get("location_name"),
                "location_address": rd.get("location_address"),
            })

        return jsonify({
            "success": True,
            "reviews": reviews,
            "total": len(reviews),
            "with_response": sum(1 for x in reviews if x["has_response"]),
            "without_response": sum(1 for x in reviews if not x["has_response"]),
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_reviews: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_reviews", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route("/api/business/<business_id>/external/summary", methods=["GET"])
def get_external_summary(business_id):
    """
    Получить сводку данных из внешних источников (рейтинг, количество отзывов, статистика).
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Проверяем, существуют ли таблицы (Postgres)
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('externalbusinessstats', 'externalbusinessreviews')
        """)
        tables = {row['table_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
        
        if 'externalbusinessstats' not in tables or 'externalbusinessreviews' not in tables:
            # Таблицы не существуют — отдаём хотя бы данные из cards (парсинг)
            cursor.execute("""
                SELECT created_at, rating, reviews_count, competitors
                FROM cards WHERE business_id = %s ORDER BY created_at DESC LIMIT 1
            """, (business_id,))
            raw = cursor.fetchone()
            card_row = _row_to_dict(cursor, raw) if raw else None
            db.close()
            rating = None
            reviews_total = 0
            last_parse_date = None
            competitors = None
            if card_row:
                try:
                    rating = float(card_row.get("rating")) if card_row.get("rating") is not None else None
                except (TypeError, ValueError):
                    pass
                reviews_total = int(card_row.get("reviews_count") or 0)
                last_parse_date = card_row.get("created_at")
                competitors = card_row.get("competitors")
            return jsonify({
                "success": True,
                "rating": rating,
                "reviews_total": reviews_total,
                "reviews_with_response": 0,
                "reviews_without_response": reviews_total,
                "last_sync_date": None,
                "last_parse_date": last_parse_date,
                "competitors": competitors,
                "scope": "business",
                "network_id": None,
            })

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        cursor.execute(
            """
            SELECT id, name, address, network_id
            FROM businesses
            WHERE id = %s
            LIMIT 1
            """,
            (business_id,),
        )
        raw_business = cursor.fetchone()
        business_row = _row_to_dict(cursor, raw_business) if raw_business else None
        network_id = business_row.get("network_id") if business_row else None
        aggregate_network = bool(network_id) and requested_scope == "network"

        stats_query = """
            SELECT business_id, rating, reviews_total, date
            FROM externalbusinessstats
            WHERE source = 'yandex_business'
        """
        stats_params = []
        if aggregate_network:
            stats_query += """
              AND business_id IN (
                  SELECT id FROM businesses WHERE network_id = %s
              )
            ORDER BY business_id, date DESC
            """
            stats_params.append(network_id)
        else:
            stats_query += """
              AND business_id = %s
            ORDER BY date DESC
            LIMIT 1
            """
            stats_params.append(business_id)

        cursor.execute(stats_query, tuple(stats_params))
        stats_rows = cursor.fetchall()
        stats_dicts = [_row_to_dict(cursor, row) for row in stats_rows]
        if aggregate_network:
            latest_by_business = {}
            filtered_stats = []
            for item in stats_dicts:
                business_stat_id = str(item.get("business_id") or "").strip()
                if business_stat_id and business_stat_id not in latest_by_business:
                    latest_by_business[business_stat_id] = True
                    filtered_stats.append(item)
            stats_dicts = filtered_stats
        stats_row = stats_dicts[0] if stats_dicts else None

        if aggregate_network and stats_dicts:
            weighted_sum = 0.0
            weighted_count = 0
            latest_sync_date = None
            for item in stats_dicts:
                item_rating = item.get("rating")
                item_reviews_total = item.get("reviews_total")
                item_date = item.get("date")
                if latest_sync_date is None or (item_date and item_date > latest_sync_date):
                    latest_sync_date = item_date
                try:
                    rating_value = float(item_rating) if item_rating is not None else None
                except (TypeError, ValueError):
                    rating_value = None
                reviews_value = int(item_reviews_total or 0)
                if rating_value is not None and reviews_value > 0:
                    weighted_sum += rating_value * reviews_value
                    weighted_count += reviews_value
            aggregated_rating = None
            if weighted_count > 0:
                aggregated_rating = weighted_sum / weighted_count
            stats_row = {
                "rating": aggregated_rating,
                "reviews_total": weighted_count,
                "date": latest_sync_date,
            }

        reviews_summary_query = """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 ELSE 0 END) AS with_response,
                   SUM(CASE WHEN response_text IS NULL OR response_text = '' THEN 1 ELSE 0 END) AS without_response
            FROM externalbusinessreviews
            WHERE source = 'yandex_business'
        """
        reviews_summary_params = []
        if aggregate_network:
            reviews_summary_query += """
              AND business_id IN (
                  SELECT id FROM businesses WHERE network_id = %s
              )
            """
            reviews_summary_params.append(network_id)
        else:
            reviews_summary_query += " AND business_id = %s "
            reviews_summary_params.append(business_id)

        cursor.execute(reviews_summary_query, tuple(reviews_summary_params))
        raw_reviews = cursor.fetchone()
        reviews_row = _row_to_dict(cursor, raw_reviews) if raw_reviews else None

        # Карточка для UI:
        # full_card  — последняя snapshot_type='full' (богатый слепок)
        # metrics_card — последняя is_latest (может быть metrics_update или full)

        # 1) full_card: последняя полноценная карточка
        # overview исторически хранится как TEXT/JSON, поэтому фильтруем snapshot_type в Python
        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
        raw_cards = cursor.fetchall()
        all_cards = [_row_to_dict(cursor, row) for row in raw_cards]

        # 2) metrics_card: последняя is_latest (она может быть metrics_update или full)
        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s AND is_latest = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_latest = cursor.fetchone()
        metrics_card = _row_to_dict(cursor, raw_latest) if raw_latest else None

        def _as_dict_obj(value):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}

        full_card = next((card for card in all_cards if _as_dict_obj(card.get("overview")).get("snapshot_type") == "full"), None)

        # 3) chosen_card: источник rich-контента (предпочитаем full, иначе metrics_card)
        chosen_card = full_card or metrics_card
        parse_row = chosen_card
        last_parse_date = parse_row.get("created_at") if parse_row else None

        db.close()

        # Метрики: сначала внешние источники, затем cards (metrics_card / chosen_card)
        rating = stats_row.get("rating") if stats_row else None
        reviews_total = (reviews_row.get("total") or 0) if reviews_row else 0
        reviews_with_response = (reviews_row.get("with_response") or 0) if reviews_row else 0
        reviews_without_response = (reviews_row.get("without_response") or 0) if reviews_row else 0

        # 4) Fallback по метрикам:
        #   - сначала metrics_card, если это metrics_update
        #   - затем chosen_card (обычно full)
        metrics_overview = _as_dict_obj(metrics_card.get("overview")) if metrics_card else {}
        if rating is None:
            if metrics_card and metrics_overview.get("snapshot_type") == "metrics_update" and metrics_card.get("rating") is not None:
                try:
                    rating = float(metrics_card.get("rating"))
                except (TypeError, ValueError):
                    rating = None
            elif parse_row and parse_row.get("rating") is not None:
                try:
                    rating = float(parse_row.get("rating"))
                except (TypeError, ValueError):
                    rating = None

        if reviews_total == 0:
            if metrics_card and metrics_overview.get("snapshot_type") == "metrics_update" and (metrics_card.get("reviews_count") or 0) != 0:
                reviews_total = int(metrics_card.get("reviews_count") or 0)
            elif parse_row and (parse_row.get("reviews_count") or 0) != 0:
                reviews_total = int(parse_row.get("reviews_count") or 0)

        return jsonify({
            "success": True,
            "rating": float(rating) if rating is not None else None,
            "reviews_total": reviews_total,
            "reviews_with_response": reviews_with_response,
            "reviews_without_response": reviews_without_response,
            "last_sync_date": stats_row.get("date") if stats_row else None,
            "last_parse_date": last_parse_date,
            "competitors": parse_row.get("competitors") if parse_row else None,
            "scope": "network" if aggregate_network else "business",
            "network_id": network_id if aggregate_network else None,
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_summary: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_summary", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route("/api/business/<business_id>/external/posts", methods=["GET"])
def get_external_posts(business_id):
    """
    Получить все спарсенные посты/новости из внешних источников.
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Сначала пробуем externalbusinessposts (Postgres)
        cursor.execute("SELECT to_regclass('public.externalbusinessposts') AS table_ref")
        table_exists_row = cursor.fetchone()
        table_exists_data = _row_to_dict(cursor, table_exists_row) if table_exists_row else {}
        table_ref = table_exists_data.get("table_ref")
        posts = []
        if table_ref:
            cursor.execute(
                """
                SELECT id, source, external_post_id, title, text, published_at, created_at
                FROM externalbusinessposts
                WHERE business_id = %s
                AND (title IS NULL OR title NOT IN ('working_intervals', 'urls', 'phone', 'photos', 'price_lists', 'logo', 'features', 'english_name'))
                AND (title IS NOT NULL OR text IS NOT NULL)
                AND (COALESCE(title, '') != '' OR COALESCE(text, '') != '')
                ORDER BY COALESCE(published_at, created_at) DESC, created_at DESC
                """,
                (business_id,),
            )
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r)
                if not rd:
                    continue
                title = rd.get("title") or ""
                text = rd.get("text") or ""
                if not title and not text:
                    continue
                posts.append({
                    "id": rd.get("id"),
                    "source": rd.get("source") or "external",
                    "external_post_id": rd.get("external_post_id"),
                    "title": title,
                    "text": text,
                    "published_at": rd.get("published_at"),
                    "created_at": rd.get("created_at"),
                })

        # Если постов нет — временно отдаём новости из последней карточки (cards.news)
        if not posts:
            cursor.execute("""
                SELECT news FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (business_id,))
            card_row = cursor.fetchone()
            if card_row:
                rd = _row_to_dict(cursor, card_row)
                news_raw = rd.get("news") if rd else None
                if news_raw is not None:
                    if isinstance(news_raw, list):
                        news_list = news_raw
                    elif isinstance(news_raw, str):
                        try:
                            news_list = json.loads(news_raw) if news_raw.strip() else []
                        except Exception:
                            news_list = []
                    else:
                        news_list = []
                    for i, entry in enumerate(news_list):
                        if not isinstance(entry, dict):
                            continue
                        posts.append({
                            "id": f"card_news_{i}",
                            "source": "yandex_maps",
                            "external_post_id": None,
                            "title": entry.get("title") or entry.get("name") or "",
                            "text": entry.get("text") or entry.get("content") or "",
                            "published_at": entry.get("published_at") or entry.get("date"),
                            "created_at": None,
                        })

        db.close()
        return jsonify({
            "success": True,
            "posts": posts,
            "total": len(posts),
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_posts: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_posts", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route("/api/business/<business_id>/competitors/manual", methods=["GET"])
def get_manual_competitors(business_id):
    """Возвращает конкурентов из последнего card snapshot (ручной блок UI)."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT competitors
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()
        db.close()

        competitors_raw = (_row_to_dict(cursor, row) or {}).get("competitors") if row else None
        competitors = []
        if isinstance(competitors_raw, list):
            competitors = competitors_raw
        elif isinstance(competitors_raw, str):
            try:
                parsed = json.loads(competitors_raw)
                competitors = parsed if isinstance(parsed, list) else []
            except Exception:
                competitors = []

        return jsonify({"success": True, "competitors": competitors, "count": len(competitors)})
    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_manual_competitors: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_manual_competitors", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route("/api/business/<business_id>/services", methods=["GET"])
def get_business_services(business_id):
    """
    Получить список услуг бизнеса
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
            
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверка доступа
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
            
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Читаем из userservices (Postgres, каноничная таблица услуг)
        cursor.execute("""
            SELECT id, category, name, description, price, price_from, price_to, created_at
            FROM userservices
            WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY category NULLS LAST, name NULLS LAST, created_at DESC
        """, (business_id,))
        rows = cursor.fetchall()
        db.close()

        services = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            price = rd.get("price")
            if price is None and (rd.get("price_from") is not None or rd.get("price_to") is not None):
                price = str(rd.get("price_from") or "") if rd.get("price_from") == rd.get("price_to") else f"{rd.get('price_from') or ''}-{rd.get('price_to') or ''}"
            services.append({
                "id": rd.get("id"),
                "category": rd.get("category") or "Без категории",
                "name": rd.get("name") or "",
                "description": rd.get("description") or "",
                "price": price,
                "created_at": rd.get("created_at"),
            })

        return jsonify({"success": True, "services": services})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_business_services: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_business_services", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

# ==================== SUPERADMIN USER MANAGEMENT ====================
# Эти маршруты должны быть ПЕРЕД SPA fallback, чтобы Flask их правильно обрабатывал

@app.route('/api/superadmin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Удалить пользователя - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403
        
        # Нельзя удалить самого себя
        if user_id == user_data['user_id']:
            db.close()
            return jsonify({"error": "Нельзя удалить самого себя"}), 400
        
        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Удаляем пользователя (каскадное удаление удалит все связанные данные)
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Пользователь удален"})
        
    except Exception as e:
        print(f"❌ Ошибка удаления пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users/<user_id>/pause', methods=['POST'])
def pause_user(user_id):
    """Приостановить пользователя (деактивировать) - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403
        
        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, email, is_active FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Нельзя деактивировать самого себя
        if user_id == user_data['user_id']:
            db.close()
            return jsonify({"error": "Нельзя деактивировать самого себя"}), 400
        
        # Деактивируем пользователя
        cursor.execute("""
            UPDATE Users 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (user_id,))
        
        # Деактивируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE owner_id = ?
        """, (user_id,))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Пользователь приостановлен"})
        
    except Exception as e:
        print(f"❌ Ошибка приостановки пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users/<user_id>/unpause', methods=['POST'])
def unpause_user(user_id):
    """Возобновить пользователя (активировать) - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403
        
        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Активируем пользователя
        cursor.execute("""
            UPDATE Users 
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (user_id,))
        
        # Активируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP 
            WHERE owner_id = ?
        """, (user_id,))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Пользователь возобновлен"})
        
    except Exception as e:
        print(f"❌ Ошибка возобновления пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# SPA-фолбэк: любые не-API пути возвращают index.html
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def spa_fallback(path):
    # Не трогаем API маршруты
    if path.startswith('api/'):
        # Для несуществующих API путей отвечаем корректным JSON и статусами, а не HTML/405
        if request.method == 'OPTIONS':
            return ('', 204)
        return jsonify({"error": "Not Found"}), 404

    full_path = os.path.join(FRONTEND_DIST_DIR, path)
    if os.path.isfile(full_path):
        # Если файл существует в dist, отдаем его напрямую
        return send_from_directory(FRONTEND_DIST_DIR, path)

    # Иначе - SPA индекс
    response = send_from_directory(FRONTEND_DIST_DIR, 'index.html')
    # Для index.html отключаем кэширование, чтобы всегда получать свежую версию приложения
    if response:
         response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
         response.headers["Pragma"] = "no-cache"
         response.headers["Expires"] = "0"
    return response

# Временные заглушки для тихой работы фронтенда
@app.route('/api/users/reports', methods=['GET'])
def stub_users_reports():
    return jsonify({"success": True, "reports": []})

@app.route('/api/users/queue', methods=['GET'])
def stub_users_queue():
    return jsonify({"success": True, "queue": []})

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API для анализа карточки"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"success": False, "error": "URL не предоставлен"})

        print(f"Анализируем карточку: {url}")
        card_data = parse_yandex_card(url)

        # Проверка на капчу
        if card_data.get('error') == 'captcha_detected':
            return jsonify({
                "success": False,
                "error": "Страница закрыта капчой. Попробуйте позже или пройдите капчу вручную."
            })

        # Логика выбора и парсинга конкурента
        competitor_data = None
        competitor_url = None
        competitors = card_data.get('competitors', [])
        competitor_status = ''

        if competitors:
            for comp in competitors:
                comp_url = comp.get('url')
                if comp_url and not competitor_exists(comp_url):
                    competitor_url = comp_url
                    break
            if competitor_url:
                print(f"Парсим конкурента: {competitor_url}")
                try:
                    competitor_data = parse_yandex_card(competitor_url)
                    competitor_data['competitors'] = []
                    save_card_to_db(competitor_data)
                except Exception as e:
                    print(f"Ошибка при парсинге конкурента: {e}")
                    competitor_status = f"Ошибка при парсинге конкурента: {e}"
            else:
                competitor_status = "Все конкуренты уже были спарсены ранее."
        else:
            competitor_status = "Конкуренты не найдены на карточке."

        # Сохраняем основную карточку
        competitors_urls = []
        if competitor_url:
            competitors_urls.append(competitor_url)
        card_data['competitors'] = competitors_urls
        save_card_to_db(card_data)

        # Анализ и генерация отчёта
        print("Анализ данных...")
        analysis = analyze_card(card_data)
        print("Генерация отчёта...")
        report_path = generate_html_report(
            card_data,
            analysis,
            competitor_data if competitor_data else {'status': competitor_status}
        )

        return jsonify({
            "success": True,
            "title": card_data.get('overview', {}).get('title', 'Без названия'),
            "seo_score": analysis.get('score', 0),
            "card_id": card_data.get('id', 'unknown'),
            "report_path": report_path
        })

    except Exception as e:
        print(f"Ошибка при анализе: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервера"""
    return jsonify({"status": "ok", "message": "SEO анализатор работает"})

# ==================== ХЕЛПЕР: РАБОТА С БИЗНЕСАМИ ====================
# Импортируем helper функции из core модуля
from core.helpers import get_business_owner_id, get_business_id_from_user, get_user_language, find_business_id_for_user


def _row_to_dict(cursor, row):
    """Маппинг строки в dict: dict-like row — по ключам, tuple-row — по cursor.description."""
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))

def _table_columns(cursor, table_name: str) -> set:
    """Получить набор колонок (lowercase) для таблицы Postgres."""
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    cols = set()
    for row in cursor.fetchall() or []:
        if hasattr(row, "get"):
            name = row.get("column_name")
        else:
            name = row[0] if row else None
        if name:
            cols.add(str(name).lower())
    return cols


def _resolve_request_business_id(user_data, *, json_data=None):
    """Извлечь business_id из query/form/json, чтобы не падать на fallback к "первому бизнесу"."""
    payload = json_data if isinstance(json_data, dict) else {}
    candidates = [
        request.args.get('business_id'),
        request.form.get('business_id'),
        payload.get('business_id'),
        payload.get('businessId'),
    ]
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if not normalized:
            continue
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            owner_id = get_business_owner_id(cursor, normalized, include_active_check=False)
            db.close()
            if owner_id and (owner_id == user_data.get('user_id') or user_data.get('is_superadmin')):
                return normalized
        except Exception as access_exc:
            print(f"⚠️ _resolve_request_business_id access check skipped: {access_exc}")
            return normalized

    return get_business_id_from_user(user_data['user_id'], None)


def _business_display_fields(row_dict):
    """Из row_dict (из businesses) извлечь поля для UI: name, business_type, address, working_hours (строки)."""
    if not row_dict:
        return "", "", "", ""
    def s(v):
        return (v or "").strip() if v is not None else ""
    return s(row_dict.get("name")), s(row_dict.get("business_type")), s(row_dict.get("address")), s(row_dict.get("working_hours"))


def suggest_city_from_address(address: str):
    """Подсказка города из адреса (best-effort, без справочника). Не перезаписывает введённый пользователем city."""
    if not address or not isinstance(address, str):
        return None
    addr = address.strip()
    if not addr:
        return None
    # Первый кандидат — до первой запятой
    if "," in addr:
        candidate = addr.split(",")[0].strip()
    else:
        candidate = addr
    if not candidate:
        return None
    # Убираем префиксы: г. / город / city
    for prefix in ("г.", "город", "city", "Г.", "Город", "City"):
        if candidate.lower().startswith(prefix.lower()):
            candidate = candidate[len(prefix):].strip()
            break
    return candidate if candidate else None


def parse_ll_from_maps_url(maps_url: str):
    """Из ссылки на карты (yandex и т.п.) извлечь ll=lon,lat. Возвращает (geo_lon, geo_lat) или (None, None)."""
    if not maps_url or "ll=" not in maps_url:
        return None, None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(maps_url)
        qs = parse_qs(parsed.query)
        ll = qs.get("ll") or qs.get("LL")
        if not ll or not ll[0]:
            return None, None
        parts = ll[0].strip().split(",")
        if len(parts) != 2:
            return None, None
        lon_f = float(parts[0].strip())
        lat_f = float(parts[1].strip())
        return lon_f, lat_f
    except (ValueError, IndexError, TypeError):
        return None, None


def get_user_language(user_id: str, requested_language: str = None) -> str:
    """
    Получить язык пользователя из профиля бизнеса или использовать запрошенный язык.
    
    Args:
        user_id: ID пользователя
        requested_language: Язык, указанный в запросе (если есть)
    
    Returns:
        Код языка (ru, en, es, de, fr, it, pt, zh)
    """
    # Если язык указан в запросе - используем его
    if requested_language:
        return requested_language.lower()
    
    # Иначе получаем язык из профиля бизнеса пользователя
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        # Получаем первый активный бизнес пользователя
        cursor.execute("""
            SELECT ai_agent_language
            FROM businesses
            WHERE owner_id = %s AND (is_active = TRUE OR is_active IS NULL)
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        db.close()
        
        if row:
            language_value = None
            if isinstance(row, dict):
                language_value = row.get("ai_agent_language")
            else:
                language_value = row[0] if len(row) > 0 else None
            if language_value:
                return str(language_value).lower()
    except Exception as e:
        print(f"⚠️ Ошибка получения языка пользователя: {e}")
    
    # Fallback на русский, если ничего не найдено
    return 'ru'


def _normalize_text_for_semantic_compare(value: str) -> str:
    """Нормализует строку для сравнения «по смыслу» (без регистра/пунктуации/лишних пробелов)."""
    import re as _re
    if value is None:
        return ""
    text = str(value).strip().lower().replace("ё", "е")
    text = _re.sub(r"[^\w\sа-яА-Я]", " ", text, flags=_re.UNICODE)
    text = _re.sub(r"\s+", " ", text, flags=_re.UNICODE).strip()
    return text


def _strip_unchanged_service_suggestions(parsed_result: dict) -> dict:
    """
    Убирает псевдо-оптимизации, которые повторяют исходный текст.
    Это защищает UI от «предложений SEO», равных оригиналу.
    """
    if not isinstance(parsed_result, dict):
        return parsed_result
    services = parsed_result.get("services")
    if not isinstance(services, list):
        return parsed_result

    for service in services:
        if not isinstance(service, dict):
            continue

        original_name = str(service.get("original_name") or service.get("name") or "").strip()
        optimized_name = str(service.get("optimized_name") or service.get("optimizedName") or "").strip()
        if original_name and optimized_name:
            if _normalize_text_for_semantic_compare(original_name) == _normalize_text_for_semantic_compare(optimized_name):
                service["optimized_name"] = ""
                if "optimizedName" in service:
                    service["optimizedName"] = ""

        original_desc = str(
            service.get("original_description")
            or service.get("description")
            or service.get("source_description")
            or ""
        ).strip()
        optimized_desc = str(service.get("seo_description") or service.get("seoDescription") or "").strip()
        if original_desc and optimized_desc:
            if _normalize_text_for_semantic_compare(original_desc) == _normalize_text_for_semantic_compare(optimized_desc):
                service["seo_description"] = ""
                if "seoDescription" in service:
                    service["seoDescription"] = ""

    return parsed_result


def _extract_keywords_from_service_name(service_name: str) -> list[str]:
    import re as _re
    text = str(service_name or "").lower().replace("ё", "е")
    cleaned = _re.sub(r"[^a-zа-я0-9\s-]", " ", text, flags=_re.IGNORECASE)
    parts = [p.strip("- ") for p in cleaned.split() if p.strip("- ")]
    stopwords = {
        "и", "в", "на", "с", "по", "для", "или", "от", "до", "при", "без", "под",
        "the", "and", "for", "with", "from",
        "прием", "повторный", "первичный", "услуга",
    }
    keywords: list[str] = []
    for part in parts:
        if len(part) < 4 or part in stopwords:
            continue
        if part not in keywords:
            keywords.append(part)
        if len(keywords) >= 6:
            break
    return keywords


def _normalize_service_category_value(raw_category: object, fallback: str | None = None) -> str:
    category = str(raw_category or "").strip()
    fallback_category = str(fallback or "").strip()
    generic_categories = {"other", "другое", "разное", "без категории", "общие услуги", "услуги", "категория"}
    if category and category.lower() not in generic_categories:
        return category
    if fallback_category and fallback_category.lower() not in generic_categories:
        return fallback_category
    return "Общие услуги"


def _normalize_low_quality_service_suggestions(
    parsed_result: dict,
    region: str | None = None,
    preferred_category: str | None = None,
) -> dict:
    if not isinstance(parsed_result, dict):
        return parsed_result
    services = parsed_result.get("services")
    if not isinstance(services, list):
        return parsed_result

    region_text = str(region or "").strip()
    normalized: list[dict] = []
    for item in services:
        if not isinstance(item, dict):
            continue
        original_name = str(item.get("original_name") or "").strip()
        optimized_name = str(item.get("optimized_name") or "").strip()
        seo_description = str(item.get("seo_description") or "").strip()
        keywords = item.get("keywords")
        price = item.get("price")
        category = item.get("category")

        low_name = (
            not optimized_name
            or _normalize_text_for_semantic_compare(optimized_name) == _normalize_text_for_semantic_compare(original_name)
            or "в вашем районе" in optimized_name.lower()
        )
        low_description = (
            not seo_description
            or seo_description.lower().startswith("описание услуги:")
            or len(seo_description) < 80
        )
        low_keywords = not isinstance(keywords, list) or len([k for k in keywords if str(k).strip()]) == 0

        if low_name:
            base_name = original_name or "Услуга"
            if region_text:
                optimized_name = f"{base_name} — запись в {region_text}"
            else:
                optimized_name = f"{base_name} — запись к специалисту"

        if low_description:
            base_name = original_name or optimized_name or "Услуга"
            seo_description = (
                f"{base_name}. Услуга выполняется специалистом по предварительной записи. "
                f"Уточните длительность, стоимость и рекомендации перед визитом."
            )

        if low_keywords:
            keywords = _extract_keywords_from_service_name(original_name or optimized_name)

        normalized.append({
            "original_name": original_name or optimized_name,
            "optimized_name": optimized_name,
            "seo_description": seo_description,
            "keywords": keywords,
            "price": price if price is not None else "",
            "category": _normalize_service_category_value(category, fallback=preferred_category),
        })

    parsed_result["services"] = normalized if normalized else services
    return parsed_result


def _ensure_usernews_learning_columns(cursor) -> None:
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")

# ==================== СЕРВИС: ОПТИМИЗАЦИЯ УСЛУГ ====================
@app.route('/api/services/optimize', methods=['POST', 'OPTIONS'])
def services_optimize():
    """Единая точка: перефразирование услуг из текста или файла."""
    try:
        print(f"🔍 Начало обработки запроса /api/services/optimize")
        # Разрешим preflight запросы
        if request.method == 'OPTIONS':
            return ('', 204)
        # Авторизация (опционально можно смягчить)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        json_payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(json_payload, dict):
            json_payload = {}

        tone = request.form.get('tone') or json_payload.get('tone')
        instructions = request.form.get('instructions') or json_payload.get('instructions')
        region = request.form.get('region') or json_payload.get('region')
        business_name = request.form.get('business_name') or json_payload.get('business_name')
        requested_service_category = (
            request.form.get('service_category')
            or request.form.get('category')
            or json_payload.get('service_category')
            or json_payload.get('category')
        )
        length = request.form.get('description_length') or json_payload.get('description_length') or 150
        request_business_id = _resolve_request_business_id(user_data, json_data=json_payload)

        # Язык результата: получаем из запроса или из профиля пользователя
        requested_language = request.form.get('language') or json_payload.get('language')
        language = get_user_language(user_data['user_id'], requested_language)
        language_names = {
            'ru': 'Russian',
            'en': 'English',
            'es': 'Spanish',
            'de': 'German',
            'fr': 'French',
            'it': 'Italian',
            'pt': 'Portuguese',
            'zh': 'Chinese'
        }
        language_name = language_names.get(language, 'Russian')

        # Источник: файл или текст
        file = request.files.get('file') if 'file' in request.files else None
        if file:
            # Проверяем тип файла (прайс-листы + скриншоты)
            allowed_types = [
                'application/pdf', 
                'application/msword', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel', 
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain',
                'text/csv',
                'image/png',
                'image/jpeg',
                'image/jpg'
            ]
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX, TXT, CSV, PNG, JPG, JPEG"}), 400
            
            # Определяем тип обработки по типу файла
            if file.content_type.startswith('image/'):
                # Для изображений - анализ скриншота
                import base64
                image_data = file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')
                
                # Используем упрощенный промпт для анализа скриншота прайс-листа
                try:
                    with open('prompts/screenshot-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                        prompt_content = f.read()
                    
                    # Парсим SYSTEM_PROMPT и USER_PROMPT_TEMPLATE
                    system_prompt = ""
                    user_prompt_template = ""
                    
                    lines = prompt_content.split('\n')
                    current_section = None
                    
                    for line in lines:
                        if line.strip().startswith('SYSTEM_PROMPT'):
                            current_section = 'system'
                            continue
                        elif line.strip().startswith('USER_PROMPT_TEMPLATE'):
                            current_section = 'user'
                            continue
                        elif line.strip().startswith('"""') and current_section:
                            if current_section == 'system':
                                system_prompt = line.replace('"""', '').strip()
                            elif current_section == 'user':
                                user_prompt_template = line.replace('"""', '').strip()
                            current_section = None
                            continue
                        elif current_section == 'system':
                            system_prompt += line + '\n'
                        elif current_section == 'user':
                            user_prompt_template += line + '\n'
                    
                    # Формируем финальный промпт
                    formatted_user_prompt = user_prompt_template.format(
                        region=region or 'Санкт-Петербург',
                        business_name=business_name or 'Салон красоты',
                        tone=tone or 'Профессиональный',
                        length=length or 150,
                        instructions=instructions or 'Оптимизируй услуги для Яндекс.Карт'
                    )
                    screenshot_prompt = f"{system_prompt}\n\n{formatted_user_prompt}"
                    
                except FileNotFoundError:
                    screenshot_prompt = """Проанализируй скриншот прайс-листа салона красоты и найди все услуги.

ВЕРНИ РЕЗУЛЬТАТ СТРОГО В JSON ФОРМАТЕ:
{
  "services": [
    {
      "original_name": "исходное название с скриншота",
      "optimized_name": "SEO-оптимизированное название",
      "seo_description": "детальное описание с ключевыми словами",
      "keywords": ["ключ1", "ключ2", "ключ3"],
      "category": "hair|nails|spa|barber|massage|makeup|brows|lashes|other"
    }
  ]
}"""
                
                print(f"🔍 Анализ скриншота, размер base64: {len(image_base64)} символов")
                result = analyze_screenshot_with_gigachat(
                    image_base64, 
                    screenshot_prompt,
                    task_type="service_optimization",
                    business_id=request_business_id,
                    user_id=user_data['user_id']
                )
                print(f"🔍 Результат анализа скриншота: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'not dict'}")
            else:
                # Для документов - анализ текста
                content = file.read().decode('utf-8', errors='ignore')
        else:
            content = str(json_payload.get('text') or '').strip()

        # Если файл - изображение, результат уже получен выше
        if file and file.content_type.startswith('image/'):
            # Результат анализа скриншота уже в переменной result
            # Для изображений content не используется, но инициализируем пустой строкой
            content = ""
        else:
            # Для текста и документов - проверяем наличие контента
            if not content:
                return jsonify({"error": "Не передан текст услуг или файл"}), 400

            # Загружаем частотные запросы
            try:
                with open('prompts/frequent-queries.txt', 'r', encoding='utf-8') as f:
                    frequent_queries = f.read()
            except FileNotFoundError:
                frequent_queries = "Частотные запросы не найдены"

            # Проверяем наличие косметологических терминов в услугах
            cosmetic_terms = [
                'косметология', 'косметолог', 'чистка лица', 'пилинг лица',
                'ботокс', 'диспорт', 'контурная пластика', 'филлеры',
                'гиалуроновая кислота', 'биоревитализация', 'мезотерапия',
                'плазмолифтинг', 'rf-лифтинг', 'smas-лифтинг', 'ультразвуковой smas',
                'лазерная эпиляция', 'фотоэпиляция', 'лазерное омоложение',
                'лазерная шлифовка', 'нитевой лифтинг', 'липолитики',
                'микротоки', 'аппаратная косметология', 'дермапен', 'микронидлинг',
                'антивозрастные процедуры', 'лечение акне', 'постакне', 'купероз',
                'уход за кожей', 'омоложение лица', 'маска для лица'
            ]

            lower_content = content.lower()
            lower_frequent = frequent_queries.lower() if frequent_queries else ""
            missing_cosmetic_terms = [
                term for term in cosmetic_terms
                if term in lower_content and term not in lower_frequent
            ]

            if missing_cosmetic_terms:
                print(f"⚠️ Найдены косметологические термины без частоток: {missing_cosmetic_terms}")
                # Пытаемся инициировать обновление Wordstat
                try:
                    from update_wordstat_data import main as update_wordstat_main
                    update_wordstat_main()
                except Exception as e:
                    print(f"⚠️ Не удалось запустить обновление Wordstat: {e}")
                # Отправляем уведомление
                try:
                    send_email(
                        "demyanovap@yandex.ru",
                        "Нужны новые Wordstat-ключи (косметология)",
                        "При анализе услуг найдены термины без частотных запросов:\n"
                        + "\n".join(missing_cosmetic_terms)
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось отправить уведомление: {e}")

            # Загружаем новый промпт из файла
            try:
                with open('prompts/services-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                    prompt_file = f.read()
                
                # Парсим SYSTEM_PROMPT и USER_PROMPT_TEMPLATE
                system_prompt = ""
                user_template = ""
                
                if "SYSTEM_PROMPT = " in prompt_file:
                    system_start = prompt_file.find('SYSTEM_PROMPT = """') + len('SYSTEM_PROMPT = """')
                    system_end = prompt_file.find('"""', system_start)
                    system_prompt = prompt_file[system_start:system_end]
                
                if "USER_PROMPT_TEMPLATE = " in prompt_file:
                    user_start = prompt_file.find('USER_PROMPT_TEMPLATE = """') + len('USER_PROMPT_TEMPLATE = """')
                    user_end = prompt_file.find('"""', user_start)
                    user_template = prompt_file[user_start:user_end]
                
                # Загружаем примеры хороших формулировок из БД пользователя
                try:
                    db = DatabaseManager()
                    cur = db.conn.cursor()
                    from core.db_helpers import ensure_user_examples_table
                    ensure_user_examples_table(cur)
                    cur.execute(
                        "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC LIMIT 5",
                        (user_data['user_id'],),
                    )
                    rows = cur.fetchall()
                    db.close()
                    examples_list = [row[0] if isinstance(row, tuple) else row['example_text'] for row in rows]
                    good_examples = "\n".join(examples_list) if examples_list else ""
                except Exception:
                    good_examples = ""
                
                # Формируем финальный промпт
                user_prompt = user_template.replace('{region}', str(region or 'не указан'))
                user_prompt = user_prompt.replace('{business_name}', str(business_name or 'салон красоты'))
                user_prompt = user_prompt.replace('{tone}', str(tone or 'профессиональный'))
                user_prompt = user_prompt.replace('{length}', str(length or 150))
                user_prompt = user_prompt.replace('{instructions}', str(instructions or '-'))
                user_prompt = user_prompt.replace('{frequent_queries}', str(frequent_queries))
                user_prompt = user_prompt.replace('{good_examples}', str(good_examples))
                user_prompt = user_prompt.replace('{content}', str(content[:4000]))
                
                # Объединяем system и user промпты
                prompt = f"{system_prompt}\n\n{user_prompt}"
                
            except FileNotFoundError:
                # Fallback на старый промпт
                default_prompt_template = """Ты - SEO-специалист для бьюти-индустрии. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
Запрещено любые мнения, диалог, оценочные суждения, обсуждение конкурентов, оскорбления. Никакого текста кроме результата.

Регион: {region}
Название бизнеса: {business_name}
Тон: {tone}
Язык результата: {language_name} (все текстовые поля optimized_name, seo_description и general_recommendations должны быть на этом языке)
Длина описания: {length} символов
Дополнительные инструкции: {instructions}

ИСПОЛЬЗУЙ ЧАСТОТНЫЕ ЗАПРОСЫ:
{frequent_queries}

Формат ответа СТРОГО В JSON:
{{
  "services": [
    {{
      "original_name": "...",
      "optimized_name": "...",              
      "seo_description": "...",             
      "keywords": ["...", "...", "..."], 
      "price": null,
      "category": "hair|nails|spa|barber|massage|other"
    }}
  ],
  "general_recommendations": ["...", "..."]
}}

Исходные услуги/контент:
{content}"""
                
                # Пытаемся получить промпт из БД, если не получилось - используем дефолтный
                prompt_template = get_prompt_from_db('service_optimization', default_prompt_template)

                prompt = (
                    prompt_template
                    .replace('{region}', str(region or 'не указан'))
                    .replace('{business_name}', str(business_name or 'салон красоты'))
                    .replace('{tone}', str(tone or 'профессиональный'))
                    .replace('{language_name}', language_name)
                    .replace('{length}', str(length or 150))
                    .replace('{instructions}', str(instructions or '-'))
                    .replace('{frequent_queries}', str(frequent_queries))
                    .replace('{content}', str(content[:4000]))
                )

            if requested_service_category:
                prompt += (
                    f"\n\nКРИТИЧНО: Категория услуги: {requested_service_category}."
                    "\nВерни релевантную категорию в поле category и учитывай её при формулировках."
                    "\nНе используй other/другое, если категория задана."
                )

            result = analyze_text_with_gigachat(
                prompt, 
                task_type="service_optimization",
                business_id=request_business_id,
                user_id=user_data['user_id']
            )
        
        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку
        print(f"🔍 DEBUG services_optimize: result type = {type(result)}")
        print(f"🔍 DEBUG services_optimize: result = {result[:200] if isinstance(result, str) else result}")
        
        # Парсим JSON из ответа GigaChat
        parsed_result = None
        if isinstance(result, dict):
            # Если словарь (на всякий случай), проверяем наличие ошибки
            if 'error' in result:
                error_msg = result.get('error', 'Ошибка оптимизации')
                print(f"❌ Ошибка в результате: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": error_msg,
                    "raw": result.get('raw_response')
                    }), 502
            parsed_result = result
        elif isinstance(result, str):
            # Если строка, пробуем распарсить как JSON
            try:
                # Ищем JSON объект в строке
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = result[start_idx:end_idx]
                    parsed_result = json.loads(json_str)
                    if isinstance(parsed_result, dict) and 'error' in parsed_result:
                        error_msg = parsed_result.get('error', 'Ошибка оптимизации')
                        print(f"❌ Ошибка в результате: {error_msg}")
                        return jsonify({
                            "success": False,
                            "error": error_msg,
                            "raw": result
                        }), 502
                else:
                    # JSON не найден, пробуем распарсить всю строку
                    parsed_result = json.loads(result)
            except json.JSONDecodeError:
                print(f"❌ Не удалось распарсить JSON из результата")
                print(f"❌ Полный результат: {result[:500]}")
                return jsonify({
                    "success": False,
                    "error": "Не удалось распарсить результат оптимизации",
                    "raw": result
                }), 502
        else:
            print(f"❌ Неожиданный тип результата: {type(result)}")
            return jsonify({
                "success": False,
                "error": "Неожиданный формат результата",
                "raw": str(result)
            }), 502

        # Проверяем, что parsed_result - это словарь
        if not isinstance(parsed_result, dict):
            print(f"❌ Ошибка: parsed_result не является словарём, тип: {type(parsed_result)}")
            parsed_result = {}
        else:
            parsed_result = _strip_unchanged_service_suggestions(parsed_result)

        optimized_services = parsed_result.get("services") if isinstance(parsed_result, dict) else None
        if not isinstance(optimized_services, list) or len(optimized_services) == 0:
            # Retry once with stricter prompt if model returned empty payload (e.g. "{}")
            retry_prompt = (
                prompt
                + "\n\nВАЖНО: Верни СТРОГО JSON-объект без пояснений."
                + "\nВнутри обязательно поле services (массив минимум из 1 элемента)."
                + "\nКаждый элемент должен содержать: original_name, optimized_name, seo_description, keywords, price, category."
            )
            retry_raw = analyze_text_with_gigachat(
                retry_prompt,
                task_type="service_optimization",
                business_id=request_business_id,
                user_id=user_data['user_id']
            )
            try:
                if isinstance(retry_raw, str):
                    retry_start = retry_raw.find('{')
                    retry_end = retry_raw.rfind('}') + 1
                    retry_json = retry_raw[retry_start:retry_end] if retry_start != -1 and retry_end > retry_start else retry_raw
                    retry_parsed = json.loads(retry_json)
                elif isinstance(retry_raw, dict):
                    retry_parsed = retry_raw
                else:
                    retry_parsed = {}
            except Exception:
                retry_parsed = {}

            if isinstance(retry_parsed, dict):
                retry_parsed = _strip_unchanged_service_suggestions(retry_parsed)
                retry_services = retry_parsed.get("services")
                if isinstance(retry_services, list) and len(retry_services) > 0:
                    parsed_result = retry_parsed
                    optimized_services = retry_services

        if not isinstance(optimized_services, list) or len(optimized_services) == 0:
            # Last-resort deterministic fallback: do not fail request for operator UI
            fallback_original_name = ""
            fallback_description = ""
            lines = [line.strip() for line in str(content or "").splitlines() if line.strip()]
            if lines:
                fallback_original_name = lines[0]
                fallback_description = " ".join(lines[1:])[:280]
            if not fallback_original_name:
                fallback_original_name = "Услуга"
            if not fallback_description:
                fallback_description = f"Описание услуги: {fallback_original_name}"

            parsed_result = {
                "services": [
                    {
                        "original_name": fallback_original_name,
                        "optimized_name": f"{fallback_original_name} в {region or 'вашем районе'}",
                        "seo_description": fallback_description,
                        "keywords": [],
                        "price": "",
                        "category": _normalize_service_category_value(requested_service_category),
                    }
                ],
                "general_recommendations": [
                    "Проверьте формулировку и при необходимости отредактируйте её вручную перед сохранением."
                ],
                "fallback_used": True,
            }
        else:
            parsed_result = _normalize_low_quality_service_suggestions(
                parsed_result,
                region=region,
                preferred_category=requested_service_category,
            )

        # Apply quality normalization for fallback branch as well
        parsed_result = _normalize_low_quality_service_suggestions(
            parsed_result,
            region=region,
            preferred_category=requested_service_category,
        )

        # Сохраним в БД (как оптимизацию прайса, даже для текстового режима)
        db = DatabaseManager()
        cursor = db.conn.cursor()
        # Гарантируем наличие таблицы PricelistOptimizations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS PricelistOptimizations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_file_path TEXT,
                optimized_data TEXT,
                services_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
            """
        )
        optimization_id = str(uuid.uuid4())
        upload_dir = 'uploads/pricelists'
        os.makedirs(upload_dir, exist_ok=True)
        # Сохраним сырой текст в файл для истории
        raw_path = os.path.join(upload_dir, f"{optimization_id}_raw.txt")
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(content)

        result = parsed_result
        services_count = len(result.get('services', [])) if isinstance(result.get('services'), list) else 0
        cursor.execute("""
            INSERT INTO PricelistOptimizations (id, user_id, original_file_path, optimized_data, services_count, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            optimization_id,
            user_data['user_id'],
            raw_path,
            json.dumps(result, ensure_ascii=False),
            services_count,
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()

        first_service = None
        if isinstance(result.get("services"), list) and result.get("services"):
            first_service = result.get("services")[0]
        draft_name = ""
        if isinstance(first_service, dict):
            draft_name = str(first_service.get("optimized_name") or first_service.get("original_name") or "")
        record_ai_learning_event(
            capability="services.optimize",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=request_business_id,
            prompt_key="service_optimization",
            prompt_version="v1",
            draft_text=draft_name or None,
            metadata={"optimization_id": optimization_id, "services_count": services_count},
        )

        return jsonify({
            "success": True,
            "optimization_id": optimization_id,
            "result": result,
            "meta": {"tone": tone or 'professional', "region": region, "length": int(length) if str(length).isdigit() else 150}
        })

    except Exception as e:
        print(f"❌ Ошибка оптимизации услуг: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ==================== ПРИМЕРЫ ФОРМУЛИРОВОК УСЛУГ (ПОЛЬЗОВАТЕЛЯ) ====================
@app.route('/api/examples', methods=['GET', 'POST', 'OPTIONS'])
def user_service_examples():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cur = db.conn.cursor()
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall()
            db.close()
            examples = []
            for row in rows:
                rd = _row_to_dict(cur, row) if row else {}
                examples.append({"id": rd.get("id"), "text": rd.get("example_text"), "created_at": rd.get("created_at")})
            return jsonify({"success": True, "examples": examples})

        # POST
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close()
            return jsonify({"error": "Текст примера обязателен"}), 400
        # Ограничим 5 примеров на пользователя
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'service'", (user_data['user_id'],))
        count_row = cur.fetchone()
        count_data = _row_to_dict(cur, count_row) if count_row else {}
        count = count_data.get("cnt", 0) or 0
        if count >= 5:
            db.close()
            return jsonify({"error": "Максимум 5 примеров"}), 400
        example_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'service', %s)",
            (example_id, user_data['user_id'], text),
        )
        db.conn.commit()
        db.close()
        return jsonify({"success": True, "id": example_id})
    except Exception as e:
        print(f"❌ Ошибка работы с примерами услуг: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def delete_user_service_example(example_id: str):
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute(
            "DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'service'",
            (example_id, user_data['user_id']),
        )
        deleted = cur.rowcount
        db.conn.commit()
        db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== НОВОСТИ ДЛЯ КАРТ ====================
@app.route('/api/news/generate', methods=['POST', 'OPTIONS'])
def news_generate():
    try:
        print(f"🔍 Начало обработки запроса /api/news/generate")
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        use_service = bool(data.get('use_service'))
        use_transaction = bool(data.get('use_transaction'))
        content_mode = str(data.get('content_mode') or 'news').strip().lower()
        social_format = str(data.get('social_format') or '').strip().lower()
        ab_mode = str(data.get('ab_mode') or '').strip().lower()
        selected_service_id = data.get('service_id')
        selected_transaction_id = data.get('transaction_id')
        raw_info = (data.get('raw_info') or '').strip()

        # Язык новости: получаем из запроса или из профиля пользователя
        requested_language = data.get('language')
        language = get_user_language(user_data['user_id'], requested_language)
        language_names = {
            'ru': 'Russian',
            'en': 'English',
            'es': 'Spanish',
            'de': 'German',
            'fr': 'French',
            'it': 'Italian',
            'pt': 'Portuguese',
            'zh': 'Chinese'
        }
        language_name = language_names.get(language, 'Russian')

        db = DatabaseManager()
        cur = db.conn.cursor()
        # ensure table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
            )
            """
        )
        _ensure_usernews_learning_columns(cur)

        service_context = ''
        transaction_context = ''
        
        if use_service:
            if selected_service_id:
                cur.execute(
                    "SELECT name, description FROM userservices WHERE id = %s AND user_id = %s",
                    (selected_service_id, user_data['user_id']),
                )
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"
            else:
                # выбрать случайную услугу пользователя
                cur.execute(
                    "SELECT name, description FROM userservices WHERE user_id = %s ORDER BY RANDOM() LIMIT 1",
                    (user_data['user_id'],),
                )
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"
        
        if use_transaction:
            if selected_transaction_id:
                # Получаем транзакцию
                cur.execute("""
                    SELECT transaction_date, amount, services, notes, client_type
                    FROM FinancialTransactions
                    WHERE id = %s AND user_id = %s
                """, (selected_transaction_id, user_data['user_id']))
                row = cur.fetchone()
                if row:
                    tx_date, amount, services_raw, notes, client_type = row
                    services_list = []
                    if services_raw:
                        try:
                            services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                            if not isinstance(services_list, list):
                                services_list = []
                        except Exception:
                            services_list = []
                    
                    services_str = ', '.join(services_list) if services_list else 'Услуги'
                    transaction_context = f"Выполнена работа: {services_str}. Дата: {tx_date}. Сумма: {amount}₽. {notes if notes else ''}"
            else:
                # Выбираем последнюю транзакцию
                cur.execute("""
                    SELECT transaction_date, amount, services, notes
                    FROM financialtransactions
                    WHERE user_id = %s
                    ORDER BY transaction_date DESC, created_at DESC
                    LIMIT 1
                """, (user_data['user_id'],))
                row = cur.fetchone()
                if row:
                    tx_date, amount, services_raw, notes = row
                    services_list = []
                    if services_raw:
                        try:
                            services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                            if not isinstance(services_list, list):
                                services_list = []
                        except Exception:
                            services_list = []
                    
                    services_str = ', '.join(services_list) if services_list else 'Услуги'
                    transaction_context = f"Выполнена работа: {services_str}. Дата: {tx_date}. Сумма: {amount}₽. {notes if notes else ''}"

        # Подтянем примеры новостей пользователя (до 5)
        news_examples = ""
        try:
            from core.db_helpers import ensure_user_examples_table
            ensure_user_examples_table(cur)
            cur.execute(
                "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC LIMIT 5",
                (user_data['user_id'],),
            )
            r = cur.fetchall()
            ex = [row[0] if isinstance(row, tuple) else row['example_text'] for row in r]
            if ex:
                news_examples = "\n".join(ex)
        except Exception:
            news_examples = ""

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt = """Ты - маркетолог для локального бизнеса. Сгенерируй новость для публикации на картах (Google, Яндекс).
Требования: до 1500 символов, можно использовать 2-3 эмодзи (не переборщи), без хештегов, без оценочных суждений, без упоминания конкурентов. Стиль - информативный и дружелюбный.
Write all generated text in {language_name}.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Контекст услуги (может отсутствовать): {service_context}
Контекст выполненной работы/транзакции (может отсутствовать): {transaction_context}
Свободная информация (может отсутствовать): {raw_info}
Если уместно, ориентируйся на стиль этих примеров (если они есть):
{news_examples}"""
        
        prompt_template = get_prompt_from_db('news_generation', default_prompt)
        
        # Логируем тип и значение prompt_template
        print(f"🔍 DEBUG news_generate: prompt_template type = {type(prompt_template)}", flush=True)
        print(f"🔍 DEBUG news_generate: prompt_template (первые 200 символов) = {str(prompt_template)[:200] if prompt_template else 'None'}", flush=True)
        
        # Убеждаемся, что prompt_template - это строка
        if not isinstance(prompt_template, str):
            print(f"⚠️ prompt_template не строка: {type(prompt_template)} = {prompt_template}", flush=True)
            prompt_template = default_prompt
        else:
            # Принудительно преобразуем в строку (на случай, если это bytes или что-то еще)
            try:
                prompt_template = str(prompt_template)
            except Exception as conv_err:
                print(f"⚠️ Ошибка преобразования prompt_template в строку: {conv_err}", flush=True)
                prompt_template = default_prompt
        
        # Финальная проверка
        if not isinstance(prompt_template, str):
            print(f"❌ prompt_template всё ещё не строка после преобразования: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt
        
        # Принудительно преобразуем в обычную строку Python (не bytes, не специальные типы)
        try:
            if isinstance(prompt_template, bytes):
                prompt_template = prompt_template.decode('utf-8')
            else:
                prompt_template = str(prompt_template)
        except Exception as conv_err:
            print(f"⚠️ Ошибка финального преобразования prompt_template: {conv_err}", flush=True)
            prompt_template = default_prompt
        
        # Форматируем промпт с обработкой ошибок
        try:
            # Преобразуем все аргументы в строки для безопасности
            prompt = prompt_template.format(
                language_name=str(language_name),
                service_context=str(service_context),
                transaction_context=str(transaction_context),
                raw_info=str(raw_info[:800]),
                news_examples=str(news_examples)
            )
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            print(f"⚠️ Ошибка форматирования промпта: {e}. Используем default_prompt", flush=True)
            import traceback
            traceback.print_exc()
            # Используем default_prompt как fallback
            prompt = default_prompt.format(
                language_name=str(language_name),
                service_context=str(service_context),
                transaction_context=str(transaction_context),
                raw_info=str(raw_info[:800]),
                news_examples=str(news_examples)
        )

        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') or data.get('business_id'))
        result = analyze_text_with_gigachat(
            prompt, 
            task_type="news_generation",
            business_id=business_id,
            user_id=user_data['user_id']
        )
        
        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку, не словарь
        print(f"🔍 DEBUG news_generate: result type = {type(result)}")
        print(f"🔍 DEBUG news_generate: result = {result[:200] if isinstance(result, str) else result}")
        
        # Обрабатываем результат - analyze_text_with_gigachat возвращает строку
        if isinstance(result, dict):
            # Если словарь (на всякий случай), проверяем наличие ошибки
            if 'error' in result:
                db.close()
                return jsonify({"error": result['error']}), 500
            generated_text = result.get('news') or result.get('text') or json.dumps(result, ensure_ascii=False)
        elif not isinstance(result, str):
            # Если не строка и не словарь, конвертируем в строку
            generated_text = str(result)
        else:
            # Если строка, пробуем распарсить как JSON
            generated_text = result
            parsed_result = None
            try:
                # Ищем JSON объект в строке
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = result[start_idx:end_idx]
                    parsed_result = json.loads(json_str)
            except json.JSONDecodeError:
                # Если не JSON (например, кавычки внутри), пробуем регулярку/ручной парсинг
                try:
                    import re
                    # Ищем pattern: "news": "..."
                    # Используем non-greedy match для содержимого, но так как внутри могут быть кавычки,
                    # это сложно. Попробуем взять все между первыми и последними кавычками значения.
                    match = re.search(r'"news"\s*:\s*"(.*)"\s*\}', result, re.DOTALL)
                    if match:
                        generated_text = match.group(1)
                        # Экранированные кавычки возвращаем обратно, если они были правильно экранированы
                        # Но скорее всего проблема в неэкранированных.
                        # В простом случае просто вернем то что нашли.
                        parsed_result = {"news": generated_text}
                except Exception:
                    pass

            if isinstance(parsed_result, dict):
                # Проверяем наличие ошибки
                if 'error' in parsed_result:
                    db.close()
                    return jsonify({"error": parsed_result['error']}), 500
                
                # Используем явную проверку ключей, чтобы пустая строка не вызывала фолбэк
                if 'news' in parsed_result:
                    generated_text = parsed_result['news']
                elif 'text' in parsed_result:
                    generated_text = parsed_result['text']
                else:
                    # Если ключей нет, но это словарь - странно, но оставим result или json dump
                    pass
        
        # Проверяем, что generated_text не пустой
        if not generated_text or not generated_text.strip():
            db.close()
            return jsonify({"error": "Пустой результат генерации"}), 500

        news_id = str(uuid.uuid4())
        prompt_key = "news_social_generation" if content_mode == "social" else "news_generation"
        prompt_version = "v1"
        cur.execute(
            """
            INSERT INTO usernews (
                id, user_id, service_id, source_text, generated_text, original_generated_text,
                edited_before_approve, prompt_key, prompt_version
            )
            VALUES (%s, %s, %s, %s, %s, %s, FALSE, %s, %s)
            """,
            (
                news_id,
                user_data['user_id'],
                selected_service_id,
                raw_info,
                generated_text,
                generated_text,
                prompt_key,
                prompt_version,
            )
        )
        db.conn.commit()
        db.close()

        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') or data.get('business_id'))
        record_ai_learning_event(
            capability="news.generate",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            draft_text=generated_text,
            metadata={
                "content_mode": content_mode,
                "social_format": social_format,
                "ab_mode": ab_mode,
                "news_id": news_id,
            },
        )

        return jsonify({"success": True, "news_id": news_id, "generated_text": generated_text})
    except Exception as e:
        print(f"❌ Ошибка генерации новости: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/approve', methods=['POST', 'OPTIONS'])
def news_approve():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        news_id = data.get('news_id')
        if not news_id:
            return jsonify({"error": "news_id обязателен"}), 400

        db = DatabaseManager()
        cur = db.conn.cursor()
        # ensure table exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_usernews_learning_columns(cur)
        cur.execute(
            """
            SELECT id, service_id, generated_text, original_generated_text, edited_before_approve, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
            """,
            (news_id, user_data['user_id']),
        )
        current_row = cur.fetchone()
        if not current_row:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        current_data = _row_to_dict(cur, current_row)
        cur.execute("UPDATE usernews SET approved = 1 WHERE id = %s AND user_id = %s", (news_id, user_data['user_id']))
        if cur.rowcount == 0:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit()
        db.close()
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
        record_ai_learning_event(
            capability="news.generate",
            event_type="accepted",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            accepted=True,
            edited_before_accept=bool(current_data.get("edited_before_approve")),
            prompt_key=str(current_data.get("prompt_key") or "news_generation"),
            prompt_version=str(current_data.get("prompt_version") or "v1"),
            draft_text=str(current_data.get("original_generated_text") or current_data.get("generated_text") or ""),
            final_text=str(current_data.get("generated_text") or ""),
            metadata={"news_id": news_id},
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка утверждения новости: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/list', methods=['GET', 'OPTIONS'])
def news_list():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_usernews_learning_columns(cur)
        cur.execute(
            "SELECT id, service_id, source_text, generated_text, original_generated_text, edited_before_approve, approved, created_at FROM usernews WHERE user_id = %s ORDER BY created_at DESC",
            (user_data['user_id'],),
        )
        rows = cur.fetchall()
        db.close()
        items = []
        for row in rows:
            if isinstance(row, tuple):
                items.append({
                    "id": row[0], "service_id": row[1], "source_text": row[2],
                    "generated_text": row[3],
                    "original_generated_text": row[4],
                    "edited_before_approve": bool(row[5]),
                    "approved": bool(row[6]),
                    "created_at": row[7]
                })
            else:
                items.append({
                    "id": row['id'], "service_id": row['service_id'], "source_text": row['source_text'],
                    "generated_text": row['generated_text'],
                    "original_generated_text": row.get('original_generated_text'),
                    "edited_before_approve": bool(row.get('edited_before_approve')),
                    "approved": bool(row['approved']),
                    "created_at": row['created_at']
                })
        return jsonify({"success": True, "news": items})
    except Exception as e:
        print(f"❌ Ошибка получения списка новостей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/update', methods=['POST', 'OPTIONS'])
def news_update():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        news_id = data.get('news_id'); text = (data.get('text') or '').strip()
        if not news_id or not text:
            return jsonify({"error": "news_id и text обязательны"}), 400
        db = DatabaseManager(); cur = db.conn.cursor()
        _ensure_usernews_learning_columns(cur)
        cur.execute(
            """
            SELECT generated_text, original_generated_text, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
            """,
            (news_id, user_data['user_id']),
        )
        existing_row = cur.fetchone()
        if not existing_row:
            db.close(); return jsonify({"error": "Новость не найдена"}), 404
        existing = _row_to_dict(cur, existing_row)
        original_generated_text = str(existing.get("original_generated_text") or existing.get("generated_text") or "")
        edited_before_approve = _normalize_text_for_semantic_compare(text) != _normalize_text_for_semantic_compare(original_generated_text)
        cur.execute(
            """
            UPDATE usernews
            SET generated_text = %s,
                edited_before_approve = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
            """,
            (text, edited_before_approve, news_id, user_data['user_id']),
        )
        if cur.rowcount == 0:
            db.close(); return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit(); db.close()
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
        record_ai_learning_event(
            capability="news.generate",
            event_type="edited",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            accepted=None,
            edited_before_accept=edited_before_approve,
            prompt_key=str(existing.get("prompt_key") or "news_generation"),
            prompt_version=str(existing.get("prompt_version") or "v1"),
            draft_text=original_generated_text,
            final_text=text,
            metadata={"news_id": news_id},
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка обновления новости: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/delete', methods=['POST', 'OPTIONS'])
def news_delete():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        news_id = data.get('news_id')
        if not news_id:
            return jsonify({"error": "news_id обязателен"}), 400
        
        db = DatabaseManager()
        cur = db.conn.cursor()
        _ensure_usernews_learning_columns(cur)
        cur.execute(
            """
            SELECT id, approved, generated_text, original_generated_text, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
            """,
            (news_id, user_data['user_id']),
        )
        existing_row = cur.fetchone()
        if not existing_row:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        existing = _row_to_dict(cur, existing_row)
        cur.execute("DELETE FROM usernews WHERE id = %s AND user_id = %s", (news_id, user_data['user_id']))
        deleted = cur.rowcount
        db.conn.commit()
        db.close()

        if deleted == 0:
            return jsonify({"error": "Новость не найдена"}), 404
        if not bool(existing.get("approved")):
            business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') or data.get('business_id'))
            record_ai_learning_event(
                capability="news.generate",
                event_type="rejected",
                intent="operations",
                user_id=user_data['user_id'],
                business_id=business_id,
                rejected=True,
                prompt_key=str(existing.get("prompt_key") or "news_generation"),
                prompt_version=str(existing.get("prompt_version") or "v1"),
                draft_text=str(existing.get("original_generated_text") or existing.get("generated_text") or ""),
                final_text=None,
                metadata={"news_id": news_id, "via": "delete"},
            )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления новости: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== ПРИМЕРЫ ДЛЯ ОТЗЫВОВ И НОВОСТЕЙ ====================
@app.route('/api/review-examples', methods=['GET', 'POST', 'OPTIONS'])
def review_examples():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager(); cur = db.conn.cursor()
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                rd = _row_to_dict(cur, row) if row else {}
                items.append({"id": rd.get("id"), "text": rd.get("example_text"), "created_at": rd.get("created_at")})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'review'", (user_data['user_id'],))
        cnt_row = cur.fetchone()
        cnt_data = _row_to_dict(cur, cnt_row) if cnt_row else {}
        cnt = cnt_data.get("cnt", 0) or 0
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'review', %s)",
            (ex_id, user_data['user_id'], text),
        )
        db.conn.commit(); db.close()
        return jsonify({"success": True, "id": ex_id})
    except Exception as e:
        print(f"❌ Ошибка примеров отзывов: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/review-examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def review_examples_delete(example_id: str):
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        db = DatabaseManager(); cur = db.conn.cursor()
        cur.execute(
            "DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'review'",
            (example_id, user_data['user_id']),
        )
        deleted = cur.rowcount
        db.conn.commit(); db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера отзывов: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news-examples', methods=['GET', 'POST', 'OPTIONS'])
def news_examples():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager(); cur = db.conn.cursor()
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                if isinstance(row, tuple):
                    items.append({"id": row[0], "text": row[1], "created_at": row[2]})
                else:
                    items.append({"id": row['id'], "text": row['example_text'], "created_at": row['created_at']})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'news'", (user_data['user_id'],))
        cnt_row = cur.fetchone()
        cnt_data = _row_to_dict(cur, cnt_row) if cnt_row else {}
        cnt = cnt_data.get("cnt", 0) or 0
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'news', %s)",
            (ex_id, user_data['user_id'], text),
        )
        db.conn.commit(); db.close()
        return jsonify({"success": True, "id": ex_id})
    except Exception as e:
        print(f"❌ Ошибка примеров новостей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news-examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def news_examples_delete(example_id: str):
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        db = DatabaseManager(); cur = db.conn.cursor()
        cur.execute("DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'news'", (example_id, user_data['user_id']))
        deleted = cur.rowcount
        db.conn.commit(); db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера новостей: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/news/ab-mode/availability', methods=['GET', 'OPTIONS'])
def news_ab_mode_availability():
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        is_superadmin = bool(user_data.get("is_superadmin")) if isinstance(user_data, dict) else False
        is_test_mode = os.getenv("NEWS_AB_TEST_MODE", "1").strip().lower() in ("1", "true", "yes", "on")
        return jsonify({
            "success": True,
            "allowed": bool(is_superadmin and is_test_mode),
            "is_superadmin": is_superadmin,
            "test_mode": is_test_mode,
        })
    except Exception as e:
        print(f"❌ Ошибка проверки доступности news AB mode: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== СЕРВИС: ОТВЕТЫ НА ОТЗЫВЫ ====================
@app.route('/api/reviews/reply', methods=['POST', 'OPTIONS'])
def reviews_reply():
    """Сгенерировать короткий вежливый ответ на отзыв в заданном тоне."""
    import sys
    print(f"🔍 Начало обработки запроса /api/reviews/reply", file=sys.stderr, flush=True)
    print(f"🔍 Начало обработки запроса /api/reviews/reply", flush=True)
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем, что user_data - это словарь
        if not isinstance(user_data, dict):
            print(f"⚠️ user_data не словарь: {type(user_data)} = {user_data}", flush=True)
            return jsonify({"error": "Ошибка авторизации: неверный формат данных пользователя"}), 401

        data = request.get_json() or {}
        review_text = (data.get('review') or '').strip()
        tone = (data.get('tone') or 'профессиональный').strip()

        # Язык ответа: получаем из запроса или из профиля пользователя
        requested_language = data.get('language')
        language = get_user_language(user_data['user_id'], requested_language)
        language_names = {
            'ru': 'Russian',
            'en': 'English',
            'es': 'Spanish',
            'de': 'German',
            'fr': 'French',
            'it': 'Italian',
            'pt': 'Portuguese',
            'zh': 'Chinese'
        }
        language_name = language_names.get(language, 'Russian')
        if not review_text:
            return jsonify({"error": "Не передан текст отзыва"}), 400
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))

        # Подтянем примеры ответов пользователя (до 5)
        # Сначала проверяем, переданы ли примеры в запросе
        examples_from_request = data.get('examples', [])
        examples_text = ""
        
        if examples_from_request and isinstance(examples_from_request, list):
            # Используем примеры из запроса
            examples_text = "\n".join(examples_from_request[:5])
        else:
            # Иначе загружаем из БД
            try:
                db = DatabaseManager()
                cur = db.conn.cursor()
                from core.db_helpers import ensure_user_examples_table
                ensure_user_examples_table(cur)
                cur.execute(
                    "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC LIMIT 5",
                    (user_data['user_id'],),
                )
                rows = cur.fetchall(); db.close()
                examples = []
                for row in rows:
                    if isinstance(row, tuple) and len(row) > 0:
                        examples.append(row[0])
                    elif isinstance(row, dict):
                        examples.append(row.get('example_text', ''))
                    elif hasattr(row, '__getitem__'):
                        try:
                            examples.append(row[0] if len(row) > 0 else '')
                        except (TypeError, KeyError):
                            try:
                                examples.append(row['example_text'])
                            except (TypeError, KeyError):
                                pass
                if examples:
                    examples_text = "\n".join(examples)
            except Exception:
                examples_text = ""

        # Подтягиваем SEO-ключи (Top-10), чтобы ответы были ближе к целевому семантическому ядру
        seo_keywords_list = []
        seo_keywords_top10 = ""
        if business_id:
            try:
                from core.seo_keywords import collect_ranked_keywords
                db_kw = DatabaseManager()
                cur_kw = db_kw.conn.cursor()
                ranked = collect_ranked_keywords(cur_kw, business_id=business_id, limit=10)
                seo_keywords_list = [str((it or {}).get("keyword", "")).strip() for it in (ranked or {}).get("items", [])]
                seo_keywords_list = [kw for kw in seo_keywords_list if kw]
                seo_keywords_top10 = ", ".join(seo_keywords_list[:10])
                db_kw.close()
            except Exception as kw_err:
                print(f"⚠️ reviews_reply: не удалось загрузить SEO-ключи: {kw_err}", flush=True)

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt_template = """Ты - вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Write the reply in {language_name}.
Если уместно, ориентируйся на стиль этих примеров (если они есть):
{examples_text}
SEO Wordstat ключи (если есть): {seo_keywords}
Top-10 SEO ключей: {seo_keywords_top10}
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text}"""
        
        prompt_template = get_prompt_from_db('review_reply', default_prompt_template)
        
        # Логируем тип и значение prompt_template
        print(f"🔍 DEBUG reviews_reply: prompt_template type = {type(prompt_template)}", flush=True)
        print(f"🔍 DEBUG reviews_reply: prompt_template (первые 200 символов) = {str(prompt_template)[:200] if prompt_template else 'None'}", flush=True)
        
        # Убеждаемся, что prompt_template - это строка
        if not isinstance(prompt_template, str):
            print(f"⚠️ prompt_template не строка: {type(prompt_template)} = {prompt_template}", flush=True)
            prompt_template = default_prompt_template
        else:
            # Принудительно преобразуем в строку (на случай, если это bytes или что-то еще)
            try:
                prompt_template = str(prompt_template)
            except Exception as conv_err:
                print(f"⚠️ Ошибка преобразования prompt_template в строку: {conv_err}", flush=True)
                prompt_template = default_prompt_template
        
        # Финальная проверка
        if not isinstance(prompt_template, str):
            print(f"❌ prompt_template всё ещё не строка после преобразования: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt_template
        
        # Принудительно преобразуем в обычную строку Python (не bytes, не специальные типы)
        try:
            if isinstance(prompt_template, bytes):
                prompt_template = prompt_template.decode('utf-8')
            else:
                prompt_template = str(prompt_template)
        except Exception as conv_err:
            print(f"⚠️ Ошибка финального преобразования prompt_template: {conv_err}", flush=True)
            prompt_template = default_prompt_template
        
        # Убеждаемся, что это действительно строка
        if not isinstance(prompt_template, str):
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: prompt_template не строка: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt_template
        
        # Логируем все аргументы перед format
        print(f"🔍 DEBUG reviews_reply: tone type = {type(tone)}, value = {tone}", flush=True)
        print(f"🔍 DEBUG reviews_reply: language_name type = {type(language_name)}, value = {language_name}", flush=True)
        print(f"🔍 DEBUG reviews_reply: examples_text type = {type(examples_text)}, value (первые 100) = {str(examples_text)[:100] if examples_text else 'None'}", flush=True)
        print(f"🔍 DEBUG reviews_reply: review_text type = {type(review_text)}, value (первые 100) = {str(review_text)[:100] if review_text else 'None'}", flush=True)
        
        # Принудительно преобразуем все аргументы в строки
        tone_str = str(tone) if tone else ''
        language_name_str = str(language_name) if language_name else 'Russian'
        examples_text_str = str(examples_text) if examples_text else ''
        review_text_str = str(review_text[:1000]) if review_text else ''
        
        try:
            prompt = prompt_template.format(
                tone=tone_str,
                language_name=language_name_str,
                examples_text=examples_text_str,
                review_text=review_text_str,
                seo_keywords=seo_keywords_top10,
                seo_keywords_top10=seo_keywords_top10
            )
        except (KeyError, ValueError, TypeError) as format_err:
            print(f"⚠️ Ошибка форматирования промпта: {format_err}, type: {type(format_err)}", flush=True)
            import traceback
            traceback.print_exc()
            # Используем default_prompt_template как fallback
            prompt = default_prompt_template.format(
                tone=tone_str,
                language_name=language_name_str,
                examples_text=examples_text_str,
                review_text=review_text_str,
                seo_keywords=seo_keywords_top10,
                seo_keywords_top10=seo_keywords_top10
            )
        # Логируем промпт для отладки
        print(f"🔍 DEBUG reviews_reply: prompt (первые 500 символов) = {prompt[:500]}")
        print(f"🔍 DEBUG reviews_reply: review_text = {review_text[:200] if review_text else 'ПУСТО'}")
        print(f"🔍 DEBUG reviews_reply: examples_text (первые 200 символов) = {examples_text[:200] if examples_text else 'ПУСТО'}")
        
        result_text = analyze_text_with_gigachat(
            prompt, 
            task_type="review_reply",
            business_id=business_id,
            user_id=user_data['user_id']
        )
        
        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку
        print(f"🔍 DEBUG reviews_reply: result_text type = {type(result_text)}")
        print(f"🔍 DEBUG reviews_reply: result_text = {result_text[:200] if isinstance(result_text, str) else result_text}")
        
        # Парсим JSON из ответа GigaChat
        import json
        reply_text = "Ошибка генерации ответа"
        
        # Проверяем тип result_text перед обработкой
        if result_text is None:
            print("⚠️ result_text is None")
            reply_text = "Ошибка генерации ответа"
        elif isinstance(result_text, dict):
            # Если словарь (не должно быть, но на всякий случай)
            print(f"⚠️ result_text is dict: {result_text}")
            if 'error' in result_text:
                print(f"❌ Ошибка в результате: {result_text.get('error')}")
                return jsonify({"error": result_text.get('error', 'Ошибка генерации')}), 500
            reply_text = result_text.get('reply') or str(result_text)
        elif isinstance(result_text, str):
            # Если строка - парсим JSON
            # Ищем JSON объект в строке
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = result_text[start_idx:end_idx]
                try:
                    parsed_result = json.loads(json_str)
                    if isinstance(parsed_result, dict):
                        # Проверяем наличие ошибки в распарсенном JSON
                        if 'error' in parsed_result:
                            print(f"❌ Ошибка в распарсенном JSON: {parsed_result.get('error')}")
                            return jsonify({"error": parsed_result.get('error', 'Ошибка генерации')}), 500
                    # Извлекаем reply из JSON
                    reply_text = parsed_result.get('reply', result_text)
                except json.JSONDecodeError as json_err:
                    # Если не удалось распарсить JSON, используем весь текст
                    print(f"⚠️ Ошибка парсинга JSON: {json_err}")
                    reply_text = result_text
            else:
                # Если JSON-объект не найден, возвращаем исходный текст модели
                reply_text = result_text
        else:
            # Если другой тип - конвертируем в строку
            print(f"⚠️ Неожиданный тип result_text: {type(result_text)}")
            reply_text = str(result_text) if result_text else "Ошибка генерации ответа"
        
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') if request else None)
        record_ai_learning_event(
            capability="reviews.reply",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            prompt_key="review_reply",
            prompt_version="v1",
            draft_text=reply_text,
            metadata={"tone": tone, "language": language},
        )
        return jsonify({"success": True, "result": {"reply": reply_text}})
    except Exception as e:
        import sys
        import traceback
        error_msg = f"❌ Ошибка генерации ответа на отзыв: {e}"
        print(error_msg, file=sys.stderr, flush=True)
        print(error_msg, flush=True)
        traceback.print_exc(file=sys.stderr)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/review-replies/update', methods=['POST', 'OPTIONS'])
def review_replies_update():
    """Сохранить отредактированный ответ на отзыв"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        reply_id = data.get('replyId') or data.get('reply_id')
        reply_text = (data.get('replyText') or data.get('reply_text') or '').strip()
        generated_text = str(data.get('generatedText') or data.get('generated_text') or '').strip()
        business_id = str(data.get('business_id') or '').strip()
        
        if not reply_id:
            return jsonify({"error": "ID ответа обязателен"}), 400
        
        if not reply_text:
            return jsonify({"error": "Текст ответа обязателен"}), 400
        
        # Создаем таблицу для хранения ответов на отзывы, если её нет
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS userreviewreplies (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_review TEXT,
                reply_text TEXT NOT NULL,
                tone TEXT DEFAULT 'профессиональный',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # Обновляем или создаем запись
        cursor.execute(
            """
            INSERT INTO userreviewreplies (id, user_id, reply_text, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE
            SET reply_text = EXCLUDED.reply_text,
                user_id = EXCLUDED.user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (reply_id, user_data['user_id'], reply_text),
        )
        
        db.conn.commit()
        db.close()

        normalized_generated = _normalize_text_for_semantic_compare(generated_text)
        normalized_reply = _normalize_text_for_semantic_compare(reply_text)
        edited_before_accept = bool(generated_text) and normalized_generated != normalized_reply
        record_ai_learning_event(
            capability="reviews.reply",
            event_type="accepted",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id if business_id else None,
            accepted=True,
            edited_before_accept=edited_before_accept,
            prompt_key="review_reply",
            prompt_version="v1",
            draft_text=generated_text or None,
            final_text=reply_text,
            metadata={"reply_id": reply_id},
        )
        
        return jsonify({"success": True, "message": "Ответ на отзыв сохранен"})
        
    except Exception as e:
        print(f"❌ Ошибка сохранения ответа на отзыв: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== СЕРВИС: УПРАВЛЕНИЕ УСЛУГАМИ ====================
@app.route('/api/services/add', methods=['POST', 'OPTIONS'])
def add_service():
    """Добавление услуги в список пользователя."""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Данные не предоставлены"}), 400

        category = data.get('category', 'Общие услуги')
        name = data.get('name', '')
        description = data.get('description', '')
        keywords = data.get('keywords', [])
        price = data.get('price', '')
        business_id = data.get('business_id')

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']
        service_id = str(uuid.uuid4())

        # Проверяем, есть ли поле business_id в таблице userservices
        columns = _table_columns(cursor, "userservices")

        if 'business_id' in columns and business_id:
            cursor.execute(
                """
                INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (service_id, user_id, business_id, category, name, description, json.dumps(keywords), price),
            )
        else:
            cursor.execute(
                """
                INSERT INTO userservices (id, user_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (service_id, user_id, category, name, description, json.dumps(keywords), price),
            )

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга добавлена"})

    except Exception as e:
        print(f"❌ Ошибка добавления услуги: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/list-legacy', methods=['GET', 'OPTIONS'])
def get_services_legacy():
    """Получение списка услуг пользователя."""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']
        
        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')
        
        # Если передан business_id - фильтруем по нему, иначе по user_id
        if business_id:
            # Проверяем доступ к бизнесу
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if owner_id:
                if owner_id == user_id or user_data.get('is_superadmin'):
                    # Проверяем, есть ли поля optimized_description и optimized_name
                    columns = _table_columns(cursor, "userservices")
                    has_optimized_desc = 'optimized_description' in columns
                    has_optimized_name = 'optimized_name' in columns
                    
    # Формируем SELECT с учетом наличия полей
                    select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
                    if has_optimized_desc:
                        select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                    if has_optimized_name:
                        select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
                    
                    select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE business_id = %s ORDER BY created_at DESC"
                    cursor.execute(select_sql, (business_id,))
                    
                    user_services = []
                    rows = cursor.fetchall()
                    for r in rows:
                        rd = r if hasattr(r, "keys") else None
                        if rd is None:
                            rd = {field: r[idx] for idx, field in enumerate(select_fields) if idx < len(r)}
                        srv = {
                            "id": rd.get("id"),
                            "category": rd.get("category"),
                            "name": rd.get("name"),
                            "description": rd.get("description"),
                            "keywords": rd.get("keywords"),
                            "price": rd.get("price"),
                            "created_at": rd.get("created_at"),
                            "updated_at": (str(rd.get("updated_at")) if rd.get("updated_at") else None),
                        }
                        if has_optimized_desc:
                            srv["optimized_description"] = rd.get("optimized_description")
                        if has_optimized_name:
                            srv["optimized_name"] = rd.get("optimized_name")
                        user_services.append(srv)

                    # Получаем внешние услуги
                    external_services = []
                    cursor.execute("SELECT to_regclass('public.externalbusinessservices')")
                    if cursor.fetchone():
                        # Проверяем колонки externalbusinessservices (Postgres)
                        cursor.execute("""
                            SELECT column_name FROM information_schema.columns 
                            WHERE table_schema = 'public' AND table_name = 'externalbusinessservices'
                        """)
                        ext_cols = [col['column_name'] if isinstance(col, dict) else col[0] for col in cursor.fetchall()]
                        ext_has_updated_at = 'updated_at' in ext_cols
                        
                        query_cols = "id, name, price, description, category, created_at"
                        if ext_has_updated_at:
                            query_cols += ", updated_at"
                            
                        cursor.execute(f"""
                            SELECT {query_cols}
                            FROM externalbusinessservices
                            WHERE business_id = %s
                        """, (business_id,))
                        
                        for r in cursor.fetchall():
                            rd = r if hasattr(r, "keys") else None
                            if rd is None:
                                rd = {
                                    "id": r[0],
                                    "name": r[1],
                                    "price": r[2],
                                    "description": r[3],
                                    "category": r[4],
                                    "created_at": r[5],
                                    "updated_at": r[6] if ext_has_updated_at and len(r) > 6 else None,
                                }
                            srv_obj = {
                                "id": rd.get("id"),
                                "name": rd.get("name"),
                                "price": rd.get("price"),
                                "description": rd.get("description"),
                                "category": rd.get("category"),
                                "created_at": rd.get("created_at"),
                                "is_external": True,
                            }
                            val = rd.get("updated_at") if ext_has_updated_at else rd.get("created_at")
                            srv_obj["updated_at"] = str(val) if val else None
                            external_services.append(srv_obj)

                    db.close()
                    return jsonify({
                        "success": True, 
                        "services": user_services,
                        "external_services": external_services
                    })
                else:
                    db.close()
                    return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            else:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
        else:
            # Старая логика для обратной совместимости
            # Проверяем, есть ли поля optimized_description и optimized_name
            columns = _table_columns(cursor, "userservices")
            has_optimized_desc = 'optimized_description' in columns
            has_optimized_name = 'optimized_name' in columns
            
            # Формируем SELECT с учетом наличия полей
            select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
            if has_optimized_desc:
                select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
            if has_optimized_name:
                select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
            
            select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE user_id = %s ORDER BY created_at DESC"
            print(f"🔍 DEBUG get_services: SQL запрос (старая логика) = {select_sql}", flush=True)
            print(f"🔍 DEBUG get_services: select_fields = {select_fields}", flush=True)
            # Сохраняем select_fields для использования в цикле
            _select_fields = select_fields
            _has_optimized_desc = has_optimized_desc
            _has_optimized_name = has_optimized_name
            
            cursor.execute(select_sql, (user_id,))
        
        services = cursor.fetchall()
        db.close()

        result = []
        # Используем глобальные переменные, если они установлены
        try:
            has_optimized_desc = _has_optimized_desc
            has_optimized_name = _has_optimized_name
            select_fields = _select_fields
        except NameError:
            # Если не установлены (старая логика), проверяем заново
            cursor_temp = db.conn.cursor() if 'db' in locals() else None
            if cursor_temp:
                columns = _table_columns(cursor_temp, "userservices")
                has_optimized_desc = 'optimized_description' in columns
                has_optimized_name = 'optimized_name' in columns
                select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
                if has_optimized_desc:
                    select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                if has_optimized_name:
                    select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
            else:
                has_optimized_desc = False
                has_optimized_name = False
                select_fields = []
        
        for service in services:
            # ПРОСТОЕ РЕШЕНИЕ: Преобразуем Row в словарь через dict()
            # Это гарантирует правильное извлечение всех полей, включая optimized_name и optimized_description
            if hasattr(service, 'keys'):
                service_dict = dict(service)  # Преобразуем Row в dict
            else:
                # Fallback для tuple/list - создаем словарь по порядку полей
                service_dict = {field_name: service[idx] for idx, field_name in enumerate(select_fields) if idx < len(service)}
            
            # Парсим keywords
            raw_kw = service_dict.get('keywords')
            parsed_kw = []
            if raw_kw:
                try:
                    parsed_kw = json.loads(raw_kw)
                    if not isinstance(parsed_kw, list):
                        parsed_kw = []
                except Exception:
                    parsed_kw = [k.strip() for k in str(raw_kw).split(',') if k.strip()]
            service_dict['keywords'] = parsed_kw
            
            # optimized_name и optimized_description уже будут в service_dict после dict(service)
            # Дополнительная проверка не нужна, т.к. dict(service) извлекает все поля из Row
            
            # Логируем для отладки (только для первой услуги и для услуги с ID 3772931e-9796-475b-b439-ee1cc07b1dc9)
            service_id = service_dict.get('id')
            if len(result) == 0 or service_id == '3772931e-9796-475b-b439-ee1cc07b1dc9':
                print(f"🔍 DEBUG get_services: Услуга {service_id}", flush=True)
                print(f"🔍 DEBUG get_services: service_dict keys = {list(service_dict.keys())}", flush=True)
                print(f"🔍 DEBUG get_services: optimized_name = {service_dict.get('optimized_name')}", flush=True)
                print(f"🔍 DEBUG get_services: optimized_description = {service_dict.get('optimized_description')[:50] if service_dict.get('optimized_description') else None}...", flush=True)
            
            result.append(service_dict)

        return jsonify({"success": True, "services": result})

    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/update/<string:service_id>', methods=['PUT', 'OPTIONS'])
def update_service(service_id):
    """Обновление существующей услуги пользователя."""
    try:
        print(f"🔍 Начало обновления услуги: {service_id}", flush=True)
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Данные не предоставлены"}), 400

        print(f"🔍 DEBUG update_service: data keys = {list(data.keys())}", flush=True)

        category = data.get('category', '')
        name = data.get('name', '')
        description = data.get('description', '')
        optimized_description = data.get('optimized_description', '')  # Новое поле для SEO описания
        keywords = data.get('keywords', [])
        price = data.get('price', '')
        user_id = user_data['user_id']
        
        print(f"🔍 DEBUG update_service: keywords type = {type(keywords)}, value = {keywords}", flush=True)
        
        # Преобразуем keywords в строку JSON, если это массив
        if isinstance(keywords, list):
            keywords_str = json.dumps(keywords, ensure_ascii=False)
        elif isinstance(keywords, str):
            keywords_str = keywords
        else:
            keywords_str = json.dumps([])
        
        print(f"🔍 DEBUG update_service: keywords_str = {keywords_str[:100]}", flush=True)

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, есть ли поля optimized_description и optimized_name в таблице
        columns = _table_columns(cursor, "userservices")
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG update_service: columns = {columns}", flush=True)
        print(f"🔍 DEBUG update_service: optimized_name = '{optimized_name}' (type: {type(optimized_name)}, length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG update_service: optimized_description = '{optimized_description[:100] if optimized_description else ''}...' (type: {type(optimized_description)}, length: {len(optimized_description) if optimized_description else 0})", flush=True)

        cursor.execute(
            """
            SELECT name, description, optimized_name, optimized_description, business_id
            FROM userservices
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (service_id, user_id),
        )
        previous_row = cursor.fetchone()
        if not previous_row:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        previous_data = _row_to_dict(cursor, previous_row) or {}
        
        if has_optimized_description and has_optimized_name:
            print(f"🔍 DEBUG update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute(
                """
                UPDATE userservices SET
                category = %s, name = %s, optimized_name = %s, description = %s,
                optimized_description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (category, name, optimized_name, description, optimized_description, keywords_str, price, service_id, user_id),
            )
            print(f"✅ DEBUG update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)

        else:
            print(f"🔍 DEBUG update_service: Обновление БЕЗ optimized_description/name", flush=True)
            cursor.execute(
                """
                UPDATE userservices SET
                category = %s, name = %s, description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (category, name, description, keywords_str, price, service_id, user_id),
            )

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        db.conn.commit()
        db.close()

        request_business_id = _resolve_request_business_id(user_data, json_data=data)
        service_business_id = str(previous_data.get("business_id") or "").strip() or None
        business_id = request_business_id or service_business_id
        prev_name = str(previous_data.get("name") or "")
        prev_description = str(previous_data.get("description") or "")
        prev_optimized_name = str(previous_data.get("optimized_name") or "")
        prev_optimized_description = str(previous_data.get("optimized_description") or "")
        next_name = str(name or "")
        next_description = str(description or "")
        next_optimized_name = str(optimized_name or "")
        next_optimized_description = str(optimized_description or "")

        if prev_optimized_name and not next_optimized_name:
            accepted_name = _normalize_text_for_semantic_compare(next_name) != _normalize_text_for_semantic_compare(prev_name)
            if accepted_name:
                edited_before_accept = _normalize_text_for_semantic_compare(next_name) != _normalize_text_for_semantic_compare(prev_optimized_name)
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="accepted",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    accepted=True,
                    edited_before_accept=edited_before_accept,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_name,
                    final_text=next_name,
                    metadata={"field": "name", "service_id": service_id},
                )
            else:
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="rejected",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    rejected=True,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_name,
                    final_text=prev_name,
                    metadata={"field": "name", "service_id": service_id},
                )

        if prev_optimized_description and not next_optimized_description:
            accepted_description = _normalize_text_for_semantic_compare(next_description) != _normalize_text_for_semantic_compare(prev_description)
            if accepted_description:
                edited_before_accept = _normalize_text_for_semantic_compare(next_description) != _normalize_text_for_semantic_compare(prev_optimized_description)
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="accepted",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    accepted=True,
                    edited_before_accept=edited_before_accept,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_description,
                    final_text=next_description,
                    metadata={"field": "description", "service_id": service_id},
                )
            else:
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="rejected",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    rejected=True,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_description,
                    final_text=prev_description,
                    metadata={"field": "description", "service_id": service_id},
                )

        return jsonify({"success": True, "message": "Услуга обновлена"})

    except Exception as e:
        print(f"❌ Ошибка обновления услуги: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/delete/<string:service_id>', methods=['DELETE', 'OPTIONS'])
def delete_service(service_id):
    """Удаление услуги пользователя."""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data['user_id']

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM userservices WHERE id = %s AND user_id = %s", (service_id, user_id))

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для удаления"}), 404

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга удалена"})

    except Exception as e:
        print(f"❌ Ошибка удаления услуги: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== КЛИЕНТСКАЯ ИНФОРМАЦИЯ (ПРОФИЛЬ БИЗНЕСА) ====================
@app.route('/api/client-info', methods=['GET', 'POST', 'PUT', 'OPTIONS'])
def client_info():
    try:
        # Preflight
        if request.method == 'OPTIONS':
            return ('', 204)

        # Авторизация
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        print(f"🔍 /api/client-info: method={request.method}, user_id={user_id}")

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Postgres-only: данные профиля из businesses, userservices, businessprofiles, users;
        # ссылки на карты — только из businessmaplinks. Таблица ClientInfo не используется.

        if request.method == 'GET':
            current_business_id = request.args.get('business_id')
            print(f"🔍 GET /api/client-info: method=GET, business_id={current_business_id}, user_id={user_id}")
            
            # Если передан business_id — данные только из таблицы businesses (lowercase). Фильтр is_active согласован с dropdown (auth/me).
            if current_business_id:
                print(f"🔍 GET /api/client-info: Ищу бизнес в таблице businesses, business_id={current_business_id}")
                cursor.execute(
                    "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
                    (current_business_id,),
                )
                business_row = cursor.fetchone()
                row_dict = _row_to_dict(cursor, business_row)

                if row_dict:
                    owner_id = row_dict.get("owner_id")
                    business_name, business_type, address, working_hours = _business_display_fields(row_dict)
                    is_active_val = row_dict.get("is_active")
                    city = (row_dict.get("city") or "").strip() or None
                    geo_lat = row_dict.get("geo_lat")
                    geo_lon = row_dict.get("geo_lon")
                    city_suggestion = None
                    if not city and address:
                        city_suggestion = suggest_city_from_address(address)
                    print(f"🔍 GET /api/client-info: Бизнес найден, owner_id={owner_id}, name={business_name!r}, is_active={is_active_val}")
                    if owner_id == user_id or user_data.get("is_superadmin"):
                        print(f"✅ GET /api/client-info: Доступ разрешен, возвращаю данные из businesses")
                        links = []
                        cursor.execute("""
                            SELECT id, url, map_type, created_at 
                            FROM businessmaplinks 
                            WHERE business_id = %s 
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        link_rows = cursor.fetchall()
                        for r in link_rows:
                            rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                            if rd:
                                links.append({
                                    "id": rd.get("id"),
                                    "url": rd.get("url") or "",
                                    "mapType": rd.get("map_type") or "other",
                                    "createdAt": rd.get("created_at"),
                                })

                        cursor.execute("""
                            SELECT name, description, category, price 
                            FROM userservices 
                            WHERE business_id = %s 
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        services_rows = cursor.fetchall()
                        services_list = []
                        for r in services_rows:
                            rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                            if rd:
                                services_list.append({
                                    "name": rd.get("name") or "",
                                    "description": rd.get("description") or "",
                                    "category": rd.get("category") or "",
                                    "price": rd.get("price") or "",
                                })

                        owner_data = None
                        cursor.execute("SELECT contact_name, contact_phone, contact_email FROM businessprofiles WHERE business_id = %s", (current_business_id,))
                        profile_row = cursor.fetchone()
                        if profile_row:
                            pr = _row_to_dict(cursor, profile_row)
                            if pr and (pr.get("contact_name") or pr.get("contact_phone") or pr.get("contact_email")):
                                owner_data = {
                                    "id": owner_id,
                                    "name": (pr.get("contact_name") or "").strip(),
                                    "phone": (pr.get("contact_phone") or "").strip(),
                                    "email": (pr.get("contact_email") or "").strip(),
                                }
                        if not owner_data and owner_id:
                            cursor.execute("SELECT id, email, name, phone FROM users WHERE id = %s", (owner_id,))
                            owner_row = cursor.fetchone()
                            if owner_row:
                                ur = _row_to_dict(cursor, owner_row)
                                if ur:
                                    owner_data = {
                                        "id": ur.get("id"),
                                        "email": ur.get("email") or "",
                                        "name": ur.get("name") or "",
                                        "phone": ur.get("phone") or "",
                                    }

                        payload = {
                            "success": True,
                            "businessName": business_name or "",
                            "businessType": business_type or "",
                            "address": address or "",
                            "workingHours": working_hours or "",
                            "city": city or "",
                            "citySuggestion": city_suggestion or "",
                            "geoLat": geo_lat,
                            "geoLon": geo_lon,
                            "description": "",
                            "services": services_list,
                            "mapLinks": links,
                            "owner": owner_data,
                        }
                        if getattr(app, "debug", False):
                            payload["_debug"] = {
                                "foundBusiness": True,
                                "isActive": is_active_val,
                                "returnedName": business_name or "",
                            }
                        db.close()
                        return jsonify(payload)
                    else:
                        print(f"❌ GET /api/client-info: Нет доступа к бизнесу, owner_id={owner_id}, user_id={user_id}")
                        db.close()
                        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
                else:
                    print(f"⚠️ GET /api/client-info: Бизнес не найден, business_id={current_business_id}")
                    err_payload = {"error": "Бизнес не найден"}
                    if getattr(app, "debug", False):
                        err_payload["_debug"] = {"foundBusiness": False, "isActive": None, "returnedName": ""}
                    db.close()
                    return jsonify(err_payload), 404

            # business_id не передан — первый бизнес пользователя (фильтр is_active как в dropdown)
            cursor.execute(
                "SELECT id FROM businesses WHERE owner_id = %s AND (is_active = TRUE OR is_active IS NULL) ORDER BY created_at ASC LIMIT 1",
                (user_id,),
            )
            first_row = cursor.fetchone()
            if not first_row:
                db.close()
                return jsonify({
                    "success": True,
                    "businessName": "",
                    "businessType": "",
                    "address": "",
                    "workingHours": "",
                    "description": "",
                    "services": [],
                    "mapLinks": [],
                    "owner": None
                })
            first_dict = _row_to_dict(cursor, first_row)
            current_business_id = first_dict.get("id") if first_dict else None
            if not current_business_id:
                db.close()
                return jsonify({"success": True, "businessName": "", "businessType": "", "address": "", "workingHours": "", "description": "", "services": [], "mapLinks": [], "owner": None})
            cursor.execute(
                "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
                (current_business_id,),
            )
            business_row = cursor.fetchone()
            row_dict = _row_to_dict(cursor, business_row)
            if not row_dict:
                db.close()
                return jsonify({"success": True, "businessName": "", "businessType": "", "address": "", "workingHours": "", "city": "", "citySuggestion": "", "geoLat": None, "geoLon": None, "description": "", "services": [], "mapLinks": [], "owner": None})
            owner_id = row_dict.get("owner_id")
            business_name, business_type, address, working_hours = _business_display_fields(row_dict)
            is_active_val = row_dict.get("is_active")
            city = (row_dict.get("city") or "").strip() or None
            geo_lat, geo_lon = row_dict.get("geo_lat"), row_dict.get("geo_lon")
            city_suggestion = suggest_city_from_address(address) if not city and address else None
            links = []
            cursor.execute("""
                SELECT id, url, map_type, created_at FROM businessmaplinks WHERE business_id = %s ORDER BY created_at DESC
            """, (current_business_id,))
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                if rd:
                    links.append({
                        "id": rd.get("id"),
                        "url": rd.get("url") or "",
                        "mapType": rd.get("map_type") or "other",
                        "createdAt": rd.get("created_at"),
                    })
            cursor.execute("SELECT name, description, category, price FROM userservices WHERE business_id = %s ORDER BY created_at DESC", (current_business_id,))
            services_list = []
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                if rd:
                    services_list.append({
                        "name": rd.get("name") or "",
                        "description": rd.get("description") or "",
                        "category": rd.get("category") or "",
                        "price": rd.get("price") or "",
                    })
            owner_data = None
            cursor.execute("SELECT contact_name, contact_phone, contact_email FROM businessprofiles WHERE business_id = %s", (current_business_id,))
            profile_row = cursor.fetchone()
            if profile_row:
                pr = _row_to_dict(cursor, profile_row)
                if pr and (pr.get("contact_name") or pr.get("contact_phone") or pr.get("contact_email")):
                    owner_data = {"id": owner_id, "name": (pr.get("contact_name") or "").strip(), "phone": (pr.get("contact_phone") or "").strip(), "email": (pr.get("contact_email") or "").strip()}
            if not owner_data and owner_id:
                cursor.execute("SELECT id, email, name, phone FROM users WHERE id = %s", (owner_id,))
                owner_row = cursor.fetchone()
                if owner_row:
                    ur = _row_to_dict(cursor, owner_row)
                    if ur:
                        owner_data = {"id": ur.get("id"), "email": ur.get("email") or "", "name": ur.get("name") or "", "phone": ur.get("phone") or ""}
            payload = {
                "success": True,
                "businessName": business_name or "",
                "businessType": business_type or "",
                "address": address or "",
                "workingHours": working_hours or "",
                "city": city or "",
                "citySuggestion": city_suggestion or "",
                "geoLat": geo_lat,
                "geoLon": geo_lon,
                "description": "",
                "services": services_list,
                "mapLinks": links,
                "owner": owner_data,
            }
            if getattr(app, "debug", False):
                payload["_debug"] = {"foundBusiness": True, "isActive": is_active_val, "returnedName": business_name or ""}
            db.close()
            return jsonify(payload)

        # POST/PUT: сохранить/обновить
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Получаем business_id из запроса или используем первый бизнес пользователя
        business_id = request.args.get('business_id') or data.get('business_id') or data.get('businessId')
        print(f"📝 POST /api/client-info: business_id={business_id}, data keys={list(data.keys()) if data else 'None'}")
        if not business_id:
            # Если business_id не передан, пытаемся найти первый бизнес пользователя
            cursor.execute("SELECT id FROM businesses WHERE owner_id = %s AND is_active = TRUE LIMIT 1", (user_id,))
            business_row = cursor.fetchone()
            if business_row:
                business_id = business_row[0] if isinstance(business_row, tuple) else business_row['id']
            else:
                # Если бизнеса нет, используем user_id как business_id для обратной совместимости
                business_id = user_id
        
        # Сохраняем ссылки на карты в businessmaplinks (Postgres-only, ClientInfo не используется)
        map_links = None
        if 'mapLinks' in data:
            map_links = data.get('mapLinks')
        elif 'map_links' in data:
            map_links = data.get('map_links')
        # Не перезаписывать business_id: он уже задан выше из args/data/БД

        print(f"🔍 DEBUG client-info: business_id={business_id}, map_links={map_links}, type={type(map_links)}")

        def detect_map_type(url: str) -> str:
            u = (url or '').lower()
            if 'yandex' in u:
                return 'yandex'
            if '2gis' in u:
                return '2gis'
            if 'google.com/maps' in u or 'maps.app.goo.gl' in u:
                return 'google'
            if 'maps.apple.com' in u:
                return 'apple'
            return 'other'

        # Парсер больше не запускается автоматически при сохранении ссылок
        # Он запускается только вручную через кнопку "Запустить парсер" на странице "Обзор карточки"

        # mapLinks: обновляем только если в теле явно передан ключ mapLinks/map_links. Если ключа нет — существующие ссылки не трогаем. Пустой список [] = удалить все.
        if business_id and ("mapLinks" in data or "map_links" in data) and isinstance(map_links, list):
            print(f"📝 SAVE mapLinks: business_id={business_id}, user_id={user_id}, map_links={map_links}")
            valid_links = []
            for link in map_links:
                url = link.get('url') if isinstance(link, dict) else str(link)
                if url and url.strip():
                    valid_links.append(url.strip())
            print(f"📝 SAVE mapLinks: valid_links={valid_links}, count={len(valid_links)}")

            cursor.execute("DELETE FROM businessmaplinks WHERE business_id = %s", (business_id,))
            deleted_count = cursor.rowcount
            print(f"📝 DELETE mapLinks: business_id={business_id}, deleted_count={deleted_count}")

            inserted_count = 0
            for url in valid_links:
                map_type = detect_map_type(url)
                link_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO businessmaplinks (id, user_id, business_id, url, map_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (link_id, user_id, business_id, url, map_type))
                inserted_count += cursor.rowcount
                print(f"📝 INSERT mapLink: id={link_id}, business_id={business_id}, url={url}, map_type={map_type}")

            db.conn.commit()
            print(f"📝 mapLinks: commit() выполнен (DELETE + {inserted_count} INSERT)")

            # Парсим ll=lon,lat из первой ссылки на Яндекс.Карты и сохраняем в businesses
            for url in valid_links:
                if "yandex" in (url or "").lower() and "ll=" in (url or ""):
                    geo_lon, geo_lat = parse_ll_from_maps_url(url)
                    if geo_lon is not None and geo_lat is not None:
                        cursor.execute(
                            "UPDATE businesses SET geo_lon = %s, geo_lat = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (geo_lon, geo_lat, business_id),
                        )
                        db.conn.commit()
                        print(f"📝 geo: business_id={business_id} geo_lon={geo_lon} geo_lat={geo_lat} из ll в ссылке")
                    break

            cursor.execute("SELECT COUNT(*) FROM businessmaplinks WHERE business_id = %s", (business_id,))
            count_row = cursor.fetchone()
            saved_count = count_row['count'] if isinstance(count_row, dict) else count_row[0]
            print(f"📝 VERIFY mapLinks: business_id={business_id}, saved_count={saved_count}")

        # Всегда возвращаем текущие ссылки для бизнеса
        current_links = []
        if business_id:
            print(f"📖 GET mapLinks: business_id={business_id}")
            cursor.execute("""
                SELECT id, url, map_type, created_at 
                FROM businessmaplinks 
                WHERE business_id = %s 
                ORDER BY created_at DESC
            """, (business_id,))
            link_rows = cursor.fetchall()
            current_links = [
                {
                    "id": r['id'] if isinstance(r, dict) else r[0],
                    "url": r['url'] if isinstance(r, dict) else r[1],
                    "mapType": r['map_type'] if isinstance(r, dict) else r[2],
                    "createdAt": r['created_at'] if isinstance(r, dict) else r[3]
                } for r in link_rows
            ]
            print(f"📖 GET mapLinks: business_id={business_id}, found_count={len(current_links)}, links={[l['url'] for l in current_links]}")

        # Синхронизация с Businesses: обновляем существующий бизнес
        try:
            business_name = data.get('businessName') or ''
            
            # Если business_id не передан, ищем существующий бизнес пользователя
            if not business_id:
                # Сначала ищем по имени (если переименовали)
                if business_name:
                    cursor.execute("""
                        SELECT id FROM businesses
                        WHERE owner_id = %s AND name = %s AND is_active = TRUE
                        LIMIT 1
                    """, (user_id, business_name))
                    existing_by_name = cursor.fetchone()
                    if existing_by_name:
                        business_id = existing_by_name['id'] if isinstance(existing_by_name, dict) else existing_by_name[0]
                        print(f"✅ Найден бизнес по имени: {business_name} (ID: {business_id})")
                
                # Если не нашли по имени, берём первый активный бизнес пользователя
                if not business_id:
                    cursor.execute("""
                        SELECT id FROM businesses
                        WHERE owner_id = %s AND is_active = TRUE
                        ORDER BY created_at ASC
                        LIMIT 1
                    """, (user_id,))
                    first_business = cursor.fetchone()
                    if first_business:
                        business_id = first_business['id'] if isinstance(first_business, dict) else first_business[0]
                        print(f"✅ Используется первый бизнес пользователя (ID: {business_id})")
            
            # Обновляем бизнес, если найден
            if business_id:
                # Проверяем доступ
                owner_id = get_business_owner_id(cursor, business_id)
                if not owner_id or (owner_id != user_id and not user_data.get('is_superadmin')):
                    print(f"⚠️ Нет доступа к бизнесу {business_id}")
                    business_id = None
                else:
                    # Обновляем данные бизнеса
                    updates = []
                    params = []
                    if data.get('businessName') is not None:
                        updates.append('name = %s'); params.append(data.get('businessName'))
                    if data.get('address') is not None:
                        updates.append('address = %s'); params.append(data.get('address'))
                    if data.get('workingHours') is not None:
                        updates.append('working_hours = %s'); params.append(data.get('workingHours'))
                    if data.get('businessType') is not None:
                        business_type_value = data.get('businessType')
                        print(f"📋 Сохраняем businessType в businesses: {business_type_value}")
                        updates.append('business_type = %s'); params.append(business_type_value)
                    # city: ручной приоритет; если не передан и в БД пусто — подсказка из address
                    if 'city' in data:
                        updates.append('city = %s'); params.append((data.get('city') or "").strip() or None)
                    else:
                        cursor.execute("SELECT city, address FROM businesses WHERE id = %s", (business_id,))
                        cur_row = cursor.fetchone()
                        cur_dict = _row_to_dict(cursor, cur_row) if cur_row else {}
                        current_city = (cur_dict.get("city") or "").strip() if cur_dict else ""
                        if not current_city:
                            addr = data.get('address') or (cur_dict.get("address") or "")
                            suggested = suggest_city_from_address(addr)
                            if suggested:
                                updates.append('city = %s'); params.append(suggested)
                    if updates:
                        updates.append('updated_at = CURRENT_TIMESTAMP')
                        params.append(business_id)
                        cursor.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id = %s", params)
                        db.conn.commit()
                        print(f"✅ Обновлён бизнес: {business_id}")
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации с Businesses: {e}")
            import traceback
            traceback.print_exc()

        # Возвращаем полные данные бизнеса после сохранения
        response_data = {
            "success": True,
            "mapLinks": current_links
        }
        
        # Ответ: данные бизнеса всегда из таблицы businesses (lowercase), маппинг через cursor.description
        if business_id:
            cursor.execute("SELECT name, business_type, address, working_hours, city, geo_lat, geo_lon FROM businesses WHERE id = %s", (business_id,))
            business_row = cursor.fetchone()
            row_dict = _row_to_dict(cursor, business_row)
            if row_dict:
                business_name, business_type, address, working_hours = _business_display_fields(row_dict)
                city = (row_dict.get("city") or "").strip() or ""
                city_suggestion = suggest_city_from_address(address) if not city and address else ""
                print(f"📋 POST /api/client-info: из businesses для business_id={business_id}: name={business_name!r}, businessType={business_type!r}")
                response_data.update({
                    "businessName": business_name or "",
                    "businessType": business_type or "",
                    "address": address or "",
                    "workingHours": working_hours or "",
                    "city": city or "",
                    "citySuggestion": city_suggestion or "",
                    "geoLat": row_dict.get("geo_lat"),
                    "geoLon": row_dict.get("geo_lon"),
                })

        db.close()
        return jsonify(response_data)

    except Exception as e:
        import traceback
        print(f"❌ Ошибка в /api/client-info: {e}")
        print(f"❌ Method: {request.method}")
        print(f"❌ User ID: {user_id if 'user_id' in locals() else 'N/A'}")
        try:
            if request.method == 'POST' or request.method == 'PUT':
                print(f"❌ Request JSON: {request.json}")
                print(f"❌ Request data: {request.get_data(as_text=True)[:500]}")
            elif request.method == 'GET':
                print(f"❌ Request args: {request.args}")
        except Exception as log_err:
            print(f"❌ Ошибка логирования request: {log_err}")
        print("❌ Traceback:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<string:business_id>/parse-status', methods=['GET'])
def get_parse_status(business_id):
    """Получить статус парсинга для бизнеса из очереди"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем владельца
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_id and not db.is_superadmin(user_id):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        cursor.execute("""
            SELECT status, retry_after, created_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_queue = cursor.fetchone()
        queue_row = _row_to_dict(cursor, raw_queue) if raw_queue else None
        
        retry_info = None
        overall_status = "idle"
        
        if queue_row:
            overall_status = normalize_status(queue_row.get("status") or "") or "idle"
            retry_after = queue_row.get("retry_after")
            
            # Вычисляем оставшееся время до повтора для статуса captcha
            if overall_status == 'captcha' and retry_after:
                try:
                    from datetime import datetime
                    retry_dt = datetime.fromisoformat(retry_after)
                    now = datetime.now()
                    if retry_dt > now:
                        delta = retry_dt - now
                        hours = int(delta.total_seconds() / 3600)
                        minutes = int((delta.total_seconds() % 3600) / 60)
                        retry_info = {
                            'retry_after': retry_after,
                            'hours': hours,
                            'minutes': minutes
                        }
                        print(f"✅ Вычислен retry_info: {hours} ч {minutes} мин")
                    else:
                        print(f"⚠️ Время retry_after уже прошло: {retry_after} < {now}")
                        retry_info = None
                except Exception as e:
                    print(f"⚠️ Ошибка вычисления retry_info: {e}")
                    import traceback
                    traceback.print_exc()
                    retry_info = None
            else:
                if overall_status == 'captcha':
                    print(f"⚠️ Статус captcha, но retry_after отсутствует: {retry_after}")
        
        cursor.execute("""
            SELECT status, COUNT(*) AS count
            FROM parsequeue
            WHERE business_id = %s
            GROUP BY status
        """, (business_id,))
        status_rows = cursor.fetchall()
        
        statuses = {}
        for row in status_rows:
            rd = _row_to_dict(cursor, row)
            if rd:
                st = normalize_status(rd.get("status") or "idle")
                statuses[st] = statuses.get(st, 0) + (rd.get("count") or 0)

        # Определяем общий статус (если не определён выше из queue_row)
        # НЕ переопределяем статус, если он уже установлен из queue_row (например, captcha)
        if overall_status == "idle":
            if statuses.get('processing'):
                overall_status = "processing"
            elif statuses.get('pending') or statuses.get('queued'):
                overall_status = "queued"
            elif statuses.get('error'):
                overall_status = "error"
            elif statuses.get(STATUS_COMPLETED):
                overall_status = STATUS_COMPLETED
            elif statuses.get('captcha'):
                overall_status = "captcha"
                # Если статус captcha, но retry_info не был вычислен выше, вычисляем его здесь
                if retry_info is None:
                    cursor.execute("""
                        SELECT retry_after
                        FROM parsequeue
                        WHERE business_id = %s AND status = 'captcha'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (business_id,))
                    raw_retry = cursor.fetchone()
                    retry_row = _row_to_dict(cursor, raw_retry) if raw_retry else None
                    if retry_row and retry_row.get("retry_after"):
                        try:
                            from datetime import datetime
                            retry_dt = datetime.fromisoformat(str(retry_row["retry_after"]))
                            now = datetime.now()
                            if retry_dt > now:
                                delta = retry_dt - now
                                hours = int(delta.total_seconds() / 3600)
                                minutes = int((delta.total_seconds() % 3600) / 60)
                                retry_info = {
                                    'retry_after': retry_row[0],
                                    'hours': hours,
                                    'minutes': minutes
                                }
                                print(f"✅ Вычислен retry_info (fallback): {hours} ч {minutes} мин")
                        except Exception as e:
                            print(f"⚠️ Ошибка вычисления retry_info (fallback): {e}")
        
        print(f"📊 Возвращаю статус: {overall_status}, retry_info: {retry_info}")
        db.close()
        return jsonify({
            "success": True,
            "status": overall_status,
            "details": statuses,
            "retry_info": retry_info
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_parse_status: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_parse_status", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route('/api/business/<string:business_id>/map-parses', methods=['GET'])
def get_map_parses(business_id):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем владельца
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_id and not db.is_superadmin(user_id):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        # В PostgreSQL все результаты парсинга в cards. Берём реальные поля и считаем counts из JSONB.
        cursor.execute("""
            SELECT id, url, rating, reviews_count, report_path, created_at,
                   overview, products, news, photos, competitors, hours_full
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (business_id,))
        rows = cursor.fetchall()
        db.close()

        def _len(v):
            if v is None:
                return 0
            if isinstance(v, (list, dict)):
                return len(v)
            if isinstance(v, str):
                try:
                    p = json.loads(v)
                    return len(p) if isinstance(p, (list, dict)) else 0
                except Exception:
                    return 0
            return 0

        items = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            news_count = _len(rd.get("news"))
            photos_count = _len(rd.get("photos"))
            products_count = _len(rd.get("products"))
            item = {
                "id": rd.get("id"),
                "url": rd.get("url"),
                "mapType": "yandex",
                "rating": rd.get("rating"),
                "reviewsCount": rd.get("reviews_count") or 0,
                "unansweredReviewsCount": 0,
                "newsCount": news_count,
                "photosCount": photos_count,
                "productsCount": products_count,
                "servicesCount": products_count,
                "reportPath": rd.get("report_path"),
                "createdAt": rd.get("created_at"),
            }
            items.append(item)

        return jsonify({"success": True, "items": items})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_map_parses: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_map_parses", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route('/api/map-report/<string:parse_id>', methods=['GET'])
def get_map_report(parse_id):
    try:
        # Авторизация
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT c.report_path, c.business_id, b.owner_id
            FROM cards c
            LEFT JOIN businesses b ON c.business_id = b.id
            WHERE c.id = %s
            LIMIT 1
        """, (parse_id,))
        raw = cursor.fetchone()
        row = _row_to_dict(cursor, raw) if raw else None
        db.close()

        if not row:
            return jsonify({"error": "Отчет не найден"}), 404

        report_path = row.get("report_path")
        business_owner = row.get("owner_id")
        if business_owner != user_id:
            # Проверка суперадмина
            db2 = DatabaseManager()
            if not db2.is_superadmin(user_id):
                db2.close()
                return jsonify({"error": "Нет доступа"}), 403
            db2.close()

        if not report_path or not os.path.exists(report_path):
            return jsonify({"error": "Файл отчета недоступен"}), 404

        with open(report_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return Response(html, mimetype='text/html')

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_map_report: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_map_report", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


@app.route('/api/analyze-screenshot', methods=['POST'])
def analyze_screenshot():
    """Анализ скриншота карточки через GigaChat"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем наличие файла
        if 'image' not in request.files:
            return jsonify({"error": "Файл изображения не найден"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Проверяем тип файла
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PNG, JPG, JPEG"}), 400
        
        # Проверяем размер файла (15 МБ)
        file.seek(0, 2)  # Переходим в конец файла
        file_size = file.tell()
        file.seek(0)  # Возвращаемся в начало
        
        if file_size > 15 * 1024 * 1024:  # 15 МБ
            return jsonify({"error": "Файл слишком большой. Максимум 15 МБ"}), 400
        
        # Читаем промпт из файла
        try:
            with open('prompts/cards-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except FileNotFoundError:
            prompt = """Проанализируй скриншот карточки организации на Яндекс.Картах. 
ВЕРНИ РЕЗУЛЬТАТ СТРОГО В JSON ФОРМАТЕ:
{
  "completeness_score": число от 0 до 100,
  "business_name": "название из карточки",
  "category": "основная категория",
  "analysis": {
    "photos": {"count": количество_фото, "quality": "низкое/среднее/высокое", "recommendations": ["рекомендация1"]},
    "description": {"exists": true/false, "length": количество_символов, "seo_optimized": true/false, "recommendations": ["рекомендация1"]},
    "contacts": {"phone": true/false, "website": true/false, "social_media": true/false, "recommendations": ["рекомендация1"]},
    "schedule": {"complete": true/false, "recommendations": ["рекомендация1"]},
    "services": {"listed": true/false, "count": количество, "recommendations": ["рекомендация1"]}
  },
  "priority_actions": ["действие1", "действие2", "действие3"],
  "overall_recommendations": "общие рекомендации по улучшению"
}"""
        
        # Конвертируем изображение в base64
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Анализируем через GigaChat
        business_id = get_business_id_from_user(user_data['user_id'])
        result = analyze_screenshot_with_gigachat(
            image_base64, 
            prompt,
            business_id=business_id,
            user_id=user_data['user_id']
        )
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        # Сохраняем результат в БД
        db = DatabaseManager()
        analysis_id = str(uuid.uuid4())
        
        # Сохраняем файл
        upload_dir = 'uploads/screenshots'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{analysis_id}.{file.filename.split('.')[-1]}")
        file.seek(0)
        file.save(file_path)
        
        # Сохраняем в БД
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO screenshotanalyses (id, user_id, image_path, analysis_result, completeness_score, business_name, category, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            analysis_id,
            user_data['user_id'],
            file_path,
            json.dumps(result, ensure_ascii=False),
            result.get('completeness_score', 0),
            result.get('business_name', ''),
            result.get('category', ''),
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "analysis_id": analysis_id,
            "result": result
        })
        
    except Exception as e:
        print(f"❌ Ошибка анализа скриншота: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/optimize-pricelist', methods=['POST'])
def optimize_pricelist():
    """SEO оптимизация прайс-листа через GigaChat"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем наличие файла
        if 'file' not in request.files:
            return jsonify({"error": "Файл прайс-листа не найден"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Проверяем тип файла
        allowed_types = ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel', 
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX"}), 400
        
        # Читаем промпт из файла
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except FileNotFoundError:
            prompt = """Оптимизируй прайс-лист услуг для локального SEO и поисковых запросов.
КОНТЕКСТ: Салон красоты в России, целевые запросы включают географические модификаторы и коммерческие интенты.
ВЕРНИ РЕЗУЛЬТАТ В JSON:
{
  "services": [
    {
      "original_name": "исходное название",
      "optimized_name": "SEO-оптимизированное название",
      "seo_description": "описание 120-150 символов для сайта/карт",
      "keywords": ["ключ1", "ключ2", "ключ3"],
      "price": "цена если указана",
      "category": "категория услуги"
    }
  ],
  "general_recommendations": ["рекомендация по структуре прайса", "рекомендация по ключевым словам"]
}
ТРЕБОВАНИЯ:
- Названия до 60 символов
- Описания 120-150 символов  
- Включай местные модификаторы при необходимости
- Используй коммерческие интенты в формулировках"""
        
        # Читаем содержимое файла (упрощенная версия - только текст)
        file_content = file.read().decode('utf-8', errors='ignore')
        
        # Формируем полный промпт с данными файла
        full_prompt = f"{prompt}\n\nДанные прайс-листа:\n{file_content[:2000]}"  # Ограничиваем размер
        
        # Анализируем через GigaChat
        result = analyze_text_with_gigachat(full_prompt)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        
        # Сохраняем результат в БД
        db = DatabaseManager()
        optimization_id = str(uuid.uuid4())
        
        # Сохраняем файл
        upload_dir = 'uploads/pricelists'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{optimization_id}_{file.filename}")
        file.seek(0)
        file.save(file_path)
        
        # Сохраняем в БД
        cursor = db.conn.cursor()
        services_count = len(result.get('services', [])) if isinstance(result.get('services'), list) else 0
        cursor.execute("""
            INSERT INTO PricelistOptimizations (id, user_id, original_file_path, optimized_data, services_count, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            optimization_id,
            user_data['user_id'],
            file_path,
            json.dumps(result, ensure_ascii=False),
            services_count,
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "optimization_id": optimization_id,
            "result": result
        })
        
    except Exception as e:
        print(f"❌ Ошибка оптимизации прайс-листа: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/<analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    """Получить результат анализа по ID"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Ищем анализ скриншота
        cursor.execute("""
            SELECT * FROM screenshotanalyses 
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))
        
        analysis = cursor.fetchone()
        if analysis:
            analysis_data = _row_to_dict(cursor, analysis) if analysis else {}
            db.close()
            return jsonify({
                "success": True,
                "type": "screenshot",
                "result": json.loads(analysis_data.get('analysis_result') or "{}"),
                "created_at": analysis_data.get('created_at')
            })
        
        # Ищем оптимизацию прайс-листа
        cursor.execute("""
            SELECT * FROM pricelistoptimizations 
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))
        
        optimization = cursor.fetchone()
        if optimization:
            optimization_data = _row_to_dict(cursor, optimization) if optimization else {}
            db.close()
            return jsonify({
                "success": True,
                "type": "pricelist",
                "result": json.loads(optimization_data.get('optimized_data') or "{}"),
                "created_at": optimization_data.get('created_at')
            })
        
        db.close()
        return jsonify({"error": "Анализ не найден или истек срок действия"}), 404
        
    except Exception as e:
        print(f"❌ Ошибка получения анализа: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-card-auto', methods=['POST'])
def analyze_card_auto():
    """Автоматический анализ карточки компании на Яндекс.Картах"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        yandex_url = data.get('url')
        
        if not yandex_url:
            return jsonify({"error": "URL карточки обязателен"}), 400
        
        # Проверяем, что это URL Яндекс.Карт
        if 'yandex.ru/maps' not in yandex_url:
            return jsonify({"error": "Неверный URL. Требуется ссылка на Яндекс.Карты"}), 400
        
        # Импортируем модуль автоматического скриншота
        from automated_screenshot import YandexMapsScreenshotter
        
        # Создаем скриншот и анализируем
        screenshotter = YandexMapsScreenshotter(headless=True)
        result = screenshotter.analyze_card_from_url(yandex_url)
        
        if not result:
            return jsonify({"error": "Не удалось проанализировать карточку"}), 500
        
        # Сохраняем результат в базу данных
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        analysis_id = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()
        
        cursor.execute("""
            INSERT INTO screenshotanalyses 
            (id, user_id, analysis_result, completeness_score, business_name, category, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            analysis_id,
            user_data['user_id'],
            json.dumps(result),
            result.get('completeness_score', 0),
            result.get('business_name', ''),
            result.get('category', ''),
            expires_at
        ))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "analysis_id": analysis_id,
            "result": result,
            "message": "Карточка успешно проанализирована"
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка автоматического анализа: {str(e)}"}), 500

@app.route('/api/gigachat/config', methods=['GET'])
def get_gigachat_config():
    """Получить текущую конфигурацию GigaChat"""
    try:
        from gigachat_config import get_gigachat_config, get_available_models
        
        config = get_gigachat_config()
        available_models = get_available_models()
        
        return jsonify({
            "success": True,
            "current_config": config.get_model_config(),
            "model_info": config.get_model_info(),
            "available_models": available_models
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения конфигурации: {str(e)}"}), 500

@app.route('/api/gigachat/config', methods=['POST'])
def set_gigachat_config():
    """Изменить конфигурацию GigaChat"""
    try:
        from gigachat_config import set_gigachat_model
        
        data = request.get_json()
        model_name = data.get('model')
        
        if not model_name:
            return jsonify({"error": "Модель не указана"}), 400
        
        if set_gigachat_model(model_name):
            return jsonify({
                "success": True,
                "message": f"Модель изменена на {model_name}",
                "model": model_name
            })
        else:
            return jsonify({"error": f"Модель {model_name} не поддерживается"}), 400
            
    except Exception as e:
        return jsonify({"error": f"Ошибка изменения конфигурации: {str(e)}"}), 500

# ==================== ДИАГНОСТИКА GIGACHAT ====================
@app.route('/api/gigachat/diagnostics', methods=['GET'])
def gigachat_diagnostics():
    """Проверка загрузки ключей и получения access_token у GigaChat"""
    try:
        from services.gigachat_client import get_gigachat_client
        client = get_gigachat_client()

        # Проверим наличие ключей в пуле
        creds_count = len(client.credentials_pool)
        model_cfg = client.config.get_model_config()

        token_ok = False
        token_error = None
        try:
            token = client.get_access_token()
            token_ok = bool(token)
        except Exception as e:
            token_error = str(e)

        return jsonify({
            "success": token_ok,
            "credentials_loaded": creds_count,
            "current_key_index": client.current_index if creds_count else None,
            "model": model_cfg.get("model"),
            "temperature": model_cfg.get("temperature"),
            "max_tokens": model_cfg.get("max_tokens"),
            "token_error": token_error
        }), (200 if token_ok else 503)
    except Exception as e:
        return jsonify({"error": f"Диагностика не удалась: {str(e)}"}), 500

# ==================== ФИНАНСОВЫЕ ЭНДПОИНТЫ ====================

@app.route('/api/finance/transaction', methods=['POST'])
def add_transaction():
    """Добавить финансовую транзакцию"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        
        # Валидация данных
        required_fields = ['transaction_date', 'amount', 'client_type']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Поле {field} обязательно"}), 400
        
        if data['client_type'] not in ['new', 'returning']:
            return jsonify({"error": "client_type должен быть 'new' или 'returning'"}), 400
        
        if data['amount'] <= 0:
            return jsonify({"error": "Сумма должна быть больше 0"}), 400
        
        # Сохраняем транзакцию
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        transaction_id = str(uuid.uuid4())
        
        # Проверяем наличие поля master_id в таблице
        columns = _table_columns(cursor, "financialtransactions")
        has_master_id = 'master_id' in columns
        
        if has_master_id:
            cursor.execute(
                """
                INSERT INTO financialtransactions
                (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    user_data['user_id'],
                    data['transaction_date'],
                    data['amount'],
                    data['client_type'],
                    json.dumps(data.get('services', [])),
                    data.get('notes', ''),
                    data.get('master_id'),
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO financialtransactions
                (id, user_id, transaction_date, amount, client_type, services, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    transaction_id,
                    user_data['user_id'],
                    data['transaction_date'],
                    data['amount'],
                    data['client_type'],
                    json.dumps(data.get('services', [])),
                    data.get('notes', ''),
                ),
            )
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "transaction_id": transaction_id,
            "message": "Транзакция добавлена успешно"
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка добавления транзакции: {str(e)}"}), 500


@app.route('/api/finance/transaction/<string:transaction_id>', methods=['PUT', 'OPTIONS'])
def update_transaction(transaction_id):
    """Обновить финансовую транзакцию"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем принадлежность транзакции пользователю
        cursor.execute("SELECT id, user_id FROM financialtransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        owner_id = row.get("user_id") if hasattr(row, "get") else row[1]
        if owner_id != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        fields = []
        params = []
        if 'transaction_date' in data:
            fields.append("transaction_date = %s")
            params.append(data.get('transaction_date'))
        if 'amount' in data:
            fields.append("amount = %s")
            params.append(float(data.get('amount') or 0))
        if 'client_type' in data:
            fields.append("client_type = %s")
            params.append(data.get('client_type') or 'new')
        if 'services' in data:
            fields.append("services = %s")
            params.append(json.dumps(data.get('services') or []))
        if 'notes' in data:
            fields.append("notes = %s")
            params.append(data.get('notes') or '')

        if not fields:
            db.close()
            return jsonify({"error": "Нет полей для обновления"}), 400

        params.append(transaction_id)
        cursor.execute(f"UPDATE financialtransactions SET {', '.join(fields)} WHERE id = %s", params)
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Транзакция обновлена"})
        
    except Exception as e:
        return jsonify({"error": f"Ошибка обновления транзакции: {str(e)}"}), 500


@app.route('/api/finance/transaction/<string:transaction_id>', methods=['DELETE', 'OPTIONS'])
def delete_transaction(transaction_id):
    """Удалить финансовую транзакцию"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем принадлежность транзакции пользователю
        cursor.execute("SELECT id, user_id FROM financialtransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        owner_id = row.get("user_id") if hasattr(row, "get") else row[1]
        if owner_id != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        cursor.execute("DELETE FROM financialtransactions WHERE id = %s", (transaction_id,))
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Транзакция удалена"})
        
    except Exception as e:
        return jsonify({"error": f"Ошибка удаления транзакции: {str(e)}"}), 500

@app.route('/api/finance/transaction/upload', methods=['POST', 'OPTIONS'])
def upload_transaction_file():
    """Загрузить файл или фото с транзакциями и распознать их"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем наличие файла
        file = None
        is_image = False
        
        if 'file' in request.files:
            file = request.files['file']
            if file.filename == '':
                file = None
        elif 'photo' in request.files:
            file = request.files['photo']
            is_image = True
            if file.filename == '':
                file = None
        
        if not file:
            return jsonify({"error": "Файл не выбран"}), 400
        
        # Проверяем тип файла
        if is_image:
            allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PNG, JPG, JPEG"}), 400
        else:
            allowed_types = ['application/pdf', 'application/msword', 
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'application/vnd.ms-excel',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                           'text/plain', 'text/csv']
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX, TXT, CSV"}), 400
        
        # Читаем промпт для анализа транзакций
        try:
            with open('prompts/transaction-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt_content = f.read()
        except FileNotFoundError:
            prompt_content = """Проанализируй документ/фото и извлеки все транзакции (продажи услуг).
Верни результат в формате JSON:
{
  "transactions": [
    {
      "transaction_date": "YYYY-MM-DD",
      "amount": число,
      "client_type": "new" или "returning",
      "services": ["услуга1", "услуга2"],
      "master_name": "имя мастера" или null,
      "notes": "дополнительная информация" или null
    }
  ]
}"""
        
        # Обрабатываем файл
        if is_image:
            # Для изображений - анализ через GigaChat
            import base64
            image_data = file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            business_id = get_business_id_from_user(user_data['user_id'])
            result = analyze_screenshot_with_gigachat(
                image_base64, 
                prompt_content,
                business_id=business_id,
                user_id=user_data['user_id']
            )
            
            if 'error' in result:
                return jsonify({"error": result['error']}), 500
            
            # Парсим JSON из результата
            try:
                analysis_result = json.loads(result) if isinstance(result, str) else result
                transactions = analysis_result.get('transactions', [])
            except:
                return jsonify({"error": "Не удалось распарсить результат анализа"}), 500
        else:
            # Для текстовых файлов - читаем содержимое и анализируем
            file_content = file.read().decode('utf-8', errors='ignore')
            business_id = get_business_id_from_user(user_data['user_id'])
            result = analyze_text_with_gigachat(
                prompt_content + "\n\nСодержимое файла:\n" + file_content,
                business_id=business_id,
                user_id=user_data['user_id']
            )
            
            if 'error' in result:
                return jsonify({"error": result['error']}), 500
            
            try:
                analysis_result = json.loads(result) if isinstance(result, str) else result
                transactions = analysis_result.get('transactions', [])
            except:
                return jsonify({"error": "Не удалось распарсить результат анализа"}), 500
        
        # Сохраняем транзакции в БД
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем наличие полей master_id и business_id
        columns = _table_columns(cursor, "financialtransactions")
        has_master_id = 'master_id' in columns
        has_business_id = 'business_id' in columns
        
        saved_transactions = []
        for trans in transactions:
            transaction_id = str(uuid.uuid4())
            
            # Получаем master_id по имени мастера (если есть таблица Masters)
            master_id = None
            if trans.get('master_name'):
                cursor.execute("SELECT to_regclass('public.masters')")
                masters_table_exists = cursor.fetchone()
                if masters_table_exists:
                    cursor.execute("SELECT id FROM masters WHERE name = %s LIMIT 1", (trans['master_name'],))
                    master_row = cursor.fetchone()
                    if master_row:
                        master_id = master_row[0]
            
            # Получаем business_id из текущего бизнеса пользователя
            business_id = None
            if has_business_id:
                cursor.execute("SELECT id FROM businesses WHERE owner_id = %s LIMIT 1", (user_data['user_id'],))
                business_row = cursor.fetchone()
                if business_row:
                    business_id = business_row.get("id") if hasattr(business_row, "get") else business_row[0]
            
            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO financialtransactions 
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', ''),
                    master_id
                ))
            elif has_master_id:
                cursor.execute("""
                    INSERT INTO financialtransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', ''),
                    master_id
                ))
            elif has_business_id:
                cursor.execute("""
                    INSERT INTO financialtransactions 
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    business_id,
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', '')
                ))
            else:
                cursor.execute("""
                    INSERT INTO financialtransactions 
                    (id, user_id, transaction_date, amount, client_type, services, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    transaction_id,
                    user_data['user_id'],
                    trans.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),
                    trans.get('amount', 0),
                    trans.get('client_type', 'new'),
                    json.dumps(trans.get('services', [])),
                    trans.get('notes', '')
                ))
            
            saved_transactions.append({
                "id": transaction_id,
                "transaction_date": trans.get('transaction_date'),
                "amount": trans.get('amount'),
                "client_type": trans.get('client_type'),
                "services": trans.get('services', []),
                "master_id": master_id,
                "notes": trans.get('notes')
            })
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "transactions": saved_transactions,
            "count": len(saved_transactions),
            "message": f"Успешно добавлено {len(saved_transactions)} транзакций"
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка обработки файла: {str(e)}"}), 500

@app.route('/api/finance/transactions', methods=['GET'])
def get_transactions():
    """Получить список транзакций"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Параметры запроса
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Строим запрос с явными полями (без SELECT *)
        query = """
            SELECT 
                id,
                business_id,
                transaction_date,
                amount,
                client_type,
                services,
                notes,
                created_at
            FROM FinancialTransactions
            WHERE user_id = ?
        """
        params = [user_data['user_id']]
        
        # Фильтр по бизнесу, если передан
        current_business_id = request.args.get('business_id')
        if current_business_id:
            query += " AND business_id = ?"
            params.append(current_business_id)
        
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY transaction_date DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        # Преобразуем в словари
        result = []
        for t in transactions:
            tx_id = t[0]
            business_id = t[1]
            tx_date = t[2]
            amount = float(t[3] or 0)
            client_type_val = t[4] or 'new'
            services_raw = t[5]
            notes_val = t[6] or ''
            created_at_val = t[7]
            
            services_list = []
            if services_raw:
                try:
                    services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                    if not isinstance(services_list, list):
                        services_list = []
                except Exception:
                    services_list = []
            
            result.append({
                "id": tx_id,
                "business_id": business_id,
                "transaction_date": tx_date,
                "amount": amount,
                "client_type": client_type_val,
                "services": services_list,
                "notes": notes_val,
                "created_at": created_at_val
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "transactions": result,
            "count": len(result)
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения транзакций: {str(e)}"}), 500

@app.route('/api/finance/metrics', methods=['GET'])
def get_financial_metrics():
    """Получить финансовые метрики"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Параметры периода
        period = request.args.get('period', 'month')  # week, month, quarter, year
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        business_id = request.args.get('business_id')
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Если передан business_id - проверяем доступ
        if business_id:
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Если даты не указаны, вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
        
        # Формируем WHERE условие с учётом business_id
        where_clause = "transaction_date BETWEEN %s AND %s"
        where_params = [start_date, end_date]
        
        if business_id:
            where_clause = f"business_id = %s AND {where_clause}"
            where_params = [business_id] + where_params
        else:
            # Старая логика для обратной совместимости
            where_clause = f"user_id = %s AND {where_clause}"
            where_params = [user_data['user_id']] + where_params
        
        # Получаем агрегированные данные
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as average_check,
                SUM(CASE WHEN client_type = 'new' THEN 1 ELSE 0 END) as new_clients,
                SUM(CASE WHEN client_type = 'returning' THEN 1 ELSE 0 END) as returning_clients
            FROM financialtransactions 
            WHERE {where_clause}
        """, tuple(where_params))
        
        raw_metrics = cursor.fetchone()
        metrics = _row_to_dict(cursor, raw_metrics) if raw_metrics else {}
        
        # Вычисляем retention rate
        # Вычисляем retention rate
        new_clients = metrics.get("new_clients") or 0
        returning_clients = metrics.get("returning_clients") or 0
        total_clients = new_clients + returning_clients
        retention_rate = (returning_clients / total_clients * 100) if total_clients > 0 else 0
        
        # Получаем данные за предыдущий период для сравнения
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        period_days = (end_dt - start_dt).days
        
        prev_start = (start_dt - timedelta(days=period_days)).strftime('%Y-%m-%d')
        prev_end = start_date
        
        # Формируем WHERE условие для предыдущего периода
        prev_where_clause = "transaction_date BETWEEN %s AND %s"
        prev_where_params = [prev_start, prev_end]
        
        if business_id:
            prev_where_clause = f"business_id = %s AND {prev_where_clause}"
            prev_where_params = [business_id] + prev_where_params
        else:
            prev_where_clause = f"user_id = %s AND {prev_where_clause}"
            prev_where_params = [user_data['user_id']] + prev_where_params
        
        cursor.execute(f"""
            SELECT 
                COUNT(*) as prev_orders,
                SUM(amount) as prev_revenue
            FROM financialtransactions 
            WHERE {prev_where_clause}
        """, tuple(prev_where_params))
        
        raw_prev_metrics = cursor.fetchone()
        prev_metrics = _row_to_dict(cursor, raw_prev_metrics) if raw_prev_metrics else {}
        
        # Вычисляем рост
        revenue_growth = 0
        orders_growth = 0
        
        prev_revenue = prev_metrics.get("prev_revenue")
        prev_orders = prev_metrics.get("prev_orders")
        total_revenue = metrics.get("total_revenue")
        total_orders = metrics.get("total_orders")
        average_check = metrics.get("average_check")

        if prev_revenue and prev_revenue > 0:
            revenue_growth = ((total_revenue or 0) - prev_revenue) / prev_revenue * 100
        
        if prev_orders and prev_orders > 0:
            orders_growth = ((total_orders or 0) - prev_orders) / prev_orders * 100
        
        db.close()
        
        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": period
            },
            "metrics": {
                "total_revenue": float(total_revenue or 0),
                "total_orders": total_orders or 0,
                "average_check": float(average_check or 0),
                "new_clients": new_clients,
                "returning_clients": returning_clients,
                "retention_rate": round(retention_rate, 2)
            },
            "growth": {
                "revenue_growth": round(revenue_growth, 2),
                "orders_growth": round(orders_growth, 2)
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения метрик: {str(e)}"}), 500

@app.route('/api/finance/breakdown', methods=['GET'])
def get_financial_breakdown():
    """Получить разбивку доходов по услугам и мастерам для круговых диаграмм"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Параметры периода
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Если даты не указаны, вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
        
        # Проверяем наличие полей в таблице
        columns = _table_columns(cursor, "financialtransactions")
        has_business_id = 'business_id' in columns
        has_master_id = 'master_id' in columns
        
        # Получаем business_id из запроса
        current_business_id = request.args.get('business_id')
        
        # Получаем транзакции за период
        if has_business_id and current_business_id:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM financialtransactions 
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM financialtransactions 
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
        else:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM financialtransactions 
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM financialtransactions 
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))
        
        transactions = cursor.fetchall()
        
        # Агрегируем по услугам
        def _row_val(row, idx, key):
            if isinstance(row, dict):
                return row.get(key)
            if row is None:
                return None
            return row[idx] if len(row) > idx else None

        services_revenue = {}
        for row in transactions:
            services_json = _row_val(row, 0, "services")  # services (JSON)
            amount = float(_row_val(row, 1, "amount") or 0)
            
            if services_json:
                try:
                    services = json.loads(services_json) if isinstance(services_json, str) else services_json
                    if isinstance(services, list):
                        # Распределяем сумму поровну между услугами
                        service_amount = amount / len(services) if len(services) > 0 else amount
                        for service in services:
                            service_name = service.strip() if isinstance(service, str) else str(service)
                            if service_name:
                                services_revenue[service_name] = services_revenue.get(service_name, 0) + service_amount
                except:
                    pass
        
        # Агрегируем по мастерам
        masters_revenue = {}
        for row in transactions:
            master_id = _row_val(row, 2, "master_id")
            amount = float(_row_val(row, 1, "amount") or 0)
            
            if master_id:
                # Проверяем наличие таблицы Masters
                cursor.execute("SELECT to_regclass('public.masters')")
                masters_table_exists = cursor.fetchone()
                
                if masters_table_exists:
                    cursor.execute("SELECT name FROM masters WHERE id = %s", (master_id,))
                    master_row = cursor.fetchone()
                    master_dict = _row_to_dict(cursor, master_row) if master_row else None
                    master_name = master_dict.get("name") if master_dict else f"Мастер {master_id[:8]}"
                else:
                    master_name = f"Мастер {master_id[:8]}"
                
                masters_revenue[master_name] = masters_revenue.get(master_name, 0) + amount
            else:
                # Если мастер не указан, добавляем в "Не указан"
                masters_revenue["Не указан"] = masters_revenue.get("Не указан", 0) + amount
        
        # Преобразуем в массивы для диаграмм
        services_data = [{"name": name, "value": round(value, 2)} for name, value in services_revenue.items()]
        masters_data = [{"name": name, "value": round(value, 2)} for name, value in masters_revenue.items()]
        
        # Сортируем по убыванию значения
        services_data.sort(key=lambda x: x['value'], reverse=True)
        masters_data.sort(key=lambda x: x['value'], reverse=True)
        
        db.close()
        
        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": period
            },
            "by_services": services_data,
            "by_masters": masters_data
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения разбивки: {str(e)}"}), 500

# ==================== ЭНДПОИНТЫ ДЛЯ СЕТЕЙ ====================

@app.route('/api/networks/<string:network_id>/locations', methods=['GET'])
def get_network_locations_by_network_id(network_id):
    """Получить список точек сети"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что пользователь имеет доступ к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        # Проверяем права доступа (владелец или суперадмин)
        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Получаем точки сети
        cursor.execute("""
            SELECT id, name, address, description 
            FROM businesses 
            WHERE network_id = %s 
            ORDER BY name
        """, (network_id,))
        
        locations = []
        for row in cursor.fetchall():
            row_data = _row_to_dict(cursor, row) if row else {}
            locations.append({
                "id": row_data.get("id"),
                "name": row_data.get("name"),
                "address": row_data.get("address"),
                "description": row_data.get("description")
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "locations": locations
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения точек сети: {str(e)}"}), 500

@app.route('/api/networks/<string:network_id>/stats', methods=['GET'])
def get_network_stats(network_id):
    """Получить статистику сети"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем доступ к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Получаем точки сети
        cursor.execute("SELECT id, name FROM businesses WHERE network_id = %s", (network_id,))
        raw_locations = cursor.fetchall()
        locations = [_row_to_dict(cursor, row) for row in raw_locations]
        location_ids = [loc.get("id") for loc in locations if loc.get("id")]
        
        if not location_ids:
            db.close()
            return jsonify({
                "success": True,
                "stats": {
                    "total_revenue": 0,
                    "total_orders": 0,
                    "locations_count": 0,
                    "by_services": [],
                    "by_masters": [],
                    "by_locations": [],
                    "ratings": [],
                    "bad_reviews": []
                }
            })
        
        # Вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()
            
            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
        
        # Получаем транзакции всех точек сети
        # Проверяем наличие поля business_id
        columns = _table_columns(cursor, "financialtransactions")
        has_business_id = 'business_id' in columns
        
        if has_business_id and location_ids:
            placeholders = ','.join(['%s'] * len(location_ids))
            cursor.execute(f"""
                SELECT services, amount, master_id, business_id
                FROM financialtransactions 
                WHERE business_id IN ({placeholders}) AND transaction_date BETWEEN %s AND %s
            """, tuple(location_ids + [start_date, end_date]))
        else:
            # Если business_id нет, получаем через user_id владельца сети
            cursor.execute("""
                SELECT services, amount, master_id, NULL as business_id
                FROM financialtransactions 
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
            """, (network.get("owner_id"), start_date, end_date))
        
        transactions = cursor.fetchall()
        
        # Агрегируем данные
        services_revenue = {}
        masters_revenue = {}
        locations_revenue = {(loc.get("name") or "Неизвестно"): 0 for loc in locations}
        
        for row in transactions:
            row_data = _row_to_dict(cursor, row) if row else {}
            services_json = row_data.get("services")
            amount = float(row_data.get("amount") or 0)
            master_id = row_data.get("master_id")
            business_id = row_data.get("business_id")
            
            # По услугам
            if services_json:
                try:
                    services = json.loads(services_json) if isinstance(services_json, str) else services_json
                    if isinstance(services, list):
                        service_amount = amount / len(services) if len(services) > 0 else amount
                        for service in services:
                            service_name = service.strip() if isinstance(service, str) else str(service)
                            if service_name:
                                services_revenue[service_name] = services_revenue.get(service_name, 0) + service_amount
                except:
                    pass
            
            # По мастерам
            if master_id:
                cursor.execute("SELECT name FROM masters WHERE id = %s", (master_id,))
                master_row = cursor.fetchone()
                master_dict = _row_to_dict(cursor, master_row) if master_row else None
                master_name = master_dict.get("name") if master_dict else f"Мастер {master_id[:8]}"
                masters_revenue[master_name] = masters_revenue.get(master_name, 0) + amount
            
            # По точкам
            location_name = next((loc.get("name") for loc in locations if loc.get("id") == business_id), "Неизвестно")
            locations_revenue[location_name] = locations_revenue.get(location_name, 0) + amount
        
        # Преобразуем в массивы
        by_services = [{"name": name, "value": round(value, 2)} for name, value in services_revenue.items()]
        by_masters = [{"name": name, "value": round(value, 2)} for name, value in masters_revenue.items()]
        by_locations = [{"name": name, "value": round(value, 2)} for name, value in locations_revenue.items()]
        
        by_services.sort(key=lambda x: x['value'], reverse=True)
        by_masters.sort(key=lambda x: x['value'], reverse=True)
        by_locations.sort(key=lambda x: x['value'], reverse=True)
        
        # Рейтинги и отзывы по данным Яндекс.Карт (если есть кеш-поля)
        ratings = []
        try:
            cursor.execute(
                """
                SELECT id, name, yandex_rating, yandex_reviews_total, yandex_reviews_30d, yandex_last_sync
                FROM businesses
                WHERE network_id = %s AND (is_active = TRUE OR is_active = 1 OR is_active IS NULL)
                """,
                (network_id,),
            )
            for row in cursor.fetchall():
                row_data = _row_to_dict(cursor, row) if row else {}
                ratings.append(
                    {
                        "business_id": row_data.get("id"),
                        "name": row_data.get("name"),
                        "rating": row_data.get("yandex_rating"),
                        "reviews_total": row_data.get("yandex_reviews_total"),
                        "reviews_30d": row_data.get("yandex_reviews_30d"),
                        "last_sync": row_data.get("yandex_last_sync"),
                    }
                )
        except Exception:
            ratings = []
        
        bad_reviews = []
        
        db.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_revenue": sum(locations_revenue.values()),
                "total_orders": len(transactions),
                "locations_count": len(locations),
                "by_services": by_services,
                "by_masters": by_masters,
                "by_locations": by_locations,
                "ratings": ratings,
                "bad_reviews": bad_reviews
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения статистики сети: {str(e)}"}), 500


@app.route('/api/admin/yandex/sync/<string:network_id>', methods=['POST'])
def admin_sync_network_yandex(network_id):
    """
    Ручной запуск синхронизации Яндекс-данных для сети.
    Требует действующей сессии и прав суперадмина или владельца сети.
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        if network.get("owner_id") != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403

        db.close()

        if YandexSyncService is None:
            return jsonify({"error": "YandexSyncService не доступен. Проверьте логи сервера."}), 500
        
        try:
            sync_service = YandexSyncService()
            synced_count = sync_service.sync_network(network_id)
        except Exception as e:
            import traceback
            print(f"❌ Ошибка при синхронизации сети {network_id}: {e}")
            traceback.print_exc()
            return jsonify({"error": f"Ошибка синхронизации: {str(e)}"}), 500

        return jsonify(
            {
                "success": True,
                "synced_count": synced_count,
                "message": f"Обновлено бизнесов: {synced_count}",
            }
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка синхронизации Яндекс для сети: {str(e)}"}), 500


@app.route('/api/admin/yandex/sync/business/<string:business_id>', methods=['POST'])
def admin_sync_business_yandex(business_id):
    """
    Ручной запуск синхронизации Яндекс-данных для одного бизнеса.
    Требует действующей сессии и прав суперадмина или владельца бизнеса.
    """
    import traceback
    print(f"🔄 Запрос на синхронизацию бизнеса {business_id}")
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id, name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business = _row_to_dict(cursor, raw_business) if raw_business else None

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business.get("owner_id")
        business_name = (business.get("name") or "").strip() or "Unknown"

        if business_owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Аккаунт Яндекс.Бизнес (таблица externalbusinessaccounts — Postgres)
        cursor.execute("""
            SELECT id, auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'yandex_business' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        account_id = account_row.get("id") if account_row else None

        if account_id:
            print(f"✅ Найден аккаунт: {account_id}")
        else:
            print(f"⚠️ Аккаунт Яндекс.Бизнес не найден")

        cursor.execute("SELECT url FROM businessmaplinks WHERE business_id = %s AND map_type = 'yandex' LIMIT 1", (business_id,))
        raw_map = cursor.fetchone()
        map_link_row = _row_to_dict(cursor, raw_map) if raw_map else None
        map_url = map_link_row.get("url") if map_link_row else None

        if not account_id and not map_url:
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден источник данных",
                "message": "Для запуска парсинга добавьте ссылку на Яндекс.Карты или подключите аккаунт Яндекс.Бизнес"
            }), 400

        task_id = str(uuid.uuid4())
        user_id = user_data["user_id"]

        if map_url:
            task_type = 'parse_card'
            use_apify_map_parsing = bool(get_use_apify_map_parsing(db.conn))
            source = resolve_map_source_for_queue('yandex_maps', use_apify_map_parsing)
            target_url = map_url
            message = "Запущен парсинг карт (Apify)" if source == "apify_yandex" else "Запущен парсинг карт"
        else:
            task_type = 'sync_yandex_business'
            source = 'yandex_business'
            target_url = ''
            message = "Запущена синхронизация (без парсинга)"

        cursor.execute("""
            INSERT INTO parsequeue (
                id, business_id, account_id, task_type, source,
                status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s,
                    'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (task_id, business_id, account_id, task_type, source, user_id, target_url))
        db.conn.commit()
        db.close()
        print(f"✅ Задача {task_type} добавлена в очередь: {task_id}")

        return jsonify({
            "success": True,
            "message": message,
            "sync_id": task_id,
            "task_type": task_type
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ admin_sync_business_yandex: {e}\n{error_details}")
        payload = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        if getattr(app, "debug", False):
            payload["traceback"] = error_details
        return jsonify(payload), 500


@app.route('/api/admin/2gis/sync/business/<string:business_id>', methods=['POST'])
def admin_sync_business_2gis(business_id):
    """
    Ручной запуск синхронизации/парсинга 2ГИС для одного бизнеса.
    Приоритет:
      1) Если есть ссылка на 2ГИС в businessmaplinks -> task_type=parse_card, source=2gis
      2) Иначе, если есть активный external account 2gis -> task_type=sync_2gis
    """
    import traceback
    print(f"🔄 Запрос на синхронизацию 2ГИС бизнеса {business_id}")
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id, name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business = _row_to_dict(cursor, raw_business) if raw_business else None

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business.get("owner_id")
        if business_owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT id, auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = '2gis' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        account_id = account_row.get("id") if account_row else None

        cursor.execute(
            """
            SELECT url
            FROM businessmaplinks
            WHERE business_id = %s
              AND (
                map_type = '2gis'
                OR LOWER(url) LIKE '%%2gis.ru/%%'
                OR LOWER(url) LIKE '%%2gis.com/%%'
              )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_map = cursor.fetchone()
        map_row = _row_to_dict(cursor, raw_map) if raw_map else None
        map_url = (map_row.get("url") if map_row else None) or ""
        map_url = str(map_url).strip()

        if not map_url and not account_id:
            db.close()
            return jsonify(
                {
                    "success": False,
                    "error": "Не найден источник данных 2ГИС",
                    "message": "Добавьте ссылку на 2ГИС в Профиле или подключите аккаунт 2ГИС в интеграциях",
                }
            ), 400

        task_id = str(uuid.uuid4())
        user_id = user_data["user_id"]

        if map_url:
            task_type = "parse_card"
            use_apify_map_parsing = bool(get_use_apify_map_parsing(db.conn))
            source = resolve_map_source_for_queue("2gis", use_apify_map_parsing)
            target_url = map_url
            message = "Запущен парсинг 2ГИС карточки (Apify)" if source == "apify_2gis" else "Запущен парсинг 2ГИС карточки"
        else:
            task_type = "sync_2gis"
            source = "2gis"
            target_url = ""
            message = "Запущена синхронизация 2ГИС через API"

        cursor.execute(
            """
            INSERT INTO parsequeue (
                id, business_id, account_id, task_type, source,
                status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (task_id, business_id, account_id, task_type, source, user_id, target_url),
        )
        db.conn.commit()
        db.close()

        print(f"✅ Задача {task_type} (2GIS) добавлена в очередь: {task_id}")
        return jsonify(
            {
                "success": True,
                "message": message,
                "sync_id": task_id,
                "task_type": task_type,
                "source": source,
            }
        )
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ admin_sync_business_2gis: {e}\n{error_details}")
        payload = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        if getattr(app, "debug", False):
            payload["traceback"] = error_details
        return jsonify(payload), 500


def _sync_yandex_business_sync_task(sync_id, business_id, account_id):
    """Внутренняя функция для выполнения синхронизации (вызывается из worker)"""
    if YandexBusinessParser is None:
        print("❌ YandexBusinessParser не доступен")
        return False
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        cursor.execute("""
            SELECT auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE id = %s
        """, (account_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        
        if not account_row:
            print(f"❌ Аккаунт {account_id} не найден")
            cursor.execute("""
                UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (STATUS_ERROR, "Аккаунт не найден", sync_id))
            db.conn.commit()
            return False
        
        auth_data_encrypted = account_row.get("auth_data_encrypted")
        external_id = account_row.get("external_id")
        
        cursor.execute("SELECT name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business_row = _row_to_dict(cursor, raw_business) if raw_business else None
        business_name = (business_row.get("name") or "").strip() or "Unknown"
        
        db.close()
        
        # Расшифровываем auth_data
        print(f"🔐 Расшифровка auth_data для аккаунта {account_id}...")
        print(f"   Длина зашифрованных данных: {len(auth_data_encrypted) if auth_data_encrypted else 0} символов")
        auth_data_plain = decrypt_auth_data(auth_data_encrypted)
        if not auth_data_plain:
            print(f"❌ Не удалось расшифровать auth_data для аккаунта {account_id}")
            print(f"   Проверьте:")
            print(f"   1. Установлен ли EXTERNAL_AUTH_SECRET_KEY в .env (должен совпадать с ключом при шифровании)")
            print(f"   2. Установлена ли библиотека cryptography: pip install cryptography")
            print(f"   3. Правильный ли формат данных в БД")
            return False
        print(f"✅ auth_data успешно расшифрован (длина: {len(auth_data_plain)} символов)")
        
        # Парсим JSON auth_data
        import json
        try:
            auth_data_dict = json.loads(auth_data_plain)
        except json.JSONDecodeError:
            # Если не JSON, предполагаем что это просто cookies строка
            auth_data_dict = {"cookies": auth_data_plain}
        
        # Создаём парсер
        parser = YandexBusinessParser(auth_data_dict)
        
        # Получаем данные
        account_data = {
            "id": account_id,
            "business_id": business_id,
            "external_id": external_id
        }
        
        print(f"📥 Получение отзывов...")
        reviews = parser.fetch_reviews(account_data)
        print(f"✅ Получено отзывов: {len(reviews)}")
        
        print(f"📥 Получение статистики...")
        stats = parser.fetch_stats(account_data)
        print(f"✅ Получено точек статистики: {len(stats)}")
        
        print(f"📥 Получение публикаций...")
        posts = parser.fetch_posts(account_data)
        print(f"✅ Получено публикаций: {len(posts)}")
        
        # Получаем услуги/прайс-лист
        print(f"📥 Получение услуг/прайс-листа...")
        services = parser.fetch_services(account_data)
        print(f"✅ Получено услуг: {len(services)}")
        
        # Получаем информацию об организации (рейтинг, количество отзывов, новостей, фото)
        print(f"📥 Получение информации об организации...")
        org_info = parser.fetch_organization_info(account_data)
        print(f"✅ Информация об организации:")
        print(f"   Рейтинг: {org_info.get('rating')}")
        print(f"   Отзывов: {org_info.get('reviews_count')}")
        print(f"   Новостей: {org_info.get('news_count')}")
        print(f"   Фото: {org_info.get('photos_count')}")
        
        # Сохраняем данные
        db = DatabaseManager()
        worker = YandexBusinessSyncWorker()
        
        if reviews:
            worker._upsert_reviews(db, reviews)
            print(f"💾 Сохранено отзывов: {len(reviews)}")
        
        # Создаём статистику с информацией об организации, если её нет
        if not stats and org_info:
                from external_sources import ExternalStatsPoint, make_stats_id
                from datetime import date
                today_str = date.today().isoformat()
                stat_id = make_stats_id(business_id, "yandex_business", today_str)
                stat = ExternalStatsPoint(
                    id=stat_id,
                    business_id=business_id,
                    source="yandex_business",
                    date=today_str,
                    views_total=0,
                    clicks_total=0,
                    actions_total=0,
                    rating=org_info.get('rating'),
                    reviews_total=org_info.get('reviews_count') or len(reviews),
                    raw_payload=org_info,
                )
                stats = [stat]
        
        if stats:
            # Обновляем последнюю статистику информацией об организации
            if org_info and stats:
                last_stat = stats[-1]
                if last_stat.raw_payload:
                    last_stat.raw_payload.update(org_info)
                else:
                    last_stat.raw_payload = org_info
                # Обновляем рейтинг и количество отзывов из org_info
                if org_info.get('rating'):
                    last_stat.rating = org_info.get('rating')
                if org_info.get('reviews_count'):
                    last_stat.reviews_total = org_info.get('reviews_count')
            
            worker._upsert_stats(db, stats)
            print(f"💾 Сохранено точек статистики: {len(stats)}")
        
        if posts:
            worker._upsert_posts(db, posts)
            print(f"💾 Сохранено публикаций: {len(posts)}")
            
        # Сохраняем услуги в UserServices
        if services:
            try:
                cursor = db.conn.cursor()
                cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
                owner_row = cursor.fetchone()
                user_id = owner_row[0] if owner_row else None
                if not user_id:
                    print(f"⚠️ Нет user_id для сохранения услуг")
                else:
                    saved_count = 0
                    updated_count = 0
                    for service in services:
                        try:
                            # Проверяем, что service - это словарь
                            if not isinstance(service, dict):
                                print(f"⚠️ Услуга не является словарём: {type(service)}")
                                continue
                            
                            # Проверяем наличие обязательного поля name
                            if "name" not in service or not service["name"]:
                                print(f"⚠️ Услуга без названия, пропускаем")
                                continue
                            
                            # Проверяем, есть ли уже такая услуга
                            cursor.execute("""
                                SELECT id FROM UserServices 
                                WHERE business_id = ? AND name = ? 
                                LIMIT 1
                            """, (business_id, service["name"]))
                            existing = cursor.fetchone()
                            
                            # Преобразуем description в строку, если это dict (делаем это один раз в начале)
                            description = service.get("description", "")
                            if isinstance(description, dict):
                                description = description.get("text") or description.get("value") or description.get("content") or str(description)
                            elif not isinstance(description, str):
                                description = str(description) if description else ""
                            
                            # Преобразуем category в строку, если это dict
                            category = service.get("category", "Общие услуги")
                            if isinstance(category, dict):
                                category = category.get("name") or category.get("title") or str(category)
                            elif not isinstance(category, str):
                                category = str(category) if category else "Общие услуги"
                            
                            if not existing:
                                # Добавляем новую услугу
                                service_id = str(uuid.uuid4())
                                cursor.execute("""
                                    INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at, updated_at)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (
                                    service_id,
                                    user_id,
                                    business_id,
                                    category,
                                    service["name"],
                                    description,
                                    json.dumps(service.get("keywords", [])),
                                    service.get("price", "")
                                ))
                                saved_count += 1
                            else:
                                # Обновляем существующую услугу
                                cursor.execute("""
                                    UPDATE UserServices 
                                    SET category = ?, description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                                    WHERE business_id = ? AND name = ?
                                """, (
                                    category,
                                    description,
                                    json.dumps(service.get("keywords", [])),
                                    service.get("price", ""),
                                    business_id,
                                        service["name"]
                                    ))
                            updated_count += 1
                        except Exception as e:
                            print(f"⚠️ Ошибка сохранения услуги '{service.get('name', 'unknown')}': {e}")
                            import traceback
                            traceback.print_exc()
                            continue
                    
                    db.conn.commit()
                    print(f"💾 Сохранено услуг: {saved_count} новых, {updated_count} обновлено")
            except Exception as e:
                print(f"❌ Критическая ошибка при сохранении услуг: {e}")
                import traceback
                traceback.print_exc()
            
            # Обновляем last_sync_at
            cursor = db.conn.cursor()
            cursor.execute("""
                UPDATE externalbusinessaccounts
                SET last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = %s
            """, (account_id,))
        
            # Сохраняем срез в cards (Postgres source of truth вместо MapParseResults)
            try:
                cursor.execute("SELECT yandex_url FROM businesses WHERE id = %s", (business_id,))
                raw_url = cursor.fetchone()
                yandex_url = (_row_to_dict(cursor, raw_url) or {}).get("yandex_url") if raw_url else None
                if not yandex_url and external_id:
                    yandex_url = f"https://yandex.ru/sprav/{external_id}"
                url = yandex_url or f"https://yandex.ru/sprav/{external_id or 'unknown'}"
                rating_val = org_info.get('rating') if org_info else None
                reviews_cnt = len(reviews) if reviews else 0
                photos_cnt = org_info.get('photos_count', 0) if org_info else 0
                db.save_new_card_version(
                    business_id,
                    url=url,
                    rating=float(rating_val) if rating_val is not None else None,
                    reviews_count=reviews_cnt,
                    overview=json.dumps({"photos_count": photos_cnt, "posts_count": len(posts) if posts else 0}, ensure_ascii=False),
                )
                db.conn.commit()
                print(f"💾 Сохранена история в cards для business_id={business_id}")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в cards: {e}")
                import traceback
                traceback.print_exc()
        
        cursor = db.conn.cursor()
        cursor.execute("UPDATE parsequeue SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (STATUS_COMPLETED, sync_id))
        db.conn.commit()
        db.close()
        
        print(f"✅ Синхронизация завершена успешно для бизнеса {business_name}")
        return True
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Ошибка при синхронизации бизнеса {business_id}: {e}\n{error_details}")
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute("UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (STATUS_ERROR, str(e), sync_id))
            cursor.execute("UPDATE externalbusinessaccounts SET last_error = %s WHERE id = %s", (str(e), account_id))
            db.conn.commit()
            db.close()
        except Exception as save_error:
            print(f"⚠️ Не удалось сохранить ошибку в БД: {save_error}")
        return False

@app.route('/api/admin/yandex/sync/status/<string:sync_id>', methods=['GET'])
def admin_sync_status(sync_id):
    """Проверить статус синхронизации"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT id, business_id, account_id, source, status, error_message, created_at, updated_at
            FROM parsequeue
            WHERE id = %s AND task_type = 'sync_yandex_business'
        """, (sync_id,))
        raw_sync = cursor.fetchone()
        sync_data = _row_to_dict(cursor, raw_sync) if raw_sync else None
        
        if not sync_data:
            db.close()
            return jsonify({"error": "Синхронизация не найдена"}), 404
        
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (sync_data['business_id'],))
        raw_owner = cursor.fetchone()
        owner_row = _row_to_dict(cursor, raw_owner) if raw_owner else None
        owner_id = owner_row.get("owner_id") if owner_row else None
        
        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
        
        db.close()
        
        return jsonify({
            "success": True,
            "sync": {
                "id": sync_data['id'],
                "business_id": sync_data['business_id'],
                "status": sync_data['status'],
                "error_message": sync_data.get('error_message'),
                "created_at": sync_data['created_at'],
                "updated_at": sync_data['updated_at']
            }
        })
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса синхронизации: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/networks', methods=['GET'])
def get_user_networks():
    """Получить список сетей пользователя"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем наличие таблицы networks (Postgres)
        cursor.execute("SELECT to_regclass('public.networks')")
        networks_table_exists = cursor.fetchone()
        
        if not networks_table_exists:
            db.close()
            return jsonify({
                "success": True,
                "networks": []
            })
        
        # Получаем сети пользователя
        cursor.execute("""
            SELECT id, name, description 
            FROM networks 
            WHERE owner_id = %s 
            ORDER BY name
        """, (user_data['user_id'],))
        
        networks = []
        for row in cursor.fetchall():
            row_data = _row_to_dict(cursor, row) if row else {}
            networks.append({
                "id": row_data.get("id"),
                "name": row_data.get("name"),
                "description": row_data.get("description")
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "networks": networks
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения сетей: {str(e)}"}), 500

@app.route('/api/networks', methods=['POST'])
def create_network():
    """Создать новую сеть"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        
        if not name:
            return jsonify({"error": "Название сети обязательно"}), 400
        
        db = DatabaseManager()
        network_id = db.create_network(name, user_data['user_id'], description)
        db.close()
        
        return jsonify({
            "success": True,
            "network_id": network_id
        }), 201
        
    except Exception as e:
        import traceback
        print(f"❌ Ошибка создания сети: {e}")
        print(traceback.format_exc())
        return jsonify({"error": f"Ошибка создания сети: {str(e)}"}), 500

@app.route('/api/networks/<string:network_id>/businesses', methods=['POST'])
def add_business_to_network(network_id):
    """Добавить бизнес в сеть"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        business_id = data.get('business_id')
        name = data.get('name')
        address = data.get('address', '')
        yandex_url = data.get('yandex_url', '')
        
        if not business_id and not name:
            return jsonify({"error": "Необходимо указать business_id или name"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем права доступа к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Если business_id указан - добавляем существующий бизнес в сеть
        if business_id:
            # Проверяем, что бизнес принадлежит пользователю
            owner_id = get_business_owner_id(cursor, business_id)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            
            db.add_business_to_network(business_id, network_id)
            db.close()
            return jsonify({"success": True, "message": "Бизнес добавлен в сеть"})
        
        # Если business_id не указан - создаем новый бизнес в сети
        if not name:
            db.close()
            return jsonify({"error": "Название бизнеса обязательно"}), 400
        
        # Создаем новый бизнес
        new_business_id = db.create_business(
            name=name,
            owner_id=user_data['user_id'],
            address=address,
            business_type='beauty_salon',
            yandex_url=yandex_url
        )
        
        # Добавляем в сеть
        db.add_business_to_network(new_business_id, network_id)
        
        db.close()
        
        return jsonify({
            "success": True,
            "business_id": new_business_id,
            "message": "Бизнес создан и добавлен в сеть"
        }), 201
        
    except Exception as e:
        return jsonify({"error": f"Ошибка добавления бизнеса в сеть: {str(e)}"}), 500

@app.route('/api/finance/roi', methods=['GET'])
def get_roi_data():
    """Получить данные ROI"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Получаем последние данные ROI
        cursor.execute("""
            SELECT * FROM ROIData 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (user_data['user_id'],))
        
        roi_data = cursor.fetchone()
        
        if not roi_data:
            # Если данных нет, возвращаем базовую структуру
            return jsonify({
                "success": True,
                "roi": {
                    "investment_amount": 0,
                    "returns_amount": 0,
                    "roi_percentage": 0,
                    "period_start": None,
                    "period_end": None
                },
                "message": "Данные ROI не найдены. Добавьте транзакции для расчета."
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "roi": {
                "investment_amount": float(roi_data[2]),
                "returns_amount": float(roi_data[3]),
                "roi_percentage": float(roi_data[4]),
                "period_start": roi_data[5],
                "period_end": roi_data[6]
            }
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка получения ROI: {str(e)}"}), 500

@app.route('/api/finance/roi', methods=['POST'])
def calculate_roi():
    """Рассчитать и сохранить ROI"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json()
        
        # Валидация
        if 'investment_amount' not in data or 'returns_amount' not in data:
            return jsonify({"error": "Требуются investment_amount и returns_amount"}), 400
        
        investment = float(data['investment_amount'])
        returns = float(data['returns_amount'])
        
        if investment <= 0:
            return jsonify({"error": "Сумма инвестиций должна быть больше 0"}), 400
        
        # Вычисляем ROI
        roi_percentage = ((returns - investment) / investment * 100) if investment > 0 else 0
        
        # Сохраняем данные
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        roi_id = str(uuid.uuid4())
        period_start = data.get('period_start', datetime.now().strftime('%Y-%m-%d'))
        period_end = data.get('period_end', datetime.now().strftime('%Y-%m-%d'))
        
        cursor.execute("""
            INSERT OR REPLACE INTO ROIData 
            (id, user_id, investment_amount, returns_amount, roi_percentage, period_start, period_end)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (roi_id, user_data['user_id'], investment, returns, roi_percentage, period_start, period_end))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "roi": {
                "investment_amount": investment,
                "returns_amount": returns,
                "roi_percentage": round(roi_percentage, 2)
            },
            "message": "ROI рассчитан и сохранен"
        })
        
    except Exception as e:
        return jsonify({"error": f"Ошибка расчета ROI: {str(e)}"}), 500

@app.route('/api/auth/register', methods=['POST'])
@rate_limit_if_available("10 per hour")
def register():
    """Регистрация пользователя"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        
        # Создаем пользователя
        from auth_system import create_user
        result = create_user(email, password, name, phone)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 400
        
        # Отправляем приветственное письмо
        welcome_subject = "Добро пожаловать в BeautyBot!"
        welcome_body = f"""
Добро пожаловать в BeautyBot, {name}!

Ваш аккаунт успешно создан:
Email: {email}
Имя: {name}
Телефон: {phone if phone else 'Не указан'}

Теперь вы можете:
- Настроить описания услуг для Яндекс.Карт
- Генерировать ответы на отзывы
- Создавать новости для публикации
- И многое другое!

Начните с настройки вашего первого бизнеса.

---
С уважением,
Команда BeautyBot
        """
        
        send_email(email, welcome_subject, welcome_body)
        
        # Создаем сессию
        try:
            session_token = create_session(result['id'])
            if not session_token:
                return jsonify({"error": "Ошибка создания сессии"}), 500
        except Exception as session_error:
            print(f"❌ Ошибка создания сессии: {session_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "Ошибка создания сессии"}), 500
        
        return jsonify({
            "success": True,
            "user": {
                "id": result['id'],
                "email": result['email'],
                "name": result['name'],
                "phone": result['phone']
            },
            "token": session_token
        })
        
    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
@rate_limit_if_available("5 per minute")
def login():
    """Вход пользователя с защитой от brute force атак"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Неверный формат запроса"}), 400
            
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        
        # Аутентификация
        result = authenticate_user(email, password)
        
        if 'error' in result:
            if result.get('error') == 'account_blocked':
                return jsonify({"error": "account_blocked", "message": "user is blocked"}), 403
            return jsonify({"error": result['error']}), 401
        
        # Проверяем, есть ли у пользователя хотя бы один активный бизнес
        # Если все бизнесы заблокированы, пользователь не может войти
        db = None
        try:
            db = DatabaseManager()
            is_superadmin = db.is_superadmin(result['id'])
            
            if not is_superadmin:
                # Проверяем активные бизнесы для обычных пользователей
                businesses = db.get_businesses_by_owner(result['id'])
                if len(businesses) == 0:
                    if db:
                        db.close()
                    return jsonify({"error": "Все ваши бизнесы заблокированы. Обратитесь к администратору."}), 403
        except Exception as db_error:
            print(f"❌ Ошибка проверки бизнесов: {db_error}")
            import traceback
            traceback.print_exc()
            if db:
                db.close()
            return jsonify({"error": "Ошибка проверки данных пользователя"}), 500
        finally:
            if db:
                db.close()
        
        # Создаем сессию
        try:
            session_token = create_session(result['id'])
            if not session_token:
                return jsonify({"error": "Ошибка создания сессии"}), 500
        except Exception as session_error:
            print(f"❌ Ошибка создания сессии: {session_error}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": "Ошибка создания сессии"}), 500
        
        return jsonify({
            "success": True,
            "user": {
                "id": result['id'],
                "email": result.get('email', ''),
                "name": result.get('name', ''),
                "phone": result.get('phone', '')
            },
            "token": session_token
        })
        
    except Exception as e:
        print(f"❌ Ошибка входа: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Полный traceback:\n{error_traceback}")
        return jsonify({
            "error": str(e),
            "details": error_traceback if app.debug else None
        }), 500

@app.route('/api/auth/me', methods=['GET'])
def get_user_info():
    """Получить информацию о текущем пользователе"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Заблокированный пользователь — 403 (не 401)
        if user_data.get('is_active') is False:
            return jsonify({"error": "account_blocked", "message": "user is blocked"}), 403
        
        # Отладочное логирование
        print(f"🔍 DEBUG get_user_info: user_data type = {type(user_data)}")
        print(f"🔍 DEBUG get_user_info: user_data = {user_data}")
        
        # Получаем дополнительную информацию о пользователе
        db = DatabaseManager()
        # Безопасное получение user_id
        user_id = None
        if isinstance(user_data, dict):
            user_id = user_data.get('user_id') or user_data.get('id')
        elif hasattr(user_data, 'keys'):
            # Это sqlite3.Row
            if 'user_id' in user_data.keys():
                user_id = user_data['user_id']
            elif 'id' in user_data.keys():
                user_id = user_data['id']
        
        if not user_id:
            db.close()
            print(f"❌ Ошибка: не удалось определить user_id из user_data: {user_data}")
            return jsonify({"error": "Не удалось определить ID пользователя"}), 500
        
        print(f"🔍 DEBUG get_user_info: user_id = {user_id}")
        
        is_superadmin = db.is_superadmin(user_id)
        
        # Определяем, какие бизнесы показывать пользователю
        businesses = []
        if is_superadmin:
            # Суперадмин видит все бизнесы
            businesses = db.get_all_businesses()
        elif db.is_network_owner(user_id):
            # Владелец сети видит ТОЛЬКО бизнесы из своих сетей
            businesses = db.get_businesses_by_network_owner(user_id)
        else:
            # Обычный пользователь видит только свои бизнесы
            businesses = db.get_businesses_by_owner(user_id)
        
        # Проверяем, есть ли у пользователя хотя бы один активный бизнес
        # Если все бизнесы заблокированы, пользователь не может войти
        if not is_superadmin and len(businesses) == 0:
            db.close()
            return jsonify({"error": "Все ваши бизнесы заблокированы. Обратитесь к администратору."}), 403
        
        db.close()
        
        # Безопасное получение данных пользователя
        def safe_get(data, key, default=None):
            if isinstance(data, dict):
                return data.get(key, default)
            elif hasattr(data, 'keys') and key in data.keys():
                return data[key]
            return default
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "email": safe_get(user_data, 'email'),
                "name": safe_get(user_data, 'name'),
                "phone": safe_get(user_data, 'phone'),
                "is_superadmin": is_superadmin
            },
            "businesses": businesses
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о пользователе: {e}")
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Полный traceback:\n{error_traceback}")
        return jsonify({
            "error": str(e),
            "details": error_traceback if app.debug else None
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Выход пользователя"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        
        # Удаляем сессию
        from auth_system import logout_session
        success = logout_session(token)
        
        if success:
            return jsonify({"success": True, "message": "Выход выполнен успешно"})
        else:
            return jsonify({"error": "Ошибка выхода"}), 500
        
    except Exception as e:
        print(f"❌ Ошибка выхода: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/users/profile', methods=['PUT'])
def update_user_profile():
    """Обновить профиль пользователя"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        
        # Получаем пользователя по токену
        from auth_system import verify_session
        user = verify_session(token)
        if not user:
            return jsonify({"error": "Неверный токен"}), 401
        
        # Получаем данные для обновления
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Обновляем только разрешенные поля
        updates = {}
        if 'name' in data:
            updates['name'] = data['name']
        if 'phone' in data:
            updates['phone'] = data['phone']
        
        if not updates:
            return jsonify({"error": "Нет данных для обновления"}), 400
        
        # Обновляем в базе данных
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [user['user_id']]
        
        cursor.execute(f"UPDATE Users SET {set_clause} WHERE id = ?", values)
        db.conn.commit()
        db.close()
        
        # Возвращаем обновленные данные пользователя
        updated_user = {**user, **updates}
        return jsonify({
            "success": True,
            "user": updated_user
        })
        
    except Exception as e:
        print(f"❌ Ошибка обновления профиля: {e}")
        return jsonify({"error": str(e)}), 500

# ===== SUPERADMIN API =====

@app.route('/api/superadmin/businesses', methods=['GET'])
def get_all_businesses():
    """Получить все бизнесы (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        businesses = db.get_all_businesses()
        db.close()
        
        return jsonify({"success": True, "businesses": businesses})
        
    except Exception as e:
        print(f"❌ Ошибка получения бизнесов: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/businesses', methods=['POST'])
def create_business():
    """Создать новый бизнес (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        with DatabaseManager() as db:
            if not db.is_superadmin(user_data['user_id']):
                return jsonify({"error": "Недостаточно прав"}), 403
            
            data = request.get_json()
            name = data.get('name')
            description = data.get('description', '')
            industry = data.get('industry', '')
            owner_id = data.get('owner_id')
            owner_email = data.get('owner_email')
            owner_name = data.get('owner_name', '')
            owner_phone = data.get('owner_phone', '')
            
            if not name:
                return jsonify({"error": "Название бизнеса обязательно"}), 400
            
            # Если передан owner_email, но не owner_id - находим или создаём пользователя
            if owner_email and not owner_id:
                existing_user = db.get_user_by_email(owner_email)
                if existing_user:
                    owner_id = existing_user['id']
                    print(f"✅ Найден существующий пользователь: {owner_email} (ID: {owner_id})")
                else:
                    # Создаём пользователя напрямую через DatabaseManager, чтобы использовать то же соединение
                    import uuid
                    from datetime import datetime
                    
                    # Используем то же соединение, что и DatabaseManager
                    cursor = db.conn.cursor()
                    owner_id = str(uuid.uuid4())
                    
                    try:
                        cursor.execute("""
                            INSERT INTO Users (id, email, name, phone, created_at, is_active, is_verified)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            owner_id,
                            owner_email,
                            owner_name or None,
                            owner_phone or None,
                            datetime.now().isoformat(),
                            1,  # is_active
                            0   # is_verified
                        ))
                        db.conn.commit()
                        print(f"✅ Создан новый пользователь: {owner_email} (ID: {owner_id})")
                    except Exception as e:
                        db.conn.rollback()
                        print(f"❌ Ошибка создания пользователя: {e}")
                        import traceback
                        traceback.print_exc()
                        return jsonify({"error": f"Ошибка создания пользователя: {str(e)}"}), 400
            
            # Проверяем, что owner_id установлен
            if not owner_id:
                return jsonify({"error": "Необходимо указать owner_id или owner_email для создания бизнеса"}), 400
            
            try:
                business_id = db.create_business(name, description, industry, owner_id)
                db.conn.commit()  # Явно коммитим транзакцию
                return jsonify({"success": True, "business_id": business_id, "owner_id": owner_id})
            except Exception as e:
                db.conn.rollback()
                print(f"❌ Ошибка создания бизнеса: {e}")
                import traceback
                traceback.print_exc()
                return jsonify({"error": f"Ошибка создания бизнеса: {str(e)}"}), 500
        
    except Exception as e:
        print(f"❌ Ошибка создания бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ===== EXTERNAL SOURCES API (Яндекс.Бизнес / Google Business / 2ГИС) =====
# ДУБЛИКАТ УДАЛЁН - см. определения выше (строки 429, 500, 627)

@app.route('/api/superadmin/businesses/<business_id>', methods=['PUT'])
def update_business(business_id):
    """Обновить бизнес (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description')
        industry = data.get('industry')
        
        db.update_business(business_id, name, description, industry)
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка обновления бизнеса: {e}")
        return jsonify({"error": str(e)}), 500

# ==================== УПРАВЛЕНИЕ ПРОКСИ ====================
@app.route('/api/admin/proxies', methods=['GET'])
def get_proxies():
    """Получить список прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, proxy_type, host, port, is_active, is_working, 
                   success_count, failure_count, last_used_at, last_checked_at
            FROM ProxyServers
            ORDER BY created_at DESC
        """)
        
        proxies = []
        for row in cursor.fetchall():
            row_get = row.get if hasattr(row, "get") else None
            proxies.append({
                "id": (row_get("id") if row_get else row[0]),
                "type": (row_get("proxy_type") if row_get else row[1]),
                "host": (row_get("host") if row_get else row[2]),
                "port": (row_get("port") if row_get else row[3]),
                "is_active": bool(row_get("is_active") if row_get else row[4]),
                "is_working": bool(row_get("is_working") if row_get else row[5]),
                "success_count": (row_get("success_count") if row_get else row[6]),
                "failure_count": (row_get("failure_count") if row_get else row[7]),
                "last_used_at": (row_get("last_used_at") if row_get else row[8]),
                "last_checked_at": (row_get("last_checked_at") if row_get else row[9]),
            })
        
        db.close()
        return jsonify({"proxies": proxies})
        
    except Exception as e:
        print(f"❌ Ошибка получения прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies', methods=['POST'])
def add_proxy():
    """Добавить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.json
        proxy_id = str(uuid.uuid4())
        
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO ProxyServers (
                id, proxy_type, host, port, username, password,
                is_active, is_working, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            proxy_id,
            data.get('type', 'http'),
            data['host'],
            data['port'],
            data.get('username'),
            data.get('password')  # TODO: зашифровать
        ))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "proxy_id": proxy_id})
        
    except Exception as e:
        print(f"❌ Ошибка добавления прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies/<proxy_id>', methods=['DELETE'])
def delete_proxy(proxy_id):
    """Удалить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM ProxyServers WHERE id = %s", (proxy_id,))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка удаления прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies/<proxy_id>/toggle', methods=['POST'])
def toggle_proxy(proxy_id):
    """Включить/выключить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        # Получаем текущий статус
        cursor.execute("SELECT is_active FROM ProxyServers WHERE id = %s", (proxy_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Прокси не найден"}), 404
        
        current_status = row.get("is_active") if hasattr(row, "get") else row[0]
        new_status = False if bool(current_status) else True
        cursor.execute("""
            UPDATE ProxyServers 
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, proxy_id))
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "is_active": bool(new_status)})
        
    except Exception as e:
        print(f"❌ Ошибка переключения прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ==================== ПРОМПТЫ ДЛЯ AI ====================
@app.route('/api/admin/prompts', methods=['GET', 'OPTIONS'])
def get_prompts():
    """Получить все промпты (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        # Проверяем, существует ли таблица, если нет - создаём
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aiprompts (
                id TEXT PRIMARY KEY,
                prompt_type TEXT UNIQUE NOT NULL,
                prompt_text TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                FOREIGN KEY (updated_by) REFERENCES Users(id) ON DELETE SET NULL
            )
        """)
        db.conn.commit()
        
        cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM aiprompts ORDER BY prompt_type")
        rows = cursor.fetchall()
        
        # Если таблица пустая, инициализируем дефолтные промпты
        if not rows:
            default_prompts = [
                ('service_optimization', 
                 """Ты - SEO-специалист для бьюти-индустрии. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
Запрещено любые мнения, диалог, оценочные суждения, обсуждение конкурентов, оскорбления. Никакого текста кроме результата.

Регион: {region}
Название бизнеса: {business_name}
Тон: {tone}
Язык результата: {language_name} (все текстовые поля optimized_name, seo_description и general_recommendations должны быть на этом языке)
Длина описания: {length} символов
Дополнительные инструкции: {instructions}

ИСПОЛЬЗУЙ ЧАСТОТНЫЕ ЗАПРОСЫ:
{frequent_queries}

Формат ответа СТРОГО В JSON:
{{
  "services": [
    {{
      "original_name": "...",
      "optimized_name": "...",              
      "seo_description": "...",             
      "keywords": ["...", "...", "..."], 
      "price": null,
      "category": "hair|nails|spa|barber|massage|other"
    }}
  ],
  "general_recommendations": ["...", "..."]
}}

Исходные услуги/контент:
{content}""",
                 'Промпт для оптимизации услуг и прайс-листа'),
                ('review_reply',
                 """Ты - вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Write the reply in {language_name}.
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{examples_text}
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text[:1000]}""",
                 'Промпт для генерации ответов на отзывы'),
                ('news_generation',
                 """Ты - маркетолог для локального бизнеса. Сгенерируй новость для публикации на картах (Google, Яндекс).
Требования: до 1500 символов, можно использовать 2-3 эмодзи (не переборщи), без хештегов, без оценочных суждений, без упоминания конкурентов. Стиль - информативный и дружелюбный.
Write all generated text in {language_name}.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Контекст услуги (может отсутствовать): {service_context}
Контекст выполненной работы/транзакции (может отсутствовать): {transaction_context}
Свободная информация (может отсутствовать): {raw_info[:800]}
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{news_examples}""",
                 'Промпт для генерации новостей')
            ]
            
            for prompt_type, prompt_text, description in default_prompts:
                cursor.execute(
                    """
                    INSERT INTO aiprompts (id, prompt_type, prompt_text, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (f"prompt_{prompt_type}", prompt_type, prompt_text, description),
                )
            
            db.conn.commit()
            # Перечитываем после вставки
            cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM aiprompts ORDER BY prompt_type")
            rows = cursor.fetchall()
        
        prompts = []
        for row in rows:
            row_data = _row_to_dict(cursor, row) if row else {}
            prompts.append({
                'type': row_data.get('prompt_type'),
                'text': row_data.get('prompt_text'),
                'description': row_data.get('description'),
                'updated_at': row_data.get('updated_at'),
                'updated_by': row_data.get('updated_by')
            })
        
        db.close()
        return jsonify({"prompts": prompts})
        
    except Exception as e:
        print(f"❌ Ошибка получения промптов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/prompts/<prompt_type>', methods=['PUT', 'OPTIONS'])
def update_prompt(prompt_type):
    """Обновить промпт (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.get_json()
        prompt_text = data.get('text', '').strip()
        description = data.get('description', '').strip()
        
        if not prompt_text:
            return jsonify({"error": "Текст промпта не может быть пустым"}), 400
        
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE aiprompts 
            SET prompt_text = %s, description = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE prompt_type = %s
        """, (prompt_text, description, user_data['user_id'], prompt_type))
        
        if cursor.rowcount == 0:
            # Если промпта нет, создаём его
            cursor.execute("""
                INSERT INTO aiprompts (id, prompt_type, prompt_text, description, updated_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (f"prompt_{prompt_type}", prompt_type, prompt_text, description, user_data['user_id']))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка обновления промпта: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def get_prompt_from_db(prompt_type: str, fallback: str = None) -> str:
    """Получить промпт из БД или использовать fallback"""
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT prompt_text FROM aiprompts WHERE prompt_type = %s", (prompt_type,))
        row = cursor.fetchone()
        db.close()
        
        if row:
            # Правильно извлекаем строку из row (может быть tuple, dict, или sqlite3.Row)
            prompt_text = None
            
            # Если это sqlite3.Row (имеет атрибут keys)
            if hasattr(row, 'keys'):
                try:
                    prompt_text = row['prompt_text']
                except (KeyError, IndexError):
                    try:
                        prompt_text = row[0]
                    except (KeyError, IndexError):
                        prompt_text = None
            # Если это dict
            elif isinstance(row, dict):
                prompt_text = row.get('prompt_text', '')
            # Если это tuple или list
            elif isinstance(row, (tuple, list)) and len(row) > 0:
                prompt_text = row[0]
            else:
                prompt_text = None
            
            # Убеждаемся, что это строка
            if prompt_text is not None:
                print(f"🔍 DEBUG get_prompt_from_db: prompt_text type before conversion = {type(prompt_text)}", flush=True)
                prompt_text = str(prompt_text) if not isinstance(prompt_text, str) else prompt_text
                print(f"🔍 DEBUG get_prompt_from_db: prompt_text type after conversion = {type(prompt_text)}", flush=True)
                if prompt_text.strip():
                    return prompt_text
            
            # Если не удалось извлечь - используем fallback
            if fallback:
                print(f"⚠️ Не удалось извлечь промпт из row, используем fallback. Row type: {type(row)}, Row value: {row}", flush=True)
                return fallback
            else:
                return ""
        elif fallback:
            return fallback
        else:
            return ""
    except Exception as e:
        print(f"⚠️ Ошибка получения промпта из БД: {e}")
        import traceback
        traceback.print_exc()
        return fallback or ""

# ==================== СХЕМА РОСТА (GROWTH PLAN) ====================
@app.route('/api/business-types', methods=['GET'])
def get_business_types_public():
    """Получить все активные типы бизнеса (для всех пользователей)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT type_key, label
            FROM businesstypes
            WHERE COALESCE(LOWER(is_active::text), '1') IN ('1', 'true', 't')
            ORDER BY label
        """)
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            row_data = _row_to_dict(cursor, row) if row else {}
            types.append({
                'type_key': row_data.get('type_key'),
                'label': row_data.get('label')
            })
        
        db.close()
        return jsonify({"types": types})
        
    except Exception as e:
        print(f"❌ Ошибка получения типов бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/business-types', methods=['GET', 'OPTIONS'])
def get_business_types():
    """Получить все типы бизнеса (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, type_key, label, description, is_active FROM businesstypes ORDER BY label")
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            row_data = _row_to_dict(cursor, row) if row else {}
            is_active_raw = row_data.get('is_active')
            is_active_bool = str(is_active_raw).lower() in ('1', 'true', 't') if is_active_raw is not None else True
            types.append({
                'id': row_data.get('id'),
                'type_key': row_data.get('type_key'),
                'label': row_data.get('label'),
                'description': row_data.get('description'),
                'is_active': is_active_bool
            })
        
        db.close()
        return jsonify({"types": types})
        
    except Exception as e:
        print(f"❌ Ошибка получения типов бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/business-types', methods=['POST', 'OPTIONS'])
def create_business_type():
    """Создать новый тип бизнеса (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.get_json()
        type_key = data.get('type_key', '').strip()
        label = data.get('label', '').strip()
        description = data.get('description', '').strip()
        
        if not type_key or not label:
            return jsonify({"error": "type_key и label обязательны"}), 400
        
        import uuid
        type_id = f"bt_{uuid.uuid4().hex[:12]}"
        
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO businesstypes (id, type_key, label, description)
            VALUES (%s, %s, %s, %s)
        """, (type_id, type_key, label, description))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "id": type_id})
        
    except Exception as e:
        print(f"❌ Ошибка создания типа бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/business-types/<type_id>', methods=['PUT', 'DELETE', 'OPTIONS'])
def update_or_delete_business_type(type_id):
    """Обновить или удалить тип бизнеса (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        
        if request.method == 'DELETE':
            cursor.execute("DELETE FROM businesstypes WHERE id = %s", (type_id,))
            db.conn.commit()
            db.close()
            return jsonify({"success": True})
        
        # PUT - обновление
        data = request.get_json()
        label = data.get('label', '').strip()
        description = data.get('description', '').strip()
        is_active = data.get('is_active', True)
        
        if not label:
            return jsonify({"error": "label обязателен"}), 400
        
        cursor.execute("""
            UPDATE businesstypes 
            SET label = %s, description = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (label, description, bool(is_active), type_id))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка обновления/удаления типа бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/progress', methods=['GET'])
def get_business_progress():
    """Получить прогресс развития бизнеса"""
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
            
        business_id = request.args.get('business_id')
        if not business_id:
             return jsonify({"error": "Не указан business_id"}), 400
             
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверка доступа
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
            
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
            
        # 1. Определяем тип бизнеса
        cursor.execute("SELECT business_type FROM businesses WHERE id = %s", (business_id,))
        row = cursor.fetchone()
        business_type_key = row[0] if row else 'other'
        
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM businesstypes WHERE type_key = %s OR id = %s", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
             # Fallback
             cursor.execute("SELECT id FROM businesstypes WHERE type_key = 'other'")
             bt_row = cursor.fetchone()
             
        business_type_id = bt_row[0] if bt_row else None
        
        if not business_type_id:
            # Если даже 'other' нет
            db.close()
            return jsonify({"stages": [], "current_step": 1})
            
        # 2. Получаем текущий прогресс (шаг визарда)
        cursor.execute("SELECT step FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row[0] if wiz_row else 1
        
        # 3. Получаем этапы
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration, is_permanent
            FROM GrowthStages
            WHERE business_type_id = ?
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        stages = []
        for stage_row in stages_rows:
            stage_id = stage_row[0]
            stage_number = stage_row[1]
            
            # Получаем задачи
            cursor.execute("""
                SELECT id, task_number, task_text
                FROM GrowthTasks
                WHERE stage_id = ?
                ORDER BY task_number
            """, (stage_id,))
            tasks_rows = cursor.fetchall()
            
            # Определяем статус этапа
            is_completed = stage_number < current_step
            is_current = stage_number == current_step
            
            tasks = []
            for t in tasks_rows:
                tasks.append({
                    'id': t[0], 
                    'number': t[1], 
                    'text': t[2],
                    'is_completed': is_completed # Пока считаем все задачи выполненными если этап пройден
                })
            
            stages.append({
                'id': stage_id,
                'stage_number': stage_number,
                'title': stage_row[2],
                'description': stage_row[3],
                'goal': stage_row[4],
                'expected_result': stage_row[5],
                'duration': stage_row[6],
                'is_permanent': bool(stage_row[7]),
                'status': 'completed' if is_completed else ('current' if is_current else 'locked'),
                'tasks': tasks
            })
            
        db.close()
        
        return jsonify({
            "success": True,
            "current_step": current_step,
            "stages": stages
        })
        
    except Exception as e:
        print(f"❌ Ошибка api/progress: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<string:business_id>/stages', methods=['GET'])
def get_business_stages(business_id):
    """Получить этапы роста для конкретного бизнеса (для ProgressTracker)"""
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
            
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверка доступа
        cursor.execute("SELECT owner_id, business_type FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
            
        owner_id = business['owner_id'] if isinstance(business, dict) else business[0]
        business_type_key = business['business_type'] if isinstance(business, dict) else business[1]
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
            
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM businesstypes WHERE type_key = %s OR id = %s", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
            cursor.execute("SELECT id FROM businesstypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()
             
        business_type_id = bt_row['id'] if isinstance(bt_row, dict) else (bt_row[0] if bt_row else None)
        
        if not business_type_id:
            db.close()
            return jsonify({"stages": []})
            
        # Получаем текущий шаг визарда
        cursor.execute("SELECT step FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row[0] if wiz_row else 1
        
        # Получаем этапы
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration
            FROM growthstages
            WHERE business_type_id = %s
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        stages = []
        for stage_row in stages_rows:
            stage_number = stage_row[1]
            
            # Определяем статус
            if stage_number < current_step:
                status = 'completed'
            elif stage_number == current_step:
                status = 'active'
            else:
                status = 'pending'
            
            stages.append({
                'id': stage_row[0],
                'stage_number': stage_number,
                'stage_name': stage_row[2],
                'stage_description': stage_row[3],
                'status': status,
                'progress_percentage': 100 if status == 'completed' else (50 if status == 'active' else 0),
                'target_revenue': 0,  # TODO: Можно добавить из финансовых данных
                'target_clients': 0,
                'target_roi': 0,
                'current_revenue': 0,
                'current_clients': 0,
                'current_roi': 0,
                'started_at': None,
                'completed_at': None
            })
            
        db.close()
        
        return jsonify({
            "success": True,
            "stages": stages
        })
        
    except Exception as e:
        print(f"❌ Ошибка /api/business/{business_id}/stages: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/growth-stages/<business_type_id>', methods=['GET', 'OPTIONS'])
def get_growth_stages(business_type_id):
    """Получить этапы роста для типа бизнеса"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration, is_permanent
            FROM GrowthStages
            WHERE business_type_id = ?
            ORDER BY stage_number
        """, (business_type_id,))
        stages_rows = cursor.fetchall()
        
        stages = []
        for stage_row in stages_rows:
            stage_id = stage_row[0]
            # Получаем задачи для этапа
            cursor.execute("""
                SELECT id, task_number, task_text
                FROM GrowthTasks
                WHERE stage_id = ?
                ORDER BY task_number
            """, (stage_id,))
            tasks_rows = cursor.fetchall()
            
            tasks = [{'id': t[0], 'number': t[1], 'text': t[2]} for t in tasks_rows]
            
            stages.append({
                'id': stage_id,
                'stage_number': stage_row[1],
                'title': stage_row[2],
                'description': stage_row[3],
                'goal': stage_row[4],
                'expected_result': stage_row[5],
                'duration': stage_row[6],
                'is_permanent': bool(stage_row[7]),
                'tasks': tasks
            })
        
        db.close()
        return jsonify({"stages": stages})
        
    except Exception as e:
        print(f"❌ Ошибка получения этапов роста: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/growth-stages', methods=['POST', 'OPTIONS'])
def create_growth_stage():
    """Создать этап роста"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.get_json()
        business_type_id = data.get('business_type_id')
        stage_number = data.get('stage_number')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        goal = data.get('goal', '').strip()
        expected_result = data.get('expected_result', '').strip()
        duration = data.get('duration', '').strip()
        is_permanent = data.get('is_permanent', False)
        tasks = data.get('tasks', [])
        
        if not business_type_id or stage_number is None or not title:
            return jsonify({"error": "business_type_id, stage_number и title обязательны"}), 400
        
        stage_id = f"gs_{uuid.uuid4().hex[:12]}"
        
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO GrowthStages (id, business_type_id, stage_number, title, description, goal, expected_result, duration, is_permanent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (stage_id, business_type_id, stage_number, title, description, goal, expected_result, duration, 1 if is_permanent else 0))
        
        # Добавляем задачи
        for task_idx, task_text in enumerate(tasks, 1):
            task_id = f"gt_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO GrowthTasks (id, stage_id, task_number, task_text)
                VALUES (?, ?, ?, ?)
            """, (task_id, stage_id, task_idx, task_text.strip()))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "id": stage_id})
        
    except Exception as e:
        print(f"❌ Ошибка создания этапа роста: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/growth-stages/<stage_id>', methods=['PUT', 'DELETE', 'OPTIONS'])
def update_or_delete_growth_stage(stage_id):
    """Обновить или удалить этап роста"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        cursor = db.conn.cursor()
        
        if request.method == 'DELETE':
            cursor.execute("DELETE FROM growthstages WHERE id = %s", (stage_id,))
            db.conn.commit()
            db.close()
            return jsonify({"success": True})
        
        # PUT - обновление
        data = request.get_json()
        stage_number = data.get('stage_number')
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        goal = data.get('goal', '').strip()
        expected_result = data.get('expected_result', '').strip()
        duration = data.get('duration', '').strip()
        is_permanent = data.get('is_permanent', False)
        tasks = data.get('tasks', [])
        
        if stage_number is None or not title:
            return jsonify({"error": "stage_number и title обязательны"}), 400
        
        cursor.execute("""
            UPDATE GrowthStages 
            SET stage_number = ?, title = ?, description = ?, goal = ?, expected_result = ?, duration = ?, is_permanent = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (stage_number, title, description, goal, expected_result, duration, 1 if is_permanent else 0, stage_id))
        
        # Удаляем старые задачи и добавляем новые
        cursor.execute("DELETE FROM GrowthTasks WHERE stage_id = ?", (stage_id,))
        for task_idx, task_text in enumerate(tasks, 1):
            task_id = f"gt_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO GrowthTasks (id, stage_id, task_number, task_text)
                VALUES (?, ?, ?, ?)
            """, (task_id, stage_id, task_idx, task_text.strip()))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка обновления/удаления этапа роста: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/businesses/<business_id>/send-credentials', methods=['POST'])
def send_business_credentials(business_id):
    """Отправить данные для входа владельцу бизнеса (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        # Получаем информацию о бизнесе и владельце
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT b.*, u.email, u.name as owner_name
            FROM Businesses b
            LEFT JOIN Users u ON b.owner_id = u.id
            WHERE b.id = ?
        """, (business_id,))
        business_row = cursor.fetchone()
        
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        business = dict(business_row)
        owner_email = business.get('email')
        
        if not owner_email:
            db.close()
            return jsonify({"error": "У бизнеса не указан email владельца"}), 400
        
        # Генерируем временный пароль, если у пользователя его нет
        import secrets
        from auth_system import set_password, get_user_by_id
        
        owner_id = business.get('owner_id')
        if not owner_id:
            db.close()
            return jsonify({"error": "У бизнеса не указан владелец"}), 400
        
        owner_user = get_user_by_id(owner_id)
        if not owner_user:
            db.close()
            return jsonify({"error": "Владелец бизнеса не найден"}), 404
        
        # Генерируем пароль, если его нет
        temp_password = None
        if not owner_user.get('password_hash'):
            temp_password = secrets.token_urlsafe(12)
            set_password(owner_id, temp_password)
            print(f"✅ Сгенерирован временный пароль для {owner_email}")
        
        # Отправляем email с данными для входа
        login_url = "https://beautybot.pro/login"
        subject = f"Данные для входа в личный кабинет {business.get('name', 'BeautyBot')}"
        
        if temp_password:
            body = f"""
Здравствуйте, {business.get('owner_name', '')}!

Ваш бизнес "{business.get('name', '')}" был зарегистрирован в системе BeautyBot.

Данные для входа в личный кабинет:
Email: {owner_email}
Пароль: {temp_password}

Пожалуйста, войдите в систему по ссылке: {login_url}

После первого входа рекомендуется изменить пароль в настройках профиля.

---
С уважением,
Команда BeautyBot
            """
        else:
            body = f"""
Здравствуйте, {business.get('owner_name', '')}!

Ваш бизнес "{business.get('name', '')}" зарегистрирован в системе BeautyBot.

Для входа в личный кабинет используйте ваш существующий пароль:
Email: {owner_email}

Войти в систему: {login_url}

Если вы забыли пароль, воспользуйтесь функцией восстановления пароля на странице входа.

---
С уважением,
Команда BeautyBot
            """
        
        email_sent = send_email(owner_email, subject, body)
        db.close()
        
        if email_sent:
            return jsonify({
                "success": True,
                "message": f"Данные для входа отправлены на {owner_email}",
                "password_generated": temp_password is not None
            })
        else:
            return jsonify({"error": "Не удалось отправить email"}), 500
        
    except Exception as e:
        print(f"❌ Ошибка отправки credentials: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/businesses/<business_id>', methods=['DELETE'])
def delete_business(business_id):
    """Удалить бизнес (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403
        
        print(f"🔍 DELETE запрос для бизнеса: {business_id}")
        success = db.delete_business(business_id)
        db.close()
        
        if success:
            return jsonify({"success": True, "message": "Бизнес удалён навсегда"})
        else:
            return jsonify({"error": "Бизнес не найден или не удалось удалить"}), 404
        
    except Exception as e:
        print(f"❌ Ошибка удаления бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users', methods=['GET'])
def get_all_users():
    """Получить всех пользователей (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403
        
        users = db.get_all_users()
        db.close()
        
        return jsonify({"success": True, "users": users})
        
    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users-with-businesses', methods=['GET'])
def get_users_with_businesses():
    """Получить всех пользователей с их бизнесами и сетями (для админской страницы)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем, что это именно demyanovap@yandex.ru
        if user_data.get('email') != 'demyanovap@yandex.ru':
            return jsonify({"error": "Доступ запрещён. Только для demyanovap@yandex.ru"}), 403
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        users_with_businesses = db.get_all_users_with_businesses()
        
        # Логируем для отладки
        total_blocked = 0
        for user in users_with_businesses:
            email = user.get('email', 'N/A')
            blocked_direct = sum(1 for b in user.get('direct_businesses', []) if b.get('is_active') == 0)
            blocked_network = sum(1 for network in user.get('networks', []) for b in network.get('businesses', []) if b.get('is_active') == 0)
            total_blocked += blocked_direct + blocked_network
            if blocked_direct > 0 or blocked_network > 0:
                print(f"🔍 DEBUG API: Пользователь {email} имеет {blocked_direct} заблокированных прямых + {blocked_network} в сетях")
                if email == 'demyanovap@yandex.ru':
                    print(f"🔍 DEBUG API: Всего бизнесов у {email}: {len(user.get('direct_businesses', []))}")
                    for b in user.get('direct_businesses', []):
                        print(f"  - {b.get('name')} (is_active: {b.get('is_active')})")
        print(f"🔍 DEBUG API get_all_users_with_businesses: всего заблокированных бизнесов: {total_blocked}")
        
        db.close()
        
        return jsonify({"success": True, "users": users_with_businesses})
        
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"❌ Ошибка получения пользователей с бизнесами: {e}")
        print(f"❌ Полный traceback:\n{error_traceback}")
        # Всегда возвращаем JSON с подробной ошибкой (для dev).
        payload = {
            "detail": "internal_error in /api/admin/users-with-businesses",
            "where": "main.get_users_with_businesses",
            "error_type": e.__class__.__name__,
            "error": str(e),
            "traceback": error_traceback,
        }
        return jsonify(payload), 500

@app.route('/api/admin/businesses/<business_id>/block', methods=['POST'])
def block_business(business_id):
    """Заблокировать/разблокировать бизнес (только для demyanovap@yandex.ru)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Доступ запрещён"}), 403
        db.close()
        
        data = request.get_json()
        is_blocked = data.get('is_blocked', True)
        
        db = DatabaseManager()
        success = db.block_business(business_id, is_blocked)
        db.close()
        
        if success:
            return jsonify({"success": True, "message": "Бизнес заблокирован" if is_blocked else "Бизнес разблокирован"})
        else:
            return jsonify({"error": "Бизнес не найден"}), 404
        
    except Exception as e:
        print(f"❌ Ошибка блокировки бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/businesses/<business_id>/promo', methods=['POST'])
def set_promo_tier(business_id):
    """Установить/отключить промо тариф для бизнеса (только для суперадмина)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Доступ запрещён"}), 403
        
        data = request.get_json()
        is_promo = data.get('is_promo', True)
        
        cursor = db.conn.cursor()
        
        # Проверяем, что бизнес существует
        cursor.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Проверяем наличие колонок subscription_tier и subscription_status
        cursor.execute("PRAGMA table_info(Businesses)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Добавляем колонки, если их нет
        if 'subscription_tier' not in columns:
            cursor.execute("ALTER TABLE Businesses ADD COLUMN subscription_tier TEXT DEFAULT 'trial'")
            print("✅ Добавлена колонка subscription_tier")
        
        if 'subscription_status' not in columns:
            cursor.execute("ALTER TABLE Businesses ADD COLUMN subscription_status TEXT DEFAULT 'active'")
            print("✅ Добавлена колонка subscription_status")
        
        # Устанавливаем или отключаем промо тариф
        if is_promo:
            # Устанавливаем промо тариф
            cursor.execute("""
                UPDATE Businesses 
                SET subscription_tier = 'promo',
                    subscription_status = 'active',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (business_id,))
            message = "Промо тариф установлен"
        else:
            # Отключаем промо тариф (возвращаем к trial или basic)
            cursor.execute("""
                UPDATE Businesses 
                SET subscription_tier = 'trial',
                    subscription_status = 'inactive',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (business_id,))
            message = "Промо тариф отключен"
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": message})
        
    except Exception as e:
        print(f"❌ Ошибка установки промо тарифа: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/network-locations', methods=['GET'])
def get_network_locations(business_id):
    """Получить все точки сети для бизнеса (если пользователь является владельцем сети)"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        
        # Получаем бизнес
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # ! FIX: Получаем только точки ТОЙ ЖЕ сети, к которой принадлежит бизнес
        network_id = business.get('network_id')
        print(f"🔍 API DEBUG: Business {business_id} ({business.get('name')}) -> Network {network_id}")
        
        if not network_id:
            print("🔍 API DEBUG: No network_id, returning []")
            db.close()
            return jsonify({"success": True, "is_network": False, "locations": []})
            
        locations = db.get_businesses_by_network(network_id)
        print(f"🔍 API DEBUG: Found {len(locations)} locations for network {network_id}")
        
        # Нормализация: алиас website = site для фронта, пустые строки вместо NULL
        def _norm_loc(loc):
            if not loc or not isinstance(loc, dict):
                return loc
            site_val = loc.get("site") or loc.get("website") or ""
            out = {k: (v if v is not None else "") for k, v in loc.items() if isinstance(k, str)}
            out["website"] = site_val
            out["site"] = loc.get("site") or loc.get("website") or ""
            return out

        normalized_locations = [_norm_loc(loc) for loc in locations]
        representative_id = None
        if normalized_locations:
            def _normalized_name(value):
                return " ".join(
                    re.sub(r"[^\w\s]+", " ", str(value or "").lower().replace("ё", "е")).split()
                )

            name_counts = {}
            for loc in normalized_locations:
                name_key = _normalized_name(loc.get("name"))
                if not name_key:
                    continue
                name_counts[name_key] = int(name_counts.get(name_key) or 0) + 1

            explicit_parent = next((loc for loc in normalized_locations if str(loc.get("id") or "") == str(network_id)), None)
            representative = explicit_parent
            if representative is None:
                unique_candidates = []
                for loc in normalized_locations:
                    normalized_name = _normalized_name(loc.get("name"))
                    if normalized_name and int(name_counts.get(normalized_name) or 0) == 1:
                        unique_candidates.append(loc)
                if unique_candidates:
                    unique_candidates.sort(
                        key=lambda loc: (
                            -len(_normalized_name(loc.get("name")).split()),
                            -len(str(loc.get("name") or "")),
                            str(loc.get("created_at") or ""),
                        )
                    )
                    representative = unique_candidates[0]
                else:
                    representative = sorted(
                        normalized_locations,
                        key=lambda loc: (
                            str(loc.get("created_at") or ""),
                            str(loc.get("name") or ""),
                        ),
                    )[0]
            representative_id = str(representative.get("id") or "") if representative else None
            for loc in normalized_locations:
                loc["is_network_parent"] = bool(representative_id) and str(loc.get("id") or "") == representative_id
        db.close()

        return jsonify({
            "success": True,
            "is_network": (business_id == network_id),
            "locations": normalized_locations,
            "parent_business_id": representative_id,
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения точек сети: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/optimization-wizard', methods=['POST', 'GET', 'OPTIONS'])
def business_optimization_wizard(business_id):
    """Сохранить или получить данные мастера оптимизации бизнеса"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        

        
        # Проверяем доступ к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        if request.method == 'POST':
            # Сохраняем данные мастера
            data = request.get_json(silent=True) or {}
            wizard_data = {
                'experience': data.get('experience', ''),
                'clients': data.get('clients', ''),
                'crm': data.get('crm', ''),
                'location': data.get('location', ''),
                'average_check': data.get('average_check', ''),
                'revenue': data.get('revenue', '')
            }
            
            # Проверяем, есть ли уже запись
            cursor.execute("SELECT id FROM businessoptimizationwizard WHERE business_id = %s", (business_id,))
            existing = cursor.fetchone()
            
            if existing:
                # Обновляем существующую запись
                cursor.execute("""
                    UPDATE BusinessOptimizationWizard 
                    SET data = ?, completed = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = ?
                """, (json.dumps(wizard_data, ensure_ascii=False), business_id))
            else:
                # Создаем новую запись
                wizard_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO BusinessOptimizationWizard (id, business_id, step, data, completed)
                    VALUES (?, ?, 3, ?, 1)
                """, (wizard_id, business_id, json.dumps(wizard_data, ensure_ascii=False)))
            
            db.conn.commit()
            db.close()
            
            return jsonify({
                "success": True,
                "message": "Данные мастера оптимизации сохранены"
            })
        
        else:  # GET
            # Получаем данные мастера
            cursor.execute("""
                SELECT data, completed FROM BusinessOptimizationWizard 
                WHERE business_id = ? 
                ORDER BY updated_at DESC 
                LIMIT 1
            """, (business_id,))
            row = cursor.fetchone()
            
            db.close()
            
            if row:
                wizard_data = json.loads(row[0]) if row[0] else {}
                return jsonify({
                    "success": True,
                    "data": wizard_data,
                    "completed": row[1] == 1
                })
            else:
                return jsonify({
                    "success": True,
                    "data": {},
                    "completed": False
                })
    
    except Exception as e:
        print(f"❌ Ошибка работы с мастером оптимизации: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/sprint', methods=['GET', 'POST', 'OPTIONS'])
def business_sprint(business_id):
    """Получить или сгенерировать спринт для бизнеса"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Создаем таблицу спринтов если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessSprints (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                week_start DATE NOT NULL,
                tasks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
            )
        """)
        
        # Проверяем доступ к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем текущую неделю (понедельник)
        today = datetime.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        
        if request.method == 'POST':
            # Генерируем новый спринт на основе данных мастера
            # Получаем данные мастера
            cursor.execute("""
                SELECT data FROM BusinessOptimizationWizard 
                WHERE business_id = ? AND completed = 1
                ORDER BY updated_at DESC 
                LIMIT 1
            """, (business_id,))
            wizard_row = cursor.fetchone()
            
            wizard_data = {}
            if wizard_row and wizard_row[0]:
                wizard_data = json.loads(wizard_row[0])
            
            # Генерируем задачи на основе данных мастера
            tasks = []
            
            # Базовая задача для всех
            tasks.append({
                'id': str(uuid.uuid4()),
                'title': 'Оптимизировать описание услуг на картах',
                'description': 'Обновить формулировки услуг для лучшего SEO',
                'expected_effect': '+5% к выручке',
                'deadline': 'Пт',
                'status': 'pending'
            })
            
            # Если есть данные о клиентах
            if wizard_data.get('clients'):
                tasks.append({
                    'id': str(uuid.uuid4()),
                    'title': 'Настроить систему напоминаний для постоянных клиентов',
                    'description': f'Использовать CRM ({wizard_data.get("crm", "любую")}) для автоматических напоминаний',
                    'expected_effect': '+10% к повторным визитам',
                    'deadline': 'Пт',
                    'status': 'pending'
                })
            
            # Если указан средний чек
            if wizard_data.get('average_check'):
                tasks.append({
                    'id': str(uuid.uuid4()),
                    'title': 'Проанализировать и оптимизировать ценообразование',
                    'description': f'Текущий средний чек: {wizard_data.get("average_check")}₽. Проверить конкурентов и оптимизировать',
                    'expected_effect': '+7% к среднему чеку',
                    'deadline': 'Пт',
                    'status': 'pending'
                })
            
            # Если указана выручка
            if wizard_data.get('revenue'):
                revenue = int(wizard_data.get('revenue', 0)) if str(wizard_data.get('revenue', '')).isdigit() else 0
                if revenue > 0:
                    target_increase = int(revenue * 0.1)  # 10% прирост
                    tasks.append({
                        'id': str(uuid.uuid4()),
                        'title': 'Увеличить выручку на 10%',
                        'description': f'Текущая выручка: {revenue}₽. Цель: +{target_increase}₽ за месяц',
                        'expected_effect': f'+{target_increase}₽ к выручке',
                        'deadline': 'Пт',
                        'status': 'pending'
                    })
            
            # Сохраняем спринт
            sprint_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT OR REPLACE INTO BusinessSprints (id, business_id, week_start, tasks, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (sprint_id, business_id, week_start.isoformat(), json.dumps(tasks, ensure_ascii=False)))
            
            db.conn.commit()
            db.close()
            
            return jsonify({
                "success": True,
                "sprint": {
                    "id": sprint_id,
                    "week_start": week_start.isoformat(),
                    "tasks": tasks
                }
            })
        
        else:  # GET
            # Получаем спринт на текущую неделю
            cursor.execute("""
                SELECT id, tasks, updated_at FROM BusinessSprints 
                WHERE business_id = ? AND week_start = ?
                ORDER BY updated_at DESC 
                LIMIT 1
            """, (business_id, week_start.isoformat()))
            row = cursor.fetchone()
            
            db.close()
            
            if row:
                tasks = json.loads(row[1]) if row[1] else []
                return jsonify({
                    "success": True,
                    "sprint": {
                        "id": row[0],
                        "week_start": week_start.isoformat(),
                        "tasks": tasks
                    }
                })
            else:
                return jsonify({
                    "success": True,
                    "sprint": None
                })
    
    except Exception as e:
        print(f"❌ Ошибка работы со спринтом: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/data', methods=['GET'])
def get_business_data(business_id):
    """Получить полные данные конкретного бизнеса"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Создаем таблицу FinancialTransactions если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FinancialTransactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                business_id TEXT,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                category TEXT,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        
        # Создаем таблицу BusinessProfiles если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessProfiles (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        
        # Добавляем поле business_id в UserServices если его нет
        try:
            cursor.execute("ALTER TABLE UserServices ADD COLUMN business_id TEXT")
            cursor.execute("""
                UPDATE UserServices 
                SET business_id = (
                    SELECT b.id FROM Businesses b 
                    WHERE b.owner_id = UserServices.user_id 
                    LIMIT 1
                )
                WHERE business_id IS NULL
            """)
        except Exception:
            # Поле уже существует или другая ошибка
            pass
        
        db.conn.commit()
        
        # Проверяем доступ к бизнесу
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Проверяем права доступа
        if not db.is_superadmin(user_data['user_id']) and business['owner_id'] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        # Получаем услуги бизнеса
        services = db.get_services_by_business(business_id)
        
        # Получаем финансовые данные бизнеса
        financial_data = db.get_financial_data_by_business(business_id)
        
        # Получаем отчеты бизнеса
        reports = db.get_reports_by_business(business_id)
        
        # Получаем профиль бизнеса
        cursor.execute("""
            SELECT contact_name, contact_phone, contact_email
            FROM BusinessProfiles 
            WHERE business_id = ?
        """, (business_id,))
        profile_row = cursor.fetchone()
        business_profile = {
            "contact_name": profile_row[0] if profile_row else "",
            "contact_phone": profile_row[1] if profile_row else "",
            "contact_email": profile_row[2] if profile_row else ""
        } if profile_row else {
            "contact_name": "",
            "contact_phone": "",
            "contact_email": ""
        }
        
        db.close()
        
        return jsonify({
            "success": True,
            "business": business,
            "business_profile": business_profile,
            "services": services,
            "financial_data": financial_data,
            "reports": reports
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения данных бизнеса: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/business/<business_id>/yandex-link', methods=['POST', 'OPTIONS'])
def update_business_yandex_link(business_id):
    """Обновление ссылки/ID Яндекс.Карт для бизнеса и запуск синхронизации (по возможности)."""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        yandex_url = (data.get('yandex_url') or '').strip()

        if not yandex_url:
            return jsonify({"error": "Не указана ссылка на Яндекс.Карты"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем права доступа к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Обновляем ссылку и, при возможности, yandex_org_id
        from yandex_adapter import YandexAdapter

        adapter = YandexAdapter()
        org_id = adapter.parse_org_id_from_url(yandex_url)

        cursor.execute(
            """
            UPDATE Businesses
            SET yandex_url = ?, yandex_org_id = ?
            WHERE id = ?
            """,
            (yandex_url, org_id, business_id),
        )

        db.conn.commit()
        db.close()

        # Пытаемся запустить синхронизацию (если есть org_id и настроен адаптер)
        synced = False
        try:
            if org_id and YandexSyncService is not None:
                sync_service = YandexSyncService()
                synced = sync_service.sync_business(business_id)
        except Exception as sync_err:
            print(f"⚠️ Ошибка при синхронизации Яндекс после обновления ссылки: {sync_err}")

        return jsonify(
            {
                "success": True,
                "synced": bool(synced),
                "message": "Ссылка Яндекс.Карт обновлена",
            }
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка обновления ссылки Яндекс.Карт: {str(e)}"}), 500

@app.route('/api/business/<business_id>/profile', methods=['POST', 'OPTIONS'])
def update_business_profile(business_id):
    """Обновить профиль бизнеса"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Создаем таблицу BusinessProfiles если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessProfiles (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        
        # Обновляем или создаем профиль бизнеса
        profile_id = f"profile_{business_id}"
        cursor.execute("""
            INSERT OR REPLACE INTO BusinessProfiles 
            (id, business_id, contact_name, contact_phone, contact_email, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            profile_id,
            business_id,
            data.get('contact_name', ''),
            data.get('contact_phone', ''),
            data.get('contact_email', '')
        ))
        
        db.conn.commit()
        db.close()
        
        return jsonify({"success": True, "message": "Профиль бизнеса обновлен"})
        
    except Exception as e:
        print(f"❌ Ошибка обновления профиля бизнеса: {e}")
        return jsonify({"error": str(e)}), 500


def send_email(to_email, subject, body, from_name="LocalOS"):
    """Универсальная функция для отправки email"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Настройки SMTP из .env
        smtp_server = os.getenv("SMTP_SERVER", "mail.hosting.reg.ru")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "info@localos.pro")
        smtp_password = os.getenv("SMTP_PASSWORD")
        
        if not smtp_password:
            print("❌ SMTP_PASSWORD не установлен в переменных окружения")
            return False
        
        # Создание сообщения
        msg = MIMEMultipart()
        msg['From'] = f"{from_name} <{smtp_username}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Отправка
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email отправлен на {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return False

def send_contact_email(name, email, phone, message):
    """Отправка email с сообщением обратной связи"""
    contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")
    
    subject = f"Новое сообщение с сайта LocalOS от {name}"
    body = f"""
Новое сообщение с сайта LocalOS

Имя: {name}
Email: {email}
Телефон: {phone if phone else 'Не указан'}

Сообщение:
{message}

---
Отправлено с сайта localos.pro
    """
    
    return send_email(contact_email, subject, body)

@app.route('/api/auth/reset-password', methods=['POST'])
@rate_limit_if_available("5 per hour")
def reset_password():
    """Запрос на восстановление пароля"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({"error": "Email обязателен"}), 400
        
        # Проверяем, существует ли пользователь
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "Пользователь с таким email не найден"}), 404
        
        # Генерируем токен восстановления
        import secrets
        from datetime import datetime, timedelta
        
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)
        
        # Сохраняем токен в базе
        cursor.execute("""
            UPDATE Users 
            SET reset_token = ?, reset_token_expires = ? 
            WHERE email = ?
        """, (reset_token, expires_at.isoformat(), email))
        conn.commit()
        conn.close()
        
        # Отправляем email с токеном
        print(f"🔑 Токен восстановления для {email}: {reset_token}")
        print(f"⏰ Действителен до: {expires_at}")
        
        # Отправляем реальное письмо
        subject = "Восстановление пароля LocalOS"
        body = f"""
Восстановление пароля для LocalOS

Ваш токен восстановления: {reset_token}
Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}

Для сброса пароля перейдите по ссылке:
https://localos.pro/reset-password?token={reset_token}&email={email}

Если вы не запрашивали восстановление пароля, проигнорируйте это письмо.

---
LocalOS
        """
        
        email_sent = send_email(email, subject, body)
        
        if email_sent:
            print(f"✅ Email отправлен на {email}")
        else:
            print(f"❌ Не удалось отправить email на {email}")
        
        return jsonify({
            "success": True, 
            "message": "Инструкции по восстановлению пароля отправлены на email"
        })
        
    except Exception as e:
        print(f"❌ Ошибка восстановления пароля: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/confirm-reset', methods=['POST'])
@rate_limit_if_available("5 per hour")
def confirm_reset():
    """Подтверждение сброса пароля с новым паролем"""
    try:
        data = request.get_json()
        email = data.get('email')
        token = data.get('token')
        new_password = data.get('password')
        
        if not all([email, token, new_password]):
            return jsonify({"error": "Все поля обязательны"}), 400
        
        # Проверяем токен
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, reset_token, reset_token_expires 
            FROM Users 
            WHERE email = ? AND reset_token = ?
        """, (email, token))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({"error": "Неверный токен"}), 400
        
        # Проверяем срок действия токена
        from datetime import datetime
        if datetime.now() > datetime.fromisoformat(user[2]):
            return jsonify({"error": "Токен истек"}), 400
        
        # Устанавливаем новый пароль
        from auth_system import set_password
        result = set_password(user[0], new_password)
        
        if 'error' in result:
            return jsonify(result), 400
        
        # Очищаем токен
        cursor.execute("""
            UPDATE Users 
            SET reset_token = NULL, reset_token_expires = NULL 
            WHERE id = ?
        """, (user[0],))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Пароль успешно изменен"})
        
    except Exception as e:
        print(f"❌ Ошибка подтверждения сброса: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/request-report', methods=['POST', 'OPTIONS'])
def public_request_report():
    """Публичная заявка на отчёт без авторизации.
    Создаёт публичную страницу аудита, запускает фоновый парсинг карты и возвращает ссылку на отчёт.
    """
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        email = data.get('email', '').strip()
        url = data.get('url', '').strip()
        
        if not email or not url:
            return jsonify({"error": "Email и URL обязательны"}), 400

        source = _detect_public_map_source(url)
        normalized_slug = _slugify_public_report_name(
            re.sub(r"https?://", "", url).split("/", 1)[-1].replace("/", "-")
        )
        pending_page = _build_public_pending_page(email=email, map_url=url)

        conn = get_db_connection()
        try:
            _ensure_public_report_requests_table(conn)
            cur = conn.cursor()
            suffix = 0
            slug = normalized_slug
            while True:
                cur.execute("SELECT slug FROM publicreportrequests WHERE slug = %s LIMIT 1", (slug,))
                existing = cur.fetchone()
                if not existing:
                    break
                suffix += 1
                slug = f"{normalized_slug}-{suffix}"

            cur.execute(
                """
                INSERT INTO publicreportrequests (slug, email, source_url, source, status, page_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                """,
                (slug, email, url, source, "queued", json.dumps(pending_page, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

        # Асинхронный запуск: сразу возвращаем ссылку на страницу, а данные подтянутся после парсинга.
        thread = threading.Thread(target=_run_public_report_pipeline, args=(slug,), daemon=True)
        thread.start()

        frontend_base = str(os.getenv("FRONTEND_BASE_URL") or "").strip().rstrip("/")
        public_url = f"{frontend_base}/{slug}" if frontend_base else f"/{slug}"
        
        # Отправляем email на info@localos.pro о новой заявке
        contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")
        subject = f"Новая заявка с сайта LocalOS от {email}"
        body = f"""
Новая заявка с сайта LocalOS

Email клиента: {email}
Ссылка на бизнес: {url}
Публичная страница отчёта: {public_url}

---
Отправлено с сайта localos.pro
        """
        
        email_sent = send_email(contact_email, subject, body)
        if not email_sent:
            print("⚠️ Не удалось отправить email")
        
        # Логирование в консоль
        print(f"📧 НОВАЯ ЗАЯВКА ОТ {email}:")
        print(f"🔗 URL: {url}")
        print(f"📄 Публичная страница: {public_url}")
        print("-" * 50)
        
        return jsonify({
            "success": True,
            "message": "Заявка принята. Формируем отчёт.",
            "slug": slug,
            "public_url": public_url,
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка обработки заявки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/request-registration', methods=['POST', 'OPTIONS'])
def public_request_registration():
    """Публичная заявка на регистрацию без авторизации.
    Принимает данные регистрации, отправляет email на info@localos.pro о новой заявке.
    """
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        yandex_url = data.get('yandex_url', '').strip()
        
        if not email:
            return jsonify({"error": "Email обязателен"}), 400
        
        # Отправляем email на info@localos.pro о новой заявке на регистрацию
        contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")
        subject = f"Новая заявка на регистрацию от {email}"
        body = f"""
Новая заявка на регистрацию с сайта LocalOS

Имя: {name or 'Не указано'}
Email: {email}
Телефон: {phone or 'Не указан'}
Ссылка на Яндекс.Карты: {yandex_url or 'Не указана'}

---
Отправлено с сайта localos.pro
        """
        
        email_sent = send_email(contact_email, subject, body)
        if not email_sent:
            print("⚠️ Не удалось отправить email")
        
        # Логирование в консоль
        print(f"📧 НОВАЯ ЗАЯВКА НА РЕГИСТРАЦИЮ ОТ {email}:")
        print(f"👤 Имя: {name or 'Не указано'}")
        print(f"📞 Телефон: {phone or 'Не указан'}")
        print(f"🔗 Яндекс.Карты: {yandex_url or 'Не указана'}")
        print("-" * 50)
        
        return jsonify({
            "success": True,
            "message": "Заявка на регистрацию принята. Мы свяжемся с вами в ближайшее время."
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка обработки заявки на регистрацию: {e}")
        return jsonify({"error": str(e)}), 500

# ===== TELEGRAM BOT API =====

@app.route('/api/telegram/bind', methods=['POST'])
def generate_telegram_bind_token():
    """Генерация токена для привязки Telegram аккаунта для конкретного бизнеса"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Получаем business_id из запроса
        data = request.get_json(silent=True) or {}
        business_id = data.get('business_id')
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        # Проверяем, что бизнес принадлежит пользователю
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM businesses WHERE id = %s AND owner_id = %s", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403
        
        # Генерируем токен привязки
        import secrets
        from datetime import datetime, timedelta
        
        bind_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=5)  # Токен действует 5 минут
        
        # Удаляем старые неиспользованные токены для этого бизнеса
        cursor.execute(
            """
            DELETE FROM telegrambindtokens
            WHERE business_id = %s
              AND used = 0
              AND expires_at < %s
            """,
            (business_id, datetime.now()),
        )

        # Создаем новый токен
        token_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO telegrambindtokens (id, user_id, business_id, token, expires_at, used, created_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s)
            """,
            (token_id, user_data['user_id'], business_id, bind_token, expires_at, datetime.now()),
        )
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "token": bind_token,
            "expires_at": expires_at.isoformat(),
            "qr_data": f"https://t.me/LocalOspro_bot?start={bind_token}"
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка генерации токена привязки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telegram/bind/status', methods=['GET'])
def get_telegram_bind_status():
    """Проверка статуса привязки Telegram аккаунта для конкретного бизнеса"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')
        
        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, что бизнес принадлежит пользователю
        cursor.execute("SELECT id FROM businesses WHERE id = %s AND owner_id = %s", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403
        
        # Проверяем, привязан ли Telegram для этого бизнеса
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM telegrambindtokens
            WHERE business_id = %s
              AND used = 1
              AND user_id = %s
            """,
            (business_id, user_data['user_id']),
        )
        result = cursor.fetchone()
        count_value = 0
        if result:
            if hasattr(result, "get"):
                count_value = int(result.get("count") or 0)
            else:
                count_value = int(result[0] or 0)
        has_used_token_for_this_business = count_value > 0

        cursor.execute("SELECT telegram_id FROM users WHERE id = %s", (user_data['user_id'],))
        user_row = cursor.fetchone()
        if user_row and hasattr(user_row, "get"):
            telegram_id = user_row.get("telegram_id")
        else:
            telegram_id = user_row[0] if user_row else None
        telegram_id = str(telegram_id or "").strip()
        is_linked = bool(has_used_token_for_this_business and telegram_id and telegram_id.lower() != "none")
        
        db.close()
        
        return jsonify({
            "success": True,
            "is_linked": is_linked,
            "telegram_id": telegram_id if is_linked else None
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка проверки статуса привязки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telegram/bind/verify', methods=['POST'])
def verify_telegram_bind_token():
    """Проверка токена привязки (вызывается из бота)"""
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        bind_token = data.get('token', '').strip()
        telegram_id = data.get('telegram_id', '').strip()
        
        if not bind_token or not telegram_id:
            return jsonify({"error": "Токен и telegram_id обязательны"}), 400
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute(
            """
            SELECT id, user_id, business_id, expires_at, used
            FROM telegrambindtokens
            WHERE token = %s
            """,
            (bind_token,),
        )
        token_row = cursor.fetchone()
        if token_row:
            token_id, user_id, business_id_from_token, expires_at, used = token_row
        
        if not token_row:
            db.close()
            return jsonify({"error": "Токен не найден"}), 404
        
        # Проверяем срок действия
        from datetime import datetime
        expires_dt = expires_at
        if isinstance(expires_at, str):
            expires_dt = datetime.fromisoformat(expires_at)
        if expires_dt < datetime.now(expires_dt.tzinfo) if getattr(expires_dt, "tzinfo", None) else datetime.now():
            db.close()
            return jsonify({"error": "Токен истек"}), 400
        
        # Проверяем, не использован ли уже
        if used:
            db.close()
            return jsonify({"error": "Токен уже использован"}), 400
        
        # Проверяем, не привязан ли уже этот Telegram к другому аккаунту
        cursor.execute("SELECT id FROM users WHERE telegram_id = %s AND id != %s", (telegram_id, user_id))
        existing_user = cursor.fetchone()
        if existing_user:
            db.close()
            return jsonify({"error": "Этот Telegram уже привязан к другому аккаунту"}), 400
        
        # Привязываем Telegram к аккаунту
        cursor.execute("""
            UPDATE users
            SET telegram_id = %s, updated_at = %s
            WHERE id = %s
        """, (telegram_id, datetime.now(), user_id))
        
        # Помечаем токен как использованный
        cursor.execute(
            """
            UPDATE telegrambindtokens
            SET used = 1,
                business_id = COALESCE(%s, business_id)
            WHERE id = %s
            """,
            (business_id_from_token, token_id),
        )
        
        db.conn.commit()
        
        # Получаем информацию о пользователе
        cursor.execute("SELECT email, name FROM users WHERE id = %s", (user_id,))
        user_info = cursor.fetchone()
        
        db.close()
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "email": user_info[0] if user_info else None,
                "name": user_info[1] if user_info else None
            }
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка проверки токена привязки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/contact', methods=['POST', 'OPTIONS'])
def public_contact():
    """Обработка формы обратной связи"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()
        
        if not name or not email or not message:
            return jsonify({"error": "Имя, email и сообщение обязательны"}), 400
        
        # Логирование в консоль
        print(f"📧 НОВОЕ СООБЩЕНИЕ ОТ {name} ({email}):")
        print(f"📞 Телефон: {phone}")
        print(f"💬 Сообщение: {message}")
        print("-" * 50)
        
        # Отправка email
        email_sent = send_contact_email(name, email, phone, message)
        if not email_sent:
            print("⚠️ Не удалось отправить email с формы обратной связи")
            return jsonify({"error": "Не удалось отправить сообщение. Попробуйте позже."}), 503
        
        return jsonify({"success": True, "message": "Сообщение отправлено"})
        
    except Exception as e:
        print(f"❌ Ошибка обработки формы обратной связи: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/download-report/<card_id>', methods=['GET'])
def download_report(card_id):
    """
    Скачивание HTML отчёта по ID карточки
    """
    try:
        from safe_db_utils import get_db_connection
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        report_path = card_data['report_path']
        
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Формируем имя файла для скачивания (только латинские символы)
        title = card_data['title'] if card_data['title'] else 'report'
        # Транслитерация русских символов
        translit_map = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z',
            'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
            'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'YO', 'Ж': 'ZH', 'З': 'Z',
            'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R',
            'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'H', 'Ц': 'TS', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'YU', 'Я': 'YA'
        }
        
        safe_title = ""
        for char in title:
            if char in translit_map:
                safe_title += translit_map[char]
            elif char.isalnum() or char in (' ', '-', '_'):
                safe_title += char
            else:
                safe_title += '_'
        
        safe_title = safe_title.strip().replace(' ', '_')
        filename = f"seo_report_{safe_title}_{card_id}.html"
        
        # Читаем содержимое файла
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаём ответ с правильными заголовками для скачивания
        from flask import Response
        response = Response(content, mimetype='text/html; charset=utf-8')
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/view-report/<card_id>', methods=['GET'])
def view_report(card_id):
    """
    Просмотр HTML отчёта в браузере
    """
    try:
        from safe_db_utils import get_db_connection
        from flask import Response
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        report_path = card_data['report_path']
        
        if not report_path:
            return jsonify({"error": "Отчёт ещё не сгенерирован"}), 404
        
        if not os.path.exists(report_path):
            return jsonify({"error": "Файл отчёта не найден"}), 404
        
        # Читаем содержимое файла
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаём ответ для просмотра в браузере
        response = Response(content, mimetype='text/html; charset=utf-8')
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        # Разрешаем отображение в iframe для просмотра
        response.headers['X-Frame-Options'] = 'ALLOWALL'
        
        return response
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/reports/<card_id>/status', methods=['GET'])
def report_status(card_id):
    """
    Проверка статуса отчёта
    """
    try:
        from safe_db_utils import get_db_connection
        # Нормализуем ID
        normalized_id = card_id.replace('_', '-')
        
        # Получаем данные карточки из SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (normalized_id,))
        card_data = cursor.fetchone()
        conn.close()
        
        if not card_data:
            return jsonify({"error": "Отчёт не найден"}), 404
        
        return jsonify({
            "success": True,
            "card_id": card_id,
            "title": card_data['title'],
            "seo_score": card_data['seo_score'],
            "has_report": bool(card_data['report_path']),
            "has_ai_analysis": bool(card_data['ai_analysis']),
            "report_path": card_data['report_path']
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


_RU_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ы": "y", "э": "e", "ю": "yu", "я": "ya",
}


def _slugify_public_report_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    converted: list[str] = []
    for ch in raw:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            converted.append(ch)
            continue
        if "а" <= ch <= "я" or ch == "ё":
            converted.append(_RU_LAT.get(ch, ""))
            continue
        if ch in {" ", "-", "_", ".", ",", "/", "|", ":"}:
            converted.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(converted)).strip("-")
    return slug or f"report-{uuid.uuid4().hex[:8]}"


def _detect_public_map_source(url: str) -> str:
    value = str(url or "").lower()
    if "2gis." in value:
        return "apify_2gis"
    if "google.com/maps/" in value or "maps.app.goo.gl/" in value:
        return "apify_google"
    if "maps.apple.com/" in value:
        return "apify_apple"
    return "apify_yandex"


def _normalize_public_media_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        text = f"https:{text}"
    if "{size}" in text:
        text = text.replace("{size}", "XXXL")
    if "/%s" in text:
        text = text.replace("/%s", "/XXXL")
    elif "%s" in text:
        text = text.replace("%s", "XXXL")
    return text


def _to_json_compatible(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            normalized[str(key)] = _to_json_compatible(inner)
        return normalized
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(item) for item in value]
    return value


def _build_public_pending_page(*, email: str, map_url: str) -> dict[str, Any]:
    return {
        "processing": True,
        "processing_message": "Здесь появится ваш отчёт, как только он будет готов.",
        "name": "Ваш отчёт готовится",
        "category": "Аудит карточки на картах",
        "source_url": map_url,
        "audit": {
            "summary_score": 0,
            "health_level": "processing",
            "health_label": "Готовим отчёт",
            "summary_text": "Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.",
            "findings": [],
            "recommended_actions": [
                {
                    "title": "Собираем фактические данные карточки",
                    "description": "Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.",
                },
                {
                    "title": "Формируем персональный аудит",
                    "description": "После парсинга покажем конкретные шаги роста именно для вашей карточки.",
                },
            ],
            "services_preview": [],
            "reviews_preview": [],
            "news_preview": [],
            "subscores": {},
            "current_state": {
                "rating": None,
                "reviews_count": 0,
                "unanswered_reviews_count": 0,
                "services_count": 0,
                "services_with_price_count": 0,
                "has_website": False,
                "has_recent_activity": False,
                "photos_state": "unknown",
            },
            "revenue_potential": {},
            "cadence": {
                "news_posts_per_month_min": 4,
                "photos_per_month_min": 8,
                "reviews_response_hours_max": 48,
            },
        },
        "cta": {
            "email": email,
            "telegram_url": None,
            "whatsapp_url": None,
            "website": None,
        },
        "updated_at": datetime.utcnow().isoformat(),
    }


def _ensure_public_report_requests_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS publicreportrequests (
            slug TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'apify_yandex',
            status TEXT NOT NULL DEFAULT 'queued',
            page_json JSONB NOT NULL,
            result_json JSONB,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.commit()


def _run_public_report_pipeline(slug: str) -> None:
    conn = None
    try:
        conn = get_db_connection()
        _ensure_public_report_requests_table(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT slug, email, source_url, source
            FROM publicreportrequests
            WHERE slug = %s
            LIMIT 1
            """,
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            return
        payload = dict(row) if hasattr(row, "keys") else {
            "slug": row[0],
            "email": row[1],
            "source_url": row[2],
            "source": row[3],
        }
        source_url = str(payload.get("source_url") or "").strip()
        source = str(payload.get("source") or "apify_yandex").strip().lower()
        email = str(payload.get("email") or "").strip()

        cur.execute(
            "UPDATE publicreportrequests SET status = %s, updated_at = NOW() WHERE slug = %s",
            ("processing", slug),
        )
        conn.commit()

        service = ProspectingService(source=source)
        run_result = service.run_business_by_map_url(source_url, limit=1, timeout_sec=320)
        items = run_result.get("items") if isinstance(run_result, dict) else []
        first_item = items[0] if isinstance(items, list) and items else {}
        if not isinstance(first_item, dict) or not first_item:
            raise RuntimeError("Парсер не вернул данные по карточке")

        lead_like = {
            "id": f"public-{slug}",
            "name": first_item.get("name"),
            "category": first_item.get("category"),
            "city": first_item.get("city"),
            "address": first_item.get("address"),
            "website": first_item.get("website"),
            "phone": first_item.get("phone"),
            "email": first_item.get("email") or email,
            "rating": first_item.get("rating"),
            "reviews_count": first_item.get("reviews_count"),
            "source_url": first_item.get("source_url") or source_url,
            "telegram_url": first_item.get("telegram_url"),
            "whatsapp_url": first_item.get("whatsapp_url"),
            "search_payload_json": first_item.get("search_payload_json"),
            "reviews_json": first_item.get("reviews_json"),
            "services_json": first_item.get("services_json"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        snapshot = _to_json_compatible(build_lead_card_preview_snapshot(lead_like))
        preview_meta = snapshot.get("preview_meta") if isinstance(snapshot.get("preview_meta"), dict) else {}
        logo_url = _normalize_public_media_url(preview_meta.get("logo_url") if isinstance(preview_meta, dict) else "")
        photo_urls = []
        photo_values = preview_meta.get("photo_urls") if isinstance(preview_meta, dict) else []
        if isinstance(photo_values, list):
            for item in photo_values:
                media_url = _normalize_public_media_url(item)
                if media_url:
                    photo_urls.append(media_url)

        page_json = {
            "processing": False,
            "name": lead_like.get("name") or "Компания",
            "category": lead_like.get("category"),
            "city": lead_like.get("city"),
            "address": lead_like.get("address"),
            "source_url": lead_like.get("source_url"),
            "logo_url": logo_url or None,
            "photo_urls": photo_urls[:8],
            "audit": {
                "summary_score": snapshot.get("summary_score"),
                "health_level": snapshot.get("health_level"),
                "health_label": snapshot.get("health_label"),
                "summary_text": snapshot.get("summary_text"),
                "findings": snapshot.get("findings") if isinstance(snapshot.get("findings"), list) else [],
                "recommended_actions": snapshot.get("recommended_actions") if isinstance(snapshot.get("recommended_actions"), list) else [],
                "services_preview": snapshot.get("services_preview") if isinstance(snapshot.get("services_preview"), list) else [],
                "subscores": snapshot.get("subscores") if isinstance(snapshot.get("subscores"), dict) else {},
                "current_state": snapshot.get("current_state") if isinstance(snapshot.get("current_state"), dict) else {},
                "parse_context": snapshot.get("parse_context") if isinstance(snapshot.get("parse_context"), dict) else {},
                "revenue_potential": snapshot.get("revenue_potential") if isinstance(snapshot.get("revenue_potential"), dict) else {},
                "reviews_preview": snapshot.get("reviews_preview") if isinstance(snapshot.get("reviews_preview"), list) else [],
                "news_preview": snapshot.get("news_preview") if isinstance(snapshot.get("news_preview"), list) else [],
                "cadence": {
                    "news_posts_per_month_min": 4,
                    "photos_per_month_min": 8,
                    "reviews_response_hours_max": 48,
                },
            },
            "cta": {
                "email": lead_like.get("email") or email,
                "telegram_url": lead_like.get("telegram_url"),
                "whatsapp_url": lead_like.get("whatsapp_url"),
                "website": lead_like.get("website"),
            },
            "updated_at": datetime.utcnow().isoformat(),
        }

        cur.execute(
            """
            UPDATE publicreportrequests
            SET status = %s,
                page_json = %s::jsonb,
                result_json = %s::jsonb,
                error_text = NULL,
                updated_at = NOW()
            WHERE slug = %s
            """,
            (
                "completed",
                json.dumps(page_json, ensure_ascii=False),
                json.dumps(_to_json_compatible(run_result), ensure_ascii=False),
                slug,
            ),
        )
        conn.commit()
    except Exception as e:
        try:
            if conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE publicreportrequests
                    SET status = %s,
                        error_text = %s,
                        updated_at = NOW()
                    WHERE slug = %s
                    """,
                    ("error", str(e), slug),
                )
                conn.commit()
        except Exception:
            pass
        print(f"Error running public report pipeline for slug={slug}: {e}")
    finally:
        if conn:
            conn.close()


@app.route('/api/public/report-offer/<slug>', methods=['GET'])
def get_public_report_offer(slug):
    try:
        normalized_slug = _slugify_public_report_name(slug)
        conn = get_db_connection()
        try:
            _ensure_public_report_requests_table(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT slug, status, page_json, error_text, updated_at
                FROM publicreportrequests
                WHERE slug = %s
                LIMIT 1
                """,
                (normalized_slug,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            payload = dict(row) if hasattr(row, "keys") else {
                "slug": row[0],
                "status": row[1],
                "page_json": row[2],
                "error_text": row[3],
                "updated_at": row[4],
            }
            page_json = payload.get("page_json")
            if isinstance(page_json, str):
                try:
                    page_json = json.loads(page_json)
                except Exception:
                    page_json = {}
            if not isinstance(page_json, dict):
                page_json = {}
            page_json["updated_at"] = str(payload.get("updated_at") or page_json.get("updated_at") or "")
            if str(payload.get("status") or "") == "error":
                page_json["processing"] = True
                page_json["processing_message"] = "Отчёт готовится дольше обычного. Мы продолжаем обработку данных."
            return jsonify({"success": True, "status": payload.get("status"), "page": page_json})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Глобальный обработчик исключений"""
    if isinstance(e, HTTPException):
        if request.path.startswith('/api/'):
            return jsonify({"error": e.description}), e.code
        return e

    import traceback
    print(f"🚨 ГЛОБАЛЬНАЯ ОШИБКА: {str(e)}")
    print(f"🚨 ТРАССИРОВКА: {traceback.format_exc()}")
    return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500


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


if __name__ == "__main__":
    # Runtime строго Postgres-only: подключаемся только через pg_db_utils.
    from pg_db_utils import log_connection_info

    log_connection_info(prefix="BACKEND")

    print("SEO анализатор запущен на порту 8000")
    app.run(host="0.0.0.0", port=8000, debug=False, request_handler=QuietWSGIRequestHandler)
