# Поиск API Endpoints Яндекс.Бизнес

## Проблема

Нужно найти правильные API endpoints для получения:
1. **Отзывов** из личного кабинета
2. **Статистики** (просмотры, клики, действия, рейтинг)
3. **Публикаций/новостей** из личного кабинета
4. **Фотографий** (количество) из личного кабинета

## ✅ Найденные Endpoints

### Публикации/Новости и Фотографии

**Правильный endpoint для публикаций и фотографий:**
```
https://yandex.ru/business/server-components/sidebar?permalink={ORG_ID}
```

Где `{ORG_ID}` - это ID организации (например, `203293742306`)

**Как найти в Network tab:**
1. Откройте страницу публикаций: `https://yandex.ru/sprav/{ORG_ID}/p/edit/posts/`
2. Или страницу фотографий: `https://yandex.ru/sprav/{ORG_ID}/p/edit/photos/`
3. Откройте DevTools → Network tab
4. Найдите запрос в **Request initiator chain**:
   - Страница → JavaScript файл → `https://yandex.ru/business/server-components/sidebar?permalink={ORG_ID}`
5. Этот endpoint возвращает данные как для публикаций, так и для фотографий

**Примечание:** Один и тот же endpoint используется для получения данных о публикациях и фотографиях. Данные находятся в структуре ответа `sidebar`.

## Способ 1: Через DevTools браузера (рекомендуется)

### Шаги:

1. **Откройте страницу отзывов в браузере:**
   ```
   https://yandex.ru/sprav/{ORG_ID}/p/edit/reviews/
   ```
   Где `{ORG_ID}` - это ID организации (например, `203293742306`)

2. **Откройте DevTools:**
   - **Chrome/Edge**: `F12` или `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - **Firefox**: `F12` или `Ctrl+Shift+I`

3. **Перейдите на вкладку Network (Сеть):**
   - Вверху DevTools найдите вкладку "Network" / "Сеть"
   - Убедитесь, что включена запись (красная кнопка должна быть активна)

4. **Очистите список запросов:**
   - Нажмите кнопку "Clear" (Очистить) или `Ctrl+L`

5. **Обновите страницу:**
   - Нажмите `F5` или `Ctrl+R`
   - Или перейдите на другую вкладку и вернитесь обратно

6. **Найдите запросы, которые загружают отзывы:**
   - В списке запросов ищите:
     - **XHR** или **Fetch** запросы (не JS, CSS, изображения)
     - URL, содержащие слова: `review`, `reviews`, `api`, `sprav`
     - Запросы с типом `json` или `xhr`
   
   **Примеры URL, которые могут быть:**
   ```
   https://yandex.ru/sprav/api/organizations/203293742306/reviews
   https://business.yandex.ru/api/organizations/203293742306/reviews
   https://yandex.ru/api/sprav/organizations/203293742306/reviews
   ```

7. **Откройте найденный запрос:**
   - Кликните на запрос
   - Перейдите на вкладку **Headers** (Заголовки)
   - Скопируйте **Request URL** (URL запроса)

8. **Проверьте ответ:**
   - Перейдите на вкладку **Response** (Ответ) или **Preview**
   - Убедитесь, что там есть данные об отзывах (JSON с массивом отзывов)

9. **Скопируйте URL и обновите код:**
   - Откройте `src/yandex_business_parser.py`
   - Найдите список `possible_urls` в методе `fetch_reviews()`
   - Добавьте найденный URL в начало списка

### Для статистики:

Повторите те же шаги, но на странице статистики:
```
https://yandex.ru/sprav/{ORG_ID}/p/edit/stats/
```

Ищите запросы с словами: `stats`, `statistics`, `metrics`

## Способ 2: Через скрипт автоматического поиска

Я создал скрипт, который автоматически пробует различные варианты endpoints:

```bash
cd "/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/AI bots/SEO с Реплит на Курсоре"
source venv/bin/activate
python scripts/find_yandex_api_endpoints.py
```

Скрипт автоматически найдёт бизнес "Оливер" в БД и протестирует все возможные endpoints.

Скрипт:
- Загрузит cookies из БД
- Попробует различные варианты endpoints
- Покажет, какие из них работают
- Выведет структуру ответа

## Способ 3: Проверка встроенных данных в HTML и глобальных переменных

Иногда данные могут быть встроены прямо в HTML страницы или в глобальные переменные JavaScript.

### Шаг 1: Проверка глобальных переменных в консоли

1. Откройте страницу отзывов в браузере
2. Откройте DevTools → Console (Консоль)
3. Выполните следующие команды:

```javascript
// Проверяем глобальные переменные с данными
console.log(window.__INITIAL_STATE__);
console.log(window.__DATA__);
console.log(window.__PRELOADED_STATE__);
console.log(window.initialData);
console.log(window.reviewsData);

