# Задача: Парсинг из кабинета как fallback для неуспешного публичного парсинга

**Дата:** 2025-01-03  
**Приоритет:** Средний  
**Исполнитель:** Кодер

---

## Проблема

Публичные парсеры (interception и legacy) могут не получить полные данные из-за:
- Капчи
- Блокировок IP
- Неполных данных (отзывы не загрузились, статистика отсутствует)
- Ошибок парсинга

Если у бизнеса есть аккаунт в личном кабинете Яндекс.Бизнес, можно использовать его для допарсинга недостающих данных.

---

## Решение

Добавить третий тип задачи в ParseQueue: `task_type = 'parse_cabinet_fallback'`

**Логика:**
1. После неуспешного публичного парсинга проверять, есть ли у бизнеса аккаунт в `ExternalBusinessAccounts`
2. Если есть → создавать задачу `parse_cabinet_fallback` в ParseQueue
3. Worker обрабатывает задачу через `YandexBusinessParser`
4. Дополняет данные из публичного парсинга данными из кабинета

---

## Архитектура

### Схема приоритизации парсеров:

```
1. Публичный парсинг (parse_card)
   ├─ Interception парсер (приоритет 1)
   │  ├─ Перехват API → извлечение данных
   │  └─ Fallback: HTML парсинг (если API не сработал)
   └─ Legacy парсер (приоритет 2, если interception не работает)

2. Проверка успешности парсинга
   ├─ Данные полные? → Сохранить, завершить
   └─ Данные неполные/ошибка/капча? → Проверить наличие кабинета

3. Fallback через кабинет (parse_cabinet_fallback)
   └─ Если есть аккаунт в ExternalBusinessAccounts
      └─ YandexBusinessParser → дополнение данных
```

---

## Критерии "неуспешного" парсинга

**Когда создавать задачу fallback:**

1. **Капча обнаружена:**
   - `card_data.get("error") == "captcha_detected"`
   - Статус задачи = `"captcha"`

2. **Неполные данные:**
   - Отсутствует название (`title` или `overview.title`)
   - Отсутствует адрес (`address`)
   - Нет отзывов (`reviews` пустой или отсутствует), но бизнес должен их иметь
   - Нет статистики (если ожидается)

3. **Ошибка парсинга:**
   - `card_data.get("error")` не пустое
   - Исключение при парсинге

4. **Пустые критичные поля:**
   - Рейтинг = 0 или отсутствует (если ожидается)
   - Количество отзывов = 0 (если ожидается больше)

---

## План изменений

### Этап 1: Добавление функции проверки успешности парсинга

**Файл:** `src/worker.py` (создать функцию)

```python
def _is_parsing_successful(card_data: dict, business_id: str = None) -> tuple[bool, str]:
    """
    Проверяет, успешен ли парсинг.
    
    Returns:
        (is_successful: bool, reason: str)
    """
    # Проверка на капчу
    if card_data.get("error") == "captcha_detected":
        return False, "captcha_detected"
    
    # Проверка на ошибку
    if card_data.get("error"):
        return False, f"error: {card_data.get('error')}"
    
    # Проверка критичных полей
    title = card_data.get('title') or card_data.get('overview', {}).get('title')
    address = card_data.get('address') or card_data.get('overview', {}).get('address')
    
    if not title:
        return False, "missing_title"
    
    if not address:
        return False, "missing_address"
    
    # Проверка на неполные данные (опционально, можно настроить)
    reviews = card_data.get('reviews', [])
    if isinstance(reviews, dict):
        reviews = reviews.get('items', [])
    
    # Если бизнес должен иметь отзывы, но их нет - считаем неполным
    # (можно добавить проверку через БД, если у бизнеса были отзывы ранее)
    
    return True, "success"
```

---

### Этап 2: Добавление функции проверки наличия кабинета

**Файл:** `src/worker.py` (создать функцию)

```python
def _has_cabinet_account(business_id: str) -> tuple[bool, str]:
    """
    Проверяет, есть ли у бизнеса аккаунт в личном кабинете.
    
    Returns:
        (has_account: bool, account_id: str)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id 
            FROM ExternalBusinessAccounts 
            WHERE business_id = ? 
              AND source = 'yandex_business' 
              AND is_active = 1
            LIMIT 1
        """, (business_id,))
        
        row = cursor.fetchone()
        if row:
            return True, row[0]
        return False, None
    finally:
        cursor.close()
        conn.close()
```

---

### Этап 3: Изменение логики обработки parse_card

**Файл:** `src/worker.py` (изменить функцию `process_queue()`)

**После парсинга карты (строка 127):**

