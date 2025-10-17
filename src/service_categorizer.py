#!/usr/bin/env python3
"""
Система умной категоризации услуг для BeautyBot
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

@dataclass
class ServiceCategory:
    """Категория услуги"""
    name: str
    keywords: List[str]
    wordstat_queries: List[str]
    priority: int = 1

class ServiceCategorizer:
    """Умная категоризация услуг по ключевым словам и запросам Вордстата"""
    
    def __init__(self):
        self.categories = self._init_categories()
        self.wordstat_queries = self._load_wordstat_queries()
    
    def _init_categories(self) -> Dict[str, ServiceCategory]:
        """Инициализация категорий услуг"""
        return {
            'hair': ServiceCategory(
                name='Стрижки и укладки',
                keywords=[
                    'стрижка', 'укладка', 'прическа', 'волосы', 'парикмахер',
                    'боб', 'каре', 'пикси', 'каскад', 'лесенка', 'асимметрия',
                    'челка', 'бангс', 'стрижка женская', 'стрижка мужская',
                    'детская стрижка', 'креативная стрижка'
                ],
                wordstat_queries=[
                    'стрижка женская', 'стрижка мужская', 'укладка волос',
                    'парикмахерская', 'стрижка в салоне', 'детская стрижка'
                ],
                priority=1
            ),
            'coloring': ServiceCategory(
                name='Окрашивание',
                keywords=[
                    'окрашивание', 'покраска', 'мелирование', 'колорирование',
                    'тонирование', 'блондирование', 'осветление', 'балаяж',
                    'шатуш', 'омбре', 'айртач', 'бразильское окрашивание',
                    'скрытое окрашивание', 'контуринг', 'рефлекс'
                ],
                wordstat_queries=[
                    'окрашивание волос', 'мелирование', 'колорирование',
                    'тонирование', 'блондирование', 'балаяж', 'шатуш'
                ],
                priority=1
            ),
            'nails': ServiceCategory(
                name='Маникюр и педикюр',
                keywords=[
                    'маникюр', 'педикюр', 'ногти', 'гель-лак', 'шеллак',
                    'наращивание', 'френч', 'френч-маникюр', 'дизайн ногтей',
                    'парафинотерапия', 'обрезной маникюр', 'европейский маникюр',
                    'аппаратный маникюр', 'покрытие гель-лак'
                ],
                wordstat_queries=[
                    'маникюр', 'педикюр', 'гель-лак', 'наращивание ногтей',
                    'дизайн ногтей', 'френч-маникюр'
                ],
                priority=2
            ),
            'eyebrows': ServiceCategory(
                name='Брови и ресницы',
                keywords=[
                    'брови', 'ресницы', 'коррекция бровей', 'окрашивание бровей',
                    'ламинирование бровей', 'наращивание ресниц', 'окрашивание ресниц',
                    'наращивание бровей', 'микроблейдинг', 'татуаж бровей',
                    'ламинирование ресниц', 'завивка ресниц'
                ],
                wordstat_queries=[
                    'брови', 'ресницы', 'коррекция бровей', 'наращивание ресниц',
                    'ламинирование бровей', 'микроблейдинг'
                ],
                priority=2
            ),
            'spa': ServiceCategory(
                name='Массаж и СПА',
                keywords=[
                    'массаж', 'спа', 'обертывание', 'пилинг', 'скрабирование',
                    'антицеллюлитный массаж', 'релакс массаж', 'классический массаж',
                    'лимфодренажный массаж', 'тайский массаж', 'ароматерапия',
                    'солевое обертывание', 'шоколадное обертывание'
                ],
                wordstat_queries=[
                    'массаж', 'спа процедуры', 'обертывание', 'антицеллюлитный массаж',
                    'релакс массаж', 'ароматерапия'
                ],
                priority=3
            ),
            'barber': ServiceCategory(
                name='Барбершоп',
                keywords=[
                    'барбершоп', 'мужская стрижка', 'борода', 'усы', 'бритье',
                    'стрижка бороды', 'коррекция бороды', 'укладка бороды',
                    'мужской маникюр', 'мужской педикюр', 'стрижка под машинку',
                    'креативная мужская стрижка'
                ],
                wordstat_queries=[
                    'барбершоп', 'мужская стрижка', 'стрижка бороды', 'мужской маникюр',
                    'стрижка под машинку'
                ],
                priority=2
            ),
            'other': ServiceCategory(
                name='Другие услуги',
                keywords=[],
                wordstat_queries=[],
                priority=10
            )
        }
    
    def _load_wordstat_queries(self) -> Dict[str, List[str]]:
        """Загрузка популярных запросов из файла"""
        try:
            with open('../prompts/popular_queries_with_clicks.txt', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Парсим запросы по категориям
            queries_by_category = {}
            current_category = None
            
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('## '):
                    current_category = line[3:].strip()
                    queries_by_category[current_category] = []
                elif line.startswith('- ') and current_category:
                    # Извлекаем запрос и количество показов
                    query = line[2:].split(' (')[0].strip()
                    queries_by_category[current_category].append(query)
            
            return queries_by_category
            
        except FileNotFoundError:
            print("⚠️  Файл с популярными запросами не найден")
            return {}
        except Exception as e:
            print(f"⚠️  Ошибка загрузки запросов: {e}")
            return {}
    
    def categorize_service(self, service_name: str, service_description: str = "") -> Tuple[str, float, List[str]]:
        """
        Категоризация услуги
        
        Args:
            service_name: Название услуги
            service_description: Описание услуги (опционально)
            
        Returns:
            Tuple[category_key, confidence, matched_keywords]
        """
        text = f"{service_name} {service_description}".lower()
        
        # Счетчики совпадений для каждой категории
        category_scores = {}
        matched_keywords = {}
        
        for category_key, category in self.categories.items():
            score = 0
            matched = []
            
            # Проверяем ключевые слова категории
            for keyword in category.keywords:
                if keyword.lower() in text:
                    score += category.priority * 2  # Ключевые слова весят больше
                    matched.append(keyword)
            
            # Проверяем популярные запросы Вордстата
            if category_key in self.wordstat_queries:
                for query in self.wordstat_queries[category_key]:
                    if query.lower() in text:
                        score += category.priority * 1.5
                        matched.append(query)
            
            if score > 0:
                category_scores[category_key] = score
                matched_keywords[category_key] = matched
        
        if not category_scores:
            return 'other', 0.0, []
        
        # Находим категорию с максимальным счетом
        best_category = max(category_scores.items(), key=lambda x: x[1])
        confidence = min(best_category[1] / 10.0, 1.0)  # Нормализуем до 0-1
        
        return best_category[0], confidence, matched_keywords[best_category[0]]
    
    def get_category_info(self, category_key: str) -> Optional[ServiceCategory]:
        """Получение информации о категории"""
        return self.categories.get(category_key)
    
    def get_suggested_queries(self, category_key: str, limit: int = 10) -> List[str]:
        """Получение рекомендуемых запросов для категории"""
        if category_key not in self.wordstat_queries:
            return []
        
        queries = self.wordstat_queries[category_key]
        return queries[:limit]
    
    def analyze_service_text(self, text: str) -> Dict:
        """Анализ текста услуги и предложение улучшений"""
        category, confidence, matched = self.categorize_service(text)
        category_info = self.get_category_info(category)
        suggested_queries = self.get_suggested_queries(category, 5)
        
        return {
            'category': category,
            'category_name': category_info.name if category_info else 'Неизвестно',
            'confidence': confidence,
            'matched_keywords': matched,
            'suggested_queries': suggested_queries,
            'improvements': self._suggest_improvements(text, category, suggested_queries)
        }
    
    def _suggest_improvements(self, text: str, category: str, suggested_queries: List[str]) -> List[str]:
        """Предложения по улучшению текста услуги"""
        improvements = []
        
        # Проверяем наличие популярных запросов в тексте
        text_lower = text.lower()
        missing_queries = []
        
        for query in suggested_queries[:3]:  # Топ-3 запроса
            if query.lower() not in text_lower:
                missing_queries.append(query)
        
        if missing_queries:
            improvements.append(f"Добавьте популярные запросы: {', '.join(missing_queries)}")
        
        # Проверяем длину описания
        if len(text) < 50:
            improvements.append("Увеличьте описание услуги (минимум 50 символов)")
        elif len(text) > 200:
            improvements.append("Сократите описание (рекомендуется до 200 символов)")
        
        # Проверяем наличие ключевых слов
        category_info = self.get_category_info(category)
        if category_info:
            missing_keywords = []
            for keyword in category_info.keywords[:5]:  # Топ-5 ключевых слов
                if keyword.lower() not in text_lower:
                    missing_keywords.append(keyword)
            
            if missing_keywords:
                improvements.append(f"Используйте ключевые слова: {', '.join(missing_keywords[:3])}")
        
        return improvements

# Глобальный экземпляр категоризатора
categorizer = ServiceCategorizer()

# Пример использования
if __name__ == "__main__":
    # Тестируем категоризацию
    test_services = [
        "Стрижка женская с укладкой",
        "Окрашивание волос мелирование",
        "Маникюр гель-лак с дизайном",
        "Коррекция бровей и окрашивание",
        "Антицеллюлитный массаж",
        "Мужская стрижка под машинку"
    ]
    
    print("🧪 Тестирование категоризации услуг:")
    print("=" * 50)
    
    for service in test_services:
        result = categorizer.analyze_service_text(service)
        print(f"\n📝 Услуга: {service}")
        print(f"🏷️  Категория: {result['category_name']} (уверенность: {result['confidence']:.2f})")
        print(f"🔍 Найденные ключевые слова: {', '.join(result['matched_keywords'])}")
        if result['suggested_queries']:
            print(f"💡 Рекомендуемые запросы: {', '.join(result['suggested_queries'])}")
        if result['improvements']:
            print(f"✨ Улучшения: {'; '.join(result['improvements'])}")
