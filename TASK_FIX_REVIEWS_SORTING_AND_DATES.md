# Задача: Исправление сортировки отзывов и парсинга дат

**Дата:** 2025-01-06  
**Приоритет:** КРИТИЧЕСКИЙ  
**Исполнитель:** Кодер

---

## Проблемы

1. **Отзывы отображаются от старого к новому** - нужно наоборот (новые сверху)
2. **Даты не парсятся** - все 67 отзывов имеют `published_at: None`
3. **Селектор для даты не подходит** - нужно проверить и добавить правильный селектор `Review-RatingDate`

---

## Проблема 1: Сортировка отзывов

### Анализ

**Файл:** `src/main.py` (строки 1101-1108)

**Текущая ситуация:**
- SQL запрос уже имеет `ORDER BY published_at DESC, created_at DESC`
- Но если `published_at` = NULL, сортировка не работает правильно
- Нужно обработать NULL значения

### Решение

**Файл:** `src/main.py` (строки 1101-1108)

**Изменить SQL запрос:**

```python
# Было:
ORDER BY published_at DESC, created_at DESC

# Стало:
ORDER BY 
    CASE WHEN published_at IS NOT NULL THEN 0 ELSE 1 END,
    published_at DESC NULLS LAST,
    created_at DESC
```

**Альтернативный вариант (более простой):**

```python
ORDER BY 
    COALESCE(published_at, created_at) DESC,
    created_at DESC
```

Это будет сортировать сначала по `published_at`, а если он NULL, то по `created_at`.

---

## Проблема 2: Парсинг дат не работает

### Анализ

**Проблемные места:**
1. `src/parser.py` - селекторы для даты не включают `Review-RatingDate`
2. `src/parser_interception.py` - дата может не извлекаться из API
3. `src/worker.py` - парсинг даты из строки может не работать

### Решение

#### 2.1. Добавить селектор `Review-RatingDate` в parser.py

**Файл:** `src/parser.py` (строки 828-856)

**Добавить селектор в начало списка:**

```python
# Дата - расширенный парсинг
date = ""
date_selectors = [
    "div.Review-RatingDate",  # НОВЫЙ селектор из кабинета
    "div.Review-InfoWrapper > div > div.Review-RatingDate",  # Полный путь
    "div.business-review-view__date",
    "span.business-review-view__date",
    "span[class*='date']",
    "time[datetime]",
    "time",
    "[data-date]",
    "div[class*='review-date']",
    "span[class*='review-date']"
]
```

**Также добавить парсинг атрибута `data-date` или `datetime`:**

```python
for selector in date_selectors:
    date_el = block.query_selector(selector)
    if date_el:
        # Пробуем атрибут datetime (если есть)
        date_attr = date_el.get_attribute('datetime')
        if date_attr:
            date = date_attr.strip()
            break
        
        # Пробуем атрибут data-date
        data_date_attr = date_el.get_attribute('data-date')
        if data_date_attr:
            date = data_date_attr.strip()
            break
        
        # Пробуем атрибут title (может содержать дату)
        title_attr = date_el.get_attribute('title')
        if title_attr and ('202' in title_attr or '2023' in title_attr or '2024' in title_attr):
            date = title_attr.strip()
            break
        
        # Иначе берем текст
        date_text = date_el.inner_text().strip()
        if date_text:
            date = date_text
            break
```

#### 2.2. Улучшить парсинг даты в parser_interception.py

**Файл:** `src/parser_interception.py` (строки 472-491)

**Добавить больше вариантов полей с датой:**

```python
# Извлекаем дату (может быть в разных форматах)
date_raw = (
    item.get('date') or 
    item.get('publishedAt') or 
    item.get('published_at') or 
    item.get('createdAt') or 
    item.get('created_at') or
    item.get('time') or
    item.get('timestamp') or
    item.get('created') or
    item.get('published') or
    item.get('dateCreated') or
    item.get('datePublished') or
    item.get('reviewDate') or
    item.get('review_date')
)
```

**Улучшить парсинг timestamp:**

```python
if date_raw:
    # Если это timestamp (число)
    if isinstance(date_raw, (int, float)):
        try:
            from datetime import datetime
            # Проверяем, в миллисекундах или секундах
            if date_raw > 1e10:  # Вероятно миллисекунды
                date = datetime.fromtimestamp(date_raw / 1000.0).isoformat()
            else:  # Секунды
                date = datetime.fromtimestamp(date_raw).isoformat()
        except Exception as e:
            print(f"⚠️ Ошибка парсинга timestamp {date_raw}: {e}")
            date = str(date_raw)
    # Если это строка ISO формата
    elif isinstance(date_raw, str):
        # Пробуем распарсить как ISO
        try:
            from datetime import datetime
            # Убираем Z и заменяем на +00:00
            date_clean = date_raw.replace('Z', '+00:00')
            datetime.fromisoformat(date_clean)  # Проверяем валидность
            date = date_clean
        except:
            # Если не ISO, оставляем как есть (будет парситься в worker.py)
            date = date_raw
    else:
        date = str(date_raw)
```

