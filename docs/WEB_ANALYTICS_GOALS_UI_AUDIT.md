# Website analytics goals UI audit

Status: implemented beta. Route: `/dashboard/web-analytics`.

## User task

The owner wants to answer three questions: where visitors lose intent, which site changes affect results, and which campaigns produce confirmed business outcomes. Success means the owner can configure a measurable path without knowing the database model, see whether data is arriving, and identify the next external integration needed.

## Scenario structure

1. **Results** — funnel, CTA/form performance, confirmed outcomes, audience, campaigns, recommendations and a daily trend with change markers.
2. **Goals and page groups** — create a URL rule, preview it against observed paths, then configure a measurable outcome.
3. **Site changes** — record a change before or after publication; LocalOS also records configuration/key changes automatically.
4. **Integrations** — copy markup examples, rotate the conversion key with an explicit warning, and add campaign costs.

Each configured group and goal has a lifecycle state: draft, configured, receiving data, no data, disabled. Empty states explain the first useful action. Configuration deletion and key replacement require explicit confirmation.

## Data and state boundaries

- The screen reads tenant-scoped aggregate metrics and configuration from authenticated business routes.
- Public browser events contain no form values. Confirmed server events use a separate hashed bearer key and discard personal contact fields.
- Loading, empty, API error and no-data states remain visible; existing dashboard navigation and design-system primitives are preserved.

## Acceptance checks

- A first-time owner can preview a page-group rule before saving it.
- A goal cannot be enabled without its required stable identifier.
- CTA CTR and form success counts appear only from the explicit tracker events.
- CPA/ROI appear only when campaign costs and attributed confirmed outcomes exist.
- Automatic and manual change markers align to the daily trend.
- Key replacement warns that existing integrations will stop working.
- Controls remain keyboard reachable and use at least 40–44 px targets.

## Deferred

- Automated imports from advertising platforms, CRM, telephony and booking providers.
- Statistical significance calculations and experiment assignment.
- Translation of the new beta workspace beyond Russian UI copy.
