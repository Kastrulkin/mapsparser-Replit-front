# Cumulative frontend review — 2026-09-21

Scope: static, read-only review of committed range `30262a5bf7b468e0a6f5a0e3d8262dbef119e075..7fd95caaeed88ae1a2480c63afe50b195c5c0086`, limited to all changed `frontend/` implementation, test, E2E, and configuration paths plus the adjacent approval contract needed to evaluate the finding below.

## Candidate (not runtime reproduced)

### P2 — stale draft approval is still actionable after the UI says it must be recreated

Reachable input: a pending `approval_type: drafts` whose payload has no `snapshot_version: 1`, no items, or an item without a non-empty `review_text`.

`ApprovalPayloadSummary` displays “Проверка черновиков устарела или неполна. Пересоздайте проверку перед утверждением.” for this input (`frontend/src/pages/dashboard/agents/runs.tsx:1488`).  The changed render paths then show that warning above approval controls without gating them (`frontend/src/pages/dashboard/agents/detail.tsx:842-856`; `frontend/src/pages/dashboard/agents/employee.tsx:1176-1182`).

Expected contract: a flow must not offer “Подтвердить публикацию” after it tells the user that the exact reviewed snapshot is stale or incomplete. The backend does reject the resulting request as `approval_payload_stale` (`src/services/agent_blueprint_runner.py:269-281`, `3518-3545`), so provider safety is retained, but the frontend permits a knowingly invalid approval attempt and produces a recoverable error rather than blocking the action.

Cause: snapshot completeness is computed only within `ApprovalPayloadSummary`; neither parent uses it to disable or remove `onApprove`.

Small deterministic check: mount both `AgentApprovalDecisionPanel` and `EmployeeTestResultPanel` with the incomplete payload used in `draftApprovalSnapshot.test.tsx`; assert the approve control is disabled/absent and `onApprove` is never called. Existing test coverage asserts the warning only in isolation and invokes callbacks only for valid snapshots.

Classification: **CANDIDATE (high static confidence)**. No runtime execution was authorized.

## Reviewed changed frontend paths (71)

```text
frontend/e2e/staging/fixtureCommand.ts
frontend/e2e/staging/journey-registration-continuity.spec.ts
frontend/e2e/staging/owner-reviews-finance.spec.ts
frontend/e2e/staging/plan-compiled.spec.ts
frontend/e2e/staging/runtimeErrors.ts
frontend/e2e/staging/social-publication-reconciliation.spec.ts
frontend/playwright.journey-staging.config.ts
frontend/src/components/DashboardLayout.scope.test.tsx
frontend/src/components/DashboardLayout.tsx
frontend/src/components/FinanceImportPanel.test.tsx
frontend/src/components/FinanceImportPanel.tsx
frontend/src/components/ReviewReplyAssistant.i18n.test.tsx
frontend/src/components/ReviewReplyAssistant.tsx
frontend/src/components/content-plan/PublicationReconciliation.test.tsx
frontend/src/components/content-plan/PublicationReconciliation.tsx
frontend/src/components/growth/ManagedCardGrowthPanel.test.tsx
frontend/src/components/growth/ManagedCardGrowthPanel.tsx
frontend/src/components/growth/managedCardGrowthCopy.test.ts
frontend/src/components/growth/managedCardGrowthCopy.ts
frontend/src/components/growth/managedCardGrowthCopyAdditional.ts
frontend/src/components/growth/managedCardGrowthCopyEuropean.ts
frontend/src/components/journey/JourneyActionCard.i18n.test.tsx
frontend/src/components/journey/JourneyActionCard.scope.test.tsx
frontend/src/components/journey/JourneyActionCard.test.tsx
frontend/src/components/journey/JourneyActionCard.tsx
frontend/src/components/journey/JourneyWorkspaceFocus.test.tsx
frontend/src/components/journey/JourneyWorkspaceFocus.tsx
frontend/src/components/prospecting/OutreachCampaignBuilder.consent.test.tsx
frontend/src/components/prospecting/OutreachCampaignBuilder.scope.test.tsx
frontend/src/components/prospecting/OutreachCampaignBuilder.test.tsx
frontend/src/components/prospecting/OutreachCampaignBuilder.tsx
frontend/src/components/ui/sheet.test.tsx
frontend/src/components/ui/sheet.tsx
frontend/src/i18n/contentCalendarCopy.ts
frontend/src/i18n/journeyActionCopy.ts
frontend/src/i18n/locales/ar.ts
frontend/src/i18n/locales/de.ts
frontend/src/i18n/locales/el.ts
frontend/src/i18n/locales/en.ts
frontend/src/i18n/locales/es.ts
frontend/src/i18n/locales/fr.ts
frontend/src/i18n/locales/ha.ts
frontend/src/i18n/locales/ru.ts
frontend/src/i18n/locales/th.ts
frontend/src/i18n/locales/tr.ts
frontend/src/i18n/todayPageCopy.test.ts
frontend/src/i18n/todayPageCopy.ts
frontend/src/i18n/todayWorkCopy.test.ts
frontend/src/i18n/todayWorkCopy.ts
frontend/src/pages/LeadJourneyPage.test.tsx
frontend/src/pages/LeadJourneyPage.tsx
frontend/src/pages/SetPassword.logging.test.tsx
frontend/src/pages/SetPassword.tsx
frontend/src/pages/dashboard/ContentPage.dom-mutation.test.tsx
frontend/src/pages/dashboard/ContentPage.tsx
frontend/src/pages/dashboard/InfluencersPage.test.tsx
frontend/src/pages/dashboard/InfluencersPage.tsx
frontend/src/pages/dashboard/ProgressPage.i18n.test.tsx
frontend/src/pages/dashboard/ProgressPage.tsx
frontend/src/pages/dashboard/TodayPage.test.tsx
frontend/src/pages/dashboard/TodayPage.tsx
frontend/src/pages/dashboard/agents/detail.tsx
frontend/src/pages/dashboard/agents/draftApprovalSnapshot.test.tsx
frontend/src/pages/dashboard/agents/employee.test.tsx
frontend/src/pages/dashboard/agents/employee.tsx
frontend/src/pages/dashboard/agents/normalization.ts
frontend/src/pages/dashboard/agents/runs.tsx
frontend/src/pages/dashboard/agents/workflow-graph.test.tsx
frontend/src/pages/dashboard/agents/workflow-graph.tsx
frontend/src/test/stagingFixtureCommand.test.ts
frontend/src/test/stagingRuntimeErrors.test.ts
```