**Добавить логирование для отладки:**

```python
# Логируем дату отзыва (только для первых 5 отзывов)
if date and len(reviews) < 5:
    print(f"📅 Дата отзыва извлечена: {date}")
elif not date and len(reviews) < 5:
    print(f"⚠️ Дата отзыва не найдена. Доступные поля: {list(item.keys())}")
```

#### 2.3. Улучшить парсинг даты в worker.py

**Файл:** `src/worker.py` (строки 325-363)

**Добавить больше форматов дат:**

```python
# Парсим дату
published_at = None
date_str = review.get('date', '').strip()

# Также пробуем другие поля
if not date_str:
    date_str = (
        review.get('published_at') or 
        review.get('publishedAt') or 
        review.get('created_at') or 
        review.get('createdAt') or
        review.get('time') or
        review.get('timestamp') or
        ''
    )
    if isinstance(date_str, (int, float)):
        # Если это timestamp
        try:
            if date_str > 1e10:  # Миллисекунды
                published_at = datetime.fromtimestamp(date_str / 1000.0)
            else:  # Секунды
                published_at = datetime.fromtimestamp(date_str)
        except:
            date_str = str(date_str)
    elif isinstance(date_str, str):
        date_str = date_str.strip()
    else:
        date_str = str(date_str) if date_str else ''

if date_str:
    try:
        # Пробуем разные форматы дат
        # "2 дня назад", "неделю назад", "15 января 2024", "2024-01-15"
        if 'дня' in date_str or 'день' in date_str or 'дней' in date_str:
            # Относительная дата
            days_match = re.search(r'(\d+)', date_str)
            if days_match:
                days_ago = int(days_match.group(1))
                published_at = datetime.now() - timedelta(days=days_ago)
        elif 'неделю' in date_str or 'недели' in date_str or 'недель' in date_str:
            weeks_match = re.search(r'(\d+)', date_str)
            if weeks_match:
                weeks_ago = int(weeks_match.group(1))
                published_at = datetime.now() - timedelta(weeks=weeks_ago)
            else:
                published_at = datetime.now() - timedelta(weeks=1)
        elif 'месяц' in date_str or 'месяца' in date_str or 'месяцев' in date_str:
            months_match = re.search(r'(\d+)', date_str)
            if months_match:
                months_ago = int(months_match.group(1))
                published_at = datetime.now() - timedelta(days=months_ago * 30)
            else:
                published_at = datetime.now() - timedelta(days=30)
        elif 'год' in date_str or 'года' in date_str or 'лет' in date_str:
            years_match = re.search(r'(\d+)', date_str)
            if years_match:
                years_ago = int(years_match.group(1))
                published_at = datetime.now() - timedelta(days=years_ago * 365)
            else:
                published_at = datetime.now() - timedelta(days=365)
        elif 'сегодня' in date_str.lower() or 'today' in date_str.lower():
            published_at = datetime.now()
        elif 'вчера' in date_str.lower() or 'yesterday' in date_str.lower():
            published_at = datetime.now() - timedelta(days=1)
        else:
            # Пробуем распарсить как обычную дату
            try:
                # Сначала пробуем ISO формат
                if 'T' in date_str or 'Z' in date_str or date_str.count('-') >= 2:
                    published_at = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                else:
                    # Используем dateutil для парсинга других форматов
                    published_at = date_parser.parse(date_str, fuzzy=True)
            except Exception as iso_err:
                print(f"⚠️ Не удалось распарсить дату '{date_str}': {iso_err}")
    except Exception as date_err:
        print(f"⚠️ Не удалось распарсить дату '{date_str}': {date_err}")
```

---

## Проблема 3: Проверка селектора Review-RatingDate

### Анализ

**Селектор от тестировщика:**
```
#root > div > div.EditPage.EditPage_type_reviews > div.EditPage-Right > div > div.ReviewsPage > div.ReviewsPage-Content > div.ReviewsPage-Left > div > div.ReviewsPage-ListContent > div.ReviewsPage-ReviewsList > div:nth-child(7) > div.Review-Header > div.Review-InfoWrapper > div > div.Review-RatingDate
```

