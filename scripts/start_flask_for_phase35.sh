#!/bin/bash
# Start Flask server for Phase 3.5 testing

set -e

echo "🚀 Starting Flask server for Phase 3.5 Step 1"
echo "=============================================="

# Check if Flask is already running
if lsof -tiTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "⚠️  Flask is already running on port 8000"
    echo "   PID: $(lsof -tiTCP:8000 -sTCP:LISTEN)"
    echo ""
    read -p "Kill existing Flask and restart? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill $(lsof -tiTCP:8000 -sTCP:LISTEN)
        sleep 2
        echo "✅ Old Flask process killed"
    else
        echo "✅ Using existing Flask process"
        exit 0
    fi
fi

# Check .env flags
if ! grep -q "USE_REVIEW_REPOSITORY=true" .env 2>/dev/null; then
    echo "⚠️  USE_REVIEW_REPOSITORY not set to true"
    echo "   Run: ./scripts/start_phase35_step1.sh first"
    exit 1
fi

echo "✅ USE_REVIEW_REPOSITORY=true is set"
echo ""
echo "🔄 Starting Flask server..."
echo "   (Press Ctrl+C to stop)"
echo ""

# Start Flask
cd "$(dirname "$0")/.."
python3 src/main.py
