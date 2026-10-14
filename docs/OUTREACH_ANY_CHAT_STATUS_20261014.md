# Outreach acceptance — 14 October 2026

Full acceptance remains open. No new email has been sent during this check.

## Installed scoped fixes

- The existing worker runs its native send/reply cycle in one serialized background thread. Slow unrelated jobs no longer own that thread; legacy call sites share its lock. Existing dispatch limits, provider checks and reply synchronization remain enforced.
- Shared recipient addresses in template and ordinary campaign histories no longer stop the entire mailbox sync. Direct parent message IDs take precedence over thread references; unresolved multi-campaign replies remain unmatched rather than being assigned arbitrarily.
- The existing daily schedule accepts one explicit date and up to two distinct times, using the existing date/time event deduplication. It cannot repeat on another date. Editing a regular daily time clears these bounded slots. This is not a new scheduler.

Production files were freshly compared and merged with neighbouring work. Backups are in `/opt/seo-app/.release/outreach-acceptance-20261014/`. App, worker, Operator worker and Telegram restarted successfully. The frontend bundle was not replaced.

## Live evidence

- The native worker renewed the Riderra sender's reply sync at **07:03:08 UTC / 10:03:08 Moscow** with no sync error, without invoking a manual sync function.
- Partnerships for Dook task `d4b43860-d176-41f9-8085-462f962f39f3` shows **one sent message, zero replies**, three execution credits, and “Ответы проверяются автоматически” with that timestamp. Provider acceptance is not inbox delivery.
- Owner approved creation for three credits; web chat created blueprint `7eb3f7e6-a588-599e-9fe8-ef0f088ade63`, version `9bedc05e-9f16-4ca3-98f7-ba38ad9dcbac`, **14 October, 10:35 and 10:50 Europe/Moscow**, draft-only, two new suitable companies per run. Native free preview `ad67322a-047f-4f3b-b92d-70f1f640f9c6` completed at 10:28 Moscow. The UI has no business artifact for this no-side-effect preview; this does not count as actual prospecting.
- Preview initially remained queued: production restricted the run consumer to one older blueprint. Only the newly approved blueprint was appended to `AGENT_RUN_QUEUE_BLUEPRINT_IDS`; the old entry remains, schedule dispatch remains disabled. Environment backup is `env-before-preview-cohort` in the release directory, mode 0600.
- Native agent schedule/run/sheet processing now has its own serialized loop, independent of contact-maintenance backlog, retaining existing flags and native database leases. No run was manually dispatched.
- Persisted cost quote is at most six credits for search/checks per run, plus two saved drafts and two reserved runtime credits: **at most 20 additional credits for two runs**. Owner approval for execution is pending. No paid search or generation has occurred in this check.
- Browser reload retained current Partnerships layout and Dook group. Switching to Organika and reloading retained Organika without Riderra's selected group; switching back restored Riderra.

## Checks and remaining acceptance

55 focused tests pass for reply scope, dispatch serialization, bounded schedules, email adapter behavior, exact send review and channel limits. A prior broader run has fixture failures around advisory-lock handling; it is not reported as a clean complete suite.

Still required: approve the concrete native automation and its execution costs, complete two autonomous runs 15 minutes apart, reconcile unique companies/drafts/charges, pause it afterward, verify Telegram and business-switch recovery, and verify an actual reply association and stop behavior. Do not count a healthy mailbox poll or unit-test reply fixture as a new real incoming reply.

## Approved schedule activation

Owner approved two real draft-only runs within **20 additional credits total**. Since 10:35 had already passed when approval arrived, both slots were moved to **11:00 and 11:15 Moscow**, preserving the 15-minute interval and all other limits. The change was made through web chat, creating version `f25005a4-8338-42b9-9f3b-663459483a92`; its free preview completed at 10:50. Native UI activation shows “Работает” and next run 11:00. The worker's existing schedule flag is enabled and its existing cohort includes this blueprint plus the previous draft-only entry, which remains inactive. No schedule event has yet been counted as a completed prospecting run.

Chat initially failed during this change because automation status queried nonexistent `agent_runs.created_at`. It now reads `queued_at AS created_at`, preserving the response field. A focused status regression passes and a real chat retry read history successfully. Live files were compared before installing; backup is `management-before.py` in the same release directory.

Existing real Riderra inbound event `4493f180-a03c-435f-bb17-6896df540400` is linked to campaign `5f74ec40-25c2-4a0f-9668-250458e04cd9`, touch `960af7f4-524a-4ade-86c4-fb341bd094cb`, lead and workstream. It is human/question, `stops_campaign=true`, campaign stopped with `recipient_replied`. This establishes stored real reply/stop linkage for that campaign, not a reply to Dook or today's scheduled groups.
