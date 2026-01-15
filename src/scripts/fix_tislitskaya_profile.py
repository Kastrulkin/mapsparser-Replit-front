import os
import sys
import sqlite3

# Add src to path so we can import safe_db_utils
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
sys.path.append(src_dir)

try:
    from safe_db_utils import get_db_connection
except ImportError:
    # Fallback if run from different location
    sys.path.append(os.path.join(os.getcwd(), 'src'))
    from safe_db_utils import get_db_connection

def fix_profile():
    print("🔧 Starting repair of user profile for tislitskaya@yandex.ru...")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Check current state
        print("📊 Checking current record...")
        cursor.execute("SELECT id, email, name, phone, password_hash FROM Users WHERE email='tislitskaya@yandex.ru'")
        row = cursor.fetchone()
        
        if not row:
            print("❌ User tislitskaya@yandex.ru not found!")
            conn.close()
            return
        
        print(f"   Current data: ID={row['id' if hasattr(row, 'keys') else 0]}, Name='{row['name' if hasattr(row, 'keys') else 2]}'")
        
        # 2. Fix it
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
            conn.commit()
        else:
            print("⚠️  No records matched the corruption criteria (name='1234567890'). Found distinct record or already fixed.")
            # Force update name anyway just in case
            cursor.execute("UPDATE Users SET name='Oliver' WHERE email='tislitskaya@yandex.ru'")
            conn.commit()
            print("   Forced name update to 'Oliver'.")

        # 3. Verify
        cursor.execute("SELECT id, email, name, phone FROM Users WHERE email='tislitskaya@yandex.ru'")
        new_row = cursor.fetchone()
        print(f"✅ New state: Name='{new_row['name' if hasattr(new_row, 'keys') else 2]}'")
        
        conn.close()
            
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        import traceback
        traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Error during repair: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_profile()
