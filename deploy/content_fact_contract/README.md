# Scoped content fact contract release — 12 October 2026

This release fixes writer/validator fact drift without replacing the older Git
tree with a production snapshot. The production module contains newer content
features that are absent from that tree. `release_functions.py` is a reviewed
patch asset, not an alternate runtime or sender.

The installer replaces seven named functions and one pattern tuple, inserts five
helpers and changes one generation call site. It verifies the complete inspected
source hash and checks that unrelated top-level AST nodes stay identical.
Frontend, menu, business switching, Compose, DB records/schema, provider routes,
model settings, delivery receipts and schedules are not modified.

Expected input SHA256:
`b591db1b5d99048afb7bfbefcb193651d0e4edf6b1b12de88581bdab4001c07d`

Expected installed SHA256:
`531b15407dcef125dbc6de6ad746386dd5bf38fec509d7c3fe830fad2f8bd256`

Changes: shared provenance-bearing fact snapshot, service descriptions and
address visible to both writer and validator, automatic JSON fence removal,
non-blocking creative warnings, no diploma-specific prohibition. This does not
claim comprehensive semantic fact checking; known IDs alone do not prove every
sentence. No new paid generation is part of rollout.

Verification: seven pure local regression tests and a PostgreSQL read-only check
of real service provenance, address/diploma, unknown source/price and JSON handling.
The read-only smoke never invokes a provider, writes a post or sends a message.

Install from `/opt/seo-app` using `install.py --apply`; the guarded installer saves
the previous module under `backups/content-facts-<UTC>/`. Import-check the live
`/app/src/services/content_plan_service.py`, then restart only app, worker and
operator-worker in tmux. Recheck containers, logs, HTTP and the read-only smoke.

Rollback: after confirming the live hash is the installed hash, restore only the
backed-up `content_plan_service.py` and restart those same affected services.
Do not reset the production tree or modify receipts, schedules or other files.