```python
# После card_data = parse_yandex_card(queue_dict["url"])

# Проверяем успешность парсинга
is_successful, reason = _is_parsing_successful(card_data, business_id)

if not is_successful and business_id:
    # Проверяем, есть ли кабинет для fallback
    has_account, account_id = _has_cabinet_account(business_id)
    
    if has_account:
        print(f"⚠️ Парсинг неполный ({reason}), создаю задачу fallback через кабинет")
        
        # Создаем задачу fallback
        fallback_task_id = str(uuid.uuid4())
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO ParseQueue (
                    id, business_id, account_id, task_type, source,
                    status, user_id, url, created_at, updated_at
                )
                VALUES (?, ?, ?, 'parse_cabinet_fallback', 'yandex_business',
                        'pending', ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (fallback_task_id, business_id, account_id, queue_dict["user_id"], queue_dict["url"]))
            conn.commit()
            print(f"✅ Создана задача fallback: {fallback_task_id}")
        finally:
            cursor.close()
            conn.close()
        
        # Сохраняем частичные данные (если есть)
        # Продолжаем обработку как обычно, но помечаем как неполное
```

---

### Этап 4: Добавление обработки parse_cabinet_fallback

**Файл:** `src/worker.py` (изменить функцию `process_queue()`)

**В блоке обработки разных типов задач (после строки 100):**

```python
elif task_type == "parse_cabinet_fallback":
    # Fallback парсинг через кабинет
    _process_cabinet_fallback_task(queue_dict)
    return
```

**Создать функцию:**

```python
def _process_cabinet_fallback_task(queue_dict: dict):
    """Обработка fallback парсинга через кабинет"""
    business_id = queue_dict.get("business_id")
    account_id = queue_dict.get("account_id")
    url = queue_dict.get("url")
    
    if not business_id or not account_id:
        # Обновляем статус на error
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = 'Отсутствует business_id или account_id',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (queue_dict["id"],))
        conn.commit()
        conn.close()
        return
    
    try:
        from yandex_business_parser import YandexBusinessParser
        from auth_encryption import decrypt_auth_data
        import json
        
        # Получаем auth_data
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        cursor.execute("""
            SELECT auth_data_encrypted, external_id 
            FROM ExternalBusinessAccounts 
            WHERE id = ? AND business_id = ?
        """, (account_id, business_id))
        account_row = cursor.fetchone()
        
        if not account_row:
            raise Exception("Аккаунт не найден")
        
        auth_data_encrypted, external_id = account_row
        auth_data_plain = decrypt_auth_data(auth_data_encrypted)
        
        if not auth_data_plain:
            raise Exception("Не удалось расшифровать auth_data")
        
        # Парсим auth_data
        try:
            auth_data_dict = json.loads(auth_data_plain)
        except json.JSONDecodeError:
            auth_data_dict = {"cookies": auth_data_plain}
        
        # Создаем парсер
        parser = YandexBusinessParser(auth_data_dict)
        account_data = {
            "id": account_id,
            "business_id": business_id,
            "external_id": external_id
        }
        
        # Получаем данные из кабинета
        print(f"🔄 Получаю данные из кабинета для бизнеса {business_id}...")
        reviews = parser.fetch_reviews(account_data)
        stats = parser.fetch_stats(account_data)
        posts = parser.fetch_posts(account_data)
        org_info = parser.fetch_organization_info(account_data)
        
        # Получаем существующие данные из MapParseResults (если есть)
        cursor.execute("""
            SELECT rating, reviews_count, unanswered_reviews_count, news_count, photos_count
            FROM MapParseResults
            WHERE business_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        existing_data = cursor.fetchone()
        
        # ВАЖНО: Fallback парсинг получает ВСЕ данные из кабинета заново
        # Это не "дополнение", а полная замена данных из кабинета
        # 
        # Причины:
        # 1. Кабинет дает более полные и актуальные данные
        # 2. Проще получить все данные сразу, чем проверять что отсутствует
        # 3. Данные из кабинета более надежные (официальный API)
        #
        # Если нужно дополнять только недостающие данные, можно добавить логику:
        # - Проверять, какие поля отсутствуют в публичном парсинге
        # - Запрашивать только недостающие данные из кабинета
        # Но это усложняет код и может быть менее надежным
        
        # Получаем ВСЕ данные из кабинета
        parse_id = str(uuid.uuid4())
        reviews_without_response = sum(1 for r in reviews if not r.response_text) if reviews else 0
        
        # Используем данные из кабинета (приоритет кабинету)
        # Если данных нет в кабинете, используем существующие (если есть)
        rating = org_info.get('rating') if org_info and org_info.get('rating') else (existing_data[0] if existing_data and existing_data[0] else None)
        reviews_count = len(reviews) if reviews else (existing_data[1] if existing_data and existing_data[1] else 0)
        news_count = len(posts) if posts else (existing_data[3] if existing_data and existing_data[3] else 0)
        photos_count = org_info.get('photos_count', 0) if org_info else (existing_data[4] if existing_data and existing_data[4] else 0)
        
        cursor.execute("""
            INSERT INTO MapParseResults (
                id, business_id, url, map_type, rating, reviews_count, 
                unanswered_reviews_count, news_count, photos_count, 
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            parse_id,
            business_id,
            url or f"https://yandex.ru/sprav/{external_id or 'unknown'}",
            'yandex',
            rating,
            reviews_count,
            reviews_without_response,
            news_count,
            photos_count,
        ))
        
        # Сохраняем отзывы в ExternalBusinessReviews
        # (используем существующую логику из _sync_yandex_business_sync_task)
        
        db.conn.commit()
        db.close()
        
        # Обновляем статус задачи
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'completed', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (queue_dict["id"],))
        conn.commit()
        conn.close()
        
        print(f"✅ Fallback парсинг завершен для бизнеса {business_id}")
        
    except Exception as e:
        print(f"❌ Ошибка fallback парсинга: {e}")
        import traceback
        traceback.print_exc()
        
        # Обновляем статус на error
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE ParseQueue 
            SET status = 'error', 
                error_message = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (str(e), queue_dict["id"]))
        conn.commit()
        conn.close()
```

