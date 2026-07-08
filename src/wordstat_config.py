import os
from typing import Optional

class WordstatConfig:
    """Конфигурация для API Яндекс.Вордстат"""

    @staticmethod
    def _int_env(name: str, default: int) -> int:
        raw = (os.getenv(name, "") or "").strip()
        if not raw:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    
    def __init__(self):
        self.client_id = (os.getenv('YANDEX_WORDSTAT_CLIENT_ID') or '').strip()
        self.client_secret = (os.getenv('YANDEX_WORDSTAT_CLIENT_SECRET') or '').strip()
        self.oauth_token = (os.getenv('YANDEX_WORDSTAT_OAUTH_TOKEN') or '').strip()
        self.api_key = (
            os.getenv('YANDEX_WORDSTAT_API_KEY')
            or os.getenv('YANDEX_AI_API_KEY')
            or ''
        ).strip()
        self.folder_id = (
            os.getenv('YANDEX_WORDSTAT_FOLDER_ID')
            or os.getenv('YANDEX_FOLDER_ID')
            or ''
        ).strip()
        self.update_interval = self._int_env('WORDSTAT_UPDATE_INTERVAL', 604800)  # 7 дней
        self.default_region = self._int_env('WORDSTAT_DEFAULT_REGION', 225)  # Россия
        
    def is_configured(self) -> bool:
        """Проверка, настроен ли API"""
        return self.is_cloud_configured() or self.is_oauth_configured()

    def is_cloud_configured(self) -> bool:
        """Проверка настроек актуального Yandex Cloud Search API."""
        return bool(self.api_key and self.folder_id)

    def is_oauth_configured(self) -> bool:
        """Проверка legacy OAuth-настроек старого Wordstat API."""
        return bool(self.client_id and self.client_secret and self.oauth_token)

    def auth_mode(self) -> str:
        """Возвращает режим API, который будет использоваться клиентом."""
        if self.is_cloud_configured():
            return "cloud"
        if self.is_oauth_configured():
            return "oauth"
        return "missing"
    
    def get_auth_url(self) -> str:
        """Получение URL для авторизации"""
        if not self.client_id:
            raise ValueError("YANDEX_WORDSTAT_CLIENT_ID is not configured")
        return f"https://oauth.yandex.ru/authorize?response_type=code&client_id={self.client_id}"
    
    def get_region_name(self, region_id: int) -> str:
        """Получение названия региона по ID"""
        regions = {
            225: "Россия",
            213: "Москва", 
            2: "Санкт-Петербург",
            54: "Новосибирск",
            66: "Екатеринбург",
            16: "Казань",
            1: "Московская область"
        }
        return regions.get(region_id, f"Регион {region_id}")

# Глобальный экземпляр конфигурации
config = WordstatConfig()
