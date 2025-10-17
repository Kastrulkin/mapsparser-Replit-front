"""
main.py — Веб-сервер для SEO-анализатора Яндекс.Карт
"""
import os
import sys

# Устанавливаем переменную окружения для отключения SSL проверки GigaChat
os.environ.setdefault('GIGACHAT_SSL_VERIFY', 'false')
from flask import Flask, request, jsonify, render_template_string, send_from_directory
from parser import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat
from database_manager import DatabaseManager
from auth_system import authenticate_user, create_session, verify_session
import uuid
import base64
import os
import json
from datetime import datetime, timedelta

# Автоматическая загрузка переменных окружения из .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print('Внимание: для автоматической загрузки .env установите пакет python-dotenv')

app = Flask(__name__)

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

# ==================== ЛОКАЛЬНЫЕ УТИЛИТЫ ДЛЯ SQLITE (вместо Supabase) ====================
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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.ico')

@app.route('/favicon.svg')
def favicon_svg():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.svg')

@app.route('/robots.txt')
def robots():
    return send_from_directory(FRONTEND_DIST_DIR, 'robots.txt')

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
    return send_from_directory(FRONTEND_DIST_DIR, 'index.html')

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

# ==================== СЕРВИС: ОПТИМИЗАЦИЯ УСЛУГ ====================
@app.route('/api/services/optimize', methods=['POST', 'OPTIONS'])
def services_optimize():
    """Единая точка: перефразирование услуг из текста или файла."""
    try:
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

        # Источник: файл или текст
        file = request.files.get('file') if 'file' in request.files else None
        if file:
            content = file.read().decode('utf-8', errors='ignore')
        else:
            data = request.get_json(silent=True) or {}
            content = (data.get('text') or '').strip()

        if not content:
            return jsonify({"error": "Не передан текст услуг или файл"}), 400

        # Загружаем частотные запросы
        try:
            with open('prompts/frequent-queries.txt', 'r', encoding='utf-8') as f:
                frequent_queries = f.read()
        except FileNotFoundError:
            frequent_queries = "Частотные запросы не найдены"

        # Загружаем основной промпт из файла
        try:
            with open('prompts/services-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            prompt_template = """Ты — SEO-специалист для бьюти-индустрии. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
Запрещено любые мнения, диалог, оценочные суждения, обсуждение конкурентов, оскорбления. Никакого текста кроме результата.

Регион: {region}
Название бизнеса: {business_name}
Тон: {tone}
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

        # Формируем финальный промпт БЕЗ str.format (чтобы не сломать JSON-скобки)
        prompt = (
            prompt_template
            .replace('{region}', str(region or 'не указан'))
            .replace('{business_name}', str(business_name or 'салон красоты'))
            .replace('{tone}', str(tone or 'профессиональный'))
            .replace('{length}', str(length or 150))
            .replace('{instructions}', str(instructions or '—'))
            .replace('{frequent_queries}', str(frequent_queries))
            .replace('{content}', str(content[:4000]))
        )

        result = analyze_text_with_gigachat(prompt)
        # Если парсинг не удался, вернем понятное сообщение и сырую выдачу для диагностики
        if 'error' in result:
            return jsonify({
                "success": False,
                "error": result.get('error', 'Ошибка оптимизации'),
                "raw": result.get('raw_response')
            }), 502

        # Сохраним в БД (как оптимизацию прайса, даже для текстового режима)
        db = DatabaseManager()
        cursor = db.conn.cursor()
        optimization_id = str(uuid.uuid4())
        upload_dir = 'uploads/pricelists'
        os.makedirs(upload_dir, exist_ok=True)
        # Сохраним сырой текст в файл для истории
        raw_path = os.path.join(upload_dir, f"{optimization_id}_raw.txt")
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(content)

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
        return jsonify({"error": str(e)}), 500

# ==================== СЕРВИС: ОТВЕТЫ НА ОТЗЫВЫ ====================
@app.route('/api/reviews/reply', methods=['POST', 'OPTIONS'])
def reviews_reply():
    """Сгенерировать короткий вежливый ответ на отзыв в заданном тоне."""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        if not verify_session(token):
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        review_text = (data.get('review') or '').strip()
        tone = (data.get('tone') or 'профессиональный').strip()
        if not review_text:
            return jsonify({"error": "Не передан текст отзыва"}), 400

        prompt = f"""
Ты — вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента. 
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text[:1000]}
"""
        result = analyze_text_with_gigachat(prompt)
        if 'error' in result:
            return jsonify({"error": result['error']}), 500
        return jsonify({"success": True, "result": result})
    except Exception as e:
        print(f"❌ Ошибка генерации ответа на отзыв: {e}")
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

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']
        service_id = str(uuid.uuid4())

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

        cursor.execute("""
            SELECT id, category, name, description, keywords, price, created_at
            FROM UserServices 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        
        services = cursor.fetchall()
        db.close()

        result = []
        for service in services:
            result.append({
                "id": service['id'],
                "category": service['category'],
                "name": service['name'],
                "description": service['description'],
                "keywords": json.loads(service['keywords']) if service['keywords'] else [],
                "price": service['price'],
                "created_at": service['created_at']
            })

        return jsonify({"success": True, "services": result})

    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/update/<string:service_id>', methods=['PUT', 'OPTIONS'])
def update_service(service_id):
    """Обновление существующей услуги пользователя."""
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

        category = data.get('category', '')
        name = data.get('name', '')
        description = data.get('description', '')
        keywords = data.get('keywords', [])
        price = data.get('price', '')
        user_id = user_data['user_id']

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE UserServices SET
            category = ?, name = ?, description = ?, keywords = ?, price = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (category, name, description, json.dumps(keywords), price, service_id, user_id))

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга обновлена"})

    except Exception as e:
        print(f"❌ Ошибка обновления услуги: {e}")
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ClientInfo (
                user_id TEXT PRIMARY KEY,
                business_name TEXT,
                business_type TEXT,
                address TEXT,
                working_hours TEXT,
                description TEXT,
                services TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        if request.method == 'GET':
            cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            db.close()
            if not row:
                return jsonify({
                    "success": True,
                    "businessName": "",
                    "businessType": "",
                    "address": "",
                    "workingHours": "",
                    "description": "",
                    "services": ""
                })
            return jsonify({
                "success": True,
                "businessName": row[0] or "",
                "businessType": row[1] or "",
                "address": row[2] or "",
                "workingHours": row[3] or "",
                "description": row[4] or "",
                "services": row[5] or ""
            })

        # POST/PUT: сохранить/обновить
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400
        cursor.execute(
            """
            INSERT INTO ClientInfo (user_id, business_name, business_type, address, working_hours, description, services, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
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
                data.get('businessName') or "",
                data.get('businessType') or "",
                data.get('address') or "",
                data.get('workingHours') or "",
                data.get('description') or "",
                data.get('services') or ""
            )
        )
        db.conn.commit()
        db.close()
        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Ошибка сохранения клиентской информации: {e}")
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
        result = analyze_screenshot_with_gigachat(image_base64, prompt)
        
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
        
        # Строим запрос
        query = "SELECT * FROM FinancialTransactions WHERE user_id = ?"
        params = [user_data['user_id']]
        
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY transaction_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        transactions = cursor.fetchall()
        
        # Преобразуем в словари
        result = []
        for transaction in transactions:
            result.append({
                "id": transaction[0],
                "transaction_date": transaction[2],
                "amount": float(transaction[3]),
                "client_type": transaction[4],
                "services": json.loads(transaction[5]) if transaction[5] else [],
                "notes": transaction[6],
                "created_at": transaction[7]
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
        
        # Получаем агрегированные данные
        cursor.execute("""
            SELECT 
                COUNT(*) as total_orders,
                SUM(amount) as total_revenue,
                AVG(amount) as average_check,
                SUM(CASE WHEN client_type = 'new' THEN 1 ELSE 0 END) as new_clients,
                SUM(CASE WHEN client_type = 'returning' THEN 1 ELSE 0 END) as returning_clients
            FROM FinancialTransactions 
            WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
        """, (user_data['user_id'], start_date, end_date))
        
        metrics = cursor.fetchone()
        
        # Вычисляем retention rate
        total_clients = metrics[3] + metrics[4]  # new + returning
        retention_rate = (metrics[4] / total_clients * 100) if total_clients > 0 else 0
        
        # Получаем данные за предыдущий период для сравнения
        from datetime import datetime, timedelta
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        period_days = (end_dt - start_dt).days
        
        prev_start = (start_dt - timedelta(days=period_days)).strftime('%Y-%m-%d')
        prev_end = start_date
        
        cursor.execute("""
            SELECT 
                COUNT(*) as prev_orders,
                SUM(amount) as prev_revenue
            FROM FinancialTransactions 
            WHERE user_id = ? AND transaction_date BETWEEN ? AND ?
        """, (user_data['user_id'], prev_start, prev_end))
        
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
        
        # Создаем сессию
        session_token = create_session(result['id'])
        if not session_token:
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
def login():
    """Вход пользователя"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        
        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        
        # Аутентификация
        result = authenticate_user(email, password)
        
        if 'error' in result:
            return jsonify({"error": result['error']}), 401
        
        # Создаем сессию
        session_token = create_session(result['id'])
        if not session_token:
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
        print(f"❌ Ошибка входа: {e}")
        return jsonify({"error": str(e)}), 500

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
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_data.get('user_id') or user_data.get('id'),
                "email": user_data.get('email'),
                "name": user_data.get('name'),
                "phone": user_data.get('phone')
            }
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения информации о пользователе: {e}")
        return jsonify({"error": str(e)}), 500

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

if __name__ == "__main__":
    print("SEO анализатор запущен на порту 8000")
    app.run(host='0.0.0.0', port=8000, debug=False)