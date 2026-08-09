# Growth loop UI audit

## User job

The owner needs to understand whether LocalOS has enough current business data, see one useful next step, and add statistics without turning LocalOS into another CRM.

## First layer

- one stable priority shared by Progress and the Telegram Mini App;
- source and freshness of the financial data behind recommendations;
- a factual weekly rhythm, derived from confirmed data rather than visits or points;
- a direct file-import path for YCLIENTS;
- a saved request for another CRM.

## Secondary layer

- import mapping and preview;
- thresholds, transaction history, and detailed finance tools;
- technical event IDs and analytics storage.

## Safety and evidence

- imports keep their existing preview and final confirmation;
- CRM requests are scope-checked and deduplicated;
- product events are allowlisted and never block an operational action;
- no publication, payment, provider write, or destructive action was added;
- freshness uses source timestamps, never the API response time.

## Verification

- backend contract, access, telemetry, CRM request, overview, and import tests;
- Mini App component tests for growth state and CRM request states;
- dashboard Progress localization test;
- production frontend build.

## Deliberately deferred

- automatic CRM connectors beyond the existing supported adapters;
- server-persisted completion state for missions that are not yet backed by a canonical domain event;
- a dedicated web `Today` route (the shared loop is currently exposed in Progress and Finance);
- source-level freshness breakdown for every location of a network.
