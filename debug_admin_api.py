import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

try:
    from database_manager import DatabaseManager
    
    print("🚀 initializing DatabaseManager...")
    db = DatabaseManager()
    
    print("🔄 Calling get_all_users_with_businesses()...")
    users = db.get_all_users_with_businesses()
    
    print(f"✅ Success! Retrieved {len(users)} users.")
    for u in users:
        print(f"  - User: {u.get('email')} (Businesses: {len(u.get('direct_businesses', []))}, Networks: {len(u.get('networks', []))})")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
