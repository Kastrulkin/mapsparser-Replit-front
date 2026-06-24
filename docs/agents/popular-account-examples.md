# Popular Agent Examples for Every Account

Status: `product canon / ready for seed implementation`

LocalOS should give every account a small gallery of practical agent examples so
the owner does not open an empty automation screen. These examples are not
active automations by default. They are starter drafts/templates that explain
what the agent can do, what data it needs, and where human approval is required.

## Product Rule

- Each account should see the same 10 popular examples unless a vertical-specific
  pack later overrides or reorders them.
- Examples should be presented as draft agents or one-click prompts, not as
  already running background jobs.
- External sends, map publications, spreadsheet writes, finance writes, mass
  actions and third-party actions stay behind preview and manual approval.
- If a connector is missing, the example remains visible and shows the exact
  missing connection instead of disappearing.
- The UI wording should describe the business result, not `capabilities`,
  provider internals, OpenClaw, or raw blueprint fields.

## The 10 Default Examples

| # | Example | User-facing prompt | Main data | Required connections | Approval boundary |
| --- | --- | --- | --- | --- | --- |
| 1 | Daily owner digest | Каждый день собирай короткий отчёт: что требует внимания по отзывам, новостям, услугам, партнёрствам и финансам, и присылай владельцу в Telegram. | business profile, audits, reviews, services, posts, finance, partnerships | Telegram | External message only after owner confirms the channel and first-run format. |
| 2 | New negative review reply | Если появился новый негативный отзыв, подготовь короткий ответ в стиле компании и пришли черновик владельцу в Telegram. | external reviews, business profile, services | Telegram | Draft only; publishing to maps is manual or separately approved. |
| 3 | Card posts from real signals | Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач. | services, reviews, content plan, business website | none required for draft mode | Publication to maps/social channels requires approval. |
| 4 | Service SEO cleanup | Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки. | services, audit profile, local search patterns | none | Applying service changes requires approval. |
| 5 | Partnership outreach draft | Найди или возьми из списка потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение. | partnership leads, services, business profile, location | optional email/Telegram for owner notification | Outreach sending is manual/approved. |
| 6 | Competitor website monitor | Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь короткий отчёт владельцу в Telegram. | competitor websites, services/menu, business profile | Browser use, Telegram | Browser run is supervised; Telegram send requires confirmation. |
| 7 | Google Sheets leads to Telegram | Проверяй Google Sheets с заявками или заказами и присылай новые строки ответственному в Telegram. | Google Sheets rows | Google Sheets, Telegram | External read/write settings must pass preflight; messages are controlled by limits. |
| 8 | WhatsApp and Telegram FAQ miner | Собирай повторяющиеся вопросы клиентов из WhatsApp и Telegram, группируй их и предлагай новые ответы для FAQ. | customer messages, customer questions, business profile | WhatsApp, Telegram where used | FAQ changes and customer replies require approval. |
| 9 | Finance import assistant | Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS. | Google Sheets or uploaded table, finance categories | Google Sheets or uploaded table | Finance entries are proposals until approved. |
| 10 | Tomorrow bookings check | Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up. | appointments, clients, services, payment status | optional Telegram | Customer contact and task creation require approval. |

## Account Placement

Recommended placement in the product:

1. Empty state on `/dashboard/agents`: show these examples as "Популярные
   сценарии" with one-click prompt fill.
2. Create-agent dialog: show the same examples as prompt chips.
3. Existing accounts: backfill as inactive example drafts only if this is done
   idempotently and does not create active agents or spend credits.
4. New accounts: attach the example pack during account onboarding or first open
   of the agents screen.

Implementation should store examples with stable keys so repeated backfills do
not duplicate them. Suggested key prefix: `popular_default_v1`.

## Seed/Backfill Acceptance Criteria

- Every business account can discover the 10 examples without asking support.
- No example is active by default.
- No credits are spent merely by showing examples.
- Creating a real agent from an example still goes through the normal create
  preview, connection preflight, approval, billing and audit path.
- Backfill is idempotent: rerunning it does not duplicate examples.
- Superadmin can distinguish an example draft from a user-created active agent.

## Backfill Command

Use the idempotent script for production or local PostgreSQL environments:

```bash
python scripts/seed_popular_agent_examples.py
python scripts/seed_popular_agent_examples.py --apply
python scripts/seed_popular_agent_examples.py --refresh-existing --apply
```

Default mode is dry-run. `--apply` writes missing examples. `--refresh-existing`
updates metadata for already seeded examples without creating duplicates and
keeps them disabled (`agent_blueprints.status = 'draft'`).
