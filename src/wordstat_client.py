import requests
import json
import time
from typing import List, Dict, Optional
import os
from datetime import datetime, timedelta

WORDSTAT_TEMPORARILY_UNAVAILABLE_MESSAGE = (
    "Яндекс.Вордстат временно недоступен. "
    "Попробуйте обновить SEO-ключи позже."
)

WORDSTAT_LEGACY_TLS_MESSAGE = (
    "Старый API Яндекс.Вордстат сейчас возвращает некорректный TLS-сертификат. "
    "Подключите Yandex Cloud Search API v2 через YANDEX_WORDSTAT_API_KEY и YANDEX_WORDSTAT_FOLDER_ID."
)


class WordstatTemporaryUnavailable(Exception):
    """External Wordstat API is temporarily unavailable or misconfigured upstream."""


class WordstatClient:
    """Клиент для работы с API Яндекс.Вордстат"""
    
    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        api_key: str = "",
        folder_id: str = "",
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.wordstat.yandex.net"
        self.cloud_base_url = "https://searchapi.api.cloud.yandex.net/v2/wordstat"
        self.oauth_url = "https://oauth.yandex.ru"
        self.access_token = None
        self.token_expires_at = None
        self.api_key = (api_key or "").strip()
        self.folder_id = (folder_id or "").strip()

    @classmethod
    def from_config(cls, config):
        return cls(
            client_id=getattr(config, "client_id", ""),
            client_secret=getattr(config, "client_secret", ""),
            api_key=getattr(config, "api_key", ""),
            folder_id=getattr(config, "folder_id", ""),
        )
        
    def get_access_token(self) -> str:
        """Получение OAuth токена для доступа к API"""
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
            
        # Для получения токена нужно пройти OAuth flow
        # Это требует пользовательского взаимодействия
        auth_url = f"{self.oauth_url}/authorize?response_type=code&client_id={self.client_id}"
        print(f"Перейдите по ссылке для авторизации: {auth_url}")
        
        # В реальном приложении здесь должен быть OAuth flow
        # Пока возвращаем None, токен нужно получить вручную
        return None
    
    def set_access_token(self, token: str, expires_in: int = 3600):
        """Установка токена (для ручного ввода)"""
        self.access_token = token
        self.token_expires_at = datetime.now() + timedelta(seconds=expires_in)
    
    def _make_request(self, endpoint: str, payload: Dict = None):
        """Выполнение запроса к API"""
        if self.api_key and self.folder_id:
            return self._make_cloud_request(endpoint, payload)

        if not self.access_token:
            raise Exception("Необходимо получить access token")
            
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json;charset=utf-8'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.post(url, headers=headers, json=(payload or {}), timeout=30)
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Превышена квота. Повторите через {retry_after} секунд")
                return None
                
            if response.status_code == 503:
                print("Сервис временно недоступен")
                return None
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.SSLError as e:
            raise WordstatTemporaryUnavailable(
                f"{WORDSTAT_LEGACY_TLS_MESSAGE} detail={e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise WordstatTemporaryUnavailable(
                f"Яндекс.Вордстат временно недоступен. Попробуйте обновить SEO-ключи позже. detail={e}"
            ) from e

    def _make_cloud_request(self, endpoint: str, payload: Dict = None):
        """Выполнение запроса к актуальному Yandex Cloud Search API v2."""
        headers = {
            'Authorization': f'Api-Key {self.api_key}',
            'Content-Type': 'application/json;charset=utf-8',
        }
        cloud_endpoint = endpoint
        if cloud_endpoint.startswith("v1/"):
            cloud_endpoint = cloud_endpoint[3:]
        if cloud_endpoint.startswith("v2/"):
            cloud_endpoint = cloud_endpoint[3:]
        url = f"{self.cloud_base_url}/{cloud_endpoint}"
        body = dict(payload or {})
        body['folderId'] = self.folder_id

        try:
            response = requests.post(url, headers=headers, json=body, timeout=30)
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Превышена квота. Повторите через {retry_after} секунд")
                return None
            if response.status_code == 503:
                print("Сервис временно недоступен")
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise WordstatTemporaryUnavailable(
                f"Яндекс.Вордстат временно недоступен. Попробуйте обновить SEO-ключи позже. detail={e}"
            ) from e
    
    def get_popular_queries(self, keywords: List[str], region: int = 225) -> Dict:
        """
        Получение популярных запросов
        
        Args:
            keywords: Список ключевых слов для анализа
            region: ID региона (225 - Россия)
        """
        if self.api_key and self.folder_id:
            results = []
            for keyword in keywords[:128]:
                phrase = (keyword or "").strip()
                if not phrase:
                    continue
                payload = {
                    'phrase': phrase,
                    'regions': [str(region)],
                    'devices': ['DEVICE_ALL'],
                    'numPhrases': 50,
                }
                data = self._make_request('topRequests', payload)
                if data:
                    results.append(data)
            return results

        payload = {
            'phrases': keywords[:128],
            'regions': [region],
            'devices': ['all'],
            'numPhrases': 50,
        }
        return self._make_request('v1/topRequests', payload)
    
    def get_similar_queries(self, keyword: str, region: int = 225) -> Dict:
        """
        Получение похожих запросов
        
        Args:
            keyword: Ключевое слово
            region: ID региона
        """
        if self.api_key and self.folder_id:
            payload = {
                'phrase': keyword,
                'regions': [str(region)],
                'devices': ['DEVICE_ALL'],
                'numPhrases': 50,
            }
            return self._make_request('topRequests', payload)

        payload = {
            'phrase': keyword,
            'regions': [region],
            'devices': ['all'],
            'numPhrases': 50,
        }
        return self._make_request('v1/topRequests', payload)
    
    def get_queries_statistics(self, phrases: List[str], region: int = 225) -> Dict:
        """
        Получение статистики по запросам
        
        Args:
            phrases: Список фраз для анализа
            region: ID региона
        """
        # Для статистики используем актуальный метод dynamics по одной фразе.
        results = []
        for phrase in phrases[:20]:
            payload = {
                'phrase': phrase,
                'period': 'monthly',
                'regions': [region],
                'devices': ['all'],
            }
            data = self._make_request('v1/dynamics', payload)
            if data:
                results.append({'phrase': phrase, 'dynamics': data.get('dynamics', [])})
        return {'data': results}

