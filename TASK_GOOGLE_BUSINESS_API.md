# Задача: Полная интеграция Google Business Profile API

**Дата:** 2025-01-06  
**Приоритет:** Высокий  
**Исполнитель:** Кодер

---

## Цель

Реализовать полную интеграцию с Google Business Profile API для:
- Получения данных (услуги, новости, отзывы, статистика)
- Публикации данных (формулировки услуг, новости, ответы на отзывы)
- Получения расширенной статистики (посетители, рейтинги, клики, построение маршрутов)

---

## Google Business Profile API - Возможности

### ✅ Что можно делать через API:

1. **Получение данных:**
   - Отзывы (`reviews.list`, `reviews.get`)
   - Статистика (`locations.reportInsights`)
   - Информация о локации (`locations.get`)
   - Посты/публикации (`localPosts.list`, `localPosts.get`)
   - Фото (`media.list`)
   - Услуги (`attributes.get`)

2. **Публикация данных:**
   - ✅ Ответы на отзывы (`reviews.updateReply`)
   - ✅ Посты/публикации (`localPosts.create`, `localPosts.update`)
   - ✅ Фото (`media.create`)
   - ⚠️ Услуги - через `attributes.update` (ограниченно)

3. **Статистика:**
   - Просмотры карты (`LOCATION_SEARCH_QUERIES`)
   - Клики по кнопке "Позвонить" (`ACTION_TYPE_PHONE`)
   - Построение маршрутов (`ACTION_TYPE_GET_DIRECTIONS`)
   - Переходы на сайт (`ACTION_TYPE_WEBSITE`)
   - Запросы на звонок (`ACTION_TYPE_REQUEST_QUOTE`)
   - Просмотры фото (`PHOTO_VIEWS`)
   - Поисковые запросы (`SEARCH_QUERIES`)

### ⚠️ Ограничения:

- **Услуги (Services)**: Google Business Profile API не предоставляет прямой способ редактирования услуг через API. Услуги управляются через веб-интерфейс Google Business Profile.
- **Атрибуты**: Можно обновлять некоторые атрибуты через `attributes.update`, но не все.

---

## Архитектура решения

### 1. OAuth 2.0 аутентификация

**Файл:** `src/google_business_auth.py` (создать)

```python
"""
OAuth 2.0 аутентификация для Google Business Profile API
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleBusinessAuth:
    def __init__(self):
        self.client_id = os.getenv('GOOGLE_CLIENT_ID')
        self.client_secret = os.getenv('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:8000/api/google/oauth/callback')
        self.scopes = [
            'https://www.googleapis.com/auth/business.manage',
            'https://www.googleapis.com/auth/businessprofileperformance'
        ]
    
    def get_authorization_url(self, state: str) -> str:
        """Получить URL для авторизации"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        return authorization_url
    
    def get_credentials_from_code(self, code: str) -> Credentials:
        """Получить credentials из authorization code"""
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        flow.fetch_token(code=code)
        return flow.credentials
```

### 2. Google Business API клиент

**Файл:** `src/google_business_api.py` (создать)

