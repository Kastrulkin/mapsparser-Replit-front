#!/usr/bin/env python3
"""
Скрипт для автоматического обновления данных Яндекс.Вордстат
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__))))

from wordstat_client import WordstatClient
from wordstat_config import config

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
        
        # Получаем похожие запросы для каждого ключевого слова
        print("🔗 Получение похожих запросов...")
        similar_queries = []
        
        for keyword in beauty_keywords[:5]:  # Ограничиваем для экономии квоты
            similar_data = client.get_similar_queries(keyword, config.default_region)
            if similar_data and 'data' in similar_data:
                similar_queries.extend(similar_data['data'])
        
        # Объединяем данные
        all_queries = []
        if popular_data and 'data' in popular_data:
            all_queries.extend(popular_data['data'])
        all_queries.extend(similar_queries)
        
        # Обрабатываем и сохраняем данные в БД
        from database_manager import DatabaseManager
        from service_categorizer import categorizer
        import uuid
        
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        print("💾 Сохранение данных в таблицу WordstatKeywords...")
        
        saved_count = 0
        updated_count = 0
        
        try:
            for item in all_queries:
                keyword = item.get('key', '').strip()
                if not keyword:
                    continue
                    
                views = int(item.get('clicks', 0))
                
                # Категоризация
                # Используем categorizer.categorize_service, чтобы определить наиболее подходящую категорию
                # Он возвращает (category_key, confidence, matched_keywords)
                category, confidence, _ = categorizer.categorize_service(keyword)
                
                if confidence < 0.3:
                    category = 'other'

                # Проверяем существование
                cursor.execute("SELECT id FROM WordstatKeywords WHERE keyword = ?", (keyword,))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("""
                        UPDATE WordstatKeywords 
                        SET views = ?, category = ?, updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (views, category, existing[0]))
                    updated_count += 1
                else:
                    new_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO WordstatKeywords (id, keyword, views, category, updated_at) 
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (new_id, keyword, views, category))
                    saved_count += 1
            
            db.conn.commit()
            print("✅ Данные успешно сохранены в БД")
            print(f"   ➕ Новых: {saved_count}")
            print(f"   🔄 Обновлено: {updated_count}")
            
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
