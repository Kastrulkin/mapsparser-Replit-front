# Free-only outreach discovery

Outreach defaults to web search. Maps requires explicit search_source=maps, a separate cost warning and a fresh policy-version approval. Existing Maps results and receipts are retained. No provider is enabled by the presence of a key alone.

Provider order: Tavily -> Exa, switching only after explicit credit exhaustion. 429 rate limits, authentication failures, timeouts and unknown responses stop the request; empty successful results do not trigger a second provider.

Activation requires TAVILY_API_KEY / EXA_API_KEY, OUTREACH_WEB_SEARCH_ENABLED=true and per-provider TAVILY_FREE_ONLY_VERIFIED=true / EXA_FREE_ONLY_VERIFIED=true. Verify the account in the provider dashboard before setting the attestation: free plan, no paid overage, no automatic payment/refill. Do not enter secrets in chat, commit them, or print them in logs. Add variables to the existing deployment secret configuration and pass them explicitly to app, worker and operator-worker; an env file alone does not inject variables into Docker services.

Tavily checks /usage before each basic search, rejects paid/unverified plans and any nonzero paygo_limit. Exa has no free-balance endpoint integrated: its free-only account setting is a required operator verification. It stops with HTTP 402 when exhausted. Do not activate Exa on a paid account by merely setting the attestation. Neither provider is upgraded automatically. After monthly quota renewal the user can explicitly continue the saved task; quota renewal does not resume work automatically.

Only Search endpoints are called: no Maps, images, paid deep research, contact enrichment or summaries. Results are unqualified candidates with source provenance, not verified companies/contacts. Existing enrichment and qualification remain responsible for evidence. Existing LocalOS credits for execution/checks/drafts are separate from provider free API quotas.

Validation: 19 deterministic adapter/routing tests; real search remains unverified until credentials are configured. No external search, provider spending, letter generation or sends in this verification.
