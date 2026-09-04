# LocalOS Product Design Rules

## Role Of This Document

This is the design operating model for LocalOS product UI. It sits above individual component choices and below product strategy in `PRODUCT.md`.

Use it before editing dashboard, cockpit, builder, form, approval, run history, or agent-management screens.

## Product Surfaces Before Brand Surfaces

LocalOS has two different surface types:

- `Product surfaces`: dashboards, cockpits, forms, approvals, agents, workflows, ledgers, support tools.
- `Brand surfaces`: public pages, landing pages, articles, marketing explainers, public audit pages.

Product surfaces must be quiet, direct, and operational. They should prioritize scanning, comparison, and safe action over expressive visuals.

## Canonical Logo

Use the approved LocalOS logo from
`frontend/src/assets/images/logo.png` on every product and brand surface.
Do not recreate the mark with a generic icon, emoji, generated symbol, or an
icon-plus-text wordmark. Size and crop the existing asset for its context, but
do not redraw or substitute it.

## Canonical Public Background

The homepage and every `/growth` state — direction selection, direction detail,
personal preview, and result — belong to one public acquisition surface and
must use the same LocalOS background:

- warm off-white base `#f7f7f5`;
- a subtle `48px` slate grid;
- restrained orange and gold radial light near the top;
- decorative layers must remain non-interactive and hidden from assistive technology.

Reuse `frontend/src/components/PublicBrandBackdrop.tsx`. Do not recreate the
grid, change its spacing, or introduce a separate grey background for an
individual `/growth` route. Content cards remain solid enough to preserve text
contrast over the grid.

## Canonical Button Hierarchy

LocalOS buttons use one shared hierarchy across the product:

- product primary actions use the black `Button` default;
- public conversion actions use the gold `brand` variant, backed by
  `btn-iridescent`;
- secondary actions use `outline`, `secondary`, `ghost`, or a black button on
  a light brand surface when the composition requires it;
- flat rust/orange, blue, indigo, or purple must not be introduced as a local
  primary-button treatment;
- red is reserved for destructive actions, while green, amber, and blue remain
  semantic status colors rather than CTA colors;
- provider colors are allowed only where the provider identity itself matters,
  such as a Telegram sign-in control;
- disabled public conversion actions retain the brand gradient and communicate
  unavailability through opacity and state copy rather than changing hue.

Use `frontend/src/components/ui/button.tsx` instead of restyling primary buttons
screen by screen. Use `variant="brand"` for public conversion CTA and the default
variant for the dominant action inside the authenticated product.

## Public Growth Choice

The homepage pain-point section explains why owners use LocalOS. It is not a
second product taxonomy. The primary homepage CTA leads to one `/growth`
choice with six directions:

- clients: local creators, nearby businesses, and maps;
- ongoing work: content, average ticket, and automation.

Keep all six directions available on the first `/growth` screen. Do not label
this route as three opportunities or reduce the whole product to customer
acquisition.

## Subscription Preview

- A locked screen starts with one useful, truthful read-only fragment and only then shows a blurred continuation and one upgrade action.
- Influencer and partner previews contain at most 10 stable public records. Filters must not rotate that sample, and hidden records or contacts must never be sent to the browser.
- Blur is a conversion affordance, not an authorization boundary. Backend capability checks remain authoritative for every read and mutation.
- Upgrade copy names the minimum result-oriented tier: `Карты`, `Привлечение`, or `Управление`, and preserves the user's return route.

## Operating Principles

### Agents Are Employees, Not Workflows

For agents, the product model is "AI employees", not workflow automation.
The canonical contract is `docs/AGENTS_INTERFACE_MODEL_COMPILED_AI.md`.

The ordinary user layer must never be organized around backend entities such as
blueprint, runtime, capability, provider, execution, context, DSL, JSON,
active version, migration, legacy, credits, or raw logs.

Each agents screen must answer one user question and always make four answers
obvious:

- what the agent does;
- whether it is working;
- what happened last time;
- what the user should do now.

If the agent is healthy, the interface should become smaller, not more
detailed. Detail appears when there is a problem, a result to approve, or the
user opens a secondary/advanced layer.

### One Screen, One Dominant Job

Before implementation, write the screen job in one sentence. If a block does not serve that job, collapse it, move it to a detail layer, or remove it.

### First Layer Is Human Language

Primary UI copy must use user-facing language:

- "Telegram пока не подключён" instead of "capability не подключена".
- "Нужен доступ к Google Sheets перед записью" instead of "credentials required before provider executor can write".
- "Запись только после подтверждения" instead of "approved external write".
- "Проверить на примере" instead of "Preview run".

