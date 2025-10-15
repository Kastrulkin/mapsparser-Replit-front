#!/bin/bash

echo "🔍 Проверка Docker..."

# Проверяем Docker
if command -v docker &> /dev/null; then
    echo "✅ Docker установлен: $(docker --version)"
else
    echo "❌ Docker не установлен"
    echo "📖 Инструкции по установке: INSTALL_DOCKER.md"
    exit 1
fi

# Проверяем Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose установлен: $(docker-compose --version)"
elif docker compose version &> /dev/null; then
    echo "✅ Docker Compose (новый) установлен: $(docker compose version)"
else
    echo "❌ Docker Compose не установлен"
    echo "📖 Инструкции по установке: INSTALL_DOCKER.md"
    exit 1
fi

# Проверяем, запущен ли Docker daemon
if docker info &> /dev/null; then
    echo "✅ Docker daemon запущен"
else
    echo "❌ Docker daemon не запущен"
    echo "💡 Запустите Docker Desktop или выполните: sudo systemctl start docker"
    exit 1
fi

echo ""
echo "🎉 Docker готов к работе!"
echo "🚀 Теперь можете запустить: ./docker-run.sh build"
