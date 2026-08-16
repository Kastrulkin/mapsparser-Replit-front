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
