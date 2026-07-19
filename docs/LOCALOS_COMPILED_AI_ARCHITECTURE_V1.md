# LocalOS Compiled AI Architecture v1

Обновлено: 19 июля 2026
Статус: canonical implementation and rollout contract for LocalOS Compiled AI v1

## Цель

LocalOS Compiled AI превращает человеческое описание агента в проверенный
исполняемый workflow. ИИ может использоваться на этапе проектирования, но
runtime truth остается deterministic: сохраненная версия blueprint, capability
allowlist, approval policy, connector bindings, limits and audit trail.

## Pipeline

```text
User intent
  -> design-time compiler
  -> workflow DSL
  -> compiled artifact candidate
  -> validation
  -> connector preflight
  -> activation
  -> deterministic runs
```

## Workflow DSL

Source: `src/services/agent_workflow_dsl.py`.

Schema: `localos_agent_workflow_dsl_v1`.

Required contract:

- `goal` — что должен сделать агент;
- `trigger` — ручной запуск, расписание или external event;
- `inputs_schema` — входные данные;
- `steps` — ordered `artifact`, `approval` and `capability` steps;
- `capability_allowlist` — разрешенные действия;
- `approval_policy` — human gates;
- `required_integration_bindings` — нужные подключения;
- `limits` — caps and autonomy boundaries;
- `output_schema` — expected result.

## Compiled Artifact Candidate

Source: `src/services/agent_compiled_artifact.py`.

Schema: `localos_compiled_artifact_candidate_v1`.

The candidate is stored in blueprint metadata as a control-plane snapshot:

- `dsl` — normalized workflow DSL;
- `validation` — current validation result;
- `runtime_truth` — always the blueprint version row;
- `runtime_llm_required` — must be false for deterministic compiled workflows;
- `activation_gate` — validation + connector preflight requirements.

The candidate is not a second runtime source of truth. Runtime still reads
`agent_blueprint_versions.steps_json`, `capability_allowlist_json`,
`approval_policy_json`, `inputs_schema_json` and `output_schema_json`.

## Validation v1

Validation rejects workflows when:

- required DSL fields are missing;
- step keys are missing or duplicated;
- step type is outside `artifact`, `capability`, `approval`;
- a capability step is absent from `capability_allowlist`;
- write capability does not require approval;
- connector binding references a capability outside the allowlist;
- autonomous write flags are enabled.

Activation must pass both:

1. compiled workflow validation;
2. integration preflight.

## Compiler Registry

Source: `src/services/agent_compiler_registry.py`.

The design-time LLM is not allowed to invent arbitrary runtime actions. It
selects from a registry of compiled templates and capabilities:

- source/destination templates such as `google_sheets_to_localos_finance` and
  `telegram_to_google_sheets`;
- communication templates from `communication_agent_templates`;
- allowed capabilities from the provider/capability map;
- allowed business-facing connectors from the integration catalog.

`agent_compiler_llm.py` includes this registry in the prompt and sanitizes the
model output against it. If a model returns only `compiled_template_key`,
LocalOS fills source, destination, trigger, capabilities, connectors and
approval reasons from the registry. Unknown capabilities are dropped before a
blueprint is created.

## First Reference Template

The first full compiled template is:

```text
Google Sheets -> LocalOS Finance
```

Contract:

- trigger: `schedule.daily`;
- source capability: `google_sheets.read_rows`;
- destination capability: `finance.transaction.create`;
- approval: `finance_transaction_import`;
- limits: no autonomous LocalOS write;
- output: finance preview, rows requiring review, errors and outcome artifact.

This template proves the core model: the compiler may use AI once to understand
intent, but the resulting runtime is a saved, validated, approval-gated workflow.

## Product And Version Model

LocalOS exposes one user-facing product: `Agents`. A simple natural-language
builder is not a second runtime. It creates an `AgentBlueprint`, and the saved
blueprint version remains the executable truth.

