#!/bin/bash
# Phase 3.5 Step 1: Enable USE_REVIEW_REPOSITORY (read-only)
# Safe to run - only enables reading reviews through repository

set -e

echo "🚀 Phase 3.5 Step 1: Enabling USE_REVIEW_REPOSITORY"
echo "=================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found, creating..."
    touch .env
fi

# Backup .env
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)
echo "✅ .env backed up"

# Add or update repository flags
if grep -q "USE_REVIEW_REPOSITORY" .env; then
    # Update existing
    sed -i.bak 's/^USE_REVIEW_REPOSITORY=.*/USE_REVIEW_REPOSITORY=true/' .env
    echo "✅ Updated USE_REVIEW_REPOSITORY=true"
else
    # Add new
    echo "" >> .env
    echo "# Phase 3.5 Repository Pattern" >> .env
    echo "USE_REVIEW_REPOSITORY=true" >> .env
    echo "✅ Added USE_REVIEW_REPOSITORY=true"
fi

# Ensure other flags are false
if grep -q "USE_SERVICE_REPOSITORY" .env; then
    sed -i.bak 's/^USE_SERVICE_REPOSITORY=.*/USE_SERVICE_REPOSITORY=false/' .env
else
    echo "USE_SERVICE_REPOSITORY=false" >> .env
fi

if grep -q "USE_BUSINESS_REPOSITORY" .env; then
    sed -i.bak 's/^USE_BUSINESS_REPOSITORY=.*/USE_BUSINESS_REPOSITORY=false/' .env
else
    echo "USE_BUSINESS_REPOSITORY=false" >> .env
fi

# Clean up backup files (macOS creates .bak files)
rm -f .env.bak

echo ""
echo "✅ Step 1 configuration complete!"
echo ""
echo "📋 Current flags:"
grep "USE_.*_REPOSITORY" .env || echo "  (no flags found)"
echo ""
echo "🔄 Next steps:"
echo "1. Restart Flask server:"
echo "   python3 src/main.py"
echo ""
echo "2. Test in another terminal:"
echo "   curl http://localhost:8000/api/business/YOUR_BUSINESS_ID/external/reviews"
echo ""
echo "3. Monitor for 15-30 minutes for errors"
