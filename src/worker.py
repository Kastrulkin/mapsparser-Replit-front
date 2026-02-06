import time
# PostgreSQL-only: sqlite3 больше не используется
import os
import uuid
import json
import re
from datetime import datetime, timedelta
import signal
import sys
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# New imports
from database_manager import DatabaseManager
from yandex_business_sync_worker import YandexBusinessSyncWorker
from external_sources import ExternalReview, ExternalSource, ExternalPost, ExternalStatsPoint, make_stats_id
from dateutil import parser as date_parser
from parser_interception import parse_yandex_card

# ==================== PART A: OID MISMATCH HARDENING ====================

@dataclass
class ColumnsInfo:
    """Результат интроспекции колонок таблицы"""
    ok: bool
    columns: set[str]
    source: str  # "information_schema" | "pragma" | "error"
    error: Optional[str]

# Константы для raw capture
MAX_CAPTURE_BYTES = 300_000

# ==================== PART B: CAPTCHA SESSION REGISTRY ====================
# Реестр активных сессий браузера для human-in-the-loop обработки капчи
ACTIVE_CAPTCHA_SESSIONS: dict[str, dict] = {}
"""
Структура записи:
{
    "session_id": {
        "task_id": str,
        "browser": Browser,  # Playwright Browser объект
        "context": BrowserContext,  # Playwright Context объект
        "page": Page,  # Playwright Page объект
        "created_at": datetime,
    }
}
"""

def is_captcha_page(page) -> bool:
    """
    Проверяет, является ли текущая страница страницей с капчей.
    
    Args:
        page: Playwright Page объект
    
    Returns:
        bool: True если это страница с капчей
    """
    try:
        current_url = page.url
        if "/showcaptcha" in current_url:
            return True
        
        title = page.title()
        if any(keyword in title for keyword in ["Ой!", "Captcha", "Robot", "Вы не робот"]):
            return True
        
        # Проверка селекторов капчи
        try:
            if page.locator(".smart-captcha").count() > 0:
                return True
            if page.locator("input[name='smart-token']").count() > 0:
                return True
            if page.get_by_text("Подтвердите, что вы не робот").is_visible():
                return True
        except Exception:
            pass
        
        return False
    except Exception:
        return False

def park_task_for_captcha(task_id: str, page, session_id: str, token: str, vnc_path: str, browser=None, context=None) -> None:
    """
    Сохраняет задачу в статус WAIT_CAPTCHA и сохраняет сессию браузера.
    
    Args:
        task_id: ID задачи в очереди
        page: Playwright Page объект
        session_id: UUID сессии
        token: одноразовый токен для доступа
        vnc_path: путь для открытия в кабинете
        browser: Playwright Browser объект (опционально)
        context: Playwright Context объект (опционально)
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        captcha_url = page.url
        captcha_started_at = datetime.now()
        
        # Сохраняем screenshot
        screenshot_path = None
        try:
            screenshot_bytes = page.screenshot()
            screenshot_dir = "debug_data/captcha_screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, f"{task_id}_{session_id}.png")
            with open(screenshot_path, "wb") as f:
                f.write(screenshot_bytes)
            print(f"📸 Screenshot сохранён: {screenshot_path}")
        except Exception as e:
            print(f"⚠️ Не удалось сохранить screenshot: {e}")
        
        # Обновляем задачу в БД (добавляем captcha_token_expires_at если колонка есть)
        captcha_token_expires_at = captcha_started_at + timedelta(minutes=30)  # TTL 30 минут
        try:
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'captcha',
                    captcha_required = TRUE,
                    captcha_url = %s,
                    captcha_session_id = %s,
                    captcha_token = %s,
                    captcha_token_expires_at = %s,
                    captcha_vnc_path = %s,
                    captcha_started_at = %s,
                    captcha_status = 'waiting',
                    resume_requested = FALSE,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (captcha_url, session_id, token, captcha_token_expires_at, vnc_path, captcha_started_at, task_id))
        except Exception as e:
            # Если колонка captcha_token_expires_at не существует, обновляем без неё
            if 'captcha_token_expires_at' in str(e) or 'column' in str(e).lower():
                cursor.execute("""
                    UPDATE parsequeue 
                    SET status = 'captcha',
                        captcha_required = TRUE,
                        captcha_url = %s,
                        captcha_session_id = %s,
                        captcha_token = %s,
                        captcha_vnc_path = %s,
                        captcha_started_at = %s,
                        captcha_status = 'waiting',
                        resume_requested = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (captcha_url, session_id, token, vnc_path, captcha_started_at, task_id))
            else:
                raise
        conn.commit()
        cursor.close()
        conn.close()
        
        # Сохраняем сессию в реестре
        ACTIVE_CAPTCHA_SESSIONS[session_id] = {
            "task_id": task_id,
            "browser": browser,
            "context": context,
            "page": page,
            "created_at": captcha_started_at,
        }
        
        print(f"✅ Задача {task_id} поставлена в очередь ожидания решения капчи (сессия: {session_id})")
    except Exception as e:
        print(f"❌ Ошибка при сохранении задачи капчи: {e}")
        import traceback
        traceback.print_exc()

