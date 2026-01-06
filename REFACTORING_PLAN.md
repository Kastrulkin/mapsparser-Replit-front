# План рефакторинга main.py (8872 строки)

## Структура модулей

### 1. `api/business_api.py` - API для бизнесов
- `/api/business/<business_id>/external-accounts` (GET, POST)
- `/api/external-accounts/<account_id>` (DELETE)
- `/api/business/<business_id>/external-accounts/test` (POST)
- `/api/business/<business_id>/external/reviews` (GET)
- `/api/business/<business_id>/external/summary` (GET)
- `/api/business/<business_id>/external/posts` (GET)
- `/api/business/<business_id>/parse-status` (GET)
- `/api/business/<business_id>/map-parses` (GET)
- `/api/business/<business_id>/data` (GET)
- И другие бизнес-эндпоинты

### 2. `api/services_api.py` - API для услуг
- `/api/services/add` (POST)
- `/api/services/list` (GET)
- `/api/services/update/<service_id>` (PUT)
- `/api/services/delete/<service_id>` (DELETE)
- `/api/services/optimize` (POST)

### 3. `api/news_api.py` - API для новостей
- `/api/news/generate` (POST)
- `/api/news/approve` (POST)
- `/api/news/list` (GET)
- `/api/news/update` (POST)
- `/api/news/delete` (POST)
- `/api/news-examples` (GET, POST)
- `/api/news-examples/<example_id>` (DELETE)

### 4. `api/reviews_api.py` - API для отзывов
- `/api/reviews/reply` (POST)
- `/api/review-replies/update` (POST)
- `/api/review-examples` (GET, POST)
- `/api/review-examples/<example_id>` (DELETE)

### 5. `api/analysis_api.py` - API для анализа
- `/api/analyze` (POST)
- `/api/analyze-card-auto` (POST)
- `/api/analyze-screenshot` (POST)
- `/api/optimize-pricelist` (POST)
- `/api/analysis/<analysis_id>` (GET)

### 6. `api/admin_api.py` - Админские функции
- `/api/admin/token-usage` (GET)
- `/api/superadmin/users/<user_id>` (DELETE)
- `/api/superadmin/users/<user_id>/pause` (POST)
- `/api/superadmin/users/<user_id>/unpause` (POST)
- `/api/admin/business-types` (GET)

### 7. `api/finance_api.py` - Финансовые API
- `/api/finance/metrics` (GET)
- И другие финансовые эндпоинты

### 8. `api/masters_api.py` - API для мастеров
- `/api/business/<business_id>/masters` (GET, POST)
- `/api/masters/<master_id>` (PUT, DELETE)

### 9. `api/networks_api.py` - API для сетей
- `/api/networks` (GET, POST)
- `/api/networks/<network_id>` (GET, PUT, DELETE)
- `/api/networks/<network_id>/businesses` (POST)
- `/api/networks/<network_id>/stats` (GET)

### 10. `api/public_api.py` - Публичные API
- `/api/business-types` (GET)
- `/api/geo/payment-provider` (GET)
- `/api/examples` (GET, POST)
- `/api/examples/<example_id>` (DELETE)

### 11. `api/users_api.py` - API для пользователей
- `/api/users/reports` (GET)
- `/api/users/queue` (GET)
- `/api/client-info` (GET, POST, PUT)

### 12. `core/helpers.py` - Helper функции
- `get_business_owner_id()`
- `get_business_id_from_user()`
- `get_user_language()`
- `rate_limit_if_available()`

### 13. `core/app_factory.py` - Создание Flask app
- Инициализация Flask
- Настройка CORS
- Настройка rate limiting
- Регистрация Blueprint'ов

### 14. `core/routes.py` - Основные роуты
- `/` (SPA fallback)
- `/health`
- `/favicon.ico`
- `/robots.txt`
- SPA fallback для всех остальных путей

## Порядок выполнения

1. ✅ Создать `core/helpers.py` с helper функциями
2. ✅ Создать `core/app_factory.py` для инициализации app
3. Создать модули API по одному
4. Обновить `main.py` для использования модулей
5. Тестирование

## Преимущества

- Модульность: каждый модуль отвечает за свою область
- Читаемость: легче найти нужный код
- Тестируемость: можно тестировать модули отдельно
- Масштабируемость: легко добавлять новые модули

