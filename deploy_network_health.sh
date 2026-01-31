#!/bin/bash
set -e

echo "🚀 Deploying Network Health Dashboard & Yandex Growth Strategy..."

# Go to project directory
cd /root/mapsparser-Replit-front

# Verify we have the correct commit
echo "📋 Checking current commit..."
git log --oneline -1

# Verify files exist
echo "✅ Checking required files..."
ls -la frontend/src/components/NetworkHealthDashboard.tsx
ls -la src/api/growth_api.py
ls -la src/scripts/populate_yandex_growth.py

# 1. Update Backend
echo "🐘 Updating Backend..."
# Ensure permissions
chmod +x src/scripts/*.py

# Run database migration (if not already run)
echo "🔄 Running DB Migrations..."
python3 src/scripts/migrate_growth_tasks_schema.py || echo "⚠️ Migration might have already run"

# 2. Update Frontend
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps

echo "🏗️ Building frontend..."
# Force cache busting by creating a unique build identifier
export VITE_BUILD_TIME=$(date +%s)
npm run build

# Check build output
echo "📊 Checking build output..."
ls -lh dist/assets/index-*.js | tail -1

# Copy to Web Root
echo "🚀 Publishing to Nginx..."
rm -rf /var/www/html/*
cp -r dist/* /var/www/html/


# 3. Populate Content
echo "📚 Populating Yandex Growth Content..."
cd ..
python3 src/scripts/populate_yandex_growth.py

# 4. Restart Services
echo "🔄 Restarting services..."
systemctl restart nginx
systemctl restart seo-api  # Assuming the backend service name
systemctl status nginx --no-pager -l | head -10

echo "✅ Deployment complete!"
echo "🌐 Clear browser cache (Ctrl+Shift+R) and reload the page"
