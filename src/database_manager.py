#!/usr/bin/env python3
"""
Менеджер базы данных для управления всеми 4 таблицами
"""
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    from safe_db_utils import get_db_connection as _get_db_connection
    return _get_db_connection()

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
    
    def authenticate_user(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Аутентификация пользователя по email и паролю"""
        import hashlib
        
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            return None
            
        # Проверяем пароль
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if user['password_hash'] != password_hash:
            return None
            
        return dict(user)
    
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
                       phone: str = None, email: str = None, website: str = None, yandex_url: str = None) -> str:
        """Создать новый бизнес"""
        if not owner_id:
            raise ValueError("owner_id обязателен для создания бизнеса")
        
        business_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO Businesses (id, name, description, industry, business_type, address, working_hours, phone, email, website, owner_id, yandex_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (business_id, name, description, industry, business_type, address, working_hours, phone, email, website, owner_id, yandex_url))
            # НЕ коммитим здесь - вызывающий код должен сделать commit
            return business_id
        except Exception as e:
            # Откатываем при ошибке
            self.conn.rollback()
            raise
    
    def get_all_businesses(self) -> List[Dict[str, Any]]:
        """Получить все бизнесы (только для суперадмина)"""
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
        """Получить бизнесы владельца сети: свои личные + бизнесы из сетей"""
        cursor = self.conn.cursor()
        
        # Получаем бизнесы, которые напрямую принадлежат пользователю
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE owner_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (owner_id,))
        direct_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Получаем бизнесы из сетей, которыми владеет пользователь
        cursor.execute("""
            SELECT b.* 
            FROM Businesses b
            INNER JOIN Networks n ON b.network_id = n.id
            WHERE n.owner_id = ? AND b.is_active = 1
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
        """Получить все бизнесы (точки) сети"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM Businesses 
            WHERE network_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """, (network_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_users_with_businesses(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей с их бизнесами и сетями (для админской страницы)"""
        cursor = self.conn.cursor()
        
        # Получаем всех пользователей
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified, is_superadmin
            FROM Users 
            ORDER BY created_at DESC
        """)
        users = cursor.fetchall()
        
        result = []
        for user_row in users:
            user_id = user_row['id'] if hasattr(user_row, 'keys') else user_row[0]
            
            # Преобразуем пользователя в словарь
            if hasattr(user_row, 'keys'):
                user_dict = {key: user_row[key] for key in user_row.keys()}
            else:
                columns = [desc[0] for desc in cursor.description]
                user_dict = dict(zip(columns, user_row))
            
            # Получаем прямые бизнесы пользователя (не в сети)
            cursor.execute("""
                SELECT * FROM Businesses 
                WHERE owner_id = ? AND network_id IS NULL AND (is_active = 1 OR is_active IS NULL)
                ORDER BY created_at DESC
            """, (user_id,))
            direct_businesses = [dict(row) for row in cursor.fetchall()]
            
            # Получаем сети пользователя
            cursor.execute("""
                SELECT * FROM Networks 
                WHERE owner_id = ? 
                ORDER BY created_at DESC
            """, (user_id,))
            networks = [dict(row) for row in cursor.fetchall()]
            
            # Для каждой сети получаем её точки (бизнесы)
            networks_with_businesses = []
            for network in networks:
                network_id = network['id']
                network_businesses = self.get_businesses_by_network(network_id)
                networks_with_businesses.append({
                    **network,
                    'businesses': network_businesses
                })
            
            result.append({
                **user_dict,
                'direct_businesses': direct_businesses,
                'networks': networks_with_businesses
            })
        
        return result
    
    def get_business_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Получить бизнес по ID"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, name, description, industry, business_type, address, working_hours, 
                   phone, email, website, owner_id, owner_name, owner_email, is_active, 
                   created_at, updated_at
            FROM Businesses WHERE id = ?
        """, (business_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
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
        """Удалить бизнес (мягкое удаление)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE Businesses 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (business_id,))
        self.conn.commit()
    
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
