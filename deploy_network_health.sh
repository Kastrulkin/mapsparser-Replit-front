#!/bin/bash
set -e

echo "🚀 Deploying Network Health Dashboard..."

# Go to project directory
cd /root/mapsparser-Replit-front

# Verify we have the correct commit
echo "📋 Checking current commit..."
git log --oneline -1

# Verify files exist
echo "✅ Checking NetworkHealthDashboard.tsx exists..."
ls -la frontend/src/components/NetworkHealthDashboard.tsx

# Install dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install --legacy-peer-deps

# Build frontend
echo "🏗️ Building frontend..."
npm run build

# Check build output
echo "📊 Checking build output..."
ls -lh dist/assets/index-*.js | tail -1

# Restart services
echo "🔄 Restarting services..."
cd ..
systemctl restart nginx
systemctl status nginx --no-pager -l | head -10

echo "✅ Deployment complete!"
echo "🌐 Clear browser cache (Ctrl+Shift+R) and reload the page"
