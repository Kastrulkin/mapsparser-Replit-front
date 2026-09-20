# Independent campaign consent review

Parent191488ba, UX-CAMPAIGN-CONSENT-03. Reviewer draft_approval_regression is
read-only and did not implement this patch. Source review and final targeted
evidence review PASS; no actionable source/test finding. Not a whole-project
security, production or release verdict.

Reviewed: exact saved-ID reload, transient state cleared only after canonical
GET snapshot, explicit discard/version selection, handler and UI guards for
approval/pilot/resume, unchanged backend policy and cross-scope lifetime fence.
Final40frontend/288guarded backend captures are untruncated exit0 with no timeout;
backend effect counters all zero. Fourteen new cases include canonical B text/
recipient and B-only approve, learning save/reload failure, failed save/missing
version/rejected reload, discard, saved C selection, explicit pilot cancellation
then confirmation targeting B, and resume after return to saved A.

Reviewer initially noted missing final hash manifest/integrity artifacts. Root
subsequently captured11source/test/config/guard hashes before full frontend,
and199JS integrity/scoped Ruff. Final independent broader evidence closure PASS:
723frontend tests/134files pass314.24s/capture316492.583ms, exit0, no timeout or
truncation. Known intentional jsdom/negative-fixture stderr is retained; no
failing/unhandled test result. App/node TypeScript and lint pass with exactly the
existing auth_new.ts115 warning. All eleven hashes independently match current
source/test/config/guard files after full tests; diff check clean. This closes
the earlier manifest gap for this bounded package, not original full readiness.

Limits: UI mocks/jsdom and synthetic SQL; no actual approval/send, provider
delivery, native DB/concurrency, new-build browser/mobile or deployed patch proof.
Same-lifetime competing request ordering and edits during pending requests are
not globally certified. Existing foreign worktree and denied lanes preserved.
