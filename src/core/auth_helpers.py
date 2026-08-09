"""Auth helper functions for API endpoints."""
from flask import request
from auth_system import verify_session


def require_auth_from_request():
    """
    Проверка авторизации из request headers.
    
    Returns:
        dict | None: user_data если авторизован, иначе None
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    return verify_session(token)


def verify_business_access(cursor, business_id: str, user_data: dict) -> tuple[bool, str | None]:
    """
    Проверяет доступ пользователя к бизнесу.
    
    Args:
        cursor: database cursor
        business_id: ID бизнеса
        user_data: данные пользователя из verify_session
    
    Returns:
        tuple: (has_access: bool, owner_id: str | None)
            - has_access: True если есть доступ, иначе False
            - owner_id: ID владельца бизнеса или None если бизнес не найден
    """
    user_id = user_data.get('user_id') or user_data.get('id')
    session_kind = str(user_data.get('session_kind') or 'standard')
    demo_scope_business_id = str(user_data.get('scope_business_id') or '').strip()
    if session_kind == 'demo' and demo_scope_business_id != str(business_id):
        return False, None

    cursor.execute(
        """
        SELECT b.owner_id,
               EXISTS (
                   SELECT 1
                   FROM business_members bm
                   WHERE bm.business_id = b.id
                     AND bm.user_id = %s
                     AND bm.status = 'active'
               ) AS has_business_membership,
               EXISTS (
                   SELECT 1
                   FROM network_members nm
                   WHERE nm.network_id = b.network_id
                     AND nm.user_id = %s
                     AND nm.status = 'active'
               ) AS has_network_membership,
               EXISTS (
                   SELECT 1
                   FROM networks n
                   WHERE n.id = b.network_id
                     AND n.owner_id = %s
               ) AS owns_network
        FROM businesses b
        WHERE b.id = %s
          AND (b.is_active = TRUE OR b.is_active IS NULL)
        LIMIT 1
        """,
        (
            user_id,
            user_id,
            user_id,
            business_id,
        ),
    )
    row = cursor.fetchone()
    if not row:
        return False, None

    if hasattr(row, "keys"):
        owner_id = row.get("owner_id")
        has_business_membership = bool(row.get("has_business_membership"))
        has_network_membership = bool(row.get("has_network_membership"))
        owns_network = bool(row.get("owns_network"))
    else:
        owner_id = row[0]
        has_business_membership = bool(row[1])
        has_network_membership = bool(row[2])
        owns_network = bool(row[3]) if len(row) > 3 else False

    has_access = (
        owner_id == user_id
        or has_business_membership
        or has_network_membership
        or owns_network
        or user_data.get('is_superadmin', False)
    )
    
    return has_access, owner_id
