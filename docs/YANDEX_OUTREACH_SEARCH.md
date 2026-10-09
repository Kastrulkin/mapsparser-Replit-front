# Yandex Search API for outreach

Implemented using the synchronous REST endpoint https://searchapi.api.cloud.yandex.net/v2/web/search and XML output. No Maps, Apify, photos, reviews, generative search or smart snippets. International search is the default; YANDEX_SEARCH_TYPE can select another documented search type.

Yandex Search API is paid. It is never part of the Tavily/Exa free quota fallback. Existing configs remain unchanged. Selecting `web_search_provider: "yandex"` in an existing continuation preview creates a different approval revision and shows the paid-source warning. Changed providers create a new search rather than altering a saved group. The worker accepts the provider only through the existing approved config. No additional sending permission is granted.

Required deployment secrets (never put secrets in Git or chat):
- YANDEX_SEARCH_API_KEY: service-account API key with yc.search-api.execute scope.
- YANDEX_SEARCH_FOLDER_ID: folder with search-api.webSearch.user role granted to the service account.
- OUTREACH_WEB_SEARCH_ENABLED=true.
- YANDEX_SEARCH_PAID_REQUESTS_ENABLED=true: enable only after separate cost approval.

Pass these environment variables to app, worker and operator-worker using the existing production secret configuration; recreating the affected containers is required for environment changes. Keep the paid switch false until credentials and costs are approved. Connecting a SpeechKit or Wordstat key alone does not enable web search. No new service accounts or privileges are created by this patch.

The LocalOS preview continues to quote credits using the existing web-search billing contract; Yandex Cloud bills the operator separately per search request. Its quota is not a free allowance. No prepaid grant or remaining balance is inferred from an API key. Rate limits, access errors and unknown results are not retried or moved to another paid provider. Future actual provider-cost reconciliation remains separate from the existing fixed web-call credit price.

Documentation verified on 2026-10-09:
- https://aistudio.yandex.ru/en/docs/search-api/api-ref/WebSearch/search
- https://aistudio.yandex.ru/en/docs/search-api/pricing
- https://aistudio.yandex.ru/en/docs/search-api/api-ref/authentication

Verification: mocked REST headers/body, base64/XML parsing, snippets, domain deduplication, mandatory paid consent, rate-limit no-retry, malformed XML/entity rejection, approval revision change. Live searches are not verified because credentials and paid usage are not yet authorized.
