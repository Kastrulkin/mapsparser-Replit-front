## 2026-01-21 - Fix Missing Environment Variables (Local Debugging)

### Current Task
Diagnose why `worker.py` failed to decrypt auth tokens, leading to empty parser results.
User requested local debugging to find the cause.

### Architecture Decision
1.  **Local Reproduction**: Created `local_check_env.py` which confirmed that `src/worker.py` was NOT loading variables from `.env`.
2.  **Fix**: Added `from dotenv import load_dotenv; load_dotenv()` to:
    *   `src/worker.py` (Main entry point)
    *   `src/yandex_business_sync_worker.py` (Safety measure for direct usage)

### Files to Modify
- `src/worker.py`
- `src/yandex_business_sync_worker.py`
- Created temporary `local_check_env.py` and `.env` (will be ignored/deleted).

### Trade-offs & Decisions
- **Explicit Loading**: Relying on system environment variables is cleaner for containerization, but since we use `nohup python ...` and a `.env` file on the server, explicit `load_dotenv()` is required.

### Dependencies
- `python-dotenv` (already in requirements.txt).

### Status
- [x] Completed
