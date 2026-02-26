import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCcw } from 'lucide-react';

type MetricsResponse = {
  success: boolean;
  metrics?: {
    sent: number;
    retry: number;
    dlq: number;
    pending: number;
    sending: number;
    stuck_retry: number;
    total_recent: number;
    delivery_success_rate: number;
  };
  alerts?: Array<{
    code: string;
    severity: string;
    message: string;
  }>;
  error?: string;
};

interface Props {
  businessId?: string;
}

export default function OpenClawOutboxMetrics({ businessId }: Props) {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!businessId) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(
        `/api/capabilities/callbacks/metrics?tenant_id=${encodeURIComponent(businessId)}&window_minutes=60`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const json = await res.json();
      if (!res.ok || !json?.success) {
        throw new Error(json?.error || `HTTP ${res.status}`);
      }
      setData(json);
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить метрики callback');
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => {
    load();
  }, [load]);

  const metrics = data?.metrics;
  const alerts = data?.alerts || [];
  const hasAlerts = alerts.length > 0;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">OpenClaw Callback Health (60m)</div>
          <div className="text-xs text-gray-500">Доставка callback событий: sent/retry/dlq</div>
        </div>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          <RefreshCcw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Обновить
        </button>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
            <MetricCell label="Sent" value={metrics?.sent ?? 0} />
            <MetricCell label="Retry" value={metrics?.retry ?? 0} />
            <MetricCell label="DLQ" value={metrics?.dlq ?? 0} />
            <MetricCell label="Pending" value={metrics?.pending ?? 0} />
            <MetricCell label="Stuck" value={metrics?.stuck_retry ?? 0} />
            <MetricCell label="Success %" value={`${metrics?.delivery_success_rate ?? 0}%`} />
          </div>

          <div className="mt-3">
            {hasAlerts ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                <div className="mb-1 flex items-center gap-2 font-medium">
                  <AlertTriangle className="h-4 w-4" />
                  Алерты callback доставки
                </div>
                <ul className="space-y-1">
                  {alerts.map((a) => (
                    <li key={`${a.code}:${a.message}`}>[{a.severity}] {a.message}</li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                Callback доставка в норме
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function MetricCell({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-gray-100 bg-gray-50 px-2 py-2">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="text-base font-semibold text-gray-900">{value}</div>
    </div>
  );
}
