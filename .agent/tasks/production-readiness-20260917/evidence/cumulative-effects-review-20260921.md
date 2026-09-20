# Cumulative effects-path source review — 2026-09-21

## Scope and method

Read-only source/contract review of the exact cumulative range
`30262a5bf7b468e0a6f5a0e3d8262dbef119e075..7fd95caaeed88ae1a2480c63afe50b195c5c0086`.

The review used the bug-reproducer source-candidate rule: a finding requires a
reachable supported trigger, a violated code/data contract, a causal path, and
a small deterministic check.  No test, application import, database, Docker,
network, browser, or script was run.  This is not a runtime or whole-project
pass verdict.

## Result

No concrete source candidate met that threshold in this owned effects slice.

The initially suspicious callback alert cursor is not a candidate: the
canonical outbox migration defines `action_callback_outbox.tenant_id TEXT`, so
the initial empty-string cursor used by `src/worker.py:3415-3443` is type-safe.
The changed PostgreSQL coverage also expressly exercises round-robin, cursor
wrap, disappearance, and a per-tenant metric failure
(`tests/test_action_orchestrator_callback_recovery_pg.py:721-887`).

## Contract observations

- **WhatsApp admission and uncertainty:** authenticated requests are admitted
  under the resolved business before AI processing (`src/ai_agent_webhooks.py:230-375`).
  Completed duplicates do not send again; processing, process, send, and local
  completion uncertainty are retained as reconciliation rather than retried
  blindly (`:317-378`).  The adjacent durable-admission implementation and its
  native concurrent tenant-scope contract were reviewed; the latter is covered
  at `tests/test_whatsapp_webhook_replay.py:240-414,547-614`.
- **Telegram identity and replay:** the endpoint validates its business-scoped
  secret before payload handling (`src/ai_agent_webhooks.py:388-440`).  It then
  commits the trigger event and suppresses the legacy responder for a duplicate
  source event (`:459-500`; adjacent trigger runtime
  `src/services/agent_trigger_runtime.py:85-104,202-211`).  The direct endpoint
  contract is in `tests/test_legacy_webhook_auth_security.py:513-535`; no
  supported replay path to a second legacy reply remained.
- **Blueprint approval identity:** a capability must be raw-allowlisted, pass
  policy approval, and for `outreach.send_batch` gets its IDs only from the
  approved snapshot (`src/services/agent_blueprint_runner.py:1058-1125`).  The
  snapshot verifies tenant, IDs, recipient, reviewed bytes, current status, and
  approved text (`:3518-3553`), with stale/mutated cases in
  `tests/test_agent_draft_approval_identity.py:119-350`.
- **Outreach preflight:** dispatch replaces a claimed item with the fresh,
  validated provider payload and rejects any missing/mismatched payload
  (`src/services/outreach_dispatch_service.py:21-43,379-385`).  Generic,
  author-template, and Riderra-template paths bind queue, draft, touch, sender,
  channel, contact, source facts, and approval hashes before provider handoff
  (`src/services/outreach_safety_service.py:925-1090`).  The adjacent focused
  contract review was `tests/test_manual_campaign_dispatch_identity.py:118-300`
  (this file is not changed in the exact range).
- **Social publish (corrected frozen changed-chunk review):** immutable
  descriptors bind the post, exact text, target/sender or external account, and
  selected media (`src/services/social_posts/approval_binding.py:1-400`).
  Approval and queue transitions construct/recheck that descriptor
  (`src/services/social_posts/launch_proof.py:977-1210`); the claim then
  invalidates a drifted binding before external work
  (`src/services/social_posts/publication_lifecycle.py:78-103`),
  then an advisory-locked provider phase re-admits writer access, attempt ID,
  fingerprint, and snapshot (`:325-360`).  Provider adapters use the frozen
  target and re-check sender identity; the Telegram target-after-claim test
  confirms a changed target cannot redirect the effect
  (`tests/test_social_approval_binding_pg.py:383-408`).  One-call concurrency,
  accepted receipt, uncertain outcome, and manual-reconciliation races are
  covered in `tests/test_social_publish_uncertain_commit.py:227-593` and role
  readmission in `tests/test_social_publish_role_readmission.py:139-161`.
- **Frozen media/provider boundaries:** the new media layer resolves only
  business-owned selected assets, captures version/hash/path/public URL in the
  approval snapshot, and reloads that exact identity at send time
  (`src/services/social_posts/media_delivery.py:43-252`). Provider adapters use
  frozen bindings and classify indeterminate provider responses as uncertain
  (`src/services/social_posts/recommendations_handoff.py:474-1099`). Changed
  reports/workflow preserve `publishing` for reconciliation and require writer
  permission for scoped dispatch/metrics (`dispatch_reports.py:799-890,
  1300-1480`; `workflow.py:368-511`).
- **Callback recovery:** stale `sending` records are treated as uncertain and
  surfaced; the worker’s bounded cyclic scan includes historical uncertainty
  (`src/worker.py:3394-3475`).  The corresponding recovery/tenant-isolation
  contracts are `tests/test_action_orchestrator_callback_recovery_pg.py:338-887`.

## Exact changed implementation paths reviewed

1. `src/ai_agent_webhooks.py`
2. `src/worker.py`
3. `src/services/agent_blueprint_runner.py`
4. `src/services/agent_capability_handlers.py`
5. `src/services/outreach_campaign_service.py`
6. `src/services/outreach_dispatch_service.py`
7. `src/services/outreach_safety_service.py`
8. `src/services/social_post_service.py`
9. `src/services/social_posts/approval_binding.py`
10. `src/services/social_posts/dispatch_reports.py`
11. `src/services/social_posts/launch_proof.py`
12. `src/services/social_posts/media_delivery.py`
13. `src/services/social_posts/provider_adapters.py`
14. `src/services/social_posts/publication_lifecycle.py`
15. `src/services/social_posts/readiness_foundation.py`
16. `src/services/social_posts/recommendations_handoff.py`
17. `src/services/social_posts/workflow.py`
18. `src/services/whatsapp_webhook_admission.py`

The frozen range adds `approval_binding.py`, `media_delivery.py`,
`publication_lifecycle.py`, and `whatsapp_webhook_admission.py`; it modifies
the other six listed `social_posts` modules. All ten were re-reviewed from the
frozen HEAD source/diff for this corrected pass.

## Changed corresponding test paths reviewed

- `tests/agent_blueprint_fakes.py`
- `tests/test_action_orchestrator_callback_recovery_pg.py`
- `tests/test_agent_draft_approval_identity.py`
- `tests/test_founder_outreach_campaigns.py`
- `tests/test_legacy_webhook_auth_security.py`
- `tests/test_social_approval_binding_pg.py`
- `tests/test_social_approval_binding_unit.py`
- `tests/test_social_media_delivery_ssrf.py`
- `tests/test_social_post_service.py`
- `tests/test_social_posts_viewer_readiness.py`
- `tests/test_social_publish_provider_outcomes.py`
- `tests/test_social_publish_role_readmission.py`
- `tests/test_social_publish_uncertain_commit.py`
- `tests/test_staging_fixture_social_publication.py`
- `tests/test_webhook_config_contract.py`
- `tests/test_whatsapp_webhook_replay.py`

## Limitations and next action

This review establishes source-level contract coverage only.  It did not prove
the production migration state, database locking behavior, provider responses,
or execution of the listed tests.  There is no new effects-path source fix to
make from this review.  The next safe action is to retain this as a static
review artifact. Aggregate/restore preparation was previously denied; renewed
explicit permission remains required before any runtime validation. Do not
reinterpret this result as approval to rerun an uncertain external effect.
