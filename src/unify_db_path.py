#!/usr/bin/env python3
"""
Скрипт для унификации путей к базе данных
Обновляет все модули для использования единого пути через safe_db_utils
"""
import os
import re

# Файлы, которые нужно обновить
FILES_TO_UPDATE = [
    "src/user_api.py",
    "src/worker.py",
    "src/download_server.py",
    "src/download_report.py",
    "src/add_to_queue.py",
    "src/ai_analyzer.py",
    "src/clear_database.py",
    "src/init_database.py",
    "src/migrate_database.py",
    "src/migrate_business_fields.py",
]

def update_file(file_path):
    """Обновить файл для использования safe_db_utils"""
    if not os.path.exists(file_path):
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Паттерны для замены
    patterns = [
        # Паттерн 1: Стандартная функция get_db_connection с "reports.db"
        (r'def get_db_connection\(\):\s*"""Получить соединение с SQLite базой данных"""\s*conn = sqlite3\.connect\("reports\.db"\)\s*conn\.row_factory = sqlite3\.Row\s*return conn',
         'def get_db_connection():\n    """Получить соединение с SQLite базой данных"""\n    from safe_db_utils import get_db_connection as _get_db_connection\n    return _get_db_connection()'),
        
        # Паттерн 2: get_db_connection с "src/reports.db"
        (r'def get_db_connection\(\):\s*"""Получить соединение с SQLite базой данных"""\s*conn = sqlite3\.connect\("src/reports\.db"\)\s*conn\.row_factory = sqlite3\.Row\s*return conn',
         'def get_db_connection():\n    """Получить соединение с SQLite базой данных"""\n    from safe_db_utils import get_db_connection as _get_db_connection\n    return _get_db_connection()'),
        
        # Паттерн 3: Прямое подключение sqlite3.connect("reports.db")
        (r'sqlite3\.connect\("reports\.db"\)',
         'get_db_connection()'),
        
        # Паттерн 4: Прямое подключение sqlite3.connect("src/reports.db")
        (r'sqlite3\.connect\("src/reports\.db"\)',
         'get_db_connection()'),
    ]
    
    # Применяем замены
    for pattern, replacement in patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Если есть изменения, добавляем импорт в начало файла
    if content != original_content:
        # Проверяем, есть ли уже импорт safe_db_utils
        if 'from safe_db_utils import' not in content:
            # Находим место после импортов
            import_match = re.search(r'(^import |^from ).*?$', content, re.MULTILINE)
            if import_match:
                insert_pos = content.rfind('\n', 0, import_match.end()) + 1
                content = content[:insert_pos] + 'from safe_db_utils import get_db_connection\n' + content[insert_pos:]
            else:
                # Если нет импортов, добавляем в начало
                content = 'from safe_db_utils import get_db_connection\n' + content
        
        # Убираем дублирующиеся импорты
        lines = content.split('\n')
        seen_imports = set()
        new_lines = []
        for line in lines:
            if 'from safe_db_utils import' in line:
                if 'safe_db_utils' not in seen_imports:
                    new_lines.append(line)
                    seen_imports.add('safe_db_utils')
            else:
                new_lines.append(line)
        content = '\n'.join(new_lines)
        
        return content, True
    
    return content, False

def main():
    """Обновить все файлы"""
    print("🔄 Унификация путей к базе данных...")
    print("=" * 60)
    
    updated_count = 0
    for file_path in FILES_TO_UPDATE:
        if os.path.exists(file_path):
            print(f"\n📝 Обрабатываю: {file_path}")
            new_content, changed = update_file(file_path)
            
            if changed:
                # Создаем бэкап файла
                backup_path = file_path + '.backup'
                with open(file_path, 'r', encoding='utf-8') as f:
                    with open(backup_path, 'w', encoding='utf-8') as bf:
                        bf.write(f.read())
                
                # Записываем обновленный файл
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"  ✅ Обновлен (бэкап: {backup_path})")
                updated_count += 1
            else:
                print(f"  ⏭️  Без изменений")
        else:
            print(f"\n⚠️  Файл не найден: {file_path}")
    
    print(f"\n{'=' * 60}")
    print(f"✅ Обновлено файлов: {updated_count}/{len(FILES_TO_UPDATE)}")
    print(f"\n📝 Теперь все модули используют safe_db_utils.get_db_connection()")
    print(f"📁 Единая база данных: src/reports.db")

if __name__ == "__main__":
    main()

