# 🔍 Получить полную ошибку из Flask

## Проблема
Ошибка 500, но traceback не виден. Нужно увидеть полную ошибку.

## Решение на сервере

```bash
ssh root@80.78.242.105

# 1. Сделать тестовый запрос и сразу проверить логи
# Сначала получите токен из браузера (F12 -> Application -> Local Storage -> auth_token)
TOKEN="ваш_токен_из_браузера"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/client-info?business_id=38a11c0e-6eea-4fdc-90d6-66f21af9adce" \
  2>&1 | head -20

# 2. Сразу проверить логи Flask
tail -100 /tmp/seo_main.out | tail -50

# 3. Проверить, есть ли traceback в логах
tail -200 /tmp/seo_main.out | grep -A 30 "Traceback\|ERROR\|Exception\|business_id"

# 4. Если traceback не виден, проверить stderr
# Flask может логировать в stderr, а не в stdout
# Проверить, куда идут логи:
ps aux | grep "python.*main.py" | grep -v grep

# 5. Перезапустить Flask с явным логированием stderr
pkill -9 -f "python.*main.py"
sleep 2
cd /root/mapsparser-Replit-front
source venv/bin/activate
python src/main.py >/tmp/seo_main.out 2>&1 &
sleep 3

# 6. Сделать запрос снова и проверить логи
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/client-info?business_id=38a11c0e-6eea-4fdc-90d6-66f21af9adce" \
  2>&1

tail -100 /tmp/seo_main.out
```

## Альтернатива: Добавить логирование в код

Если traceback не виден, можно временно добавить больше логирования в код, чтобы увидеть, где именно происходит ошибка.

