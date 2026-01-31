import logging
import sys
import json
import os
import time

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.parser_interception import YandexMapsInterceptionParser

# Usage: python repro_oliver.py

def run():
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    # URL from the user's screenshot
    url = "https://yandex.ru/maps/org/oliver/203293742306"
    
    print(f"Starting parser for: {url}")
    
    parser = YandexMapsInterceptionParser()
    try:
        # parser.parse_yandex_card is synchronous
        result = parser.parse_yandex_card(url)
        
        print("\n" + "="*50)
        print("PARSING RESULT")
        print("="*50)
        print(f"Name: {result.get('name')}")
        print(f"Rating: {result.get('rating')}")
        print(f"Reviews Count: {result.get('reviews_count')}")
        print(f"Services Count: {len(result.get('services', []))}")
        print(f"Photos Count: {result.get('photos_count')}")
        
        if result.get('services'):
            print("\nFirst 3 Services found:")
            for s in result['services'][:3]:
                print(f" - {s}")
        else:
            print("\nNO SERVICES FOUND.")

        # Save result to file for inspection
        with open('oliver_result.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.exception("Parser failed")

if __name__ == "__main__":
    run()
