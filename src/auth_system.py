#!/usr/bin/env python3
"""
Система аутентификации для PostgreSQL базы данных
PostgreSQL-only: SQLite больше не поддерживается
"""
import uuid
from typing import Optional, Dict, Any
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    """Получить соединение с PostgreSQL базой данных"""
    from core.db_connection import get_db_connection as _get_db_connection
    return _get_db_connection()

def hash_password(password: str) -> str:
    """Хеширование пароля через werkzeug"""
    return generate_password_hash(password)

def verify_password_legacy(password: str, hashed: str) -> bool:
    """
    Проверка пароля в старом формате (salt:hash через PBKDF2)
    Используется только для миграции старых паролей
    """
    if not hashed or ':' not in hashed:
        return False
    try:
        import hashlib
        salt, pwd_hash = hashed.split(':', 1)
        new_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return new_hash.hex() == pwd_hash
    except Exception:
        return False

def verify_password(password: str, hashed: str) -> bool:
    """
    Проверка пароля с поддержкой двух форматов:
    1. werkzeug (scrypt:) - новый формат
    2. legacy (salt:hash) - старый формат (для миграции)
    """
    if not hashed:
        return False
    
    # Новый формат (werkzeug)
    if hashed.startswith('scrypt:'):
        try:
            return check_password_hash(hashed, password)
        except Exception as e:
            print(f"❌ Ошибка при проверке пароля (werkzeug): {e}")
            return False
    
    # Старый формат (legacy)
    try:
        result = verify_password_legacy(password, hashed)
        if result:
            print("[AUTH] Использован legacy формат пароля (будет перехеширован при следующем входе)")
        return result
    except Exception as e:
        print(f"❌ Ошибка при проверке пароля (legacy): {e}")
        return False

