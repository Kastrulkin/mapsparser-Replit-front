from safe_db_utils import safe_migrate

def run_migration(cursor):
    """
    Callback function that performs the actual schema changes.
    Receives a cursor from safe_migrate.
    """
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='BusinessOptimizationWizard'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        print("Creating BusinessOptimizationWizard table...")
        cursor.execute("""
            CREATE TABLE BusinessOptimizationWizard (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                step INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id)
            )
        """)
        # Add index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wizard_business_id ON BusinessOptimizationWizard(business_id)")
        print("✅ Table created successfully")
    else:
        print("ℹ️ Table already exists, checking columns...")
        cursor.execute("PRAGMA table_info(BusinessOptimizationWizard)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'step' not in columns:
            print("Adding 'step' column...")
            cursor.execute("ALTER TABLE BusinessOptimizationWizard ADD COLUMN step INTEGER DEFAULT 1")
            print("✅ Column 'step' added")
        else:
            print("✨ Column 'step' already exists")

def migrate():
    print("🚀 Starting safe migration for BusinessOptimizationWizard...")
    success = safe_migrate(run_migration, "Create/Update BusinessOptimizationWizard table")
    
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        exit(1)

if __name__ == "__main__":
    migrate()
