#!/usr/bin/env python3
"""
Создание тестовых услуг для каждого бизнеса
"""
import sqlite3
import uuid

def create_test_services():
    """Создаем тестовые услуги для каждого бизнеса"""
    conn = sqlite3.connect("src/reports.db")
    cursor = conn.cursor()
    
    try:
        print("🛠️ Создаем тестовые услуги для каждого бизнеса...")
        
        # Получаем все бизнесы
        cursor.execute("SELECT id, name, business_type FROM Businesses")
        businesses = cursor.fetchall()
        
        for business_id, business_name, business_type in businesses:
            print(f"\n📋 Создаем услуги для: {business_name} ({business_type})")
            
            # Определяем услуги в зависимости от типа бизнеса
            if business_type == 'beauty_salon':
                services = [
                    ("Женская стрижка", "Стрижка волос любой длины с укладкой", "haircut", "стрижка, волосы, укладка", "2500"),
                    ("Окрашивание", "Окрашивание волос в любой цвет", "coloring", "окрашивание, цвет, волосы", "3500"),
                    ("Маникюр", "Классический и аппаратный маникюр", "manicure", "маникюр, ногти, покрытие", "1500"),
                    ("Педикюр", "Классический педикюр", "pedicure", "педикюр, ноги, ногти", "2000"),
                    ("Брови", "Коррекция и окрашивание бровей", "eyebrows", "брови, коррекция, окрашивание", "800")
                ]
            elif business_type == 'barbershop':
                services = [
                    ("Мужская стрижка", "Классическая мужская стрижка", "haircut", "стрижка, мужская, классика", "1200"),
                    ("Бритье", "Бритье опасной бритвой", "shaving", "бритье, опасная бритва", "800"),
                    ("Укладка", "Укладка волос с укладкой", "styling", "укладка, волосы, стиль", "600"),
                    ("Стрижка + Бритье", "Комплексная услуга", "combo", "стрижка, бритье, комплекс", "1800"),
                    ("Усы и борода", "Стрижка усов и бороды", "beard", "усы, борода, стрижка", "1000")
                ]
            elif business_type == 'nail_studio':
                services = [
                    ("Маникюр", "Классический маникюр", "manicure", "маникюр, ногти", "1000"),
                    ("Педикюр", "Классический педикюр", "pedicure", "педикюр, ноги, ногти", "1500"),
                    ("Покрытие гель-лак", "Покрытие гель-лаком", "gel_polish", "гель-лак, покрытие, ногти", "800"),
                    ("Наращивание ногтей", "Наращивание гелем", "extension", "наращивание, гель, ногти", "3000"),
                    ("Дизайн ногтей", "Художественный дизайн", "design", "дизайн, художественный, ногти", "1200")
                ]
            else:
                services = [
                    ("Услуга 1", "Описание услуги 1", "general", "услуга, описание", "1000"),
                    ("Услуга 2", "Описание услуги 2", "general", "услуга, описание", "1500"),
                    ("Услуга 3", "Описание услуги 3", "general", "услуга, описание", "2000")
                ]
            
            # Создаем услуги
            for name, description, category, keywords, price in services:
                service_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT OR IGNORE INTO Services 
                    (id, business_id, name, description, category, keywords, price)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (service_id, business_id, name, description, category, keywords, price))
            
            print(f"✅ Создано {len(services)} услуг")
        
        conn.commit()
        print("\n🎉 Все тестовые услуги созданы!")
        
        # Показываем статистику
        cursor.execute("SELECT COUNT(*) FROM Services")
        total_services = cursor.fetchone()[0]
        print(f"📊 Всего услуг в системе: {total_services}")
        
        # Показываем услуги по бизнесам
        cursor.execute("""
            SELECT b.name, COUNT(s.id) as service_count
            FROM Businesses b
            LEFT JOIN Services s ON b.id = s.business_id
            GROUP BY b.id, b.name
        """)
        
        print("\n📋 Услуги по бизнесам:")
        for business_name, service_count in cursor.fetchall():
            print(f"  {business_name}: {service_count} услуг")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка создания услуг: {e}")
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_services()
