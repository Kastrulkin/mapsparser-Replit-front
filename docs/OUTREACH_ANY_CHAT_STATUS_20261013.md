# Outreach acceptance — 13 October 2026

The full outreach goal is **not accepted**. Do not equate deployed components, old sent campaigns, or successful qualification with a new successful draft/send pilot.

## Sources and release boundaries

Backend fixes are committed on `codex/outreach-acceptance-20261013` (through `ed1d02e41`). The compact Operator/task-picker change is on `codex/operator-task-picker-20261013` (through `77582c3c2`), based on the compact UI release `3616c45a4`.

Production and the main working checkout contain other uncommitted changes. They are not interchangeable release sources. Preserve demo/navigation, ready-email import, manual-text support and the neighbouring free-access UI. Apply scoped changes to current runtime files; do not rebuild the old main checkout and overwrite the current UI. The frontend release script's active dependency-graph check rejects the older Operator/Partnerships/navigation layout.

LocalOS backups for this run: `/opt/seo-app/.release/outreach-acceptance-20261013/`. OpenClaw bridge backup: `/root/openclaw_runtime/var/releases/outreach-acceptance-20261013/`. No database migration, destructive deduplication or mail send was performed.

## Verified fixes

- Installed OpenClaw `web_fetch` is invoked through the existing authenticated bridge. Website readiness is renewed only by a successful real read of the controlled LocalOS robots resource; authorization is checked first. Failure does not extend the verification timestamp. Paid fallback remains disabled.
- Canonical `www`/apex redirects are accepted only for the same website and port. Initial plus four same-site pages remain the maximum. Public contact/company pages and previously sourced same-site pages fit that budget; unknown URLs are not guessed.
- Public source-confirmed contacts are included in qualification evidence. A sourced email is not evidence of mailbox delivery. Collected excerpts remain untrusted evidence.
- The actual Compose `operator-worker` runs `src/operator_worker.py`, not the general worker loop. It now consumes the existing approved website queue in one bounded background thread, leaving pause/chat commands responsive. Jobs created by active approved web searches are also eligible; unrelated historical enrichment is excluded.
- A domain-only historical import does not become a second company when there is exactly one named company for that website. Both records remain. Two named companies require a decision.
- A group's drafts/receipts/replies are scoped to its campaigns, including native batch projections. Reusing a company no longer automatically imports unrelated historical sends into the group's counters.
- Campaign drafting is bound to the exact current reviewed task. A new task cannot reuse an old sent campaign as its new draft. Replays of the same task reuse only its own draft.
- `English` and Russian/English language labels normalize to the existing language codes. Invalid conditions explain the failure rather than returning “Data received”. Validated outreach actions finish without another planning loop. Resume chooses the actual continuation worker unless an existing batch-draft job is present.
- Task picker refreshes on opening and immediately retains newly returned tasks. Temporary refresh failure retains the last list.

## Live evidence

- Telegram link command created task `34301e4b-09b2-47da-8d25-9aa767eadac6`, reused Holiday Advisor and delivered its negative result to the originating Telegram conversation. This is a negative-path test, not successful draft acceptance.
- Web task `a8549889-9e13-4bea-9af0-023496f3a5bc` qualified Holiday Advisor, but reused an old sent campaign. That result is explicitly **not** counted as a fresh draft. The reuse defect was subsequently fixed.
- Current three-company web task `e361ce95-586a-441f-a167-455805fdb5ed` retained its ID through a native reviewed resume. It reused the original EWS Holidays, Holiday Advisor and Kingdom of Holidays records. OpenClaw source jobs completed; Holiday Advisor and Kingdom of Holidays passed the requirements. EWS lacks sourced evidence of Phuket sales. Three qualification credits were charged; zero search calls occurred.
- Initial drafting failed because it selected the oldest historical contract. The exact-task fix then exposed a production-only extra function parameter; the merged signature was corrected and verified through the actual container import. No new letter was sent or manually repaired.
- The next reviewed version permits up to five draft attempts. The owner explicitly approved this exact draft-only version after the initial approval rejection. The start has not yet been verified: LocalOS HTTPS and server SSH currently time out. Do not claim the approved run passed.
- Mobile 390 px and desktop 1366 px: input remained visible and no horizontal overflow was observed. Task picker stale-list defect was reproduced; its regression now passes, including a refresh failure.

