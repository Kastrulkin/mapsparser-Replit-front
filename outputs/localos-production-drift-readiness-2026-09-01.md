# LocalOS: read-only production drift readiness — 2026-09-01

## Итог

Production доступен по SSH и работает, но blanket deploy остаётся `NO-GO`. Проверка выполнялась только чтением: файлы, контейнеры, credentials и данные не изменялись; значения секретов не читались и не выводились.

## Exact staging package

- Manifest: 252 файла, SHA-256 `828916fe94c515dd8fa5e95b4c3e99edbfa6a05e9efd71009b94bcd3cc87c79a`.
- Локальный verifier: `252/252`.
- `frontend/dist` пересобран с точными staging feature flags.
- Локальный dist и `/app/frontend/dist` в image `557f1a6e`: 184/184 файла, 0 missing, 0 extra, 0 hash mismatch.
- Канонический digest списка dist: `bb54aeae499579ed97568292cd9772a43d30056f7d63be851122c370d1a33d63`.
- Один непрерывный staging run: `108/108` на desktop, laptop и mobile.

## Production drift

Production Git HEAD: `c728015c95e47880120c025deed70c6c88657963`.

| Сравнение manifest с `/opt/seo-app` | Количество |
|---|---:|
| Совпадает | 97 |
| Отсутствует | 102 |
| Отличается | 53 |
| Всего | 252 |

Большая часть отсутствующих файлов — hashed frontend assets другой сборки. Это ожидаемое подтверждение drift, а не разрешение смешивать старые и новые assets. Frontend должен выпускаться атомарным dist-пакетом с полным rollback предыдущего dist.

Внутри production `app` и `worker` 15 из 17 backend-security файлов совпадают с manifest. Не выпущены две последние доказанные error-redaction правки:

- `src/api/media_intelligence_api.py`;
- `src/api/social_posts_api.py`.

## Credentials

- `app` и `worker`: Wordstat Cloud variables присутствуют.
- `app` и `worker`: legacy Wordstat OAuth fallback присутствовал на момент read-only snapshot; 2 сентября 2026 года он удалён из secret source и обоих runtime после успешной ротации Cloud key.
- `app` и `worker`: Supabase variables отсутствуют; 2 сентября 2026 года legacy Supabase `anon`/`service_role` отключены provider-side как API keys, legacy HS256 signing key отозван без добавления Supabase credentials в LocalOS.
- Значения переменных не читались и не выводились.

## Non-root и cookie preflight

- NUL-safe ownership snapshot `debug_data` передан только в локальный private temp и не добавлен в Git.
- Snapshot SHA-256: `f9f5710aa6322c8a8bd7f691fb949b6115d4949876da617ae0e13bee01da950c`.
- 1618 entries: 1614 принадлежат `root:root`, 4 — host user; ownership production не менялся.
- `BROWSER_COOKIE_AUTH_ENABLED` и совместимые cookie/CSRF flags не заданы в production `app`/`worker`; эффективный backend default остаётся `false`.
- Non-root ownership migration и cookie-auth cohort остаются отдельными rollout packages.

## Решение

- Полный `git pull`, reset, blanket rsync и смешивание frontend assets запрещены.
- Проверенный rollout готов только как набор отдельных partial packages с backup/rollback и отдельным разрешением на каждый production-пакет.
- Credential rotation и non-root ownership migration остаются самостоятельными gates и не должны объединяться с frontend или error-redaction deploy.
