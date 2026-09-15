# Хранилища фотографий: выпуск 15 сентября 2026

Пользователь запросил завершить инфраструктуру, добавить интерфейс Client ID/Secret, закоммитить, отправить и развернуть на production.

Страница: https://localos.pro/dashboard/settings/storage — только действующий superadmin LocalOS. API `/api/operator/storage-apps` GET/POST, секреты write-only, шифрование существующим EXTERNAL_AUTH_SECRET_KEY. Права проверяются по БД при каждом запросе; демонстрационные сессии запрещены. Ключи общие для платформы, клиент подключает свой аккаунт отдельно. Для Google и Яндекса сохранён доступ минимального объёма. Выбор произвольной папки не реализован.

Проверено: 38 backend-тестов на изолированном PostgreSQL, 6 frontend-тестов, Vite build. CUA-проверка узкой формы: оба провайдера, callback, поля, маскированный ввод секрета, ссылки на консоли и объяснение прав. Общий TypeScript-check имеет прежние 6 ошибок в AdminLeadRegistry/InfluencersPage, новые компоненты ошибок не добавляют.

Миграции: `20260914_google_drive` и `20260915_storage_oauth`, Alembic после проверенного pg_dump. Резервная копия: `/Users/alexdemyanov/Backups/LocalOS/20260915-storage/database.dump` и SHA256 рядом; архив полностью прочитан pg_restore. Данные клиентов и настройки пилотов не изменяются. API приложений не ограничен флагом конкретного бизнеса; подключение аккаунтов и синхронизация остаются под OPERATOR_WORKDAY_BUSINESS_IDS.

Частичный выпуск: исходники app/worker/operator-worker/telegram-bot, Compose env для необязательного Google и frontend/dist. Runtime images сохраняются. Перед применением сверяются хеши действующих исходников и index.html. Откат: `/opt/seo-app/.deploy/storage-20260915/rollback-files.tar.gz`; восстановить исходники, compose и frontend, пересоздать только затронутые сервисы; историю БД не удалять.

Доказательства: `/tmp/localos-storage-deploy/{backend.txt,frontend.txt,build.txt,types.txt,backup.verified,manifest.json}`; серверный журнал `/opt/seo-app/.deploy/storage-20260915/deploy.log` и read-only smoke. Факт завершённого развёртывания и живых проверок дополняется после выпуска. Настоящие OAuth/grant и загрузка в клиентский аккаунт требуют введённых реквизитов и согласия владельца; их нельзя считать проверенными до этого шага.