## Verification and remaining work

62 focused backend tests pass; changed backend files compile. Task-picker regression passes; three frontend release-guard tests pass. Application type check (`tsc --noEmit -p tsconfig.app.json`) passed with exit 0. Earlier clean root-config checks were not application type checks.

The server UI build initially failed because an already declared/locked `@xyflow/react` dependency was not installed. Dependencies are being restored from the existing lockfile; the previous served bundle remains in place until build and release checks pass.

Remaining acceptance:

1. Start the owner-approved version once connectivity is restored and obtain fresh canonical drafts without manual result editing; find a third actually suitable candidate rather than weakening evidence for EWS.
2. Complete a positive Telegram review → complete draft-text delivery. Desktop user interactions interrupted the attempted follow-up test; coordinate a short uninterrupted window.
3. Review exact new recipients/text/version and obtain separate human send approval before native queue/send tests. Historical receipts and the prior control reply do not establish acceptance for these new letters.
4. Perform two real native scheduled draft-only runs, 15 minutes apart, then pause and reconcile duplicates/expenses. Existing chat schedule accepts daily/weekly schedules; no interval-schedule implementation or substitute Codex automation is claimed.
5. Finish served UI/task-picker/browser checks and business-switch recovery. Do not claim full outreach complete while any of the above remain unresolved.

## Additional scoped fix pending deployment

The live Partnerships draft list showed historical sent letters for the same leads while the new task correctly reported zero new letters. List and send snapshot filters now use exact task/campaign ownership instead of shared lead membership. Empty campaign scope remains empty; business/task access is validated first. Regression tests cover exact campaign ownership, empty groups and another business. This patch has not been deployed or browser-verified because HTTPS/SSH connectivity is unavailable. Merge its hunks with live files, preserving production additions, before release.

## After owner reboot, 13 October 2026

Direct SSH restored and application, both workers, Telegram, PostgreSQL and Redis were running. Group-list fix merged with live additions and installed with backup `group-list-before.tgz`. Chat status now returns real counts, expenses, reason and task-specific link; regression passes and patch is installed with `chat-status-before.tgz`.

The staged UI assets had already been written before the interrupted compression report. Active navigation and JS/CSS dependency checks passed; assets were copied first, index atomically last, older chunks retained. `/dashboard/operator` actually returns `index-Deg9xrk_.js`, verified within the actual app container. Public `/` has its separate bundle and must not be used as proof of the dashboard revision. Browser pass remains pending: HTTPS from the workstation times out although server-side HTTPS and direct SSH work.

Telegram status request reached the existing e361 task and reproduced a label-only response; fixed subsequently. Further Telegram interaction stopped when the owner switched to another chat. No fresh draft run or external email was started. Approval for the same reviewed draft-only version remains valid. Prior kernel journal contains memory-pressure messages; this is evidence of resource pressure, not proof that this UI build caused the outage. Do not repeat a heavy server build during live task execution.

## Latest native acceptance evidence, 13 October

This section supersedes earlier connectivity/build/draft statements above. The browser is reachable and serves the compact Operator bundle. The owner-approved max-five draft run produced two fresh canonical texts, delivered in full by both web chat and Telegram, with recipients, sender and source links. This proves cross-channel retrieval, not draft quality acceptance. The Kingdom opener incorrectly copied a recipient first-person quotation as the sender; Holiday used an unrelated company-history fact. Neither is approved for sending.

