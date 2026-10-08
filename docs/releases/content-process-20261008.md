# Content process release — 2026-10-08

## Scope

The release ports the necessary content/backend dependencies onto a clean branch,
preserving the smart navigation, Armenian/Kazakh languages and current production
Operator functionality. Production snapshots, secrets and database archives are
not included in Git. A concurrent `communications.control_email` result-link fix
was preserved after comparing the live file with the initial snapshot.

Content editor and chat use contentplanitems/social_posts, with explicit record
versions. Photo selection is independent of successful AI analysis and checks the
business/file availability. Delivery is projected from existing receipts and never
changes the publication status. An invalid multi-field chat edit does not partially
save an earlier text change.

## Compiled content boundary

The description compiler generates immutable Python source using the existing
restricted runtime. Each run receives a fresh, authorized content snapshot and
returns only post IDs/revisions. The host validates those requests and invokes the
existing capability/sender/receipts. No new scheduler or transport is introduced.

Approval binds artifact hash, version, scope and the saved Telegram ID. A changed
binding, paused blueprint, stale lease, changed post, incomplete kit or unknown
delivery cannot automatically dispatch again. Execution additionally requires both
the business allowlist and COMPILED_CONTENT_HANDOFF_BLUEPRINT_IDS.

Chat preparation uses the same blueprint-creation service as the menu. It no
longer enables legacy notification preferences as a substitute for compilation.
Legacy approval compatibility is retained, not used for new chat requests.

## Verification before deployment

- Backend targeted suite: 128 passed on disposable PostgreSQL and pure-runtime tests.
- Frontend: TypeScript passed; dashboard/public builds passed.
- Content editor DOM: 27 passed.
- LocalOS-wide chat content query: 1 passed (six unrelated chat tests deselected).
- Wider chat DOM suite also has older expectations incompatible with the current
  production animated reply/partnership display. Do not claim that suite passed.
- Isolated program and lease/binding fence tests are not proof of real Telegram delivery.

## Deployment and pilot

Only explicit release files may be copied, never all src. Compare production
hashes again before replacing any shared file. Backup under
/opt/seo-app/debug_data/releases/content-process-20261008; preserve its permissions.
Restart only affected services. Verify live container hashes, HTTP and affected API.

Runner deployment/attestation, pilot creation, real owner-only delivery and browser
end-to-end confirmation remain separate acceptance gates. Do not enable dispatch
until the runner is pinned/inspected and the exact pilot ID is allowlisted. Preserve
the two active Riderra schedules and all existing Telegram receipts on rollback.

Pilot: business cb674174-8b3d-41a3-8277-525c849935f2, Telegram/VK/MAX, 10:00
Europe/Moscow, one day before publication. Test recipient is the existing owner
binding, not a phone-number lookup. Do not send to Irina. Keep regular scheduling
off until the user's browser verification and a separate recipient decision.
