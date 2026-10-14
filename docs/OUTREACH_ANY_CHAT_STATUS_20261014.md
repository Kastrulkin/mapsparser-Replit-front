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

## Two autonomous schedule runs completed

- 11:00 slot: run `1da3fee6-6b14-4c5c-8ed4-e689085c8424`, queued **08:00:22.783930 UTC**, completed **08:01:32.386406 UTC**. Outreach task `f6ede573-312b-40d1-b60e-8659534b608c`: six new raw candidates, four checks, zero eligible, zero drafts, five execution credits (one search plus four checks).
- 11:15 slot: run `1cb337fa-6d30-416d-8d23-8a011c5a58d4`, queued **08:15:24.885993 UTC**, completed **08:16:43.683122 UTC**. Outreach task `fbfeb341-c1ae-492b-b5d1-aea253953e5d`: six duplicates excluded, zero new imported companies, zero drafts, two search credits. Its runtime reserve was released, with zero runtime tokens/charge.
- Event interval: **15 minutes 2.102063 seconds**. Both used native scheduler and worker, with no manual claim/dispatcher invocation. No campaign or send was created. Execution cost **seven credits**, distinct from three-credit creation and charged chat planning commands.
- Native web-chat pause was confirmed after completion; blueprint status is `paused`. Existing results and costs remain.

This is successful schedule/deduplication acceptance, **not successful prospecting/draft acceptance**. The reviewed Russian query returned Russian sellers of trips to India instead of India-based agencies selling Phuket. Qualification correctly refused to count those candidates. A source-confirmed contact and a raw search result did not become eligibility.

Installed correction: creation preview now exposes exact queries, audience, geography and requirements instead of blank legacy country/destination labels and cents. The action catalog instructs concise queries in the target market language, preserving the requested service and company location rather than workflow wording. This prompt change is not claimed as proven improved search quality.

Web chat saved candidate version **3**, `552e2e4a-9553-46f9-ade5-3f8916de7a43`, with two explicit English queries for India-based outbound agencies / Phuket-Krabi packages in Delhi and Mumbai. Other requirements and limits remain unchanged. It is **not active**, no new search has run, and the blueprint remains paused. A single additional run up to ten credits (combined execution at most seventeen) is awaiting owner approval.

The bounded schedule projection no longer invents tomorrow's run after today's last slot; it returns no next run. Tests cover selecting the second slot and expiry. Earlier UI showed tomorrow despite correctly bounded worker execution; this was a presentation defect, not an actual third scheduled event.

Telegram parity remains unverified in this session; a request to open the LocalOS chat is pending. Full outreach acceptance is still open.

Final targeted suite: **58 passed**. After reload, automation UI correctly says “Автоматические запуски приостановлены”, but its prominent badge still says “Работает” despite persisted `paused`. This residual frontend status-priority defect is not claimed fixed; avoid replacing the current neighbour-owned UI bundle from an older checkout.

## Corrected-query acceptance run (v3, 14 October)

Owner approved one run, execution cap 10 credits; total execution cap 17 including the two earlier scheduled runs. Version `552e2e4a-9553-46f9-ade5-3f8916de7a43`, parent run `9d93733e-1a4b-41cf-b355-89c38d2f3f83`, continuation `49fd9bf6-84e6-48dc-bb8a-7f4ce314b309`.

- English Delhi/Mumbai queries returned six new candidates. Execution charged six credits (one search, four checks, one saved draft); combined execution thirteen credits. Operator command/planning charges are separate and must not be presented as included in execution costs.
- A completed preparation stopped at the qualification budget before drafting an already qualified company. Fixed the branch and added tightly scoped recovery of the same completed preparation parent/step, within its original limits, owner, business and active version. No new run/search, budget reset or external send. Native chat retry and confirmation resumed that same task.
- The generated NETTOURS draft failed quality checks (`WEAK_OFFER_BRIDGE`, `MULTIPLE_CTA`). It is not a ready letter.
- More seriously, the model incorrectly accepted “Outbound Tours from India” / South East Asia as proof of the mandatory Phuket condition. The cited fact contains no Phuket. Added a necessary source guard for explicit capitalized names inside mandatory requirements, including transliteration normalization, to reject this case. Applied it both to new qualifications and read-time eligibility/letter contracts/send review of stored qualifications; original model audit records are preserved.
- This guard is conservative and is not complete semantic entailment or entity resolution. It does not prove suitability merely because a name appears; unrecognized translations/inflections may remain unverified. Lowercase names, implicit requirements and negative/contradictory evidence still require broader qualification validation. Do not describe this as a universal solved qualification system.
- Paused test automation through the web chat after the run. No send was performed. No additional paid search/check/generation was started after detecting unsupported evidence.
- Free previews of paused automations now remain claimable by the native queue; paid runs of paused or archived automations remain blocked. Regression tests cover the actual claim predicate.

Acceptance remains open: corrected prospecting must produce genuinely evidenced companies and quality drafts, Telegram parity must be verified on the actual current result, and same-group incoming replies remain unproven. Two autonomous scheduled executions and deduplication passed earlier; that does not establish prospecting success.
