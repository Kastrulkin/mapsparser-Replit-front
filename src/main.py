"""
main.py — Веб-сервер для SEO-анализатора Яндекс.Карт
"""
import os
import sys
import json
import sqlite3
import uuid
import base64
import random
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
    # Если FLASK_ENV=test|testing — используем .env.test, иначе обычный .env
    env_file = ".env.test" if os.getenv("FLASK_ENV", "").lower() in ("test", "testing") else ".env"
    load_dotenv(env_file)
except ImportError:
    print('Внимание: для автоматической загрузки .env установите пакет python-dotenv')

app = Flask(__name__)

# Настройка CORS для продакшена и разработки
# В .env укажите: ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')
allowed_origins = [origin.strip() for origin in allowed_origins if origin.strip()]
CORS(app, supports_credentials=True, origins=allowed_origins)

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


@app.route('/')
def index():
    """Главная страница — раздаём собранный SPA"""
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
        
        # Проверяем, существует ли таблица TokenUsage
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='TokenUsage'
        """)
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
            where_conditions.append("status = ?")
            params.append(status_filter)
        
        if task_type_filter:
            where_conditions.append("task_type = ?")
            params.append(task_type_filter)
        
        if source_filter:
            where_conditions.append("source = ?")
            params.append(source_filter)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Получаем задачи
        cursor.execute(f"""
            SELECT 
                id, url, user_id, business_id, task_type, account_id, source,
                status, retry_after, error_message, created_at, updated_at
            FROM ParseQueue
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, params + [limit, offset])
        
        rows = cursor.fetchall()
        
        # Получаем общее количество
        cursor.execute(f"""
            SELECT COUNT(*) FROM ParseQueue WHERE {where_clause}
        """, params)
        total = cursor.fetchone()[0]
        
        # Получаем статистику по статусам
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM ParseQueue
            GROUP BY status
        """)
        status_stats = {}
        for row in cursor.fetchall():
            status_stats[row[0]] = row[1]
        
        # Получаем информацию о бизнесах для отображения
        tasks = []
        for row in rows:
            task_dict = dict(row) if hasattr(row, 'keys') else {
                'id': row[0],
                'url': row[1],
                'user_id': row[2],
                'business_id': row[3],
                'task_type': row[4] or 'parse_card',
                'account_id': row[5],
                'source': row[6],
                'status': row[7],
                'retry_after': row[8],
                'error_message': row[9],
                'created_at': row[10],
                'updated_at': row[11] if len(row) > 11 else None
            }
            
            # Получаем название бизнеса
            if task_dict.get('business_id'):
                cursor.execute("SELECT name FROM Businesses WHERE id = ?", (task_dict['business_id'],))
                business_row = cursor.fetchone()
                task_dict['business_name'] = business_row[0] if business_row else None
            else:
                task_dict['business_name'] = None
            
            tasks.append(task_dict)
        
        db.close()
        
        return jsonify({
            "success": True,
            "tasks": tasks,
            "total": total,
            "stats": status_stats
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения задач парсинга: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
        cursor.execute("SELECT id, status FROM ParseQueue WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        
        if not task:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404
        
        if isinstance(task, dict):
            current_status = task.get('status')
        else:
             # tuple or sqlite3.Row
            current_status = task[1]
        
        # Перезапускаем задачу (сбрасываем статус на pending)
        cursor.execute("""
            UPDATE ParseQueue
            SET status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
        
        cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (task_id,))
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
        
        # Получаем задачу
        cursor.execute("""
            SELECT id, business_id, task_type, status 
            FROM ParseQueue 
            WHERE id = ?
        """, (task_id,))
        task = cursor.fetchone()
        
        if not task:
            db.close()
            return jsonify({"error": "Задача не найдена"}), 404
        
        task_dict = dict(task) if hasattr(task, 'keys') else {
            'id': task[0],
            'business_id': task[1],
            'task_type': task[2],
            'status': task[3]
        }
        
        business_id = task_dict.get('business_id')
        if not business_id:
            db.close()
            return jsonify({"error": "У задачи нет business_id"}), 400
        
        # Проверяем, что задача еще не синхронизация
        if task_dict.get('task_type') == 'sync_yandex_business':
            db.close()
            return jsonify({"error": "Задача уже является синхронизацией"}), 400
        
        # Ищем аккаунт Яндекс.Бизнес для этого бизнеса
        cursor.execute("""
            SELECT id 
            FROM ExternalBusinessAccounts 
            WHERE business_id = ? 
              AND source = 'yandex_business' 
              AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        account_row = cursor.fetchone()
        
        if not account_row:
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден активный аккаунт Яндекс.Бизнес",
                "message": "Добавьте аккаунт Яндекс.Бизнес в настройках внешних интеграций"
            }), 400
        
        if isinstance(account_row, dict):
            account_id = account_row.get('id')
        else:
            # tuple or sqlite3.Row (supports index access)
            account_id = account_row[0]
        
        # Обновляем задачу на синхронизацию
        cursor.execute("""
            UPDATE ParseQueue
            SET task_type = 'sync_yandex_business',
                account_id = ?,
                source = 'yandex_business',
                status = 'pending',
                error_message = NULL,
                retry_after = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM ParseQueue")
        total_tasks = cursor.fetchone()[0]
        
        # По статусам
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM ParseQueue
            GROUP BY status
        """)
        by_status = {}
        for row in cursor.fetchall():
            by_status[row[0]] = row[1]
        
        # По типам задач
        cursor.execute("""
            SELECT task_type, COUNT(*) as count
            FROM ParseQueue
            GROUP BY task_type
        """)
        by_task_type = {}
        for row in cursor.fetchall():
            task_type = row[0] or 'parse_card'
            by_task_type[task_type] = row[1]
        
        # По источникам
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM ParseQueue
            WHERE source IS NOT NULL
            GROUP BY source
        """)
        by_source = {}
        for row in cursor.fetchall():
            by_source[row[0]] = row[1]
        
        # Зависшие задачи (processing более 30 минут)
        # Проверяем наличие колонки updated_at
        cursor.execute("PRAGMA table_info(ParseQueue)")
        columns = [row[1] for row in cursor.fetchall()]
        has_updated_at = 'updated_at' in columns
        
        if has_updated_at:
            cursor.execute("""
                SELECT id, business_id, task_type, created_at, updated_at
                FROM ParseQueue
                WHERE status = 'processing'
                  AND updated_at < datetime('now', '-30 minutes')
            """)
        else:
            cursor.execute("""
                SELECT id, business_id, task_type, created_at, created_at as updated_at
                FROM ParseQueue
                WHERE status = 'processing'
                  AND created_at < datetime('now', '-30 minutes')
            """)
        
        stuck_tasks = []
        for row in cursor.fetchall():
            stuck_tasks.append({
                'id': row[0],
                'business_id': row[1],
                'task_type': row[2] or 'parse_card',
                'created_at': row[3],
                'updated_at': row[4] if len(row) > 4 else row[3]
            })
        
        db.close()
        
        return jsonify({
            "success": True,
            "stats": {
                "total_tasks": total_tasks,
                "by_status": by_status,
                "by_task_type": by_task_type,
                "by_source": by_source,
                "stuck_tasks_count": len(stuck_tasks),
                "stuck_tasks": stuck_tasks
            }
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения статистики парсинга: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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

        # Проверяем, существует ли таблица ExternalBusinessAccounts
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ExternalBusinessAccounts'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Таблица не существует - возвращаем пустой список
            db.close()
            return jsonify({"success": True, "accounts": []})

        cursor.execute(
            """
            SELECT id, source, external_id, display_name, is_active,
                   last_sync_at, last_error, created_at, updated_at
            FROM ExternalBusinessAccounts
            WHERE business_id = ?
            ORDER BY source, created_at DESC
            """,
            (business_id,),
        )
        rows = cursor.fetchall()
        db.close()

        accounts = []
        for r in rows:
            accounts.append(
                {
                    "id": r[0],
                    "source": r[1],
                    "external_id": r[2],
                    "display_name": r[3],
                    "is_active": r[4],
                    "last_sync_at": r[5],
                    "last_error": r[6],
                    "created_at": r[7],
                    "updated_at": r[8],
                }
            )

        return jsonify({"success": True, "accounts": accounts})

    except Exception as e:
        print(f"❌ Ошибка получения внешних аккаунтов: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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
        auth_data = (data.get("auth_data") or "").strip() or None
        is_active = data.get("is_active", True)

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

        # Проверяем, существует ли таблица ExternalBusinessAccounts
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ExternalBusinessAccounts'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Таблица не существует - нужно применить миграцию
            db.close()
            return jsonify({
                "error": "Таблица ExternalBusinessAccounts не существует. Необходимо применить миграцию migrate_external_sources.py"
            }), 500

        import uuid
        from datetime import datetime
        from auth_encryption import encrypt_auth_data

        # Логирование для отладки
        print(f"🔍 POST /api/business/{business_id}/external-accounts:")
        print(f"   source={source}, external_id={external_id}, display_name={display_name}")
        print(f"   auth_data length={len(auth_data) if auth_data else 0}")

        # Шифруем auth_data перед сохранением
        auth_data_encrypted = None
        if auth_data:
            try:
                auth_data_encrypted = encrypt_auth_data(auth_data)
                print(f"✅ auth_data зашифрован, длина={len(auth_data_encrypted)}")
            except Exception as e:
                print(f"❌ Ошибка шифрования auth_data: {e}")
                import traceback
                traceback.print_exc()
                db.close()
                return jsonify({"error": f"Ошибка шифрования данных: {str(e)}"}), 500

        # Для простоты: один активный аккаунт на source + business
        cursor.execute(
            """
            SELECT id FROM ExternalBusinessAccounts
            WHERE business_id = ? AND source = ?
            """,
            (business_id, source),
        )
        existing = cursor.fetchone()
        print(f"🔍 Существующий аккаунт: {existing[0] if existing else 'не найден'}")

        now = datetime.utcnow().isoformat()

        if existing:
            account_id = existing[0]
            print(f"🔄 Обновление существующего аккаунта: {account_id}")
            # Если auth_data не передан, не обновляем его (сохраняем существующий)
            if auth_data_encrypted is not None:
                cursor.execute(
                    """
                    UPDATE ExternalBusinessAccounts
                    SET external_id = ?, display_name = ?, 
                        auth_data_encrypted = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        external_id,
                        display_name,
                        auth_data_encrypted,
                        1 if is_active else 0,
                        now,
                        account_id,
                    ),
                )
                print(f"✅ Аккаунт обновлен с auth_data: external_id={external_id}, display_name={display_name}")
            else:
                # Обновляем только другие поля, не трогая auth_data_encrypted
                cursor.execute(
                    """
                    UPDATE ExternalBusinessAccounts
                    SET external_id = ?, display_name = ?, 
                        is_active = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        external_id,
                        display_name,
                        1 if is_active else 0,
                        now,
                        account_id,
                    ),
                )
                print(f"✅ Аккаунт обновлен без auth_data: external_id={external_id}, display_name={display_name}")
        else:
            # При создании нового аккаунта auth_data обязателен
            if not auth_data_encrypted:
                db.close()
                return jsonify({"error": "auth_data обязателен для нового аккаунта"}), 400
            
            account_id = str(uuid.uuid4())
            print(f"🆕 Создание нового аккаунта: {account_id}")
            cursor.execute(
                """
                INSERT INTO ExternalBusinessAccounts (
                    id, business_id, source, external_id, display_name,
                    auth_data_encrypted, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    business_id,
                    source,
                    external_id,
                    display_name,
                    auth_data_encrypted,
                    1 if is_active else 0,
                    now,
                    now,
                ),
            )
            print(f"✅ Аккаунт создан: id={account_id}, external_id={external_id}, display_name={display_name}")

        db.conn.commit()
        print(f"✅ Изменения закоммичены в БД")
        db.close()

        return jsonify({"success": True, "account_id": account_id})

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
            "SELECT business_id FROM ExternalBusinessAccounts WHERE id = ?", (account_id,)
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
            UPDATE ExternalBusinessAccounts
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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

        # Проверяем, существует ли таблица ExternalBusinessReviews
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ExternalBusinessReviews'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Таблица не существует - возвращаем пустой список
            db.close()
            return jsonify({"success": True, "reviews": []})

        # Получаем все отзывы для этого бизнеса, отсортированные по дате публикации (новые сначала)
        cursor.execute(
            """
            SELECT id, source, external_review_id, rating, author_name, text,
                   response_text, response_at, published_at, created_at
            FROM ExternalBusinessReviews
            WHERE business_id = ?
            ORDER BY COALESCE(published_at, created_at) DESC, created_at DESC
            """,
            (business_id,),
        )
        rows = cursor.fetchall()
        db.close()

        reviews = []
        for r in rows:
            reviews.append({
                "id": r[0],
                "source": r[1],
                "external_review_id": r[2],
                "rating": r[3],
                "author_name": r[4] or "Анонимный пользователь",
                "text": r[5] or "",
                "response_text": r[6],
                "response_at": r[7],
                "published_at": r[8],
                "created_at": r[9],
                "has_response": bool(r[6]),  # Есть ли ответ организации
            })

        return jsonify({
            "success": True,
            "reviews": reviews,
            "total": len(reviews),
            "with_response": sum(1 for r in reviews if r["has_response"]),
            "without_response": sum(1 for r in reviews if not r["has_response"]),
        })

    except Exception as e:
        print(f"❌ Ошибка получения внешних отзывов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

        # Проверяем, существуют ли таблицы
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name IN ('ExternalBusinessStats', 'ExternalBusinessReviews')
        """)
        tables = {row[0] for row in cursor.fetchall()}
        
        if 'ExternalBusinessStats' not in tables or 'ExternalBusinessReviews' not in tables:
            # Таблицы не существуют - возвращаем пустую статистику
            db.close()
            return jsonify({
                "success": True,
                "rating": None,
                "reviews_total": 0,
                "reviews_with_response": 0,
                "reviews_without_response": 0,
                "last_update": None
            })

        # Получаем последнюю статистику
        cursor.execute(
            """
            SELECT rating, reviews_total, date
            FROM ExternalBusinessStats
            WHERE business_id = ? AND source = 'yandex_business'
            ORDER BY date DESC
            LIMIT 1
            """,
            (business_id,),
        )
        stats_row = cursor.fetchone()
        
        # Получаем количество отзывов
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN response_text IS NOT NULL THEN 1 ELSE 0 END) as with_response,
                   SUM(CASE WHEN response_text IS NULL THEN 1 ELSE 0 END) as without_response
            FROM ExternalBusinessReviews
            WHERE business_id = ? AND source = 'yandex_business'
            """,
            (business_id,),
        )
        reviews_row = cursor.fetchone()
        
        db.close()

        rating = stats_row[0] if stats_row else None
        reviews_total = stats_row[1] if stats_row else (reviews_row[0] if reviews_row else 0)
        reviews_with_response = reviews_row[1] if reviews_row else 0
        reviews_without_response = reviews_row[2] if reviews_row else 0

        return jsonify({
            "success": True,
            "rating": float(rating) if rating else None,
            "reviews_total": reviews_total,
            "reviews_with_response": reviews_with_response,
            "reviews_without_response": reviews_without_response,
            "last_sync_date": stats_row[2] if stats_row else None,
        })

    except Exception as e:
        print(f"❌ Ошибка получения сводки внешних данных: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


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

        # Проверяем, существует ли таблица ExternalBusinessPosts
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ExternalBusinessPosts'
        """)
        table_exists = cursor.fetchone()
        
        if not table_exists:
            # Таблица не существует - возвращаем пустой список
            db.close()
            return jsonify({"success": True, "posts": []})

        # Получаем все посты, исключая некорректные (метаданные)
        cursor.execute(
            """
            SELECT id, source, external_post_id, title, text, published_at, created_at
            FROM ExternalBusinessPosts
            WHERE business_id = ?
            AND title NOT IN ('working_intervals', 'urls', 'phone', 'photos', 'price_lists', 'logo', 'features', 'english_name')
            AND (title IS NOT NULL OR text IS NOT NULL)
            AND (title != '' OR text != '')
            ORDER BY COALESCE(published_at, created_at) DESC, created_at DESC
            """,
            (business_id,),
        )
        rows = cursor.fetchall()
        db.close()

        posts = []
        for r in rows:
            # Дополнительная проверка - пропускаем метаданные
            title = r[3] or ""
            text = r[4] or ""
            metadata_titles = ["working_intervals", "urls", "phone", "photos", "price_lists", "logo", "features", "english_name"]
            
            if title in metadata_titles or (not title and not text):
                continue  # Пропускаем метаданные
            
            posts.append({
                "id": r[0],
                "source": r[1],
                "external_post_id": r[2],
                "title": title,
                "text": text,
                "published_at": r[5],
                "created_at": r[6],
            })

        return jsonify({
            "success": True,
            "posts": posts,
            "total": len(posts),
        })

    except Exception as e:
        print(f"❌ Ошибка получения внешних постов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
        cursor.execute("SELECT id, email FROM Users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404
        
        # Удаляем пользователя (каскадное удаление удалит все связанные данные)
        cursor.execute("DELETE FROM Users WHERE id = ?", (user_id,))
        
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
        cursor.execute("SELECT id, email, is_active FROM Users WHERE id = ?", (user_id,))
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
        cursor.execute("SELECT id FROM Users WHERE id = ?", (user_id,))
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

    # Иначе — SPA индекс
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
            FROM Businesses 
            WHERE owner_id = ? AND (is_active = 1 OR is_active IS NULL)
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        db.close()
        
        if row and row[0]:
            return row[0].lower()
    except Exception as e:
        print(f"⚠️ Ошибка получения языка пользователя: {e}")
    
    # Fallback на русский, если ничего не найдено
    return 'ru'

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

        tone = request.form.get('tone') or request.json.get('tone') if request.is_json else None
        instructions = request.form.get('instructions') or (request.json.get('instructions') if request.is_json else None)
        region = request.form.get('region') or (request.json.get('region') if request.is_json else None)
        business_name = request.form.get('business_name') or (request.json.get('business_name') if request.is_json else None)
        length = request.form.get('description_length') or (request.json.get('description_length') if request.is_json else 150)

        # Язык результата: получаем из запроса или из профиля пользователя
        requested_language = request.form.get('language') or (request.json.get('language') if request.is_json else None)
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
                business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
                result = analyze_screenshot_with_gigachat(
                    image_base64, 
                    screenshot_prompt,
                    task_type="service_optimization",
                    business_id=business_id,
                    user_id=user_data['user_id']
                )
                print(f"🔍 Результат анализа скриншота: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'not dict'}")
            else:
                # Для документов - анализ текста
                content = file.read().decode('utf-8', errors='ignore')
        else:
            data = request.get_json(silent=True) or {}
            content = (data.get('text') or '').strip()

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
                    cur.execute("SELECT example_text FROM UserExamples WHERE user_id = ? AND example_type = 'service' ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
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
                user_prompt = user_prompt.replace('{instructions}', str(instructions or '—'))
                user_prompt = user_prompt.replace('{frequent_queries}', str(frequent_queries))
                user_prompt = user_prompt.replace('{good_examples}', str(good_examples))
                user_prompt = user_prompt.replace('{content}', str(content[:4000]))
                
                # Объединяем system и user промпты
                prompt = f"{system_prompt}\n\n{user_prompt}"
                
            except FileNotFoundError:
                # Fallback на старый промпт
                default_prompt_template = """Ты — SEO-специалист для бьюти-индустрии. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
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
                    .replace('{instructions}', str(instructions or '—'))
                    .replace('{frequent_queries}', str(frequent_queries))
                    .replace('{content}', str(content[:4000]))
                )

            business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
            result = analyze_text_with_gigachat(
                prompt, 
                task_type="service_optimization",
                business_id=business_id,
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
            VALUES (?, ?, ?, ?, ?, ?)
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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = ? AND example_type = 'service' ORDER BY created_at DESC", (user_data['user_id'],))
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
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = ? AND example_type = 'service'", (user_data['user_id'],))
        count = cur.fetchone()[0]
        if count >= 5:
            db.close()
            return jsonify({"error": "Максимум 5 примеров"}), 400
        example_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (?, ?, 'service', ?)", (example_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = ? AND user_id = ? AND example_type = 'service'", (example_id, user_data['user_id']))
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

        service_context = ''
        transaction_context = ''
        
        if use_service:
            if selected_service_id:
                cur.execute("SELECT name, description FROM UserServices WHERE id = ? AND user_id = ?", (selected_service_id, user_data['user_id']))
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"
            else:
                # выбрать случайную услугу пользователя
                cur.execute("SELECT name, description FROM UserServices WHERE user_id = ? ORDER BY RANDOM() LIMIT 1", (user_data['user_id'],))
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
                    WHERE id = ? AND user_id = ?
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
                    WHERE user_id = ?
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
            cur.execute("SELECT example_text FROM UserExamples WHERE user_id = ? AND example_type = 'news' ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
            r = cur.fetchall()
            ex = [row[0] if isinstance(row, tuple) else row['example_text'] for row in r]
            if ex:
                news_examples = "\n".join(ex)
        except Exception:
            news_examples = ""

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt = """Ты — маркетолог для локального бизнеса. Сгенерируй новость для публикации на картах (Google, Яндекс).
Требования: до 1500 символов, можно использовать 2-3 эмодзи (не переборщи), без хештегов, без оценочных суждений, без упоминания конкурентов. Стиль — информативный и дружелюбный.
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

        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
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
        cur.execute(
            """
            INSERT INTO UserNews (id, user_id, service_id, source_text, generated_text)
            VALUES (?, ?, ?, ?, ?)
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
        cur.execute("UPDATE UserNews SET approved = 1 WHERE id = ? AND user_id = ?", (news_id, user_data['user_id']))
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
        cur.execute("SELECT id, service_id, source_text, generated_text, approved, created_at FROM UserNews WHERE user_id = ? ORDER BY created_at DESC", (user_data['user_id'],))
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
        cur.execute("UPDATE UserNews SET generated_text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?", (text, news_id, user_data['user_id']))
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
        cur.execute("DELETE FROM UserNews WHERE id = ? AND user_id = ?", (news_id, user_data['user_id']))
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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = ? AND example_type = 'review' ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = ? AND example_type = 'review'", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (?, ?, 'review', ?)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = ? AND user_id = ? AND example_type = 'review'", (example_id, user_data['user_id']))
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
            cur.execute("SELECT id, example_text, created_at FROM UserExamples WHERE user_id = ? AND example_type = 'news' ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserExamples WHERE user_id = ? AND example_type = 'news'", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserExamples (id, user_id, example_type, example_text) VALUES (?, ?, 'news', ?)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserExamples WHERE id = ? AND user_id = ? AND example_type = 'news'", (example_id, user_data['user_id']))
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
                cur.execute("SELECT example_text FROM UserExamples WHERE user_id = ? AND example_type = 'review' ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
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

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt_template = """Ты — вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Write the reply in {language_name}.
Если уместно, ориентируйся на стиль этих примеров (если они есть):
{examples_text}
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text}"""
        
        prompt_template = get_prompt_from_db('review_reply', default_prompt_template)
        
        # Логируем тип и значение prompt_template
        print(f"🔍 DEBUG reviews_reply: prompt_template type = {type(prompt_template)}", flush=True)
        print(f"🔍 DEBUG reviews_reply: prompt_template (первые 200 символов) = {str(prompt_template)[:200] if prompt_template else 'None'}", flush=True)
        
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
                review_text=review_text_str
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
                review_text=review_text_str
            )
        # Логируем промпт для отладки
        print(f"🔍 DEBUG reviews_reply: prompt (первые 500 символов) = {prompt[:500]}")
        print(f"🔍 DEBUG reviews_reply: review_text = {review_text[:200] if review_text else 'ПУСТО'}")
        print(f"🔍 DEBUG reviews_reply: examples_text (первые 200 символов) = {examples_text[:200] if examples_text else 'ПУСТО'}")
        
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
            INSERT OR REPLACE INTO UserReviewReplies 
            (id, user_id, reply_text, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
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

        # Проверяем, есть ли поле business_id в таблице UserServices
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'business_id' in columns and business_id:
            cursor.execute("""
                INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (service_id, user_id, business_id, category, name, description, json.dumps(keywords), price))
        else:
            cursor.execute("""
                INSERT INTO UserServices (id, user_id, category, name, description, keywords, price, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (service_id, user_id, category, name, description, json.dumps(keywords), price))

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга добавлена"})

    except Exception as e:
        print(f"❌ Ошибка добавления услуги: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/list', methods=['GET', 'OPTIONS'])
def get_services():
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
                    cursor.execute("PRAGMA table_info(UserServices)")
                    columns = [col[1] for col in cursor.fetchall()]
                    has_optimized_desc = 'optimized_description' in columns
                    has_optimized_name = 'optimized_name' in columns
                    
                    # Формируем SELECT с учетом наличия полей
                    select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
                    if has_optimized_desc:
                        select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                    if has_optimized_name:
                        select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
                    
                    select_sql = f"SELECT {', '.join(select_fields)} FROM UserServices WHERE business_id = ? ORDER BY created_at DESC"
                    print(f"🔍 DEBUG get_services: SQL запрос = {select_sql}", flush=True)
                    print(f"🔍 DEBUG get_services: select_fields = {select_fields}", flush=True)
                    print(f"🔍 DEBUG get_services: has_optimized_name = {has_optimized_name}, has_optimized_desc = {has_optimized_desc}", flush=True)
                    
                    cursor.execute(select_sql, (business_id,))
                else:
                    db.close()
                    return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            else:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
        else:
            # Старая логика для обратной совместимости
            # Проверяем, есть ли поля optimized_description и optimized_name
            cursor.execute("PRAGMA table_info(UserServices)")
            columns = [col[1] for col in cursor.fetchall()]
            has_optimized_desc = 'optimized_description' in columns
            has_optimized_name = 'optimized_name' in columns
            
            # Формируем SELECT с учетом наличия полей
            select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
            if has_optimized_desc:
                select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
            if has_optimized_name:
                select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
            
            select_sql = f"SELECT {', '.join(select_fields)} FROM UserServices WHERE user_id = ? ORDER BY created_at DESC"
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
                cursor_temp.execute("PRAGMA table_info(UserServices)")
                columns = [col[1] for col in cursor_temp.fetchall()]
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
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [col[1] for col in cursor.fetchall()]
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns
        
        optimized_name = data.get('optimized_name', '')
        
        print(f"🔍 DEBUG update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG update_service: columns = {columns}", flush=True)
        print(f"🔍 DEBUG update_service: optimized_name = '{optimized_name}' (type: {type(optimized_name)}, length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG update_service: optimized_description = '{optimized_description[:100] if optimized_description else ''}...' (type: {type(optimized_description)}, length: {len(optimized_description) if optimized_description else 0})", flush=True)
        
        try:
            if has_optimized_description and has_optimized_name:
                print(f"🔍 DEBUG update_service: Обновление с optimized_description и optimized_name", flush=True)
                cursor.execute("""
                    UPDATE UserServices SET
                    category = ?, name = ?, optimized_name = ?, description = ?, optimized_description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                """, (category, name, optimized_name, description, optimized_description, keywords_str, price, service_id, user_id))
                print(f"✅ DEBUG update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)
                
                # Проверяем, что данные сохранились
                cursor.execute("SELECT optimized_name, optimized_description FROM UserServices WHERE id = ?", (service_id,))
                check_row = cursor.fetchone()
                if check_row:
                    print(f"✅ DEBUG update_service: Проверка после UPDATE - optimized_name = '{check_row[0]}', optimized_description = '{check_row[1][:50] if check_row[1] else ''}...'", flush=True)
                else:
                    print(f"❌ DEBUG update_service: Услуга не найдена после UPDATE!", flush=True)
            elif has_optimized_description:
                print(f"🔍 DEBUG update_service: Обновление с optimized_description", flush=True)
                cursor.execute("""
                    UPDATE UserServices SET
                    category = ?, name = ?, description = ?, optimized_description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                """, (category, name, description, optimized_description, keywords_str, price, service_id, user_id))
            elif has_optimized_name:
                print(f"🔍 DEBUG update_service: Обновление с optimized_name", flush=True)
                cursor.execute("""
                    UPDATE UserServices SET
                    category = ?, name = ?, optimized_name = ?, description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                """, (category, name, optimized_name, description, keywords_str, price, service_id, user_id))
            else:
                print(f"🔍 DEBUG update_service: Обновление без optimized полей (обратная совместимость)", flush=True)
                # Если полей нет - обновляем без них (для обратной совместимости)
                cursor.execute("""
                    UPDATE UserServices SET
                    category = ?, name = ?, description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND user_id = ?
                """, (category, name, description, keywords_str, price, service_id, user_id))
        except Exception as sql_err:
            print(f"❌ Ошибка SQL запроса: {sql_err}", flush=True)
            import traceback
            traceback.print_exc()
            db.close()
            raise

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
        cursor.execute("DELETE FROM UserServices WHERE id = ? AND user_id = ?", (service_id, user_id))

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

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Таблица для бизнес-профиля
        # Проверяем существование таблицы и её структуру
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ClientInfo'")
        table_exists = cursor.fetchone() is not None
        
        # #region agent log
        log_data = {
            "location": "src/main.py:2971",
            "message": "client-info: проверка существования таблицы",
            "data": {
                "table_exists": table_exists,
                "method": request.method
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "F"
        }
        try:
            with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except: pass
        # #endregion
        
        if not table_exists:
            # Создаем таблицу с правильной структурой
            cursor.execute("""
                CREATE TABLE ClientInfo (
                    user_id TEXT,
                    business_id TEXT,
                    business_name TEXT,
                    business_type TEXT,
                    address TEXT,
                    working_hours TEXT,
                    description TEXT,
                    services TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, business_id)
                )
            """)
            db.conn.commit()
        else:
            # Проверяем структуру существующей таблицы
            cursor.execute("PRAGMA table_info(ClientInfo)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Проверяем PRIMARY KEY
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ClientInfo'")
            table_sql = cursor.fetchone()
            has_composite_pk = table_sql and ("PRIMARY KEY (user_id, business_id)" in table_sql[0] or "PRIMARY KEY(user_id,business_id)" in table_sql[0])
            
            if 'business_id' not in columns or not has_composite_pk:
                # Нужна миграция
                print(f"⚠️ Миграция ClientInfo: business_id exists={('business_id' in columns)}, composite PK={has_composite_pk}")
                print(f"⚠️ Колонки таблицы: {columns}")
                # #region agent log
                log_data = {
                    "location": "src/main.py:3001",
                    "message": "client-info: начало миграции",
                    "data": {
                        "has_business_id": 'business_id' in columns,
                        "has_composite_pk": has_composite_pk,
                        "columns": columns
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "G"
                }
                try:
                    with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps(log_data) + '\n')
                except: pass
                # #endregion
                try:
                    # Сохраняем структуру колонок перед удалением таблицы
                    cursor.execute("PRAGMA table_info(ClientInfo)")
                    old_column_names = [col[1] for col in cursor.fetchall()]
                    
                    # Сохраняем данные
                    cursor.execute("SELECT * FROM ClientInfo")
                    existing_data = cursor.fetchall()
                    
                    # Удаляем старую таблицу
                    cursor.execute("DROP TABLE ClientInfo")
                    
                    # Создаем новую с правильной структурой
                    cursor.execute("""
                        CREATE TABLE ClientInfo (
                            user_id TEXT,
                            business_id TEXT,
                            business_name TEXT,
                            business_type TEXT,
                            address TEXT,
                            working_hours TEXT,
                            description TEXT,
                            services TEXT,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            PRIMARY KEY (user_id, business_id)
                        )
                    """)
                    
                    # Восстанавливаем данные с правильным маппингом колонок
                    restored_count = 0
                    for row in existing_data:
                        # Преобразуем row в словарь для удобства
                        row_dict = dict(zip(old_column_names, row))
                        
                        user_id = row_dict.get('user_id', '')
                        # Если business_id нет в старых данных, пытаемся найти его в таблице Businesses
                        business_id = row_dict.get('business_id')
                        if not business_id:
                            business_id = find_business_id_for_user(cursor, user_id)
                            if business_id == user_id:
                                print(f"⚠️ Не найден business_id для user_id={user_id}, используем user_id как fallback")
                        
                        cursor.execute("""
                            INSERT INTO ClientInfo (user_id, business_id, business_name, business_type, address, working_hours, description, services, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            user_id,
                            business_id,
                            row_dict.get('business_name', ''),
                            row_dict.get('business_type', ''),
                            row_dict.get('address', ''),
                            row_dict.get('working_hours', ''),
                            row_dict.get('description', ''),
                            row_dict.get('services', ''),
                            row_dict.get('updated_at', None)
                        ))
                        restored_count += 1
                    
                    db.conn.commit()
                    print(f"✅ Миграция ClientInfo выполнена успешно! Восстановлено записей: {restored_count}")
                    # #region agent log
                    log_data = {
                        "location": "src/main.py:3042",
                        "message": "client-info: миграция успешна",
                        "data": {
                            "migration_success": True
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "H"
                    }
                    try:
                        with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps(log_data) + '\n')
                    except: pass
                    # #endregion
                except Exception as e:
                    print(f"❌ Ошибка миграции ClientInfo: {e}")
                    import traceback
                    traceback.print_exc()
                    # #region agent log
                    log_data = {
                        "location": "src/main.py:3044",
                        "message": "client-info: ошибка миграции",
                        "data": {
                            "migration_success": False,
                            "error": str(e)
                        },
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "sessionId": "debug-session",
                        "runId": "run1",
                        "hypothesisId": "I"
                    }
                    try:
                        with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                            f.write(json.dumps(log_data) + '\n')
                    except: pass
                    # #endregion
                    # Если миграция не удалась, продолжаем работу

        # Таблица ссылок на карты (несколько на бизнес)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessMapLinks (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                business_id TEXT,
                url TEXT,
                map_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица результатов парсинга карт
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS MapParseResults (
                id TEXT PRIMARY KEY,
                business_id TEXT,
                url TEXT,
                map_type TEXT,
                rating TEXT,
                reviews_count INTEGER,
                news_count INTEGER,
                photos_count INTEGER,
                report_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        if request.method == 'GET':
            current_business_id = request.args.get('business_id')
            print(f"🔍 GET /api/client-info: method=GET, business_id={current_business_id}, user_id={user_id}")
            
            # Если передан business_id - берём данные из таблицы Businesses
            if current_business_id:
                print(f"🔍 GET /api/client-info: Ищу бизнес в таблице Businesses, business_id={current_business_id}")
                # Проверяем доступ к бизнесу
                cursor.execute("SELECT owner_id, name, business_type, address, working_hours FROM Businesses WHERE id = ? AND is_active = 1", (current_business_id,))
                business_row = cursor.fetchone()
                
                if business_row:
                    owner_id = business_row[0]
                    print(f"🔍 GET /api/client-info: Бизнес найден, owner_id={owner_id}, user_id={user_id}, is_superadmin={user_data.get('is_superadmin')}")
                    # Проверяем права доступа
                    if owner_id == user_id or user_data.get('is_superadmin'):
                        print(f"✅ GET /api/client-info: Доступ разрешен, возвращаю данные из Businesses")
                        # Получаем ссылки на карты для этого бизнеса
                        links = []
                        cursor.execute("""
                            SELECT id, url, map_type, created_at 
                            FROM BusinessMapLinks 
                            WHERE business_id = ? 
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        link_rows = cursor.fetchall()
                        links = [
                            {
                                "id": r[0],
                                "url": r[1],
                                "mapType": r[2],
                                "createdAt": r[3]
                            } for r in link_rows
                        ]
                        
                        # Получаем услуги для этого бизнеса
                        cursor.execute("""
                            SELECT name, description, category, price 
                            FROM UserServices 
                            WHERE business_id = ? 
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        services_rows = cursor.fetchall()
                        services_list = [{"name": r[0], "description": r[1], "category": r[2], "price": r[3]} for r in services_rows]
                        
                        # Получаем данные владельца бизнеса для отображения
                        owner_data = None
                        
                        # Сначала проверяем BusinessProfiles (где сохраняются обновления)
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
                        
                        cursor.execute("""
                            SELECT contact_name, contact_phone, contact_email
                            FROM BusinessProfiles
                            WHERE business_id = ?
                        """, (current_business_id,))
                        profile_row = cursor.fetchone()
                        
                        if profile_row and (profile_row[0] or profile_row[1] or profile_row[2]):
                             owner_data = {
                                'id': owner_id, # Оставляем ID реального владельца
                                'name': profile_row[0] or "",
                                'phone': profile_row[1] or "",
                                'email': profile_row[2] or ""
                            }
                        
                        # Если в профиле нет данных, берем из таблицы Users
                        if not owner_data and owner_id:
                            cursor.execute("""
                                SELECT id, email, name, phone
                                FROM Users
                                WHERE id = ?
                            """, (owner_id,))
                            owner_row = cursor.fetchone()
                            if owner_row:
                                if hasattr(owner_row, 'keys'):
                                    owner_data = {
                                        'id': owner_row['id'],
                                        'email': owner_row['email'],
                                        'name': owner_row['name'],
                                        'phone': owner_row['phone']
                                    }
                                else:
                                    owner_data = {
                                        'id': owner_row[0],
                                        'email': owner_row[1],
                                        'name': owner_row[2],
                                        'phone': owner_row[3] if len(owner_row) > 3 else None
                                    }
                        
                        db.close()
                        return jsonify({
                            "success": True,
                            "businessName": business_row[1] or "",
                            "businessType": business_row[2] or "",
                            "address": business_row[3] or "",
                            "workingHours": business_row[4] or "",
                            "description": "",
                            "services": services_list,
                            "mapLinks": links,
                            "owner": owner_data  # Добавляем данные владельца
                        })
                    else:
                        print(f"❌ GET /api/client-info: Нет доступа к бизнесу, owner_id={owner_id}, user_id={user_id}")
                        db.close()
                        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
                else:
                    print(f"⚠️ GET /api/client-info: Бизнес не найден в таблице Businesses, перехожу к ClientInfo")
                    # Бизнес не найден в Businesses - пробуем получить из ClientInfo
                    # НЕ закрываем db.close() здесь, продолжаем выполнение
            
            # Старая логика для обратной совместимости (если business_id не передан ИЛИ бизнес не найден в Businesses)
            # Пытаемся получить данные из ClientInfo по user_id и business_id (если есть)
            current_business_id = request.args.get('business_id')
            if current_business_id:
                print(f"🔍 GET /api/client-info: Пытаюсь получить данные из ClientInfo, business_id={current_business_id}")
                # Сначала проверяем, что колонка business_id существует
                cursor.execute("PRAGMA table_info(ClientInfo)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # #region agent log
                import json
                log_data = {
                    "location": "src/main.py:3167",
                    "message": "GET client-info: проверка структуры таблицы",
                    "data": {
                        "columns": columns,
                        "has_business_id": 'business_id' in columns,
                        "current_business_id": current_business_id
                    },
                    "timestamp": int(datetime.now().timestamp() * 1000),
                    "sessionId": "debug-session",
                    "runId": "run1",
                    "hypothesisId": "J"
                }
                try:
                    with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                        f.write(json.dumps(log_data) + '\n')
                except: pass
                # #endregion
                
                if 'business_id' in columns:
                    # Колонка существует - используем запрос с business_id
                    try:
                        print(f"🔍 GET /api/client-info: Выполняю запрос с business_id={current_business_id}, user_id={user_id}")
                        cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ? AND business_id = ?", (user_id, current_business_id))
                        row = cursor.fetchone()
                        print(f"✅ GET /api/client-info: Запрос выполнен успешно, row={row is not None}")
                    except Exception as e:
                        error_msg = str(e)
                        print(f"❌ Ошибка запроса ClientInfo с business_id: {error_msg}")
                        import traceback
                        traceback.print_exc()
                        # Если ошибка "no such column: business_id" - значит проверка колонки не сработала
                        if "no such column: business_id" in error_msg.lower():
                            print(f"🚨 КРИТИЧЕСКАЯ ОШИБКА: Колонка business_id не найдена, хотя проверка показала, что она есть!")
                            print(f"🚨 Колонки из проверки: {columns}")
                        # Пытаемся получить без business_id
                        cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ? LIMIT 1", (user_id,))
                        row = cursor.fetchone()
                    else:
                        # Другая ошибка - пробуем без business_id
                        cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ? LIMIT 1", (user_id,))
                        row = cursor.fetchone()
                else:
                    # Колонка не существует - используем запрос без business_id
                    print(f"⚠️ Колонка business_id отсутствует, используем запрос без неё. Колонки: {columns}")
                    cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ? LIMIT 1", (user_id,))
                    row = cursor.fetchone()
                
                # Если не найдено, пытаемся получить из Businesses
                if not row:
                    cursor.execute("SELECT name, business_type, address, working_hours FROM Businesses WHERE id = ? AND owner_id = ?", (current_business_id, user_id))
                    business_row = cursor.fetchone()
                    if business_row:
                        row = (business_row[0], business_row[1], business_row[2], business_row[3], "", "")
            else:
                cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ? LIMIT 1", (user_id,))
                row = cursor.fetchone()

            # Получаем ссылки на карты (старая логика - по user_id)
            links = []
            cursor.execute("""
                SELECT id, url, map_type, created_at 
                FROM BusinessMapLinks 
                WHERE user_id = ? 
                ORDER BY created_at DESC
            """, (user_id,))
            link_rows = cursor.fetchall()
            links = [
                {
                    "id": r[0],
                    "url": r[1],
                    "mapType": r[2],
                    "createdAt": r[3]
                } for r in link_rows
            ]

            db.close()
            if not row:
                return jsonify({
                    "success": True,
                    "businessName": "",
                    "businessType": "",
                    "address": "",
                    "workingHours": "",
                    "description": "",
                    "services": "",
                    "mapLinks": links
                })
            return jsonify({
                "success": True,
                "businessName": row[0] or "",
                "businessType": row[1] or "",
                "address": row[2] or "",
                "workingHours": row[3] or "",
                "description": row[4] or "",
                "services": row[5] or "",
                "mapLinks": links
            })

        # POST/PUT: сохранить/обновить
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        
        # Получаем business_id из запроса или используем первый бизнес пользователя
        business_id = request.args.get('business_id') or data.get('business_id')
        if not business_id:
            # Если business_id не передан, пытаемся найти первый бизнес пользователя
            cursor.execute("SELECT id FROM Businesses WHERE owner_id = ? AND is_active = 1 LIMIT 1", (user_id,))
            business_row = cursor.fetchone()
            if business_row:
                business_id = business_row[0] if isinstance(business_row, tuple) else business_row['id']
            else:
                # Если бизнеса нет, используем user_id как business_id для обратной совместимости
                business_id = user_id
        
        # #region agent log
        log_data = {
            "location": "src/main.py:3256",
            "message": "POST/PUT client-info: перед INSERT",
            "data": {
                "user_id": user_id,
                "business_id": business_id,
                "has_business_id_param": bool(request.args.get('business_id') or data.get('business_id'))
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "A"
        }
        try:
            with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except: pass
        # #endregion
        
        # Проверяем структуру таблицы перед INSERT (критично для POST/PUT)
        # #region agent log
        cursor.execute("PRAGMA table_info(ClientInfo)")
        columns_after = [col[1] for col in cursor.fetchall()]
        log_data = {
            "location": "src/main.py:3270",
            "message": "POST/PUT client-info: проверка структуры таблицы",
            "data": {
                "columns": columns_after,
                "has_business_id": 'business_id' in columns_after
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "B"
        }
        try:
            with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except: pass
        # #endregion
        
        if 'business_id' not in columns_after:
            # Таблица не имеет business_id - это критическая ошибка
            error_msg = f"Критическая ошибка: таблица ClientInfo не имеет колонки business_id. Колонки: {columns_after}"
            print(f"❌ {error_msg}")
            # #region agent log
            log_data = {
                "location": "src/main.py:3285",
                "message": "POST/PUT client-info: ОШИБКА - нет business_id",
                "data": {
                    "columns": columns_after,
                    "error": error_msg
                },
                "timestamp": int(datetime.now().timestamp() * 1000),
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": "C"
            }
            try:
                with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                    f.write(json.dumps(log_data) + '\n')
            except: pass
            # #endregion
            db.close()
            return jsonify({"error": error_msg}), 500
        
        # #region agent log
        log_data = {
            "location": "src/main.py:3295",
            "message": "POST/PUT client-info: выполнение INSERT",
            "data": {
                "user_id": user_id,
                "business_id": business_id,
                "will_use_business_id": True
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "D"
        }
        try:
            with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except: pass
        # #endregion
        
        cursor.execute(
            """
            INSERT INTO ClientInfo (user_id, business_id, business_name, business_type, address, working_hours, description, services, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, business_id) DO UPDATE SET
                business_name=excluded.business_name,
                business_type=excluded.business_type,
                address=excluded.address,
                working_hours=excluded.working_hours,
                description=excluded.description,
                services=excluded.services,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                user_id,
                business_id,
                data.get('businessName') or "",
                data.get('businessType') or "",
                data.get('address') or "",
                data.get('workingHours') or "",
                data.get('description') or "",
                data.get('services') or ""
            )
        )
        
        # #region agent log
        log_data = {
            "location": "src/main.py:3330",
            "message": "POST/PUT client-info: INSERT выполнен успешно",
            "data": {
                "user_id": user_id,
                "business_id": business_id
            },
            "timestamp": int(datetime.now().timestamp() * 1000),
            "sessionId": "debug-session",
            "runId": "run1",
            "hypothesisId": "E"
        }
        try:
            with open('/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре/.cursor/debug.log', 'a') as f:
                f.write(json.dumps(log_data) + '\n')
        except: pass
        # #endregion
        print(f"📋 Сохранено в ClientInfo: businessType = {data.get('businessType') or ''}")
        db.conn.commit()

        # Сохраняем ссылки на карты, если переданы (чтобы не стирать при отсутствии поля)
        map_links = None
        if 'mapLinks' in data:
            map_links = data.get('mapLinks')
        elif 'map_links' in data:
            map_links = data.get('map_links')
        business_id = (data.get('businessId') or data.get('business_id'))

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

        # Обновляем ссылки, только если поле пришло в payload
        if business_id and isinstance(map_links, list):
            # Фильтруем пустые ссылки
            valid_links = []
            for link in map_links:
                url = link.get('url') if isinstance(link, dict) else str(link)
                if url and url.strip():
                    valid_links.append(url.strip())
            
            print(f"🔍 DEBUG: valid_links={valid_links}")
            
            # Удаляем старые ссылки для консистентности
            cursor.execute("DELETE FROM BusinessMapLinks WHERE business_id = ?", (business_id,))
            db.conn.commit()

            # Сохраняем валидные ссылки
            for url in valid_links:
                map_type = detect_map_type(url)
                cursor.execute("""
                    INSERT INTO BusinessMapLinks (id, user_id, business_id, url, map_type, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (str(uuid.uuid4()), user_id, business_id, url, map_type))
                print(f"✅ Сохранена ссылка: {url} (тип: {map_type})")
            
            db.conn.commit()

        # Всегда возвращаем текущие ссылки для бизнеса
        current_links = []
        if business_id:
            cursor.execute("""
                SELECT id, url, map_type, created_at 
                FROM BusinessMapLinks 
                WHERE business_id = ? 
                ORDER BY created_at DESC
            """, (business_id,))
            link_rows = cursor.fetchall()
            current_links = [
                {
                    "id": r[0],
                    "url": r[1],
                    "mapType": r[2],
                    "createdAt": r[3]
                } for r in link_rows
            ]

        # Синхронизация с Businesses: обновляем существующий бизнес
        try:
            business_name = data.get('businessName') or ''
            
            # Если business_id не передан, ищем существующий бизнес пользователя
            if not business_id:
                # Сначала ищем по имени (если переименовали)
                if business_name:
                    cursor.execute("""
                        SELECT id FROM Businesses 
                        WHERE owner_id = ? AND name = ? AND is_active = 1
                        LIMIT 1
                    """, (user_id, business_name))
                    existing_by_name = cursor.fetchone()
                    if existing_by_name:
                        business_id = existing_by_name[0]
                        print(f"✅ Найден бизнес по имени: {business_name} (ID: {business_id})")
                
                # Если не нашли по имени, берём первый активный бизнес пользователя
                if not business_id:
                    cursor.execute("""
                        SELECT id FROM Businesses 
                        WHERE owner_id = ? AND is_active = 1
                        ORDER BY created_at ASC
                        LIMIT 1
                    """, (user_id,))
                    first_business = cursor.fetchone()
                    if first_business:
                        business_id = first_business[0]
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
                        updates.append('name = ?'); params.append(data.get('businessName'))
                    if data.get('address') is not None:
                        updates.append('address = ?'); params.append(data.get('address'))
                    if data.get('workingHours') is not None:
                        updates.append('working_hours = ?'); params.append(data.get('workingHours'))
                    if data.get('businessType') is not None:
                        business_type_value = data.get('businessType')
                        print(f"📋 Сохраняем businessType в Businesses: {business_type_value}")
                        updates.append('business_type = ?'); params.append(business_type_value)
                    if updates:
                        updates.append('updated_at = CURRENT_TIMESTAMP')
                        params.append(business_id)
                        cursor.execute(f"UPDATE Businesses SET {', '.join(updates)} WHERE id = ?", params)
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
        
        # Если есть business_id, добавляем обновленные данные бизнеса
        if business_id:
            cursor.execute("SELECT name, business_type, address, working_hours FROM Businesses WHERE id = ?", (business_id,))
            business_row = cursor.fetchone()
            if business_row:
                business_type = business_row[1] or ""
                print(f"📋 POST /api/client-info: businessType из Businesses = '{business_type}' для business_id={business_id}")
                response_data.update({
                    "businessName": business_row[0] or "",
                    "businessType": business_type,
                    "address": business_row[2] or "",
                    "workingHours": business_row[3] or ""
                })

        db.close()
        return jsonify(response_data)

    except Exception as e:
        print(f"❌ Ошибка сохранения клиентской информации: {e}")
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

        # Получаем последнюю задачу парсинга для этого бизнеса с retry_after
        cursor.execute("""
            SELECT status, retry_after, created_at 
            FROM ParseQueue 
            WHERE business_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        """, (business_id,))
        queue_row = cursor.fetchone()
        
        retry_info = None
        overall_status = "idle"
        
        if queue_row:
            overall_status = queue_row[0] if queue_row[0] else 'idle'
            retry_after = queue_row[1] if queue_row[1] else None
            
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
        
        # Проверяем статусы в очереди для этого бизнеса (для обратной совместимости)
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM ParseQueue
            WHERE business_id = ?
            GROUP BY status
        """, (business_id,))
        status_rows = cursor.fetchall()
        
        statuses = {}
        for row in status_rows:
            statuses[row[0]] = row[1]
        
        # Определяем общий статус (если не определён выше из queue_row)
        # НЕ переопределяем статус, если он уже установлен из queue_row (например, captcha)
        if overall_status == "idle":
            if statuses.get('processing'):
                overall_status = "processing"
            elif statuses.get('pending') or statuses.get('queued'):
                overall_status = "queued"
            elif statuses.get('error'):
                overall_status = "error"
            elif statuses.get('captcha'):
                overall_status = "captcha"
                # Если статус captcha, но retry_info не был вычислен выше, вычисляем его здесь
                if retry_info is None:
                    cursor.execute("""
                        SELECT retry_after 
                        FROM ParseQueue 
                        WHERE business_id = ? AND status = 'captcha'
                        ORDER BY created_at DESC 
                        LIMIT 1
                    """, (business_id,))
                    retry_row = cursor.fetchone()
                    if retry_row and retry_row[0]:
                        try:
                            from datetime import datetime
                            retry_dt = datetime.fromisoformat(retry_row[0])
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
            elif statuses.get('done'):
                overall_status = "done"
        
        print(f"📊 Возвращаю статус: {overall_status}, retry_info: {retry_info}")
        db.close()
        return jsonify({
            "success": True,
            "status": overall_status,
            "details": statuses,
            "retry_info": retry_info
        })

    except Exception as e:
        print(f"❌ Ошибка получения статуса парсинга: {e}")
        return jsonify({"error": str(e)}), 500

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

        # Проверяем наличие колонки unanswered_reviews_count
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]
        has_unanswered_col = 'unanswered_reviews_count' in columns
        
        if has_unanswered_col:
            cursor.execute("""
                SELECT id, url, map_type, rating, reviews_count, unanswered_reviews_count, news_count, photos_count, report_path, created_at
                FROM MapParseResults
                WHERE business_id = ?
                ORDER BY datetime(created_at) DESC
            """, (business_id,))
        else:
            cursor.execute("""
                SELECT id, url, map_type, rating, reviews_count, 0 as unanswered_reviews_count, news_count, photos_count, report_path, created_at
                FROM MapParseResults
                WHERE business_id = ?
                ORDER BY datetime(created_at) DESC
            """, (business_id,))
        
        rows = cursor.fetchall()
        db.close()

        items = []
        for r in rows:
            items.append({
                "id": r[0],
                "url": r[1],
                "mapType": r[2],
                "rating": r[3],
                "reviewsCount": r[4],
                "unansweredReviewsCount": r[5] if has_unanswered_col else 0,
                "newsCount": r[6] if has_unanswered_col else r[5],
                "photosCount": r[7] if has_unanswered_col else r[6],
                "reportPath": r[8] if has_unanswered_col else r[7],
                "createdAt": r[9] if has_unanswered_col else r[8]
            })

        return jsonify({"success": True, "items": items})

    except Exception as e:
        print(f"❌ Ошибка получения результатов парсинга: {e}")
        return jsonify({"error": str(e)}), 500


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
            SELECT m.report_path, m.business_id, b.owner_id
            FROM MapParseResults m
            LEFT JOIN Businesses b ON m.business_id = b.id
            WHERE m.id = ?
            LIMIT 1
        """, (parse_id,))
        row = cursor.fetchone()
        db.close()

        if not row:
            return jsonify({"error": "Отчет не найден"}), 404

        report_path = row[0]
        business_owner = row[2]
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
        print(f"❌ Ошибка выдачи отчета: {e}")
        return jsonify({"error": str(e)}), 500


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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
            VALUES (?, ?, ?, ?, ?, ?)
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
            WHERE id = ? AND user_id = ? AND expires_at > ?
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
            WHERE id = ? AND user_id = ? AND expires_at > ?
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
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [row[1] for row in cursor.fetchall()]
        has_master_id = 'master_id' in columns
        
        if has_master_id:
            cursor.execute("""
                INSERT INTO FinancialTransactions 
                (id, user_id, transaction_date, amount, client_type, services, notes, master_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                VALUES (?, ?, ?, ?, ?, ?, ?)
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
        cursor.execute("SELECT id, user_id FROM FinancialTransactions WHERE id = ? LIMIT 1", (transaction_id,))
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
            fields.append("transaction_date = ?")
            params.append(data.get('transaction_date'))
        if 'amount' in data:
            fields.append("amount = ?")
            params.append(float(data.get('amount') or 0))
        if 'client_type' in data:
            fields.append("client_type = ?")
            params.append(data.get('client_type') or 'new')
        if 'services' in data:
            fields.append("services = ?")
            params.append(json.dumps(data.get('services') or []))
        if 'notes' in data:
            fields.append("notes = ?")
            params.append(data.get('notes') or '')

        if not fields:
            db.close()
            return jsonify({"error": "Нет полей для обновления"}), 400

        params.append(transaction_id)
        cursor.execute(f"UPDATE FinancialTransactions SET {', '.join(fields)} WHERE id = ?", params)
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
        cursor.execute("SELECT id, user_id FROM FinancialTransactions WHERE id = ? LIMIT 1", (transaction_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Транзакция не найдена"}), 404
        if row[1] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к транзакции"}), 403

        cursor.execute("DELETE FROM FinancialTransactions WHERE id = ?", (transaction_id,))
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
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [row[1] for row in cursor.fetchall()]
        has_master_id = 'master_id' in columns
        has_business_id = 'business_id' in columns
        
        saved_transactions = []
        for trans in transactions:
            transaction_id = str(uuid.uuid4())
            
            # Получаем master_id по имени мастера (если есть таблица Masters)
            master_id = None
            if trans.get('master_name'):
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Masters'")
                masters_table_exists = cursor.fetchone()
                if masters_table_exists:
                    cursor.execute("SELECT id FROM Masters WHERE name = ? LIMIT 1", (trans['master_name'],))
                    master_row = cursor.fetchone()
                    if master_row:
                        master_id = master_row[0]
            
            # Получаем business_id из текущего бизнеса пользователя
            business_id = None
            if has_business_id:
                cursor.execute("SELECT id FROM Businesses WHERE owner_id = ? LIMIT 1", (user_data['user_id'],))
                business_row = cursor.fetchone()
                if business_row:
                    business_id = business_row[0]
            
            if has_master_id and has_business_id:
                cursor.execute("""
                    INSERT INTO FinancialTransactions 
                    (id, user_id, business_id, transaction_date, amount, client_type, services, notes, master_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                    VALUES (?, ?, ?, ?, ?, ?, ?)
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
        where_clause = "transaction_date BETWEEN ? AND ?"
        where_params = [start_date, end_date]
        
        if business_id:
            where_clause = f"business_id = ? AND {where_clause}"
            where_params = [business_id] + where_params
        else:
            # Старая логика для обратной совместимости
            where_clause = f"user_id = ? AND {where_clause}"
            where_params = [user_data['user_id']] + where_params
        
        # Получаем агрегированные данные
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as average_check,
                SUM(CASE WHEN client_type = 'new' THEN 1 ELSE 0 END) as new_clients,
                SUM(CASE WHEN client_type = 'returning' THEN 1 ELSE 0 END) as returning_clients
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
        prev_where_clause = "transaction_date BETWEEN ? AND ?"
        prev_where_params = [prev_start, prev_end]
        
        if business_id:
            prev_where_clause = f"business_id = ? AND {prev_where_clause}"
            prev_where_params = [business_id] + prev_where_params
        else:
            prev_where_clause = f"user_id = ? AND {prev_where_clause}"
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
        
        # Проверяем наличие полей в таблице
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [row[1] for row in cursor.fetchall()]
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
                    WHERE business_id = ? AND transaction_date BETWEEN ? AND ?
                """, (current_business_id, start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM FinancialTransactions 
                    WHERE business_id = ? AND transaction_date BETWEEN ? AND ?
                """, (current_business_id, start_date, end_date))
        else:
            if has_master_id:
                cursor.execute("""
                    SELECT services, amount, master_id
                    FROM FinancialTransactions 
                    WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
                """, (user_data['user_id'], start_date, end_date))
            else:
                cursor.execute("""
                    SELECT services, amount, NULL as master_id
                    FROM FinancialTransactions 
                    WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
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
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Masters'")
                masters_table_exists = cursor.fetchone()
                
                if masters_table_exists:
                    cursor.execute("SELECT name FROM Masters WHERE id = ?", (master_id,))
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = ?", (network_id,))
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
            WHERE network_id = ? 
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = ?", (network_id,))
        network = cursor.fetchone()
        
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404
        
        if network[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403
        
        # Получаем точки сети
        cursor.execute("SELECT id, name FROM Businesses WHERE network_id = ?", (network_id,))
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
        
        # Получаем транзакции всех точек сети
        # Проверяем наличие поля business_id
        cursor.execute("PRAGMA table_info(FinancialTransactions)")
        columns = [row[1] for row in cursor.fetchall()]
        has_business_id = 'business_id' in columns
        
        if has_business_id and location_ids:
            placeholders = ','.join(['?'] * len(location_ids))
            cursor.execute(f"""
                SELECT services, amount, master_id, business_id
                FROM FinancialTransactions 
                WHERE business_id IN ({placeholders}) AND transaction_date BETWEEN ? AND ?
            """, location_ids + [start_date, end_date])
        else:
            # Если business_id нет, получаем через user_id владельца сети
            cursor.execute("""
                SELECT services, amount, master_id, NULL as business_id
                FROM FinancialTransactions 
                WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
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
                cursor.execute("SELECT name FROM Masters WHERE id = ?", (master_id,))
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
                WHERE network_id = ? AND is_active = 1
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

        cursor.execute("SELECT owner_id FROM Networks WHERE id = ?", (network_id,))
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
    Ручной запуск синхронизации Яндекс-данных для одного бизнеса.
    Требует действующей сессии и прав суперадмина или владельца бизнеса.
    """
    print(f"🔄 Запрос на синхронизацию бизнеса {business_id}")
    import traceback
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            print("❌ Отсутствует заголовок авторизации")
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            print("❌ Недействительный токен")
            return jsonify({"error": "Недействительный токен"}), 401

        print(f"✅ Пользователь авторизован: {user_data.get('email', 'unknown')}")

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id, name FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()

        if not business:
            db.close()
            print(f"❌ Бизнес {business_id} не найден")
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business[0]
        business_name = business[1] if len(business) > 1 else 'Unknown'
        print(f"📊 Бизнес найден: {business_name}, владелец: {business_owner_id}")

        if business_owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            print(f"❌ Нет доступа: пользователь {user_data['user_id']} не является владельцем бизнеса")
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Ищем аккаунт Яндекс.Бизнес для этого бизнеса
        print(f"🔍 Поиск аккаунта Яндекс.Бизнес для бизнеса {business_id}...")
        cursor.execute("""
            SELECT id, auth_data_encrypted, external_id 
            FROM ExternalBusinessAccounts 
            WHERE business_id = ? AND source = 'yandex_business' AND is_active = 1
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        account_row = cursor.fetchone()
        
        account_id = None
        if account_row:
             account_id = account_row[0]
             print(f"✅ Найден аккаунт: {account_id}")
        else:
             print(f"⚠️ Аккаунт Яндекс.Бизнес не найден")

        # Ищем ссылку на карты (NEW)
        print(f"🔍 Поиск ссылки на карты для бизнеса {business_id}...")
        cursor.execute("SELECT url FROM BusinessMapLinks WHERE business_id = ? AND map_type = 'yandex' LIMIT 1", (business_id,))
        map_link_row = cursor.fetchone()
        map_url = map_link_row[0] if map_link_row else None
        
        if not account_id and not map_url:
            print(f"❌ Не найден ни аккаунт Яндекс.Бизнес, ни ссылка на карты для бизнеса {business_id}")
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден источник данных",
                "message": "Для запуска парсинга добавьте ссылку на Яндекс.Карты или подключите аккаунт Яндекс.Бизнес"
            }), 400
            
        # Определяем тип задачи
        task_id = str(uuid.uuid4())
        user_id = user_data["user_id"]
        
        if map_url:
            task_type = 'parse_card'
            source = 'yandex_maps'  # Worker ожидает это для parse_card? В worker.py source используется для fallback.
            target_url = map_url
            print(f"✅ Найдена ссылка на карты: {map_url}. Запуск парсинга (с фоллбеком на синхронизацию).")
            message = "Запущен парсинг карт"
        else:
            task_type = 'sync_yandex_business'
            source = 'yandex_business'
            target_url = ''
            print(f"⚠️ Ссылка на карты не найдена, но есть аккаунт. Запуск прямой синхронизации.")
            message = "Запущена синхронизация (без парсинга)"

        print(f"🔄 Добавление задачи {task_type} в очередь для бизнеса {business_id}")
        
        try:
            cursor.execute("""
                INSERT INTO ParseQueue (
                    id, business_id, account_id, task_type, source, 
                    status, user_id, url, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 
                        'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (task_id, business_id, account_id, task_type, source, user_id, target_url))
            db.conn.commit()
            print(f"✅ Задача {task_type} добавлена в очередь: {task_id}")
        except Exception as e:
            db.close()
            print(f"❌ Ошибка при добавлении задачи в очередь: {e}")
            return jsonify({
                "success": False,
                "error": f"Ошибка при добавлении задачи в очередь: {str(e)}"
            }), 500
        finally:
            db.close()
        
        return jsonify({
            "success": True,
            "message": message,
            "sync_id": task_id,
            "task_type": task_type
        })
    
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Критическая ошибка в admin_sync_business_yandex: {e}")
        print(f"❌ Детали ошибки:\n{error_details}")
        return jsonify({
            "success": False,
            "error": f"Критическая ошибка: {str(e)}",
            "message": str(e)
        }), 500

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
            FROM ExternalBusinessAccounts 
            WHERE id = ?
        """, (account_id,))
        account_row = cursor.fetchone()
        
        if not account_row:
            print(f"❌ Аккаунт {account_id} не найден")
            cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         ("Аккаунт не найден", sync_id))
            db.conn.commit()
            return False
        
        auth_data_encrypted = account_row[0]
        external_id = account_row[1] if len(account_row) > 1 else None
        
        cursor.execute("SELECT name FROM Businesses WHERE id = ?", (business_id,))
        business_row = cursor.fetchone()
        business_name = business_row[0] if business_row else 'Unknown'
        
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
                cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
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
                UPDATE ExternalBusinessAccounts 
                SET last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = ?
            """, (account_id,))
        
            # Сохраняем историю парсинга в MapParseResults
            try:
                cursor.execute("SELECT yandex_url FROM Businesses WHERE id = ?", (business_id,))
                yandex_url_row = cursor.fetchone()
                yandex_url = yandex_url_row[0] if yandex_url_row else None
                
                if not yandex_url and external_id:
                    yandex_url = f"https://yandex.ru/sprav/{external_id}"
                
                parse_id = str(uuid.uuid4())
                reviews_without_response = sum(1 for r in reviews if not r.response_text) if reviews else 0
                
                cursor.execute("""
                    INSERT INTO MapParseResults (
                        id, business_id, url, map_type, rating, reviews_count, 
                        unanswered_reviews_count, news_count, photos_count, 
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    parse_id,
                    business_id,
                yandex_url or f"https://yandex.ru/sprav/{external_id or 'unknown'}",
                    'yandex',
                    org_info.get('rating') if org_info else None,
                    len(reviews) if reviews else 0,
                    reviews_without_response,
                    len(posts) if posts else 0,
                    org_info.get('photos_count', 0) if org_info else 0,
                ))
                db.conn.commit()
                print(f"💾 Сохранена история парсинга: {parse_id}")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения истории парсинга: {e}")
                import traceback
                traceback.print_exc()
        
        # Обновляем статус задачи на completed
        cursor = db.conn.cursor()
        cursor.execute("UPDATE SyncQueue SET status = 'completed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (sync_id,))
        db.conn.commit()
        db.close()
        
        print(f"✅ Синхронизация завершена успешно для бизнеса {business_name}")
        return True
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Ошибка при синхронизации бизнеса {business_id}: {e}")
        print(f"❌ Детали ошибки:\n{error_details}")
            
        # Сохраняем ошибку в SyncQueue и ExternalBusinessAccounts
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute("UPDATE SyncQueue SET status = 'error', error_message = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
                         (str(e), sync_id))
            cursor.execute("UPDATE ExternalBusinessAccounts SET last_error = ? WHERE id = ?", (str(e), account_id))
            db.conn.commit()
            db.close()
        except Exception as save_error:
            print(f"⚠️ Не удалось сохранить ошибку в БД: {save_error}")
            
        return False
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ Критическая ошибка в admin_sync_business_yandex: {e}")
        print(f"❌ Детали ошибки:\n{error_details}")
        return jsonify({
            "success": False,
            "error": f"Критическая ошибка: {str(e)}",
            "message": str(e)
        }), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Ошибка синхронизации Яндекс для бизнеса {business_id}: {e}")
        print(f"❌ Детали ошибки:\n{error_details}")
        return jsonify({"error": f"Ошибка синхронизации Яндекс для бизнеса: {str(e)}"}), 500

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
            FROM ParseQueue 
            WHERE id = ? AND task_type = 'sync_yandex_business'
        """, (sync_id,))
        sync_row = cursor.fetchone()
        
        if not sync_row:
            db.close()
            return jsonify({"error": "Синхронизация не найдена"}), 404
        
        sync_data = dict(sync_row)
        
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (sync_data['business_id'],))
        owner_row = cursor.fetchone()
        owner_id = owner_row[0] if owner_row else None
        
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
        
        # Проверяем наличие таблицы Networks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Networks'")
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
            WHERE owner_id = ? 
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
        cursor.execute("SELECT owner_id FROM Networks WHERE id = ?", (network_id,))
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
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
        cursor.execute("DELETE FROM ProxyServers WHERE id = ?", (proxy_id,))
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
        cursor.execute("SELECT is_active FROM ProxyServers WHERE id = ?", (proxy_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Прокси не найден"}), 404
        
        new_status = 0 if row[0] else 1
        cursor.execute("""
            UPDATE ProxyServers 
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
            default_prompts = [
                ('service_optimization', 
                 """Ты — SEO-специалист для бьюти-индустрии. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
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
                 """Ты — вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Write the reply in {language_name}.
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{examples_text}
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text[:1000]}""",
                 'Промпт для генерации ответов на отзывы'),
                ('news_generation',
                 """Ты — маркетолог для локального бизнеса. Сгенерируй новость для публикации на картах (Google, Яндекс).
Требования: до 1500 символов, можно использовать 2-3 эмодзи (не переборщи), без хештегов, без оценочных суждений, без упоминания конкурентов. Стиль — информативный и дружелюбный.
Write all generated text in {language_name}.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Контекст услуги (может отсутствовать): {service_context}
Контекст выполненной работы/транзакции (может отсутствовать): {transaction_context}
Свободная информация (может отсутствовать): {raw_info[:800]}
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{news_examples}""",
                 'Промпт для генерации новостей')
            ]
            
            for prompt_type, prompt_text, description in default_prompts:
                cursor.execute("""
                    INSERT OR IGNORE INTO AIPrompts (id, prompt_type, prompt_text, description)
                    VALUES (?, ?, ?, ?)
                """, (f"prompt_{prompt_type}", prompt_type, prompt_text, description))
            
            db.conn.commit()
            # Перечитываем после вставки
            cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM AIPrompts ORDER BY prompt_type")
            rows = cursor.fetchall()
        
        prompts = []
        for row in rows:
            prompts.append({
                'type': row[0],
                'text': row[1],
                'description': row[2],
                'updated_at': row[3],
                'updated_by': row[4]
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
            SET prompt_text = ?, description = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
            WHERE prompt_type = ?
        """, (prompt_text, description, user_data['user_id'], prompt_type))
        
        if cursor.rowcount == 0:
            # Если промпта нет, создаём его
            cursor.execute("""
                INSERT INTO AIPrompts (id, prompt_type, prompt_text, description, updated_by)
                VALUES (?, ?, ?, ?, ?)
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
        cursor.execute("SELECT prompt_text FROM AIPrompts WHERE prompt_type = ?", (prompt_type,))
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
        cursor.execute("SELECT type_key, label FROM BusinessTypes WHERE is_active = 1 ORDER BY label")
        rows = cursor.fetchall()
        
        types = []
        for row in rows:
            types.append({
                'type_key': row[0],
                'label': row[1]
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
            VALUES (?, ?, ?, ?)
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
            cursor.execute("DELETE FROM BusinessTypes WHERE id = ?", (type_id,))
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
            SET label = ?, description = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
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
        cursor.execute("SELECT business_type FROM Businesses WHERE id = ?", (business_id,))
        row = cursor.fetchone()
        business_type_key = row[0] if row else 'other'
        
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = ? OR id = ?", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
             # Fallback
             cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'other'")
             bt_row = cursor.fetchone()
             
        business_type_id = bt_row[0] if bt_row else None
        
        if not business_type_id:
            # Если даже 'other' нет
            db.close()
            return jsonify({"stages": [], "current_step": 1})
            
        # 2. Получаем текущий прогресс (шаг визарда)
        cursor.execute("SELECT step FROM BusinessOptimizationWizard WHERE business_id = ?", (business_id,))
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
        cursor.execute("SELECT owner_id, business_type FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
            
        owner_id, business_type_key = business[0], business[1]
        
        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403
            
        # Находим ID типа бизнеса
        cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = ? OR id = ?", (business_type_key, business_type_key))
        bt_row = cursor.fetchone()
        
        if not bt_row:
            cursor.execute("SELECT id FROM BusinessTypes WHERE type_key = 'other'")
            bt_row = cursor.fetchone()
             
        business_type_id = bt_row[0] if bt_row else None
        
        if not business_type_id:
            db.close()
            return jsonify({"stages": []})
            
        # Получаем текущий шаг визарда
        cursor.execute("SELECT step FROM BusinessOptimizationWizard WHERE business_id = ?", (business_id,))
        wiz_row = cursor.fetchone()
        current_step = wiz_row[0] if wiz_row else 1
        
        # Получаем этапы
        cursor.execute("""
            SELECT id, stage_number, title, description, goal, expected_result, duration
            FROM GrowthStages
            WHERE business_type_id = ?
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
            cursor.execute("DELETE FROM GrowthStages WHERE id = ?", (stage_id,))
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
        print(f"❌ Ошибка получения пользователей с бизнесами: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

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
        cursor.execute("SELECT id FROM Businesses WHERE id = ?", (business_id,))
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
        
        if not network_id:
            db.close()
            return jsonify({"success": True, "is_network": False, "locations": []})
            
        locations = db.get_businesses_by_network(network_id)
        
        db.close()
        
        return jsonify({
            "success": True,
            "is_network": True,
            "locations": locations
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
        
        # Создаем таблицу если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessOptimizationWizard (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                step INTEGER DEFAULT 1,
                data TEXT,
                completed INTEGER DEFAULT 0,
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
            cursor.execute("SELECT id FROM BusinessOptimizationWizard WHERE business_id = ?", (business_id,))
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

@app.route('/api/business/<business_id>/services', methods=['GET'])
def get_business_services(business_id):
    """Получить услуги конкретного бизнеса"""
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
        
        # Проверяем доступ к бизнесу
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        
        # Проверяем права доступа
        if not db.is_superadmin(user_data['user_id']) and business['owner_id'] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
        
        services = db.get_services_by_business(business_id)
        db.close()
        
        return jsonify({"success": True, "services": services})
        
    except Exception as e:
        print(f"❌ Ошибка получения услуг бизнеса: {e}")
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
        smtp_username = os.getenv("SMTP_USERNAME", "info@beautybot.pro")
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
    contact_email = os.getenv("CONTACT_EMAIL", "info@beautybot.pro")
    
    subject = f"Новое сообщение с сайта BeautyBot от {name}"
    body = f"""
Новое сообщение с сайта BeautyBot

Имя: {name}
Email: {email}
Телефон: {phone if phone else 'Не указан'}

Сообщение:
{message}

---
Отправлено с сайта beautybot.pro
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
        subject = "Восстановление пароля BeautyBot"
        body = f"""
Восстановление пароля для BeautyBot

Ваш токен восстановления: {reset_token}
Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}

Для сброса пароля перейдите по ссылке:
https://beautybot.pro/reset-password?token={reset_token}&email={email}

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
    Принимает email и url, отправляет email на info@beautybot.pro о новой заявке.
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
        
        # Отправляем email на info@beautybot.pro о новой заявке
        contact_email = os.getenv("CONTACT_EMAIL", "info@beautybot.pro")
        subject = f"Новая заявка с сайта BeautyBot от {email}"
        body = f"""
Новая заявка с сайта BeautyBot

Email клиента: {email}
Ссылка на бизнес: {url}

---
Отправлено с сайта beautybot.pro
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
    Принимает данные регистрации, отправляет email на info@beautybot.pro о новой заявке.
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
        
        # Отправляем email на info@beautybot.pro о новой заявке на регистрацию
        contact_email = os.getenv("CONTACT_EMAIL", "info@beautybot.pro")
        subject = f"Новая заявка на регистрацию от {email}"
        body = f"""
Новая заявка на регистрацию с сайта BeautyBot

Имя: {name or 'Не указано'}
Email: {email}
Телефон: {phone or 'Не указан'}
Ссылка на Яндекс.Карты: {yandex_url or 'Не указана'}

---
Отправлено с сайта beautybot.pro
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
        cursor.execute("SELECT id FROM Businesses WHERE id = ? AND owner_id = ?", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403
        
        # Генерируем токен привязки
        import secrets
        from datetime import datetime, timedelta
        
        bind_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=5)  # Токен действует 5 минут
        
        # Проверяем наличие поля business_id в таблице TelegramBindTokens
        cursor.execute("PRAGMA table_info(TelegramBindTokens)")
        columns = [row[1] for row in cursor.fetchall()]
        has_business_id = 'business_id' in columns
        
        # Если поля нет, добавляем его
        if not has_business_id:
            cursor.execute("ALTER TABLE TelegramBindTokens ADD COLUMN business_id TEXT")
            db.conn.commit()
        
        # Удаляем старые неиспользованные токены для этого бизнеса
        if has_business_id or 'business_id' in [row[1] for row in cursor.execute("PRAGMA table_info(TelegramBindTokens)").fetchall()]:
            cursor.execute("""
                DELETE FROM TelegramBindTokens 
                WHERE business_id = ? AND used = 0 AND expires_at < ?
            """, (business_id, datetime.now().isoformat()))
        else:
            cursor.execute("""
                DELETE FROM TelegramBindTokens 
                WHERE user_id = ? AND used = 0 AND expires_at < ?
            """, (user_data['user_id'], datetime.now().isoformat()))
        
        # Создаем новый токен
        token_id = str(uuid.uuid4())
        if has_business_id or 'business_id' in [row[1] for row in cursor.execute("PRAGMA table_info(TelegramBindTokens)").fetchall()]:
            cursor.execute("""
                INSERT INTO TelegramBindTokens (id, user_id, business_id, token, expires_at, used, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?)
            """, (token_id, user_data['user_id'], business_id, bind_token, expires_at.isoformat(), datetime.now().isoformat()))
        else:
            cursor.execute("""
                INSERT INTO TelegramBindTokens (id, user_id, token, expires_at, used, created_at)
                VALUES (?, ?, ?, ?, 0, ?)
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
        cursor.execute("SELECT id FROM Businesses WHERE id = ? AND owner_id = ?", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403
        
        # Проверяем наличие поля business_id в таблице TelegramBindTokens
        cursor.execute("PRAGMA table_info(TelegramBindTokens)")
        columns = [row[1] for row in cursor.fetchall()]
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
                WHERE business_id = ? AND used = 1 AND user_id = ?
            """, (business_id, user_data['user_id']))
            result = cursor.fetchone()
            has_used_token_for_this_business = result[0] > 0 if result else False
            
            print(f"🔍 Проверка статуса Telegram для бизнеса {business_id}: has_used_token_for_this_business={has_used_token_for_this_business}")
            
            if has_used_token_for_this_business:
                # Проверяем, что у пользователя есть telegram_id
                cursor.execute("SELECT telegram_id FROM Users WHERE id = ?", (user_data['user_id'],))
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
            cursor.execute("SELECT telegram_id FROM Users WHERE id = ?", (user_data['user_id'],))
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
        
        # Проверяем токен (включая business_id)
        cursor.execute("PRAGMA table_info(TelegramBindTokens)")
        columns = [row[1] for row in cursor.fetchall()]
        has_business_id = 'business_id' in columns
        
        if has_business_id:
            cursor.execute("""
                SELECT id, user_id, business_id, expires_at, used
                FROM TelegramBindTokens
                WHERE token = ?
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
                WHERE token = ?
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
        cursor.execute("SELECT id FROM Users WHERE telegram_id = ? AND id != ?", (telegram_id, user_id))
        existing_user = cursor.fetchone()
        if existing_user:
            db.close()
            return jsonify({"error": "Этот Telegram уже привязан к другому аккаунту"}), 400
        
        # Привязываем Telegram к аккаунту
        cursor.execute("""
            UPDATE Users 
            SET telegram_id = ?, updated_at = ?
            WHERE id = ?
        """, (telegram_id, datetime.now().isoformat(), user_id))
        
        # Помечаем токен как использованный
        # Если у токена был business_id, сохраняем его при обновлении
        if has_business_id and business_id_from_token:
            cursor.execute("""
                UPDATE TelegramBindTokens
                SET used = 1, business_id = ?
                WHERE id = ?
            """, (business_id_from_token, token_id))
        else:
            cursor.execute("""
                UPDATE TelegramBindTokens
                SET used = 1
                WHERE id = ?
            """, (token_id,))
        
        db.conn.commit()
        
        # Получаем информацию о пользователе
        cursor.execute("SELECT email, name FROM Users WHERE id = ?", (user_id,))
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

@app.errorhandler(Exception)
def handle_exception(e):
    """Глобальный обработчик исключений"""
    import traceback
    print(f"🚨 ГЛОБАЛЬНАЯ ОШИБКА: {str(e)}")
    print(f"🚨 ТРАССИРОВКА: {traceback.format_exc()}")
    return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500

if __name__ == "__main__":
    # Инициализируем схему базы данных при первом запуске
    print("🔄 Проверка схемы базы данных...")
    init_database_schema()
    
    print("SEO анализатор запущен на порту 8000")
    app.run(host='0.0.0.0', port=8000, debug=False)