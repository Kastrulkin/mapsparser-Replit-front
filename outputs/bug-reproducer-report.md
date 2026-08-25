# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS
**Bug:** Нативный Yandex-парсер принимает неполную коллекцию отзывов
**Environment:** Python 3.11 arm64, pytest; production Docker worker on localos.pro
**Generated:** 2026-08-25

## Original report

Собственный парсер отзывов работает нестабильно; требуется сначала пробовать его, а при неудаче использовать Apify.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Нативный результат сохраняется только при достаточно полном наборе отзывов; блокировка, таймаут или неполнота запускают Apify fallback. | До исправления 5 загруженных отзывов при reviews_count=344 признавались успешным результатом; HTTP 429 и пустая страница могли занимать попытку несколько минут. |

## Minimal reproduction

Regression-тест передаёт валидную карточку Органики с reviews_count=344 и только пятью уникальными отзывами.

**Confirming signal:** До исправления _validate_parsing_result вернул True вместо False; тест завершился с exit code 1.

### Reproduction files approved at Gate 1

- [test_worker_services_quality.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_worker_services_quality.py:168>) — Regression-тест неполной коллекции и тесты native-first/fallback.
- [smoke_native_yandex_reviews.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/scripts/smoke_native_yandex_reviews.py:1>) — Read-only production canary нативного Yandex-парсера.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 1,329.118 ms | 517.449 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
F                                                                        [100%]
=================================== FAILURES ===================================
_______ test_validate_native_yandex_rejects_incomplete_review_collection _______

    def test_validate_native_yandex_rejects_incomplete_review_collection():
        card_data = {
            "title": "Органика",
            "address": "Санкт-Петербург, проспект Испытателей, 35",
            "rating": 4.8,
            "reviews_count": 344,
            "categories": ["Салон красоты"],
            "reviews": [
                {
                    "id": f"review-{index}",
                    "author": f"Автор {index}",
                    "rating": 5,
                    "text": f"Отзыв {index}",
                }
                for index in range(5)
            ],
        }

        is_successful, reason, validation = worker._validate_parsing_result(
            card_data,
            source="yandex_maps",
        )

>       assert is_successful is False
E       assert True is False

tests/test_worker_services_quality.py:191: AssertionError
=========================== short test summary info ============================
FAILED tests/test_worker_services_quality.py::test_validate_native_yandex_rejects_incomplete_review_collection
1 failed, 17 deselected in 0.82s
```

### After — fixed evidence

```text
.                                                                        [100%]
1 passed, 23 deselected in 0.25s
```

## Root cause

Валидация проверяла наличие reviews_count, но не сопоставляла его с фактически загруженными уникальными отзывами. Нативный sync Playwright обычно не имел отдельного короткого общего таймаута, а HTTP 403/429 не завершал разбор немедленно.

## Approved fix

Добавлена проверка полноты нативных отзывов, раннее распознавание HTTP 403/429/limited, изолированная нативная попытка с лимитом 180 секунд и автоматический fallback на Apify только для Yandex. Google, 2ГИС и Apple сохраняют прежние маршруты.

**Why this is causal:** Новый guard отклоняет доказанный неполный payload, а единый native-first helper вызывает Apify ровно при отклонении нативного результата. Принудительный subprocess гарантирует завершение нативной попытки по лимиту.

### Production files approved at Gate 2

- [worker.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/worker.py:1280>) — Ограниченная нативная попытка, проверка полноты и Apify fallback.
- [parser_interception.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/parser_interception.py:688>) — Быстрое завершение при HTTP 403/429 и ответах limited/forbidden.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Тот же regression-тест | ✅ passed | exit 1 до исправления → exit 0 после исправления. |
| Целевой worker/parser набор | ✅ passed | 34 passed, 2 skipped. |
| Расширенный worker/parser набор | ✅ passed | 49 passed, 3 skipped. |
| Синтаксис и diff | ✅ passed | py_compile и git diff --check завершились успешно. |

## Reproduce

```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_worker_services_quality.py -k native_yandex_rejects_incomplete_review_collection
```
```bash
arch -arm64 venv/bin/python -m pytest -q tests/test_worker*.py tests/test_parser*.py
```

## Limitations

- Полнота допускает расхождение до 5%, но не менее двух отзывов, чтобы учитывать удалённые или задвоенные записи.
- Production canary показал текущий HTTP 429 без прокси и пустой ответ через активный прокси; до улучшения proxy pool Apify будет использоваться часто.

## Residual risks

- Нужна production smoke-проверка после частичного deployment.
- Нативный маршрут зависит от качества proxy pool; fallback сохраняет обновление отзывов при его деградации.

## Notes

- Тестовые canary-запуски не записывали карточки или отзывы в production DB.
- Операторская резервация кредитов освобождается с фактической стоимостью 0, если нативный путь успешен и Apify не запускался.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
