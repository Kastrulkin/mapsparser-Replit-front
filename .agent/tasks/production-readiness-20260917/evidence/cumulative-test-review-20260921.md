# Completed changed-test-path review — 21 September 2026

Frozen range: `30262a5bf7b468e0a6f5a0e3d8262dbef119e075` to
`8be8e45a5a2930607311becebf05a3d456d100b0`. The cumulative inventory binds
the base/head blobs. **Static review, not test execution or whole acceptance.**

All112 changed test-tree paths have now been semantically reviewed at the
changed-hunk/assertion/fixture level: earlier27 infrastructure paths and
`test_social_media_delivery_ssrf.py`, plus84 paths below (including the
remainder of previously partial `test_social_post_service.py`). Helpers/docs
are counted as paths, not fictional tests. No native PostgreSQL, browser,
provider, network or application execution was performed by these reviewers.

These reports supersede the historical83-path gap in cumulative notes and older
checkpoints. Frontend75/backend-source55/infra29 source review remains as
previously recorded. Most of522 evidence/docs artifacts are not yet fully
semantically reconciled; full current-revision runtime/release proof is missing.
The later VK and safety-guard deltas have separate bounded reviews and captures.
**Whole FAIL; AC1–9/11 FAIL, AC10 PASS unchanged.**

## Per-path report

“PG-designed” or “Browser-designed” describes assertions inspected in a test,
not a successful run. “Unit” denotes its actual mocked boundary. No reviewer
proved a new P0/P1 runtime defect in these84 paths.

