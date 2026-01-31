#!/bin/bash
# Get test token for Phase 3.5 testing

set -e

echo "🔑 Getting test token for API testing"
echo "======================================"

# Check if database exists
if [ ! -f "src/reports.db" ]; then
    echo "❌ Database not found: src/reports.db"
    exit 1
fi

# Get first user email
USER_EMAIL=$(sqlite3 src/reports.db "SELECT email FROM Users LIMIT 1;" 2>/dev/null)

if [ -z "$USER_EMAIL" ]; then
    echo "❌ No users found in database"
    echo ""
    echo "💡 Create a user first, or check database:"
    echo "   sqlite3 src/reports.db \"SELECT email FROM Users;\""
    exit 1
fi

echo "✅ Found user: $USER_EMAIL"
echo ""
echo "💡 To get a token, you need to:"
echo ""
echo "1. Login through the web interface:"
echo "   http://localhost:8000"
echo ""
echo "2. Or create a test session manually:"
echo "   python3 -c \"
import sys
sys.path.insert(0, 'src')
from auth_system import create_session
from database_manager import DatabaseManager

db = DatabaseManager()
cursor = db.conn.cursor()
cursor.execute('SELECT id FROM Users WHERE email = ?', ('$USER_EMAIL',))
row = cursor.fetchone()
if row:
    user_id = row[0]
    session = create_session(user_id)
    print('Token:', session['token'])
    print('Expires:', session['expires_at'])
else:
    print('User not found')
db.close()
\""
echo ""
echo "3. Or use existing session from database:"
echo "   sqlite3 src/reports.db \"SELECT token FROM UserSessions WHERE user_id = (SELECT id FROM Users WHERE email = '$USER_EMAIL') ORDER BY expires_at DESC LIMIT 1;\""
