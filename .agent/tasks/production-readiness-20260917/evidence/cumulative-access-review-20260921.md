# Cumulative access review — 2026-09-21

## Scope and method

Read-only cumulative source review of exact range:

`30262a5bf7b468e0a6f5a0e3d8262dbef119e075 -> 7fd95caaeed88ae1a2480c63afe50b195c5c0086`

Focus: object/tenant/role gates; supported paths; rollback, retry, and race regressions. README, repository AGENTS.md, the `bug-reproducer` skill, shared execution contract, and bug-discovery contract were read before ranking candidates. No application edits, tests, imports, scripts, DB, Docker, or network calls were made. At review time, owned paths were clean; separately dirty unrelated prospecting files were not touched.

This is source evidence only. It is not a runtime, production-data, deployment, or whole-project PASS claim.

## Result

No remaining high-confidence finding in the owned exact-range access review.

The review originally raised a P1 candidate that `network_parent` content plans were unreachable when a network ID differed from all business IDs. That inference is **withdrawn: NO_BUG_PROVEN**. The state is schema-permitted but not shown to be created by the supported writer; treating it as a regression would confuse a representation/data-repair gap with the user-created route.

### Withdrawn candidate: network-parent representation

The apparent concern was that `src/services/content_plan_service.py` identifies the network parent with `business.id == network_id`, notably in `_fetch_network_scope_options`, and HEAD’s `_resolve_content_plan_scope` rejects a requested parent scope when no such option exists.

The supported writer establishes exactly that identity convention:

- `DatabaseManager.create_network()` inserts a new network and immediately invokes `ensure_network_parent_business()` (`src/database_manager.py`, exact HEAD lines 1475-1490).
- `ensure_network_parent_business()` documents that the parent uses the network ID as its business ID, then persists `id=network_id` and `network_id=network_id` (`src/database_manager.py`, lines 1499-1503 and 1547-1552).

An independent reader confirms the same contract:

- `services/telegram_control_scope.py` counts locations with `b.id <> n.id`, excludes the synthetic parent from ordinary business selection, and excludes it when enumerating network locations (exact HEAD lines 70, 122, 139).

The content-plan representation itself is pre-existing: BASE already used `WHERE network_id = %s OR id = %s` and `parent_business_id = network_id` in `_fetch_network_scope_options`. HEAD adds canonical selection and access checks around that existing representation; it does not introduce it. The web content page gets `/content-plans/context` and submits the context option's `scope_type` and `scope_target_id` unchanged (`frontend/src/pages/dashboard/ContentPage.tsx`, exact HEAD lines 1015 and 1961-1966).

Precise future check, if a data-repair lane is authorized: create a network through `create_network`, add a location through `add_business_to_network`, then assert that the synthetic parent has `id == network_id`, the context exposes `network_parent` for that ID, and generated scope includes the parent plus locations. A separate migration/repair audit is required before classifying any missing parent row as a production defect.

## Exact implementation paths reviewed

```text
src/api/agent_blueprints_api.py
src/api/auth_user_api.py
src/api/crm_integration_requests_api.py
src/api/finance_api.py
src/api/google_business_api.py
src/api/media_intelligence_api.py
src/api/operator_api.py
src/api/outreach_campaign_api.py
src/api/services_api.py
src/auth_system.py
src/core/action_orchestrator.py
src/core/action_policy.py
src/core/auth_helpers.py
src/core/capability_names.py
src/core/finance_imports.py
src/core/outbound_network.py
src/core/readiness.py
src/core/telegram_webhook_auth.py
src/database_manager.py
src/legacy_routes/client_reports.py
src/legacy_routes/core_public.py
src/legacy_routes/public_requests.py
src/services/card_growth_service.py
src/services/contact_intelligence_service.py
src/services/content_plan_service.py
src/services/content_voice_service.py
src/services/operator_audio.py
src/services/operator_colleagues.py
src/services/operator_mobile_actions.py
src/services/telegram_dashboard.py
src/services/today_workspace.py
```

## Changed corresponding tests reviewed

