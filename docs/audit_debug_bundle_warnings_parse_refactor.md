# Технический аудит: debug bundle + warnings + parse_yandex_card refactor

## ЧАСТЬ 1 — Проверка сигнатуры parse_yandex_card

**Поиск вызовов:** `rg "parse_yandex_card\(" -n`

| Файл:строка | Вызов | Совместимость |
|-------------|--------|----------------|
| src/main.py:2228 | `parse_yandex_card(url)` | OK — только url, остальное по умолчанию |
| src/main.py:2252 | `parse_yandex_card(competitor_url)` | OK |
| src/worker.py:447 | `parse_yandex_card(url, keep_open_on_captcha=False, session_registry=..., session_id=...)` | OK — все именованные, без лишних kwargs |
| src/worker.py:630 | `parse_yandex_card(url, keep_open_on_captcha=True, session_registry=..., cookies=..., user_agent=..., viewport=..., locale=..., timezone_id=..., headless=True, debug_bundle_id=...)` | OK — все ключи в ALLOWED_SESSION_KWARGS или явный debug_bundle_id |
| src/parser_interception.py:2155 | `parse_yandex_card(test_url)` (в __main__) | OK |
| tests/test_parser_orchestrator.py | url, keep_open_on_captcha, session_registry[, session_id] | OK |
| tests/test_worker_*.py | подмена на fake_parse_yandex_card(url, **kwargs) | OK — реальная сигнатура не вызывается |

**Итог:** Позиционных аргументов после session_id нет. Лишних kwargs, не входящих в ALLOWED_SESSION_KWARGS, не передаётся. Несовместимостей нет, diff не требуется.

---

## ЧАСТЬ 2 — ALLOWED_SESSION_KWARGS

**Проверка использования каждого ключа:**

| key | используется | где |
|-----|--------------|-----|
| headless | да | parse_yandex_card → manager.open_session |
| cookies | да | parse_yandex_card → manager.open_session |
| user_agent | да | open_session (browser_session.py) |
| viewport | да | open_session |
| locale | да | open_session |
| timezone_id | да | open_session |
| proxy | да | open_session |
| launch_args | да | open_session |
| init_scripts | да | open_session |
| timeout | нет | нигде не передаётся в open_session |
| retries | нет | нигде не используется |
| trace | нет | нигде не используется |

**Сделано:** Из ALLOWED_SESSION_KWARGS удалены `timeout`, `retries`, `trace`. Оставлены только ключи, реально передаваемые в `manager.open_session`.

---

## ЧАСТЬ 3 — Debug bundle integrity

**Проверки:**

1. **self.debug_bundle_dir создаётся только при наличии debug_bundle_id**  
   В `__init__`: `self.debug_bundle_dir = os.path.join(..., debug_bundle_id) if debug_bundle_id else None` — корректно.  
   В методе `parse_yandex_card`: при `debug_bundle_id is None` генерируется id и затем выставляется `debug_bundle_dir` — это осознанное поведение (bundle при любом прогоне, если передан или сгенерирован id).

2. **main_http_status и http_status.txt**  
   После `page.goto`: `main_http_status` остаётся `None`, если `main_response is None` или при исключении. Запись: `f.write("" if main_http_status is None else str(main_http_status))` — исключений не вызывает.

3. **Запись только при guard `if self.debug_bundle_dir`**  
   Обнаружены записи без guard (при `debug_bundle_dir is None` использовался fallback `DEBUG_DIR`):
   - перехват JSON в `handle_response` (строки ~296–310);
   - `redirect_page.html` (~424–428);
   - `failed_page_final.html` (~447–451);
   - блок DEBUG BUNDLE summary (~812–943).

**Сделано:** Все перечисленные записи обёрнуты в `if self.debug_bundle_dir:`; при отсутствии bundle в файлы не пишем.

---

## ЧАСТЬ 4 — Fallback warnings (UndefinedColumn)

- **pgcode 42703** — стандартный код PostgreSQL для `undefined_column` (psycopg2: `errors.UndefinedColumn` имеет `pgcode == "42703"`). Использование `getattr(upd_err, "pgcode", None) == "42703"` корректно.

**Сделано:** В fallback при 42703 выполняется `UPDATE` с `error_message = warning_msg`, чтобы не терять предупреждения при отсутствии колонки `warnings`.

---

## ЧАСТЬ 5 — validation.json в bundle

**Сделано:** Сразу после `_validate_parsing_result` в worker добавлена запись в bundle:

- условие: `bundle_dir` и `validation_result` заданы;
- файл: `validation.json` с полями `quality_score`, `hard_missing`, `missing_fields`, `warnings`.

---

## ЧАСТЬ 6 — Self-check сценарии

| Сценарий | parsequeue.status | error_message | warnings | debug bundle | файлы в bundle |
|----------|-------------------|---------------|----------|---------------|-----------------|
| **1. Успешный full parse** | completed | NULL | строка или NULL | да (если передан business_id) | request_url.txt, final_url.txt, http_status.txt, page.html, payload.json, validation.json; опционально debug_*.json/html/png, redirect/failed_page*.html |
| **2. low_quality_payload** | error | `low_quality_payload missing=... score=... bundle=/app/debug_data/...` | не обновляется | да | те же + validation.json (если есть); payload.json с тем, что вернул парсер |
| **3. Playwright Sync-in-async crash** | error | `playwright_sync_in_async_loop exc=Error bundle=/app/debug_data/...` | не обновляется | да (bundle_dir создаётся воркером до вызова парсера) | exception.txt (traceback); request_url/final_url/http_status/page.html могут отсутствовать (парсер не дошёл) |

---

## Итог изменений (точечные правки)

- **parser_interception.py:** белый список ALLOWED_SESSION_KWARGS без timeout/retries/trace; все записи в debug (handle_response, redirect_page, failed_page_final, DEBUG BUNDLE summary) только при `if self.debug_bundle_dir`.
- **worker.py:** при pgcode 42703 в fallback пишем `error_message = warning_msg`; после `_validate_parsing_result` при наличии `bundle_dir` и `validation_result` пишем `validation.json`.

Полный diff — в `git diff src/parser_interception.py src/worker.py`.