| Path (relative to repository) | Reviewed guarantee and limit |
| --- | --- |
| `tests/test_action_orchestrator_callback_recovery_pg.py` | PG-designed: recovery claims, lease fencing, tenant isolation and bounded scans; transport/URL validation stubbed. |
| `tests/test_action_orchestrator_callback_ssrf.py` | Unit: dispatcher bookkeeping plus actual pinned-client construction; no real DNS/TLS/proxy. |
| `tests/test_agent_draft_approval_identity.py` | Unit fake cursor: draft identity/tenant/snapshot/capability binding; no concurrent PostgreSQL approval. |
| `tests/test_agent_finance_untrusted_rows_pg.py` | PG-designed: hostile finance rows cannot replace tenant/capability/approval; only owner business changes. |
| `tests/test_agent_sheet_provider_recovery_pg.py` | PG-designed: closed transaction before provider, uncertain outcome/expiry/commit failure avoid retry; explicit guarded DSN change. |
| `tests/test_auth_email_case_insensitive.py` | Unit DB double: email query and active-user behavior; no uniqueness/collation race. |
| `tests/test_browser_session_security.py` | Flask unit: cookie/CSRF routing, with session validation mocked; no deployed browser/domain proof. |
| `tests/test_campaign_recipient_review.py` | Pure projection: strict recipient join and selected-recipient normalization; no send or approval persistence. |
| `tests/test_compiled_run_claim_pg.py` | PG-designed: direct/network revocation and active user admission before artifact validation; read transaction release. |
| `tests/test_content_voice_write_access.py` | Unit strict cursor: real write-role SQL parameters and zero write/commit on denial; no native concurrency. |
| `tests/test_employee_content_plan_access.py` | Unit service branches: decisive read/write helpers mocked; not stored-role authorization proof. |
| `tests/test_finance_import_resource_limits.py` | Route/helper: bounded file reads and 413 before parser/normalizer/DB; not server streaming-multipart limit. |
| `tests/test_finance_import_transaction_pg.py` | PG-designed: unique violation savepoint followed by successful row insertion. |
| `tests/test_finance_roi_scope.py` | Unit: business-scoped ROI SQL and denied insert; write-access helper mocked, limitation documented. |
| `tests/test_google_oauth_current_access.py` | Unit route: signed-state denial, post-exchange recheck, rollback/lock boundary; provider/DB transaction mocked. |
| `tests/test_legacy_agent_approval_policy.py` | Unit runner/policy: aliases, approval envelope and payload; fake cursor/orchestrator, not real executor. |
| `tests/test_legacy_business_data_pg.py` | PG-designed full route: migrated tenant denial and returned business-data shape. |
| `tests/test_legacy_business_data_preauth_pg.py` | PG-designed statement recording: no DDL/write before admission; direct/network/viewer reads. |
| `tests/test_legacy_webhook_auth_security.py` | Flask route: raw HMAC/admission/redaction and effect spies; no provider/proxy deployment. |
| `tests/test_password_reset_sessions.py` | PG-shaped fake: reset/revoke row-lock/query/rollback/replay; no actual two-connection race. |
| `tests/e2e/test_guided_tour_transient_gateway_error.py` | Browser-designed: routed API/Vite UI error copy and local progress; missing assertion that second failing PUT occurred. |
| `tests/e2e/test_telegram_mini_app_operator_error.py` | Browser-designed: malformed-response safe copy; missing proof that target request actually occurred. |
| `tests/e2e/test_vite_harness.py` | Unit harness: own API/static allowed, other origins aborted, startup failure stops owned mocked process. |
| `tests/e2e/vite_harness.py` | Support implementation: isolated loopback server/request allowlist/bounded stop, not an assertion file. |
| `tests/test_apify_diagnostic_privacy.py` | Pure helper/AST: synthetic privacy markers absent, legacy trace rewrite, unknown event category and re-raise. |
| `tests/test_large_module_size_ratchet.py` | Static line-count ratchet only, not semantic architecture proof. |
| `tests/test_legacy_parser_diagnostic_logs.py` | AST exact legacy branches: raw synthetic values stay functional but not stdout. |
| `tests/test_legacy_parser_leaf_diagnostics.py` | AST selected sinks/leaf branches: finite diagnostics; limited by curated sink inventory. |
| `tests/test_parser_debug_bundle_safety.py` | Helper/tempdir/AST: diagnostic JSON omits values; release evidence needs source hashes (already required). |
| `tests/test_parser_diagnostic_logs.py` | AST parser/helpers: redaction and functional returns; runtime source is bound by release capture hashes. |
| `tests/test_worker_apify_ipc_safety.py` | AST IPC plus one actual synthetic fork/TemporaryFile: large-result drain and cleanup; other process states simulated. |
| `tests/test_worker_captcha_flow.py` | PG-designed CAPTCHA lifecycle: state/fields checked, but no retry_after timing assertion. |
| `tests/test_worker_expired_flow.py` | PG-designed expiration lifecycle: status/session cleanup with mocked session manager. |
| `tests/test_worker_failure_reason_safety.py` | AST worker plus real taxonomy, fake DB: reason/retry/terminal projection, not full worker integration. |
| `tests/test_worker_parser_artifact_safety.py` | AST worker file/process doubles: serialization/privacy and preservation; not OS durability proof. |
| `tests/test_worker_parser_diagnostic_logs.py` | AST retry branches: parser/proxy markers redacted while retry decision retained. |
| `tests/test_worker_proxy_diagnostic_safety.py` | AST preflight/review: raw health-policy input separate from finite diagnostics; DB/HTTP mocked. |
| `tests/test_worker_resume_flow.py` | PG-designed resume lifecycle: completed state and CAPTCHA cleanup, not card-persistence claim. |
| `tests/test_worker_services_quality.py` | Worker test: anonymous IPC marker/round-trip, fake provider; process semantics covered in IPC test. |
| `tests/test_work_journal_pg.py` | PG-designed journal: role/status/tenant revocation and mutation/no-mutation/idempotency. |
| `tests/agent_blueprint_fakes.py` | Support fake: approval fields/lookup; insertion order does not model SQL decided_at/id sorting. |
| `tests/helpers/db_init_client_info.py` | Support schema helper: reduced client/network columns; not production migration or complete write-RBAC schema. |
| `tests/legacy/README.md` | Documentation: accurately quarantines unvalidated legacy script. |
| `tests/legacy/test_api.py` | Legacy script: fail-closed immediate error/no requests import; does not claim to run canonical gate. |
| `tests/test_agent_source_pdf_compatibility.py` | Pure pypdf parser: valid generated PDF, encrypted/malformed failures; not upload resource-limit proof. |
| `tests/test_card_growth_copy_contract.py` | Pure copy/data: provider facts/goals, stable codes, evidence distinction and immutability. |
| `tests/test_contact_intelligence.py` | Changed timeout fixture: pinned-fetch failure reaches graceful warning; URL validation stubbed separately. |
| `tests/test_contact_intelligence_ssrf.py` | Unit SSRF: private/mixed/rebound DNS, IP/SNI/Host, IPv6, read cap/cleanup/redirect; fake network. |
| `tests/test_content_plan_site_ssrf.py` | Unit site fetch: credentials/schemes/private/rebind/redirect/charset/cap/fallback; no real HTTP server. |
| `tests/test_crm_integration_requests_api.py` | Flask SQL-shape/role doubles: tamper, viewer/writer/network/admin/no-write; not stored-RBAC/transactions. |
| `tests/test_founder_outreach_campaigns.py` | Static frontend source assertions for restore hook/unsaved review; not browser behavior. |
| `tests/test_legacy_news_generation_readiness.py` | AST legacy generation: admission, scoped queries, rollback/redaction and fail-closed schema; fake transaction. |
| `tests/test_manual_campaign_dispatch_identity.py` | Unit manual dispatch: approved bytes/recipient/hash/queue/sender/channel; fake SQL/gates, no concurrent provider. |
| `tests/test_media_intelligence_api.py` | Flask route/SQL: approval reset and writer gate before effects; fake stored-role rows. |
| `tests/test_network_member_access.py` | Only compatibility lambda changed; existing assertions unchanged, no new guarantee. |
| `tests/test_operator_chat_fallback_api.py` | Only fixture compatibility changed, always-true write gate; not authorization proof. |
| `tests/test_operator_chat_viewer_readiness.py` | PG-designed Operator chat: stored viewer/revoked deny, writers allow, viewer read bypasses write gate; chat stub. |
| `tests/test_operator_colleague_transport.py` | Pure transport state machine: proxy priority, timeout no-blind-retry, auth before transport; request/DB fake. |
| `tests/test_operator_miniapp_subscription_access.py` | Pure capability mapping assertion only, not stored subscription admission. |
| `tests/test_operator_mobile_actions.py` | Unit mobile state machine: scope, expiry, authorization, replay and cross-business target; no real concurrent DB. |
| `tests/test_operator_mobile_review_capability_readiness.py` | PG-designed review capability: stored subscription rechecked at confirmation; counted generator stub. |
| `tests/test_operator_mobile_review_confirmation_readiness.py` | PG-designed confirmation: direct/network viewer/revoked denial, writers, retained target and replay before generator. |
| `tests/test_operator_news_write_access.py` | Flask role-aware cursor: write gate/SQL before generator/event/commit; invalid/anonymous before DB. |
| `tests/test_operator_plan_continuation_pg.py` | PG-designed continuation: old-plan preservation, request-id replay and atomic allocation/batches; generator fake. |
| `tests/test_operator_review_reply_viewer_readiness.py` | PG-designed replies: viewer previews, denied mutations with unchanged state/no generator, writer controls. |
| `tests/test_operator_viewer_readiness.py` | PG-designed Operator routes: write/run/approval/compiled-preview deny before runner; read-only preflight allowed. |
| `tests/test_riderra_template_authorization.py` | Changed assertion rejects non-template pass-through; recipient binding tightened. |
| `tests/test_service_compression_apply_concurrency_pg.py` | PG-designed concurrent compression: advisory lock/idempotency on disposable fixture; not run here. |
| `tests/test_services_content_viewer_readiness.py` | PG-designed content/services/mobile/network routes: stored role and admission before generation. |
| `tests/test_services_content_viewer_readiness_guard.py` | Guard unit: owned loopback DSN only, libpq override/hash-mismatch refusal. |
| `tests/test_social_approval_binding_pg.py` | PG-designed social binding: real claim/finalizer and snapshot/target/media drift/race; Telegram transport stub. |
| `tests/test_social_approval_binding_unit.py` | Pure descriptor: supported nonsecret destinations and overflow media-history fail-closed. |
| `tests/test_social_posts_viewer_readiness.py` | PG-designed social routes: denial before lock/state change, writer mutations, viewer read/rehearsal. |
| `tests/test_social_publish_provider_outcomes.py` | Adapter transport doubles: receipts, rejection/uncertain/HTTP/account drift; not live interoperability. |
| `tests/test_social_publish_role_readmission.py` | Fake DB: durable claim followed by fresh role check before adapter/finalizer; demotion and writer controls. |
| `tests/test_social_publish_uncertain_commit.py` | PG-designed uncertain publication: controlled transport/commit failure/concurrency, durable state prevents repeat. |
| `tests/test_telegram_dashboard_copy.py` | Fixture signature compatibility only; no changed behavior assertion. |
| `tests/test_telegram_operator_write_access.py` | Telegram role-aware doubles: write gate before chat, inactive/no-user before query, read default. |
| `tests/test_telegram_research.py` | Fixture subscriptions added for both tenants before cross-tenant assertion; correct current contract. |
| `tests/test_today_work_copy.py` | Pure copy mapping: additive codes, unknown state avoids invented copy, user/provider text retained. |
| `tests/test_viewer_mutation_readiness.py` | PG-designed finance routes: direct/network/owner/admin admission and no host override. |
| `tests/test_webhook_config_contract.py` | Static Compose/staging-validator wiring only, not live configuration proof. |
| `tests/test_whatsapp_webhook_replay.py` | Flask signed webhook doubles plus opt-in PG replay/tenant/concurrency design; native portion not run. |
| `tests/test_social_post_service.py` | Full changed legacy service assertions: explicit fake write-gate scope, new snapshot/media binding and dispatch metrics. Adapter outcome, not status alone, remains lifecycle authority. |

