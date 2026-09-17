import type { AgentRun, AgentRunAnimation } from './types';
import { isAgentRunProviderPollingActive, sheetProviderAttentionState } from './model';

type AgentRunResumeState = {
  runId: string;
  blueprintId: string;
  kind: AgentRunAnimation['kind'];
  startedAt: number;
  storedAt: number;
};

const AGENT_RUN_RESUME_TTL_MS = 24 * 60 * 60 * 1000;

export const shouldContinueAgentRunPolling = (run?: AgentRun | null) => {
  const status = String(run?.status || '');
  if (status === 'waiting_provider') {
    return isAgentRunProviderPollingActive(run);
  }
  return ![
    'completed',
    'waiting_approval',
    'approval_invalid',
    'failed',
    'rejected',
    'superseded',
  ].includes(status);
};

export const isWaitingForProviderResult = (run?: AgentRun | null) => (
  String(run?.status || '') === 'waiting_provider' && !shouldContinueAgentRunPolling(run)
);

export const providerResultNotice = (run?: AgentRun | null) => (
  sheetProviderAttentionState(run) === 'provider_reconciliation_required'
    ? 'Запись могла выполниться; сверьте таблицу перед следующим запуском.'
    : 'Запись требует проверки. Откройте статус записи перед следующим запуском.'
);

const agentRunResumeStorageKey = (businessId: string) => `localos:agent-run-resume:${businessId}`;

export const readAgentRunResume = (businessId: string): AgentRunResumeState | null => {
  if (!businessId) return null;
  try {
    const raw = window.localStorage.getItem(agentRunResumeStorageKey(businessId));
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (
      !value
      || typeof value.runId !== 'string'
      || typeof value.blueprintId !== 'string'
      || !['test', 'work'].includes(String(value.kind || ''))
      || typeof value.startedAt !== 'number'
      || typeof value.storedAt !== 'number'
      || Date.now() - value.storedAt > AGENT_RUN_RESUME_TTL_MS
    ) {
      window.localStorage.removeItem(agentRunResumeStorageKey(businessId));
      return null;
    }
    return {
      runId: value.runId,
      blueprintId: value.blueprintId,
      kind: value.kind,
      startedAt: value.startedAt,
      storedAt: value.storedAt,
    };
  } catch {
    return null;
  }
};

export const saveAgentRunResume = (businessId: string, state: Omit<AgentRunResumeState, 'storedAt'>) => {
  if (!businessId || !state.runId || !state.blueprintId) return;
  try {
    window.localStorage.setItem(agentRunResumeStorageKey(businessId), JSON.stringify({ ...state, storedAt: Date.now() }));
  } catch {
    // A blocked storage API must not block the run itself.
  }
};

export const clearAgentRunResume = (businessId: string, expectedRunId = '') => {
  if (!businessId) return;
  try {
    if (expectedRunId) {
      const current = readAgentRunResume(businessId);
      if (current && current.runId !== expectedRunId) return;
    }
    window.localStorage.removeItem(agentRunResumeStorageKey(businessId));
  } catch {
    // The result remains available in server history even if storage cleanup fails.
  }
};