Personalization v16 (commit `9fa96d49e`, installed with `quality-before.tgz`) selects a verified requirement related to the offer and attributes first-person quotations to the recipient's website. Explicit retry can refresh stale generation contracts while preserving old versions, consumed attempts and costs. A max-six revision preview for e361 is prepared; expansion by two saved texts requires the pending owner approval and has NOT started.

The separately approved Dook run is task `73ae0d00-9d3e-4171-902a-edad10b9aae2`. It reused the saved company, read five pages through OpenClaw, performed zero searches, charged one execution credit and produced no letter. Source-confirmed email was found, but India location and Phuket sale were not proven in readable content. This is a negative qualification result, not a successful third candidate. Readability omitted footer/navigation evidence and Russian requirement tokens did not match English links. Do not mark fit manually or silently start new paid reads.

The bridge's additional link-selection defect was reproduced: a required organic-supply page was discarded while an unrelated tourism URL was selected. The scoped fix considers actual link labels/path against requirements, prioritizes relevant service links after contact/about pages, and preserves the five-read budget and same-site restrictions. Installed in the active `capabilities/outreach_mvp/web_read.py` with `web-read-before-link-priority.py` backup; service active. It does not solve cross-language requirements or restore omitted footer content by itself.

Targeted backend suite: **93 passed**. App typecheck previously passed; no new frontend or heavy server build in this step. No email queued or sent. Task e361 execution cost is five credits (three checks plus two saved texts); Dook execution cost is one credit. These figures exclude separately charged Operator planning commands; full ledger reconciliation remains outstanding.

Remaining: three good automatic drafts; positive Telegram link-to-draft run; exact send approval and native provider/reply proof; two native schedule runs 15 minutes apart; final responsive/browser/business-switch checks and complete expense reconciliation. No full outreach readiness claim.

### Approved repeat completed

Owner approved max-six version; it was confirmed through native web chat, followed by retry and native resume confirmation. Two new v16 canonical texts were saved, bringing e361 execution cost to **seven credits**, attempts to six. Kingdom (`ce29e40c-8699-4c7b-a7fc-81f3c7b93c59`) now references its sourced Krabi–Phuket itinerary and passes the semantic gate. Holiday (`81122e4f-b2f3-42da-97d7-b8cf3f30aaa3`) references the sourced Phuket arrival day but remains blocked by `WEAK_OFFER_BRIDGE`. No sends occurred; old versions remain in retry history.

The remaining defect is the service's mandatory generic proposal bridge. It asserted generic client need rather than connecting to the verified context. Scoped fix now creates the bridge from the reviewed offer and exact qualified context, strips Markdown heading syntax only for display, and retains semantic approval requirements. Installed over freshly compared live files with `ai-bridge-before.py` / `campaign-bridge-before.py` backups. **94 targeted tests pass.** No further generation was started. A max-seven preview is being prepared for one blocked Holiday retry; it requires separate owner approval. Ready Kingdom must be preserved. Dook remains unqualified.

## Telegram readability correction

Owner reported duplicated email bodies and unrelated manual-map instructions. Reproduced dispatcher defect: every result containing `drafts` was sent through the bulk review-answer renderer. Outreach is now explicitly distinguished from review replies. Ordinary task notifications use a compact counts/credits/next-action card; requested canonical letters use separate cards with recipient, sender, subject, complete body, source and readable status. Existing ledger/chunking remain; no new generation or sends are introduced.

A live read additionally reproduced a correctness defect: the planner returned old letter text from conversation history with zero tool calls. Explicit “Покажи письма [задачи UUID]” now routes directly through the existing business-scoped task read operation in all channels. Ambiguous IDs/missing selected task require clarification instead of copying history. A Telegram “Показать письма” callback carries the task ID and invokes the same authorized read route. Scoped files installed over freshly compared live files; backups in the existing release directory. **100 targeted tests pass**; live format recheck is in progress. Owner-approved max-seven Holiday-only repeat started via web chat; outcome pending, Kingdom remains preserved. No external email sent.

### Live Telegram format and latest repeat outcome

