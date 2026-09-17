import { useLatestCallback } from '@/hooks/useLatestCallback';
import { browserBearerToken } from '@/lib/browserSessionFetch';
import { useEffect, useRef, useState } from 'react';

interface UseApiDataOptions<T, Input> {
  transform?: (data: Input) => T;
  onSuccess?: (data: T) => void;
  onError?: (error: string) => void;
  keepPreviousData?: boolean;
  dataScopeKey?: string | null;
}

export function useApiData<T, Input = T>(
  endpoint: string | null,
  options?: RequestInit & UseApiDataOptions<T, Input>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dataRef = useRef<T | null>(null);
  const scopeRef = useRef<string | null | undefined>(options?.dataScopeKey);

  const getOptions = useLatestCallback(() => options);
  const dataScopeKey = options?.dataScopeKey;
  useEffect(() => {
    const requestSettings = getOptions();
    const keepPreviousData = Boolean(requestSettings?.keepPreviousData);
    const scopeChanged = scopeRef.current !== requestSettings?.dataScopeKey;
    if (scopeChanged) {
      scopeRef.current = requestSettings?.dataScopeKey;
      dataRef.current = null;
      setData(null);
    }

    if (!endpoint) {
      dataRef.current = null;
      setData(null);
      setLoading(false);
      setRefreshing(false);
      setError(null);
      return;
    }

    const hasPreviousData = keepPreviousData && !scopeChanged && dataRef.current !== null;
    setLoading(!hasPreviousData);
    setRefreshing(hasPreviousData);
    setError(null);
    const controller = new AbortController();
    const {
      transform,
      onSuccess,
      onError,
      keepPreviousData: _keepPreviousData,
      dataScopeKey: _dataScopeKey,
      ...requestOptions
    } = requestSettings || {};

    const token = browserBearerToken();
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${token || ''}` },
      ...requestOptions,
      signal: controller.signal,
    })
      .then(async (res) => {
        if (!res.ok) {
          const errorData = await res.json().catch(() => ({ error: 'Ошибка загрузки' }));
          throw new Error(errorData.error || `HTTP ${res.status}`);
        }
        return res.json();
      })
      .then((responseData) => {
        if (controller.signal.aborted) return;
        if (responseData.success !== false) {
          const transformedData: T = transform
            ? transform(responseData.data || responseData)
            : responseData.data || responseData;
          dataRef.current = transformedData;
          setData(transformedData);
          onSuccess?.(transformedData);
        } else {
          const errorMsg = responseData.error || 'Ошибка загрузки';
          setError(errorMsg);
          onError?.(errorMsg);
        }
      })
      .catch((e) => {
        if (controller.signal.aborted) return;
        const errorMsg = e.message || 'Ошибка соединения с сервером';
        setError(errorMsg);
        onError?.(errorMsg);
      })
      .finally(() => {
        if (controller.signal.aborted) return;
        setLoading(false);
        setRefreshing(false);
      });

    return () => controller.abort();
  }, [endpoint, dataScopeKey, getOptions]);

  return { data, loading, refreshing, error };
}
