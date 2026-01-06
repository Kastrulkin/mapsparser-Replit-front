# 🔍 Code Simplification Review — BeautyBot

Анализ кода на предмет упрощения согласно правилам простоты.

---

## 📋 Содержание

1. [worker.py — Критические проблемы](#workerpy)
2. [parser.py — Дублирование и сложность](#parserpy)
3. [React компоненты — Лишние абстракции](#react-components)
4. [SQL запросы — Повторяющийся код](#sql-queries)
5. [Приоритеты исправлений](#priorities)

---

## 🔴 worker.py

### Проблема 1: Сложное преобразование Row в dict

**Текущий код (строки 74-85):**
```python
try:
    columns = [description[0] for description in cursor.description]
    queue_dict = {columns[i]: queue_item[i] for i in range(len(columns))}
except:
    queue_dict = {
        'id': queue_item[0],
        'url': queue_item[1],
        'user_id': queue_item[2],
        'status': queue_item[3],
        'created_at': queue_item[4] if len(queue_item) > 4 else None,
        'business_id': queue_item[5] if len(queue_item) > 5 else None
    }
```

**Проблемы:**
- Дублирование логики (try-except с fallback)
- Хардкод индексов в fallback
- Неявная зависимость от порядка колонок

**Решение:**
```python
# Используем Row factory из sqlite3
conn.row_factory = sqlite3.Row
# ...
queue_item = cursor.fetchone()
if not queue_item:
    return
queue_dict = dict(queue_item)
```

**Почему проще:**
- Один способ преобразования вместо двух
- Автоматическое создание dict из Row
- Нет зависимости от индексов

---

### Проблема 2: Множественные открытия/закрытия соединений

**Текущий код:**
- Строки 21-93: открытие → закрытие
- Строки 106-122: открытие → закрытие (для капчи)
- Строки 127-317: открытие → закрытие (для сохранения)
- Строки 326-346: открытие → закрытие (для ошибок)

**Проблемы:**
- Дублирование паттерна `conn = get_db_connection() ... finally: conn.close()`
- Легко забыть закрыть соединение при исключении
- Нет единого места для управления соединениями

**Решение:**
```python
def with_db_connection(func):
    """Context manager для БД соединений"""
    def wrapper(*args, **kwargs):
        conn = get_db_connection()
        try:
            return func(conn, *args, **kwargs)
        finally:
            conn.close()
    return wrapper

# Использование:
@with_db_connection
def get_next_queue_item(conn):
    cursor = conn.cursor()
    # ... код ...
    return queue_dict

@with_db_connection
def update_queue_status(conn, queue_id, status, retry_after=None):
    cursor = conn.cursor()
    if retry_after:
        cursor.execute("UPDATE ParseQueue SET status = ?, retry_after = ? WHERE id = ?", 
                      (status, retry_after, queue_id))
    else:
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", (status, queue_id))
    conn.commit()
```

**Почему проще:**
- Один паттерн для всех операций с БД
- Автоматическое закрытие соединений
- Меньше кода, меньше ошибок

---

### Проблема 3: Сложная логика проверки колонок

**Текущий код (строки 38-52, 166-203):**
```python
try:
    cursor.execute("PRAGMA table_info(ParseQueue)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'retry_after' not in columns:
        print("📝 Добавляю поле retry_after в ParseQueue...")
        cursor.execute("ALTER TABLE ParseQueue ADD COLUMN retry_after TEXT")
        conn.commit()
    
    if 'business_id' not in columns:
        print("📝 Добавляю поле business_id в ParseQueue...")
        cursor.execute("ALTER TABLE ParseQueue ADD COLUMN business_id TEXT")
        conn.commit()
except Exception as e:
    print(f"⚠️ Ошибка проверки структуры ParseQueue: {e}")
```

**Проблемы:**
- Дублирование логики проверки колонок
- Хардкод названий колонок
- Нет единой функции для миграций

**Решение:**
```python
def ensure_column_exists(conn, table_name, column_name, column_type="TEXT"):
    """Проверяет и добавляет колонку если её нет"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(?)", (table_name,))
    columns = [row[1] for row in cursor.fetchall()]
    
    if column_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        conn.commit()
        return True
    return False

# Использование:
ensure_column_exists(conn, "ParseQueue", "retry_after")
ensure_column_exists(conn, "ParseQueue", "business_id")
```

**Почему проще:**
- Одна функция вместо дублирования
- Переиспользуемый код
- Легко добавить новые колонки

---

### Проблема 4: Сложные условия в SQL запросе

**Текущий код (строки 55-67):**
```python
cursor.execute("""
    SELECT * FROM ParseQueue 
    WHERE status = 'pending' 
    OR (status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?))
    ORDER BY 
        CASE 
            WHEN status = 'pending' THEN 1
            WHEN status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?) THEN 2
            ELSE 3
        END,
        created_at ASC 
    LIMIT 1
""", (datetime.now().isoformat(), datetime.now().isoformat()))
```

**Проблемы:**
- Дублирование условия `retry_after <= ?` дважды
- Сложный CASE в ORDER BY
- Дублирование параметра `datetime.now().isoformat()`

**Решение:**
```python
now = datetime.now().isoformat()
cursor.execute("""
    SELECT * FROM ParseQueue 
    WHERE status = 'pending' 
       OR (status = 'captcha' AND (retry_after IS NULL OR retry_after <= ?))
    ORDER BY 
        CASE WHEN status = 'pending' THEN 1 ELSE 2 END,
        created_at ASC 
    LIMIT 1
""", (now,))
```

**Почему проще:**
- Один параметр вместо двух
- Упрощенный CASE (нет дублирования условия)
- Понятнее логика приоритетов

---

### Проблема 5: Вложенные try-except для обработки ошибок

**Текущий код (строки 319-346):**
```python
except Exception as e:
    # ... логирование ...
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE ParseQueue SET status = ? WHERE id = ?", ("error", queue_id))
        conn.commit()
        # ...
        try:
            from user_api import send_email
            send_email(...)
        except:
            pass
    except Exception as update_error:
        print(f"❌ Не удалось обновить статус заявки {queue_id}: {update_error}")
    finally:
        cursor.close()
        conn.close()
```

**Проблемы:**
- Вложенные try-except усложняют чтение
- `except: pass` скрывает ошибки
- Дублирование паттерна открытия/закрытия соединения

**Решение:**
```python
except Exception as e:
    queue_id = queue_dict.get('id', 'unknown')
    print(f"❌ Ошибка при обработке заявки {queue_id}: {e}")
    import traceback
    traceback.print_exc()
    
    # Обновляем статус через helper функцию
    update_queue_status(queue_id, "error")
    
    # Отправляем email (ошибка не критична)
    try:
        from user_api import send_email
        send_email("demyanovap@yandex.ru", "Ошибка парсинга карты",
                   f"URL: {queue_dict.get('url', 'unknown')}\nОшибка: {e}")
    except Exception as email_error:
        print(f"⚠️ Не удалось отправить email: {email_error}")
```

**Почему проще:**
- Нет вложенных try-except
- Явная обработка ошибок (не `pass`)
- Использование helper функции

---

## 🟡 parser.py

### Проблема 1: Огромный список cookies в коде

**Текущий код (строки 48-74):**
```python
cookies = [
    {"name": "_yasc", "value": "+nRgeAgdQvcUzBXmoMj8pj3o4NAMqN+CCHHN8J9/1lgNfV+4kHD1Sh3zeyrGAQw5", ...},
    {"name": "_yasc", "value": "biwmzqpVhmFOmsUovC7mHXedgeCta8YxIE4/1irJQVFGT+VWqh2xJNmwwC1OtCIXlpDhth57aht1oLEYU3XZbIItFHp3McubCw==", ...},
    # ... еще 20+ строк cookies ...
]
```

**Проблемы:**
- Загромождает код
- Сложно обновлять
- Не переиспользуется

**Решение:**
```python
# Вынести в отдельный файл или переменную окружения
# src/config.py или .env
YANDEX_COOKIES = os.getenv('YANDEX_COOKIES', '')
# Или загружать из файла:
# with open('cookies.json') as f:
#     cookies = json.load(f)
```

**Почему проще:**
- Код не загроможден
- Легко обновлять cookies
- Можно использовать разные cookies для разных окружений

---

### Проблема 2: Вложенные try-except для запуска браузеров

**Текущий код (строки 83-145):**
```python
browser = None
browser_name = ""

try:
    browser = p.chromium.launch(...)
    browser_name = "Chromium"
except Exception as e:
    print(f"Chromium недоступен: {e}")
    try:
        browser = p.firefox.launch(...)
        browser_name = "Firefox"
    except Exception as e2:
        print(f"Firefox недоступен: {e2}")
        try:
            browser = p.webkit.launch(...)
            browser_name = "WebKit"
        except Exception as e3:
            raise Exception(f"Все браузеры недоступны: ...")
```

**Проблемы:**
- Три уровня вложенности
- Дублирование логики для каждого браузера
- Сложно добавить новый браузер

**Решение:**
```python
def launch_browser(p):
    """Пробует запустить браузер, возвращает (browser, name) или None"""
    browsers = [
        (p.chromium, "Chromium", {
            'headless': True,
            'args': ['--no-sandbox', '--disable-setuid-sandbox', ...]
        }),
        (p.firefox, "Firefox", {
            'headless': True,
            'args': ['--no-sandbox', ...]
        }),
        (p.webkit, "WebKit", {
            'headless': True,
            'args': ['--no-sandbox']
        })
    ]
    
    for browser_type, name, options in browsers:
        try:
            browser = browser_type.launch(**options)
            print(f"Используем {name}")
            return browser, name
        except Exception as e:
            print(f"{name} недоступен: {e}")
            continue
    
    raise Exception("Не удалось запустить ни один браузер")

# Использование:
browser, browser_name = launch_browser(p)
```

**Почему проще:**
- Нет вложенности
- Легко добавить новый браузер
- Один паттерн для всех

---

## 🟢 React компоненты

### Проблема 1: Моковые данные в компоненте

**Текущий код (ProgressTracker.tsx, строки 43-108):**
```tsx
const mockStages: ProgressStage[] = [
  {
    id: '1',
    stage_number: 1,
    stage_name: 'Диагностика',
    // ... 20+ строк моковых данных ...
  },
  // ... еще 3 стадии ...
];

useEffect(() => {
  setTimeout(() => {
    setStages(mockStages);
    setLoading(false);
  }, 1000);
}, []);
```

**Проблемы:**
- Моковые данные загромождают компонент
- Не используется реальный API
- `setTimeout` имитирует загрузку (не нужно в продакшене)

**Решение:**
```tsx
useEffect(() => {
  const loadStages = async () => {
    if (!businessId) return;
    
    setLoading(true);
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch(`/api/business/${businessId}/stages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setStages(data.stages || []);
      }
    } catch (err) {
      setError('Ошибка загрузки стадий');
    } finally {
      setLoading(false);
    }
  };
  
  loadStages();
}, [businessId]);
```

**Почему проще:**
- Нет моковых данных в компоненте
- Единый паттерн загрузки (как в `loadSprint`)
- Реальные данные из API

---

### Проблема 2: Дублирование логики загрузки

**Текущий код:**
- `loadSprint` (строки 119-145) и `load` в MapParseTable делают одно и то же

**Решение:**
```tsx
// Вынести в хук
function useApiData<T>(endpoint: string | null, options?: RequestInit) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    if (!endpoint) return;
    
    setLoading(true);
    setError(null);
    
    const token = localStorage.getItem('auth_token');
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${token || ''}` },
      ...options
    })
      .then(res => res.json())
      .then(data => {
        if (data.success) {
          setData(data.data);
        } else {
          setError(data.error || 'Ошибка загрузки');
        }
      })
      .catch(e => setError('Ошибка соединения'))
      .finally(() => setLoading(false));
  }, [endpoint]);
  
  return { data, loading, error };
}

// Использование:
const { data: stages, loading, error } = useApiData<ProgressStage[]>(
  businessId ? `/api/business/${businessId}/stages` : null
);
```

