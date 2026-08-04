# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS

**Bug:** Greek demo crashes on review tones and shows Russian copy

**Environment:** React 18, Vitest 4.1.10, jsdom, macOS arm64 local frontend workspace
**Generated:** 2026-08-04

## Original report

On the multilingual demo, a Greek guided-tour step crashes with TypeError: Cannot read properties of undefined (reading 'tones'); the Progress and Maps pages also show Russian system copy while Greek is selected.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | Selecting Greek keeps every tested demo step renderable and displays Greek system copy on review replies, business progress, and the maps/services start screen. | ReviewReplyAssistant dereferenced a missing reviewReply.tones object and crashed; Progress and CardOverview rendered Russian labels and API-derived Russian strings. |

## Minimal reproduction

Three focused component/page tests select Greek through the real LanguageProvider, render the reported routes with deterministic API fixtures, and assert the review workflow renders plus the Progress and Maps screens contain their Greek headings without Cyrillic system copy.

**Confirming signal:** Before the fix, the focused run had 3 failed tests and an unhandled TypeError at ReviewReplyAssistant.tsx:313 reading reviewReply.tones.friendly.

### Reproduction files approved at Gate 1

- [ReviewReplyAssistant.i18n.test.tsx](/tmp/localos-demo-i18n-20260804/frontend/src/components/ReviewReplyAssistant.i18n.test.tsx:1) — Reproduces the missing Greek reviewReply.tones crash.
- [ProgressPage.i18n.test.tsx](/tmp/localos-demo-i18n-20260804/frontend/src/pages/dashboard/ProgressPage.i18n.test.tsx:1) — Covers Greek localization of structured progress data.
- [CardOverviewPage.i18n.test.tsx](/tmp/localos-demo-i18n-20260804/frontend/src/pages/dashboard/CardOverviewPage.i18n.test.tsx:1) — Covers the Greek maps/services start screen and Cyrillic leakage.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 3,373.488 ms | 4,422.239 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
TypeError: Cannot read properties of undefined (reading 'tones')
    at ReviewReplyAssistant (/private/tmp/localos-demo-i18n-20260804/frontend/src/components/ReviewReplyAssistant.tsx:313:60)
    at renderWithHooks (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:15486:18)
    at mountIndeterminateComponent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:20103:13)
    at beginWork (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:21626:16)
    at HTMLUnknownElement.callCallback (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:4164:14)
    at HTMLUnknownElement.callTheUserObjectsOperation (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/jsdom/lib/generated/idl/EventListener.js:26:30)
    at innerInvokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:360:16)
    at invokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:296:3)
    at HTMLUnknownElementImpl._dispatch (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:243:9)
    at HTMLUnknownElementImpl.dispatchEvent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:114:17)
