# Operator work chat — 2026-10-09

Job: give a command, see real execution/results, and know the next safe action without leaving chat.

First layer: compact heading, selected task/result/actual credits, latest messages, docked composer. Search selector is a Tasks sheet; request history, help and feedback are separate dialogs. Sources, conditions and full task stages are secondary. No search/send logic or approvals changed.

Only selected task polls (3s active, 15s idle, focus refresh). Older messages keep their saved result and can select a task without independent polling. Failed refresh retains last data and permits retry. Raw candidate counts remain distinct from confirmed target; unknown costs stay unknown.

Follow latest messages by default. Reading history pauses follow; new-message indicator and explicit jump restore it. Context changes reset following and close secondary panels.

Verification: production-source build and asset integrity pass. Three targeted tests cover safe attention/billing actions and scrolling/context transitions. Global tsc has 237 pre-existing errors; normalized baseline/current diagnostics have no new errors. Browser acceptance uses existing data only: no sends or paid searches.

Release preserves production photos/business links and current sidebar. GitHub receives only the UI changes on the existing outreach branch, preserving its own voice recovery behavior. Production and GitHub had pre-existing source differences; unrelated work is not committed or reverted.

Residual checks: native mobile keyboard and real voice recognition require a device/session with microphone permission. Existing search availability is independent of this interface change.
