# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> Обе воспроизведённые причины устранены; точечные и смежные тесты, а также production build прошли.

**Project:** LocalOS<br>
**Bug:** Статистика тем не видна в мобильной Ленте<br>
**Environment:** Python 3.11.7 arm64, Vitest 4.1.10, Vite 7.3.6<br>
**Generated:** 2026-08-27

## Discovery scope

- Mobile feed rendering order
- Community topic snapshot selection for personalized source sets
- Production source fingerprints for the selected beauty business

## Ranked and tested candidates

| # | Candidate | Contract evidence | Trigger | Location | Confidence | Outcome |
|---:|---|---|---|---|---|---|
| 1 | Персональный fingerprint не использует совместимый отраслевой snapshot при ошибке расчёта | Отраслевые темы должны отображаться по умолчанию, а личные источники только дополняют подборку. | У бизнеса 53 отраслевых и один личный источник; персональный snapshot отсутствует, GigaChat временно отвечает 429. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/community_topic_trends.py:490 | high | REPRODUCED |
| 2 | Статистика отрисована после длинного суточного саммари | Статистика за месяц, квартал и год должна быть видна до блока суточных обсуждений. | Открытие мобильной Ленты с непустыми topics и topic_trends. | /Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/telegram/CommunityFeedMobile.tsx:214 | high | REPRODUCED |

## Original report

Пользователь открывает Ленту и сразу видит «О чём говорят предприниматели», но не видит статистику тем.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Сначала видна статистика пяти тем за месяц, квартал и год; при временном сбое персонального расчёта используются доступные отраслевые данные. | Суточное саммари шло первым, а при отсутствии точного персонального snapshot API мог вернуть пустой topic_trends. |

## Minimal reproduction

Два точечных теста проверяют fallback при ошибке обновления и DOM-порядок заголовков статистики и суточного саммари.

**Confirming signal:** Backend получил [] вместо трёх периодов; frontend compareDocumentPosition подтвердил, что статистика шла после суточного блока.

### Reproduction files approved at Gate 1

- [test_community_topic_trends.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_community_topic_trends.py:88>) — Регрессия совместимого отраслевого snapshot, одобренная на Gate 1.
- [CommunityFeedMobile.test.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/telegram/CommunityFeedMobile.test.tsx:38>) — Регрессия порядка блоков Ленты, одобренная на Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 4,560 ms | 6,464.749 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
2 focused regressions failed for the predicted reasons.
```

### After — fixed evidence

```text
Backend focused regression: 1 passed. Frontend focused regression: 1 passed. Broader checks: 15 backend tests passed, 3 frontend tests passed, Vite production build passed.
```

## Root cause

Backend искал только точный fingerprint набора источников и при ошибке обновления возвращал пустой результат. Frontend помещал статистику в конец карточки суточных тем.

## Approved fix

Добавлен выбор самого полного snapshot, чей набор источников входит в разрешённый набор бизнеса. Статистика вынесена в самостоятельную карточку перед суточным саммари.

**Why this is causal:** Fallback покрывает точное пустое состояние без смешивания посторонних источников, а новый DOM-порядок непосредственно делает статистику первым содержательным блоком Ленты.

### Production files approved at Gate 2

- [community_topic_trends.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/services/community_topic_trends.py:490>) — Совместимый subset-fallback snapshot, одобренный на Gate 2.
- [CommunityFeedMobile.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/telegram/CommunityFeedMobile.tsx:217>) — Отдельная карточка статистики перед суточными темами, одобренная на Gate 2.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Backend regression | ✅ passed | 6/6 тестов community_topic_trends и 15/15 смежных backend-тестов прошли. |
| Frontend regression | ✅ passed | 3/3 тестов CommunityFeedMobile прошли. |
| Production build | ✅ passed | Vite production build завершён успешно. |

## Reproduce

```bash
python3 -m pytest -q tests/test_community_topic_trends.py
```
```bash
cd frontend && npm test -- --run src/components/telegram/CommunityFeedMobile.test.tsx
```

## Limitations

- Визуальная проверка в авторизованном Telegram WebView не выполнялась в этом локальном цикле.

## Residual risks

- Если в базе нет ни точного, ни совместимого snapshot, статистика останется скрыта до первого успешного расчёта.

## Notes

- Fallback выбирает только подмножество уже разрешённых бизнесу источников; источники другого tenant не добавляются.
- Схема базы и публичные API-контракты не изменялись.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
