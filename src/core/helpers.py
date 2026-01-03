"""
Helper функции для работы с бизнесами и пользователями
"""
from database_manager import DatabaseManager

def get_business_owner_id(cursor, business_id: str, include_active_check: bool = False) -> str | None:
    """Получить owner_id бизнеса
    
    Args:
        cursor: Курсор БД
        business_id: ID бизнеса
        include_active_check: Проверять ли is_active = 1
    
    Returns:
        owner_id или None если бизнес не найден
    """
    if include_active_check:
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ? AND is_active = 1", (business_id,))
    else:
        cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def get_business_id_from_user(user_id: str, business_id_from_request: str = None) -> str:
    """Получить business_id для отслеживания токенов
    
    Args:
        user_id: ID пользователя
        business_id_from_request: business_id из запроса (если есть)
    
    Returns:
        business_id или None
    """
    if business_id_from_request:
        return business_id_from_request
    
    # Пытаемся получить первый бизнес пользователя
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id FROM Businesses 
            WHERE owner_id = ? 
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        db.close()
        if row:
            return row[0] if isinstance(row, tuple) else row['id']
    except Exception as e:
        print(f"⚠️ Ошибка получения business_id: {e}")
    
    return None

def get_user_language(user_id: str, requested_language: str = None) -> str:
    """
    Получить язык пользователя из профиля бизнеса или использовать запрошенный язык.
    
    Args:
        user_id: ID пользователя
        requested_language: Язык, указанный в запросе (если есть)
    
    Returns:
        Код языка (ru, en, es, de, fr, it, pt, zh)
    """
    # Если язык указан в запросе - используем его
    if requested_language:
        return requested_language
    
    # Пытаемся получить язык из профиля бизнеса
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT language FROM Businesses 
            WHERE owner_id = ? 
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        db.close()
        if row and row[0]:
            return row[0]
    except Exception as e:
        print(f"⚠️ Ошибка получения языка пользователя: {e}")
    
    # По умолчанию русский
    return 'ru'

def find_business_id_for_user(cursor, user_id: str) -> str:
    """
    Найти business_id для пользователя из таблицы Businesses.
    Если не найден, возвращает user_id как fallback.
    
    Args:
        cursor: Курсор БД
        user_id: ID пользователя
    
    Returns:
        business_id или user_id если не найден
    """
    cursor.execute("SELECT id FROM Businesses WHERE owner_id = ? LIMIT 1", (user_id,))
    business_row = cursor.fetchone()
    if business_row:
        return business_row[0]
    return user_id

