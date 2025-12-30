# Исправление пропавшего фронтенда

## Проблема
Flask показывает fallback HTML страницу вместо React приложения.

## Причина
Фронтенд не собран или `frontend/dist/` отсутствует на сервере.

## Решение

### Шаг 1: Проверить наличие dist на сервере
```bash
cd /root/mapsparser-Replit-front
ls -la frontend/dist/ 2>/dev/null || echo "Директория dist не существует"
```

### Шаг 2: Если dist отсутствует или пуст - собрать фронтенд
```bash
cd /root/mapsparser-Replit-front/frontend
npm run build
```

### Шаг 3: Проверить, что сборка завершилась успешно
```bash
ls -lh frontend/dist/assets/index-*.js
# Должен быть файл с текущей датой
```

### Шаг 4: Перезапустить Flask
```bash
cd /root/mapsparser-Replit-front
pkill -f 'python.*main.py' 2>/dev/null
sleep 2
source venv/bin/activate
nohup python src/main.py > /tmp/seo_main.out 2>&1 &
sleep 3
```

### Шаг 5: Проверить, что Flask видит dist
```bash
ls -la /root/mapsparser-Replit-front/frontend/dist/index.html
```

## Альтернатива: Собрать локально и загрузить

Если сборка на сервере зависает, можно собрать локально:

```bash
# Локально (на вашем Mac)
cd frontend
npm run build
tar czf dist.tar.gz dist/

# Загрузить на сервер через веб-консоль или SCP
# Затем на сервере:
cd /root/mapsparser-Replit-front
rm -rf frontend/dist
tar xzf dist.tar.gz -C frontend/
```

## Проверка после исправления

```bash
# Проверить, что Flask отдает правильный файл
curl -s http://localhost:8000/ | head -20
# Должен быть React HTML, а не простая форма
```