Native Telegram test “Покажи письма задачи e361...” now returned **three separate messages**: compact summary (3 found, 2 qualified, 2 saved letters, 8 execution credits), current Kingdom letter marked ready for review, and current Holiday letter marked needs revision. Current subjects/bodies matched canonical campaigns; no duplicate “Ответ 1/2” or map-publication footer. This is a positive native presentation/read test. Button markup is installed; click-through validation remains pending because the native app window became unavailable. Historical notifications are preserved.

Owner-approved Holiday-only attempt seven completed. Kingdom campaign remains unchanged `ce29e40c-8699-4c7b-a7fc-81f3c7b93c59`. Holiday new campaign `23423cf0-209f-4b46-951e-575d90c7cb07` remains blocked by `WEAK_OFFER_BRIDGE`: proposal mentions the arrival-day itinerary but does not explain the practical arrival-transfer role. Gate remains enforced; no manual approval/data/text repair. **One ready letter, one blocked letter, third candidate unqualified**; full pilot not accepted. No further paid retry is authorized or started.

Browser reload restored selected task and compact layout; task picker contains Dook, Escape returned focus to “Задачи”. Picker labels still use a coarser stage (“Готовим письма”) than the current task card (“Требуется действие”); do not claim complete status parity. Other notification families (incoming replies, scheduled-batch shortage, content/reviews/system errors) still need the same concise event→result→next-action convention; only outreach task/draft presentation was corrected here.


## Native continuation and source recovery, 13 October 17:15

Owner approved Holiday attempt eight plus bounded Dook within seven additional execution credits, without search or sends. Holiday campaign `1d6333a5-c23d-458c-ad7f-32d6109915c9` passed automatic quality review; Kingdom remains unchanged. e361 has two ready texts, eight attempts and nine execution credits. Browser refresh verified the task-scoped letters list contains two current canonical texts instead of six historical versions. Full campaign scope/history is preserved separately.

Reviewed same-site sources survive enrichment handoff and fit within the five-page OpenClaw budget. Two same-company URLs preserve target_count=1. Dook task `d4b43860-d176-41f9-8085-462f962f39f3` completed through Telegram, reused the saved company, charged one check credit, performed zero searches and generated no letter. India/email passed; Phuket did not. Stored fetch text contains only generic company/contact content. OpenClaw returned the actual title `10 Days Phuket Krabi Tour Package From India`, previously dropped by our bridge. The installed fix preserves the title as explicitly labelled sourced evidence; it does not invent missing itinerary details. Real cached OpenClaw read confirmed the title.

104 targeted tests pass. Dook revision preview at 17:14 keeps sources/conditions, max four checks plus one draft within remaining owner-approved budget. Native coordinate click reports noWindowsAvailable although AX text/input work; owner asked to click latest confirmation. No manual qualification or data repair.

Live Send section still instructs manual email sending, lacks shared exact-version group approval and loses letter count on filtered view. Native scheduler supports daily/weekly only; two 15-minute-spaced draft-only runs remain unimplemented/unaccepted. No current pilot email queued or sent. Final reply/channel/responsive/business-switch checks and complete expense reconciliation remain open.


## Automatic third draft and exact send review, 13 October

Dook task `d4b43860-d176-41f9-8085-462f962f39f3` now completed natively after explicit retry in the web chat. Same company, sources, expenses and task were preserved. The retry refreshes only unproven source workstreams within remaining checks, preserving old qualification history and ready companies. Dook qualified all three requirements using actually fetched company, India and Phuket-page-title evidence. Campaign `2dc6bd08-5df1-4f8c-838c-01cd6f772aea` generated a new text and passed native automatic quality review. Dook cumulative execution cost is three credits: initial check plus retry check plus one draft. Together with the approved Holiday retry, four of the owner's seven additional execution credits were consumed. Operator planning-command charges are separate and full reconciliation remains pending. The existing notification ledger records the Dook result delivered to Telegram; canonical full text was read in web chat.

