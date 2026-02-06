
from safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Adds missing columns to MapParseResults table.
    """
    print("Checking MapParseResults columns...")
    cursor.execute("PRAGMA table_info(MapParseResults)")
    columns = [row[1] for row in cursor.fetchall()]

    # 1. Title
    if 'title' not in columns:
        print("adding title to MapParseResults...")
        cursor.execute("ALTER TABLE MapParseResults ADD COLUMN title TEXT")
        print("✅ Added title.")
    
    # 2. Address
    if 'address' not in columns:
        print("adding address to MapParseResults...")
        cursor.execute("ALTER TABLE MapParseResults ADD COLUMN address TEXT")
        print("✅ Added address.")

    # 3. analysis_json (Server report missed this too, though local init has it)
    if 'analysis_json' not in columns:
        print("adding analysis_json to MapParseResults...")
        cursor.execute("ALTER TABLE MapParseResults ADD COLUMN analysis_json TEXT")
        print("✅ Added analysis_json.")
        
    print("✨ MapParseResults schema is correct.")

def migrate():
    print("🚀 Starting safe migration for MapParseResults...")
    success = safe_migrate(run_migration, "Fix MapParseResults Schema")
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)

if __name__ == "__main__":
    migrate()
