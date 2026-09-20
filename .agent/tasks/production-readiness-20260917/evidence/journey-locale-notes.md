# Shared JourneyActionCard locale — locally verified

Parent7c080d11, UX-LOCALE-07 continuation. Previous goal turn was progress: saved
campaign-consent package committed with723frontend/288backend passes. The
original whole-project production-readiness DoD remains unchanged and FAIL.

User task: understand and record the next business action on Today, Progress,
partnership/influencer workspaces or Telegram Mini App in the chosen language.
JourneyActionCard was locale-blind: Russian system controls/help/placeholders/
default/error/date formatting even when surrounding UI uses ES/EN. Raw task
title/description/CTA are API/business content and are not translation targets.
Contract sources: DESIGN's human-language first layer, existing LanguageContext
ten supported locales, localized Today/Progress callers and existing card tests.

Root guarded RED on unchanged component:4failed/6passed across new5 + existing5,
7.17s/capture9592.439ms, exit1/no timeout/truncation. Failures are absent ES/EN
headings, Spanish date format and Spanish reply option. Retry/wire assertions in
the last case were not reached after the option failure. Existing RU behavior
and raw owner draft/unknown CTA/API error positive pass. Before execution root
removed three harness flaws (ambiguous ancestor date matcher, unclosed menu,
persistent vi.fn history); none is counted as a product failure.

Implementation: existing language context plus typed ten-language copy module;
known command labels, selects, fields, help, generic fallback and date locale.
Reply select gains a localized accessible name. Default expected result uses a
null sentinel so only absent/untouched default follows language; incoming,
edited and intentionally empty values persist. Raw API/user strings, command/
outcome/use-case values, business/action/version, surface, approval and retry
idempotency remain unchanged. No new dependency, backend/API/schema or layout.

Independent actual source review PASS: no actionable implementation defect;
exact command/payload/user-content contracts and null-default semantics checked.
Local app build passes12.98s/capture15205.897ms, exit0/no timeout/truncation.
Only existing upstream Yandex PURE/external-outDir warnings; no old dist emptied.
Expanded focused/adjacent suite91cases initially90pass/1fail,35.24s/capture
36661.264ms, no timeout/truncation. The sole failure is clipboard harness order:
userEvent.setup replaces navigator.clipboard after the manually defined spy.
Root confirmed installed library setup.js58 and changed only test setup order
to spy on the installed clipboard after setup; exact byte/command assertions
stay unchanged. This is not another product defect. Original causal four states
pass. Final rerun91/5files passes38.89s/capture41146.947ms, untruncated, only
known jsdom scrollTo diagnostics. App/node TypeScript+lint pass53358.768ms,
one existing auth_new.ts115 any warning. Eleven inputs captured37.912ms before
the rerun/quality/full checks. Full frozen757frontend/135files passes309.20s/
capture310547.28ms, exit0/no timeout/truncation. All11hashes match afterward.
Its stderr byte-equals the preceding campaign-consent full run's known jsdom/
intentional negative fixture diagnostics; no unhandled/failing test result.

Integrity passes181.551ms,199reachable JS files, entry index-BpAWkddx.js and
CSS index-BM6vOqzw.css in /private/tmp/localos-journey-locale-build-20260920.VsmIZr/dist.
Application source stayed unchanged after build; only test harness/additions
followed. No backend implementation or backend suite is changed/run in this slice.
Workers own distinct copy and tests, root owns integration/guarded captures.
No external calls or production forms; frontend API is mocked. Native browser,
RTL/mobile layout, all-server copy, provider and deployment are not proven.
Language-switch tests directly update LanguageContext.Provider value; they do
not exercise the real LanguageProvider's async translation-loading fallback,
which can unmount children. Therefore no whole-app locale-switch preservation
claim follows; that integration needs separate causal verification.
Nine foreign paths excluded. Disk6,922,648KiB (~6.60GiB), below10GiB image floor.
Aggregate/restore preparation denials and prior unguarded-reset INCONCLUSIVE
effects persist. No push/deploy, DB action, cleanup or Docker build.

Precommit capture passes1448.675ms, exit0/no timeout/truncation: all11manifest
hashes match, staged diff-check clean, staged Gitleaks scanned236870bytes with
no findings, original overallFAIL/onlyAC10PASS unchanged. Independent ownership
review confirms26owned files and9foreign exclusions; the capture adds a27th
owned file. Final scan follows documentation restaging. Local commit only.
