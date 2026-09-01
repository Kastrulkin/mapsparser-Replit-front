# LocalOS: проверенный rollout runbook — 2026-08-31

## Проверенная база

- Канонический тестовый runtime: Docker Compose + отдельная PostgreSQL staging DB.
- Текущий staging-пакет прошёл 108/108 Playwright одним непрерывным запуском, backend security suites, frontend build, dependency scans, Semgrep, Trivy и ZAP baseline.
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

- SHA-256 самого manifest: `828916fe94c515dd8fa5e95b4c3e99edbfa6a05e9efd71009b94bcd3cc87c79a`.
- `runtime_nonroot`: 2 файла.
- `backend_security`: 17 файлов.
- `frontend_source`: 49 файлов.
- `frontend_dist`: 184 файла.
- Локальный `frontend/dist` пересобран с точными staging feature flags и побайтово совпал с 184/184 файлами внутри образа `557f1a6e`, прошедшего E2E 1 сентября 2026 года. Канонический `LC_ALL=C` digest отсортированного списка файлов: `bb54aeae499579ed97568292cd9772a43d30056f7d63be851122c370d1a33d63`.

Перед упаковкой и перед отправкой файлов выполнить:

```bash
python3 scripts/verify_rollout_manifest.py
```

После новой проверенной frontend-сборки manifest обновляется детерминированно:

```bash
python3 scripts/refresh_rollout_manifest.py
python3 scripts/verify_rollout_manifest.py
```

Любой отсутствующий файл или SHA mismatch означает `NO-GO`: manifest нужно пересоздать и повторить профильные тесты. Файлы вне allowlist не входят в production rollout. В частности, staging compose, fixtures, E2E, audit outputs, `.agent/`, Riderra-материалы и локальные daily reports не копируются на сервер.

Read-only comparison 1 сентября подтверждает production drift: 97 файлов совпадают, 102 отсутствуют и 53 отличаются. Внутри `app` и `worker` совпадают 15/17 backend-security файлов; две последние media/social error-redaction правки ещё не выпущены. Полный отчёт: `outputs/localos-production-drift-readiness-2026-09-01.md`.

Повторный non-root preflight сохранил NUL-safe ownership snapshot только локально: 1618 entries, из них 1614 `root:root`. Production ownership не менялся. Cookie-auth flags в текущих `app`/`worker` не заданы и эффективный backend default остаётся выключенным; cookie rollout нельзя объединять с non-root или credential rotation.

## Пакеты rollout

### A. Staging и audit infrastructure

Credential-free overrides, isolation preflight, fixtures и regression gates. Production impact отсутствует.

### B. UX и accessibility

Accessible names, contrast, progress labels, touch targets и journey UI. Deployment: только точный frontend build/dist manifest.

Порядок: сохранить текущий live `frontend/dist` и asset manifest → проверить пакет `frontend_dist` → заменить только dist → проверить `/`, `/dashboard/today`, `/dashboard/growth-paths`, browser console и failed requests. Rollback: полностью вернуть сохранённый dist; отдельный restart backend не требуется.

### C. Backend security

Safe errors, XML hardening, SSRF transport contract, terminal 402 semantics и security headers. Deployment: только перечисленные `src/` файлы с выборочным restart.

Пакет разделён по зависимости:

- C1 code-only: `src/api/wordstat_api.py`, `src/core/html_head.py`, `src/core/outbound_network.py`, `src/core/security_headers.py`, `src/legacy_routes/core_public.py`, `src/services/contact_intelligence_service.py`, `src/services/gigachat_client.py`, `src/services/outreach_personalization_ai.py`, `src/services/outreach_reply_tracking_service.py`.
- C2 image dependency: `requirements.txt`, `src/services/agent_source_ingestion.py`, `src/services/yandex_xml_parser.py`. `defusedxml` должен присутствовать в immutable image до рестарта этих модулей.

