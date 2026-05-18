# Problems: p1-p2-cleanup-main-lint-20260518

No verifier findings for this pass.

Known non-blocking notes:
- Full `main.py` decomposition remains future work.
- Live `py_compile` cannot write `__pycache__` under read-only `/app/src`; live syntax proof uses `ast.parse`.
- `EXTERNAL_AUTH_SECRET_KEY` remains a separate blocker in `p1-security-smoke-20260518`.
