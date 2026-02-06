"""
Helper функции для работы с базой данных
"""

def ensure_user_examples_table(cursor):
    """
    Создать таблицу UserExamples если её нет.
    Используется в нескольких местах для избежания дублирования.
    """
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS UserExamples (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            example_type TEXT NOT NULL,
            example_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_examples_user_type ON UserExamples(user_id, example_type)")

