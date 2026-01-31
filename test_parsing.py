import sys
import os
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
load_dotenv()

from yandex_maps_scraper import parse_yandex_card

def test_parsing():
    # The URL that was causing issues (normalized version)
    url = "https://yandex.ru/maps/org/redirect/203293742306"
    print(f"🧪 Testing parsing for: {url}")
    
    try:
        data = parse_yandex_card(url)
        
        print("\n✅ Parsing Result:")
        print(f"Title: {data.get('title')}")
        print(f"Address: {data.get('address')}")
        print(f"Rating: {data.get('rating')}")
        print(f"Reviews: {data.get('reviews_count')}")
        
        if data.get('title') and data.get('address'):
            print("\n🎉 SUCCESS: Data extracted successfully!")
        else:
            print("\n❌ FAILURE: Critical data missing.")
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")

if __name__ == "__main__":
    test_parsing()
