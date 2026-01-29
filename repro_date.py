
import re
from datetime import datetime

def _parse_russian_date(date_str: str) -> datetime | None:
    """Парсинг русских дат типа '27 января 2026' или '10 октября'"""
    try:
        months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4, 'мая': 5, 'июня': 6,
            'июля': 7, 'августа': 8, 'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4, 'май': 5, 'июн': 6,
            'июл': 7, 'авг': 8, 'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        parts = date_str.lower().split()
        if len(parts) >= 2:
            day_str = parts[0]
            month_str = parts[1]
            year_str = parts[2] if len(parts) > 2 else str(datetime.now().year)
            
            # Очистка от лишних символов
            day_str = re.sub(r'\D', '', day_str)
            year_str = re.sub(r'\D', '', year_str)
            # Очищаем месяц от знаков препинания (запятые, точки)
            month_str = re.sub(r'[^\w\s]', '', month_str, flags=re.UNICODE) 
            
            if not day_str or not month_str:
                return None
                
            day = int(day_str)
            month = months.get(month_str)
            year = int(year_str)
            
            if month:
                return datetime(year, month, day)
                
    except Exception as e:
        print(f"Error: {e}")
        pass
    return None

test_cases = [
    "5 сентября",
    "5 сентября 2024",
    "5 сентября,",
    "5 сентября, 12:00",
    "10 октября",
    "1 мая"
]

for tc in test_cases:
    print(f"'{tc}' -> {_parse_russian_date(tc)}")
