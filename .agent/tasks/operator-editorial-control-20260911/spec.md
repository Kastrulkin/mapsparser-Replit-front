# Operator editorial control
Implement general semantic tools shared by text/voice in all three channels: edit one planned post using dictated topic/brief; preview and confirm a changed editorial focus for an explicit plan/date range; save attributed company facts, founder story and tone for future generation. Examples are fixtures only, never production facts.

Backend enforces business access, current actor/tariff, quoted user source, schema limits, published/approved protection, versioned bulk approval, atomicity, idempotent chat transaction. Preserve original text in item history and previous plans. Missing/ambiguous target requires clarification; no invented successful mutation. Company memory must reach plan-post, standalone news and social prompts. Scope supports up to 20 plan edits per preview; larger requests ask for a narrower period.

Verify on isolated PostgreSQL with deterministic planner, plus read-only production source/import/HTTP checks and real semantic planning using stubbed mutation handlers. Do not create or mutate Riderra content during checks. Commit, push and selective deploy are authorized by prior conversation. No new schema intended.
