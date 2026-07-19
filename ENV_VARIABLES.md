# Переменные окружения для ChatGPT интеграции

## 📋 Необходимые переменные для .env файла

### Google Maps API
```bash
GOOGLE_MAPS_API_KEY=your-google-maps-api-key
```
**Назначение:** Определение часового пояса и координат по адресу  
**Где получить:** https://console.cloud.google.com/apis/credentials

### Stripe
```bash
STRIPE_SECRET_KEY=sk_test_your-stripe-secret-key
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
```
**Назначение:** Обработка платежей и подписок  
**Где получить:** https://dashboard.stripe.com/apikeys

### WhatsApp Business API (WABA)
```bash
WHATSAPP_PHONE_ID=your-whatsapp-phone-id
WHATSAPP_ACCESS_TOKEN=your-whatsapp-access-token
WHATSAPP_VERIFY_TOKEN=your-whatsapp-verify-token
```
**Назначение:** Отправка уведомлений через WhatsApp  
**Где получить:** https://developers.facebook.com/apps/

### Существующие переменные (уже есть)
```bash
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_REVIEWS_BOT_TOKEN=your-reviews-bot-token
API_BASE_URL=http://localhost:8000
```

### Файлы цифровых комнат: S3-compatible Object Storage
```bash
SALES_ROOM_STORAGE_BACKEND=s3
SALES_ROOM_S3_ENDPOINT_URL=https://s3.regru.cloud
SALES_ROOM_S3_REGION=
SALES_ROOM_S3_BUCKET=localos
SALES_ROOM_S3_PREFIX=sales-room-files
SALES_ROOM_S3_ACCESS_KEY_ID=your-static-access-key-id
SALES_ROOM_S3_SECRET_ACCESS_KEY=your-static-secret-access-key
SALES_ROOM_UPLOAD_MAX_BYTES=10485760
```
**Назначение:** хранение файлов, загруженных в публичных цифровых комнатах, во внешнем S3-compatible Object Storage вместо диска сервера.
Для REG.RU регион остаётся пустым. Для другого S3-провайдера укажите регион, если он требуется.

Если `SALES_ROOM_STORAGE_BACKEND` не задан или равен `local`, файлы продолжают сохраняться в `SALES_ROOM_UPLOAD_DIR` / `DEBUG_DIR/sales_room_uploads`.

### Founder-led персонализация аутрича
```bash
OUTREACH_AI_PERSONALIZATION_ENABLED=false
GIGACHAT_CA_BUNDLE=/app/src/certs/russian_trusted_root_ca_pem.crt
```
**Назначение:** включает нативную AI-генерацию цепочки по подтверждённым evidence, founder story и голосу отправителя. Каждая версия проходит отдельную семантическую проверку. При ошибке генерации LocalOS блокирует сохранение и отправку версии.

В production включайте только после GigaChat preflight и пилотного preview. Флаг не включает dispatcher и не разрешает отправку.

`GIGACHAT_CA_BUNDLE` указывает на корневой сертификат НУЦ Минцифры, который требует GigaChat API. Проверка TLS остаётся включённой; `GIGACHAT_SSL_VERIFY=false` для этого сценария не используется.

### Ограниченный rollout dispatcher аутрича
```bash
OUTREACH_DISPATCH_ENABLED=false
OUTREACH_DISPATCH_BUSINESS_IDS=
OUTREACH_DISPATCH_PLATFORM_SCOPE_ENABLED=false
```
**Назначение:** фоновый dispatcher включается только после двух живых пилотов и только для явно заданной когорты. `OUTREACH_DISPATCH_BUSINESS_IDS` — CSV со списком business ID; `OUTREACH_DISPATCH_PLATFORM_SCOPE_ENABLED=true` отдельно разрешает кампании продаж LocalOS. Даже при `OUTREACH_DISPATCH_ENABLED=true` пустая когорта блокирует отправку с причиной `dispatch_cohort_not_configured`. Фоновый dispatcher не подхватывает legacy-очереди без versioned campaign touch.

### Фоновое обогащение лидов
```bash
PROSPECTING_CONTACT_INTELLIGENCE_ENABLED=false
PROSPECTING_CONTACT_INTELLIGENCE_INTERVAL_SEC=10
PROSPECTING_CONTACT_INTELLIGENCE_BATCH_SIZE=1
```
**Назначение:** включает очередь нормализации контактов, сбора публичных evidence и подготовки message brief. `BATCH_SIZE` ограничивает число последовательно обрабатываемых задач за один цикл worker; допустимый диапазон принудительно ограничен значениями от 1 до 20. Параллельная отправка сообщений этим параметром не включается.

## 🔒 Безопасность

- **Никогда не коммитьте .env файл в git**
- Все ключи должны быть в .env на сервере
- Используйте разные ключи для dev и production
