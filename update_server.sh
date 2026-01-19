#!/bin/bash
set -e

echo "🚀 Starting server update..."

# 1. Update code
echo "📥 Pulling latest changes..."
git pull origin main

# 2. Build Frontend
echo "🏗️ Building frontend..."
cd frontend
npm install
npm run build
cd ..

# 3. Restart Backend (optional, but good practice if any python files changed)
# echo "🔄 Restarting backend service..."
# systemctl restart seo-worker || echo "Warning: Could not restart seo-worker"

echo "✅ Update completed successfully!"