Shared `outreach_send_review` now prepares exact current first-email review over existing campaigns; confirmation delegates to native approve_campaign and one existing send batch, atomically. Current user/business/groups, qualified contact, quality, campaign version/policy, complete text, recipient and sender are bound to the review hash. Native grants, source freshness, suppression and queue idempotency remain enforced. Multiple touches and duplicate selected first contacts are rejected. Existing Operator approval supplies replay protection; no direct provider send occurs in the service. Dedicated approval capability `partnerships.send_review` avoids the legacy search-credit confirmation renderer. Explicit send-preview commands route directly to this read operation, without copying historical texts or running a search.

Important newly reconciled historical evidence: Kingdom and Holiday already have native queue rows with provider_message_id, sent on 8 October (16:15 and 16:18 Moscow). These are accepted provider sends, not proof of inbox delivery. Their new drafts must NOT be sent as first contacts again. The new review rejects prior accepted, queued or uncertain first sends and prior replies/refusals. Read-only production check: Dook alone returns one pending send review; combined e361 plus Dook is blocked with first_contact_exists. No new current pilot email was queued or sent in this step.

124 targeted tests pass (read requests, source recovery, qualification, current group scope, exact send hash, business isolation, atomic rollback, no preview dispatch, first-contact evidence and distinct approval kind). Runtime files installed with compared live-file backups in the existing release directory. The temporary local checkout disappeared during interruption; restored from published branch and recovered only the new service from production, then reconstructed scoped changes without importing unrelated live core changes.

Final new-browser proof is NOT complete: the first preview exposed a legacy search-confirmation mismatch, corrected above. Subsequent browser/local HTTPS connections stalled during TLS handshake; DNS resolves to the expected 80.78.242.105, TCP connects, other HTTPS sites work, server HTTPS returns 200, nginx listens publicly, UFW inactive and INPUT/OUTPUT policies ACCEPT. No certificate checks, security protections, network settings or provider policy were weakened. Owner asked whether their ordinary browser can open LocalOS. UI handoff/rendering, Telegram button approval, two native 15-minute-spaced draft-only schedule runs, final narrow-screen/business-switch checks and full credit reconciliation remain open. Current native scheduler still supports daily/weekly only. No full outreach readiness claim.

### Telegram dispatch regression: explicit send review

A real Telegram request for the Dook send preview was intercepted by an unfinished clarification for another task and returned a false "no tool" response. Explicit send-review requests now dispatch before clarification/context routers. The shared action still validates actor permissions and the currently selected business; mentioning Riderra does not silently switch from Organika or expose another business's task. Added a regression executing the actual router with stale profile clarification and a different business. Targeted suite: 125 passed.

The update preserves the current production file's other changes and has a guarded before/after backup. Browser HTTPS still times out from the verification environment while the owner confirms the site opens normally and the server returns HTTP 200. Telegram UI verification was interrupted by a locked Mac; no send approval or email dispatch was performed.

After the dispatch fix the native Telegram request reached `partnerships.send_review`. The current Telegram scope was Organika (owner's concurrent content test), so the action was correctly denied rather than loading the Riderra task. Previously this denial rendered the misleading generic "Command processed". The review router now explains missing feature/business scope, direct-session/write permission, or Partnerships access without changing permissions. Choosing Riderra and confirming a fresh preview remains pending; no cross-business task or send was executed.

### Real Telegram send preview, 19:40 Moscow

Owner selected Riderra using the native business switcher. The real Telegram command `Покажи просмотр отправки задачи d4b43860-d176-41f9-8085-462f962f39f3` returned the canonical Dook recipient, sender, subject, full text, source, and separate approval notice. Screenshot saved at `/private/tmp/localos-dook-send-review.png` during acceptance. No message generation, provider call, or queue approval was performed by this check. Owner approval of this exact first email is pending. Native button clicking/scrolling still returns `noWindowsAvailable`; text-entry accessibility and screenshot observation work.