**Почему проще:**
- Один паттерн для всех API запросов
- Меньше дублирования
- Легко переиспользовать

---

## 🔵 SQL запросы

### Проблема: Повторяющийся запрос `SELECT owner_id FROM Businesses`

**Текущий код:**
В `main.py` этот запрос повторяется 7+ раз:
```python
cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
```

**Решение:**
```python
# Вынести в helper функцию
def get_business_owner_id(conn, business_id: str) -> str | None:
    """Получить owner_id бизнеса"""
    cursor = conn.cursor()
    cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
    row = cursor.fetchone()
    return row[0] if row else None

# Использование:
owner_id = get_business_owner_id(conn, business_id)
if not owner_id or owner_id != user_data['user_id']:
    return jsonify({"error": "Нет доступа"}), 403
```

**Почему проще:**
- Один источник истины
- Легко изменить логику (например, добавить кеш)
- Меньше дублирования

---

## 📊 Приоритеты исправлений

### ✅ ВЫПОЛНЕНО

1. **worker.py: Преобразование Row в dict** ✅
   - Было: 12 строк с try-except и fallback
   - Стало: 1 строка `dict(queue_item)`
   - Экономия: ~11 строк

2. **worker.py: Упрощение SQL запроса** ✅
   - Было: дублирование параметра `datetime.now().isoformat()`
   - Стало: один параметр `now`
   - Экономия: упрощение логики

