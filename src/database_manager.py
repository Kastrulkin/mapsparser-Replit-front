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
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.conn = get_db_connection()
    
    def close(self):
        """Закрыть соединение"""
        if self.conn:
            self.conn.close()
    
    # ===== USERS (Пользователи) =====
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified
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