C1 допускает точечный sync в host source и контейнеры app/worker с рестартом только затронутых сервисов. Rollback: вернуть сохранённые файлы и повторить тот же restart. C2 нельзя имитировать временным `pip install` в живой контейнер: нужен проверенный image и сохранённые предыдущие image IDs.

### D. Browser cookie compatibility

Реализация staging-ready: production-компоненты больше не читают стандартные browser bearer tokens напрямую; общий transport очищает legacy credentials до первого render, использует cookie + CSRF и сохраняет bearer только для явно scoped Mini App/demo sessions. Billing provider return также проверен без JavaScript-токена.

Production rollout: dual-stack → internal cohort → cookie-first → наблюдение ошибок auth/CSRF → отзыв старых browser sessions. Mini App и Agent API сохраняют короткоживущий scoped bearer.

### E. Journey migrations и пять flows

Перед миграцией обязателен PostgreSQL backup. Флаги: foundation → influencer → partnership → maps → content → automation → notifications → upsell. Send/publish/payment сохраняют review и ручное подтверждение.

### F. Non-root production runtime

Локальный образ проверен с `uid=10001`. Перед production нужно инвентаризировать writable mounts, подготовить ownership только runtime paths, оставить source/migrations/assets read-only и проверить Alembic, parsers, uploads, worker и Telegram. Не объединять с migration или credential rotation.

Текущий Dockerfile одновременно включает C2 dependency и non-root runtime. Поэтому production image rebuild разрешён только после F-preflight. Если C2 нужно выпустить раньше, промежуточный immutable image собирается из `67cd05e2` (`Harden LocalOS backend security boundaries`); non-root/staging пакет начинается с `c6cbe63d` (`Add isolated Docker staging and full journey E2E`). Собирать произвольный Dockerfile из live drift запрещено. Rollback: вернуть сохранённые image IDs и исходный ownership runtime-каталогов, затем проверить app/worker/Telegram отдельно.

Read-only live preflight от 31 августа:

- production Git HEAD: `c728015c95e47880120c025deed70c6c88657963`;
- Compose checksum: `59893bdb870263432afde759ed8a1f3ff6206fd4fa9d5948b5c185e6b7069a7b`;
- app/worker image: `sha256:9ef456892909839202f564eea9ca79ff6de42dac0437c48b634701f77e2f4b4b`;
- Telegram image: `sha256:0b93edee0489d72ff52abe6fe745481795ed411e18c947cb93e0a3dbcbd8d7c7`;
- app, worker и Telegram runtime UID: `0`;
- `src`, `alembic_migrations` и entrypoint смонтированы read-only;
- `debug_data`: 445 МБ, 1432 файла; 1591 entries принадлежат `root:root`, 4 — `501:staff`; host не имеет `setfacl`;
- свободно 8.3 ГБ, PostgreSQL healthy, localhost HTTP 200.

F-rollout обязан сначала сохранить NUL-safe snapshot `uid/gid/path` для каждого entry в `debug_data`, затем изменить владельца только этого explicit path на `10001:10001`. Нельзя применять recursive ownership к `/opt/seo-app`, frontend, source, migrations или database volumes. После recreate отдельно проверить запись app и worker в `debug_data`; при rollback вернуть предыдущие image IDs и ownership из snapshot. Эта ownership mutation требует отдельного разрешения непосредственно перед выполнением.

## Ротация credentials

- Точная карта потребителей и approval gates: `outputs/localos-credential-rotation-readiness-2026-08-31.md`.
- Wordstat: production `app` и `worker` уже выбирают Cloud Search API; создать/подтвердить scoped Cloud credential, обновить только эти два consumer runtime, выполнить минимальный approved smoke, затем удалить и отозвать legacy OAuth fallback.
- Supabase `SEOmaps`: сначала определить внешних потребителей. Если их нет — retire/revoke; если есть — обновить и проверить их до revoke.
- Новый Supabase credential в LocalOS production не добавлять: read-only production presence-check подтвердил отсутствие `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY` в `app` и `worker`.
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
