# Задача: Ротация IP-адресов для обхода блокировок Яндекс

**Дата:** 2025-01-03  
**Приоритет:** Высокий  
**Исполнитель:** Кодер

---

## Проблема

Яндекс может блокировать IP-адреса при частых запросах парсинга:
- Капча
- Блокировка IP
- Rate limiting
- Бан аккаунта

Нужна ротация IP-адресов для распределения нагрузки и обхода блокировок.

---

## Решение

Реализовать систему ротации прокси для Playwright и requests:
1. Хранение списка прокси (БД или конфиг)
2. Ротация прокси между запросами
3. Проверка работоспособности прокси
4. Автоматическое исключение неработающих прокси

---

## Архитектура

### Варианты реализации:

#### Вариант 1: Прокси-серверы (рекомендуется)

**Преимущества:**
- Полный контроль над IP
- Можно использовать резидентные прокси (меньше банов)
- Ротация на уровне запросов

**Недостатки:**
- Требует покупки/настройки прокси
- Дополнительные расходы

**Реализация:**
- Таблица `ProxyServers` в БД
- Ротация через Playwright `proxy` параметр
- Проверка работоспособности перед использованием

---

#### Вариант 2: VPN ротация (альтернатива)

**Преимущества:**
- Проще настройка (если есть VPN сервер)
- Меньше расходов

**Недостатки:**
- Медленнее переключение IP
- Меньше контроля

**Реализация:**
- Переключение VPN перед запросами (через API VPN провайдера)
- Медленнее, но проще

---

#### Вариант 3: Tor ротация (для тестирования)

**Преимущества:**
- Бесплатно
- Автоматическая ротация

**Недостатки:**
- Очень медленно
- Яндекс может блокировать Tor IP
- Не подходит для продакшена

---

## Рекомендуемое решение: Прокси-серверы

### Варианты получения прокси:

#### Вариант 1: Покупка резидентных прокси (рекомендуется)

**Провайдеры:**
- **Bright Data (Luminati)** - от $500/месяц, резидентные прокси
- **Smartproxy** - от $75/месяц, резидентные прокси
- **Oxylabs** - от $300/месяц, резидентные прокси
- **IPRoyal** - от $7/GB, резидентные прокси

**Преимущества:**
- Резидентные IP (меньше банов)
- Высокая скорость
- Надежность

**Недостатки:**
- Дорого (от $75/месяц)
- Нужна настройка аккаунта

---

#### Вариант 2: Бесплатные прокси-листы (для тестирования)

**Источники:**
- **Free Proxy List** (free-proxy-list.net)
- **ProxyScrape** (proxyscrape.com)
- **ProxyList** (proxylist.geonode.com)

**Преимущества:**
- Бесплатно
- Быстрое тестирование

**Недостатки:**
- Низкая надежность (многие не работают)
- Медленно
- Частые баны
- Не подходит для продакшена

---

#### Вариант 3: Собственные прокси-серверы (для больших объемов)

**Настройка:**
- Арендовать VPS серверы в разных локациях
- Установить прокси-сервер (Squid, 3proxy)
- Настроить ротацию

**Преимущества:**
- Полный контроль
- Можно масштабировать

**Недостатки:**
- Требует настройки и поддержки
- Дороже при малых объемах

---

#### Вариант 4: VPN API ротация (альтернатива)

**Провайдеры:**
- **NordLayer API** - ротация IP через VPN
- **Surfshark API** - ротация IP через VPN

**Преимущества:**
- Проще настройка
- Меньше расходов

**Недостатки:**
- Медленнее переключение IP
- Меньше контроля

---

### Рекомендация:

**Для начала:** Использовать бесплатные прокси-листы для тестирования
**Для продакшена:** Покупка резидентных прокси (Smartproxy или IPRoyal - оптимальное соотношение цена/качество)

---

### Структура БД

**Таблица `ProxyServers`:**

