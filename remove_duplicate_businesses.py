#!/usr/bin/env python3
"""
Скрипт для удаления дубликатов бизнесов
Оставляет только один бизнес для каждого названия (самый старый, принадлежащий demyanovap@yandex.ru)
"""
import sqlite3
from datetime import datetime

def remove_duplicates():
    """Удалить дубликаты бизнесов"""
    conn = sqlite3.connect('src/reports.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Получаем ID пользователя demyanovap@yandex.ru
    cursor.execute("SELECT id FROM Users WHERE email = 'demyanovap@yandex.ru'")
    user_row = cursor.fetchone()
    if not user_row:
        print("❌ Пользователь demyanovap@yandex.ru не найден")
        return
    
    main_user_id = user_row['id']
    print(f"✅ Найден пользователь: {main_user_id}")
    print()
    
    # Находим дубликаты
    cursor.execute("""
        SELECT name, COUNT(*) as count
        FROM Businesses
        GROUP BY name
        HAVING count > 1
        ORDER BY count DESC
    """)
    duplicates = cursor.fetchall()
    
    if not duplicates:
        print("✅ Дубликатов не найдено")
        return
    
    print(f"Найдено {len(duplicates)} групп с дубликатами:")
    for dup in duplicates:
        print(f"  - {dup['name']}: {dup['count']} записей")
    print()
    
    # Для каждой группы дубликатов
    businesses_to_delete = []
    
    for dup in duplicates:
        name = dup['name']
        
        # Получаем все бизнесы с этим названием
        cursor.execute("""
            SELECT id, owner_id, created_at
            FROM Businesses
            WHERE name = ?
            ORDER BY created_at
        """, (name,))
        businesses = cursor.fetchall()
        
        # Оставляем самый старый бизнес, принадлежащий main_user_id
        keep_business = None
        for business in businesses:
            if business['owner_id'] == main_user_id:
                keep_business = business
                break
        
        # Если не нашли бизнес main_user_id, оставляем самый старый
        if not keep_business:
            keep_business = businesses[0]
        
        print(f"📋 {name}:")
        print(f"   Оставляем: {keep_business['id']} (владелец: {keep_business['owner_id']}, создан: {keep_business['created_at']})")
        
        # Помечаем остальные для удаления
        for business in businesses:
            if business['id'] != keep_business['id']:
                businesses_to_delete.append(business['id'])
                print(f"   Удаляем: {business['id']} (владелец: {business['owner_id']}, создан: {business['created_at']})")
        print()
    
    if not businesses_to_delete:
        print("✅ Нет бизнесов для удаления")
        return
    
    print(f"⚠️  Будет удалено {len(businesses_to_delete)} бизнесов:")
    for bid in businesses_to_delete:
        cursor.execute("SELECT name FROM Businesses WHERE id = ?", (bid,))
        name_row = cursor.fetchone()
        name = name_row['name'] if name_row else 'Неизвестно'
        print(f"   - {bid} ({name})")
    print()
    
    # Проверяем связанные данные
    print("Проверка связанных данных...")
    for bid in businesses_to_delete:
        cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id = ?", (bid,))
        services_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM FinancialTransactions WHERE business_id = ?", (bid,))
        transactions_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM Cards WHERE business_id = ?", (bid,))
        cards_count = cursor.fetchone()[0]
        
        if services_count > 0 or transactions_count > 0 or cards_count > 0:
            print(f"   ⚠️  Бизнес {bid} имеет связанные данные:")
            print(f"      - Услуг: {services_count}")
            print(f"      - Транзакций: {transactions_count}")
            print(f"      - Карточек: {cards_count}")
    
    print()
    response = input("Продолжить удаление? (yes/no): ")
    
    if response.lower() != 'yes':
        print("❌ Удаление отменено")
        conn.close()
        return
    
    # Удаляем дубликаты
    deleted_count = 0
    for bid in businesses_to_delete:
        try:
            # Удаляем связанные данные
            cursor.execute("DELETE FROM UserServices WHERE business_id = ?", (bid,))
            cursor.execute("DELETE FROM FinancialTransactions WHERE business_id = ?", (bid,))
            cursor.execute("DELETE FROM Cards WHERE business_id = ?", (bid,))
            cursor.execute("DELETE FROM BusinessOptimizationWizard WHERE business_id = ?", (bid,))
            
            # Удаляем бизнес
            cursor.execute("DELETE FROM Businesses WHERE id = ?", (bid,))
            deleted_count += 1
        except Exception as e:
            print(f"❌ Ошибка при удалении {bid}: {e}")
            conn.rollback()
            conn.close()
            return
    
    conn.commit()
    conn.close()
    
    print(f"✅ Успешно удалено {deleted_count} дубликатов")

if __name__ == "__main__":
    remove_duplicates()

