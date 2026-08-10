# Эстем: исправление парсинга контактов, оценки и runtime-состояния

Статус: **FIX_PROVEN_WITH_BASELINE_FAILURES**.

Production-данные, отправки, старая кампания Эстем и новая цепочка не изменялись.

## Исправлено

1. Парсер свободного текста больше не принимает ИНН, ОГРН, КПП, СНИЛС и номера лицензий за телефоны. Явные `tel:`-ссылки и структурированные телефонные поля продолжают обрабатываться прежним путём.
2. Реестр использует актуальный `touch.channel_status` раньше сохранённого `message_brief_json.channel_status`. При `recipient_missing` показывает «Нет контакта» и не показывает сохранённую оценку как актуальную. Оценка также скрывается при `requires_regeneration`.
3. Для signal-обращений от LocalOS raw-ошибка `ABSTRACT_SOLUTION` теперь блокирует approval даже при пустом `localos_action`. Партнёрские сообщения от имени другого бизнеса не затронуты.

## Red → green

- `test_estem_tax_id_and_medical_license_are_not_extracted_as_phone_contacts`: FAIL → PASS.
- `test_estem_generic_email_with_no_localos_action_cannot_approve_raw_abstract_solution`: FAIL → PASS.
- `AdminLeadRegistry.runtime-state.test.tsx`: 2 FAIL → 2 PASS.

Production-like fixture воспроизводит карточку Эстем: устаревшая draft-кампания, `requires_regeneration=true`, top-level `recipient_missing`, сохранённое `ready`, отсутствующий `contact_point_id` и историческая оценка 18/18. Компонент показывает «Нет контакта» и скрывает 18/18.

## Проверки

- Контакты + founder outreach: **196 passed**.
- Расширенный backend-набор контактов и outreach: **431 passed, 2 skipped, 2 baseline failures**.
- Frontend runtime-state: **2 passed**.
- Frontend production build: **PASS**.
- `git diff --check`: **PASS**.

## Не относящиеся к патчу baseline failures

1. `test_campaign_payload_links_delivery_and_human_reply_to_exact_touch` падает и на чистом `HEAD`: mock cursor не поддерживает уже существующий запрос `lead_workstream_research`.
2. `test_lead_drawer_exposes_manual_touch_actions_for_needs_attention` — ранее добавленный в грязном worktree тест, ожидающий отсутствующую UI-фразу «Отметить отправленным». Исправление не меняло этот участок интерфейса.

Эти два теста не исправлялись, потому что это расширило бы отдельно согласованный scope.
