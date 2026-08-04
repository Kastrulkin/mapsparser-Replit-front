#!/usr/bin/env python3
"""
Конфигурация GigaChat API
"""
import os


def _env_float(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

class GigaChatConfig:
    """Конфигурация для GigaChat API"""
    
    # Доступные модели GigaChat
    AVAILABLE_MODELS = {
        "GigaChat-2": {
            "name": "GigaChat-2",
            "description": "Быстрая модель для простых задач и первичной проверки",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["простые ответы", "классификация", "первичная корректура"]
        },
        "GigaChat-2-Pro": {
            "name": "GigaChat-2-Pro",
            "description": "Сбалансированная модель для большинства задач",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["ответы на отзывы", "генерация новостей", "AI агенты", "общие задачи"]
        },
        "GigaChat-2-Max": {
            "name": "GigaChat-2-Max",
            "description": "Самая мощная модель для сложных аналитических задач",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["анализ и оптимизация услуг", "сложный анализ", "стратегические задачи"]
        },
        "GigaChat-3-Ultra": {
            "name": "GigaChat-3-Ultra",
            "description": "Резерв для сложных задач и независимой проверки",
            "max_tokens": 4000,
            "supports_images": True,
            "recommended_for": ["сложная проверка", "чувствительный резерв", "большой контекст"]
        },
    }
    
    def __init__(self):
        # Модель по умолчанию (можно изменить через переменную окружения)
        default_model = os.getenv('GIGACHAT_MODEL', 'GigaChat-2-Pro')
        # Маппинг старых названий на новые
        model_mapping = {
            'GigaChat-3': 'GigaChat-2-Pro',
            'GigaChat-2.5': 'GigaChat-2-Pro',
            'GigaChat-Lite': 'GigaChat-2',
            'GigaChat-Pro': 'GigaChat-2-Pro',
            'GigaChat-Max': 'GigaChat-2-Max'
        }
        self.model = model_mapping.get(default_model, default_model)
        
        # Параметры генерации
        self.temperature = _env_float('GIGACHAT_TEMPERATURE', 0.1)
        self.max_tokens = _env_int('GIGACHAT_MAX_TOKENS', 4000)
        
        # Таймауты
        self.request_timeout = _env_int('GIGACHAT_TIMEOUT', 60)
        self.retry_attempts = _env_int('GIGACHAT_RETRY_ATTEMPTS', 3)
        
        # Валидация модели
        if self.model not in self.AVAILABLE_MODELS:
            print(f"⚠️ Предупреждение: Модель '{self.model}' не найдена в списке доступных. Используется GigaChat-2-Pro")
            self.model = 'GigaChat-2-Pro'
    
    def get_model_info(self):
        """Возвращает информацию о текущей модели"""
        return self.AVAILABLE_MODELS.get(self.model, self.AVAILABLE_MODELS['GigaChat-2-Pro'])
    
    def get_model_config(self, task_type: str = None, model_override: str = ""):
        """Возвращает конфигурацию для API запроса
        
        Args:
            task_type: Ключ задачи из единого services.llm registry.
        """
        model_name = str(model_override or "").strip() or self.get_model_for_task(task_type or "")
        
        # Получаем информацию о модели
        model_info = self.AVAILABLE_MODELS.get(model_name, self.AVAILABLE_MODELS['GigaChat-2-Pro'])
        
        return {
            "model": model_info['name'],
            "temperature": self.temperature,
            "max_tokens": min(self.max_tokens, model_info['max_tokens']),
            "timeout": self.request_timeout,
            "retry_attempts": self.retry_attempts
        }
    
    def get_model_for_task(self, task_type: str) -> str:
        """Возвращает название модели для конкретной задачи"""
        try:
            from services.llm.registry import get_task_definition, model_for_definition

            definition = get_task_definition(task_type)
            if definition and definition.primary_provider == "gigachat":
                return model_for_definition(definition)
        except Exception:
            pass
        return self.model
    
    def list_available_models(self):
        """Возвращает список доступных моделей (без дубликатов для обратной совместимости)"""
        # Возвращаем только основные модели
        return ["GigaChat-2", "GigaChat-2-Pro", "GigaChat-2-Max", "GigaChat-3-Ultra"]
    
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
