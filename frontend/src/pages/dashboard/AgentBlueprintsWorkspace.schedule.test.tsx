import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Suspense } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  blueprintOneDetailRequests: 0,
  dashboardContext: {
    currentBusinessId: 'business-1',
    currentBusiness: { id: 'business-1', name: 'Тестовый бизнес' },
    demoMode: false,
  },
}));

type WorkspaceHarnessScope = {
  workspaceMode: string;
  setWorkspaceMode: (mode: string) => void;
  selectedBlueprint: { id: string } | null;
  setSelectedBlueprintId: (id: string) => void;
  blueprintDetails: {
    blueprint?: { id?: string };
    candidate_version_id?: string;
    execution_contract?: {
      candidate?: { schedule?: { time?: string; timezone?: string } };
      active?: { schedule?: { time?: string; timezone?: string } };
    };
  } | null;
  loadBlueprintDetails: (id: string) => Promise<void>;
  scheduleTime: string;
  setScheduleTime: (value: string) => void;
  scheduleTimezone: string;
  setScheduleTimezone: (value: string) => void;
  selectedExecutionMode: 'one_off' | 'manual' | 'scheduled';
  setSelectedExecutionMode: (mode: 'one_off' | 'manual' | 'scheduled') => void;
  actionLoading: boolean;
  saveExecutionMode: () => void;
};

vi.mock('@/i18n/LanguageContext.logic', () => ({
  useLanguage: () => ({ language: 'ru' }),
}));

vi.mock('@/lib/auth_new', () => ({
  newAuth: {
    getCurrentUserSync: () => null,
    getCurrentUser: async () => null,
    getToken: () => null,
  },
}));

vi.mock('@/lib/browserSessionFetch', () => ({
  browserAuthenticationAvailable: () => false,
}));

vi.mock('@/services/api', () => ({
  api: mocks,
}));

vi.mock('react-router-dom', () => ({
  useLocation: () => ({ search: '' }),
  useOutletContext: () => mocks.dashboardContext,
}));

vi.mock('./agents/useAgentRunAnimation', () => ({
  useAgentRunAnimation: () => ({
    runAnimation: null,
    setRunAnimation: () => undefined,
    beginRunAnimation: () => undefined,
    finishRunAnimation: () => undefined,
    failRunAnimation: () => undefined,
    syncRunAnimation: () => undefined,
  }),
}));

vi.mock('./agents/useAgentRunTracking', () => ({
  useAgentRunTracking: () => ({
    waitForAgentRun: async () => undefined,
  }),
}));

vi.mock('./agents/view', async () => {
  const { AgentExecutionModePanel } = await import('./agents/employee');
  return {
    AgentBlueprintsView: ({ scope }: { scope: WorkspaceHarnessScope }) => (
      <section>
        <button type="button" onClick={() => scope.setWorkspaceMode('settings')}>Открыть настройки</button>
        <button type="button" onClick={() => scope.setSelectedBlueprintId('blueprint-2')}>Выбрать второй сценарий</button>
        <button type="button" onClick={() => scope.selectedBlueprint && scope.loadBlueprintDetails(scope.selectedBlueprint.id)}>Обновить детали</button>
        <output data-testid="workspace-mode">{scope.workspaceMode}</output>
        <output data-testid="schedule-time">{scope.scheduleTime}</output>
        <output data-testid="schedule-timezone">{scope.scheduleTimezone}</output>
        <output data-testid="details-revision">{scope.blueprintDetails?.candidate_version_id || ''}</output>
        <output data-testid="loaded-blueprint-id">{scope.blueprintDetails?.blueprint?.id || ''}</output>
        {scope.workspaceMode === 'settings' ? (
          <AgentExecutionModePanel
            mode={scope.selectedExecutionMode}
            confirmationRequired={false}
            time={scope.scheduleTime}
            timezone={scope.scheduleTimezone}
            actionLoading={scope.actionLoading}
            onModeChange={scope.setSelectedExecutionMode}
            onTimeChange={scope.setScheduleTime}
            onTimezoneChange={scope.setScheduleTimezone}
            onSave={scope.saveExecutionMode}
          />
        ) : null}
      </section>
    ),
  };
});

