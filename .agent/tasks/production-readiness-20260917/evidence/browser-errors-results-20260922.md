# Browser error-path regression — 22 September 2026

Status: **2/2 PASS**, not a full end-to-end or production-readiness result.
Parent source: `ef6d3e1e`; no application code or test assertion changed.

The two Python/Playwright regressions that could not start Vite in the earlier
offline full-suite profile were run unchanged on a fresh Git archive of current
frontend and test sources. Existing frontend dependencies were APFS-cloned from
the previously verified frontend snapshot; existing native Python/Chromium were
reused. This is not a clean dependency installation proof.

## Actual checks

- Desktop guided tour: advance through steps while the second progress save
  returns HTTP 502; local progress survives and there is no unhandled page error.
- Mobile Telegram Operator (393 × 852): an HTML response to the chat request
  produces the intended Russian error text, not raw JSON parsing diagnostics;
  exactly one mocked chat request is observed.

`browser-v2.json`: exit 0, 25.59 s pytest / 26.863 s wrapper, exactly two named
tests and all six setup/call/teardown stages passed, no skip/xfail/timeout, empty
stderr. All 735 snapshot file content entries before/after are identical.
Independent read-only reviewer verified the raw result, six stages, external
denial and test bytes against `git show ef6d3e1e`: bounded PASS for these two flows.

## Isolation and limitations

Named tmux `audit-browser-errors-v2`; clear environment with private HOME/TMPDIR,
no DB/provider credentials, no Docker access or app/backend launch. Inherited
macOS sandbox denies external network, user-home file reads and writes outside
the task directory/cache exceptions. A pre-test socket probe confirms external
network denial. Loopback sockets are allowed for owned Vite; the unchanged
browser route guard mocks API calls and aborts other origins. This is a trusted
test profile, not a hostile-code sandbox or proof of backend behavior.

Only private node_modules `.vite` / `.vite-temp` caches and task-owned writable
files may change. The tests terminate their own Vite processes. No production,
existing database/container, provider send, push or deploy was performed.

First attempt `browser-v1.json` exited 65 in 0.624 s because macOS sandbox network
filters require `localhost`, not the literal IPv4 spelling. No pytest ran in that
attempt. Both original runner and failed capture are retained; v2 changes the
policy spelling and adds the explicit external-denial probe.

These are scoped regression results. Do not merge their counts into the previous
5487-node offline result or declare all browser scenarios/whole backend green.
Native PostgreSQL callback recovery is a separate in-progress profile.
