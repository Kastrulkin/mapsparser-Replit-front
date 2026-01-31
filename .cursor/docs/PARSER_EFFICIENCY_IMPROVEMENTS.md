# План повышения эффективности парсера

**Дата:** 2026-02-01  
**Приоритет:** Высокий  
**Статус:** Планирование

---

## 🎯 Цель

Повысить **точность и надежность** парсинга (не просто скорость), устранив проблемы:
- Data Drift (перезапись хороших данных плохими)
- Отсутствие метаданных о качестве данных
- Нет защиты от бана API
- Нет валидации перед записью в БД

---

## 📊 Текущие проблемы

### 1. **Fallback Cascade (перезапись вместо merge)**

**Проблема:** В `parser_interception.py:412-443`:
```python
if not data.get('products'):
    html_products = parse_products(page)
    if html_products:
        data['products'] = html_products  # ❌ Перезапись
```

**Последствия:**
- Если API вернул пустой список → перезаписываем HTML-данными
- Если API вернул данные → игнорируем HTML (даже если он лучше)
- Нет метаданных о источнике данных

### 2. **Нет Quality Score**

**Проблема:** В БД нет информации о:
- Источнике данных (API/HTML/Meta)
- Уровне надежности (0-100)
- Сырых данных для аудита

**Последствия:**
- Невозможно понять, какие данные надежные
- Невозможно автоматически пере-парсить "плохие" данные
- Невозможно показать пользователю предупреждение

### 3. **Нет Circuit Breaker**

**Проблема:** При бане API парсер продолжает спамить запросами → вечный бан.

**Последствия:**
- IP блокируется навсегда
- Нет явного режима деградации
- Пользователь не видит, что API недоступен

### 4. **Нет Data Validation Gates**

**Проблема:** В БД записываются любые данные, даже если они явно некорректные.

**Последствия:**
- Мусорные данные в БД
- Нет логирования проблемных данных
- Невозможно отследить паттерны ошибок

---

## 🚀 План улучшений (по приоритетам)

### **Приоритет 1: Quality Score + Source Priority (2-3 часа)**

#### 1.1. Миграция БД: добавить метаданные

```sql
-- Для ExternalBusinessReviews
ALTER TABLE ExternalBusinessReviews 
ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS quality_score INTEGER DEFAULT 0,
-- raw_snapshot только для плохих данных (quality_score < 50) для экономии места
ADD COLUMN IF NOT EXISTS raw_snapshot TEXT;  -- TEXT для SQLite, JSONB для PostgreSQL (определяется в миграции)

-- Для MapParseResults (общие метрики)
ALTER TABLE MapParseResults
ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) DEFAULT 'unknown',
ADD COLUMN IF NOT EXISTS quality_score INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS parse_metadata JSONB;

-- Индексы для быстрого поиска "плохих" данных
CREATE INDEX IF NOT EXISTS idx_reviews_quality_score 
ON ExternalBusinessReviews(quality_score) WHERE quality_score < 50;

CREATE INDEX IF NOT EXISTS idx_map_parse_quality_score 
ON MapParseResults(quality_score) WHERE quality_score < 50;
```

#### 1.2. Обновить ReviewRepository

