# Public HTML without JavaScript

This change has a separate release boundary from the production-readiness audit.

## Released overlay — 2026-09-21

The isolated seven-route release was applied at 11:37 UTC and passed its
server-side verifier twice, both on localhost and `https://localos.pro` from the
production host. Release status is `success`; live container file hashes match
the payload. No database migration/data operation, image rebuild, full source
sync, Git pull, or container restart was performed. Gunicorn workers were
gracefully reloaded with HUP; app/PostgreSQL/worker/bot container identities and
StartedAt values remained unchanged. The previously unhealthy Telegram bot is
outside this release and remains a readiness issue.

Release directory: `/opt/seo-app/releases/public-seo-20260921`.
The directory holds the exact package, prestate, backup, verifier and status.
Package SHA-256:
`44d08d9aa32a2ee04dcefe2e800e7734c66f7b996daebc93503454e73008c04b`.
Manifest SHA-256:
`ec2894114b616b4c6e49a2f54cbcf75d2c9720e4439e1120d1aeae58765ba559`.

The overlay adds `public-seo-index.html` and the
`/seo-assets-20260921/index-CL92rNRc.js` public bundle. The original private
`index.html`, `/assets/index-BmALpHaF.js`, articles, and all 633 protected files
remain byte-identical. Only two Python files and the allowlisted public static
files are activated. Production Git HEAD was not moved from
`c728015c95e47880120c025deed70c6c88657963`; a source commit is not the deployed
revision of the full audit branch.

`publicShell: "public-seo-index.html"` explicitly opts the fallback manifest
into this sidecar. A future normal build omitting that field uses its normal
index, even if the old sidecar still exists. Public-to-private navigation in
the isolated bundle performs a document navigation to the preserved old entry.
The source/build snapshot is in `outputs/seo-public-release-20260921/`.
Do not deploy the whole audit branch or copy a sibling article branch over it.

Release checks: candidate renderer 12/12, main-workspace renderer/fallback
14/14, candidate and main frontend 6/6, Vite build and both private/public
artifact integrity checks pass. The old production source baseline and the
candidate have exactly the same 87 TypeScript diagnostics: zero added errors,
not a claim that the production snapshot is TypeScript-clean. Test-harness
environment failures are retained separately from final green captures.
The current main workspace separately passes both app/tooling TypeScript and
scoped ESLint with empty diagnostics (`main-quality-final.json`). This is not
the old production source baseline used to isolate the overlay.

Final in-app localhost preview: all seven routes with JavaScript and all seven
with scripts blocked, matching single H1s, working original login/article
entry boundaries and restored `/demo` CTA. Mobile pricing at 390×844 has no
horizontal overflow in either mode. Two reproduced release parity defects
(home heading and demo CTA) were fixed with red/green tests. This followed the
bug-reproducer evidence discipline; neither changed the published product flow.

Post-deploy browser verification from this Mac remains incomplete: the IAB
navigation timed out, and a separate HTTPS HEAD timed out during TLS. No network
or browser security settings were changed. Server-host HTTPS checks and the
exact-byte localhost browser preview pass; they do not replace an external
browser check. Indexing and rankings are not asserted.

## Contract

The homepage, `/about`, `/pricing`, `/cases` and the three published case pages
return their own visible heading, text, links, title and description before
JavaScript runs. React still owns the interactive page after loading. There is
no hidden crawler-only block, user-agent switch or claim of guaranteed indexing.

The Vite build emits `frontend/dist/public-page-fallbacks.json` from
`frontend/src/content/publicPageFallbacks.ts`, reusing the existing public case,
product-story and subscription copy. `src/core/public_page_html.py` validates
and escapes that data; `src/legacy_routes/core_public.py` inserts it into the
visible fallback inside `#root`, keeping the generated scripts intact.

Unknown/private routes and existing article metadata retain their previous
behavior. Missing or invalid manifests retain the previous SPA shell, so an old
frontend build remains compatible. Known public pages bypass the database-backed
offer-slug lookup. There are no migrations or changes to business data.

