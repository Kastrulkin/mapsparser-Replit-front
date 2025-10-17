import os
from typing import Optional

class WordstatConfig:
    """Конфигурация для API Яндекс.Вордстат"""
    
    def __init__(self):
        self.client_id = os.getenv('YANDEX_WORDSTAT_CLIENT_ID', '623b9605a95c4a57965cc4ccff1a7130')
        self.client_secret = os.getenv('YANDEX_WORDSTAT_CLIENT_SECRET', '8ec666a7306b49e78c895bfbbba63ad4')
        self.oauth_token = os.getenv('YANDEX_WORDSTAT_OAUTH_TOKEN')
        self.update_interval = int(os.getenv('WORDSTAT_UPDATE_INTERVAL', '604800'))  # 7 дней
        self.default_region = int(os.getenv('WORDSTAT_DEFAULT_REGION', '225'))  # Россия
        
    def is_configured(self) -> bool:
        """Проверка, настроен ли API"""
        return bool(self.oauth_token)
    
    def get_auth_url(self) -> str:
        """Получение URL для авторизации"""
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
