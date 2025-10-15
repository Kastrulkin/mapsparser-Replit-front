#!/bin/bash

# Скрипт развертывания SEO-анализатора без Docker
# Использование: ./deploy.sh

set -e

echo "🚀 Начинаем развертывание SEO-анализатора..."

# Проверяем, что мы на сервере
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт с правами root: sudo ./deploy.sh"
    exit 1
fi

# Обновляем систему
echo "📦 Обновляем систему..."
apt update && apt upgrade -y

# Устанавливаем необходимые пакеты
echo "🔧 Устанавливаем зависимости..."
apt install -y python3 python3-venv python3-pip nginx git curl wget

# Останавливаем Docker (если запущен)
echo "🛑 Останавливаем Docker..."
systemctl stop docker docker.socket containerd 2>/dev/null || true
systemctl disable docker docker.socket containerd 2>/dev/null || true

# Создаем swap (если не существует)
echo "💾 Настраиваем swap..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "✅ Swap создан (2GB)"
else
    echo "✅ Swap уже существует"
fi

# Создаем директорию проекта
echo "📁 Создаем директорию проекта..."
mkdir -p /opt/seo-bot
cd /opt/seo-bot

# Клонируем или обновляем репозиторий
if [ -d "app" ]; then
    echo "🔄 Обновляем код..."
    cd app
    git pull
    cd ..
else
    echo "📥 Клонируем репозиторий..."
    # Замените на ваш URL репозитория
    echo "⚠️  ВНИМАНИЕ: Замените URL репозитория в скрипте!"
    # git clone <YOUR_REPO_URL> app
    echo "❌ Пожалуйста, склонируйте репозиторий вручную:"
    echo "   git clone <YOUR_REPO_URL> app"
    exit 1
fi

# Создаем виртуальное окружение
echo "🐍 Настраиваем Python окружение..."
cd /opt/seo-bot/app
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
echo "📚 Устанавливаем Python зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

# Устанавливаем playwright браузеры
echo "🌐 Устанавливаем браузеры для Playwright..."
python -m playwright install chromium

# Копируем systemd сервисы
echo "⚙️  Настраиваем systemd сервисы..."
cp seo-api.service /etc/systemd/system/
cp seo-download.service /etc/systemd/system/
cp seo-worker.service /etc/systemd/system/

# Перезагружаем systemd
systemctl daemon-reload

# Включаем и запускаем сервисы
echo "🚀 Запускаем сервисы..."
systemctl enable seo-api.service
systemctl enable seo-download.service
# systemctl enable seo-worker.service  # Раскомментируйте если нужен воркер

systemctl start seo-api.service
systemctl start seo-download.service
# systemctl start seo-worker.service  # Раскомментируйте если нужен воркер

# Настраиваем nginx
echo "🌐 Настраиваем nginx..."
cp nginx-config.conf /etc/nginx/sites-available/seo-bot
ln -sf /etc/nginx/sites-available/seo-bot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверяем конфигурацию nginx
nginx -t

# Перезапускаем nginx
systemctl restart nginx

# Проверяем статус сервисов
echo "🔍 Проверяем статус сервисов..."
systemctl status seo-api.service --no-pager
systemctl status seo-download.service --no-pager

# Проверяем порты
echo "🔌 Проверяем порты..."
ss -tulpn | grep -E ':80|:8000|:8001'

echo ""
echo "✅ Развертывание завершено!"
echo ""
echo "🌐 Веб-интерфейс: http://$(curl -s ifconfig.me)"
echo "🔧 API: http://$(curl -s ifconfig.me)/api/analyze"
echo "📊 Health check: http://$(curl -s ifconfig.me)/health"
echo ""
echo "📋 Полезные команды:"
echo "   systemctl status seo-api.service"
echo "   systemctl status seo-download.service"
echo "   journalctl -u seo-api -f"
echo "   journalctl -u seo-download -f"
echo ""
echo "🔄 Для обновления кода:"
echo "   cd /opt/seo-bot/app && git pull && systemctl restart seo-api seo-download"
