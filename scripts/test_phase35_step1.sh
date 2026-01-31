#!/bin/bash
# Test Phase 3.5 Step 1: Verify USE_REVIEW_REPOSITORY works

set -e

echo "🧪 Testing Phase 3.5 Step 1: USE_REVIEW_REPOSITORY"
echo "=================================================="

# Check if Flask is running
if ! lsof -tiTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "❌ Flask server is not running on port 8000"
    echo "   Start it with: python3 src/main.py"
    exit 1
fi

echo "✅ Flask server is running"

# Check .env flags
if grep -q "USE_REVIEW_REPOSITORY=true" .env; then
    echo "✅ USE_REVIEW_REPOSITORY=true is set"
else
    echo "⚠️  USE_REVIEW_REPOSITORY is not set to true"
    echo "   Run: ./scripts/start_phase35_step1.sh"
    exit 1
fi

# Test endpoint (requires business_id)
if [ -z "$1" ]; then
    echo ""
    echo "⚠️  No business_id provided"
    echo ""
    echo "💡 Getting business_id from database..."
    
    # Try to get business_id from database
    if [ -f "src/reports.db" ]; then
        BUSINESS_ID=$(sqlite3 src/reports.db "SELECT id FROM Businesses LIMIT 1;" 2>/dev/null)
        if [ -n "$BUSINESS_ID" ]; then
            BUSINESS_NAME=$(sqlite3 src/reports.db "SELECT name FROM Businesses WHERE id = '$BUSINESS_ID';" 2>/dev/null)
            echo "   ✅ Found: $BUSINESS_ID ($BUSINESS_NAME)"
            echo ""
            echo "   Using this business_id for testing..."
        else
            echo "   ❌ No businesses found in database"
            echo ""
            echo "   Usage: ./scripts/test_phase35_step1.sh YOUR_BUSINESS_ID"
            echo ""
            echo "   Or get business_id:"
            echo "   ./scripts/get_business_id.sh"
            exit 1
        fi
    else
        echo "   ❌ Cannot find database"
        echo ""
        echo "   Usage: ./scripts/test_phase35_step1.sh YOUR_BUSINESS_ID"
        echo ""
        echo "   Or get business_id:"
        echo "   ./scripts/get_business_id.sh"
        exit 1
    fi
else
    BUSINESS_ID=$1
fi
TOKEN=${2:-""}

# If no token provided, try to create one automatically
if [ -z "$TOKEN" ]; then
    echo ""
    echo "⚠️  No token provided"
    echo "💡 Creating test token automatically..."
    
    TOKEN=$(QUIET=1 python3 scripts/create_test_token.py 2>/dev/null | tail -1)
    
    if [ -z "$TOKEN" ]; then
        echo "   ❌ Failed to create token automatically"
        echo "   Testing without auth (will fail with 401)..."
        USE_TOKEN=false
    else
        echo "   ✅ Token created: ${TOKEN:0:30}..."
        USE_TOKEN=true
    fi
else
    USE_TOKEN=true
fi

echo ""
echo "📡 Testing endpoint: /api/business/$BUSINESS_ID/external/reviews"

if [ "$USE_TOKEN" = "true" ] && [ -n "$TOKEN" ]; then
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "http://localhost:8000/api/business/$BUSINESS_ID/external/reviews" 2>&1)
else
    RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        "http://localhost:8000/api/business/$BUSINESS_ID/external/reviews" 2>&1)
fi

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

echo ""
echo "📊 Response:"
echo "   HTTP Code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Success!"
    echo ""
    echo "   Response preview:"
    echo "$BODY" | head -20 | sed 's/^/   /'
    
    # Check for errors in response
    if echo "$BODY" | grep -qi "error\|exception\|traceback"; then
        echo ""
        echo "   ⚠️  Warning: Response contains error keywords"
    fi
else
    echo "   ❌ Failed!"
    echo ""
    echo "   Response:"
    echo "$BODY" | head -30 | sed 's/^/   /'
fi

echo ""
echo "🔍 Check Flask logs for:"
echo "   - IntegrityError"
echo "   - violat"
echo "   - traceback"
echo "   - rollback"
