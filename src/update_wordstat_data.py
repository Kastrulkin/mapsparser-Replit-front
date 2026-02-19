#!/usr/bin/env python3
"""
Скрипт для автоматического обновления данных Яндекс.Вордстат
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

from wordstat_client import WordstatClient, WordstatDataProcessor
from wordstat_config import config

STOP_TOKENS = {
    "и", "в", "на", "с", "по", "для", "или", "от", "до", "под", "при", "за", "к", "из", "о",
    "the", "and", "for", "with", "from", "to", "of", "a", "an",
}

BEAUTY_ROOTS = (
    "стриж", "волос", "окраш", "мелир", "бров", "ресниц", "маник", "педик",
    "ногт", "космет", "пилинг", "лифт", "ботокс", "массаж", "спа", "эпиля",
    "омолож", "уход", "парикмах", "салон",
)

def _extract_tokens(text: str):
    raw = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9-]+", (text or "").lower())
    out = []
    for t in raw:
        if len(t) < 3 or t in STOP_TOKENS:
            continue
        out.append(t)
    return out

def _build_relevance_terms(beauty_keywords, cursor):
    terms = set()
    for phrase in beauty_keywords:
        terms.update(_extract_tokens(phrase))

    # Добавляем токены из услуг, чтобы фильтр подхватывал фактический профиль бизнеса.
    try:
        cursor.execute(
            """
            SELECT name, description
            FROM userservices
            WHERE (is_active IS TRUE OR is_active IS NULL)
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 5000
            """
        )
        for row in cursor.fetchall() or []:
            if hasattr(row, "keys"):
                name = row.get("name") or ""
                desc = row.get("description") or ""
            else:
                name = row[0] if len(row) > 0 else ""
                desc = row[1] if len(row) > 1 else ""
            terms.update(_extract_tokens(name))
            terms.update(_extract_tokens(desc))
    except Exception:
        pass

    return terms

def _load_city_terms(cursor):
    cities = set()
    try:
        cursor.execute(
            """
            SELECT DISTINCT city
            FROM businesses
            WHERE city IS NOT NULL AND btrim(city) <> ''
            LIMIT 500
            """
        )
        for row in cursor.fetchall() or []:
            city = (row[0] if not hasattr(row, "keys") else row.get("city") or "").strip().lower()
            if len(city) >= 3:
                cities.add(city)
    except Exception:
        pass
    return cities

def _is_noise_keyword(keyword: str) -> bool:
    q = (keyword or "").strip().lower()
    if len(q) < 3:
        return True
    # Шум типа "a an", "c a", "x y z"
    if re.fullmatch(r"[a-z]{1,2}(?:\s+[a-z]{1,2}){0,4}", q):
        return True
    tokens = _extract_tokens(q)
    if not tokens:
        return True
    # Не пропускаем строки, где нет кириллицы и нет профильных корней.
    has_cyr = bool(re.search(r"[а-яё]", q))
    if not has_cyr and not any(root in q for root in BEAUTY_ROOTS):
        return True
    return False

def _is_relevant_keyword(keyword: str, relevance_terms, city_terms) -> bool:
    q = (keyword or "").strip().lower()
    if _is_noise_keyword(q):
        return False
    if any(term in q for term in relevance_terms):
        return True
    # Допускаем запросы с городом только если есть бьюти-корень.
    if any(city in q for city in city_terms) and any(root in q for root in BEAUTY_ROOTS):
        return True
    return any(root in q for root in BEAUTY_ROOTS)

def _extract_queries(api_payload):
    """
    Нормализует ответы Wordstat topRequests в список {key, clicks}.
    Поддерживает ответ-объект и массив по нескольким фразам.
    """
    if not api_payload:
        return []

    blocks = api_payload if isinstance(api_payload, list) else [api_payload]
    rows = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        for section in ("topRequests", "top_requests", "associations", "alsoSearch"):
            items = block.get(section) or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                text = (
                    item.get("text")
                    or item.get("phrase")
                    or item.get("query")
                    or item.get("key")
                    or ""
                ).strip()
                if not text:
                    continue
                count = (
                    item.get("count")
                    or item.get("shows")
                    or item.get("clicks")
                    or 0
                )
                try:
                    count = int(count)
                except (TypeError, ValueError):
                    count = 0
                rows.append({"key": text, "clicks": count})

    # дедуп: оставляем максимум по показам
    by_key = {}
    for r in rows:
        key = r["key"].lower().strip()
        prev = by_key.get(key)
        if not prev or r["clicks"] > prev["clicks"]:
            by_key[key] = r
    return list(by_key.values())

def main():
    """Основная функция обновления данных"""
    
    print("🔄 Запуск обновления данных Яндекс.Вордстат...")
    
    # Проверяем конфигурацию
    if not config.is_configured():
        print("❌ API Яндекс.Вордстат не настроен")
        print(f"🔗 Получите OAuth токен по ссылке: {config.get_auth_url()}")
        print("📝 Установите токен в переменную окружения YANDEX_WORDSTAT_OAUTH_TOKEN")
        return False
    
    # Инициализируем клиент
    client = WordstatClient(config.client_id, config.client_secret)
    client.set_access_token(config.oauth_token)
    
    # Ключевые слова для анализа бьюти-индустрии (расширены, включая косметологию)
    beauty_keywords = [
        # Волосы/стрижки/окрашивание
        "стрижка женская", "стрижка мужская", "укладка волос",
        "окрашивание волос", "мелирование", "блондирование",
        "парикмахерская", "салон красоты", "барбершоп",
        # Ногти
        "маникюр", "педикюр", "гель-лак", "наращивание ногтей",
        # SPA/массаж
        "массаж", "спа процедуры", "обертывание",
        # Брови/ресницы
        "брови", "ресницы", "ламинирование бровей", "ламинирование ресниц",
        # Косметология — добавлено
        "косметология", "косметолог", "чистка лица", "пилинг лица",
        "ботокс", "диспорт", "контурная пластика", "филлеры",
        "гиалуроновая кислота", "биоревитализация", "мезотерапия",
        "плазмолифтинг", "RF-лифтинг", "SMAS-лифтинг", "ультразвуковой SMAS",
        "лазерная эпиляция", "фотоэпиляция", "лазерное омоложение",
        "лазерная шлифовка", "нитевой лифтинг", "липолитики",
        "микротоки", "аппаратная косметология", "дермапен", "микронидлинг",
        "антивозрастные процедуры", "лечение акне", "постакне", "купить купероз",
        "уход за кожей", "омоложение лица", "маска для лица"
    ]
    
    print(f"🔍 Анализируем {len(beauty_keywords)} ключевых слов...")
    
    try:
        # Получаем популярные запросы
        print("📊 Получение популярных запросов...")
        popular_data = client.get_popular_queries(beauty_keywords, config.default_region)
        
        if not popular_data:
            print("❌ Не удалось получить данные от API")
            return False

        all_queries = _extract_queries(popular_data)
        if not all_queries:
            print("❌ В ответе API нет topRequests/associations")
            return False
        
        # Обрабатываем и сохраняем данные в БД
        from database_manager import DatabaseManager
        from service_categorizer import categorizer
        import uuid
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS wordstatkeywords (
                id TEXT PRIMARY KEY,
                keyword TEXT UNIQUE NOT NULL,
                views INTEGER DEFAULT 0,
                category TEXT DEFAULT 'other',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_views ON wordstatkeywords(views DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wordstat_category ON wordstatkeywords(category)")
        db.conn.commit()
        
        print("💾 Сохранение данных в таблицу WordstatKeywords...")
        relevance_terms = _build_relevance_terms(beauty_keywords, cursor)
        city_terms = _load_city_terms(cursor)
        
        saved_count = 0
        updated_count = 0
        skipped_noise_count = 0
        
        try:
            for item in all_queries:
                keyword = item.get('key', '').strip()
                if not keyword:
                    continue
                if not _is_relevant_keyword(keyword, relevance_terms, city_terms):
                    skipped_noise_count += 1
                    continue
                    
                views = int(item.get('clicks', 0))
                
                # Категоризация
                # Используем categorizer.categorize_service, чтобы определить наиболее подходящую категорию
                # Он возвращает (category_key, confidence, matched_keywords)
                category, confidence, _ = categorizer.categorize_service(keyword)
                
                if confidence < 0.3:
                    category = 'other'

                # Проверяем существование
                cursor.execute("SELECT id FROM wordstatkeywords WHERE keyword = %s", (keyword,))
                existing = cursor.fetchone()
                
                if existing:
                    existing_id = existing[0] if not hasattr(existing, "keys") else existing.get("id")
                    cursor.execute("""
                        UPDATE wordstatkeywords 
                        SET views = %s, category = %s, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = %s
                    """, (views, category, existing_id))
                    updated_count += 1
                else:
                    new_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO wordstatkeywords (id, keyword, views, category, updated_at) 
                        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (new_id, keyword, views, category))
                    saved_count += 1
            
            db.conn.commit()
            print(f"✅ Данные успешно сохранены в БД")
            print(f"   ➕ Новых: {saved_count}")
            print(f"   🔄 Обновлено: {updated_count}")
            print(f"   🧹 Отфильтровано шумных: {skipped_noise_count}")
            
        except Exception as db_err:
            print(f"❌ Ошибка записи в БД: {db_err}")
            db.conn.rollback()
            return False
            
        finally:
            db.close()
        
        # Сохраняем метаданные обновления (все еще полезно)
        metadata = {
            'last_update': datetime.now().isoformat(),
            'queries_count': saved_count + updated_count,
            'region': config.default_region,
            'region_name': config.get_region_name(config.default_region)
        }
        
        prompts_dir = Path(__file__).parent.parent / "prompts"
        if not prompts_dir.exists():
            prompts_dir.mkdir(parents=True, exist_ok=True)
            
        metadata_path = prompts_dir / "wordstat_metadata.json"
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        print(f"📋 Метаданные сохранены в {metadata_path}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при обновлении данных: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_update_needed() -> bool:
    """Проверка, нужно ли обновление данных"""
    metadata_path = Path(__file__).parent.parent / "prompts" / "wordstat_metadata.json"
    
    if not metadata_path.exists():
        return True
    
    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        last_update = datetime.fromisoformat(metadata['last_update'])
        update_interval = timedelta(seconds=config.update_interval)
        
        return datetime.now() - last_update > update_interval
        
    except Exception:
        return True

if __name__ == "__main__":
    if check_update_needed():
        success = main()
        if success:
            print("🎉 Обновление завершено успешно!")
        else:
            print("💥 Обновление завершилось с ошибками")
            sys.exit(1)
    else:
        print("⏰ Обновление не требуется (данные актуальны)")
