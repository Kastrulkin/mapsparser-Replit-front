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
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from pg_db_utils import get_db_connection

PLACEHOLDER = "%s"

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{pwd_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля"""
    try:
        if not hashed or ':' not in hashed:
            print(f"❌ Неверный формат хеша: {hashed[:50] if hashed else 'None'}...")
            return False
        
        salt, pwd_hash = hashed.split(':', 1)
        print(f"🔍 Соль: {salt[:20]}..., Хеш: {pwd_hash[:20]}...")
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        new_hash_hex = new_hash.hex()
        print(f"🔍 Новый хеш: {new_hash_hex[:20]}...")
        result = new_hash_hex == pwd_hash
        print(f"🔍 Сравнение: {result}")
        return result
    except Exception as e:
        print(f"❌ Ошибка при проверке пароля: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_user(email: str, password: str = None, name: str = None, phone: str = None) -> Dict[str, Any]:
    """Создать нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли пользователь
        cursor.execute(f"SELECT id FROM Users WHERE email = {PLACEHOLDER}", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Создаем пользователя
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password) if password else None
        verification_token = secrets.token_urlsafe(32)

        # Runtime-схема может отличаться на старых окружениях:
        # если verification_token отсутствует, создаём пользователя без него.
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'verification_token'
            """
        )
        has_verification_token = bool(cursor.fetchone())

        if has_verification_token:
            cursor.execute(
                f"""
                INSERT INTO Users (id, email, password_hash, name, phone, verification_token, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """,
                (user_id, email, password_hash, name, phone, verification_token, datetime.now().isoformat()),
            )
        else:
            cursor.execute(
                f"""
                INSERT INTO Users (id, email, password_hash, name, phone, created_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
            """,
                (user_id, email, password_hash, name, phone, datetime.now().isoformat()),
            )
        
        conn.commit()
        
        return {
            "id": user_id,
            "email": email,
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
    
    try:
        cursor.execute(
            f"""
            SELECT id, email, password_hash, name, phone, is_active, is_verified
            FROM Users WHERE email = {PLACEHOLDER}
        """,
            (email,),
        )
        
        user = cursor.fetchone()
        if not user:
            print(f"❌ Пользователь не найден: {email}")
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
            print(f"❌ Ошибка извлечения данных пользователя: {e}")
            import traceback
            traceback.print_exc()
            return {"error": "Ошибка обработки данных пользователя"}
        
        if not is_active:
            print(f"❌ Аккаунт заблокирован: {email}")
            return {"error": "account_blocked", "message": "user is blocked"}
        
        # Если у пользователя нет пароля, это новый пользователь
        if not password_hash:
            print(f"❌ У пользователя нет пароля: {email}")
            return {"error": "NEED_PASSWORD", "message": "Необходимо установить пароль"}
        
        print(f"🔍 Проверка пароля для: {email}")
        print(f"🔍 Формат хеша в БД: {password_hash[:50] if password_hash else 'None'}...")
        password_valid = verify_password(password, password_hash)
        print(f"🔍 Результат проверки пароля: {password_valid}")
        
        if not password_valid:
            print(f"❌ Неверный пароль для: {email}")
            return {"error": "Неверный пароль"}
        
        print(f"✅ Успешная авторизация: {email}")
        return {
            "id": user_id,
            "email": user_email,
            "name": user_name,
            "phone": user_phone,
            "is_verified": is_verified
        }
        
    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}
    finally:
        conn.close()

def create_session(user_id: str, ip_address: str = None, user_agent: str = None) -> str:
    """Создать сессию пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        session_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(64)
        expires_at = datetime.now() + timedelta(days=30)
        
        cursor.execute(
            f"""
            INSERT INTO UserSessions (id, user_id, token, expires_at, ip_address, user_agent, created_at)
            VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
        """,
            (session_id, user_id, token, expires_at.isoformat(), ip_address, user_agent, datetime.now().isoformat()),
        )
        
        conn.commit()
        return token
        
    except Exception as e:
        return None
    finally:
        conn.close()

def verify_session(token: str) -> Optional[Dict[str, Any]]:
    """Проверить сессию пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            f"""
            SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active, u.is_superadmin
            FROM UserSessions s
            JOIN Users u ON s.user_id = u.id
            WHERE s.token = {PLACEHOLDER} AND s.expires_at > {PLACEHOLDER}
        """,
            (token, datetime.now().isoformat()),
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
            else:
                # Если это tuple или другой тип (user_id, expires_at, email, name, phone, is_active, is_superadmin)
                user_id = session[0] if len(session) > 0 else None
                email = session[2] if len(session) > 2 else None
                name = session[3] if len(session) > 3 else None
                phone = session[4] if len(session) > 4 else None
                is_active_val = session[5] if len(session) > 5 else True
                is_superadmin_val = session[6] if len(session) > 6 else None
            
            return {
                "user_id": user_id,
                "email": email,
                "name": name,
                "phone": phone,
                "is_active": bool(is_active_val) if is_active_val is not None else True,
                "is_superadmin": bool(is_superadmin_val) if is_superadmin_val is not None else False
            }
        except Exception as e:
            print(f"❌ Ошибка извлечения данных сессии: {e}")
            import traceback
            traceback.print_exc()
            return None
        
    except Exception as e:
        print(f"❌ Ошибка проверки сессии: {e}")
        import traceback
        traceback.print_exc()
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
    
    try:
        # Проверяем, существует ли пользователь с таким email
        cursor.execute(f"SELECT id FROM Users WHERE email = {PLACEHOLDER}", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Проверяем, есть ли уже приглашение
        cursor.execute(
            f"SELECT id FROM Invites WHERE email = {PLACEHOLDER} AND status = 'pending'",
            (email,),
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
            (invite_id, email, invited_by, token, expires_at.isoformat(), datetime.now().isoformat()),
        )
        
        conn.commit()
        
        return {
            "id": invite_id,
            "email": email,
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
