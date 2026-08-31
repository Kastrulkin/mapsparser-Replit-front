# LocalOS: готовность к ротации credentials — 2026-08-31

## Legacy Supabase

- В авторизованной Supabase dashboard подтверждён проект `SEOmaps` с ref `bvhpvzcvcuswiozhyqlk`; вкладка относится к организации `Riderra`.
- Проект приостановлен. UI сообщает, что данные и backups сохранены, а resume доступен до 15 ноября 2026 года.
- Поиск по текущему LocalOS и соседним локальным проектам не нашёл runtime consumer этого project ref или Supabase environment configuration. Единственное текущее совпадение — security report.
- LocalOS production по текущему коду Supabase не использует. Новый Supabase key в LocalOS добавлять нельзя.
- Ключи не просматривались, проект не возобновлялся, credentials не создавались и не отзывались.

Следующее внешнее действие требует action-time подтверждения: возобновить paused-проект, проверить список active API keys и затем отозвать legacy `service_role`, если внешний consumer не обнаружен. Перед resume нужно отдельно решить, требуется ли скачать backup; это не часть обычного LocalOS rollout.

## Yandex Wordstat

- LocalOS реально использует Wordstat в `src/api/wordstat_api.py`, `src/wordstat_client.py`, `src/wordstat_config.py` и background update.
- Compose передаёт Wordstat variables в app и worker.
- В локальных `.env` и `.env.bak.2026-03-21-173649` присутствуют три legacy OAuth значения: client ID, client secret и OAuth token. Значения не читались и не выводились.
- Cloud Search API mode (`YANDEX_WORDSTAT_API_KEY` + `YANDEX_WORDSTAT_FOLDER_ID`) в локальных env не настроен; runtime выбирает legacy OAuth fallback.

Безопасный порядок ротации:

1. После восстановления SSH выполнить только presence-check production app/worker environment без вывода значений.
2. В Yandex console создать новую credential pair/token либо перейти на Cloud Search API key + folder. Создание credentials требует отдельного action-time подтверждения.
3. Обновить только production secret source для app и worker, выполнить выборочный restart и Wordstat smoke.
4. После успешного smoke отозвать старый OAuth token/secret.
5. Удаление `.env.bak.2026-03-21-173649` выполнять отдельно: это локальное destructive action и не должно быть скрытым шагом ротации.

## Статус

Карта потребителей подготовлена. Production и provider state не изменялись. Ротация остаётся внешним approval gate и не блокирует проверенный staging package, но блокирует production go-live security decision.
