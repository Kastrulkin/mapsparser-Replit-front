"""Auth helper functions for API endpoints."""
from flask import request
from auth_system import verify_session
from core.helpers import get_business_owner_id


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
    owner_id = get_business_owner_id(cursor, business_id)
    if not owner_id:
        return False, None
    
    user_id = user_data.get('user_id') or user_data.get('id')
    has_access = owner_id == user_id or user_data.get('is_superadmin', False)
    
    return has_access, owner_id
