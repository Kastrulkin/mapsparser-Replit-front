#!/usr/bin/env python3
"""
Менеджер базы данных для управления всеми 4 таблицами
"""
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional


try:
    from src.query_adapter import QueryAdapter
except ImportError:
    from query_adapter import QueryAdapter
import os

class DBCursorWrapper:
    """Wrapper around database cursor to intercept and adapt queries"""
    def __init__(self, cursor, db_type='sqlite'):
        self.cursor = cursor
        self.db_type = db_type
        
    def execute(self, query, params=()):
        if self.db_type == 'postgres':
            try:
                query = QueryAdapter.adapt_query(query, params)
                params = QueryAdapter.adapt_params(params)
            except Exception as e:
                import logging
                logging.getLogger('db_adapter').error(f"Adapter Error: {e}")
                raise
        return self.cursor.execute(query, params)
        
    def executemany(self, query, params_list):
        if self.db_type == 'postgres':
            # executemany is trickier. We adapt the query once.
            if params_list:
                first_params = params_list[0]
                query = QueryAdapter.adapt_query(query, first_params)
                # Then adapt all params
                params_list = [QueryAdapter.adapt_params(p) for p in params_list]
        return self.cursor.executemany(query, params_list)
        
    def fetchone(self):
        return self.cursor.fetchone()
        
    def fetchall(self):
        return self.cursor.fetchall()
        
    def __getattr__(self, name):
        return getattr(self.cursor, name)

