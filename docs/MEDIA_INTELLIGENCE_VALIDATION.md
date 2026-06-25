# Media Intelligence Validation

Статус: internal runbook before first live proof.

## Цель

Перед первым реальным бизнесом проверить, что фото анализируется один раз, повторные публикации используют cache, кредиты списываются только за реальные Vision-вызовы, а ошибки не оставляют зависшие списания.

## Validation Scenarios

### 1. Новая фотография

1. Включить `vision_enabled` для бизнеса через `POST /api/media-intelligence/settings`.
2. Создать asset через `POST /api/media-intelligence/photos`.
3. Запустить `POST /api/media-intelligence/photos/<asset_id>/analyze`.

Ожидаемо:

- `photo_assets.analysis_status = analyzed`;
- `photo_assets.meta_storage_key` указывает на `photo.meta.json`;
- создан `ai_usage_events` с `cache_hit = false`;
- списано `2` кредита;
- создан `ai_runtime_cache`.

### 2. Повторная публикация с тем же фото

Повторить `analyze` для того же `asset_id`, `asset_version`, prompt/context.

Ожидаемо:

- VisionProvider не вызывается;
- ответ `status = cached`;
- создан `ai_usage_events` с `cache_hit = true`;
- `charged_credits = 0`;
- новых списаний в ledger нет.

### 3. Изменённая фотография

1. Создать новую версию через `POST /api/media-intelligence/photos/<asset_id>/version`.
2. Повторить `analyze`.

Ожидаемо:

- `asset_version` увеличился;
- `analysis_status` сброшен в `not_analyzed`;
- повторный анализ выполняется;
- списывается `2` кредита;
- cache ключ новый из-за новой версии.

### 4. Одно фото в нескольких публикациях

Для одного asset вызвать `POST /api/media-intelligence/photos/<asset_id>/usage` пять раз с разными `target_id`.

Ожидаемо:

- анализ один;
- usage-событий пять;
- списание одно;
- `last_used_at` обновляется.

### 5. Выключенная функция

Не включать `vision_enabled` и попробовать создать asset через `POST /api/media-intelligence/photos`.

Ожидаемо:

- asset не создаётся;
- VisionProvider не вызывается;
- кредиты не списываются;
- API возвращает человеческое сообщение: `Работа с фотографиями выключена.`

### 6. Ошибка VisionProvider

Смоделировать ошибку GigaChat Vision.

Ожидаемо:

- 3 попытки;
- reservation released;
- списания нет;
- `photo_assets.analysis_status = analysis_failed`;
- `analysis_error` сохранён;
- API возвращает: `Не удалось автоматически проанализировать фотографию.`;
- повторный запуск возможен позже.

## Economics Check

Endpoint:

```http
POST /api/media-intelligence/economics/photo-analysis
```

Payload:

```json
{
  "photo_count": 100,
  "provider_total_cost": 0,
  "credit_price": 5,
  "multiplier": 10
}
```

Проверить:

- общую стоимость provider;
- стоимость одного анализа;
- выручку по кредитам;
- `needs_meter_adjustment`.

Если `needs_meter_adjustment = true`, до первого клиента нужно менять billing meter: `photo_analysis = 2 credits` недостаточно для выбранной стоимости provider и целевой наценки.

## Live Proof Gate

Live proof на реальном бизнесе, например `Весёлая расчёска`, начинается только после прохождения сценариев 1-6.