import { AgentBlueprintsWorkspace } from './AgentBlueprintsWorkspace';

describe('AgentBlueprintsWorkspace schedule hydration', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(() => {
      throw new Error('unexpected network');
    }));
    mocks.post.mockReset();
    mocks.post.mockResolvedValue({ data: {} });
    mocks.blueprintOneDetailRequests = 0;
    mocks.get.mockReset();
    mocks.get.mockImplementation(async (url: string) => {
      if (url === '/agent-blueprints') {
        return {
          data: {
            blueprints: [{
              id: 'blueprint-1',
              business_id: 'business-1',
              name: 'Scenario agent',
              category: 'operations',
              status: 'draft',
              metadata_json: {
                custom_process: {
                  schedule: { time: '09:00', timezone: 'Europe/Moscow' },
                },
              },
            }, {
              id: 'blueprint-2',
              business_id: 'business-1',
              name: 'Active schedule agent',
              category: 'operations',
              status: 'draft',
              execution_mode: 'scheduled',
              metadata_json: {},
            }],
          },
        };
      }
      if (url === '/agent-blueprints/blueprint-1') {
        mocks.blueprintOneDetailRequests += 1;
        return {
          data: {
            blueprint: { id: 'blueprint-1', business_id: 'business-1' },
            versions: [],
            runs: [],
            approval_queue: [],
            candidate_version: { id: `candidate-${mocks.blueprintOneDetailRequests}` },
            candidate_version_id: `candidate-${mocks.blueprintOneDetailRequests}`,
            execution_mode: 'scheduled',
            execution_contract: {
              candidate: {
                schedule: {
                  time: '18:00',
                  timezone: 'Europe/Moscow',
                },
              },
            },
          },
        };
      }
      if (url === '/agent-blueprints/blueprint-2') {
        return {
          data: {
            blueprint: { id: 'blueprint-2', business_id: 'business-1' },
            versions: [],
            runs: [],
            approval_queue: [],
            execution_mode: 'scheduled',
            execution_contract: {
              active: {
                schedule: {
                  time: '17:00',
                  timezone: 'Europe/Moscow',
                },
              },
            },
          },
        };
      }
      return { data: {} };
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('uses the selected candidate schedule when opening settings without saving', async () => {
    const user = userEvent.setup();

    render(<Suspense fallback={<div>Загрузка</div>}><AgentBlueprintsWorkspace /></Suspense>);

    await screen.findByTestId('schedule-time');
    await user.click(screen.getByRole('button', { name: 'Открыть настройки' }));

    await waitFor(() => expect(screen.getByTestId('workspace-mode')).toHaveTextContent('settings'));
    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('18:00'));
    expect(screen.getByTestId('schedule-timezone')).toHaveTextContent('Europe/Moscow');
    expect(screen.getByDisplayValue('18:00')).toHaveAttribute('type', 'time');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('uses the active schedule only when the selected candidate is absent', async () => {
    const user = userEvent.setup();

    render(<Suspense fallback={<div>Загрузка</div>}><AgentBlueprintsWorkspace /></Suspense>);

    await screen.findByTestId('schedule-time');
    await user.click(screen.getByRole('button', { name: 'Выбрать второй сценарий' }));
    await user.click(screen.getByRole('button', { name: 'Открыть настройки' }));

    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('17:00'));
    expect(screen.getByDisplayValue('17:00')).toHaveAttribute('type', 'time');
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('shows the selected legacy schedule while matching details are still deferred', async () => {
    let resolveDetails: (response: { data: Record<string, unknown> }) => void = () => undefined;
    const deferredDetails = new Promise<{ data: Record<string, unknown> }>((resolve) => {
      resolveDetails = resolve;
    });
    mocks.get.mockImplementation(async (url: string) => {
      if (url === '/agent-blueprints') {
        return {
          data: {
            blueprints: [{
              id: 'blueprint-1',
              business_id: 'business-1',
              name: 'Deferred schedule agent',
              category: 'operations',
              status: 'draft',
              metadata_json: {
                custom_process: {
                  schedule: { time: '11:00', timezone: 'Europe/Moscow' },
                },
              },
            }],
          },
        };
      }
      if (url === '/agent-blueprints/blueprint-1') {
        return deferredDetails;
      }
      return { data: {} };
    });

    render(<Suspense fallback={<div>Загрузка</div>}><AgentBlueprintsWorkspace /></Suspense>);

    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('11:00'));
    resolveDetails({
      data: {
        blueprint: { id: 'blueprint-1', business_id: 'business-1' },
        versions: [],
        runs: [],
        approval_queue: [],
        execution_mode: 'scheduled',
        execution_contract: {
          candidate: { schedule: { time: '18:00', timezone: 'Europe/Moscow' } },
        },
      },
    });
    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('18:00'));
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('keeps the selected blueprint schedule when stale details from the prior selection arrive', async () => {
    const user = userEvent.setup();
    let resolveFirstDetails: (response: { data: Record<string, unknown> }) => void = () => undefined;
    const deferredFirstDetails = new Promise<{ data: Record<string, unknown> }>((resolve) => {
      resolveFirstDetails = resolve;
    });
    mocks.get.mockImplementation(async (url: string) => {
      if (url === '/agent-blueprints') {
        return {
          data: {
            blueprints: [{
              id: 'blueprint-1', business_id: 'business-1', name: 'First', category: 'operations', status: 'draft', metadata_json: {},
            }, {
              id: 'blueprint-2', business_id: 'business-1', name: 'Second', category: 'operations', status: 'draft', metadata_json: {},
            }],
          },
        };
      }
      if (url === '/agent-blueprints/blueprint-1') {
        return deferredFirstDetails;
      }
      if (url === '/agent-blueprints/blueprint-2') {
        return {
          data: {
            blueprint: { id: 'blueprint-2', business_id: 'business-1' }, versions: [], runs: [], approval_queue: [], execution_mode: 'scheduled',
            execution_contract: { active: { schedule: { time: '17:00', timezone: 'Europe/Moscow' } } },
          },
        };
      }
      return { data: {} };
    });

    render(<Suspense fallback={<div>Загрузка</div>}><AgentBlueprintsWorkspace /></Suspense>);
    await screen.findByTestId('schedule-time');
    await user.click(screen.getByRole('button', { name: 'Выбрать второй сценарий' }));
    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('17:00'));

    resolveFirstDetails({
      data: {
        blueprint: { id: 'blueprint-1', business_id: 'business-1' }, versions: [], runs: [], approval_queue: [], execution_mode: 'scheduled',
        execution_contract: { candidate: { schedule: { time: '18:00', timezone: 'Europe/Moscow' } } },
      },
    });
    await waitFor(() => expect(screen.getByTestId('loaded-blueprint-id')).toHaveTextContent('blueprint-1'));
    await waitFor(() => expect(screen.getByTestId('schedule-time')).toHaveTextContent('17:00'));
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it('keeps an unsaved settings edit when matching blueprint details refresh', async () => {
    const user = userEvent.setup();

    render(<Suspense fallback={<div>Загрузка</div>}><AgentBlueprintsWorkspace /></Suspense>);

    await screen.findByTestId('schedule-time');
    await user.click(screen.getByRole('button', { name: 'Открыть настройки' }));
    const input = await screen.findByDisplayValue('18:00');
    fireEvent.change(input, { target: { value: '19:00' } });
    expect(screen.getByDisplayValue('19:00')).toBeVisible();
    const revisionBeforeRefresh = screen.getByTestId('details-revision').textContent;

    await user.click(screen.getByRole('button', { name: 'Обновить детали' }));

    await waitFor(() => expect(screen.getByTestId('details-revision')).not.toHaveTextContent(revisionBeforeRefresh || ''));
    await waitFor(() => expect(screen.getByDisplayValue('19:00')).toBeVisible());
    expect(mocks.post).not.toHaveBeenCalled();
  });
});
