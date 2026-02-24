# Simplification Log (Current)

Purpose: record simplification/refactoring actions with measurable impact.

## Simplification policy
- Remove contradictory or obsolete instructions first.
- Keep runbooks short, executable, and environment-accurate.
- Prefer one canonical path over multiple competing variants.

## Entry template
```markdown
## YYYY-MM-DD — <task>

### Removed/condensed
- <what was removed>

### Kept canonical
- <what remains authoritative>

### Impact
- <clarity/speed/risk reduction>
```

## Recent entries

## 2026-02-24 — Documentation simplification (agent workflows)

### Removed/condensed
- Large outdated SQLite/systemd-first workflow instructions in active rule files.
- Contradictory deployment paths and legacy server paths.

### Kept canonical
- Docker Compose runtime
- PostgreSQL runtime DB
- `/opt/seo-app` as server path
- `README.md` as top-level source of truth

### Impact
- Reduced ambiguity during debugging/deploy.
- Lower risk of applying wrong (legacy) commands in production.
