#!/usr/bin/env python3
"""
Скрипт для настройки суперадмина
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database_manager import DatabaseManager

def setup_superadmin():
    """Настроить demyanovap@yandex.ru как суперадмина"""
    db = DatabaseManager()
    
    try:
        # Ищем пользователя demyanovap@yandex.ru
        user = db.get_user_by_email("demyanovap@yandex.ru")
        
        if not user:
            print("❌ Пользователь demyanovap@yandex.ru не найден!")
            print("Сначала зарегистрируйтесь в системе")
            return False
        
        # Устанавливаем права суперадмина
        db.set_superadmin(user['id'], True)
        
        print(f"✅ Пользователь {user['email']} ({user['name']}) назначен суперадмином!")
        print(f"ID пользователя: {user['id']}")
        
        # Создаем тестовые бизнесы для демонстрации
        print("\n📊 Создаем тестовые бизнесы...")
        
        # Бизнес 1: Салон красоты
        business1_id = db.create_business(
            name="Салон красоты 'Элегант'",
            description="Премиальный салон красоты в центре города",
            industry="Красота и здоровье",
            owner_id=user['id'],
            business_type="beauty_salon",
            address="Невский проспект, 100, Санкт-Петербург",
            working_hours="09:00-21:00",
            phone="+7 (812) 123-45-67",
            email="elegant@beauty.ru",
            website="https://elegant-beauty.ru"
        )
        print(f"✅ Создан бизнес: Салон красоты 'Элегант' (ID: {business1_id})")
        
        # Бизнес 2: Барбершоп
        business2_id = db.create_business(
            name="Барбершоп 'Мужской стиль'",
            description="Современный барбершоп для мужчин",
            industry="Красота и здоровье",
            owner_id=user['id'],
            business_type="barbershop",
            address="Литейный проспект, 50, Санкт-Петербург",
            working_hours="10:00-22:00",
            phone="+7 (812) 234-56-78",
            email="style@barber.ru",
            website="https://mens-style.ru"
        )
        print(f"✅ Создан бизнес: Барбершоп 'Мужской стиль' (ID: {business2_id})")
        
        # Бизнес 3: Ногтевая студия
        business3_id = db.create_business(
            name="Ногтевая студия 'Маникюр Плюс'",
            description="Студия маникюра и педикюра",
            industry="Красота и здоровье",
            owner_id=user['id'],
            business_type="nail_studio",
            address="Малая Посадская улица, 28/2, Санкт-Петербург",
            working_hours="09:00-20:00",
            phone="+7 (812) 345-67-89",
            email="manicure@plus.ru",
            website="https://manicure-plus.ru"
        )
        print(f"✅ Создан бизнес: Ногтевая студия 'Маникюр Плюс' (ID: {business3_id})")
        
        print(f"\n🎉 Настройка завершена!")
        print(f"Теперь {user['email']} может переключаться между {3} бизнесами")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка настройки: {e}")
        return False
    
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Настройка суперадмина...")
    success = setup_superadmin()
    
    if success:
        print("\n✅ Готово! Перезапустите сервер для применения изменений.")
    else:
        print("\n❌ Настройка не удалась.")
        sys.exit(1)