```python
# src/repositories/review_repository.py

def upsert_review(
    self, 
    review_data: Dict[str, Any],
    source: str = 'api',
    quality_score: int = 100,
    raw_snapshot: Optional[Dict] = None
) -> str:
    """
    Upsert review with quality score protection.
    
    Правила обновления:
    1. Обновляем если новый quality_score выше существующего
    2. Обновляем если тот же источник и данные свежее (updated_at новее)
    3. Не обновляем если существующий quality_score выше нового
    """
    cursor = self._get_cursor()
    
    # Проверяем существующую запись
    existing = self.get_by_external_id(
        review_data.get('external_review_id'),
        review_data.get('business_id'),
        review_data.get('source')
    )
    
    if existing:
        existing_score = existing.get('quality_score', 0)
        existing_source = existing.get('data_source', 'unknown')
        existing_updated = existing.get('updated_at')
        
        # Правило 1: Новый quality_score выше - обновляем
        if quality_score > existing_score:
            # Обновляем
            pass
        # Правило 2: Тот же источник и данные свежее - обновляем
        elif source == existing_source and existing_updated:
            # Проверяем, что новые данные свежее (в пределах 1 часа)
            from datetime import datetime, timedelta
            try:
                if isinstance(existing_updated, str):
                    existing_dt = datetime.fromisoformat(existing_updated.replace('Z', '+00:00'))
                else:
                    existing_dt = existing_updated
                
                # Если данные старше 1 часа - обновляем
                if datetime.now() - existing_dt > timedelta(hours=1):
                    pass  # Обновляем
                else:
                    # Данные свежие, не обновляем
                    self._logger.debug(
                        f"Skipping upsert: existing data is fresh (updated_at={existing_updated})"
                    )
                    return existing['id']
            except Exception as e:
                self._logger.warning(f"Error parsing updated_at: {e}, updating anyway")
                pass  # Обновляем при ошибке парсинга
        # Правило 3: Существующий quality_score выше - не трогаем
        else:
            self._logger.debug(
                f"Skipping upsert: existing quality_score={existing_score} >= new={quality_score}"
            )
            return existing['id']
    
    # Добавляем метаданные
    review_data['data_source'] = source
    review_data['quality_score'] = quality_score
    
    # raw_snapshot только для плохих данных (экономия места)
    if quality_score < 50 and raw_snapshot:
        # Ограничиваем размер snapshot (первые 1000 символов)
        snapshot_str = json.dumps(raw_snapshot)
        if len(snapshot_str) > 1000:
            snapshot_str = snapshot_str[:1000] + '...'
        
        # Для SQLite храним как TEXT, для PostgreSQL как JSONB
        from config import DB_TYPE
        if DB_TYPE == 'sqlite':
            review_data['raw_snapshot'] = snapshot_str
        else:
            # PostgreSQL автоматически конвертирует JSON строку в JSONB
            review_data['raw_snapshot'] = json.loads(snapshot_str)
    
    # Upsert с учетом quality_score
    # ... (существующая логика upsert)
```

#### 1.3. Source Priority Pipeline в парсере

```python
# src/parser_interception.py

class ParseResult:
    """Результат парсинга с метаданными"""
    def __init__(self, data: Dict, source: str, quality_score: int):
        self.data = data
        self.source = source
        self.quality_score = quality_score
    
    def merge(self, other: 'ParseResult') -> 'ParseResult':
        """Merge двух результатов, выбирая лучшие данные"""
        merged = self.data.copy()
        merged_quality = self.quality_score
        
        # Правило: дополняем только пустые поля, не перезаписываем
        for key, value in other.data.items():
            if not merged.get(key) and value:
                merged[key] = value
                # Quality score = среднее взвешенное
                merged_quality = min(merged_quality, other.quality_score)
        
        return ParseResult(merged, f"{self.source}+{other.source}", merged_quality)

def parse_yandex_card(self, url: str) -> Dict[str, Any]:
    """Парсинг с Source Priority Pipeline"""
    
    # Параллельно собираем из всех источников
    results = []
    
    # 1. API Interception (quality: 100)
    try:
        api_data = self._parse_api_interception(page)
        if api_data:
            results.append(ParseResult(api_data, 'yandex_api_v2', 100))
    except Exception as e:
        self._logger.warning(f"API parsing failed: {e}")
    
    # 2. HTML Fallback (quality: 70)
    try:
        html_data = self._fallback_html_parsing(page, url)
        if html_data:
            results.append(ParseResult(html_data, 'html_fallback', 70))
    except Exception as e:
        self._logger.warning(f"HTML parsing failed: {e}")
    
    # 3. Meta tags (quality: 40)
    try:
        meta_data = self._parse_meta_tags(page)
        if meta_data:
            results.append(ParseResult(meta_data, 'meta_tags', 40))
    except Exception as e:
        self._logger.warning(f"Meta parsing failed: {e}")
    
    # Выбираем лучший результат и мержим остальные
    if not results:
        return {'error': 'all_sources_failed', 'url': url}
    
    # Сортируем по quality_score
    results.sort(key=lambda r: r.quality_score, reverse=True)
    
    # Мержим все результаты (лучший как база)
    final = results[0]
    for other in results[1:]:
        final = final.merge(other)
    
    # Добавляем метаданные
    final.data['_parse_metadata'] = {
        'source': final.source,
        'quality_score': final.quality_score,
        'sources_used': [r.source for r in results]
    }
    
    return final.data
```

