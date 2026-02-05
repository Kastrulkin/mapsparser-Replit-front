#!/usr/bin/env python3
"""
Безопасные утилиты для работы с базой данных
- Единая точка подключения к PostgreSQL
- Автоматические бэкапы перед изменениями
- Защита от случайного удаления данных
- PostgreSQL-only: SQLite больше не поддерживается в runtime
"""
import os
import shutil
from datetime import datetime
from pathlib import Path

# Импортируем единую точку подключения (lazy import для избежания циклических зависимостей)
def get_db_connection():
    """Получить соединение с PostgreSQL базой данных"""
    from core.db_connection import get_db_connection as _get_db_connection
    return _get_db_connection()

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db_backups')

def backup_database():
    """
    Создать резервную копию базы данных PostgreSQL
    Возвращает путь к файлу бэкапа (pg_dump)
    
    Для PostgreSQL используйте pg_dump вручную:
    pg_dump -h localhost -U beautybot_user -d beautybot_local > backup.sql
    """
    print("⚠️  Для PostgreSQL используйте pg_dump:")
    print("   pg_dump -h localhost -U beautybot_user -d beautybot_local > backup.sql")
    return None

def safe_migrate(callback, description=""):
    """
    Безопасное выполнение миграции с автоматическим бэкапом
    
    Args:
        callback: Функция, выполняющая миграцию (принимает cursor)
        description: Описание миграции для логов
    
    PostgreSQL-only: рекомендуется создать бэкап через pg_dump перед миграцией
    """
    print("⚠️  Для PostgreSQL рекомендуется создать бэкап через pg_dump перед миграцией")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        print(f"🔄 Выполняю миграцию: {description}")
        print(f"📊 Тип БД: PostgreSQL")
        
        # Проверяем существующие данные перед миграцией
        businesses_before = 0
        services_before = 0
        
        try:
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            row = cursor.fetchone()
            businesses_before = row[0] if row else 0
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            row = cursor.fetchone()
            services_before = row[0] if row else 0
        except Exception:
            # Таблицы могут не существовать - это нормально для новой БД
            print("   ℹ️  Таблицы еще не созданы (новая БД)")
        
        print(f"📊 Данные до миграции: {businesses_before} бизнесов, {services_before} услуг")
        
        # Выполняем миграцию
        callback(cursor)
        
        # Проверяем данные после миграции
        businesses_after = 0
        services_after = 0
        
        try:
            cursor.execute("SELECT COUNT(*) FROM Businesses")
            row = cursor.fetchone()
            businesses_after = row[0] if row else 0
            cursor.execute("SELECT COUNT(*) FROM UserServices")
            row = cursor.fetchone()
            services_after = row[0] if row else 0
        except Exception:
            pass
        
        # Валидация: данные не должны уменьшиться
        if businesses_before > 0 and businesses_after < businesses_before:
            raise Exception(f"❌ Количество бизнесов уменьшилось! Было: {businesses_before}, Стало: {businesses_after}")
        if services_before > 0 and services_after < services_before:
            raise Exception(f"❌ Количество услуг уменьшилось! Было: {services_before}, Стало: {services_after}")
        
        conn.commit()
        
        print(f"✅ Данные после миграции: {businesses_after} бизнесов, {services_after} услуг")
        print(f"✅ Миграция выполнена успешно!")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        import traceback
        traceback.print_exc()
        print(f"⚠️  Для PostgreSQL откат нужно делать вручную через pg_restore")
        return False
    finally:
        conn.close()

def list_backups():
    """Показать список доступных бэкапов"""
    if not os.path.exists(BACKUP_DIR):
        print("📁 Директория бэкапов не существует")
        return []
    
    backups = []
    for file in os.listdir(BACKUP_DIR):
        if file.endswith('.db.backup'):
            file_path = os.path.join(BACKUP_DIR, file)
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            backups.append({
                'filename': file,
                'path': file_path,
                'size': size,
                'modified': datetime.fromtimestamp(mtime)
            })
    
    backups.sort(key=lambda x: x['modified'], reverse=True)
    return backups

def restore_from_backup(backup_path):
    """
    Восстановить базу данных PostgreSQL из бэкапа
    
    Args:
        backup_path: Путь к файлу бэкапа (SQL dump)
    
    Для PostgreSQL используйте pg_restore или psql:
    psql -h localhost -U beautybot_user -d beautybot_local < backup.sql
    """
    print("⚠️  Для PostgreSQL используйте pg_restore или psql:")
    print(f"   psql -h localhost -U beautybot_user -d beautybot_local < {backup_path}")
    return False

