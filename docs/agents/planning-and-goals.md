# Planning And Goal Loops

Status: `internal`

This page defines planning mode and goal-like loops for LocalOS agents. It does not replace human approval or the Ralph learning loop.

## Planning Mode

Planning mode is a runtime mode for ambiguous, risky, multi-step, or high-impact work.

Allowed in planning mode:

- read scoped LocalOS data;
- search approved sources;
- compare approaches;
- draft a plan;
- identify risks;
- estimate validation and rollback steps;
- ask a clarifying question.

Blocked in planning mode:

- external sends;
- publishing;
- payments or billing changes;
- destructive changes;
- credential changes;
- mass edits;
- external-system actions;
- production data mutation unless explicitly approved for the exact plan.

## Plan Artifact

For non-trivial agent work, store a plan artifact outside prompt context.

Recommended fields:

- objective;
- scope;
- assumptions;
- non-goals;
- risks;
- steps;
- required tools;
- approval points;
- validation;
- rollback or recovery;
- done condition.

Approval applies to the specific plan version. If scope or risk changes materially, request approval again.

## Execution After Approval

After a plan is approved:

1. Reattach the approved plan to the run state.
2. Execute one bounded step at a time.
3. Validate after each meaningful change.
4. Record observations and decisions.
5. Stop if risk increases, assumptions fail, or approval expires.

## Goal-Like Loop

A goal is a durable objective with a measurable done condition. Use it when an agent should keep making progress across multiple steps, batches, or sessions.

Recommended goal state:

```yaml
objective: ""
intent: operations | client_outreach | partnership_outreach
status: active | paused | completed | blocked | cancelled
scope: ""
done_condition: ""
budget:
  max_steps: 0
  max_tool_calls: 0
  max_cost: ""
  max_wall_time: ""
checkpoints:
  - ""
validation:
  - ""
forbidden_actions:
  - ""
approval_required_for:
  - ""
progress_log_ref: ""
```

Good goals are bounded. Bad goals are vague.

Bad:

```text
Improve outreach.
```

Good:

```text
Prepare 30 partnership leads for Moscow beauty salons, classify fit, draft offers, stop before any external send, and produce an approval-ready shortlist with reasons.
```

## Goal Loop Vs Ralph Loop

Goal-like loop and Ralph loop solve different problems.

| Loop | Purpose | Input | Output |
| --- | --- | --- | --- |
| Goal-like loop | Execute a bounded objective safely | objective, budget, checkpoints, validation | completed/blocked state plus evidence |
| Ralph loop | Learn from outcomes and edits | draft, final text, outcome, edited fields | improvement signals and metrics |

Use goal-like loop to control execution. Use Ralph loop to learn from human edits and real-world outcomes.

## Outreach Defaults

For supervised outreach and partnerships:

- goal must specify `intent`;
- shortlist approval comes before draft generation at scale;
- draft approval comes before any send batch;
- send batch is capped by policy;
- inbound reactions update outcome taxonomy;
- hard-no and unsubscribe signals stop further sends for that lead;
- delivery status is recorded before outcome analysis.

## Stop Conditions

Stop the goal when:

- done condition is met;
- budget is exhausted;
- approval is required;
- access is missing;
- data quality is insufficient;
- validation fails;
- policy denies the next action;
- user or operator cancels the goal.

The stop reason should be machine-readable and visible in the operator surface.