**Это селектор из личного кабинета Яндекс.Бизнес**, а не из публичных карт.

**Нужно:**
- Добавить этот селектор в `yandex_business_parser.py` (для парсинга из кабинета)
- Проверить, что он работает в `parser.py` (для публичных карт, если такой элемент есть)

### Решение

**Файл:** `src/yandex_business_parser.py`

**Уже есть логика парсинга даты (строки 429-452), но нужно добавить селектор для HTML парсинга (если используется):**

Если в `yandex_business_parser.py` есть HTML парсинг (не только API), добавить селектор:

```python
# Если парсим HTML из кабинета
date_selectors = [
    "div.Review-RatingDate",
    "div.Review-InfoWrapper > div > div.Review-RatingDate",
    "div.Review-Header > div.Review-InfoWrapper > div > div.Review-RatingDate",
    "time[datetime]",
    "[data-date]"
]
```

---

## Порядок выполнения

1. **Исправить сортировку отзывов** (критично)
   - Изменить SQL запрос в `src/main.py`
   - Протестировать сортировку

2. **Добавить селектор Review-RatingDate** (критично)
   - Добавить в `src/parser.py`
   - Проверить в `src/yandex_business_parser.py` (если используется HTML)

3. **Улучшить парсинг дат** (критично)
   - Улучшить `src/parser_interception.py`
   - Улучшить `src/parser.py`
   - Улучшить `src/worker.py`

4. **Протестировать парсинг дат**
   - Запустить парсинг на тестовом бизнесе
   - Проверить логи worker'а
   - Убедиться, что даты сохраняются в БД

---

## Чеклист для кодера

### Исправление сортировки
- [ ] Изменить SQL запрос в `src/main.py` (строки 1101-1108)
- [ ] Использовать `COALESCE(published_at, created_at) DESC` для сортировки
- [ ] Протестировать сортировку отзывов на фронтенде

### Добавление селектора Review-RatingDate
- [ ] Добавить `div.Review-RatingDate` в начало списка селекторов в `src/parser.py`
- [ ] Добавить полный путь `div.Review-InfoWrapper > div > div.Review-RatingDate`
- [ ] Проверить, используется ли HTML парсинг в `yandex_business_parser.py`
- [ ] Если да, добавить селектор туда тоже

### Улучшение парсинга дат
- [ ] Улучшить извлечение даты в `src/parser_interception.py`:
  - Добавить больше вариантов полей
  - Улучшить парсинг timestamp
  - Добавить логирование
- [ ] Улучшить извлечение даты в `src/parser.py`:
  - Добавить парсинг атрибутов `data-date`, `title`
  - Улучшить логирование
- [ ] Улучшить парсинг даты в `src/worker.py`:
  - Добавить больше форматов дат
  - Обработать timestamp
  - Добавить обработку "сегодня", "вчера"

### Тестирование
- [ ] Запустить парсинг на тестовом бизнесе
- [ ] Проверить логи worker'а: `tail -f /tmp/seo_worker.out | grep -i "дата\|date"`
- [ ] Проверить БД: `sqlite3 src/reports.db "SELECT COUNT(*) FROM ExternalBusinessReviews WHERE published_at IS NOT NULL;"`
- [ ] Проверить сортировку на фронтенде

---

## Важные замечания

1. **Селектор Review-RatingDate:**
   - Это селектор из личного кабинета Яндекс.Бизнес
   - Для публичных карт может не работать
   - Нужно проверить, есть ли такой элемент на публичных картах

2. **Парсинг дат:**
   - Даты могут быть в разных форматах: timestamp, ISO, относительные ("2 дня назад")
   - Нужно обрабатывать все варианты
   - Логировать ошибки парсинга для отладки

3. **Сортировка:**
   - Если `published_at` = NULL, использовать `created_at`
   - Новые отзывы должны быть сверху

---

## Ожидаемый результат

**После исправления:**
- Отзывы сортируются от новых к старым (новые сверху)
- Даты парсятся и сохраняются в БД
- Все отзывы имеют `published_at` (или `created_at` если дата не найдена)
- Селектор `Review-RatingDate` работает для парсинга из кабинета

---

## Дополнительно: Задача по админ-панели

**Задача по вкладке "Парсинг" в административной панели уже создана:**
- Файл: `TASK_ADMIN_PARSING_TAB.md`
- Статус: Approved for Implementation
- Содержит полное описание реализации

**Что нужно сделать:**
- См. `TASK_ADMIN_PARSING_TAB.md` для деталей
- Создать backend API эндпоинты
- Создать frontend компонент `ParsingManagement.tsx`
- Интегрировать в `AdminPage.tsx`
