# Mini App: historical email text repair

Status: `FIX_DEPLOYED`

## Result

The Mini App no longer depends on a technical reconciliation marker as recipient-visible text. The 39 affected «Весёлая расчёска» records now contain the verified school, kindergarten, or gymnasium email body. Their original reconciliation data remains in audit metadata.

## Evidence

- Gmail SENT contains normal messages from `localosgo@gmail.com`; the exact technical phrase is absent.
- LocalOS repaired 39 records: 17 schools, 18 kindergartens, and 4 gymnasiums.
- YouGile contains all 39 assigned follow-ups in `Второе касание`, due 29 August 2026.

## Red to green

```bash
cd frontend
npm test -- src/components/telegram/PartnershipsMobileModule.test.tsx
```

- Before: 1 failed, 4 passed. The historical marker was found in the email textarea.
- After: 5 passed.
- Targeted ESLint: passed.
- Frontend production build: passed.

## Release

- Source commit: `0ad685d8` (`fix: hide historical email markers in mini app`).
- Branch: `codex/content-generation-v2`.
- Built from an isolated clean worktree.
- Production deployment completed on 25 August 2026.
- Server checks passed: app container running, frontend integrity checks passed, and `http://localhost:8000` returned HTTP 200.
- The deployed asset `TelegramControlPage-CLa3a_QO.js` contains the safe user-facing status text.

## Production data safety

Backup: `/opt/seo-app/debug_data/veselaya-school-email-drafts-before-repair-20260825.csv`

SHA-256: `dca534da79f892263dbbecd13ce492a8634ff2cccea0dc522c31c7be455a4b06`

After repair: 0 visible markers, 39 preserved audit records, and all 39 queue items remain `sent`.

## Residual risk

The historical marker contract remains the detection boundary for future imported records. The affected records are repaired and the general Mini App guard is live in production.