Technical terms are allowed in `Advanced`, support exports, raw traces, and developer-only panels.

### Progressive Disclosure

Show the minimum useful layer first:

- state;
- next action;
- why action is safe or blocked;
- what happens after the action.

Move raw payloads, capability maps, provider executor details, OpenClaw traces, and action ledgers behind tabs, details, drawers, or advanced sections.

### No Nested Cards By Default

Cards are for repeated items, modals, focused tools, and bounded summaries. Avoid cards inside cards unless the inner item is a true repeated record.

Use spacing, headings, rows, tabs, and dividers before adding another framed surface.

### Responsive Is A Product Requirement

On small and medium laptop widths:

- avoid permanent three-column layouts;
- avoid permanent right rails with dense technical blocks;
- keep one main working column where possible;
- move secondary panels into tabs, drawers, or details;
- keep the primary action visible without hunting.

### Density, Motion, Variance

For product dashboards:

- density: medium-high, but grouped and scannable;
- motion: low, only for loading/feedback;
- variance: moderate; use hierarchy, not decorative novelty.

Marketing pages may use more motion and visual variance, but product screens should stay operational.

### Interface Polish

After the screen job, state model, and main action are clear, polish the interface through small details:

- nested rounded surfaces must use concentric radius: outer radius = inner radius + padding;
- icons should be aligned optically, not only geometrically; icon buttons and text-with-icon buttons may need small padding corrections;
- use borders for separation and form/input affordance; use subtle layered shadows or ring-like shadows for elevation and depth where appropriate;
- interactive controls should have at least a `40x40px` hit area, ideally `44x44px`, without overlapping neighboring controls;
- dynamic dashboard numbers, counters, prices, timers, KPI columns, and changing totals must use tabular numbers;
- headings should use balanced wrapping where supported; short descriptions and card text should avoid orphan words where practical;
- images and previews should have a subtle inset outline so they stay readable on varied backgrounds;
- press feedback may use a restrained `scale(0.96)` on buttons where it does not distract from operational work.

## LocalOS UI Workflow

Use this six-step loop:

1. `audit`: name clutter, unclear copy, competing CTAs, hidden primary actions, and exposed internals.
2. `distill`: remove or collapse secondary content until the dominant job is clear.
3. `shape`: define layout, states, tabs, drawers, and responsive behavior.
4. `implement`: reuse existing primitives and code patterns.
5. `harden`: test empty, loading, error, long text, i18n, permission, and narrow viewport states.
6. `polish`: final copy, spacing, contrast, alignment, and screenshot pass.

For complex product screens, keep a small audit artifact in `docs/` that names
the screen job, first-layer answers, hidden technical layers, verification
evidence, and remaining hardening gaps. For the agents screen this artifact is
`docs/AGENTS_PRODUCT_UI_AUDIT.md`.

When a screen has a dedicated copy guard, run it with the other hardening
checks. For the agents screen:

```bash
scripts/ci_gate_product_ui.sh
```

## Detector Checklist

Before shipping product UI, check:

- The screen has one dominant job.
- The primary action is visible and named clearly.
- No technical internal term appears in the first layer unless the user needs it.
- No permanent three-column layout on narrow laptop widths.
- No nested cards unless the inner cards are repeated records.
- Status explains what to do next, not just a color.
- Approval states explain why the agent waits.
- Empty states explain the next step.
- Long Russian and English text does not overflow.
- Mobile and small laptop layouts are explicitly considered.
- Motion is quiet, interruptible, and tied to feedback or state change.
- CSS transitions specify exact properties instead of `transition: all`.
- `will-change` is used only for observed first-frame stutter, and only for compositor-friendly properties such as `transform`, `opacity`, or `filter`.
- Dynamic numbers use tabular numerals where layout shift would be visible.
- Small icon controls have a real hit area of at least `40x40px`.

## Agents UI Rules

Agents must be presented as AI employees.

`/dashboard/agents` should behave as:

- `Agents Home`: answer "What needs my attention today?"
- `My Employees`: answer "Which AI employees do I have?"
- `Agent Card`: answer "Is this employee working?"
- `Result Review`: answer "Do I agree to use this result?"
- `History`: answer "What did this employee do before?"
- `Settings`: answer "What can I change if I need to?"

Do not expose the workflow/debugger as the default mental model. Existing
cockpit-style UI is considered an intermediate implementation, not the final
target.

## Canonical Agent Tabs

Use these labels only as secondary navigation inside the employee model:

- `Обзор`
- `История`
- `Сценарий`
- `Настройки`

Advanced/debug surfaces must be gated or visually secondary.