// Ищем все глобальные переменные, содержащие "review" или "data"
Object.keys(window).filter(k => k.toLowerCase().includes('review') || k.toLowerCase().includes('data')).forEach(k => console.log(k, window[k]));
```

Если какая-то переменная содержит данные, скопируйте её и используйте для парсинга.

### Шаг 2: Поиск данных в исходном HTML

1. Откройте страницу отзывов
2. Нажмите `Ctrl+U` (просмотр исходного кода) или `Cmd+Option+U` (Mac)
3. Нажмите `Ctrl+F` и ищите:
   - `window.__INITIAL_STATE__`
   - `window.__DATA__`
   - `"reviews"`
   - `var reviews =`
   - `const reviews =`
   - `JSON.parse`

Если найдёте JSON данные в HTML, можно их парсить напрямую.

### Шаг 3: Поиск в Network tab при загрузке страницы

1. Откройте DevTools → Network
2. Очистите список запросов (Clear)
3. Обновите страницу (F5)
4. Ищите запросы типа:
   - `document` (HTML страница)
   - `xhr` или `fetch` (API запросы)
   - `js` (JavaScript файлы, могут содержать данные)

5. Откройте запрос типа `document` (сама страница)
6. Перейдите на вкладку **Response** (Ответ)
7. Нажмите `Ctrl+F` и ищите `"reviews"` или `"statistics"`

Если данные встроены в HTML, они будут в Response.

## Что делать после нахождения endpoints

1. **Обновите `src/yandex_business_parser.py`:**
   - Добавьте найденный URL в начало списка `possible_urls` в методе `fetch_reviews()`
   - Или в `fetch_stats()` для статистики
   - Для публикаций: обновите `sidebar_url` в методе `fetch_posts()`
   - Для фотографий: обновите `sidebar_url` в методе `fetch_photos_count()`

2. **Проверьте структуру ответа:**
   - Откройте Response в DevTools
   - Убедитесь, что понимаете структуру JSON
   - Обновите код парсинга в соответствующих методах, если структура отличается
   - Для `sidebar` endpoint: данные могут быть вложены в структуру, используйте рекурсивный поиск

3. **Протестируйте:**
   ```bash
   python scripts/test_oliver_yandex.py
   ```
   Или для конкретного бизнеса:
   ```bash
   python tests/test_yandex_business_connection.py <BUSINESS_ID>
   ```

## Типичные структуры ответов

### Отзывы:
```json
{
  "reviews": [
    {
      "id": "123",
      "rating": 5,
      "text": "Отличный сервис!",
      "author": {
        "name": "Иван Иванов"
      },
      "published_at": "2024-01-01T00:00:00Z",
      "response": {
        "text": "Спасибо!",
        "created_at": "2024-01-02T00:00:00Z"
      }
    }
  ]
}
```

### Статистика:
```json
{
  "stats": [
    {
      "date": "2024-01-01",
      "views": 100,
      "clicks": 10,
      "actions": 5,
      "rating": 4.8,
      "reviews_count": 123
    }
  ]
}
```

### Sidebar (публикации и фотографии):
```json
{
  "sidebar": {
    "posts": [
      {
        "id": "123",
        "title": "Новая акция",
        "text": "Описание акции",
        "published_at": "2024-01-01T00:00:00Z",
        "image_url": "https://..."
      }
    ],
    "photos": {
      "total": 62,
      "categories": [
        {"count": 9},
        {"count": 2}
      ]
    }
  }
}
```

**Важно:** Структура `sidebar` может быть вложенной и отличаться. Парсер использует рекурсивный поиск для нахождения данных о публикациях и фотографиях в любом месте структуры ответа.

Но структура может отличаться! Всегда проверяйте реальный ответ в DevTools.

## Полезные советы

1. **Фильтры в DevTools:**
   - Используйте фильтр "XHR" или "Fetch" для показа только API запросов
   - Используйте поиск по URL (Ctrl+F в списке запросов)

2. **Preserve log:**
   - Включите "Preserve log" в Network tab, чтобы запросы не очищались при переходах

3. **Copy as cURL:**
   - Правый клик на запросе → "Copy" → "Copy as cURL"
   - Можно использовать для тестирования в терминале

4. **Проверка авторизации:**
   - Убедитесь, что cookies актуальны
   - Если получаете 401/403, возможно нужно обновить cookies в БД

