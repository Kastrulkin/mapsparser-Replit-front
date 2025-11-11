#!/usr/bin/env python3
"""
Безопасные утилиты для работы с базой данных
- Единая точка подключения
- Автоматические бэкапы перед изменениями
- Защита от случайного удаления данных
"""
import sqlite3
import os
import shutil
from datetime import datetime
from pathlib import Path

# Единый путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports.db')
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'db_backups')

def get_db_path():
    """
    Получить путь к основной базе данных
    Проверяет оба возможных местоположения
    """
    # Приоритет 1: src/reports.db (как в auth_system)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports.db')
    if os.path.exists(db_path):
        return db_path
    
    # Приоритет 2: reports.db в корне
    root_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports.db')
    if os.path.exists(root_db):
        return root_db
    
    # Если не найдена, создаем в src/
    return db_path

def get_db_connection():
    """Получить соединение с SQLite базой данных (безопасно)"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backup_database():
    """
    Создать резервную копию базы данных
    Возвращает путь к файлу бэкапа
    """
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"⚠️  База данных не найдена: {db_path}")
        return None
    
    # Создаем директорию для бэкапов
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Имя файла бэкапа с timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"reports_{timestamp}.db.backup"
    backup_path = os.path.join(BACKUP_DIR, backup_filename)
    
    # Копируем файл
    shutil.copy2(db_path, backup_path)
    
    print(f"💾 Создан бэкап: {backup_path}")
    return backup_path

def safe_migrate(callback, description=""):
    """
    Безопасное выполнение миграции с автоматическим бэкапом
    
    Args:
        callback: Функция, выполняющая миграцию (принимает cursor)
        description: Описание миграции для логов
    """
    # Создаем бэкап перед миграцией
    backup_path = backup_database()
    
    if not backup_path:
        print("❌ Не удалось создать бэкап! Миграция отменена.")
        return False
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print(f"🔄 Выполняю миграцию: {description}")
        
        # Проверяем существующие данные перед миграцией
        cursor.execute("SELECT COUNT(*) FROM Businesses")
        businesses_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM UserServices")
        services_before = cursor.fetchone()[0]
        
        print(f"📊 Данные до миграции: {businesses_before} бизнесов, {services_before} услуг")
        
        # Выполняем миграцию
        callback(cursor)
        
        # Проверяем данные после миграции
        cursor.execute("SELECT COUNT(*) FROM Businesses")
        businesses_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM UserServices")
        services_after = cursor.fetchone()[0]
        
        # Валидация: данные не должны уменьшиться
        if businesses_after < businesses_before:
            raise Exception(f"❌ Количество бизнесов уменьшилось! Было: {businesses_before}, Стало: {businesses_after}")
        if services_after < services_before:
            raise Exception(f"❌ Количество услуг уменьшилось! Было: {services_before}, Стало: {services_after}")
        
        conn.commit()
        
        print(f"✅ Данные после миграции: {businesses_after} бизнесов, {services_after} услуг")
        print(f"✅ Миграция выполнена успешно! Бэкап: {backup_path}")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        print(f"💾 Откат к бэкапу: {backup_path}")
        
        # Восстанавливаем из бэкапа
        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, db_path)
            print(f"✅ База данных восстановлена из бэкапа")
        
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
    Восстановить базу данных из бэкапа
    
    Args:
        backup_path: Путь к файлу бэкапа
    """
    if not os.path.exists(backup_path):
        print(f"❌ Файл бэкапа не найден: {backup_path}")
        return False
    
    db_path = get_db_path()
    
    # Создаем бэкап текущей базы перед восстановлением
    current_backup = backup_database()
    
    try:
        shutil.copy2(backup_path, db_path)
        print(f"✅ База данных восстановлена из: {backup_path}")
        print(f"💾 Старая версия сохранена в: {current_backup}")
        return True
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        return False