def create_user(email: str, password: str = None, name: str = None, phone: str = None) -> Dict[str, Any]:
    """Создать нового пользователя"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли пользователь
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Создаем пользователя
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password) if password else None
        verification_token = secrets.token_urlsafe(32)
        
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, name, phone, verification_token, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
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
    """
    Аутентификация пользователя
    
    Returns:
        Dict с данными пользователя или {"error": "...", "status": 401/500}
        401 - неверные креды (пользователь не найден, неверный пароль, заблокирован)
        500 - ошибка БД/SQL (логируется traceback)
    """
    import os
    
    # DEBUG флаг для логирования
    DEBUG_AUTH = os.getenv('DEBUG_AUTH', 'false').lower() == 'true'
    LOG_FILE = '/tmp/seo_api.out'
    
    def debug_log(msg: str):
        """Логирование в файл и stdout"""
        if DEBUG_AUTH:
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"{msg}\n")
            except Exception:
                pass
        print(msg, flush=True)
    
    conn = None
    try:
        # Нормализация email (НЕ теряем password!)
        email = email.strip().lower() if email else ""
        # password остается как есть - НЕ хешируем до проверки!
        
        debug_log(f"[AUTH] email={email} pw_len={len(password) if password else 0}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # PostgreSQL запрос с %s плейсхолдером
        query = """
            SELECT id, email, password_hash, name, phone, is_active, is_verified
            FROM users WHERE email = %s
        """
        params = (email,)
        
        # Логируем SQL для отладки
        try:
            if hasattr(cursor, 'mogrify'):
                sql = cursor.mogrify(query, params).decode('utf-8')
                debug_log(f"🔍 [SQL] authenticate_user: {sql}")
        except Exception as e:
            debug_log(f"⚠️ [SQL] Не удалось вывести SQL: {e}")
        
        cursor.execute(query, params)
        user = cursor.fetchone()
        
        if not user:
            debug_log(f"[AUTH] Пользователь не найден: {email}")
            return {"error": "Пользователь не найден", "status": 401}
        
        # Извлекаем данные из RealDictCursor (PostgreSQL)
        user_id = user.get('id') if isinstance(user, dict) else user[0]
        user_email = user.get('email') if isinstance(user, dict) else user[1]
        password_hash = user.get('password_hash') if isinstance(user, dict) else user[2]
        user_name = user.get('name') if isinstance(user, dict) else user[3]
        user_phone = user.get('phone') if isinstance(user, dict) else user[4]
        is_active = user.get('is_active') if isinstance(user, dict) else user[5]
        is_verified = user.get('is_verified') if isinstance(user, dict) else user[6]
        
        if not is_active:
            debug_log(f"[AUTH] Аккаунт заблокирован: {email}")
            return {"error": "Аккаунт заблокирован", "status": 401}
        
        if not password_hash:
            debug_log(f"[AUTH] У пользователя нет пароля: {email}")
            return {"error": "NEED_PASSWORD", "message": "Необходимо установить пароль", "status": 401}
        
        # Определяем префикс хэша
        hash_prefix = password_hash[:20] if password_hash else 'None'
        debug_log(f"[AUTH] hash_prefix={hash_prefix}...")
        
        # Проверка пароля: если scrypt: -> ТОЛЬКО werkzeug, иначе legacy
        password_valid = False
        used_legacy = False
        
        if password_hash.startswith('scrypt:'):
            # Новый формат (werkzeug) - проверяем ТОЛЬКО через werkzeug
            debug_log("[AUTH] path=werkzeug")
            try:
                password_valid = check_password_hash(password_hash, password)
                debug_log(f"[AUTH] werkzeug.check_password_hash result: {password_valid}")
            except Exception as e:
                debug_log(f"❌ [AUTH] Ошибка werkzeug.check_password_hash: {e}")
                password_valid = False
        else:
            # Старый формат (legacy) - используем fallback
            debug_log("[AUTH] path=legacy")
            try:
                password_valid = verify_password_legacy(password, password_hash)
                used_legacy = password_valid
                debug_log(f"[AUTH] legacy verify_password result: {password_valid}")
            except Exception as e:
                debug_log(f"❌ [AUTH] Ошибка legacy verify_password: {e}")
                password_valid = False
        
        if not password_valid:
            debug_log(f"[AUTH] Неверный пароль для: {email}")
            return {"error": "Неверный пароль", "status": 401}
        
        # Migration-on-login: если использовали legacy и пароль верный -> перехешируем
        if used_legacy and password_valid:
            debug_log("[AUTH] Migration-on-login: перехешируем пароль в werkzeug формат")
            try:
                new_hash = generate_password_hash(password)
                cursor.execute("""
                    UPDATE users 
                    SET password_hash = %s, updated_at = %s
                    WHERE id = %s
                """, (new_hash, datetime.now().isoformat(), user_id))
                conn.commit()
                debug_log("[AUTH] ✅ Пароль перехеширован в werkzeug формат")
            except Exception as e:
                debug_log(f"⚠️ [AUTH] Ошибка при перехешировании пароля: {e}")
                conn.rollback()
                # Не прерываем авторизацию, если перехеширование не удалось
        
        debug_log(f"[AUTH] ✅ Успешная авторизация: {email}")
        return {
            "id": user_id,
            "email": user_email,
            "name": user_name,
            "phone": user_phone,
            "is_verified": is_verified
        }
        
    except Exception as e:
        # Ошибка БД/SQL - возвращаем 500 и логируем traceback
        import traceback
        error_traceback = traceback.format_exc()
        debug_log(f"❌ [AUTH] Ошибка при авторизации: {e}")
        debug_log(f"❌ [AUTH] Traceback:\n{error_traceback}")
        
        if conn:
            try:
                conn.rollback()
                debug_log("✅ [AUTH] Rollback выполнен")
            except Exception as rollback_error:
                debug_log(f"⚠️ [AUTH] Ошибка при rollback: {rollback_error}")
        
        return {"error": f"Ошибка сервера: {str(e)}", "status": 500}
    finally:
        if conn:
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
            INSERT INTO usersessions (id, user_id, token, expires_at, ip_address, user_agent, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (session_id, user_id, token, expires_at.isoformat(), ip_address, user_agent, datetime.now().isoformat()))
        
        conn.commit()
        return token
        
    except Exception as e:
        return None
    finally:
        conn.close()

def verify_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Проверить сессию пользователя (PostgreSQL-only)
    
    Returns:
        Dict с ключами: user_id, expires_at, email, name, phone, is_active, is_superadmin
        или None если сессия недействительна
    """
    import traceback
    
    LOG_FILE = '/tmp/seo_api.out'
    
    def log_error(msg: str, tb: str = "") -> None:
        """Логирование ошибок verify_session в файл и stdout"""
        try:
            with open(LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.now().isoformat()} [verify_session] {msg}\n")
                if tb:
                    f.write(f"{tb}\n")
        except Exception:
            # Не ломаем основной поток из‑за ошибок логирования
            pass
        print(msg, flush=True)
        if tb:
            print(tb, flush=True)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # PostgreSQL запрос с %s плейсхолдерами и lowercase таблицами
        cursor.execute("""
            SELECT s.user_id, s.expires_at, u.email, u.name, u.phone, u.is_active, u.is_superadmin
            FROM usersessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = %s AND s.expires_at > %s
        """, (token, datetime.now().isoformat()))
        
        session = cursor.fetchone()
        if not session:
            return None
        
        # RealDictCursor всегда возвращает dict-like объект (PostgreSQL)
        # Преобразуем в обычный dict для гарантии
        if isinstance(session, dict):
            session_dict = dict(session)
        else:
            # Fallback: если по какой-то причине не dict, создаем из ключей
            if hasattr(session, 'keys'):
                session_dict = {key: session[key] for key in session.keys()}
            else:
                # На всякий случай обрабатываем tuple/list с известным порядком колонок
                # (user_id, expires_at, email, name, phone, is_active, is_superadmin)
                try:
                    values = list(session)
                    session_dict = {
                        "user_id": values[0] if len(values) > 0 else None,
                        "expires_at": values[1] if len(values) > 1 else None,
                        "email": values[2] if len(values) > 2 else None,
                        "name": values[3] if len(values) > 3 else None,
                        "phone": values[4] if len(values) > 4 else None,
                        "is_active": values[5] if len(values) > 5 else None,
                        "is_superadmin": values[6] if len(values) > 6 else None,
                    }
                except Exception:
                    session_dict = {}
        
        # Возвращаем всегда dict с нужными ключами
        return {
            "user_id": session_dict.get('user_id'),
            "expires_at": session_dict.get('expires_at'),
            "email": session_dict.get('email'),
            "name": session_dict.get('name'),
            "phone": session_dict.get('phone'),
            "is_active": bool(session_dict.get('is_active')) if session_dict.get('is_active') is not None else True,
            "is_superadmin": bool(session_dict.get('is_superadmin')) if session_dict.get('is_superadmin') is not None else False
        }
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        log_error(f"❌ Ошибка проверки сессии: {e}", error_traceback)
        return None
    finally:
        conn.close()

