#!/usr/bin/env python3
"""
Миграция: добавление колонки ai_agents_config для поддержки множественных AI агентов
"""
from safe_db_utils import safe_migrate
import json

def migrate_add_ai_agents_config():
    """Добавить колонку ai_agents_config и мигрировать существующие данные"""
    
    def migration_func(cursor):
        print("Добавление колонки ai_agents_config в Businesses...")
        
        # Добавляем новую колонку
        try:
            cursor.execute("""
                ALTER TABLE Businesses 
                ADD COLUMN ai_agents_config TEXT DEFAULT NULL
            """)
            print("✅ Колонка ai_agents_config добавлена")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка ai_agents_config уже существует")
            else:
                raise
        
        # Мигрируем существующие данные из старых полей в новый формат
        print("Миграция существующих настроек агентов...")
        cursor.execute("""
            SELECT id, ai_agent_enabled, ai_agent_type, ai_agent_id, 
                   ai_agent_tone, ai_agent_language, ai_agent_restrictions
            FROM Businesses
            WHERE ai_agent_enabled = 1 OR ai_agent_type IS NOT NULL
        """)
        
        businesses = cursor.fetchall()
        migrated_count = 0
        
        for business in businesses:
            business_id, enabled, agent_type, agent_id, tone, language, restrictions = business
            
            # Создаем новую структуру конфигурации
            agents_config = {}
            
            # Если был активен агент, переносим его настройки
            if enabled and agent_type:
                try:
                    variables = json.loads(restrictions) if restrictions else {}
                except:
                    variables = {}
                
                agents_config[f"{agent_type}_agent"] = {
                    "enabled": True,
                    "agent_id": agent_id or None,
                    "tone": tone or "professional",
                    "language": language or "ru",
                    "variables": variables
                }
            
            # Сохраняем новую конфигурацию
            if agents_config:
                cursor.execute("""
                    UPDATE Businesses 
                    SET ai_agents_config = ?
                    WHERE id = ?
                """, (json.dumps(agents_config), business_id))
                migrated_count += 1
        
        print(f"✅ Мигрировано {migrated_count} бизнесов с настройками агентов")
    
    safe_migrate(migration_func, "Add ai_agents_config column and migrate existing data")

if __name__ == "__main__":
    migrate_add_ai_agents_config()
    print("\n✅ Миграция завершена успешно!")