```sql
CREATE TABLE ProxyServers (
    id TEXT PRIMARY KEY,
    proxy_type TEXT NOT NULL,  -- 'http', 'socks5', 'socks4'
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    username TEXT,  -- опционально
    password TEXT,  -- опционально (зашифровать)
    is_active INTEGER DEFAULT 1,
    last_used_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    is_working INTEGER DEFAULT 1,  -- 1 = работает, 0 = не работает
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_proxy_servers_active ON ProxyServers(is_active, is_working);
CREATE INDEX idx_proxy_servers_last_used ON ProxyServers(last_used_at);
```

**Формат прокси:**
- HTTP: `http://username:password@host:port`
- SOCKS5: `socks5://username:password@host:port`

---

## План изменений

### Этап 1: Создание таблицы ProxyServers

**Файл:** `src/init_database_schema.py`

**Добавить создание таблицы:**

```python
# ProxyServers - список прокси-серверов для ротации IP
cursor.execute("""
    CREATE TABLE IF NOT EXISTS ProxyServers (
        id TEXT PRIMARY KEY,
        proxy_type TEXT NOT NULL,
        host TEXT NOT NULL,
        port INTEGER NOT NULL,
        username TEXT,
        password TEXT,  -- TODO: зашифровать
        is_active INTEGER DEFAULT 1,
        last_used_at TIMESTAMP,
        last_checked_at TIMESTAMP,
        success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0,
        is_working INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
print("✅ Таблица ProxyServers создана/проверена")

cursor.execute("CREATE INDEX IF NOT EXISTS idx_proxy_servers_active ON ProxyServers(is_active, is_working)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_proxy_servers_last_used ON ProxyServers(last_used_at)")
```

---

### Этап 2: Создание модуля управления прокси

**Файл:** `src/proxy_manager.py` (создать)

```python
"""
Модуль управления прокси-серверами для ротации IP
"""
# ВАЖНО: Только необходимые импорты (см. рекомендации упростителя в SIMPLIFICATION.md)
from typing import Optional, Dict, Any
from safe_db_utils import get_db_connection
# НЕ импортировать random, time, datetime, timedelta - они не используются


class ProxyManager:
    """Управление прокси-серверами"""
    
    def __init__(self):
        # ВАЖНО: Только необходимые поля (см. рекомендации упростителя в SIMPLIFICATION.md)
        self.current_proxy: Optional[Dict[str, Any]] = None
        # НЕ добавлять proxy_cache и cache_ttl - они не используются
    
    def get_next_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Получает следующий рабочий прокси для использования.
        Использует round-robin с приоритетом на неиспользуемые.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Получаем рабочие прокси, отсортированные по последнему использованию
            cursor.execute("""
                SELECT id, proxy_type, host, port, username, password
                FROM ProxyServers
                WHERE is_active = 1 AND is_working = 1
                ORDER BY 
                    CASE WHEN last_used_at IS NULL THEN 0 ELSE 1 END,
                    last_used_at ASC,
                    RANDOM()
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if not row:
                print("⚠️ Нет доступных прокси, используем прямой доступ")
                return None
            
            proxy_id, proxy_type, host, port, username, password = row
            
            # Формируем URL прокси
            if username and password:
                proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{proxy_type}://{host}:{port}"
            
            # Обновляем last_used_at
            cursor.execute("""
                UPDATE ProxyServers 
                SET last_used_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
            
            proxy_dict = {
                "server": proxy_url,
                "id": proxy_id,
                "type": proxy_type,
                "host": host,
                "port": port
            }
            
            self.current_proxy = proxy_dict
            print(f"✅ Используем прокси: {host}:{port} (ID: {proxy_id})")
            
            return proxy_dict
            
        finally:
            cursor.close()
            conn.close()
    
    def mark_proxy_success(self, proxy_id: str):
        """Отмечает прокси как успешно использованный"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE ProxyServers 
                SET success_count = success_count + 1,
                    is_working = 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def mark_proxy_failure(self, proxy_id: str, reason: str = None):
        """Отмечает прокси как неработающий"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE ProxyServers 
                SET failure_count = failure_count + 1,
                    is_working = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (proxy_id,))
            conn.commit()
            
            print(f"⚠️ Прокси {proxy_id} помечен как неработающий: {reason}")
        finally:
            cursor.close()
            conn.close()
    
    def check_proxy(self, proxy_dict: Dict[str, Any]) -> bool:
        """
        Проверяет работоспособность прокси.
        Делает тестовый запрос к Яндекс.Картам.
        """
        try:
            import requests
            
            test_url = "https://yandex.ru/maps"
            proxies = {
                "http": proxy_dict["server"],
                "https": proxy_dict["server"]
            }
            
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            return False
            
        except Exception as e:
            print(f"⚠️ Ошибка проверки прокси {proxy_dict.get('id')}: {e}")
            return False
    
    def get_proxy_for_playwright(self, proxy_dict: Optional[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        """
        Преобразует прокси в формат для Playwright.
        
        Returns:
            {
                "server": "http://host:port",
                "username": "user",  # опционально
                "password": "pass"   # опционально
            }
        """
        if not proxy_dict:
            return None
        
        playwright_proxy = {
            "server": f"{proxy_dict['type']}://{proxy_dict['host']}:{proxy_dict['port']}"
        }
        
        # Извлекаем username/password из server URL если есть
        server_url = proxy_dict["server"]
        if "@" in server_url:
            # Формат: http://user:pass@host:port
            parts = server_url.split("@")
            if len(parts) == 2:
                auth_part = parts[0].split("://")[1]
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                    playwright_proxy["username"] = username
                    playwright_proxy["password"] = password
        
        return playwright_proxy
```

