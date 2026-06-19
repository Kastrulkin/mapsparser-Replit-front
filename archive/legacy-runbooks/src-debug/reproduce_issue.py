import sys
import json
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from yandex_maps_scraper import parse_yandex_card

# Test URL (Oliver salon or similar)
# Using a generic one if specific not found, but trying to match user's case
# User URL: https://yandex.ru/maps/org/oliver/20329374...
# Let's try a real working URL for a salon to check general parser health
TEST_URL = "https://yandex.ru/maps/org/oliver/203293744630" 

try:
    print(f"Testing parser on: {TEST_URL}")
    data = parse_yandex_card(TEST_URL)
    
    print("\nXXX PARSING RESULT XXX")
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    # Check critical fields
    print("\n--- DIAGNOSTICS ---")
    print(f"Rating found: {bool(data.get('rating'))} ({data.get('rating')})")
    print(f"Phone found: {bool(data.get('phone'))} ({data.get('phone')})")
    print(f"Site found: {bool(data.get('site'))} ({data.get('site')})")
    print(f"Reviews count: {data.get('reviews_count')}")
    print(f"Services count: {len(data.get('products', []))}")
    
except Exception as e:
    print(f"\nCRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
