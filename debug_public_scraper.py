
import sys
import os
import json
import logging

# Setup path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from database_manager import DatabaseManager
from parser_config import parse_yandex_card

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_public_scraper():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Get active account URL
    # MapParseResults/BusinessMapLinks/ParseQueue - where is the URL?
    # ParseQueue usually has it. Let's find a recently completed task or just use a known hardcoded URL if possible, 
    # but querying BusinessMapLinks is better.
    
    cursor.execute("""
        SELECT url FROM BusinessMapLinks 
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if not row:
         # Fallback to ParseQueue
         cursor.execute("SELECT url FROM ParseQueue WHERE url LIKE '%yandex%' LIMIT 1")
         row = cursor.fetchone()

    if not row:
        print("❌ No URLs found in DB to test.")
        return

    url = row[0]
    print(f"🔍 Testing Public Scraper for URL: {url}")
    
    if '/sprav/' in url:
        print("⚠️ This is a cabinet URL. Converting to public if possible (or skipping if not).")
        # Scraper might handle it or fail.
        
    try:
        print("🚀 Calling parse_yandex_card(url)...")
        card_data = parse_yandex_card(url)
        
        print("\n📦 Scraper Result Overview:")
        print(f"   Name: {card_data.get('name')}")
        print(f"   Error: {card_data.get('error')}")
        
        products = card_data.get('products', [])
        print(f"   Products found: {len(products)}")
        
        if products:
             print(json.dumps(products[:2], indent=2, ensure_ascii=False))
        else:
             print("   ⚠️ No products found in scraped data. Possible reasons: No 'Prices' tab, selectors changed, or blocking.")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    db.close()

if __name__ == "__main__":
    debug_public_scraper()