class WordstatDataProcessor:
    """Обработчик данных от API Вордстата"""
    
    @staticmethod
    def format_queries_for_prompt(api_data: Dict) -> str:
        """Форматирование данных API для использования в промпте"""
        if not api_data or 'data' not in api_data:
            return "Данные не получены"
        
        formatted_queries = []
        
        for item in api_data['data']:
            phrase = item.get('phrase', '')
            shows = item.get('shows', 0)
            
            if phrase and shows > 0:
                formatted_queries.append(f"- {phrase} ({shows:,} показов/месяц)")
        
        return "\n".join(formatted_queries)
    
    @staticmethod
    def save_queries_to_file(api_data: Dict, file_path: str):
        """Сохранение запросов в файл"""
        if not api_data or 'data' not in api_data:
            return
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("# Популярные запросы с количеством показов (обновлено автоматически)\n\n")
            
            # Группировка по категориям
            categories = {
                'Стрижки и укладки': [],
                'Окрашивание': [],
                'Маникюр и педикюр': [],
                'Массаж и СПА': [],
                'Брови и ресницы': [],
                'Другие услуги': []
            }
            
            for item in api_data['data']:
                phrase = item.get('phrase', '').lower()
                shows = item.get('shows', 0)
                
                if 'стрижк' in phrase or 'укладк' in phrase:
                    categories['Стрижки и укладки'].append((phrase, shows))
                elif 'окрашиван' in phrase or 'покраск' in phrase or 'мелирован' in phrase:
                    categories['Окрашивание'].append((phrase, shows))
                elif 'маникюр' in phrase or 'педикюр' in phrase or 'ногт' in phrase:
                    categories['Маникюр и педикюр'].append((phrase, shows))
                elif 'массаж' in phrase or 'спа' in phrase or 'обертыван' in phrase:
                    categories['Массаж и СПА'].append((phrase, shows))
                elif 'бров' in phrase or 'ресниц' in phrase:
                    categories['Брови и ресницы'].append((phrase, shows))
                else:
                    categories['Другие услуги'].append((phrase, shows))
            
            # Запись в файл
            for category, queries in categories.items():
                if queries:
                    f.write(f"## {category}:\n")
                    # Сортировка по количеству показов
                    queries.sort(key=lambda x: x[1], reverse=True)
                    for phrase, shows in queries[:50]:  # Топ 50 по категории
                        f.write(f"- {phrase} ({shows:,} показов/месяц)\n")
                    f.write("\n")
            
            f.write(f"\n*Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}*\n")

# Пример использования
if __name__ == "__main__":
    api_key = (
        os.getenv("YANDEX_WORDSTAT_API_KEY")
        or os.getenv("YANDEX_AI_API_KEY")
        or ""
    ).strip()
    folder_id = (
        os.getenv("YANDEX_WORDSTAT_FOLDER_ID")
        or os.getenv("YANDEX_FOLDER_ID")
        or ""
    ).strip()
    client_id = os.getenv("YANDEX_WORDSTAT_CLIENT_ID", "").strip()
    client_secret = os.getenv("YANDEX_WORDSTAT_CLIENT_SECRET", "").strip()
    if not (api_key and folder_id) and not (client_id and client_secret):
        raise SystemExit(
            "Set YANDEX_WORDSTAT_API_KEY and YANDEX_WORDSTAT_FOLDER_ID for Cloud API, "
            "or YANDEX_WORDSTAT_CLIENT_ID and YANDEX_WORDSTAT_CLIENT_SECRET for legacy OAuth."
        )

    # Инициализация клиента
    client = WordstatClient(
        client_id=client_id,
        client_secret=client_secret,
        api_key=api_key,
        folder_id=folder_id,
    )
    
    # Установка токена (получить вручную через OAuth)
    # client.set_access_token("your_oauth_token_here")
    
    print("WordstatClient инициализирован")
    print("Для Cloud API используется YANDEX_WORDSTAT_API_KEY/YANDEX_WORDSTAT_FOLDER_ID")
