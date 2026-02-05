#!/usr/bin/env python3
"""Применение миграции add_parser_tables.sql"""
import sys
import os
sys.path.append('src')

from database_manager import DatabaseManager

def apply_migration():
    """Применяет миграцию add_parser_tables.sql"""
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        # Читаем SQL файл
        migration_file = os.path.join('src', 'migrations', 'add_parser_tables.sql')
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Выполняем команды по одной, разделяя по ;
        # Но группируем CREATE TABLE и CREATE INDEX вместе
        import re
        
        # Разделяем на отдельные команды
        commands = []
        current_command = ""
        for line in sql.split('\n'):
            line = line.strip()
            # Пропускаем комментарии и пустые строки
            if not line or line.startswith('--'):
                continue
            current_command += line + " "
            if line.endswith(';'):
                commands.append(current_command.strip())
                current_command = ""
        
        # Выполняем команды
        for cmd in commands:
            if not cmd:
                continue
            try:
                cursor.execute(cmd)
                # Определяем тип команды для логирования
                if 'CREATE TABLE' in cmd.upper():
                    table_name = re.search(r'CREATE TABLE.*?(\w+)', cmd, re.IGNORECASE)
                    if table_name:
                        print(f"✅ Создана таблица: {table_name.group(1)}")
                elif 'CREATE INDEX' in cmd.upper():
                    index_name = re.search(r'CREATE INDEX.*?(\w+)', cmd, re.IGNORECASE)
                    if index_name:
                        print(f"✅ Создан индекс: {index_name.group(1)}")
                elif 'ALTER TABLE' in cmd.upper():
                    table_name = re.search(r'ALTER TABLE.*?(\w+)', cmd, re.IGNORECASE)
                    if table_name:
                        print(f"✅ Обновлена таблица: {table_name.group(1)}")
            except Exception as e:
                error_str = str(e).lower()
                # Игнорируем ошибки "уже существует"
                if 'already exists' in error_str or 'duplicate' in error_str:
                    print(f"⚠️ Пропущено (уже существует): {cmd[:60]}...")
                elif 'current transaction is aborted' in error_str:
                    # Откатываем транзакцию и продолжаем
                    db.conn.rollback()
                    print(f"⚠️ Транзакция откачена, продолжаем...")
                else:
                    print(f"❌ Ошибка: {e}")
                    print(f"   SQL: {cmd[:100]}...")
                    # Откатываем и продолжаем
                    db.conn.rollback()
        
        db.conn.commit()
        print("\n✅ Миграция применена успешно")
        
    except Exception as e:
        db.conn.rollback()
        print(f"\n❌ Ошибка применения миграции: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cursor.close()
        db.close()
    
    return True

if __name__ == "__main__":
    success = apply_migration()
    sys.exit(0 if success else 1)
