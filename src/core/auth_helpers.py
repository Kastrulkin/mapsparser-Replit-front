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


def session_allows_business(user_data: dict, business_id: str) -> bool:
    """Session restriction only; callers must still authorize business membership."""
    return (str(user_data.get('session_kind') or 'standard') != 'demo'
            or str(user_data.get('scope_business_id') or '').strip() == str(business_id))


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
    if not session_allows_business(user_data, business_id):
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


def verify_business_write_access(cursor, business_id: str, user_data: dict) -> tuple[bool, str | None]:
    """Require tenant access and reject a viewer-only membership for writes.

    ``verify_business_access`` deliberately remains the role-blind read/tenant
    boundary. A person can hold both a direct and a network membership; a
    non-viewer active membership preserves the existing write behavior.
    """
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not has_access:
        return False, owner_id

    user_id = user_data.get('user_id') or user_data.get('id')
    if owner_id == user_id or user_data.get('is_superadmin', False):
        return True, owner_id

    cursor.execute(
        """
        SELECT bm.role
        FROM business_members bm
        WHERE bm.business_id = %s
          AND bm.user_id = %s
          AND bm.status = 'active'
        UNION ALL
        SELECT nm.role
        FROM network_members nm
        JOIN businesses b ON b.network_id = nm.network_id
        WHERE b.id = %s
          AND nm.user_id = %s
          AND nm.status = 'active'
        UNION ALL
        SELECT 'network_owner' AS role
        FROM networks n
        JOIN businesses b ON b.network_id = n.id
        WHERE b.id = %s
          AND n.owner_id = %s
        """,
        (business_id, user_id, business_id, user_id, business_id, user_id),
    )
    rows = cursor.fetchall() or []
    roles = []
    for row in rows:
        if hasattr(row, 'get'):
            role = row.get('role')
        else:
            role = row[0] if row else None
        if role:
            roles.append(str(role).strip().lower())

    return any(role != 'viewer' for role in roles), owner_id