---

### **Приоритет 2: Circuit Breaker (1-2 часа)**

#### 2.1. Создать CircuitBreaker класс

**⚠️ ВАЖНО:** Circuit Breaker должен хранить состояние в БД для работы в многопоточном окружении (worker.py + main.py).

```python
# src/parsers/circuit_breaker.py

from datetime import datetime, timedelta
from enum import Enum
from database_manager import get_db_connection

class CircuitState(Enum):
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # API заблокирован, используем только HTML
    HALF_OPEN = "half_open"  # Пробуем восстановить

class CircuitBreaker:
    """
    Circuit Breaker для защиты API от бана.
    
    ВАЖНО: Состояние хранится в БД для работы в многопоточном окружении.
    """
    
    def __init__(
        self,
        api_name: str = 'yandex_api',  # Имя API для изоляции
        failure_threshold: int = 5,
        recovery_timeout: int = 3600,  # 1 час
        success_threshold: int = 2
    ):
        self.api_name = api_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
    
    def _get_state_from_db(self) -> Dict[str, Any]:
        """Получить состояние из БД"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            # Создаем таблицу если не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS CircuitBreakerState (
                    api_name TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    failure_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    last_failure_time TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute(
                "SELECT * FROM CircuitBreakerState WHERE api_name = ?",
                (self.api_name,)
            )
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                # Создаем начальное состояние
                cursor.execute("""
                    INSERT INTO CircuitBreakerState 
                    (api_name, state, failure_count, success_count)
                    VALUES (?, ?, 0, 0)
                """, (self.api_name, CircuitState.CLOSED.value))
                conn.commit()
                return {
                    'state': CircuitState.CLOSED.value,
                    'failure_count': 0,
                    'success_count': 0,
                    'last_failure_time': None
                }
        finally:
            cursor.close()
            conn.close()
    
    def _update_state_in_db(self, state: CircuitState, failure_count: int, success_count: int, last_failure_time: Optional[datetime]):
        """Обновить состояние в БД"""
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE CircuitBreakerState 
                SET state = ?, failure_count = ?, success_count = ?, 
                    last_failure_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE api_name = ?
            """, (
                state.value, failure_count, success_count,
                last_failure_time.isoformat() if last_failure_time else None,
                self.api_name
            ))
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def record_success(self):
        """Записать успешный запрос"""
        state_data = self._get_state_from_db()
        state = CircuitState(state_data['state'])
        failure_count = state_data['failure_count']
        success_count = state_data['success_count']
        
        if state == CircuitState.HALF_OPEN:
            success_count += 1
            if success_count >= self.success_threshold:
                state = CircuitState.CLOSED
                failure_count = 0
                success_count = 0
                print("✅ Circuit Breaker: API восстановлен")
        elif state == CircuitState.CLOSED:
            failure_count = 0  # Сбрасываем счетчик при успехе
        
        self._update_state_in_db(state, failure_count, success_count, None)
    
    def record_failure(self):
        """Записать неудачный запрос"""
        state_data = self._get_state_from_db()
        state = CircuitState(state_data['state'])
        failure_count = state_data['failure_count'] + 1
        last_failure_time = datetime.now()
        
        if failure_count >= self.failure_threshold:
            state = CircuitState.OPEN
            print(f"⚠️ Circuit Breaker: API заблокирован (failures: {failure_count})")
            print(f"   Переходим в режим деградации (только HTML парсинг)")
        
        self._update_state_in_db(state, failure_count, 0, last_failure_time)
    
    def can_call_api(self) -> bool:
        """Можно ли вызывать API?"""
        state_data = self._get_state_from_db()
        state = CircuitState(state_data['state'])
        last_failure_time_str = state_data.get('last_failure_time')
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            # Проверяем, прошло ли время восстановления
            if last_failure_time_str:
                try:
                    last_failure_time = datetime.fromisoformat(last_failure_time_str.replace('Z', '+00:00'))
                    elapsed = (datetime.now() - last_failure_time.replace(tzinfo=None)).total_seconds()
                    if elapsed >= self.recovery_timeout:
                        state = CircuitState.HALF_OPEN
                        self._update_state_in_db(state, state_data['failure_count'], 0, last_failure_time)
                        print("🔄 Circuit Breaker: Пробуем восстановить API (half-open)")
                        return True
                except Exception as e:
                    print(f"⚠️ Error parsing last_failure_time: {e}")
            return False
        
        if state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус для логирования"""
        state_data = self._get_state_from_db()
        return {
            'api_name': self.api_name,
            'state': state_data['state'],
            'failure_count': state_data['failure_count'],
            'last_failure_time': state_data.get('last_failure_time')
        }
```

