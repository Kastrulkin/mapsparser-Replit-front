import os
import json
from typing import Dict, Any
from gigachat_analyzer import GigaChatAnalyzer

class SEOOptimizer:
    def __init__(self):
        self.giga_chat = GigaChatAnalyzer()
        
    def optimize_pricelist(self, file_path: str) -> Dict[str, Any]:
        """
        Оптимизирует прайс-лист для SEO через GigaChat API
        """
        try:
            # Читаем промпт из файла
            prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'seo-optimization-prompt.txt')
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            
            # Читаем содержимое файла (упрощённая версия - только текст)
            file_content = self._extract_text_from_file(file_path)
            
            # Отправляем запрос в GigaChat
            response = self.giga_chat.analyze_text(prompt + "\n\nСодержимое прайс-листа:\n" + file_content)
            
            # Парсим JSON ответ
            try:
                result = json.loads(response)
                return result
            except json.JSONDecodeError:
                # Если не удалось распарсить JSON, возвращаем базовую структуру
                return {
                    "services": [],
                    "general_recommendations": [
                        "Не удалось обработать прайс-лист. Попробуйте загрузить файл в другом формате.",
                        "Убедитесь, что файл содержит читаемый текст."
                    ]
                }
                
        except Exception as e:
            print(f"Ошибка оптимизации прайс-листа: {e}")
            return {
                "services": [],
                "general_recommendations": [
                    f"Произошла ошибка при обработке файла: {str(e)}",
                    "Попробуйте загрузить файл в другом формате."
                ]
            }
    
    def _extract_text_from_file(self, file_path: str) -> str:
        """
        Извлекает текст из файла (упрощённая версия)
        """
        try:
            # Для простоты, читаем как текстовый файл
            # В реальной реализации нужно использовать библиотеки для парсинга PDF, DOC, XLS
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except:
            # Если не удалось прочитать как текст, возвращаем заглушку
            return "Содержимое файла не удалось извлечь. Пожалуйста, убедитесь, что файл содержит читаемый текст."
