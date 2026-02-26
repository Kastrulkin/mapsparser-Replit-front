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
import secrets
from datetime import datetime, timedelta

# Устанавливаем переменную окружения для отключения SSL проверки GigaChat
os.environ.setdefault('GIGACHAT_SSL_VERIFY', 'false')
from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
from flask_cors import CORS

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
from api.services_api import services_bp
from api.growth_api import growth_bp
from api.admin_growth_api import admin_growth_bp
from api.progress_api import progress_bp
from api.stage_progress_api import stage_progress_bp
from api.metrics_history_api import metrics_history_bp
from api.networks_api import networks_bp
from api.network_health_api import network_health_bp
from api.admin_prospecting import admin_prospecting_bp
from core.default_ai_prompts import get_default_ai_prompts
from core.default_business_types import get_default_business_types
from core.seo_keywords import collect_ranked_keywords
from core.action_orchestrator import ActionOrchestrator
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
        cur.execute("SELECT id FROM Cards WHERE url = %s LIMIT 1", (url,))
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
        INSERT INTO Cards (
            id, url, title, address, phone, site, rating, reviews_count,
            categories, overview, products, news, photos, features_full,
            competitors, hours, hours_full, report_path, user_id, seo_score,
            ai_analysis, recommendations
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            url = EXCLUDED.url,
            title = EXCLUDED.title,
            address = EXCLUDED.address,
            phone = EXCLUDED.phone,
            site = EXCLUDED.site,
            rating = EXCLUDED.rating,
            reviews_count = EXCLUDED.reviews_count,
            categories = EXCLUDED.categories,
            overview = EXCLUDED.overview,
            products = EXCLUDED.products,
            news = EXCLUDED.news,
            photos = EXCLUDED.photos,
            features_full = EXCLUDED.features_full,
            competitors = EXCLUDED.competitors,
            hours = EXCLUDED.hours,
            hours_full = EXCLUDED.hours_full,
            report_path = EXCLUDED.report_path,
            user_id = EXCLUDED.user_id,
            seo_score = EXCLUDED.seo_score,
            ai_analysis = EXCLUDED.ai_analysis,
            recommendations = EXCLUDED.recommendations
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


@app.route('/')
def index():
    """Главная страница - раздаём собранный SPA"""
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
        
        def _cell(row, key: str, idx: int, default=0):
            if row is None:
                return default
            if isinstance(row, dict):
                return row.get(key, default)
            try:
                return row[idx]
            except Exception:
                return default

        # Проверяем, существует ли таблица tokenusage (Postgres)
        cursor.execute("SELECT to_regclass('public.tokenusage') AS reg")
        reg_row = cursor.fetchone()
        if not _cell(reg_row, "reg", 0, None):
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
                "user_id": _cell(row, "id", 0),
                "email": _cell(row, "email", 1),
                "name": _cell(row, "name", 2),
                "total_tokens": _cell(row, "total_tokens", 3, 0) or 0,
                "prompt_tokens": _cell(row, "prompt_tokens", 4, 0) or 0,
                "completion_tokens": _cell(row, "completion_tokens", 5, 0) or 0,
                "requests_count": _cell(row, "requests_count", 6, 0) or 0
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
                "business_id": _cell(row, "id", 0),
                "business_name": _cell(row, "name", 1),
                "owner_id": _cell(row, "owner_id", 2),
                "owner_email": _cell(row, "owner_email", 3),
                "total_tokens": _cell(row, "total_tokens", 4, 0) or 0,
                "prompt_tokens": _cell(row, "prompt_tokens", 5, 0) or 0,
                "completion_tokens": _cell(row, "completion_tokens", 6, 0) or 0,
                "requests_count": _cell(row, "requests_count", 7, 0) or 0
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
                "task_type": _cell(row, "task_type", 0, "unknown") or "unknown",
                "total_tokens": _cell(row, "total_tokens", 1, 0) or 0,
                "prompt_tokens": _cell(row, "prompt_tokens", 2, 0) or 0,
                "completion_tokens": _cell(row, "completion_tokens", 3, 0) or 0,
                "requests_count": _cell(row, "requests_count", 4, 0) or 0
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "total": {
                "total_tokens": _cell(total_stats, "total", 0, 0) or 0,
                "prompt_tokens": _cell(total_stats, "prompt_total", 1, 0) or 0,
                "completion_tokens": _cell(total_stats, "completion_total", 2, 0) or 0,
                "requests_count": _cell(total_stats, "requests_count", 3, 0) or 0
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


@app.route('/api/token-usage', methods=['GET'])
def get_user_token_usage():
    """Пользовательская статистика токенов по бизнесу с разбивкой по категориям и периодам."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        business_id = request.args.get('business_id')
        months_raw = request.args.get('months', '1')
        try:
            months = int(months_raw)
        except Exception:
            months = 1
        if months < 1:
            months = 1
        if months > 24:
            months = 24

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем наличие таблицы
        cursor.execute("SELECT to_regclass('public.tokenusage') AS reg")
        reg_row = cursor.fetchone()
        reg_val = (reg_row.get('reg') if isinstance(reg_row, dict) else reg_row[0]) if reg_row else None
        if not reg_val:
            db.close()
            return jsonify({
                "success": True,
                "period_months": months,
                "month_total": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests_count": 0},
                "period_total": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests_count": 0},
                "by_category": [],
                "timeline": []
            })

        scope_col = "user_id"
        scope_value = user_id
        scope_sql = f"{scope_col} = %s"
        scope_params = [scope_value]

        if business_id:
            cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
            b_row = cursor.fetchone()
            if not b_row:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            owner_id = b_row.get('owner_id') if isinstance(b_row, dict) else b_row[0]
            if owner_id != user_id and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа"}), 403
            # Часть старых записей TokenUsage может не иметь business_id.
            # Для выбранного бизнеса учитываем:
            # 1) прямые записи по business_id
            # 2) записи владельца без business_id (legacy)
            scope_sql = "(business_id = %s OR (business_id IS NULL AND user_id = %s))"
            scope_params = [business_id, owner_id]

        # Общая сумма за текущий календарный месяц
        cursor.execute(
            f"""
            SELECT
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COUNT(*) AS requests_count
            FROM tokenusage
            WHERE {scope_sql}
              AND created_at >= date_trunc('month', NOW())
            """,
            tuple(scope_params),
        )
        month_row = cursor.fetchone() or {}
        month_total = {
            "total_tokens": int((month_row.get('total_tokens') if isinstance(month_row, dict) else month_row[0]) or 0),
            "prompt_tokens": int((month_row.get('prompt_tokens') if isinstance(month_row, dict) else month_row[1]) or 0),
            "completion_tokens": int((month_row.get('completion_tokens') if isinstance(month_row, dict) else month_row[2]) or 0),
            "requests_count": int((month_row.get('requests_count') if isinstance(month_row, dict) else month_row[3]) or 0),
        }

        # Период: N последних месяцев
        cursor.execute(
            f"""
            SELECT
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COUNT(*) AS requests_count
            FROM tokenusage
            WHERE {scope_sql}
              AND created_at >= (NOW() - ((%s || ' months')::interval))
            """,
            tuple(scope_params + [months]),
        )
        period_row = cursor.fetchone() or {}
        period_total = {
            "total_tokens": int((period_row.get('total_tokens') if isinstance(period_row, dict) else period_row[0]) or 0),
            "prompt_tokens": int((period_row.get('prompt_tokens') if isinstance(period_row, dict) else period_row[1]) or 0),
            "completion_tokens": int((period_row.get('completion_tokens') if isinstance(period_row, dict) else period_row[2]) or 0),
            "requests_count": int((period_row.get('requests_count') if isinstance(period_row, dict) else period_row[3]) or 0),
        }

        # Разбивка по функциональным блокам
        cursor.execute(
            f"""
            SELECT
                CASE
                    WHEN task_type = 'service_optimization' THEN 'services_optimization'
                    WHEN task_type = 'news_generation' THEN 'news_generation'
                    WHEN task_type LIKE 'ai_agent%%' THEN 'ai_agents'
                    WHEN task_type IN ('review_reply', 'review_response', 'reviews_reply', 'reviews') THEN 'reviews'
                    ELSE 'other'
                END AS category,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COUNT(*) AS requests_count
            FROM tokenusage
            WHERE {scope_sql}
              AND created_at >= (NOW() - ((%s || ' months')::interval))
            GROUP BY category
            ORDER BY total_tokens DESC
            """,
            tuple(scope_params + [months]),
        )
        by_category = []
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                category = row.get('category') or 'other'
                total_tokens = row.get('total_tokens') or 0
                prompt_tokens = row.get('prompt_tokens') or 0
                completion_tokens = row.get('completion_tokens') or 0
                requests_count = row.get('requests_count') or 0
            else:
                category = row[0] or 'other'
                total_tokens = row[1] or 0
                prompt_tokens = row[2] or 0
                completion_tokens = row[3] or 0
                requests_count = row[4] or 0
            by_category.append({
                "category": category,
                "total_tokens": int(total_tokens),
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "requests_count": int(requests_count),
            })

        # Таймлайн по месяцам для прошлых периодов
        cursor.execute(
            f"""
            SELECT
                to_char(date_trunc('month', created_at), 'YYYY-MM') AS month_key,
                COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM tokenusage
            WHERE {scope_sql}
              AND created_at >= (NOW() - ((%s || ' months')::interval))
            GROUP BY month_key
            ORDER BY month_key DESC
            """,
            tuple(scope_params + [months]),
        )
        timeline = []
        for row in cursor.fetchall() or []:
            if isinstance(row, dict):
                timeline.append({
                    "month": row.get('month_key'),
                    "total_tokens": int(row.get('total_tokens') or 0)
                })
            else:
                timeline.append({
                    "month": row[0],
                    "total_tokens": int(row[1] or 0)
                })

        db.close()
        return jsonify({
            "success": True,
            "period_months": months,
            "scope": {"business_id": business_id, "user_id": None if business_id else user_id},
            "month_total": month_total,
            "period_total": period_total,
            "by_category": by_category,
            "timeline": timeline,
        })
    except Exception as e:
        print(f"❌ Ошибка пользовательской статистики токенов: {e}")
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
            # Create: auth_data опционален — можно сохранить external_id, cookies добавить позже
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
            saved_fields = ["external_id", "display_name", "is_active"]
            if auth_data_encrypted is not None:
                saved_fields.append("auth_data_updated")

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

        if not source or not auth_data:
            return jsonify({"error": "source и auth_data обязательны"}), 400

        if source not in ("yandex_business", "2gis"):
            return jsonify({"error": "Некорректный source"}), 400

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
        reg_val = None
        if isinstance(table_exists, dict):
            reg_val = next(iter(table_exists.values()), None)
        elif isinstance(table_exists, (list, tuple)):
            reg_val = table_exists[0] if table_exists else None
        else:
            reg_val = table_exists
        if not reg_val:
            db.close()
            return jsonify({"success": True, "reviews": [], "total": 0, "with_response": 0, "without_response": 0})

        # Читаем из externalbusinessreviews (lowercase для Postgres)
        cursor.execute(
            """
            SELECT id, source, external_review_id, rating, author_name, text,
                   response_text, response_at, published_at, created_at
            FROM externalbusinessreviews
            WHERE business_id = %s
            ORDER BY COALESCE(published_at, created_at) DESC, created_at DESC
            """,
            (business_id,),
        )
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
            })

        return jsonify({
            "success": True,
            "reviews": reviews,
            "total": len(reviews),
            "with_response": sum(1 for x in reviews if x["has_response"]),
            "without_response": sum(1 for x in reviews if not x["has_response"]),
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

        def _normalize_rating(value):
            """Нормализовать рейтинг в float [0..5], поддерживая формат с запятой."""
            if value is None:
                return None
            if isinstance(value, (int, float)):
                candidate = float(value)
            else:
                try:
                    raw = str(value).strip().replace(",", ".")
                except Exception:
                    return None
                if not raw:
                    return None
                m = re.search(r"(\d+(?:\.\d+)?)", raw)
                if not m:
                    return None
                try:
                    candidate = float(m.group(1))
                except (TypeError, ValueError):
                    return None
            if 0.0 <= candidate <= 5.0:
                return candidate
            return None

        def _overview_rating(card_row):
            if not card_row:
                return None
            overview = card_row.get("overview")
            if isinstance(overview, str):
                raw = overview.strip()
                if raw:
                    try:
                        overview = json.loads(raw)
                    except Exception:
                        overview = {}
            if isinstance(overview, dict):
                return _normalize_rating(overview.get("rating"))
            return None

        cursor.execute("SELECT rating FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business_row = _row_to_dict(cursor, raw_business) if raw_business else None
        yandex_rating_cached = _normalize_rating((business_row or {}).get("rating"))

        # Проверяем, существуют ли таблицы (Postgres)
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name IN ('externalbusinessstats', 'externalbusinessreviews')
        """)
        tables = {row['table_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
        
        if 'externalbusinessstats' not in tables or 'externalbusinessreviews' not in tables:
            # Таблицы не существуют — отдаём хотя бы данные из cards (парсинг)
            cursor.execute("""
                SELECT created_at, rating, reviews_count, competitors, overview
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
                rating = _normalize_rating(card_row.get("rating"))
                if rating is None:
                    rating = _overview_rating(card_row)
                if rating is None:
                    rating = yandex_rating_cached
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
            })

        # Статистика из externalbusinessstats (Postgres)
        cursor.execute(
            """
            SELECT rating, reviews_total, date
            FROM externalbusinessstats
            WHERE business_id = %s AND source IN ('yandex_business', 'yandex_maps')
            ORDER BY date DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_stats = cursor.fetchone()
        stats_row = _row_to_dict(cursor, raw_stats) if raw_stats else None

        cursor.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 ELSE 0 END) AS with_response,
                   SUM(CASE WHEN response_text IS NULL OR response_text = '' THEN 1 ELSE 0 END) AS without_response
            FROM externalbusinessreviews
            WHERE business_id = %s AND source IN ('yandex_business', 'yandex_maps')
            """,
            (business_id,),
        )
        raw_reviews = cursor.fetchone()
        reviews_row = _row_to_dict(cursor, raw_reviews) if raw_reviews else None

        # Карточка для UI:
        # full_card  — последняя snapshot_type='full' (богатый слепок)
        # metrics_card — последняя is_latest (может быть metrics_update или full)

        # 1) full_card: последняя полноценная карточка (совместимо с overview как text/json/jsonb)
        cursor.execute(
            """
            SELECT *
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (business_id,),
        )
        raw_cards = cursor.fetchall()
        cards_rows = [_row_to_dict(cursor, row) for row in raw_cards if row]

        def _snapshot_type(card_row):
            if not card_row:
                return None
            overview = card_row.get("overview")
            if isinstance(overview, dict):
                st = overview.get("snapshot_type")
                return str(st).strip().lower() if st else None
            if isinstance(overview, str):
                raw = overview.strip()
                if not raw:
                    return None
                try:
                    parsed = json.loads(raw)
                except Exception:
                    return None
                if isinstance(parsed, dict):
                    st = parsed.get("snapshot_type")
                    return str(st).strip().lower() if st else None
            return None

        def _overview_dict(card_row):
            if not card_row:
                return {}
            overview = card_row.get("overview")
            if isinstance(overview, dict):
                return overview
            if isinstance(overview, str):
                raw = overview.strip()
                if not raw:
                    return {}
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}

        full_card = next((row for row in cards_rows if _snapshot_type(row) == "full"), None)

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

        # 3) chosen_card: источник rich-контента (предпочитаем full, иначе metrics_card)
        chosen_card = full_card or metrics_card
        parse_row = chosen_card
        last_parse_date = parse_row.get("created_at") if parse_row else None

        db.close()

        # Метрики: сначала внешние источники, затем cards (metrics_card / chosen_card)
        rating = _normalize_rating(stats_row.get("rating")) if stats_row else None
        reviews_total = (reviews_row.get("total") or 0) if reviews_row else 0
        reviews_with_response = (reviews_row.get("with_response") or 0) if reviews_row else 0
        reviews_without_response = (reviews_row.get("without_response") or 0) if reviews_row else 0

        # 4) Fallback по метрикам:
        #   - сначала metrics_card, если это metrics_update
        #   - затем chosen_card (обычно full)
        if rating is None:
            if metrics_card and _overview_dict(metrics_card).get("snapshot_type") == "metrics_update":
                rating = _overview_rating(metrics_card) or _normalize_rating(metrics_card.get("rating"))
            if rating is None and parse_row:
                rating = _overview_rating(parse_row) or _normalize_rating(parse_row.get("rating"))
            if rating is None:
                rating = yandex_rating_cached

        if reviews_total == 0:
            if metrics_card and _overview_dict(metrics_card).get("snapshot_type") == "metrics_update" and (metrics_card.get("reviews_count") or 0) != 0:
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
            "competitors": parse_row.get("competitors") if parse_row else None
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_external_summary: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_external_summary", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500


def _ensure_manual_competitors_tables(cursor):
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ManualCompetitors (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            created_by TEXT NOT NULL,
            name TEXT,
            url TEXT NOT NULL,
            audit_status TEXT NOT NULL DEFAULT 'not_requested',
            audit_requested_at TIMESTAMP NULL,
            audit_requested_by TEXT NULL,
            report_path TEXT NULL,
            report_ready_at TIMESTAMP NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_manualcompetitors_business_url_unique
        ON ManualCompetitors (business_id, url)
        """
    )


@app.route("/api/business/<business_id>/competitors/manual", methods=["GET"])
def list_manual_competitors(business_id):
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

        _ensure_manual_competitors_tables(cursor)
        cursor.execute(
            """
            SELECT id, name, url, audit_status, audit_requested_at, report_path, report_ready_at, created_at
            FROM ManualCompetitors
            WHERE business_id = %s
            ORDER BY created_at DESC
            """,
            (business_id,),
        )
        rows = cursor.fetchall() or []
        competitors = []
        for row in rows:
            rd = _row_to_dict(cursor, row)
            competitors.append(
                {
                    "id": rd.get("id"),
                    "name": rd.get("name") or "",
                    "url": rd.get("url"),
                    "audit_status": rd.get("audit_status") or "not_requested",
                    "audit_requested_at": rd.get("audit_requested_at"),
                    "report_path": rd.get("report_path"),
                    "report_ready_at": rd.get("report_ready_at"),
                    "created_at": rd.get("created_at"),
                }
            )

        db.close()
        return jsonify({"success": True, "competitors": competitors})
    except Exception as e:
        import traceback

        err_tb = traceback.format_exc()
        print(f"❌ list_manual_competitors: {e}\n{err_tb}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/business/<business_id>/competitors/manual", methods=["POST"])
def add_manual_competitor(business_id):
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        competitor_url = str(data.get("url") or "").strip()
        if not competitor_url:
            return jsonify({"error": "Ссылка конкурента обязательна"}), 400

        if not re.match(r"^https?://", competitor_url, re.IGNORECASE):
            return jsonify({"error": "Укажите корректную ссылку (http/https)"}), 400

        competitor_name = str(data.get("name") or "").strip()

        db = DatabaseManager()
        cursor = db.conn.cursor()
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        _ensure_manual_competitors_tables(cursor)

        existing_id = None
        cursor.execute(
            "SELECT id FROM ManualCompetitors WHERE business_id = %s AND url = %s LIMIT 1",
            (business_id, competitor_url),
        )
        existing_row = cursor.fetchone()
        if existing_row:
            existing = _row_to_dict(cursor, existing_row)
            existing_id = existing.get("id")

        if existing_id:
            cursor.execute(
                """
                UPDATE ManualCompetitors
                SET name = COALESCE(NULLIF(%s, ''), name), updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (competitor_name, existing_id),
            )
            competitor_id = existing_id
        else:
            competitor_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO ManualCompetitors (id, business_id, created_by, name, url)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (competitor_id, business_id, user_data["user_id"], competitor_name, competitor_url),
            )

        db.conn.commit()
        db.close()

        return jsonify(
            {
                "success": True,
                "competitor": {
                    "id": competitor_id,
                    "name": competitor_name,
                    "url": competitor_url,
                    "audit_status": "not_requested",
                },
            }
        )
    except Exception as e:
        import traceback

        err_tb = traceback.format_exc()
        print(f"❌ add_manual_competitor: {e}\n{err_tb}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/business/<business_id>/competitors/manual/<competitor_id>/audit", methods=["POST"])
