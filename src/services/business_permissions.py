"""Action permissions for business owners and membership roles."""
ROLE_PERMISSIONS = {
    'owner': {'business.read', 'business.settings.write', 'team.manage', 'operations.write', 'work.facts.write'},
    'admin': {'business.read', 'operations.write', 'work.facts.write'},
    'manager': {'business.read', 'operations.write', 'work.facts.write'},
    'member': {'business.read', 'operations.write', 'work.facts.write'},
    'master': {'business.read', 'work.facts.write'},
    'viewer': {'business.read'},
}


def roles_allow(roles, permission):
    return any(permission in ROLE_PERMISSIONS.get('owner' if role == 'network_owner' else role, set()) for role in roles)


def actor_roles(cursor, business_id, user):
    from core.auth_helpers import verify_business_access
    allowed, owner_id = verify_business_access(cursor, business_id, user)
    if not allowed:
        return []
    if owner_id == (user.get('user_id') or user.get('id')) or user.get('is_superadmin'):
        return ['owner']
    user_id = user.get('user_id') or user.get('id')
    cursor.execute("""SELECT role FROM business_members WHERE business_id=%s AND user_id=%s AND status='active'
        UNION ALL SELECT nm.role FROM network_members nm JOIN businesses b ON b.network_id=nm.network_id
        WHERE b.id=%s AND nm.user_id=%s AND nm.status='active'
        UNION ALL SELECT 'owner' FROM networks n JOIN businesses b ON b.network_id=n.id
        WHERE b.id=%s AND n.owner_id=%s""", (business_id, user_id, business_id, user_id, business_id, user_id))
    return [row.get('role') if hasattr(row, 'keys') else row[0] for row in cursor.fetchall()]


def require_permission(cursor, business_id, user, permission):
    if not roles_allow(actor_roles(cursor, business_id, user), permission):
        raise PermissionError('Нет права на это действие в выбранном бизнесе.')


def load_actor(cursor, user_id):
    cursor.execute('SELECT id, is_active, is_superadmin FROM users WHERE id=%s', (user_id,))
    row = cursor.fetchone()
    if row is None:
        raise PermissionError('Аккаунт недоступен.')
    user = dict(row) if hasattr(row, 'keys') else dict(zip(('id', 'is_active', 'is_superadmin'), row))
    if user.get('is_active') is False:
        raise PermissionError('Аккаунт отключён.')
    user['user_id'] = user_id
    return user
