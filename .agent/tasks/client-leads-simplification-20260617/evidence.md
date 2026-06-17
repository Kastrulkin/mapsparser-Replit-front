# Evidence Bundle: client-leads-simplification-20260617

## Summary
- Overall status: PASS
- Last updated: 2026-06-17T16:25:00+00:00

## Acceptance criteria evidence

### AC1
- Status: PASS
- Proof:
  - `frontend/src/components/ProspectingManagement.tsx` renderKanbanCard now renders name/category/city/address, source/rating, one `leadHumanStatus` badge, and one computed primary action.
  - Contact/audit/room badge stacks were removed from the lead card first layer.
- Gaps:
  - Visual QA is via build/static review in this pass; no browser screenshot artifact captured yet.

### AC2
- Status: PASS
- Proof:
  - Added `roomPreparationLead` state and `Dialog` titled `Подготовить цифровую комнату`.
  - Dialog offers `Подготовить данные и создать комнату` and `Создать комнату без подготовки`, with copy `Подготовка данных расходует кредиты.`
- Gaps:
  - None known.

### AC3
- Status: PASS
- Proof:
  - `ProspectingPipelineHeader` now exposes search, quick filters, `Фильтры`, `Добавить лиды`, and kanban/list controls only.
  - Source and channel controls were removed from first-layer header; existing filter drawer remains.
- Gaps:
  - None known.

### AC4
- Status: PASS
- Proof:
  - Added simplified column order with four columns: `needs_action`, `preparing_offer`, `contacted`, `replied`.
  - Kanban now maps over `simplifiedPipelineBoardColumns`.
- Gaps:
  - Postponed/not relevant/converted are hidden from the default kanban unless the detailed status filter is used.

### AC5
- Status: PASS
- Proof:
  - Bulk select row and sticky bulk action bar render only when `pipelineView === 'list'`.
- Gaps:
  - None known.

### AC6
- Status: PASS
- Proof:
  - `npm --prefix frontend run build` passed.
  - `git diff --check -- frontend/src/components/ProspectingManagement.tsx frontend/src/components/prospecting/ProspectingWorkspaceChrome.tsx` passed.
- Gaps:
  - Browserslist and Rollup third-party warnings remain pre-existing/non-blocking.

## Commands run
- `npm --prefix frontend run build 2>&1 | tee .agent/tasks/client-leads-simplification-20260617/raw/build.txt`
- `git diff --check -- frontend/src/components/ProspectingManagement.tsx frontend/src/components/prospecting/ProspectingWorkspaceChrome.tsx`

## Raw artifacts
- .agent/tasks/client-leads-simplification-20260617/raw/build.txt
- .agent/tasks/client-leads-simplification-20260617/raw/test-unit.txt
- .agent/tasks/client-leads-simplification-20260617/raw/test-integration.txt
- .agent/tasks/client-leads-simplification-20260617/raw/lint.txt
- .agent/tasks/client-leads-simplification-20260617/raw/screenshot-1.png

## Known gaps
- No backend changes or DB changes were required.
- Browser screenshot artifact has not been captured yet; live deploy verification will check the served bundle after deployment.