The current published plans are 1,200 / 5,000 / 25,000 RUB per month. The supplied
claims of “+170% in three months” and “from 15,000 RUB” are not added. Existing
published case text is reused without new metrics or independent-verification
claims. External actions continue to require human approval. The existing Elite
commercial copy is not changed by this technical SEO work.

## Verification and release boundary

Focused renderer checks do not start the application or connect to a database:

```bash
PYTHONPATH=src:. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest --noconftest -q tests/test_public_route_html.py tests/test_public_html_fallback.py
```

Build with the existing frontend workflow and run
`scripts/verify_frontend_dist_integrity.sh frontend/dist`. The release needs both
the frontend build and the two backend files above. Updating source HTML alone,
or deploying only the frontend, does not enable per-route server body rendering.
These general instructions are not deployment approval; actual release evidence
is identified separately at the top of this document.
The working branch also contains unreleased audit work: a deployment must first
isolate this change against the actual production revision. Do not publish the
whole branch or sync the dirty source tree as part of this SEO change.

On the released site, check the raw responses for every listed route, the
robots/sitemap responses and referenced assets; then verify the same pages with
JavaScript disabled and enabled. A readable HTML response improves accessibility
to crawlers but does not prove ranking or recommendations by an AI assistant.
See [Google's JavaScript guidance](https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics).

## Historical local verification — before isolated release

- Renderer and existing fallback tests: **13 passed**. Tests exercise the actual
  extracted route functions with isolated Flask fixtures, not full application startup.
- Frontend: **4 tests passed**, TypeScript passed, scoped ESLint **0 errors / 0
  warnings**, production build passed. The build still reports the existing
  third-party Yandex Maps `PURE`-annotation warnings.
- Built artifact integrity: **200 reachable JavaScript files** checked. Seven
  local raw HTTP responses contain their own headings, metadata, text and
  canonical links, with published case metrics where applicable; 10 directly referenced assets, robots and
  sitemap checks passed. The emitted logo matches the original image bytes.
- In-app browser: **7/7 routes with scripts blocked and 7/7 with scripts enabled**.
  Each has one H1 and readable content; React replaces the fallback successfully.
  The check used Russian content. English and other locale variants were not
  exhaustively tested.
- Desktop fallback and mobile pricing screenshots were visually checked. At a
  390 × 844 viewport, both pricing modes had content width equal to the document
  width (375 px excluding the scrollbar), with no horizontal overflow.
- Captured browser logs contained no warnings/errors; all 183 observed JS/CSS
  asset responses were 200 or 304. The isolated preview returns synthetic API
  errors (including tracking POST 405); it does not exercise billing, accounts,
  database connectivity or production middleware.

The browser preview used the real build and renderer, bound only to
`127.0.0.1:48731`, with outbound connections, database/application imports and
environment-file reads prohibited. The no-script mode used a response CSP
`script-src 'none'`; browser-wide settings were not changed. Its first startup
was stopped by the environment-file guard; disabling Flask's automatic dotenv
loading fixed the preview harness without weakening the guard. The preview was
stopped after verification.

Reproduction evidence distinguishes harness failures from product failures:
the corrected baseline produced 7 expected failures / 3 passes; the public-route
offer-lookup regression produced 1 failure / 10 passes before its fix. An earlier
fixture endpoint naming error and the initial preview connection failure are not
counted as product regressions.

Local captures are in `/private/tmp/localos-public-html-20260921.3ut9JF/`
(`causal-red.json`, `route-red.json`, `release-green.json`,
`built-http-assets-final.json`), with frontend output at
`/private/tmp/public-manifest-freeze.log`. Final manifest SHA-256:
`6989c60a9a76e7a8984014c02c362bf6aa6a7e75fe44b19556f59335a5dcc5e7`.

At this historical checkpoint, the 13 pre-existing foreign worktree files, three protected audit records and
the paused audit's unexecuted draft test were preserved. **No commit, push or
production deployment had been performed for this SEO change.** The released
overlay and its newer evidence are described at the top of this document.
