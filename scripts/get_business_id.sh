#!/bin/bash
# Get business_id from database for testing

set -e

echo "🔍 Getting business_id from database..."
echo "========================================"

# Check if we're using PostgreSQL or SQLite
if [ -f "src/reports.db" ]; then
    echo "📦 Using SQLite database"
    
    # Get first business_id
    BUSINESS_ID=$(sqlite3 src/reports.db "SELECT id FROM Businesses LIMIT 1;" 2>/dev/null)
    
    if [ -z "$BUSINESS_ID" ]; then
        echo "❌ No businesses found in database"
        echo ""
        echo "💡 Create a business first, or check database:"
        echo "   sqlite3 src/reports.db \"SELECT id, name FROM Businesses;\""
        exit 1
    fi
    
    # Get business name
    BUSINESS_NAME=$(sqlite3 src/reports.db "SELECT name FROM Businesses WHERE id = '$BUSINESS_ID';" 2>/dev/null)
    
    echo "✅ Found business:"
    echo "   ID: $BUSINESS_ID"
    echo "   Name: $BUSINESS_NAME"
    echo ""
    echo "📋 All businesses:"
    sqlite3 src/reports.db "SELECT id, name FROM Businesses LIMIT 5;" 2>/dev/null | while IFS='|' read -r id name; do
        echo "   - $id: $name"
    done
    
elif [ -n "$DATABASE_URL" ] || [ -n "$DB_HOST" ]; then
    echo "📦 Using PostgreSQL database"
    echo ""
    echo "💡 To get business_id, run:"
    echo "   psql \$DATABASE_URL -c \"SELECT id, name FROM Businesses LIMIT 5;\""
    echo ""
    echo "   Or if using connection string:"
    echo "   psql -h \$DB_HOST -U \$DB_USER -d \$DB_NAME -c \"SELECT id, name FROM Businesses LIMIT 5;\""
    exit 0
else
    echo "⚠️  Cannot determine database type"
    echo ""
    echo "💡 Check database manually:"
    echo "   SQLite: sqlite3 src/reports.db \"SELECT id, name FROM Businesses;\""
    echo "   PostgreSQL: psql -c \"SELECT id, name FROM Businesses;\""
    exit 1
fi

echo ""
echo "🚀 Use this business_id for testing:"
echo "   ./scripts/test_phase35_step1.sh $BUSINESS_ID"
echo ""
echo "   Or with token:"
echo "   ./scripts/test_phase35_step1.sh $BUSINESS_ID YOUR_TOKEN"
