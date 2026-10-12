# Outreach chat release verification — 12 October 2026

The recurring UI rollback came from deploying the complete frontend built from stale local Operator sources. Production had a newer Operator source, but the local build still bundled the older page. Repeated reloads could not repair that release.

The current Operator components are restored in source control. The deployment script now checks the active entry module and its Operator dependencies, rather than accepting an unrelated new chunk left in assets. It also retains the existing Partnerships and sidebar guard. A local build with stale Partnerships is blocked, not published over production.

Telegram now receives the same continuation enable flag and business allowlist as the app. This restores native URL-import/research actions for already permitted businesses; it does not add sending rights.

Verified:
- Production frontend build and full navigation gate passed. Backup: /opt/seo-app/.release/outreach-finish-20261012/ui-before.tgz.
- Published entry: index-DTkbPRcH.js. Browser reload shows compact Operator, Tasks, task summary and composer.
- 360 and 390 px: composer within viewport; no horizontal overflow.
- Local frontend type check (`tsc --noEmit`) and build passed.
- Three gate regressions pass: current dependency graph, stale active chunk with unused new chunk, missing dependency.
- Actual Telegram URL command now returns native reviewed research conditions instead of missing-tool refusal.
- Actual web chat confirmed bounded Flamingo website research; native task 1b2fa8c1-33e6-4672-af05-fb077f2230db; no additional search or mail sending.

The live Flamingo task completed with 0 drafts and a source-research failure: OpenClaw returned no pages, with `openclaw_read_unavailable`. The failure was preserved; it was not treated as qualified evidence.

Acceptance remains open until research produces evidence and a canonical draft, Telegram completes its confirmation/result cycle, and two reviewed draft-only schedule runs complete. A successful build or preview is not full outreach acceptance. Keep Tavily free-mode guards; Exa and Yandex are not silently enabled. Never send generated pilot letters before exact-material user review.
