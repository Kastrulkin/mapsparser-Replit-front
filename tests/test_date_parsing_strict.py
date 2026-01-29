
import unittest
import re
from datetime import datetime

# Function to test (copied from worker.py implementation plan)
def _parse_russian_date(date_str: str) -> datetime | None:
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
            # FIX: Strip punctuation
            month_str = re.sub(r'[^\w\s]', '', month_str, flags=re.UNICODE) 
            
            if not day_str or not month_str:
                return None
                
            day = int(day_str)
            month = months.get(month_str)
            year = int(year_str)
            
            if month:
                return datetime(year, month, day)
                
    except Exception:
        pass
    return None

class TestDateParsingStrict(unittest.TestCase):
    def test_clean_dates(self):
        self.assertIsNotNone(_parse_russian_date("5 сентября"))
        self.assertEqual(_parse_russian_date("5 сентября").month, 9)

    def test_punctuation_cases(self):
        # The key fix triggers here
        self.assertIsNotNone(_parse_russian_date("5 сентября,"))
        self.assertIsNotNone(_parse_russian_date("5 сентября."))
        self.assertEqual(_parse_russian_date("5 сентября,").month, 9)

    def test_leading_zero(self):
        self.assertIsNotNone(_parse_russian_date("05 сентября"))
        self.assertEqual(_parse_russian_date("05 сентября").day, 5)

    def test_with_year(self):
        dt = _parse_russian_date("5 сентября 2024")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)

    def test_different_month(self):
        dt = _parse_russian_date("1 января")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.day, 1)

if __name__ == '__main__':
    unittest.main()