```python
"""
Клиент для работы с Google Business Profile API
"""
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

class GoogleBusinessAPI:
    def __init__(self, credentials: Credentials):
        self.service = build('mybusiness', 'v4', credentials=credentials)
        self.account_service = self.service.accounts()
        self.locations_service = self.service.accounts().locations()
    
    def list_locations(self, account_name: str) -> List[Dict[str, Any]]:
        """Получить список локаций"""
        try:
            response = self.account_service.locations().list(
                parent=account_name
            ).execute()
            return response.get('locations', [])
        except HttpError as e:
            print(f"❌ Ошибка получения локаций: {e}")
            return []
    
    def get_location(self, location_name: str) -> Optional[Dict[str, Any]]:
        """Получить информацию о локации"""
        try:
            return self.locations_service.get(name=location_name).execute()
        except HttpError as e:
            print(f"❌ Ошибка получения локации: {e}")
            return None
    
    def list_reviews(self, location_name: str, page_size: int = 50) -> List[Dict[str, Any]]:
        """Получить отзывы"""
        try:
            response = self.locations_service.reviews().list(
                parent=location_name,
                pageSize=page_size
            ).execute()
            return response.get('reviews', [])
        except HttpError as e:
            print(f"❌ Ошибка получения отзывов: {e}")
            return []
    
    def update_review_reply(self, location_name: str, review_id: str, reply_text: str) -> bool:
        """Опубликовать ответ на отзыв"""
        try:
            self.locations_service.reviews().updateReply(
                name=f"{location_name}/reviews/{review_id}",
                body={
                    'reply': {
                        'comment': reply_text
                    }
                }
            ).execute()
            return True
        except HttpError as e:
            print(f"❌ Ошибка публикации ответа: {e}")
            return False
    
    def list_local_posts(self, location_name: str) -> List[Dict[str, Any]]:
        """Получить посты/публикации"""
        try:
            response = self.locations_service.localPosts().list(
                parent=location_name
            ).execute()
            return response.get('localPosts', [])
        except HttpError as e:
            print(f"❌ Ошибка получения постов: {e}")
            return []
    
    def create_local_post(self, location_name: str, post_data: Dict[str, Any]) -> Optional[str]:
        """Создать пост/публикацию"""
        try:
            response = self.locations_service.localPosts().create(
                parent=location_name,
                body=post_data
            ).execute()
            return response.get('name')
        except HttpError as e:
            print(f"❌ Ошибка создания поста: {e}")
            return None
    
    def get_insights(self, location_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """Получить статистику (insights)"""
        try:
            response = self.locations_service.reportInsights(
                name=location_name,
                body={
                    'locationNames': [location_name],
                    'basicRequest': {
                        'metricRequests': [
                            {
                                'metric': 'QUERIES_DIRECT',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'QUERIES_INDIRECT',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'VIEWS_MAPS',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'VIEWS_SEARCH',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'ACTIONS_WEBSITE',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'ACTIONS_PHONE',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'ACTIONS_DRIVING_DIRECTIONS',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'PHOTOS_VIEWS_MERCHANT',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'PHOTOS_VIEWS_CUSTOMERS',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'PHOTOS_COUNT_MERCHANT',
                                'options': ['AGGREGATED_DAILY']
                            },
                            {
                                'metric': 'PHOTOS_COUNT_CUSTOMERS',
                                'options': ['AGGREGATED_DAILY']
                            }
                        ],
                        'timeRange': {
                            'startTime': start_date,
                            'endTime': end_date
                        }
                    }
                }
            ).execute()
            return response
        except HttpError as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {}
```

### 3. Обновление GoogleBusinessSyncWorker

**Файл:** `src/google_business_sync_worker.py`

**Заменить заглушки на реальные вызовы API:**