```text
tests/legacy/test_api.py
tests/test_auth_email_case_insensitive.py
tests/test_browser_session_security.py
tests/test_card_growth_copy_contract.py
tests/test_contact_intelligence.py
tests/test_contact_intelligence_ssrf.py
tests/test_content_plan_site_ssrf.py
tests/test_content_voice_write_access.py
tests/test_crm_integration_requests_api.py
tests/test_employee_content_plan_access.py
tests/test_finance_import_resource_limits.py
tests/test_finance_import_transaction_pg.py
tests/test_finance_roi_scope.py
tests/test_google_oauth_current_access.py
tests/test_legacy_business_data_pg.py
tests/test_legacy_business_data_preauth_pg.py
tests/test_legacy_news_generation_readiness.py
tests/test_media_intelligence_api.py
tests/test_network_member_access.py
tests/test_operator_chat_fallback_api.py
tests/test_operator_colleague_transport.py
tests/test_operator_miniapp_subscription_access.py
tests/test_operator_mobile_actions.py
tests/test_operator_mobile_review_capability_readiness.py
tests/test_operator_mobile_review_confirmation_readiness.py
tests/test_operator_news_write_access.py
tests/test_operator_plan_continuation_pg.py
tests/test_operator_review_reply_viewer_readiness.py
tests/test_operator_viewer_readiness.py
tests/test_readiness_endpoint.py
tests/test_service_compression_apply_concurrency_pg.py
tests/test_services_content_viewer_readiness.py
tests/test_services_content_viewer_readiness_guard.py
tests/test_telegram_dashboard_copy.py
tests/test_telegram_operator_write_access.py
tests/test_telegram_research.py
tests/test_today_work_copy.py
tests/test_viewer_mutation_readiness.py
```

## Limitations

- No test was run, including isolated PostgreSQL RBAC and concurrency checks.
- No production data was inspected; the synthetic-parent convention was established from source writer/reader contracts, not from a data census.
- The review excludes paths explicitly owned by other reviewers, including agent runtime/services, social/outreach/WhatsApp execution, webhooks, worker paths, infrastructure, migrations, and harness work, except where cited only to establish an adjacent source contract.

## Final bounded test/harness coverage pass

Additional exact-range, source-only review of test credibility and supported contracts (not a test execution or an application-runtime review):

```text
tests/helpers/db_init_client_info.py
tests/legacy/README.md
tests/test_action_orchestrator_callback_ssrf.py
tests/test_agent_finance_untrusted_rows_pg.py
tests/test_agent_sheet_provider_recovery_pg.py
tests/test_agent_source_pdf_compatibility.py
tests/test_approval_boundaries_audit.py
tests/test_campaign_recipient_review.py
tests/test_compiled_run_claim_pg.py
tests/test_creator_offer_distribution_migration_rollback.py
tests/test_creator_portal_migration_rollback.py
tests/test_legacy_agent_approval_policy.py
tests/test_manual_campaign_dispatch_identity.py
tests/test_operator_chat_viewer_readiness.py
tests/test_password_reset_sessions.py
tests/test_riderra_template_authorization.py
tests/test_work_journal_pg.py
tests/test_work_review_migration_rollback.py
tests/test_worker_captcha_flow.py
tests/test_worker_expired_flow.py
tests/test_worker_resume_flow.py
```

### Result

No additional source-proven test/harness defect found in this bounded pass.

The reviewed tests add or maintain meaningful contract coverage rather than simply mirroring comments: callback dispatch carries a claim token through redirect/SSRF coverage; untrusted finance rows are pinned to stored run tenant/capability/approval; compiled claims recheck direct and network membership after admission; recipient projections retain the selected contact; password reset tests assert atomic session revocation; and worker captcha flows now use migrated Postgres schemas rather than creating an ad-hoc compatible table.

The new native PostgreSQL tests use explicit test-DSN/guard requirements or Testcontainers/migrations. Those constraints are appropriate isolation signals but were not exercised here; their practical collectability remains unverified. The client-info helper's reduced `network_members` shape has no `role` column, whereas the production role-gated writer uses one. The identified helper consumers are read/client-info gates, so this is not a demonstrated test failure or product defect; any future reuse of that helper for a write-gate test must extend the fixture to the canonical role schema.
