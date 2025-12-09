# Развертывание SEO-анализатора без Docker

## Быстрый старт

1. **Восстановите бэкап сервера** (если еще не сделали)

2. **Загрузите код на сервер:**
   ```bash
   # На локальной машине
   scp -r . root@YOUR_SERVER_IP:/tmp/seo-bot/
   
   # На сервере
   mv /tmp/seo-bot /opt/seo-bot/app
   ```

3. **Запустите развертывание:**
   ```bash
   cd /opt/seo-bot/app
   chmod +x deploy.sh
   sudo ./deploy.sh
   ```

## Ручное развертывание

Если автоматический скрипт не подходит, выполните команды вручную:

### 1. Подготовка системы
```bash
# Обновляем систему
apt update && apt upgrade -y

# Устанавливаем зависимости
apt install -y python3 python3-venv python3-pip nginx git curl wget

# Останавливаем Docker
systemctl stop docker docker.socket containerd 2>/dev/null || true
systemctl disable docker docker.socket containerd 2>/dev/null || true
```

### 2. Настройка swap
```bash
# Создаем swap (2GB)
fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

### 3. Установка Python зависимостей
```bash
# Создаем директорию
mkdir -p /opt/seo-bot/app
cd /opt/seo-bot/app

# Клонируем репозиторий (замените URL)
git clone <YOUR_REPO_URL> .

# Создаем виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Устанавливаем зависимости
pip install --upgrade pip
pip install -r requirements.txt

# Устанавливаем браузеры для Playwright
python -m playwright install chromium
```

### 4. Настройка systemd сервисов
```bash
# Копируем сервисы
cp seo-api.service /etc/systemd/system/
cp seo-download.service /etc/systemd/system/
cp seo-worker.service /etc/systemd/system/

# Перезагружаем systemd
systemctl daemon-reload

# Включаем и запускаем сервисы
systemctl enable seo-api.service
systemctl enable seo-download.service
# systemctl enable seo-worker.service  # Если нужен воркер

systemctl start seo-api.service
systemctl start seo-download.service
# systemctl start seo-worker.service  # Если нужен воркер
```

### 5. Настройка nginx
```bash
# Копируем конфигурацию
cp nginx-config.conf /etc/nginx/sites-available/seo-bot
ln -sf /etc/nginx/sites-available/seo-bot /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверяем и перезапускаем nginx
nginx -t
systemctl restart nginx
```

## Проверка работы

### Проверка сервисов
```bash
# Статус сервисов
systemctl status seo-api.service
systemctl status seo-download.service

# Логи
journalctl -u seo-api -f
journalctl -u seo-download -f
```

### Проверка портов
```bash
ss -tulpn | grep -E ':80|:8000|:8001'
```

### Проверка веб-интерфейса
- Откройте в браузере: `http://YOUR_SERVER_IP`
- API: `http://YOUR_SERVER_IP/api/analyze`
- Health check: `http://YOUR_SERVER_IP/health`

## Управление сервисами

### Основные команды
```bash
# Перезапуск сервисов
systemctl restart seo-api.service
systemctl restart seo-download.service

# Остановка сервисов
systemctl stop seo-api.service
systemctl stop seo-download.service

# Просмотр логов
journalctl -u seo-api -n 100
journalctl -u seo-download -n 100
```

### Обновление кода
```bash
cd /opt/seo-bot/app
git pull
systemctl restart seo-api seo-download
```

## Мониторинг

### Проверка использования памяти
```bash
free -h
htop
```

### Проверка дискового пространства
```bash
df -h
du -sh /opt/seo-bot/app/reports.db
```

### Проверка логов на ошибки
```bash
journalctl -u seo-api --since "1 hour ago" | grep -i error
journalctl -u seo-download --since "1 hour ago" | grep -i error
```

## Устранение проблем

### Если сервисы не запускаются
```bash
# Проверяем статус
systemctl status seo-api.service

# Смотрим логи
journalctl -u seo-api -n 50

# Проверяем права доступа
ls -la /opt/seo-bot/app/
```

### Если не хватает памяти
```bash
# Увеличиваем swap
swapoff /swapfile
fallocate -l 4G /swapfile
mkswap /swapfile
swapon /swapfile
```

### Если nginx не работает
```bash
# Проверяем конфигурацию
nginx -t

# Перезапускаем
systemctl restart nginx

# Проверяем логи
journalctl -u nginx -n 50
```

## Архитектура без Docker

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx :80     │────│  API :8000      │    │ Download :8001  │
│   (Frontend)    │    │  (main.py)      │    │ (download_server)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    ┌────▼────┐              ┌───▼───┐               ┌────▼────┐
    │ Static  │              │ SQLite│               │ Reports │
    │ Files   │              │ DB    │               │ Files   │
    └─────────┘              └───────┘               └─────────┘
```

## Преимущества без Docker

- ✅ Меньше потребление памяти (нет overhead контейнеров)
- ✅ Проще отладка и мониторинг
- ✅ Прямой доступ к логам systemd
- ✅ Автоматический перезапуск при сбоях
- ✅ Простое обновление через git pull

## Недостатки

- ❌ Нет изоляции процессов
- ❌ Сложнее масштабирование
- ❌ Зависимость от системных библиотек
