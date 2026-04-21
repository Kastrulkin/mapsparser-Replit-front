# Telegram Proxy Runbook

Текущий production-маршрут Telegram для `localos.pro` больше не опирается на старый SOCKS/MTProxy для owner-bot polling.

Сейчас используется узкий `Telegram-only` outbound через `sing-box`:

- systemd unit: `localos-telegram-proxy.service`
- локальный HTTP proxy:
  - `127.0.0.1:2081` для host runtime
  - `172.17.0.1:2081` для default Docker bridge
  - `172.18.0.1:2081` для compose bridge
- transport:
  - `VLESS + REALITY`
  - server: `92.118.234.170:443`
  - `server_name = www.microsoft.com`
  - `fingerprint = chrome`

## Production model

- Owner-bot runtime:
  - `openclaw-localos-telegram-bot.service`
  - env file: `/opt/seo-app/runtime_bot/bot.env`
- Telegram proxy runtime:
  - `localos-telegram-proxy.service`
  - config: `/opt/seo-app/runtime_bot/telegram_proxy/config.json`
- App/worker:
  - используют `TELEGRAM_HTTP_PROXY`
  - остальной внешний трафик не уходит в VPN

Это важно:

- в VPN уходит только Telegram API traffic;
- `app`, `worker` и owner-bot не переводятся целиком на VPN;
- для WhatsApp, SMTP, Apify и прочих интеграций остаётся прямой outbound.

## Canonical env

Для host runtime:

```env
TELEGRAM_HTTP_PROXY=http://127.0.0.1:2081
```

Для Docker `app` и `worker`:

```env
TELEGRAM_HTTP_PROXY=http://host.docker.internal:2081
```

## Verify proxy

Проверка на хосте:

```bash
cd /opt/seo-app
systemctl status localos-telegram-proxy.service --no-pager -l
curl -I -x http://127.0.0.1:2081 https://api.telegram.org
```

Ожидаемо:

- `active (running)` у `localos-telegram-proxy.service`
- `HTTP/1.1 200 Connection established`
- затем `HTTP/2 302`
- `location: https://core.telegram.org/bots`

## Verify app/worker route

```bash
cd /opt/seo-app
docker compose exec -T app python3 - <<'PY'
import requests
from core.telegram_network import build_requests_proxy_kwargs, resolve_telegram_http_proxy
print(resolve_telegram_http_proxy())
r = requests.get('https://api.telegram.org', timeout=15, allow_redirects=False, **build_requests_proxy_kwargs())
print(r.status_code, r.headers.get('location'))
PY

docker compose exec -T worker python3 - <<'PY'
import requests
from core.telegram_network import build_requests_proxy_kwargs, resolve_telegram_http_proxy
print(resolve_telegram_http_proxy())
r = requests.get('https://api.telegram.org', timeout=15, allow_redirects=False, **build_requests_proxy_kwargs())
print(r.status_code, r.headers.get('location'))
PY
```

## Verify owner-bot runtime

```bash
cd /opt/seo-app
systemctl status openclaw-localos-telegram-bot.service --no-pager -l
journalctl -u openclaw-localos-telegram-bot.service -n 80 --no-pager -l
```

Зелёный сигнал:

- сервис `active (running)`
- в журнале есть:
  - `🤖 Telegram-бот запущен...`
  - `✅ Бот готов к работе. Ожидаю сообщения...`

## Current implementation note

В коде Telegram proxy routing реализован через:

- `src/core/telegram_network.py`
- `src/telegram_bot.py`
- `src/worker.py`
- `src/core/channel_delivery.py`
- `src/notifications.py`
- `src/ai_agent_webhooks.py`

То есть `TELEGRAM_HTTP_PROXY` уже является каноническим способом направить Telegram traffic через VPN.

## Host-runtime DB note

Owner-bot живёт вне Docker как systemd service, поэтому не может надёжно использовать compose DNS host `postgres`.

`/opt/seo-app/runtime_bot/run_localos_telegram_bot.sh` должен:

- брать `DATABASE_URL` из `seo-app-app-1`
- заменять host `postgres` на текущий IP контейнера `seo-app-postgres-1`

Если этого не сделать, бот может дойти до polling, но упасть при первом запросе к БД.

## Legacy notes

Что теперь не считать каноном для owner-bot:

- `telegram-bot.service` как основной runtime
- прямой polling без `TELEGRAM_HTTP_PROXY` на текущем VPS
- старый paid SOCKS как основной production route

MTProxy/SOCKS остаются только как исторический контекст и fallback для отдельных userbot-сценариев.
