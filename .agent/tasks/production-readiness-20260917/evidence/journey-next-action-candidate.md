# Next-action state retention: candidate, not reproduced

Read-only next-lane trace during the locale package, parent7c080d11. Independent
social_role_readmission_fix and root both read relevant source. No test or source
repair is claimed by this note. Keep it separate from UX-LOCALE-07.

JourneyActionCard initializes draftText/outcome/schedule/details only at mount,
but execute uses current action/id/version and current entity_id. Unkeyed
JourneyWorkspaceFocus:54–61 replaces action with a successful command's nextAction;
TelegramControlWorkspace:761–762 does likewise. These are supported transitions,
not arbitrary DB edits. Some list callers instead key by action.id and remount.

lead_journey_service.py:1054–1076 defines content review → schedule → publication
→ result → next cycle → prepare → new review. start_next_content_cycle removes
draft_text/scheduled_for/publication_url from persisted payload. execute_command
creates the next action at1411–1418, carrying the same entity through this path.
The retained React draft may therefore survive a new content cycle even where
the backend deliberately removed it. Root checked those branches. Cross-entity
or cross-business write is NOT proven; business-scoped action loading rejects
the wrong business. Today replacing the first action after reload is a second
source candidate, not a measured ordering outcome.

Proposed causal check: edit review A, advance through supported action types to
a new review B with same entity and cleared draft payload, then verify displayed
and submitted draft no longer comes from A. Positive: same action/context rerender
and locale changes preserve an in-progress edit. Also test late resolve/reject
after context change before designing any reset/lifetime fence. Do not assume
version changes mean discard; establish the supported refresh/edit contract.
