# Evidence Bundle: telegram-bot-phase1

## Summary
- Overall status: PASS
- Last updated: 2026-04-21T17:30:00+03:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `src/telegram_bot.py`: `/start` for unbound users now shows `_guest_welcome_text()` and `_build_guest_menu()` instead of bind-only instructions.
  - `src/telegram_bot.py`: guest callback handlers added for `guest_audit_start`, `guest_compare_start`, `guest_about`, `guest_bind_help`.
  - `src/telegram_bot.py`: free-text handler for unbound users now attempts quick audit intake via `_request_public_report_from_telegram(...)`.
- Gaps:
  - Compare-with-competitor flow is still a placeholder in this phase.

### AC2
- Status: PASS
- Proof:
  - `src/services/telegram_lead_intake.py`: added URL extraction, normalization, source classification, and user-friendly validation messages.
  - local unit smoke proved supported URLs return `ok=True`, while unsupported URLs return a readable error.
  - `src/telegram_bot.py`: `_request_public_report_from_telegram(...)` now requires exactly one valid normalized card URL before calling public audit API.
- Gaps:
  - No automated test suite exists yet for link-intake edge cases beyond targeted smoke checks.

### AC3
- Status: PASS
- Proof:
  - `src/telegram_bot.py`: bound-user main menu now contains `🤝 Поиск партнёрств` and `✨ Что автоматизировать?`.
  - `src/telegram_bot.py`: added `/partnerships` and `/feature_request` commands plus callback/state-machine flow for category selection and free-text submission.
  - `src/services/bot_feature_requests.py` and `alembic_migrations/versions/20260421_add_bot_feature_requests.py`: request flow persists into new `botfeaturerequests` table.
- Gaps:
  - Admin/UI surface for browsing feature requests is not added in this phase.

### AC4
- Status: PASS
- Proof:
  - production DB backup created before schema change: `data/backups/postgres/local_20260421_172148.sql.gz`
  - production app/worker redeployed and verified with `docker compose ps` + `curl -I http://localhost:8000`
  - production Alembic revision is `20260421_001`
  - production table check returns `botfeaturerequests`
  - runtime bot source on server contains new markers: `guest_audit_start`, `menu_feature_request`, `menu_partnerships`
  - server runtime venv successfully imports guest helpers and link parser from updated `src/telegram_bot.py`
- Gaps:
  - Telegram polling process still cannot complete `getMe()` because the VPS cannot reach Telegram API; this is an external network blocker, not a code-loading failure.

## Commands run
- `PYTHONPATH=src python3 -m py_compile src/telegram_bot.py src/services/telegram_lead_intake.py src/services/bot_feature_requests.py`
- `PYTHONPATH=src python3 - <<'PY' ... parse_map_links_from_text(...) ... PY`
- `ssh root@80.78.242.105 'cd /opt/seo-app && bash scripts/postgres-backup.sh'`
- `scp ... src/telegram_bot.py src/services/telegram_lead_intake.py src/services/bot_feature_requests.py alembic_migrations/versions/20260421_add_bot_feature_requests.py root@80.78.242.105:/tmp/tgphase1/`
- `ssh root@80.78.242.105 'cd /opt/seo-app && docker compose up -d app worker'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && curl -I http://localhost:8000'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && docker compose exec -T postgres psql -U beautybot -d local -c "SELECT version_num FROM alembic_version;"'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && docker compose exec -T postgres psql -U beautybot -d local -c "SELECT to_regclass(''public.botfeaturerequests'');"'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && PYTHONPATH=/opt/seo-app:/opt/seo-app/src runtime_bot/.venv/bin/python - <<'\"'\"'PY'\"'\"' ... PY'`
- `ssh root@80.78.242.105 'cd /opt/seo-app && tail -n 120 runtime_bot/telegram_bot.log'`

## Raw artifacts
- .agent/tasks/telegram-bot-phase1/raw/build.txt
- .agent/tasks/telegram-bot-phase1/raw/test-unit.txt
- .agent/tasks/telegram-bot-phase1/raw/test-integration.txt
- .agent/tasks/telegram-bot-phase1/raw/lint.txt
- .agent/tasks/telegram-bot-phase1/raw/screenshot-1.png

## Known gaps
- `compare with competitor` is intentionally deferred to the next Telegram phase.
- The Telegram bot process still cannot talk to Telegram API from the current VPS; VPN/proxy or separate bot relay is still required for live polling/send functionality.
