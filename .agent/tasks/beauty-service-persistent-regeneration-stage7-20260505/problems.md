# Problems

No unresolved blockers.

Known tradeoffs:
- Jobs and attempts are durable, but execution is still app-thread triggered. A dedicated worker consumer can pick up persisted queued jobs in a later stage.
- The service table shows the latest quality-history item inline. A full expandable history view is still future polish.