TypeError: Cannot read properties of undefined (reading 'tones')
    at ReviewReplyAssistant (/private/tmp/localos-demo-i18n-20260804/frontend/src/components/ReviewReplyAssistant.tsx:313:60)
    at renderWithHooks (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:15486:18)
    at mountIndeterminateComponent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:20103:13)
    at beginWork (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:21626:16)
    at HTMLUnknownElement.callCallback (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:4164:14)
    at HTMLUnknownElement.callTheUserObjectsOperation (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на К
... [output truncated] ...
 Unhandled Errors ⎯⎯⎯⎯⎯⎯

Vitest caught 1 unhandled error during the test run.
This might cause false positive tests. Resolve unhandled errors to make sure your tests are not affected.

⎯⎯⎯⎯⎯ Uncaught Exception ⎯⎯⎯⎯⎯
TypeError: Cannot read properties of undefined (reading 'tones')
 ❯ ReviewReplyAssistant src/components/ReviewReplyAssistant.tsx:313:60
    311|   // Get tone labels from translations
    312|   const tones: { key: Tone; label: string }[] = [
    313|     { key: 'friendly', label: t.dashboard.card.reviewReply.tones.frien…
       |                                                            ^
    314|     { key: 'professional', label: t.dashboard.card.reviewReply.tones.p…
    315|     { key: 'premium', label: t.dashboard.card.reviewReply.tones.premiu…
 ❯ renderWithHooks ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:15486:18
 ❯ mountIndeterminateComponent ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:20103:13
 ❯ beginWork ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:21626:16
 ❯ beginWork$1 ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:27465:14
 ❯ performUnitOfWork ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:26599:12
 ❯ workLoopSync ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:26505:5
 ❯ renderRootSync ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:26473:7
 ❯ recoverFromConcurrentError ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:25889:20
 ❯ performConcurrentWorkOnRoot ../../../../Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/react-dom/cjs/react-dom.development.js:25789:22

This error originated in "src/components/ReviewReplyAssistant.i18n.test.tsx" test file. It doesn't mean the error was thrown inside the file itself, but while it was running.
The latest test that might've caused the error is "renders the review workflow in Greek without a missing tones dictionary crash". It might mean one of the following:
- The error was thrown, while Vitest was running this test.
- If the error occurred after the test had been completed, this was the last documented test before it was thrown.
⎯⎯⎯⎯
```

### After — fixed evidence

```text
RUN  v4.1.10 /private/tmp/localos-demo-i18n-20260804/frontend


 Test Files  3 passed (3)
      Tests  4 passed (4)
   Start at  17:23:00
   Duration  3.30s (transform 2.55s, setup 1.85s, import 2.71s, tests 780ms, environment 3.62s)
```

## Root cause

LanguageProvider replaced the complete English dictionary with an incomplete locale object, so absent nested branches were undefined. In addition, Progress API labels and CardOverview presentation strings had Russian-only or Russian/English-only rendering paths.

## Approved fix

Deep-merge the selected locale over the complete English dictionary, supply the Greek review-reply branch, localize Greek progress/API copy, and route the visible CardOverview services start screen through Greek page copy.

**Why this is causal:** The merge guarantees the nested tones contract for every locale, while the added Greek dictionaries replace the exact hardcoded and API-derived strings asserted by the route tests.

### Production files approved at Gate 2

- [LanguageContext.tsx](/tmp/localos-demo-i18n-20260804/frontend/src/i18n/LanguageContext.tsx:17) — Recursively fills missing locale branches from English.
- [el.ts](/tmp/localos-demo-i18n-20260804/frontend/src/i18n/locales/el.ts:1) — Adds Greek card and review-reply copy.
- [progressPageCopy.ts](/tmp/localos-demo-i18n-20260804/frontend/src/pages/dashboard/progressPageCopy.ts:1) — Adds Greek progress labels and API-copy normalization.
- [CardOverviewPage.tsx](/tmp/localos-demo-i18n-20260804/frontend/src/pages/dashboard/CardOverviewPage.tsx:77) — Uses localized copy on the maps/services start screen.
- [cardOverviewPageCopy.ts](/tmp/localos-demo-i18n-20260804/frontend/src/pages/dashboard/cardOverviewPageCopy.ts:1) — Defines English, Russian, and Greek page-level presentation copy.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Exact reproducer | ✅ passed | Same command changed from exit 1 with 3 failures to exit 0 with 4 passing tests. |
| Relevant demo and tour tests | ✅ passed | 27 tests passed across six files. |
| Targeted ESLint | ✅ passed | No errors; 20 pre-existing warnings remain in legacy files. |
| Production frontend build | ✅ passed | Vite production build completed successfully in 8.80 seconds. |

## Reproduce

```bash
cd frontend && ./node_modules/.bin/vitest run src/components/ReviewReplyAssistant.i18n.test.tsx src/pages/dashboard/ProgressPage.i18n.test.tsx src/pages/dashboard/CardOverviewPage.i18n.test.tsx
```

## Limitations

- The focused CardOverview fixture covers the initial empty-services screen; deeper service dialogs and every tab are outside this reproducer.
- English fallback prevents crashes for untranslated nested keys but intentionally remains visible until a locale supplies its own translation.

## Residual risks

- Older shared service-filter controls still contain Russian literals when a non-empty service list is opened; translating that shared component requires a separately scoped change.
- Other Greek dashboard pages not included in the supplied screenshots may still fall back to English where Greek keys are absent.

## Notes

- No API, route, production data, external send, or action behavior changed.
- The existing root bug-reproducer report belongs to another task, so this evidence is stored in a task-specific output directory.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
