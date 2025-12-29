#!/usr/bin/env python3
"""
Утилиты для персонализации ChatGPT взаимодействий
"""
from database_manager import DatabaseManager
from datetime import datetime
import json
import uuid

# Исправляем импорт для работы с safe_db_utils
try:
    from safe_db_utils import get_db_connection
except ImportError:
    # Fallback на DatabaseManager
    pass

def get_or_create_session(chatgpt_user_id: str, business_id: str = None) -> dict:
    """
    Получить или создать сессию пользователя ChatGPT
    
    Args:
        chatgpt_user_id: Уникальный ID пользователя в ChatGPT
        business_id: ID бизнеса (опционально)
    
    Returns:
        dict: Данные сессии
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        # Проверяем, существует ли таблица
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='ChatGPTUserSessions'
        """)
        if not cursor.fetchone():
            # Таблица не существует, возвращаем пустую сессию
            return {
                'id': None,
                'chatgpt_user_id': chatgpt_user_id,
                'business_id': business_id,
                'session_started_at': None,
                'last_interaction_at': None,
                'total_interactions': 0,
                'preferred_city': None,
                'preferred_service_types': None,
                'search_history': [],
                'booking_history': [],
                'preferences_json': None
            }
        
        # Ищем существующую сессию
        cursor.execute("""
            SELECT id, chatgpt_user_id, business_id, session_started_at,
                   last_interaction_at, total_interactions, preferred_city,
                   preferred_service_types, search_history, booking_history,
                   preferences_json
            FROM ChatGPTUserSessions
            WHERE chatgpt_user_id = ?
            ORDER BY last_interaction_at DESC
            LIMIT 1
        """, (chatgpt_user_id,))
        
        session = cursor.fetchone()
        
        if session:
            session_id, cgpt_user_id, biz_id, started_at, last_interaction, total, \
            city, service_types, search_hist, booking_hist, prefs_json = session
            
            # Обновляем время последнего взаимодействия
            cursor.execute("""
                UPDATE ChatGPTUserSessions
                SET last_interaction_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (session_id,))
            db.conn.commit()
            
            # Парсим JSON поля
            preferences = {}
            if prefs_json:
                try:
                    preferences = json.loads(prefs_json)
                except:
                    pass
            
            search_history_list = []
            if search_hist:
                try:
                    search_history_list = json.loads(search_hist)
                except:
                    pass
            
            booking_history_list = []
            if booking_hist:
                try:
                    booking_history_list = json.loads(booking_hist)
                except:
                    pass
            
            return {
                'id': session_id,
                'chatgpt_user_id': cgpt_user_id,
                'business_id': biz_id,
                'session_started_at': started_at,
                'last_interaction_at': last_interaction,
                'total_interactions': total,
                'preferred_city': city,
                'preferred_service_types': service_types,
                'search_history': search_history_list,
                'booking_history': booking_history_list,
                'preferences': preferences
            }
        else:
            # Создаем новую сессию
            session_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO ChatGPTUserSessions 
                (id, chatgpt_user_id, business_id, session_started_at, 
                 last_interaction_at, total_interactions)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
            """, (session_id, chatgpt_user_id, business_id))
            db.conn.commit()
            
            return {
                'id': session_id,
                'chatgpt_user_id': chatgpt_user_id,
                'business_id': business_id,
                'session_started_at': datetime.now().isoformat(),
                'last_interaction_at': datetime.now().isoformat(),
                'total_interactions': 0,
                'preferred_city': None,
                'preferred_service_types': None,
                'search_history': [],
                'booking_history': [],
                'preferences': {}
            }
    finally:
        db.close()

def record_search(chatgpt_user_id: str, city: str, service: str, results_count: int):
    """
    Записать поисковый запрос в историю
    
    Args:
        chatgpt_user_id: ID пользователя ChatGPT
        city: Город поиска
        service: Услуга поиска
        results_count: Количество найденных результатов
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        session = get_or_create_session(chatgpt_user_id)
        session_id = session['id']
        
        # Получаем текущую историю поиска
        cursor.execute("""
            SELECT search_history FROM ChatGPTUserSessions WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()
        
        search_history = []
        if row and row[0]:
            try:
                search_history = json.loads(row[0])
            except:
                pass
        
        # Добавляем новый поиск
        search_entry = {
            'city': city,
            'service': service,
            'results_count': results_count,
            'timestamp': datetime.now().isoformat()
        }
        search_history.append(search_entry)
        
        # Ограничиваем историю последними 50 запросами
        if len(search_history) > 50:
            search_history = search_history[-50:]
        
        # Обновляем предпочтения
        preferred_city = city  # Последний использованный город
        preferred_service_types = service  # Последняя использованная услуга
        
        # Обновляем сессию
        cursor.execute("""
            UPDATE ChatGPTUserSessions
            SET search_history = ?,
                preferred_city = ?,
                preferred_service_types = ?,
                total_interactions = total_interactions + 1,
                last_interaction_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(search_history), preferred_city, preferred_service_types, session_id))
        
        db.conn.commit()
    finally:
        db.close()

def record_booking(chatgpt_user_id: str, business_id: str, service_id: str = None, booking_id: str = None):
    """
    Записать бронирование в историю
    
    Args:
        chatgpt_user_id: ID пользователя ChatGPT
        business_id: ID бизнеса
        service_id: ID услуги (опционально)
        booking_id: ID бронирования (опционально)
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        session = get_or_create_session(chatgpt_user_id, business_id)
        session_id = session['id']
        
        # Получаем текущую историю бронирований
        cursor.execute("""
            SELECT booking_history FROM ChatGPTUserSessions WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()
        
        booking_history = []
        if row and row[0]:
            try:
                booking_history = json.loads(row[0])
            except:
                pass
        
        # Добавляем новое бронирование
        booking_entry = {
            'business_id': business_id,
            'service_id': service_id,
            'booking_id': booking_id,
            'timestamp': datetime.now().isoformat()
        }
        booking_history.append(booking_entry)
        
        # Ограничиваем историю последними 20 бронированиями
        if len(booking_history) > 20:
            booking_history = booking_history[-20:]
        
        # Обновляем сессию
        cursor.execute("""
            UPDATE ChatGPTUserSessions
            SET booking_history = ?,
                business_id = ?,
                total_interactions = total_interactions + 1,
                last_interaction_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (json.dumps(booking_history), business_id, session_id))
        
        db.conn.commit()
    finally:
        db.close()

def get_user_preferences(chatgpt_user_id: str) -> dict:
    """
    Получить предпочтения пользователя
    
    Args:
        chatgpt_user_id: ID пользователя ChatGPT
    
    Returns:
        dict: Предпочтения пользователя
    """
    session = get_or_create_session(chatgpt_user_id)
    
    return {
        'preferred_city': session.get('preferred_city'),
        'preferred_service_types': session.get('preferred_service_types'),
        'recent_searches': session.get('search_history', [])[-5:],  # Последние 5 поисков
        'recent_bookings': session.get('booking_history', [])[-5:],  # Последние 5 бронирований
        'total_interactions': session.get('total_interactions', 0)
    }