def wait_for_resume(task_id: str, timeout_sec: int = 1800) -> bool:
    """
    Ожидает запрос на продолжение парсинга от оператора.
    
    Args:
        task_id: ID задачи
        timeout_sec: таймаут ожидания в секундах (по умолчанию 30 минут)
    
    Returns:
        bool: True если получен запрос на продолжение, False при таймауте
    """
    start_time = datetime.now()
    poll_interval = 3  # Проверяем каждые 3 секунды
    
    while True:
        elapsed = (datetime.now() - start_time).total_seconds()
        if elapsed >= timeout_sec:
            print(f"⏱️ Таймаут ожидания решения капчи для задачи {task_id}")
            return False
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT resume_requested, captcha_status
                FROM parsequeue
                WHERE id = %s
            """, (task_id,))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if row:
                resume_requested = row.get('resume_requested') if isinstance(row, dict) else row[0]
                captcha_status = row.get('captcha_status') if isinstance(row, dict) else row[1]
                
                if resume_requested or captcha_status == 'resume':
                    print(f"✅ Получен запрос на продолжение парсинга для задачи {task_id}")
                    return True
            
            time.sleep(poll_interval)
        except Exception as e:
            print(f"⚠️ Ошибка при проверке resume_requested: {e}")
            time.sleep(poll_interval)

def verify_captcha_solved(page, timeout_sec: int = 10) -> bool:
    """
    Проверяет, что капча решена (страница больше не содержит капчу).
    Усиленная проверка: отсутствие капчи + наличие целевого селектора.
    
    Args:
        page: Playwright Page объект
        timeout_sec: таймаут ожидания целевого селектора (по умолчанию 10 сек)
    
    Returns:
        bool: True если капча решена И целевая страница загружена
    """
    try:
        current_url = page.url
        if "/showcaptcha" in current_url:
            return False
        
        title = page.title()
        if any(keyword in title for keyword in ["Ой!", "Captcha", "Robot", "Вы не робот"]):
            return False
        
        # Проверка селекторов капчи
        try:
            if page.locator(".smart-captcha").count() > 0:
                return False
            if page.locator("input[name='smart-token']").count() > 0:
                return False
            # Проверка текста капчи
            if page.get_by_text("Вы не робот", exact=False).is_visible():
                return False
            if page.get_by_text("Подтвердите, что вы не робот", exact=False).is_visible():
                return False
            # Проверка iframe капчи
            if page.locator("iframe[src*='captcha']").count() > 0:
                return False
        except Exception:
            pass
        
        # КРИТИЧНО: Проверяем наличие целевого селектора карточки организации
        # Если селектор есть - значит капча решена и мы на нужной странице
        try:
            page.wait_for_selector(
                "h1, div.business-card-title-view, div.card-title-view__title, "
                "div.orgpage-header-view__header, "
                "div.orgpage-header-view__header-wrapper > h1",
                timeout=timeout_sec * 1000,
            )
            print("✅ Целевой селектор найден - капча решена")
            return True
        except Exception:
            print("⚠️ Целевой селектор не найден - возможно капча не решена или страница не загрузилась")
            return False
        
    except Exception as e:
        print(f"⚠️ Ошибка при проверке капчи: {e}")
        return False

def close_session(session_id: str) -> None:
    """
    Закрывает сессию браузера и удаляет её из реестра.
    
    Args:
        session_id: UUID сессии
    """
    if session_id not in ACTIVE_CAPTCHA_SESSIONS:
        return
    
    session = ACTIVE_CAPTCHA_SESSIONS[session_id]
    try:
        browser = session.get("browser")
        if browser:
            browser.close()
            print(f"🔒 Браузер закрыт для сессии {session_id}")
    except Exception as e:
        print(f"⚠️ Ошибка при закрытии браузера: {e}")
    
    del ACTIVE_CAPTCHA_SESSIONS[session_id]
    print(f"🗑️ Сессия {session_id} удалена из реестра")

def get_expected_oid(queue_dict: dict) -> Optional[str]:
    """
    Извлекает expected_oid из задачи.
    
    Приоритет:
    1. queue_dict["oid"] (если есть в задаче)
    2. Извлечение из URL паттерном /org/.../<oid>/
    """
    # Если в задаче есть oid
    if queue_dict.get("oid"):
        return str(queue_dict["oid"])
    
    # Извлекаем из URL
    url = queue_dict.get("url", "")
    if not url:
        return None
    
    # Паттерн: /org/.../<oid>/ или /org/<oid>/
    patterns = [
        r'/org/[^/]+/(\d+)/',
        r'/org/(\d+)/',
        r'oid=(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_extracted_oid(card_data: dict) -> Optional[str]:
    """
    Извлекает extracted_oid из результата парсинга.
    
    Приоритет:
    1. card_data["organization"]["oid"]
    2. card_data["organization"]["id"]
    3. Парсинг из card_data["organization"]["uri"] (ymapsbm1://org?oid=...)
    4. card_data["oid"] (верхний уровень)
    """
    organization = card_data.get("organization", {})
    
    # Приоритет 1: organization.oid
    if organization.get("oid"):
        return str(organization["oid"])
    
    # Приоритет 2: organization.id
    if organization.get("id"):
        return str(organization["id"])
    
    # Приоритет 3: парсинг из organization.uri
    uri = organization.get("uri", "")
    if uri:
        match = re.search(r'oid=(\d+)', uri)
        if match:
            return match.group(1)
    
    # Приоритет 4: верхний уровень
    if card_data.get("oid"):
        return str(card_data["oid"])
    
    return None

def is_oid_mismatch(expected_oid: Optional[str], extracted_oid: Optional[str]) -> tuple[bool, str]:
    """
    Проверяет OID mismatch.
    
    Returns:
        (is_mismatch: bool, reason: str)
        reason может быть: 'oid_mismatch' | 'missing_expected_oid' | 'missing_extracted_oid' | ''
    """
    if expected_oid is None:
        return False, 'missing_expected_oid'
    
    if extracted_oid is None:
        return False, 'missing_extracted_oid'
    
    if str(expected_oid) != str(extracted_oid):
        return True, 'oid_mismatch'
    
    return False, ''

# ==================== PART E: RAW CAPTURE HYGIENE ====================

def truncate_payload(obj_or_str, max_bytes: int = MAX_CAPTURE_BYTES) -> str:
    """
    Безопасно урезает payload до max_bytes.
    
    Returns:
        JSON-строка (урезанная если нужно)
    """
    try:
        if isinstance(obj_or_str, str):
            payload_str = obj_or_str
        else:
            payload_str = json.dumps(obj_or_str, ensure_ascii=False, default=str)
        
        payload_bytes = payload_str.encode('utf-8')
        if len(payload_bytes) <= max_bytes:
            return payload_str
        
        # Урезаем до max_bytes (с запасом для "...[truncated]")
        truncated_bytes = payload_bytes[:max_bytes - 50]
        truncated_str = truncated_bytes.decode('utf-8', errors='ignore')
        return truncated_str + "...[truncated]"
    except Exception as e:
        return f'{{"error": "truncate_payload failed: {e}"}}'

def save_raw_capture(
    raw_capture: dict,
    reason: str,
    queue_dict: dict,
    card_data: dict,
    parse_status: str,
    missing_sections: list
) -> str:
    """
    Сохраняет raw capture в структурированном формате с метаданными.
    
    Returns:
        filepath сохранённого файла
    """
    try:
        # Подготовка метаданных
        ts = datetime.now().isoformat()
        task_id = queue_dict.get('id', 'unknown')
        business_id = queue_dict.get('business_id', '')
        url = queue_dict.get('url', '')
        expected_oid = get_expected_oid(queue_dict) or 'nooid'
        extracted_oid = get_extracted_oid(card_data) or 'nooid'
        
        # Урезаем raw_capture если нужно
        raw_capture_truncated = truncate_payload(raw_capture, MAX_CAPTURE_BYTES)
        
        # Структурированный формат
        capture_data = {
            'meta': {
                'ts': ts,
                'task_id': task_id,
                'business_id': business_id,
                'url': url,
                'expected_oid': expected_oid,
                'extracted_oid': extracted_oid,
                'status': parse_status,
                'reason': reason,
                'missing_sections': missing_sections,
                'endpoints': card_data.get('_raw_capture', {}).get('endpoints', []),
                'schema_hash': card_data.get('_raw_capture', {}).get('schema_hash'),
            },
            'raw_capture': json.loads(raw_capture_truncated) if isinstance(raw_capture_truncated, str) else raw_capture_truncated,
        }
        
        # Создаём директорию
        debug_dir = os.path.join(os.getcwd(), 'debug_data', reason)
        os.makedirs(debug_dir, exist_ok=True)
        
        # Имя файла: {ts}_{task_id}_{expected_oid or 'nooid'}.json
        safe_ts = ts.replace(':', '-').replace('.', '-')
        filename = f"{safe_ts}_{task_id}_{expected_oid}.json"
        filepath = os.path.join(debug_dir, filename)
        
        # Сохраняем
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(capture_data, f, ensure_ascii=False, indent=2)
        
        return filepath
    except Exception as e:
        print(f"⚠️ Не удалось сохранить raw capture: {e}")
        return ""

# ==================== PART B: COLUMNS INFO CONTRACT ====================

def get_db_connection():
    """Получить соединение с PostgreSQL базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

def _handle_worker_error(queue_id: str, error_msg: str):
    """Обновить статус задачи на error с сообщением"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parsequeue 
            SET status = 'error', 
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (error_msg, queue_id))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as ex:
        print(f"❌ Не удалось обновить статус ошибки для {queue_id}: {ex}")

def _extract_date_from_review(review: dict) -> str | int | float | None:
    """Извлечь дату из отзыва, проверяя различные поля"""
    date_fields = ['date', 'published_at', 'publishedAt', 'created_at', 'createdAt', 'time', 'timestamp']
    date_value = review.get('date')
    
    if date_value:
        if isinstance(date_value, str):
            return date_value.strip()
        return date_value
    
    # Пробуем другие поля
    for field in date_fields[1:]:
        date_value = review.get(field)
        if date_value:
            if isinstance(date_value, str):
                return date_value.strip()
            return date_value
    
    return None

def _parse_timestamp_to_datetime(timestamp: int | float) -> datetime | None:
    """Парсить timestamp в datetime (миллисекунды или секунды)"""
    try:
        if timestamp > 1e10:  # Миллисекунды
            return datetime.fromtimestamp(timestamp / 1000.0)
        return datetime.fromtimestamp(timestamp)  # Секунды
    except Exception:
        return None

def _parse_relative_date(date_str: str) -> datetime | None:
    """Парсить относительные даты: 'сегодня', 'вчера', '2 дня назад' и т.д."""
    date_lower = date_str.lower()
    
    if 'сегодня' in date_lower or 'today' in date_lower:
        return datetime.now()
    if 'вчера' in date_lower or 'yesterday' in date_lower:
        return datetime.now() - timedelta(days=1)
    
    # Дни назад
    if any(word in date_str for word in ['дня', 'день', 'дней']):
        days_match = re.search(r'(\d+)', date_str)
        if days_match:
            return datetime.now() - timedelta(days=int(days_match.group(1)))
    
    # Недели назад
    if any(word in date_str for word in ['неделю', 'недели', 'недель']):
        weeks_match = re.search(r'(\d+)', date_str)
        weeks_ago = int(weeks_match.group(1)) if weeks_match else 1
        return datetime.now() - timedelta(weeks=weeks_ago)
    
    # Месяцы назад
    if any(word in date_str for word in ['месяц', 'месяца', 'месяцев']):
        months_match = re.search(r'(\d+)', date_str)
        months_ago = int(months_match.group(1)) if months_match else 1
        return datetime.now() - timedelta(days=months_ago * 30)
    
    # Годы назад
    if any(word in date_str for word in ['год', 'года', 'лет']):
        years_match = re.search(r'(\d+)', date_str)
        years_ago = int(years_match.group(1)) if years_match else 1
        return datetime.now() - timedelta(days=years_ago * 365)
    
    return None

def _parse_russian_date(date_str: str) -> datetime | None:
    try:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        parts = date_str.lower().split()
        if len(parts) >= 2:
            day_str = parts[0]
            month_str = parts[1]
            year_str = parts[2] if len(parts) > 2 else str(datetime.now().year)
            
            # Очистка от лишних символов
            day_str = re.sub(r'\D', '', day_str)
            year_str = re.sub(r'\D', '', year_str)
            # Очищаем месяц от знаков препинания (запятые, точки)
            month_str = re.sub(r'[^\w\s]', '', month_str, flags=re.UNICODE) 
            
            if not day_str or not month_str:
                return None
                
            day = int(day_str)
            month = months.get(month_str)
            year = int(year_str)
            
            if month:
                return datetime(year, month, day)
                
    except Exception:
        pass
    return None

def _parse_date_string(date_str: str) -> datetime | None:
    """Парсить строку даты в datetime"""
    if not date_str or not isinstance(date_str, str):
        return None
    
    date_str = date_str.strip()
    if not date_str:
        return None
    
    # Пробуем относительные даты
    relative = _parse_relative_date(date_str)
    if relative:
        return relative
    
    # Пробуем русские даты (27 января 2026)
    russian_date = _parse_russian_date(date_str)
    if russian_date:
        return russian_date
    
    # Пробуем ISO формат
    try:
        if 'T' in date_str or 'Z' in date_str or date_str.count('-') >= 2:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except Exception:
        pass
    
    # Пробуем dateutil для других форматов
    try:
        from dateutil import parser as date_parser
        return date_parser.parse(date_str, fuzzy=True)
    except Exception:
        return None

def _is_parsing_successful(card_data: dict, queue_dict: dict = None, business_id: str = None) -> tuple:
    """
    Проверяет, успешен ли парсинг с жёсткими правилами.
    
    Правила:
    - Если oid_mismatch → fail
    - Если нет organization → fail
    - Если organization есть, но отсутствуют секции → partial
    - Если все ключевые секции есть → success
    
    Returns:
        (status: str, reason: str, missing_sections: list)
        status: "success" | "partial" | "fail"
        reason: описание причины
        missing_sections: список недостающих секций (для UI)
    """
    # Проверка на капчу
    if card_data.get("error") == "captcha_detected":
        return "fail", "captcha_detected", ["captcha"]
    
    # Проверка на ошибку
    if card_data.get("error"):
        return "fail", f"error: {card_data.get('error')}", ["error"]
    
    # ========== PART A: OID MISMATCH CHECK (источник истины) ==========
    expected_oid = None
    if queue_dict:
        expected_oid = get_expected_oid(queue_dict)
    else:
        expected_oid = card_data.get('expected_oid')
    
    extracted_oid = get_extracted_oid(card_data)
    
    is_mismatch, oid_reason = is_oid_mismatch(expected_oid, extracted_oid)
    if is_mismatch:
        return "fail", f"oid_mismatch: expected {expected_oid}, got {extracted_oid}", ["oid_mismatch"]
    
    if oid_reason == 'missing_extracted_oid':
        # Нет extracted_oid - проверяем есть ли organization вообще
        organization = card_data.get('organization', {})
        if not organization or not organization.get('title'):
            return "fail", "missing_organization", ["missing_organization"]
    
    # ========== PART D: СТРОГИЕ ПРАВИЛА SUCCESS/PARTIAL/FAIL ==========
    organization = card_data.get('organization', {})
    
    # Правило: нет organization → fail
    if not organization or not organization.get('title'):
        # Fallback для старого формата (обратная совместимость)
        title = (
            card_data.get('title') or 
            card_data.get('overview', {}).get('title')
        )
        if not title:
            return "fail", "missing_organization", ["missing_organization"]
        # Если есть title на верхнем уровне - считаем что organization есть (legacy)
        organization = {'title': title}
    
    # Если organization есть, проверяем секции
    missing_sections = []
    
    # Критичные секции (если нет - partial)
    if not card_data.get('reviews'):
        missing_sections.append('reviews')
    if not card_data.get('services'):
        missing_sections.append('services')
    if not card_data.get('news'):
        missing_sections.append('news')
    
    # Определяем статус
    if missing_sections:
        return "partial", f"missing_sections: {', '.join(missing_sections)}", missing_sections
    else:
        return "success", "success", []

def _has_cabinet_account(business_id: str) -> tuple[bool, str | None]:
    """
    Проверяет, есть ли у бизнеса аккаунт в личном кабинете.
    
    Returns:
        (has_account: bool, account_id: str | None)
    """
    if not business_id:
        return False, None
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            """
            SELECT id 
            FROM external_business_accounts
            WHERE business_id = %s 
              AND provider = 'yandex_business'
              AND is_active = TRUE
            LIMIT 1
            """,
            (business_id,),
        )
        
        row = cursor.fetchone()
        if row is None:
            return False, None

        # RealDictCursor / dict
        if hasattr(row, "get"):
            account_id = row.get("id") or row.get("account_id")
            if account_id is None:
                # fallback: первое значение
                try:
                    account_id = next(iter(row.values()))
                except Exception:
                    account_id = None
        elif isinstance(row, dict):
            account_id = row.get("id") or row.get("account_id") or next(iter(row.values()), None)
        elif isinstance(row, (tuple, list)) and len(row) > 0:
            account_id = row[0]
        else:
            account_id = None

        if account_id is None:
            return False, None
        return True, str(account_id)
    finally:
        cursor.close()
        conn.close()

def get_table_columns(cursor, table_name: str) -> ColumnsInfo:
    """
    Получить информацию о колонках таблицы.

    DB-aware реализация:
    - PostgreSQL: information_schema.columns (с current_schema())
    - SQLite: PRAGMA table_info(table_name)

    Returns:
        ColumnsInfo с явным контрактом (ok/columns/source/error)
    """
    kind = _detect_db_kind(cursor)
    table_name_lower = table_name.lower()

    # PostgreSQL
    if kind == "postgres":
        try:
            cursor.execute(
                """
        SELECT column_name 
        FROM information_schema.columns 
                WHERE table_schema = current_schema() AND table_name = %s
        ORDER BY ordinal_position
                """,
                (table_name_lower,),
            )
            rows = cursor.fetchall()
            columns: set[str] = set()
            for row in rows:
                name = None
                if hasattr(row, "get"):
                    name = row.get("column_name") or row.get("name")
                elif isinstance(row, dict):
                    name = row.get("column_name") or row.get("name")
                elif isinstance(row, (tuple, list)) and row:
                    name = row[0]
                if name:
                    columns.add(str(name))
            return ColumnsInfo(ok=True, columns=columns, source="information_schema", error=None)
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Ошибка чтения information_schema для {table_name} (PostgreSQL): {error_msg}")
            # Пробуем PRAGMA как fallback
            pass

    # SQLite или fallback для PostgreSQL
    if kind == "sqlite" or kind == "postgres":
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            rows = cursor.fetchall()
            columns: set[str] = set()
            for row in rows:
                name = None
                if hasattr(row, "get"):
                    name = row.get("name") or row.get("column_name")
                elif isinstance(row, dict):
                    name = row.get("name") or row.get("column_name")
                elif isinstance(row, (tuple, list)) and len(row) > 1:
                    # В PRAGMA table_info второй столбец (index 1) — имя
                    name = row[1]
                if name:
                    columns.add(str(name))
            return ColumnsInfo(ok=True, columns=columns, source="pragma", error=None)
        except Exception as e:
            error_msg = str(e)
            print(f"⚠️ Ошибка PRAGMA table_info для {table_name} (SQLite): {error_msg}")
            return ColumnsInfo(ok=False, columns=set(), source="error", error=error_msg)

    # Неизвестный тип БД
    error_msg = f"Неизвестный тип БД: {kind}"
    print(f"⚠️ get_table_columns: {error_msg}")
    return ColumnsInfo(ok=False, columns=set(), source="error", error=error_msg)

def _ensure_column_exists(cursor, conn, table_name, column_name, column_type="TEXT"):
    """
    Проверяет и добавляет колонку, если её нет.

    Важно:
    - НЕ делает commit/rollback — это ответственность вызывающего кода.
    - Работает только для явно разрешённых таблиц (ParseQueue, MapParseResults).
    - Использует ADD COLUMN IF NOT EXISTS для безопасности multi-worker.
    - Интроспекция используется только для логов, не для принятия решений.
    """
    try:
        ALLOWED_TABLES = {"parsequeue", "mapparseresults"}
        table_name_lower = table_name.lower()
        if table_name_lower not in ALLOWED_TABLES:
            raise ValueError(f"Неразрешенная таблица: {table_name}")
        
        # Интроспекция для логов (опционально)
        columns_info = get_table_columns(cursor, table_name_lower)
        if columns_info.ok and column_name in columns_info.columns:
            # Колонка уже существует
            return
        
        # Allowlist для типов колонок (с optional DEFAULT ...)
        allowed_bases = {"TEXT", "TIMESTAMP", "INTEGER", "JSONB", "BOOLEAN"}
        raw_type = (column_type or "TEXT").strip()
        base = raw_type.split()[0].upper()
        if base not in allowed_bases:
            raise ValueError(f"Неразрешённый тип колонки '{column_type}' для {table_name}.{column_name}")

        # Используем ADD COLUMN IF NOT EXISTS для безопасности multi-worker
        if _psql_sql is None:
            # Без psycopg2.sql используем простой SQL (только для PostgreSQL)
            kind = _detect_db_kind(cursor)
            if kind == "postgres":
                print(f"📝 Добавляю поле {column_name} в {table_name_lower} типом '{raw_type}' (IF NOT EXISTS)...")
                cursor.execute(
                    f'ALTER TABLE {table_name_lower} ADD COLUMN IF NOT EXISTS {column_name} {raw_type}'
                )
            else:
                print(f"⚠️ psycopg2.sql недоступен, пропускаем ALTER TABLE для {table_name}.{column_name}")
                return
        else:
            print(f"📝 Добавляю поле {column_name} в {table_name_lower} типом '{raw_type}' (IF NOT EXISTS)...")
            query = _psql_sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} " + raw_type).format(
                _psql_sql.Identifier(table_name_lower),
                _psql_sql.Identifier(column_name),
            )
            cursor.execute(query)
    except Exception as e:
        print(f"⚠️ Ошибка проверки/добавления колонки {column_name} в {table_name}: {e}")


def init_schema_checks() -> None:
    """
    Единоразовая проверка и миграция схемы для таблиц, с которыми работает worker.

    ВАЖНО:
    - Вызывается один раз при старте модуля (до основного цикла).
    - Делает один общий commit или rollback.
    - Любая ошибка не должна останавливать запуск worker.
    """
    print("🔧 init_schema_checks: старт проверки схемы очередей и MapParseResults")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        kind = _detect_db_kind(cursor)
        if kind != "postgres":
            print(f"ℹ️ init_schema_checks: DB_KIND={kind}, миграции worker пропущены")
            return

        # Простая проверка существования ParseQueue через to_regclass
        try:
            cursor.execute("SELECT to_regclass('public.parsequeue') AS tbl")
            reg_result = cursor.fetchone()
            tbl_value = None
            if reg_result is not None:
                if hasattr(reg_result, "get"):
                    tbl_value = reg_result.get("tbl")
                elif isinstance(reg_result, dict):
                    tbl_value = reg_result.get("tbl")
                elif isinstance(reg_result, (tuple, list)) and reg_result:
                    tbl_value = reg_result[0]
            if tbl_value is None:
                print("⚠️ init_schema_checks: таблица ParseQueue не найдена, вызываю init_database_schema()")
                from init_database_schema import init_database_schema
                init_database_schema()
        except Exception as e:
            print(f"⚠️ init_schema_checks: ошибка проверки существования ParseQueue: {e}")

        # После возможной инициализации схемы — заново открываем соединение, чтобы быть уверенными в актуальности
        cursor.close()
        conn.close()
        conn = get_db_connection()
        cursor = conn.cursor()

        # Проверяем/создаём недостающие поля в ParseQueue
        _ensure_column_exists(cursor, conn, "ParseQueue", "retry_after", "TIMESTAMP")
        _ensure_column_exists(cursor, conn, "ParseQueue", "business_id", "TEXT")
        _ensure_column_exists(cursor, conn, "ParseQueue", "task_type", "TEXT DEFAULT 'parse_card'")
        _ensure_column_exists(cursor, conn, "ParseQueue", "account_id", "TEXT")
        _ensure_column_exists(cursor, conn, "ParseQueue", "source", "TEXT")
        _ensure_column_exists(cursor, conn, "ParseQueue", "error_message", "TEXT")
        _ensure_column_exists(cursor, conn, "ParseQueue", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # Базовые поля профиля в MapParseResults (используются в нескольких местах)
        _ensure_column_exists(cursor, conn, "MapParseResults", "unanswered_reviews_count", "INTEGER")
        profile_columns = [
            ("is_verified", "INTEGER DEFAULT 0"),
            ("phone", "TEXT"),
            ("website", "TEXT"),
            ("messengers", "TEXT"),
            ("working_hours", "TEXT"),
            ("competitors", "TEXT"),
            ("services_count", "INTEGER DEFAULT 0"),
            ("profile_completeness", "INTEGER DEFAULT 0"),
            ("parse_status", "TEXT"),
            ("missing_sections", "TEXT"),
        ]
        for col_name, col_type in profile_columns:
            _ensure_column_exists(cursor, conn, "MapParseResults", col_name, col_type)

            conn.commit()
        print("✅ init_schema_checks: схема очередей и MapParseResults проверена/обновлена")
    except Exception as e:
        print(f"⚠️ init_schema_checks: ошибка при миграции схемы, выполняю rollback: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

# Используем parser_config для автоматического выбора парсера (interception или legacy)
try:
    # Используем psycopg2.sql для безопасной сборки ALTER TABLE (PostgreSQL)
    from psycopg2 import sql as _psql_sql
except ImportError:  # sqlite-only окружение
    _psql_sql = None

# Глобальный кэш типа БД для интроспекции схемы
_DB_KIND: str | None = None


def _detect_db_kind(cursor) -> str:
    """
    Определяем тип БД один раз и кэшируем результат.
    Возвращает: 'postgres', 'sqlite' или 'unknown'
    """
    global _DB_KIND
    if _DB_KIND:
        return _DB_KIND

    # Пытаемся определить PostgreSQL по SELECT version()
    try:
        cursor.execute("SELECT version()")
        row = cursor.fetchone()
        ver_text = None
        if hasattr(row, "get"):
            # RealDictRow / dict-подобный
            try:
                ver_text = next(iter(row.values()))
            except Exception:
                ver_text = None
        elif isinstance(row, dict):
            try:
                ver_text = next(iter(row.values()))
            except Exception:
                ver_text = None
        elif isinstance(row, (tuple, list)) and row:
            ver_text = row[0]
        if ver_text and "PostgreSQL" in str(ver_text):
            _DB_KIND = "postgres"
            return _DB_KIND
    except Exception:
        # Версия может не поддерживаться — пробуем sqlite
        pass

    # Пытаемся определить SQLite
    try:
        cursor.execute("SELECT sqlite_version()")
        _ = cursor.fetchone()
        _DB_KIND = "sqlite"
        return _DB_KIND
    except Exception:
        pass

    _DB_KIND = "unknown"
    print("⚠️ Не удалось определить тип БД, считаем DB_KIND='unknown'")
    return _DB_KIND


def _recover_lost_captcha_sessions():
    """
    Восстанавливает состояние после рестарта воркера.
    Помечает задачи с потерянными сессиями как expired.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Находим задачи со status='captcha' AND captcha_status='waiting'
        cursor.execute("""
            SELECT id, captcha_session_id
            FROM parsequeue
            WHERE status = 'captcha' 
              AND captcha_status = 'waiting'
        """)
        rows = cursor.fetchall()
        
        expired_count = 0
        for row in rows:
            task_id = row.get('id') if isinstance(row, dict) else row[0]
            session_id = row.get('captcha_session_id') if isinstance(row, dict) else row[1]
            
            # Если сессии нет в реестре - помечаем как expired
            if session_id and session_id not in ACTIVE_CAPTCHA_SESSIONS:
                cursor.execute("""
                    UPDATE parsequeue 
                    SET captcha_status = 'expired',
                        error_message = 'captcha session lost (worker restarted)',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (task_id,))
                expired_count += 1
                print(f"⚠️ Задача {task_id}: сессия {session_id} потеряна после рестарта → expired")
        
        if expired_count > 0:
            conn.commit()
            print(f"🔄 Восстановление после рестарта: {expired_count} задач помечено как expired")
        else:
            print("✅ Восстановление после рестарта: потерянных сессий не найдено")
    except Exception as e:
        print(f"⚠️ Ошибка при восстановлении сессий: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def _recover_lost_captcha_sessions():
    """
    Восстанавливает состояние после рестарта воркера.
    Помечает задачи с потерянными сессиями как expired.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Находим задачи со status='captcha' AND captcha_status='waiting'
        cursor.execute("""
            SELECT id, captcha_session_id
            FROM parsequeue
            WHERE status = 'captcha' 
              AND captcha_status = 'waiting'
        """)
        rows = cursor.fetchall()
        
        expired_count = 0
        for row in rows:
            task_id = row.get('id') if isinstance(row, dict) else row[0]
            session_id = row.get('captcha_session_id') if isinstance(row, dict) else (row[1] if len(row) > 1 else None)
            
            # Если сессии нет в реестре - помечаем как expired
            if session_id and session_id not in ACTIVE_CAPTCHA_SESSIONS:
                cursor.execute("""
                    UPDATE parsequeue 
                    SET captcha_status = 'expired',
                        error_message = 'captcha session lost (worker restarted)',
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (task_id,))
                expired_count += 1
                print(f"⚠️ Задача {task_id}: сессия {session_id} потеряна после рестарта → expired")
        
        if expired_count > 0:
            conn.commit()
            print(f"🔄 Восстановление после рестарта: {expired_count} задач помечено как expired")
        else:
            print("✅ Восстановление после рестарта: потерянных сессий не найдено")
    except Exception as e:
        print(f"⚠️ Ошибка при восстановлении сессий: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def process_queue():
    """Обрабатывает очередь парсинга из SQLite базы данных"""
    queue_dict = None
    
    # ШАГ 1: Получаем задачу из очереди и обновляем статус (закрываем соединение сразу)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Простая и безопасная проверка существования таблицы ParseQueue для PostgreSQL.
        table_exists = False
        try:
            cursor.execute(
                "SELECT to_regclass('public.parsequeue') AS tbl"
            )
            reg_result = cursor.fetchone()
            if reg_result is not None:
                # RealDictRow / dict / tuple
                tbl_value = None
                if hasattr(reg_result, "get"):
                    tbl_value = reg_result.get("tbl")
                elif isinstance(reg_result, dict):
                    tbl_value = reg_result.get("tbl")
                elif isinstance(reg_result, (tuple, list)) and len(reg_result) > 0:
                    tbl_value = reg_result[0]
                table_exists = tbl_value is not None
        except Exception as e:
            print(f"⚠️ Ошибка при проверке существования таблицы parsequeue через to_regclass: {e}")
        # Получаем заявки из очереди (обрабатываем и parse_card, и sync задачи)
        # Также обрабатываем задачи с captcha_status='waiting' и resume_requested=TRUE
        now = datetime.now().isoformat()
        cursor.execute("""
            SELECT * FROM parsequeue 
            WHERE status = 'pending' 
               OR (status = 'captcha' AND captcha_status = 'waiting' AND resume_requested = TRUE)
               OR (status = 'captcha' AND captcha_status IS NULL AND (retry_after IS NULL OR retry_after <= %s))
            ORDER BY 
                CASE WHEN status = 'pending' THEN 1 
                     WHEN resume_requested = TRUE THEN 2
                     ELSE 3 END,
                created_at ASC 
            LIMIT 1
        """, (now,))
        queue_item = cursor.fetchone()
        
        if not queue_item:
            return
        
        # Преобразуем Row в словарь (row_factory уже установлен в safe_db_utils)
        queue_dict = dict(queue_item)
        
        # Обновляем статус на "processing"
        cursor.execute("UPDATE parsequeue SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", ("processing", queue_dict["id"]))
        conn.commit()
    finally:
        # ВАЖНО: Закрываем соединение перед долгим парсингом
        cursor.close()
        conn.close()
    
    if not queue_dict:
        return
    
    # Определяем тип задачи (по умолчанию parse_card для обратной совместимости)
    task_type = queue_dict.get("task_type") or "parse_card"
    
    print(f"Обрабатываю заявку: {queue_dict.get('id')}, тип: {task_type}")
    
    # Обрабатываем в зависимости от типа задачи
    if task_type == "sync_yandex_business":
        # Синхронизация Яндекс.Бизнес
        _process_sync_yandex_business_task(queue_dict)
        return
    elif task_type == "parse_cabinet_fallback":
        # Fallback парсинг через кабинет
        _process_cabinet_fallback_task(queue_dict)
        return
    elif task_type == "sync_2gis":
        # Синхронизация 2ГИС API
        _process_sync_2gis_task(queue_dict)
        return
    elif task_type == "sync_google_business":
        # Другие источники (будущее)
        print(f"⚠️ Тип задачи {task_type} пока не реализован")
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parsequeue 
            SET status = 'error', 
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (f"Тип задачи {task_type} пока не реализован", queue_dict["id"]))
        conn.commit()
        cursor.close()
        conn.close()
        return
    
    # Обычный парсинг карт (task_type = 'parse_card' или NULL)
    # ШАГ 2: Парсим данные (БЕЗ открытого соединения с БД)
    # Устанавливаем таймаут 10 минут
    def timeout_handler(signum, frame):
        raise TimeoutError("Parsing task timed out after 10 minutes")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)
    
    try:
        if not queue_dict.get("url"):
            raise ValueError("URL не указан для задачи парсинга")
        
        url = queue_dict["url"]
        
        # --- АВТОМАТИЧЕСКОЕ ИСПРАВЛЕНИЕ ССЫЛОК (SPRAV -> MAPS) ---
        if '/sprav/' in url:
            import re
            # Ищем ID организации (цифры)
            sprav_match = re.search(r'/sprav/(\d+)', url)
            if sprav_match:
                org_id = sprav_match.group(1)
                # Конвертируем в публичную ссылку карт
                new_url = f"https://yandex.ru/maps/org/redirect/{org_id}"
                print(f"⚠️ ОБНАРУЖЕНА ССЫЛКА НА ЛИЧНЫЙ КАБИНЕТ: {url}")
                print(f"🔄 АВТОМАТИЧЕСКАЯ ЗАМЕНА НА: {new_url}")
                url = new_url
                queue_dict['url'] = new_url # Обновляем и в словаре

        # Проверяем, нужно ли продолжить парсинг после решения капчи
        resume_captcha = queue_dict.get("resume_requested") and queue_dict.get("captcha_status") == "waiting"
        session_id = queue_dict.get("captcha_session_id")
        
        # Если это продолжение после капчи, восстанавливаем сессию
        if resume_captcha and session_id and session_id in ACTIVE_CAPTCHA_SESSIONS:
            print(f"🔄 Продолжаем парсинг после решения капчи (сессия: {session_id})")
            session = ACTIVE_CAPTCHA_SESSIONS[session_id]
            page = session.get("page")
            browser = session.get("browser")
            context = session.get("context")
            
            # Проверяем, что капча решена
            if not verify_captcha_solved(page):
                print("❌ Капча ещё не решена, ожидаем...")
                # Обновляем статус обратно на waiting
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE parsequeue 
                    SET resume_requested = FALSE,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (queue_dict["id"],))
                conn.commit()
                cursor.close()
                conn.close()
                return
            
            # Продолжаем парсинг в той же сессии (используем специальный режим)
            # Для продолжения парсинга нужно вызвать парсер с уже открытой страницей
            # Пока что просто проверяем, что капча решена и продолжаем стандартный flow
            print("✅ Капча решена, продолжаем парсинг...")
        
        parse_start_time = datetime.now()
        
        # Если это новая задача или капча не была решена, запускаем парсинг с keep_open_on_captcha
        if not resume_captcha:
            # Для новых задач включаем режим keep_open_on_captcha
            card_data = parse_yandex_card(url, keep_open_on_captcha=True, session_registry=ACTIVE_CAPTCHA_SESSIONS)
        else:
            # Для продолжения после капчи используем существующую страницу
            # Пока что просто перезапускаем парсинг (в будущем можно оптимизировать)
            card_data = parse_yandex_card(url, keep_open_on_captcha=False, session_registry=None)
        
        parse_end_time = datetime.now()
        parse_time_ms = int((parse_end_time - parse_start_time).total_seconds() * 1000)
        
        # Проверяем успешность парсинга (передаём queue_dict для OID проверки)
        business_id = queue_dict.get("business_id")
        parse_status, reason, missing_sections = _is_parsing_successful(card_data, queue_dict, business_id)
        
        # Извлекаем OID для логирования
        expected_oid = get_expected_oid(queue_dict) or 'nooid'
        extracted_oid = get_extracted_oid(card_data) or 'nooid'
        
        # Критическая проверка: OID mismatch - не сохраняем данные
        if parse_status == "fail" and "oid_mismatch" in missing_sections:
            # Сохраняем raw capture для анализа
            raw_capture_path = save_raw_capture(
                card_data.get('_raw_capture', {}),
                'oid_mismatch',
                queue_dict,
                card_data,
                parse_status,
                missing_sections
            )
            if raw_capture_path:
                print(f"💾 Raw capture сохранён: {raw_capture_path}")
            
            # Обновляем статус задачи на error
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'error', 
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (f"Parsing failed: {reason}", queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
            
            # Логирование одной строкой
            print(f"📋 TASK={queue_dict['id']} expected_oid={expected_oid} extracted_oid={extracted_oid} status={parse_status} reason={reason} missing={','.join(missing_sections)} parse_time_ms={parse_time_ms}")
            return
        
        fallback_created = False
        if parse_status != "success" and business_id:
            # DISABLE AUTOMATIC FALLBACK (User Request 2026-01-23)
            # Fallback to cabinet parsing should be manual only.
            # has_account, account_id = _has_cabinet_account(business_id)
            # if has_account: ...
            
            # Проверяем, есть ли кабинет для fallback
            # has_account, account_id = _has_cabinet_account(business_id)
            
            # if has_account:
            #     print(f"⚠️ Парсинг неполный ({reason}), создаю задачу fallback через кабинет")
                
            #     # Создаем задачу fallback
            #     fallback_task_id = str(uuid.uuid4())
            #     conn = get_db_connection()
            #     cursor = conn.cursor()
                
            #     try:
            #         cursor.execute("""
            #             INSERT INTO parsequeue (
            #                 id, business_id, account_id, task_type, source,
            #                 status, user_id, url, created_at, updated_at
            #             )
            #             VALUES (%s, %s, %s, 'parse_cabinet_fallback', 'yandex_business',
            #                     'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            #         """, (fallback_task_id, business_id, account_id, queue_dict["user_id"], queue_dict["url"]))
            #         conn.commit()
            #         print(f"✅ Создана задача fallback: {fallback_task_id}")
            #         fallback_created = True
            #     finally:
            #         cursor.close()
            #         conn.close()
            if parse_status == "partial":
                print(f"⚠️ Парсинг частичный ({reason}). Сохраняем доступные данные.")
            else:
                print(f"⚠️ Парсинг неполный ({reason}). Автоматический fallback отключен.")
        
        if card_data.get("error") == "captcha_detected":
            # Если был создан фоллбэк, то считаем задачу выполненной, не уходим в цикл
            if fallback_created:
                print("✅ Капча обнаружена, но создан фоллбэк. Помечаю задачу как выполненную, чтобы не зацикливать.")
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute("UPDATE parsequeue SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", ("completed", queue_dict["id"]))
                    cursor.execute("DELETE FROM parsequeue WHERE id = %s", (queue_dict["id"],))
                    conn.commit()
                finally:
                    cursor.close()
                    conn.close()
                return

            # НОВЫЙ FLOW: Сохраняем сессию браузера для human-in-the-loop
            if card_data.get("captcha_needs_human") and card_data.get("_browser") and card_data.get("_page"):
                print("🔒 Капча обнаружена, сохраняем сессию браузера для human-in-the-loop")
                
                # Защита от утечки Playwright объектов: удаляем их из card_data
                # Объекты сохраняются только в ACTIVE_CAPTCHA_SESSIONS
                browser_obj = card_data.pop("_browser", None)
                context_obj = card_data.pop("_context", None)
                page_obj = card_data.pop("_page", None)
                
                # Проверка: убеждаемся, что в card_data нет Playwright объектов
                assert "_browser" not in card_data, "Playwright объекты не должны попадать в card_data"
                assert "_context" not in card_data, "Playwright объекты не должны попадать в card_data"
                assert "_page" not in card_data, "Playwright объекты не должны попадать в card_data"
                
                # Генерируем session_id и token
                session_id = str(uuid.uuid4())
                token = str(uuid.uuid4())
                vnc_path = f"/tasks/{queue_dict['id']}/captcha?token={token}"
                
                # Сохраняем задачу в статус WAIT_CAPTCHA
                park_task_for_captcha(
                    task_id=queue_dict["id"],
                    page=page_obj,
                    session_id=session_id,
                    token=token,
                    vnc_path=vnc_path,
                    browser=browser_obj,
                    context=context_obj,
                )
                
                print(f"⏳ Задача {queue_dict['id']} ожидает решения капчи оператором")
                print(f"🔗 Ссылка для оператора: {vnc_path}")
                return
            
            # СТАРЫЙ FLOW (fallback): Если keep_open_on_captcha не сработал, используем старую логику
            print("⚠️ Капча обнаружена, но сессия не сохранена. Используем старую логику retry.")
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                retry_after = datetime.now() + timedelta(hours=2)
                cursor.execute("SELECT COUNT(*) AS cnt FROM parsequeue WHERE status = 'pending' AND id != %s", (queue_dict["id"],))
                pending_row = cursor.fetchone()
                if pending_row:
                    if hasattr(pending_row, 'get'):
                        pending_count = pending_row.get('cnt', 0)
                    elif isinstance(pending_row, dict):
                        pending_count = pending_row.get('cnt', 0)
                    elif isinstance(pending_row, (tuple, list)) and len(pending_row) > 0:
                        pending_count = pending_row[0]
                    else:
                        pending_count = 0
                else:
                    pending_count = 0
                
                # Обновляем статус капчи (created_at НЕ обновляем - оставляем оригинальное время создания)
                cursor.execute("UPDATE parsequeue SET status = %s, retry_after = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", 
                             ("captcha", retry_after.isoformat(), queue_dict["id"]))
                conn.commit()
            finally:
                cursor.close()
                conn.close()
            return
        
        # Проверяем таймаут капчи (30 минут)
        if queue_dict.get("captcha_started_at"):
            try:
                captcha_started = datetime.fromisoformat(queue_dict["captcha_started_at"].replace('Z', '+00:00'))
                if isinstance(captcha_started, str):
                    captcha_started = datetime.fromisoformat(captcha_started)
            except:
                try:
                    captcha_started = date_parser.parse(queue_dict["captcha_started_at"])
                except:
                    captcha_started = None
            
            if captcha_started:
                elapsed = (datetime.now() - captcha_started).total_seconds()
                if elapsed > 1800:  # 30 минут
                    print(f"⏱️ Таймаут ожидания решения капчи для задачи {queue_dict['id']}")
                    session_id = queue_dict.get("captcha_session_id")
                    if session_id:
                        close_session(session_id)
                    
                    # Обновляем статус на expired
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE parsequeue 
                        SET captcha_status = 'expired',
                            status = 'error',
                            error_message = 'Капча не решена в течение 30 минут',
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (queue_dict["id"],))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    return
        
        # ШАГ 3: Сохраняем результаты (открываем новое соединение)
        # Сохраняем только если статус success или partial (не fail)
        if parse_status == "fail" and card_data.get("error") != "captcha_detected":
            # Сохраняем raw capture для анализа
            raw_capture_path = save_raw_capture(
                card_data.get('_raw_capture', {}),
                'parsing_fail',
                queue_dict,
                card_data,
                parse_status,
                missing_sections
            )
            if raw_capture_path:
                print(f"💾 Raw capture сохранён: {raw_capture_path}")
            
            # Обновляем статус задачи на error
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'error', 
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (f"Parsing failed: {reason}", queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
            
            # Логирование одной строкой
            print(f"📋 TASK={queue_dict['id']} expected_oid={expected_oid} extracted_oid={extracted_oid} status={parse_status} reason={reason} missing={','.join(missing_sections)} parse_time_ms={parse_time_ms}")
            return

        business_id = queue_dict.get("business_id")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            if business_id:
                # Новая логика: сохраняем в MapParseResults
                print(f"📊 Сохраняю результаты в MapParseResults для business_id={business_id}")
                
                try:
                    # Используем GigaChat для анализа, как и в старой логике
                    from gigachat_analyzer import analyze_business_data
                    from report import generate_html_report
                    
                    print(f"🤖 Запускаем GigaChat анализ для {business_id}...")
                    analysis_result = analyze_business_data(card_data)
                    
                    # Формируем данные для отчета
                    analysis_data = {
                        'score': analysis_result.get('score', 50),
                        'recommendations': analysis_result.get('recommendations', []),
                        'ai_analysis': analysis_result.get('analysis', {})
                    }
                    
                    # Генерируем отчет
                    report_path = generate_html_report(card_data, analysis_data, {})
                    print(f"📄 Отчет сгенерирован: {report_path}")
                    
                    # Сохраняем анализ для использования в рекомендациях (JSON)
                    analysis_json = json.dumps(analysis_data['ai_analysis'], ensure_ascii=False)
                    
                    rating = card_data.get('overview', {}).get('rating', '') or ''
                    reviews_count = card_data.get('reviews_count') or card_data.get('overview', {}).get('reviews_count') or 0
                    news_count = len(card_data.get('news') or [])
                    photos_count = card_data.get('photos_count') or 0
                    
                    # Подсчитываем неотвеченные отзывы
                    reviews_list = []  # Инициализация для избежания NameError
                    reviews = card_data.get('reviews', [])
                    if isinstance(reviews, dict) and 'items' in reviews:
                        reviews_list = reviews['items']
                    elif isinstance(reviews, list):
                        reviews_list = reviews
                    else:
                        reviews_list = []
                    
                    unanswered_reviews_count = sum(1 for r in reviews_list if not r.get('org_reply') or r.get('org_reply', '').strip() == '' or r.get('org_reply', '').strip() == '—')
                    
                    # Sync reviews_count with parsed count if parsed is higher (fixing UI inconsistency)
                    parsed_reviews_count = len(reviews_list)
                    if parsed_reviews_count > int(reviews_count):
                        print(f"⚠️ Parsed more reviews ({parsed_reviews_count}) than header count ({reviews_count}). Updating count.")
                        reviews_count = parsed_reviews_count

                    url_lower = (queue_dict["url"] or '').lower()
                    map_type = 'yandex' if 'yandex' in url_lower else ('google' if 'google' in url_lower else 'other')
                    
                    parse_result_id = str(uuid.uuid4())
                    
                    # Schema-check выполняется один раз при старте через init_schema_checks()
                    # Здесь просто используем колонки (они уже должны существовать)
                    
                    # Извлекаем данные профайла из card_data
                    phone = card_data.get('phone', '') or ''
                    website = card_data.get('site', '') or card_data.get('website', '') or ''
                    
                    # Messengers (собираем из social_links)
                    messengers = []
                    social_links = card_data.get('social_links', [])
                    for link in social_links:
                        link_lower = link.lower()
                        if 'whatsapp' in link_lower or 'wa.me' in link_lower:
                            messengers.append({'type': 'whatsapp', 'url': link})
                        elif 't.me' in link_lower or 'telegram' in link_lower:
                            messengers.append({'type': 'telegram', 'url': link})
                        elif 'viber' in link_lower:
                            messengers.append({'type': 'viber', 'url': link})
                    messengers_json = json.dumps(messengers, ensure_ascii=False) if messengers else None
                    
                    # Working hours (преобразуем в структурированный JSON)
                    hours_full = card_data.get('hours_full', [])
                    hours_json = json.dumps({'schedule': hours_full}, ensure_ascii=False) if hours_full else None
                    
                    # Competitors
                    competitors = card_data.get('competitors', [])
                    competitors_json = json.dumps(competitors, ensure_ascii=False) if competitors else None
                    
                    # Services count
                    products = card_data.get('products', [])
                    services_count = sum(len(cat.get('items', [])) for cat in products)
                    
                    # Ensure numeric values are integers
                    try:
                        photos_count = int(photos_count)
                    except (ValueError, TypeError):
                        photos_count = 0
                        
                    try:
                        reviews_count = int(reviews_count)
                    except (ValueError, TypeError):
                        reviews_count = 0
                        
                    try:
                        news_count = int(news_count)
                    except (ValueError, TypeError):
                        news_count = 0
                    
                    # Verification badge
                    is_verified = 1 if card_data.get('is_verified') else 0
                    
                    # Profile completeness calculation (Service Call)
                    try:
                        from services.analytics_service import calculate_profile_completeness
                        
                        # Prepare data for analysis
                        analysis_data = {
                            'phone': phone,
                            'website': website,
                            'schedule': hours_json,
                            'photos_count': photos_count,
                            'services_count': services_count,
                            'description': card_data.get('description'),
                            'messengers': messengers,
                            'is_verified': is_verified
                        }
                        
                        profile_completeness = calculate_profile_completeness(analysis_data)
                        print(f"   📊 Расчет completed service: {profile_completeness}%")
                        
                    except ImportError:
                         print("⚠️ Не удалось импортировать services.analytics_service")
                         profile_completeness = 0
                    except Exception as comp_err:
                        print(f"⚠️ Ошибка расчета заполненности профиля (worker): {comp_err}")
                        profile_completeness = 0
                    
                    # Извлекаем title и address из новой структуры
                    organization = card_data.get('organization', {})
                    title = (
                        organization.get('title') or 
                        organization.get('title_normalized') or
                        card_data.get('name') or 
                        card_data.get('title', '')
                    )
                    address = (
                        organization.get('address') or 
                        card_data.get('address', '')
                    )
                    
                    # Сохраняем parse_status и missing_sections
                    parse_status_value = parse_status
                    missing_sections_json = json.dumps(missing_sections, ensure_ascii=False)
                    
                    # Всегда используем колонки (они будут созданы если их нет)
                    cursor.execute("""
                        INSERT INTO mapparseresults
                        (id, business_id, url, map_type, rating, reviews_count, unanswered_reviews_count, 
                         news_count, photos_count, report_path, 
                         is_verified, phone, website, messengers, working_hours, competitors, services_count, profile_completeness,
                         title, address, parse_status, missing_sections,
                         created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (
                        parse_result_id,
                        business_id,
                        queue_dict["url"],
                        map_type,
                        str(rating),
                        int(reviews_count or 0),
                        int(unanswered_reviews_count),
                        int(news_count or 0),
                        int(photos_count or 0),
                        report_path,
                        is_verified,
                        phone,
                        website,
                        messengers_json,
                        hours_json,
                        competitors_json,
                        services_count,
                        profile_completeness,
                        title,
                        address,
                        parse_status_value,
                        missing_sections_json
                    ))
                    
                    print(f"✅ Результаты сохранены в MapParseResults: {parse_result_id}")
                    print(f"   📊 Профайл: телефон={bool(phone)}, сайт={bool(website)}, часы={bool(hours_json)}, услуг={services_count}, заполненность={profile_completeness}%")
                    
                    # Commit main connection to release write lock for DatabaseManager
                    conn.commit()
                    
                    # --- ИНИЦИАЛИЗАЦИЯ SyncWorker ДЛЯ СОХРАНЕНИЯ ДЕТАЛЬНЫХ ДАННЫХ ---
                    try:
                        import re
                        
                        db_manager = None
                        try:
                            # Используем DatabaseManager для работы с репозиториями
                            db_manager = DatabaseManager()
                            sync_worker = YandexBusinessSyncWorker()
                            
                            # DEBUG LOGGING
                            try:
                                from worker_debug_helper import debug_log
                                from safe_db_utils import get_db_path
                                db_path_debug = get_db_path()
                                r_len = len(reviews_list) if reviews_list else 0
                                debug_log(f"Worker DB Path: {db_path_debug}")
                                debug_log(f"Reviews in list: {r_len}")
                                debug_log(f"Unanswered calc: {unanswered_reviews_count}")
                            except Exception as e:
                                print(f"Debug log fail: {e}")
                            
                            # 1. СОХРАНЕНИЕ ОТЗЫВОВ (С ДЕДУПЛИКАЦИЕЙ)
                            if reviews_list:
                                external_reviews = []
                                seen_review_ids = set()
                                
                                for review in reviews_list:
                                    if not review.get('text'):
                                        continue
                                    
                                    # Дедупликация: используем ID отзыва или хеш от текста+автора
                                    raw_id = review.get('id')
                                    if raw_id:
                                        unique_key = str(raw_id)
                                    else:
                                        author = review.get('author') or 'Anon'
                                        text_snippet = (review.get('text') or '')[:50]
                                        unique_key = f"{author}_{text_snippet}"
                                        
                                    if unique_key in seen_review_ids:
                                        continue
                                    seen_review_ids.add(unique_key)
                                    
                                    # Генерируем ID для нашей БД (детерминированный, чтобы избегать дублей)
                                    # Используем business_id + author + text snippet (без ответа, чтобы ответ обновлял запись, а не создавал новую)
                                    text_part = (review.get('text') or '').strip()
                                    unique_string = f"{business_id}_{review.get('author')}_{text_part}"
                                    review_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_string))
                                    external_review_id = raw_id or f"html_{review_id}"
                                    
                                    # Инициализация переменных
                                    published_at = None
                                    response_text = None
                                    response_at = None
                                    
                                    # Парсим дату
                                    date_value = _extract_date_from_review(review)
                                    
                                    if date_value:
                                        if isinstance(date_value, (int, float)):
                                            published_at = _parse_timestamp_to_datetime(date_value)
                                        elif isinstance(date_value, str):
                                            published_at = _parse_date_string(date_value)
                                    
                                    # Ответ организации
                                    response_text = review.get('org_reply') or review.get('response_text') or ''
                                    response_text = response_text.strip() if response_text else None
                                    response_at = None
                                    
                                    if review.get('response_date'):
                                        response_at = _parse_date_string(str(review.get('response_date')))
                                    
                                    # Рейтинг
                                    r_val = review.get('score') or review.get('rating')
                                    try:
                                        r_val = int(r_val) if r_val else None
                                    except:
                                        r_val = None
                                    
                                    external_review = ExternalReview(
                                        id=review_id,
                                        business_id=business_id,
                                        source=ExternalSource.YANDEX_MAPS,
                                        external_review_id=external_review_id,
                                        rating=r_val,
                                        author_name=review.get('author') or 'Анонимный пользователь',
                                        text=review.get('text'),
                                        published_at=published_at,
                                        response_text=response_text,
                                        response_at=response_at,
                                        raw_payload=review
                                    )
                                    external_reviews.append(external_review)
                                
                                if external_reviews:
                                    print(f"📊 Найдено отзывов для сохранения: {len(external_reviews)}")
                                    sync_worker._upsert_reviews(db_manager, external_reviews)
                                    print(f"💾 Сохранено {len(external_reviews)} уникальных отзывов (было {len(reviews_list)})")

                            # 2. СОХРАНЕНИЕ НОВОСТЕЙ (Posts)
                            news_items = card_data.get('news', [])
                            if news_items:
                                external_posts = []
                                for item in news_items:
                                    post_text = item.get('text')
                                    if not post_text:
                                        continue
                                        
                                    post_id = str(uuid.uuid4())
                                    # Пытаемся дату достать
                                    pub_at = None
                                    if item.get('date'):
                                        pub_at = _parse_date_string(item['date'])
                                        
                                    ext_post = ExternalPost(
                                        id=post_id,
                                        business_id=business_id,
                                        source=ExternalSource.YANDEX_MAPS,
                                        external_post_id=f"html_{post_id}", # Нет реального ID в HTML
                                        title=item.get('title') or (post_text[:30] + '...'),
                                        text=post_text,
                                        published_at=pub_at, # Keep None if not found, don't fake it with now()
                                        image_url=None, # HTML scraper rarely gets clean image URLs for news context
                                        raw_payload=item
                                    )
                                    external_posts.append(ext_post)
                                
                                if external_posts:
                                    sync_worker._upsert_posts(db_manager, external_posts)
                                    print(f"💾 Сохранено {len(external_posts)} новостей")

                            # 3. СОХРАНЕНИЕ УСЛУГ (Services)
                            products = card_data.get('products')
                            if products:
                                services_count = len(products)
                                # Fetch owner_id for service syncing
                                cursor.execute("SELECT owner_id FROM businesses WHERE id=%s", (business_id,))
                                owner_row = cursor.fetchone()
                                if owner_row:
                                    owner_id = owner_row[0] if isinstance(owner_row, dict) else owner_row[0]
                                    sync_worker._sync_services_to_db(db_manager.conn, business_id, products, owner_id)
                                    print(f"💾 Синхронизировано {services_count} услуг (owner_id={owner_id})")
                                else:
                                    print(f"⚠️ Cannot sync services: owner_id not found for business {business_id}")

                            # 4. СОХРАНЕНИЕ СТАТИСТИКИ (Rating History)
                            if rating and reviews_count is not None:
                                today = datetime.now().strftime('%Y-%m-%d')
                                stats_id = make_stats_id(business_id, ExternalSource.YANDEX_MAPS, today)
                                
                                try:
                                    rating_val = float(rating)
                                except:
                                    rating_val = 0.0
                                    
                                stat_point = ExternalStatsPoint(
                                    id=stats_id,
                                    business_id=business_id,
                                    source=ExternalSource.YANDEX_MAPS,
                                    date=today,
                                    rating=rating_val,
                                    reviews_total=reviews_count,
                                    # Остальные поля None, так как публичные карты их не дают
                                    views_total=None,
                                    actions_total=None
                                )
                                sync_worker._upsert_stats(db_manager, [stat_point])
                                print(f"💾 Сохранена статистика (Рейтинг: {rating_val}, Отзывов: {reviews_count})")

                            # 5. СОХРАНЕНИЕ В НОВЫЕ ТАБЛИЦЫ (business_services, business_reviews, business_news)
                            if parse_status in ['success', 'partial']:
                                oid_value = get_extracted_oid(card_data) or get_expected_oid(queue_dict) or ''
                                
                                # Сохранение услуг в business_services
                                services_list = card_data.get('services', [])
                                if services_list and oid_value:
                                    _save_business_services(db_manager.conn, business_id, oid_value, services_list)
                                
                                # Сохранение отзывов в business_reviews
                                reviews_list_unified = card_data.get('reviews', [])
                                if reviews_list_unified and oid_value:
                                    _save_business_reviews(db_manager.conn, business_id, oid_value, reviews_list_unified)
                                
                                # Сохранение новостей в business_news
                                news_list_unified = card_data.get('news', [])
                                if news_list_unified and oid_value:
                                    _save_business_news(db_manager.conn, business_id, oid_value, news_list_unified)

                            # Commit changes to External Data tables
                            if db_manager and db_manager.conn:
                                db_manager.conn.commit()
                                print("💾 Detailed data committed successfully")

                        finally:
                            if db_manager:
                                db_manager.close()
                                
                    except Exception as det_err:
                        print(f"⚠️ Ошибка сохранения детальных данных (reviews/posts/stats): {det_err}")
                        import traceback
                        traceback.print_exc()

                except Exception as e:
                    print(f"⚠️ Ошибка сохранения в MapParseResults: {e}")
                    import traceback
                    traceback.print_exc()
                    try:
                        from user_api import send_email
                        send_email(
                            "demyanovap@yandex.ru",
                            "Ошибка парсинга карты",
                            f"URL: {queue_dict['url']}\nBusiness ID: {business_id}\nОшибка: {e}"
                        )
                    except:
                        pass
                    raise
            else:
                # Старая логика: сохраняем в Cards
                card_id = str(uuid.uuid4())
                
                rating = card_data.get("rating")
                if rating == "" or rating is None:
                    rating = None
                else:
                    try:
                        rating = float(rating)
                    except (ValueError, TypeError):
                        rating = None
                        
                reviews_count = card_data.get("reviews_count")
                if reviews_count == "" or reviews_count is None:
                    reviews_count = None
                else:
                    try:
                        reviews_count = int(reviews_count)
                    except (ValueError, TypeError):
                        reviews_count = None
                
                cursor.execute("""
                    INSERT INTO cards (
                        id, user_id, url, title, address, phone, site, rating, 
                        reviews_count, categories, overview, products, news, 
                        photos, features_full, competitors, hours, hours_full,
                        created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    card_id,
                    queue_dict["user_id"],
                    queue_dict["url"],
                    card_data.get("title"),
                    card_data.get("address"),
                    card_data.get("phone"),
                    card_data.get("site"),
                    rating,
                    reviews_count,
                    str(card_data.get("categories", [])),
                    str(card_data.get("overview", {})),
                    str(card_data.get("products", [])),
                    str(card_data.get("news", [])),
                    str(card_data.get("photos", [])),
                    str(card_data.get("features_full", {})),
                    str(card_data.get("competitors", [])),
                    card_data.get("hours"),
                    str(card_data.get("hours_full", [])),
                    datetime.now().isoformat()
                ))
                
                # Попытка синхронизации сервисов даже для старой схемы (если есть owner_id)
                # Но у нас нет business_id здесь, поэтому пропускаем
                pass
                
                print(f"Выполняем ИИ-анализ для карточки {card_id}...")
                
                try:
                    analysis_result = analyze_business_data(card_data)
                    
                    cursor.execute("""
                        UPDATE cards SET 
                            ai_analysis = %s, 
                            seo_score = %s, 
                            recommendations = %s
                        WHERE id = %s
                    """, (
                        str(analysis_result.get('analysis', {})),
                        analysis_result.get('score', 50),
                        str(analysis_result.get('recommendations', [])),
                        card_id
                    ))
                    
                    print(f"ИИ-анализ завершён для карточки {card_id}")
                    
                    try:
                        from report import generate_html_report
                        analysis_data = {
                            'score': analysis_result.get('score', 50),
                            'recommendations': analysis_result.get('recommendations', []),
                            'ai_analysis': analysis_result.get('analysis', {})
                        }
                        report_path = generate_html_report(card_data, analysis_data)
                        print(f"HTML отчёт сгенерирован: {report_path}")
                        cursor.execute("UPDATE cards SET report_path = %s WHERE id = %s", (report_path, card_id))
                    except Exception as report_error:
                        print(f"Ошибка при генерации отчёта для карточки {card_id}: {report_error}")
                        
                except Exception as analysis_error:
                    print(f"Ошибка при ИИ-анализе карточки {card_id}: {analysis_error}")
            
            # --- SYNC SERVICES AFTER PARSING (NEW) ---
            if business_id and card_data.get('products'):
                try:
                    # Need owner_id for sync
                    cursor = conn.cursor() # Ensure we have cursor
                    cursor.execute("SELECT owner_id FROM businesses WHERE id=%s", (business_id,))
                    owner_row = cursor.fetchone()
                    if owner_row:
                        owner_id = owner_row[0] if isinstance(owner_row, dict) else owner_row[0]
                        print(f"🔄 Синхронизация услуг для business_id={business_id} (owner_id={owner_id})...")
                        _sync_parsed_services_to_db(business_id, card_data.get('products'), conn, owner_id)
                        print("✅ Услуги успешно синхронизированы.")
                    else:
                        print(f"⚠️ Cannot sync services: owner_id not found for business {business_id}")
                except Exception as sync_error:
                    print(f"⚠️ Ошибка синхронизации услуг: {sync_error}")
                    import traceback
                    traceback.print_exc()
            
            # Обновляем статус на "completed" (чтобы задача осталась в списке)
            warning_msg = None
            if card_data.get('fallback_used'):
                warning_msg = "⚠️ Fast Endpoint Outdated (Used HTML Fallback)"
                
            # Очищаем сессию капчи, если она была
            session_id = queue_dict.get("captcha_session_id")
            if session_id:
                close_session(session_id)
                # Очищаем поля капчи в БД
                cursor.execute("""
                    UPDATE parsequeue 
                    SET captcha_required = FALSE,
                        captcha_url = NULL,
                        captcha_session_id = NULL,
                        captcha_token = NULL,
                        captcha_vnc_path = NULL,
                        captcha_started_at = NULL,
                        captcha_status = NULL,
                        resume_requested = FALSE
                    WHERE id = %s
                """, (queue_dict["id"],))
            
            if warning_msg:
                 cursor.execute("UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", ("completed", warning_msg, queue_dict["id"]))
            else:
                 cursor.execute("UPDATE parsequeue SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", ("completed", queue_dict["id"]))
            
            # cursor.execute("DELETE FROM parsequeue WHERE id = %s", (queue_dict["id"],)) -> Удаление отключено по просьбе пользователя
            conn.commit()
            
            print(f"✅ Заявка {queue_dict['id']} обработана и удалена из очереди.")
            
            # Логирование одной строкой (PART F)
            print(f"📋 TASK={queue_dict['id']} expected_oid={expected_oid} extracted_oid={extracted_oid} status={parse_status} reason={reason} missing={','.join(missing_sections)} parse_time_ms={parse_time_ms}")
            
            signal.alarm(0)  # Отключаем таймаут при успехе
            
        finally:
            try:
                if 'cursor' in locals() and cursor:
                    cursor.close()
            except:
                pass
            try:
                if 'conn' in locals() and conn:
                    conn.close()
            except:
                pass
            
    except Exception as e:
        signal.alarm(0)  # Отключаем таймаут при ошибке
        queue_id = queue_dict.get('id', 'unknown') if queue_dict else 'unknown'
        print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Извлекаем OID для логирования (если card_data доступен)
        expected_oid_log = 'nooid'
        extracted_oid_log = 'nooid'
        parse_time_ms_log = 0
        try:
            if 'card_data' in locals():
                expected_oid_log = get_expected_oid(queue_dict) or 'nooid'
                extracted_oid_log = get_extracted_oid(card_data) or 'nooid'
            if 'parse_time_ms' in locals():
                parse_time_ms_log = parse_time_ms
        except:
            pass
        
        # Обновляем статус ошибки
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", 
                         ("error", str(e), queue_id))
            conn.commit()
            print(f"⚠️ Заявка {queue_id} помечена как ошибка.")
        except Exception as update_error:
            print(f"❌ Не удалось обновить статус заявки {queue_id}: {update_error}")
        finally:
            cursor.close()
            conn.close()
        
        # Логирование одной строкой при исключении
        print(f"📋 TASK={queue_id} expected_oid={expected_oid_log} extracted_oid={extracted_oid_log} status=exception reason={str(e)[:50]} missing=[] parse_time_ms={parse_time_ms_log}")
        
        # Отправляем email (ошибка не критична)
        try:
            from user_api import send_email
            send_email(
                "demyanovap@yandex.ru",
                "Ошибка парсинга карты",
                f"URL: {queue_dict.get('url', 'unknown') if queue_dict else 'unknown'}\nОшибка: {e}"
            )
        except Exception as email_error:
            print(f"⚠️ Не удалось отправить email: {email_error}")

def _sync_parsed_services_to_db(business_id: str, products: list, conn, owner_id: str):
    """
    Синхронизирует распаршенные услуги в таблицу UserServices.
    Добавляет новые, обновляет цены существующих.
    """
    if not products:
        return

    # STRICT CHECK: owner_id required
    if not owner_id:
        print(f"⚠️ Service sync skipped: owner_id is missing for business {business_id}")
        # Raising error to fail fast as per plan, but let's confirm logic
        raise ValueError(f"owner_id (str) is required for service sync for business {business_id}")

    cursor = conn.cursor()
    
    # 1. Проверяем наличие таблицы UserServices и нужных колонок
    # PostgreSQL: проверяем существование таблицы через information_schema
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_name = 'userservices'
        )
    """)
    table_exists = cursor.fetchone()
    table_exists = table_exists[0] if isinstance(table_exists, dict) else table_exists[0] if table_exists else False
    if not table_exists:
        # Если таблицы нет, создаём (должна быть, но на всякий случай)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserServices (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                price INTEGER, -- цена в копейках
                duration INTEGER DEFAULT 60,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
    
    count_new = 0
    count_updated = 0
    
    print(f"👤 Syncing services for owner_id: {owner_id}")
    
    for category_data in products:


        category_name = category_data.get('category', 'Разное')
        items = category_data.get('items', [])
        
        for item in items:
            name = item.get('name')
            if not name:
                continue
                
            raw_price = item.get('price', '')
            description = item.get('description', '')
            
            # Парсинг цены
            price_cents = None
            if raw_price:
                # Удаляем все нецифровые символы кроме разделителей
                try:
                    # Ищем числа в строке
                    import re
                    # "от 1 500 ₽" -> "1500"
                    digits = re.sub(r'[^0-9]', '', str(raw_price))
                    if digits:
                        price_cents = int(digits) * 100 # В копейки
                except:
                    pass
            
            # Ищем существующую услугу по имени и business_id
            cursor.execute("""
                SELECT id FROM userservices 
                WHERE business_id = %s AND name = %s
            """, (business_id, name))
            
            row = cursor.fetchone()
            
            if row is not None:
                # Обновляем существующую
                if hasattr(row, "get"):
                    service_id = row.get("id") or list(row.values())[0]
                elif isinstance(row, dict):
                    service_id = row.get("id") or list(row.values())[0]
                elif isinstance(row, (tuple, list)) and len(row) > 0:
                    service_id = row[0]
                else:
                    service_id = None
                
                if service_id is None:
                    raise ValueError(f"Не удалось извлечь id услуги из результата: {row}")
                cursor.execute("""
                    UPDATE userservices 
                    SET price = %s, description = %s, category = %s, updated_at = CURRENT_TIMESTAMP, is_active = TRUE
                    WHERE id = %s
                """, (price_cents, description, category_name, service_id))
                count_updated += 1
            else:
                # Создаем новую
                service_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO userservices (id, business_id, user_id, name, description, category, price, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (service_id, business_id, owner_id, name, description, category_name, price_cents, True))
                count_new += 1
                
    conn.commit()
    print(f"📊 Синхронизация услуг завершена: {count_new} новых, {count_updated} обновлено.")

def _process_sync_yandex_business_task(queue_dict):
    """Обработка синхронизации Яндекс.Бизнес через кабинет"""
    import signal
    import sys
    
    # Устанавливаем таймаут 10 минут для задачи
    def timeout_handler(signum, frame):
        raise TimeoutError("Задача синхронизации превысила таймаут 10 минут")
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(600)  # 10 минут
    
    try:
        business_id = queue_dict.get("business_id")
        account_id = queue_dict.get("account_id")
        
        if not business_id or not account_id:
            print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'error', 
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, ("Отсутствует business_id или account_id", queue_dict["id"]))
            conn.commit()
            cursor.close()
            conn.close()
            signal.alarm(0)  # Отменяем таймаут
            return
        
        print(f"🔄 Синхронизация Яндекс.Бизнес для бизнеса {business_id}", flush=True)
        
        from yandex_business_parser import YandexBusinessParser
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        from auth_encryption import decrypt_auth_data
        from database_manager import DatabaseManager
        import json
        import traceback
        
        # Получаем auth_data
        db = None  # Initialize to None for safe cleanup
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
        

            cursor.execute("""
                SELECT auth_data, external_id 
                FROM external_business_accounts 
                WHERE id = %s AND business_id = %s
            """, (account_id, business_id))
            account_row = cursor.fetchone()
            
            if not account_row:
                raise Exception("Аккаунт не найден")
            
            if isinstance(account_row, dict):
                auth_data_encrypted = account_row.get('auth_data')
                external_id = account_row.get('external_id')
            else:
                auth_data_encrypted = account_row[0] if len(account_row) > 0 else None
                external_id = account_row[1] if len(account_row) > 1 else None
            
            auth_data_plain = decrypt_auth_data(auth_data_encrypted)
            
            if not auth_data_plain:
                raise Exception("Не удалось расшифровать auth_data")
            
            # Парсим auth_data
            try:
                auth_data_dict = json.loads(auth_data_plain)
            except json.JSONDecodeError:
                auth_data_dict = {"cookies": auth_data_plain}
            
            # Создаем парсер
            parser = YandexBusinessParser(auth_data_dict)
            account_data = {
                "id": account_id,
                "business_id": business_id,
                "external_id": external_id
            }
            
            # Получаем данные из кабинета
            print("📥 Получение отзывов из кабинета...")
            reviews = parser.fetch_reviews(account_data)
            print(f"✅ Получено отзывов: {len(reviews)}")
            
            print("📥 Получение статистики из кабинета...")
            stats = parser.fetch_stats(account_data)
            print(f"✅ Получено точек статистики: {len(stats)}")
            
            print("📥 Получение публикаций из кабинета...")
            posts = parser.fetch_posts(account_data)
            print(f"✅ Получено публикаций: {len(posts)}")
            
            print("📥 Получение информации об организации из кабинета...")
            org_info = parser.fetch_organization_info(account_data)
            
            # Сохраняем отзывы и статистику
            worker = YandexBusinessSyncWorker()
            if reviews:
                worker._upsert_reviews(db, reviews)
                print(f"💾 Сохранено отзывов: {len(reviews)}")
            
            if stats:
                worker._upsert_stats(db, stats)
                print(f"💾 Сохранено точек статистики: {len(stats)}")
            
            if posts:
                worker._upsert_posts(db, posts)
                print(f"💾 Сохранено публикаций: {len(posts)}")
            
            # Получаем существующие данные из MapParseResults (если есть)
            # Проверяем наличие колонки unanswered_reviews_count
            columns = get_table_columns(cursor, 'mapparseresults')
            has_unanswered = 'unanswered_reviews_count' in columns
            
            if has_unanswered:
                cursor.execute("""
                    SELECT rating, reviews_count, unanswered_reviews_count, news_count, photos_count
                    FROM mapparseresults
                    WHERE business_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (business_id,))
            else:
                cursor.execute("""
                    SELECT rating, reviews_count, news_count, photos_count
                    FROM mapparseresults
                    WHERE business_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """, (business_id,))
            existing_data = cursor.fetchone()
            
            # Используем данные из кабинета (приоритет кабинету)
            # Используем данные из кабинета, но с защитой от перезаписи нулями
            # Рейтинг
            rating = org_info.get('rating')
            if not rating and existing_data and existing_data[0]:
                rating = existing_data[0]
            
            # Отзывы
            current_reviews_count = len(reviews) if reviews else 0
            if current_reviews_count == 0 and existing_data:
                # Определяем индекс reviews_count в existing_data
                # Запрос: rating (0), reviews_count (1), ...
                if existing_data[1] and existing_data[1] > 0:
                    reviews_count = existing_data[1]
                else:
                    reviews_count = 0
            else:
                reviews_count = current_reviews_count

            # Неотвеченные
            current_unanswered = sum(1 for r in reviews if not r.response_text) if reviews else 0
            if current_reviews_count == 0 and existing_data and has_unanswered:
                # rating(0), reviews(1), unanswered(2)
                if existing_data[2] is not None:
                     reviews_without_response = existing_data[2]
                else:
                     reviews_without_response = 0
            else:
                reviews_without_response = current_unanswered
                
            # Новости (posts)
            current_news = len(posts) if posts else 0
            if current_news == 0 and existing_data:
                # Индекс зависит от has_unanswered
                idx = 3 if has_unanswered else 2
                if existing_data[idx] and existing_data[idx] > 0:
                    news_count = existing_data[idx]
                else:
                    news_count = 0
            else:
                 news_count = current_news
                 
            # Фото
            current_photos = org_info.get('photos_count', 0) if org_info else 0
            if current_photos == 0 and existing_data:
                idx = 4 if has_unanswered else 3
                if existing_data[idx] and existing_data[idx] > 0:
                     photos_count = existing_data[idx]
                else:
                     photos_count = 0
            else:
                photos_count = current_photos
            
            # Сохраняем в MapParseResults
            parse_id = str(uuid.uuid4())
            url = f"https://yandex.ru/sprav/{external_id or 'unknown'}"
            
            if has_unanswered:
                cursor.execute("""
                    INSERT INTO mapparseresults (
                        id, business_id, url, map_type, rating, reviews_count, 
                        unanswered_reviews_count, news_count, photos_count, 
                        created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    parse_id,
                    business_id,
                    url,
                    'yandex',
                    rating,
                    reviews_count,
                    reviews_without_response,
                    news_count,
                    photos_count,
                ))
            else:
                cursor.execute("""
                    INSERT INTO mapparseresults (
                        id, business_id, url, map_type, rating, reviews_count, 
                        news_count, photos_count, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    parse_id,
                    business_id,
                    url,
                    'yandex',
                    rating,
                    reviews_count,
                    news_count,
                    photos_count,
                ))
            
            # Также сохраняем в историю метрик для графиков
            try:
                metric_history_id = str(uuid.uuid4())
                current_date = datetime.now().strftime('%Y-%m-%d')
                
                # Проверяем, есть ли уже запись за сегодня от парсинга
                cursor.execute("""
                    SELECT id FROM businessmetricshistory 
                    WHERE business_id = %s AND metric_date = %s AND source = 'parsing'
                """, (business_id, current_date))
                
                existing_metric = cursor.fetchone()
                
                if existing_metric:
                    cursor.execute("""
                        UPDATE businessmetricshistory 
                        SET rating = %s, reviews_count = %s, photos_count = %s, news_count = %s
                        WHERE id = %s
                    """, (rating, reviews_count, photos_count, news_count, existing_metric[0]))
                else:
                    cursor.execute("""
                        INSERT INTO businessmetricshistory (
                            id, business_id, metric_date, rating, reviews_count, 
                            photos_count, news_count, source
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, 'parsing')
                    """, (
                        metric_history_id, 
                        business_id, 
                        current_date, 
                        rating, 
                        reviews_count, 
                        photos_count, 
                        news_count
                    ))
            except Exception as e:
                print(f"Error saving metrics history: {e}")
            
            db.conn.commit()
            # Safely close db and connections
            try:
                if 'db' in locals() and db:
                    db.close()
            except Exception:
                pass
            
            # The cursor and conn here refer to the ones created within the try block
            # associated with the DatabaseManager instance.
            # The subsequent conn/cursor are for the ParseQueue update.
            try:
                if 'cursor' in locals() and cursor and not cursor.closed: # Check if cursor is not already closed by db.close()
                    cursor.close()
            except Exception:
                pass
                
            try:
                if 'conn' in locals() and conn and not conn.closed: # Check if conn is not already closed by db.close()
                    conn.close()
            except Exception:
                pass
            
            # Обновляем статус задачи
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'completed', 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (queue_dict["id"],))
            conn.commit()
            try:
                if cursor:
                    cursor.close()
            except Exception:
                pass
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
            
            print(f"✅ Синхронизация завершена для бизнеса {business_id}", flush=True)
            signal.alarm(0)  # Отменяем таймаут при успехе
            
        except TimeoutError as e:
            print(f"⏱️ Таймаут синхронизации: {e}", flush=True)
            signal.alarm(0)
            # Обновляем статус ошибки
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'error', 
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (str(e), queue_dict["id"]))
            conn.commit()
            try:
                if cursor:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass
            
        except Exception as e:
            print(f"❌ Ошибка синхронизации: {e}", flush=True)
            import traceback
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
            signal.alarm(0)  # Отменяем таймаут при ошибке
            
            # Safely close db if it was created
            try:
                if 'db' in locals() and db:
                    db.close()
            except:
                pass
            
            # Обновляем статус ошибки
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'error', 
                    error_message = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (str(e), queue_dict["id"]))
            conn.commit()
            try:
                if cursor:
                    cursor.close()
            except:
                pass
            try:
                if conn:
                    conn.close()
            except:
                pass
            
    except Exception as e:
        print(f"❌ Критическая ошибка синхронизации: {e}")
        import traceback
        traceback.print_exc()
        
        # Обновляем статус ошибки
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parsequeue 
            SET status = 'error', 
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (str(e), queue_dict["id"]))
        conn.commit()
        try:
            if cursor:
                cursor.close()
        except:
            pass
        try:
            if conn:
                conn.close()
        except:
            pass

