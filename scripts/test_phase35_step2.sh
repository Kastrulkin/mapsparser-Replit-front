#!/bin/bash
# Test Phase 3.5 Step 2: Verify USE_SERVICE_REPOSITORY works

set -e

echo "🧪 Testing Phase 3.5 Step 2: USE_SERVICE_REPOSITORY"
echo "==================================================="

# Check if Flask is running
if ! lsof -tiTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "❌ Flask server is not running on port 8000"
    echo "   Start it with: python3 src/main.py"
    exit 1
fi

echo "✅ Flask server is running"

# Check .env flags
if grep -q "USE_SERVICE_REPOSITORY=true" .env; then
    echo "✅ USE_SERVICE_REPOSITORY=true is set"
else
    echo "⚠️  USE_SERVICE_REPOSITORY is not set to true"
    echo "   Run: ./scripts/start_phase35_step2.sh"
    exit 1
fi

# Get business_id
if [ -z "$1" ]; then
    echo ""
    echo "⚠️  No business_id provided"
    echo ""
    echo "💡 Getting business_id from database..."
    
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
            echo "   Usage: ./scripts/test_phase35_step2.sh YOUR_BUSINESS_ID"
            exit 1
        fi
    else
        echo "   ❌ Cannot find database"
        echo ""
        echo "   Usage: ./scripts/test_phase35_step2.sh YOUR_BUSINESS_ID"
        exit 1
    fi
else
    BUSINESS_ID=$1
fi

# Get or create token
TOKEN=${2:-""}

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
echo "📡 Testing Step 2 endpoints:"
echo ""

# Test 1: Create service (POST)
echo "1️⃣  Testing POST /api/services/add"
if [ "$USE_TOKEN" = "true" ] && [ -n "$TOKEN" ]; then
    CREATE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X POST \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"business_id\": \"$BUSINESS_ID\", \"name\": \"Test Service Step2\", \"category\": \"Test\", \"price\": \"500\"}" \
        "http://localhost:8000/api/services/add" 2>&1)
else
    CREATE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "{\"business_id\": \"$BUSINESS_ID\", \"name\": \"Test Service Step2\"}" \
        "http://localhost:8000/api/services/add" 2>&1)
fi

CREATE_HTTP_CODE=$(echo "$CREATE_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
CREATE_BODY=$(echo "$CREATE_RESPONSE" | sed '/HTTP_CODE/d')

if [ "$CREATE_HTTP_CODE" = "200" ]; then
    echo "   ✅ Success! Service created"
    # Extract service_id from response if available
    SERVICE_ID=$(echo "$CREATE_BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
    if [ -z "$SERVICE_ID" ]; then
        # Try to get last created service from list
        echo "   💡 Getting service ID from list..."
        LIST_RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
            "http://localhost:8000/api/services/list?business_id=$BUSINESS_ID" 2>/dev/null || echo "")
        SERVICE_ID=$(echo "$LIST_RESPONSE" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4 || echo "")
    fi
else
    echo "   ❌ Failed! HTTP Code: $CREATE_HTTP_CODE"
    echo "   Response: $CREATE_BODY" | head -5 | sed 's/^/      /'
    SERVICE_ID=""
fi

# Test 2: Update service (PUT) - only if create succeeded
if [ -n "$SERVICE_ID" ] && [ "$CREATE_HTTP_CODE" = "200" ]; then
    echo ""
    echo "2️⃣  Testing PUT /api/services/update/$SERVICE_ID"
    if [ "$USE_TOKEN" = "true" ] && [ -n "$TOKEN" ]; then
        UPDATE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
            -X PUT \
            -H "Authorization: Bearer $TOKEN" \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"Updated Test Service Step2\", \"price\": \"600\"}" \
            "http://localhost:8000/api/services/update/$SERVICE_ID" 2>&1)
    else
        UPDATE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
            -X PUT \
            -H "Content-Type: application/json" \
            -d "{\"name\": \"Updated Test Service Step2\"}" \
            "http://localhost:8000/api/services/update/$SERVICE_ID" 2>&1)
    fi
    
    UPDATE_HTTP_CODE=$(echo "$UPDATE_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
    UPDATE_BODY=$(echo "$UPDATE_RESPONSE" | sed '/HTTP_CODE/d')
    
    if [ "$UPDATE_HTTP_CODE" = "200" ]; then
        echo "   ✅ Success! Service updated"
    else
        echo "   ❌ Failed! HTTP Code: $UPDATE_HTTP_CODE"
        echo "   Response: $UPDATE_BODY" | head -5 | sed 's/^/      /'
    fi
    
    # Test 3: Delete service (DELETE) - only if update succeeded
    if [ "$UPDATE_HTTP_CODE" = "200" ]; then
        echo ""
        echo "3️⃣  Testing DELETE /api/services/delete/$SERVICE_ID"
        if [ "$USE_TOKEN" = "true" ] && [ -n "$TOKEN" ]; then
            DELETE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
                -X DELETE \
                -H "Authorization: Bearer $TOKEN" \
                "http://localhost:8000/api/services/delete/$SERVICE_ID" 2>&1)
        else
            DELETE_RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
                -X DELETE \
                "http://localhost:8000/api/services/delete/$SERVICE_ID" 2>&1)
        fi
        
        DELETE_HTTP_CODE=$(echo "$DELETE_RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
        DELETE_BODY=$(echo "$DELETE_RESPONSE" | sed '/HTTP_CODE/d')
        
        if [ "$DELETE_HTTP_CODE" = "200" ]; then
            echo "   ✅ Success! Service deleted"
        else
            echo "   ❌ Failed! HTTP Code: $DELETE_HTTP_CODE"
            echo "   Response: $DELETE_BODY" | head -5 | sed 's/^/      /'
        fi
    fi
else
    echo ""
    echo "⚠️  Skipping update/delete tests (create failed or no service_id)"
fi

echo ""
echo "🔍 Check Flask logs for:"
echo "   - IntegrityError"
echo "   - violat"
echo "   - traceback"
echo "   - rollback"
echo ""
echo "📝 Summary:"
echo "   - POST /api/services/add: $([ "$CREATE_HTTP_CODE" = "200" ] && echo "✅" || echo "❌")"
if [ -n "$SERVICE_ID" ]; then
    echo "   - PUT /api/services/update: $([ "$UPDATE_HTTP_CODE" = "200" ] && echo "✅" || echo "❌")"
    echo "   - DELETE /api/services/delete: $([ "$DELETE_HTTP_CODE" = "200" ] && echo "✅" || echo "❌")"
fi
