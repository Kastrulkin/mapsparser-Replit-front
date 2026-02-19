import sqlite3
import os
import re

DB_PATH = 'src/reports.db'

def fill_ids():
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Находим сеть "Мастер Кебаб"
        cursor.execute("SELECT id FROM Networks WHERE name = 'Мастер Кебаб'")
        network = cursor.fetchone()
        
        if not network:
            print("❌ Сеть 'Мастер Кебаб' не найдена!")
            # Пробуем без сети (просто по имени)
            businesses_to_check = []
        else:
            network_id = network[0]
            print(f"✅ Сеть ID: {network_id}")
            # Находим все бизнесы сети + Мастер Кебаб сам по себе
            cursor.execute("""
                SELECT id, name FROM Businesses 
                WHERE network_id = %s 
                OR name = 'Мастер Кебаб'
            """, (network_id,))
            businesses_to_check = cursor.fetchall()

        if not businesses_to_check:
             # Фоллбэк: ищем по имени
             cursor.execute("SELECT id, name FROM Businesses WHERE name LIKE '%Кебаб%'")
             businesses_to_check = cursor.fetchall()
        
        print(f"🔍 Найдено {len(businesses_to_check)} точек. Проверяем ссылки...")

        for b_id, name in businesses_to_check:
            # Ищем ссылки в BusinessMapLinks
            cursor.execute("SELECT url FROM BusinessMapLinks WHERE business_id = %s", (b_id,))
            links = cursor.fetchall()
            
            # Также проверяем yandex_url в таблице Businesses
            cursor.execute("SELECT yandex_url FROM Businesses WHERE id = %s", (b_id,))
            biz_url = cursor.fetchone()
            if biz_url and biz_url[0]:
                links.append((biz_url[0],))

            found_id = None
            found_url = None

            for row in links:
                url = row[0]
                if not url: continue
                # Ищем ID: yandex.ru/maps/org/12345
                match = re.search(r'org/(\d+)', url)
                if match:
                    found_id = match.group(1)
                    found_url = url
                    break
            
            if found_id:
                print(f"✏️  {name}: Найден ID {found_id} из ссылки {found_url}")
                cursor.execute("""
                    UPDATE Businesses 
                    SET yandex_org_id = %s, yandex_url = %s
                    WHERE id = %s
                """, (found_id, found_url, b_id))
                conn.commit()
            else:
                print(f"⚠️  {name}: Ссылка с ID организации не найдена в базе (BusinessMapLinks).")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fill_ids()
