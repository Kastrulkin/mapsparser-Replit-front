# Настройка GigaChat API

## Получение ключей

1. Перейдите на [GigaChat API](https://developers.sber.ru/portal/products/gigachat)
2. Зарегистрируйтесь или войдите в аккаунт
3. Создайте новое приложение
4. Получите `client_id` и `client_secret`

## Настройка на сервере

1. Создайте файл `.env` в корне проекта:
```bash
nano /root/mapsparser-Replit-front/.env
```

2. Добавьте ваши ключи:
```
GIGACHAT_CLIENT_ID=ваш_client_id
GIGACHAT_CLIENT_SECRET=ваш_client_secret
```

3. Перезапустите сервисы:
```bash
systemctl restart seo-worker
systemctl restart seo-api
```

## Проверка работы

Запустите тест:
```bash
cd /root/mapsparser-Replit-front
python3 src/gigachat_analyzer.py
```

## Лимиты и стоимость

- GigaChat предоставляет бесплатные токены для тестирования
- Стоимость: ~0.1₽ за 1K токенов
- Лимит запросов: зависит от тарифа

## Отладка

Если GigaChat недоступен, система автоматически переключится на простой анализ.
Логи можно посмотреть в:
```bash
journalctl -u seo-worker -f
```