```python
from google_business_api import GoogleBusinessAPI
from google_business_auth import GoogleBusinessAuth
from auth_encryption import decrypt_auth_data, encrypt_auth_data

class GoogleBusinessSyncWorker:
    def __init__(self) -> None:
        self.source = ExternalSource.GOOGLE_BUSINESS
        self.auth = GoogleBusinessAuth()
    
    def _get_api_client(self, account: dict) -> Optional[GoogleBusinessAPI]:
        """Получить API клиент для аккаунта"""
        try:
            auth_data_encrypted = account.get('auth_data')
            if not auth_data_encrypted:
                return None
            
            # Расшифровываем credentials
            auth_data_json = decrypt_auth_data(auth_data_encrypted)
            auth_data = json.loads(auth_data_json)
            
            # Восстанавливаем credentials
            credentials = Credentials.from_authorized_user_info(auth_data)
            
            # Обновляем токен, если нужно
            if credentials.expired:
                credentials.refresh(Request())
                # Сохраняем обновленные credentials
                self._save_credentials(account['id'], credentials)
            
            return GoogleBusinessAPI(credentials)
        except Exception as e:
            print(f"❌ Ошибка создания API клиента: {e}")
            return None
    
    def _fetch_reviews(self, account: dict) -> List[ExternalReview]:
        """Получить отзывы через API"""
        api = self._get_api_client(account)
        if not api:
            return []
        
        location_name = account.get('external_id')  # Google location name
        if not location_name:
            return []
        
        reviews_data = api.list_reviews(location_name)
        reviews = []
        
        for review_data in reviews_data:
            review_id = review_data.get('reviewId')
            review = review_data.get('review', {})
            
            # Парсим дату
            published_at = None
            if 'createTime' in review:
                published_at = datetime.fromisoformat(review['createTime'].replace('Z', '+00:00'))
            
            # Парсим ответ организации
            response_text = None
            response_at = None
            if 'reply' in review:
                reply = review['reply']
                response_text = reply.get('comment', '')
                if 'updateTime' in reply:
                    response_at = datetime.fromisoformat(reply['updateTime'].replace('Z', '+00:00'))
            
            reviews.append(ExternalReview(
                id=f"{account['business_id']}_google_{review_id}",
                business_id=account['business_id'],
                source=self.source,
                external_review_id=review_id,
                rating=review.get('starRating', {}).get('value'),
                author_name=review.get('reviewer', {}).get('displayName', 'Анонимный пользователь'),
                text=review.get('comment', ''),
                published_at=published_at,
                response_text=response_text,
                response_at=response_at,
                raw_payload=review_data
            ))
        
        return reviews
    
    def _fetch_stats(self, account: dict) -> List[ExternalStatsPoint]:
        """Получить статистику через API"""
        api = self._get_api_client(account)
        if not api:
            return []
        
        location_name = account.get('external_id')
        if not location_name:
            return []
        
        # Получаем статистику за последние 30 дней
        end_date = datetime.utcnow()
        start_date = datetime.utcnow() - timedelta(days=30)
        
        insights = api.get_insights(
            location_name,
            start_date.isoformat() + 'Z',
            end_date.isoformat() + 'Z'
        )
        
        # Парсим insights и создаем ExternalStatsPoint
        # ... (детальная обработка insights)
        
        return stats
    
    def _publish_review_reply(self, account: dict, review_id: str, reply_text: str) -> bool:
        """Опубликовать ответ на отзыв"""
        api = self._get_api_client(account)
        if not api:
            return False
        
        location_name = account.get('external_id')
        if not location_name:
            return False
        
        return api.update_review_reply(location_name, review_id, reply_text)
    
    def _publish_post(self, account: dict, post_data: Dict[str, Any]) -> Optional[str]:
        """Опубликовать пост/новость"""
        api = self._get_api_client(account)
        if not api:
            return None
        
        location_name = account.get('external_id')
        if not location_name:
            return None
        
        return api.create_local_post(location_name, post_data)
```

### 4. API эндпоинты

**Файл:** `src/main.py` или `src/api/google_business_api.py` (создать Blueprint)

