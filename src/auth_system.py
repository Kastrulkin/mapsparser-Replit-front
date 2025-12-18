#!/usr/bin/env python3
"""
Система аутентификации для SQLite базы данных
"""
import sqlite3
import uuid
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

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
        cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Создаем пользователя
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password) if password else None
        verification_token = secrets.token_urlsafe(32)
        
        cursor.execute("""
            INSERT INTO Users (id, email, password_hash, name, phone, verification_token, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, password_hash, name, phone, verification_token, datetime.now().isoformat()))
        
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
        cursor.execute("""
            SELECT id, email, password_hash, name, phone, is_active, is_verified
            FROM Users WHERE email = ?
        """, (email,))
        
        user = cursor.fetchone()
        if not user:
            print(f"❌ Пользователь не найден: {email}")
            return {"error": "Пользователь не найден"}
        
        if not user['is_active']:
            print(f"❌ Аккаунт заблокирован: {email}")
            return {"error": "Аккаунт заблокирован"}
        
        # Если у пользователя нет пароля, это новый пользователь
        if not user['password_hash']:
            print(f"❌ У пользователя нет пароля: {email}")
            return {"error": "NEED_PASSWORD", "message": "Необходимо установить пароль"}
        
        print(f"🔍 Проверка пароля для: {email}")
        print(f"🔍 Формат хеша в БД: {user['password_hash'][:50]}...")
        password_valid = verify_password(password, user['password_hash'])
        print(f"🔍 Результат проверки пароля: {password_valid}")
        
        if not password_valid:
            print(f"❌ Неверный пароль для: {email}")
            return {"error": "Неверный пароль"}
        
        print(f"✅ Успешная авторизация: {email}")
        return {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "phone": user['phone'],
            "is_verified": user['is_verified']
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
        
        cursor.execute("""
            INSERT INTO UserSessions (id, user_id, token, expires_at, ip_address, user_agent, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session_id, user_id, token, expires_at.isoformat(), ip_address, user_agent, datetime.now().isoformat()))
        
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
        cursor.execute("""
            SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active, u.is_superadmin
            FROM UserSessions s
            JOIN Users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, datetime.now().isoformat()))
        
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
                is_superadmin_val = session['is_superadmin'] if 'is_superadmin' in session.keys() else None
            else:
                # Если это tuple или другой тип
                user_id = session[0] if len(session) > 0 else None
                email = session[2] if len(session) > 2 else None
                name = session[3] if len(session) > 3 else None
                phone = session[4] if len(session) > 4 else None
                is_superadmin_val = session[6] if len(session) > 6 else None
            
            return {
                "user_id": user_id,
                "email": email,
                "name": name,
                "phone": phone,
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
        cursor.execute("DELETE FROM UserSessions WHERE token = ?", (token,))
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
        cursor.execute("SELECT id FROM Users WHERE id = ?", (user_id,))
        if not cursor.fetchone():
            return {"error": "Пользователь не найден"}
        
        # Хешируем пароль
        password_hash = hash_password(password)
        
        # Обновляем пароль
        cursor.execute("""
            UPDATE Users 
            SET password_hash = ?, updated_at = ?
            WHERE id = ?
        """, (password_hash, datetime.now().isoformat(), user_id))
        
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
        cursor.execute("""
            SELECT id, email, name, phone, telegram_id, created_at, is_active, is_verified
            FROM Users WHERE id = ?
        """, (user_id,))
        
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
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.append(user_id)
        query = f"UPDATE Users SET {', '.join(update_fields)}, updated_at = ? WHERE id = ?"
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
        cursor.execute("SELECT password_hash FROM Users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        
        if not user or not verify_password(old_password, user['password_hash']):
            return {"error": "Неверный текущий пароль"}
        
        # Устанавливаем новый пароль
        new_hash = hash_password(new_password)
        cursor.execute("UPDATE Users SET password_hash = ?, updated_at = ? WHERE id = ?", 
                      (new_hash, datetime.now().isoformat(), user_id))
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
        cursor.execute("SELECT id FROM Users WHERE email = ?", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Проверяем, есть ли уже приглашение
        cursor.execute("SELECT id FROM Invites WHERE email = ? AND status = 'pending'", (email,))
        if cursor.fetchone():
            return {"error": "Приглашение уже отправлено"}
        
        invite_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute("""
            INSERT INTO Invites (id, email, invited_by, token, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (invite_id, email, invited_by, token, expires_at.isoformat(), datetime.now().isoformat()))
        
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
        cursor.execute("""
            SELECT id, email, invited_by, expires_at
            FROM Invites 
            WHERE token = ? AND status = 'pending' AND expires_at > ?
        """, (token, datetime.now().isoformat()))
        
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
        cursor.execute("UPDATE Invites SET status = 'accepted' WHERE id = ?", (invite['id'],))
        conn.commit()
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
