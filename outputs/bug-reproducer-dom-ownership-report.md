# React DOM ownership crash: reproduction and fix

Status: `FIX_PROVEN`

## Root cause

Android in-app browsers and page translators can wrap a React-owned text node in an extra `font` element. React still retains the original parent in its fiber tree. When a later state transition removes, replaces, or inserts relative to that text node, the browser rejects the operation because the node is no longer a direct child of the parent React supplied.

The previous protection was incomplete: `translate="no"` only asks translators not to mutate the page, page-specific workarounds covered individual screens, and the ErrorBoundary displayed a fallback only after React had already crashed.

## Implemented invariant

`frontend/src/lib/domOwnershipGuard.ts` installs a single DOM ownership guard before the React root mounts. It recovers `removeChild`, `insertBefore`, and `replaceChild` only when both the expected parent and the externally moved node remain inside a registered LocalOS root. Operations elsewhere retain native browser behavior and still throw on invalid ownership.

Each recovery writes a console warning and dispatches `localos:dom-ownership-recovered`, so the condition remains observable instead of being silently hidden.

## Verification

- Original translated-node reproducer: fixed; the React tree stays usable.
- Native error outside `#root`: still throws.
- Targeted regression suite: 4/4 passed.
- Adjacent page mutation suite: 14/14 passed.
- ESLint: passed for all changed source and test files.
- Production build: passed.
- Production browser test: bundle `/assets/index-u3r4eNhk.js`, recovery event observed, zero page errors, no ErrorBoundary screen.

Production commit: `e2f64a95` (`Prevent translated DOM ownership crashes`).
