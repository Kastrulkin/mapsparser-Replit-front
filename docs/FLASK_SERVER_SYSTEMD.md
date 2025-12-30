# Запуск Flask сервера (main.py) через systemd

## Проблема
`seo-worker` запускает только `worker.py`, но не Flask сервер (`main.py`). Flask сервер нужно запускать отдельно.

## Решение

### Вариант 1: Проверить, есть ли systemd сервис для Flask
```bash
ssh root@80.78.242.105 "systemctl list-units | grep -E 'seo|flask|main|beautybot'"
```

### Вариант 2: Запустить Flask вручную (согласно инструкции SERVER_UPDATE_COMMANDS.md)
```bash
ssh root@80.78.242.105 "cd /root/mapsparser-Replit-front && source venv/bin/activate && pkill -f 'python.*main.py' 2>/dev/null; sleep 2 && nohup python src/main.py > /tmp/seo_main.out 2>&1 & sleep 3 && lsof -iTCP:8000 -sTCP:LISTEN"
```

### Вариант 3: Создать systemd сервис для Flask (рекомендуется для production)
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

## Проверка после запуска
```bash
ssh root@80.78.242.105 "lsof -iTCP:8000 -sTCP:LISTEN && echo '' && tail -10 /tmp/seo_main.out"
```

