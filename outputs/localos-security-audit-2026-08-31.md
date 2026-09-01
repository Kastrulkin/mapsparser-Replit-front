# LocalOS: итог комплексного staging- и security-аудита — 2026-08-31

> Актуализация 1 сентября 2026 года: reliability-gap закрыт точечным external-script fix и одним непрерывным Playwright run 108/108. Exact rollout manifest теперь содержит 252 файла и сверён с production read-only. Текущий источник go/no-go: `outputs/localos-audit-completion-matrix-2026-09-01.md`.

## Итог

- Все десять пользовательских сценариев прошли в изолированном Docker staging: **102/102 Playwright-тестов** на desktop, узком laptop и mobile/Mini App viewport.
- Staging использует отдельную PostgreSQL-базу, синтетические fixtures и отключённые внешние отправки, публикации, платежи и provider credentials.
- Production во время аудита не изменялся.
- App, worker и Telegram-образ переведены на непривилегированного пользователя `localos` (`uid=10001`). Исходный код внутри контейнера read-only; runtime-каталоги доступны для записи.
- Trivy image/config: 0 HIGH/CRITICAL. Semgrep ERROR-gate: 0 findings. `pip-audit` и npm audit: 0 известных уязвимостей.
- OWASP ZAP baseline: 0 FAIL и 0 high/critical. CSP пока остаётся report-only; SRI/COOP/COEP зафиксированы как последующее усиление.

## Десять сценариев

| № | Сценарий | Результат |
|---|---|---|
| 1 | Новый пользователь — карты | Ссылка → регистрация → задача → refresh → сравнение |
| 2 | Новый пользователь — инфлюенсеры | Preview → бартер → регистрация → подбор → ответ → размещение → результат |
| 3 | Новый пользователь — партнёрства | Preview → регистрация → ответ → запуск → результат |
| 4 | Новый пользователь — контент | Тема → факты → нужная публикация → черновик → публикация → результат |
| 5 | Новый пользователь — автоматизация | Use case → настройка → preflight → approval → результат |
| 6 | Действующий владелец — отзывы | Пройден с сохранением ручной границы публикации |
| 7 | Действующий владелец — финансы | Preview → применение → защита от двойного учёта |
| 8 | Управляющий сетью | Сеть → точка → tenant isolation → возврат без потери состояния |
| 9 | Web ↔ Mini App | Общий action, stale version, idempotency и offline retry |
| 10 | Администратор — journey | Пять маршрутов, preview, token, revoke и безопасный public payload |

Повторный финальный запуск 1 сентября 2026 года на точном Docker-образе после исправления мобильного календаря: `npx playwright test -c playwright.journey-staging.config.ts` — **102 passed (5.1m)**. После обновления `libexpat` exact image был пересобран, вновь прошёл smoke всех пяти flow и повторный полный набор: `.last-run.json` содержит `status: passed`, а `--list` подтверждает **102 tests in 11 files**.

## Исправления и security gates

- Docker staging больше не наследует production credentials и host mounts; это проверяет `scripts/check_staging_isolation.py`.
- `scripts/staging_journey_up.sh` проверяет непривилегированный UID, writable runtime paths и read-only source.
- XML из DOCX и Yandex XML разбирается через `defusedxml`.
- Удалён неиспользуемый frontend-компонент с прямым `dangerouslySetInnerHTML`.
- Public HTTP callbacks используют DNS-проверку, запрет private/loopback/link-local адресов, IP pinning и повторную проверку redirect.
- HSTS включается только при `APP_ENV=production`; staging по HTTP не объявляет ложную политику.
- GigaChat HTTP 402 классифицируется как терминальная provider-ошибка без повторов.
- Исправлены доступные имена, контраст, progress labels и минимальные touch targets.
- Мобильный календарь контента больше не сжимает семиколоночную сетку: она прокручивается горизонтально и сохраняет touch-target не меньше 40 px; профильный mobile suite прошёл 6/6.
- Повторный Trivy scan 1 сентября обнаружил `CVE-2026-56408` в унаследованной Debian-библиотеке `libexpat` версии `2.5.0-1+deb12u2`. Runtime image теперь явно устанавливает `libexpat1` и `libexpat1-dev` из актуального Bookworm security channel; пересобранный контейнер содержит `2.5.0-1+deb12u3`, а повторный image scan показывает 0 HIGH/CRITICAL. Trivy config по текущему tracked tree также показывает 0 HIGH/CRITICAL.
- Browser cookie migration доведена до staging-ready состояния: прямые чтения стандартных `auth_token`/`token` удалены из production-компонентов, browser transport до первого render очищает legacy browser credentials и не отправляет их как `Authorization`.
- Scoped bearer сохранён только для Mini App и активной demo session. Исправлен возврат из billing provider: проверка статуса работает с HttpOnly cookie без JavaScript-токена.
- Rollout ограничен SHA-256 allowlist из 247 файлов: 2 runtime, 12 backend security, 49 frontend source и 184 точных frontend dist artifacts. `scripts/verify_rollout_manifest.py` проверил весь manifest без расхождений.
- Шесть Wordstat API error path (`keywords`, `search`, `metadata`, `update`, `exclude`, `custom`) были двумя согласованными пакетами доказанно уязвимы к раскрытию текста внутренних исключений. Все шесть переведены на общий `internal_error_response`; оба reproducer-перехода доказаны red-to-green, полный Wordstat suite — 13 passed.
- Локальный dist с точными feature flags побайтово совпал с dist внутри Docker image, прошедшего 102/102 E2E. Staging/tests/evidence и посторонние `.agent`/Riderra/daily файлы исключены из production allowlist.
- Подготовлен read-only production preflight без вывода environment и без мутаций. Старый readiness-снимок от 30 августа явно помечен как исторический, чтобы он не противоречил текущему go/no-go.
- Read-only production preflight затем реально выполнен по восстановленному SSH: app, worker и Telegram работают от root; source и migrations уже read-only. `debug_data` занимает 445 МБ и содержит 1432 файла, почти все принадлежат root; UID 10001 не сможет писать туда без отдельной ownership migration. Production state не менялся.