3. **worker.py: Функция для проверки колонок** ✅
   - Было: дублирование логики в двух местах
   - Стало: одна функция `_ensure_column_exists()`
   - Экономия: ~10 строк, переиспользуемый код

4. **worker.py: Упрощение INSERT в MapParseResults** ✅
   - Было: проверка колонки + два разных INSERT
   - Стало: всегда создаём колонку, один INSERT
   - Экономия: ~15 строк

5. **worker.py: Улучшение обработки ошибок** ✅
   - Было: вложенные try-except с `except: pass`
   - Стало: явная обработка ошибок
   - Экономия: упрощение логики

6. **parser.py: Запуск браузеров** ✅
   - Было: 3 уровня вложенных try-except (65 строк)
   - Стало: функция `_launch_browser()` с циклом (40 строк)
   - Экономия: ~25 строк, убрана вложенность

7. **React: Моковые данные в ProgressTracker** ✅
   - Было: 65+ строк моковых данных в компоненте
   - Стало: использование хука `useApiData`
   - Экономия: ~60 строк, реальный API

8. **React: Хук useApiData** ✅
   - Создан переиспользуемый хук для API запросов
   - Используется в ProgressTracker и MapParseTable
   - Экономия: убрано дублирование логики загрузки

9. **React: Упрощение MapParseTable** ✅
   - Было: ручная загрузка с useState/useEffect
   - Стало: использование хука `useApiData`
   - Экономия: ~20 строк