def request_manual_competitor_audit(business_id, competitor_id):
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

        _ensure_manual_competitors_tables(cursor)
        cursor.execute(
            "SELECT id FROM ManualCompetitors WHERE id = %s AND business_id = %s LIMIT 1",
            (competitor_id, business_id),
        )
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Конкурент не найден"}), 404

        cursor.execute(
            """
            UPDATE ManualCompetitors
            SET audit_status = 'requested',
                audit_requested_at = CURRENT_TIMESTAMP,
                audit_requested_by = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (user_data["user_id"], competitor_id),
        )
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Запрос на аудит отправлен суперадмину"})
    except Exception as e:
        import traceback

        err_tb = traceback.format_exc()
        print(f"❌ request_manual_competitor_audit: {e}\n{err_tb}")
        return jsonify({"success": False, "error": str(e)}), 500


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
        cursor.execute("SELECT to_regclass('public.externalbusinessposts')")
        table_exists = cursor.fetchone()
        reg_val = None
        if isinstance(table_exists, dict):
            reg_val = next(iter(table_exists.values()), None)
        elif isinstance(table_exists, (list, tuple)):
            reg_val = table_exists[0] if table_exists else None
        else:
            reg_val = table_exists
        posts = []
        if reg_val:
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
            WHERE id = %s
        """, (user_id,))
        
        # Деактивируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE owner_id = %s
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
            WHERE id = %s
        """, (user_id,))
        
        # Активируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP 
            WHERE owner_id = %s
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


def extract_yandex_org_id_from_url(yandex_url: str):
    """Извлечь ID организации Яндекс из URL (/org/.../<id> или /sprav/<id>)."""
    if not yandex_url or not isinstance(yandex_url, str):
        return None
    url = yandex_url.strip()
    if not url:
        return None
    patterns = (
        r"/org/[^/]+/(\d+)",
        r"/org/(\d+)",
        r"/sprav/(\d+)",
    )
    for pattern in patterns:
        m = re.search(pattern, url, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def get_business_map_links(cursor, business_id: str, yandex_url: str = None):
    """
    Вернуть mapLinks для API.
    Канонический источник: businesses.yandex_url.
    Legacy fallback: businessmaplinks (только если yandex_url пуст).
    """
    canonical_url = (yandex_url or "").strip()
    if canonical_url:
        return [
            {
                "id": f"business:{business_id}:yandex",
                "url": canonical_url,
                "mapType": "yandex",
                "createdAt": None,
            }
        ]

    links = []
    cursor.execute(
        """
        SELECT id, url, map_type, created_at
        FROM businessmaplinks
        WHERE business_id = %s
        ORDER BY created_at DESC
        """,
        (business_id,),
    )
    for row in cursor.fetchall():
        rd = _row_to_dict(cursor, row)
        if rd and (rd.get("url") or "").strip():
            links.append(
                {
                    "id": rd.get("id"),
                    "url": rd.get("url") or "",
                    "mapType": rd.get("map_type") or "other",
                    "createdAt": rd.get("created_at"),
                }
            )
    return links


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
        
        lang = row.get('ai_agent_language') if isinstance(row, dict) else (row[0] if row else None)
        if lang:
            return str(lang).lower()
    except Exception as e:
        print(f"⚠️ Ошибка получения языка пользователя: {e}")
    
    # Fallback на русский, если ничего не найдено
    return 'ru'


def _seo_extract_terms(text: str):
    stop_words = {
        "и", "в", "на", "с", "по", "для", "или", "от", "до", "под", "при", "за", "к", "из", "о",
        "the", "and", "for", "with", "from", "to", "of", "a", "an",
        "услуга", "услуги", "service", "services",
    }
    terms = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", (text or "").lower())
    out = []
    for t in terms:
        if len(t) < 3 or t in stop_words or t.isdigit():
            continue
        out.append(t)
    return out


SEO_BEAUTY_BUSINESS_TYPES = {
    "beauty_salon", "barbershop", "nail_studio", "spa", "massage", "cosmetology", "brows_lashes", "makeup", "tanning"
}
SEO_BEAUTY_TERMS = {"маникюр", "педикюр", "ногти", "барбер", "косметолог", "ресниц", "бров", "спа", "стрижк", "окрашив"}
SEO_BEAUTY_CATEGORIES = {"barber", "cosmetology", "eyebrows", "nails", "spa", "beauty", "hair", "makeup", "lashes"}


def _seo_is_beauty_keyword(keyword_text: str, category: str = "") -> bool:
    category_l = (category or "").strip().lower()
    if category_l in SEO_BEAUTY_CATEGORIES:
        return True
    kw = (keyword_text or "").lower()
    return any(t in kw for t in SEO_BEAUTY_TERMS)


def build_seo_keywords_context(cursor, business_id: str | None, user_id: str | None, limit: int = 120) -> tuple[str, str]:
    """
    Возвращает:
    - seo_keywords: список ключей для вставки в промпт (много строк)
    - seo_keywords_top10: короткий список top-10 через запятую
    """
    payload = collect_ranked_keywords(
        cursor,
        business_id=business_id,
        user_id=user_id,
        limit=limit,
        add_city_suffix=False,
        fallback_global_when_empty_terms=False,
        long_weight=2,
        short_weight=1,
    )
    items = payload.get("items", [])
    if not items:
        return "No matched SEO keywords found", "No matched SEO keywords found"
    seo_keywords = "\n".join([f"- {(item.get('keyword') or '').strip()} ({int(item.get('views') or 0)})" for item in items])
    seo_keywords_top10 = ", ".join([(item.get('keyword') or '').strip() for item in items[:10] if (item.get('keyword') or '').strip()])
    return seo_keywords, seo_keywords_top10


def build_seo_keywords_context_for_service(
    cursor,
    business_id: str | None,
    user_id: str | None,
    service_name: str,
    service_description: str,
    limit: int = 120,
) -> tuple[str, str]:
    """
    SEO-контекст, сфокусированный на конкретной услуге.
    В отличие от общего контекста по бизнесу не смешивает ключи по всем услугам.
    """
    payload = collect_ranked_keywords(
        cursor,
        business_id=business_id,
        user_id=user_id,
        service_name=service_name,
        service_description=service_description,
        limit=limit,
        add_city_suffix=False,
        fallback_global_when_empty_terms=False,
        long_weight=3,
        short_weight=2,
    )
    items = payload.get("items", [])
    if not items:
        return "No matched SEO keywords found", "No matched SEO keywords found"
    seo_keywords = "\n".join([f"- {(item.get('keyword') or '').strip()} ({int(item.get('views') or 0)})" for item in items])
    seo_keywords_top10 = ", ".join([(item.get('keyword') or '').strip() for item in items[:10] if (item.get('keyword') or '').strip()])
    return seo_keywords, seo_keywords_top10


def _extract_json_candidate(raw_text: str):
    if not isinstance(raw_text, str):
        return None
    txt = raw_text.strip()
    if not txt:
        return None
    try:
        direct = json.loads(txt)
        if isinstance(direct, (dict, list)):
            return direct
    except Exception:
        pass

    start = txt.find("{")
    end = txt.rfind("}") + 1
    if start != -1 and end > start:
        try:
            return json.loads(txt[start:end])
        except Exception:
            return None
    return None


def _format_prompt_with_replacements(template: str, mapping: dict) -> str:
    prompt = str(template or "")
    for key, value in (mapping or {}).items():
        prompt = prompt.replace("{" + str(key) + "}", str(value or ""))
    return prompt


def _capability_reviews_reply(envelope: dict, user_data: dict) -> dict:
    payload = envelope.get("payload") or {}
    review_text = str(payload.get("review") or "").strip()
    tone = str(payload.get("tone") or "профессиональный").strip()
    language = str(payload.get("language") or "ru").strip()
    examples = payload.get("examples") or []
    if not review_text:
        raise ValueError("review is required for reviews.reply")

    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
    }
    language_name = language_names.get(language, "Russian")

    examples_text = ""
    if isinstance(examples, list) and examples:
        examples_text = "\n".join([str(x) for x in examples[:5] if str(x).strip()])

    prompt_template = get_prompt_from_db("review_reply", None)
    if not prompt_template:
        raise ValueError("Промпт review_reply не настроен в админ-панели.")

    prompt = _format_prompt_with_replacements(
        prompt_template,
        {
            "tone": tone,
            "language_name": language_name,
            "examples_text": examples_text,
            "review_text": review_text[:1000],
        },
    )

    tenant_id = envelope.get("tenant_id")
    result_text = analyze_text_with_gigachat(
        prompt,
        task_type="review_reply",
        business_id=tenant_id,
        user_id=user_data["user_id"],
    )
    parsed = _extract_json_candidate(result_text if isinstance(result_text, str) else "")
    if isinstance(parsed, dict) and parsed.get("error"):
        raise ValueError(str(parsed.get("error")))

    reply_text = ""
    if isinstance(parsed, dict):
        reply_text = str(parsed.get("reply") or parsed.get("text") or "").strip()
    if not reply_text:
        reply_text = str(result_text or "").strip()

    return {
        "result": {"reply": reply_text},
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
            "tool_calls": 1,
            "tariff_id": str(((envelope.get("billing") or {}).get("tariff_id") or "")),
        },
    }


def _capability_services_optimize(envelope: dict, user_data: dict) -> dict:
    payload = envelope.get("payload") or {}
    language = str(payload.get("language") or "ru").strip()
    tone = str(payload.get("tone") or "профессиональный").strip()
    length = int(payload.get("description_length") or 150)
    instructions = str(payload.get("instructions") or "").strip()
    business_name = str(payload.get("business_name") or "бизнес").strip()
    region = str(payload.get("region") or "").strip()

    original_name = str(payload.get("name") or payload.get("original_name") or "").strip()
    original_description = str(payload.get("description") or payload.get("original_description") or "").strip()
    content = (original_name + ("\n" + original_description if original_description else "")).strip()
    if not content:
        raise ValueError("service name/description is required for services.optimize")

    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
    }
    language_name = language_names.get(language, "Russian")

    tenant_id = envelope.get("tenant_id")
    prompt_template = get_prompt_from_db("service_optimization", None)
    if not prompt_template:
        raise ValueError("Промпт service_optimization не настроен в админ-панели.")

    seo_keywords = "No matched SEO keywords found"
    seo_keywords_top10 = "No matched SEO keywords found"
    try:
        db_kw = DatabaseManager()
        cur_kw = db_kw.conn.cursor()
        seo_keywords, seo_keywords_top10 = build_seo_keywords_context_for_service(
            cur_kw,
            tenant_id,
            user_data["user_id"],
            original_name,
            original_description,
        )
        db_kw.close()
    except Exception:
        pass

    prompt = _format_prompt_with_replacements(
        prompt_template,
        {
            "region": region or "не указан",
            "business_name": business_name,
            "industry": str(payload.get("industry") or "-"),
            "business_type": str(payload.get("business_type") or "-"),
            "tone": tone,
            "language_name": language_name,
            "length": length,
            "instructions": instructions or "-",
            "frequent_queries": "",
            "seo_keywords": seo_keywords,
            "seo_keywords_top10": seo_keywords_top10,
            "good_examples": "",
            "content": content[:4000],
        },
    )

    result_text = analyze_text_with_gigachat(
        prompt,
        task_type="service_optimization",
        business_id=tenant_id,
        user_id=user_data["user_id"],
    )
    parsed = _extract_json_candidate(result_text if isinstance(result_text, str) else "")
    if isinstance(parsed, dict) and parsed.get("error"):
        raise ValueError(str(parsed.get("error")))

    services = []
    if isinstance(parsed, dict):
        raw_services = parsed.get("services")
        if isinstance(raw_services, list):
            services = raw_services
    elif isinstance(parsed, list):
        services = parsed

    if not services:
        services = [{
            "original_name": original_name,
            "optimized_name": original_name,
            "original_description": original_description,
            "seo_description": original_description,
            "keywords": [],
            "price": payload.get("price"),
            "category": payload.get("category") or "other",
        }]

    normalized_services = []
    for svc in services:
        if not isinstance(svc, dict):
            continue
        normalized_services.append({
            "original_name": str(svc.get("original_name") or original_name or "").strip(),
            "optimized_name": str(svc.get("optimized_name") or svc.get("name") or original_name or "").strip(),
            "original_description": str(svc.get("original_description") or original_description or "").strip(),
            "seo_description": str(svc.get("seo_description") or svc.get("description") or original_description or "").strip(),
            "keywords": svc.get("keywords") if isinstance(svc.get("keywords"), list) else [],
            "price": svc.get("price"),
            "category": str(svc.get("category") or payload.get("category") or "other"),
        })

    return {
        "result": {
            "services": normalized_services,
            "general_recommendations": [],
        },
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
            "tool_calls": 1,
            "tariff_id": str(((envelope.get("billing") or {}).get("tariff_id") or "")),
        },
    }


def _load_table_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE lower(table_name) = lower(%s)
          AND table_schema = ANY (current_schemas(false))
        """,
        (table_name,),
    )
    return {str((row[0] if isinstance(row, tuple) else row.get("column_name")) or "").lower() for row in (cursor.fetchall() or [])}


