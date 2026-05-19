# Telegram Bot-to-Bot Security

Status: `foundation`

Telegram bot-to-bot communication can become a transport for LocalOS Agent API. LocalOS should not trust a Telegram message by itself. The trust chain remains:

`agent_clients -> scopes -> agent_action_ledger -> human approval`

## Why It Matters

Telegram bots can now communicate with other bots when bot-to-bot communication mode is enabled. This is useful for multi-agent workflows, but it creates new risks:

- infinite bot loops;
- unknown bots triggering automation;
- bots trying to publish, send, edit, or delete through chat messages;
- unclear identity between human users, business owners, LocalOS bot, and external agent bots.

## Sender Classification

Every Telegram update should be classified before routing:

- `human`;
- `telegram_bot`;
- `localos_bot`;
- `trusted_agent_bot`;
- `unknown_bot`.

The foundation helper is `src/core/telegram_agent_transport.py`.
It is wired into:

- `src/telegram_bot.py`;
- `src/ai_agent_webhooks.py`.

## Routing Rules

Current default behavior:

- human messages continue through the current Telegram UX;
- messages from LocalOS bot itself are ignored;
- unknown bots do not trigger automation, are written to `agent_action_ledger`, and alert superadmin;
- bound Telegram agent bots are resolved through `agent_clients.metadata_json`;
- sandbox/suspended Telegram agent bots are stopped before normal routing and logged;
- live Telegram agent bots must still use Agent API scopes and approval flow instead of direct chat automation;
- publish/send/payment/destructive requests still require human approval.

## Loop Protection

Every bot-to-bot flow should carry:

- `thread_id`;
- `hop_count`;
- `max_hops`;
- `max_auto_turns`;
- cooldown per chat/thread/action.

Initial limits:

- `MAX_BOT_TO_BOT_HOPS = 3`;
- `MAX_AUTO_TURNS_PER_THREAD = 6`.

If the limit is exceeded, LocalOS logs the event and stops automatic replies.

## Agent Client Binding

Trusted Telegram bots should be bound to `agent_clients` through metadata:

- `telegram_bot_username`;
- `telegram_bot_id`;
- `allowed_transport = telegram`;
- scopes;
- status: `sandbox`, `live`, `suspended`.

Unknown Telegram bots can ask for a promotion or registration flow, but cannot run actions.

Binding can be managed in the Agent API admin UI. The backend also exposes:

- `POST /api/agent-api/clients/telegram-binding/lookup`

## Ledger

Bot-to-bot messages that request LocalOS work should be recorded in `agent_action_ledger` with:

- `transport = telegram`;
- sender type;
- Telegram bot username/id;
- chat id;
- message id;
- hop count;
- requested capability;
- risk level;
- approval id when needed.

## Telegram Alerts

Notify superadmin when:

- an unknown bot contacts LocalOS bot;
- a bot-to-bot hop limit is reached;
- a trusted bot requests high/critical action;
- a bot-to-bot message is denied by scope/status;
- a bot repeatedly fails authentication or tries to bypass approval.

## Implementation Steps

1. Add sender classification helper. Done in foundation.
2. Add `telegram_bot_username` / `telegram_bot_id` metadata to Agent API admin UI. Done.
3. In Telegram webhook/polling handlers, classify sender before intent routing. Done in foundation.
4. Ignore `localos_bot` self-messages. Done in foundation.
5. Deny `unknown_bot` automation and alert superadmin. Done for Telegram transport guardrails.
6. Bind trusted bots to `agent_clients`. Done through metadata.
7. Route trusted bot requests through scopes and `agent_action_ledger`. Partly done: transport events are logged; executable requests still require Agent API endpoints.
8. Add hop count and cooldown to bot-to-bot replies.
9. Add regression tests for unknown bot, trusted bot, self-message, hop limit.
10. Only after this, enable Telegram as an Agent API transport.
