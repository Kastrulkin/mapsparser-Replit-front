# Запуск Flask сервера

> 📖 **Для локальной разработки**: см. [LOCAL_DEV.md](../LOCAL_DEV.md) — используйте скрипты `scripts/run_web.sh` и `scripts/run_worker.sh`

## Проблема (Production)
Flask сервер не запущен, поэтому nginx возвращает 502 Bad Gateway.

## Решение

### Вариант 1: Через systemd (РЕКОМЕНДУЕТСЯ - согласно инструкции SERVER_UPDATE_COMMANDS.md)
```bash
ssh root@80.78.242.105 "systemctl restart seo-worker && sleep 3 && systemctl status seo-worker"
```

### Вариант 2: Проверить статус и логи systemd
```bash
ssh root@80.78.242.105 "systemctl status seo-worker && echo '' && journalctl -u seo-worker -n 30 --no-pager"
```

### Вариант 3: Запуск вручную (только если systemd не работает)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && nohup python src/main.py > /tmp/seo_main.out 2>&1 & sleep 3 && lsof -iTCP:8000 -sTCP:LISTEN"
```

### Вариант 4: С проверкой ошибок (для диагностики)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && timeout 10 python src/main.py 2>&1 | head -50"
```

### Вариант 4: Полный перезапуск с очисткой
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && pkill -f 'python.*main.py' && sleep 2 && source venv/bin/activate && nohup python src/main.py > /tmp/seo_main.out 2>&1 & sleep 5 && echo '=== Статус ===' && ps aux | grep 'python.*main.py' | grep -v grep && echo '' && echo '=== Порт ===' && lsof -iTCP:8000 -sTCP:LISTEN && echo '' && echo '=== Логи (последние 10 строк) ===' && tail -10 /tmp/seo_main.out"
```

## Проверка после запуска

```bash
ssh root@80.78.242.105 "curl -s http://localhost:8000/api/health 2>&1 || curl -s http://localhost:8000/ 2>&1 | head -5"
```

## Настройка автозапуска (systemd)

Если нужно, чтобы Flask запускался автоматически при перезагрузке сервера:

```bash
ssh root@80.78.242.105 "cat > /etc/systemd/system/seo-main.service << 'EOF'
[Unit]
Description=SEO Analyzer Flask Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/mapsparser-Replit-front
Environment=\"PATH=/root/mapsparser-Replit-front/venv/bin\"
ExecStart=/root/mapsparser-Replit-front/venv/bin/python src/main.py
Restart=always
RestartSec=10
StandardOutput=append:/tmp/seo_main.out
StandardError=append:/tmp/seo_main.out

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable seo-main && systemctl start seo-main && systemctl status seo-main"
```

