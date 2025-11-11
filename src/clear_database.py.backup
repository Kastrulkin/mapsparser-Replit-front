#!/usr/bin/env python3
"""
Скрипт для очистки базы данных
"""
import sqlite3
import os

def clear_database():
    """Очистить все таблицы базы данных"""
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    
    try:
        print("🧹 Очищаем базу данных...")
        
        # Удаляем все данные из таблиц (в правильном порядке из-за внешних ключей)
        tables = [
            "UserSessions",  # Сессии пользователей
            "Cards",         # Готовые отчёты
            "ParseQueue",    # Очередь запросов
            "Invites",       # Приглашения
            "Users"          # Пользователи
        ]
        
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            print(f"  ✅ Очищена таблица {table}")
        
        # Сбрасываем автоинкремент (если есть)
        cursor.execute("DELETE FROM sqlite_sequence")
        
        conn.commit()
        print("✅ База данных очищена успешно!")
        
        # Показываем статистику
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} записей")
            
    except Exception as e:
        print(f"❌ Ошибка при очистке базы данных: {e}")
    finally:
        conn.close()

def remove_report_files():
    """Удалить файлы отчётов"""
    data_dir = "data"
    if os.path.exists(data_dir):
        print(f"🗑️ Удаляем файлы отчётов из {data_dir}/...")
        
        removed_count = 0
        for filename in os.listdir(data_dir):
            if filename.endswith('.html'):
                file_path = os.path.join(data_dir, filename)
                try:
                    os.remove(file_path)
                    print(f"  ✅ Удален: {filename}")
                    removed_count += 1
                except Exception as e:
                    print(f"  ❌ Ошибка при удалении {filename}: {e}")
        
        print(f"✅ Удалено файлов отчётов: {removed_count}")
    else:
        print("📁 Папка data не найдена")

if __name__ == "__main__":
    print("🚀 Начинаем очистку системы...")
    
    # Очищаем базу данных
    clear_database()
    
    # Удаляем файлы отчётов
    remove_report_files()
    
    print("\n✅ Система полностью очищена!")
    print("Теперь вы можете:")
    print("1. Переавторизоваться")
    print("2. Запросить новый отчёт")
    print("3. Система начнёт работу с чистого листа")
