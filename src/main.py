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
import random

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
                
                result = analyze_screenshot_with_gigachat(image_base64, screenshot_prompt)
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
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS UserServiceExamples (
                            id TEXT PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            example_text TEXT NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                        )
                        """
                    )
                    cur.execute("SELECT example_text FROM UserServiceExamples WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
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
        # Обеспечим таблицу
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserServiceExamples (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                example_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            )
            """
        )

        if request.method == 'GET':
            cur.execute("SELECT id, example_text, created_at FROM UserServiceExamples WHERE user_id = ? ORDER BY created_at DESC", (user_data['user_id'],))
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
        cur.execute("SELECT COUNT(*) FROM UserServiceExamples WHERE user_id = ?", (user_data['user_id'],))
        count = cur.fetchone()[0]
        if count >= 5:
            db.close()
            return jsonify({"error": "Максимум 5 примеров"}), 400
        example_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserServiceExamples (id, user_id, example_text) VALUES (?, ?, ?)", (example_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserServiceExamples WHERE id = ? AND user_id = ?", (example_id, user_data['user_id']))
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
        selected_service_id = data.get('service_id')
        raw_info = (data.get('raw_info') or '').strip()

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

        # Подтянем примеры новостей пользователя (до 5)
        news_examples = ""
        try:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS UserNewsExamples (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    example_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute("SELECT example_text FROM UserNewsExamples WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
            r = cur.fetchall()
            ex = [row[0] if isinstance(row, tuple) else row['example_text'] for row in r]
            if ex:
                news_examples = "\n".join(ex)
        except Exception:
            news_examples = ""

        prompt = f"""
Ты — маркетолог для локального бизнеса. Сгенерируй короткую новость для публикации в Яндекс.Картах.
Требования: 1-2 предложения, до 300 символов, без эмодзи и хештегов, без оценочных суждений, без упоминания конкурентов. Стиль — информативный и дружелюбный.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Контекст услуги (может отсутствовать): {service_context}
Свободная информация (может отсутствовать): {raw_info[:800]}
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{news_examples}
"""

        result = analyze_text_with_gigachat(prompt)
        if 'error' in result:
            db.close()
            return jsonify({"error": result['error']}), 500

        generated_text = result.get('news') or result.get('text') or json.dumps(result, ensure_ascii=False)

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
        print(f"❌ Ошибка генерации новости: {e}")
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserReviewExamples (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                example_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            )
            """
        )

        if request.method == 'GET':
            cur.execute("SELECT id, example_text, created_at FROM UserReviewExamples WHERE user_id = ? ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserReviewExamples WHERE user_id = ?", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserReviewExamples (id, user_id, example_text) VALUES (?, ?, ?)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserReviewExamples WHERE id = ? AND user_id = ?", (example_id, user_data['user_id']))
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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNewsExamples (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                example_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            )
            """
        )

        if request.method == 'GET':
            cur.execute("SELECT id, example_text, created_at FROM UserNewsExamples WHERE user_id = ? ORDER BY created_at DESC", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                items.append({"id": (row[0] if isinstance(row, tuple) else row['id']), "text": (row[1] if isinstance(row, tuple) else row['example_text']), "created_at": (row[2] if isinstance(row, tuple) else row['created_at'])})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) FROM UserNewsExamples WHERE user_id = ?", (user_data['user_id'],))
        cnt = cur.fetchone()[0]
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute("INSERT INTO UserNewsExamples (id, user_id, example_text) VALUES (?, ?, ?)", (ex_id, user_data['user_id'], text))
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
        cur.execute("DELETE FROM UserNewsExamples WHERE id = ? AND user_id = ?", (example_id, user_data['user_id']))
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

        data = request.get_json() or {}
        review_text = (data.get('review') or '').strip()
        tone = (data.get('tone') or 'профессиональный').strip()
        if not review_text:
            return jsonify({"error": "Не передан текст отзыва"}), 400

        # Подтянем примеры ответов пользователя (до 5)
        examples_text = ""
        try:
            db = DatabaseManager()
            cur = db.conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS UserReviewExamples (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    example_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                )
                """
            )
            cur.execute("SELECT example_text FROM UserReviewExamples WHERE user_id = ? ORDER BY created_at DESC LIMIT 5", (user_data['user_id'],))
            rows = cur.fetchall(); db.close()
            examples = [row[0] if isinstance(row, tuple) else row['example_text'] for row in rows]
            if examples:
                examples_text = "\n".join(examples)
        except Exception:
            examples_text = ""

        prompt = f"""
Ты — вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Если уместно, ориентируйся на стиль этих примеров (если они есть):\n{examples_text}
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
            # keywords в старых данных могли храниться как строка "a, b" — сделаем устойчивый парсинг
            raw_kw = service['keywords']
            parsed_kw = []
            if raw_kw:
                try:
                    parsed_kw = json.loads(raw_kw)
                    if not isinstance(parsed_kw, list):
                        parsed_kw = []
                except Exception:
                    parsed_kw = [k.strip() for k in str(raw_kw).split(',') if k.strip()]
            result.append({
                "id": service['id'],
                "category": service['category'],
                "name": service['name'],
                "description": service['description'],
                "keywords": parsed_kw,
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

        # Опциональная синхронизация с Businesses, если явно передан business_id
        try:
            business_id = (data.get('businessId') or data.get('business_id'))
            if business_id:
                # Проверим доступ
                # Получим владельца бизнеса
                cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
                row = cursor.fetchone()
                owner_id = row[0] if row else None
                if owner_id and (owner_id == user_id or user_id):
                    # Обновляем только базовые поля, если пришли
                    updates = []
                    params = []
                    if data.get('businessName') is not None:
                        updates.append('name = ?'); params.append(data.get('businessName'))
                    if data.get('address') is not None:
                        updates.append('address = ?'); params.append(data.get('address'))
                    if data.get('workingHours') is not None:
                        updates.append('working_hours = ?'); params.append(data.get('workingHours'))
                    if updates:
                        updates.append('updated_at = CURRENT_TIMESTAMP')
                        params.append(business_id)
                        cursor.execute(f"UPDATE Businesses SET {', '.join(updates)} WHERE id = ?", params)
                        db.conn.commit()
        except Exception as _:
            pass

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
        
        # Получаем дополнительную информацию о пользователе
        db = DatabaseManager()
        user_id = user_data.get('user_id') or user_data.get('id')
        is_superadmin = db.is_superadmin(user_id)
        
        # Если суперадмин - получаем все бизнесы
        businesses = []
        if is_superadmin:
            businesses = db.get_all_businesses()
        else:
            businesses = db.get_businesses_by_owner(user_id)
        
        db.close()
        
        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "email": user_data.get('email'),
                "name": user_data.get('name'),
                "phone": user_data.get('phone'),
                "is_superadmin": is_superadmin
            },
            "businesses": businesses
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
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403
        
        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')
        industry = data.get('industry', '')
        owner_id = data.get('owner_id')
        
        if not name:
            return jsonify({"error": "Название бизнеса обязательно"}), 400
        
        business_id = db.create_business(name, description, industry, owner_id)
        db.close()
        
        return jsonify({"success": True, "business_id": business_id})
        
    except Exception as e:
        print(f"❌ Ошибка создания бизнеса: {e}")
        return jsonify({"error": str(e)}), 500

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
            return jsonify({"error": "Недостаточно прав"}), 403
        
        db.delete_business(business_id)
        db.close()
        
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Ошибка удаления бизнеса: {e}")
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
            return jsonify({"error": "Недостаточно прав"}), 403
        
        users = db.get_all_users()
        db.close()
        
        return jsonify({"success": True, "users": users})
        
    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
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

def send_contact_email(name, email, phone, message):
    """Отправка email с сообщением обратной связи"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Настройки SMTP для reg.ru
        smtp_server = "mail.hosting.reg.ru"
        smtp_port = 587
        smtp_username = "info@beautybot.pro"
        smtp_password = "an9-Nfx-j7V-Nrx"
        contact_email = "info@beautybot.pro"
        
        # Создание сообщения
        msg = MIMEMultipart()
        msg['From'] = smtp_username
        msg['To'] = contact_email
        msg['Subject'] = f"Новое сообщение с сайта BeautyBot от {name}"
        
        # Тело письма
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
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Отправка
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Email отправлен на {contact_email}")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка отправки email: {e}")
        return False

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

@app.errorhandler(Exception)
def handle_exception(e):
    """Глобальный обработчик исключений"""
    import traceback
    print(f"🚨 ГЛОБАЛЬНАЯ ОШИБКА: {str(e)}")
    print(f"🚨 ТРАССИРОВКА: {traceback.format_exc()}")
    return jsonify({"error": f"Внутренняя ошибка сервера: {str(e)}"}), 500

if __name__ == "__main__":
    print("SEO анализатор запущен на порту 8000")
    app.run(host='0.0.0.0', port=8000, debug=False)