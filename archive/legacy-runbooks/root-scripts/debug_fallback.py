
import sys
import json
import os

# Setup environment
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "src"))


from dotenv import load_dotenv
load_dotenv()

from src.yandex_business_parser import YandexBusinessParser
from src.auth_encryption import decrypt_auth_data
from src.database_manager import DatabaseManager

def debug_account(account_id):
    print(f"🔍 Debugging account {account_id}...")
    db = DatabaseManager()
    
    # Get auth data
    cursor = db.conn.cursor()
    cursor.execute("SELECT auth_data_encrypted, business_id FROM ExternalBusinessAccounts WHERE id = %s", (account_id,))
    row = cursor.fetchone()
    
    if not row:
        print("❌ Account not found")
        return

    auth_encrypted, business_id = row
    
    # Initialize account dict EARLY
    account = {"id": account_id, "business_id": business_id}

    auth_plain = decrypt_auth_data(auth_encrypted)
    try:
        auth_dict = json.loads(auth_plain)
    except:
        auth_dict = {"cookies": auth_plain}
        
    print(f"🔑 Auth data loaded for Business {business_id}")
    parser = YandexBusinessParser(auth_dict)
    
    # Get external_id from DB
    cursor.execute("SELECT external_id FROM ExternalBusinessAccounts WHERE id = %s", (account_id,))
    row_ext = cursor.fetchone()
    if row_ext and row_ext[0]:
        account["external_id"] = row_ext[0]
        print(f"🆔 External ID found: {account['external_id']}")
    else:
        print("⚠️ No external_id found in DB")

    # 1. Test Products
    print("\n📦 Fetching Products...")
    try:
        products = parser.fetch_products(account)
        print(f"✅ Products found: {len(products)} categories")
        print(json.dumps(products[:1], indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"❌ Error fetching products: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test Org Info
    print("\n🏢 Fetching Org Info...")
    try:
        org_info = parser.fetch_organization_info(account)
        print(f"✅ Org Info: {org_info}")
    except Exception as e:
        print(f"❌ Error fetching org info: {e}")

    # 3. Test Reviews
    print("\n💬 Fetching Reviews...")
    try:
        reviews = parser.fetch_reviews(account)
        print(f"✅ Reviews found: {len(reviews)}")
        if reviews:
            print(f"Sample review: {reviews[0]}")
    except Exception as e:
        print(f"❌ Error fetching reviews: {e}")

if __name__ == "__main__":
    # Get the latest account ID from DB
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("SELECT id FROM ExternalBusinessAccounts LIMIT 1")
    acc = cursor.fetchone()
    if acc:
        debug_account(acc[0])
    else:
        print("No accounts found")
