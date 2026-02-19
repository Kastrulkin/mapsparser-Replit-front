import sqlite3
import sys
import os

# Add parent directory to path to import database_manager if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = 'src/reports.db'

def link_kebab_network():
    if not os.path.exists(DB_PATH):
        print(f"❌ Ошибка: База данных не найдена по пути {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        print("🔍 Поиск сети 'Мастер Кебаб'...")
        
        # 1. Находим сеть
        cursor.execute("SELECT id, name FROM Networks WHERE name LIKE '%Мастер Кебаб%' OR name LIKE '%Master Kebab%'")
        network = cursor.fetchone()

        if not network:
            print("❌ Сеть 'Мастер Кебаб' не найдена.")
            print("   Пожалуйста, убедитесь, что вы создали сеть с таким именем в админке.")
            return

        network_id, network_name = network
        print(f"✅ Найдена сеть: '{network_name}' (ID: {network_id})")

        # 2. Находим бизнесы для привязки
        # Ищем всё, что похоже на Кебаб, но НЕ является самой сетью (материнским аккаунтом)
        print("\n🔍 Поиск точек для привязки (бизнесов с именем 'Кебаб' или 'Kebab')...")
        
        # Используем LOWER для регистронезависимого сравнения
        cursor.execute("SELECT id, name, network_id FROM Businesses")
        all_businesses = cursor.fetchall()
        
        businesses = []
        network_name_lower = network_name.lower().strip()
        
        for b_id, b_name, b_net_id in all_businesses:
            name_lower = b_name.lower()
            if ('кебаб' in name_lower or 'kebab' in name_lower):
                # Пропускаем, если это сама сеть (точное совпадение имени)
                if name_lower.strip() == network_name_lower:
                    print(f"  ℹ️ Пропускаем материнский аккаунт: {b_name}")
                    continue
                businesses.append((b_id, b_name, b_net_id))
        
        if not businesses:
            print("⚠️ Не найдено подходящих точек с названием 'Кебаб'.")
            return

        to_update = []
        already_linked = []

        for b_id, b_name, b_net_id in businesses:
            if b_net_id == network_id:
                already_linked.append(b_name)
            else:
                to_update.append((b_id, b_name))

        print(f"\nНайдено всего точек: {len(businesses)}")
        if already_linked:
            print(f"Уже привязаны ({len(already_linked)}):")
            for name in already_linked:
                print(f"  - {name}")

        if not to_update:
            print("\n✅ Все точки уже привязаны. Действий не требуется.")
            return

        print(f"\nБудут привязаны к сети '{network_name}' ({len(to_update)}):")
        for _, name in to_update:
            print(f"  - {name}")

        # 3. Подтверждение (если запускается интерактивно, но для автоматизации пропустим)
        # confirm = input("\nПродолжить? (y/n): ")
        # if confirm.lower() != 'y':
        #     print("Отмена.")
        #     return

        # 4. Обновление
        print("\n🚀 Привязываем точки...")
        for b_id, b_name in to_update:
            cursor.execute("UPDATE Businesses SET network_id = %s WHERE id = %s", (network_id, b_id))
            print(f"  ✅ {b_name} -> привязан")

        conn.commit()
        print("\n✨ Готово! Все точки успешно привязаны к сети.")

    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    link_kebab_network()