```python
from flask import Blueprint, request, jsonify, redirect
from google_business_auth import GoogleBusinessAuth
from google_business_sync_worker import GoogleBusinessSyncWorker
from auth_encryption import encrypt_auth_data, decrypt_auth_data
from database_manager import DatabaseManager
import json
import uuid

google_business_bp = Blueprint('google_business', __name__)

@google_business_bp.route('/api/google/oauth/authorize', methods=['GET'])
def google_oauth_authorize():
    """
    Начать OAuth авторизацию
    
    Query параметры:
    - business_id: ID бизнеса для подключения Google
    
    Returns:
    - auth_url: URL для редиректа пользователя на авторизацию Google
    """
    # Проверка авторизации
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({"error": "Требуется авторизация"}), 401
    
    token = auth_header.split(' ')[1]
    user_data = verify_session(token)
    if not user_data:
        return jsonify({"error": "Недействительный токен"}), 401
    
    business_id = request.args.get('business_id')
    if not business_id:
        return jsonify({"error": "business_id обязателен"}), 400
    
    # Проверяем доступ к бизнесу
    db = DatabaseManager()
    cursor = db.conn.cursor()
    cursor.execute("SELECT owner_id FROM Businesses WHERE id = ?", (business_id,))
    row = cursor.fetchone()
    db.close()
    
    if not row:
        return jsonify({"error": "Бизнес не найден"}), 404
    
    owner_id = row[0]
    if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
    
    # Генерируем state для безопасности (user_id + business_id)
    state = f"{user_data['user_id']}_{business_id}"
    
    # Сохраняем state в сессии или временной таблице для проверки в callback
    # (можно использовать Redis или временную таблицу в БД)
    
    auth = GoogleBusinessAuth()
    auth_url = auth.get_authorization_url(state)
    
    return jsonify({
        "success": True,
        "auth_url": auth_url
    })

@google_business_bp.route('/api/google/oauth/callback', methods=['GET'])
def google_oauth_callback():
    """
    Обработка OAuth callback от Google
    
    Query параметры:
    - code: Authorization code от Google
    - state: State для проверки (user_id_business_id)
    
    Returns:
    - HTML страница с редиректом на фронтенд или сообщение об успехе
    """
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        # Пользователь отменил авторизацию
        return redirect(f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/dashboard/profile?google_auth=error")
    
    if not code or not state:
        return redirect(f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/dashboard/profile?google_auth=error")
    
    # Парсим state (user_id_business_id)
    try:
        user_id, business_id = state.split('_', 1)
    except ValueError:
        return redirect(f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/dashboard/profile?google_auth=error")
    
    try:
        auth = GoogleBusinessAuth()
        credentials = auth.get_credentials_from_code(code)
        
        # Преобразуем credentials в словарь
        creds_dict = auth.credentials_to_dict(credentials)
        creds_json = json.dumps(creds_dict)
        
        # Шифруем credentials
        encrypted_creds = encrypt_auth_data(creds_json)
        
        # Сохраняем или обновляем аккаунт в ExternalBusinessAccounts
        db = DatabaseManager()
        cursor = db.conn.cursor()
        
        # Проверяем, есть ли уже аккаунт для этого бизнеса
        cursor.execute("""
            SELECT id FROM ExternalBusinessAccounts
            WHERE business_id = ? AND source = 'google_business'
        """, (business_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Обновляем существующий аккаунт
            cursor.execute("""
                UPDATE ExternalBusinessAccounts
                SET auth_data = ?, is_active = 1, last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = ?
            """, (encrypted_creds, existing[0]))
        else:
            # Создаем новый аккаунт
            account_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO ExternalBusinessAccounts
                (id, business_id, source, external_id, display_name, auth_data, is_active, created_at, updated_at)
                VALUES (?, ?, 'google_business', ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (account_id, business_id, None, 'Google Business', encrypted_creds))
        
        db.conn.commit()
        db.close()
        
        # Редиректим на фронтенд с успешным статусом
        return redirect(f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/dashboard/profile?google_auth=success")
        
    except Exception as e:
        print(f"❌ Ошибка обработки OAuth callback: {e}")
        import traceback
        traceback.print_exc()
        return redirect(f"{os.getenv('FRONTEND_URL', 'http://localhost:3000')}/dashboard/profile?google_auth=error")

@google_business_bp.route('/api/business/<business_id>/google/publish-review-reply', methods=['POST'])
def publish_review_reply(business_id):
    """Опубликовать ответ на отзыв в Google"""
    # ... проверка авторизации ...
    
    data = request.get_json()
    review_id = data.get('review_id')
    reply_text = data.get('reply_text')
    account_id = data.get('account_id')
    
    # Получаем аккаунт
    # ... загрузка из БД ...
    
    worker = GoogleBusinessSyncWorker()
    success = worker._publish_review_reply(account, review_id, reply_text)
    
    return jsonify({"success": success})

@google_business_bp.route('/api/business/<business_id>/google/publish-post', methods=['POST'])
def publish_post(business_id):
    """Опубликовать пост/новость в Google"""
    # ... проверка авторизации ...
    
    data = request.get_json()
    post_data = {
        'summary': data.get('title', ''),
        'callToAction': {
            'actionType': 'CALL',
            'url': data.get('url', '')
        },
        'media': []  # Если есть фото
    }
    
    # ... аналогично publish_review_reply ...
    
    return jsonify({"success": True, "post_id": post_id})
```

