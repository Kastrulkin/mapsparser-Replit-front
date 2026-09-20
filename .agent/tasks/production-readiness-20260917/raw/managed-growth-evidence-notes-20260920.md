# Managed Progress copy — evidence scope

Parent2fac7241, UX-LOCALE-07 follow-up. Owner/manager reads card state, goal,
next correction and measurement in the selected language. User-reported IAB
login was reconfirmed on the existing Today tab, without navigation, refresh,
preference/data controls or token access. Today still displays mixed languages;
this is the deployed version, not evidence that local source fixes failed.
Earlier authenticated Progress observation is preserved separately.

Backend RED `card-growth-copy-red-20260920.json`:27failed/12passed in0.16s,
516.225ms wall; missing additive metadata. This is API-contract coverage;
the causal visible locale failure is the frontend capture below.
First GREEN `card-growth-copy-green-20260920.json`:2failed/37passed,480.555ms;
two fixtures used overview.duplicate instead of the real overview.is_duplicate.
The fixture was corrected, not production duplicate interpretation.
`card-growth-copy-final-20260920.json` precedes the legacy-read review correction.
Authoritative backend `card-growth-copy-reviewed-20260920.json`:212passed
in0.16s/487.598ms. Supported provider facts ×5goals, source/fact failures,
legacy nested-only results, no input mutation, old text/CTA/scope checks.
All four guard counters are zero; complete captures, no timeout.
Scoped Ruff F821/F822/F823 passes in96.959ms, not a global backend lint claim.

The pure wrapper forbids DB connects, dotenv files, socket operations and child
processes before project imports; plugin autoload/conftest/cache are disabled.
This process-local guard is not an OS sandbox or native transaction test.
No main application, Docker, migration or real provider was started.

UI RED `managed-progress-ui-red-20260920.json`:1failed/4passed in6.12s,
9003.237ms wall; Spanish managed heading absent while Russian heading renders.
Actual canonical Russian payload text is retained in the synthetic fixture;
Cyrillic business names and provider brands intentionally remain visible.
Vitest uses envDir:false, sanitized environment and mocked request boundary;
it is not a real API or native browser test. Later captures record the GREEN.

Intermediate UI GREEN:3failed/4passed,12600.889ms. The Spanish heading, direct
action and decision already render; its provider query was ambiguous across
baseline/summary. Two older panel tests inspected the asynchronous language
provider before loading finished. These are fixture timing/query issues.
Initial typecheck:exit2/39971.462ms, two incomplete locale objects lacked the
new resultDisclaimer field during integration. Final checks must follow the
completed source, not reinterpret that capture as green.
Initial build:exit1/2033.864ms. Root-cwd launcher caused Tailwind to miss its
frontend-relative configuration (border-border/content error); no product CSS
change is warranted. Correct build cwd is frontend, with the explicit no-env
wrapper config and a fresh outDir. The failed build is retained as harness
evidence and is not an artifact ready for use.

Reviewed UI run:1failed/14passed plus1unhandled error,15468.234ms. The new panel
rating test repeated an ambiguous provider query (baseline and summary). The
audit=open scenario also reached the existing scrollIntoView API, which jsdom
does not implement. Fix the test query and scoped browser-API stub, asserting
audit focus, without changing application scroll/focus behavior. This run is
not GREEN despite its14passing tests.

The corrected app build passes in19.80s/21438.911ms. Its fresh final-dist is
inside /private/tmp/localos-managed-growth-build-20260920.uLLxel, not the deploy
directory. Rollup reports existing Yandex annotation warnings; Vite explicitly
does not empty an external outDir. No cleanup flag was used. First completed
app/node TypeScript and frontend lint pass in63515.376ms with the existing
auth_new.ts:115 any warning. Test-only corrections afterward need final checks.

Independent frontend review accepted fixes for rating and explicit baseline/
benchmark disclaimer fallbacks. The normal managed journey-action branch still
uses shared JourneyActionCard and can display Russian API/command copy. Replacing
it with the translated direct-focus navigation card would change execution and
approval behavior, so it is explicitly deferred, not described as localized.
The current package covers the managed panel, direct-focus and provider audit.

Further UI final:1failed/14passed,13893.245ms, no unhandled errors. One generic
fallback assertion matched both the baseline and a legacy next action. Root
scoped it to the baseline block. Authoritative final2:15passed/3files9.62s,
11084.613ms,exit0/empty stderr/complete. Audit focus is real jsdom focus; only
scrollIntoView and frame timing are stubbed and restored. This is not a native
smooth-scrolling test. Last type/lint final2:57763.466ms,exit0,existing1warning.
Build integrity199JS assets passes410.232ms. No application source changed after
the successful build/source review; subsequent corrections are test-only.

Final2 UI, full units and final types preload the existing no-egress-compatible
Node guard with sanitized env. Initial UI captures use mocked requests but did
not preload this extra guard; later guard success is not retrospective evidence
about earlier processes. The guard is JavaScript-level, not an OS sandbox.

First full frontend run exits1:665passed/7failed plus1failed-suite import,
309.55s/310913.613ms. All eight failing nodes are ENOENT: legacy static-file
tests resolve src/index.css, App.tsx, tracker.js, index.html and feature source
from process.cwd(), which was repository root even though Vite root is frontend.
Do not change those product files or call this a product regression. Full2 runs
the same frozen sources/config/guard from frontend cwd; the failed full capture
is retained rather than combining its665passes with other runs into a green suite.
Independent read-only review confirms all eight failing nodes are cwd-only,
with no failed product assertion. Full2 passes676tests/131files305.19s,
306719.104ms,exit0/no timeout/no truncation. Stderr includes expected negative-
scenario diagnostics; do not claim an empty stderr. The exact source and all
tests are unchanged from the source manifest. A later tmux-pane read found no
pane because the session had normally completed; the durable full2 capture,
not tmux session presence, is authoritative.

Final independent source/evidence reconciliation PASS: full2 counts and complete
capture confirmed, all eight frontend hashes match, expected negative-path/jsdom
stderr distinguished from unhandled failures. This is scoped unit/build evidence,
not a final whole-goal verdict or certification of native/provider behavior.
Precommit quality exits0/1877.86ms:20source/test/guard/artifact checksums match,
staged diff/ledger pass and Gitleaks reports no leaks in the staged payload.
One harmless improperly-formatted input line is jq -r adding an extra newline;
it does not replace or skip any of the20manifest entries. This staged scan is
not a historical/image/provider-secret or whole-project security certification.

Independent backend review initially rejected incomplete nested-only measurement
fallback. The resolved decision/reason now return from cycle columns or stored
JSON; no database rewrite. Final backend static review PASS. Frontend and final
whole-package review remain separate from this backend result.

No push, deployment, production/DB mutation or cleanup. Existing aggregate-v2
and synthetic-restore preparation denials persist. Current image needs10GiB
local headroom; latest observed5,976,336KiB is below the gate. Nine unrelated
dirty paths preserved. Overall goal acceptance remains FAIL.