class DBConnectionWrapper:
    """Wrapper around database connection"""
    def __init__(self, conn):
        self.conn = conn
        self.db_type = os.getenv('DB_TYPE', 'sqlite')
        
    def cursor(self):
        return DBCursorWrapper(self.conn.cursor(), self.db_type)
        
    def commit(self):
        return self.conn.commit()
        
    def rollback(self):
        return self.conn.rollback()
        
    def close(self):
        return self.conn.close()
        
    def __getattr__(self, name):
        return getattr(self.conn, name)

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    conn = _get_db_connection()
    return DBConnectionWrapper(conn)

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.conn = get_db_connection()
        self._closed = False
    
    def close(self):
        """Закрыть соединение"""
        if self.conn and not self._closed:
            try:
                # Коммитим все незакоммиченные изменения
                self.conn.commit()
            except:
                pass
            try:
                self.conn.close()
            except:
                pass
            self._closed = True
    
    def __enter__(self):
        """Контекстный менеджер: вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.close()
        return False
    
    # ===== USERS (Пользователи) =====
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified, is_superadmin
            FROM Users 
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить пользователя по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Получить пользователя по email"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_user(self, email: str, password_hash: str, name: str = None, phone: str = None) -> str:
        """Создать пользователя"""
        user_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO Users (id, email, password_hash, name, phone, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, email, password_hash, name, phone, datetime.now().isoformat()))
        self.conn.commit()
        return user_id
    
    # УДАЛЕНО: authenticate_user - используйте auth_system.authenticate_user вместо этого
    # Метод был удален для унификации хеширования паролей (PBKDF2 вместо SHA256)
    
    def create_session(self, user_id: str) -> str:
        """Создать сессию для пользователя"""
        session_token = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO Sessions (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (session_token, user_id, datetime.now().isoformat(), 
              (datetime.now() + timedelta(days=30)).isoformat()))
        self.conn.commit()
        return session_token
    
    def verify_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверить сессию и получить данные пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.*, s.created_at as session_created_at
            FROM Users u
            JOIN Sessions s ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > ?
        """, (token, datetime.now().isoformat()))
        
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def delete_session(self, token: str) -> bool:
        """Удалить сессию"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM Sessions WHERE token = ?", (token,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """Обновить пользователя"""
        cursor = self.conn.cursor()
        allowed_fields = ['name', 'phone', 'telegram_id', 'is_active', 'is_verified']
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.extend([datetime.now().isoformat(), user_id])
        query = f"UPDATE Users SET {', '.join(update_fields)}, updated_at = ? WHERE id = ?"
        
        cursor.execute(query, values)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_user(self, user_id: str) -> bool:
        """Удалить пользователя (каскадное удаление)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM Users WHERE id = ?", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== INVITES (Приглашения) =====
    
    def get_all_invites(self) -> List[Dict[str, Any]]:
        """Получить все приглашения"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT i.*, u.email as invited_by_email, u.name as invited_by_name
            FROM Invites i
            JOIN Users u ON i.invited_by = u.id
            ORDER BY i.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_invite_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Получить приглашение по токену"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Invites WHERE token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_invite(self, email: str, invited_by: str, expires_days: int = 7) -> str:
        """Создать приглашение"""
        invite_id = str(uuid.uuid4())
        token = str(uuid.uuid4()).replace('-', '')
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO Invites (id, email, invited_by, token, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (invite_id, email, invited_by, token, expires_at.isoformat(), datetime.now().isoformat()))
        self.conn.commit()
        return token
    
    def update_invite_status(self, invite_id: str, status: str) -> bool:
        """Обновить статус приглашения"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE Invites SET status = ? WHERE id = ?", (status, invite_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_invite(self, invite_id: str) -> bool:
        """Удалить приглашение"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM Invites WHERE id = ?", (invite_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== PARSEQUEUE (Очередь запросов) =====
    
    def get_all_queue_items(self) -> List[Dict[str, Any]]:
        """Получить все элементы очереди"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT q.*, u.email as user_email, u.name as user_name
            FROM ParseQueue q
            JOIN Users u ON q.user_id = u.id
            ORDER BY q.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_queue_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Получить очередь пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ParseQueue 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_to_queue(self, url: str, user_id: str) -> str:
        """Добавить в очередь"""
        queue_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO ParseQueue (id, url, user_id, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        """, (queue_id, url, user_id, datetime.now().isoformat()))
        self.conn.commit()
        return queue_id
    
    def update_queue_status(self, queue_id: str, status: str) -> bool:
        """Обновить статус элемента очереди"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", (status, queue_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_queue_item(self, queue_id: str) -> bool:
        """Удалить элемент очереди"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM ParseQueue WHERE id = ?", (queue_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_pending_queue_items(self) -> List[Dict[str, Any]]:
        """Получить ожидающие элементы очереди"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM ParseQueue 
            WHERE status = 'pending' 
            ORDER BY created_at ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== CARDS (Готовые отчёты) =====
    
    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Получить все карточки"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, u.email as user_email, u.name as user_name
            FROM Cards c
            JOIN Users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_cards_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Получить карточки пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM Cards 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_card_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Получить карточку по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Cards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_card(self, user_id: str, url: str, **kwargs) -> str:
        """Создать карточку"""
        card_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        
        # Подготавливаем данные
        fields = ['url', 'title', 'address', 'phone', 'site', 'rating', 'reviews_count', 
                 'categories', 'overview', 'products', 'news', 'photos', 'features_full', 
                 'competitors', 'hours', 'hours_full', 'report_path', 'seo_score', 
                 'ai_analysis', 'recommendations']
        
        values = [card_id, user_id]
        field_names = ['id', 'user_id']
        
        for field in fields:
            if field in kwargs:
                values.append(kwargs[field])
                field_names.append(field)
        
        values.append(datetime.now().isoformat())
        field_names.append('created_at')
        
        placeholders = ', '.join(['?' for _ in values])
        field_list = ', '.join(field_names)
        
        cursor.execute(f"INSERT INTO Cards ({field_list}) VALUES ({placeholders})", values)
        self.conn.commit()
        return card_id
    
    def update_card(self, card_id: str, **kwargs) -> bool:
        """Обновить карточку"""
        cursor = self.conn.cursor()
        allowed_fields = ['title', 'address', 'phone', 'site', 'rating', 'reviews_count',
                         'categories', 'overview', 'products', 'news', 'photos', 
                         'features_full', 'competitors', 'hours', 'hours_full', 
                         'report_path', 'seo_score', 'ai_analysis', 'recommendations']
        
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.append(card_id)
        query = f"UPDATE Cards SET {', '.join(update_fields)} WHERE id = ?"
        
        cursor.execute(query, values)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_card(self, card_id: str) -> bool:
        """Удалить карточку"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM Cards WHERE id = ?", (card_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== СТАТИСТИКА =====
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Количество пользователей
        cursor.execute("SELECT COUNT(*) as count FROM Users")
        stats['users_count'] = cursor.fetchone()['count']
        
        # Количество активных пользователей
        cursor.execute("SELECT COUNT(*) as count FROM Users WHERE is_active = 1")
        stats['active_users_count'] = cursor.fetchone()['count']
        
        # Количество приглашений
        cursor.execute("SELECT COUNT(*) as count FROM Invites")
        stats['invites_count'] = cursor.fetchone()['count']
        
        # Количество ожидающих приглашений
        cursor.execute("SELECT COUNT(*) as count FROM Invites WHERE status = 'pending'")
        stats['pending_invites_count'] = cursor.fetchone()['count']
        
        # Количество элементов в очереди
        cursor.execute("SELECT COUNT(*) as count FROM ParseQueue")
        stats['queue_items_count'] = cursor.fetchone()['count']
        
        # Количество ожидающих в очереди
        cursor.execute("SELECT COUNT(*) as count FROM ParseQueue WHERE status = 'pending'")
        stats['pending_queue_count'] = cursor.fetchone()['count']
        
        # Количество готовых отчётов
        cursor.execute("SELECT COUNT(*) as count FROM Cards")
        stats['cards_count'] = cursor.fetchone()['count']
        
        # Количество отчётов с файлами
        cursor.execute("SELECT COUNT(*) as count FROM Cards WHERE report_path IS NOT NULL")
        stats['completed_reports_count'] = cursor.fetchone()['count']
        
        return stats
    
    # ===== SUPERADMIN METHODS =====
    
    def is_superadmin(self, user_id: str) -> bool:
        """Проверить, является ли пользователь суперадмином"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_superadmin FROM Users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False

        # Безопасная обработка sqlite3.Row или tuple
        try:
            if hasattr(row, "keys"):
                # sqlite3.Row
                if "is_superadmin" in row.keys():
                    return bool(row["is_superadmin"])
                # Если по какой‑то причине колонки нет — считаем, что не суперадмин
                return False
            else:
                # tuple/list — берём первый столбец
                return bool(row[0]) if len(row) > 0 else False
        except Exception as e:
            print(f"❌ Ошибка проверки is_superadmin: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_superadmin(self, user_id: str, is_superadmin: bool = True):
        """Установить статус суперадмина для пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE Users 
            SET is_superadmin = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (is_superadmin, user_id))
        self.conn.commit()
    
    # ===== BUSINESSES =====
    
    def create_business(self, name: str, description: str = None, industry: str = None, owner_id: str = None, 
                       business_type: str = None, address: str = None, working_hours: str = None,
                       phone: str = None, email: str = None, website: str = None, yandex_url: str = None,
                       city: str = None, country: str = 'US', moderation_status: str = 'pending') -> str:
        """Создать новый бизнес"""
        if not owner_id:
            raise ValueError("owner_id обязателен для создания бизнеса")
        
        business_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        try:
            # Проверяем, есть ли новые поля в таблице
            cursor.execute("PRAGMA table_info(Businesses)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Формируем список полей и значений динамически
            base_fields = ['id', 'name', 'description', 'industry', 'business_type', 'address', 'working_hours', 
                          'phone', 'email', 'website', 'owner_id', 'yandex_url']
            base_values = [business_id, name, description, industry, business_type, address, working_hours, 
                          phone, email, website, owner_id, yandex_url]
            
            # Добавляем новые поля, если они есть в таблице
            if 'city' in columns:
                base_fields.append('city')
                base_values.append(city)
            if 'country' in columns:
                base_fields.append('country')
                base_values.append(country)
            if 'moderation_status' in columns:
                base_fields.append('moderation_status')
                base_values.append(moderation_status)
            
            fields_str = ', '.join(base_fields)
            placeholders = ', '.join(['?' for _ in base_fields])
            
            cursor.execute(f"""
                INSERT INTO Businesses ({fields_str})
                VALUES ({placeholders})
            """, base_values)
            # НЕ коммитим здесь - вызывающий код должен сделать commit
            return business_id
        except Exception as e:
            # Откатываем при ошибке
            self.conn.rollback()
            raise
    
    def get_all_businesses(self) -> List[Dict[str, Any]]:
        """Получить все бизнесы (только для суперадмина) - только активные"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.*, u.email as owner_email, u.name as owner_name
            FROM Businesses b
            LEFT JOIN Users u ON b.owner_id = u.id
            WHERE b.is_active = 1 OR b.is_active IS NULL
            ORDER BY b.created_at DESC
        """)
        rows = cursor.fetchall()
        # Преобразуем sqlite3.Row в словари
        result = []
        for row in rows:
            if hasattr(row, 'keys'):
                # Это sqlite3.Row
                result.append({key: row[key] for key in row.keys()})
            else:
                # Это tuple - преобразуем в dict по описанию колонок
                columns = [desc[0] for desc in cursor.description]
                result.append(dict(zip(columns, row)))
        return result
    
    def get_businesses_by_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить бизнесы конкретного владельца (только прямые, без сетей)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE owner_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (owner_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_businesses_by_network_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить бизнесы владельца сети: свои личные + бизнесы из сетей - только активные"""
        cursor = self.conn.cursor()
        
        # Получаем бизнесы, которые напрямую принадлежат пользователю
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE owner_id = ? AND (is_active = 1 OR is_active IS NULL)
            ORDER BY created_at DESC
        """, (owner_id,))
        direct_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Получаем бизнесы из сетей, которыми владеет пользователь
        cursor.execute("""
            SELECT b.* 
            FROM Businesses b
            INNER JOIN Networks n ON b.network_id = n.id
            WHERE n.owner_id = ? AND (b.is_active = 1 OR b.is_active IS NULL)
            ORDER BY b.created_at DESC
        """, (owner_id,))
        network_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Объединяем и убираем дубликаты
        all_businesses = {}
        for business in direct_businesses + network_businesses:
            all_businesses[business['id']] = business
        
        return list(all_businesses.values())
    
    def is_network_owner(self, user_id: str) -> bool:
        """Проверить, является ли пользователь владельцем хотя бы одной сети"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM Networks WHERE owner_id = ?
        """, (user_id,))
        count = cursor.fetchone()[0]
        return count > 0
    
    def create_network(self, name: str, owner_id: str, description: str = None) -> str:
        """Создать новую сеть"""
        network_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO Networks (id, name, owner_id, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (network_id, name, owner_id, description, datetime.now().isoformat(), datetime.now().isoformat()))
        self.conn.commit()
        return network_id
    
    def get_user_networks(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить все сети пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM Networks 
            WHERE owner_id = ? 
            ORDER BY created_at DESC
        """, (owner_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_business_to_network(self, business_id: str, network_id: str) -> bool:
        """Добавить бизнес в сеть"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE Businesses 
            SET network_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (network_id, business_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_business_from_network(self, business_id: str) -> bool:
        """Удалить бизнес из сети"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE Businesses 
            SET network_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (business_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_businesses_by_network(self, network_id: str) -> List[Dict[str, Any]]:
        """Получить все бизнесы (точки) сети - включая заблокированные"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE network_id = ?
            ORDER BY created_at DESC
        """, (network_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_users_with_businesses(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей с их бизнесами и сетями (для админской страницы)
        
        Оптимизировано: вместо N+1 запросов используется один запрос с JOIN и группировка в Python
        """
        cursor = self.conn.cursor()
        
        # Получаем всех пользователей одним запросом
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified, is_superadmin
            FROM Users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        # Получаем все прямые бизнесы одним запросом (не в сети)
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE network_id IS NULL
            ORDER BY owner_id, created_at DESC
        """)
        all_direct_businesses = cursor.fetchall()
        
        # Получаем все сети одним запросом
        cursor.execute("""
            SELECT * FROM Networks 
            ORDER BY owner_id, created_at DESC
        """)
        all_networks = cursor.fetchall()
        
        # Получаем все бизнесы в сетях одним запросом
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE network_id IS NOT NULL
            ORDER BY network_id, created_at DESC
        """)
        all_network_businesses = cursor.fetchall()
        
        # Группируем бизнесы по owner_id
        businesses_by_owner = {}
        for business_row in all_direct_businesses:
            business = dict(business_row)
            owner_id = business.get('owner_id')
            if owner_id:
                if owner_id not in businesses_by_owner:
                    businesses_by_owner[owner_id] = []
                businesses_by_owner[owner_id].append(business)
        
        # Группируем сети по owner_id
        networks_by_owner = {}
        for network_row in all_networks:
            network = dict(network_row)
            owner_id = network.get('owner_id')
            if owner_id:
                if owner_id not in networks_by_owner:
                    networks_by_owner[owner_id] = []
                networks_by_owner[owner_id].append(network)
        
        # Группируем бизнесы в сетях по network_id
        businesses_by_network = {}
        for business_row in all_network_businesses:
            business = dict(business_row)
            network_id = business.get('network_id')
            if network_id:
                if network_id not in businesses_by_network:
                    businesses_by_network[network_id] = []
                businesses_by_network[network_id].append(business)
        
        # Формируем результат
        result = []
        for user_row in users:
            user_id = user_row['id'] if hasattr(user_row, 'keys') else user_row[0]
            
            # Преобразуем пользователя в словарь
            if hasattr(user_row, 'keys'):
                user_dict = {key: user_row[key] for key in user_row.keys()}
            else:
                columns = [desc[0] for desc in cursor.description]
                user_dict = dict(zip(columns, user_row))
            
            # Получаем прямые бизнесы пользователя
            direct_businesses = businesses_by_owner.get(user_id, [])
            # Логируем для отладки
            blocked_count = sum(1 for b in direct_businesses if b.get('is_active') == 0)
            if blocked_count > 0:
                print(f"🔍 DEBUG: Пользователь {user_id} имеет {blocked_count} заблокированных бизнесов из {len(direct_businesses)} всего")
            
            # Получаем сети пользователя
            networks = networks_by_owner.get(user_id, [])
            
            # Для каждой сети получаем её точки (бизнесы)
            networks_with_businesses = []
            for network in networks:
                network_id = network['id']
                network_businesses = businesses_by_network.get(network_id, [])
                networks_with_businesses.append({
                    **network,
                    'businesses': network_businesses
                })
            
            result.append({
                **user_dict,
                'direct_businesses': direct_businesses,
                'networks': networks_with_businesses
            })
        
        # Находим бизнесы без владельцев (orphan businesses) - включая заблокированные
        cursor.execute("""
            SELECT b.*
            FROM Businesses b
            LEFT JOIN Users u ON b.owner_id = u.id
            WHERE b.network_id IS NULL
            AND b.owner_id IS NOT NULL
            AND u.id IS NULL
            ORDER BY b.created_at DESC
        """)
        orphan_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Добавляем специальную запись для бизнесов без владельцев
        if orphan_businesses:
            result.append({
                'id': None,
                'email': '[Без владельца]',
                'name': '[Бизнесы без владельца]',
                'phone': None,
                'created_at': None,
                'is_active': None,
                'is_verified': None,
                'is_superadmin': False,
                'direct_businesses': orphan_businesses,
                'networks': []
            })
            
        # Находим сети без владельцев (orphan networks)
        cursor.execute("""
            SELECT n.*
            FROM Networks n
            LEFT JOIN Users u ON n.owner_id = u.id
            WHERE u.id IS NULL
            ORDER BY n.created_at DESC
        """)
        orphan_networks = [dict(row) for row in cursor.fetchall()]
        
        if orphan_networks:
            # Для каждой сиротливой сети собираем её бизнесы
            networks_with_businesses = []
            for network in orphan_networks:
                network_id = network['id']
                # Ищем бизнесы этой сети (используем уже полученные all_network_businesses)
                # Это эффективнее чем делать новый запрос
                network_businesses = businesses_by_network.get(network_id, [])
                networks_with_businesses.append({
                    **network,
                    'businesses': network_businesses
                })
            
            # Если уже есть группа "Без владельца", добавляем туда
            found_orphan_group = False
            for user_group in result:
                if user_group['id'] is None and user_group['email'] == '[Без владельца]':
                    user_group['networks'].extend(networks_with_businesses)
                    found_orphan_group = True
                    break
            
            # Если группы нет, создаем её
            if not found_orphan_group:
                result.append({
                    'id': None,
                    'email': '[Без владельца]',
                    'name': '[Сети без владельца]',
                    'phone': None,
                    'created_at': None,
                    'is_active': None,
                    'is_verified': None,
                    'is_superadmin': False,
                    'direct_businesses': [],
                    'networks': networks_with_businesses
                })
        
        return result
    
    def get_business_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Получить бизнес по ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, name, description, industry, business_type, address, working_hours, 
                   phone, email, website, owner_id, network_id, is_active, 
                   created_at, updated_at
            FROM Businesses WHERE id = ?
        """, (business_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    def update_business(self, business_id: str, name: str = None, description: str = None, industry: str = None):
        """Обновить информацию о бизнесе"""
        cursor = self.conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if industry is not None:
            updates.append("industry = ?")
            params.append(industry)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(business_id)
            cursor.execute(f"""
                UPDATE Businesses 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            self.conn.commit()
    
    def delete_business(self, business_id: str):
        """Удалить бизнес навсегда (реальное удаление)"""
        cursor = self.conn.cursor()
        
        # Проверяем, существует ли бизнес
        cursor.execute("SELECT id, name FROM Businesses WHERE id = ?", (business_id,))
        business = cursor.fetchone()
        if not business:
            print(f"❌ Бизнес с ID {business_id} не найден")
            return False
        
        print(f"🔍 Удаление бизнеса: ID={business_id}, name={business[1] if business else 'N/A'}")
        
        # Удаляем связанные данные
        cursor.execute("DELETE FROM UserServices WHERE business_id = ?", (business_id,))
        deleted_services = cursor.rowcount
        cursor.execute("DELETE FROM FinancialTransactions WHERE business_id = ?", (business_id,))
        deleted_transactions = cursor.rowcount
        cursor.execute("DELETE FROM BusinessMapLinks WHERE business_id = ?", (business_id,))
        deleted_links = cursor.rowcount
        cursor.execute("DELETE FROM MapParseResults WHERE business_id = ?", (business_id,))
        deleted_results = cursor.rowcount
        cursor.execute("DELETE FROM ParseQueue WHERE business_id = ?", (business_id,))
        deleted_queue = cursor.rowcount
        cursor.execute("DELETE FROM TelegramBindTokens WHERE business_id = ?", (business_id,))
        deleted_tokens = cursor.rowcount
        
        print(f"🔍 Удалено связанных данных: services={deleted_services}, transactions={deleted_transactions}, links={deleted_links}, results={deleted_results}, queue={deleted_queue}, tokens={deleted_tokens}")
        
        # Удаляем сам бизнес
        cursor.execute("DELETE FROM Businesses WHERE id = ?", (business_id,))
        deleted_count = cursor.rowcount
        self.conn.commit()
        
        print(f"🔍 Удалено бизнесов: {deleted_count}")
        
        return deleted_count > 0
    
    def block_business(self, business_id: str, is_blocked: bool = True):
        """Заблокировать/разблокировать бизнес"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (0 if is_blocked else 1, business_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_services_by_business(self, business_id: str):
        """Получить услуги конкретного бизнеса"""
        cursor = self.conn.cursor()
        
        # Проверяем, есть ли поле business_id в таблице UserServices
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'business_id' in columns:
            # Используем business_id для фильтрации
            cursor.execute("""
                SELECT id, name, description, category, keywords, price, created_at, updated_at
                FROM UserServices 
                WHERE business_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (business_id,))
        else:
            # Fallback: получаем owner_id бизнеса и выбираем услуги по user_id
            cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
            row = cursor.fetchone()
            owner_id = row[0] if row else None
            if not owner_id:
                return []
            cursor.execute("""
                SELECT id, name, description, category, keywords, price, created_at, updated_at
                FROM UserServices 
                WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (owner_id,))
        
        columns = [description[0] for description in cursor.description]
        services = []
        for row in cursor.fetchall():
            service = dict(zip(columns, row))
            services.append(service)
        
        return services
    
    def get_financial_data_by_business(self, business_id: str):
        """Получить финансовые данные конкретного бизнеса"""
        cursor = self.conn.cursor()
        
        # Создаем таблицу FinancialMetrics если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FinancialMetrics (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                period TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()
        
        # Получаем транзакции
        cursor.execute("""
            SELECT id, amount, description, transaction_type, date, created_at
            FROM FinancialTransactions 
            WHERE business_id = ? 
            ORDER BY date DESC
        """, (business_id,))
        
        columns = [description[0] for description in cursor.description]
        transactions = []
        for row in cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        # Получаем метрики
        cursor.execute("""
            SELECT id, metric_name, metric_value, period, created_at
            FROM FinancialMetrics 
            WHERE business_id = ? 
            ORDER BY created_at DESC
        """, (business_id,))
        
        columns = [description[0] for description in cursor.description]
        metrics = []
        for row in cursor.fetchall():
            metric = dict(zip(columns, row))
            metrics.append(metric)
        
        return {
            "transactions": transactions,
            "metrics": metrics
        }
    
    def get_reports_by_business(self, business_id: str):
        """Получить отчеты конкретного бизнеса"""
        cursor = self.conn.cursor()
        
        # Создаем таблицу Cards если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Cards (
                id TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                report_path TEXT,
                user_id TEXT,
                business_id TEXT,
                seo_score INTEGER,
                ai_analysis TEXT,
                recommendations TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)
        self.conn.commit()
        
        cursor.execute("""
            SELECT id, title, report_path, seo_score, ai_analysis, created_at, updated_at
            FROM Cards 
            WHERE business_id = ? 
            ORDER BY created_at DESC
        """, (business_id,))
        
        columns = [description[0] for description in cursor.description]
        reports = []
        for row in cursor.fetchall():
            report = dict(zip(columns, row))
            reports.append(report)
        
        return reports

    # ===== PROSPECTING LEADS =====

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """Получить все лиды"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM ProspectingLeads ORDER BY created_at DESC")
        return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

    def save_lead(self, lead_data: Dict[str, Any]) -> str:
        """Сохранить лид (если уже есть google_id - обновить)"""
        cursor = self.conn.cursor()
        
        # Проверяем дубликат по google_id
        google_id = lead_data.get('google_id')
        if google_id:
            cursor.execute("SELECT id FROM ProspectingLeads WHERE google_id = ?", (google_id,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        lead_id = str(uuid.uuid4())
        fields = ['id', 'name', 'address', 'phone', 'website', 'rating', 'reviews_count', 
                  'source_url', 'google_id', 'category', 'location', 'status']
        
        values = [lead_id]
        for f in fields[1:]:
            values.append(lead_data.get(f))
            
        placeholders = ', '.join(['?' for _ in values])
        
        cursor.execute(f"""
            INSERT INTO ProspectingLeads ({', '.join(fields)}, created_at, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, values)
        
        self.conn.commit()
        return lead_id

    def update_lead_status(self, lead_id: str, status: str) -> bool:
        """Обновить статус лида"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE ProspectingLeads 
            SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (status, lead_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_lead(self, lead_id: str) -> bool:
        """Удалить лид"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM ProspectingLeads WHERE id = ?", (lead_id,))
        self.conn.commit()
        return cursor.rowcount > 0

def main():
    """Основная функция для тестирования"""
    db = DatabaseManager()
    
    try:
        print("📊 Статистика системы:")
        stats = db.get_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n👥 Пользователи:")
        users = db.get_all_users()
        for user in users[:5]:  # Показываем первых 5
            print(f"  {user['email']} - {user['name'] or 'Без имени'}")
        
        print("\n📋 Очередь:")
        queue = db.get_all_queue_items()
        for item in queue[:5]:  # Показываем первых 5
            print(f"  {item['url']} - {item['status']}")
        
        print("\n📄 Отчёты:")
        cards = db.get_all_cards()
        for card in cards[:5]:  # Показываем первых 5
            print(f"  {card['title'] or 'Без названия'} - {card['seo_score'] or 'Нет оценки'}")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
