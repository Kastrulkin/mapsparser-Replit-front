
import sys
import os
import json
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from src.parser_interception import parse_yandex_card
import sys

def test_parser():
    url = "https://yandex.ru/maps/org/oliver/203293742306/?ll=30.219413%2C59.987283&z=13"
    print(f"Testing parser with URL: {url}")
    
    try:
        data = parse_yandex_card(url)
        print("\n--- Parser Result ---")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        
        # Check specific fields
        print("\n--- Validation ---")
        reviews_count = len(data.get('reviews', []))
        photos_count = len(data.get('photos', []))
        if isinstance(data.get('photos'), dict):
             photos_count = len(data.get('photos', {}).get('photos', []))
        news_count = len(data.get('news', []))
        products_count = len(data.get('products', []))
        
        print(f"Reviews found: {reviews_count}")
        print(f"Photos found: {photos_count}")
        print(f"News found: {news_count}")
        print(f"Products found: {products_count}")
        
    except Exception as e:
        print(f"\n❌ Error during parsing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_parser()
