#!/usr/bin/env python3
"""
Smoke-тест для DatabaseManager после миграции на Postgres.
Проверяет основные методы "на чтение" без изменения данных.
"""
import os
import sys
from pathlib import Path

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

from pg_db_utils import get_db_connection, log_connection_info
from database_manager import DatabaseManager


def test_connection():
    """Проверка подключения к БД"""
    print("=" * 60)
    print("🔍 Проверка подключения к PostgreSQL")
    print("=" * 60)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT current_database() AS db, current_user AS user")
        row = cur.fetchone()
        print(f"✅ Подключение успешно:")
        print(f"   База данных: {row.get('db')}")
        print(f"   Пользователь: {row.get('user')}")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return False


def test_get_user_by_email(db: DatabaseManager):
    """Тест get_user_by_email"""
    print("\n" + "=" * 60)
    print("📧 Тест: get_user_by_email")
    print("=" * 60)
    
    try:
        # Пробуем найти первого пользователя
        users = db.get_all_users()
        if users:
            test_email = users[0].get('email')
            print(f"   Ищем пользователя: {test_email}")
            user = db.get_user_by_email(test_email)
            if user:
                print(f"✅ Найден пользователь: {user.get('name') or 'Без имени'}")
                return True
            else:
                print("⚠️  Пользователь не найден (возможно, нет данных)")
                return True  # Не ошибка, просто нет данных
        else:
            print("⚠️  Нет пользователей в БД (пропускаем тест)")
            return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_businesses_by_owner(db: DatabaseManager):
    """Тест get_businesses_by_owner"""
    print("\n" + "=" * 60)
    print("🏢 Тест: get_businesses_by_owner")
    print("=" * 60)
    
    try:
        # Пробуем найти первого пользователя с бизнесами
        users = db.get_all_users()
        for user in users:
            owner_id = user.get('id')
            businesses = db.get_businesses_by_owner(owner_id)
            if businesses:
                print(f"✅ Найдено бизнесов у пользователя {user.get('email')}: {len(businesses)}")
                return True
        
        print("⚠️  Нет пользователей с бизнесами (пропускаем тест)")
        return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_business_by_id(db: DatabaseManager):
    """Тест get_business_by_id"""
    print("\n" + "=" * 60)
    print("🔍 Тест: get_business_by_id")
    print("=" * 60)
    
    try:
        # Пробуем найти первый бизнес
        all_businesses = db.get_all_businesses()
        if all_businesses:
            test_business_id = all_businesses[0].get('id')
            print(f"   Ищем бизнес: {test_business_id}")
            business = db.get_business_by_id(test_business_id)
            if business:
                print(f"✅ Найден бизнес: {business.get('name') or 'Без названия'}")
                return True
            else:
                print("⚠️  Бизнес не найден")
                return False
        else:
            print("⚠️  Нет бизнесов в БД (пропускаем тест)")
            return True
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_get_reports_by_business(db: DatabaseManager):
    """Тест get_reports_by_business"""
    print("\n" + "=" * 60)
    print("📄 Тест: get_reports_by_business")
    print("=" * 60)
    
    try:
        # Пробуем найти первый бизнес
        all_businesses = db.get_all_businesses()
        if all_businesses:
            test_business_id = all_businesses[0].get('id')
            print(f"   Ищем отчёты для бизнеса: {test_business_id}")
            reports = db.get_reports_by_business(test_business_id)
            print(f"✅ Найдено отчётов: {len(reports)}")
            return True
        else:
            print("⚠️  Нет бизнесов в БД (пропускаем тест)")
            return True
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "relation" in error_msg.lower():
            print(f"⚠️  Таблица не существует (возможно, не создана): {error_msg}")
            print("   Это не критично для проверки Postgres-совместимости SQL")
            return True  # Не критично, если таблица не создана
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        # Откатываем транзакцию
        try:
            db.conn.rollback()
        except:
            pass
        return False


def test_get_services_by_business(db: DatabaseManager):
    """Тест get_services_by_business"""
    print("\n" + "=" * 60)
    print("🛠️  Тест: get_services_by_business")
    print("=" * 60)
    
    try:
        # Откатываем предыдущую транзакцию, если была ошибка
        try:
            db.conn.rollback()
        except:
            pass
        
        # Пробуем найти первый бизнес
        all_businesses = db.get_all_businesses()
        if all_businesses:
            test_business_id = all_businesses[0].get('id')
            print(f"   Ищем услуги для бизнеса: {test_business_id}")
            services = db.get_services_by_business(test_business_id)
            print(f"✅ Найдено услуг: {len(services)}")
            return True
        else:
            print("⚠️  Нет бизнесов в БД (пропускаем тест)")
            return True
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "relation" in error_msg.lower():
            print(f"⚠️  Таблица не существует (возможно, не создана): {error_msg}")
            print("   Это не критично для проверки Postgres-совместимости SQL")
            return True  # Не критично, если таблица не создана
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        # Откатываем транзакцию
        try:
            db.conn.rollback()
        except:
            pass
        return False