10. **main.py: Helper функция для owner_id** ✅
    - Создана функция `get_business_owner_id()`
    - Применена в одном месте (остальные можно заменить)
    - Экономия: переиспользуемый код

### 🟡 Осталось сделать

1. **main.py: Заменить все использования owner_id запроса** (9+ мест)
   - Использовать `get_business_owner_id()` везде
   - Экономия: ~50 строк

2. **parser.py: Вынести cookies в конфиг** (Проблема 1)
   - Улучшит читаемость
   - Не критично для функциональности

3. **main.py: Разбить на модули** (8872 строки)
   - Критично для поддержки
   - Требует рефакторинга архитектуры

---

## ✅ Чеклист перед коммитом

После применения исправлений проверь:

- [ ] Код стал короче (меньше строк)
- [ ] Нет дублирования логики
- [ ] Упрощены условия и ветвления
- [ ] Убраны лишние абстракции
- [ ] Сохранено поведение (тесты проходят)
- [ ] Type safety сохранен (TypeScript без ошибок)

---

## 💡 Принципы

**Помни:**
- Простота > Умность
- Одна функция = одна ответственность
- Явный код > "магия"
- DRY (Don't Repeat Yourself)
- Guard clauses вместо вложенных if

**Не делай:**
- Абстракции "на будущее"
- Сложные паттерны без необходимости
- Комментарии к очевидному коду
- Оптимизация преждевременно