#### 2.2. Интегрировать в YandexMapsInterceptionParser

```python
# src/parser_interception.py

class YandexMapsInterceptionParser:
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
    
    def parse_yandex_card(self, url: str) -> Dict[str, Any]:
        """Парсинг с Circuit Breaker"""
        
        # Проверяем, можно ли вызывать API
        if not self.circuit_breaker.can_call_api():
            print("⚠️ API недоступен (Circuit Breaker OPEN), используем только HTML")
            html_data = self._fallback_html_parsing(page, url)
            html_data['_degradation_mode'] = True
            html_data['_circuit_breaker_status'] = self.circuit_breaker.get_status()
            return html_data
        
        # Пробуем API
        try:
            api_data = self._parse_api_interception(page)
            self.circuit_breaker.record_success()
            return api_data
        except Exception as e:
            self.circuit_breaker.record_failure()
            # Fallback на HTML
            html_data = self._fallback_html_parsing(page, url)
            html_data['_degradation_mode'] = True
            html_data['_circuit_breaker_status'] = self.circuit_breaker.get_status()
            return html_data
```

---

### **Приоритет 3: Data Validation Gates (1-2 часа)**

#### 3.1. Создать валидаторы

```python
# src/parsers/validators.py

from typing import Dict, Any, List, Optional
from dataclasses import dataclass

@dataclass
class ValidationError:
    field: str
    value: Any
    reason: str
    severity: str  # 'error' or 'warning'

class DataValidator:
    """Валидатор данных перед записью в БД"""
    
    @staticmethod
    def validate_review(review_data: Dict[str, Any], source: str) -> List[ValidationError]:
        """Валидация отзыва"""
        errors = []
        
        # Проверка rating
        rating = review_data.get('rating')
        if rating:
            try:
                rating_float = float(rating)
                if not (1 <= rating_float <= 5):
                    errors.append(ValidationError(
                        'rating', rating, 
                        f"Rating out of range: {rating_float}",
                        'error'
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    'rating', rating,
                    f"Invalid rating format: {rating}",
                    'error'
                ))
        
        # Проверка text (более мягкая для названий, строже для текстов)
        text = review_data.get('text', '')
        if source == 'html_meta' and text and len(text) < 10:  # Минимум 10 символов для текста отзыва
            errors.append(ValidationError(
                'text', text,
                "Text too short for meta-source (minimum 10 chars)",
                'warning'
            ))
        
        # Проверка author_name (минимум 1 символ - названия могут быть короткими)
        author_name = review_data.get('author_name', '')
        if source == 'html_meta' and author_name and len(author_name) < 1:
            errors.append(ValidationError(
                'author_name', author_name,
                "Author name too short for meta-source",
                'warning'
            ))
        
        return errors
    
    @staticmethod
    def validate_service(service_data: Dict[str, Any], source: str) -> List[ValidationError]:
        """Валидация услуги"""
        errors = []
        
        name = service_data.get('name', '')
        # Названия услуг могут быть короткими (например, "Я" - валидное название)
        if source == 'html_meta' and name and len(name) < 1:
            errors.append(ValidationError(
                'name', name,
                "Service name too short for meta-source (minimum 1 char)",
                'error'
            ))
        
        return errors
```

