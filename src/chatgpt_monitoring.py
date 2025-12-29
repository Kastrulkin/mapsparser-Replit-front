#!/usr/bin/env python3
"""
Утилиты для мониторинга и логирования запросов ChatGPT API
"""
from database_manager import DatabaseManager
from datetime import datetime, timedelta
import json
import uuid
import time

def log_request(
    endpoint: str,
    method: str,
    request_params: dict = None,
    response_status: int = None,
    response_time_ms: int = None,
    error_message: str = None,
    chatgpt_user_id: str = None,
    business_id: str = None,
    service_id: str = None,
    booking_id: str = None,
    ip_address: str = None,
    user_agent: str = None
):
    """
    Записать запрос в лог
    
    Args:
        endpoint: Путь endpoint (например, '/api/chatgpt/search')
        method: HTTP метод (GET, POST, etc.)
        request_params: Параметры запроса (словарь)
        response_status: HTTP статус ответа
        response_time_ms: Время ответа в миллисекундах
        error_message: Сообщение об ошибке (если есть)
        chatgpt_user_id: ID пользователя ChatGPT
        business_id: ID бизнеса (если применимо)
        service_id: ID услуги (если применимо)
        booking_id: ID бронирования (если применимо)
        ip_address: IP адрес клиента
        user_agent: User-Agent заголовок
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        request_id = str(uuid.uuid4())
        
        # Сериализуем параметры запроса
        params_json = None
        if request_params:
            try:
                params_json = json.dumps(request_params)
            except:
                params_json = str(request_params)
        
        cursor.execute("""
            INSERT INTO ChatGPTRequests 
            (id, chatgpt_user_id, endpoint, method, request_params,
             response_status, response_time_ms, error_message,
             business_id, service_id, booking_id, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_id,
            chatgpt_user_id,
            endpoint,
            method,
            params_json,
            response_status,
            response_time_ms,
            error_message,
            business_id,
            service_id,
            booking_id,
            ip_address,
            user_agent
        ))
        
        db.conn.commit()
    except Exception as e:
        print(f"⚠️ Ошибка логирования запроса: {e}")
    finally:
        db.close()

def get_statistics(
    start_date: datetime = None,
    end_date: datetime = None,
    business_id: str = None,
    endpoint: str = None
) -> dict:
    """
    Получить статистику запросов
    
    Args:
        start_date: Начальная дата (по умолчанию - последние 30 дней)
        end_date: Конечная дата (по умолчанию - сейчас)
        business_id: Фильтр по бизнесу (опционально)
        endpoint: Фильтр по endpoint (опционально)
    
    Returns:
        dict: Статистика запросов
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        if not start_date:
            start_date = datetime.now() - timedelta(days=30)
        if not end_date:
            end_date = datetime.now()
        
        # Базовый запрос
        query = """
            SELECT 
                COUNT(*) as total_requests,
                COUNT(DISTINCT chatgpt_user_id) as unique_users,
                COUNT(DISTINCT business_id) as unique_businesses,
                AVG(response_time_ms) as avg_response_time,
                SUM(CASE WHEN response_status >= 200 AND response_status < 300 THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN response_status >= 400 THEN 1 ELSE 0 END) as error_count,
                COUNT(CASE WHEN endpoint = '/api/chatgpt/search' THEN 1 END) as search_count,
                COUNT(CASE WHEN endpoint = '/api/chatgpt/book' THEN 1 END) as booking_count,
                COUNT(CASE WHEN endpoint = '/api/chatgpt/salon/{salonId}' THEN 1 END) as salon_details_count
            FROM ChatGPTRequests
            WHERE created_at >= ? AND created_at <= ?
        """
        
        params = [start_date.isoformat(), end_date.isoformat()]
        
        if business_id:
            query += " AND business_id = ?"
            params.append(business_id)
        
        if endpoint:
            query += " AND endpoint = ?"
            params.append(endpoint)
        
        cursor.execute(query, params)
        stats = cursor.fetchone()
        
        if not stats:
            return {
                'total_requests': 0,
                'unique_users': 0,
                'unique_businesses': 0,
                'avg_response_time_ms': 0,
                'success_count': 0,
                'error_count': 0,
                'success_rate': 0,
                'search_count': 0,
                'booking_count': 0,
                'salon_details_count': 0
            }
        
        total, users, businesses, avg_time, success, errors, searches, bookings, details = stats
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        return {
            'total_requests': total,
            'unique_users': users,
            'unique_businesses': businesses,
            'avg_response_time_ms': round(avg_time, 2) if avg_time else 0,
            'success_count': success,
            'error_count': errors,
            'success_rate': round(success_rate, 2),
            'search_count': searches,
            'booking_count': bookings,
            'salon_details_count': details
        }
    finally:
        db.close()

def get_endpoint_statistics(endpoint: str, days: int = 30) -> dict:
    """
    Получить статистику по конкретному endpoint
    
    Args:
        endpoint: Путь endpoint
        days: Количество дней для анализа
    
    Returns:
        dict: Статистика endpoint
    """
    start_date = datetime.now() - timedelta(days=days)
    return get_statistics(start_date=start_date, endpoint=endpoint)

def get_top_businesses(limit: int = 10, days: int = 30) -> list:
    """
    Получить топ бизнесов по количеству запросов
    
    Args:
        limit: Количество бизнесов
        days: Количество дней для анализа
    
    Returns:
        list: Список бизнесов с количеством запросов
    """
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    try:
        start_date = datetime.now() - timedelta(days=days)
        
        cursor.execute("""
            SELECT 
                b.id,
                b.name,
                COUNT(cr.id) as request_count,
                COUNT(DISTINCT cr.chatgpt_user_id) as unique_users,
                COUNT(CASE WHEN cr.endpoint = '/api/chatgpt/book' THEN 1 END) as booking_count
            FROM ChatGPTRequests cr
            JOIN Businesses b ON cr.business_id = b.id
            WHERE cr.created_at >= ? AND cr.business_id IS NOT NULL
            GROUP BY b.id, b.name
            ORDER BY request_count DESC
            LIMIT ?
        """, (start_date.isoformat(), limit))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                'business_id': row[0],
                'business_name': row[1],
                'request_count': row[2],
                'unique_users': row[3],
                'booking_count': row[4]
            })
        
        return results
    finally:
        db.close()


