# Authenticated IAB navigation — 20 September 2026

Root observed the user-owned `localos.pro/dashboard/today` tab after the user
reported signing in. This is UI evidence, not a deployed revision attestation,
API test suite, or verification of unshipped local fixes.

Read-only route sequence: Today → Progress → Content → Agents → Today.
All four rendered authenticated page content. Navigation used the existing
sidebar. It was closed on return to Today. No settings, language, business,
approval, generation, refresh/sync, schedule, publish, send or credential action
was submitted. No token/cookie was extracted. Routine application read-side
telemetry is not audited by this observation.

The IAB developer log query (`error`/`warn`, limit 15) returned an empty list
at the initial Today, settled Progress, Content, Agents and final Today checks.
This means no entries were visible in those bounded captured logs, not proof
that every API response or runtime condition was error-free. No timing or
performance benchmark was taken; loading transitions were allowed to settle.

## Locale observations

- Spanish Today still displays the English system labels `What to show first
  on Today`, `Needs your decision`, and `Review the prepared result and choose
  the next step`, plus a Russian system Open button.
- The local Today static dictionary already contains Spanish versions of the
  three English labels (`frontend/src/i18n/todayPageCopy.ts`), and the page uses
  those keys. This observation does not distinguish deployed revision/bundle,
  cache or runtime-language mismatch. Local fixes were not deployed here.
- Progress visibly mixes Spanish overview text with the Russian system block
  `Цель и состояние карточек`, `Подтвердить цель`, and `Главное действие`.
  Read-only independent source trace identifies hardcoded Russian copy in
  `ManagedCardGrowthPanel.tsx` and the managed-growth branch of `ProgressPage.tsx`.
  The existing Progress i18n test does not supply `card_state`, so its assertions
  do not cover that branch. This is additional localization debt, not a tested fix.
- Agents renders its list and selected overview, but some system statuses and
  details remain English/Russian within Spanish chrome. They were not source-
  traced or exercised beyond read-only rendering during this pass.
- User-authored task names, business content and previously generated results
  are deliberately excluded from the localization defect classification.

No complete scenario, approval, provider, permissions matrix, mobile layout
acceptance or full production health audit is claimed. The current narrow panel
size was used unchanged; no viewport override or account preference was set.