- `AIAgents`: persona, voice and legacy chat configuration only;
- `agent_blueprints`: lifecycle and ownership;
- `agent_blueprint_versions`: candidate and active workflow versions;
- `agent_runs`: one preview or working execution;
- `agent_run_steps`: durable step journal;
- `agent_artifacts`: outputs tied to an exact run;
- `agent_approvals`: human decisions tied to an exact run;
- `ActionOrchestrator`: policy, approval, billing and external-action boundary.

Preview uses the candidate version. `manual` and `scheduled` working runs use
only the explicitly active version. A successful candidate preview is required
before activation. Rollback selects an earlier tested version and does not
launch a run or change schedule settings.

Execution modes are explicit metadata, not title inference:

| Mode | Meaning | Working version |
| --- | --- | --- |
| `one_off` | no automatic launch; may be rerun with new parameters | candidate |
| `manual` | reusable owner-launched agent | active |
| `scheduled` | active agent launched at confirmed local time | active |

Legacy blueprints without a confirmed mode remain safe drafts. Preview is
allowed, but working and automatic launches are blocked until confirmation.

## Run Input Contract

Source: `src/services/agent_run_contract.py`.

The UI builds run parameters from the selected version's
`inputs_schema_json`. Supported public fields include string, multiline text,
number, integer, boolean, enum, date, time, date-time and string arrays.

Reserved service fields such as `business_id`, `tenant_id`, `preview_mode`,
provider bindings, policy and trace context are never accepted as user-defined
parameters. Backend validation applies the same public schema before a run is
created. `content_plan.item.create_draft` additionally requires a future
`scheduled_for` date.

## Durable Run Runtime

Source: `src/services/agent_run_queue.py` and `src/worker.py`.

For businesses admitted by `AGENT_ASYNC_RUNS_ENABLED` and
`AGENT_BETA_BUSINESS_IDS`:

1. `POST /api/agent-blueprints/<id>/runs` validates mode, version, inputs and
   connections.
2. The client-supplied `idempotency_key` is locked and deduplicated per
   business and blueprint.
3. A production run reserves credits and is stored as `queued`; preview has no
   reservation.
4. Worker claims runs with `FOR UPDATE SKIP LOCKED` and moves them through
   `queued -> running -> completed | waiting_approval | retry_wait | failed`.
5. A stale heartbeat after five minutes schedules recovery; transient failures
   retry at most three attempts.
6. Completed steps and idempotent artifacts are reused rather than recreated.
7. `GET /api/agent-runs/<id>` is the polling and recovery contract for the UI.

The synchronous runner remains a compatibility fallback outside the admitted
cohort. It is not the target production runtime.

## Billing Contract

Source: `src/services/agent_run_billing.py`.

- preview: free, while token usage may still be recorded;
- production run: reserve 2 credits before enqueue;
- settlement: 1 credit per started 1,000 recorded tokens;
- beta charge is capped by the reservation;
- unused credits are released on completion;
- failed, rejected or superseded runs release the reservation;
- excess calculated cost is stored as `unbilled_overage` for calibration;
- the same idempotency key cannot create a second reservation.

## Business Result And Approval Contract

The result shown to the user is selected for the exact run in this order:

1. `agent_final_result` for a completed run;
2. `agent_output_draft` for a waiting run;
3. approval payload only when `approval.run_id` matches the current run.

API detail exposes normalized `business_result`, `result_state`,
`current_approval` and, for scheduled agents, `next_run_at`. Starting a newer
test supersedes stale pending approvals and unfinished obsolete runs for the
same blueprint.

Preview never performs an external action and must not create internal-write
artifacts such as a content-plan item. A working run may create an idempotent
internal draft. Publication, external send, payment, destructive mutation and
third-party action remain behind a separate approval.

## Certified Capability Boundary

Source: `src/services/agent_capability_handlers.py`.

The catalog exposes `runtime_status` and `beta_enabled`. The compiler may mark a
workflow ready for the beta only when every required capability is certified.

Current `beta_enabled=true` capabilities:

- `google_sheets.read_rows`;
- `reviews.reply.draft`;
- `services.optimize`;
- `news.generate`;
- `content_plan.item.create_draft`;
- `appointments.read`;
- `communications.draft`;
- `support.export`;
- `partnership.audit_card`;
- `partnership.match_services`;
- `partnership.draft_offer`.

