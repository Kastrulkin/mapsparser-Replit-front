# Problems: shansik-partner-search

No unresolved verifier findings.

Resolved during the task:
- Geo-search candidates imported from Yandex were saved with misleading `source_provider=openclaw_google`; fixed and corrected the 17 created Shansik rows.
- Partnership lead cards displayed raw `yandex_maps`; fixed to show `Яндекс Карты`.
- Partnership geo-search form defaulted to Google Maps; changed default to Yandex Maps for this flow.
- `/api/partnership/health` returned 500 because it assumed tuple rows and a `business_id` column on `outreachsendbatches`; fixed with schema-compatible counters.
