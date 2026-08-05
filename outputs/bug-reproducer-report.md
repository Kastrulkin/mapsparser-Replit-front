# Guided-tour deployment version mismatch

Status: **FIX_PROVEN**

## Report

The interactive demo displayed “Не удалось сохранить прогресс. Попробуйте ещё раз.” when the user started the tour on `https://localos.pro/demo`.

Expected: the deployed frontend and backend use the same guided-tour version and the first progress request succeeds.

Actual: production served frontend tour version `1`, while the backend required version `3`; the progress endpoint returned HTTP `409`.

## Root cause

The bind-mounted production directory `/opt/seo-app/frontend/dist` contained an older frontend build. This was a deployed-artifact mismatch, not browser cache.

## Reproduction

The approved checker [check_guided_tour_deploy_contract.py](/tmp/localos-demo-progress-20260805/scripts/check_guided_tour_deploy_contract.py) creates an isolated demo session, opens the deployed dashboard, captures the first progress request, and compares its tour version with the version advertised by the backend.

Before deployment:

```text
frontend_tour_version=1
backend_tour_version=3
```

## Fix

The current frontend was rebuilt from the version-3 source and synchronized to the bind-mounted production `frontend/dist` directory. Old hashed assets were retained for already-open tabs.

After deployment:

```text
frontend_tour_version=3
backend_tour_version=3
```

Production logs show the progress request returning HTTP `200` and guided-tour events returning HTTP `201`.

## Limitations and residual risk

The checker covers the deployed version contract and the first tour transition. It does not walk through all 31 steps. A future deployment that replaces `frontend/dist` from an older checkout will be detected when this checker is run.
