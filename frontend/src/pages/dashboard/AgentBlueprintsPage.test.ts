import { describe, expect, it } from 'vitest';

import { shouldContinueAgentRunPolling } from './agents/run-resume';
import type { AgentRun } from './agents/types';

const queuedSheetWrite: AgentRun = {
  id: 'run-sheet-queued',
  blueprint_id: 'blueprint-1',
  status: 'waiting_provider',
  observability: {
    domain_requests: {
      items: [{ kind: 'google_sheets_update_cells', apply_state: 'provider_request_queued' }],
    },
  },
};

describe('agent run polling', () => {
  it('stops polling when the provider result needs a separate check', () => {
    expect(shouldContinueAgentRunPolling(queuedSheetWrite)).toBe(true);
    expect(shouldContinueAgentRunPolling({
      ...queuedSheetWrite,
      observability: {
        domain_requests: {
          items: [{ kind: 'google_sheets_update_cells', apply_state: 'provider_reconciliation_required' }],
        },
      },
    })).toBe(false);
    expect(shouldContinueAgentRunPolling({ ...queuedSheetWrite, status: 'approval_invalid' })).toBe(false);
    expect(shouldContinueAgentRunPolling({ ...queuedSheetWrite, status: 'running' })).toBe(true);
  });
});