---

### Этап 3: Интеграция прокси в parser_interception.py

**Файл:** `src/parser_interception.py`

**ВАЖНО: Рекомендации упростителя (см. SIMPLIFICATION.md):**
- Создать маленький helper `get_playwright_proxy_or_none()` вместо размазанной логики
- Четкий early-return: "нет прокси → работаем без них, никаких доп. веток"

**Изменения:**

```python
from proxy_manager import ProxyManager

def get_playwright_proxy_or_none(proxy_manager: ProxyManager) -> Optional[Dict[str, str]]:
    """
    Получает прокси для Playwright или None.
    Простой helper для избежания размазанной логики.
    """
    proxy_dict = proxy_manager.get_next_proxy()
    if not proxy_dict:
        return None
    
    return proxy_manager.get_proxy_for_playwright(proxy_dict)

class YandexMapsInterceptionParser:
    def __init__(self, proxy_manager: ProxyManager = None):
        self.api_responses = {}
        self.org_id = None
        self.proxy_manager = proxy_manager or ProxyManager()
    
    def parse_yandex_card(self, url: str) -> Dict[str, Any]:
        # Получаем прокси через helper (early-return если нет)
        playwright_proxy = get_playwright_proxy_or_none(self.proxy_manager)
        
        # ... существующий код ...
        
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--disable-images',
                    ]
                )
                
                # Настраиваем контекст: прокси опционально (early-return)
                context_options = {
                    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'viewport': {'width': 1920, 'height': 1080},
                }
                
                if playwright_proxy:
                    context_options['proxy'] = playwright_proxy
                    print(f"🌐 Используем прокси: {playwright_proxy.get('server', 'unknown')}")
                
                context = browser.new_context(**context_options)
                
                # ... остальной код ...
                
                # После успешного парсинга
                if proxy_dict:
                    self.proxy_manager.mark_proxy_success(proxy_dict['id'])
                
            except Exception as e:
                # При ошибке отмечаем прокси как неработающий
                if proxy_dict and "proxy" in str(e).lower():
                    self.proxy_manager.mark_proxy_failure(proxy_dict['id'], str(e))
                raise
```

---

### Этап 4: Интеграция прокси в parser.py

**Файл:** `src/parser.py`

**ВАЖНО: Рекомендации упростителя (см. SIMPLIFICATION.md):**
- Использовать тот же helper `get_playwright_proxy_or_none()` для единообразия
- Четкий early-return: "нет прокси → работаем без них"

