# Problems: supervised-outreach-integration-20260524

No open verifier findings.

Resolved during proof:
- First live smoke failed with `NO_APPROVED_DRAFTS`.
- Root cause: draft approval updates were still in the API transaction, while `outreach.send_batch` opened a separate DB connection and could not see them.
- Fix: commit approval side effects before continuing capability execution.
