# Проверка статуса Flask сервера

## Команды для проверки

### 1. Проверить, запущен ли Flask процесс
```bash
ssh root@80.78.242.105 "ps aux | grep 'python.*main.py' | grep -v grep"
```

### 2. Проверить порт 8000
```bash
ssh root@80.78.242.105 "lsof -iTCP:8000 -sTCP:LISTEN"
```

### 3. Проверить логи Flask
```bash
ssh root@80.78.242.105 "tail -30 /tmp/seo_main.out"
```

### 4. Полная проверка одной командой
```bash
ssh root@80.78.242.105 "echo '=== Flask процесс ===' && ps aux | grep 'python.*main.py' | grep -v grep && echo '' && echo '=== Порт 8000 ===' && lsof -iTCP:8000 -sTCP:LISTEN 2>&1 && echo '' && echo '=== Последние логи ===' && tail -20 /tmp/seo_main.out 2>&1"
```

### 5. Если Flask не запущен - запустить с выводом ошибок
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && timeout 10 python src/main.py 2>&1 | head -50"
```

