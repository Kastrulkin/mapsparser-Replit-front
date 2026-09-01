# Bug Reproducer: устойчивость к внешним frontend-скриптам

## ✅ FIX_PROVEN

Оба дефекта воспроизведены до исправления и устранены тем же набором тестов после точечного фикса.

**Commit:** `557f1a6e`

**Среда:** isolated Docker staging, отдельные PostgreSQL/Redis, только синтетические fixtures

**Production:** не изменялся

## Дефекты

| Дефект | Ожидалось | До исправления | Причина |
|---|---|---|---|
| Обычный web зависел от Telegram CDN | `/login` отображается независимо от Telegram | Форма не появлялась за 3 секунды при задержке SDK на 7 секунд | Telegram SDK синхронно загружался в `<head>` на всех маршрутах |
| Metrika загружалась на приватном маршруте | При `localosTrackingConsent=false` запросов к `mc.yandex.ru` нет | Запрос выполнялся на `/login` | Metrika инициализировалась глобально вне route-consent логики |

## Одобренный минимальный фикс

- Telegram SDK динамически загружается только на `/telegram/control`.
- Mini App ждёт SDK не больше пяти секунд и затем показывает существующее fallback-состояние.
- Yandex Metrika включается только на разрешённых публичных marketing-маршрутах и получает `destruct` при переходе в приватную область.
- Бизнес-логика journey, approval и внешних действий не менялась.

## Red → green

Команда:

```bash
cd frontend
JOURNEY_STAGING_BASE_URL=http://127.0.0.1:8000 npm run test:e2e -- -c playwright.journey-staging.config.ts e2e/staging/external-script-resilience.spec.ts --project=desktop
```

| Проверка | До | После |
|---|---:|---:|
| Обычный web работает при недоступном Telegram SDK | FAIL | PASS |
| Приватный `/login` не запрашивает Metrika | FAIL | PASS |
| Итого | 0/2 | 2/2 |

## Более широкая проверка

- Python regression/static suite: `47 passed`.
- Frontend unit suite: `403 passed`.
- Frontend build: PASS.
- ESLint: 0 errors; 535 существующих предупреждений вне фикса.
- Staging isolation, non-root runtime и smoke пяти flow: PASS.
- Один непрерывный Playwright run: `108/108` за 2,9 минуты на desktop, laptop и mobile.
- Staging после прогона: HTTP 200.

## Ограничения

- Изменение не является общей переработкой аналитики или Mini App bootstrap.
- Реальные provider credentials и production-данные не использовались.
- Production rollout требует отдельного разрешения и остаётся под существующими security gates.
