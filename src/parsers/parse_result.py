"""
ParseResult - результат парсинга с метаданными о качестве данных
Используется для Source Priority Pipeline (без merge по имени)
"""
from typing import Dict, Any


class ParseResult:
    """Результат парсинга с метаданными"""
    
    def __init__(self, data: Dict[str, Any], source: str, quality_score: int):
        """
        Args:
            data: Данные парсинга
            source: Источник данных ('yandex_api_v2', 'html_fallback', 'meta_tags')
            quality_score: Оценка качества (0-100)
        """
        self.data = data
        self.source = source
        self.quality_score = quality_score
    
    def merge(self, other: 'ParseResult') -> 'ParseResult':
        """
        Merge двух результатов, выбирая лучшие данные.
        
        Правило: дополняем только пустые поля, не перезаписываем существующие.
        Quality score = минимум из двух (консервативный подход).
        
        Args:
            other: Другой ParseResult для merge
            
        Returns:
            Новый ParseResult с объединенными данными
        """
        merged = self.data.copy()
        merged_quality = min(self.quality_score, other.quality_score)
        
        # Правило: дополняем только пустые поля, не перезаписываем
        for key, value in other.data.items():
            if not merged.get(key) and value:
                merged[key] = value
        
        # Объединяем источники
        merged_source = f"{self.source}+{other.source}"
        
        return ParseResult(merged, merged_source, merged_quality)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразовать в словарь с метаданными.
        
        Returns:
            Словарь с данными и метаданными
        """
        result = self.data.copy()
        result['_parse_metadata'] = {
            'source': self.source,
            'quality_score': self.quality_score
        }
        return result
