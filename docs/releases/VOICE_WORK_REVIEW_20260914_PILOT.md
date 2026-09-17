# Riderra voice/work journal pilot

## 2026-09-14, 19:00–19:04 UTC — first scheduled check

Read-only production checks; no messages, business records, rights or configuration changed.

- All Compose services running; Telegram container healthy. App/worker now use the later organika image release. Pilot review, revision and journal flags still include Riderra.
- HTTP localhost and public HTTPS Operator: 200.
- Since activation (13:20 UTC): 0 Riderra async jobs, 0 chat requests, 0 new observations, 0 work-journal notification deliveries and 0 recorded operator_tool_plan/content_plan_direction calls. No available sample for latency, token averages, completion or clarification rate. Earlier generation probes are not user activity.
- Duplicate action idempotency keys: 0; duplicate observation request keys: 0. With no new activity, this is not evidence of successful real-use deduplication.
- Current retained logs (requested last 6h, bounded by container recreation): 144 tracebacks, 48 Telegram NetworkError occurrences with underlying connection/protocol/read errors. Last 30 minutes: 16 Telegram NetworkError occurrences. No successful getUpdates markers in retained log level; end-to-end receipt is unverified. Container health does not establish Telegram connectivity.
- DEEPSEEK_EMPTY_RESPONSE mentions: 0; content_plan_revision error mentions: 0.
- Physical iOS/Android, real customer sends and full control scenario: NOT RUN.

Attention: recurring Telegram transport errors can delay or interrupt bot input. Alert raised; this monitoring run is read-only and did not restart or alter services. Next check should compare the network-error count and incoming activity. No prior scheduled sample exists.

## 2026-09-15, 19:01–19:04 UTC — second scheduled check

Read-only production checks. Window for business activity: since the previous check, 2026-09-14 19:04 UTC.

- App, worker, operator-worker and Telegram bot running. Both workers have been up about four hours following the earlier authorized recovery. Local HTTP and public HTTPS return 200.
- Telegram transport problem has recurred: 133 NetworkError occurrences in the last hour and 31 polling errors in the last ten minutes. Bot health reports healthy, so the getMe probe does not establish reliable continuous getUpdates operation. 399 tracebacks reflect nested exception logging, not 399 separate lost messages. This is a new recurrence after the previously reported recovery.
- Five completed audio_transcription jobs (mean completion interval 4 seconds), five completed audio_speech jobs (mean 2 seconds); maximum attempts one. No recorded content_plan_revision jobs in this window.
- Five Telegram chat requests: two clarification_required, one denied, two completed. These are response statuses, not proof of successful requested edits. Latest request at 09:29:51 UTC; none after 15:00 UTC. The morning editing failures preceded the rewrite deployment/recovery, so no new user interaction validates that fix yet.
- Eleven completed operator_tool_plan calls: mean input 5,455 tokens, maximum 19,239, mean latency 1,638 ms. Mean falls within the control target, but the maximum still exceeds it. No comparison of like-for-like commands is available. Provider completion is not business-task completion.
- No new journal observations or journal notification deliveries. Duplicate action keys, observation keys and journal delivery keys: zero. Small/no mutation sample cannot establish full deduplication correctness.
- Last-hour logs: zero DEEPSEEK_EMPTY_RESPONSE and zero content_plan_revision error mentions.
- Physical iOS/Android and external customer sending remain NOT RUN; observed audio jobs do not identify a physical device.

Attention raised for recurring Telegram polling connectivity. Monitoring did not alter proxy settings, services, records, recipients or outbound actions. Seven-day pilot remains incomplete.

## 2026-09-16, 19:38–19:40 UTC — third scheduled check

Targeted read-only production checks. Business activity window: since 2026-09-15 19:04 UTC. No production records, permissions, plans, configuration or services changed by this monitoring run.

- App and operator-worker running after the separately authorized release; localhost HTTP and public HTTPS Operator return 200. General worker is stopped (exit 137); the active implementation task had already identified this as intentionally stopped by concurrent work. Monitoring did not restart it. An independent application job is running; it is not evidence of voice-pilot success.
- Telegram remains unavailable, as already reported immediately before this heartbeat. Bot is restarting/health starting rather than proving stable polling. Retained last-30-minute logs contain 64 NetworkError, 96 ConnectError and 46 TimedOut mentions, plus 165 traceback markers. These overlap in exception chains and are not separate lost-message counts; container recreation also bounds retained history. This is the same acknowledged proxy/SSH blocker, not a newly discovered incident. No repeat alert sent.
- Three completed audio_transcription jobs and three completed audio_speech jobs; each group mean completion interval 4 seconds, maximum attempts one. No content_plan_revision jobs in the window. Observed retained logs contain zero DEEPSEEK_EMPTY_RESPONSE and zero content_plan_revision mentions; absence of jobs limits the latter conclusion.
- Six web chat requests, all status completed. Latest retained Riderra request: 2026-09-16 09:19 UTC. These statuses do not by themselves establish requested business mutations or real-device operation. No later incoming Riderra activity validates the current evening release.
- One journal entry created in the window is already voided; no active new observation from that sample. No work-journal notification deliveries recorded. Duplicate action keys, observation keys and notification delivery keys: zero; the small/absent mutation sample cannot prove real-use deduplication reliability.
- 137 completed operator_tool_plan calls: mean input 4,244 tokens, maximum 20,193; mean latency 1,323 ms. Previous means were 5,455 tokens / 1,638 ms, but workload is not matched, so this is not a measured causal improvement. The maximum still exceeds the 3–6k control target.
- Content-plan direction: 19 GigaChat provider_terminal_error records and 19 completed DeepSeek records (mean input 741, maximum 771, mean latency 7,115 ms for completed calls). The permitted fallback is producing completed provider calls; aggregates alone do not establish that every requested plan was saved. Provider errors/fallback were already observed during the active repair work. Test/diagnostic generation cannot be separated reliably from organic usage by these aggregates, so do not attribute the 137/19 calls to six user requests.
- Physical iOS/Android, actual Telegram voice delivery and client-specific external sends remain NOT RUN. Seven-day pilot gate remains incomplete; final assessment due 21 September.

Aggregate results recorded quietly: known Telegram outage unchanged, no new actionable regression established by this targeted check.