def logout_session(token: str) -> bool:
    """Выйти из сессии"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM usersessions WHERE token = %s", (token,))
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
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cursor.fetchone():
            return {"error": "Пользователь не найден"}
        
        # Хешируем пароль
        password_hash = hash_password(password)
        
        # Обновляем пароль
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s, updated_at = %s
            WHERE id = %s
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
            FROM users WHERE id = %s
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
                update_fields.append(f"{field} = %s")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(update_fields)}, updated_at = %s WHERE id = %s"
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
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user or not verify_password(old_password, user['password_hash']):
            return {"error": "Неверный текущий пароль"}
        
        # Устанавливаем новый пароль
        new_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s", 
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
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            return {"error": "Пользователь с таким email уже существует"}
        
        # Проверяем, есть ли уже приглашение
        cursor.execute("SELECT id FROM invites WHERE email = %s AND status = 'pending'", (email,))
        if cursor.fetchone():
            return {"error": "Приглашение уже отправлено"}
        
        invite_id = str(uuid.uuid4())
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(days=7)
        
        cursor.execute("""
            INSERT INTO invites (id, email, invited_by, token, expires_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
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
            FROM invites 
            WHERE token = %s AND status = 'pending' AND expires_at > %s
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
        cursor.execute("UPDATE invites SET status = 'accepted' WHERE id = %s", (invite['id'],))
        conn.commit()
        
        return result
        
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()
