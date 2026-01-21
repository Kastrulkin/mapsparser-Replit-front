## 2026-01-21 - Fix Parser Data & DB Schema

### Current Task
Resolve missing data (products, reviews, rating) in parser results.

### Architecture Decision
1.  **DB Schema Update**: Added `products` column to `MapParseResults`.
    *   *Hotfix*: Applied via `sqlite3` CLI on server.
    *   *Formalization*: Created `src/migrate_add_products_to_map_parse_results.py`.
2.  **Parser Fix**: `YandexBusinessSyncWorker` now ensures `external_id` is passed to the parser (fixing missing reviews).
3.  **Logging**: Enabled unbuffered logging (`python -u`) in `run_worker.sh` for real-time debugging.

### Files to Modify
- `src/yandex_business_sync_worker.py` (Fixed `external_id` logic)
- `src/run_worker.sh` (Added `-u` flag)
- `src/migrate_add_products_to_map_parse_results.py` (New migration)

### Trade-offs & Decisions
- **Manual vs Migrations**: User correctly insisted on migrations. The new script ensures the change is reproducible for future deployments/dev environments.

### Dependencies
- None.

### Status
- [x] Completed
