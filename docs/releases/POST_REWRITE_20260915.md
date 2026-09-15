# Selected content-plan post rewriting

The Operator can generate a complete replacement for one selected unpublished plan item. `content.rewrite_item` reuses the social-post generator with the user's editorial brief, current draft and saved business/editorial context. `content.edit_item` also delegates explicit creative rewrite requests, so choosing the older tool does not require a verbatim finished post.

The saved draft keeps its item ID and publication date. Previous text is retained in `operator_edit_history`. Generation happens before mutation; malformed/empty output, unverified links, a stale version and provider failures preserve the existing draft. Published items are blocked. The ordinary chat request ledger handles replay; no second news row or publication is created.

Completed rewriting retains the selected item/version in channel conversation context for follow-ups such as “Короче”. A new recognized domain clears that context. `content.restore_item` restores previous text only on an explicit request and a fresh version. A missing booking URL is represented as `[ссылка для бронирования]`; the system does not invent one.

Tests cover six input combinations using simulated STT and generation, same-request replay, selected-post follow-up, the original “придумай” rejection, generation failure, invalid format, unverified URL, stale version, published protection and restoring previous text. Real iOS/Android and a user-approved production content replacement are not claimed by these tests.

Production rollout is a two-module partial update without a migration or a business-data edit. Evidence directory: `/tmp/post-rewrite/`; server staging `/opt/seo-app/.deploy/post-rewrite-20260915/`.
