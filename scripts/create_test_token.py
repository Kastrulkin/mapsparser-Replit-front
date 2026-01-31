#!/usr/bin/env python3
"""
Create a test token for Phase 3.5 API testing
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auth_system import create_session
from database_manager import DatabaseManager

def main():
    db = DatabaseManager()
    cursor = db.conn.cursor()
    
    # Get first user
    cursor.execute("SELECT id, email FROM Users LIMIT 1")
    row = cursor.fetchone()
    
    if not row:
        print("❌ No users found in database")
        sys.exit(1)
    
    user_id, email = row
    print(f"✅ Found user: {email} (ID: {user_id})")
    
    # Create session (returns token string, not dict)
    token = create_session(user_id)
    
    if not token:
        print("❌ Failed to create session")
        sys.exit(1)
    
    # Get business_id for testing
    cursor.execute("SELECT id FROM Businesses LIMIT 1")
    business_row = cursor.fetchone()
    business_id = business_row[0] if business_row else "YOUR_BUSINESS_ID"
    
    # If called from test script, output only token
    if os.getenv('QUIET') == '1':
        print(token)
        return
    
    print("")
    print("🔑 Test token created:")
    print(f"   Token: {token}")
    print("")
    print("🚀 Use it for testing:")
    print(f"   ./scripts/test_phase35_step1.sh {business_id} {token}")
    print("")
    print("   Or with curl:")
    print(f"   curl -H 'Authorization: Bearer {token}' \\")
    print(f"        http://localhost:8000/api/business/{business_id}/external/reviews")
    
    db.close()

if __name__ == "__main__":
    main()
