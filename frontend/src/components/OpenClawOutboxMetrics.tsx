import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, RefreshCcw } from 'lucide-react';

type HealthResponse = {
  success: boolean;
  status?: 'ready' | 'degraded' | string;
  ready?: boolean;
  checks?: {
    token_configured: boolean;
    callbacks_enabled: boolean;
    dlq_count: number;
    retry_backlog: number;
    stuck_retry: number;
  };
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
  snapshot_id?: string | null;
  window_minutes?: number;
  error?: string;
};

type HealthTrendItem = {
  id: string;
  status: 'ready' | 'degraded' | string;
  ready: boolean;
  captured_at: string;
  checks?: {
    dlq_count?: number;
    stuck_retry?: number;
  };
};

type TrendResponse = {
  success: boolean;
  items?: HealthTrendItem[];
  count?: number;
  error?: string;
};

interface Props {
  businessId?: string;
}

export default function OpenClawOutboxMetrics({ businessId }: Props) {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [trend, setTrend] = useState<HealthTrendItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!businessId) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem('auth_token');
      const [healthRes, trendRes] = await Promise.all([
        fetch(
          `/api/capabilities/health?tenant_id=${encodeURIComponent(businessId)}&window_minutes=60`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
        fetch(
          `/api/capabilities/health/trend?tenant_id=${encodeURIComponent(businessId)}&window_minutes=720&limit=24`,
          { headers: { Authorization: `Bearer ${token}` } }
        ),
      ]);

      const healthJson: HealthResponse = await healthRes.json();
      const trendJson: TrendResponse = await trendRes.json();

      if (!healthRes.ok || !healthJson?.success) {
        throw new Error(healthJson?.error || `HTTP ${healthRes.status}`);
      }
      if (!trendRes.ok || !trendJson?.success) {
        throw new Error(trendJson?.error || `HTTP ${trendRes.status}`);
      }

      setData(healthJson);
      setTrend((trendJson.items || []).slice(0, 24));
    } catch (e: any) {
      setError(e?.message || 'Не удалось загрузить состояние интеграции ИИ-агентов');
    } finally {
      setLoading(false);
    }
  }, [businessId]);

  useEffect(() => {
    load();
  }, [load]);

  const metrics = data?.metrics;
  const checks = data?.checks;
  const alerts = data?.alerts || [];
  const hasAlerts = alerts.length > 0;
  const isReady = data?.status === 'ready' && !hasAlerts;
  const statusLabel = isReady ? 'Готово к работе' : 'Требует внимания';
  const statusClass = isReady
    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
    : 'bg-amber-50 border-amber-200 text-amber-800';

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">Связь ИИ-агентов с системой</div>
          <div className="text-xs text-gray-500">Статус интеграции OpenClaw ↔ LocalOS и доставка callback-событий</div>
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
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium ${statusClass}`}>
              {isReady ? <CheckCircle2 className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
              {statusLabel}
            </div>
            {data?.snapshot_id && (
              <div className="text-[11px] text-gray-500">snapshot: {String(data.snapshot_id).slice(0, 8)}</div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
            <MetricCell label="Sent" value={metrics?.sent ?? 0} />
            <MetricCell label="Retry" value={metrics?.retry ?? 0} />
            <MetricCell label="DLQ" value={metrics?.dlq ?? 0} />
            <MetricCell label="Pending" value={metrics?.pending ?? 0} />
            <MetricCell label="Stuck" value={metrics?.stuck_retry ?? 0} />
            <MetricCell label="Success %" value={`${metrics?.delivery_success_rate ?? 0}%`} />
          </div>

          <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-gray-500">Тренд состояния (последние 24 замера)</div>
            <div className="flex items-center gap-1 overflow-x-auto pb-1">
              {trend.length === 0 ? (
                <span className="text-xs text-gray-500">Нет данных тренда</span>
              ) : (
                trend.map((item) => {
                  const degraded = item.status !== 'ready' || Number(item.checks?.dlq_count || 0) > 0 || Number(item.checks?.stuck_retry || 0) > 0;
                  return (
                    <div
                      key={item.id}
                      title={`${item.captured_at} · ${item.status}`}
                      className={`h-5 w-3 rounded-sm ${degraded ? 'bg-amber-500' : 'bg-emerald-500'}`}
                    />
                  );
                })
              )}
            </div>
          </div>

          <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
            <MetricCell label="Token auth" value={checks?.token_configured ? 'ok' : 'missing'} />
            <MetricCell label="Dispatch" value={checks?.callbacks_enabled ? 'enabled' : 'disabled'} />
            <MetricCell label="DLQ / Stuck" value={`${checks?.dlq_count ?? 0} / ${checks?.stuck_retry ?? 0}`} />
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
