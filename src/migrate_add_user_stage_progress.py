#!/usr/bin/env python3
"""
Миграция: Добавить таблицу UserStageProgress для отслеживания прогресса пользователя
"""
from safe_db_utils import safe_migrate

def migrate_add_user_stage_progress():
    """Создать таблицу UserStageProgress"""
    
    def migration_func(cursor):
        print("Creating UserStageProgress table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS UserStageProgress (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                business_id TEXT NOT NULL,
                stage_id TEXT NOT NULL,
                is_unlocked INTEGER DEFAULT 0,
                progress_percentage INTEGER DEFAULT 0,
                completed_tasks TEXT,
                unlocked_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stage_id) REFERENCES GrowthStages(id),
                FOREIGN KEY (business_id) REFERENCES Businesses(id),
                FOREIGN KEY (user_id) REFERENCES Users(id)
            )
        """)
        print("✅ Table UserStageProgress created")
        
        # Создаем индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_stage_progress_business 
            ON UserStageProgress(business_id, user_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_stage_progress_stage 
            ON UserStageProgress(stage_id)
        """)
        print("✅ Indexes created")

    safe_migrate(
        migration_func,
        "Add UserStageProgress table for tracking user progress"
    )

if __name__ == "__main__":
    migrate_add_user_stage_progress()
    print("\n✅ Migration completed successfully!")
