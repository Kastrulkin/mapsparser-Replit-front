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

# 2. Определить путь к Python из venv
PYTHON_BIN="${PROJECT_DIR}/venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    # Попробовать python3 как fallback
    PYTHON_BIN=$(which python3 || which python || echo "python3")
    echo -e "${YELLOW}⚠️  venv/bin/python не найден, использую: $PYTHON_BIN${NC}"
fi

# 3. Применить миграции БД (если есть)
echo -e "${YELLOW}🗄️  Проверяю миграции БД...${NC}"
if [ -f "src/migrate_clientinfo_add_business_id.py" ]; then
    echo -e "${YELLOW}📦 Создаю бэкап БД...${NC}"
    $PYTHON_BIN src/safe_db_utils.py 2>/dev/null || cp src/reports.db db_backups/reports_$(date +%Y%m%d_%H%M%S).db.backup
    
    echo -e "${YELLOW}🔄 Применяю миграцию ClientInfo...${NC}"
    if $PYTHON_BIN src/migrate_clientinfo_add_business_id.py; then
        echo -e "${GREEN}✅ Миграция применена успешно${NC}"
    else
        echo -e "${YELLOW}⚠️  Миграция не применена (возможно уже применена или ошибка)${NC}"
    fi
    
    echo -e "${YELLOW}✅ Проверяю структуру таблицы ClientInfo...${NC}"
    # Использовать Python для проверки структуры, если sqlite3 недоступен
    if command -v sqlite3 >/dev/null 2>&1; then
        sqlite3 src/reports.db "PRAGMA table_info(ClientInfo);" | grep business_id && echo -e "${GREEN}✅ Колонка business_id существует${NC}" || echo -e "${YELLOW}⚠️  Колонка business_id не найдена${NC}"
    else
        # Проверка через Python
        $PYTHON_BIN -c "
import sqlite3
conn = sqlite3.connect('src/reports.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(ClientInfo)')
columns = [col[1] for col in cursor.fetchall()]
if 'business_id' in columns:
    print('✅ Колонка business_id существует')
else:
    print('⚠️  Колонка business_id не найдена')
    print(f'Доступные колонки: {columns}')
conn.close()
" || echo -e "${YELLOW}⚠️  Не удалось проверить структуру таблицы${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Миграция migrate_clientinfo_add_business_id.py не найдена${NC}"
fi

# 3.1. Исправление профиля tislitskaya
if [ -f "src/scripts/fix_tislitskaya_profile.py" ]; then
    echo -e "${YELLOW}🔧 Запускаю исправление профиля tislitskaya...${NC}"
    $PYTHON_BIN src/scripts/fix_tislitskaya_profile.py
fi

# 4. Пересобрать фронтенд
echo -e "${YELLOW}🏗️  Пересобираю фронтенд...${NC}"
cd frontend
npm install --silent
npm run build
cd ..
echo -e "${GREEN}✅ Фронтенд пересобран${NC}"

# 5. Проверить что сборка прошла успешно
if [ ! -f "frontend/dist/index.html" ]; then
    echo -e "${RED}❌ Ошибка: frontend/dist/index.html не найден${NC}"
    exit 1
fi

# 6. Перезапустить Flask API (main.py)
echo -e "${YELLOW}🔄 Перезапускаю Flask API (main.py)...${NC}"

# Найти процесс Flask API на порту 8000
FLASK_PID=$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || echo "")
if [ -n "$FLASK_PID" ]; then
    echo -e "${YELLOW}Найден процесс Flask на порту 8000 (PID: $FLASK_PID)${NC}"
fi

# Остановить старые процессы main.py (Flask API)
pkill -9 -f "python.*main.py" 2>/dev/null || true
sleep 2

# Проверить, что порт свободен
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Порт 8000 всё ещё занят, пытаюсь освободить...${NC}"
    pkill -9 -f "python.*main.py" 2>/dev/null || true
    sleep 2
fi

# Перезапустить через systemd (если настроен seo-api) или напрямую
if systemctl is-enabled seo-api >/dev/null 2>&1; then
    # seo-api.service запускает main.py
    systemctl restart seo-api
    echo -e "${GREEN}✅ Flask API перезапущен через systemd (seo-api.service)${NC}"
elif systemctl is-enabled seo-worker >/dev/null 2>&1; then
    # seo-worker запускает worker.py, но проверим, может он тоже запускает main.py
    # В любом случае, перезапустим worker (для обработки очереди)
    systemctl restart seo-worker
    echo -e "${YELLOW}⚠️  seo-worker перезапущен (но он запускает worker.py, не main.py)${NC}"
    echo -e "${YELLOW}Запускаю main.py напрямую...${NC}"
    source venv/bin/activate
    $PYTHON_BIN src/main.py >/tmp/seo_main.out 2>&1 &
    sleep 3
    echo -e "${GREEN}✅ Flask API (main.py) запущен напрямую${NC}"
