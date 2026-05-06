# Problems

No unresolved blockers.

Known tradeoff: the queue and repeat-attempt memory are process-local because this stage intentionally avoids schema changes. A durable queue can be added in a later stage if jobs must survive app restarts.
