# LocalOS: готовность к ротации credentials — 2026-08-31

## Legacy Supabase

- В авторизованной Supabase dashboard подтверждён проект `SEOmaps` с ref `bvhpvzcvcuswiozhyqlk`; вкладка относится к организации `Riderra`.
- Проект приостановлен. UI сообщает, что данные и backups сохранены, а resume доступен до 15 ноября 2026 года.
- Поиск по текущему LocalOS и соседним локальным проектам не нашёл runtime consumer этого project ref или Supabase environment configuration. Единственное текущее совпадение — security report.
- Read-only presence-check внутри production `app` и `worker` подтвердил: `SUPABASE_URL` и `SUPABASE_SERVICE_ROLE_KEY` отсутствуют в обоих runtime. Значения environment не выводились.
- LocalOS production Supabase не использует. Новый Supabase key в LocalOS добавлять нельзя.
- Ключи не просматривались, проект не возобновлялся, credentials не создавались и не отзывались.

Следующее внешнее действие требует action-time подтверждения: возобновить paused-проект, проверить список active API keys и затем отозвать legacy `service_role`, если внешний consumer не обнаружен. Перед resume нужно отдельно решить, требуется ли скачать backup; это не часть обычного LocalOS rollout.

## Yandex Wordstat

- LocalOS реально использует Wordstat в `src/api/wordstat_api.py`, `src/wordstat_client.py`, `src/wordstat_config.py` и background update.
- Compose передаёт Wordstat variables в app и worker.
- В локальных `.env` и `.env.bak.2026-03-21-173649` присутствуют три legacy OAuth значения: client ID, client secret и OAuth token. Значения не читались и не выводились.
- Read-only production presence-check подтвердил в `app` и `worker` обе группы переменных: Cloud Search API (`YANDEX_WORDSTAT_API_KEY` + `YANDEX_WORDSTAT_FOLDER_ID`) и legacy OAuth. Значения не читались и не выводились.
- В обоих production runtime `WordstatConfig.auth_mode()` возвращает `cloud`. Реализация `WordstatClient._make_request()` также отдаёт Cloud Search API безусловный приоритет, если заданы API key и folder ID; наличие legacy OAuth не меняет выбранный endpoint.
- В production DB сохранены 5 747 общих и 544 пользовательских Wordstat-записи. Последние `updated_at` — 8 июля 2026 года, поэтому наличие данных не считается свежим provider smoke.
- Внешний Wordstat-запрос во время аудита намеренно не выполнялся: он расходует provider quota. Выбранный auth path доказан конфигурацией обоих runtime и текущей реализацией; работоспособность нового/ротированного credential проверяется отдельным approved smoke после замены.
- Добавлены regression-тесты для одновременного наличия Cloud и OAuth credentials: config и HTTP client обязаны выбрать Cloud endpoint. В тот же focused-набор включены три доказанные проверки redaction внутренних API-ошибок; после согласованного fix полный Wordstat suite прошёл: **10 passed**.

Безопасный порядок ротации:

1. Считать Cloud Search API текущим production path; не переключать runtime обратно на legacy OAuth.
2. В Yandex console создать новый Cloud API credential либо подтвердить допустимость текущего scoped key. Создание credentials требует отдельного action-time подтверждения.
3. Обновить только production secret source для `app` и `worker`, выполнить выборочный restart и один согласованный Wordstat smoke с минимальным запросом.
4. После успешного Cloud smoke удалить legacy OAuth variables из production secret source и отозвать старый OAuth token/client secret у provider. Это production/provider mutation и требует отдельного подтверждения непосредственно перед выполнением.
5. Удаление локального `.env.bak.2026-03-21-173649` выполнять отдельно: это destructive action и не должно быть скрытым шагом ротации.

## Статус

Карта потребителей и активный production auth path подтверждены read-only. Production и provider state не изменялись. Ротация остаётся внешним approval gate и не блокирует проверенный staging package, но блокирует production go-live security decision.
