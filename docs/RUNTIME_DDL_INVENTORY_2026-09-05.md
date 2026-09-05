# Runtime DDL inventory

The average-ticket tables are fully represented by Alembic revision
`20260515_001`; request handlers no longer create them. Sales-room tables used
by partnership analytics are represented by revisions `20260617_002`,
`20260618_001`, `20260629_001`, and later sales-room extensions; the analytics
read path no longer calls the legacy schema bootstrap.

The remaining runtime DDL is intentionally not removed in this change:

- `src/api/prospecting/access_schema.py`: legacy bootstrap functions for manual
  CRM, partner-card, and sales-room compatibility. They have several write and
  public-route callers, so each needs schema parity and endpoint coverage before
  removal.
- legacy SQLite migration/init scripts and `src/ai_agents_api.py`: outside the
  PostgreSQL request paths changed here.
- `src/core/action_orchestrator.py`, `src/core/card_automation.py` and
  `src/core/growth_schema.py` still contain schema bootstrap operations in
  active subsystems. Their callers, table/index parity and deployment order
  have not been fully migrated in this release. The list above is a targeted
  inventory, not proof that all request-path DDL has been removed.

Future B1 work should migrate one named bootstrap at a time, add an Alembic
revision first, then replace the call with an actionable schema-readiness error
or remove it once deployment migration is mandatory.