## Limitations

Static source review only. No tests, build, browser, runtime, network, database, Docker, staging-fixture, or shell-script execution was performed. Uncommitted paths were preserved and not assessed. This is not a whole-project pass claim.

---

# Independent cumulative infrastructure / migration / harness review — 2026-09-21

Scope: static review of the same committed range, limited to changed Docker/Compose/CI configuration, dependencies, Alembic migrations, and `scripts/` implementation paths listed below. This is a distinct review pass from the frontend review above.

## Result

**NO_BUG_PROVEN**: no further actionable candidate met the required reachability and contract-evidence threshold.

Specific static checks included:

- staging CI creates an explicit fresh GitHub-hosted Compose project, clears ambient configuration and provider credentials, verifies project labels before teardown, and confines staging browser work to the owned container;
- compiled-staging ingress uses a fixed `app:8000` upstream, origin-form request targets, body limits, hop-by-hop header filtering, a loopback host port, and a read-only mounted proxy; its source SHA-256 (`0fd0f918a5390fdf97d51019d5e9481227e9d1410838e23c1325718b27c22798`) matches the verifier constant in `scripts/test_compiled_table_staging.py`;
- the changed migration downgrades take stable locks and refuse destructive rollback when the migration's operational evidence exists;
- readiness/load/query-plan tools validate loopback high-port disposable DB names, preserve guard provenance, and bound cleanup to their UUID-owned database namespaces;
- the restore helper requires an explicit trusted archive, exactly matching disposable target confirmation, local Unix Docker context, and Compose-owned loopback PostgreSQL identity.
- the release constraints file is explicitly scoped to its audited ARM64 Python 3.11 inventory, identifies the omitted installer-tool pins as Dockerfile-owned, and does not misrepresent itself as a universal or hash-enforced lock; no source-only dependency-resolution defect is established.

## Reviewed implementation paths (29)

