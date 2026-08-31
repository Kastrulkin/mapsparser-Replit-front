# LocalOS: проверенный rollout runbook — 2026-08-31

## Проверенная база

- Канонический тестовый runtime: Docker Compose + отдельная PostgreSQL staging DB.
- Текущий staging-пакет прошёл 102/102 Playwright, backend security suites, frontend build, dependency scans, Semgrep, Trivy и ZAP baseline.
- Внешние credentials и действия в staging отключены. Production не изменялся.

## Почему нельзя делать полный deploy репозитория

Production содержит существенный drift от Git и следы прошлых hot deploys. Запрещены `git pull`, `git reset`, blanket `rsync --delete` и замена всего `/opt/seo-app`.

Перед каждым deploy:

1. Сформировать точный file manifest.
2. Сравнить файлы с live host и live container `/app/src/...`.
3. Сохранить предыдущие файлы, permissions, ownership, image IDs, Compose checksum и frontend asset manifest.
4. Для schema-пакета создать PostgreSQL backup и использовать только Alembic.
5. Прогнать точный пакет в Docker staging.

## Точный allowlist-manifest

Канонический manifest текущего проверенного дерева: `outputs/localos-rollout-manifest-2026-08-31.tsv`.

- SHA-256 самого manifest: `00df16e0bd8d1a4889706d4e70ac95dbae068b97a9dc481528580ff006b6743e`.
- `runtime_nonroot`: 2 файла.
- `backend_security`: 11 файлов.
- `frontend_source`: 49 файлов.
- `frontend_dist`: 183 файла.
- Локальный `frontend/dist` пересобран с точными staging feature flags и побайтово совпал с dist внутри образа, прошедшего 102/102 E2E. Digest отсортированного списка файлов: `e0d818ecfd7e066ae220d66656af61ce12b1836235f5f438325fed6edcc0c9d0`.

Перед упаковкой и перед отправкой файлов выполнить:

```bash
python3 scripts/verify_rollout_manifest.py
```

Любой отсутствующий файл или SHA mismatch означает `NO-GO`: manifest нужно пересоздать и повторить профильные тесты. Файлы вне allowlist не входят в production rollout. В частности, staging compose, fixtures, E2E, audit outputs, `.agent/`, Riderra-материалы и локальные daily reports не копируются на сервер.

## Пакеты rollout

### A. Staging и audit infrastructure

Credential-free overrides, isolation preflight, fixtures и regression gates. Production impact отсутствует.

### B. UX и accessibility

Accessible names, contrast, progress labels, touch targets и journey UI. Deployment: только точный frontend build/dist manifest.

Порядок: сохранить текущий live `frontend/dist` и asset manifest → проверить пакет `frontend_dist` → заменить только dist → проверить `/`, `/dashboard/today`, `/dashboard/growth-paths`, browser console и failed requests. Rollback: полностью вернуть сохранённый dist; отдельный restart backend не требуется.

### C. Backend security

Safe errors, XML hardening, SSRF transport contract, terminal 402 semantics и security headers. Deployment: только перечисленные `src/` файлы с выборочным restart.

Пакет разделён по зависимости:

- C1 code-only: `src/core/html_head.py`, `src/core/outbound_network.py`, `src/core/security_headers.py`, `src/legacy_routes/core_public.py`, `src/services/contact_intelligence_service.py`, `src/services/gigachat_client.py`, `src/services/outreach_personalization_ai.py`, `src/services/outreach_reply_tracking_service.py`.
- C2 image dependency: `requirements.txt`, `src/services/agent_source_ingestion.py`, `src/services/yandex_xml_parser.py`. `defusedxml` должен присутствовать в immutable image до рестарта этих модулей.

C1 допускает точечный sync в host source и контейнеры app/worker с рестартом только затронутых сервисов. Rollback: вернуть сохранённые файлы и повторить тот же restart. C2 нельзя имитировать временным `pip install` в живой контейнер: нужен проверенный image и сохранённые предыдущие image IDs.

### D. Browser cookie compatibility

Реализация staging-ready: production-компоненты больше не читают стандартные browser bearer tokens напрямую; общий transport очищает legacy credentials до первого render, использует cookie + CSRF и сохраняет bearer только для явно scoped Mini App/demo sessions. Billing provider return также проверен без JavaScript-токена.

Production rollout: dual-stack → internal cohort → cookie-first → наблюдение ошибок auth/CSRF → отзыв старых browser sessions. Mini App и Agent API сохраняют короткоживущий scoped bearer.

### E. Journey migrations и пять flows

Перед миграцией обязателен PostgreSQL backup. Флаги: foundation → influencer → partnership → maps → content → automation → notifications → upsell. Send/publish/payment сохраняют review и ручное подтверждение.

### F. Non-root production runtime

Локальный образ проверен с `uid=10001`. Перед production нужно инвентаризировать writable mounts, подготовить ownership только runtime paths, оставить source/migrations/assets read-only и проверить Alembic, parsers, uploads, worker и Telegram. Не объединять с migration или credential rotation.

Текущий Dockerfile одновременно включает C2 dependency и non-root runtime. Поэтому production image rebuild разрешён только после F-preflight. Если C2 нужно выпустить раньше, требуется отдельный промежуточный immutable image из C2-коммита до non-root-коммита; собирать произвольный Dockerfile из live drift запрещено. Rollback: вернуть сохранённые image IDs и исходный ownership runtime-каталогов, затем проверить app/worker/Telegram отдельно.

## Ротация credentials

- Точная карта потребителей и approval gates: `outputs/localos-credential-rotation-readiness-2026-08-31.md`.
- Wordstat: создать новый credential, обновить только реальные consumer env vars, выполнить smoke, затем revoke старого.
- Supabase `SEOmaps`: сначала определить внешних потребителей. Если их нет — retire/revoke; если есть — обновить и проверить их до revoke.
- Новый Supabase credential в LocalOS production не добавлять: runtime его не использует.
- Значения не передавать через command arguments, Git, отчёты или логи.

## Серверная дисциплина

Все server command blocks начинаются с `cd /opt/seo-app`. Долгие операции выполняются в tmux. Используются частичные обновления и restart затронутых сервисов; `docker compose down` не применяется.

После восстановления SSH первым запускается только read-only inventory:

```bash
cd /opt/seo-app
bash scripts/production_rollout_preflight.sh
```

Скрипт не выводит environment, не меняет ownership, не создаёт backup и не перезапускает сервисы. Он фиксирует Compose checksum, image IDs, configured/runtime UID, mounts, runtime-path ownership, PostgreSQL readiness, disk и локальный HTTP response. Любая мутация начинается только после разбора этого вывода и отдельного разрешения на конкретный пакет.

## Smoke после пакета

1. `docker compose ps`.
2. Свежие app/worker/Telegram logs.
3. `curl -I http://localhost:8000`.
4. Целевой endpoint/UI flow.
5. `https://localos.pro/` и live security headers.
6. Browser console и failed requests.
7. Для journey: orphan/stale/domain divergence.
8. Подтвердить отсутствие непредусмотренных send/publish/payment.

## Go/no-go

Production остаётся NO-GO без exact manifest, зелёного exact-package staging, rollback/backup, закрытых HIGH/CRITICAL findings, ротации historically exposed privileged credentials и подготовки production ownership для non-root runtime.

Каждый production-пакет требует отдельного явного разрешения пользователя.