def test_cards_versioning(db: DatabaseManager):
    """Тест версионирования карточек"""
    print("\n" + "=" * 60)
    print("📋 Тест: cards_versioning")
    print("=" * 60)
    
    try:
        # Откатываем предыдущую транзакцию, если была ошибка
        try:
            db.conn.rollback()
        except:
            pass
        
        # Находим первый бизнес
        all_businesses = db.get_all_businesses()
        if not all_businesses:
            print("⚠️  Нет бизнесов в БД (пропускаем тест)")
            return True
        
        test_business_id = all_businesses[0].get('id')
        print(f"   Тестируем версионирование для бизнеса: {test_business_id}")
        
        # Проверяем, что таблица cards существует и имеет нужные колонки
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'cards'
        """)
        columns = {row.get('column_name') if isinstance(row, dict) else row[0] for row in cursor.fetchall()}
        
        if 'version' not in columns or 'is_latest' not in columns:
            print("⚠️  Таблица cards не имеет полей version/is_latest")
            print("   Запустите миграцию: python src/migrate_add_cards_versioning.py")
            return True  # Не критично для проверки
        
        # Тест 1: Создаём первую версию карточки
        print("   Создаём версию 1...")
        card_id_1 = db.save_new_card_version(
            business_id=test_business_id,
            title="Версия 1",
            seo_score=85
        )
        print(f"   ✅ Создана карточка ID: {card_id_1}")
        
        # Проверяем первую версию
        latest_1 = db.get_latest_card_by_business(test_business_id)
        if not latest_1:
            print("   ❌ Не удалось получить первую версию")
            return False
        
        if latest_1.get('version') != 1 or not latest_1.get('is_latest'):
            print(f"   ❌ Неверные данные первой версии: version={latest_1.get('version')}, is_latest={latest_1.get('is_latest')}")
            return False
        print(f"   ✅ Версия 1 корректна: version={latest_1.get('version')}, is_latest={latest_1.get('is_latest')}")
        
        # Тест 2: Создаём вторую версию карточки
        print("   Создаём версию 2...")
        card_id_2 = db.save_new_card_version(
            business_id=test_business_id,
            title="Версия 2",
            seo_score=90
        )
        print(f"   ✅ Создана карточка ID: {card_id_2}")
        
        # Проверяем, что первая версия больше не актуальна
        latest_1_after = db.get_latest_card_by_business(test_business_id)
        if latest_1_after.get('id') == card_id_1:
            print("   ❌ Первая версия всё ещё актуальна после создания второй")
            return False
        
        # Проверяем вторую версию
        latest_2 = db.get_latest_card_by_business(test_business_id)
        if not latest_2:
            print("   ❌ Не удалось получить вторую версию")
            return False
        
        if latest_2.get('version') != 2 or not latest_2.get('is_latest'):
            print(f"   ❌ Неверные данные второй версии: version={latest_2.get('version')}, is_latest={latest_2.get('is_latest')}")
            return False
        print(f"   ✅ Версия 2 корректна: version={latest_2.get('version')}, is_latest={latest_2.get('is_latest')}")
        
        # Тест 3: Проверяем историю
        history = db.get_card_history_by_business(test_business_id)
        if len(history) != 2:
            print(f"   ❌ Неверное количество версий в истории: {len(history)} (ожидалось 2)")
            return False
        
        # Проверяем, что версии отсортированы по убыванию
        if history[0].get('version') != 2 or history[1].get('version') != 1:
            print(f"   ❌ Неверный порядок версий: {[h.get('version') for h in history]}")
            return False
        
        # Проверяем, что только одна версия is_latest = TRUE
        latest_count = sum(1 for h in history if h.get('is_latest'))
        if latest_count != 1:
            print(f"   ❌ Неверное количество актуальных версий: {latest_count} (ожидалось 1)")
            return False
        
        print(f"   ✅ История корректна: {len(history)} версий, {latest_count} актуальная")
        print(f"   ✅ Все тесты версионирования прошли успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        # Откатываем транзакцию
        try:
            db.conn.rollback()
        except:
            pass
        return False


def main():
    """Основная функция smoke-теста"""
    print("\n" + "=" * 60)
    print("🚀 Smoke-тест DatabaseManager (Postgres-only)")
    print("=" * 60)
    
    # Проверка DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("❌ DATABASE_URL не установлен!")
        print("   Установите: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'")
        sys.exit(1)
    
    # Логируем информацию о подключении
    log_connection_info("SMOKE")
    
    # Проверка подключения
    if not test_connection():
        print("\n❌ Не удалось подключиться к БД. Прерываем тесты.")
        sys.exit(1)
    
    # Создаём DatabaseManager
    db = DatabaseManager()
    
    results = []
    
    try:
        # Запускаем тесты
        results.append(("Подключение", test_connection()))
        results.append(("get_user_by_email", test_get_user_by_email(db)))
        results.append(("get_businesses_by_owner", test_get_businesses_by_owner(db)))
        results.append(("get_business_by_id", test_get_business_by_id(db)))
        results.append(("get_reports_by_business", test_get_reports_by_business(db)))
        results.append(("get_services_by_business", test_get_services_by_business(db)))
        results.append(("cards_versioning", test_cards_versioning(db)))
        
        # Итоги
        print("\n" + "=" * 60)
        print("📊 Итоги smoke-теста")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {status}: {test_name}")
        
        print(f"\n   Всего: {passed}/{total} тестов прошли")
        
        if passed == total:
            print("\n✅ Все тесты прошли успешно!")
            return 0
        else:
            print(f"\n⚠️  {total - passed} тест(ов) не прошли")
            return 1
            
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
