import sqlite3

def fix_cards_schema():
    conn = sqlite3.connect("reports.db")
    cur = conn.cursor()
    
    print("=== Текущая структура Cards ===")
    cur.execute("PRAGMA table_info(Cards)")
    for col in cur.fetchall():
        print(f"{col[1]} {col[2]}")
    
    print("\n=== Добавляем недостающие колонки ===")
    
    # Список колонок для добавления
    columns_to_add = [
        "site TEXT",
        "phone TEXT", 
        "hours TEXT",
        "hours_full TEXT",
        "competitors TEXT"
    ]
    
    for col_def in columns_to_add:
        col_name = col_def.split()[0]
        try:
            cur.execute(f"ALTER TABLE Cards ADD COLUMN {col_def}")
            print(f"✅ Добавлена колонка {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"⚠️ Колонка {col_name} уже существует")
            else:
                print(f"❌ Ошибка {col_name}: {e}")
    
    conn.commit()
    
    print("\n=== Обновленная структура Cards ===")
    cur.execute("PRAGMA table_info(Cards)")
    for col in cur.fetchall():
        print(f"{col[1]} {col[2]}")
    
    conn.close()

if __name__ == "__main__":
    fix_cards_schema()
