# One-time approved content handoff — 11 October 2026

## Scope and result

The user approved moving item `461d4363-faed-4790-8c3a-41dc97d75650` to 12 October, reviewing and approving its Telegram/VK/MAX package, and sending it once to Alex and Irina. The date and approval were saved through the real content editor. Texts and selected photo were preserved; the 1,200 RUB price was checked against current services.

Run `f493efd5-28ef-42d0-9624-85bf060b587a` was admitted through the real compiled-program UI and completed at 16:44 UTC. The busy background worker delayed consumption; the existing queue claim and compiled executor consumed exactly this admitted run in a one-off worker invocation. No second run was enqueued.

Telegram accepted all 12 parts, each with attempt_count=1:

| Recipient | MAX photo/text | VK photo/text | Telegram photo/text |
| --- | --- | --- | --- |
| Irina | 1034 / 1035 | 1036 / 1037 | 1038 / 1039 |
| Alex | 1040 / 1041 | 1042 / 1043 | 1044 / 1045 |

Provider receipts confirm transport acceptance, not that recipients read messages. Each recipient has an independent receipt and revision in existing social_posts metadata. Telegram/VK/MAX remain approved; Yandex remains published. No public post was sent. The blueprint remains draft and AGENT_SCHEDULE_DISPATCH_ENABLED=false.

## Scoped frontend repair and deployment

Both current cockpit detail adapters dropped compiled_access, leaving the approved test button disabled. The scoped release preserves backend permission data; it does not bypass permission checks. Production source was patched and a compatible frontend built from current production files was switched atomically. A concurrent frontend update was detected and the initial rollout safely aborted; fresh Today/App/shared component changes were then preserved. All source hashes and current index were guarded before switching.

Deployed entry asset: index-MJ0ZYOiF.js. Backup: /opt/seo-app/backups/content-execution-access-e079d8093b05. No service restart was performed for this frontend repair. HTTP returned 200; the live button became enabled and the actual preview showed six eligible recipient/channel rows for this item only.

Relevant commits through 8d7aa3f38 were pushed to codex/network-content-release. Main dirty workspace and unrelated production source were not reset or mass-committed.

## Verification and remaining limits

- Current compatible content component and copy tests: 23 passed; build passed.
- Scoped adapter/source contract tests: 5 passed.
- Earlier compatible baseline: 35 UI tests passed.
- Fresh production Today test suite has five existing failures because its fixture omits LanguageProvider; these were not concealed or changed as part of this fix. Today source was preserved unchanged.
- The run history UI reports completed but its business-result panel says the result was not saved. Provider delivery was verified from canonical receipts; this display inconsistency still needs repair. Do not follow its suggestion to send again.
- No continuation job was found under the expected previous-plan idempotency key during this check. Automatic plan renewal is not claimed as verified by this test.
- Regular scheduling remains off pending completion of the broader network workflow verification.

Screenshot of the saved post: /private/tmp/content-12oct-approved.png.