def _normalize_news_text(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = _extract_json_candidate(text)
    if isinstance(parsed, dict):
        text = str(parsed.get("news") or parsed.get("text") or text)
    if text.startswith("{") and '"news"' in text:
        try:
            candidate = _extract_json_candidate(text)
            if isinstance(candidate, dict) and candidate.get("news"):
                text = str(candidate.get("news"))
        except Exception:
            pass
    return text.replace('\\"', '"').replace("\\n", "\n").strip()


def _capability_news_generate(envelope: dict, user_data: dict) -> dict:
    payload = envelope.get("payload") or {}
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required for news.generate")

    language = str(payload.get("language") or "ru").strip()
    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
    }
    language_name = language_names.get(language, "Russian")

    use_service = bool(payload.get("use_service"))
    use_transaction = bool(payload.get("use_transaction"))
    use_seo_keywords = bool(payload.get("use_seo_keywords"))
    selected_seo_keyword = str(payload.get("selected_seo_keyword") or "").strip()
    selected_service_id = payload.get("service_id")
    selected_transaction_id = payload.get("transaction_id")
    raw_info = str(payload.get("raw_info") or "").strip()

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
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

        service_context = ""
        selected_service_name = ""
        selected_service_description = ""
        transaction_context = ""

        if use_service and selected_service_id:
            cursor.execute(
                """
                SELECT name, description
                FROM UserServices
                WHERE id = %s
                  AND (
                    business_id = %s
                    OR user_id = %s
                  )
                LIMIT 1
                """,
                (selected_service_id, tenant_id, user_data["user_id"]),
            )
            row = cursor.fetchone()
            if row:
                selected_service_name = str(row[0] if isinstance(row, tuple) else row.get("name") or "").strip()
                selected_service_description = str(row[1] if isinstance(row, tuple) else row.get("description") or "").strip()
                service_context = f"Услуга: {selected_service_name}. Описание: {selected_service_description}"

        if use_transaction and selected_transaction_id:
            cursor.execute(
                """
                SELECT transaction_date, amount, services, notes
                FROM FinancialTransactions
                WHERE id = %s
                  AND (
                    business_id = %s
                    OR user_id = %s
                  )
                LIMIT 1
                """,
                (selected_transaction_id, tenant_id, user_data["user_id"]),
            )
            tx = cursor.fetchone()
            if tx:
                tx_date = tx[0] if isinstance(tx, tuple) else tx.get("transaction_date")
                amount = tx[1] if isinstance(tx, tuple) else tx.get("amount")
                services_raw = tx[2] if isinstance(tx, tuple) else tx.get("services")
                notes = tx[3] if isinstance(tx, tuple) else tx.get("notes")
                services_list = []
                if isinstance(services_raw, list):
                    services_list = services_raw
                elif isinstance(services_raw, str) and services_raw.strip():
                    try:
                        parsed_services = json.loads(services_raw)
                        if isinstance(parsed_services, list):
                            services_list = parsed_services
                    except Exception:
                        services_list = [services_raw]
                services_str = ", ".join([str(x).strip() for x in services_list if str(x).strip()]) or "Услуги"
                transaction_context = f"Выполнена работа: {services_str}. Дата: {tx_date}. Сумма: {amount}₽. {notes or ''}"

        news_examples = ""
        try:
            from core.db_helpers import ensure_user_examples_table

            ensure_user_examples_table(cursor)
            cursor.execute(
                "SELECT example_text FROM UserExamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC LIMIT 5",
                (user_data["user_id"],),
            )
            examples_rows = cursor.fetchall() or []
            examples = []
            for row in examples_rows:
                if isinstance(row, tuple):
                    examples.append(str(row[0] or ""))
                elif hasattr(row, "keys"):
                    examples.append(str(row.get("example_text") or ""))
            news_examples = "\n".join([x for x in examples if x.strip()])
        except Exception:
            news_examples = ""

        if use_service and selected_service_name:
            seo_keywords, seo_keywords_top10 = build_seo_keywords_context_for_service(
                cursor,
                tenant_id,
                user_data["user_id"],
                selected_service_name,
                selected_service_description,
            )
        else:
            seo_keywords, seo_keywords_top10 = build_seo_keywords_context(cursor, tenant_id, user_data["user_id"])

        seo_generation_hint = ""
        if use_seo_keywords:
            seo_generation_hint = (
                "Режим генерации: SEO-first. Сначала выбери 1-2 самых частотных SEO-запроса из блока WORDSTAT, "
                "затем естественно свяжи их с реальными услугами бизнеса."
            )
            if selected_seo_keyword:
                seo_generation_hint += f" Приоритетный ключ: {selected_seo_keyword}."

        prompt_template = get_prompt_from_db("news_generation", None)
        if not prompt_template:
            raise ValueError("Промпт news_generation не настроен в админ-панели.")

        prompt = _format_prompt_with_replacements(
            prompt_template,
            {
                "language_name": language_name,
                "service_context": service_context,
                "transaction_context": transaction_context,
                "raw_info": raw_info[:800],
                "seo_keywords": seo_keywords,
                "seo_keywords_top10": seo_keywords_top10,
                "seo_generation_hint": seo_generation_hint,
                "news_examples": news_examples,
            },
        )

        result_text = analyze_text_with_gigachat(
            prompt,
            task_type="news_generation",
            business_id=tenant_id,
            user_id=user_data["user_id"],
        )
        generated_text = _normalize_news_text(result_text if isinstance(result_text, str) else str(result_text))
        if not generated_text:
            raise ValueError("Пустой результат генерации")

        news_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO UserNews (id, user_id, service_id, source_text, generated_text)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (news_id, user_data["user_id"], selected_service_id, raw_info, generated_text),
        )
        db.conn.commit()
    finally:
        db.close()

    return {
        "result": {
            "news_id": news_id,
            "generated_text": generated_text,
        },
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
            "tool_calls": 1,
            "tariff_id": str(((envelope.get("billing") or {}).get("tariff_id") or "")),
        },
    }


