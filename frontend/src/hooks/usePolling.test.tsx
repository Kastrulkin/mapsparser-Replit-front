import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePolling } from './usePolling';

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); });

  it('waits for the previous request before scheduling another', async () => {
    let resolve: (value: string) => void = () => undefined;
    const request = vi.fn(() => new Promise<string>((done) => { resolve = done; }));
    const onResult = vi.fn();
    const { unmount } = renderHook(() => usePolling({ enabled: true, scopeKey: 'a', intervalMs: 1000, request, onResult }));
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(request).toHaveBeenCalledTimes(1);
    await act(async () => { resolve('ready'); });
    expect(onResult).toHaveBeenCalledWith('ready');
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(request).toHaveBeenCalledTimes(2);
    unmount();
  });

  it('aborts and ignores a late response from a previous business', async () => {
    const results: string[] = [];
    let completeOld: (value: string) => void = () => undefined;
    let oldSignal: AbortSignal | undefined;
    const { rerender, unmount } = renderHook(({ scopeKey }) => usePolling({
      enabled: true, scopeKey, intervalMs: 1000, immediate: true,
      request: (signal) => scopeKey === 'old'
        ? new Promise<string>((resolve) => { completeOld = resolve; oldSignal = signal; })
        : Promise.resolve('new'),
      onResult: (result) => results.push(result),
    }), { initialProps: { scopeKey: 'old' } });
    await act(async () => rerender({ scopeKey: 'new' }));
    expect(oldSignal?.aborted).toBe(true);
    await act(async () => completeOld('old'));
    expect(results).toEqual(['new']);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('uses updated callbacks without restarting the polling clock', async () => {
    const seen: number[] = [];
    const { rerender, unmount } = renderHook(({ value }) => usePolling({
      enabled: true, scopeKey: 'same', intervalMs: 1000,
      request: async () => value, onResult: (result) => seen.push(result),
    }), { initialProps: { value: 1 } });
    await act(() => vi.advanceTimersByTimeAsync(500));
    rerender({ value: 2 });
    await act(() => vi.advanceTimersByTimeAsync(500));
    expect(seen).toEqual([2]);
    unmount();
  });

  it('does not report failures or restart after being disabled', async () => {
    let reject: (reason: Error) => void = () => undefined;
    const onError = vi.fn();
    const { rerender } = renderHook(({ enabled }) => usePolling({
      enabled, scopeKey: 'a', intervalMs: 1000, immediate: true,
      request: () => new Promise<string>((_, fail) => { reject = fail; }),
      onResult: vi.fn(), onError,
    }), { initialProps: { enabled: true } });
    rerender({ enabled: false });
    await act(async () => reject(new Error('late')));
    expect(onError).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });
});