#### 3.2. Интегрировать в Repository

```python
# src/repositories/review_repository.py

from parsers.validators import DataValidator

def upsert_review(self, review_data: Dict, source: str, quality_score: int) -> str:
    """Upsert с валидацией"""
    
    # Валидация
    validation_errors = DataValidator.validate_review(review_data, source)
    
    # Критические ошибки - не записываем
    critical_errors = [e for e in validation_errors if e.severity == 'error']
    if critical_errors:
        error_msg = f"Validation failed: {[e.reason for e in critical_errors]}"
        self._logger.warning(f"Skipping upsert due to validation errors: {error_msg}")
        # Логируем в RawParseLogs для ручной проверки
        self._log_validation_errors(review_data, validation_errors)
        raise ValueError(error_msg)
    
    # Предупреждения - записываем, но снижаем quality_score
    warnings = [e for e in validation_errors if e.severity == 'warning']
    if warnings:
        quality_score = max(0, quality_score - 10 * len(warnings))
        self._logger.debug(f"Validation warnings: {[e.reason for e in warnings]}")
    
    # Upsert
    # ... (существующая логика)
```

---

### **Приоритет 4: Source Priority (без Merge) (1 час)**

**⚠️ КРИТИЧНО:** Merge API + HTML по имени создает data corruption (устаревшие данные HTML смешиваются с актуальными API).

#### 4.1. Исправить логику в parser_interception.py

**Правило:** Если API вернул данные (даже пустой список) — используем только API. HTML используется только если API полностью не сработал.

```python
# src/parser_interception.py:412-443

# БЫЛО (перезапись):
if not data.get('products'):
    html_products = parse_products(page)
    if html_products:
        data['products'] = html_products  # ❌ Перезапись

# СТАЛО (Source Priority, без merge):
# Правило: API данные никогда не перезаписываются HTML-данными
api_products = data.get('products', [])

# Если API вернул пустой список - это значит услуг нет, не парсим HTML
if api_products is None:
    # API не сработал вообще - используем HTML как fallback
    print("⚠️ API не вернул данные об услугах, пробуем HTML парсинг...")
    try:
        from yandex_maps_scraper import parse_products
        html_products = parse_products(page)
        if html_products:
            data['products'] = html_products
            data['_parse_metadata'] = {
                'products_source': 'html_fallback',
                'products_quality_score': 70,
                'degraded_mode': True
            }
    except Exception as e:
        print(f"⚠️ HTML парсинг услуг не удался: {e}")
        data['products'] = []  # Явно пустой список
        data['_parse_metadata'] = {
            'products_source': 'none',
            'products_quality_score': 0
        }
elif api_products == []:
    # API вернул пустой список - услуг нет, не используем HTML
    print("✅ API вернул пустой список услуг - услуг нет")
    data['products'] = []
    data['_parse_metadata'] = {
        'products_source': 'api',
        'products_quality_score': 100
    }
else:
    # API вернул данные - используем только их
    data['_parse_metadata'] = {
        'products_source': 'api',
        'products_quality_score': 100
    }
```

---

## 📋 Чеклист внедрения (с учетом критических исправлений)

### Этап 1: Quality Score (2-3 часа) - КРИТИЧНО
- [ ] Создать миграцию БД для `data_source`, `quality_score`, `raw_snapshot` (TEXT для SQLite, JSONB для PostgreSQL)
- [ ] Обновить `ReviewRepository.upsert_review()` с защитой от перезаписи + проверка `updated_at`
- [ ] Ограничить `raw_snapshot` только для `quality_score < 50` (экономия места)
- [ ] Реализовать `ParseResult` класс (без merge по имени - только Source Priority)
- [ ] Обновить `parse_yandex_card()` для Source Priority Pipeline (API → HTML → Meta, без merge)
- [ ] Протестировать на реальных данных

