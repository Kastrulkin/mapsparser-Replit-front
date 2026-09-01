# LocalOS: live edge security headers — 2026-09-01

Проверка выполнена read-only для `https://localos.pro/`, `/login` и несуществующего `/api/health`. Production не изменялся.

| Header | Live state |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | camera/microphone/usb disabled; geolocation/payment same-origin |
| `Content-Security-Policy-Report-Only` | присутствует |
| Enforced `Content-Security-Policy` | отсутствует |
| COOP/COEP/CORP | отсутствуют |

Результат соответствует текущему rollout runbook: базовые live headers присутствуют, а CSP enforcement и COOP/COEP/CORP остаются отдельным hardening-пакетом. Endpoint `/api/health` возвращает 404 и не должен использоваться как production health signal; каноническая localhost-проверка остаётся `curl -I http://localhost:8000` на сервере.
