# Next causal frontend check — read-only map, not a fix

The fresh default-worker v5 capture has828/830 passing; capped v6 has830/830.
Both frozen postcheck captures show5720blobs/zero mismatches at99849935. A
different worker count correlates with success but does not prove the cause.

Evidence lives in `native-frontend-checks-hflypi-20260921/`:
`native-frontend-unit-v5.json`, `native-frontend-unit-v6.json`, and
`native-frontend-unit-targeted-flaky-v6.json` (targeted3/3passed).

- `frontend/src/components/SEOKeywordsTab.i18n.test.tsx:50`: expected Turkish
  demo keyword `köpek bakımı` is absent. Failure DOM already has Turkish labels
  but only the all-queries category. Component begins with empty state at
  `SEOKeywordsTab.tsx:108`, effect calls load at432, demo state is set at137.
  Observation: translated chrome loaded, keyword demo state not yet observable.
- `frontend/src/pages/dashboard/ContentPage.i18n.test.tsx:31`: Greek heading
  is absent; DOM is exclusively LanguageLoadingFallback. The provider has not
  completed dynamic locale initialization (`LanguageContext.tsx:79`). The
  AudienceInsights request/empty-state path has not been reached. This differs
  from the keyword failure's later readiness phase.

Vitest config has no worker/timeout/isolation override; setup provides cleanup
and matchMedia, not broad storage/mock/timer resets. Do not infer cross-test
pollution solely from that absence. No test/component/runtime edits or repeat
executions were performed for this read-only map.

Next bounded diagnostic: repeat just these two modules under unchanged default
configuration, preserve each outcome/readiness phase, then evaluate explicit
test-only locale/data readiness synchronization. Do not change expectations,
product behavior, or blindly increase timeouts to get green. A deterministic
readiness correction remains a hypothesis until causal RED/GREEN evidence.
