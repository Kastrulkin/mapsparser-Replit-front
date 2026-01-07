# Проблема: optimized_name и optimized_description не возвращаются из API

## Симптомы

1. **Данные сохраняются в БД** ✅
   - Логи Flask показывают: `✅ DEBUG services_api.update_service: Проверка после UPDATE - optimized_name = 'Безаммиачное окрашивание...'`
   - UPDATE выполняется успешно (`rowcount = 1`)
   - Проверка после UPDATE подтверждает сохранение данных

2. **Данные НЕ возвращаются при загрузке** ❌
   - Логи браузера показывают: `optimized_name: undefined`
   - Поля отсутствуют в ответе API `/api/services/list`

## Технические детали

### Эндпоинты
- **Сохранение**: `PUT /api/services/update/<service_id>` в `src/api/services_api.py` ✅ Работает
- **Загрузка**: `GET /api/services/list?business_id=...` в `src/main.py` ❌ Не возвращает поля

### База данных
- Таблица: `UserServices`
- Поля существуют: `optimized_name TEXT`, `optimized_description TEXT` (миграция применена)
- `row_factory = sqlite3.Row` установлен в `src/safe_db_utils.py`

### Проблемный код
**Файл**: `src/main.py`, функция `get_services()` (строка ~2973)

**Текущая логика**:
1. Проверяет наличие полей в таблице через `PRAGMA table_info`
2. Формирует динамический SELECT с полями `optimized_name` и `optimized_description`
3. Выполняет запрос и получает `sqlite3.Row` объекты
4. **ПРОБЛЕМА**: Не извлекает значения из `sqlite3.Row` правильно

**Код извлечения** (строки ~3103-3128):
```python
if has_optimized_name:
    try:
        val = service['optimized_name']
        if val:
            service_dict['optimized_name'] = val
    except (KeyError, IndexError):
        pass
```

### Гипотезы проблемы

1. **Поля не включаются в SELECT** - но логи показывают, что они включаются
2. **Поля NULL в БД** - но проверка после UPDATE показывает, что данные есть
3. **Неправильное извлечение из sqlite3.Row** - наиболее вероятно
4. **Проблема с порядком полей в SELECT** - возможно, порядок не соответствует ожидаемому

## Что нужно проверить

1. **Логи Flask при загрузке**:
   ```bash
   tail -100 /tmp/seo_main.out | grep -A 10 "DEBUG get_services.*3772931e"
   ```
   Должны показать:
   - SQL запрос с полями
   - Значения из Row объекта
   - Что попадает в service_dict

2. **Прямая проверка БД**:
   ```sql
   SELECT id, name, optimized_name, optimized_description 
   FROM UserServices 
   WHERE id = '3772931e-9796-475b-b439-ee1cc07b1dc9';
   ```

3. **Проверка row_factory**:
   - Убедиться, что `conn.row_factory = sqlite3.Row` установлен
   - Проверить, что `service.keys()` возвращает правильные ключи

## Ожидаемое поведение

После оптимизации услуги:
1. `optimized_name` и `optimized_description` сохраняются в БД ✅
2. При загрузке списка услуг эти поля возвращаются в JSON ❌
3. На фронтенде отображаются под оригинальными названием и описанием с кнопками "Принять"/"Отклонить" ❌

## Файлы для проверки

- `src/main.py` - функция `get_services()` (строка ~2973)
- `src/api/services_api.py` - функция `update_service()` (строка ~149) ✅ Работает
- `src/safe_db_utils.py` - настройка `row_factory` (строка ~32)

## Приоритет

**КРИТИЧЕСКИЙ** - функциональность не работает, пользователь не может видеть оптимизированные предложения

