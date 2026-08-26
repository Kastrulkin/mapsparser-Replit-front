# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS
**Bug:** Operator hides content-plan posts behind a false tool-catalog error
**Environment:** LocalOS production trace plus Python 3.11.7 regression tests on Darwin arm64
**Generated:** 2026-08-26

## Original report

For Riderra (Tallinn), the request ‘покажи мне вчерашние посты из контент-плана’ produced a content link but said that the tool catalog was missing and omitted the posts from the response body.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | The response body contains the title and full draft text for the 25 August post, excludes other dates, and preserves the content link. | The tool returned the target post, but the final model text claimed that no tool catalog was provided; the UI showed only the link and charged one credit. |

## Minimal reproduction

A focused unit test runs content.list_items with posts for 25 and 26 August, then makes the planner return the exact false catalog-error message seen in production.

**Confirming signal:** Before the fix, the returned chat_response contained the false catalog error instead of the 25 August title and draft body.

### Reproduction files approved at Gate 1

- [test_operator_tool_loop.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_operator_tool_loop.py:370>) — Approved reproduction of the exact false final message with yesterday and today fixtures.
- [test_operator_tool_loop.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_operator_tool_loop.py:431>) — Adjacent check prevents substituting content from another date when the requested day is empty.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 532.227 ms | 467.639 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
............F                                                            [100%]
=================================== FAILURES ===================================
_ test_tool_loop_renders_yesterday_content_in_body_when_planner_claims_catalog_missing _

    def test_tool_loop_renders_yesterday_content_in_body_when_planner_claims_catalog_missing():
        decisions = iter(
            [
                {"action": "tool_call", "tool": "content.list_items", "arguments": {}},
                {
                    "action": "final",
                    "message": "Каталог инструментов не предоставлен. Пожалуйста, передайте список доступных инструментов для выполнения задач.",
                },
            ]
        )

        result = run_operator_tool_loop(
            business_id="business-1",
            user_id="user-1",
            message="покажи мне вчерашние посты из контент-плана",
            tools=[
                _tool(
                    "content.list_items",
                    lambda _args: {
                        "status": "available",
                        "module": "content",
                        "items": [
                            {
                                "id": "post-yesterday",
                                "title": "Багаж, коляски и спортинвентарь",
                                "draft_text": "Укажите число пассажиров и весь нестандартный багаж.",
                                "scheduled_for": "2026-08-25",
                                "status": "edited",
                            },
                            {
                                "id": "post-today",
                                "title": "Детское кресло в трансфере",
                                "draft_text": "Укажите возраст ребёнка при бронировании.",
                                "scheduled_for": "2026-08-26",
                                "status": "edited",
                            },
                        ],
                        "as_of": "2026-08-26T06:50:29+00:00",
                        "ui_actions": [
                            {
                                "action": "open_result",
                                "label": "Открыть историю контента и черновиков",
                                "href": "/dashboard/content",
                            }
                        ],
                        "external_writes_performed": False,
                    },
                )
            ],
            planner=lambda _state: next(decisions),
        )

>       assert "Каталог инструментов не предоставлен" not in result["chat_response"]
E       AssertionError: assert 'Каталог инс...предоставлен' not in 'Каталог инс...нения задач.'
E
E         'Каталог инструментов не предоставлен' is contained here:
E           Каталог инструментов не предоставлен. Пожалуйста, передайте список доступных инструментов для выполнения задач.

tests/test_operator_tool_loop.py:422: AssertionError
=========================== short test summary info ============================
FAILED tests/test_operator_tool_loop.py::test_tool_loop_renders_yesterday_content_in_body_when_planner_claims_catalog_missing
1 failed, 12 passed in 0.14s
```

### After — fixed evidence

```text
.............                                                            [100%]
13 passed in 0.11s
```

## Root cause

The action=final branch trusted the model's final text after a successful tool call. The deterministic content formatter was used only for planner errors and understood today but not yesterday.

## Approved fix

For relative-date content requests, derive today or yesterday in Europe/Moscow, select only matching items, and render title, date, status, and full draft text from the successful tool output. Preserve the original result fields and UI actions.

**Why this is causal:** The fix bypasses the unreliable final prose only for the proven content/date path and formats the already-returned source data that the previous branch discarded.

### Production files approved at Gate 2

- [operator_tool_loop.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/operator_tool_loop.py:114>) — Relative-date resolution and deterministic full-body content response.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact red-to-green reproducer | ✅ passed | Exit code changed from 1 to 0 with the same test command. |
| Targeted tool-loop suite | ✅ passed | 14 tests passed. |
| Broader Operator suite | ✅ passed | 240 tests passed. |
| Static validation | ✅ passed | py_compile and git diff --check passed. |
| Production deployment | ✅ passed | app and worker use SHA-256 feae3bf16cbae4c626c05198c377c9b0ca12942e10634d0f1f9efa00e25797bb; HTTP returned 200 and the in-container dated-content smoke passed. |
| Billing correction | ✅ passed | One idempotent +1 compensating ledger entry restored the user balance from 40 to 41. |

## Reproduce

```bash
./venv/bin/python -m pytest -q tests/test_operator_tool_loop.py
```
```bash
./venv/bin/python -m pytest -q tests/test_operator*.py
```

## Limitations

- Deterministic date filtering currently covers the Russian relative-date words ‘сегодня’ and ‘вчера’.
- The paid production request was not repeated because doing so could create another charge.

## Residual risks

- Other relative date expressions such as ‘позавчера’ or explicit ranges still use the model response unless separately implemented.
- Live provider phrasing remains variable for content requests that do not contain a supported relative-date expression.

## Notes

- Gate 1 and Gate 2 were explicitly approved by the user.
- Commit `5acd125b` was pushed to GitHub and GitVerse and deployed to LocalOS production.
- Refund ledger entry: `f2ab7194-ff2e-4fd8-b617-888939bb0f57`; original charge remains intact for audit.
- No publication, external send, or provider write was performed.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
