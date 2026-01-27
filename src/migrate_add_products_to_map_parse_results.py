
from safe_db_utils import safe_migrate

def migrate_add_products_column():
    """Добавить колонку products в таблицу MapParseResults"""
    
    def migration_func(cursor):
        print("Добавление колонки products в MapParseResults...")
        
        # Проверяем и создаем таблицу если нет (на всякий случай, хотя должна быть)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='MapParseResults'")
        if not cursor.fetchone():
            print("⚠️ Таблица MapParseResults не найдена, пропускаем добавление колонки.")
            return

        try:
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN products TEXT DEFAULT NULL")
            print("✅ Колонка products добавлена")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("ℹ️ Колонка products уже существует")
            else:
                raise
    
    safe_migrate(migration_func, "Add products column to MapParseResults")

if __name__ == '__main__':
    migrate_add_products_column()
