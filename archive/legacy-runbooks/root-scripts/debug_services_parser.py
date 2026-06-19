
import sys
import os
import json
import logging

# Setup path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from database_manager import DatabaseManager
from yandex_business_parser import YandexBusinessParser

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from auth_encryption import decrypt_auth_data

def debug_services():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Get active account
    cursor.execute("""
        SELECT * FROM ExternalBusinessAccounts 
        WHERE is_active = 1 
        LIMIT 1
    """)
    row = cursor.fetchone()
    
    if not row:
        print("❌ No active accounts found.")
        return

    # Convert row to dict
    columns = [col[0] for col in cursor.description]
    account = dict(zip(columns, row))
    
    print(f"🔍 Testing parser for Business: {account.get('business_id')} (External ID: {account.get('external_id')})")
    
    # Decrypt auth data
    encrypted = account.get('auth_data_encrypted')
    cookies_json = None
    if encrypted:
        print(f"🔐 Decrypting auth data (len={len(encrypted)})...")
        cookies_json = decrypt_auth_data(encrypted)
    else:
        print("⚠️ No encrypted auth data found.")
        cookies_json = account.get('cookies_json') # Fallback if column exists (it doesn't, but logic holds)
        
    print(f"🍪 Decrypted cookies present: {bool(cookies_json)}")
    
    # Construct auth_data
    auth_data = {}
    if cookies_json:
        try:
            # Try to parse as JSON if it's a string
            if isinstance(cookies_json, str):
                cookies_dict = json.loads(cookies_json)
                # Convert dict to semi-colon string for header
                if isinstance(cookies_dict, dict):
                    auth_data['cookies'] = "; ".join([f"{k}={v}" for k,v in cookies_dict.items()])
                else:
                    print(f"⚠️ Unexpected JSON type: {type(cookies_dict)}")
                    auth_data['cookies'] = str(cookies_json)
            else:
                 auth_data['cookies'] = str(cookies_json) # Fallback
        except Exception as e:
             print(f"⚠️ JSON parse error: {e}")
             auth_data['cookies'] = str(cookies_json)

    print(f"🔑 Auth Data Cookies length: {len(auth_data.get('cookies', ''))}")
    
    parser = YandexBusinessParser(auth_data)
    
    # Trace fetch_products
    print("\n🚀 calling parser.fetch_products(account)...")
    try:
        products = parser.fetch_products(account)
        print(f"\n📦 Result: {len(products)} categories found.")
        print(json.dumps(products, indent=2, ensure_ascii=False)[:1000] + "...")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    db.close()

if __name__ == "__main__":
    debug_services()