### Этап 2: Circuit Breaker (1-2 часа) - ВАЖНО
- [ ] Создать таблицу `CircuitBreakerState` в БД
- [ ] Создать `CircuitBreaker` класс с хранением состояния в БД (для многопоточности)
- [ ] Интегрировать в `YandexMapsInterceptionParser`
- [ ] Добавить логирование статуса в worker.py
- [ ] Протестировать сценарий бана API в многопоточном окружении

### Этап 3: Data Validation (1-2 часа)
- [ ] Создать `DataValidator` класс с мягкой валидацией (минимум 1 символ для названий, 10 для текстов)
- [ ] Интегрировать в `ReviewRepository` и `ServiceRepository`
- [ ] Создать таблицу `RawParseLogs` для проблемных данных
- [ ] Протестировать валидацию

### Этап 4: Source Priority (без merge) (1 час) - КРИТИЧНО
- [ ] Исправить логику в `parser_interception.py` (отказаться от merge по имени)
- [ ] Правило: Если API вернул данные (даже пустой список) - используем только API
- [ ] HTML используется только если API полностью не сработал
- [ ] Протестировать на реальных данных

---

## 🎯 Ожидаемые результаты

1. **Точность данных:** Quality Score позволяет отслеживать надежность
2. **Защита от бана:** Circuit Breaker предотвращает вечный бан IP (работает в многопоточном окружении)
3. **Чистота БД:** Validation Gates не пропускают мусорные данные (мягкая валидация)
4. **Data Drift устранен:** Source Priority (без merge) предотвращает смешивание устаревших HTML-данных с актуальными API-данными
5. **Экономия места:** `raw_snapshot` хранится только для плохих данных (`quality_score < 50`)
6. **Обновление старых данных:** Проверка `updated_at` позволяет обновлять старые данные новыми (даже если источник тот же)

---

## 📝 Примечания

- Все изменения совместимы с Phase 3.5 (Repository Pattern)
- Миграции БД можно применять постепенно
- Circuit Breaker можно включать через feature flag
- Validation можно настраивать по источникам

---

## ⚠️ Критические исправления (внесены в план)

### 1. **Отказ от Merge API + HTML**
- ❌ **Было:** Merge по имени создавал data corruption (устаревшие HTML-данные смешивались с актуальными API)
- ✅ **Стало:** Source Priority - если API вернул данные (даже пустой список), используем только API. HTML только если API полностью не сработал.

### 2. **Ограничение raw_snapshot**
- ❌ **Было:** Хранение полного RAW ответа для всех записей → гигабайты данных
- ✅ **Стало:** `raw_snapshot` только для `quality_score < 50` (экономия места), ограничение размера до 1000 символов

### 3. **Проверка updated_at в quality_score**
- ❌ **Было:** Quality Score без timestamp → старые данные не обновлялись новыми
- ✅ **Стало:** Обновляем если новый `quality_score` выше ИЛИ тот же источник и данные свежее (старше 1 часа)

### 4. **SQLite vs PostgreSQL**
- ❌ **Было:** `JSONB` - только PostgreSQL
- ✅ **Стало:** `TEXT` для SQLite, `JSONB` для PostgreSQL (определяется в миграции)

### 5. **Многопоточность Circuit Breaker**
- ❌ **Было:** Состояние в `self` → не работает в многопоточном окружении
- ✅ **Стало:** Состояние в БД (таблица `CircuitBreakerState`) → работает в worker.py + main.py

### 6. **Мягкая валидация**
- ❌ **Было:** Слишком жесткая валидация (минимум 3 символа для названий)
- ✅ **Стало:** Мягкая валидация (минимум 1 символ для названий, 10 для текстов отзывов)

---

**Следующий шаг:** Начать с Приоритета 1 (Quality Score) с учетом всех критических исправлений - это даст максимальный эффект при минимальных изменениях.