| Проверка | Результат |
|---|---|
| Focused backend security suite | 65 passed |
| GigaChat/contact-intelligence suite | 88 passed |
| XML/SSRF/security-header suite | 21 passed |
| Frontend unit suite | 403 passed |
| Browser cookie focused suite | 15 passed |
| Wordstat Cloud/OAuth/error-redaction suite | 13 passed |
| Playwright journey/UX/a11y | 102 passed |
| `pip-audit` | 0 vulnerabilities |
| npm production/full audit | 0 vulnerabilities |
| Trivy image/config HIGH/CRITICAL | 0 |
| Semgrep ERROR-gate | 0 findings |
| OWASP ZAP baseline | 61 pass, 0 fail, 0 high/critical |

## Секреты

Gitleaks повторно проверил tracked HEAD и полную Git-историю в redacted-режиме 1 сентября. В tracked HEAD осталось 10 совпадений, и все они классифицированы как ложные срабатывания: idempotency/domain keys, стабильные seed keys, placeholder `Bearer` и test fixtures. Полный history scan вернул 620 redacted-совпадений в 29 commits; значения не выводились. Игнорируемые локальные `.env` не входят в tracked HEAD и не добавляются в rollout.

В истории подтверждены старые Wordstat credentials и legacy Supabase `service_role` для приостановленного проекта `SEOmaps` (`bvhpvzcvcuswiozhyqlk`). Текущий LocalOS production не использует Supabase. Нельзя добавлять новый Supabase key в LocalOS; сначала нужно определить других потребителей legacy-проекта.

Read-only consumer audit завершён в `outputs/localos-credential-rotation-readiness-2026-08-31.md`: локальных Supabase consumers не найдено; production `app`/`worker` не содержат Supabase variables; dashboard подтверждает, что `SEOmaps` приостановлен и может быть возобновлён до 15 ноября 2026 года. Wordstat остаётся реальным app/worker consumer, но production использует Cloud Search API: `auth_mode()` возвращает `cloud` в обоих runtime, а legacy OAuth variables лишь продолжают присутствовать как исторический fallback. Provider state и production не изменялись.

## Что ещё не завершено

1. Для Wordstat подтверждён текущий Cloud path, но остаются удаление/отзыв исторического OAuth fallback и controlled Cloud credential rotation. Для legacy Supabase `service_role` требуется provider-console revoke после проверки внешних потребителей.
2. Browser cookie migration реализована и проверена на staging. Остался совместимый production rollout: dual-stack/internal cohort, cookie-first и отзыв старых browser sessions после наблюдения; Mini App и Agent API сохраняют scoped bearer.
3. Production существенно расходится с Git из-за hot deploys. Нужен точный manifest и reconciliation, не `git pull`/reset/full rsync.
4. Production пока работает root-контейнерами. Реальные mounts проверены: перед non-root rollout нужен ownership snapshot и контролируемая смена владельца только `debug_data`; `setfacl` на host отсутствует.
5. После отдельного разрешения нужно проверить security headers на live edge `https://localos.pro`.
6. CSP enforcement и SRI/COOP/COEP остаются отдельным hardening-пакетом.

## Статус готовности

Docker staging и покрытые пользовательские/security-сценарии зелёные. Production остаётся **NO-GO** до reconciliation live drift, ротации исторических privileged credentials, подготовки ownership для non-root runtime и отдельного разрешения на deployment-пакеты.
