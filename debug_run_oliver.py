
import sys
import os
import sqlite3
import json

# Add src to path
sys.path.append(os.path.abspath("src"))

try:
    from yandex_maps_scraper import parse_yandex_card
    from worker import _sync_parsed_services_to_db
    from safe_db_utils import get_db_connection
except ImportError as e:
    print(f"ImportError: {e}")
    print("Ensure you are running from the project root.")
    sys.exit(1)

URL = "https://yandex.ru/maps/org/oliver/203293742306/?ll=30.219413%2C59.987283&z=13"
BUSINESS_ID = "203293742306"
USER_ID = "debug_oliver_user"

def run_debug():
    print(f"🚀 Starting debug parse for Oliver ({URL})...")
    
    # 1. Parse
    try:
        # Note: parse_yandex_card internally uses Playwright.
        # Ensure 'headless' is used (it usually is default/config dependent).
        data = parse_yandex_card(URL)
        print("✅ Parsing finished.")
    except Exception as e:
        print(f"❌ Parsing failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Check products
    products = data.get('products', [])
    print(f"📦 Found {len(products)} categories.")
    
    if not products:
        print("⚠️ No products found! Check if scraper is picking up 'Меню' or 'Товары'.")
    else:
        for p in products:
            items = p.get('items', [])
            print(f"   - Category: {p.get('category')} ({len(items)} items)")
            if items:
                first = items[0]
                print(f"     Example: {first.get('name')} | Price: {first.get('price')} | Desc: {first.get('description')}")

    # 2. Sync to DB
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure business exists
    cursor.execute("INSERT OR IGNORE INTO Businesses (id, name, yandex_url, owner_id) VALUES (?, ?, ?, ?)", 
                   (BUSINESS_ID, "Oliver (Debug)", URL, USER_ID))
    conn.commit()
    
    print("\n💾 Syncing to DB using fixed worker logic...")
    try:
        # This calls the fixed function requiring user_id
        _sync_parsed_services_to_db(BUSINESS_ID, products, USER_ID, conn)
        conn.commit()
        print("✅ Sync finished successfully.")
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        conn.close()
        return
        
    # 3. Verify in DB
    print("\n📊 DB Verification (UserServices Table):")
    
    # Count by category
    cursor.execute("SELECT category, count(*) FROM UserServices WHERE business_id = ? GROUP BY category", (BUSINESS_ID,))
    rows = cursor.fetchall()
    if not rows:
        print("   ⚠️ No services found in DB!")
    for row in rows:
        print(f"   - {row[0]}: {row[1]}")
        
    # Check details of a few
    print("\n🔍 Detail check (First 3):")
    cursor.execute("SELECT name, price, description, updated_at FROM UserServices WHERE business_id = ? LIMIT 3", (BUSINESS_ID,))
    samples = cursor.fetchall()
    for s in samples:
        print(f"   Name: {s[0]}")
        print(f"   Price (cents): {s[1]}")
        print(f"   Desc: {s[2]}")
        print(f"   Updated: {s[3]}")
        print("   ---")

    conn.close()

if __name__ == "__main__":
    run_debug()
