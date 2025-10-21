#!/usr/bin/env python3
"""
Скрипт для автоматической синхронизации базы данных
"""
import sqlite3
import os
import shutil
from datetime import datetime

def sync_database():
    """Синхронизировать базу данных с локальной версией"""
    
    # Путь к локальной базе данных
    local_db_path = "reports.db"
    
    # Путь к серверной базе данных
    server_db_path = "reports.db"
    
    print("🔄 Синхронизация базы данных...")
    
    # Если локальная база существует, копируем её
    if os.path.exists(local_db_path):
        print(f"✅ Найдена локальная база: {local_db_path")
        
        # Создаем резервную копию серверной базы
        if os.path.exists(server_db_path):
            backup_path = f"reports_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy2(server_db_path, backup_path)
            print(f"📦 Создана резервная копия: {backup_path}")
        
        # Копируем локальную базу на сервер
        shutil.copy2(local_db_path, server_db_path)
        print(f"✅ База данных синхронизирована: {server_db_path}")
        
        # Проверяем, что таблицы существуют
        conn = sqlite3.connect(server_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"📊 Таблиц в базе: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        conn.close()
        
        return True
    else:
        print("❌ Локальная база данных не найдена")
        return False

if __name__ == "__main__":
    sync_database()
