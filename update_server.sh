#!/bin/bash
# Скрипт для обновления проекта на сервере 80.78.242.105
# Использование: ./update_server.sh или bash update_server.sh

set -e  # Остановка при ошибке

echo "🔄 Начинаю обновление проекта на сервере..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка что мы на сервере (или в правильной директории)
PROJECT_DIR="/root/mapsparser-Replit-front"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ Директория проекта не найдена: $PROJECT_DIR${NC}"
    echo "Убедитесь, что вы находитесь на сервере или измените PROJECT_DIR в скрипте"
    exit 1
fi

cd "$PROJECT_DIR"
echo -e "${GREEN}✅ Перешел в директорию проекта${NC}"

# 1. Получить последние изменения (если используется git)
if [ -d ".git" ]; then
    echo -e "${YELLOW}📥 Получаю последние изменения из git...${NC}"
    git pull origin main || echo -e "${YELLOW}⚠️  Git pull не выполнен (возможно нет изменений)${NC}"
else
    echo -e "${YELLOW}⚠️  Git репозиторий не найден, пропускаю git pull${NC}"
fi

# 2. Пересобрать фронтенд
echo -e "${YELLOW}🏗️  Пересобираю фронтенд...${NC}"
cd frontend
npm install --silent
npm run build
cd ..
echo -e "${GREEN}✅ Фронтенд пересобран${NC}"

# 3. Проверить что сборка прошла успешно
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${RED}❌ Ошибка: frontend/dist/index.html не найден${NC}"
    exit 1
fi

# 4. Перезапустить сервисы
echo -e "${YELLOW}🔄 Перезапускаю сервисы...${NC}"
systemctl restart seo-worker
systemctl restart telegram-bot
systemctl restart telegram-reviews-bot
echo -e "${GREEN}✅ Сервисы перезапущены${NC}"

# 5. Проверить статус сервисов
echo -e "${YELLOW}📊 Проверяю статус сервисов...${NC}"
echo ""
echo "=== seo-worker ==="
systemctl status seo-worker --no-pager | head -5
echo ""
echo "=== telegram-bot ==="
systemctl status telegram-bot --no-pager | head -5
echo ""
echo "=== telegram-reviews-bot ==="
systemctl status telegram-reviews-bot --no-pager | head -5
echo ""
echo "=== nginx ==="
systemctl status nginx --no-pager | head -5

# 6. Проверить порты
echo ""
echo -e "${YELLOW}🔌 Проверяю порты...${NC}"
echo "=== Порт 8000 (Flask API) ==="
lsof -i :8000 || echo "⚠️  Порт 8000 не слушается"
echo ""
echo "=== Порт 80 (Nginx HTTP) ==="
lsof -i :80 || echo "⚠️  Порт 80 не слушается"

# 7. Проверить API
echo ""
echo -e "${YELLOW}🌐 Проверяю API...${NC}"
API_RESPONSE=$(curl -s http://localhost:8000/api/health 2>&1 | head -c 100)
if [ -n "$API_RESPONSE" ]; then
    echo -e "${GREEN}✅ API отвечает: $API_RESPONSE${NC}"
else
    echo -e "${RED}❌ API не отвечает${NC}"
fi

# 8. Показать последние логи
echo ""
echo -e "${YELLOW}📋 Последние логи seo-worker:${NC}"
journalctl -u seo-worker -n 10 --no-pager || echo "⚠️  Логи недоступны"

echo ""
echo -e "${GREEN}✅ Обновление завершено!${NC}"
echo ""
echo "Проверьте работу проекта:"
echo "  - Frontend: http://80.78.242.105"
echo "  - API: http://80.78.242.105:8000/api/health"
