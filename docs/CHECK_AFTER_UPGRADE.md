# Проверка сервера после апгрейда

## Новые характеристики
- **CPU**: 2 vCPU ✅
- **RAM**: 4 ГБ ✅
- **Диск**: 20 ГБ ✅

## Команды для проверки

### 1. Проверить использование ресурсов
```bash
# Память
free -h

# CPU и нагрузка
uptime
top -bn1 | head -10

# Процессы
ps aux --sort=-%mem | head -10
```

### 2. Перезапустить процессы для использования новых ресурсов
```bash
cd /root/mapsparser-Replit-front

# Перезапустить Flask сервер
pkill -f 'python.*main.py' 2>/dev/null
sleep 2
source venv/bin/activate
nohup python src/main.py > /tmp/seo_main.out 2>&1 &

# Перезапустить worker (если используется systemd)
systemctl restart seo-worker

# Проверить статус
sleep 3
lsof -iTCP:8000 -sTCP:LISTEN
systemctl status seo-worker
```

### 3. Проверить, что всё работает
```bash
# Проверить Flask
curl -s http://localhost:8000/ | head -5

# Проверить логи
tail -20 /tmp/seo_main.out

# Проверить использование ресурсов
free -h
uptime
```

## Ожидаемые результаты

### Память
- **До апгрейда**: ~90-100% использования (1 ГБ)
- **После апгрейда**: ~30-50% использования (4 ГБ) ✅

### CPU
- **До апгрейда**: часто 100% (1 ядро)
- **После апгрейда**: ~30-60% (2 ядра) ✅

### Процессы
- Flask сервер должен работать стабильно
- Worker не должен зависать
- Сборка фронтенда должна проходить без проблем

## Если проблемы остались

1. Проверить, что процессы перезапущены:
```bash
ps aux | grep python | grep -v grep
```

2. Проверить логи на ошибки:
```bash
tail -50 /tmp/seo_main.out | grep -i error
journalctl -u seo-worker -n 50 | grep -i error
```

3. Очистить старые файлы:
```bash
cd /root/mapsparser-Replit-front
bash scripts/cleanup_server_files.sh
```

