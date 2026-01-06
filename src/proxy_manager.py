"""
Модуль управления прокси-серверами для ротации IP.

Работает без прокси, если их нет в БД (возвращает None).
Когда прокси будут добавлены через админ-панель, автоматически начнет их использовать.
"""
from typing import Optional, Dict, Any

from safe_db_utils import get_db_connection


class ProxyManager:
    """Управление прокси-серверами."""
    
    def __init__(self):
        # Храним последний выданный прокси (может пригодиться для логирования/отладки)
        self.current_proxy: Optional[Dict[str, Any]] = None
    
    def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Получает следующий рабочий прокси для использования.
        Использует round-robin с приоритетом на неиспользуемые.
        
        Если прокси нет в БД, возвращает None (работа без прокси).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Получаем рабочие прокси, отсортированные по последнему использованию
            cursor.execute("""
                SELECT id, proxy_type, host, port, username, password
                FROM ProxyServers
                WHERE is_active = 1 AND is_working = 1
                ORDER BY 
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    RANDOM()
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                # Нет доступных прокси - работаем без прокси
                return None
            
            proxy_id, proxy_type, host, port, username, password = row
            
            # Формируем URL прокси
            if username and password:
                proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{proxy_type}://{host}:{port}"
            
            # Обновляем last_used_at
            cursor.execute("""
                UPDATE ProxyServers 
                SET last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
            
            proxy_dict = {
                "server": proxy_url,
                "id": proxy_id,
                "type": proxy_type,
                "host": host,
                "port": port
            }
            
            self.current_proxy = proxy_dict
            print(f"✅ Используем прокси: {host}:{port} (ID: {proxy_id})")
            
            return proxy_dict
            
        finally:
            cursor.close()
            conn.close()
    
    def mark_proxy_success(self, proxy_id: str):
        """Отмечает прокси как успешно использованный"""
        if not proxy_id:
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE ProxyServers 
                SET success_count = success_count + 1,
                    is_working = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def mark_proxy_failure(self, proxy_id: str, reason: str = None):
        """Отмечает прокси как неработающий"""
        if not proxy_id:
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE ProxyServers 
                SET failure_count = failure_count + 1,
                    is_working = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
            
            print(f"⚠️ Прокси {proxy_id} помечен как неработающий: {reason}")
        finally:
            cursor.close()
            conn.close()
    
    def check_proxy(self, proxy_dict: Dict[str, Any]) -> bool:
        """
        Проверяет работоспособность прокси.
        Делает тестовый запрос к Яндекс.Картам.
        """
        if not proxy_dict:
            return False
        
        try:
            import requests
            
            test_url = "https://yandex.ru/maps"
            proxies = {
                "http": proxy_dict["server"],
                "https": proxy_dict["server"]
            }
            
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            return False
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки прокси {proxy_dict.get('id')}: {e}")
            return False
    
    def get_proxy_for_playwright(self, proxy_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Преобразует прокси в формат для Playwright.
        
        Returns:
            {
                "server": "http://host:port",
                "username": "user",  # опционально
                "password": "pass"   # опционально
            }
        """
        if not proxy_dict:
            return None
        
        playwright_proxy = {
            "server": f"{proxy_dict['type']}://{proxy_dict['host']}:{proxy_dict['port']}"
        }
        
        # Извлекаем username/password из server URL если есть
        server_url = proxy_dict["server"]
        if "@" in server_url:
            # Формат: http://user:pass@host:port
            parts = server_url.split("@")
            if len(parts) == 2:
                auth_part = parts[0].split("://")[1]
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                    playwright_proxy["username"] = username
                    playwright_proxy["password"] = password
        
        return playwright_proxy

