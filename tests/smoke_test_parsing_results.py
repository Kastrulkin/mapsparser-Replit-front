
import sqlite3
import sys
import os

DB_PATH = 'reports.db'

def check_results():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔍 Checking parsing results for 'Oliver'...")
    
    # 1. Check Services
    # First find business_id for Oliver
    cursor.execute("SELECT id FROM Businesses WHERE name LIKE '%Oliver%' LIMIT 1")
    biz_row = cursor.fetchone()
    
    if not biz_row:
        print("⚠️ Business 'Oliver' not found in DB.")
        # Try to check ANY services to prove system works
        cursor.execute("SELECT COUNT(*) FROM UserServices")
        total = cursor.fetchone()[0]
        print(f"ℹ️ Total UserServices in DB: {total}")
    else:
        biz_id = biz_row[0]
        cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id = ?", (biz_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✅ Services found for Oliver: {count}")
            if count >= 36:
                 print("   (Good match with expectation of ~36)")
            else:
                 print(f"   (Partial match: expected ~36, got {count})")
        else:
            print("❌ No services found for Oliver.")

    # 2. Check Reviews
    cursor.execute("SELECT COUNT(*) FROM ExternalBusinessReviews WHERE business_id = ?", (biz_id if biz_row else 'UNKNOWN',))
    reviews = cursor.fetchone()[0]
    
    if reviews > 20:
        print(f"✅ Reviews found: {reviews} (API parsing likely worked)")
    elif reviews > 0:
        print(f"⚠️ Reviews found but low count: {reviews} (HTML fallback?)")
    else:
        print("❌ No reviews found.")

    conn.close()

if __name__ == "__main__":
    check_results()
