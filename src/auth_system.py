#!/usr/bin/env python3
"""
Система аутентификации (Postgres‑only runtime).

Runtime всегда использует PostgreSQL через pg_db_utils и psycopg2.
SQLite/`reports.db` допускаются только в legacy‑скриптах, но не здесь.
"""

import uuid
from typing import Optional, Dict, Any
import hashlib
import secrets
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from pg_db_utils import get_db_connection

PLACEHOLDER = "%s"
CONSENT_VERSION = "localos-personal-data-v1-2026-05-11"
logger = logging.getLogger(__name__)

def normalize_email(email: str) -> str:
    """Normalize email for identity lookup."""
    return str(email or "").strip().lower()

def _row_value(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    if hasattr(row, "keys"):
        try:
            if key in row.keys():
                return row[key]
        except Exception:
            return default
    try:
        return row[index]
    except Exception:
        return default

def _table_columns(cursor: Any, table_name: str) -> set:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name.lower(),),
    )
    rows = cursor.fetchall() or []
    columns = set()
    for row in rows:
        column_name = _row_value(row, "column_name", 0)
        if column_name:
            columns.add(str(column_name).lower())
    return columns

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{pwd_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля"""
    try:
        if not hashed or ':' not in hashed:
            logger.warning("Invalid password hash format")
            return False
        
        salt, pwd_hash = hashed.split(':', 1)
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        new_hash_hex = new_hash.hex()
        result = secrets.compare_digest(new_hash_hex, pwd_hash)
        return result
    except Exception as e:
        logger.warning("Password verification failed: %s", type(e).__name__)
        return False

def create_user(
    email: str,
    password: str = None,
    name: str = None,
    phone: str = None,
    *,
    personal_data_consent: bool = False,
    consent_version: str = CONSENT_VERSION,
    consent_ip: str = None,
    consent_user_agent: str = None,
    is_verified: bool = False,
) -> Dict[str, Any]:
    """Создать нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    normalized_email = normalize_email(email)
    
    try:
        # Проверяем, существует ли пользователь
        cursor.execute(f"SELECT id FROM Users WHERE LOWER(email) = {PLACEHOLDER}", (normalized_email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password) if password else None
        verification_token = secrets.token_urlsafe(32)
        now = datetime.now().isoformat()
        columns = _table_columns(cursor, "users")

        insert_columns = ["id", "email", "password_hash", "name", "phone", "created_at"]
        insert_values = [user_id, normalized_email, password_hash, name, phone, now]

        optional_values = {
            "updated_at": now,
            "verification_token": verification_token,
            "is_verified": bool(is_verified),
        }
        if personal_data_consent:
            optional_values.update(
                {
                    "personal_data_consent_at": now,
                    "personal_data_consent_version": consent_version,
                    "privacy_accepted_at": now,
                    "terms_accepted_at": now,
                    "consent_ip": consent_ip,
                    "consent_user_agent": consent_user_agent,
                }
            )

        for column, value in optional_values.items():
            if column in columns:
                insert_columns.append(column)
                insert_values.append(value)

        placeholders = ", ".join([PLACEHOLDER] * len(insert_columns))
        column_sql = ", ".join(insert_columns)
        cursor.execute(
            f"INSERT INTO Users ({column_sql}) VALUES ({placeholders})",
            tuple(insert_values),
        )
        
        conn.commit()
        
        return {
            "id": user_id,
            "email": normalized_email,
            "name": name,
            "phone": phone,
            "verification_token": verification_token,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def authenticate_user(email: str, password: str) -> Dict[str, Any]:
    """Аутентификация пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    normalized_email = normalize_email(email)
    
    try:
        cursor.execute(
            f"""
            SELECT id, email, password_hash, name, phone, is_active, is_verified
            FROM Users WHERE LOWER(email) = {PLACEHOLDER}
        """,
            (normalized_email,),
        )
        
        user = cursor.fetchone()
        if not user:
            logger.info("Authentication failed: user not found")
            return {"error": "Пользователь не найден"}
        
        # Безопасное извлечение данных из sqlite3.Row
        try:
            if hasattr(user, 'keys'):
                # Это sqlite3.Row
                user_id = user['id'] if 'id' in user.keys() else None
                user_email = user['email'] if 'email' in user.keys() else None
                password_hash = user['password_hash'] if 'password_hash' in user.keys() else None
                user_name = user['name'] if 'name' in user.keys() else None
                user_phone = user['phone'] if 'phone' in user.keys() else None
                is_active = user['is_active'] if 'is_active' in user.keys() else None
                is_verified = user['is_verified'] if 'is_verified' in user.keys() else None
            else:
                # Если это tuple
                user_id = user[0] if len(user) > 0 else None
                user_email = user[1] if len(user) > 1 else None
                password_hash = user[2] if len(user) > 2 else None
                user_name = user[3] if len(user) > 3 else None
                user_phone = user[4] if len(user) > 4 else None
                is_active = user[5] if len(user) > 5 else None
                is_verified = user[6] if len(user) > 6 else None
        except Exception as e:
            logger.warning("Authentication failed: user row extraction error: %s", type(e).__name__)
            return {"error": "Ошибка обработки данных пользователя"}
        
        if not is_active:
            logger.info("Authentication blocked inactive account")
            return {"error": "account_blocked", "message": "user is blocked"}

        if is_verified is False:
            logger.info("Authentication blocked unverified account")
            return {"error": "EMAIL_NOT_VERIFIED", "message": "Подтвердите email перед входом"}
        
        # Если у пользователя нет пароля, это новый пользователь
        if not password_hash:
            logger.info("Authentication requires password setup")
            return {"error": "NEED_PASSWORD", "message": "Необходимо установить пароль"}
        
        password_valid = verify_password(password, password_hash)
        
        if not password_valid:
            logger.info("Authentication failed: invalid password")
            return {"error": "Неверный пароль"}
        
        logger.info("Authentication succeeded")
        return {
            "id": user_id,
            "email": user_email,
            "name": user_name,
            "phone": user_phone,
            "is_verified": is_verified
        }
        
    except Exception as e:
        logger.warning("Authentication error: %s", type(e).__name__)
        return {"error": str(e)}
    finally:
        conn.close()

def create_session(
    user_id: str,
    ip_address: str = None,
    user_agent: str = None,
    *,
    session_kind: str = "standard",
    scope_business_id: str = None,
    expires_days: int = 30,
) -> str:
    """Создать сессию пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        session_id = str(uuid.uuid4())
        normalized_kind = str(session_kind or "standard").strip().lower()
        if normalized_kind not in {"standard", "demo"}:
            return None
        token_value = secrets.token_urlsafe(64)
        token = f"demo_{token_value}" if normalized_kind == "demo" else token_value
        safe_expires_days = max(1, min(int(expires_days or 30), 90))
        expires_at = datetime.now() + timedelta(days=safe_expires_days)
        
        cursor.execute(
            f"""
            INSERT INTO UserSessions (
                id, user_id, token, expires_at, ip_address, user_agent, created_at,
                session_kind, scope_business_id
            )
            VALUES (
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER},
                {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}
            )
        """,
            (
                session_id,
                user_id,
                token,
                expires_at.isoformat(),
                ip_address,
                user_agent,
                datetime.now().isoformat(),
                normalized_kind,
                scope_business_id,
            ),
        )
        
        conn.commit()
        return token
        
    except Exception as e:
        return None
    finally:
        conn.close()

def verify_email_token(token: str) -> Dict[str, Any]:
    """Подтвердить email по verification token."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        columns = _table_columns(cursor, "users")
        if "verification_token" not in columns:
            return {"error": "Email-подтверждение не настроено"}

        cursor.execute(
            f"""
            SELECT id, email, name, phone, is_verified
            FROM Users
            WHERE verification_token = {PLACEHOLDER}
            LIMIT 1
            """,
            (str(token or "").strip(),),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Ссылка подтверждения недействительна или уже использована"}

        user_id = _row_value(row, "id", 0)
        email = _row_value(row, "email", 1)
        name = _row_value(row, "name", 2)
        phone = _row_value(row, "phone", 3)

        updates = ["is_verified = %s", "verification_token = NULL", "updated_at = %s"]
        values = [True, datetime.now().isoformat()]
        if "email_verified_at" in columns:
            updates.append("email_verified_at = %s")
            values.append(datetime.now().isoformat())
        values.append(user_id)

        cursor.execute(
            f"UPDATE Users SET {', '.join(updates)} WHERE id = %s",
            tuple(values),
        )
        conn.commit()

        return {
            "success": True,
            "id": user_id,
            "email": email,
            "name": name,
            "phone": phone,
        }
    except Exception:
        return {"error": "Ошибка подтверждения email"}
    finally:
        conn.close()

def rotate_verification_token(email: str) -> Dict[str, Any]:
    """Создать новый verification token для неподтвержденного пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    normalized_email = normalize_email(email)

    try:
        columns = _table_columns(cursor, "users")
        if "verification_token" not in columns:
            return {"error": "Email-подтверждение не настроено"}

        cursor.execute(
            f"""
            SELECT id, email, name, is_verified
            FROM Users
            WHERE LOWER(email) = {PLACEHOLDER}
            LIMIT 1
            """,
            (normalized_email,),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Пользователь с таким email не найден"}

        if _row_value(row, "is_verified", 3) is True:
            return {"error": "Email уже подтвержден"}

        token = secrets.token_urlsafe(32)
        cursor.execute(
            f"""
            UPDATE Users
            SET verification_token = {PLACEHOLDER}, updated_at = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
            """,
            (token, datetime.now().isoformat(), _row_value(row, "id", 0)),
        )
        conn.commit()
        return {
            "success": True,
            "id": _row_value(row, "id", 0),
            "email": _row_value(row, "email", 1),
            "name": _row_value(row, "name", 2),
            "verification_token": token,
        }
    except Exception:
        return {"error": "Ошибка повторной отправки подтверждения"}
    finally:
        conn.close()

def create_password_setup_token(user_id: str) -> Dict[str, Any]:
    """Create or rotate a setup token for an active passwordless user."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        columns = _table_columns(cursor, "users")
        if "verification_token" not in columns:
            return {"error": "Установка пароля по ссылке не настроена"}

        cursor.execute(
            f"""
            SELECT id, email, name, phone, password_hash, is_active
            FROM Users
            WHERE id = {PLACEHOLDER}
            LIMIT 1
            """,
            (str(user_id or "").strip(),),
        )
        row = cursor.fetchone()
        if not row:
            return {"error": "Пользователь не найден"}
        is_active = _row_value(row, "is_active", 5)
        if is_active in (False, 0, "0"):
            return {"error": "Пользователь приостановлен"}
        if str(_row_value(row, "password_hash", 4) or "").strip():
            return {"error": "У пользователя уже установлен пароль"}

        token = secrets.token_urlsafe(32)
        updates = ["verification_token = %s", "updated_at = %s"]
        values = [token, datetime.now().isoformat()]
        if "is_verified" in columns:
            updates.append("is_verified = %s")
            values.append(False)
        values.append(_row_value(row, "id", 0))

        cursor.execute(
            f"UPDATE Users SET {', '.join(updates)} WHERE id = %s",
            tuple(values),
        )
        conn.commit()

        return {
            "success": True,
            "id": _row_value(row, "id", 0),
            "email": _row_value(row, "email", 1),
            "name": _row_value(row, "name", 2),
            "phone": _row_value(row, "phone", 3),
            "verification_token": token,
        }
    except Exception:
        return {"error": "Ошибка создания ссылки установки пароля"}
    finally:
        conn.close()

def verify_session(token: str) -> Optional[Dict[str, Any]]:
    """Проверить сессию пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        params = (token, datetime.now().isoformat())
        try:
            cursor.execute(
                f"""
                SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active, u.is_superadmin,
                       s.id AS session_id, s.session_kind, s.scope_business_id
                FROM UserSessions s
                JOIN Users u ON s.user_id = u.id
                WHERE s.token = {PLACEHOLDER} AND s.expires_at > {PLACEHOLDER}
            """,
                params,
            )
        except Exception as query_error:
            error_text = str(query_error).lower()
            if "session_kind" not in error_text and "scope_business_id" not in error_text:
                raise
            conn.rollback()
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active, u.is_superadmin
                FROM UserSessions s
                JOIN Users u ON s.user_id = u.id
                WHERE s.token = {PLACEHOLDER} AND s.expires_at > {PLACEHOLDER}
            """,
                params,
            )
        
        session = cursor.fetchone()
        if not session:
            return None
        
        # Безопасное извлечение данных из sqlite3.Row
        try:
            # Если это sqlite3.Row, обращаемся по ключам
            if hasattr(session, 'keys'):
                user_id = session['user_id'] if 'user_id' in session.keys() else None
                email = session['email'] if 'email' in session.keys() else None
                name = session['name'] if 'name' in session.keys() else None
                phone = session['phone'] if 'phone' in session.keys() else None
                is_active_val = session['is_active'] if 'is_active' in session.keys() else True
                is_superadmin_val = session['is_superadmin'] if 'is_superadmin' in session.keys() else None
                session_id = session['session_id'] if 'session_id' in session.keys() else None
                session_kind = session['session_kind'] if 'session_kind' in session.keys() else 'standard'
                scope_business_id = session['scope_business_id'] if 'scope_business_id' in session.keys() else None
            else:
                # Если это tuple или другой тип (user_id, expires_at, email, name, phone, is_active, is_superadmin)
                user_id = session[0] if len(session) > 0 else None
                email = session[2] if len(session) > 2 else None
                name = session[3] if len(session) > 3 else None
                phone = session[4] if len(session) > 4 else None
                is_active_val = session[5] if len(session) > 5 else True
                is_superadmin_val = session[6] if len(session) > 6 else None
                session_id = session[7] if len(session) > 7 else None
                session_kind = session[8] if len(session) > 8 else 'standard'
                scope_business_id = session[9] if len(session) > 9 else None
            
            normalized_session_kind = str(session_kind or "standard")
            return {
                "user_id": user_id,
                "email": email,
                "name": name,
                "phone": phone,
                "is_active": bool(is_active_val) if is_active_val is not None else True,
                "is_superadmin": (
                    False
                    if normalized_session_kind == "demo"
                    else bool(is_superadmin_val) if is_superadmin_val is not None else False
                ),
                "session_id": session_id,
                "session_kind": normalized_session_kind,
                "scope_business_id": scope_business_id,
            }
        except Exception as e:
            logger.warning("Session row extraction error: %s", type(e).__name__)
            return None
        
    except Exception as e:
        logger.warning("Session verification error: %s", type(e).__name__)
        return None
    finally:
        conn.close()

def logout_session(token: str) -> bool:
    """Выйти из сессии"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"DELETE FROM UserSessions WHERE token = {PLACEHOLDER}", (token,))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False
    finally:
        conn.close()

def set_password(user_id: str, password: str) -> Dict[str, Any]:
    """Установить пароль для пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, что пользователь существует
        cursor.execute(f"SELECT id FROM Users WHERE id = {PLACEHOLDER}", (user_id,))
        if not cursor.fetchone():
            return {"error": "Пользователь не найден"}
        
        # Хешируем пароль
        password_hash = hash_password(password)
        
        # Обновляем пароль
        cursor.execute(
            f"""
            UPDATE Users 
            SET password_hash = {PLACEHOLDER}, updated_at = {PLACEHOLDER}
            WHERE id = {PLACEHOLDER}
        """,
            (password_hash, datetime.now().isoformat(), user_id),
        )
        
        conn.commit()
        
        return {"success": True, "message": "Пароль успешно установлен"}
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Получить пользователя по ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            f"""
            SELECT id, email, name, phone, telegram_id, created_at, is_active, is_verified
            FROM Users WHERE id = {PLACEHOLDER}
        """,
            (user_id,),
        )
        
        user = cursor.fetchone()
        if not user:
            return None
        
        return dict(user)
        
    except Exception as e:
        return None
    finally:
        conn.close()

def update_user(user_id: str, **kwargs) -> bool:
    """Обновить данные пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Подготавливаем данные для обновления
        update_fields = []
        values = []
        
        allowed_fields = ['name', 'phone', 'telegram_id']
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = %s")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.append(user_id)
        query = f"UPDATE Users SET {', '.join(update_fields)}, updated_at = %s WHERE id = %s"
        values.append(datetime.now().isoformat())
        
        cursor.execute(query, values)
        conn.commit()
        
        return cursor.rowcount > 0
        
    except Exception as e:
        return False
    finally:
        conn.close()

def change_password(user_id: str, old_password: str, new_password: str) -> Dict[str, Any]:
    """Изменить пароль пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем старый пароль
        cursor.execute(f"SELECT password_hash FROM Users WHERE id = {PLACEHOLDER}", (user_id,))
        user = cursor.fetchone()
        
        if not user or not verify_password(old_password, user['password_hash']):
            return {"error": "Неверный текущий пароль"}
        
        # Устанавливаем новый пароль
        new_hash = hash_password(new_password)
        cursor.execute(
            f"UPDATE Users SET password_hash = {PLACEHOLDER}, updated_at = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
            (new_hash, datetime.now().isoformat(), user_id),
        )
        conn.commit()
        
        return {"success": True}
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def create_invite(invited_by: str, email: str) -> Dict[str, Any]:
    """Создать приглашение"""
    conn = get_db_connection()
    cursor = conn.cursor()
    normalized_email = normalize_email(email)
    
    try:
        # Проверяем, существует ли пользователь с таким email
        cursor.execute(f"SELECT id FROM Users WHERE LOWER(email) = {PLACEHOLDER}", (normalized_email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Проверяем, есть ли уже приглашение
        cursor.execute(
            f"SELECT id FROM Invites WHERE LOWER(email) = {PLACEHOLDER} AND status = 'pending'",
            (normalized_email,),
        )
        if cursor.fetchone():
            return {"error": "Приглашение уже отправлено"}
        
        invite_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute(
            f"""
            INSERT INTO Invites (id, email, invited_by, token, expires_at, created_at)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """,
            (invite_id, normalized_email, invited_by, token, expires_at.isoformat(), datetime.now().isoformat()),
        )
        
        conn.commit()
        
        return {
            "id": invite_id,
            "email": normalized_email,
            "token": token,
            "expires_at": expires_at.isoformat()
        }
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

def verify_invite(token: str) -> Optional[Dict[str, Any]]:
    """Проверить приглашение"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            f"""
            SELECT id, email, invited_by, expires_at
            FROM Invites 
            WHERE token = {PLACEHOLDER} AND status = 'pending' AND expires_at > {PLACEHOLDER}
        """,
            (token, datetime.now().isoformat()),
        )
        
        invite = cursor.fetchone()
        if not invite:
            return None
        
        return dict(invite)
        
    except Exception as e:
        return None
    finally:
        conn.close()

def accept_invite(token: str, password: str, name: str = None) -> Dict[str, Any]:
    """Принять приглашение и создать пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем приглашение
        invite = verify_invite(token)
        if not invite:
            return {"error": "Недействительное или просроченное приглашение"}
        
        # Создаем пользователя
        result = create_user(invite['email'], password, name)
        if 'error' in result:
            return result
        
        # Отмечаем приглашение как принятое
        cursor.execute(
            f"UPDATE Invites SET status = 'accepted' WHERE id = {PLACEHOLDER}",
            (invite["id"],),
        )
        conn.commit()
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
