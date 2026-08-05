# Настройка Telegram-контуров

LocalOS использует Bot API и MTProto для разных пользовательских задач. Эти подключения нельзя подменять друг другом.

| Контур | От чьего имени работает | Назначение |
|---|---|---|
| `@LocalOspro_bot` + Mini App | бот LocalOS | управление, уведомления, approvals, публикации в подключённый канал |
| Telegram API application + Telethon session бизнеса | пользовательский аккаунт бизнеса | радар, контакты и одобренный аутрич от имени бизнеса |
| Брендированный бот бизнеса | отдельный бот бизнеса | клиентский бот/ИИ-агент, если он действительно нужен |

Bot API не читает личные контакты и не может отправлять сообщения как пользовательский Telegram-аккаунт. Для радара и аутрича бизнес создаёт собственное API application на `my.telegram.org`, затем авторизует номер в `Настройки → Подключения → Telegram-аккаунт бизнеса`. `api_id`, `api_hash` и session сохраняются зашифрованно; пароль 2FA не сохраняется.

У нас два Telegram-бота:

1. **@LocalOspro_bot** - для управления аккаунтом и OpenClaw actions (использует `TELEGRAM_BOT_TOKEN`)
2. **@beautyreviewexchange_bot** - для обмена отзывами (использует `TELEGRAM_REVIEWS_BOT_TOKEN`)

## 📋 Требования

1. Python 3.11+
2. Установленная зависимость `python-telegram-bot>=20.0`
3. Токен `@LocalOspro_bot` от [@BotFather](https://t.me/BotFather). Токен бота обмена отзывами нужен только если этот legacy-контур включён.

## 🔧 Установка

### 1. Установка зависимостей

```bash
python3 -m venv telegram-bot-venv
./telegram-bot-venv/bin/pip install "python-telegram-bot>=20.0" requests python-dotenv psycopg2-binary
```

Или установите из `requirements.txt`:
```bash
pip install -r requirements.txt
```

### 2. Настройка токенов в .env

Добавьте токен owner-bot и, при необходимости, токен legacy-бота обмена отзывами в `.env`:

```bash
# Бот для управления аккаунтом
TELEGRAM_BOT_TOKEN=ваш_токен_от_Local_bot

# Бот для обмена отзывами
TELEGRAM_REVIEWS_BOT_TOKEN=ваш_токен_от_beautyreviewexchange_bot
```

## 🚀 Текущий production runtime

Backend и worker работают в Docker Compose. На текущем production основной owner-bot запускается отдельным host service `openclaw-localos-telegram-bot.service`. Compose-сервис `telegram-bot` остаётся допустимым альтернативным runtime, но нельзя одновременно запускать два polling-процесса с одним токеном.

Все команды на сервере выполняются из `/opt/seo-app`:

```bash
cd /opt/seo-app
docker compose ps
systemctl status openclaw-localos-telegram-bot.service --no-pager
journalctl -u openclaw-localos-telegram-bot.service -n 50 --no-pager
```

После запуска для рабочего сценария используйте в Telegram:

```text
/control
```

Это основной guided-вход. Из него доступны:
- статус бизнеса;
- ответы на отзывы;
- оптимизация одной услуги;
- генерация новости;
- последние actions;
- очередь подтверждений (`pending approvals`);
- support snapshot и recovery report.

### Бот для обмена отзывами

Этот отдельный bot runtime является legacy-контуром и нужен только там, где обмен отзывами действительно включён. Актуальный unit хранится на production host; архивные service-файлы репозитория не следует копировать как новый runtime.

```bash
systemctl status telegram-reviews-bot.service --no-pager
journalctl -u telegram-reviews-bot.service -n 50 --no-pager
```

### Локальная отладка

```bash
# Бот для управления аккаунтом
python src/telegram_bot.py

# Бот для обмена отзывами (в другом терминале)
python src/telegram_reviews_bot.py
```

## 🔍 Проверка работы

### Проверка бота для управления аккаунтом

```bash
systemctl status openclaw-localos-telegram-bot.service --no-pager
journalctl -u openclaw-localos-telegram-bot.service -n 50 --no-pager
```

### Проверка бота для обмена отзывами:

```bash
systemctl status telegram-reviews-bot
journalctl -u telegram-reviews-bot -n 20
```

Должно быть:
```
🤖 Telegram-бот запущен...
✅ Бот готов к работе. Ожидаю сообщения...
```

## 📋 Полезные команды

### Управление ботом для управления аккаунтом

```bash
systemctl restart openclaw-localos-telegram-bot.service
journalctl -u openclaw-localos-telegram-bot.service -f
```

### Управление ботом для обмена отзывами:

```bash
systemctl start telegram-reviews-bot
systemctl stop telegram-reviews-bot
systemctl restart telegram-reviews-bot
journalctl -u telegram-reviews-bot -f
```

## ⚠️ Важные замечания

- Включённые боты должны иметь доступ к Telegram Bot API через актуальный HTTP proxy
- Убедитесь, что контейнер `app` запущен и доступен
- Проверьте, что база данных доступна и содержит необходимые таблицы
- Для работы с фото нужен настроенный GigaChat API (только для бота управления аккаунтом)
- Для human-in-the-loop доступны команды:
  - `/pending_approvals`
  - `/approve_action <action_id>`
  - `/reject_action <action_id>`
