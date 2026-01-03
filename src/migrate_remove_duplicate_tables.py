#!/usr/bin/env python3
"""
Миграция: Удаление дублирующих таблиц
Этап 2 из плана оптимизации БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_connection

ALLOWED_TABLES = {'ClientInfo', 'GigaChatTokenUsage', 'Cards', 'TokenUsage', 'MapParseResults', 'Businesses'}

def _migrate_table_data(cursor, source_table, target_table, migration_sql, existing_tables):
    """Мигрировать данные из source_table в target_table"""
    if source_table not in ALLOWED_TABLES:
        raise ValueError(f"Неразрешенная таблица: {source_table}")
    if target_table not in ALLOWED_TABLES:
        raise ValueError(f"Неразрешенная таблица: {target_table}")
    
    if source_table not in existing_tables:
        return False
    
    cursor.execute("SELECT COUNT(*) FROM " + source_table)
    count = cursor.fetchone()[0]
    print(f"📊 Записей в {source_table}: {count}")
    
    if count == 0:
        return False
    
    if target_table not in existing_tables:
        print(f"⚠️ Таблица {target_table} не найдена, пропускаю миграцию данных")
        return False
    
    print(f"⚠️ В {source_table} есть данные. Переношу в {target_table}...")
    cursor.execute(migration_sql)
    migrated_count = cursor.rowcount
    print(f"✅ Перенесено записей в {target_table}: {migrated_count}")
    return True

def migrate_remove_duplicate_tables(cursor):
    """Удалить дублирующие таблицы после миграции данных"""
    
    print("🔄 Начинаю удаление дублирующих таблиц...")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    removed_tables = []
    
    # ClientInfo → Businesses (обновление, не миграция)
    if 'ClientInfo' in existing_tables:
        print("📋 Проверяю таблицу ClientInfo...")
        cursor.execute("SELECT COUNT(*) FROM ClientInfo")
        clientinfo_count = cursor.fetchone()[0]
        print(f"📊 Записей в ClientInfo: {clientinfo_count}")
        
        if clientinfo_count > 0:
            print("⚠️ В ClientInfo есть данные. Обновляю Businesses из ClientInfo...")
            cursor.execute("""
                UPDATE Businesses 
                SET 
                    name = COALESCE((SELECT business_name FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id), name),
                    business_type = COALESCE((SELECT business_type FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id), business_type),
                    address = COALESCE((SELECT address FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id), address),
                    working_hours = COALESCE((SELECT working_hours FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id), working_hours),
                    description = COALESCE((SELECT description FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id), description)
                WHERE EXISTS (SELECT 1 FROM ClientInfo WHERE ClientInfo.business_id = Businesses.id)
            """)
            updated_count = cursor.rowcount
            print(f"✅ Обновлено записей в Businesses: {updated_count}")
        
        cursor.execute("DROP TABLE IF EXISTS ClientInfo")
        removed_tables.append("ClientInfo")
        print("✅ Таблица ClientInfo удалена")
    
    # GigaChatTokenUsage → TokenUsage
    if 'GigaChatTokenUsage' in existing_tables:
        print("📋 Проверяю таблицу GigaChatTokenUsage...")
        _migrate_table_data(
            cursor,
            'GigaChatTokenUsage',
            'TokenUsage',
            """
                INSERT INTO TokenUsage (id, business_id, user_id, task_type, model, total_tokens, created_at)
                SELECT 
                    id, business_id, user_id,
                    COALESCE(request_type, 'unknown') as task_type,
                    'GigaChat' as model,
                    tokens_used as total_tokens,
                    created_at
                FROM GigaChatTokenUsage
                WHERE NOT EXISTS (
                    SELECT 1 FROM TokenUsage WHERE TokenUsage.id = GigaChatTokenUsage.id
                )
            """,
            existing_tables
        )
        cursor.execute("DROP TABLE IF EXISTS GigaChatTokenUsage")
        removed_tables.append("GigaChatTokenUsage")
        print("✅ Таблица GigaChatTokenUsage удалена")
    
    # Cards → MapParseResults
    if 'Cards' in existing_tables:
        print("📋 Проверяю таблицу Cards...")
        
        # Проверяем структуру Cards
        cursor.execute("PRAGMA table_info(Cards)")
        cards_columns = {row[1] for row in cursor.fetchall()}
        print(f"📋 Колонки в Cards: {sorted(cards_columns)}")
        
        # Проверяем структуру MapParseResults
        cursor.execute("PRAGMA table_info(MapParseResults)")
        map_columns = {row[1] for row in cursor.fetchall()}
        
        # Если колонки analysis_json нет - добавляем
        if 'analysis_json' not in map_columns:
            print("⚠️ Колонка analysis_json отсутствует в MapParseResults, добавляю...")
            try:
                cursor.execute("ALTER TABLE MapParseResults ADD COLUMN analysis_json TEXT")
                print("✅ Колонка analysis_json добавлена")
            except Exception as e:
                print(f"⚠️ Ошибка при добавлении колонки: {e}")
        
        # Проверяем количество записей
        cursor.execute("SELECT COUNT(*) FROM Cards")
        cards_count = cursor.fetchone()[0]
        print(f"📊 Записей в Cards: {cards_count}")
        
        # Пытаемся мигрировать данные только если есть нужные колонки
        migration_attempted = False
        
        if 'business_id' in cards_columns and cards_count > 0:
            # Есть business_id - используем его
            print("✅ В Cards есть business_id, мигрирую данные...")
            try:
                cursor.execute("""
                    INSERT INTO MapParseResults (id, business_id, url, map_type, rating, reviews_count, report_path, analysis_json, created_at)
                    SELECT 
                        id, business_id, url,
                        'yandex' as map_type,
                        NULL as rating,
                        0 as reviews_count,
                        report_path,
                        json_object('seo_score', seo_score, 'ai_analysis', ai_analysis, 'recommendations', recommendations) as analysis_json,
                        created_at
                    FROM Cards
                    WHERE business_id IS NOT NULL
                    AND NOT EXISTS (
                        SELECT 1 FROM MapParseResults WHERE MapParseResults.id = Cards.id
                    )
                """)
                migrated_count = cursor.rowcount
                print(f"✅ Перенесено записей в MapParseResults: {migrated_count}")
                migration_attempted = True
            except Exception as e:
                print(f"⚠️ Ошибка миграции с business_id: {e}")
        
        if not migration_attempted and 'user_id' in cards_columns and cards_count > 0:
            # Нет business_id, но есть user_id - находим business_id из Businesses
            print("⚠️ В Cards нет business_id, но есть user_id. Ищу business_id из Businesses...")
            try:
                cursor.execute("""
                    INSERT INTO MapParseResults (id, business_id, url, map_type, rating, reviews_count, report_path, analysis_json, created_at)
                    SELECT 
                        Cards.id,
                        (SELECT id FROM Businesses WHERE owner_id = Cards.user_id LIMIT 1) as business_id,
                        Cards.url,
                        'yandex' as map_type,
                        NULL as rating,
                        0 as reviews_count,
                        Cards.report_path,
                        json_object('seo_score', Cards.seo_score, 'ai_analysis', Cards.ai_analysis, 'recommendations', Cards.recommendations) as analysis_json,
                        Cards.created_at
                    FROM Cards
                    WHERE Cards.user_id IS NOT NULL
                    AND EXISTS (SELECT 1 FROM Businesses WHERE owner_id = Cards.user_id)
                    AND NOT EXISTS (
                        SELECT 1 FROM MapParseResults WHERE MapParseResults.id = Cards.id
                    )
                """)
                migrated_count = cursor.rowcount
                print(f"✅ Перенесено записей в MapParseResults: {migrated_count}")
                migration_attempted = True
            except Exception as e:
                print(f"⚠️ Ошибка миграции с user_id: {e}")
        
        if not migration_attempted:
            print("⚠️ Миграция данных не выполнена (нет нужных колонок или ошибка). Удаляю таблицу Cards без миграции.")
        
        # Удаляем таблицу в любом случае
        cursor.execute("DROP TABLE IF EXISTS Cards")
        removed_tables.append("Cards")
        print("✅ Таблица Cards удалена")
        cursor.execute("DROP TABLE IF EXISTS Cards")
        removed_tables.append("Cards")
        print("✅ Таблица Cards удалена")
    
    print(f"📊 Итого удалено таблиц: {len(removed_tables)}")
    if removed_tables:
        print(f"📋 Удаленные таблицы: {', '.join(removed_tables)}")

if __name__ == "__main__":
    print("🔄 Запуск миграции: удаление дублирующих таблиц...")
    
    success = safe_migrate(
        migrate_remove_duplicate_tables,
        "Удаление дублирующих таблиц после миграции данных"
    )
    
    if success:
        print("✅ Миграция выполнена успешно!")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 Всего таблиц: {len(tables)}")
        
        removed = ['ClientInfo', 'GigaChatTokenUsage', 'Cards']
        for table in removed:
            if table in tables:
                print(f"⚠️ Таблица {table} все еще существует!")
            else:
                print(f"✅ Таблица {table} удалена")
        
        conn.close()
        
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибкой")
        sys.exit(1)