**Изменения:**

```python
from proxy_manager import ProxyManager, get_playwright_proxy_or_none

def parse_yandex_card(url: str) -> dict:
    # Получаем прокси через helper (early-return если нет)
    proxy_manager = ProxyManager()
    playwright_proxy = get_playwright_proxy_or_none(proxy_manager)
    
    # ... существующий код ...
    
    with sync_playwright() as p:
        try:
            browser, browser_name = _launch_browser(p)
            
            # Настраиваем контекст: прокси опционально (early-return)
            context_options = {
                'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'locale': 'ru-RU',
                'timezone_id': 'Europe/Moscow',
                'viewport': {'width': 1920, 'height': 1080},
                # ... остальные опции ...
            }
            
            if playwright_proxy:
                context_options['proxy'] = playwright_proxy
                print(f"🌐 Используем прокси: {playwright_proxy.get('server', 'unknown')}")
            
            context = browser.new_context(**context_options)
            
            # ... остальной код ...
            
            # После успешного парсинга
            if proxy_manager.current_proxy:
                proxy_manager.mark_proxy_success(proxy_manager.current_proxy['id'])
            
        except Exception as e:
            # При ошибке отмечаем прокси как неработающий
            if proxy_manager.current_proxy and "proxy" in str(e).lower():
                proxy_manager.mark_proxy_failure(proxy_manager.current_proxy['id'], str(e))
            raise
```

---

### Этап 5: Интеграция прокси в yandex_business_parser.py

**Файл:** `src/yandex_business_parser.py`

**Для requests сессии:**

```python
from proxy_manager import ProxyManager

class YandexBusinessParser:
    def __init__(self, auth_data: Dict[str, Any], proxy_manager: ProxyManager = None):
        # ... существующий код ...
        self.proxy_manager = proxy_manager or ProxyManager()
        self.current_proxy = None
    
    def _make_request(self, url: str, method: str = "GET", params: Optional[Dict[str, Any]] = None, **kwargs) -> Optional[Dict[str, Any]]:
        # Получаем прокси
        proxy_dict = self.proxy_manager.get_next_proxy()
        self.current_proxy = proxy_dict
        
        # ... существующий код ...
        
        # Настраиваем прокси для requests
        if proxy_dict:
            proxies = {
                "http": proxy_dict["server"],
                "https": proxy_dict["server"]
            }
            kwargs["proxies"] = proxies
        
        response = self.session.request(
            method,
            url,
            headers=headers,
            params=params,
            timeout=30,
            **kwargs,
        )
        
        # После успешного запроса
        if proxy_dict and response.status_code == 200:
            self.proxy_manager.mark_proxy_success(proxy_dict['id'])
        
        return response.json() if response.status_code == 200 else None
```

---

### Этап 6: Создание админ-панели для управления прокси

**Файл:** `src/main.py`

**Эндпоинты:**

```python
@app.route('/api/admin/proxies', methods=['GET'])
def get_proxies():
    """Получить список прокси"""
    # ... авторизация ...
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT id, proxy_type, host, port, is_active, is_working, 
               success_count, failure_count, last_used_at, last_checked_at
        FROM ProxyServers
        ORDER BY created_at DESC
    """)
    
    proxies = []
    for row in cursor.fetchall():
        proxies.append({
            "id": row[0],
            "type": row[1],
            "host": row[2],
            "port": row[3],
            "is_active": bool(row[4]),
            "is_working": bool(row[5]),
            "success_count": row[6],
            "failure_count": row[7],
            "last_used_at": row[8],
            "last_checked_at": row[9]
        })
    
    db.close()
    return jsonify({"proxies": proxies})

@app.route('/api/admin/proxies', methods=['POST'])
def add_proxy():
    """Добавить прокси"""
    # ... авторизация, проверка прав суперадмина ...
    
    data = request.json
    proxy_id = str(uuid.uuid4())
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("""
        INSERT INTO ProxyServers (
            id, proxy_type, host, port, username, password,
            is_active, is_working, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 1, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (
        proxy_id,
        data.get('type', 'http'),
        data['host'],
        data['port'],
        data.get('username'),
        data.get('password')  # TODO: зашифровать
    ))
    db.conn.commit()
    db.close()
    
    return jsonify({"success": True, "proxy_id": proxy_id})

@app.route('/api/admin/proxies/<proxy_id>', methods=['DELETE'])
def delete_proxy(proxy_id):
    """Удалить прокси"""
    # ... авторизация ...
    
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM ProxyServers WHERE id = ?", (proxy_id,))
    db.conn.commit()
    db.close()
    
    return jsonify({"success": True})
```

