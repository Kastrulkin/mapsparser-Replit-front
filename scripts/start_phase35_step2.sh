#!/bin/bash
# Configure environment for Phase 3.5 Step 2: USE_SERVICE_REPOSITORY

set -e

echo "🚀 Configuring Phase 3.5 Step 2: USE_SERVICE_REPOSITORY"
echo "========================================================"

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  .env file not found, creating..."
    touch .env
fi

# Backup .env
cp .env .env.backup.$(date +%Y%m%d_%H%M%S)

# Update or add flags
if grep -q "USE_SERVICE_REPOSITORY" .env; then
    sed -i.bak 's/^USE_SERVICE_REPOSITORY=.*/USE_SERVICE_REPOSITORY=true/' .env
    echo "✅ Updated USE_SERVICE_REPOSITORY=true"
else
    echo "" >> .env
    echo "# Phase 3.5 Repository Pattern - Step 2" >> .env
    echo "USE_SERVICE_REPOSITORY=true" >> .env
    echo "✅ Added USE_SERVICE_REPOSITORY=true"
fi

# Ensure other flags are set correctly
if ! grep -q "USE_REVIEW_REPOSITORY" .env; then
    echo "USE_REVIEW_REPOSITORY=true" >> .env
    echo "✅ Added USE_REVIEW_REPOSITORY=true (Step 1)"
fi

if ! grep -q "USE_BUSINESS_REPOSITORY" .env; then
    echo "USE_BUSINESS_REPOSITORY=false" >> .env
    echo "✅ Added USE_BUSINESS_REPOSITORY=false (Step 3 - not yet)"
fi

# Ensure USE_REVIEW_REPOSITORY is true (Step 1 should be active)
if grep -q "^USE_REVIEW_REPOSITORY=" .env; then
    sed -i.bak 's/^USE_REVIEW_REPOSITORY=.*/USE_REVIEW_REPOSITORY=true/' .env
fi

# Ensure USE_BUSINESS_REPOSITORY is false (Step 3 not yet)
if grep -q "^USE_BUSINESS_REPOSITORY=" .env; then
    sed -i.bak 's/^USE_BUSINESS_REPOSITORY=.*/USE_BUSINESS_REPOSITORY=false/' .env
fi

echo ""
echo "✅ Configuration complete!"
echo ""
echo "Current flags:"
grep "USE_.*_REPOSITORY" .env | grep -v "^#"
echo ""
echo "⚠️  IMPORTANT: Before starting Step 2, verify:"
echo "   1. FK constraints are in place (see PHASE_3_5_STEP2_GUIDE.md)"
echo "   2. No orphaned records in UserServices"
echo "   3. Step 1 has been stable for at least 24 hours"
echo ""
echo "Next steps:"
echo "   1. Verify prerequisites (see guide)"
echo "   2. Start Flask: python3 src/main.py"
echo "   3. Test: ./scripts/test_phase35_step2.sh"