---

## Порядок выполнения

1. **Создать функции проверки:**
   - `_is_parsing_successful()` - проверка успешности парсинга
   - `_has_cabinet_account()` - проверка наличия кабинета

2. **Изменить логику обработки parse_card:**
   - После парсинга проверять успешность
   - Если неуспешно и есть кабинет → создавать задачу fallback

3. **Добавить обработку parse_cabinet_fallback:**
   - Создать функцию `_process_cabinet_fallback_task()`
   - Добавить в `process_queue()` обработку нового типа задачи

4. **Протестировать:**
   - Публичный парсинг с капчей → должна создаться задача fallback
   - Публичный парсинг с неполными данными → должна создаться задача fallback
   - Fallback парсинг должен дополнять данные

---

## Чеклист для кодера

- [ ] Создать функцию `_is_parsing_successful()` в `worker.py`
- [ ] Создать функцию `_has_cabinet_account()` в `worker.py`
- [ ] Изменить логику обработки `parse_card` в `process_queue()`:
  - После парсинга проверять успешность
  - Создавать задачу fallback при неуспехе
- [ ] Создать функцию `_process_cabinet_fallback_task()` в `worker.py`
- [ ] Добавить обработку `task_type = 'parse_cabinet_fallback'` в `process_queue()`
- [ ] Протестировать:
  - Парсинг с капчей → создание fallback задачи
  - Парсинг с неполными данными → создание fallback задачи
  - Fallback парсинг → дополнение данных

---

## Важные замечания

1. **Логика получения данных:**
   - **Fallback парсинг получает ВСЕ данные из кабинета заново** (не только недостающие)
   - Причины:
     - Кабинет дает более полные и актуальные данные
     - Проще получить все данные сразу, чем проверять что отсутствует
     - Данные из кабинета более надежные (официальный API)
   - **Альтернатива (опционально):** Можно добавить логику "умного дополнения":
     - Проверять, какие поля отсутствуют в публичном парсинге
     - Запрашивать только недостающие данные из кабинета
     - Но это усложняет код и может быть менее надежным

2. **Приоритет данных:**
   - Данные из кабинета имеют приоритет (более полные и актуальные)
   - Если данных нет в кабинете, используем существующие из публичного парсинга

3. **Не создавать дубликаты:**
   - Проверять, не создана ли уже задача fallback для этого бизнеса
   - Можно добавить поле `parent_task_id` для связи задач

4. **Ограничения:**
   - Fallback работает только если у бизнеса есть активный аккаунт
   - Не все данные доступны через кабинет (например, конкуренты, публичная информация)

5. **Производительность:**
   - Fallback парсинг медленнее (HTTP запросы к API кабинета)
   - Использовать только при необходимости (неуспешный публичный парсинг)

---

## Ожидаемый результат

**После реализации:**
- Публичный парсинг → если неуспешен → автоматически создается задача fallback
- Fallback парсинг дополняет данные из кабинета
- Более полные данные для бизнесов с кабинетом
- Меньше потерянных данных из-за капчи/блокировок

