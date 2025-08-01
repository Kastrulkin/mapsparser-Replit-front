# Конфигурация моделей Hugging Face для ИИ-анализа

# Доступные модели для анализа
AVAILABLE_MODELS = {
    "ainize/bart-base-cnn": {
        "name": "ainize/bart-base-cnn",
        "description": "Рабочая модель для генерации текста",
        "max_length": 1024,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9,
        "repetition_penalty": 1.1
    },
    "gpt2": {
        "name": "gpt2",
        "description": "Базовая модель для генерации текста",
        "max_length": 200,
        "temperature": 0.8,
        "do_sample": True,
        "top_p": 0.9,
        "repetition_penalty": 1.1
    },
    "facebook/bart-base": {
        "name": "facebook/bart-base",
        "description": "Модель для понимания текста",
        "max_length": 1024,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    }
}

# Промпты для разных типов анализа
PROMPTS = {
    "seo_analysis": """Анализ SEO для Яндекс.Карт. Данные: {text}

Дай 5 рекомендаций:
1) Название: убрать ключевые слова
2) Услуги: добавить геолокацию  
3) Контакты: полный адрес
4) Контент: больше фото
5) Активность: регулярные посты

Не советуй Google Pay/Apple Pay - они не работают в России.""",
    "rating_analysis": "Анализ рейтинга и отзывов. Данные: {text}. Оцени качество и дай 2-3 совета по улучшению.",
    "general_analysis": "Общий анализ бизнеса. Данные: {text}. Дай 3-4 рекомендации по развитию."
}

# Текущая активная модель
CURRENT_MODEL = "ainize/bart-base-cnn"

def get_model_config(model_name=None):
    """Получить конфигурацию модели"""
    if model_name is None:
        model_name = CURRENT_MODEL
    
    return AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["ainize/bart-base-cnn"])

def get_prompt(prompt_type="seo_analysis", text=""):
    """Получить промпт для анализа"""
    return PROMPTS.get(prompt_type, PROMPTS["seo_analysis"]).format(text=text)
