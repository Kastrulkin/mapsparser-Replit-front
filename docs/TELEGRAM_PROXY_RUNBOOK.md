# Grimbird Proxy Runbook

Grimbird на OpenClaw является единственным актуальным VPN/proxy-контуром для Telegram и внешних HTTP API LocalOS.

## Адреса

| Где работает клиент | SOCKS5 | HTTP |
|---|---|---|
| На OpenClaw host | `socks5://127.0.0.1:10808` | `http://127.0.0.1:10809` |
| На LocalOS host | `socks5://192.168.0.177:10808` | `http://192.168.0.177:10809` |

`127.0.0.1` разрешён только процессам, запущенным на самом OpenClaw host. LocalOS работает на другом сервере и всегда использует private IP `192.168.0.177`.

## Назначение маршрутов

- Telegram Bot API, Meta Graph, VK и другие HTTP API: HTTP proxy `:10809`.
- Telethon, MTProto и другие SOCKS-capable клиенты: SOCKS5 proxy `:10808`.
- Парсинг через HTTP: HTTP proxy `:10809`, если конкретный parser/provider поддерживает proxy-параметр.
- Внутренний трафик LocalOS, PostgreSQL и callbacks не нужно отправлять через Grimbird.

## LocalOS env

После того как OpenClaw разрешил доступ с LocalOS, в `/opt/seo-app/.env` должны быть заданы:

```env
TELEGRAM_HTTP_PROXY=http://192.168.0.177:10809
OUTBOUND_HTTP_PROXY=http://192.168.0.177:10809
TELEGRAM_USERBOT_PROXY=socks5://192.168.0.177:10808

# Для parser/provider-контуров, которые читают эти параметры.
APIFY_HTTP_PROXY=http://192.168.0.177:10809
APIFY_HTTPS_PROXY=http://192.168.0.177:10809
```

`TELEGRAM_PROXY_URL` поддерживается как совместимый alias для Telegram userbot. Если заданы оба значения, `TELEGRAM_USERBOT_PROXY` имеет приоритет.

LocalOS намеренно не задаёт глобальные `HTTP_PROXY`/`HTTPS_PROXY`: это предотвращает случайное проксирование внутренних запросов и callbacks.

## Firewall handoff

Grimbird должен слушать private interface, а firewall OpenClaw должен разрешать TCP `10808` и `10809` только от LocalOS source IP/subnet.

Текущий production source IP LocalOS:

```text
80.78.242.105
```

Не открывайте proxy-порты в публичный интернет.

## Проверка с LocalOS host

Все server-команды выполняются из `/opt/seo-app`:

```bash
cd /opt/seo-app
curl -x http://192.168.0.177:10809 -I --max-time 12 https://api.telegram.org
curl --socks5-hostname 192.168.0.177:10808 -I --max-time 12 https://api.telegram.org
```

Ожидаемый результат:

```text
HTTP/2 302
location: https://core.telegram.org/bots
```

## Проверка из app и worker

```bash
cd /opt/seo-app
docker compose exec -T app sh -lc \
  'curl -x http://192.168.0.177:10809 -I --max-time 12 https://api.telegram.org'
docker compose exec -T worker sh -lc \
  'curl -x http://192.168.0.177:10809 -I --max-time 12 https://api.telegram.org'
```

Проверка фактической конфигурации приложения:

```bash
cd /opt/seo-app
docker compose exec -T app python3 - <<'PY'
from core.outbound_network import resolve_outbound_http_proxy
from core.telegram_network import resolve_telegram_http_proxy

print("outbound", resolve_outbound_http_proxy())
print("telegram", resolve_telegram_http_proxy())
PY
```

## Активация

1. OpenClaw разрешает `80.78.242.105` на TCP `10808/10809` по private network.
2. Обе проверки с LocalOS host возвращают `HTTP/2 302`.
3. Значения добавляются в `/opt/seo-app/.env`.
4. `app` и `worker` пересоздаются, чтобы получить новые env.
5. Host owner-bot перезапускается и проходит Telegram polling check.
6. Выполняется read-only Telegram preflight в LocalOS.
7. Только после успешной проверки удаляется или выключается legacy proxy runtime на LocalOS.

Команды применения:

```bash
cd /opt/seo-app
docker compose up -d --force-recreate app worker
systemctl restart openclaw-localos-telegram-bot.service
docker compose ps
docker compose logs --since 10m app worker
curl -I http://localhost:8000
```

## Если соединение не проходит

- `connection refused`: Grimbird слушает только loopback или firewall не разрешает LocalOS.
- `timeout`: проверить private route и firewall между LocalOS и OpenClaw.
- HTTP работает, SOCKS нет: Bot API сможет работать, но Telethon/userbot ещё не готов.
- SOCKS работает, HTTP нет: Telethon сможет работать, но Bot API и social HTTP adapters ещё не готовы.

При отказе передайте OpenClaw-агенту source IP `80.78.242.105` и попросите разрешить private TCP-доступ к `10808/10809`.
