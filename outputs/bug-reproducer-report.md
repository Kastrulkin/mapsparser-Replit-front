# Bug Reproducer

## ✅ FIX_PROVEN — Bug reproduced and fix proven

> The same reproducer changed from failing to passing and broader checks passed.

**Project:** LocalOS
**Bug:** Operator language context mismatch has no automatic recovery
**Environment:** React 18, Vitest and jsdom on macOS; production asset hashes inspected read-only
**Generated:** 2026-08-28

## Original report

Opening the Operator route displayed: useLanguage must be used within a LanguageProvider.

| Contract | Expected | Actual |
|---|---|---|
| Observed behavior | A language-context mismatch caused by a stale frontend runtime triggers one cache-busting reload, then falls back normally if it repeats. | The exact context error remained on the generic ErrorBoundary screen and no version recovery was attempted. |

## Minimal reproduction

A child of the root ErrorBoundary throws the exact useLanguage provider mismatch observed in production.

**Confirming signal:** The one-time recovery key remained null instead of being set to 1.

### Reproduction files approved at Gate 1

- [ErrorBoundary.test.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/ErrorBoundary.test.tsx:30>) — Exact production error regression test approved at Gate 1.

## Red to green evidence

| Evidence | Before fix | After fix |
|---|---:|---:|
| Exit code | 1 | 0 |
| Timed out | False | False |
| Duration | 2,700 ms | 5,533.08 ms |
| Same command | — | True |
| Broader suite | — | passed |

### Before — failing evidence

```text
FAIL src/components/ErrorBoundary.test.tsx > ErrorBoundary with externally translated DOM > marks a language-provider version mismatch for one-time runtime recovery
AssertionError: expected null to be '1'

Expected: "1"
Received: null

Test Files 1 failed (1)
Tests 1 failed | 3 passed (4)
```

### After — fixed evidence

```text
Error: useLanguage must be used within a LanguageProvider
    at LanguageProviderVersionMismatch (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/ErrorBoundary.test.tsx:26:9)
    at renderWithHooks (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:15486:18)
    at mountIndeterminateComponent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:20103:13)
    at beginWork (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:21626:16)
    at HTMLUnknownElement.callCallback (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:4164:14)
    at HTMLUnknownElement.callTheUserObjectsOperation (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/generated/idl/EventListener.js:26:30)
    at innerInvokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:360:16)
    at invokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:296:3)
    at HTMLUnknownElementImpl._dispatch (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:243:9)
    at HTMLUnknownElementImpl.dispatchEvent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:114:17)
Error: useLanguage must be used within a LanguageProvider
    at LanguageProviderVersionMismatch (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/ErrorBoundary.test.tsx:26:9)
    at renderWithHooks (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:15486:18)
    at mountIndeterminateComponent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:20103:13)
    at beginWork (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:21626:16)
    at HTMLUnknownElement.callCallback (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/react-dom@18.3.1_react@18.3.1/node_modules/react-dom/cjs/react-dom.development.js:4164:14)
    at HTMLUnknownElement.callTheUserObjectsOperation (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/generated/idl/EventListener.js:26:30)
    at innerInvokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:360:16)
    at invokeEventListeners (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:296:3)
    at HTMLUnknownElementImpl._dispatch (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:243:9)
    at HTMLUnknownElementImpl.dispatchEvent (/Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/node_modules/.pnpm/jsdom@29.1.1/node_modules/jsdom/lib/jsdom/living/events/EventTarget-impl.js:114:17)
```

## Root cause

Frontend recovery recognized dynamic-import failures but the root ErrorBoundary did not classify the language-context mismatch as a recoverable stale-runtime error.

## Approved fix

Added exact-match, one-time cache-busting recovery for the language-provider mismatch in the root ErrorBoundary.

**Why this is causal:** The ErrorBoundary now intercepts the same error message before leaving the user on the failure screen and uses the existing reload guard to avoid loops.

### Production files approved at Gate 2

- [ErrorBoundary.tsx](</Users/alexdemyanov/Yandex.Disk-demyanovap.localized/Всякое/SEO с Реплит на Курсоре/frontend/src/components/ErrorBoundary.tsx:29>) — One-time cache-busting recovery for the language-provider mismatch.

## Verification

| Check | Status | Evidence |
|---|---|---|
| Regression test | ✅ passed | The same test changed from a null recovery key to passing. |
| Operator and ErrorBoundary tests | ✅ passed | 6 focused localization, DOM ownership, and recovery tests passed. |
| Frontend build | ✅ passed | Vite production build completed successfully. |

## Reproduce

```bash
npm test -- src/components/ErrorBoundary.test.tsx
```
```bash
npm test -- src/pages/dashboard/OperatorPage.i18n.test.tsx src/pages/dashboard/OperatorPage.dom-mutation.test.tsx src/components/ErrorBoundary.test.tsx
```
```bash
npm run build
```

## Limitations

- The component test proves the recovery gap and fix; it does not recreate an already-open browser tab spanning two deployments.

## Residual risks

- A genuine provider programming error causes one reload before the normal ErrorBoundary remains visible.

## Notes

- Fresh production chunks and retained Operator chunk dependencies were internally consistent during diagnosis.
- The recovery is exact-message scoped and guarded against reload loops.

---

Generated by `$bug-reproducer`. A fix is proven only by the same red-to-green reproducer plus relevant broader checks.
