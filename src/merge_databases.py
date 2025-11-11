#!/usr/bin/env python3
"""
Скрипт для объединения двух баз данных в одну
Объединяет reports.db (корень) и src/reports.db в src/reports.db
"""
import sqlite3
import os
import shutil
from datetime import datetime
from safe_db_utils import backup_database, get_db_path

def merge_databases():
    """Объединить две базы в одну"""
    print("🔄 Объединение баз данных...")
    print("=" * 60)
    
    # Создаем бэкап обеих баз
    backup_root = backup_database() if os.path.exists("reports.db") else None
    if os.path.exists("src/reports.db"):
        os.makedirs("db_backups", exist_ok=True)
        backup_src = f"db_backups/src_reports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db.backup"
        shutil.copy2("src/reports.db", backup_src)
        print(f"💾 Бэкап src/reports.db: {backup_src}")
    
    # Основная база - src/reports.db (там актуальные данные с услугами)
    main_db = "src/reports.db"
    secondary_db = "reports.db"
    
    if not os.path.exists(secondary_db):
        print("✅ Вторая база не найдена, объединение не требуется")
        return True
    
    print(f"\n📊 Анализ данных...")
    
    # Подключаемся к обеим базам
    main_conn = sqlite3.connect(main_db)
    main_cursor = main_conn.cursor()
    
    secondary_conn = sqlite3.connect(secondary_db)
    secondary_cursor = secondary_conn.cursor()
    
    try:
        # Список бизнесов из основной базы
        main_cursor.execute("SELECT id, name FROM Businesses")
        main_businesses = {row[0]: row[1] for row in main_cursor.fetchall()}
        print(f"📋 В основной базе: {len(main_businesses)} бизнесов")
        
        # Список бизнесов из вторичной базы
        secondary_cursor.execute("SELECT id, name FROM Businesses")
        secondary_businesses = secondary_cursor.fetchall()
        print(f"📋 Во вторичной базе: {len(secondary_businesses)} бизнесов")
        
        # Получаем структуру таблицы Businesses из вторичной базы
        secondary_cursor.execute("PRAGMA table_info(Businesses)")
        secondary_columns = {col[1]: col[0] for col in secondary_cursor.fetchall()}
        
        # Получаем структуру таблицы Businesses из основной базы
        main_cursor.execute("PRAGMA table_info(Businesses)")
        main_columns = {col[1]: col[0] for col in main_cursor.fetchall()}
        
        # Список всех возможных колонок
        all_columns = ['id', 'name', 'description', 'industry', 'business_type', 
                      'address', 'working_hours', 'phone', 'email', 'website', 
                      'owner_id', 'is_active']
        
        # Находим колонки, которые есть в обеих базах
        common_columns = [col for col in all_columns if col in secondary_columns and col in main_columns]
        select_columns = ', '.join(common_columns)
        
        print(f"📋 Общие колонки для объединения: {len(common_columns)}")
        
        # Находим бизнесы, которых нет в основной базе
        new_businesses = []
        for business_id, business_name in secondary_businesses:
            if business_id not in main_businesses:
                # Получаем данные бизнеса только по общим колонкам
                secondary_cursor.execute(f"""
                    SELECT {select_columns}
                    FROM Businesses WHERE id = ?
                """, (business_id,))
                business_data = secondary_cursor.fetchone()
                new_businesses.append((business_id, business_data, common_columns))
                print(f"  ➕ Найден новый бизнес: {business_name}")
        
        # Добавляем новые бизнесы в основную базу
        if new_businesses:
            print(f"\n📝 Добавляю {len(new_businesses)} новых бизнесов в основную базу...")
            for business_id, business_data, columns in new_businesses:
                # Формируем INSERT с учетом всех колонок основной базы
                placeholders = ', '.join(['?' for _ in range(len(all_columns))])
                column_names = ', '.join(all_columns)
                
                # Создаем список значений: заполняем общие колонки из данных, остальные NULL
                values = []
                value_dict = dict(zip(columns, business_data))
                for col in all_columns:
                    if col in value_dict:
                        values.append(value_dict[col])
                    else:
                        values.append(None)
                
                main_cursor.execute(f"""
                    INSERT OR IGNORE INTO Businesses ({column_names})
                    VALUES ({placeholders})
                """, values)
        
        # Проверяем пользователей
        secondary_cursor.execute("SELECT id, email, name, phone, password_hash, is_superadmin FROM Users")
        secondary_users = secondary_cursor.fetchall()
        
        main_cursor.execute("SELECT id FROM Users")
        main_user_ids = {row[0] for row in main_cursor.fetchall()}
        
        new_users = [u for u in secondary_users if u[0] not in main_user_ids]
        if new_users:
            print(f"\n📝 Добавляю {len(new_users)} новых пользователей...")
            for user in new_users:
                main_cursor.execute("""
                    INSERT OR IGNORE INTO Users 
                    (id, email, name, phone, password_hash, is_superadmin)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, user)
        
        # Проверяем Cards (если таблица существует в обеих базах)
        secondary_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Cards'")
        secondary_has_cards = secondary_cursor.fetchone() is not None
        
        main_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Cards'")
        main_has_cards = main_cursor.fetchone() is not None
        
        if secondary_has_cards and main_has_cards:
            # Получаем структуру таблицы Cards из обеих баз
            secondary_cursor.execute("PRAGMA table_info(Cards)")
            secondary_card_columns = {col[1]: col[0] for col in secondary_cursor.fetchall()}
            
            main_cursor.execute("PRAGMA table_info(Cards)")
            main_card_columns = {col[1]: col[0] for col in main_cursor.fetchall()}
            
            # Общие колонки
            common_card_columns = [col for col in secondary_card_columns.keys() if col in main_card_columns]
            
            if common_card_columns and 'id' in common_card_columns:
                secondary_cursor.execute(f"SELECT COUNT(*) FROM Cards")
                secondary_cards_count = secondary_cursor.fetchone()[0]
                
                if secondary_cards_count > 0:
                    select_card_cols = ', '.join(common_card_columns)
                    secondary_cursor.execute(f"SELECT {select_card_cols} FROM Cards")
                    secondary_cards = secondary_cursor.fetchall()
                    
                    main_cursor.execute("SELECT id FROM Cards")
                    main_card_ids = {row[0] for row in main_cursor.fetchall()}
                    
                    # Фильтруем только новые карточки
                    new_cards = []
                    for card in secondary_cards:
                        card_dict = dict(zip(common_card_columns, card))
                        if card_dict.get('id') not in main_card_ids:
                            new_cards.append(card)
                    
                    if new_cards:
                        print(f"\n📝 Добавляю {len(new_cards)} новых карточек...")
                        for card in new_cards:
                            # Формируем INSERT только с общими колонками
                            placeholders = ', '.join(['?' for _ in common_card_columns])
                            column_names = ', '.join(common_card_columns)
                            
                            main_cursor.execute(f"""
                                INSERT OR IGNORE INTO Cards ({column_names})
                                VALUES ({placeholders})
                            """, card)
        
        main_conn.commit()
        
        # Финальная проверка
        main_cursor.execute("SELECT COUNT(*) FROM Businesses")
        final_count = main_cursor.fetchone()[0]
        print(f"\n✅ Объединение завершено!")
        print(f"📊 Итого в основной базе: {final_count} бизнесов")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка объединения: {e}")
        import traceback
        traceback.print_exc()
        main_conn.rollback()
        return False
    finally:
        main_conn.close()
        secondary_conn.close()

if __name__ == "__main__":
    print("🔄 Начинаю объединение баз данных...")
    success = merge_databases()
    
    if success:
        print("\n✅ Объединение успешно!")
        print("💾 Бэкапы созданы в db_backups/")
        print("\n📝 Следующий шаг: обновить все модули для использования src/reports.db")
    else:
        print("\n❌ Объединение не удалось")
        print("💾 Используйте бэкапы для восстановления")

