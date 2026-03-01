# Настройка Telegram-ботов

У нас два Telegram-бота:

1. **@Local_bot** - для управления аккаунтом (использует `TELEGRAM_BOT_TOKEN`)
2. **@beautyreviewexchange_bot** - для обмена отзывами (использует `TELEGRAM_REVIEWS_BOT_TOKEN`)

## 📋 Требования

1. Python 3.11+
2. Установленная зависимость `python-telegram-bot>=20.0`
3. Токены обоих ботов от [@BotFather](https://t.me/BotFather)

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

Добавьте оба токена в `.env` файл:

```bash
# Бот для управления аккаунтом
TELEGRAM_BOT_TOKEN=ваш_токен_от_Local_bot

# Бот для обмена отзывами
TELEGRAM_REVIEWS_BOT_TOKEN=ваш_токен_от_beautyreviewexchange_bot
```

## 🚀 Запуск ботов

### Вариант 1: Запуск через systemd (рекомендуется)

#### Бот для управления аккаунтом:

```bash
# Скопировать сервис
cp telegram-bot.service /etc/systemd/system/

# Подготовить отдельное окружение бота в runtime-каталоге
python3 -m venv /opt/seo-app/telegram-bot-venv
/opt/seo-app/telegram-bot-venv/bin/pip install "python-telegram-bot>=20.0" requests python-dotenv psycopg2-binary

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск и запустить
systemctl enable telegram-bot
systemctl start telegram-bot

# Проверить статус
systemctl status telegram-bot
```

#### Бот для обмена отзывами:

```bash
# Скопировать сервис
cp telegram-reviews-bot.service /etc/systemd/system/

# Перезагрузить systemd
systemctl daemon-reload

# Включить автозапуск и запустить
systemctl enable telegram-reviews-bot
systemctl start telegram-reviews-bot

# Проверить статус
systemctl status telegram-reviews-bot
```

### Вариант 2: Запуск вручную

```bash
# Бот для управления аккаунтом
python src/telegram_bot.py

# Бот для обмена отзывами (в другом терминале)
python src/telegram_reviews_bot.py
```

## 🔍 Проверка работы

### Проверка бота для управления аккаунтом:

```bash
systemctl status telegram-bot
journalctl -u telegram-bot -n 20
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

### Управление ботом для управления аккаунтом:

```bash
systemctl start telegram-bot
systemctl stop telegram-bot
systemctl restart telegram-bot
journalctl -u telegram-bot -f
```

### Управление ботом для обмена отзывами:

```bash
systemctl start telegram-reviews-bot
systemctl stop telegram-reviews-bot
systemctl restart telegram-reviews-bot
journalctl -u telegram-reviews-bot -f
```

## ⚠️ Важные замечания

- Оба бота должны иметь доступ к интернету для подключения к Telegram API
- Убедитесь, что API сервер (`main.py`) запущен и доступен
- Проверьте, что база данных доступна и содержит необходимые таблицы
- Для работы с фото нужен настроенный GigaChat API (только для бота управления аккаунтом)
