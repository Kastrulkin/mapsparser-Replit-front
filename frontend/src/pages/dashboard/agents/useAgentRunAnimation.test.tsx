import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAgentRunAnimation } from './useAgentRunAnimation';

describe('agent run animation lifecycle', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

  it('does not finish a newer run when the previous delay completes', async () => {
    const { result, unmount } = renderHook(() => useAgentRunAnimation(null));
    let startedAt = 0;
    act(() => { startedAt = result.current.beginRunAnimation('first', 'test'); });
    const finishing = result.current.finishRunAnimation(startedAt);
    await act(() => vi.advanceTimersByTimeAsync(1000));
    act(() => { result.current.beginRunAnimation('second', 'work'); });
    await act(() => vi.advanceTimersByTimeAsync(6000));
    await finishing;
    expect(result.current.runAnimation?.blueprintId).toBe('second');
    expect(result.current.runAnimation?.status).toBe('running');
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('cancels the finish delay on a scope change', async () => {
    const { result, unmount } = renderHook(() => useAgentRunAnimation(null));
    const controller = new AbortController();
    let startedAt = 0;
    act(() => { startedAt = result.current.beginRunAnimation('first', 'test'); });
    const finishing = result.current.finishRunAnimation(startedAt, controller.signal);
    const cancelled = expect(finishing).rejects.toMatchObject({ name: 'AbortError' });
    controller.abort();
    await cancelled;
    expect(result.current.runAnimation?.status).toBe('running');
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
