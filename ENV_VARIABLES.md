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

## 🔒 Безопасность

- **Никогда не коммитьте .env файл в git**
- Все ключи должны быть в .env на сервере
- Используйте разные ключи для dev и production

