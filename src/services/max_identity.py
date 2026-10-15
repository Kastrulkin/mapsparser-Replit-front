"""Account linking requires both a LocalOS login and a signed MAX identity."""
import hashlib
import secrets


class MaxLinkError(ValueError):
    pass


def issue_link_code(cursor, user_id):
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("max-link-user:" + user_id,))
    cursor.execute("UPDATE max_link_tokens SET consumed_at=NOW() WHERE user_id=%s AND consumed_at IS NULL", (user_id,))
    code = secrets.token_urlsafe(32)
    cursor.execute("""INSERT INTO max_link_tokens(token_hash,user_id,expires_at)
        VALUES (%s,%s,NOW()+INTERVAL '10 minutes')""", (hashlib.sha256(code.encode()).hexdigest(), user_id))
    return code


def consume_link_code(cursor, code, max_id):
    if not isinstance(code, str) or not 40 <= len(code) <= 100:
        raise MaxLinkError("Код недействителен или истёк")
    return consume_link_hash(cursor, hashlib.sha256(code.encode()).hexdigest(), max_id)


def consume_link_hash(cursor, token_hash, max_id):
    if not isinstance(token_hash, str) or len(token_hash) != 64 or any(char not in '0123456789abcdef' for char in token_hash):
        raise MaxLinkError("Код недействителен или истёк")
    cursor.execute("""SELECT user_id FROM max_link_tokens WHERE token_hash=%s
        AND consumed_at IS NULL AND expires_at>NOW()""", (token_hash,))
    row = cursor.fetchone()
    if not row:
        raise MaxLinkError("Код недействителен или истёк")
    user_id = str(row["user_id"] if hasattr(row, "keys") else row[0])
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("max-link-user:" + user_id,))
    cursor.execute("SELECT user_id FROM max_link_tokens WHERE token_hash=%s AND consumed_at IS NULL AND expires_at>NOW() FOR UPDATE", (token_hash,))
    if not cursor.fetchone():
        raise MaxLinkError("Код недействителен или истёк")
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("max-link-id:" + max_id,))
    cursor.execute("SELECT id FROM users WHERE id=%s AND COALESCE(is_active,TRUE)=TRUE", (user_id,))
    if not cursor.fetchone():
        raise MaxLinkError("Аккаунт недоступен")
    cursor.execute("SELECT user_id FROM max_identities WHERE max_id=%s OR user_id=%s FOR UPDATE", (max_id, user_id))
    for existing in cursor.fetchall():
        owner = str(existing["user_id"] if hasattr(existing, "keys") else existing[0])
        if owner != user_id:
            raise MaxLinkError("Аккаунт MAX уже связан с другим пользователем")
    cursor.execute("SELECT max_id,revoked_at FROM max_identities WHERE user_id=%s", (user_id,))
    existing = cursor.fetchone()
    if existing and str(existing["max_id"] if hasattr(existing, "keys") else existing[0]) != max_id:
        revoked = existing["revoked_at"] if hasattr(existing, "keys") else existing[1]
        if not revoked:
            raise MaxLinkError("Сначала отключите предыдущую привязку MAX")
        cursor.execute("DELETE FROM max_identities WHERE user_id=%s AND revoked_at IS NOT NULL", (user_id,))
    cursor.execute("""INSERT INTO max_identities(max_id,user_id) VALUES (%s,%s)
        ON CONFLICT(max_id) DO UPDATE SET revoked_at=NULL,linked_at=NOW(),notifications_enabled=FALSE
        WHERE max_identities.user_id=EXCLUDED.user_id""", (max_id, user_id))
    cursor.execute("UPDATE max_link_tokens SET consumed_at=NOW() WHERE token_hash=%s", (token_hash,))
    return user_id
