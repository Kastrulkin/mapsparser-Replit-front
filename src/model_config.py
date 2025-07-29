# Конфигурация моделей Hugging Face для ИИ-анализа

# Доступные модели для анализа
AVAILABLE_MODELS = {
    "gpt2": {
        "name": "gpt2",
        "description": "Базовая модель для генерации текста",
        "max_length": 300,
        "temperature": 0.8,
        "do_sample": True,
        "top_p": 0.9
    },
    "microsoft/DialoGPT-medium": {
        "name": "microsoft/DialoGPT-medium", 
        "description": "Модель для диалогов и рекомендаций",
        "max_length": 200,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.8
    },
    "t5-base": {
        "name": "t5-base",
        "description": "Модель для задач перевода и анализа",
        "max_length": 250,
        "temperature": 0.6,
        "do_sample": True,
        "top_p": 0.85
    },
    "facebook/bart-base": {
        "name": "facebook/bart-base",
        "description": "Модель для суммирования и анализа",
        "max_length": 200,
        "temperature": 0.7,
        "do_sample": True,
        "top_p": 0.9
    }
}

# Промпты для разных типов анализа
PROMPTS = {
    "seo_analysis": "Анализ бизнеса для SEO оптимизации. Данные: {text}. Дай краткие рекомендации по улучшению позиций в поиске.",
    "rating_analysis": "Анализ рейтинга и отзывов. Данные: {text}. Оцени качество и дай советы по улучшению.",
    "general_analysis": "Общий анализ бизнеса. Данные: {text}. Дай рекомендации по развитию."
}

# Текущая активная модель
CURRENT_MODEL = "gpt2"

def get_model_config(model_name=None):
    """Получить конфигурацию модели"""
    if model_name is None:
        model_name = CURRENT_MODEL
    
    return AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["gpt2"])

def get_prompt(prompt_type="seo_analysis", text=""):
    """Получить промпт для анализа"""
    return PROMPTS.get(prompt_type, PROMPTS["seo_analysis"]).format(text=text) 