# LocalOS Compiled AI Envelope Over OpenClaw v1

Дата: 11 июня 2026
Статус: canonical product/runtime direction

## Цель

LocalOS не должен становиться вторым OpenClaw. LocalOS должен дать пользователям
свободу OpenClaw внутри продуктовой, финансовой и безопасной рамки LocalOS:

```text
user intent
  -> OpenClaw/LLM planner asks clarifying questions and proposes tools
  -> LocalOS compiler freezes the workflow as DSL
  -> LocalOS validates capabilities, connectors, approvals, limits and billing
  -> OpenClaw executes only scoped allowed actions
  -> LocalOS stores runs, artifacts, approvals, ledger, cost and learning history
```

## Ownership

| Layer | Owner | Rule |
| --- | --- | --- |
| Tool/runtime engine | OpenClaw | Reuse existing planning, tool schemas, connector intelligence and action execution where available. |
| Product object | LocalOS | User sees LocalOS Agent, not raw OpenClaw. |
| Runtime truth | LocalOS | Saved `agent_blueprint_versions` workflow is the executable contract. |
| Policy envelope | LocalOS | Tenant boundary, subscription, credits, limits, approvals, audit and forbidden actions. |
| Business data | LocalOS | Business ownership and data scopes are checked before planner or runtime access. |

Do not reimplement OpenClaw capabilities manually when OpenClaw already exposes
the action and schema. Import or map them into LocalOS capabilities, then apply
the LocalOS policy envelope.

## Capability Intelligence

OpenClaw can be used as a capability intelligence provider. LocalOS normalizes
OpenClaw actions into:

```text
openclaw_action_ref
localos_capability
service
risk_class
required_auth
approval_class
status
provider_candidates
provider_paths
```

Catalog source order:

1. `OPENCLAW_CAPABILITY_CATALOG_URL`, when explicitly configured.
2. `OPENCLAW_BASE_URL + /api/openclaw/capabilities/catalog`.
3. Local static fallback catalog, only when OpenClaw is not configured or the
   catalog request fails.

Auth header for the live catalog is `X-OpenClaw-Token`, sourced from
`OPENCLAW_LOCALOS_TOKEN` or `OPENCLAW_TOKEN`.

The live OpenClaw catalog may expose either an `actions[]` payload or the current
LocalOS/OpenClaw `capabilities{}` payload. LocalOS must normalize both shapes
into the same envelope contract before builder, compiler, feasibility or runtime
code can use them.

The normalized catalog must preserve provider paths. A capability is not only
"supported" or "unsupported"; it may be supported through OpenClaw, native
LocalOS, Maton.ai, a future Composio connector or a manual/draft-only fallback.
The builder/planner loop must surface these paths so the UI can explain whether
the next step is "use existing connection", "connect Maton", "connect Telegram",
"planned via Composio later" or "not possible in LocalOS".

Examples:

```text
openclaw.google_sheets.read_rows
  -> localos: google_sheets.read_rows
  -> risk: read
  -> auth: google_sheets
```

```text
openclaw.telegram.publish_message
  -> localos: communications.send_offer / communications.send_reminder
  -> risk: external_publish
  -> approval: required
  -> auth: telegram
```

```text
unauthorized_external_system_access
  -> localos: forbidden
  -> reason: no approved provider and unsafe target
```

## Feasibility Contract

Before an agent is created, activated or run, LocalOS resolves feasibility:

```text
requested intent/capabilities
+ OpenClaw capability catalog
+ LocalOS native capability registry
+ Maton/Composio/manual provider candidates
+ business connection inventory
+ subscription and balance
+ approval rules
= feasibility result
```

Statuses:

- `ready` — all required capabilities and bindings are available.
- `needs_connection` — supported, but the business must connect a provider.
- `needs_choice` — multiple existing connections can satisfy the binding.
- `needs_clarification` — planner needs details before compilation.
- `needs_approval` — workflow can be compiled but human gate must be configured or approved.
- `needs_payment` — plan or credit balance blocks activation/runtime.
- `unsupported` — no supported provider path exists.
- `forbidden` — LocalOS policy rejects the request.

## Builder Session Rule

OpenClaw may ask clarifying questions, but only inside the LocalOS envelope. The
builder prompt/context sent to OpenClaw must include:

- allowed capabilities;
- forbidden action classes;
- available and missing connectors;
- subscription and credit limits;
- business context and ownership scope;
- approval requirements;
- output contract for structured workflow draft.

LocalOS stores this as `localos_openclaw_planner_context_v1` in the builder
preview. That context is the only supported input envelope for an OpenClaw
clarifying/planning loop. It tells OpenClaw what it may reason about, which
connectors are already available, which connectors are missing, which action
classes are forbidden and which action classes require approval.

