import { api } from '@/services/api';
import { shouldContinueAgentRunPolling } from './run-resume';
import type { AgentRun } from './types';

export function waitForPollInterval(milliseconds: number, signal?: AbortSignal): Promise<void> {
  signal?.throwIfAborted();
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(signal?.reason); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, milliseconds);
    signal?.addEventListener('abort', abort, { once: true });
  });
}

export async function pollAgentRun(runId: string, { signal, onRun, expectedBlueprintId, attempts = 600 }: {
  signal?: AbortSignal;
  onRun: (run: AgentRun) => void;
  expectedBlueprintId?: string;
  attempts?: number;
}): Promise<AgentRun | null> {
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    signal?.throwIfAborted();
    const response = await api.get(`/agent-runs/${runId}`, { signal });
    signal?.throwIfAborted();
    const run: AgentRun | null = response.data?.run && typeof response.data.run === 'object' ? response.data.run : null;
    if (expectedBlueprintId && (!run || run.blueprint_id !== expectedBlueprintId)) return null;
    if (run) {
      onRun(run);
      if (!shouldContinueAgentRunPolling(run)) return run;
    }
    await waitForPollInterval(1000, signal);
  }
  throw new Error('Агент продолжает работу дольше ожидаемого. Результат появится в истории после завершения.');
}
