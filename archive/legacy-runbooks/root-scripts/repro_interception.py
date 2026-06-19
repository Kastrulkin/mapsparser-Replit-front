import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from parser_interception import YandexMapsInterceptionParser
import json
from datetime import datetime

def test_interception_parsing():
    # URL from user context (Oliver)
    url = "https://yandex.ru/maps/org/yogi_room/5270814379/?ll=30.213846%2C59.952290&z=17.12"
    
    print(f"🚀 Starting reproduction test for: {url}")
    parser = YandexMapsInterceptionParser()
    
    try:
        data = parser.parse_yandex_card(url)
        
        print("\n" + "="*50)
        print("📊 RESULTS ANALYSIS")
        print("="*50)
        
        # 1. Check News Dates
        print(f"\n📰 NEWS ({len(data.get('news', []))} found):")
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        for i, post in enumerate(data.get('news', [])[:5]):
            date = post.get('date', '')
            print(f"  [{i+1}] Date: '{date}' | Title: {post.get('title', '')[:30]}...")
            if date.startswith(current_date_str) or not date:
                 print(f"      ⚠️  SUSPICIOUS: Date matches today ({current_date_str}) or is empty!")
        
        # 2. Check Services
        print(f"\n📦 SERVICES ({len(data.get('products', []))} categories):")
        total_items = 0
        for cat in data.get('products', []):
            item_count = len(cat.get('items', []))
            total_items += item_count
            print(f"  Category: '{cat.get('category', '')}' - {item_count} items")
        print(f"  TOTAL ITEMS: {total_items}")
        if total_items == 0:
            print("  ❌ FAILURE: No services found!")
            
        # 3. Check Reviews
        print(f"\n💬 REVIEWS ({len(data.get('reviews', []))} found):")
        if data.get('reviews'):
            print(f"  First review date: {data['reviews'][0].get('date', 'N/A')}")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interception_parsing()