The builder should also produce `localos_openclaw_planner_loop_v1`. This is a
design-time-only planner result derived from the OpenClaw capability catalog and
the LocalOS envelope. It may propose clarifying questions, connector choices and
OpenClaw action references, but it must keep `may_execute_tools = false` and
`must_compile_in_localos = true`.

The loop also carries `localos_openclaw_planner_contract_v1`. This is the
actual handoff contract for a future live OpenClaw planning call:

- OpenClaw may clarify and propose workflow drafts only;
- tool execution and external side effects are forbidden at builder time;
- action references are returned as references, not executed actions;
- the response must be JSON with clarifying questions, workflow draft,
  required connectors, capability plan, approval points and unsupported
  requests;
- LocalOS remains the owner of compilation, validation, activation, billing,
  approvals and runtime execution policy.

When AI compilation is enabled, LocalOS first builds a deterministic draft and
feasibility preview, then calls the AI/OpenClaw planner with this envelope. The
planner response is treated as a design-time proposal only. LocalOS sanitizes
the proposal against the compiler registry, recompiles it into a blueprint
version payload, runs compiled workflow validation and keeps
`agent_blueprint_versions.steps_json` as runtime truth.

OpenClaw can propose a workflow. LocalOS must still compile, validate and store
the workflow before activation.

## Activation Gate

An agent can be active only when:

- compiled workflow validation passed;
- required connector preflight is ready;
- LocalOS policy allows every capability;
- subscription and credits allow the planned usage;
- approval policy exists for external sends, publishes, payments, destructive
  changes and mass operations.

Draft agents may exist without connections. Scheduled or external side-effect
agents may not run without the required gates.

## Builder Setup Flow

The builder preview must include `localos_agent_builder_setup_flow_v1`. This is
the product-facing state machine for agent creation:

- `needs_clarification` — ask the next missing question before creating a draft.
- `needs_connection` — draft can be created, activation waits for connectors.
- `needs_choice` — draft can be created, activation waits for a selected
  existing connector.
- `blocked` — forbidden or unsupported request; no draft should be created.
- `ready_for_draft` — LocalOS can create the draft compiled agent.

The API must reject draft creation when `can_create_draft` is false. The UI must
show the same next action instead of leaving the user to interpret raw workflow
details.

Connector actions in the builder are pre-draft guidance, not credential writes.
Before a blueprint exists, LocalOS may show `connect_after_draft` or
`choose_existing` actions. After draft creation, the UI must open the agent
connections workspace and use the blueprint integration endpoints to attach or
configure Google Sheets, Telegram, Maton or native LocalOS destinations.

Draft creation responses should include
`localos_agent_post_create_handoff_v1`. This tells the UI which workspace to
open next, which bindings are still missing and whether the user should connect
sources, review settings or run a preview. This keeps the handoff from free-form
builder chat to the product cockpit explicit and measurable.

After connectors are configured, the UI should run the blueprint preflight and
read `localos_agent_preview_run_gate_v1`. Preview run is allowed only when
preflight is ready. The gate must keep `external_side_effects_allowed = false`;
any external send, publish, payment or destructive write still requires the
compiled workflow approval policy and runtime gate.

Agent detail responses should include `localos_agent_activation_gate_v1`. This
is a read-only cockpit summary of the same checks enforced by the activation
endpoint: compiled validation, connector preflight and approval policy. The UI
may show an activation CTA only when `can_activate = true`; otherwise it must
show the exact blockers and route the user to logic or connections.

## Forbidden Examples

LocalOS must reject:

- access to third-party computers or private systems without an approved
  connector/provider path;
- credential extraction;
- autonomous external publish/send/payment without approval;
- attempts to bypass subscription or billing limits;
- cross-business data access.

## MVP Acceptance Scenario

User intent:

```text
Каждый вторник возьми один заказ за предыдущий день из Google Sheets и подготовь
пост в Telegram.
```

Expected behavior:

1. Builder asks for missing details: sheet, tab, date/order columns, Telegram
   destination and approval owner.
2. Feasibility says Google Sheets and Telegram are required.
3. Existing connections are offered for reuse; missing connections block
   activation.
4. LocalOS compiles a workflow with OpenClaw action references behind LocalOS
   capabilities.
5. Preview can create a draft and approval request.
6. No publish happens without human approval.
7. Run detail shows steps, artifacts, OpenClaw action trace, cost and outcome.

## Workflow Step Contract

Compiled workflow steps may store an OpenClaw action reference, but the LocalOS
capability remains the permission boundary:

```json
{
  "type": "capability",
  "capability": "google_sheets.read_rows",
  "provider": "openclaw",
  "provider_action_ref": "openclaw.google_sheets.read_rows",
  "provider_policy": "localos_envelope"
}
```

Validation must reject any step where `provider_action_ref` does not map back to
the declared LocalOS capability. OpenClaw action refs are execution hints inside
the envelope, not independent authority to run arbitrary tools.
