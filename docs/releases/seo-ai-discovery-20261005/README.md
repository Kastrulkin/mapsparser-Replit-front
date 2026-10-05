# LocalOS search and AI discovery — 5 October 2026

Status: deployed and verified on production on 5 October 2026; seven priority URLs accepted into the Yandex recrawl queue at 16:42 Moscow time.

## Verified production evidence

- `https://localos.pro/` returns HTTP 200, Russian H1, product description, current prices (1,200 / 5,000 / 25,000 RUB monthly), visible case metrics, canonical URL and JSON-LD in the raw HTML. It does not require JavaScript to expose this text.
- Requests using YandexAdditionalBot and YandexBot User-Agents received readable HTML; the latter was checked on `/pricing`. These checks establish HTTP access, not actual visits by authenticated search-engine robots.
- `robots.txt` allows public crawling; sitemap and `llms.txt` are accessible. The primary module `/assets/index-65BWuS5m.js` returned 200 with JavaScript MIME type. An intentionally missing asset returned 404.
- In the owner's authenticated Yandex Webmaster: 64 loaded pages, 29 pages in search, no diagnostic errors, four recommendations. Homepage added to search on 1 October; pricing, two cases and contact added in the 5 October update. This disproves complete absence from Yandex search.
- Yandex Webmaster shows crawled and indexed `__localos_reload` variants. Recent crawl history contains many pricing variants with this parameter. It also reports five duplicate titles and four duplicate descriptions; the duplicate warning may have additional causes.
- An intentionally nonexistent `/seo-check-nonexistent-20261005` returned 200. Webmaster independently recommends correcting responses for nonexistent pages/files. Live application logs also show nonexistent PHP paths returning 200.
- External web retrieval sometimes failed and sometimes returned an older generic fallback for `/cases`, while a direct current HTTP request returned the case-specific body. Old indexed/cached content is a plausible contributor to the reported AI answer; the actual Alice conversation has not been reproduced.
- Compose services were running; app logs and local HTTP HEAD were inspected in the required order. These are targeted checks, not a full production health audit.

## Prepared correction

- `frontend/public/robots.txt`: add `User-agent: Yandex`, retain `Allow: /`, add `Clean-param: __localos_reload`. This consolidates recovery URLs without interfering with browser chunk recovery. All nine checked search/AI User-Agents remain allowed on the home, pricing, cases and llms paths.
- `src/core/public_page_html.py`: recognize current SPA entry routes, current published document routes, SEO-manifest routes and application/token routes. Public case fallbacks remain resolved before this check.
- `src/legacy_routes/core_public.py`: unknown URLs render the existing SPA with HTTP 404 and `X-Robots-Tag: noindex`; valid pages retain HTTP 200. Existing real-file and public-offer handling is preserved.
- `tests/test_public_route_html.py`: regression coverage for missing pages and preserved login, dashboard, documentation, published document and token routes.

Validation: 14 public HTML tests passed; 12 route tests also passed against the patched copy of the live backend. Patch application and Python syntax checks succeeded. No frontend source or bundle changed, so a frontend rebuild is unnecessary. The working tree already contains unrelated changes: deploy only the reviewed [live-source patch](seo-live.patch), not the whole local backend.

## Release and follow-through

Deployment requires approval under README's partial-deployment policy. Start all server commands with `cd /opt/seo-app`; use a named tmux session for deployment. Back up the two source files and robots files, check that the live source has not changed since preparation, apply the patch, sync only these source files and robots.txt into the active app paths, and restart only app. No database migration or data mutation is part of this change.

After release: verify Compose status, recent app logs, localhost HEAD, then public 200/404 responses and robots directives. Submit `/`, `/about`, `/pricing`, `/cases` and the three case pages for recrawl in Yandex Webmaster; confirm sitemap processing. The seven URLs were submitted and each visibly showed «В очереди» at 05.10.2026 16:42. Leave business region and Yandex Business registration for a separate factual decision rather than inventing an address or service region.

Search visibility is already established; appearance in Alice recommendations is still unverified. Recrawl and AI inclusion are not guaranteed by HTML, robots.txt or llms.txt changes. Recheck Alice with a fresh conversation and a direct URL request after indexing updates.

References: [Yandex Clean-param](https://yandex.ru/support/webmaster/en/robot-workings/clean-param), [Alice AI access restrictions](https://yandex.ru/support/webmaster/ru/adding-site/indexing-prohibition), [pages in Yandex search](https://yandex.ru/support/webmaster/ru/site-indexing/page-in-search). Product/source rules: `README.md`, `AGENTS.md`, `src/core/public_page_html.py`, `src/legacy_routes/core_public.py`.

## Production verification

User approved deployment and recrawl in this chat. Backup: `/opt/seo-app/backups/seo-ai-discovery-20261005T133918Z`. Only app was restarted. Sources under `/app/src` are a read-only bind mount of `/opt/seo-app/src`; the initial copy into that mount was rejected, then matching live hashes confirmed that host edits were already visible. Deployment completed by updating the second `/app/dist/robots.txt` copy and restarting app. No database changes occurred.

Live hashes:
- core_public.py: `3a9d680251b94972a4d3d836e1866d0742677cd77db4dd23afda66af8167e342`
- public_page_html.py: `e1cd42af0563ef69db2c0d539e6b507f69b3876f4b91c432ddfe5603070e5c2d`
- active robots.txt: `b2057f92a5dd22f1eb159cdd136c9ace4b868de044b2e383039ad828edfb996b`

Public-domain checks passed: home with YandexAdditionalBot UA contains H1 and current prices; missing page returns 404/noindex; robots.txt contains Clean-param; pricing, case, published document and login return 200. [Result record](evidence/production-result.json). Index refresh and actual Alice inclusion remain pending external processing.

Yandex Sitemap panel confirmed `sitemap.xml` status «ок», 27 links, last fetched 28 September. Requested a fresh sitemap crawl; allowance decreased from 10 to 9 and the submission button became disabled.
