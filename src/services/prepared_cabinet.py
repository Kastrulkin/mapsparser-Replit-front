"""Owner-only handoff for a cabinet prepared before the first sign-in."""
import hashlib
import json
import secrets

from psycopg2.extras import Json

from auth_system import hash_password
from core.email_delivery import build_password_setup_link

SECTIONS = ("services", "reviews", "content", "partnerships", "influencers")
TOKEN_PREFIX = "prepared."


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def validate_materials(value):
    if not isinstance(value, dict) or set(value) != set(SECTIONS):
        raise ValueError("Заполните все пять разделов подготовленного кабинета.")
    for items in value.values():
        if not isinstance(items, list) or not 1 <= len(items) <= 30:
            raise ValueError("В каждом разделе должно быть от 1 до 30 материалов.")
        for item in items:
            if not isinstance(item, dict) or set(item) != {"title", "text"}:
                raise ValueError("У каждого материала должны быть название и текст.")
            for field, limit in (("title", 200), ("text", 12000)):
                if not isinstance(item[field], str) or not item[field].strip() or len(item[field]) > limit:
                    raise ValueError("Проверьте название и текст материалов.")
    return value


def save_materials(cursor, business_id, materials):
    cursor.execute("""
        INSERT INTO prepared_cabinets (business_id, owner_id, materials)
        SELECT id, owner_id, %s FROM businesses WHERE id = %s AND is_active IS NOT FALSE
        ON CONFLICT (business_id) DO UPDATE SET materials = EXCLUDED.materials
        WHERE prepared_cabinets.owner_id = EXCLUDED.owner_id
        RETURNING business_id
    """, (Json(validate_materials(materials)), business_id))
    return bool(cursor.fetchone())


def issue_invite(cursor, business_id):
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    cursor.execute("""
        UPDATE prepared_cabinets p
        SET invite_hash = %s, invite_expires_at = NOW() + INTERVAL '7 days'
        FROM businesses b, users u
        WHERE p.business_id = %s AND b.id = p.business_id AND b.owner_id = p.owner_id
          AND u.id = p.owner_id AND b.is_active IS NOT FALSE AND u.is_active IS NOT FALSE
          AND COALESCE(u.password_hash, '') = ''
        RETURNING u.email
    """, (_digest(token), business_id))
    row = cursor.fetchone()
    if not row:
        return None
    return build_password_setup_link(row["email"], token, private_fragment=True)


def activate(cursor, *, email, password, token, consent_version, consent_ip, user_agent):
    cursor.execute("""
        SELECT p.business_id, u.id, u.email, u.name, u.phone
        FROM prepared_cabinets p
        JOIN businesses b ON b.id = p.business_id AND b.owner_id = p.owner_id
        JOIN users u ON u.id = p.owner_id
        WHERE p.invite_hash = %s AND p.invite_expires_at > NOW()
          AND LOWER(u.email) = %s AND b.is_active IS NOT FALSE AND u.is_active IS NOT FALSE
          AND COALESCE(u.password_hash, '') = ''
        FOR UPDATE OF p, b, u
    """, (_digest(token), email))
    row = cursor.fetchone()
    if not row:
        return None
    business_id, user_id = row["business_id"], row["id"]
    cursor.execute("""
        UPDATE users SET password_hash = %s, updated_at = NOW(), verification_token = NULL,
          personal_data_consent_at = NOW(), personal_data_consent_version = %s,
          privacy_accepted_at = NOW(), terms_accepted_at = NOW(), consent_ip = %s,
          consent_user_agent = %s
        WHERE id = %s
    """, (hash_password(password), consent_version, consent_ip, user_agent, user_id))
    cursor.execute("""
        UPDATE prepared_cabinets SET invite_hash = NULL, invite_expires_at = NULL, activated_at = NOW()
        WHERE business_id = %s
    """, (business_id,))
    return {"id": user_id, "email": row["email"], "name": row["name"] or "", "phone": row["phone"] or "", "business_id": business_id}


def owner_package(cursor, business_id, owner_id, reviewed=None):
    cursor.execute("""
        SELECT p.materials, p.seen FROM prepared_cabinets p
        JOIN businesses b ON b.id = p.business_id AND b.owner_id = p.owner_id
        WHERE p.business_id = %s AND p.owner_id = %s AND b.is_active IS NOT FALSE
    """ + (" FOR UPDATE OF p" if reviewed else ""), (business_id, owner_id))
    row = cursor.fetchone()
    if not row:
        return []
    materials, seen = row["materials"], row["seen"]
    sections = [
        {"key": key, "items": materials[key], "version": _digest(json.dumps(materials[key], sort_keys=True))}
        for key in SECTIONS if key in materials
    ]
    if reviewed:
        key, version = reviewed
        if any(section["key"] == key and section["version"] == version for section in sections):
            seen[key] = version
            cursor.execute("UPDATE prepared_cabinets SET seen = %s WHERE business_id = %s", (Json(seen), business_id))
    for section in sections:
        section["unread"] = seen.get(section["key"]) != section["version"]
    return sections
