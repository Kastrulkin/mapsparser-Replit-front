"""
main.py — Веб-сервер для SEO-анализатора Яндекс.Карт
"""
import os
import sys

# Устанавливаем переменную окружения для отключения SSL проверки GigaChat
os.environ.setdefault('GIGACHAT_SSL_VERIFY', 'false')
from flask import Flask, request, jsonify, render_template_string, send_from_directory, Response
from flask_cors import CORS
from parser import parse_yandex_card
from analyzer import analyze_card
from report import generate_html_report
from services.gigachat_client import analyze_screenshot_with_gigachat, analyze_text_with_gigachat
from database_manager import DatabaseManager, get_db_connection
from auth_system import authenticate_user, create_session, verify_session
from init_database_schema import init_database_schema
from chatgpt_api import chatgpt_bp
from stripe_integration import stripe_bp
import uuid
import base64
import os
import json
import sqlite3
from datetime import datetime, timedelta
import random

# Автоматическая загрузка переменных окружения из .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print('Внимание: для автоматической загрузки .env установите пакет python-dotenv')

app = Flask(__name__)
# Разрешаем CORS для локального фронтенда
CORS(app, supports_credentials=True, origins=["http://localhost:3000", "http://127.0.0.1:3000"])

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
                result = analyze_screenshot_with_gigachat(image_base64, screenshot_prompt)
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
            error_msg = result.get('error', 'Ошибка оптимизации')
            print(f"❌ Ошибка в результате: {error_msg}")
            print(f"❌ Полный результат: {result}")
            return jsonify({
                "success": False,
                "error": error_msg,
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
Ты — маркетолог для локального бизнеса. Сгенерируй короткую новость для публикации на картах (Google, Яндекс).
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
        
        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')
        
        # Если передан business_id - фильтруем по нему, иначе по user_id
        if business_id:
            # Проверяем доступ к бизнесу
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = ? AND is_active = 1", (business_id,))
            business_row = cursor.fetchone()
            if business_row:
                owner_id = business_row[0]
                if owner_id == user_id or user_data.get('is_superadmin'):
                    cursor.execute("""
                        SELECT id, category, name, description, keywords, price, created_at
                        FROM UserServices 
                        WHERE business_id = ? 
                        ORDER BY created_at DESC
                    """, (business_id,))
                else:
                    db.close()
                    return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            else:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
        else:
            # Старая логика для обратной совместимости
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
            
            # Если передан business_id - берём данные из таблицы Businesses
            if current_business_id:
                # Проверяем доступ к бизнесу
                cursor.execute("SELECT owner_id, name, business_type, address, working_hours FROM Businesses WHERE id = ? AND is_active = 1", (current_business_id,))
                business_row = cursor.fetchone()
                
                if business_row:
                    owner_id = business_row[0]
                    # Проверяем права доступа
                    if owner_id == user_id or user_data.get('is_superadmin'):
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
                        if owner_id:
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
                        db.close()
                        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
                else:
                    db.close()
                    return jsonify({"error": "Бизнес не найден"}), 404
            
            # Старая логика для обратной совместимости (если business_id не передан)
            cursor.execute("SELECT business_name, business_type, address, working_hours, description, services FROM ClientInfo WHERE user_id = ?", (user_id,))
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

        parse_errors = []
        parse_status = "skipped"

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

            # Если есть Яндекс карты — добавляем в очередь парсинга
            yandex_urls = [url for url in valid_links if detect_map_type(url) == 'yandex']
            if yandex_urls:
                parse_status = "queued"
                
                # Добавляем задачи в очередь
                for url in yandex_urls:
                    try:
                        queue_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO ParseQueue (id, url, user_id, business_id, status, created_at)
                            VALUES (?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)
                        """, (queue_id, url, user_id, business_id))
                        print(f"✅ Добавлена задача в очередь: {queue_id} для URL: {url}")
                    except Exception as e:
                        print(f"⚠️ Ошибка добавления в очередь: {e}")
                        parse_errors.append(f"Ошибка добавления {url} в очередь: {str(e)}")
                        parse_status = "error"
                
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
                cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
                row = cursor.fetchone()
                owner_id = row[0] if row else None
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
                        updates.append('business_type = ?'); params.append(data.get('businessType'))
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

        db.close()
        return jsonify({"success": True, "parseStatus": parse_status, "parseErrors": parse_errors, "mapLinks": current_links})

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
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        owner_id = row[0]
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
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        owner_id = row[0]
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
            
            result = analyze_screenshot_with_gigachat(image_base64, prompt_content)
            
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
            result = analyze_text_with_gigachat(prompt_content + "\n\nСодержимое файла:\n" + file_content)
            
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
        # Используем COALESCE(transaction_date, date) для совместимости со старой схемой
        query = """
            SELECT 
                id,
                business_id,
                COALESCE(transaction_date, date) AS tx_date,
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
            query += " AND COALESCE(transaction_date, date) >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND COALESCE(transaction_date, date) <= ?"
            params.append(end_date)
        
        query += " ORDER BY tx_date DESC, created_at DESC LIMIT ? OFFSET ?"
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
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = ? AND is_active = 1", (business_id,))
            business_row = cursor.fetchone()
            if not business_row:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            owner_id = business_row[0]
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
        total_clients = metrics[3] + metrics[4]  # new + returning
        retention_rate = (metrics[4] / total_clients * 100) if total_clients > 0 else 0
        
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

        sync_service = YandexSyncService()
        synced_count = sync_service.sync_network(network_id)

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

        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if business[0] != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        db.close()

        sync_service = YandexSyncService()
        ok = sync_service.sync_business(business_id)

        return jsonify(
            {
                "success": bool(ok),
                "message": "Синхронизация выполнена" if ok else "Не удалось синхронизировать бизнес",
            }
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка синхронизации Яндекс для бизнеса: {str(e)}"}), 500


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
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
            business = cursor.fetchone()
            if not business:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if business[0] != user_data['user_id'] and not user_data.get('is_superadmin'):
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
        
        # Проверяем, есть ли у пользователя хотя бы один активный бизнес
        # Если все бизнесы заблокированы, пользователь не может войти
        db = DatabaseManager()
        is_superadmin = db.is_superadmin(result['id'])
        
        if not is_superadmin:
            # Проверяем активные бизнесы для обычных пользователей
            businesses = db.get_businesses_by_owner(result['id'])
            if len(businesses) == 0:
                db.close()
                return jsonify({"error": "Все ваши бизнесы заблокированы. Обратитесь к администратору."}), 403
        
        db.close()
        
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
        traceback.print_exc()
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
        
        # Проверяем, что это именно demyanovap@yandex.ru
        if user_data.get('email') != 'demyanovap@yandex.ru':
            return jsonify({"error": "Доступ запрещён"}), 403
        
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
        
        user_id = user_data['user_id']
        
        # Проверяем, является ли пользователь владельцем сети
        # Получаем все сети пользователя
        user_networks = db.get_user_networks(user_id)
        
        if not user_networks or len(user_networks) == 0:
            db.close()
            # Если у пользователя нет сетей, возвращаем пустой список
            return jsonify({"success": True, "is_network": False, "locations": []})
        
        # Получаем все точки всех сетей пользователя
        all_locations = []
        for network in user_networks:
            network_id = network['id']
            locations = db.get_businesses_by_network(network_id)
            all_locations.extend(locations)
        
        db.close()
        
        return jsonify({
            "success": True,
            "is_network": len(user_networks) > 0,
            "locations": all_locations
        })
        
    except Exception as e:
        print(f"❌ Ошибка получения точек сети: {e}")
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
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        owner_id = row[0]
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
            if org_id:
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
    # Регистрируем Blueprint для ChatGPT интеграции
    app.register_blueprint(chatgpt_bp)
    # Регистрируем Blueprint для Stripe интеграции
    app.register_blueprint(stripe_bp)
    
    # Инициализируем схему базы данных при первом запуске
    print("🔄 Проверка схемы базы данных...")
    init_database_schema()
    
    print("SEO анализатор запущен на порту 8000")
    app.run(host='0.0.0.0', port=8000, debug=False)