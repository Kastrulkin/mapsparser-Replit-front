## 2026-01-21 - Fix Sync Worker Error Handling

### Current Task
Investigate why "Fallback" parsing tasks show as "Completed" (green status) but have no data in the "Progress" tab.

### Architecture Decision
- Modified `YandexBusinessSyncWorker.sync_account` to **re-raise exceptions**. Previously, it swallowed exceptions, causing the calling `worker.py` logic to assume success and mark the task as "completed".
- Added explicit `db.conn.commit()` after updating `MapParseResults` in `sync_account` to ensure data persistence.

### Files to Modify
- `src/yandex_business_sync_worker.py` - added `raise e` and `commit()`.

### Trade-offs & Decisions
- **Error Visibility**: Now, if a sync task fails (e.g., due to auth errors or timeouts), the UI will show an **Error** status instead of a misleading "Completed" status. This helps in debugging the root cause (auth failure, network, etc.).
- **Data Safety**: Explicit commit reduces the risk of data loss if the connection closes unexpectedly.

### Dependencies
- None.
- Requires restart of `worker.py`.

### Status
- [x] Completed
