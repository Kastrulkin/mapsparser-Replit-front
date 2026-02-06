#!/usr/bin/env python3
"""
Миграция: Добавление FOREIGN KEY на user_id в UserServices
Критично для Step 2 (USE_SERVICE_REPOSITORY=true)
"""
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from safe_db_utils import safe_migrate

def migrate():
    """Добавить FOREIGN KEY на user_id"""
    
    def apply_migration(cursor):
        # Проверяем, существуют ли уже оба FK
        cursor.execute("PRAGMA foreign_key_list(UserServices)")
        existing_fks = cursor.fetchall()
        
        has_user_id_fk = False
        has_business_id_fk = False
        
        for fk in existing_fks:
            # fk[3] - это имя колонки (from), fk[2] - таблица (table)
            if len(fk) >= 4:
                col_name = fk[3]
                ref_table = fk[2]
                
                if col_name == 'user_id' and ref_table == 'Users':
                    has_user_id_fk = True
                elif col_name == 'business_id' and ref_table == 'Businesses':
                    has_business_id_fk = True
        
        if has_user_id_fk and has_business_id_fk:
            print("✅ Оба FOREIGN KEY уже существуют")
            return
        
        if not has_business_id_fk:
            print("⚠️ FOREIGN KEY на business_id отсутствует, будет добавлен")
        
        if not has_user_id_fk:
            print("⚠️ FOREIGN KEY на user_id отсутствует, будет добавлен")
        
        # Проверяем наличие orphaned records перед добавлением FK
        cursor.execute("""
            SELECT COUNT(*) FROM UserServices 
            WHERE user_id IS NOT NULL 
            AND user_id NOT IN (SELECT id FROM Users)
        """)
        orphaned_count = cursor.fetchone()[0]
        
        if orphaned_count > 0:
            print(f"⚠️ Найдено {orphaned_count} orphaned записей (user_id не существует)")
            print("   Удаляем orphaned записи...")
            
            cursor.execute("""
                DELETE FROM UserServices 
                WHERE user_id IS NOT NULL 
                AND user_id NOT IN (SELECT id FROM Users)
            """)
            print(f"✅ Удалено {orphaned_count} orphaned записей")
        
        # В SQLite нельзя добавить FK через ALTER TABLE напрямую
        # Нужно пересоздать таблицу
        print("🔄 Пересоздание таблицы UserServices с FOREIGN KEY на user_id...")
        
        # Удаляем временную таблицу, если она существует (от предыдущей неудачной попытки)
        cursor.execute("DROP TABLE IF EXISTS UserServices_new")
        
        # Получаем текущую структуру таблицы
        cursor.execute("PRAGMA table_info(UserServices)")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        print(f"   Найдено колонок: {len(column_names)}")
        print(f"   Колонки: {', '.join(column_names)}")
        
        # 1. Создаем временную таблицу с новой структурой
        # Используем все существующие колонки + добавляем FK
        columns_def = []
        for col in columns_info:
            col_name = col[1]
            col_type = col[2]
            not_null = "NOT NULL" if col[3] else ""
            default = f"DEFAULT {col[4]}" if col[4] else ""
            primary_key = "PRIMARY KEY" if col[5] else ""
            
            col_def = f"{col_name} {col_type}"
            if primary_key:
                col_def += f" {primary_key}"
            elif not_null:
                col_def += f" {not_null}"
            if default:
                col_def += f" {default}"
            
            columns_def.append(col_def)
        
        # Добавляем FK constraints (отдельно, не в определении колонок)
        fk_constraints = []
        
        # Всегда добавляем FK на business_id (должен быть всегда)
        fk_constraints.append("FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE")
        
        # Всегда добавляем FK на user_id (это цель миграции)
        fk_constraints.append("FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT")
        
        # Собираем CREATE TABLE
        create_parts = columns_def.copy()
        if fk_constraints:
            create_parts.extend(fk_constraints)
        
        create_sql = f"""
            CREATE TABLE UserServices_new (
                {', '.join(create_parts)}
            )
        """
        
        cursor.execute(create_sql)
        
        # 2. Копируем данные (явно указываем все колонки)
        columns_str = ', '.join(column_names)
        cursor.execute(f"""
            INSERT INTO UserServices_new ({columns_str})
            SELECT {columns_str} FROM UserServices
            WHERE user_id IS NOT NULL 
            AND user_id IN (SELECT id FROM Users)
        """)
        
        # 3. Удаляем старую таблицу
        cursor.execute("DROP TABLE UserServices")
        
        # 4. Переименовываем новую таблицу
        cursor.execute("ALTER TABLE UserServices_new RENAME TO UserServices")
        
        # 5. Восстанавливаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_services_business_id ON UserServices(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_services_user_id ON UserServices(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_services_category ON UserServices(category)")
        
        print("✅ Таблица пересоздана с FOREIGN KEY на user_id")
        print("✅ Индексы восстановлены")
    
    safe_migrate(apply_migration, "add_fk_user_services_user_id")

if __name__ == "__main__":
    migrate()
