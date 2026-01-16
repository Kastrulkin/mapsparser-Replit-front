import os
import sys
import sqlite3
import uuid
import hashlib
import secrets
from datetime import datetime

# Standalone helper to avoid import issues
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return f"{salt}:{pwd_hash.hex()}"

def get_db_path():
    # Try typical paths
    paths = ['src/reports.db', 'reports.db', '../reports.db']
    for p in paths:
        if os.path.exists(p):
            return p
    return 'src/reports.db' # Default

def restore_access():
    print("🚑 Starting Emergency Admin Restoration...")
    
    db_path = get_db_path()
    print(f"📂 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # --- 1. Restore/Fix Demyanovap ---
    target_email = 'demyanovap@yandex.ru'
    print(f"\n🔍 Checking {target_email}...")
    
    cursor.execute("SELECT id FROM Users WHERE email = ?", (target_email,))
    user = cursor.fetchone()
    
    demyanovap_id = None
    
    if user:
        print("   ✅ User exists. Ensuring superadmin status...")
        demyanovap_id = user['id']
        cursor.execute("UPDATE Users SET is_superadmin = 1 WHERE id = ?", (demyanovap_id,))
    else:
        print("   ❌ User MISSING. Creating new superadmin account...")
        demyanovap_id = str(uuid.uuid4())
        default_pass = "admin12345"
        pwd_hash = hash_password(default_pass)
        
        cursor.execute("""
            INSERT INTO Users (id, email, password_hash, name, is_superadmin, is_active, created_at)
            VALUES (?, ?, ?, ?, 1, 1, ?)
        """, (demyanovap_id, target_email, pwd_hash, "SuperAdmin", datetime.now().isoformat()))
        print(f"   ✨ Created user {target_email} with password: {default_pass}")

    # --- 2. Fix Tislitskaya ---
    tislitskaya_email = 'tislitskaya@yandex.ru'
    print(f"\n🔍 Checking {tislitskaya_email}...")
    
    cursor.execute("SELECT id FROM Users WHERE email = ?", (tislitskaya_email,))
    tis = cursor.fetchone()
    
    if tis:
        print("   ⚠️  Demoting from superadmin...")
        cursor.execute("UPDATE Users SET is_superadmin = 0 WHERE id = ?", (tis['id'],))
        tislitskaya_id = tis['id']
        
        # --- 3. Transfer Businesses ---
        if demyanovap_id:
            print("\n📦 Transferring businesses...")
            cursor.execute("SELECT id, name FROM Businesses WHERE owner_id = ?", (tislitskaya_id,))
            businesses = cursor.fetchall()
            
            to_transfer = []
            kept = []
            
            for b in businesses:
                name_lower = b['name'].lower()
                if 'оливер' in name_lower or 'oliver' in name_lower:
                    kept.append(b['name'])
                else:
                    to_transfer.append(b['id'])
            
            if to_transfer:
                placeholders = ','.join('?' * len(to_transfer))
                cursor.execute(f"""
                    UPDATE Businesses 
                    SET owner_id = ? 
                    WHERE id IN ({placeholders})
                """, [demyanovap_id] + to_transfer)
                print(f"   🚀 Transferred {len(to_transfer)} businesses to {target_email}")
            else:
                print("   ℹ️  No businesses needed transfer.")
                
            print(f"   ✅ Tislitskaya keeps: {', '.join(kept) if kept else 'None'}")
            
    else:
        print(f"   ℹ️  User {tislitskaya_email} not found.")

    conn.commit()
    conn.close()
    print("\n✅ Restoration Complete.")

if __name__ == '__main__':
    restore_access()
