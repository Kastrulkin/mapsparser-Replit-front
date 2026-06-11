# LocalOS Compiled AI Architecture v1

Дата: 11 июня 2026
Статус: canonical implementation note for LocalOS agent compiler v1

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
