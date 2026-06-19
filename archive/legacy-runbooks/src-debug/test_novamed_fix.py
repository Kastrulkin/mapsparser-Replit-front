
import sys
import os
import json

# Add current directory to path
sys.path.append(os.getcwd())

try:
    from src.yandex_maps_scraper import parse_yandex_card
except ImportError:
    # Try direct import if running from src
    sys.path.append(os.path.join(os.getcwd(), 'src'))
    from yandex_maps_scraper import parse_yandex_card

url = "https://yandex.ru/maps/org/novamed_clinica/74391716023/"

print(f"Testing scraper for URL: {url}")

try:
    data = parse_yandex_card(url)
    
    print("\n--- RESULTS ---")
    print(f"Title: {data.get('title')}")
    print(f"Phone: {data.get('phone')}")
    print(f"Site: {data.get('site')}")
    
    products = data.get('products', [])
    print(f"Services count: {len(products)}")
    
    if products:
        print(f"First service category: {products[0].get('category')}")
        items = products[0].get('items', [])
        if items:
            print(f"First service item: {items[0].get('name')}")
            print(f"First service price: {items[0].get('price')}")
            
    print("\nFull Data Keys:", list(data.keys()))
    
except Exception as e:
    print(f"Error running scraper: {e}")
    import traceback
    traceback.print_exc()
