import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useApiData } from './useApiData';

vi.mock('@/lib/browserSessionFetch', () => ({ browserBearerToken: () => 'test-token' }));
const response = (name: string) => new Response(JSON.stringify({ success: true, data: { name } }), {
  headers: { 'Content-Type': 'application/json' },
});

describe('useApiData scope isolation', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('ignores a late response after changing business, even when the endpoint is unchanged', async () => {
    let completeOld: (value: Response) => void = () => undefined;
    const fetchMock = vi.fn()
      .mockImplementationOnce(() => new Promise<Response>(resolve => { completeOld = resolve; }))
      .mockResolvedValueOnce(response('new business'));
    vi.stubGlobal('fetch', fetchMock);
    const seen = vi.fn();
    const { result, rerender } = renderHook(({ scope }) => useApiData<{ name: string }>('/api/current', {
      dataScopeKey: scope, keepPreviousData: true, onSuccess: seen,
    }), { initialProps: { scope: 'old' } });
    rerender({ scope: 'new' });
    await waitFor(() => expect(result.current.data?.name).toBe('new business'));
    await act(async () => { completeOld(response('old business')); });
    expect(result.current.data?.name).toBe('new business');
    expect(seen).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not refetch merely because a parent rendered a new options object', async () => {
    const fetchMock = vi.fn().mockResolvedValue(response('same business'));
    vi.stubGlobal('fetch', fetchMock);
    const { result, rerender } = renderHook(() => useApiData<{ name: string }>('/api/current', {
      dataScopeKey: 'same', onSuccess: () => undefined,
    }));
    await waitFor(() => expect(result.current.data?.name).toBe('same business'));
    rerender();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('does not invoke a success callback after unmounting', async () => {
    let complete: (value: Response) => void = () => undefined;
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { complete = resolve; })));
    const onSuccess = vi.fn();
    const { unmount } = renderHook(() => useApiData<{ name: string }>('/api/current', { onSuccess }));
    unmount();
    await act(async () => { complete(response('too late')); });
    expect(onSuccess).not.toHaveBeenCalled();
  });
});