External sends, publish requests, spreadsheet writes, finance writes and
billing mutations are `request_only` or `manual_only` and are not eligible as
autonomous beta workflow capabilities. Unknown or unsupported mandatory intent
must be returned as `unsupported_requirements`, not silently omitted.

## HTTP Contract

The canonical surface remains route-compatible:

- `POST /api/agent-blueprints/draft`;
- `GET|POST /api/agent-blueprints`;
- `GET /api/agent-blueprints/<id>`;
- `POST /api/agent-blueprints/<id>/execution-mode`;
- `GET|POST /api/agent-blueprints/<id>/integrations`;
- `POST /api/agent-blueprints/<id>/preflight`;
- `POST /api/agent-blueprints/<id>/runs`;
- `GET /api/agent-runs/<id>`;
- version diff, activate and rollback endpoints;
- run approval, feedback and support-export endpoints.

Async enqueue returns `202`; an idempotent replay returns the existing run with
`reused=true`; a different key while another run is active returns
`409 AGENT_RUN_ALREADY_IN_PROGRESS`.

Blueprint detail also returns the computed `execution_contract`. It presents
the original request, candidate and active goals, public inputs, ordered saved
steps, expected result, schedule and approval boundaries without introducing a
second runtime representation. Run detail returns `progress`, derived from the
version steps and durable `agent_run_steps`: queue state, completed count and
the current step. These fields drive the user-facing Scenario and execution
views; keyword inference is only a marked legacy fallback.

## Archive And Lifecycle Learning

`DELETE /api/agent-blueprints/<id>` is a soft archive, not physical deletion.
Versions, runs, results and audit history remain available for support and
product learning; pending approvals and queued work are superseded. A running
task must finish before the blueprint can be archived.

The archive event records a user-selected reason and a server-derived result
state: `without_result`, `test_result_only` or `with_work_result`. The server
derives this state from production runs and result artifacts, so the learning
signal does not depend on a frontend label or the currently selected run.

## Scheduler Boundary

Scheduled execution uses the same active version, preflight, queue, billing and
approval path. Dedupe key includes blueprint, local date and local time. An IANA
timezone is mandatory before activation.

The scheduler scans every active blueprint with an explicitly confirmed
`execution_mode=scheduled`; it no longer restricts dispatch by blueprint
category. Before dispatch, every capability in the active version must have
`beta_enabled=true`.

`AGENT_SCHEDULE_DISPATCH_ENABLED` is a deployment gate, not proof of a working
customer schedule. As verified on 19 July 2026, the flag is enabled in
production, but there is no active confirmed scheduled blueprint and no saved
scheduler event. Scheduled mode is therefore implemented but not yet
production-proven.

## Current Rollout Status

| Layer | Status |
| --- | --- |
| Builder -> DSL -> compiled candidate -> validation | implemented |
| Explicit `one_off` / `manual` / `scheduled` mode | implemented |
| Candidate preview and active version separation | implemented |
| Typed run parameters and backend validation | implemented |
| Google Sheets read and normalized business result | implemented/beta |
| Content-plan draft internal write | implemented/beta |
| Idempotent async queue, heartbeat and retry | implemented/cohort beta |
| Production run reservation and settlement | implemented/cohort beta |
| Version diff, activation and rollback | implemented |
| Scenario contract and server-driven run progress | implemented |
| Scheduler dispatch | implemented, production canary missing |
| Certified provider E2E matrix | partial |
| Mass legacy mode migration | not completed |
| Mass self-service rollout | not approved |

Production currently admits three businesses to the async beta. Existing
starter drafts are not activated automatically. The launch gate remains:
provider E2E, tenant-isolation regression coverage, a successful scheduled
canary and explicit owner activation.

## Verification

Canonical local path:

```bash
scripts/test_agent_blueprints.sh
scripts/ci_gate_product_ui.sh
npm --prefix frontend run build
```

Architecture-independent Docker path:

```bash
scripts/test_agents_docker.sh
```

Reference provider smoke:

```bash
PYTHONPATH=/app/src BUSINESS_ID=<business_id> \
  python scripts/smoke_google_sheets_reference_agent.py
```
