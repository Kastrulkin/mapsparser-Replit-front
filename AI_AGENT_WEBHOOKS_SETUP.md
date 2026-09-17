# Настройка Webhooks для ИИ агента

## Обзор

ИИ агент может автоматически отвечать на сообщения клиентов через WhatsApp Business API (WABA) и Telegram. Для этого нужно настроить webhooks.

## WhatsApp Business API (WABA)

### 1. Настройка в личном кабинете

1. Войдите в личный кабинет на `/dashboard/settings`
2. Найдите раздел "Учётные данные WhatsApp Business API"
3. Введите:
   - **Phone ID** - ID телефона из вашего WABA аккаунта
   - **Access Token** - токен доступа к WABA API
4. Сохраните данные

### 2. Настройка Webhook в Meta Developer Console

1. Перейдите в [Meta for Developers](https://developers.facebook.com/)
2. Выберите ваше приложение
3. Перейдите в раздел "WhatsApp" → "Configuration"
4. В поле "Webhook URL" укажите:
   ```
   https://localos.pro/api/webhooks/whatsapp
   ```
5. В поле "Verify Token" укажите значение `WHATSAPP_VERIFY_TOKEN` из `.env`. Это должен быть уникальный случайный секрет: fallback-значения нет.
6. Сохраните изменения

### 3. Подписка на события

В Meta Developer Console подпишитесь на события:
- `messages` - для получения входящих сообщений

### 4. Включение ИИ агента

1. В личном кабинете перейдите в раздел "Настройки ИИ агента"
2. Включите переключатель "Включить ИИ агента"
3. Настройте тон общения и ограничения
4. Сохраните настройки

## Telegram

### Архитектура Telegram-ботов для ИИ агента

- Для **уведомлений владельцам** (новые бронирования, запросы поддержки из ChatGPT) используется **глобальный бот BeautyBot** (`TELEGRAM_BOT_TOKEN`). Этого достаточно для базового сценария.
- **Собственный бот салона (`telegram_bot_token` в таблице `Businesses`)** нужен только если вы хотите, чтобы ИИ-агент общался с клиентами **от имени вашего бренда**.
- Webhook-и из этого файла относятся именно к **боту салона**, который используется ИИ-агентом для переписки с клиентами.

### 1. Создание собственного бота салона

1. Найдите [@BotFather](https://t.me/BotFather) в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Сохраните полученный токен

### 2. Настройка токена бота салона в личном кабинете

1. Войдите в личный кабинет на `/dashboard/settings`
2. Найдите раздел "Токен Telegram бота"
3. Введите токен вашего **брендированного бота салона**
4. Сохраните токен

### 3. Настройка Webhook

Для каждого бота webhook настраивается отдельно. URL содержит только
несекретный UUID бизнеса: `https://localos.pro/api/webhooks/telegram?business_id=<business-uuid>`.
Токен бота в URL, query и `X-Bot-Token` запрещены. Telegram передаёт
`secret_token` в callback как `X-Telegram-Bot-Api-Secret-Token`.

Секрет вычисляется из текущего токена бота и UUID бизнеса. Его не нужно
хранить отдельно, но после смены токена webhook надо перевязать. Одноразовый
операторский шаг в доверенной среде, только после одобрения изменения
подключения (без secret в shell history; этот пример не выполняется аудитом):

```python
from getpass import getpass
import hashlib, hmac, json, uuid
from urllib.request import Request, urlopen

business_id = str(uuid.UUID(input("Business UUID: ").strip()))
bot_token = getpass("Telegram bot token: ").strip()
secret_token = hmac.new(
    bot_token.encode(),
    f"localos.telegram.webhook.v1:{business_id}".encode(),
    hashlib.sha256,
).hexdigest()
body = json.dumps({
    "url": f"https://localos.pro/api/webhooks/telegram?business_id={business_id}",
    "secret_token": secret_token,
}).encode()
request = Request(
    f"https://api.telegram.org/bot{bot_token}/setWebhook",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    response = urlopen(request, timeout=15)
    try:
        result = json.loads(response.read())
    finally:
        response.close()
    if result.get("ok") is not True:
        raise RuntimeError("Webhook registration rejected")
except Exception:
    # Не выводите исключение HTTP: URL Telegram API содержит токен бота.
    raise RuntimeError("Webhook registration failed; inspect provider status securely") from None
```

`/api/webhooks/telegram/<bot_token>` закрыт и возвращает `410`; сначала
перевяжите брендированного бота. `X-Bot-Token` в запросе `setWebhook` не
настраивает заголовок будущих callback-запросов Telegram.

### 4. Включение ИИ агента

1. В личном кабинете перейдите в раздел "Настройки ИИ агента"
2. Включите переключатель "Включить ИИ агента"
3. Настройте тон общения и ограничения
4. Сохраните настройки

## Переменные окружения

Добавьте в `.env` файл:

```bash
# WhatsApp Webhook Verify Token (unique random secret; required for GET verification)
WHATSAPP_VERIFY_TOKEN=<unique-random-verify-token>

# Meta App Secret (required for HMAC validation of every WhatsApp POST)
WHATSAPP_APP_SECRET=<meta-app-secret>

# GigaChat (для ИИ агента)
GIGACHAT_CLIENT_ID=your_client_id
GIGACHAT_CLIENT_SECRET=your_client_secret
```

## Стейты разговора

ИИ агент использует следующие захардкоженные стейты:

1. **greeting** - Приветствие и знакомство
2. **service_inquiry** - Вопросы об услугах
3. **booking** - Запись на услугу
4. **pricing** - Уточнение цен
5. **confirmation** - Подтверждение записи
6. **goodbye** - Завершение разговора

## Тестирование

### Тест WhatsApp

1. Отправьте сообщение на номер, связанный с вашим WABA аккаунтом
2. ИИ агент должен автоматически ответить
3. Проверьте логи сервера для отладки

### Тест Telegram

1. Найдите вашего бота в Telegram
2. Отправьте команду `/start` или любое сообщение
3. ИИ агент должен автоматически ответить
4. Проверьте логи сервера для отладки

## Отладка

Логи webhook запросов можно найти в консоли сервера. Ищите сообщения:
- `📱 Получено WhatsApp сообщение от...`
- `📱 Получено Telegram сообщение от...`
- `✅ WhatsApp сообщение отправлено...`
- `✅ Telegram сообщение отправлено...`
- `❌ Ошибка...` - для ошибок

## Безопасность

- Токены WABA и Telegram хранятся в базе данных в зашифрованном виде
- Webhook endpoints требуют правильной структуры запросов
- WhatsApp GET webhook требует настроенный verify token; известного fallback-значения нет
- Каждый WhatsApp POST до разбора JSON проверяется по заголовку Meta `X-Hub-Signature-256` (HMAC-SHA256 от сырых байтов тела с `WHATSAPP_APP_SECRET`)
- Telegram webhook проверяет токен бота перед обработкой

## Ограничения

- ИИ агент работает только для бизнесов с включённым `ai_agent_enabled = 1`
- Для WhatsApp требуется активный WABA аккаунт
- Для Telegram требуется собственный бот
- Ответы генерируются через GigaChat API (требуется настройка)
