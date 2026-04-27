# 🧪 Тестирование парсера Яндекс.Бизнес на реальном сервере

> Актуализация: текущий production runtime использует `/opt/seo-app` и Docker Compose.
> Вместо старых команд через `venv` используйте [scripts/test_yandex_on_server.sh](../scripts/test_yandex_on_server.sh) или `cd /opt/seo-app && docker compose exec -T app python3 scripts/test_oliver_yandex.py`.

## Вариант 1: Через SSH (рекомендуется)

### Шаг 1: Подключитесь к серверу

```bash
ssh root@local
# или
ssh root@<IP_СЕРВЕРА>
```

### Шаг 2: Перейдите в директорию проекта

```bash
cd /opt/seo-app
```

### Шаг 3: Обновите код из GitHub (если нужно)

```bash
git pull origin main
```

### Шаг 4: Запустите тест

**Вариант А: Используя готовый скрипт**
```bash
bash scripts/test_yandex_on_server.sh
```

**Вариант Б: Вручную**
```bash
docker compose exec -T app python3 scripts/test_oliver_yandex.py
```

## Вариант 2: Одной командой через SSH

Если у вас настроен SSH доступ, можно запустить тест одной командой с локального компьютера:

```bash
ssh root@local "cd /opt/seo-app && docker compose exec -T app python3 scripts/test_oliver_yandex.py"
```

## Что проверить в выводе

### ✅ Успешные признаки:

1. **Парсер инициализирован:**
   ```
   ✅ Парсер создан
   🍪 Парсер инициализирован с 25 cookies
   ```

2. **Успешные запросы к API:**
   ```
   ✅ Успешно получены данные из sidebar API
   ✅ Успешно получены данные постов с https://yandex.ru/business/server-components/sidebar?permalink=203293742306
   ```

3. **Данные извлечены:**
   ```
   📊 Найдено постов в ответе: X
   ✅ Количество фотографий из sidebar API: X
   ✅ Получено отзывов: X
   ```

### ⚠️ Возможные проблемы:

1. **401 Unauthorized:**
   - Cookies устарели, нужно обновить их в админ-панели

2. **404 Not Found:**
   - Endpoint изменился, нужно проверить Network tab в браузере

3. **Пустые данные:**
   - Структура ответа отличается, нужно проверить Response в DevTools

## После успешного теста

Если тест прошёл успешно, можно проверить рабочий runtime:

```bash
cd /opt/seo-app
docker compose ps
docker compose logs --since 10m worker | tail -n 120
```

## Логирование

Если нужно сохранить вывод теста в файл:

```bash
python3 scripts/test_oliver_yandex.py 2>&1 | tee /tmp/yandex_test_$(date +%Y%m%d_%H%M%S).log
```

Файл будет сохранён в `/tmp/` с временной меткой.
