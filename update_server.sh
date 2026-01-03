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

# 0. Проверить статус ботов
echo -e "${YELLOW}🤖 Проверяю статус ботов...${NC}"
systemctl status telegram-bot telegram-reviews-bot --no-pager | head -3 || echo "⚠️  Боты не настроены"

# 1. Получить последние изменения (если используется git)
if [ -d ".git" ]; then
    echo -e "${YELLOW}📥 Получаю последние изменения из git...${NC}"
    git pull origin main || echo -e "${YELLOW}⚠️  Git pull не выполнен (возможно нет изменений)${NC}"
else
    echo -e "${YELLOW}⚠️  Git репозиторий не найден, пропускаю git pull${NC}"
fi

# 2. Применить миграции БД (если есть)
echo -e "${YELLOW}🗄️  Проверяю миграции БД...${NC}"
if [ -f "src/migrate_clientinfo_add_business_id.py" ]; then
    echo -e "${YELLOW}📦 Создаю бэкап БД...${NC}"
    python src/safe_db_utils.py || cp src/reports.db db_backups/reports_$(date +%Y%m%d_%H%M%S).db.backup
    
    echo -e "${YELLOW}🔄 Применяю миграцию ClientInfo...${NC}"
    python src/migrate_clientinfo_add_business_id.py || echo -e "${YELLOW}⚠️  Миграция не применена (возможно уже применена)${NC}"
    
    echo -e "${YELLOW}✅ Проверяю структуру таблицы ClientInfo...${NC}"
    sqlite3 src/reports.db "PRAGMA table_info(ClientInfo);" | grep business_id && echo -e "${GREEN}✅ Колонка business_id существует${NC}" || echo -e "${YELLOW}⚠️  Колонка business_id не найдена${NC}"
else
    echo -e "${YELLOW}⚠️  Миграция migrate_clientinfo_add_business_id.py не найдена${NC}"
fi

# 3. Пересобрать фронтенд
echo -e "${YELLOW}🏗️  Пересобираю фронтенд...${NC}"
cd frontend
npm install --silent
npm run build
cd ..
echo -e "${GREEN}✅ Фронтенд пересобран${NC}"

# 4. Проверить что сборка прошла успешно
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${RED}❌ Ошибка: frontend/dist/index.html не найден${NC}"
    exit 1
fi

# 5. Перезапустить Flask API
echo -e "${YELLOW}🔄 Перезапускаю Flask API...${NC}"
# Остановить старые процессы
pkill -9 -f "python.*main.py" 2>/dev/null || true
pkill -9 -f "python.*worker.py" 2>/dev/null || true
sleep 2

# Проверить, что порт свободен
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Порт 8000 всё ещё занят, пытаюсь освободить...${NC}"
    sleep 2
fi

# Запустить через systemd (если настроен) или напрямую
if systemctl is-enabled seo-worker >/dev/null 2>&1; then
    systemctl restart seo-worker
    echo -e "${GREEN}✅ Flask API перезапущен через systemd${NC}"
else
    # Запустить напрямую
    source venv/bin/activate
    python src/main.py >/tmp/seo_main.out 2>&1 &
    sleep 3
    echo -e "${GREEN}✅ Flask API запущен напрямую${NC}"
fi

# 6. Перезапустить Telegram боты (ТОЛЬКО если изменялись файлы ботов)
# Раскомментируйте, если нужно перезапустить боты:
# echo -e "${YELLOW}🔄 Перезапускаю Telegram боты...${NC}"
# systemctl restart telegram-bot
# systemctl restart telegram-reviews-bot
# echo -e "${GREEN}✅ Telegram боты перезапущены${NC}"

# 7. Проверить статус сервисов
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

# 8. Проверить порты
echo ""
echo -e "${YELLOW}🔌 Проверяю порты...${NC}"
echo "=== Порт 8000 (Flask API) ==="
lsof -i :8000 || echo "⚠️  Порт 8000 не слушается"
echo ""
echo "=== Порт 80 (Nginx HTTP) ==="
lsof -i :80 || echo "⚠️  Порт 80 не слушается"

# 9. Проверить API
echo ""
echo -e "${YELLOW}🌐 Проверяю API...${NC}"
API_RESPONSE=$(curl -s http://localhost:8000/api/health 2>&1 | head -c 100)
if [ -n "$API_RESPONSE" ]; then
    echo -e "${GREEN}✅ API отвечает: $API_RESPONSE${NC}"
else
    echo -e "${RED}❌ API не отвечает${NC}"
fi

# 10. Показать последние логи
echo ""
echo -e "${YELLOW}📋 Последние логи seo-worker:${NC}"
if systemctl is-active seo-worker >/dev/null 2>&1; then
    journalctl -u seo-worker -n 10 --no-pager || echo "⚠️  Логи недоступны"
else
    tail -20 /tmp/seo_main.out || echo "⚠️  Логи недоступны"
fi

# 11. Проверить, что боты всё ещё работают
echo ""
echo -e "${YELLOW}🤖 Проверяю статус ботов после обновления...${NC}"
systemctl status telegram-bot telegram-reviews-bot --no-pager | head -3 || echo "⚠️  Боты не настроены"

echo ""
echo -e "${GREEN}✅ Обновление завершено!${NC}"
echo ""
echo "Проверьте работу проекта:"
echo "  - Frontend: http://80.78.242.105"
echo "  - API: http://80.78.242.105:8000/api/health"
