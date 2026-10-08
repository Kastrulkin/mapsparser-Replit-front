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

## Один Telegram-аккаунт для радара и аутрича

Этот контур не использует Bot API. В текущей BYO-модели каждый бизнес создаёт Telegram API application на `my.telegram.org`, а затем авторизует свой пользовательский аккаунт в LocalOS через номер, код и при необходимости 2FA.

LocalOS хранит `api_id`, `api_hash` и одну Telethon session в зашифрованном `externalbusinessaccounts.auth_data_encrypted`, но не сохраняет пароль 2FA. Для аккаунта проверяются два независимых разрешения в `telegram_account_permissions`:

- `radar_enabled` — чтение выбранных публичных источников и сохранение сигналов;
- `outreach_enabled` — отправка только одобренных сообщений и обязательный reply sync.

Отключение радара не блокирует отдельно разрешённый outreach. Отключение outreach немедленно запрещает новые Telegram sends, но не удаляет drafts и не отключает radar. Существующий radar account после миграции не получает outreach permission автоматически.

Перед каждым чтением или отправкой используется concrete `account_id`; глобальный «последний подключённый аккаунт» не выбирается.

API application само не определяет отправителя. Сообщения отправляются от пользовательского Telegram-аккаунта, которому принадлежит авторизованная session. `@LocalOspro_bot` и Mini App остаются отдельным control/publishing-контуром.

## Entity preflight

Публичная ссылка проверяется через Telethon `get_entity` по SOCKS5-маршруту:

- `User` — личный recipient candidate;
- bot — не recipient;
- broadcast channel — public radar source;
- megagroup/gigagroup/chat — group source, не личный recipient;
- unknown/unavailable — автоматическая отправка запрещена.

HTML preview `https://t.me/s/<username>` остаётся fallback для чтения публичных постов и может подтвердить источник, но не может подтвердить личного получателя. Результат entity API хранится в metadata knowledge source. Каналы и группы исключаются из `lead_contact_points` для direct outreach, а их посты сохраняются в `knowledge_documents` с permalink и датой.

Полный продуктовый поток описан в [OUTREACH_SYSTEM.md](OUTREACH_SYSTEM.md).

## LocalOS env

После того как OpenClaw разрешил доступ с LocalOS, в `/opt/seo-app/.env` должны быть заданы отдельные HTTP- и SOCKS5-учётные данные:

```env
TELEGRAM_HTTP_PROXY=http://<HTTP_USER>:<HTTP_PASSWORD>@192.168.0.177:10809
OUTBOUND_HTTP_PROXY=http://<HTTP_USER>:<HTTP_PASSWORD>@192.168.0.177:10809
TELEGRAM_USERBOT_PROXY=socks5://<SOCKS_USER>:<SOCKS_PASSWORD>@192.168.0.177:10808
TELEGRAM_PROXY_URL=socks5://<SOCKS_USER>:<SOCKS_PASSWORD>@192.168.0.177:10808

# Для parser/provider-контуров, которые читают эти параметры.
APIFY_HTTP_PROXY=http://<HTTP_USER>:<HTTP_PASSWORD>@192.168.0.177:10809
APIFY_HTTPS_PROXY=http://<HTTP_USER>:<HTTP_PASSWORD>@192.168.0.177:10809
```

`TELEGRAM_PROXY_URL` поддерживается как совместимый alias для Telegram userbot. Если заданы оба значения, `TELEGRAM_USERBOT_PROXY` имеет приоритет.

LocalOS намеренно не задаёт глобальные `HTTP_PROXY`/`HTTPS_PROXY`: это предотвращает случайное проксирование внутренних запросов и callbacks.

Храните реальные URL только в root-only `/opt/seo-app/.env` и защищённом Xray config. Не вставляйте пароли в команды, shell history, логи или отчёты. Firewall и пароль обязательны одновременно: firewall допускает только `192.168.0.90/32` на TCP `10808/10809` и UDP `10808`, а Xray требует аутентификацию.

## Firewall handoff

Grimbird должен слушать private interface. Выделенная служба `grimbird-proxy-firewall.service` поддерживает отдельную цепочку `GRIMBIRD_PROXY`: она пропускает только `192.168.0.90/32` к прокси-портам и не очищает общие firewall-цепочки или правила Fail2ban. Служба должна быть включена и запускаться до Xray.

Текущий публичный egress IP LocalOS (для запросов через публичный интернет):

```text
80.78.242.105
```

LocalOS и OpenClaw сейчас соединены по private-сети `192.168.0.0/24`. При
прямом подключении LocalOS к Grimbird `192.168.0.177` OpenClaw видит private
source `192.168.0.90`, а не публичный egress IP выше. Для этого маршрута
ограничивайте firewall source-адресом, который реально виден на private
интерфейсе (`192.168.0.90/32` в текущей топологии). Перед изменением
топологии перепроверьте адрес командой `ip route get 192.168.0.177` на LocalOS.

Не открывайте proxy-порты в публичный интернет.

## Проверка из app и worker

```bash
cd /opt/seo-app
docker compose exec -T app sh -lc \
  'curl -x "$TELEGRAM_HTTP_PROXY" -I --max-time 12 https://api.telegram.org'
docker compose exec -T worker sh -lc \
  'curl -x "$TELEGRAM_HTTP_PROXY" -I --max-time 12 https://api.telegram.org'
docker compose exec -T app sh -lc \
  'curl --proxy "$TELEGRAM_USERBOT_PROXY" --socks5-hostname -I --max-time 12 https://api.telegram.org'
```

Все server-команды выполняются из `/opt/seo-app`. Ожидаемый для аутентифицированных проверок ответ — HTTP `302` с `location: https://core.telegram.org/bots`; проверка без пароля должна завершаться отказом прокси.

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

1. Сверить private route и source address командой `ip route get 192.168.0.177` на LocalOS.
2. На OpenClaw проверить `systemctl is-enabled grimbird-proxy-firewall.service` и правила цепочки `GRIMBIRD_PROXY`; не открывать proxy-порты для публичного egress IP.
3. Убедиться, что запросы без пароля получают отказ, а аутентифицированные HTTP и SOCKS5 проверки возвращают `302` от Telegram.
4. Добавить секретные URL в `/opt/seo-app/.env` с ограниченными правами.
5. Пересоздать только затронутые `app`, `worker` и `telegram-bot`, затем проверить `docker compose ps`, логи, `curl -I http://localhost:8000` и polling heartbeat.
6. Проверить read-only Telegram preflight; не отправлять тестовые сообщения без отдельного разрешения.
7. Xray access log должен оставаться выключенным; error log и system journal ограничены ротацией/квотами.

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

При отказе проверьте private route, правила выделенной цепочки firewall, аутентификацию обоих входов и последние ошибки Xray/LocalOS. Не отключайте firewall и не возвращайте прокси без пароля для устранения ошибки.
