#!/usr/bin/env python3
"""
Конфигурация GigaChat API
"""
import os

class GigaChatConfig:
    """Конфигурация для GigaChat API"""
    
    # Доступные модели GigaChat
    AVAILABLE_MODELS = {
        "GigaChat-2-Pro": {
            "name": "GigaChat-2-Pro",
            "description": "Самая мощная модель для сложных задач",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["анализ изображений", "сложный анализ текста"]
        },
        "GigaChat-3": {
            "name": "GigaChat-3", 
            "description": "Новая модель с улучшенными возможностями",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["анализ изображений", "общий анализ"]
        },
        "GigaChat-2.5": {
            "name": "GigaChat-2.5",
            "description": "Сбалансированная модель для большинства задач",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["анализ текста", "общие задачи"]
        }
    }
    
    def __init__(self):
        # Модель по умолчанию (можно изменить через переменную окружения)
        self.model = os.getenv('GIGACHAT_MODEL', 'GigaChat-2-Pro')
        
        # Параметры генерации
        self.temperature = float(os.getenv('GIGACHAT_TEMPERATURE', '0.1'))
        self.max_tokens = int(os.getenv('GIGACHAT_MAX_TOKENS', '6000'))
        
        # Таймауты
        self.request_timeout = int(os.getenv('GIGACHAT_TIMEOUT', '60'))
        self.retry_attempts = int(os.getenv('GIGACHAT_RETRY_ATTEMPTS', '3'))
        
        # Валидация модели
        if self.model not in self.AVAILABLE_MODELS:
            print(f"⚠️ Предупреждение: Модель '{self.model}' не найдена в списке доступных. Используется GigaChat-2-Pro")
            self.model = 'GigaChat-2-Pro'
    
    def get_model_info(self):
        """Возвращает информацию о текущей модели"""
        return self.AVAILABLE_MODELS.get(self.model, self.AVAILABLE_MODELS['GigaChat-2-Pro'])
    
    def get_model_config(self):
        """Возвращает конфигурацию для API запроса"""
        model_info = self.get_model_info()
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": min(self.max_tokens, model_info['max_tokens']),
            "timeout": self.request_timeout,
            "retry_attempts": self.retry_attempts
        }
    
    def list_available_models(self):
        """Возвращает список доступных моделей"""
        return list(self.AVAILABLE_MODELS.keys())
    
    def set_model(self, model_name: str):
        """Устанавливает модель"""
        if model_name in self.AVAILABLE_MODELS:
            self.model = model_name
            return True
        return False

# Глобальный экземпляр конфигурации
config = GigaChatConfig()

def get_gigachat_config():
    """Возвращает текущую конфигурацию GigaChat"""
    return config

def set_gigachat_model(model_name: str):
    """Устанавливает модель GigaChat"""
    return config.set_model(model_name)

def get_available_models():
    """Возвращает список доступных моделей"""
    return config.list_available_models()

if __name__ == "__main__":
    # Тестирование конфигурации
    print("🔧 Конфигурация GigaChat:")
    print(f"Текущая модель: {config.model}")
    print(f"Температура: {config.temperature}")
    print(f"Максимум токенов: {config.max_tokens}")
    print(f"Таймаут: {config.request_timeout}с")
    print(f"Попытки повтора: {config.retry_attempts}")
    
    print("\n📋 Доступные модели:")
    for model_name, info in config.AVAILABLE_MODELS.items():
        status = "✅" if model_name == config.model else "⚪"
        print(f"{status} {model_name}: {info['description']}")
    
    print(f"\n🎯 Текущая конфигурация: {config.get_model_config()}")
