#!/usr/bin/env python3
"""
Скрипт для проверки готовности Phase 3.5 к production rollout
Проверяет:
1. Constraints в БД (UNIQUE, FOREIGN KEY)
2. Orphaned records
3. Соответствие схеме
"""
import sqlite3
import sys
import os

# Добавляем путь к src для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'src', 'reports.db')

def check_constraints():
    """Проверка constraints в БД"""
    print("=" * 60)
    print("1. ПРОВЕРКА CONSTRAINTS")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    issues = []
    
    # Проверка UNIQUE constraint для ExternalBusinessReviews
    print("\n📋 Проверка UNIQUE constraint для ExternalBusinessReviews...")
    # В SQLite UNIQUE constraint может быть реализован через уникальный индекс
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name='idx_ext_reviews_unique'
    """)
    unique_index = cursor.fetchone()
    
    if unique_index:
        print("   ✅ Уникальный индекс найден (работает как UNIQUE constraint)")
    else:
        # Проверяем, есть ли UNIQUE в определении таблицы
        cursor.execute("""
            SELECT sql FROM sqlite_master 
            WHERE type='table' AND name='ExternalBusinessReviews'
        """)
        table_sql = cursor.fetchone()
        
        if table_sql and table_sql[0]:
            sql_text = table_sql[0]
            if 'UNIQUE' in sql_text.upper() and ('business_id' in sql_text and 'source' in sql_text and 'external_review_id' in sql_text):
                print("   ✅ UNIQUE constraint найден в определении таблицы")
            else:
                print("   ❌ UNIQUE constraint НЕ найден")
                issues.append("ExternalBusinessReviews: отсутствует UNIQUE(business_id, source, external_review_id)")
        else:
            print("   ⚠️ Таблица ExternalBusinessReviews не найдена")
            issues.append("ExternalBusinessReviews: таблица не существует")
    
    # Проверка FOREIGN KEY для UserServices
    print("\n📋 Проверка FOREIGN KEY для UserServices...")
    
    # Проверяем через PRAGMA foreign_key_list (более надежно)
    cursor.execute("PRAGMA foreign_key_list(UserServices)")
    fk_list = cursor.fetchall()
    
    has_business_id_fk = False
    has_user_id_fk = False
    
    # Структура результата PRAGMA foreign_key_list:
    # [0] id, [1] seq, [2] table (ссылается на), [3] from (колонка), [4] to (колонка в ссылаемой таблице)
    for fk in fk_list:
        if len(fk) >= 4:
            col_name = fk[3]  # from - имя колонки в UserServices
            ref_table = fk[2]  # table - таблица, на которую ссылается
            
            if col_name == 'business_id' and ref_table == 'Businesses':
                has_business_id_fk = True
            elif col_name == 'user_id' and ref_table == 'Users':
                has_user_id_fk = True
    
    if has_business_id_fk:
        print("   ✅ FOREIGN KEY на business_id найден")
    else:
        # Проверяем через определение таблицы (fallback)
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='UserServices'")
        table_sql = cursor.fetchone()
        if table_sql and table_sql[0] and 'FOREIGN KEY' in table_sql[0].upper() and 'business_id' in table_sql[0] and 'Businesses' in table_sql[0]:
            print("   ✅ FOREIGN KEY на business_id найден (в определении таблицы)")
            has_business_id_fk = True
        else:
            print("   ❌ FOREIGN KEY на business_id НЕ найден")
            issues.append("UserServices: отсутствует FOREIGN KEY (business_id) REFERENCES Businesses(id)")
    
    # КРИТИЧНО для Step 2 (USE_SERVICE_REPOSITORY)
    if has_user_id_fk:
        print("   ✅ FOREIGN KEY на user_id найден (КРИТИЧНО для Step 2)")
    else:
        print("   ❌ FOREIGN KEY на user_id НЕ найден (КРИТИЧНО для Step 2!)")
        issues.append("UserServices: отсутствует FOREIGN KEY (user_id) REFERENCES Users(id) - КРИТИЧНО для USE_SERVICE_REPOSITORY")
    
    conn.close()
    
    return issues

def check_orphaned_records():
    """Проверка orphaned records"""
    print("\n" + "=" * 60)
    print("2. ПРОВЕРКА ORPHANED RECORDS")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    issues = []
    
    # Проверка UserServices
    print("\n📋 Проверка UserServices...")
    cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        print(f"   ❌ Найдено {null_count} записей с business_id = NULL")
        issues.append(f"UserServices: {null_count} записей с business_id = NULL")
    else:
        print("   ✅ Нет записей с business_id = NULL")
    
    cursor.execute("""
        SELECT COUNT(*) FROM UserServices 
        WHERE business_id NOT IN (SELECT id FROM Businesses)
    """)
    orphaned_count = cursor.fetchone()[0]
    if orphaned_count > 0:
        print(f"   ❌ Найдено {orphaned_count} orphaned записей (business_id не существует)")
        issues.append(f"UserServices: {orphaned_count} orphaned записей")
    else:
        print("   ✅ Нет orphaned записей")
    
    # Проверка ExternalBusinessReviews
    print("\n📋 Проверка ExternalBusinessReviews...")
    cursor.execute("SELECT COUNT(*) FROM ExternalBusinessReviews WHERE business_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        print(f"   ❌ Найдено {null_count} записей с business_id = NULL")
        issues.append(f"ExternalBusinessReviews: {null_count} записей с business_id = NULL")
    else:
        print("   ✅ Нет записей с business_id = NULL")
    
    cursor.execute("""
        SELECT COUNT(*) FROM ExternalBusinessReviews 
        WHERE business_id NOT IN (SELECT id FROM Businesses)
    """)
    orphaned_count = cursor.fetchone()[0]
    if orphaned_count > 0:
        print(f"   ❌ Найдено {orphaned_count} orphaned записей (business_id не существует)")
        issues.append(f"ExternalBusinessReviews: {orphaned_count} orphaned записей")
    else:
        print("   ✅ Нет orphaned записей")
    
    conn.close()
    
    return issues

def main():
    """Главная функция"""
    print("\n" + "=" * 60)
    print("PHASE 3.5 PRODUCTION READINESS CHECK")
    print("=" * 60)
    
    if not os.path.exists(DB_PATH):
        print(f"\n❌ База данных не найдена: {DB_PATH}")
        sys.exit(1)
    
    all_issues = []
    
    # Проверка constraints
    constraint_issues = check_constraints()
    all_issues.extend(constraint_issues)
    
    # Проверка orphaned records
    orphaned_issues = check_orphaned_records()
    all_issues.extend(orphaned_issues)
    
    # Итоговый отчет
    print("\n" + "=" * 60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)
    
    # Разделяем проблемы по критичности для разных этапов
    step1_issues = [i for i in all_issues if 'USE_SERVICE_REPOSITORY' not in i and 'USE_BUSINESS_REPOSITORY' not in i]
    step2_issues = [i for i in all_issues if 'USE_SERVICE_REPOSITORY' in i or 'user_id' in i]
    step3_issues = [i for i in all_issues if 'USE_BUSINESS_REPOSITORY' in i]
    
    if all_issues:
        print(f"\n❌ Найдено {len(all_issues)} проблем:")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i}. {issue}")
        
        # Оценка готовности по этапам
        print("\n" + "=" * 60)
        print("ОЦЕНКА ГОТОВНОСТИ ПО ЭТАПАМ")
        print("=" * 60)
        
        if not step1_issues:
            print("\n✅ Step 1 (USE_REVIEW_REPOSITORY): ГОТОВО")
            print("   Можно включить: USE_REVIEW_REPOSITORY=true")
        else:
            print("\n❌ Step 1 (USE_REVIEW_REPOSITORY): НЕ ГОТОВО")
            print(f"   Проблемы: {len(step1_issues)}")
        
        if not step2_issues:
            print("\n✅ Step 2 (USE_SERVICE_REPOSITORY): ГОТОВО")
            print("   Можно включить после Step 1 (через 24 часа)")
        else:
            print("\n❌ Step 2 (USE_SERVICE_REPOSITORY): НЕ ГОТОВО")
            print(f"   Критичные проблемы: {len(step2_issues)}")
            print("   ⚠️ ВАЖНО: Без FK на user_id нельзя включать USE_SERVICE_REPOSITORY!")
            print("   Выполните: python3 src/migrations/add_fk_user_services_user_id.py")
        
        if not step3_issues:
            print("\n✅ Step 3 (USE_BUSINESS_REPOSITORY): ГОТОВО")
            print("   Можно включить после Step 2 (через неделю)")
        else:
            print("\n❌ Step 3 (USE_BUSINESS_REPOSITORY): НЕ ГОТОВО")
            print(f"   Проблемы: {len(step3_issues)}")
        
        print("\nРекомендации:")
        print("1. Применить миграции для добавления constraints")
        print("2. Очистить orphaned records")
        print("3. Повторить проверку")
        
        # Если Step 1 готов, все равно можно начинать
        if not step1_issues:
            print("\n⚠️ Можно начать с Step 1, но Step 2 требует исправлений!")
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        print("\n✅ Все проверки пройдены!")
        print("✅ Готово к staged rollout (все этапы)")
        print("\nСледующие шаги:")
        print("1. Включить флаги поэтапно:")
        print("   - Этап 1: USE_REVIEW_REPOSITORY=true (только чтение) ✅")
        print("   - Этап 2: USE_SERVICE_REPOSITORY=true (после 24 часов) ✅")
        print("   - Этап 3: USE_BUSINESS_REPOSITORY=true (после недели) ✅")
        print("\n2. Мониторить логи первые 30 минут:")
        print("   tail -f /tmp/seo_main.out | grep -i 'integrity\\|violat\\|error'")
        print("\n3. При проблемах - быстро отключить флаги в .env")
        sys.exit(0)

if __name__ == "__main__":
    main()
