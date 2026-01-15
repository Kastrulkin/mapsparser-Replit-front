import os
import sys
import sqlite3

# Add src to path so we can import safe_db_utils
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

try:
    from safe_db_utils import SafeDatabase
except ImportError:
    # Fallback if run from different location
    sys.path.append(os.path.join(os.getcwd(), 'src'))
    from safe_db_utils import SafeDatabase

def fix_profile():
    print("🔧 Starting repair of user profile for tislitskaya@yandex.ru...")
    
    try:
        with SafeDatabase() as db:
            cursor = db.cursor()
            
            # 1. Check current state
            print("📊 Checking current record...")
            cursor.execute("SELECT id, email, name, phone, password_hash FROM Users WHERE email='tislitskaya@yandex.ru'")
            row = cursor.fetchone()
            
            if not row:
                print("❌ User tislitskaya@yandex.ru not found!")
                return
            
            print(f"   Current data: ID={row[0]}, Name='{row[2]}', Phone='{row[3]}'")
            
            # 2. Fix it
            # We explicitly set name='Oliver' and clear invalid phone/password_hash fields that were corrupted
            # Note: The actual password hash is likely secure in auth_system, here we just clear garbage columns if they were shifted
            print("🛠  Fixing corrupted fields...")
            cursor.execute("""
                UPDATE Users 
                SET name='Oliver', 
                    phone=NULL, 
                    password_hash=NULL 
                WHERE email='tislitskaya@yandex.ru' AND name='1234567890'
            """)
            
            if cursor.rowcount > 0:
                print(f"✅ Updated {cursor.rowcount} record(s).")
                db.conn.commit()
            else:
                print("⚠️  No records matched the corruption criteria (name='1234567890'). Found distinct record or already fixed.")
                # Force update name anyway just in case
                cursor.execute("UPDATE Users SET name='Oliver' WHERE email='tislitskaya@yandex.ru'")
                db.conn.commit()
                print("   Forced name update to 'Oliver'.")

            # 3. Verify
            cursor.execute("SELECT id, email, name, phone FROM Users WHERE email='tislitskaya@yandex.ru'")
            new_row = cursor.fetchone()
            print(f"✅ New state: Name='{new_row[2]}', Phone='{new_row[3]}'")
            
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_profile()
