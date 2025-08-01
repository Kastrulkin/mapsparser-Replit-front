# Конфигурация моделей Hugging Face для ИИ-анализа

# Доступные модели для анализа (бесплатные)
AVAILABLE_MODELS = {
    "t5-base": {
        "name": "t5-base",
        "description": "Бесплатная модель для анализа карточек",
        "max_length": 512,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    },
    "facebook/bart-base": {
        "name": "facebook/bart-base",
        "description": "Бесплатная модель для рекомендаций",
        "max_length": 1024,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    },
    "microsoft/DialoGPT-medium": {
        "name": "microsoft/DialoGPT-medium",
        "description": "Бесплатная модель для диалогов",
        "max_length": 1000,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    }
}

# Промпты для разных типов анализа (оптимизированы для бесплатных моделей)
PROMPTS = {
    "seo_analysis": "Проанализируй карточку бизнеса для SEO. Данные: {text}. Дай 3-5 конкретных рекомендаций по улучшению позиций в Яндекс.Картах. Формат: 1) Название: [рекомендация] 2) Услуги: [рекомендация] 3) Контакты: [рекомендация] 4) Контент: [рекомендация] 5) Активность: [рекомендация]",
    "rating_analysis": "Анализ рейтинга и отзывов. Данные: {text}. Оцени качество и дай 2-3 совета по улучшению.",
    "general_analysis": "Общий анализ бизнеса. Данные: {text}. Дай 3-4 рекомендации по развитию."
}

# Текущая активная модель
CURRENT_MODEL = "facebook/bart-base"

def get_model_config(model_name=None):
    """Получить конфигурацию модели"""
    if model_name is None:
        model_name = CURRENT_MODEL
    
    return AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["facebook/bart-base"])

def get_prompt(prompt_type="seo_analysis", text=""):
    """Получить промпт для анализа"""
    return PROMPTS.get(prompt_type, PROMPTS["seo_analysis"]).format(text=text) 