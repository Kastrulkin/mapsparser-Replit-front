import { useState, useEffect } from 'react';

interface UseApiDataOptions<T> {
  transform?: (data: any) => T;
  onSuccess?: (data: T) => void;
  onError?: (error: string) => void;
}

export function useApiData<T>(
  endpoint: string | null,
  options?: RequestInit & UseApiDataOptions<T>
) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!endpoint) {
      setData(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    const token = localStorage.getItem('auth_token');
    fetch(endpoint, {
      headers: { Authorization: `Bearer ${token || ''}` },
      ...options
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
          const transformedData = options?.transform
            ? options.transform(responseData.data || responseData)
            : (responseData.data || responseData) as T;
          setData(transformedData);
          options?.onSuccess?.(transformedData);
        } else {
          const errorMsg = responseData.error || 'Ошибка загрузки';
          setError(errorMsg);
          options?.onError?.(errorMsg);
        }
      })
      .catch((e) => {
        const errorMsg = e.message || 'Ошибка соединения с сервером';
        setError(errorMsg);
        options?.onError?.(errorMsg);
      })
      .finally(() => setLoading(false));
  }, [endpoint]);

  return { data, loading, error };
}

