# Problems: agent-product-compiler-20260609

No verifier findings.

Known follow-ups:
- `communications.send` is compiled into the capability allowlist but is not implemented in `ActionOrchestrator` yet.
- Existing production `AIAgents` rows are not migrated to blueprint-backed agents in this stage.
- UI can display attached voice, but selecting/changing `persona_agent_id` from the blueprint editor remains a follow-up.
