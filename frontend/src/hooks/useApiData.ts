import { useEffect, useRef, useState } from 'react';

interface UseApiDataOptions<T> {
  transform?: (data: any) => T;
  onSuccess?: (data: T) => void;
  onError?: (error: string) => void;
  keepPreviousData?: boolean;
  dataScopeKey?: string | null;
}

export function useApiData<T>(
  endpoint: string | null,
  options?: RequestInit & UseApiDataOptions<T>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dataRef = useRef<T | null>(null);
  const scopeRef = useRef<string | null | undefined>(options?.dataScopeKey);

  useEffect(() => {
    const keepPreviousData = Boolean(options?.keepPreviousData);
    const scopeChanged = scopeRef.current !== options?.dataScopeKey;
    if (scopeChanged) {
      scopeRef.current = options?.dataScopeKey;
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
    } = options || {};

    const token = localStorage.getItem('auth_token');
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
  }, [endpoint, options?.dataScopeKey]);

  return { data, loading, refreshing, error };
}
