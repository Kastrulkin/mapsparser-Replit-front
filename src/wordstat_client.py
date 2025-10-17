import requests
import json
import time
from typing import List, Dict, Optional
import os
from datetime import datetime, timedelta

class WordstatClient:
    """Клиент для работы с API Яндекс.Вордстат"""
    
    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = "https://api.wordstat.yandex.net"
        self.oauth_url = "https://oauth.yandex.ru"
        self.access_token = None
        self.token_expires_at = None
        
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
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Выполнение запроса к API"""
        if not self.access_token:
            raise Exception("Необходимо получить access token")
            
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
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
            print(f"Ошибка запроса к API: {e}")
            return None
    
    def get_popular_queries(self, keywords: List[str], region: int = 225) -> Dict:
        """
        Получение популярных запросов
        
        Args:
            keywords: Список ключевых слов для анализа
            region: ID региона (225 - Россия)
        """
        params = {
            'phrases': keywords,
            'geo': region
        }
        
        return self._make_request('phrases', params)
    
    def get_similar_queries(self, keyword: str, region: int = 225) -> Dict:
        """
        Получение похожих запросов
        
        Args:
            keyword: Ключевое слово
            region: ID региона
        """
        params = {
            'phrase': keyword,
            'geo': region
        }
        
        return self._make_request('phrases', params)
    
    def get_queries_statistics(self, phrases: List[str], region: int = 225) -> Dict:
        """
        Получение статистики по запросам
        
        Args:
            phrases: Список фраз для анализа
            region: ID региона
        """
        params = {
            'phrases': phrases,
            'geo': region
        }
        
        return self._make_request('stat', params)

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
    # Инициализация клиента
    client = WordstatClient(
        client_id="623b9605a95c4a57965cc4ccff1a7130",
        client_secret="8ec666a7306b49e78c895bfbbba63ad4"
    )
    
    # Установка токена (получить вручную через OAuth)
    # client.set_access_token("your_oauth_token_here")
    
    print("WordstatClient инициализирован")
    print("Для работы необходимо получить OAuth токен")
