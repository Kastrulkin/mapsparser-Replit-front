# Telegram Control UI Audit

## Screen job

Help an owner, network manager, or superadmin see what LocalOS has already found, understand the one most important next decision, and safely continue the work in the correct business scope.

## First layer

- selected business, network, or platform;
- calm background-work status;
- one primary attention item and action;
- up to four secondary items;
- source and observation time for every metric.

The single-business owner does not see the words `scope` or `context`. The switcher appears only when there is a real choice.

## Progressive disclosure

- business/network/platform search lives in the switcher;
- secondary metrics and actions follow the primary task;
- detailed tables, filters, imports, editors, and bulk review open in the dashboard/Mini App continuation;
- diagnostics stay outside the ordinary summary.

## Safety states

- every callback and Mini App selection is resolved again on the server;
- a callback business target must match the selected business;
- aggregate scopes cannot silently run a single-business mutation;
- external, paid, destructive, and bulk operations keep their existing preview and approval boundaries.

## Motion and feedback

- staged copy explains loading instead of showing an unexplained spinner;
- scope switching has a short, stable transition so the user sees LocalOS rebuild the summary;
- pulse and ping motion is limited to working/background states and respects reduced-motion preferences;
- buttons keep a stable 44–48 px hit area and restrained press feedback.

## Verification

- production frontend build;
- focused resolver, Telegram signature, source/freshness, and role-default tests;
- mobile browser pass at the Mini App route;
- Python syntax compilation for bot, API, summaries, digest, and migration.

## Dashboard continuation

The Mini App validates Telegram `initData` and receives a one-day LocalOS web session for dashboard continuations. Search requests do not mint extra sessions. Dashboard APIs still repeat their normal access checks, so this bridge does not bypass tenant or superadmin rules.
