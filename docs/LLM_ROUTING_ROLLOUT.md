# LLM Routing: rollout и rollback

Статус: `beta`. Этот runbook относится к маршрутизации DeepSeek Analytics / GigaChat Max Copy.
Он не включает генерацию кода приложений и не меняет approval, публикацию,
внешние отправки или клиентский биллинг.

## Безопасные состояния

| Состояние | `LLM_ROUTER_ENABLED` | `LLM_SHADOW_MODE` | Результат |
|---|---:|---:|---|
| Выключено | `false` | любое | Русские тексты выполняет GigaChat Max; DeepSeek analytics не запускается. |
| Shadow | `true` | `true` | Пользователь получает GigaChat Max; разрешённый cohort дополнительно анализируется DeepSeek. |
| Пилот | `true` | `false` | DeepSeek-задачи идут в DeepSeek только для `LLM_DEEPSEEK_BUSINESS_IDS`. |

Неизвестный `task_key` блокируется. DeepSeek не вызывается для бизнеса вне
cohort или при запрещённом классе данных. Shadow-вызовы не создают продуктовые
artifacts и не участвуют в клиентском биллинге.

## Маршруты моделей

- Все зарегистрированные русскоязычные генерации используют `GigaChat-Max`.
- GigaChat Pro не участвует в автоматическом fallback.
- DeepSeek Pro выполняет `average_ticket_analysis`, `service_catalog_analysis`,
  compiler и документы; Flash выполняет review classification, таблицы и
  неоднозначную классификацию намерений.
- При ошибке Max разрешён один DeepSeek Pro fallback только для public,
  business_internal или financial_aggregated payload. Для отзывов fallback
  требует отдельный обезличенный prompt; исходный PII prompt в DeepSeek не уходит.
- Ошибка обоих провайдеров передаёт caller-у reason code для deterministic fallback.

Каждый этап пишет `pipeline_id`, `pipeline_stage`, primary/fallback provider и
причину отказа в `metadata_json`; исходный prompt не сохраняется. Несколько
provider usage-записей одного pipeline не создают несколько продуктовых списаний.

## Preflight и миграция

Перед schema migration на production обязательно получить отдельное разрешение
владельца и сделать backup. Все серверные команды выполняются из канонического
каталога.

```bash
cd /opt/seo-app
mkdir -p db_backups
docker compose exec -T postgres pg_dump \
  -U "${POSTGRES_USER:-beautybot}" \
  -d "${POSTGRES_DB:-beautybot}" \
  -Fc > "db_backups/pre_llm_routing_$(date +%Y%m%d_%H%M%S).dump"
```

Проверка backup и текущей головы:

```bash
cd /opt/seo-app
ls -lh db_backups/pre_llm_routing_*.dump
docker compose run --rm app python -m alembic -c alembic.ini heads
```

После доставки backend и migration пересоздаются только затронутые сервисы,
чтобы они получили обновлённые переменные окружения. Entry point применяет
Alembic; затем нужно подтвердить новую голову и здоровье.

```bash
cd /opt/seo-app
docker compose up -d --no-deps --force-recreate app worker
docker compose ps
docker compose logs --since 10m app worker
curl -I http://localhost:8000
docker compose exec -T app python -m alembic -c alembic.ini current
```

Ожидаемая Alembic head: `20260722_001`.

## Shadow-пилот

1. Сохранить `DEEPSEEK_API_KEY` только в server environment.
2. Указать beta business IDs в `LLM_DEEPSEEK_BUSINESS_IDS`.
3. Установить `LLM_ROUTER_ENABLED=true`, `LLM_SHADOW_MODE=true`.
4. Оставить `LLM_SHADOW_MAX_CONCURRENCY=4`, пока нагрузка не измерена.
5. Установить `GIGACHAT_MODEL=GigaChat-Max` и `GIGACHAT_MODEL_MAX=GigaChat-Max`.
6. Перезапустить только `app` и `worker` и выполнить health checks выше.

Техническая статистика доступна в существующих ответах token usage в поле
`by_provider`. Она агрегируется по task/provider/model/shadow и содержит:

- `completion_rate` и `first_pass_valid_rate`;
- `fallback_rate` и количество correction retry;
- policy-blocked attempts;
- average и p95 latency;
- `automated_gate_passed` и обязательный `manual_review_required`.

Исходные промпты в `tokenusage` не сохраняются.

## Gate переключения

Для первого аналитического этапа нужны 50 анализов среднего чека, 50 каталогов
услуг и 100 наборов отзывов. `automated_gate_passed=true` означает только, что
выполнены автоматически измеримые условия:

- валидный JSON после correction retry не ниже 98%;
- fallback rate не выше 3%;
- policy-blocked attempts равны 0;
- p95 не выше 45 секунд для Pro и 20 секунд для Flash.

До переключения вручную проверяются supported intent не ниже 95%, фактическая
точность/неподтверждённые факты не выше 2%, сохранение provenance, отсутствие
двойного списания и отсутствие внешних действий без approval.

Переключение выполняется по одной задаче/cohort: средний чек, затем услуги, затем
отзывы — с тремя стабильными днями между этапами. Контент, outreach и knowledge
начинаются только после отдельной недельной оценки.

## Rollback

Schema rollback не нужен: новые колонки совместимы со старым runtime. Самый
быстрый rollback — отключить router, затем пересоздать `app` и `worker`.

```bash
cd /opt/seo-app
# В server environment установить LLM_ROUTER_ENABLED=false.
docker compose up -d --no-deps --force-recreate app worker
docker compose ps
docker compose logs --since 10m app worker
curl -I http://localhost:8000
```

Если нужно отключить только DeepSeek для отдельного бизнеса, удалить его ID из
`LLM_DEEPSEEK_BUSINESS_IDS`. Не переключать заблокированные данные на другого
внешнего провайдера: должен сработать deterministic fallback с reason code.

## Что не меняется

- Runtime исполняет сохранённый `steps_json`, а не вызывает compiler заново.
- Capability registry и LocalOS validator остаются границей исполнения.
- Approval обязателен для publish/send/payment/destructive/bulk/provider writes.
- Shadow не меняет artifacts, workflow, баланс или пользовательский результат.
- Цена пользовательских кредитов в этом пилоте не меняется.
