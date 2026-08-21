# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS
**Bug:** Network manager cannot read reviews or partnership rooms
**Environment:** Local Python/pytest regression suite and Docker/PostgreSQL production at localos.pro
**Generated:** 2026-08-21

## Original report

Елена, менеджер сети Весёлая расчёска, должна видеть отзывы и цифровые комнаты точки Энгельса, 154, но получает отказ доступа.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Активный участник сети получает тот же read-доступ к отзывам и партнёрскому контуру точки, что и к остальным данным этой точки. | Маршрут отзывов возвращал 403, а партнёрский определитель бизнеса возвращал None, потому что оба пути признавали только непосредственного владельца. |

## Minimal reproduction

Два сфокусированных теста используют активное членство в сети и вызывают реальные функции маршрута и определения бизнеса.

**Confirming signal:** Два теста падали: отзывы возвращали 403 вместо 200, партнёрский resolver возвращал None вместо business-1.

### Reproduction files approved at Gate 1

- [test_employee_remaining_read_access.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_employee_remaining_read_access.py:129>) — Регрессия чтения отзывов активным участником сети.
- [test_network_member_access.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/tests/test_network_member_access.py:59>) — Регрессия разрешения партнёрского business scope участнику сети.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 3,039.808 ms | 1,993.457 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
.....F..F............                                                    [100%]
=================================== FAILURES ===================================
________ test_network_member_can_read_shared_business_external_reviews _________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x10b879690>

    def test_network_member_can_read_shared_business_external_reviews(monkeypatch):
        monkeypatch.setattr(external_accounts_api, "verify_session", _network_member_session)
        monkeypatch.setattr(external_accounts_api, "DatabaseManager", AccessDatabase)
        monkeypatch.setattr(external_accounts_api, "get_business_owner_id", lambda cursor, business_id: "owner-1")

        response = main.app.test_client().get(
            "/api/business/business-1/external/reviews",
            headers=_auth_headers(),
        )

>       assert response.status_code == 200
E       assert 403 == 200
E        +  where 403 = <WrapperTestResponse streamed [403 FORBIDDEN]>.status_code

tests/test_employee_remaining_read_access.py:139: AssertionError
_________ test_partnership_business_resolution_accepts_network_member __________

    def test_partnership_business_resolution_accepts_network_member():
        business_id = _resolve_business_for_user(
            PartnershipAccessCursor(),
            {"user_id": "member-1", "is_superadmin": False},
            "business-1",
        )

>       assert business_id == "business-1"
E       AssertionError: assert None == 'business-1'

tests/test_network_member_access.py:66: AssertionError
=========================== short test summary info ============================
FAILED tests/test_employee_remaining_read_access.py::test_network_member_can_read_shared_business_external_reviews
FAILED tests/test_network_member_access.py::test_partnership_business_resolution_accepts_network_member
2 failed, 19 passed in 2.28s
```

### After — fixed evidence

```text
.....................                                                    [100%]
21 passed in 1.32s
```

## Root cause

Два устаревших условия доступа обходили канонический verify_business_access и проверяли только owner_id/superadmin.

## Approved fix

Оба пути переведены на канонический verify_business_access без изменения правил для посторонних пользователей.

**Why this is causal:** Каноническая функция уже учитывает active business_members и network_members и сохранила tenant/demo ограничения.

### Production files approved at Gate 2

- [external_accounts_api.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/external_accounts_api.py:1961>) — Чтение отзывов использует каноническую проверку бизнес-доступа.
- [access_schema.py](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/src/api/prospecting/access_schema.py:489>) — Партнёрский scope учитывает активное членство в сети.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Focused red-to-green regression | ✅ passed | 2 failures before; 21 focused tests passed after. |
| Adjacent access and route suite | ✅ passed | 27 tests passed. |
| Production role probe | ✅ passed | Web reviews, services, content, partnerships and Mini App read routes returned 200 for Elena's role. |

## Reproduce

```bash
python3 -m pytest -q tests/test_employee_remaining_read_access.py tests/test_network_member_access.py
```

## Limitations

- Telegram UI cannot authenticate as Elena until she completes the one-time bind flow from her own Telegram account.

## Residual risks

- Telegram ID remains empty, so the bot and Mini App cannot yet identify Elena despite the corrected backend access.

## Notes

- Production subscription for Engelsa 154 was backed up and activated through 2026-09-15.
- No external messages or publications were sent.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
