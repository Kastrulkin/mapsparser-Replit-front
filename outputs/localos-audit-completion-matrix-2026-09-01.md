# LocalOS: матрица завершения комплексного аудита — 2026-09-01

## Проверенная среда

- Exact Docker image `localos-staging-app:latest`, отдельные PostgreSQL и Redis, только синтетические fixtures.
- Runtime: непривилегированный `uid=10001`, исходный код read-only, writable только runtime-каталоги.
- Внешние provider credentials, отправки, публикации, платежи и фоновые внешние dispatch отключены.
- `http://127.0.0.1:18000` отвечает 200; smoke проверяет пять flow: maps, influencer, partnership, content и automation.
- Финальный Playwright run на исправленном image: **102/102**, 11 файлов, desktop 1440×1000, laptop 1024×768, mobile/Mini App 393×852.

## Десять пользовательских сценариев

| № | Путь | Доказанное поведение | Основная проверка | Статус |
|---|---|---|---|---|
| 1 | Новый пользователь — карты | Public preview показывает конкретную проблему; регистрация и email verification возвращают в действие; недельный цикл доходит до verified comparison и следующей недели | `public-lead-journeys`, `journey-registration-continuity`, `full-cycle-journeys` | PASS |
| 2 | Новый пользователь — инфлюенсеры | Preview автора и бартера; возврат на список; реальный shortlist; ответ, размещение и результат сохраняются | те же suites, influencer flow | PASS |
| 3 | Новый пользователь — партнёрства | Preview подходящего бизнеса; возврат в workspace; launch mechanic и измеренный результат сохраняются | те же suites, partnership flow; `partnership-api-postgres` | PASS |
| 4 | Новый пользователь — контент | Preview темы; возврат к выбранному action; факты, черновик, публикация и result evidence не теряются | те же suites, content flow | PASS |
| 5 | Новый пользователь — автоматизация | Preview use case; возврат к настройке; preflight требует approval; journey связывает только завершённый run | те же suites, automation flow | PASS |
| 6 | Действующий владелец — отзывы | Конкретный отзыв открывается с подготовленным ручным черновиком; автоматическая публикация не выполняется | `owner-reviews-finance` | PASS |
| 7 | Действующий владелец — финансы | Import preview предшествует применению; повтор не создаёт двойной учёт | `owner-reviews-finance` | PASS |
| 8 | Управляющий сетью | Переключение сеть/точка сохраняет scope; данные чужого tenant не появляются | `network-tenant` | PASS |
| 9 | Web ↔ Mini App | Один action продолжается между поверхностями; повторный idempotency key воспроизводит прежний ответ; старая version отклоняется; потерянный ответ безопасно повторяется | `cross-surface-continuity`, `journey-offline-retry` | PASS |
| 10 | Администратор — journey | Один из пяти маршрутов создаётся, preview открывается глазами клиента, ссылка отзывается; публичная часть сохраняет один понятный CTA | `admin-journey-builder`, `public-lead-journeys` | PASS |

## Общие UX и accessibility gates

| Проверка | Результат |
|---|---|
| Основные authenticated routes | «Сегодня», «Пути роста», инфлюенсеры, партнёрства, контент и автоматизация открываются без неожиданных API denial |
| Accessible names | Нет видимых кнопок, ссылок или полей без доступного имени |
| Axe | 0 critical/serious violations на проверенных маршрутах |
| Keyboard | Первый Tab получает видимый `:focus-visible` indicator |
| Mobile touch targets | Все видимые controls на проверенных маршрутах не меньше 40×40 px |
| Public CTA contrast | Пять flow проходят WCAG AA contrast-check |
| Mobile content calendar | Семиколоночная сетка не сжимается; доступен горизонтальный scroll и сохраняются touch targets |
| Runtime stability | Console errors и неожиданные API 4xx/5xx отсутствуют в проверяемых flows |

## Security evidence

| Класс | Текущий результат |
|---|---|
| Backend auth/CORS/headers/runtime config | 24/24 focused tests |
| Python dependencies | `pip-audit`: 0 известных уязвимостей |
| Frontend dependencies | npm production/full audit: 0 уязвимостей |
| Container image | Trivy HIGH/CRITICAL: 0 после обновления `libexpat` до `2.5.0-1+deb12u3` |
| Docker configuration | Trivy HIGH/CRITICAL: 0 по tracked tree |
| Current tracked secrets | 10 Gitleaks matches, все подтверждены как fixtures/placeholders/domain keys; active credential в tracked HEAD не найден |
| Git history | 620 redacted matches в 29 commits; исторические Wordstat и Supabase credentials требуют provider-side rotation/revoke |
| Static analysis | Последний Semgrep ERROR-gate: 0 findings; текущий дополнительный diff затрагивает только системный пакет Docker image и audit evidence |
| Dynamic baseline | Последний OWASP ZAP baseline: 61 pass, 0 fail, 0 high/critical |
| Rollout integrity | 247 allowlisted files; manifest SHA-256 `58794de25a9c3a293ab5770197c1fd6ced06ff76116c0537393b28f31fb2da7e`; verifier 247/247 |

## Approval-инварианты

- Review replies остаются черновиками до ручной публикации.
- Automation выполняет preflight и требует явного approval; незавершённый run не считается результатом journey.
- Staging не содержит реальных provider credentials и не может выполнять внешние send/publish/payment.
- Idempotency и optimistic version защищают от двойного клика, повторного запроса и одновременного действия web/Mini App.
- Completion создаётся после доменного результата, а не по telemetry event.

## Что завершено, а что нет

Функциональный и security-аудит проверенного staging-пакета завершён: 10/10 сценариев зелёные, открытых P0/P1 и HIGH/CRITICAL в exact image нет.

Production rollout остаётся отдельной работой и сейчас **NO-GO** до выполнения следующих gates:

1. Проверить внешних потребителей legacy Supabase `SEOmaps`, затем отозвать старый `service_role`; новый Supabase key в LocalOS не добавлять.
2. Контролируемо ротировать Wordstat Cloud credential для app/worker, выполнить один минимальный provider smoke и удалить legacy OAuth fallback.
3. Сверить production drift с exact manifest; не использовать полный `git pull`, reset или blanket rsync.
4. Перед non-root image rollout сохранить ownership snapshot и отдельно согласовать смену владельца только production `debug_data`.
5. Выпустить browser cookie migration по dual-stack/internal-cohort схеме и после наблюдения отозвать старые browser sessions.
6. После отдельного разрешения проверить live edge headers и выполнить production smoke без автоматических отправок, публикаций или платежей.

До этих действий production не изменяется.
