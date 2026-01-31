import sqlite3
import os

DB_PATH = 'src/reports.db'

def fix_mother_account():
    if not os.path.exists(DB_PATH):
        print(f"❌ База данных не найдена: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Находим "Мастер Кебаб"
        print("🔍 Ищу бизнес 'Мастер Кебаб'...")
        cursor.execute("SELECT id, name, network_id FROM Businesses WHERE name = 'Мастер Кебаб'")
        business = cursor.fetchone()

        if not business:
            print("❌ Бизнес 'Мастер Кебаб' не найден!")
            return

        b_id, name, net_id = business
        print(f"📄 Нашел бизнес: {name} (ID: {b_id})")
        print(f"🔗 Текущий network_id: {net_id}")

        if net_id:
            print("⚠️ У материнского аккаунта установлен network_id! Это ошибка.")
            print("🛠 Очищаю network_id...")
            cursor.execute("UPDATE Businesses SET network_id = NULL WHERE id = ?", (b_id,))
            conn.commit()
            print("✅ network_id очищен. Теперь бизнес должен появиться в списке.")
        else:
            print("✅ network_id уже пустой (NULL). Бизнес должен быть виден.")
            print("Если он не виден, проверьте фильтры во фронтенде.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_mother_account()
