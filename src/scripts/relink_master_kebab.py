import sqlite3
import os

DB_PATH = 'src/reports.db'

def relink_mother_account():
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Находим сеть "Мастер Кебаб"
        print("🔍 Ищу сеть 'Мастер Кебаб'...")
        cursor.execute("SELECT id FROM Networks WHERE name = 'Мастер Кебаб'")
        network = cursor.fetchone()

        if not network:
            print("❌ Сеть 'Мастер Кебаб' не найдена!")
            return
        
        network_id = network[0]
        print(f"✅ Найдена сеть ID: {network_id}")

        # 2. Находим бизнес "Мастер Кебаб"
        print("🔍 Ищу бизнес 'Мастер Кебаб'...")
        cursor.execute("SELECT id, name, network_id FROM Businesses WHERE name = 'Мастер Кебаб'")
        business = cursor.fetchone()

        if not business:
            print("❌ Бизнес 'Мастер Кебаб' не найден!")
            return

        b_id, name, current_net_id = business
        print(f"📄 Нашел бизнес: {name} (ID: {b_id})")

        if current_net_id == network_id:
            print("✅ Бизнес уже привязан к правильной сети.")
        else:
            print(f"🛠 Привязываю бизнес к сети {network_id}...")
            cursor.execute("UPDATE Businesses SET network_id = ? WHERE id = ?", (network_id, b_id))
            conn.commit()
            print("✅ Успешно привязан.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    relink_mother_account()