def _capability_sales_ingest(envelope: dict, user_data: dict) -> dict:
    payload = envelope.get("payload") or {}
    tenant_id = str(envelope.get("tenant_id") or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required for sales.ingest")

    transactions = payload.get("transactions")
    if not isinstance(transactions, list):
        single = payload.get("transaction")
        transactions = [single] if isinstance(single, dict) else []
    if not transactions:
        raise ValueError("transactions payload is required for sales.ingest")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    inserted = []
    total_amount = 0.0
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS FinancialTransactions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT,
                transaction_date DATE,
                amount REAL,
                client_type TEXT,
                services TEXT,
                notes TEXT,
                master_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cols = _load_table_columns(cursor, "financialtransactions")
        if not cols:
            raise ValueError("FinancialTransactions table is unavailable")

        for item in transactions:
            if not isinstance(item, dict):
                continue
            tx_id = str(uuid.uuid4())
            tx_date = str(item.get("transaction_date") or datetime.now().strftime("%Y-%m-%d"))
            amount = float(item.get("amount") or 0.0)
            transaction_type = str(item.get("transaction_type") or ("income" if amount >= 0 else "expense")).strip().lower()
            client_type = str(item.get("client_type") or "new")
            notes = str(item.get("notes") or "")
            services = item.get("services")
            if isinstance(services, str):
                services_value = json.dumps([services], ensure_ascii=False)
            elif isinstance(services, list):
                services_value = json.dumps([str(x) for x in services], ensure_ascii=False)
            else:
                services_value = json.dumps([], ensure_ascii=False)
            master_id = item.get("master_id")

            insert_cols = ["id"]
            params = [tx_id]
            if "user_id" in cols:
                insert_cols.append("user_id")
                params.append(str(user_data["user_id"]))
            if "business_id" in cols:
                insert_cols.append("business_id")
                params.append(tenant_id)
            if "transaction_date" in cols:
                insert_cols.append("transaction_date")
                params.append(tx_date)
            if "amount" in cols:
                insert_cols.append("amount")
                params.append(amount)
            if "transaction_type" in cols:
                insert_cols.append("transaction_type")
                params.append(transaction_type)
            if "client_type" in cols:
                insert_cols.append("client_type")
                params.append(client_type)
            if "services" in cols:
                insert_cols.append("services")
                params.append(services_value)
            if "notes" in cols:
                insert_cols.append("notes")
                params.append(notes)
            if "master_id" in cols and master_id:
                insert_cols.append("master_id")
                params.append(str(master_id))

            placeholders = ", ".join(["%s"] * len(insert_cols))
            cursor.execute(
                f"INSERT INTO FinancialTransactions ({', '.join(insert_cols)}) VALUES ({placeholders})",
                tuple(params),
            )
            inserted.append({"transaction_id": tx_id, "amount": amount, "transaction_date": tx_date})
            total_amount += amount

        if not inserted:
            raise ValueError("No valid transactions to ingest")

        db.conn.commit()
    finally:
        db.close()

    return {
        "result": {
            "inserted_count": len(inserted),
            "total_amount": round(total_amount, 2),
            "transactions": inserted,
        },
        "billing": {
            "total_tokens": 0,
            "cost": 0.0,
            "tool_calls": 1,
            "tariff_id": str(((envelope.get("billing") or {}).get("tariff_id") or "")),
        },
    }


PHASE1_ACTION_ORCHESTRATOR = ActionOrchestrator(
    handlers={
        "reviews.reply": _capability_reviews_reply,
        "services.optimize": _capability_services_optimize,
        "news.generate": _capability_news_generate,
        "sales.ingest": _capability_sales_ingest,
    }
)


def _resolve_tenant_owner_id(tenant_id: str):
    db = DatabaseManager()
    try:
        cursor = db.conn.cursor()
        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s LIMIT 1", (tenant_id,))
        row = cursor.fetchone()
        if not row:
            return None
        if hasattr(row, "get"):
            return row.get("owner_id")
        if isinstance(row, (tuple, list)):
            return row[0] if len(row) > 0 else None
        return None
    finally:
        db.close()


def _authenticate_openclaw_request():
    expected = os.getenv("OPENCLAW_LOCALOS_TOKEN", "").strip()
    provided = request.headers.get("X-OpenClaw-Token", "").strip()
    if not expected:
        return False, "OPENCLAW_LOCALOS_TOKEN is not configured"
    if not provided:
        return False, "X-OpenClaw-Token header is required"
    if not secrets.compare_digest(expected, provided):
        return False, "invalid integration token"
    return True, ""


def _openclaw_service_user(tenant_id: str):
    owner_id = _resolve_tenant_owner_id(tenant_id)
    if not owner_id:
        return None
    return {
        "user_id": str(owner_id),
        "id": str(owner_id),
        "is_superadmin": False,
        "email": "openclaw@system.local",
        "name": "OpenClaw Service",
    }


@app.route('/api/capabilities/execute', methods=['POST', 'OPTIONS'])
def capabilities_execute():
    if request.method == 'OPTIONS':
        return ('', 204)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401

    envelope = request.get_json(silent=True) or {}
    if not isinstance(envelope, dict):
        return jsonify({"error": "Invalid JSON body"}), 400

    # business_id == tenant_id в текущей tenant-модели
    if not envelope.get("tenant_id"):
        requested_business_id = envelope.get("business_id") or request.args.get("business_id")
        envelope["tenant_id"] = get_business_id_from_user(user_data["user_id"], requested_business_id)

    if not envelope.get("trace_id"):
        envelope["trace_id"] = str(uuid.uuid4())
    if not envelope.get("idempotency_key"):
        envelope["idempotency_key"] = str(uuid.uuid4())
    if not envelope.get("actor") or not isinstance(envelope.get("actor"), dict):
        envelope["actor"] = {}
    envelope["actor"].setdefault("id", user_data.get("user_id"))
    envelope["actor"].setdefault("type", "user")
    envelope["actor"].setdefault("role", "owner")
    envelope["actor"].setdefault("channel", "api")
    envelope.setdefault("approval", {"mode": "auto", "ttl_sec": 1800})
    envelope.setdefault("billing", {"tariff_id": "", "reserve_tokens": 2000})
    envelope.setdefault("payload", {})

    result = PHASE1_ACTION_ORCHESTRATOR.execute(envelope, user_data)
    status = result.get("status")
    http_code = 200
    if status == "failed":
        http_code = 400
    return jsonify(result), http_code


@app.route('/api/openclaw/capabilities/execute', methods=['POST', 'OPTIONS'])
def openclaw_capabilities_execute():
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    envelope = request.get_json(silent=True) or {}
    if not isinstance(envelope, dict):
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    tenant_id = str(envelope.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    if not envelope.get("trace_id"):
        envelope["trace_id"] = str(uuid.uuid4())
    if not envelope.get("idempotency_key"):
        envelope["idempotency_key"] = str(uuid.uuid4())
    if not envelope.get("actor") or not isinstance(envelope.get("actor"), dict):
        envelope["actor"] = {}
    envelope["actor"].setdefault("id", service_user["user_id"])
    envelope["actor"].setdefault("type", "system")
    envelope["actor"].setdefault("role", "openclaw")
    envelope["actor"].setdefault("channel", "openclaw")
    envelope.setdefault("approval", {"mode": "auto", "ttl_sec": 1800})
    envelope.setdefault("billing", {"tariff_id": "openclaw-default", "reserve_tokens": 2000})
    envelope.setdefault("payload", {})
    envelope["tenant_id"] = tenant_id

    result = PHASE1_ACTION_ORCHESTRATOR.execute(envelope, service_user)
    return jsonify(result), (200 if result.get("status") != "failed" else 400)


@app.route('/api/openclaw/capabilities/actions/<action_id>', methods=['GET', 'OPTIONS'])
def openclaw_capabilities_action_status(action_id):
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    tenant_id = str(request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    result = PHASE1_ACTION_ORCHESTRATOR.get_action(action_id, service_user)
    if result.get("success") and str(result.get("tenant_id") or "") != tenant_id:
        return jsonify({"success": False, "error": "tenant mismatch"}), 403
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/openclaw/capabilities/actions/<action_id>/billing', methods=['GET', 'OPTIONS'])
def openclaw_capabilities_action_billing(action_id):
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    tenant_id = str(request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    result = PHASE1_ACTION_ORCHESTRATOR.get_action_billing(action_id, service_user)
    if result.get("success") and str(result.get("tenant_id") or "") != tenant_id:
        return jsonify({"success": False, "error": "tenant mismatch"}), 403
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/openclaw/capabilities/actions', methods=['GET', 'OPTIONS'])
def openclaw_capabilities_actions_list():
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    tenant_id = str(request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    status = request.args.get("status")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)

    result = PHASE1_ACTION_ORCHESTRATOR.list_actions(
        service_user,
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return jsonify(result), 200


@app.route('/api/openclaw/callbacks/dispatch', methods=['POST', 'OPTIONS'])
def openclaw_callbacks_dispatch():
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    data = request.get_json(silent=True) or {}
    batch_size = data.get("batch_size", request.args.get("batch_size", 50))
    result = PHASE1_ACTION_ORCHESTRATOR.dispatch_callback_outbox(batch_size=batch_size)
    return jsonify(result), 200


@app.route('/api/openclaw/callbacks/outbox', methods=['GET', 'OPTIONS'])
def openclaw_callbacks_outbox():
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    tenant_id = str(request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    status = request.args.get("status")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    result = PHASE1_ACTION_ORCHESTRATOR.list_callback_outbox(
        service_user,
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return jsonify(result), 200


@app.route('/api/openclaw/callbacks/metrics', methods=['GET', 'OPTIONS'])
def openclaw_callbacks_metrics():
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    tenant_id = str(request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    window_minutes = request.args.get("window_minutes", 60)
    result = PHASE1_ACTION_ORCHESTRATOR.get_callback_metrics(
        service_user,
        tenant_id=tenant_id,
        window_minutes=window_minutes,
    )
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/openclaw/capabilities/actions/<action_id>/decision', methods=['POST', 'OPTIONS'])
def openclaw_capabilities_action_decision(action_id):
    if request.method == 'OPTIONS':
        return ('', 204)

    ok, reason = _authenticate_openclaw_request()
    if not ok:
        return jsonify({"success": False, "error": reason}), 401

    data = request.get_json(silent=True) or {}
    tenant_id = str(data.get("tenant_id") or request.args.get("tenant_id") or "").strip()
    if not tenant_id:
        return jsonify({"success": False, "error": "tenant_id is required"}), 400

    service_user = _openclaw_service_user(tenant_id)
    if not service_user:
        return jsonify({"success": False, "error": "tenant_id not found"}), 404

    status_check = PHASE1_ACTION_ORCHESTRATOR.get_action(action_id, service_user)
    if not status_check.get("success"):
        return jsonify(status_check), int(status_check.pop("http_code", 400))
    if str(status_check.get("tenant_id") or "") != tenant_id:
        return jsonify({"success": False, "error": "tenant mismatch"}), 403

    decision = str(data.get("decision") or "").strip().lower()
    reason_text = str(data.get("reason") or "").strip()
    result = PHASE1_ACTION_ORCHESTRATOR.resolve_human_decision(action_id, decision, service_user, reason_text)
    return jsonify(result), int(result.pop("http_code", 200 if result.get("success") else 400))


@app.route('/api/capabilities/actions/<action_id>/decision', methods=['POST', 'OPTIONS'])
def capabilities_action_decision(action_id):
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
    decision = str(data.get("decision") or "").strip().lower()
    reason = str(data.get("reason") or "").strip()
    result = PHASE1_ACTION_ORCHESTRATOR.resolve_human_decision(action_id, decision, user_data, reason)
    return jsonify(result), int(result.pop("http_code", 200 if result.get("success") else 400))


@app.route('/api/capabilities/callbacks/metrics', methods=['GET', 'OPTIONS'])
def capabilities_callbacks_metrics():
    if request.method == 'OPTIONS':
        return ('', 204)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401

    tenant_id = request.args.get("tenant_id") or request.args.get("business_id")
    if not tenant_id:
        tenant_id = get_business_id_from_user(user_data["user_id"], None)
    window_minutes = request.args.get("window_minutes", 60)
    result = PHASE1_ACTION_ORCHESTRATOR.get_callback_metrics(
        user_data,
        tenant_id=str(tenant_id),
        window_minutes=window_minutes,
    )
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/capabilities/actions/<action_id>', methods=['GET', 'OPTIONS'])
def capabilities_action_status(action_id):
    if request.method == 'OPTIONS':
        return ('', 204)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401

    result = PHASE1_ACTION_ORCHESTRATOR.get_action(action_id, user_data)
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/capabilities/actions/<action_id>/billing', methods=['GET', 'OPTIONS'])
def capabilities_action_billing(action_id):
    if request.method == 'OPTIONS':
        return ('', 204)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401

    result = PHASE1_ACTION_ORCHESTRATOR.get_action_billing(action_id, user_data)
    return jsonify(result), int(result.pop("http_code", 200))


@app.route('/api/capabilities/actions', methods=['GET', 'OPTIONS'])
def capabilities_actions_list():
    if request.method == 'OPTIONS':
        return ('', 204)
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401

    tenant_id = request.args.get("tenant_id") or request.args.get("business_id")
    status = request.args.get("status")
    limit = request.args.get("limit", 50)
    offset = request.args.get("offset", 0)
    result = PHASE1_ACTION_ORCHESTRATOR.list_actions(
        user_data,
        tenant_id=tenant_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return jsonify(result), 200


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

        payload = request.get_json(silent=True) or {}
        tone = request.form.get('tone') or payload.get('tone')
        instructions = request.form.get('instructions') or payload.get('instructions')
        region = request.form.get('region') or payload.get('region')
        business_name = request.form.get('business_name') or payload.get('business_name')
        length = request.form.get('description_length') or payload.get('description_length') or 150
        recognize_only_raw = request.form.get('recognize_only')
        if recognize_only_raw is None:
            recognize_only_raw = payload.get('recognize_only')
        recognize_only = str(recognize_only_raw).strip().lower() in ('1', 'true', 'yes', 'on')

        # Язык результата: получаем из запроса или из профиля пользователя
        requested_language = request.form.get('language') or payload.get('language')
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
        requested_business_id = None
        if request.is_json:
            requested_business_id = payload.get('business_id')
        if not requested_business_id:
            requested_business_id = request.args.get('business_id')
        business_id = get_business_id_from_user(user_data['user_id'], requested_business_id)
        business_industry = ""
        business_type_value = ""
        try:
            db_meta = DatabaseManager()
            cursor_meta = db_meta.conn.cursor()
            cursor_meta.execute("SELECT industry, business_type FROM businesses WHERE id = %s", (business_id,))
            row_meta = cursor_meta.fetchone()
            if row_meta:
                if hasattr(row_meta, "keys"):
                    business_industry = (row_meta.get("industry") or "").strip()
                    business_type_value = (row_meta.get("business_type") or "").strip()
                elif isinstance(row_meta, (tuple, list)):
                    business_industry = (row_meta[0] or "").strip() if len(row_meta) > 0 else ""
                    business_type_value = (row_meta[1] or "").strip() if len(row_meta) > 1 else ""
            db_meta.close()
        except Exception:
            business_industry = ""
            business_type_value = ""

        # Источник: файл или текст
        file = request.files.get('file') if 'file' in request.files else None
        if file:
            # Для файлов всегда выполняем шаг распознавания (без SEO-оптимизации).
            # SEO-оптимизация должна выполняться отдельным явным действием.
            recognize_only = True

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
                    if recognize_only:
                        screenshot_prompt = """Ты анализируешь изображение прайс-листа/услуг.
Верни СТРОГО валидный JSON без markdown:
{
  "services": [
    {
      "original_name": "точный текст названия услуги из изображения",
      "original_description": "краткое описание из изображения или пустая строка",
      "price": "цена как в изображении или null",
      "keywords": [],
      "category": "other"
    }
  ]
}
ПРАВИЛА:
- НИЧЕГО не оптимизируй и не переписывай.
- Не подменяй тематику услуг.
- Если услуги не найдены, верни {"services": []}.
"""
                    else:
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
                    screenshot_prompt = """Проанализируй скриншот прайс-листа и найди все услуги.

ВЕРНИ РЕЗУЛЬТАТ СТРОГО В JSON ФОРМАТЕ:
{
  "services": [
    {
      "original_name": "исходное название с скриншота",
      "original_description": "описание услуги или пустая строка",
      "price": null,
      "keywords": [],
      "category": "other"
    }
  ]
}"""
                
                print(f"🔍 Анализ скриншота, размер base64: {len(image_base64)} символов")
                result = analyze_screenshot_with_gigachat(
                    image_base64, 
                    screenshot_prompt,
                    task_type="service_optimization",
                    business_id=business_id,
                    user_id=user_data['user_id']
                )
                print(f"🔍 Результат анализа скриншота: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'not dict'}")
            else:
                # Для документов - извлекаем текст по типу/расширению.
                raw_bytes = file.read()
                filename = (file.filename or "").lower()
                content = ""

                # TXT / CSV
                if file.content_type in ("text/plain", "text/csv") or filename.endswith((".txt", ".csv")):
                    content = raw_bytes.decode("utf-8", errors="ignore")

                # DOCX (zip + word/document.xml)
                elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or filename.endswith(".docx"):
                    try:
                        import io
                        import zipfile
                        import xml.etree.ElementTree as ET

                        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                            xml_data = zf.read("word/document.xml")
                        root = ET.fromstring(xml_data)
                        text_parts = [node.text.strip() for node in root.iter() if node.tag.endswith("}t") and node.text and node.text.strip()]
                        content = "\n".join(text_parts)
                    except Exception as docx_err:
                        print(f"⚠️ Не удалось извлечь текст из DOCX: {docx_err}")
                        content = ""

                # XLSX (zip + xl/worksheets + sharedStrings)
                elif file.content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or filename.endswith(".xlsx"):
                    try:
                        import io
                        import zipfile
                        import xml.etree.ElementTree as ET

                        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                            shared_strings = []
                            if "xl/sharedStrings.xml" in zf.namelist():
                                ss_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
                                for si in ss_root.iter():
                                    if si.tag.endswith("}si"):
                                        parts = [t.text for t in si.iter() if t.tag.endswith("}t") and t.text]
                                        shared_strings.append("".join(parts).strip())

                            sheet_names = [n for n in zf.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")]
                            rows_text = []

                            def _cell_value(cell_node):
                                cell_type = cell_node.attrib.get("t")

                                # Inline string: <c t="inlineStr"><is><t>...</t></is></c>
                                if cell_type == "inlineStr":
                                    t_nodes = [t.text for t in cell_node.iter() if t.tag.endswith("}t") and t.text]
                                    return "".join(t_nodes).strip()

                                v_node = None
                                for ch in cell_node:
                                    if ch.tag.endswith("}v"):
                                        v_node = ch
                                        break

                                if v_node is None or v_node.text is None:
                                    return ""

                                raw_val = v_node.text.strip()
                                if not raw_val:
                                    return ""

                                if cell_type == "s" and raw_val.isdigit():
                                    idx = int(raw_val)
                                    if 0 <= idx < len(shared_strings):
                                        return shared_strings[idx].strip()

                                # Для чисел/текста возвращаем как есть — цены важны.
                                return raw_val

                            for sheet_name in sheet_names:
                                root = ET.fromstring(zf.read(sheet_name))
                                for row in root.iter():
                                    if not row.tag.endswith("}row"):
                                        continue

                                    row_values = []
                                    for cell in row:
                                        if not cell.tag.endswith("}c"):
                                            continue
                                        value = _cell_value(cell)
                                        if value:
                                            row_values.append(value)

                                    if not row_values:
                                        continue

                                    # Строковый вид сохраняет связь "услуга + цена" в одной строке.
                                    rows_text.append(" | ".join(row_values))

                            # Убираем дубли строк, сохраняя порядок.
                            seen_rows = set()
                            normalized_rows = []
                            for row_text in rows_text:
                                key = row_text.strip().lower()
                                if not key or key in seen_rows:
                                    continue
                                seen_rows.add(key)
                                normalized_rows.append(row_text.strip())
                            content = "\n".join(normalized_rows)
                    except Exception as xlsx_err:
                        print(f"⚠️ Не удалось извлечь текст из XLSX: {xlsx_err}")
                        content = ""

                # Для PDF/DOC/XLS без парсера не пытаемся декодировать бинарь как текст.
                else:
                    content = ""
        else:
            content = (payload.get('text') or '').strip()

        # Если файл - изображение, результат уже получен выше
        if file and file.content_type.startswith('image/'):
            # Результат анализа скриншота уже в переменной result
            # Для изображений content не используется, но инициализируем пустой строкой
            content = ""
        else:
            # Для текста и документов - проверяем наличие контента
            if not content or not content.strip():
                return jsonify({
                    "error": "Не удалось извлечь текст из файла. Для документов используйте TXT/CSV или DOCX с текстом."
                }), 400

            if recognize_only:
                prompt = f"""Ты анализируешь файл с услугами и должен только извлечь услуги.
Отвечай только валидным JSON без markdown:
{{
  "services": [
    {{
      "original_name": "точное название услуги из файла",
      "original_description": "описание услуги из файла или пустая строка",
      "price": "цена как в файле или null",
      "keywords": [],
      "category": "other"
    }}
  ]
}}
ПРАВИЛА:
- Ничего не оптимизируй, не переписывай и не заменяй тематику.
- Используй только данные из исходного текста.
- Если подходящих услуг нет, верни: {{"services":[]}}.

Текст файла:
{content[:4000]}"""
            else:
                # Загружаем частотные запросы
                try:
                    with open('prompts/frequent-queries.txt', 'r', encoding='utf-8') as f:
                        frequent_queries = f.read()
                except FileNotFoundError:
                    frequent_queries = "Частотные запросы не найдены"

                seo_keywords = "SEO keywords are unavailable"
                seo_keywords_top10 = "SEO keywords are unavailable"
                try:
                    db_kw = DatabaseManager()
                    cur_kw = db_kw.conn.cursor()
                    seo_keywords, seo_keywords_top10 = build_seo_keywords_context(cur_kw, business_id, user_data['user_id'])
                    db_kw.close()
                except Exception:
                    pass

                # Загружаем примеры хороших формулировок из профиля пользователя
                try:
                    db_examples = DatabaseManager()
                    cur_examples = db_examples.conn.cursor()
                    from core.db_helpers import ensure_user_examples_table
                    ensure_user_examples_table(cur_examples)
                    cur_examples.execute(
                        "SELECT example_text FROM UserExamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC LIMIT 5",
                        (user_data['user_id'],)
                    )
                    rows = cur_examples.fetchall()
                    db_examples.close()
                    examples_list = [row[0] if isinstance(row, tuple) else row.get('example_text') for row in rows]
                    good_examples = "\n".join([e for e in examples_list if e]) if examples_list else ""
                except Exception:
                    good_examples = ""

                # Единственный источник промпта: админка (AIPrompts)
                prompt_template_db = get_prompt_from_db('service_optimization', None)
                if not prompt_template_db:
                    return jsonify({
                        "success": False,
                        "error": "Промпт service_optimization не настроен в админ-панели."
                    }), 500

                prompt = (
                    prompt_template_db
                    .replace('{region}', str(region or 'не указан'))
                    .replace('{business_name}', str(business_name or 'бизнес'))
                    .replace('{industry}', str(business_industry or '-'))
                    .replace('{business_type}', str(business_type_value or '-'))
                    .replace('{tone}', str(tone or 'профессиональный'))
                    .replace('{language_name}', language_name)
                    .replace('{length}', str(length or 150))
                    .replace('{instructions}', str(instructions or '-'))
                    .replace('{frequent_queries}', str(frequent_queries))
                    .replace('{seo_keywords}', str(seo_keywords))
                    .replace('{seo_keywords_top10}', str(seo_keywords_top10))
                    .replace('{good_examples}', str(good_examples))
                    .replace('{content}', str(content[:4000]))
                )

                # Страховка от "утечки" примеров: запрещаем перенос контента из examples в итог.
                prompt += (
                    "\n\n"
                    "КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ:\n"
                    "1) Используй ТОЛЬКО исходные услуги из блока {content}. Не добавляй чужие тематики.\n"
                    "2) Текст из разделов с примерами (good_examples/Примеры) нельзя копировать в ответ.\n"
                    "3) Если не можешь сформировать корректный SEO-вариант по исходной услуге, верни исходное название и исходное описание.\n"
                    "4) Верни СТРОГО JSON в требуемой схеме, без markdown и без пояснений.\n"
                )

            result = analyze_text_with_gigachat(
                prompt, 
                task_type="service_optimization",
                business_id=business_id,
                user_id=user_data['user_id']
            )
        
        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку
        print(f"🔍 DEBUG services_optimize: result type = {type(result)}")
        print(f"🔍 DEBUG services_optimize: result = {result[:200] if isinstance(result, str) else result}")
        
        # Парсим JSON из ответа GigaChat (устойчиво: fenced-json / шум вокруг JSON / plain-text ошибки)
        parsed_result = None

        def _extract_balanced_json_block(text: str, open_ch: str, close_ch: str):
            start = text.find(open_ch)
            if start < 0:
                return None
            depth = 0
            in_str = False
            escape = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if escape:
                        escape = False
                    elif ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                    continue
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
            return None

        def _try_parse_json_payload(raw_text: str):
            if not isinstance(raw_text, str):
                return None
            txt = raw_text.strip()
            if not txt:
                return None

            candidates = [txt]
            try:
                import re as _re
                fenced = _re.findall(r"```json\s*(.*?)\s*```", txt, flags=_re.IGNORECASE | _re.DOTALL)
                fenced += _re.findall(r"```\s*(.*?)\s*```", txt, flags=_re.DOTALL)
                candidates.extend([c.strip() for c in fenced if c and c.strip()])
            except Exception:
                pass

            obj_block = _extract_balanced_json_block(txt, '{', '}')
            arr_block = _extract_balanced_json_block(txt, '[', ']')
            if obj_block:
                candidates.append(obj_block)
            if arr_block:
                candidates.append(arr_block)

            seen = set()
            for candidate in candidates:
                if not candidate or candidate in seen:
                    continue
                seen.add(candidate)
                try:
                    parsed = json.loads(candidate)
                except Exception:
                    continue
                if isinstance(parsed, str):
                    nested = _try_parse_json_payload(parsed)
                    if nested is not None:
                        return nested
                    continue
                return parsed
            return None

        def _extract_identity_service_from_content():
            """Fail-safe: вернуть исходную услугу из входного текста без оптимизации."""
            try:
                source_lines = [ln.strip(" -*\t") for ln in str(content or "").splitlines() if ln.strip()]
                original_name = source_lines[0] if source_lines else ""
                original_description = " ".join(source_lines[1:]).strip() if len(source_lines) > 1 else ""
                if not original_name:
                    return None
                return {
                    "services": [
                        {
                            "original_name": str(original_name).strip(),
                            "optimized_name": str(original_name).strip(),
                            "original_description": str(original_description).strip(),
                            "seo_description": str(original_description).strip(),
                            "keywords": [],
                            "price": None,
                            "category": "other"
                        }
                    ],
                    "general_recommendations": []
                }
            except Exception:
                return None

        def _extract_service_from_markdown(raw_text: str):
            """Fallback: вытаскивает название/описание из markdown-текста модели."""
            if not isinstance(raw_text, str):
                return None
            txt = raw_text.strip()
            if not txt:
                return None
            try:
                import re as _re

                # Исходные значения из content (что пришло на оптимизацию)
                original_name = ""
                original_description = ""
                content_lines = [ln.strip(" -*\t") for ln in str(content or "").splitlines() if ln.strip()]
                if content_lines:
                    original_name = content_lines[0]
                if len(content_lines) > 1:
                    original_description = " ".join(content_lines[1:]).strip()

                patterns_name = [
                    r"(?:Новое\s+)?Название\s+услуги[:\s]*\*{0,2}\s*([^\n\r*]+)",
                    r"###\s*Название\s+услуги[:\s]*([^\n\r]+)",
                ]
                patterns_desc = [
                    r"(?:Новое\s+)?Описание\s+услуги[:\s]*\*{0,2}\s*([^\n\r]+(?:\n(?!\s*(?:-|\*|###|##|\*\*|Название|Описание)).+)*)",
                    r"###\s*Описание\s+услуги[:\s]*([^\n\r]+(?:\n(?!\s*(?:-|\*|###|##|\*\*|Название|Описание)).+)*)",
                ]

                extracted_name = ""
                extracted_desc = ""
                for p in patterns_name:
                    m = _re.search(p, txt, flags=_re.IGNORECASE)
                    if m:
                        extracted_name = " ".join(m.group(1).split()).strip(" -*_")
                        if extracted_name:
                            break
                for p in patterns_desc:
                    m = _re.search(p, txt, flags=_re.IGNORECASE | _re.DOTALL)
                    if m:
                        extracted_desc = " ".join(m.group(1).split()).strip(" -*_")
                        if extracted_desc:
                            break

                if not extracted_name and not extracted_desc:
                    return None

                if not original_name:
                    original_name = extracted_name
                if not original_description:
                    original_description = extracted_desc

                return {
                    "services": [
                        {
                            "original_name": str(original_name or "").strip(),
                            "optimized_name": str(extracted_name or original_name or "").strip(),
                            "original_description": str(original_description or "").strip(),
                            "seo_description": str(extracted_desc or original_description or "").strip(),
                            "keywords": [],
                            "price": None,
                            "category": "other"
                        }
                    ],
                    "general_recommendations": []
                }
            except Exception:
                return None

        if isinstance(result, dict):
            if 'error' in result:
                error_msg = str(result.get('error') or 'Ошибка оптимизации')
                print(f"❌ Ошибка в результате: {error_msg}")
                status_code = 429 if '429' in error_msg else 502
                return jsonify({
                    "success": False,
                    "error": error_msg,
                    "raw": result.get('raw_response')
                }), status_code
            parsed_result = result
        elif isinstance(result, str):
            # Если провайдер вернул текстовую ошибку — пробрасываем её как есть.
            text_result = result.strip()
            if (
                "Запрос к GigaChat не удался" in text_result
                or "HTTP 429" in text_result
                or text_result.lower().startswith("error")
            ):
                status_code = 429 if "429" in text_result else 502
                return jsonify({
                    "success": False,
                    "error": text_result,
                    "raw": result
                }), status_code

            parsed_result = _try_parse_json_payload(result)
            if parsed_result is None:
                parsed_result = _extract_service_from_markdown(result)
                if parsed_result is None:
                    fallback_result = None
                    # Для одиночной оптимизации из UI не роняем запрос:
                    # возвращаем исходную услугу, если модель прислала "грязный" текст.
                    if not recognize_only and not file:
                        fallback_result = _extract_identity_service_from_content()
                    if fallback_result is not None:
                        fallback_name = fallback_result["services"][0].get("original_name") if fallback_result.get("services") else ""
                        print(f"⚠️ Не удалось распарсить результат оптимизации, применён fallback для услуги: {fallback_name}")
                        print(f"⚠️ Сырой ответ модели (первые 500): {result[:500]}")
                        parsed_result = fallback_result
                    else:
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

        # Нормализуем тип результата
        if isinstance(parsed_result, list):
            parsed_result = {"services": parsed_result}
        elif isinstance(parsed_result, dict):
            nested_result = parsed_result.get("result")
            if isinstance(nested_result, dict) and "services" in nested_result and "services" not in parsed_result:
                parsed_result = nested_result

        # Проверяем, что parsed_result - это словарь
        if not isinstance(parsed_result, dict):
            print(f"❌ Ошибка: parsed_result не является словарём, тип: {type(parsed_result)}")
            parsed_result = {}

        # Защита от "утечки примеров" из промпта в финальный ответ:
        # если модель ушла в нерелевантную тему, не применяем такой SEO-текст.
        def _tokenize_topic(text: str):
            import re as _re
            if not text:
                return set()
            return {
                w.lower()
                for w in _re.findall(r"[A-Za-zА-Яа-яЁё0-9]{4,}", str(text))
                if len(w) >= 4
            }

        def _looks_like_prompt_leak(text: str) -> bool:
            if not text:
                return False
            lower = str(text).lower()
            markers = (
                "пример",
                "исходные данные",
                "результат:",
                "seo-ключи",
                "название услуги:",
                "описание услуги:",
                "###",
                "---",
            )
            return sum(1 for m in markers if m in lower) >= 2

        source_lines = [ln.strip() for ln in str(content or "").splitlines() if ln.strip()]
        input_original_name = source_lines[0] if source_lines else ""
        input_original_description = " ".join(source_lines[1:]).strip() if len(source_lines) > 1 else ""

        services_block = parsed_result.get("services")
        if not isinstance(services_block, list):
            services_block = []
            parsed_result["services"] = services_block

        # Для одиночной оптимизации из UI всегда фиксируем исходные поля из входного текста.
        if (
            not recognize_only
            and not file
            and isinstance(services_block, list)
            and len(services_block) == 1
            and input_original_name
            and isinstance(services_block[0], dict)
        ):
            services_block[0]["original_name"] = input_original_name
            if input_original_description:
                services_block[0]["original_description"] = input_original_description

        # Fail-safe для одиночной оптимизации из UI:
        # если модель вернула пустой список, сохраняем исходную услугу вместо ошибки на фронте.
        if (
            not recognize_only
            and not file
            and input_original_name
            and isinstance(services_block, list)
            and len(services_block) == 0
        ):
            print(f"⚠️ Пустой services[] от модели, применён fallback для услуги: {input_original_name}")
            services_block = [{
                "original_name": input_original_name,
                "optimized_name": input_original_name,
                "original_description": input_original_description,
                "seo_description": input_original_description,
                "keywords": [],
                "price": None,
                "category": "other"
            }]
            parsed_result["services"] = services_block

        sanitized_services = []
        for svc in services_block:
            if not isinstance(svc, dict):
                continue
            original_name = str(svc.get("original_name") or input_original_name or "").strip()
            original_description = str(svc.get("original_description") or input_original_description or "").strip()
            optimized_name = str(svc.get("optimized_name") or "").strip()
            seo_description = str(svc.get("seo_description") or "").strip()

            # Если модель не дала optimized_* в ожидаемом JSON, но вернула "Название/Описание услуги" строками.
            if not optimized_name and "Название услуги:" in seo_description:
                import re as _re
                m_name = _re.search(r"Название услуги:\s*\*{0,2}\s*([^\n\r*]+)", seo_description, flags=_re.IGNORECASE)
                if m_name:
                    optimized_name = " ".join(m_name.group(1).split()).strip(" -*_")
                m_desc = _re.search(r"Описание услуги:\s*\*{0,2}\s*(.+)", seo_description, flags=_re.IGNORECASE | _re.DOTALL)
                if m_desc:
                    seo_description = " ".join(m_desc.group(1).split()).strip(" -*_")

            # Анти-дрифт: проверяем пересечение темы исходника и оптимизации.
            src_tokens = _tokenize_topic(f"{original_name} {original_description}")
            out_tokens = _tokenize_topic(f"{optimized_name} {seo_description}")
            overlap = len(src_tokens & out_tokens)
            leaked = _looks_like_prompt_leak(seo_description) or _looks_like_prompt_leak(optimized_name)
            topic_mismatch = bool(src_tokens) and overlap == 0

            if (leaked or topic_mismatch) and not recognize_only:
                print(f"⚠️ Нерелевантный SEO-ответ (leaked={leaked}, overlap={overlap}). Оставляем исходный текст.")
                optimized_name = original_name or optimized_name
                seo_description = original_description or seo_description

            svc["original_name"] = original_name
            svc["original_description"] = original_description
            svc["optimized_name"] = optimized_name or original_name
            svc["seo_description"] = seo_description or original_description
            sanitized_services.append(svc)

        parsed_result["services"] = sanitized_services

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

        if recognize_only and isinstance(result, dict):
            raw_services = result.get('services', [])
            normalized_services = []
            if isinstance(raw_services, list):
                for item in raw_services:
                    if isinstance(item, str):
                        name = item.strip()
                        if not name:
                            continue
                        normalized_services.append({
                            "original_name": name,
                            "optimized_name": name,
                            "original_description": "",
                            "seo_description": "",
                            "keywords": [],
                            "price": None,
                            "category": "other"
                        })
                        continue
                    if not isinstance(item, dict):
                        continue

                    original_name = (
                        item.get('original_name')
                        or item.get('name')
                        or item.get('service_name')
                        or item.get('title')
                        or ''
                    )
                    original_name = str(original_name).strip()
                    if not original_name:
                        continue

                    original_description = (
                        item.get('original_description')
                        or item.get('description')
                        or item.get('seo_description')
                        or ''
                    )
                    original_description = str(original_description).strip()

                    raw_keywords = item.get('keywords', [])
                    if isinstance(raw_keywords, list):
                        keywords = [str(v).strip() for v in raw_keywords if str(v).strip()]
                    elif isinstance(raw_keywords, str):
                        keywords = [v.strip() for v in re.split(r"[,\n;]+", raw_keywords) if v.strip()]
                    else:
                        keywords = []

                    price = item.get('price')
                    category = item.get('category') or 'other'

                    normalized_services.append({
                        "original_name": original_name,
                        "optimized_name": original_name,
                        "original_description": original_description,
                        "seo_description": original_description,
                        "keywords": keywords,
                        "price": price,
                        "category": category
                    })

            result = {
                "services": normalized_services,
                "general_recommendations": []
            }

        services_count = len(result.get('services', [])) if isinstance(result.get('services'), list) else 0

        if file and services_count == 0:
            return jsonify({
                "success": False,
                "error": "В файле не найдены подходящие услуги. Проверьте содержание и формат файла."
            }), 422

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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall()
            db.close()
            examples = []
            for row in rows:
                # row может быть tuple или Row
                if isinstance(row, tuple):
                    examples.append({"id": row[0], "text": row[1], "created_at": row[2]})
                else:
                    examples.append({"id": row['id'], "text": row['example_text'], "created_at": row['created_at']})
            return jsonify({"success": True, "examples": examples})

        # POST
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close()
            return jsonify({"error": "Текст примера обязателен"}), 400
        # Ограничим 5 примеров на пользователя
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = %s AND example_type = 'service'", (user_data['user_id'],))
        count = cur.fetchone()[0]
        if count >= 5:
            db.close()
            return jsonify({"error": "Максимум 5 примеров"}), 400
        example_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'service', %s)", (example_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = %s AND user_id = %s AND example_type = 'service'", (example_id, user_data['user_id']))
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
        use_seo_keywords = bool(data.get('use_seo_keywords'))
        selected_seo_keyword = (data.get('selected_seo_keyword') or '').strip()
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
        business_id = get_business_id_from_user(
            user_data['user_id'],
            data.get('business_id') or request.args.get('business_id')
        )

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

        service_context = ''
        selected_service_name = ''
        selected_service_description = ''
        transaction_context = ''
        
        if use_service:
            if selected_service_id:
                cur.execute("SELECT name, description FROM UserServices WHERE id = %s AND user_id = %s", (selected_service_id, user_data['user_id']))
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    selected_service_name = name or ''
                    selected_service_description = desc or ''
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"
            else:
                # выбрать случайную услугу пользователя
                cur.execute("SELECT name, description FROM UserServices WHERE user_id = %s ORDER BY RANDOM() LIMIT 1", (user_data['user_id'],))
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    selected_service_name = name or ''
                    selected_service_description = desc or ''
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
                    FROM FinancialTransactions
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
            cur.execute("SELECT example_text FROM UserExamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
            r = cur.fetchall()
            ex = [row[0] if isinstance(row, tuple) else row['example_text'] for row in r]
            if ex:
                news_examples = "\n".join(ex)
        except Exception:
            news_examples = ""

        if use_service and selected_service_name:
            seo_keywords, seo_keywords_top10 = build_seo_keywords_context_for_service(
                cur,
                business_id,
                user_data['user_id'],
                selected_service_name,
                selected_service_description,
            )
        else:
            seo_keywords, seo_keywords_top10 = build_seo_keywords_context(cur, business_id, user_data['user_id'])
        seo_service_context = ""
        if use_seo_keywords:
            try:
                if business_id:
                    cur.execute(
                        """
                        SELECT DISTINCT name
                        FROM userservices
                        WHERE business_id = %s
                          AND (is_active IS TRUE OR is_active IS NULL)
                          AND name IS NOT NULL
                          AND TRIM(name) <> ''
                        ORDER BY name ASC
                        LIMIT 30
                        """,
                        (business_id,),
                    )
                else:
                    cur.execute(
                        """
                        SELECT DISTINCT name
                        FROM userservices
                        WHERE user_id = %s
                          AND (is_active IS TRUE OR is_active IS NULL)
                          AND name IS NOT NULL
                          AND TRIM(name) <> ''
                        ORDER BY name ASC
                        LIMIT 30
                        """,
                        (user_data['user_id'],),
                    )
                rows = cur.fetchall() or []
                service_names = []
                for row in rows:
                    if isinstance(row, tuple):
                        name = (row[0] or "").strip()
                    elif hasattr(row, "keys"):
                        name = (row.get("name") or "").strip()
                    else:
                        name = ""
                    if name:
                        service_names.append(name)
                if service_names:
                    seo_service_context = ", ".join(service_names)
            except Exception:
                seo_service_context = ""

        seo_generation_hint = ""
        if use_seo_keywords:
            seo_generation_hint = (
                "Режим генерации: SEO-first. Сначала выбери 1-2 самых частотных SEO-запроса из блока WORDSTAT, "
                "затем естественно свяжи их с реальными услугами бизнеса. "
                f"Доступные услуги бизнеса: {seo_service_context or 'не указаны'}."
            )
            if selected_seo_keyword:
                seo_generation_hint += f" Приоритетный ключ для этой новости: {selected_seo_keyword}."
        if use_service and selected_service_name:
            seo_generation_hint += (
                f" Жесткое ограничение темы: новость должна быть только про услугу '{selected_service_name}'. "
                "Нельзя подменять услугу на другую, даже если у другой услуги частотность выше."
            )

        prompt_template = get_prompt_from_db('news_generation', None)
        if not prompt_template:
            db.close()
            return jsonify({
                "error": "Промпт news_generation не настроен в админ-панели."
            }), 500
        try:
            # Безопасная подстановка только известных плейсхолдеров.
            # В админ-шаблонах могут быть JSON-блоки с фигурными скобками,
            # которые нельзя пропускать через str.format/format_map.
            prompt = str(prompt_template)
            prompt = prompt.replace("{language_name}", str(language_name))
            prompt = prompt.replace("{service_context}", str(service_context))
            prompt = prompt.replace("{transaction_context}", str(transaction_context))
            prompt = prompt.replace("{raw_info}", str(raw_info[:800]))
            prompt = prompt.replace("{seo_keywords}", str(seo_keywords))
            prompt = prompt.replace("{seo_keywords_top10}", str(seo_keywords_top10))
            prompt = prompt.replace("{seo_generation_hint}", str(seo_generation_hint))
            prompt = prompt.replace("{news_examples}", str(news_examples))
        except Exception as format_err:
            db.close()
            return jsonify({
                "error": f"Ошибка шаблона news_generation в админ-панели: {format_err}"
            }), 500
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

            # Последний fail-safe: если в текст попала обёртка {"news": "..."},
            # вытаскиваем только содержимое новости.
            if isinstance(generated_text, str):
                gt = generated_text.strip()
                try:
                    import re
                    # Валидный JSON-объект с полем news
                    m_json = re.match(r'^\s*\{\s*"news"\s*:\s*"(.*)"\s*\}\s*$', gt, flags=re.DOTALL)
                    if m_json:
                        gt = m_json.group(1)
                    else:
                        # Невалидный, но типичный формат: {"news": "...}
                        m_broken = re.match(r'^\s*\{\s*"news"\s*:\s*"(.*)\}\s*$', gt, flags=re.DOTALL)
                        if m_broken:
                            gt = m_broken.group(1)
                        else:
                            # Без кавычек вокруг значения: {"news": text}
                            m_unquoted = re.match(r'^\s*\{\s*"news"\s*:\s*(.*?)\s*\}\s*$', gt, flags=re.DOTALL)
                            if m_unquoted:
                                gt = m_unquoted.group(1).strip().strip('"')
                    # Декодируем частые экранирования
                    gt = gt.replace('\\"', '"').replace("\\n", "\n").strip()
                    generated_text = gt
                except Exception:
                    pass
        
        # Проверяем, что generated_text не пустой
        if not generated_text or not generated_text.strip():
            db.close()
            return jsonify({"error": "Пустой результат генерации"}), 500

        news_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO UserNews (id, user_id, service_id, source_text, generated_text)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (news_id, user_data['user_id'], selected_service_id, raw_info, generated_text)
        )
        db.conn.commit()
        db.close()

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
        cur.execute("UPDATE UserNews SET approved = 1 WHERE id = %s AND user_id = %s", (news_id, user_data['user_id']))
        if cur.rowcount == 0:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit()
        db.close()
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
        cur.execute("SELECT id, service_id, source_text, generated_text, approved, created_at FROM UserNews WHERE user_id = %s ORDER BY created_at DESC", (user_data['user_id'],))
        rows = cur.fetchall()
        db.close()
        items = []
        for row in rows:
            if isinstance(row, tuple):
                items.append({
                    "id": row[0], "service_id": row[1], "source_text": row[2],
                    "generated_text": row[3], "approved": bool(row[4]), "created_at": row[5]
                })
            else:
                items.append({
                    "id": row['id'], "service_id": row['service_id'], "source_text": row['source_text'],
                    "generated_text": row['generated_text'], "approved": bool(row['approved']), "created_at": row['created_at']
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
        cur.execute("UPDATE UserNews SET generated_text = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s AND user_id = %s", (text, news_id, user_data['user_id']))
        if cur.rowcount == 0:
            db.close(); return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit(); db.close()
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
        cur.execute("DELETE FROM UserNews WHERE id = %s AND user_id = %s", (news_id, user_data['user_id']))
        deleted = cur.rowcount
        db.conn.commit()
        db.close()
        
        if deleted == 0:
            return jsonify({"error": "Новость не найдена"}), 404
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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = %s AND example_type = 'review'", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'review', %s)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = %s AND user_id = %s AND example_type = 'review'", (example_id, user_data['user_id']))
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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = %s AND example_type = 'news'", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'news', %s)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = %s AND user_id = %s AND example_type = 'news'", (example_id, user_data['user_id']))
        deleted = cur.rowcount
        db.conn.commit(); db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера новостей: {e}")
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
                cur.execute("SELECT example_text FROM UserExamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
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

        prompt_template = get_prompt_from_db('review_reply', None)
        if not prompt_template:
            return jsonify({
                "error": "Промпт review_reply не настроен в админ-панели."
            }), 500

        tone_str = str(tone) if tone else ''
        language_name_str = str(language_name) if language_name else 'Russian'
        examples_text_str = str(examples_text) if examples_text else ''
        review_text_str = str(review_text[:1000]) if review_text else ''

        try:
            prompt = str(prompt_template).format(
                tone=tone_str,
                language_name=language_name_str,
                examples_text=examples_text_str,
                review_text=review_text_str
            )
        except (KeyError, ValueError, TypeError) as format_err:
            return jsonify({
                "error": f"Ошибка шаблона review_reply в админ-панели: {format_err}"
            }), 500
        
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
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
                    pass
        else:
            # Если другой тип - конвертируем в строку
            print(f"⚠️ Неожиданный тип result_text: {type(result_text)}")
            reply_text = str(result_text) if result_text else "Ошибка генерации ответа"
        
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
        
        if not reply_id:
            return jsonify({"error": "ID ответа обязателен"}), 400
        
        if not reply_text:
            return jsonify({"error": "Текст ответа обязателен"}), 400
        
        # Создаем таблицу для хранения ответов на отзывы, если её нет
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserReviewReplies (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_review TEXT,
                reply_text TEXT NOT NULL,
                tone TEXT DEFAULT 'профессиональный',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            )
        """)
        
        # Обновляем или создаем запись
        cursor.execute("""
            INSERT INTO UserReviewReplies (id, user_id, reply_text, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                reply_text = EXCLUDED.reply_text,
                updated_at = CURRENT_TIMESTAMP
        """, (reply_id, user_data['user_id'], reply_text))
        
        db.conn.commit()
        db.close()
        
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

        # Проверяем, есть ли поле business_id в таблице UserServices (PostgreSQL: information_schema)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        
        def _keywords_to_jsonb_payload(raw_keywords):
            if isinstance(raw_keywords, list):
                cleaned = [str(v).strip() for v in raw_keywords if str(v).strip()]
                return json.dumps(cleaned, ensure_ascii=False)
            if isinstance(raw_keywords, str):
                text = raw_keywords.strip()
                if not text:
                    return json.dumps([], ensure_ascii=False)
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, list):
                        cleaned = [str(v).strip() for v in parsed if str(v).strip()]
                        return json.dumps(cleaned, ensure_ascii=False)
                    if isinstance(parsed, str):
                        return json.dumps([parsed.strip()] if parsed.strip() else [], ensure_ascii=False)
                except Exception:
                    pass
                cleaned = [p.strip() for p in re.split(r"[,\n;]+", text) if p.strip()]
                return json.dumps(cleaned, ensure_ascii=False)
            return json.dumps([], ensure_ascii=False)

        keywords_json = _keywords_to_jsonb_payload(keywords)

        if 'business_id' in columns and business_id:
            cursor.execute("""
                INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (service_id, user_id, business_id, category, name, description, keywords_json, price))
        else:
            cursor.execute("""
                INSERT INTO UserServices (id, user_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (service_id, user_id, category, name, description, keywords_json, price))

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
                    # Проверяем, есть ли поля optimized_description и optimized_name (PostgreSQL)
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_schema = 'public' AND table_name = 'userservices'
                    """)
                    columns = [c.get('column_name') if isinstance(c, dict) else c[0] for c in cursor.fetchall()]
                    has_optimized_desc = 'optimized_description' in columns
                    has_optimized_name = 'optimized_name' in columns
                    
    # Формируем SELECT с учетом наличия полей
                    select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
                    if has_optimized_desc:
                        select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                    if has_optimized_name:
                        select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
                    
                    select_sql = f"SELECT {', '.join(select_fields)} FROM UserServices WHERE business_id = %s ORDER BY created_at DESC"
                    cursor.execute(select_sql, (business_id,))
                    
                    user_services = []
                    rows = cursor.fetchall()
                    for r in rows:
                        srv = {
                            "id": r[0], "category": r[1], "name": r[2], 
                            "description": r[3], "keywords": r[4], 
                            "price": r[5], "created_at": r[6],
                            "updated_at": r[7].replace(" ", "T") if r[7] else None
                        }
                         # Если есть оптимизированные поля, добавляем их
                        idx_offset = 0
                        if has_optimized_desc:
                             srv["optimized_description"] = r[8]
                             idx_offset += 1
                        if has_optimized_name:
                             srv["optimized_name"] = r[8 + idx_offset]
                        
                        user_services.append(srv)

                    # Получаем внешние услуги
                    external_services = []
                    cursor.execute("SELECT to_regclass('public.externalbusinessservices')")
                    ext_reg_row = cursor.fetchone()
                    ext_reg_val = None
                    if isinstance(ext_reg_row, dict):
                        ext_reg_val = next(iter(ext_reg_row.values()), None)
                    elif isinstance(ext_reg_row, (list, tuple)):
                        ext_reg_val = ext_reg_row[0] if ext_reg_row else None
                    else:
                        ext_reg_val = ext_reg_row
                    if ext_reg_val:
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
                            srv_obj = {
                                "id": r[0],
                                "name": r[1],
                                "price": r[2],
                                "description": r[3],
                                "category": r[4],
                                "created_at": r[5],
                                "is_external": True
                            }
                            if ext_has_updated_at:
                                val = r[6]
                                srv_obj["updated_at"] = val.replace(" ", "T") if val else None
                            else:
                                val = r[5] # Fallback to created_at
                                srv_obj["updated_at"] = val.replace(" ", "T") if val else None
                                
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
            cursor.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'userservices'
            """)
            columns = [c.get('column_name') if isinstance(c, dict) else c[0] for c in cursor.fetchall()]
            has_optimized_desc = 'optimized_description' in columns
            has_optimized_name = 'optimized_name' in columns
            
            # Формируем SELECT с учетом наличия полей
            select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
            if has_optimized_desc:
                select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
            if has_optimized_name:
                select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
            
            select_sql = f"SELECT {', '.join(select_fields)} FROM UserServices WHERE user_id = %s ORDER BY created_at DESC"
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
                cursor_temp.execute("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'userservices'
                """)
                columns = [c.get('column_name') if isinstance(c, dict) else c[0] for c in cursor_temp.fetchall()]
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
        
        # Проверяем, есть ли поля optimized_description и optimized_name (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'userservices'
        """)
        columns = [c.get('column_name') if isinstance(c, dict) else c[0] for c in cursor.fetchall()]
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG update_service: columns = {columns}", flush=True)
        print(f"🔍 DEBUG update_service: optimized_name = '{optimized_name}' (type: {type(optimized_name)}, length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG update_service: optimized_description = '{optimized_description[:100] if optimized_description else ''}...' (type: {type(optimized_description)}, length: {len(optimized_description) if optimized_description else 0})", flush=True)
        
        if has_optimized_description and has_optimized_name:
            print(f"🔍 DEBUG update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute("""
                UPDATE UserServices SET
                category = %s, name = %s, optimized_name = %s, description = %s, optimized_description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            """, (category, name, optimized_name, description, optimized_description, keywords_str, price, service_id, user_id))
            print(f"✅ DEBUG update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)

        else:
            print(f"🔍 DEBUG update_service: Обновление БЕЗ optimized_description/name", flush=True)
            cursor.execute("""
                UPDATE UserServices SET
                category = %s, name = %s, description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
            """, (category, name, description, keywords_str, price, service_id, user_id))

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        db.conn.commit()
        db.close()
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
        cursor.execute("DELETE FROM UserServices WHERE id = %s AND user_id = %s", (service_id, user_id))

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

        # Postgres-only: данные профиля из businesses, userservices, businessprofiles, users.
        # Каноническая ссылка на карты хранится в businesses.yandex_url.
        # businessmaplinks используется только как legacy fallback на чтение.

        if request.method == 'GET':
            current_business_id = request.args.get('business_id')
            print(f"🔍 GET /api/client-info: method=GET, business_id={current_business_id}, user_id={user_id}")
            
            # Если передан business_id — данные только из таблицы businesses (lowercase). Фильтр is_active согласован с dropdown (auth/me).
            if current_business_id:
                print(f"🔍 GET /api/client-info: Ищу бизнес в таблице businesses, business_id={current_business_id}")
                cursor.execute(
                    "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon, yandex_url FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
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
                        links = get_business_map_links(cursor, current_business_id, row_dict.get("yandex_url"))

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
                "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon, yandex_url FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
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
            links = get_business_map_links(cursor, current_business_id, row_dict.get("yandex_url"))
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
        
        # Принимаем mapLinks, но сохраняем только каноническую yandex_url в businesses.
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
            if 'google' in u:
                return 'google'
            return 'other'

        # Парсер больше не запускается автоматически при сохранении ссылок
        # Он запускается только вручную через кнопку "Запустить парсер" на странице "Обзор карточки"

        # mapLinks: обновляем только если в теле явно передан ключ mapLinks/map_links.
        # Ключ отсутствует -> yandex_url не трогаем.
        # mapLinks=[] -> очистить yandex_url.
        if business_id and ("mapLinks" in data or "map_links" in data) and isinstance(map_links, list):
            print(f"📝 SAVE mapLinks: business_id={business_id}, user_id={user_id}, map_links={map_links}")
            valid_links = []
            for link in map_links:
                url = link.get('url') if isinstance(link, dict) else str(link)
                if url and url.strip():
                    valid_links.append(url.strip())
            print(f"📝 SAVE mapLinks: valid_links={valid_links}, count={len(valid_links)}")

            canonical_yandex_url = None
            for url in valid_links:
                if detect_map_type(url) == "yandex":
                    canonical_yandex_url = url
                    break

            cursor.execute(
                "UPDATE businesses SET yandex_url = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                (canonical_yandex_url, business_id),
            )
            db.conn.commit()
            print(f"📝 SAVE yandex_url: business_id={business_id}, yandex_url={canonical_yandex_url}")

            # Парсим ll=lon,lat из первой ссылки на Яндекс.Карты и сохраняем в businesses
            if canonical_yandex_url and "ll=" in canonical_yandex_url:
                geo_lon, geo_lat = parse_ll_from_maps_url(canonical_yandex_url)
                if geo_lon is not None and geo_lat is not None:
                    cursor.execute(
                        "UPDATE businesses SET geo_lon = %s, geo_lat = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                        (geo_lon, geo_lat, business_id),
                    )
                    db.conn.commit()
                    print(f"📝 geo: business_id={business_id} geo_lon={geo_lon} geo_lat={geo_lat} из ll в ссылке")
            elif not canonical_yandex_url:
                print(f"📝 yandex_url очищен для business_id={business_id}")

            cursor.execute("SELECT yandex_url FROM businesses WHERE id = %s", (business_id,))
            raw_saved = cursor.fetchone()
            saved = _row_to_dict(cursor, raw_saved) if raw_saved else {}
            print(f"📝 VERIFY yandex_url: business_id={business_id}, saved={saved.get('yandex_url') if saved else None}")

        # Всегда возвращаем текущие ссылки для бизнеса
        current_links = []
        if business_id:
            print(f"📖 GET mapLinks: business_id={business_id}")
            cursor.execute("SELECT yandex_url FROM businesses WHERE id = %s", (business_id,))
            raw_biz = cursor.fetchone()
            biz_row = _row_to_dict(cursor, raw_biz) if raw_biz else {}
            current_links = get_business_map_links(cursor, business_id, (biz_row or {}).get("yandex_url"))
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
            SELECT status, retry_after, captcha_url, error_message, created_at
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
            "retry_info": retry_info,
            "captcha_url": (queue_row.get("captcha_url") if queue_row else None),
            "error_message": (queue_row.get("error_message") if queue_row else None),
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
                   overview, products, news, photos, competitors, hours_full, phone, site
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
        """, (business_id,))
        rows_raw = cursor.fetchall()
        rows = [_row_to_dict(cursor, r) for r in rows_raw if r]

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

        def _products_count(v):
            """Считает уникальные услуги: дедуп по (name, category, price)."""
            if v is None:
                return 0
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    return 0
            if not isinstance(v, list):
                return 0
            seen = set()
            for cat in v:
                if isinstance(cat, dict) and "items" in cat:
                    cat_name = (cat.get("category") or "Разное").strip() or "Разное"
                    for item in (cat.get("items") or []):
                        if not isinstance(item, dict):
                            continue
                        name = (item.get("name") or item.get("title") or "").strip().lower()
                        if not name:
                            continue
                        price = str(item.get("price") or item.get("price_from") or item.get("price_to") or "").strip()
                        seen.add((name, cat_name.lower(), price))
                else:
                    if isinstance(cat, dict):
                        name = (cat.get("name") or cat.get("title") or "").strip().lower()
                        if name:
                            price = str(cat.get("price") or "").strip()
                            ccat = (cat.get("category") or "Разное").strip().lower()
                            seen.add((name, ccat, price))
            return len(seen)

        def _overview_dict(v):
            if isinstance(v, dict):
                return v
            if isinstance(v, str):
                raw = v.strip()
                if not raw:
                    return {}
                try:
                    parsed = json.loads(raw)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
            return {}

        # Текущее число неотвеченных отзывов (для отображения в прогрессе и отчёте)
        unanswered_current = 0
        latest_parsed_services_count = 0
        stat_cursor = None
        try:
            stat_cursor = db.conn.cursor()
            stat_cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM externalbusinessreviews
                WHERE business_id = %s
                  AND source IN ('yandex_business', 'yandex_maps')
                  AND (response_text IS NULL OR TRIM(COALESCE(response_text, '')) = '')
                """,
                (business_id,),
            )
            raw_unanswered = stat_cursor.fetchone()
            raw_unanswered = _row_to_dict(stat_cursor, raw_unanswered) if raw_unanswered else None
            unanswered_current = int((raw_unanswered or {}).get("cnt") or 0)

            # Количество услуг из последнего распарсенного снапшота userservices.
            stat_cursor.execute(
                """
                WITH latest_ts AS (
                    SELECT MAX(updated_at) AS ts
                    FROM userservices
                    WHERE business_id = %s
                      AND source IN ('yandex_maps', 'yandex_business')
                      AND (is_active IS TRUE OR is_active IS NULL)
                      AND raw IS NOT NULL
                )
                SELECT COUNT(DISTINCT (
                    LOWER(TRIM(COALESCE(name, ''))),
                    LOWER(TRIM(COALESCE(category, ''))),
                    TRIM(COALESCE(price::text, ''))
                )) AS cnt
                FROM userservices
                WHERE business_id = %s
                  AND source IN ('yandex_maps', 'yandex_business')
                  AND (is_active IS TRUE OR is_active IS NULL)
                  AND raw IS NOT NULL
                  AND updated_at = (SELECT ts FROM latest_ts)
                """,
                (business_id, business_id),
            )
            raw_services_cnt = stat_cursor.fetchone()
            raw_services_cnt = _row_to_dict(stat_cursor, raw_services_cnt) if raw_services_cnt else None
            latest_parsed_services_count = int((raw_services_cnt or {}).get("cnt") or 0)
        except Exception:
            unanswered_current = 0
        finally:
            if stat_cursor is not None:
                stat_cursor.close()

        items = []
        for rd in rows:
            if not rd:
                continue
            news_count = _len(rd.get("news"))
            photos_count = _len(rd.get("photos"))
            overview = _overview_dict(rd.get("overview"))
            try:
                overview_photos_count = int(overview.get("photos_count") or 0)
            except (TypeError, ValueError):
                overview_photos_count = 0
            photos_count = max(photos_count, overview_photos_count)
            products_count = _products_count(rd.get("products"))
            if len(items) == 0 and latest_parsed_services_count > 0:
                products_count = latest_parsed_services_count
            phone = (rd.get("phone") or "").strip() if isinstance(rd.get("phone"), str) else (rd.get("phone") or "")
            website = (rd.get("site") or "").strip() if isinstance(rd.get("site"), str) else (rd.get("site") or "")
            hours_full = rd.get("hours_full")
            if isinstance(hours_full, str):
                try:
                    hours_full = json.loads(hours_full)
                except Exception:
                    hours_full = []
            if not isinstance(hours_full, list):
                hours_full = []
            working_hours_payload = {"schedule": hours_full} if hours_full else None
            social_links = overview.get("social_links") if isinstance(overview, dict) else None
            competitors_val = rd.get("competitors")
            if isinstance(competitors_val, (list, dict)):
                competitors_val = json.dumps(competitors_val, ensure_ascii=False)

            completeness_points = 0
            completeness_points += 1 if phone else 0
            completeness_points += 1 if website else 0
            completeness_points += 1 if hours_full else 0
            completeness_points += 1 if products_count > 0 else 0
            completeness_points += 1 if photos_count > 0 else 0
            profile_completeness = int((completeness_points / 5) * 100)

            item = {
                "id": rd.get("id"),
                "url": rd.get("url"),
                "mapType": "yandex",
                "rating": rd.get("rating"),
                "reviewsCount": rd.get("reviews_count") or 0,
                "unansweredReviewsCount": unanswered_current if len(items) == 0 else 0,
                "newsCount": news_count,
                "photosCount": photos_count,
                "productsCount": products_count,
                "servicesCount": products_count,
                "phone": phone or None,
                "website": website or None,
                "workingHours": json.dumps(working_hours_payload, ensure_ascii=False) if working_hours_payload else None,
                "messengers": json.dumps(social_links, ensure_ascii=False) if isinstance(social_links, list) else None,
                "profileCompleteness": profile_completeness,
                "competitors": competitors_val,
                "reportPath": rd.get("report_path"),
                "createdAt": rd.get("created_at"),
            }
            items.append(item)

        db.close()
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
            INSERT INTO ScreenshotAnalyses (id, user_id, image_path, analysis_result, completeness_score, business_name, category, expires_at)
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
            SELECT * FROM ScreenshotAnalyses 
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))
        
        analysis = cursor.fetchone()
        if analysis:
            db.close()
            return jsonify({
                "success": True,
                "type": "screenshot",
                "result": json.loads(analysis['analysis_result']),
                "created_at": analysis['created_at']
            })
        
        # Ищем оптимизацию прайс-листа
        cursor.execute("""
            SELECT * FROM PricelistOptimizations 
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))
        
        optimization = cursor.fetchone()
        if optimization:
            db.close()
            return jsonify({
                "success": True,
                "type": "pricelist",
                "result": json.loads(optimization['optimized_data']),
                "created_at": optimization['created_at']
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
            INSERT INTO ScreenshotAnalyses 
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
        
        # Проверяем наличие поля master_id (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'financialtransactions'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_master_id = 'master_id' in columns
        
        if has_master_id:
            cursor.execute("""
                INSERT INTO FinancialTransactions 
                (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                transaction_id,
                user_data['user_id'],
                data['transaction_date'],
                data['amount'],
                data['client_type'],
                json.dumps(data.get('services', [])),
                data.get('notes', ''),
                data.get('master_id')
            ))
        else:
            cursor.execute("""
                INSERT INTO FinancialTransactions 
                (id, user_id, transaction_date, amount, client_type, services, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                transaction_id,
                user_data['user_id'],
                data['transaction_date'],
                data['amount'],
                data['client_type'],
                json.dumps(data.get('services', [])),
                data.get('notes', '')
            ))
        
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
        cursor.execute("SELECT id, user_id FROM FinancialTransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        if row[1] != user_data['user_id']:
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
        cursor.execute(f"UPDATE FinancialTransactions SET {', '.join(fields)} WHERE id = %s", params)
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
        cursor.execute("SELECT id, user_id FROM FinancialTransactions WHERE id = %s LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        if row[1] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        cursor.execute("DELETE FROM FinancialTransactions WHERE id = %s", (transaction_id,))
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
        
        # Проверяем наличие полей master_id и business_id (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'financialtransactions'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
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
                cursor.execute("SELECT id FROM Businesses WHERE owner_id = %s LIMIT 1", (user_data['user_id'],))
                business_row = cursor.fetchone()
                if business_row:
                    business_id = business_row[0]
            
            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
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
                    INSERT INTO FinancialTransactions 
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
                    INSERT INTO FinancialTransactions 
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
                    INSERT INTO FinancialTransactions 
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
        
        # Проверяем наличие client_type в схеме (для совместимости старых БД)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND lower(table_name) = 'financialtransactions'
        """)
        tx_columns = {r.get('column_name') if isinstance(r, dict) else r[0] for r in (cursor.fetchall() or [])}
        has_client_type = 'client_type' in tx_columns
        client_type_select = "client_type" if has_client_type else "'new'::text AS client_type"

        # Строим запрос с явными полями (без SELECT *)
        query = """
            SELECT 
                id,
                business_id,
                transaction_date,
                amount,
                """ + client_type_select + """,
                services,
                notes,
                created_at
            FROM FinancialTransactions
            WHERE user_id = %s
        """
        params = [user_data['user_id']]
        
        # Фильтр по бизнесу, если передан
        current_business_id = request.args.get('business_id')
        if current_business_id:
            query += " AND business_id = %s"
            params.append(current_business_id)
        
        if start_date:
            query += " AND transaction_date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= %s"
            params.append(end_date)
        
        query += " ORDER BY transaction_date DESC, created_at DESC LIMIT %s OFFSET %s"
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
        
        # Проверяем наличие client_type в схеме (для совместимости старых БД)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND lower(table_name) = 'financialtransactions'
        """)
        tx_columns = {r.get('column_name') if isinstance(r, dict) else r[0] for r in (cursor.fetchall() or [])}
        has_client_type = 'client_type' in tx_columns
        new_clients_expr = "SUM(CASE WHEN client_type = 'new' THEN 1 ELSE 0 END)" if has_client_type else "0"
        returning_clients_expr = "SUM(CASE WHEN client_type = 'returning' THEN 1 ELSE 0 END)" if has_client_type else "0"

        # Получаем агрегированные данные
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as average_check,
                {new_clients_expr} as new_clients,
                {returning_clients_expr} as returning_clients
            FROM FinancialTransactions 
            WHERE {where_clause}
        """, tuple(where_params))
        
        metrics = cursor.fetchone()
        
        # Вычисляем retention rate
        # Вычисляем retention rate
        new_clients = metrics[3] or 0
        returning_clients = metrics[4] or 0
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
            FROM FinancialTransactions 
            WHERE {prev_where_clause}
        """, tuple(prev_where_params))
        
        prev_metrics = cursor.fetchone()
        
        # Вычисляем рост
        revenue_growth = 0
        orders_growth = 0
        
        if prev_metrics[1] and prev_metrics[1] > 0:
            revenue_growth = ((metrics[1] or 0) - prev_metrics[1]) / prev_metrics[1] * 100
        
        if prev_metrics[0] and prev_metrics[0] > 0:
            orders_growth = ((metrics[0] or 0) - prev_metrics[0]) / prev_metrics[0] * 100
        
        db.close()
        
        return jsonify({
            "success": True,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "period_type": period
            },
            "metrics": {
                "total_revenue": float(metrics[1] or 0),
                "total_orders": metrics[0] or 0,
                "average_check": float(metrics[2] or 0),
                "new_clients": metrics[3] or 0,
                "returning_clients": metrics[4] or 0,
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
        
        # Проверяем наличие полей в таблице (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'financialtransactions'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_business_id = 'business_id' in columns
        has_master_id = 'master_id' in columns
        
        # Получаем business_id из запроса
        current_business_id = request.args.get('business_id')
        
        # Получаем транзакции за период
        if has_business_id and current_business_id:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM FinancialTransactions 
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM FinancialTransactions 
                    WHERE business_id = %s AND transaction_date BETWEEN %s AND %s
                """, (current_business_id, start_date, end_date))
        else:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM FinancialTransactions 
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM FinancialTransactions 
                    WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
                """, (user_data['user_id'], start_date, end_date))
        
        transactions = cursor.fetchall()
        
        # Агрегируем по услугам
        services_revenue = {}
        for row in transactions:
            services_json = row[0]  # services (JSON)
            amount = float(row[1] or 0)
            
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
            master_id = row[2] if len(row) > 2 else None  # master_id (может отсутствовать)
            amount = float(row[1] or 0)
            
            if master_id:
                # Проверяем наличие таблицы Masters
                cursor.execute("SELECT to_regclass('public.masters')")
                masters_table_exists = cursor.fetchone()
                
                if masters_table_exists:
                    cursor.execute("SELECT name FROM masters WHERE id = %s", (master_id,))
                    master_row = cursor.fetchone()
                    master_name = master_row[0] if master_row else f"Мастер {master_id[:8]}"
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = %s", (network_id,))
        network = cursor.fetchone()
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        # Проверяем права доступа (владелец или суперадмин)
        if network[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Получаем точки сети
        cursor.execute("""
            SELECT id, name, address, description 
            FROM Businesses 
            WHERE network_id = %s 
            ORDER BY name
        """, (network_id,))
        
        locations = []
        for row in cursor.fetchall():
            locations.append({
                "id": row[0],
                "name": row[1],
                "address": row[2],
                "description": row[3]
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = %s", (network_id,))
        network = cursor.fetchone()
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        if network[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Получаем точки сети
        cursor.execute("SELECT id, name FROM Businesses WHERE network_id = %s", (network_id,))
        locations = cursor.fetchall()
        location_ids = [loc[0] for loc in locations]
        
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
        
        # Получаем транзакции всех точек сети (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'financialtransactions'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_business_id = 'business_id' in columns
        
        if has_business_id and location_ids:
            placeholders = ','.join(['%s'] * len(location_ids))
            cursor.execute(f"""
                SELECT services, amount, master_id, business_id
                FROM FinancialTransactions 
                WHERE business_id IN ({placeholders}) AND transaction_date BETWEEN %s AND %s
            """, location_ids + [start_date, end_date])
        else:
            # Если business_id нет, получаем через user_id владельца сети
            cursor.execute("""
                SELECT services, amount, master_id, NULL as business_id
                FROM FinancialTransactions 
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
            """, (network[0], start_date, end_date))
        
        transactions = cursor.fetchall()
        
        # Агрегируем данные
        services_revenue = {}
        masters_revenue = {}
        locations_revenue = {loc[1]: 0 for loc in locations}
        
        for row in transactions:
            services_json = row[0]
            amount = float(row[1] or 0)
            master_id = row[2]
            business_id = row[3]
            
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
                cursor.execute("SELECT name FROM Masters WHERE id = %s", (master_id,))
                master_row = cursor.fetchone()
                master_name = master_row[0] if master_row else f"Мастер {master_id[:8]}"
                masters_revenue[master_name] = masters_revenue.get(master_name, 0) + amount
            
            # По точкам
            location_name = next((loc[1] for loc in locations if loc[0] == business_id), "Неизвестно")
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
                FROM Businesses
                WHERE network_id = %s AND is_active = 1
                """,
                (network_id,),
            )
            for row in cursor.fetchall():
                ratings.append(
                    {
                        "business_id": row[0],
                        "name": row[1],
                        "rating": row[2],
                        "reviews_total": row[3],
                        "reviews_30d": row[4],
                        "last_sync": row[5],
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

        cursor.execute("SELECT owner_id FROM Networks WHERE id = %s", (network_id,))
        network = cursor.fetchone()

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        if network[0] != user_data["user_id"] and not user_data.get("is_superadmin"):
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
    Ручной запуск парсинга/синхронизации Яндекс для одного бизнеса или всей сети.
    scope:
      - single (default): только текущий бизнес
      - network: все точки сети с постановкой в очередь (с задержкой через retry_after)
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

        payload = request.get_json(silent=True) or {}
        scope = str(payload.get("scope") or "single").strip().lower()
        if scope not in ("single", "network"):
            scope = "single"

        try:
            delay_seconds = int(payload.get("delay_seconds", 15))
        except (TypeError, ValueError):
            delay_seconds = 15
        delay_seconds = max(0, min(delay_seconds, 300))

        user_id = user_data.get("user_id") or user_data.get("id")
        is_superadmin = bool(user_data.get("is_superadmin"))

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT id, owner_id, name, network_id FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business = _row_to_dict(cursor, raw_business) if raw_business else None

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business.get("owner_id")
        business_name = (business.get("name") or "").strip() or "Unknown"

        if business_owner_id != user_id and not is_superadmin:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Собираем целевые бизнесы
        target_businesses = [business]
        resolved_network_id = business.get("network_id")

        if scope == "network":
            # Для материнского аккаунта сеть может быть не в business.network_id
            if not resolved_network_id:
                cursor.execute("SELECT id FROM networks WHERE id = %s LIMIT 1", (business_id,))
                row = cursor.fetchone()
                if row:
                    resolved_network_id = row[0] if not hasattr(row, "keys") else row.get("id")

            if not resolved_network_id:
                cursor.execute(
                    """
                    SELECT n.id
                    FROM networks n
                    WHERE n.owner_id = %s
                    ORDER BY (
                        SELECT COUNT(*) FROM businesses b WHERE b.network_id = n.id
                    ) DESC, n.created_at DESC
                    LIMIT 1
                    """,
                    (business_owner_id,),
                )
                row = cursor.fetchone()
                if row:
                    resolved_network_id = row[0] if not hasattr(row, "keys") else row.get("id")

            if not resolved_network_id:
                db.close()
                return jsonify(
                    {
                        "success": False,
                        "error": "Сеть не найдена",
                        "message": "Для выбранного бизнеса не найдена сеть с точками",
                    }
                ), 400

            if is_superadmin:
                cursor.execute(
                    """
                    SELECT id, owner_id, name, network_id
                    FROM businesses
                    WHERE network_id = %s AND (is_active = TRUE OR is_active IS NULL)
                    ORDER BY created_at ASC
                    """,
                    (resolved_network_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, owner_id, name, network_id
                    FROM businesses
                    WHERE network_id = %s
                      AND owner_id = %s
                      AND (is_active = TRUE OR is_active IS NULL)
                    ORDER BY created_at ASC
                    """,
                    (resolved_network_id, user_id),
                )

            target_businesses = []
            for row in cursor.fetchall():
                item = _row_to_dict(cursor, row)
                if item:
                    target_businesses.append(item)

            if not target_businesses:
                db.close()
                return jsonify(
                    {
                        "success": False,
                        "error": "Нет точек сети",
                        "message": "В выбранной сети не найдено активных точек",
                    }
                ), 400

        # Формируем и ставим задачи в очередь
        enqueued = []
        skipped_no_source = []
        skipped_has_active = []
        now = datetime.now()

        for idx, biz in enumerate(target_businesses):
            target_business_id = biz.get("id")
            target_business_name = (biz.get("name") or "").strip() or target_business_id

            cursor.execute(
                """
                SELECT id
                FROM externalbusinessaccounts
                WHERE business_id = %s
                  AND source IN ('yandex_business', 'yandex')
                  AND is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (target_business_id,),
            )
            raw_account = cursor.fetchone()
            account_row = _row_to_dict(cursor, raw_account) if raw_account else None
            account_id = account_row.get("id") if account_row else None

            cursor.execute("SELECT yandex_url FROM businesses WHERE id = %s", (target_business_id,))
            raw_biz_map = cursor.fetchone()
            biz_map_row = _row_to_dict(cursor, raw_biz_map) if raw_biz_map else None
            map_url = (biz_map_row.get("yandex_url") or "").strip() if biz_map_row else ""
            if not map_url:
                # legacy fallback
                cursor.execute(
                    """
                    SELECT url
                    FROM businessmaplinks
                    WHERE business_id = %s
                      AND map_type IN ('yandex', 'yandex_maps')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (target_business_id,),
                )
                raw_map = cursor.fetchone()
                map_link_row = _row_to_dict(cursor, raw_map) if raw_map else None
                map_url = map_link_row.get("url") if map_link_row else None

            if not account_id and not map_url:
                skipped_no_source.append(target_business_name)
                continue

            cursor.execute(
                """
                SELECT id
                FROM parsequeue
                WHERE business_id = %s
                  AND task_type IN ('parse_card', 'sync_yandex_business')
                  AND status IN ('pending', 'processing', 'captcha')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (target_business_id,),
            )
            if cursor.fetchone():
                skipped_has_active.append(target_business_name)
                continue

            if map_url:
                task_type = "parse_card"
                source = "yandex_maps"
                target_url = map_url
            else:
                task_type = "sync_yandex_business"
                source = "yandex_business"
                target_url = ""

            task_id = str(uuid.uuid4())
            delay = delay_seconds * len(enqueued) if scope == "network" else 0
            retry_after = (now + timedelta(seconds=delay)).isoformat() if delay > 0 else None

            cursor.execute(
                """
                INSERT INTO parsequeue (
                    id, business_id, account_id, task_type, source,
                    status, user_id, url, retry_after, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s,
                        'pending', %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (task_id, target_business_id, account_id, task_type, source, user_id, target_url, retry_after),
            )
            enqueued.append(
                {
                    "task_id": task_id,
                    "business_id": target_business_id,
                    "business_name": target_business_name,
                    "task_type": task_type,
                    "retry_after": retry_after,
                }
            )

        db.conn.commit()
        db.close()

        if not enqueued:
            return jsonify(
                {
                    "success": False,
                    "error": "Нет задач для запуска",
                    "message": "Все точки уже в очереди или у точек отсутствует источник данных",
                    "details": {
                        "scope": scope,
                        "skipped_no_source": skipped_no_source,
                        "skipped_has_active": skipped_has_active,
                    },
                }
            ), 400

        # Backward compatibility для одиночного запуска
        if scope == "single":
            item = enqueued[0]
            return jsonify(
                {
                    "success": True,
                    "message": "Запущен парсинг карт" if item["task_type"] == "parse_card" else "Запущена синхронизация (без парсинга)",
                    "sync_id": item["task_id"],
                    "task_type": item["task_type"],
                }
            )

        return jsonify(
            {
                "success": True,
                "message": f"Поставлено в очередь: {len(enqueued)} точек сети. Капча, если появится, будет в статусе задачи.",
                "network_id": resolved_network_id,
                "scope": scope,
                "delay_seconds": delay_seconds,
                "enqueued_count": len(enqueued),
                "skipped_no_source_count": len(skipped_no_source),
                "skipped_has_active_count": len(skipped_has_active),
                "enqueued": enqueued[:25],
            }
        )

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
    Stub: 2ГИС синхронизация пока не реализована. Возвращает 501 JSON (без 404/HTML).
    """
    return jsonify({
        "success": False,
        "message": "2ГИС синк пока не реализован",
        "where": "admin_sync_business_2gis"
    }), 501


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
                                WHERE business_id = %s AND name = %s 
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
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
                                    SET category = %s, description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                                    WHERE business_id = %s AND name = %s
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
            FROM Networks 
            WHERE owner_id = %s 
            ORDER BY name
        """, (user_data['user_id'],))
        
        networks = []
        for row in cursor.fetchall():
            networks.append({
                "id": row[0],
                "name": row[1],
                "description": row[2]
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = %s", (network_id,))
        network = cursor.fetchone()
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        if network[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
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
            SELECT investment_amount, returns_amount, roi_percentage, period_start, period_end
            FROM roidata
            WHERE user_id = %s
            ORDER BY created_at DESC NULLS LAST
            LIMIT 1
        """, (user_data['user_id'],))
        
        roi_data = cursor.fetchone()
        
        if not roi_data:
            db.close()
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
                "investment_amount": float(roi_data[0] or 0),
                "returns_amount": float(roi_data[1] or 0),
                "roi_percentage": float(roi_data[2] or 0),
                "period_start": roi_data[3],
                "period_end": roi_data[4]
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
            INSERT INTO roidata
            (id, user_id, investment_amount, returns_amount, roi_percentage, period_start, period_end, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
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
        
        set_clause = ', '.join([f"{key} = %s" for key in updates.keys()])
        values = list(updates.values()) + [user['user_id']]
        
        cursor.execute(f"UPDATE Users SET {set_clause} WHERE id = %s", values)
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
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
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
            proxies.append({
                "id": row[0],
                "type": row[1],
                "host": row[2],
                "port": row[3],
                "is_active": bool(row[4]),
                "is_working": bool(row[5]),
                "success_count": row[6],
                "failure_count": row[7],
                "last_used_at": row[8],
                "last_checked_at": row[9]
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
            VALUES (%s, %s, %s, %s, %s, %s, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
        
        new_status = 0 if row[0] else 1
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
            CREATE TABLE IF NOT EXISTS AIPrompts (
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
        
        cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM AIPrompts ORDER BY prompt_type")
        rows = cursor.fetchall()
        
        # Если таблица пустая, инициализируем дефолтные промпты
        if not rows:
            default_prompts = get_default_ai_prompts()
            
            for prompt_type, prompt_text, description in default_prompts:
                cursor.execute("""
                    INSERT INTO AIPrompts (id, prompt_type, prompt_text, description)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (prompt_type) DO NOTHING
                """, (f"prompt_{prompt_type}", prompt_type, prompt_text, description))
            
            db.conn.commit()
            # Перечитываем после вставки
            cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM AIPrompts ORDER BY prompt_type")
            rows = cursor.fetchall()
        
        prompts = []
        for row in rows:
            if hasattr(row, 'keys'):
                row_type = row.get('prompt_type')
                row_text = row.get('prompt_text')
                row_desc = row.get('description')
                row_updated_at = row.get('updated_at')
                row_updated_by = row.get('updated_by')
            elif isinstance(row, dict):
                row_type = row.get('prompt_type')
                row_text = row.get('prompt_text')
                row_desc = row.get('description')
                row_updated_at = row.get('updated_at')
                row_updated_by = row.get('updated_by')
            else:
                row_type = row[0]
                row_text = row[1]
                row_desc = row[2]
                row_updated_at = row[3]
                row_updated_by = row[4]
            prompts.append({
                'type': row_type,
                'text': row_text,
                'description': row_desc,
                'updated_at': row_updated_at,
                'updated_by': row_updated_by
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
            UPDATE AIPrompts 
            SET prompt_text = %s, description = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE prompt_type = %s
        """, (prompt_text, description, user_data['user_id'], prompt_type))
        
        if cursor.rowcount == 0:
            # Если промпта нет, создаём его
            cursor.execute("""
                INSERT INTO AIPrompts (id, prompt_type, prompt_text, description, updated_by)
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
        cursor.execute("SELECT prompt_text FROM AIPrompts WHERE prompt_type = %s", (prompt_type,))
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
def _ensure_default_business_types(cursor):
    for type_key, label, description in get_default_business_types():
        cursor.execute(
            """
            INSERT INTO BusinessTypes (id, type_key, label, description)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (type_key) DO UPDATE
            SET label = EXCLUDED.label,
                description = COALESCE(BusinessTypes.description, EXCLUDED.description),
                updated_at = CURRENT_TIMESTAMP
            """,
            (f"bt_{type_key}", type_key, label, description),
        )


@app.route('/api/business-types', methods=['GET'])
def get_business_types_public():
    """Получить все активные типы бизнеса (для всех пользователей)"""
    try:
        def _row_get(row_obj, index, key, default=None):
            if row_obj is None:
                return default
            if hasattr(row_obj, "get"):
                return row_obj.get(key, default)
            if isinstance(row_obj, (tuple, list)):
                return row_obj[index] if len(row_obj) > index else default
            return default

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        _ensure_default_business_types(cursor)
        db.conn.commit()
        cursor.execute("""
            SELECT type_key, label
            FROM businesstypes
            WHERE COALESCE(LOWER(TRIM(is_active::text)), '1') IN ('1', 'true', 't', 'yes', 'on')
            ORDER BY label
        """)
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            types.append({
                'type_key': _row_get(row, 0, 'type_key'),
                'label': _row_get(row, 1, 'label')
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
        _ensure_default_business_types(cursor)
        db.conn.commit()
        cursor.execute("SELECT id, type_key, label, description, is_active FROM BusinessTypes ORDER BY label")
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            types.append({
                'id': row[0],
                'type_key': row[1],
                'label': row[2],
                'description': row[3],
                'is_active': bool(row[4])
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
            INSERT INTO BusinessTypes (id, type_key, label, description)
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
            UPDATE BusinessTypes 
            SET label = %s, description = %s, is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (label, description, 1 if is_active else 0, type_id))
        
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
            WHERE business_type_id = %s
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
                WHERE stage_id = %s
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
            WHERE business_type_id = %s
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
                WHERE stage_id = %s
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (stage_id, business_type_id, stage_number, title, description, goal, expected_result, duration, 1 if is_permanent else 0))
        
        # Добавляем задачи
        for task_idx, task_text in enumerate(tasks, 1):
            task_id = f"gt_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO GrowthTasks (id, stage_id, task_number, task_text)
                VALUES (%s, %s, %s, %s)
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
            SET stage_number = %s, title = %s, description = %s, goal = %s, expected_result = %s, duration = %s, is_permanent = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (stage_number, title, description, goal, expected_result, duration, 1 if is_permanent else 0, stage_id))
        
        # Удаляем старые задачи и добавляем новые
        cursor.execute("DELETE FROM GrowthTasks WHERE stage_id = %s", (stage_id,))
        for task_idx, task_text in enumerate(tasks, 1):
            task_id = f"gt_{uuid.uuid4().hex[:12]}"
            cursor.execute("""
                INSERT INTO GrowthTasks (id, stage_id, task_number, task_text)
                VALUES (%s, %s, %s, %s)
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
            WHERE b.id = %s
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
        login_url = "https://localhost/login"
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
        
        # Проверяем наличие колонок subscription_tier и subscription_status (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'businesses'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        
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
                WHERE id = %s
            """, (business_id,))
            message = "Промо тариф установлен"
        else:
            # Отключаем промо тариф (возвращаем к trial или basic)
            cursor.execute("""
                UPDATE Businesses 
                SET subscription_tier = 'trial',
                    subscription_status = 'inactive',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
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
        cursor = db.conn.cursor()

        # Получаем бизнес
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        business_owner_id = business.get("owner_id")

        # Проверяем доступ (владелец бизнеса или суперадмин)
        user_id = user_data.get('user_id') or user_data.get('id')
        if business_owner_id != user_id and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Резолвим сеть:
        # 1) бизнес уже привязан к сети через businesses.network_id (обычная точка сети)
        # 2) business_id совпадает с id сети (legacy кейс "мастер-аккаунт")
        # ВАЖНО: не используем fallback по owner_id -> "самая большая сеть",
        # иначе отдельные бизнесы владельца ошибочно становятся "сетевыми".
        direct_network_id = business.get('network_id')
        network_id = direct_network_id
        is_network_master = False

        if not network_id:
            cursor.execute("SELECT id FROM networks WHERE id = %s LIMIT 1", (business_id,))
            row = cursor.fetchone()
            if row:
                network_id = row[0] if not hasattr(row, "keys") else row.get("id")
                is_network_master = True

        if not network_id:
            db.close()
            return jsonify({"success": True, "is_network": False, "locations": []})

        locations = db.get_businesses_by_network(network_id)

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
        db.close()

        return jsonify(
            {
                "success": True,
                # Признак "сетевой аккаунт" для UI-блокировок:
                # только legacy-мастер сети (business_id == network_id), а не обычная точка.
                "is_network": bool(is_network_master),
                "is_network_master": bool(is_network_master),
                "is_network_member": bool(direct_network_id),
                "network_id": network_id,
                "locations": normalized_locations,
            }
        )
        
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
                    SET data = %s, completed = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = %s
                """, (json.dumps(wizard_data, ensure_ascii=False), business_id))
            else:
                # Создаем новую запись
                wizard_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO BusinessOptimizationWizard (id, business_id, step, data, completed)
                    VALUES (%s, %s, 3, %s, 1)
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
                WHERE business_id = %s 
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
                WHERE business_id = %s AND completed = 1
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
            
            # Сохраняем спринт (обновляем существующий спринт недели, если есть)
            cursor.execute("""
                SELECT id FROM BusinessSprints
                WHERE business_id = %s AND week_start = %s
                ORDER BY updated_at DESC
                LIMIT 1
            """, (business_id, week_start.isoformat()))
            existing = cursor.fetchone()
            sprint_id = (existing[0] if isinstance(existing, (list, tuple)) else existing.get("id")) if existing else str(uuid.uuid4())
            if existing:
                cursor.execute("""
                    UPDATE BusinessSprints
                    SET tasks = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (json.dumps(tasks, ensure_ascii=False), sprint_id))
            else:
                cursor.execute("""
                    INSERT INTO BusinessSprints (id, business_id, week_start, tasks, updated_at)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
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
                WHERE business_id = %s AND week_start = %s
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
            WHERE business_id = %s
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

        # Обновляем каноническую ссылку в businesses + org_id в externalbusinessaccounts.external_id
        org_id = extract_yandex_org_id_from_url(yandex_url)

        cursor.execute(
            """
            UPDATE businesses
            SET yandex_url = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (yandex_url, business_id),
        )

        cursor.execute(
            """
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND source IN ('yandex_business', 'yandex')
            ORDER BY created_at ASC
            LIMIT 1
            FOR UPDATE
            """,
            (business_id,),
        )
        existing_account = cursor.fetchone()
        existing_account_dict = _row_to_dict(cursor, existing_account) if existing_account else None
        account_id = existing_account_dict.get("id") if existing_account_dict else None

        if account_id:
            cursor.execute(
                """
                UPDATE externalbusinessaccounts
                SET external_id = %s,
                    is_active = TRUE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (org_id, account_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO externalbusinessaccounts (
                    id, business_id, source, external_id, display_name, is_active, created_at, updated_at
                )
                VALUES (%s, %s, 'yandex_business', %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (str(uuid.uuid4()), business_id, org_id, "Yandex Business"),
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
            INSERT INTO BusinessProfiles
            (id, business_id, contact_name, contact_phone, contact_email, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                business_id = EXCLUDED.business_id,
                contact_name = EXCLUDED.contact_name,
                contact_phone = EXCLUDED.contact_phone,
                contact_email = EXCLUDED.contact_email,
                updated_at = CURRENT_TIMESTAMP
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


def send_email(to_email, subject, body, from_name="BeautyBot"):
    """Универсальная функция для отправки email"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Настройки SMTP из .env
        smtp_server = os.getenv("SMTP_SERVER", "mail.hosting.reg.ru")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "info@localhost")
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
    contact_email = os.getenv("CONTACT_EMAIL", "info@localhost")
    
    subject = f"Новое сообщение с сайта BeautyBot от {name}"
    body = f"""
Новое сообщение с сайта BeautyBot

Имя: {name}
Email: {email}
Телефон: {phone if phone else 'Не указан'}

Сообщение:
{message}

---
Отправлено с сайта localhost
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
        cursor.execute("SELECT id, name FROM Users WHERE email = %s", (email,))
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
            SET reset_token = %s, reset_token_expires = %s 
            WHERE email = %s
        """, (reset_token, expires_at.isoformat(), email))
        conn.commit()
        conn.close()
        
        # Отправляем email с токеном
        print(f"🔑 Токен восстановления для {email}: {reset_token}")
        print(f"⏰ Действителен до: {expires_at}")
        
        # Отправляем реальное письмо
        subject = "Восстановление пароля BeautyBot"
        body = f"""
Восстановление пароля для BeautyBot

Ваш токен восстановления: {reset_token}
Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}

Для сброса пароля перейдите по ссылке:
https://localhost/reset-password?token={reset_token}&email={email}

Если вы не запрашивали восстановление пароля, проигнорируйте это письмо.

---
BeautyBot
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
            WHERE email = %s AND reset_token = %s
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
            WHERE id = %s
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
    Принимает email и url, отправляет email на info@localhost о новой заявке.
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
        
        # Отправляем email на info@localhost о новой заявке
        contact_email = os.getenv("CONTACT_EMAIL", "info@localhost")
        subject = f"Новая заявка с сайта BeautyBot от {email}"
        body = f"""
Новая заявка с сайта BeautyBot

Email клиента: {email}
Ссылка на бизнес: {url}

---
Отправлено с сайта localhost
        """
        
        email_sent = send_email(contact_email, subject, body)
        if not email_sent:
            print("⚠️ Не удалось отправить email")
        
        # Логирование в консоль
        print(f"📧 НОВАЯ ЗАЯВКА ОТ {email}:")
        print(f"🔗 URL: {url}")
        print("-" * 50)
        
        return jsonify({
            "success": True,
            "message": "Заявка принята. Мы свяжемся с вами в ближайшее время."
        }), 200
        
    except Exception as e:
        print(f"❌ Ошибка обработки заявки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/request-registration', methods=['POST', 'OPTIONS'])
def public_request_registration():
    """Публичная заявка на регистрацию без авторизации.
    Принимает данные регистрации, отправляет email на info@localhost о новой заявке.
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
        
        # Отправляем email на info@localhost о новой заявке на регистрацию
        contact_email = os.getenv("CONTACT_EMAIL", "info@localhost")
        subject = f"Новая заявка на регистрацию от {email}"
        body = f"""
Новая заявка на регистрацию с сайта BeautyBot

Имя: {name or 'Не указано'}
Email: {email}
Телефон: {phone or 'Не указан'}
Ссылка на Яндекс.Карты: {yandex_url or 'Не указана'}

---
Отправлено с сайта localhost
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
        
        # Проверяем наличие поля business_id в TelegramBindTokens (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telegrambindtokens'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_business_id = 'business_id' in columns

        # Если поля нет, добавляем его
        if not has_business_id:
            cursor.execute("ALTER TABLE TelegramBindTokens ADD COLUMN business_id TEXT")
            db.conn.commit()
            has_business_id = True  # только что добавили
        
        # Удаляем старые неиспользованные токены для этого бизнеса
        if has_business_id:
            cursor.execute("""
                DELETE FROM TelegramBindTokens 
                WHERE business_id = %s AND used = 0 AND expires_at < %s
            """, (business_id, datetime.now().isoformat()))
        else:
            cursor.execute("""
                DELETE FROM TelegramBindTokens 
                WHERE user_id = %s AND used = 0 AND expires_at < %s
            """, (user_data['user_id'], datetime.now().isoformat()))
        
        # Создаем новый токен
        token_id = str(uuid.uuid4())
        if has_business_id:
            cursor.execute("""
                INSERT INTO TelegramBindTokens (id, user_id, business_id, token, expires_at, used, created_at)
                VALUES (%s, %s, %s, %s, %s, 0, %s)
            """, (token_id, user_data['user_id'], business_id, bind_token, expires_at.isoformat(), datetime.now().isoformat()))
        else:
            cursor.execute("""
                INSERT INTO TelegramBindTokens (id, user_id, token, expires_at, used, created_at)
                VALUES (%s, %s, %s, %s, 0, %s)
            """, (token_id, user_data['user_id'], bind_token, expires_at.isoformat(), datetime.now().isoformat()))
        
        db.conn.commit()
        db.close()
        
        return jsonify({
            "success": True,
            "token": bind_token,
            "expires_at": expires_at.isoformat(),
            "qr_data": f"https://t.me/BeautyBotPro_bot?start={bind_token}"
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
        
        # Проверяем наличие поля business_id в TelegramBindTokens (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telegrambindtokens'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_business_id = 'business_id' in columns

        # Проверяем, привязан ли Telegram для этого бизнеса
        is_linked = False
        user_row = None
        
        if has_business_id:
            # Проверяем, есть ли использованный токен для ЭТОГО КОНКРЕТНОГО бизнеса
            # Важно: проверяем только токены с business_id = текущему бизнесу
            # Токены с business_id = NULL или другим бизнесом не учитываются
            cursor.execute("""
                SELECT COUNT(*) as count FROM TelegramBindTokens 
                WHERE business_id = %s AND used = 1 AND user_id = %s
            """, (business_id, user_data['user_id']))
            result = cursor.fetchone()
            has_used_token_for_this_business = result[0] > 0 if result else False
            
            print(f"🔍 Проверка статуса Telegram для бизнеса {business_id}: has_used_token_for_this_business={has_used_token_for_this_business}")
            
            if has_used_token_for_this_business:
                # Проверяем, что у пользователя есть telegram_id
                cursor.execute("SELECT telegram_id FROM users WHERE id = %s", (user_data['user_id'],))
                user_row = cursor.fetchone()
                is_linked = user_row and user_row[0] is not None and user_row[0] != 'None' and user_row[0] != ''
                print(f"🔍 Telegram ID пользователя: {user_row[0] if user_row else None}, is_linked={is_linked}")
            else:
                # Нет использованного токена для этого бизнеса - не подключен
                is_linked = False
                user_row = None
                print(f"🔍 Нет использованного токена для бизнеса {business_id} - не подключен")
        else:
            # Старая логика: проверяем только привязку к пользователю
            cursor.execute("SELECT telegram_id FROM Users WHERE id = %s", (user_data['user_id'],))
            user_row = cursor.fetchone()
            is_linked = user_row and user_row[0] is not None and user_row[0] != 'None'
        
        db.close()
        
        return jsonify({
            "success": True,
            "is_linked": is_linked,
            "telegram_id": user_row[0] if is_linked and user_row else None
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
        
        # Проверяем токен (включая business_id) (PostgreSQL)
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'telegrambindtokens'
        """)
        columns = [r.get('column_name') if isinstance(r, dict) else r[0] for r in cursor.fetchall()]
        has_business_id = 'business_id' in columns

        if has_business_id:
            cursor.execute("""
                SELECT id, user_id, business_id, expires_at, used
                FROM TelegramBindTokens
                WHERE token = %s
            """, (bind_token,))
            token_row = cursor.fetchone()
            if token_row:
                token_id, user_id, business_id_from_token, expires_at, used = token_row
            else:
                token_row = None
        else:
            cursor.execute("""
                SELECT id, user_id, expires_at, used
                FROM TelegramBindTokens
                WHERE token = %s
            """, (bind_token,))
            token_row = cursor.fetchone()
            if token_row:
                token_id, user_id, expires_at, used = token_row
                business_id_from_token = None
            else:
                token_row = None
        
        if not token_row:
            db.close()
            return jsonify({"error": "Токен не найден"}), 404
        
        # Проверяем срок действия
        from datetime import datetime
        if datetime.fromisoformat(expires_at) < datetime.now():
            db.close()
            return jsonify({"error": "Токен истек"}), 400
        
        # Проверяем, не использован ли уже
        if used:
            db.close()
            return jsonify({"error": "Токен уже использован"}), 400
        
        # Проверяем, не привязан ли уже этот Telegram к другому аккаунту
        cursor.execute("SELECT id FROM Users WHERE telegram_id = %s AND id != %s", (telegram_id, user_id))
        existing_user = cursor.fetchone()
        if existing_user:
            db.close()
            return jsonify({"error": "Этот Telegram уже привязан к другому аккаунту"}), 400
        
        # Привязываем Telegram к аккаунту
        cursor.execute("""
            UPDATE Users 
            SET telegram_id = %s, updated_at = %s
            WHERE id = %s
        """, (telegram_id, datetime.now().isoformat(), user_id))
        
        # Помечаем токен как использованный
        # Если у токена был business_id, сохраняем его при обновлении
        if has_business_id and business_id_from_token:
            cursor.execute("""
                UPDATE TelegramBindTokens
                SET used = 1, business_id = %s
                WHERE id = %s
            """, (business_id_from_token, token_id))
        else:
            cursor.execute("""
                UPDATE TelegramBindTokens
                SET used = 1
                WHERE id = %s
            """, (token_id,))
        
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
            print("⚠️ Не удалось отправить email, но сообщение сохранено в логах")
        
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
        cursor.execute("SELECT * FROM Cards WHERE id = %s", (normalized_id,))
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
        cursor.execute("SELECT * FROM Cards WHERE id = %s", (normalized_id,))
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
        cursor.execute("SELECT * FROM Cards WHERE id = %s", (normalized_id,))
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

@app.errorhandler(Exception)
def handle_exception(e):
    """Глобальный обработчик исключений"""
    import traceback
    print(f"🚨 ГЛОБАЛЬНАЯ ОШИБКА: {str(e)}")
    print(f"🚨 ТРАССИРОВКА: {traceback.format_exc()}")
    return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500

if __name__ == "__main__":
    # Runtime строго Postgres-only: подключаемся только через pg_db_utils.
    from pg_db_utils import log_connection_info

    log_connection_info(prefix="BACKEND")

    print("SEO анализатор запущен на порту 8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
