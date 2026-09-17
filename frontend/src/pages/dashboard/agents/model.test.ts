import { describe, expect, it } from 'vitest';

import {
  buildEmployeePrimaryAction,
  buildEmployeeStatus,
  buildEmployeeWorkspaceState,
  buildEmployeeWorkspaceStory,
} from './model';
import type { AgentBlueprint, AgentBlueprintDetails } from './types';

const pausedScheduledAgent: AgentBlueprint = {
  id: 'agent-paused',
  business_id: 'business-1',
  name: 'Ежедневная сводка',
  category: 'operations',
  status: 'paused',
  active_version_id: 'version-1',
  active_version_number: 1,
  execution_mode: 'scheduled',
  lifecycle_state: 'paused',
};

const pausedDetails: AgentBlueprintDetails = {
  versions: [],
  runs: [],
  execution_mode: 'scheduled',
  lifecycle_state: 'paused',
  active_version_id: 'version-1',
};

describe('paused agent presentation', () => {
  it('does not present a paused schedule as working', () => {
    expect(buildEmployeeWorkspaceState(pausedScheduledAgent, pausedDetails)).toBe('paused');
    expect(buildEmployeeStatus(pausedScheduledAgent, pausedDetails)).toEqual({
      label: 'Пауза',
      tone: 'slate',
      summary: 'Автоматические запуски приостановлены.',
    });
  });

  it('keeps history available without promising another automatic run', () => {
    expect(buildEmployeePrimaryAction({
      blueprint: pausedScheduledAgent,
      details: pausedDetails,
    })).toMatchObject({
      kind: 'view_history',
      label: 'Открыть последний результат',
    });
    expect(buildEmployeeWorkspaceStory(pausedScheduledAgent, pausedDetails).nextWork)
      .toBe('Автоматические запуски приостановлены');
  });
});

describe('provider write presentation', () => {
  const waitingProviderAgent: AgentBlueprint = {
    ...pausedScheduledAgent,
    id: 'agent-sheets-write',
    status: 'active',
    lifecycle_state: 'active',
    last_run_status: 'waiting_provider',
  };
  const waitingProviderDetails: AgentBlueprintDetails = {
    ...pausedDetails,
    lifecycle_state: 'active',
    runs: [{
      id: 'run-sheets-write',
      blueprint_id: 'agent-sheets-write',
      status: 'waiting_provider',
      observability: {
        domain_requests: {
          items: [{
            kind: 'google_sheets_update_cells',
            approval_state: 'approved',
            apply_state: 'provider_request_queued',
          }],
        },
      },
    }],
  };

  it('keeps an approved write open until its provider result is known', () => {
    expect(buildEmployeeWorkspaceState(waitingProviderAgent, waitingProviderDetails)).toBe('waiting_provider');
    expect(buildEmployeeStatus(waitingProviderAgent, waitingProviderDetails)).toMatchObject({
      label: 'Ожидает записи',
      tone: 'amber',
    });
    expect(buildEmployeePrimaryAction({ blueprint: waitingProviderAgent, details: waitingProviderDetails })).toMatchObject({
      kind: 'open_result',
      label: 'Открыть статус записи',
    });
  });

  it('marks an unknown provider result as attention instead of a healthy wait', () => {
    const reconciliationDetails: AgentBlueprintDetails = {
      ...waitingProviderDetails,
      runs: [{
        ...waitingProviderDetails.runs[0],
        observability: {
          domain_requests: {
            items: [{
              kind: 'google_sheets_update_cells',
              approval_state: 'approved',
              apply_state: 'provider_reconciliation_required',
            }],
          },
        },
      }],
    };
    expect(buildEmployeeWorkspaceState(waitingProviderAgent, reconciliationDetails)).toBe('needs_attention');
    expect(buildEmployeePrimaryAction({ blueprint: waitingProviderAgent, details: reconciliationDetails })).toMatchObject({
      kind: 'open_result',
      label: 'Сверить таблицу',
    });
  });
});