---

## Порядок выполнения

1. **Создать таблицу ProxyServers** в `init_database_schema.py`
2. **Создать модуль `proxy_manager.py`** с классом `ProxyManager`
3. **Интегрировать прокси в парсеры:**
   - `parser_interception.py`
   - `parser.py`
   - `yandex_business_parser.py`
4. **Создать админ-панель** для управления прокси
5. **Протестировать:**
   - Добавить тестовый прокси
   - Проверить ротацию
   - Проверить обработку ошибок

---

## Чеклист для кодера

- [ ] Создать таблицу `ProxyServers` в `init_database_schema.py`
- [ ] Создать модуль `src/proxy_manager.py` с классом `ProxyManager`:
  - **ВАЖНО:** Только необходимые импорты (typing, safe_db_utils) - см. рекомендации упростителя в SIMPLIFICATION.md
  - **ВАЖНО:** Только поле `current_proxy` (без proxy_cache, cache_ttl)
  - Создать helper `get_playwright_proxy_or_none()` для единообразия
- [ ] Интегрировать прокси в `parser_interception.py`:
  - Использовать helper `get_playwright_proxy_or_none()`
  - Early-return если нет прокси (не создавать лишних веток)
- [ ] Интегрировать прокси в `parser.py`:
  - Использовать тот же helper для единообразия
  - Early-return если нет прокси
- [ ] Интегрировать прокси в `yandex_business_parser.py`:
  - Использовать `ProxyManager` для requests сессии
  - Early-return если нет прокси
- [ ] Создать эндпоинты для управления прокси в `main.py`
- [ ] Создать UI компонент `ProxyManagement.tsx` (см. `FRONTEND_TASK_PROXY_UI.md`)
- [ ] Протестировать ротацию прокси
- [ ] Протестировать обработку неработающих прокси

---

## Важные замечания

1. **Получение прокси:**
   - **Для тестирования:** Использовать бесплатные прокси-листы (Free Proxy List, ProxyScrape)
   - **Для продакшена:** Покупка резидентных прокси (Smartproxy, IPRoyal, Bright Data)
   - **Альтернатива:** VPN API ротация (NordLayer, Surfshark) - медленнее, но проще

2. **Безопасность:**
   - Пароли прокси нужно зашифровать (использовать `auth_encryption.py`)
   - Не логировать пароли
   - Хранить прокси в БД с шифрованием

3. **Производительность:**
   - Прокси могут замедлить запросы на 10-20%
   - Резидентные прокси быстрее и надежнее
   - Бесплатные прокси часто не работают или очень медленные

4. **Мониторинг:**
   - Отслеживать `success_count` и `failure_count`
   - Автоматически исключать неработающие прокси
   - Проверять работоспособность перед использованием

5. **Настройка прокси:**
   - Добавлять прокси через админ-панель (`/api/admin/proxies`)
   - Формат: `http://username:password@host:port` или `socks5://username:password@host:port`
   - Можно добавить несколько прокси для ротации

---

## Ожидаемый результат

**После реализации:**
- Автоматическая ротация IP-адресов между запросами
- Меньше блокировок и капчи от Яндекс
- Распределение нагрузки между прокси
- Автоматическое исключение неработающих прокси
- Админ-панель для управления прокси