```text
.dockerignore
.github/workflows/staging-real-api-nightly.yml
Dockerfile
alembic_migrations/versions/20260902_add_creator_offer_distribution.py
alembic_migrations/versions/20260902_add_creator_relationships_portal.py
alembic_migrations/versions/20260914_work_review.py
docker-compose.compiled-staging.yml
docker-compose.release.yml
docker-compose.staging.yml
docker-compose.yml
docker/audit-ingress/proxy.py
pytest.ini
requirements.release.constraints.txt
requirements.txt
scripts/audit_approval_boundaries.py
scripts/check_content_learning_schema.py
scripts/check_staging_isolation.py
scripts/ci_gate_fast.sh
scripts/ci_gate_nightly.sh
scripts/ci_real_api_staging.sh
scripts/openclaw_ops_smoke_recover.sh
scripts/postgres-restore-latest.sh
scripts/readiness_journey_benchmark.py
scripts/readiness_journey_load.py
scripts/readiness_journey_measure.py
scripts/readiness_query_plans.py
scripts/seed_journey_staging.py
scripts/staging_fixture_cli.py
scripts/test_compiled_table_staging.py
```

## Limitations

No CI workflow, Docker/Compose command, migration, script, application, test suite, browser, network, or database operation was executed. The SHA-256 comparison was a local static file-integrity read only. This result covers only the listed implementation paths and is not a production-deployment or whole-project pass claim.

---

# Independent cumulative infrastructure / browser-harness test review — 2026-09-21

Scope: source-only review of the 25 changed browser-harness and infrastructure-contract test/support paths below in the same committed range. This pass assesses whether the added or changed checks preserve the advertised safety/coverage contract; it does not execute those tests or their subprocess, Docker, browser, HTTP, database, or loopback-server fixtures.

## Result

**NO_BUG_PROVEN**: no actionable reachable test-harness regression was identified by static review.

Contract findings:

- the Vite E2E helper allocates a strict isolated loopback port, awaits only its own server, captures diagnostics, and terminates only its own process group; the route guard fulfills only the explicitly mocked API origins, continues own-origin static assets, and aborts foreign loopback/external requests;
- converted guided-tour and Telegram E2E cases use that helper, retaining their user-visible transient-error assertions while removing fixed-port/shared-server exposure;
- ingress and compiled-staging tests exercise origin-form/request-size and hop-by-hop behavior, target identity, internal-network/app-alias, proxy-hash, readonly mount, and run-scoped worker-claim boundaries;
- CI/release/Docker checks validate isolated compose ownership, fail-closed cleanup and signal paths, digest/base/packaging provenance, excluded build artifacts, and opt-in compiled staging rendering;
- default collection/legacy coverage installs a child no-egress audit guard and asserts the quarantined legacy entry fails before a request;
- readiness and restore harness tests cover disposable local target admission, guard provenance/import origin, collision/cleanup ownership, watchdog reaping, semantic response failures, and structured fail-closed outputs;
- partnership seeding coverage remains limited to an idempotent unconfirmed overlap artifact and explicitly excludes offer/contact/approval/send content.

No test was found to weaken a production or external-action boundary. Tests that deliberately launch local subprocesses, Compose renderers, browsers, or loopback servers do so only when executed; this review did not execute them.

## Reviewed test and support paths (25)

```text
tests/e2e/test_guided_tour_transient_gateway_error.py
tests/e2e/test_telegram_mini_app_operator_error.py
tests/e2e/test_vite_harness.py
tests/e2e/vite_harness.py
tests/test_audit_ingress_proxy.py
tests/test_ci_real_api_staging_contract.py
tests/test_ci_typecheck_gate_contract.py
tests/test_compiled_table_staging_harness.py
tests/test_default_test_collection_safety.py
tests/test_docker_base_pins.py
tests/test_docker_browser_permissions.py
tests/test_docker_build_context_contract.py
tests/test_docker_frontend_artifacts.py
tests/test_docker_packaging_tools.py
tests/test_large_module_size_ratchet.py
tests/test_openclaw_smoke_recovery_safety.py
tests/test_postgres_restore_helper_safety.py
tests/test_readiness_journey_benchmark.py
tests/test_readiness_journey_load.py
tests/test_readiness_journey_measure.py
tests/test_readiness_query_plans.py
tests/test_release_compose_contract.py
tests/test_release_constraints.py
tests/test_seed_journey_partnership_contract.py
tests/test_staging_compiled_build_contract.py
```

## Limitations

Static source review cannot prove test discovery, dependency availability, platform-specific Compose/Vite/Playwright behavior, signal timing, or that the asserted source contracts agree with a running image. It also does not replace an independent review of the production implementations exercised by these harnesses.
