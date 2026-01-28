#!/bin/bash
set -e

# Deployment script for beautybot.pro

echo "🚀 Starting server update (Full Algorithm)..."
echo "📅 Date: $(date)"
echo ""

# 1. Update Code
echo "📥 1. Pulling latest changes from GitHub..."
git pull origin main

# 2. Frontend Update
echo "📦 2. Updating Frontend..."
cd frontend
echo "   - Installing dependencies..."
npm install --legacy-peer-deps

echo "   - Building project..."
rm -rf dist
npm run build

# Check if build was successful
if [ ! -d "dist" ]; then
    echo "❌ Build failed! 'dist' directory not found."
    exit 1
fi

echo "   - Copying files to /var/www/html..."
# Ensure destination exists
mkdir -p /var/www/html
rm -rf /var/www/html/*
cp -r dist/* /var/www/html/
chown -R www-data:www-data /var/www/html
chmod -R 755 /var/www/html
cd ..

# 3. Backend Update (Restart Services)
echo "🔄 3. Restarting Backend Services..."
# Restart seo-worker if it exists
if systemctl list-units --full -all | grep -q "seo-worker.service"; then
    echo "   - Restarting seo-worker..."
    systemctl restart seo-worker
fi

# Restart beautybot-worker if it exists
if systemctl list-units --full -all | grep -q "beautybot-worker.service"; then
    echo "   - Restarting beautybot-worker..."
    systemctl restart beautybot-worker
fi

# Restart seo-api if it exists
if systemctl list-units --full -all | grep -q "seo-api.service"; then
    echo "   - Restarting seo-api..."
    systemctl restart seo-api
fi

# Restart beautybot-backend if it exists
if systemctl list-units --full -all | grep -q "beautybot-backend.service"; then
    echo "   - Restarting beautybot-backend..."
    systemctl restart beautybot-backend
fi

# 4. Nginx Update
echo "🌐 4. updating Nginx..."
echo "   - Reloading configuration..."
systemctl reload nginx
echo "   - Clearing Nginx cache..."
rm -rf /var/cache/nginx/*

echo ""
echo "✅ Update completed successfully!"
echo "👉 Please clear your browser cache (Cmd+Shift+R) to see changes."
