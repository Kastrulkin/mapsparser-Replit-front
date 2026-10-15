# Проверки MAX — 15.10.2026

Статус: beta; локальная проверка и серверный preflight выполнены. Реальная приёмка MAX заблокирована отсутствием бота, токена и тестового канала. Внешних сообщений/публикаций MAX и регистрации webhook не выполняли.

## Точный пакет выпуска

Проверки выполнялись в `/tmp/localos-max-release-src` с отдельным Git index. Пакет сохраняет уже развёрнутую серверную версию и добавляет MAX, общие owner-диалоги и необходимый единый контракт неизменяемого approval публикаций. Незавершённый локальный рефакторинг остановки worker и другие параллельные изменения не выкладываются. Первичный runtime-пакет: 53 файла; контрольные суммы и исходные версии сверены перед preflight. Последующий пакет сессий/TLS содержит семь конкретных файлов, включая новый max_tls.py. Чужой live worker.py сохранён: отдельно проверены AST-хеш MAX-функции и единственный вызов; целиком его исходник не выгружался. Итоговая сверка в четырёх контейнерах: 53 остальных runtime-файла плюс MAX-контракт worker. Git-ветка также фиксирует необходимые уже развёрнутые зависимости интерфейса и сервисов, отсутствовавшие в старом commit.

## Backend

**125 passed, 15 subtests passed**, 22.14 s (итоговый набор с TLS/сетевыми проверками); без пропусков в этом целевом наборе. Python 3.11 arm64, одноразовые PostgreSQL testcontainers (`pgvector/pgvector:0.8.0-pg16-trixie`), без production DSN.

```text
pytest -q
  tests/test_max_owner_dialogues.py
  tests/test_max_bootstrap.py
  tests/test_max_shared_approval_pg.py
  tests/test_max_control.py
  tests/test_max_control_pg.py
  tests/test_max_publication.py
  tests/test_max_reconciliation.py
  tests/test_telegram_control_scope.py
  tests/test_operator_voice_queue.py
  tests/test_telegram_approved_media_completeness.py
  tests/test_operator_credit_reservation.py
  tests/test_social_approval_binding_unit.py
  tests/test_social_media_facade_bindings.py
  tests/test_social_media_approval_normalization.py
  tests/test_max_tls.py
  tests/test_outbound_network.py
```

Проверены подпись/давность/подмена initData, реальный bootstrap → запись штатной сессии → отзыв, выключенный MAX, secret webhook и commit до ACK, одноразовый код/конкурентные потребители, разделение одинаковых числовых ID Telegram/MAX, сохранение этапов диалога, все 23 зарегистрированные команды, формы всех исходных inline-кнопок, меню без потери элементов, отмена, смена scope/чужой nonce/повторный клик, настройки телефона/Яндекс, точный preview продаж и атомарный apply без дублей, административный preview до запуска, общая запись approval и единственное применение для разговоров Telegram/MAX, voice deferral, запрет приватной доставки после отзыва доступа.

Provider transport проверялся имитациями ответов: точные текст/назначение/MID, отзыв approval после загрузки, неполный комплект медиа, uncertain timeout без повторного POST. Сверка доставки проверяет известные MID и никогда не повторяет отправку. Это не доказательство приёма реальным MAX.

Все runtime Python-файлы пакета синтаксически проверены. Миграция дважды применялась в отдельных PostgreSQL-схемах. В дереве два Alembic head: чужая ветка `20261005_children_hair_salon_type` не объединялась; целевая новая ветка — `20261015_max_control`, родитель `20261012_business_knowledge`.

## Интерфейс

**106 tests passed, 12 files passed**; `npm run typecheck` и `npm run build:all` успешны.

```text
src/lib/miniAppPlatform.test.ts
src/pages/MaxControlPage.test.tsx
src/pages/TelegramControlPage.test.tsx
src/components/operator/OperatorVoice.test.tsx
src/components/telegram/CommunityFeedMobile.test.tsx
```

