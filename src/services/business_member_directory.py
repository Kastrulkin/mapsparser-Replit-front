"""Read the effective business team without exposing authentication data."""


def list_business_members(cursor, business_id):
    cursor.execute("""
        WITH access AS (
            SELECT owner_id AS user_id, 'owner' AS role, 'business' AS scope
            FROM businesses WHERE id = %s
            UNION ALL
            SELECT n.owner_id, 'owner', 'network'
            FROM networks n JOIN businesses b ON b.network_id = n.id WHERE b.id = %s
            UNION ALL
            SELECT user_id, role, 'business' FROM business_members
            WHERE business_id = %s AND status = 'active'
            UNION ALL
            SELECT nm.user_id, nm.role, 'network'
            FROM network_members nm JOIN businesses b ON b.network_id = nm.network_id
            WHERE b.id = %s AND nm.status = 'active'
        )
        SELECT u.id, u.name, u.email, u.is_active, access.role, access.scope
        FROM access JOIN users u ON u.id = access.user_id
        ORDER BY CASE WHEN access.role = 'owner' THEN 0 ELSE 1 END,
                 LOWER(COALESCE(u.name, u.email, '')), u.id, access.scope
    """, (business_id, business_id, business_id, business_id))
    members = {}
    for row in cursor.fetchall():
        data = dict(row) if hasattr(row, 'keys') else dict(zip(
            ('id', 'name', 'email', 'is_active', 'role', 'scope'), row))
        member = members.setdefault(data['id'], {
            'id': data['id'], 'name': data['name'] or '', 'email': data['email'] or '',
            'is_active': data['is_active'] is not False, 'access': [],
        })
        grant = {'role': data['role'], 'scope': data['scope']}
        if grant not in member['access']:
            member['access'].append(grant)
    return list(members.values())
