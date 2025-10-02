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
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str) -> str:
    """Хеширование пароля"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{pwd_hash.hex()}"

def verify_password(password: str, hashed: str) -> bool:
    """Проверка пароля"""
    try:
        salt, pwd_hash = hashed.split(':')
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return new_hash.hex() == pwd_hash
    except:
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
            return {"error": "Пользователь не найден"}
        
        if not user['is_active']:
            return {"error": "Аккаунт заблокирован"}
        
        # Если у пользователя нет пароля, это новый пользователь
        if not user['password_hash']:
            return {"error": "NEED_PASSWORD", "message": "Необходимо установить пароль"}
        
        if not verify_password(password, user['password_hash']):
            return {"error": "Неверный пароль"}
        
        return {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "phone": user['phone'],
            "is_verified": user['is_verified']
        }
        
    except Exception as e:
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
            SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active
            FROM UserSessions s
            JOIN Users u ON s.user_id = u.id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, datetime.now().isoformat()))
        
        session = cursor.fetchone()
        if not session:
            return None
        
        return {
            "user_id": session['user_id'],
            "email": session['email'],
            "name": session['name'],
            "phone": session['phone']
        }
        
    except Exception as e:
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