Проверены разделение SDK/идентичностей, native download signature, отказ микрофона, MAX bootstrap/link-required и сохранение введённого кода после ошибки, safe checkout return в оба приложения, старые Telegram scope/race/empty/error сценарии, отзывы и общий Operator. Исправлены устаревшие fixtures LanguageProvider/навигации и AST fixture зависимостей media scope; прежние ошибки этих двух наборов больше не остаются скрытыми пропусками.

На публичном сервере браузером проверены gate `/max/control` («Откройте ЛокалОС в MAX») и переход в `/dashboard/max`: существующая авторизованная сессия открывает страницу привязки и явно показывает выключенный MAX. Ошибок нового bundle в консоли не обнаружено. Отдельный выход из общей браузерной сессии не выполнялся; переход через login проверен кодом/тестами. Ранее локально проверялся `/max/control?preview=1`. Реальный native клиент, Wi-Fi/мобильная сеть, checkout и микрофон MAX не проверены.

## Серверный preflight

Пакет загружен в отдельный staging; рабочие исходники на этом этапе не заменялись. Проверены отсутствие drift по всем 53 путям, синтаксис/хеши и импорт общих диалогов в app-контейнере, где нет Telegram SDK и httpx. Зарегистрированы 23 общих команды. Отключённые webhook/bootstrap возвращают 503, диагностика без авторизации — 403.

Результаты backup, миграции и проверки после выкладки записываются в `MAX_DEPLOYMENT_20261015.md`.

## Остаток приёмки

Полный repository suite и все старые social-publish PostgreSQL сценарии не запускались в этом целевом прогоне; отсутствие всех регрессий всего продукта не заявляется. Инвентарь содержит 413 точек исходного кода, а не 413 принятых сценариев.

Остаются доступ MAX/модерация, реальная webhook-подписка, парный проход каждой применимой строки матрицы на Android/iOS/desktop/web, микрофон/скачивание/внешние переходы/checkout, разрешённый тестовый канал с подтверждением текста/медиа/права/uncertain outcome и настройка внешних alert rules. Исходный Telegram `net::ERR_TIMED_OUT` этим переносом не считается исправленным. Полный проект нельзя объявлять принятым до этих проверок и согласования платформенных различий.

## Дополнительная защита сессии и TLS

MAX-сессия привязана к хешу конкретной пары max_id/linked_at. Повторная привязка отзывает старую сессию независимо от сдвига часов. Старые сессии без версии не принимаются; Telegram-сессии сохраняют прежний контракт.

API MAX использует отдельный доверенный корень Минцифры из существующего `src/certs/russian_trusted_root_ca_pem.crt`. DER SHA-256 `d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31` совпадает с корнем, полученным по проверенному HTTPS официального ресурса gu-st.ru. Проверка сертификата и hostname включена; системное доверие и certifi не изменены. Для API сертификат передаётся явно, чтобы общий REQUESTS_CA_BUNDLE не заменял его. Для скачивания/загрузки добавляется scoped SSLContext с сохранением публичных корней и DNS pinning. Приватные IP, перенаправления и автоматические повторы публикации запрещены.

На сервере GET `/me` без токена вернул 401 по двум проверенным TLS-маршрутам (requests и pinned urllib3). Это проверка сети/TLS, не авторизация реального бота. Нативная загрузка вложений и публикация требуют доступа MAX.


Финальная общая сборка: `/assets/index-QmFrE-LL.js`. Совместная живая приёмка настроек сотрудников завершена: сохранение без изменений отключено, изменение включает кнопку, возврат исходных значений снова отключает её; отмена и переходы работают, оба сотрудника остаются активны. В последнем окне логов после рестарта новых Traceback/NameError/ImportError нет; все девять сервисов running, Telegram/PostgreSQL/Redis healthy. Это не заменяет нативную приёмку MAX.