else
    # Запустить напрямую
    source venv/bin/activate
    $PYTHON_BIN src/main.py >/tmp/seo_main.out 2>&1 &
    sleep 3
    echo -e "${GREEN}✅ Flask API запущен напрямую${NC}"
fi

# Проверить, что Flask API запустился
sleep 2
if lsof -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
    NEW_PID=$(lsof -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || echo "")
    echo -e "${GREEN}✅ Flask API запущен на порту 8000 (PID: $NEW_PID)${NC}"
else
    echo -e "${RED}❌ Flask API не запустился на порту 8000!${NC}"
    echo -e "${YELLOW}Проверьте логи: tail -50 /tmp/seo_main.out${NC}"
fi

# 7. Перезапустить Telegram боты (ТОЛЬКО если изменялись файлы ботов)
# Раскомментируйте, если нужно перезапустить боты:
# echo -e "${YELLOW}🔄 Перезапускаю Telegram боты...${NC}"
# systemctl restart telegram-bot
# systemctl restart telegram-reviews-bot
# echo -e "${GREEN}✅ Telegram боты перезапущены${NC}"

# 8. Проверить статус сервисов
echo -e "${YELLOW}📊 Проверяю статус сервисов...${NC}"
echo ""
echo "=== seo-api (Flask API - main.py) ==="
if systemctl is-enabled seo-api >/dev/null 2>&1; then
    systemctl status seo-api --no-pager | head -5
else
    echo "⚠️  Сервис seo-api не настроен, Flask API запущен напрямую"
    lsof -iTCP:8000 -sTCP:LISTEN || echo "⚠️  Flask API не запущен"
fi
echo ""
echo "=== seo-worker (worker.py) ==="
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

# 9. Проверить порты
echo ""
echo -e "${YELLOW}🔌 Проверяю порты...${NC}"
echo "=== Порт 8000 (Flask API) ==="
lsof -i :8000 || echo "⚠️  Порт 8000 не слушается"
echo ""
echo "=== Порт 80 (Nginx HTTP) ==="
lsof -i :80 || echo "⚠️  Порт 80 не слушается"

# 10. Проверить API
echo ""
echo -e "${YELLOW}🌐 Проверяю API...${NC}"
# Попробовать несколько эндпоинтов
API_RESPONSE=$(curl -s http://localhost:8000/api/health 2>&1 | head -c 200)
if echo "$API_RESPONSE" | grep -q "error\|Not Found"; then
    # Попробовать корневой эндпоинт
    API_RESPONSE=$(curl -s http://localhost:8000/ 2>&1 | head -c 200)
fi
if [ -n "$API_RESPONSE" ] && ! echo "$API_RESPONSE" | grep -q "Connection refused\|Failed to connect"; then
    echo -e "${GREEN}✅ API отвечает: ${API_RESPONSE:0:100}${NC}"
else
    echo -e "${RED}❌ API не отвечает или недоступен${NC}"
    echo -e "${YELLOW}Проверьте логи: journalctl -u seo-worker -n 20${NC}"
fi

# 11. Показать последние логи
echo ""
echo -e "${YELLOW}📋 Последние логи Flask API (main.py):${NC}"
if systemctl is-active seo-api >/dev/null 2>&1; then
    journalctl -u seo-api -n 10 --no-pager || echo "⚠️  Логи недоступны"
elif [ -f "/tmp/seo_main.out" ]; then
    tail -20 /tmp/seo_main.out || echo "⚠️  Логи недоступны"
else
    echo "⚠️  Логи недоступны (файл /tmp/seo_main.out не найден)"
fi

echo ""
echo -e "${YELLOW}📋 Последние логи seo-worker (worker.py):${NC}"
if systemctl is-active seo-worker >/dev/null 2>&1; then
    journalctl -u seo-worker -n 10 --no-pager || echo "⚠️  Логи недоступны"
fi

# 12. Проверить, что боты всё ещё работают
echo ""
echo -e "${YELLOW}🤖 Проверяю статус ботов после обновления...${NC}"
systemctl status telegram-bot telegram-reviews-bot --no-pager | head -3 || echo "⚠️  Боты не настроены"

echo ""
echo -e "${GREEN}✅ Обновление завершено!${NC}"
echo ""
echo "Проверьте работу проекта:"
echo "  - Frontend: http://80.78.242.105"
echo "  - API: http://80.78.242.105:8000/api/health"
