import { useEffect } from 'react';
import { useLatestCallback } from './useLatestCallback';

type PollingOptions<Result> = {
  enabled: boolean;
  scopeKey: string;
  intervalMs: number;
  request: (signal: AbortSignal) => Promise<Result>;
  onResult: (result: Result) => void;
  onError?: (error: unknown) => void;
  immediate?: boolean;
};

/** One request at a time; results from a previous scope never reach the view. */
export function usePolling<Result>({ enabled, scopeKey, intervalMs, request, onResult, onError, immediate = false }: PollingOptions<Result>) {
  const requestLatest = useLatestCallback(request);
  const receiveLatest = useLatestCallback(onResult);
  const rejectLatest = useLatestCallback((error: unknown) => onError?.(error));

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const result = await requestLatest(controller.signal);
        if (!controller.signal.aborted) receiveLatest(result);
      } catch (error) {
        if (!controller.signal.aborted) rejectLatest(error);
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(() => void poll(), intervalMs);
      }
    };
    if (immediate) void poll();
    else timer = setTimeout(() => void poll(), intervalMs);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [enabled, scopeKey, intervalMs, immediate, requestLatest, receiveLatest, rejectLatest]);
}
