# Исправление SSL ошибки GigaChat

## ✅ SSL проблема решена!

SSL ошибка была исправлена добавлением настройки `GIGACHAT_SSL_VERIFY=false`.

## 🔧 Что было сделано:

1. **Обновлен `src/services/gigachat_client.py`** - добавлена поддержка переменной окружения `GIGACHAT_SSL_VERIFY`
2. **Обновлен `src/main.py`** - добавлена установка `GIGACHAT_SSL_VERIFY=false` по умолчанию
3. **Добавлено в `.env`** - `GIGACHAT_SSL_VERIFY=false`
4. **SSL проверка отключена** для GigaChat API

## ⚠️ Текущая проблема: Недействительные ключи GigaChat

**Ошибка 403** означает, что ключи GigaChat в файле `.env` недействительны или истекли.

## 🔑 Решение:

### 1. Получите новые ключи GigaChat:
- Зайдите в [личный кабинет Сбера](https://developers.sber.ru/portal/products/gigachat)
- Создайте новое приложение или обновите существующее
- Скопируйте новые `CLIENT_ID` и `CLIENT_SECRET`

### 2. Обновите файл `.env`:
```bash
# Замените на ваши новые ключи
GIGACHAT_CLIENT_ID=ваш_новый_client_id
GIGACHAT_CLIENT_SECRET=ваш_новый_client_secret
GIGACHAT_SSL_VERIFY=false
```

### 3. Перезапустите сервер:
```bash
pkill -f "python3 src/main.py"
python3 src/main.py
```

## 🧪 Проверка работы:

После обновления ключей попробуйте использовать функцию "Оптимизировать" в интерфейсе - SSL ошибка больше не должна появляться.

## 📝 Примечание:

- SSL проверка отключена только для GigaChat API
- Ключи GigaChat имеют срок действия и требуют периодического обновления
- Для продакшена рекомендуется использовать правильные SSL сертификаты
