# Исправление 502 Bad Gateway

## Проблема
502 Bad Gateway означает, что nginx не может подключиться к Flask серверу.

## Диагностика

### 1. Проверить, запущен ли Flask
```bash
ssh root@80.78.242.105 "ps aux | grep 'python.*main.py' | grep -v grep"
```

### 2. Проверить порт 8000
```bash
ssh root@80.78.242.105 "lsof -iTCP:8000 -sTCP:LISTEN"
```

### 3. Проверить логи Flask
```bash
ssh root@80.78.242.105 "tail -50 /tmp/seo_main.out"
```

### 4. Проверить конфигурацию nginx
```bash
ssh root@80.78.242.105 "cat /etc/nginx/sites-available/beautybot.pro 2>/dev/null || cat /etc/nginx/sites-enabled/beautybot.pro 2>/dev/null || cat /etc/nginx/nginx.conf | grep -A 20 beautybot"
```

## Решения

### Решение 1: Перезапустить через systemd (РЕКОМЕНДУЕТСЯ - согласно инструкции SERVER_UPDATE_COMMANDS.md)
```bash
ssh root@80.78.242.105 "systemctl restart seo-worker && sleep 3 && systemctl status seo-worker"
```

### Решение 2: Проверить, почему systemd не работает
```bash
ssh root@80.78.242.105 "systemctl status seo-worker && journalctl -u seo-worker -n 30 --no-pager"
```

### Решение 3: Запустить Flask сервер вручную (только если systemd не работает)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && nohup python src/main.py > /tmp/seo_main.out 2>&1 &"
```

### Решение 3: Проверить и исправить конфигурацию nginx
```bash
ssh root@80.78.242.105 "cat /etc/nginx/sites-enabled/default | grep -A 10 'location /'"
```

Nginx должен проксировать на `http://127.0.0.1:8000` или `http://localhost:8000`

### Решение 4: Перезапустить nginx
```bash
ssh root@80.78.242.105 "systemctl restart nginx && systemctl status nginx"
```

## Полная диагностика одной командой
```bash
ssh root@80.78.242.105 "echo '=== Flask процесс ===' && ps aux | grep 'python.*main.py' | grep -v grep && echo '' && echo '=== Порт 8000 ===' && lsof -iTCP:8000 -sTCP:LISTEN 2>&1 && echo '' && echo '=== Последние логи Flask ===' && tail -20 /tmp/seo_main.out 2>&1"
```

## Быстрое исправление
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && pkill -f 'python.*main.py' && sleep 2 && nohup python src/main.py > /tmp/seo_main.out 2>&1 & sleep 3 && lsof -iTCP:8000 -sTCP:LISTEN"
```