Review attribution: rows1–20 and41–61 are from
`remaining_security_assertions_20260921`; rows21–40 and62–84 from
`remaining_worker_assertions_20260921`. Both read immutable changed assertions
and necessary production contracts, with no edits/imports/test execution.

## Remaining evidence/test quality work

- **TEST-BROWSER-FAILURE-OBSERVED-01, P2:** the guided-tour and Telegram mini-app
  scenarios do not assert that their injected failing request occurred.
  Effect: safe generic UI can conceal an unexercised error branch. Add exact
  request method/path/count assertions (guided tour second PUT), with a
  mutation that removes the request and makes the test fail. Source-supported,
  not runtime bug or executed mutation; small scope/effort/risk, medium confidence.
- **TEST-CAPTCHA-RETRY-TIME-01, P2:** CAPTCHA test claims automatic retry but
  does not assert populated/future `retry_after`. Add bounded timing assertions
  to the owned native lifecycle proof. Production scheduling was not shown
  broken; low effort, medium time-fixture risk, acceptance requires real owned
  PG run when authorized. No denied native preparation was retried.
- **TEST-APPROVAL-FAKE-ORDER-01, P2:** blueprint fake uses insertion order for
  the SQL newest-approval contract (`decided_at DESC,id DESC LIMIT 1`).
  Risk: multi-approval tests may accept the wrong row. Reproduce with reversed
  insertion/tied dates, then align fake ordering. No production defect proven;
  low effort/blast radius, medium confidence, before relying on multi-row proof.
- Mocked role checks, transactional doubles and fake DNS/TLS remain scope
  limits, not new runtime findings. Existing hash-bound captures address
  immutable-source evidence; ordinary worktree-reading tests are not inherently
  defective. Native concurrency/provider/TLS/browser gates remain separate.
- The earlier `credential.helper=store` variant claim is withdrawn:
  `git config --file /dev/null --get credential.helper=store` returned exit1,
  `invalid key`. It is not a valid setter/bypass. The valid protected-branch
  refspec gap is reproduced and corrected in the separate safety-guards package.

No production or DB/schema mutation, provider effect, cleanup, push or deploy.
