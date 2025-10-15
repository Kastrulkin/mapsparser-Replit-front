import os
import json
import base64
from typing import Dict, Any
from gigachat_analyzer import GigaChatAnalyzer

class CardAnalyzer:
    def __init__(self):
        self.giga_chat = GigaChatAnalyzer()
        
    def analyze_card_screenshot(self, image_path: str) -> Dict[str, Any]:
        """
        Анализирует скриншот карточки Яндекс.Карт через GigaChat API
        """
        try:
            # Читаем промпт из файла
            prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'cards-analysis-prompt.txt')
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            
            # Конвертируем изображение в base64
            with open(image_path, 'rb') as image_file:
                image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Отправляем запрос в GigaChat
            response = self.giga_chat.analyze_with_image(prompt, image_base64)
            
            # Парсим JSON ответ
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, возвращаем базовую структуру
                return {
                    "completeness_score": 50,
                    "business_name": "Не удалось определить",
                    "category": "Неизвестно",
                    "analysis": {
                        "photos": {"count": 0, "quality": "низкое", "recommendations": []},
                        "description": {"exists": False, "length": 0, "seo_optimized": False, "recommendations": []},
                        "contacts": {"phone": False, "website": False, "social_media": False, "recommendations": []},
                        "schedule": {"complete": False, "recommendations": []},
                        "services": {"listed": False, "count": 0, "recommendations": []}
                    },
                    "priority_actions": ["Проверьте качество изображения"],
                    "overall_recommendations": "Не удалось проанализировать карточку. Попробуйте загрузить более четкое изображение."
                }
                
        except Exception as e:
            print(f"Ошибка анализа карточки: {e}")
            return {
                "completeness_score": 0,
                "business_name": "Ошибка анализа",
                "category": "Ошибка",
                "analysis": {
                    "photos": {"count": 0, "quality": "низкое", "recommendations": []},
                    "description": {"exists": False, "length": 0, "seo_optimized": False, "recommendations": []},
                    "contacts": {"phone": False, "website": False, "social_media": False, "recommendations": []},
                    "schedule": {"complete": False, "recommendations": []},
                    "services": {"listed": False, "count": 0, "recommendations": []}
                },
                "priority_actions": ["Ошибка при анализе"],
                "overall_recommendations": f"Произошла ошибка при анализе: {str(e)}"
            }