---

## Зависимости

**Добавить в `requirements.txt`:**
```
google-api-python-client>=2.100.0
google-auth-httplib2>=0.1.1
google-auth-oauthlib>=1.1.0
```

---

## Порядок выполнения

1. **Настройка OAuth 2.0**
   - Создать проект в Google Cloud Console
   - Включить Google Business Profile API
   - Создать OAuth 2.0 Client ID
   - Добавить переменные окружения: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`

2. **Реализация аутентификации**
   - Создать `src/google_business_auth.py`
   - Реализовать OAuth flow
   - Сохранять credentials в `ExternalBusinessAccounts.auth_data` (зашифровано)

3. **Реализация API клиента**
   - Создать `src/google_business_api.py`
   - Реализовать методы для получения данных
   - Реализовать методы для публикации данных

4. **Обновление воркера**
   - Заменить заглушки в `google_business_sync_worker.py`
   - Реализовать получение отзывов, статистики, постов
   - Реализовать публикацию ответов и постов

5. **API эндпоинты**
   - Создать Blueprint для Google Business API
   - Реализовать OAuth endpoints
   - Реализовать endpoints для публикации данных

6. **Интеграция с фронтендом**
   - Добавить кнопку "Подключить Google" в ExternalIntegrations
   - Реализовать OAuth flow на фронтенде (открытие popup/нового окна)
   - Добавить кнопки "Опубликовать в Google" для ответов на отзывы
   - Добавить кнопки "Опубликовать в Google" для новостей
   - Показывать статус подключения Google

---

## Чеклист для кодера

### Настройка Google Cloud
- [ ] Создать проект в Google Cloud Console
- [ ] Включить Google Business Profile API
- [ ] Создать OAuth 2.0 Client ID
- [ ] Настроить redirect URI
- [ ] Добавить переменные окружения в `.env`

### Backend
- [ ] Создать `src/google_business_auth.py` с OAuth flow
- [ ] Создать `src/google_business_api.py` с методами API
- [ ] Обновить `src/google_business_sync_worker.py` (заменить заглушки)
- [ ] Создать Blueprint `src/api/google_business_api.py` с эндпоинтами
- [ ] Добавить endpoints для OAuth авторизации
- [ ] Добавить endpoints для публикации ответов на отзывы
- [ ] Добавить endpoints для публикации постов
- [ ] Добавить endpoints для получения статистики
- [ ] Установить зависимости: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`

### Frontend
- [ ] Добавить кнопку "Подключить Google" в `ExternalIntegrations.tsx`
- [ ] Реализовать OAuth flow на фронтенде
- [ ] Добавить кнопки "Опубликовать в Google" для ответов на отзывы
- [ ] Добавить кнопки "Опубликовать в Google" для новостей
- [ ] Показывать статус публикации

### Тестирование
- [ ] Протестировать OAuth авторизацию
- [ ] Протестировать получение отзывов
- [ ] Протестировать получение статистики
- [ ] Протестировать публикацию ответа на отзыв
- [ ] Протестировать публикацию поста

---

## Важные замечания

1. **OAuth 2.0:**
   - Использовать `offline` access для получения refresh token
   - Сохранять refresh token для автоматического обновления access token
   - Шифровать credentials в БД через `auth_encryption.py`

2. **Ограничения API:**
   - Услуги нельзя редактировать через API (только через веб-интерфейс)
   - Некоторые метрики статистики доступны только для определенных типов бизнеса
   - Rate limits: проверять документацию Google

3. **Безопасность:**
   - Всегда шифровать credentials в БД
   - Проверять права доступа перед публикацией
   - Валидировать данные перед отправкой в API

---

## Документация Google

- [Google Business Profile API](https://developers.google.com/my-business/content/overview)
- [OAuth 2.0 Setup](https://developers.google.com/identity/protocols/oauth2)
- [API Reference](https://developers.google.com/my-business/content/basic-setup)

