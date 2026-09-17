import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/services/api';
import { pollAgentRun, waitForPollInterval } from './run-polling';
import type { AgentRun } from './types';

vi.mock('@/services/api', () => ({ api: { get: vi.fn() } }));

const run = (status: string): AgentRun => ({ id: 'run-1', blueprint_id: 'blueprint-1', status });

describe('agent run polling', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.mocked(api.get).mockReset(); });
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

  it('returns the terminal result without another request', async () => {
    const onRun = vi.fn();
    vi.mocked(api.get).mockResolvedValueOnce({ data: { run: run('running') } });
    vi.mocked(api.get).mockResolvedValueOnce({ data: { run: run('completed') } });
    const result = pollAgentRun('run-1', { onRun });
    await vi.advanceTimersByTimeAsync(1000);
    await expect(result).resolves.toEqual(run('completed'));
    expect(onRun).toHaveBeenCalledTimes(2);
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('ignores an in-flight response after the view has been cancelled', async () => {
    const controller = new AbortController();
    const onRun = vi.fn();
    let complete: (value: { data: { run: AgentRun } }) => void = () => undefined;
    vi.mocked(api.get).mockImplementationOnce(() => new Promise(resolve => { complete = resolve; }));
    const result = pollAgentRun('run-1', { onRun, signal: controller.signal });
    expect(api.get).toHaveBeenCalledWith('/agent-runs/run-1', { signal: controller.signal });
    const cancelled = expect(result).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    complete({ data: { run: run('completed') } });
    await cancelled;
    expect(onRun).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('clears the pending interval on cancellation', async () => {
    const controller = new AbortController();
    const result = waitForPollInterval(1000, controller.signal);
    const cancelled = expect(result).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    await cancelled;
    expect(vi.getTimerCount()).toBe(0);
  });

  it('rejects a response from another blueprint without publishing it', async () => {
    const onRun = vi.fn();
    vi.mocked(api.get).mockResolvedValueOnce({ data: { run: run('completed') } });
    await expect(pollAgentRun('run-1', { onRun, expectedBlueprintId: 'different' })).resolves.toBeNull();
    expect(onRun).not.toHaveBeenCalled();
  });

  it('stops at an approval boundary instead of polling forever', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: { run: run('waiting_approval') } });
    await expect(pollAgentRun('run-1', { onRun: vi.fn() })).resolves.toEqual(run('waiting_approval'));
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
});