def _process_cabinet_fallback_task(queue_dict):
    """Обработка fallback парсинга через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    
    if not business_id or not account_id:
        print(f"❌ Отсутствует business_id или account_id для задачи {queue_dict.get('id')}", flush=True)
        _handle_worker_error(queue_dict["id"], "Отсутствует business_id или account_id")
        return
    
    print(f"🔄 Fallback парсинг через кабинет для бизнеса {business_id}", flush=True)
    
    try:
        from yandex_business_sync_worker import YandexBusinessSyncWorker
        
        # Используем sync_account для получения данных из кабинета
        worker = YandexBusinessSyncWorker()
        worker.sync_account(account_id)
        
        # Обновляем статус задачи в ParseQueue
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE parsequeue 
            SET status = 'completed', 
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (queue_dict["id"],))
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Fallback парсинг завершен для бизнеса {business_id}", flush=True)
        
    except Exception as e:
        print(f"❌ Ошибка fallback парсинга: {e}", flush=True)
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        _handle_worker_error(queue_dict["id"], str(e))

def _process_sync_2gis_task(queue_dict):
    """Обработка задачи синхронизации с 2ГИС через API"""
    business_id = queue_dict.get("business_id")
    target_url = queue_dict.get("url")
    user_id = queue_dict.get("user_id")
    
    print(f"🔄 Запуск синхронизации 2ГИС для бизнеса {business_id}...", flush=True)
    
    try:
        from services.two_gis_client import TwoGISClient
        from external_sources import ExternalSource, make_stats_id
        
        # Инициализация клиента
        # TODO: Можно брать ключ из настроек бизнеса, если мы разрешаем клиентам свои ключи
        # Пока берем из ENV
        if not os.getenv("TWOGIS_API_KEY"):
            raise ValueError("TWOGIS_API_KEY не установлен в .env")

        client = TwoGISClient()
        
        org_data = None
        
        # 1. Если есть URL, пробуем извлечь ID или найти по нему
        if target_url:
            # Извлекаем ID из URL вида https://2gis.ru/city/firm/70000001007629561
            import re
            match = re.search(r'/firm/(\d+)', target_url)
            if match:
                org_id = match.group(1)
                print(f"🔍 Найден ID организации в URL: {org_id}")
                org_data = client.search_organization_by_id(org_id)
            else:
                # Если URL сложный, можно попробовать поискать по названию, но это неточно
                pass
        
        # 2. Если по URL не нашли (или его нет), ищем по названию/адресу из БД
        if not org_data:
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT name, address FROM businesses WHERE id = %s", (business_id,))
                row = cursor.fetchone()
                name = None
                address = None
                if row is not None:
                    # RealDictCursor / dict
                    if hasattr(row, "get") or isinstance(row, dict):
                        getter = row.get if hasattr(row, "get") else row.__getitem__
                        try:
                            name = getter("name")
                        except Exception:
                            pass
                        try:
                            address = getter("address")
                        except Exception:
                            pass
                    # tuple/list fallback
                    if (name is None or address is None) and isinstance(row, (tuple, list)) and len(row) >= 2:
                        name, address = row[0], row[1]
                if name and address:
                    query = f"{name} {address}"
                    print(f"🔍 Поиск в 2ГИС по запросу: {query}")
                    items = client.search_organization_by_text(query)
                    if items:
                        # Берем первый результат. В идеале нужно сравнение адресов.
                        org_data = items[0]
                        print(f"✅ Найдена организация: {org_data.get('name')}")
            finally:
                cursor.close()
                conn.close()

        if not org_data:
            raise Exception("Не удалось найти организацию в 2ГИС по ID или названию")

        # 3. Сохраняем данные
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Нормализация данных для MapParseResults
            # В отличие от Yandex Maps Scraper, API 2GIS дает меньше данных в бесплатной версии
            
            # Rating & Reviews
            reviews_data = org_data.get('reviews', {})
            rating = reviews_data.get('general_rating')
            reviews_count = reviews_data.get('general_review_count', 0)
            
            # Details
            name = org_data.get('name')
            address = org_data.get('address_name') or org_data.get('adm_div', [{}])[0].get('name')
            
            # Phone / Website
            contacts = org_data.get('contact_groups', [])
            phone = None
            website = None
            for group in contacts:
                for contact in group.get('contacts', []):
                    if contact.get('type') == 'phone_number':
                        phone = contact.get('value') or contact.get('text')
                    if contact.get('type') == 'website':
                        website = contact.get('value') or contact.get('text')

            # Schedule
            schedule = org_data.get('schedule')
            schedule_json = json.dumps(schedule, ensure_ascii=False) if schedule else None
            
            # Generating ID
            parse_result_id = str(uuid.uuid4())
            
            # Schema-check выполняется один раз при старте через init_schema_checks()
            # Здесь просто используем колонки (они уже должны существовать)

            cursor.execute("""
                INSERT INTO mapparseresults
                (id, business_id, url, map_type, rating, reviews_count, unanswered_reviews_count, 
                 news_count, photos_count, report_path, 
                 is_verified, phone, website, messengers, working_hours, competitors, services_count, profile_completeness,
                 title, address,
                 created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (
                parse_result_id,
                business_id,
                target_url or "",
                "2gis",
                str(rating) if rating else None,
                int(reviews_count or 0),
                0, # API doesn't give unanswered count easily
                0, # No news in API
                0, # Photos might be available but let's skip for MVP
                None, # report path
                0, # verification status unknown
                phone,
                website,
                None, # messengers
                schedule_json,
                None, # competitors
                0, # services count
                0, # completeness
                name,
                address
            ))
            
            # External Stats (Rating History)
            if rating is not None:
                today = datetime.now().strftime('%Y-%m-%d')
                stats_id = make_stats_id(business_id, ExternalSource.TWO_GIS, today)
                
                # Check if exists to update or insert
                cursor.execute("""
                    INSERT INTO ExternalBusinessStats 
                    (id, business_id, source, date, rating, reviews_total, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        rating = EXCLUDED.rating,
                        reviews_total = EXCLUDED.reviews_total,
                        updated_at = CURRENT_TIMESTAMP
                """, (stats_id, business_id, "2gis", today, float(rating), int(reviews_count)))
                print(f"✅ Статистика 2ГИС обновлена: Рейтинг {rating}, Отзывов {reviews_count}")

            # Update Queue Status
            cursor.execute("""
                UPDATE parsequeue 
                SET status = 'completed', 
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (queue_dict["id"],))
            
            conn.commit()
            print(f"✅ Синхронизация с 2ГИС успешно завершена для {business_id}")
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"❌ Ошибка синхронизации 2ГИС: {e}", flush=True)
        # import traceback
        # traceback.print_exc()
        _handle_worker_error(queue_dict["id"], str(e))


def _save_business_services(conn, business_id: str, oid: str, services: list):
    """Сохраняет услуги в таблицу business_services"""
    if not services:
        return
    
    cursor = conn.cursor()
    try:
        saved_count = 0
        for service in services:
            if not isinstance(service, dict):
                continue
            
            category = service.get('category', 'Другое')
            title = service.get('title', '')
            if not title:
                continue
            
            # Используем ON CONFLICT для upsert
            cursor.execute("""
                INSERT INTO business_services 
                (business_id, oid, category, title, description, price, currency, photo, is_top, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (business_id, oid, category, title) 
                DO UPDATE SET
                    description = EXCLUDED.description,
                    price = EXCLUDED.price,
                    currency = EXCLUDED.currency,
                    photo = EXCLUDED.photo,
                    is_top = EXCLUDED.is_top,
                    updated_at = NOW()
            """, (
                business_id,
                oid,
                category,
                title,
                service.get('description', ''),
                service.get('price', ''),
                service.get('currency', '₽'),
                service.get('photo', ''),
                service.get('is_top', False)
            ))
            saved_count += 1
        
        conn.commit()
        print(f"💾 Сохранено {saved_count} услуг в business_services")
    except Exception as e:
        conn.rollback()
        print(f"⚠️ Ошибка сохранения услуг: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()

def _save_business_reviews(conn, business_id: str, oid: str, reviews: list):
    """Сохраняет отзывы в таблицу business_reviews"""
    if not reviews:
        return
    
    cursor = conn.cursor()
    try:
        saved_count = 0
        for review in reviews:
            if not isinstance(review, dict):
                continue
            
            review_id = review.get('reviewId') or review.get('id', '')
            if not review_id:
                continue
            
            author = review.get('author', {})
            if isinstance(author, dict):
                author_name = author.get('name', '')
            else:
                author_name = str(author) if author else ''
            
            # Парсим дату
            updated_time = None
            if review.get('updatedTime'):
                updated_time = _parse_date_string(str(review['updatedTime']))
            
            # Парсим дату ответа
            business_comment_time = None
            if review.get('org_response_date'):
                business_comment_time = _parse_date_string(str(review['org_response_date']))
            
            # Используем ON CONFLICT для upsert
            cursor.execute("""
                INSERT INTO business_reviews 
                (business_id, oid, review_id, author_name, author_public_id, rating, text, 
                 updated_time, likes, dislikes, business_comment_text, business_comment_time, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (review_id) 
                DO UPDATE SET
                    author_name = EXCLUDED.author_name,
                    rating = EXCLUDED.rating,
                    text = EXCLUDED.text,
                    updated_time = EXCLUDED.updated_time,
                    business_comment_text = EXCLUDED.business_comment_text,
                    business_comment_time = EXCLUDED.business_comment_time,
                    updated_at = NOW()
            """, (
                business_id,
                oid,
                review_id,
                author_name,
                review.get('author_public_id', ''),
                review.get('rating', ''),
                review.get('text', ''),
                updated_time,
                review.get('likes', 0),
                review.get('dislikes', 0),
                review.get('org_response', '') or review.get('org_reply', ''),
                business_comment_time
            ))
            saved_count += 1
        
        conn.commit()
        print(f"💾 Сохранено {saved_count} отзывов в business_reviews")
    except Exception as e:
        conn.rollback()
        print(f"⚠️ Ошибка сохранения отзывов: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()

def _save_business_news(conn, business_id: str, oid: str, news: list):
    """Сохраняет новости в таблицу business_news"""
    if not news:
        return
    
    cursor = conn.cursor()
    try:
        saved_count = 0
        for post in news:
            if not isinstance(post, dict):
                continue
            
            post_id = post.get('id') or post.get('post_id', '')
            if not post_id:
                # Генерируем ID из текста
                text = post.get('text', '') or post.get('content', '')
                if not text:
                    continue
                post_id = f"generated_{hash(text[:100])}"
            
            # Парсим дату публикации
            publication_time = None
            if post.get('publicationTime'):
                publication_time = _parse_date_string(str(post['publicationTime']))
            
            # Фото (JSONB)
            photos = post.get('photos', [])
            photos_json = json.dumps(photos, ensure_ascii=False) if photos else None
            
            # Используем ON CONFLICT для upsert
            cursor.execute("""
                INSERT INTO business_news 
                (business_id, oid, post_id, text, content_short, publication_time, photos, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (post_id) 
                DO UPDATE SET
                    text = EXCLUDED.text,
                    content_short = EXCLUDED.content_short,
                    publication_time = EXCLUDED.publication_time,
                    photos = EXCLUDED.photos,
                    updated_at = NOW()
            """, (
                business_id,
                oid,
                post_id,
                post.get('text', '') or post.get('content', ''),
                post.get('content_short', '') or (post.get('text', '')[:200] if post.get('text') else ''),
                publication_time,
                photos_json
            ))
            saved_count += 1
        
        conn.commit()
        print(f"💾 Сохранено {saved_count} новостей в business_news")
    except Exception as e:
        conn.rollback()
        print(f"⚠️ Ошибка сохранения новостей: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cursor.close()


if __name__ == "__main__":
    # Единоразовые проверки схемы (ParseQueue / MapParseResults)
    try:
        init_schema_checks()
    except Exception as e:
        # Не даём worker упасть из‑за проблем со схемой — просто логируем
        print(f"⚠️ init_schema_checks: необработанная ошибка при старте worker: {e}")
    
    # Восстановление потерянных сессий после рестарта
    try:
        _recover_lost_captcha_sessions()
    except Exception as e:
        print(f"⚠️ Ошибка при восстановлении сессий: {e}")

    print("Worker запущен. Проверка очереди каждые 5 минут...")
    while True:
        try:
            process_queue()
        except Exception as e:
            print(f"❌ Критическая ошибка worker loop: {e}", flush=True)
            import traceback
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
        
        try:    
            time.sleep(10)  # 10 секунд
        except Exception as e:
             # Если sleep прерван сигналом или ошибкой, просто логируем и продолжаем
             print(f"⚠️ Sleep interrupted: {e}", flush=True)
