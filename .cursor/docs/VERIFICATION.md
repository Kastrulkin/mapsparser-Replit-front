# Verification Log (Current)

Purpose: concise verification records after code or deploy changes.

## Baseline commands
```bash
docker compose ps
docker compose logs --since 5m app | tail -n 200
curl -I http://localhost:8000
```

## Entry template
```markdown
## YYYY-MM-DD — <task>

### Checks run
- `docker compose ps`
- `docker compose logs --since ... app`
- `curl -I http://localhost:8000`
- <feature-specific checks>

### Result
- ✅ / ❌

### Risks
- <if any>
```

## Recent entries

## 2026-02-24 — Rules cleanup verification

### Checks run
- Reviewed `README.md` vs `.cursor/rules/*.mdc` for runtime consistency.

### Result
- ✅ Rule set aligned to Docker/Postgres workflow.

### Risks
- Legacy instructions remain in git history and can be reintroduced manually if copied without review.
